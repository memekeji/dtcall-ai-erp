from django.shortcuts import render
from django.db.models import Q, Count
from django.utils import timezone
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
import json
import logging

from .models import MessageCategory, Message, MessageUserRelation, NotificationPreference
from .serializers import (
    MessageCategorySerializer, MessageCategorySimpleSerializer,
    MessageSerializer, MessageListSerializer, MessageCreateSerializer,
    MessageUserRelationSerializer, MessageMarkReadSerializer,
    MessageStarSerializer, MessageBatchOperationSerializer,
    NotificationPreferenceSerializer, MessageStatsSerializer
)

logger = logging.getLogger(__name__)

MESSAGE_PERMISSIONS = {
    'view_message_center': '查看消息中心',
    'view_message': '查看消息',
    'create_message': '发送消息',
    'delete_message': '删除消息',
    'mark_message_read': '标记已读',
    'star_message': '标星消息',
    'batch_message_operation': '批量操作',
    'view_message_category': '查看消息分类',
    'add_message_category': '新增分类',
    'change_message_category': '编辑分类',
    'delete_message_category': '删除分类',
    'view_message_preference': '查看通知偏好',
    'change_message_preference': '编辑通知偏好',
    'view_message_stats': '查看消息统计',
}


class MessageCategoryViewSet(viewsets.ModelViewSet):
    """消息分类视图集"""
    queryset = MessageCategory.objects.filter(is_active=True)
    serializer_class = MessageCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['sort_order', 'id']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return MessageCategorySimpleSerializer
        return MessageCategorySerializer
    
    @action(detail=False, methods=['get'])
    def all(self, request):
        """获取所有分类（包含统计信息）"""
        categories = self.get_queryset()
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)


class MessageViewSet(viewsets.ModelViewSet):
    """消息视图集"""
    queryset = Message.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'priority']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """获取当前用户的消息"""
        user = self.request.user
        queryset = super().get_queryset()
        
        category_type = self.request.query_params.get('category_type')
        if category_type:
            queryset = queryset.filter(category__type=category_type)
        
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            relation_ids = MessageUserRelation.objects.filter(
                user=user,
                is_read=is_read.lower() == 'true'
            ).values_list('message_id', flat=True)
            queryset = queryset.filter(id__in=relation_ids)
        
        is_starred = self.request.query_params.get('is_starred')
        if is_starred is not None:
            starred_ids = MessageUserRelation.objects.filter(
                user=user,
                is_starred=is_starred.lower() == 'true'
            ).values_list('message_id', flat=True)
            queryset = queryset.filter(id__in=starred_ids)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return MessageListSerializer
        if self.action == 'create':
            return MessageCreateSerializer
        return MessageSerializer
    
    def list(self, request, *args, **kwargs):
        """获取消息列表"""
        return super().list(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        """创建消息"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        
        output_serializer = MessageSerializer(message)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        """标记消息为已读"""
        message = self.get_object()
        relation, created = MessageUserRelation.objects.get_or_create(
            message=message,
            user=request.user,
            defaults={'is_read': True, 'read_time': timezone.now()}
        )
        if not created:
            relation.is_read = True
            relation.read_time = timezone.now()
            relation.save()
        return Response({'status': 'success'})
    
    @action(detail=True, methods=['post'])
    def unread(self, request, pk=None):
        """标记消息为未读"""
        message = self.get_object()
        relation = MessageUserRelation.objects.filter(
            message=message,
            user=request.user
        ).first()
        if relation:
            relation.is_read = False
            relation.read_time = None
            relation.save()
        return Response({'status': 'success'})
    
    @action(detail=True, methods=['post'])
    def star(self, request, pk=None):
        """标星消息"""
        message = self.get_object()
        relation, created = MessageUserRelation.objects.get_or_create(
            message=message,
            user=request.user,
            defaults={'is_starred': True}
        )
        if not created:
            relation.is_starred = True
            relation.save()
        return Response({'status': 'success'})
    
    @action(detail=True, methods=['post'])
    def unstar(self, request, pk=None):
        """取消标星"""
        message = self.get_object()
        relation = MessageUserRelation.objects.filter(
            message=message,
            user=request.user
        ).first()
        if relation:
            relation.is_starred = False
            relation.save()
        return Response({'status': 'success'})
    
    @action(detail=False, methods=['post'])
    def batch_operation(self, request):
        """批量操作"""
        serializer = MessageBatchOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        message_ids = serializer.validated_data['message_ids']
        operation = serializer.validated_data['operation']
        
        relations = MessageUserRelation.objects.filter(
            message_id__in=message_ids,
            user=request.user
        )
        
        if operation == 'read':
            relations.update(is_read=True, read_time=timezone.now())
        elif operation == 'unread':
            relations.update(is_read=False, read_time=None)
        elif operation == 'star':
            relations.update(is_starred=True)
        elif operation == 'unstar':
            relations.update(is_starred=False)
        elif operation == 'delete':
            relations.delete()
        
        return Response({'status': 'success', 'affected_count': len(message_ids)})


class MessageMarkReadView(views.APIView):
    """消息已读视图"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """标记消息已读"""
        serializer = MessageMarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        message_ids = serializer.validated_data.get('message_ids')
        
        if message_ids:
            MessageUserRelation.objects.filter(
                message_id__in=message_ids,
                user=request.user
            ).update(is_read=True, read_time=timezone.now())
        else:
            MessageUserRelation.objects.filter(
                user=request.user,
                is_read=False
            ).update(is_read=True, read_time=timezone.now())
        
        return Response({'status': 'success'})


class MessageStatsView(views.APIView):
    """消息统计视图"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取消息统计"""
        user = request.user
        
        total_count = MessageUserRelation.objects.filter(user=user).count()
        unread_count = MessageUserRelation.objects.filter(user=user, is_read=False).count()
        starred_count = MessageUserRelation.objects.filter(user=user, is_starred=True).count()
        
        category_stats = {}
        categories = MessageCategory.objects.filter(is_active=True)
        for category in categories:
            category_stats[category.code] = {
                'name': category.name,
                'total': MessageUserRelation.objects.filter(
                    user=user,
                    message__category=category
                ).count(),
                'unread': MessageUserRelation.objects.filter(
                    user=user,
                    message__category=category,
                    is_read=False
                ).count()
            }
        
        data = {
            'total_count': total_count,
            'unread_count': unread_count,
            'starred_count': starred_count,
            'category_stats': category_stats
        }
        
        serializer = MessageStatsSerializer(data)
        return Response(serializer.data)


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """用户通知偏好视图集"""
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        return NotificationPreferenceSerializer
    
    def get_object(self):
        obj, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return obj
    
    def list(self, request, *args, **kwargs):
        """获取当前用户的通知偏好"""
        preference = self.get_object()
        serializer = self.get_serializer(preference)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """创建通知偏好"""
        return self.update(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """更新通知偏好"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class UnreadCountView(views.APIView):
    """未读消息数量视图"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取未读消息数量"""
        user = request.user
        unread_count = MessageUserRelation.objects.filter(user=user, is_read=False).count()
        return Response({'unread_count': unread_count})


def message_center_page(request):
    """消息中心页面"""
    return render(request, 'message/message_center.html')
