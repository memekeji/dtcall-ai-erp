from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from .models import Project, ProjectStep, Task, WorkHour, ProjectDocument, ProjectCategory, ProjectStage, WorkType, Comment
from .serializers import (
    ProjectSerializer, ProjectStepSerializer, TaskSerializer,
    WorkHourSerializer, ProjectDocumentSerializer, ProjectCategorySerializer,
    ProjectStageSerializer, WorkTypeSerializer, CommentSerializer
)
from django.contrib.auth import get_user_model
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Count, Sum

User = get_user_model()


class ProjectPermission(permissions.BasePermission):
    """项目权限控制"""

    def has_object_permission(self, request, view, obj):
        # 超级用户可以访问所有项目
        if request.user.is_superuser:
            return True
        # 项目创建者、项目经理或项目成员可以访问
        return (
            obj.creator == request.user or
            obj.manager == request.user or
            request.user in obj.members.all() or
            (hasattr(request.user, 'did')
             and request.user.did and obj.department and obj.department.id == request.user.did)
        )


class ProjectViewSet(viewsets.ModelViewSet):
    """项目视图集"""
    queryset = Project.objects.filter(delete_time__isnull=True)
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, ProjectPermission]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter]
    filterset_fields = [
        'status',
        'category',
        'manager',
        'customer',
        'department']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['create_time', 'update_time', 'priority', 'progress']

    def perform_create(self, serializer):
        # 设置创建人
        serializer.save(creator=self.request.user)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """获取项目统计信息"""
        # 使用缓存减少数据库查询
        cache_key = f'project_stats_{pk}'
        cached_stats = cache.get(cache_key)

        if cached_stats:
            return Response(cached_stats)

        project = self.get_object()
        # 任务统计
        task_stats = project.tasks.aggregate(
            total=Count('id'),
            completed=Count('id', filter=Q(status=3)),
            in_progress=Count('id', filter=Q(status=2)),
            pending=Count('id', filter=Q(status=1)),
            overdue=Count(
                'id',
                filter=Q(
                    status__in=[
                        1,
                        2],
                    end_date__lt=timezone.now().date()))
        )

        # 工时统计
        work_hours = project.tasks.values('id').annotate(
            total_hours=Sum('work_hours__hours')
        ).aggregate(total=Sum('total_hours'))

        # 预算使用情况
        budget_used = project.actual_cost
        budget_total = project.budget
        budget_percentage = (
            budget_used /
            budget_total *
            100) if budget_total > 0 else 0

        # 项目成员工时统计
        member_stats = project.members.annotate(
            total_hours=Sum(
                'work_hours__hours', filter=Q(
                    work_hours__task__project=project))
        ).values('id', 'username', 'total_hours').order_by('-total_hours')

        # 项目阶段进度统计
        step_stats = project.steps.aggregate(
            total_steps=Count('id'),
            completed_steps=Count('id', filter=Q(progress=100)),
            avg_progress=Count('id') and Sum('progress') / Count('id') or 0
        )

        stats_data = {
            'task_stats': task_stats,
            'work_hours': work_hours,
            'budget_stats': {
                'total': float(budget_total),
                'used': float(budget_used),
                'percentage': round(budget_percentage, 2)
            },
            'member_stats': list(member_stats),
            'step_stats': step_stats
        }

        # 缓存300秒
        cache.set(cache_key, stats_data, 300)

        return Response(stats_data)

    @action(detail=True, methods=['get'])
    def member_hours(self, request, pk=None):
        """获取项目成员工时报告"""
        project = self.get_object()
        cache_key = f'project_member_hours_{pk}'
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        # 获取项目成员工时统计
        member_hours = project.members.annotate(
            total_hours=Sum(
                'work_hours__hours', filter=Q(
                    work_hours__task__project=project)),
            completed_tasks=Count(
                'assigned_tasks',
                filter=Q(
                    assigned_tasks__project=project,
                    assigned_tasks__status=3)),
            total_tasks=Count(
                'assigned_tasks', filter=Q(
                    assigned_tasks__project=project))
        ).values('id', 'username', 'total_hours', 'completed_tasks', 'total_tasks').order_by('-total_hours')

        data = {
            'member_hours': list(member_hours),
            'project_id': project.id,
            'project_name': project.name
        }

        cache.set(cache_key, data, 300)
        return Response(data)


