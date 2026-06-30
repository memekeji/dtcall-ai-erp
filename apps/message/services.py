import json
import logging
from typing import List, Dict, Any
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction, models
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    Conversation,
    ConversationMember,
    ConversationMessage,
    ConversationMessageReceipt,
    ConversationTaskLink,
    MessageCategory,
    Message,
    MessageUserRelation,
    NotificationPreference,
)
from apps.common.cache_service import MessageCache

logger = logging.getLogger(__name__)
User = get_user_model()


class ConversationService:
    """统一沟通会话服务"""

    SYSTEM_GROUP_COMPANY = 'company'
    SYSTEM_GROUP_DEPARTMENT = 'department'

    @staticmethod
    def build_direct_key(user_a, user_b) -> str:
        user_ids = sorted([int(user_a.id), int(user_b.id)])
        return f'{user_ids[0]}:{user_ids[1]}'

    @staticmethod
    def _ensure_member(conversation, user, role=ConversationMember.ROLE_MEMBER):
        member, created = ConversationMember.objects.get_or_create(
            conversation=conversation,
            user=user,
            defaults={'role': role},
        )
        update_fields = []
        if member.left_at is not None:
            member.left_at = None
            update_fields.append('left_at')
        if role == ConversationMember.ROLE_OWNER and member.role != role:
            member.role = role
            update_fields.append('role')
        if update_fields:
            member.save(update_fields=update_fields)
        return member

    @staticmethod
    def get_or_create_direct(user_a, user_b):
        """获取或创建两个用户之间唯一单聊会话"""
        if not user_a or not user_b:
            raise ValueError('单聊双方不能为空')
        if user_a.id == user_b.id:
            raise ValueError('不能与自己创建单聊会话')

        direct_key = ConversationService.build_direct_key(user_a, user_b)
        with transaction.atomic():
            conversation, _ = Conversation.objects.get_or_create(
                conversation_type=Conversation.TYPE_DIRECT,
                direct_key=direct_key,
                defaults={
                    'created_by': user_a,
                    'metadata': {
                        'member_ids': [
                            int(user_a.id),
                            int(user_b.id),
                        ]
                    },
                },
            )
            ConversationService._ensure_member(conversation, user_a)
            ConversationService._ensure_member(conversation, user_b)
        return conversation

    @staticmethod
    def create_group(owner, name: str, member_ids=None):
        """创建自由群聊，并将创建人设为群主"""
        if not owner:
            raise ValueError('群主不能为空')
        name = (name or '').strip()
        if not name:
            raise ValueError('群名称不能为空')

        member_ids = {int(user_id) for user_id in (member_ids or []) if user_id}
        member_ids.add(int(owner.id))
        users = list(User.objects.filter(id__in=member_ids, status=1))
        user_map = {user.id: user for user in users}
        if owner.id not in user_map:
            user_map[owner.id] = owner

        with transaction.atomic():
            conversation = Conversation.objects.create(
                conversation_type=Conversation.TYPE_GROUP,
                name=name,
                owner=owner,
                created_by=owner,
            )
            for user in user_map.values():
                role = (
                    ConversationMember.ROLE_OWNER
                    if user.id == owner.id else
                    ConversationMember.ROLE_MEMBER
                )
                ConversationMember.objects.create(
                    conversation=conversation,
                    user=user,
                    role=role,
                )
        return conversation

    @staticmethod
    def _system_metadata(group_type: str, **extra):
        metadata = {
            'system_group': group_type,
            'sync_managed': True,
        }
        metadata.update(extra)
        return metadata

    @staticmethod
    def get_or_create_company_group():
        """获取或创建公司全员群。"""
        conversation = Conversation.objects.filter(
            metadata__system_group=ConversationService.SYSTEM_GROUP_COMPANY,
        ).first()
        if conversation:
            update_fields = []
            if conversation.name != '公司全员群':
                conversation.name = '公司全员群'
                update_fields.append('name')
            if conversation.conversation_type != Conversation.TYPE_GROUP:
                conversation.conversation_type = Conversation.TYPE_GROUP
                update_fields.append('conversation_type')
            metadata = conversation.metadata or {}
            if not metadata.get('sync_managed'):
                metadata['sync_managed'] = True
                conversation.metadata = metadata
                update_fields.append('metadata')
            if update_fields:
                conversation.save(update_fields=update_fields + ['updated_at'])
            return conversation

        return Conversation.objects.create(
            conversation_type=Conversation.TYPE_GROUP,
            name='公司全员群',
            metadata=ConversationService._system_metadata(
                ConversationService.SYSTEM_GROUP_COMPANY,
            ),
        )

    @staticmethod
    def get_or_create_department_group(department):
        """获取或创建部门群。"""
        name = f'{department.name}群'
        conversation = Conversation.objects.filter(
            metadata__system_group=ConversationService.SYSTEM_GROUP_DEPARTMENT,
            metadata__department_id=department.id,
        ).first()
        if conversation:
            update_fields = []
            if conversation.name != name:
                conversation.name = name
                update_fields.append('name')
            if conversation.conversation_type != Conversation.TYPE_DEPARTMENT:
                conversation.conversation_type = Conversation.TYPE_DEPARTMENT
                update_fields.append('conversation_type')
            metadata = conversation.metadata or {}
            changed_metadata = False
            for key, value in ConversationService._system_metadata(
                ConversationService.SYSTEM_GROUP_DEPARTMENT,
                department_id=department.id,
            ).items():
                if metadata.get(key) != value:
                    metadata[key] = value
                    changed_metadata = True
            if changed_metadata:
                conversation.metadata = metadata
                update_fields.append('metadata')
            if update_fields:
                conversation.save(update_fields=update_fields + ['updated_at'])
            return conversation

        return Conversation.objects.create(
            conversation_type=Conversation.TYPE_DEPARTMENT,
            name=name,
            metadata=ConversationService._system_metadata(
                ConversationService.SYSTEM_GROUP_DEPARTMENT,
                department_id=department.id,
            ),
        )

    @staticmethod
    def _sync_managed_members(conversation, target_user_ids):
        target_user_ids = {int(user_id) for user_id in (target_user_ids or [])}
        now = timezone.now()
        existing = {
            member.user_id: member
            for member in ConversationMember.objects.filter(
                conversation=conversation,
            )
        }
        changed = {
            'joined': 0,
            'reactivated': 0,
            'removed': 0,
        }
        for user_id in target_user_ids:
            member = existing.get(user_id)
            if member is None:
                ConversationMember.objects.create(
                    conversation=conversation,
                    user_id=user_id,
                    role=ConversationMember.ROLE_MEMBER,
                )
                changed['joined'] += 1
            elif member.left_at is not None:
                member.left_at = None
                if member.role not in dict(ConversationMember.ROLE_CHOICES):
                    member.role = ConversationMember.ROLE_MEMBER
                    member.save(update_fields=['left_at', 'role'])
                else:
                    member.save(update_fields=['left_at'])
                changed['reactivated'] += 1

        for user_id, member in existing.items():
            if user_id not in target_user_ids and member.left_at is None:
                member.left_at = now
                member.save(update_fields=['left_at'])
                changed['removed'] += 1
        return changed

    @staticmethod
    def _department_member_ids(department_id):
        return set(
            User.objects.filter(
                did=department_id,
                status=1,
            ).values_list('id', flat=True).distinct()
        )

    @staticmethod
    def sync_system_conversations():
        """同步公司全员群和各部门群成员，可供人事变动后调用。"""
        from apps.department.models import Department

        with transaction.atomic():
            active_user_ids = set(
                User.objects.filter(status=1).values_list('id', flat=True)
            )
            company = ConversationService.get_or_create_company_group()
            company_changes = ConversationService._sync_managed_members(
                company,
                active_user_ids,
            )

            department_group_ids = []
            department_changes = {}
            departments = Department.objects.filter(status=1).order_by('sort', 'id')
            for department in departments:
                group = ConversationService.get_or_create_department_group(
                    department,
                )
                department_group_ids.append(group.id)
                department_changes[str(department.id)] = ConversationService._sync_managed_members(
                    group,
                    ConversationService._department_member_ids(department.id),
                )

            disabled_department_groups = Conversation.objects.filter(
                conversation_type=Conversation.TYPE_DEPARTMENT,
                metadata__system_group=ConversationService.SYSTEM_GROUP_DEPARTMENT,
            ).exclude(id__in=department_group_ids)
            for group in disabled_department_groups:
                ConversationService._sync_managed_members(group, set())

        return {
            'company_group_id': company.id,
            'department_group_ids': department_group_ids,
            'company_changes': company_changes,
            'department_changes': department_changes,
        }

    @staticmethod
    def _can_manage(conversation, actor) -> bool:
        if not actor or not actor.is_authenticated:
            return False
        if actor.is_superuser:
            return True
        return ConversationMember.objects.filter(
            conversation=conversation,
            user=actor,
            left_at__isnull=True,
            role__in=[
                ConversationMember.ROLE_OWNER,
                ConversationMember.ROLE_ADMIN,
            ],
        ).exists()

    @staticmethod
    def add_members(conversation, actor, user_ids):
        """群管理员添加成员"""
        if conversation.conversation_type == Conversation.TYPE_DIRECT:
            raise ValueError('单聊不支持添加成员')
        if not ConversationService._can_manage(conversation, actor):
            raise PermissionError('没有权限管理该会话')

        users = User.objects.filter(id__in=set(user_ids or []), status=1)
        members = []
        with transaction.atomic():
            for user in users:
                members.append(
                    ConversationService._ensure_member(conversation, user)
                )
        return members

    @staticmethod
    def remove_member(conversation, actor, user_id):
        """群管理员移除成员"""
        if conversation.conversation_type == Conversation.TYPE_DIRECT:
            raise ValueError('单聊不支持移除成员')
        if not ConversationService._can_manage(conversation, actor):
            raise PermissionError('没有权限管理该会话')

        relation = ConversationMember.objects.filter(
            conversation=conversation,
            user_id=user_id,
            left_at__isnull=True,
        ).first()
        if not relation:
            return False
        if relation.role == ConversationMember.ROLE_OWNER:
            raise ValueError('不能移除群主')
        relation.left_at = timezone.now()
        relation.save(update_fields=['left_at'])
        return True

    @staticmethod
    def set_conversation_pinned(conversation, user, is_pinned: bool):
        """设置当前用户对某个会话的置顶状态。"""
        member = ConversationMember.objects.filter(
            conversation=conversation,
            user=user,
            left_at__isnull=True,
        ).first()
        if member is None:
            raise PermissionError('用户不是该会话成员')
        member.is_pinned = bool(is_pinned)
        member.save(update_fields=['is_pinned'])
        return member

    @staticmethod
    def list_user_conversations(user):
        """列出当前用户可见会话"""
        return Conversation.objects.filter(
            member_relations__user=user,
            member_relations__left_at__isnull=True,
            is_active=True,
        ).annotate(
            current_user_pinned=models.Max(
                'member_relations__is_pinned',
                filter=models.Q(member_relations__user=user),
            )
        ).distinct().select_related(
            'last_message',
            'owner',
            'created_by',
        ).order_by(
            '-current_user_pinned',
            '-last_message_at',
            '-created_at',
        )


