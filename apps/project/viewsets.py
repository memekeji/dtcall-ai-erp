from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie, vary_on_headers
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
            (hasattr(request.user, 'did') and request.user.did and obj.department and obj.department.id == request.user.did)
        )

class ProjectViewSet(viewsets.ModelViewSet):
    """项目视图集"""
    queryset = Project.objects.filter(delete_time__isnull=True)
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, ProjectPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category', 'manager', 'customer', 'department']
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
            overdue=Count('id', filter=Q(status__in=[1, 2], end_date__lt=timezone.now().date()))
        )
        
        # 工时统计
        work_hours = project.tasks.values('id').annotate(
            total_hours=Sum('work_hours__hours')
        ).aggregate(total=Sum('total_hours'))
        
        # 预算使用情况
        budget_used = project.actual_cost
        budget_total = project.budget
        budget_percentage = (budget_used / budget_total * 100) if budget_total > 0 else 0
        
        # 项目成员工时统计
        member_stats = project.members.annotate(
            total_hours=Sum('work_hours__hours', filter=Q(work_hours__task__project=project))
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
            total_hours=Sum('work_hours__hours', filter=Q(work_hours__task__project=project)),
            completed_tasks=Count('assigned_tasks', filter=Q(assigned_tasks__project=project, assigned_tasks__status=3)),
            total_tasks=Count('assigned_tasks', filter=Q(assigned_tasks__project=project))
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
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project', 'manager']
    search_fields = ['name', 'description']
    ordering_fields = ['sort', 'create_time']

class TaskViewSet(viewsets.ModelViewSet):
    """任务视图集"""
    queryset = Task.objects.filter(delete_time__isnull=True)
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project', 'step', 'assignee', 'status', 'priority']
    search_fields = ['title', 'description']
    ordering_fields = ['create_time', 'update_time', 'priority', 'end_date']

class WorkHourViewSet(viewsets.ModelViewSet):
    """工时记录视图集"""
    queryset = WorkHour.objects.all()
    serializer_class = WorkHourSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['task', 'user', 'work_date']
    search_fields = ['description']
    ordering_fields = ['work_date', 'create_time']

class ProjectDocumentViewSet(viewsets.ModelViewSet):
    """项目文档视图集"""
    queryset = ProjectDocument.objects.filter(delete_time__isnull=True)
    serializer_class = ProjectDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
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


class CommentViewSet(viewsets.ModelViewSet):
    """评论视图集"""
    queryset = Comment.objects.filter(delete_time__isnull=True)
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['content_type', 'object_id', 'user', 'parent']
    search_fields = ['content']
    ordering_fields = ['create_time', 'update_time']
    
    def perform_create(self, serializer):
        # 自动设置当前用户为评论者
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def by_object(self, request):
        """根据对象获取评论"""
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        
        if not content_type or not object_id:
            return Response({'error': 'Missing required parameters'}, status=400)
        
        try:
            # 获取根评论（没有父评论的评论）
            comments = Comment.objects.filter(
                content_type__model=content_type,
                object_id=object_id,
                parent__isnull=True,
                delete_time__isnull=True
            ).order_by('-create_time')
            
            serializer = self.get_serializer(comments, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
