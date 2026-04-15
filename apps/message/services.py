import json
import logging
from typing import List, Dict, Any
from django.db import transaction, models
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import MessageCategory, Message, MessageUserRelation
from apps.common.cache_service import MessageCache

logger = logging.getLogger(__name__)
User = get_user_model()


class MessageService:
    """消息服务类 - 提供消息创建和推送的统一接口"""

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
                relations = [
                    MessageUserRelation(message=message, user=user)
                    for user in all_users
                ]
                MessageUserRelation.objects.bulk_create(relations)

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
                MessageUserRelation.objects.bulk_create(relations)

            logger.info(f'消息创建成功: {message.id}, 发送给 {len(all_user_ids)} 个用户')
            return message

        except Exception as e:
            logger.error(f'创建消息失败: {str(e)}')
            raise

    @staticmethod
    def mark_as_read(message_id: int, user: User) -> bool:
        """标记消息为已读"""
        relation = MessageUserRelation.objects.filter(
            message_id=message_id,
            user=user
        ).first()
        if relation:
            relation.is_read = True
            relation.read_time = timezone.now()
            relation.save()
            MessageCache.invalidate_unread_count(user.id)
            return True
        return False

    @staticmethod
    def mark_all_as_read(user: User) -> int:
        """标记所有消息为已读"""
        now = timezone.now()
        count = MessageUserRelation.objects.filter(
            user=user,
            is_read=False
        ).update(is_read=True, read_time=now)
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

        count = MessageUserRelation.objects.filter(
            user=user, is_read=False).count()
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
            action_url=f'/approval/process/{approval.id}/'
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
            action_url=f'/approval/detail/{approval.id}/'
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
            action_url=f'/approval/detail/{approval.id}/'
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
            related_object_id=approval.id
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