class ConversationMessageService:
    """会话消息发送与已读状态服务"""

    @staticmethod
    def group_name(conversation_id) -> str:
        return f'message_conversation_{conversation_id}'

    @staticmethod
    def _user_payload(user):
        if not user:
            return None
        return {
            'id': user.id,
            'username': user.username,
            'name': getattr(user, 'name', None) or user.username,
            'avatar': getattr(user, 'thumb', None),
        }

    @staticmethod
    def _message_payload(message):
        return {
            'id': message.id,
            'conversation': message.conversation_id,
            'sender': ConversationMessageService._user_payload(message.sender),
            'message_type': message.message_type,
            'content': message.content,
            'metadata': message.metadata,
            'reply_to': message.reply_to_id,
            'is_deleted': message.is_deleted,
            'created_at': message.created_at.isoformat() if message.created_at else None,
            'updated_at': message.updated_at.isoformat() if message.updated_at else None,
        }

    @staticmethod
    def _publish(conversation_id, event):
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        async_to_sync(channel_layer.group_send)(
            ConversationMessageService.group_name(conversation_id),
            event,
        )

    @staticmethod
    def ensure_member(conversation, user) -> ConversationMember:
        relation = ConversationMember.objects.filter(
            conversation=conversation,
            user=user,
            left_at__isnull=True,
        ).first()
        if not relation:
            raise PermissionError('用户不是该会话成员')
        return relation

    @staticmethod
    def _mentioned_user_ids(metadata) -> set:
        mention_ids = (metadata or {}).get('mentions') or []
        normalized_ids = set()
        for user_id in mention_ids:
            try:
                normalized_ids.add(int(user_id))
            except (TypeError, ValueError):
                continue
        return normalized_ids

    @staticmethod
    def _conversation_title(conversation) -> str:
        return conversation.name or conversation.get_conversation_type_display()

    @staticmethod
    def _notify_mentions(message, active_members) -> None:
        mentioned_ids = ConversationMessageService._mentioned_user_ids(
            message.metadata,
        )
        if not mentioned_ids:
            return

        active_member_ids = {
            member.user_id
            for member in active_members
            if member.user_id != message.sender_id
        }
        target_user_ids = mentioned_ids & active_member_ids
        if not target_user_ids:
            return

        sender_name = getattr(message.sender, 'name', None) or message.sender.username
        conversation_title = ConversationMessageService._conversation_title(
            message.conversation,
        )
        MessageService.send_notification(
            title='你在沟通中被@了',
            content=f'{sender_name} 在「{conversation_title}」中提到了你：{message.content}',
            category_code='comment',
            user_ids=list(target_user_ids),
            sender=message.sender,
            priority=3,
            related_object_type='conversation_message',
            related_object_id=message.id,
            action_url=f'/message/conversations/page/?conversation_id={message.conversation_id}',
        )

    @staticmethod
    def _create_message(
        conversation,
        sender,
        message_type: str,
        content: str,
        metadata=None,
        reply_to=None,
    ):
        ConversationMessageService.ensure_member(conversation, sender)

        with transaction.atomic():
            message = ConversationMessage.objects.create(
                conversation=conversation,
                sender=sender,
                message_type=message_type,
                content=content,
                metadata=metadata or {},
                reply_to=reply_to,
            )
            active_members = list(
                ConversationMember.objects.filter(
                    conversation=conversation,
                    left_at__isnull=True,
                ).select_related('user')
            )
            receipts = [
                ConversationMessageReceipt(message=message, user=member.user)
                for member in active_members
                if member.user_id != sender.id
            ]
            ConversationMessageReceipt.objects.bulk_create(
                receipts,
                ignore_conflicts=True,
            )
            ConversationMessageReceipt.objects.filter(
                message=message,
                user=sender,
            ).delete()
            conversation.last_message = message
            conversation.last_message_at = message.created_at
            conversation.save(update_fields=['last_message', 'last_message_at', 'updated_at'])
            ConversationMember.objects.filter(
                conversation=conversation,
                user=sender,
            ).update(last_read_message=message, last_read_at=message.created_at)
            ConversationMessageService._notify_mentions(message, active_members)
            MessageService.invalidate_user_unread_counts(
                [member.user_id for member in active_members]
            )
        ConversationMessageService._publish(
            conversation.id,
            {
                'type': 'conversation.message',
                'conversation_id': conversation.id,
                'message': ConversationMessageService._message_payload(message),
            },
        )
        return message

    @staticmethod
    def send_text(conversation, sender, content: str, metadata=None, reply_to=None):
        """发送文本消息并为其他成员创建未读回执"""
        content = (content or '').strip()
        if not content:
            raise ValueError('消息内容不能为空')
        return ConversationMessageService._create_message(
            conversation=conversation,
            sender=sender,
            message_type=ConversationMessage.TYPE_TEXT,
            content=content,
            metadata=metadata or {},
            reply_to=reply_to,
        )

    @staticmethod
    def send_attachment(
        conversation,
        sender,
        file_url: str,
        file_name: str,
        file_size: int,
        content_type: str = '',
        file_path: str = '',
        reply_to=None,
    ):
        """发送图片或文件附件消息，并复用会话未读回执逻辑。"""
        file_name = (file_name or '').strip()
        file_url = (file_url or '').strip()
        content_type = (content_type or '').strip()
        if not file_name or not file_url:
            raise ValueError('附件信息不能为空')

        message_type = (
            ConversationMessage.TYPE_IMAGE
            if content_type.startswith('image/')
            else ConversationMessage.TYPE_FILE
        )
        metadata = {
            'file_url': file_url,
            'file_name': file_name,
            'file_size': int(file_size or 0),
            'content_type': content_type,
        }
        if file_path:
            metadata['file_path'] = file_path

        return ConversationMessageService._create_message(
            conversation=conversation,
            sender=sender,
            message_type=message_type,
            content=file_name,
            metadata=metadata,
            reply_to=reply_to,
        )

    @staticmethod
    def get_unread_count(user) -> int:
        """获取用户所有会话未读消息数"""
        return ConversationMessageReceipt.objects.filter(
            user=user,
            status=ConversationMessageReceipt.STATUS_DELIVERED,
            message__is_deleted=False,
            message__conversation__member_relations__user=user,
            message__conversation__member_relations__left_at__isnull=True,
        ).distinct().count()

    @staticmethod
    def get_conversation_unread_count(conversation, user) -> int:
        """获取单个会话未读消息数"""
        ConversationMessageService.ensure_member(conversation, user)
        return ConversationMessageReceipt.objects.filter(
            user=user,
            message__conversation=conversation,
            status=ConversationMessageReceipt.STATUS_DELIVERED,
            message__is_deleted=False,
        ).count()

    @staticmethod
    def mark_conversation_read(conversation, user, through_message=None) -> int:
        """将会话消息标记为已读，并更新成员已读游标"""
        ConversationMessageService.ensure_member(conversation, user)
        queryset = ConversationMessageReceipt.objects.filter(
            user=user,
            message__conversation=conversation,
            status=ConversationMessageReceipt.STATUS_DELIVERED,
        )
        if through_message:
            queryset = queryset.filter(message_id__lte=through_message.id)

        now = timezone.now()
        message_ids = list(queryset.values_list('message_id', flat=True))
        count = queryset.update(
            status=ConversationMessageReceipt.STATUS_READ,
            read_at=now,
        )
        last_message = None
        if count:
            last_message = ConversationMessage.objects.filter(
                id__in=message_ids
            ).order_by('-created_at', '-id').first()
            ConversationMember.objects.filter(
                conversation=conversation,
                user=user,
            ).update(last_read_message=last_message, last_read_at=now)
            ConversationMessageService._publish(
                conversation.id,
                {
                    'type': 'conversation.read',
                    'conversation_id': conversation.id,
                    'user_id': user.id,
                    'read_count': count,
                    'last_read_message_id': last_message.id if last_message else None,
                    'read_at': now.isoformat(),
                },
            )
            MessageService.invalidate_user_unread_counts([user.id])
        return count


