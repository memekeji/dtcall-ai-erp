import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Task
from apps.ai.utils.analysis_tools import default_task_analysis_tool

logger = logging.getLogger(__name__)

@login_required
def ai_task_estimation(request, task_id):
    """
    智能任务工时预估与分配建议API
    """
    try:
        task = Task.objects.get(id=task_id, delete_time=0)
        
        task_data = {
            'name': task.name,
            'description': task.description,
            'status': task.status,
            'priority': task.priority,
        }
        
        assignee_data = {
            'name': task.assignee.username if task.assignee else '',
            'department': task.assignee.department.name if task.assignee and task.assignee.department else ''
        } if task.assignee else None
        
        result = default_task_analysis_tool.estimate_task(task_data, assignee_data)
        
        return JsonResponse({'code': 0, 'msg': '预估成功', 'data': result})
    except Task.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '任务不存在'}, status=404)
    except Exception as e:
        logger.error(f"任务预估失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'预估失败: {str(e)}'}, status=500)