class ProjectStepViewSet(viewsets.ModelViewSet):
    """项目步骤视图集"""
    queryset = ProjectStep.objects.all()
    serializer_class = ProjectStepSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter]
    filterset_fields = ['project', 'manager']
    search_fields = ['name', 'description']
    ordering_fields = ['sort', 'create_time']


class TaskViewSet(viewsets.ModelViewSet):
    """任务视图集"""
    queryset = Task.objects.filter(delete_time__isnull=True)
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter]
    filterset_fields = ['project', 'step', 'assignee', 'status', 'priority']
    search_fields = ['title', 'description']
    ordering_fields = ['create_time', 'update_time', 'priority', 'end_date']


class WorkHourViewSet(viewsets.ModelViewSet):
    """工时记录视图集"""
    queryset = WorkHour.objects.all()
    serializer_class = WorkHourSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter]
    filterset_fields = ['task', 'user', 'work_date']
    search_fields = ['description']
    ordering_fields = ['work_date', 'create_time']


class ProjectDocumentViewSet(viewsets.ModelViewSet):
    """项目文档视图集"""
    queryset = ProjectDocument.objects.filter(delete_time__isnull=True)
    serializer_class = ProjectDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter]
    filterset_fields = ['project', 'creator']
    search_fields = ['title', 'content']
    ordering_fields = ['create_time', 'update_time']


class ProjectCategoryViewSet(viewsets.ModelViewSet):
    """项目分类视图集"""
    queryset = ProjectCategory.objects.all()
    serializer_class = ProjectCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['sort_order', 'create_time']

    @method_decorator(cache_page(3600))
    @method_decorator(vary_on_headers('Authorization'))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class ProjectStageViewSet(viewsets.ModelViewSet):
    """项目阶段视图集"""
    queryset = ProjectStage.objects.all()
    serializer_class = ProjectStageSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['sort_order', 'create_time']

    @method_decorator(cache_page(3600))
    @method_decorator(vary_on_headers('Authorization'))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class WorkTypeViewSet(viewsets.ModelViewSet):
    """工作类型视图集"""
    queryset = WorkType.objects.all()
    serializer_class = WorkTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['sort_order', 'create_time']

    @method_decorator(cache_page(3600))
    @method_decorator(vary_on_headers('Authorization'))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class CommentPermission(permissions.BasePermission):
    """评论权限控制"""

    def has_object_permission(self, request, view, obj):
        # 超级用户可以管理所有评论
        if request.user.is_superuser:
            return True
        # 评论作者可以修改和删除自己的评论
        return obj.user == request.user


