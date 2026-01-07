import json
import logging
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db.models import Q, Count, Sum
from .models import Project, Task, WorkHour
from apps.ai.utils.analysis_tools import default_project_analysis_tool

logger = logging.getLogger(__name__)

@login_required
def ai_project_risk_prediction(request, project_id):
    """
    AI项目风险预测API
    :param request: HTTP请求对象
    :param project_id: 项目ID
    :return: JSON响应，包含风险预测结果
    """
    try:
        # 获取项目信息
        project = Project.objects.get(id=project_id, delete_time__isnull=True)
        
        # 检查用户是否有权限访问此项目
        if not has_permission(request.user, project):
            return JsonResponse({'code': 403, 'msg': '没有权限查看此项目'}, status=403)
        
        # 准备项目基本数据
        project_data = {
            'id': project.id,
            'name': project.name,
            'status': project.status,
            'priority': project.priority,
            'progress': project.progress,
            'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else '',
            'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else '',
            'budget': float(project.budget) if project.budget else 0,
            'actual_cost': float(project.actual_cost) if project.actual_cost else 0,
            'category_id': project.category_id,
            'manager_id': project.manager_id,
            'description': project.description
        }
        
        # 获取项目任务数据
        tasks = Task.objects.filter(project=project, delete_time__isnull=True)
        task_data = []
        for task in tasks:
            task_data.append({
                'id': task.id,
                'title': task.title,
                'status': task.status,
                'priority': task.priority,
                'start_date': task.start_date.strftime('%Y-%m-%d') if task.start_date else '',
                'end_date': task.end_date.strftime('%Y-%m-%d') if task.end_date else '',
                'assignee_id': task.assignee_id,
                'estimated_hours': float(task.estimated_hours) if task.estimated_hours else 0
            })
        
        # 获取工时统计数据
        work_hours = WorkHour.objects.filter(task__project=project)
        total_hours = work_hours.aggregate(total=Sum('hours'))['total'] or 0
        
        # 计算任务状态统计
        task_stats = tasks.aggregate(
            total_tasks=Count('id'),
            completed_tasks=Count('id', filter=Q(status=3)),
            in_progress_tasks=Count('id', filter=Q(status=2)),
            pending_tasks=Count('id', filter=Q(status=1))
        )
        
        # 调用AI分析工具进行风险预测
        result = default_project_analysis_tool.predict_project_risk(
            project_data, task_data, task_stats, total_hours
        )
        
        # 记录分析日志
        logger.info(f"项目ID {project_id} 风险预测完成")
        
        return JsonResponse({
            'code': 0,
            'msg': '风险预测成功',
            'data': result
        })
        
    except Project.DoesNotExist:
        logger.error(f"项目ID {project_id} 不存在")
        return JsonResponse({'code': 404, 'msg': '项目不存在'}, status=404)
    except Exception as e:
        logger.error(f"项目风险预测失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'风险预测失败: {str(e)}'}, status=500)

@login_required
def ai_project_progress_analysis(request, project_id):
    """
    AI项目进度分析API
    :param request: HTTP请求对象
    :param project_id: 项目ID
    :return: JSON响应，包含进度分析结果
    """
    try:
        # 获取项目信息
        project = Project.objects.get(id=project_id, delete_time__isnull=True)
        
        # 检查用户是否有权限访问此项目
        if not has_permission(request.user, project):
            return JsonResponse({'code': 403, 'msg': '没有权限查看此项目'}, status=403)
        
        # 准备项目数据
        project_data = {
            'id': project.id,
            'name': project.name,
            'progress': project.progress,
            'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else '',
            'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else ''
        }
        
        # 获取项目任务数据
        tasks = Task.objects.filter(project=project, delete_time__isnull=True)
        task_data = []
        for task in tasks:
            task_data.append({
                'id': task.id,
                'title': task.title,
                'status': task.status,
                'start_date': task.start_date.strftime('%Y-%m-%d') if task.start_date else '',
                'end_date': task.end_date.strftime('%Y-%m-%d') if task.end_date else ''
            })
        
        # 调用AI分析工具进行进度分析
        result = default_project_analysis_tool.analyze_project_progress(
            project_data, task_data
        )
        
        # 记录分析日志
        logger.info(f"项目ID {project_id} 进度分析完成")
        
        return JsonResponse({
            'code': 0,
            'msg': '进度分析成功',
            'data': result
        })
        
    except Project.DoesNotExist:
        logger.error(f"项目ID {project_id} 不存在")
        return JsonResponse({'code': 404, 'msg': '项目不存在'}, status=404)
    except Exception as e:
        logger.error(f"项目进度分析失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'进度分析失败: {str(e)}'}, status=500)

def has_permission(user, project):
    """
    检查用户是否有权限查看项目
    """
    if user.is_superuser:
        return True
    
    # 检查用户部门权限
    user_has_dept_permission = False
    if project.department and hasattr(user, 'did') and user.did:
        user_has_dept_permission = project.department.id == user.did
    
    return (
        project.creator == user or
        project.manager == user or
        user in project.members.all() or
        user_has_dept_permission
    )


class AIProgressAnalysisView(LoginRequiredMixin, TemplateView):
    """
    AI进度分析页面视图
    """
    template_name = 'project/ai_progress_analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projects = Project.objects.filter(delete_time__isnull=True).order_by('-id')
        context['projects'] = projects
        context['project_id'] = self.kwargs.get('project_id', 1)
        return context


class AIRiskPredictionView(LoginRequiredMixin, TemplateView):
    """
    AI风险预测页面视图
    """
    template_name = 'project/ai_risk_prediction.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projects = Project.objects.filter(delete_time__isnull=True).order_by('-id')
        context['projects'] = projects
        context['project_id'] = self.kwargs.get('project_id', 1)
        return context