class MessageTaskService:
    """会话消息转项目任务服务"""

    @staticmethod
    def convert_to_task(
        message,
        creator,
        title: str = '',
        description: str = '',
        assignee_id=None,
        project_id=None,
        priority: int = 2,
        end_date=None,
    ):
        """将会话消息转换为项目任务并保留来源关联"""
        ConversationMessageService.ensure_member(message.conversation, creator)
        title = (title or '').strip() or message.content[:80] or '沟通消息任务'
        description = (description or '').strip()
        if not description:
            description = message.content

        from apps.project.models import Project, Task

        assignee = None
        if assignee_id:
            assignee = User.objects.filter(id=assignee_id, status=1).first()
            if assignee is None:
                raise ValueError('负责人不存在或已停用')

        project = None
        if project_id:
            project = Project.objects.filter(id=project_id, delete_time__isnull=True).first()
            if project is None:
                raise ValueError('项目不存在或已删除')

        with transaction.atomic():
            task = Task.objects.create(
                title=title,
                description=description,
                assignee=assignee,
                project=project,
                priority=priority or 2,
                end_date=end_date,
                creator=creator,
            )
            if assignee:
                task.participants.add(assignee)
            ConversationTaskLink.objects.get_or_create(
                message=message,
                task=task,
                defaults={'created_by': creator},
            )
            message.metadata = {
                **(message.metadata or {}),
                'converted_task_id': task.id,
            }
            message.save(update_fields=['metadata', 'updated_at'])
        return task