class CommentViewSet(viewsets.ModelViewSet):
    """评论视图集"""
    queryset = Comment.objects.filter(delete_time__isnull=True)
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, CommentPermission]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter]
    filterset_fields = ['content_type', 'object_id', 'user', 'parent']
    search_fields = ['content']
    ordering_fields = ['create_time', 'update_time']

    def get_queryset(self):
        """优化查询，预取相关数据"""
        queryset = super().get_queryset()
        # 预取用户数据，避免N+1查询问题
        queryset = queryset.select_related('user', 'content_type', 'parent')
        return queryset

    def create(self, request, *args, **kwargs):
        """创建评论"""
        try:
            # 获取content_type_id参数
            content_type_id = request.data.get('content_type_id')
            object_id = request.data.get('object_id')
            content = request.data.get('content')
            parent_id = request.data.get('parent_id')

            if not content_type_id or not object_id or not content:
                return Response(
                    {'error': 'Missing required parameters: content_type_id, object_id and content'}, status=400)

            # 获取ContentType对象
            from django.contrib.contenttypes.models import ContentType
            try:
                content_type = ContentType.objects.get(id=int(content_type_id))
            except ContentType.DoesNotExist:
                return Response(
                    {'error': 'Invalid content_type_id'}, status=400)
            except ValueError as e:
                return Response(
                    {'error': f'Invalid content_type_id format: {str(e)}'}, status=400)

            # 创建评论
            comment = Comment.objects.create(
                user=request.user,
                content=content,
                content_type=content_type,
                object_id=object_id,
                parent_id=parent_id
            )

            # 如果是回复，发送通知
            if parent_id:
                self._send_reply_notification(comment)

            # 返回创建的评论
            serializer = self.get_serializer(comment)
            return Response(serializer.data, status=201)

        except Exception as e:
            import traceback
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'[CommentError] {str(e)}')
            logger.error(f'[CommentError] Traceback: {traceback.format_exc()}')
            return Response({'error': str(e)}, status=400)

    def _send_reply_notification(self, comment):
        """发送评论回复通知"""
        try:
            from apps.message.models import Message, MessageCategory

            parent_comment = comment.parent
            if not parent_comment:
                return

            if parent_comment.user == comment.user:
                return

            category, created = MessageCategory.objects.get_or_create(
                code='comment',
                defaults={
                    'name': '评论回复通知',
                    'type': 'comment',
                    'icon': 'layui-icon-reply-fill'
                }
            )

            Message.objects.create(
                category=category,
                user=parent_comment.user,
                sender=comment.user,
                title=f'评论回复通知',
                content=f'{comment.user.username}回复了你的评论：\n\n"{parent_comment.content[:100]}{"..." if len(parent_comment.content) > 100 else ""}"',
                priority=2,
                related_object_type='comment',
                related_object_id=comment.id,
                action_url=f'/project/detail/{comment.object_id}/#comment-{comment.id}'
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'[CommentNotificationError] 发送评论通知失败: {str(e)}')

    def update(self, request, *args, **kwargs):
        """更新评论"""
        kwargs.pop('partial', False)
        instance = self.get_object()

        # 检查权限
        if not request.user.is_superuser and instance.user != request.user:
            return Response({'error': '您没有权限修改此评论'}, status=403)

        # 更新内容
        instance.content = request.data.get('content', instance.content)
        instance.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """删除评论（软删除）"""
        instance = self.get_object()

        # 检查权限
        if not request.user.is_superuser and instance.user != request.user:
            return Response({'error': '您没有权限删除此评论'}, status=403)

        # 软删除
        instance.delete_time = timezone.now()
        instance.save()

        return Response({'message': '评论已删除'}, status=200)

    def perform_create(self, serializer):
        # 自动设置当前用户为评论者
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def by_object(self, request):
        """根据对象获取评论"""
        content_type_param = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')

        if not content_type_param or not object_id:
            return Response(
                {'error': 'Missing required parameters: content_type and object_id'}, status=400)

        try:
            from django.contrib.contenttypes.models import ContentType

            # 支持两种参数格式：ID或模型名
            if content_type_param.isdigit():
                # 如果是数字，则按ID查询
                content_type = ContentType.objects.get(
                    id=int(content_type_param))
            else:
                # 如果是字符串，则按模型名查询
                content_type = ContentType.objects.get(
                    model=content_type_param.lower())

            # 获取根评论（没有父评论的评论）
            comments = Comment.objects.filter(
                content_type=content_type,
                object_id=int(object_id),
                parent__isnull=True,
                delete_time__isnull=True
            ).order_by('-create_time')

            serializer = self.get_serializer(comments, many=True)
            return Response(serializer.data)
        except ContentType.DoesNotExist:
            return Response({'error': 'Invalid content_type'}, status=400)
        except ValueError:
            return Response({'error': 'Invalid object_id format'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
