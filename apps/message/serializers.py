from rest_framework import serializers
from .models import (
    Conversation,
    ConversationMember,
    ConversationMessage,
    ConversationMessageReceipt,
    MessageCategory,
    Message,
    MessageUserRelation,
    NotificationPreference,
)
from apps.user.models import Admin
from apps.message.services import MessageService
import json
from django.db import models


class MessageCategorySerializer(serializers.ModelSerializer):
    """消息分类序列化器"""

    class Meta:
        model = MessageCategory
        fields = [
            'id',
            'name',
            'code',
            'type',
            'icon',
            'description',
            'sort_order',
            'is_active',
            'created_at']
        read_only_fields = ['created_at']


class MessageSerializer(serializers.ModelSerializer):
    """消息序列化器"""
    category_name = serializers.CharField(
        source='category.name', read_only=True)
    category_code = serializers.CharField(
        source='category.code', read_only=True)
    sender_name = serializers.CharField(
        source='sender.username', read_only=True)
    sender_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'category', 'category_name', 'category_code',
            'sender', 'sender_name', 'sender_avatar',
            'title', 'content', 'priority', 'is_broadcast',
            'target_users', 'target_departments',
            'related_object_type', 'related_object_id', 'action_url',
            'expire_time', 'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']

    def get_sender_avatar(self, obj):
        """获取发送者头像"""
        if obj.sender and obj.sender.thumb:
            return obj.sender.thumb
        return None

    def validate_target_users(self, value):
        """验证目标用户格式"""
        if value:
            try:
                json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError('目标用户必须是有效的JSON数组格式')
        return value

    def validate_target_departments(self, value):
        """验证目标部门格式"""
        if value:
            try:
                json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError('目标部门必须是有效的JSON数组格式')
        return value


class MessageUserRelationSerializer(serializers.ModelSerializer):
    """用户消息关系序列化器"""
    message = MessageSerializer(read_only=True)
    message_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = MessageUserRelation
        fields = [
            'id',
            'message',
            'message_id',
            'user',
            'is_read',
            'is_starred',
            'read_time',
            'created_at']
        read_only_fields = ['user', 'created_at']

    def validate_message_id(self, value):
        """验证消息ID是否存在"""
        if not Message.objects.filter(id=value).exists():
            raise serializers.ValidationError('消息不存在')
        return value


