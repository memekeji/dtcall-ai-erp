from rest_framework import serializers
from .models import MessageCategory, Message, MessageUserRelation, NotificationPreference
from apps.user.models import Admin
from apps.department.models import Department
import json
from django.db import models
from django.utils import timezone


class MessageCategorySerializer(serializers.ModelSerializer):
    """消息分类序列化器"""
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = MessageCategory
        fields = ['id', 'name', 'code', 'type', 'icon', 'description', 'sort_order', 'is_active', 'message_count', 'created_at']
        read_only_fields = ['created_at']
    
    def get_message_count(self, obj):
        """获取该分类的消息数量"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            return MessageUserRelation.objects.filter(
                message__category=obj,
                user=request.user
            ).count()
        return 0


class MessageCategorySimpleSerializer(serializers.ModelSerializer):
    """消息分类简单序列化器"""
    
    class Meta:
        model = MessageCategory
        fields = ['id', 'name', 'code', 'type', 'icon']


class MessageSerializer(serializers.ModelSerializer):
    """消息序列化器"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)
    sender_name = serializers.CharField(source='sender.username', read_only=True)
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
        fields = ['id', 'message', 'message_id', 'user', 'is_read', 'is_starred', 'read_time', 'created_at']
        read_only_fields = ['user', 'created_at']
    
    def validate_message_id(self, value):
        """验证消息ID是否存在"""
        if not Message.objects.filter(id=value).exists():
            raise serializers.ValidationError('消息不存在')
        return value


class MessageListSerializer(serializers.ModelSerializer):
    """消息列表序列化器（包含用户状态）"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_icon = serializers.CharField(source='category.icon', read_only=True)
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    sender_avatar = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()
    is_starred = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'title', 'content', 'priority',
            'category_name', 'category_icon',
            'sender_name', 'sender_avatar',
            'is_read', 'is_starred',
            'related_object_type', 'related_object_id', 'action_url',
            'created_at'
        ]
    
    def get_sender_avatar(self, obj):
        """获取发送者头像"""
        if obj.sender and obj.sender.thumb:
            return obj.sender.thumb
        return None
    
    def get_is_read(self, obj):
        """获取当前用户是否已读"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            relation = obj.user_relations.filter(user=request.user).first()
            return relation.is_read if relation else False
        return False
    
    def get_is_starred(self, obj):
        """获取当前用户是否标星"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            relation = obj.user_relations.filter(user=request.user).first()
            return relation.is_starred if relation else False
        return False


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
            raise serializers.ValidationError('广播消息必须指定目标用户或目标部门')
        
        if user_ids:
            existing_users = Admin.objects.filter(id__in=user_ids).values_list('id', flat=True)
            missing_users = set(user_ids) - set(existing_users)
            if missing_users:
                raise serializers.ValidationError(f'用户ID不存在: {list(missing_users)}')
        
        return attrs
    
    def create(self, validated_data):
        """创建消息"""
        from apps.department.models import Department
        
        user_ids = validated_data.pop('user_ids', [])
        department_ids = validated_data.pop('department_ids', [])
        
        message = Message.objects.create(**validated_data)
        
        all_user_ids = set(user_ids)
        
        if department_ids:
            department_users = Admin.objects.filter(
                models.Q(did__in=department_ids) |
                models.Q(secondary_departments__id__in=department_ids)
            ).values_list('id', flat=True).distinct()
            all_user_ids.update(department_users)
        
        if all_user_ids:
            relations = [
                MessageUserRelation(message=message, user_id=user_id)
                for user_id in all_user_ids
            ]
            MessageUserRelation.objects.bulk_create(relations)
        
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
            existing_ids = Message.objects.filter(id__in=value).values_list('id', flat=True)
            missing_ids = set(value) - set(existing_ids)
            if missing_ids:
                raise serializers.ValidationError(f'消息ID不存在: {list(missing_ids)}')
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
        existing_ids = Message.objects.filter(id__in=value).values_list('id', flat=True)
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