class MessageService:
    """消息服务类 - 提供消息创建和推送的统一接口"""

    CATEGORY_PREFERENCE_FIELDS = {
        'announcement': 'notify_announcement',
        'approval': 'notify_approval',
        'task': 'notify_task',
        'comment': 'notify_comment',
        'system': 'notify_system',
    }

    @staticmethod
    def invalidate_user_unread_counts(user_ids) -> None:
        """失效一组用户的未读数缓存"""
        for user_id in set(user_ids or []):
            if user_id:
                MessageCache.invalidate_unread_count(user_id)

    @staticmethod
    def _preference_field_for_category(category_code: str) -> str:
        return MessageService.CATEGORY_PREFERENCE_FIELDS.get(
            category_code,
            'notify_system'
        )

    @staticmethod
    def filter_user_ids_by_preferences(user_ids, category_code: str) -> set:
        """根据用户通知偏好过滤消息接收人"""
        user_ids = {user_id for user_id in (user_ids or []) if user_id}
        if not user_ids:
            return set()

        preference_field = MessageService._preference_field_for_category(
            category_code
        )
        disabled_ids = set(
            NotificationPreference.objects.filter(
                user_id__in=user_ids
            ).filter(
                models.Q(**{preference_field: False})
            ).values_list('user_id', flat=True)
        )
        return user_ids - disabled_ids

    @staticmethod
    def get_or_create_category(
            code: str,
            name: str,
            category_type: str,
            icon: str = 'layui-icon-notice') -> MessageCategory:
        """获取或创建消息分类"""
        category, created = MessageCategory.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'type': category_type,
                'icon': icon
            }
        )
        return category

    @staticmethod
    def send_broadcast_notification(
        title: str,
        content: str,
        category_code: str,
        sender: User = None,
        priority: int = 2,
        related_object_type: str = '',
        related_object_id: int = None,
        action_url: str = ''
    ) -> Message:
        """发送广播消息给所有用户"""
        try:
            category = MessageService.get_or_create_category(
                code=category_code, name=dict(
                    MessageCategory.TYPE_CHOICES).get(
                    category_code, '系统通知'), category_type=category_code)

            with transaction.atomic():
                message = Message.objects.create(
                    category=category,
                    user=None,
                    sender=sender,
                    title=title,
                    content=content,
                    priority=priority,
                    is_broadcast=True,
                    related_object_type=related_object_type,
                    related_object_id=related_object_id,
                    action_url=action_url
                )

                all_users = User.objects.filter(status=1)
                allowed_user_ids = MessageService.filter_user_ids_by_preferences(
                    all_users.values_list('id', flat=True),
                    category_code
                )
                all_users = all_users.filter(id__in=allowed_user_ids)
                relations = [
                    MessageUserRelation(message=message, user=user)
                    for user in all_users
                ]
                MessageUserRelation.objects.bulk_create(relations, ignore_conflicts=True)
                MessageService.invalidate_user_unread_counts(allowed_user_ids)

            logger.info(f'广播消息创建成功: {message.id}')
            return message

        except Exception as e:
            logger.error(f'创建广播消息失败: {str(e)}')
            raise

    @staticmethod
    def send_notification(
        title: str,
        content: str,
        category_code: str,
        user_ids: List[int] = None,
        department_ids: List[int] = None,
        sender: User = None,
        priority: int = 2,
        related_object_type: str = '',
        related_object_id: int = None,
        action_url: str = ''
    ) -> Message:
        """发送通知给指定用户或部门"""
        try:
            category = MessageService.get_or_create_category(
                code=category_code, name=dict(
                    MessageCategory.TYPE_CHOICES).get(
                    category_code, '系统通知'), category_type=category_code)

            all_user_ids = set(user_ids or [])

            if department_ids:
                department_users = User.objects.filter(
                    models.Q(did__in=department_ids) |
                    models.Q(secondary_departments__id__in=department_ids)
                ).values_list('id', flat=True).distinct()
                all_user_ids.update(department_users)

            if not all_user_ids:
                logger.warning('没有指定目标用户，消息未发送')
                return None

            all_user_ids = MessageService.filter_user_ids_by_preferences(
                all_user_ids,
                category_code
            )

            if not all_user_ids:
                logger.info('目标用户均关闭了当前类型通知，消息未发送')
                return None

            target_users_json = json.dumps(list(all_user_ids))

            with transaction.atomic():
                message = Message.objects.create(
                    category=category,
                    user=None,
                    sender=sender,
                    title=title,
                    content=content,
                    priority=priority,
                    is_broadcast=False,
                    target_users=target_users_json,
                    target_departments=json.dumps(department_ids or []),
                    related_object_type=related_object_type,
                    related_object_id=related_object_id,
                    action_url=action_url
                )

                relations = [
                    MessageUserRelation(message=message, user_id=user_id)
                    for user_id in all_user_ids
                ]
                MessageUserRelation.objects.bulk_create(relations, ignore_conflicts=True)
                MessageService.invalidate_user_unread_counts(all_user_ids)

            logger.info(f'消息创建成功: {message.id}, 发送给 {len(all_user_ids)} 个用户')
            return message

        except Exception as e:
            logger.error(f'创建消息失败: {str(e)}')
            raise

    @staticmethod
    def mark_as_read(message_id: int, user: User) -> bool:
        """标记消息为已读"""
        updated = MessageUserRelation.objects.filter(
            message_id=message_id,
            user=user,
            is_read=False
        ).update(is_read=True, read_time=timezone.now())
        if updated:
            MessageCache.invalidate_unread_count(user.id)
            return True
        return MessageUserRelation.objects.filter(
            message_id=message_id,
            user=user,
            is_read=True
        ).exists()

    @staticmethod
    def mark_as_unread(message_id: int, user: User) -> bool:
        """标记消息为未读"""
        updated = MessageUserRelation.objects.filter(
            message_id=message_id,
            user=user,
            is_read=True
        ).update(is_read=False, read_time=None)
        if updated:
            MessageCache.invalidate_unread_count(user.id)
            return True
        return MessageUserRelation.objects.filter(
            message_id=message_id,
            user=user,
            is_read=False
        ).exists()

    @staticmethod
    def mark_all_as_read(user: User) -> int:
        """标记所有通知和在线沟通消息为已读"""
        now = timezone.now()
        notification_count = MessageUserRelation.objects.filter(
            user=user,
            is_read=False
        ).update(is_read=True, read_time=now)

        conversation_ids = list(
            Conversation.objects.filter(
                messages__receipts__user=user,
                messages__receipts__status=ConversationMessageReceipt.STATUS_DELIVERED,
                messages__is_deleted=False,
                member_relations__user=user,
                member_relations__left_at__isnull=True,
            ).values_list('id', flat=True).distinct()
        )
        conversation_count = 0
        for conversation in Conversation.objects.filter(id__in=conversation_ids):
            conversation_count += ConversationMessageService.mark_conversation_read(
                conversation,
                user,
            )

        count = notification_count + conversation_count
        if count > 0:
            MessageCache.invalidate_unread_count(user.id)
        return count

    @staticmethod
    def toggle_star(message_id: int, user: User) -> bool:
        """切换标星状态"""
        relation = MessageUserRelation.objects.filter(
            message_id=message_id,
            user=user
        ).first()
        if relation:
            relation.is_starred = not relation.is_starred
            relation.save()
            return relation.is_starred
        return False

    @staticmethod
    def get_unread_count(user: User) -> int:
        """获取未读消息数量"""
        cached_count = MessageCache.get_unread_count(user.id)
        if cached_count is not None:
            return cached_count

        notification_count = MessageUserRelation.objects.filter(
            user=user, is_read=False).count()
        conversation_count = ConversationMessageService.get_unread_count(user)
        count = notification_count + conversation_count
        MessageCache.set_unread_count(user.id, count)
        return count

    @staticmethod
    def get_user_messages(
        user: User,
        category_type: str = None,
        is_read: bool = None,
        is_starred: bool = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """获取用户消息列表"""
        relations = MessageUserRelation.objects.filter(
            user=user).select_related(
            'message__category', 'message__sender')

        if category_type:
            relations = relations.filter(message__category__type=category_type)

        if is_read is not None:
            relations = relations.filter(is_read=is_read)

        if is_starred is not None:
            relations = relations.filter(is_starred=is_starred)

        total = relations.count()
        offset = (page - 1) * page_size
        relations = relations[offset:offset + page_size]

        messages = []
        for relation in relations:
            msg = relation.message
            messages.append({
                'id': msg.id,
                'title': msg.title,
                'content': msg.content,
                'category': {
                    'code': msg.category.code if msg.category else '',
                    'name': msg.category.name if msg.category else '',
                    'icon': msg.category.icon if msg.category else ''
                },
                'sender': {
                    'id': msg.sender.id if msg.sender else None,
                    'name': msg.sender.username if msg.sender else '系统',
                    'avatar': msg.sender.thumb if msg.sender else None
                } if msg.sender else None,
                'is_read': relation.is_read,
                'is_starred': relation.is_starred,
                'read_time': relation.read_time,
                'priority': msg.priority,
                'action_url': msg.action_url,
                'created_at': msg.created_at
            })

        return {
            'messages': messages,
            'total': total,
            'page': page,
            'page_size': page_size
        }


class NoticeNotificationService:
    """公告通知服务 - 处理公告相关消息推送（基于 Notice 模型）"""

    @staticmethod
    def notify_new_notice(notice, sender: User = None):
        """新公告发布通知"""
        MessageService.send_broadcast_notification(
            title=f'新公告: {notice.title}',
            content=notice.content[:200] +
            '...' if len(notice.content) > 200 else notice.content,
            category_code='announcement',
            sender=sender,
            priority=3,
            related_object_type='notice',
            related_object_id=notice.id,
            action_url=f'/system/admin_office/notice/{notice.id}/'
        )

    @staticmethod
    def notify_notice_update(notice, sender: User = None):
        """公告更新通知"""
        MessageService.send_broadcast_notification(
            title=f'公告更新: {notice.title}',
            content='公告内容已更新，请查阅。',
            category_code='announcement',
            sender=sender,
            priority=2,
            related_object_type='notice',
            related_object_id=notice.id,
            action_url=f'/system/admin_office/notice/{notice.id}/'
        )


class ApprovalNotificationService:
    """审批通知服务 - 处理审批相关消息推送"""

    @staticmethod
    def notify_pending_approval(
            approval,
            reviewer_ids: List[int],
            sender: User = None):
        """待审批通知 - 通知审批人"""
        MessageService.send_notification(
            title=f'待审批: {approval.title}',
            content=f'您有一条新的审批申请需要处理。',
            category_code='approval',
            user_ids=reviewer_ids,
            sender=sender,
            priority=3,
            related_object_type='approval',
            related_object_id=approval.id,
            action_url=f'/approval/{approval.id}/process/'
        )

    @staticmethod
    def notify_approval_completed(
            approval,
            applicant_id: int,
            status: str,
            reviewer_name: str = '',
            sender: User = None):
        """审批完成通知 - 通知申请人"""
        status_text = {
            'approved': '已通过',
            'rejected': '已拒绝',
            'cancelled': '已取消'
        }.get(status, status)

        MessageService.send_notification(
            title=f'审批结果: {approval.title}',
            content=f'您的审批申请已被 {reviewer_name} {status_text}。',
            category_code='approval',
            user_ids=[applicant_id],
            sender=sender,
            priority=3 if status == 'rejected' else 2,
            related_object_type='approval',
            related_object_id=approval.id,
            action_url=f'/approval/{approval.id}/'
        )

    @staticmethod
    def notify_cc(approval, cc_user_ids: List[int], sender: User = None):
        """抄送通知 - 通知抄送人"""
        MessageService.send_notification(
            title=f'审批抄送: {approval.title}',
            content=f'您收到一份审批抄送申请。',
            category_code='approval',
            user_ids=cc_user_ids,
            sender=sender,
            priority=2,
            related_object_type='approval',
            related_object_id=approval.id,
            action_url=f'/approval/{approval.id}/'
        )

    @staticmethod
    def notify_approval_comment(
            approval,
            user_id: int,
            commenter_name: str,
            comment: str,
            sender: User = None):
        """审批评论/意见通知"""
        MessageService.send_notification(
            title=f'审批意见: {approval.title}',
            content=f'{commenter_name} 对审批发表了意见: {comment[:100]}...',
            category_code='approval',
            user_ids=[user_id],
            sender=sender,
            priority=2,
            related_object_type='approval_comment',
            related_object_id=approval.id,
            action_url=f'/approval/{approval.id}/'
        )


class TaskNotificationService:
    """任务通知服务 - 处理任务相关消息推送"""

    @staticmethod
    def notify_task_created(
            task,
            assignee_ids: List[int],
            sender: User = None):
        """任务创建通知 - 通知任务负责人"""
        MessageService.send_notification(
            title=f'新任务: {task.title}',
            content=task.description[:200] + '...' if task.description and len(
                task.description) > 200 else (task.description or ''),
            category_code='task',
            user_ids=assignee_ids,
            sender=sender,
            priority=3,
            related_object_type='task',
            related_object_id=task.id,
            action_url=f'/task/detail/{task.id}/'
        )

    @staticmethod
    def notify_task_assigned(
            task,
            assignee_id: int,
            assigner_name: str = '',
            sender: User = None):
        """任务分配通知 - 通知被分配人"""
        MessageService.send_notification(
            title=f'任务分配: {task.title}',
            content=f'{assigner_name} 将任务分配给您。',
            category_code='task',
            user_ids=[assignee_id],
            sender=sender,
            priority=3,
            related_object_type='task',
            related_object_id=task.id,
            action_url=f'/task/detail/{task.id}/'
        )

    @staticmethod
    def notify_task_status_changed(
            task,
            user_id: int,
            status: str,
            changer_name: str = '',
            sender: User = None):
        """任务状态变更通知"""
        status_text = {
            'in_progress': '进行中',
            'completed': '已完成',
            'cancelled': '已取消',
            'paused': '已暂停'
        }.get(status, status)

        MessageService.send_notification(
            title=f'任务状态变更: {task.title}',
            content=f'{changer_name} 将任务状态更新为: {status_text}',
            category_code='task',
            user_ids=[user_id],
            sender=sender,
            priority=2,
            related_object_type='task',
            related_object_id=task.id,
            action_url=f'/task/detail/{task.id}/'
        )

    @staticmethod
    def notify_task_deadline(
            task,
            user_id: int,
            deadline_str: str,
            sender: User = None):
        """任务截止日期提醒"""
        MessageService.send_notification(
            title=f'任务截止提醒: {task.title}',
            content=f'任务 "{task.title}" 截止日期为: {deadline_str}，请及时处理。',
            category_code='task',
            user_ids=[user_id],
            sender=sender,
            priority=4,
            related_object_type='task',
            related_object_id=task.id,
            action_url=f'/task/detail/{task.id}/'
        )

    @staticmethod
    def notify_task_comment(
            task,
            user_id: int,
            commenter_name: str,
            comment: str,
            sender: User = None):
        """任务评论通知"""
        MessageService.send_notification(
            title=f'任务评论: {task.title}',
            content=f'{commenter_name} 评论了任务: {comment[:100]}...',
            category_code='comment',
            user_ids=[user_id],
            sender=sender,
            priority=2,
            related_object_type='task_comment',
            related_object_id=task.id,
            action_url=f'/task/detail/{task.id}/'
        )


class SystemNotificationService:
    """系统通知服务 - 处理系统级消息推送"""

    @staticmethod
    def notify_system_maintenance(
            scheduled_time: str,
            duration: str,
            sender: User = None):
        """系统维护通知"""
        MessageService.send_broadcast_notification(
            title='系统维护通知',
            content=f'系统将于 {scheduled_time} 进行维护，预计持续 {duration}，请提前做好准备。',
            category_code='system',
            sender=sender,
            priority=4,
            action_url='/system/notice/'
        )

    @staticmethod
    def notify_policy_update(
            policy_title: str,
            summary: str,
            sender: User = None):
        """政策/制度更新通知"""
        MessageService.send_broadcast_notification(
            title=f'制度更新: {policy_title}',
            content=summary,
            category_code='system',
            sender=sender,
            priority=3,
            action_url='/system/policy/'
        )