class MessageListSerializer(serializers.ModelSerializer):
    """消息列表序列化器（包含用户状态）"""
    category_name = serializers.CharField(
        source='category.name', read_only=True)
    category_icon = serializers.CharField(
        source='category.icon', read_only=True)
    sender_name = serializers.CharField(
        source='sender.username', read_only=True)
    sender_avatar = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    sender = serializers.SerializerMethodField()
    user_relation = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()
    is_starred = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'title', 'content', 'priority',
            'category', 'category_name', 'category_icon',
            'sender', 'sender_name', 'sender_avatar',
            'user_relation', 'is_read', 'is_starred',
            'related_object_type', 'related_object_id', 'action_url',
            'created_at'
        ]

    def get_category(self, obj):
        """获取分类对象（兼容消息中心模板）"""
        if obj.category:
            return {
                'id': obj.category.id,
                'name': obj.category.name,
                'code': obj.category.code,
                'type': obj.category.type,
                'icon': obj.category.icon,
            }
        return None

    def get_sender_avatar(self, obj):
        """获取发送者头像"""
        if obj.sender and obj.sender.thumb:
            return obj.sender.thumb
        return None

    def get_sender(self, obj):
        """获取发送者对象（兼容模板）"""
        if obj.sender:
            return {
                'id': obj.sender.id,
                'username': obj.sender.username,
                'name': getattr(
                    obj.sender,
                    'name',
                    obj.sender.username),
                'avatar': obj.sender.thumb if hasattr(
                    obj.sender,
                    'thumb') else None}
        return None

    def get_user_relation(self, obj):
        """获取当前用户的消息关系"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            relation = obj.user_relations.filter(user=request.user).first()
            if relation:
                return {
                    'is_read': relation.is_read,
                    'is_starred': relation.is_starred,
                    'read_time': relation.read_time
                }
        return {'is_read': False, 'is_starred': False, 'read_time': None}

    def get_is_read(self, obj):
        """获取当前用户是否已读（兼容旧模板）"""
        return self.get_user_relation(obj).get('is_read', False)

    def get_is_starred(self, obj):
        """获取当前用户是否标星（兼容旧模板）"""
        return self.get_user_relation(obj).get('is_starred', False)


class MessageCreateSerializer(serializers.ModelSerializer):
    """创建消息序列化器"""
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        help_text='目标用户ID列表'
    )
    department_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        help_text='目标部门ID列表'
    )

    class Meta:
        model = Message
        fields = [
            'category', 'title', 'content', 'priority',
            'is_broadcast', 'user_ids', 'department_ids',
            'related_object_type', 'related_object_id', 'action_url',
            'expire_time'
        ]

    def validate(self, attrs):
        """验证消息创建参数"""
        is_broadcast = attrs.get('is_broadcast', False)
        user_ids = attrs.get('user_ids', [])
        department_ids = attrs.get('department_ids', [])

        if not is_broadcast and not user_ids and not department_ids:
            raise serializers.ValidationError('非广播消息必须指定目标用户或目标部门')

        if user_ids:
            existing_users = Admin.objects.filter(
                id__in=user_ids).values_list(
                'id', flat=True)
            missing_users = set(user_ids) - set(existing_users)
            if missing_users:
                raise serializers.ValidationError(
                    f'用户ID不存在: {list(missing_users)}')

        return attrs

    def create(self, validated_data):
        """创建消息"""
        user_ids = validated_data.pop('user_ids', [])
        department_ids = validated_data.pop('department_ids', [])
        sender = validated_data.pop('sender', self.context['request'].user)
        is_broadcast = validated_data.get('is_broadcast', False)

        if is_broadcast:
            all_user_ids = set(Admin.objects.filter(status=1).values_list('id', flat=True))
        else:
            all_user_ids = set(user_ids)
            if department_ids:
                department_users = Admin.objects.filter(
                    models.Q(did__in=department_ids) |
                    models.Q(secondary_departments__id__in=department_ids)
                ).values_list('id', flat=True).distinct()
                all_user_ids.update(department_users)

        category_code = validated_data['category'].code if validated_data.get('category') else 'system'
        all_user_ids = MessageService.filter_user_ids_by_preferences(
            all_user_ids,
            category_code
        )

        message = Message.objects.create(
            sender=sender,
            target_users=json.dumps(list(all_user_ids)),
            target_departments=json.dumps(department_ids),
            **validated_data
        )

        if all_user_ids:
            relations = [
                MessageUserRelation(message=message, user_id=user_id)
                for user_id in all_user_ids
            ]
            MessageUserRelation.objects.bulk_create(relations, ignore_conflicts=True)
            MessageService.invalidate_user_unread_counts(all_user_ids)

        return message


class MessageMarkReadSerializer(serializers.Serializer):
    """标记已读序列化器"""
    message_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text='消息ID列表，为空则标记所有消息'
    )

    def validate_message_ids(self, value):
        """验证消息ID列表"""
        if value:
            existing_ids = Message.objects.filter(
                id__in=value).values_list(
                'id', flat=True)
            missing_ids = set(value) - set(existing_ids)
            if missing_ids:
                raise serializers.ValidationError(
                    f'消息ID不存在: {list(missing_ids)}')
        return value


class MessageStarSerializer(serializers.Serializer):
    """标星消息序列化器"""
    message_id = serializers.IntegerField(required=True, help_text='消息ID')
    is_starred = serializers.BooleanField(required=True, help_text='是否标星')


class MessageBatchOperationSerializer(serializers.Serializer):
    """批量操作序列化器"""
    message_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        help_text='消息ID列表'
    )
    operation = serializers.ChoiceField(
        choices=['read', 'unread', 'star', 'unstar', 'delete'],
        required=True,
        help_text='操作类型'
    )

    def validate_message_ids(self, value):
        """验证消息ID列表"""
        if not value:
            raise serializers.ValidationError('消息ID列表不能为空')
        existing_ids = Message.objects.filter(
            id__in=value).values_list(
            'id', flat=True)
        missing_ids = set(value) - set(existing_ids)
        if missing_ids:
            raise serializers.ValidationError(f'消息ID不存在: {list(missing_ids)}')
        return value


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """用户通知偏好序列化器"""

    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'enable_email', 'enable_browser',
            'quiet_hours_start', 'quiet_hours_end',
            'notify_announcement', 'notify_approval', 'notify_task',
            'notify_comment', 'notify_system',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class MessageStatsSerializer(serializers.Serializer):
    """消息统计序列化器"""
    total_count = serializers.IntegerField(help_text='消息总数')
    unread_count = serializers.IntegerField(help_text='未读消息数')
    starred_count = serializers.IntegerField(help_text='标星消息数')
    category_stats = serializers.DictField(help_text='各分类消息统计')


class ConversationUserSerializer(serializers.ModelSerializer):
    """会话用户摘要"""
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Admin
        fields = ['id', 'username', 'name', 'avatar']

    def get_name(self, obj):
        return getattr(obj, 'name', None) or obj.username

    def get_avatar(self, obj):
        return getattr(obj, 'thumb', None)


class ConversationMemberSerializer(serializers.ModelSerializer):
    """会话成员序列化器"""
    user = ConversationUserSerializer(read_only=True)

    class Meta:
        model = ConversationMember
        fields = [
            'id', 'user', 'role', 'is_muted', 'is_pinned',
            'is_archived', 'last_read_message', 'last_read_at',
            'joined_at', 'left_at',
        ]
        read_only_fields = fields


class ConversationMessageReceiptSerializer(serializers.ModelSerializer):
    """消息回执序列化器"""
    user = ConversationUserSerializer(read_only=True)
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = ConversationMessageReceipt
        fields = [
            'id', 'user', 'status', 'is_read', 'delivered_at', 'read_at',
        ]
        read_only_fields = fields


class ConversationMessageSerializer(serializers.ModelSerializer):
    """会话消息序列化器"""
    sender = ConversationUserSerializer(read_only=True)
    metadata = serializers.SerializerMethodField()
    receipts = ConversationMessageReceiptSerializer(many=True, read_only=True)
    reply_to_message = serializers.SerializerMethodField()
    task_links = serializers.SerializerMethodField()

    class Meta:
        model = ConversationMessage
        fields = [
            'id', 'conversation', 'sender', 'message_type', 'content',
            'metadata', 'reply_to', 'reply_to_message', 'is_deleted',
            'receipts', 'task_links', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_metadata(self, obj):
        metadata = dict(obj.metadata or {})
        mention_ids = metadata.get('mentions') or []
        if mention_ids:
            mention_users = Admin.objects.filter(id__in=mention_ids, status=1)
            metadata['mention_users'] = ConversationUserSerializer(
                mention_users,
                many=True,
            ).data
        return metadata

    def get_reply_to_message(self, obj):
        if not obj.reply_to:
            return None
        sender = obj.reply_to.sender
        return {
            'id': obj.reply_to.id,
            'content': obj.reply_to.content,
            'message_type': obj.reply_to.message_type,
            'sender': ConversationUserSerializer(sender).data if sender else None,
            'created_at': obj.reply_to.created_at,
        }

    def get_task_links(self, obj):
        return [
            {
                'id': link.id,
                'task_id': link.task_id,
                'task_title': link.task.title,
                'created_at': link.created_at,
            }
            for link in obj.task_links.select_related('task')
        ]


class ConversationSerializer(serializers.ModelSerializer):
    """沟通会话序列化器"""
    members = serializers.SerializerMethodField()
    member_ids = serializers.SerializerMethodField()
    last_message = ConversationMessageSerializer(read_only=True)
    unread_count = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    is_pinned = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'conversation_type', 'name', 'display_name', 'direct_key',
            'owner', 'created_by', 'member_ids', 'members', 'last_message',
            'last_message_at', 'unread_count', 'is_pinned', 'metadata', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def _active_members(self, obj):
        prefetched = getattr(obj, '_prefetched_objects_cache', {})
        if 'member_relations' in prefetched:
            return [
                member for member in prefetched['member_relations']
                if member.left_at is None
            ]
        return obj.member_relations.filter(
            left_at__isnull=True
        ).select_related('user')

    def get_members(self, obj):
        return ConversationMemberSerializer(
            self._active_members(obj),
            many=True,
            context=self.context,
        ).data

    def get_member_ids(self, obj):
        return [member.user_id for member in self._active_members(obj)]

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        return ConversationMessageReceipt.objects.filter(
            user=request.user,
            message__conversation=obj,
            status=ConversationMessageReceipt.STATUS_DELIVERED,
            message__is_deleted=False,
        ).count()

    def get_is_pinned(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        annotated = getattr(obj, 'current_user_pinned', None)
        if annotated is not None:
            return bool(annotated)
        return ConversationMember.objects.filter(
            conversation=obj,
            user=request.user,
            left_at__isnull=True,
            is_pinned=True,
        ).exists()

    def get_display_name(self, obj):
        if obj.name:
            return obj.name
        request = self.context.get('request')
        members = self._active_members(obj)
        if obj.conversation_type == Conversation.TYPE_DIRECT and request:
            for member in members:
                if member.user_id != request.user.id:
                    return getattr(member.user, 'name', None) or member.user.username
        return obj.get_conversation_type_display()


class ConversationDirectSerializer(serializers.Serializer):
    """单聊创建参数"""
    user_id = serializers.IntegerField()

    def validate_user_id(self, value):
        request = self.context.get('request')
        if request and request.user.id == value:
            raise serializers.ValidationError('不能与自己创建单聊会话')
        if not Admin.objects.filter(id=value, status=1).exists():
            raise serializers.ValidationError('用户不存在或已停用')
        return value


class ConversationCreateGroupSerializer(serializers.Serializer):
    """群聊创建参数"""
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    member_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('群名称不能为空')
        return value.strip()

    def validate_member_ids(self, value):
        ids = {int(user_id) for user_id in value or []}
        if not ids:
            return []
        existing_ids = set(
            Admin.objects.filter(id__in=ids, status=1).values_list('id', flat=True)
        )
        missing = ids - existing_ids
        if missing:
            raise serializers.ValidationError(f'用户不存在或已停用: {sorted(missing)}')
        return sorted(ids)


class ConversationSendMessageSerializer(serializers.Serializer):
    """发送会话消息参数"""
    content = serializers.CharField(trim_whitespace=True, required=False, allow_blank=True)
    message_type = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)
    reply_to = serializers.IntegerField(required=False, allow_null=True)

    def validate_content(self, value):
        return value.strip()

    def validate(self, attrs):
        metadata = attrs.get('metadata') or {}
        content = (attrs.get('content') or '').strip()
        message_type = (attrs.get('message_type') or '').strip()
        if not content:
            if metadata.get('type') == 'collaboration_card':
                module_name = metadata.get('module_name') or metadata.get('module') or '协同'
                title = metadata.get('title') or metadata.get('name') or f'#{metadata.get("item_id", "")}'
                attrs['content'] = f'[{module_name}] {title}'.strip()
                return attrs
            if message_type == 'card' and metadata.get('module'):
                module_name = metadata.get('module_name') or metadata.get('module') or '协同'
                title = metadata.get('title') or metadata.get('name') or f'#{metadata.get("item_id", "")}'
                attrs['content'] = f'[{module_name}] {title}'.strip()
                return attrs
            raise serializers.ValidationError({'content': '消息内容不能为空'})
        attrs['content'] = content
        return attrs

    def validate_reply_to(self, value):
        if not value:
            return value
        conversation = self.context.get('conversation')
        if not ConversationMessage.objects.filter(
            id=value,
            conversation=conversation,
            is_deleted=False,
        ).exists():
            raise serializers.ValidationError('引用消息不存在')
        return value
