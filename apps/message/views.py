from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import models
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth.decorators import login_required
import logging

from .models import (
    Conversation,
    ConversationMember,
    ConversationMessage,
    MessageCategory,
    Message,
    MessageUserRelation,
    NotificationPreference,
)
from .services import (
    ConversationMessageService,
    ConversationService,
    MessageService,
    MessageTaskService,
)
from .serializers import (
    ConversationCreateGroupSerializer,
    ConversationDirectSerializer,
    ConversationMessageSerializer,
    ConversationSendMessageSerializer,
    ConversationSerializer,
    MessageCategorySerializer,
    MessageSerializer, MessageListSerializer, MessageCreateSerializer,
    MessageMarkReadSerializer, MessageBatchOperationSerializer,
    NotificationPreferenceSerializer, MessageStatsSerializer
)
from apps.common.services import CommonService
from apps.user.models import Admin

logger = logging.getLogger(__name__)

MESSAGE_PERMISSIONS = {
    'view_message_center': '查看消息中心',
    'view_message': '查看消息',
    'create_message': '发送消息',
    'delete_message': '删除消息',
    'mark_message_read': '标记已读',
    'star_message': '标星消息',
    'batch_message_operation': '批量操作',
    'view_message_preference': '查看通知偏好',
    'change_message_preference': '编辑通知偏好',
    'view_message_stats': '查看消息统计',
}


class MessageCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """消息分类视图集（只读）"""
    queryset = MessageCategory.objects.filter(is_active=True)
    serializer_class = MessageCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['sort_order', 'created_at']
    ordering = ['sort_order', 'id']

    def get_queryset(self):
        return super().get_queryset()

    def list(self, request, *args, **kwargs):
        """获取消息分类列表"""
        queryset = self.filter_queryset(self.get_queryset())

        page = int(request.GET.get('page', 1))
        page_size = CommonService.get_page_size(request, 20)

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        serializer = self.get_serializer(page_obj, many=True)

        return JsonResponse({
            'code': 200,
            'msg': 'success',
            'count': paginator.count,
            'results': serializer.data
        })

    @action(detail=False, methods=['get'])
    def all(self, request):
        """获取所有分类"""
        categories = self.get_queryset()
        serializer = self.get_serializer(categories, many=True)
        return JsonResponse({
            'code': 200,
            'msg': 'success',
            'results': serializer.data
        })


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
        if not self.request.user.has_perm('message.view_message'):
            return Message.objects.none()
        user = self.request.user
        queryset = super().get_queryset()

        queryset = queryset.filter(
            user_relations__user=user
        ).distinct()

        category_type = self.request.query_params.get('category_type')
        if category_type:
            queryset = queryset.filter(category__type=category_type)

        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(
                user_relations__user=user,
                user_relations__is_read=is_read.lower() == 'true'
            )

        is_starred = self.request.query_params.get('is_starred')
        if is_starred is not None:
            queryset = queryset.filter(
                user_relations__user=user,
                user_relations__is_starred=is_starred.lower() == 'true'
            )

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return MessageListSerializer
        if self.action == 'create':
            return MessageCreateSerializer
        return MessageSerializer

    def list(self, request, *args, **kwargs):
        """获取消息列表"""
        if not request.user.has_perm('message.view_message'):
            from rest_framework.response import Response
            return Response({'results': [], 'count': 0})
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """创建消息"""
        if not request.user.has_perm('message.create_message'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("您没有权限发送消息")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save(sender=request.user)

        output_serializer = MessageSerializer(message)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        """标记消息为已读"""
        message = self.get_object()
        MessageService.mark_as_read(message.id, request.user)
        return Response({'status': 'success'})

    @action(detail=True, methods=['post'])
    def unread(self, request, pk=None):
        """标记消息为未读"""
        message = self.get_object()
        MessageService.mark_as_unread(message.id, request.user)
        return Response({'status': 'success'})

    @action(detail=True, methods=['post'])
    def star(self, request, pk=None):
        """标星消息"""
        if not request.user.has_perm('message.star_message'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("您没有权限标星消息")
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
        if not request.user.has_perm('message.star_message'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("您没有权限标星消息")
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
        if not request.user.has_perm('message.batch_message_operation'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("您没有权限执行批量操作")
        serializer = MessageBatchOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message_ids = serializer.validated_data['message_ids']
        operation = serializer.validated_data['operation']

        if operation == 'delete' and not request.user.has_perm(
                'message.delete_message'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("您没有权限删除消息")

        relations = MessageUserRelation.objects.filter(
            message_id__in=message_ids,
            user=request.user
        )

        if operation == 'read':
            if not request.user.has_perm('message.mark_message_read'):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("您没有权限标记已读")
            updated_count = relations.filter(is_read=False).update(
                is_read=True,
                read_time=timezone.now()
            )
        elif operation == 'unread':
            updated_count = relations.filter(is_read=True).update(
                is_read=False,
                read_time=None
            )
        elif operation == 'star':
            updated_count = relations.filter(is_starred=False).update(
                is_starred=True
            )
        elif operation == 'unstar':
            updated_count = relations.filter(is_starred=True).update(
                is_starred=False
            )
        elif operation == 'delete':
            updated_count = relations.count()
            relations.delete()
        else:
            updated_count = 0

        if operation in {'read', 'unread', 'delete'}:
            MessageService.invalidate_user_unread_counts([request.user.id])

        return Response({'status': 'success',
                         'affected_count': updated_count})


class MessageMarkReadView(views.APIView):
    """消息已读视图"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """标记消息已读"""
        if not request.user.has_perm('message.mark_message_read'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("您没有权限标记消息已读")
        serializer = MessageMarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message_ids = serializer.validated_data.get('message_ids')

        if message_ids:
            MessageUserRelation.objects.filter(
                message_id__in=message_ids,
                user=request.user,
                is_read=False
            ).update(is_read=True, read_time=timezone.now())
        else:
            MessageUserRelation.objects.filter(
                user=request.user,
                is_read=False
            ).update(is_read=True, read_time=timezone.now())

        MessageService.invalidate_user_unread_counts([request.user.id])

        return Response({'status': 'success'})


class MessageStatsView(views.APIView):
    """消息统计视图"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取消息统计"""
        user = request.user

        total_count = MessageUserRelation.objects.filter(user=user).count()
        unread_count = MessageUserRelation.objects.filter(
            user=user, is_read=False).count()
        starred_count = MessageUserRelation.objects.filter(
            user=user, is_starred=True).count()

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
    serializer_class = NotificationPreferenceSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user)

    def get_object(self):
        obj, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return obj

    def list(self, request, *args, **kwargs):
        """获取当前用户的通知偏好"""
        preference = self.get_object()
        serializer = self.get_serializer(preference)
        return JsonResponse(
            {'code': 200, 'msg': 'success', 'data': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        """获取单个偏好设置"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return JsonResponse(
            {'code': 200, 'msg': 'success', 'data': serializer.data})

    def create(self, request, *args, **kwargs):
        """创建设置"""
        return self.update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """更新设置"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(
                {'code': 200, 'msg': '保存成功', 'data': serializer.data})
        return JsonResponse({'code': 400, 'msg': serializer.errors})

    def partial_update(self, request, *args, **kwargs):
        """部分更新"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def update_settings(self, request):
        """更新用户偏好设置（POST /message/preferences/update_settings/）"""
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return JsonResponse(
                {'code': 200, 'msg': '保存成功', 'data': serializer.data})
        return JsonResponse({'code': 400, 'msg': serializer.errors})


class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    """统一在线沟通会话 API"""
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'messages__content']
    ordering_fields = ['last_message_at', 'created_at', 'updated_at']
    ordering = ['-last_message_at', '-created_at']

    def get_queryset(self):
        queryset = ConversationService.list_user_conversations(
            self.request.user
        ).prefetch_related('member_relations__user')
        conversation_type = self.request.query_params.get('conversation_type')
        if conversation_type:
            queryset = queryset.filter(conversation_type=conversation_type)
        return queryset

    def get_serializer_class(self):
        if self.action == 'direct':
            return ConversationDirectSerializer
        if self.action == 'groups':
            return ConversationCreateGroupSerializer
        if self.action == 'messages' and self.request.method.lower() == 'post':
            return ConversationSendMessageSerializer
        return ConversationSerializer

    def _get_member_conversation(self):
        conversation = self.get_object()
        try:
            ConversationMessageService.ensure_member(
                conversation,
                self.request.user,
            )
        except PermissionError:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('您不是该会话成员')
        return conversation

    def _serialize_conversation(self, conversation):
        return ConversationSerializer(
            conversation,
            context={'request': self.request},
        )

    @action(detail=False, methods=['post'], url_path='direct')
    def direct(self, request):
        """创建或返回当前用户与目标用户的单聊"""
        if not request.user.has_perm('message.start_direct_conversation'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('您没有权限发起单聊')
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        target = Admin.objects.get(id=serializer.validated_data['user_id'])
        conversation = ConversationService.get_or_create_direct(
            request.user,
            target,
        )
        output = self._serialize_conversation(conversation)
        return Response(output.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='groups')
    def groups(self, request):
        """创建自由群聊"""
        if not request.user.has_perm('message.create_group_conversation'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('您没有权限创建群聊')
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        conversation = ConversationService.create_group(
            owner=request.user,
            name=serializer.validated_data['name'],
            member_ids=serializer.validated_data.get('member_ids', []),
        )
        output = self._serialize_conversation(conversation)
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='members')
    def members(self, request, pk=None):
        """群管理员添加成员"""
        if not request.user.has_perm('message.manage_group_conversation'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('您没有权限管理群聊')
        conversation = self._get_member_conversation()
        user_ids = request.data.get('user_ids') or []
        if not isinstance(user_ids, list):
            return Response(
                {'detail': 'user_ids 必须是数组'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ConversationService.add_members(
                conversation,
                request.user,
                user_ids,
            )
        except PermissionError:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('没有权限管理该会话')
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        conversation.refresh_from_db()
        output = self._serialize_conversation(conversation)
        return Response(output.data)

    @action(
        detail=True,
        methods=['delete'],
        url_path=r'members/(?P<user_id>\d+)',
    )
    def remove_member(self, request, pk=None, user_id=None):
        """群管理员移除成员"""
        if not request.user.has_perm('message.manage_group_conversation'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('您没有权限管理群聊')
        conversation = self._get_member_conversation()
        try:
            removed = ConversationService.remove_member(
                conversation,
                request.user,
                user_id,
            )
        except PermissionError:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('没有权限管理该会话')
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'status': 'success', 'removed': removed})

    @action(detail=True, methods=['get', 'post'], url_path='messages')
    def messages(self, request, pk=None):
        """获取或发送会话消息"""
        conversation = self._get_member_conversation()
        if request.method.lower() == 'get':
            queryset = ConversationMessage.objects.filter(
                conversation=conversation,
                is_deleted=False,
            ).select_related('sender', 'reply_to').prefetch_related(
                'receipts__user',
                'task_links__task',
            )
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = ConversationMessageSerializer(
                    page,
                    many=True,
                    context={'request': request},
                )
                return self.get_paginated_response(serializer.data)
            serializer = ConversationMessageSerializer(
                queryset,
                many=True,
                context={'request': request},
            )
            return Response(serializer.data)

        serializer = ConversationSendMessageSerializer(
            data=request.data,
            context={'request': request, 'conversation': conversation},
        )
        if not request.user.has_perm('message.send_conversation_message'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('您没有权限发送沟通消息')
        serializer.is_valid(raise_exception=True)
        reply_to = None
        reply_to_id = serializer.validated_data.get('reply_to')
        if reply_to_id:
            reply_to = ConversationMessage.objects.get(id=reply_to_id)
        message = ConversationMessageService.send_text(
            conversation=conversation,
            sender=request.user,
            content=serializer.validated_data['content'],
            metadata=serializer.validated_data.get('metadata') or {},
            reply_to=reply_to,
        )
        output = ConversationMessageSerializer(
            message,
            context={'request': request},
        )
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='read')
    def read(self, request, pk=None):
        """标记当前会话为已读"""
        conversation = self._get_member_conversation()
        through_message_id = request.data.get('through_message_id')
        through_message = None
        if through_message_id:
            through_message = ConversationMessage.objects.filter(
                id=through_message_id,
                conversation=conversation,
            ).first()
            if through_message is None:
                return Response(
                    {'detail': '指定消息不存在'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        count = ConversationMessageService.mark_conversation_read(
            conversation,
            request.user,
            through_message=through_message,
        )
        return Response({'status': 'success', 'read_count': count})

    @action(
        detail=True,
        methods=['get'],
        url_path=r'messages/(?P<message_id>\d+)/receipts',
    )
    def receipts(self, request, pk=None, message_id=None):
        """查看消息已读/未读回执"""
        if not request.user.has_perm('message.view_message_read_receipts'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('您没有权限查看消息回执')
        conversation = self._get_member_conversation()
        message = ConversationMessage.objects.filter(
            id=message_id,
            conversation=conversation,
            is_deleted=False,
        ).first()
        if message is None:
            return Response(
                {'detail': '消息不存在'},
                status=status.HTTP_404_NOT_FOUND,
            )
        active_member_ids = set(
            ConversationMember.objects.filter(
                conversation=conversation,
                left_at__isnull=True,
            ).exclude(user_id=message.sender_id).values_list('user_id', flat=True)
        )
        receipts = list(
            message.receipts.select_related('user').filter(
                user_id__in=active_member_ids,
            )
        )
        read_user_ids = {
            receipt.user_id for receipt in receipts
            if receipt.status == receipt.STATUS_READ
        }
        users = {
            user.id: user
            for user in Admin.objects.filter(id__in=active_member_ids)
        }
        read_users = [
            users[user_id] for user_id in read_user_ids if user_id in users
        ]
        unread_users = [
            user for user_id, user in users.items()
            if user_id not in read_user_ids
        ]
        from .serializers import ConversationUserSerializer
        return Response({
            'message_id': message.id,
            'read_count': len(read_users),
            'unread_count': len(unread_users),
            'read_users': ConversationUserSerializer(read_users, many=True).data,
            'unread_users': ConversationUserSerializer(unread_users, many=True).data,
        })

    @action(
        detail=True,
        methods=['post'],
        url_path=r'messages/(?P<message_id>\d+)/to-task',
    )
    def to_task(self, request, pk=None, message_id=None):
        """将会话消息转换为项目任务"""
        if not request.user.has_perm('message.convert_message_to_task'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('您没有权限将消息转为任务')
        conversation = self._get_member_conversation()
        message = ConversationMessage.objects.filter(
            id=message_id,
            conversation=conversation,
            is_deleted=False,
        ).first()
        if message is None:
            return Response(
                {'detail': '消息不存在'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            task = MessageTaskService.convert_to_task(
                message=message,
                creator=request.user,
                title=request.data.get('title', ''),
                description=request.data.get('description', ''),
                assignee_id=request.data.get('assignee_id'),
                project_id=request.data.get('project_id'),
                priority=request.data.get('priority') or 2,
                end_date=request.data.get('end_date') or None,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            'status': 'success',
            'task': {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'assignee_id': task.assignee_id,
                'project_id': task.project_id,
                'priority': task.priority,
                'status': task.status,
            },
        }, status=status.HTTP_201_CREATED)


class UnreadCountView(views.APIView):
    """未读消息数量视图"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取未读消息数量"""
        if not request.user.has_perm('message.view_message'):
            return Response({'unread_count': 0})
        user = request.user
        unread_count = MessageService.get_unread_count(user)
        return Response({'unread_count': unread_count})


class ConversationContactView(views.APIView):
    """组织通讯录轻量搜索"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        keyword = (request.query_params.get('q') or '').strip()
        queryset = Admin.objects.filter(status=1).exclude(id=request.user.id)
        if keyword:
            queryset = queryset.filter(
                models.Q(username__icontains=keyword) |
                models.Q(name__icontains=keyword) |
                models.Q(mobile__icontains=keyword) |
                models.Q(job_number__icontains=keyword)
            )
        queryset = queryset.order_by('name', 'username', 'id')[:50]
        results = [
            {
                'id': user.id,
                'username': user.username,
                'name': getattr(user, 'name', None) or user.username,
                'avatar': getattr(user, 'thumb', None),
                'mobile': getattr(user, 'mobile', '') or '',
                'department_id': getattr(user, 'did_id', None),
            }
            for user in queryset
        ]
        return Response({'results': results})


@login_required
def message_center_page(request):
    """消息中心页面"""
    if not request.user.has_perm('message.view_message_center'):
        return render(request, '403.html', {'message': '您没有权限访问消息中心'})
    return render(request, 'message/message_center.html')


@login_required
def conversation_center_page(request):
    """统一在线沟通页面"""
    if not request.user.has_perm('message.view_conversation_center'):
        return render(request, '403.html', {'message': '您没有权限访问在线沟通'})
    return render(request, 'message/conversation_center.html')


@login_required
def message_preference_page(request):
    """通知偏好设置页面"""
    if not request.user.has_perm('message.view_message_preference'):
        return render(request, '403.html', {'message': '您没有权限查看通知偏好'})
    return render(request, 'message/message_preference.html')


@login_required
def message_stats_page(request):
    """消息统计页面"""
    if not request.user.has_perm('message.view_message_stats'):
        return render(request, '403.html', {'message': '您没有权限查看消息统计'})
    return render(request, 'message/message_stats.html')
