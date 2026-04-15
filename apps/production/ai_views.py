import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import ProductionPlan, ProductionTask
from apps.ai.utils.analysis_tools import AIAnalysisTool

logger = logging.getLogger(__name__)

class ProductionAnalysisTool(AIAnalysisTool):
    def optimize_plan(self, plan_data, tasks_data):
        prompt = f"""请对以下生产计划进行优化建议：
        生产计划: {plan_data}
        现有任务: {tasks_data}
        
        请返回JSON格式：
        1. 预估完成时间
        2. 产能瓶颈分析
        3. 优化建议 (如调整顺序、增加人员)
        """
        return self._call_ai(prompt)

default_production_analysis_tool = ProductionAnalysisTool()

@login_required
def ai_production_optimization(request, plan_id):
    try:
        plan = ProductionPlan.objects.get(id=plan_id, delete_time=0)
        
        plan_data = {
            'name': plan.name,
            'start_time': plan.start_time.strftime('%Y-%m-%d') if plan.start_time else '',
            'end_time': plan.end_time.strftime('%Y-%m-%d') if plan.end_time else '',
        }
        
        tasks = ProductionTask.objects.filter(plan=plan)[:10]
        tasks_data = [{"name": t.name, "status": t.status} for t in tasks]
        
        result = default_production_analysis_tool.optimize_plan(plan_data, tasks_data)
        
        return JsonResponse({'code': 0, 'msg': '优化建议生成成功', 'data': result})
    except ProductionPlan.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '生产计划不存在'}, status=404)
    except Exception as e:
        logger.error(f"生产计划优化失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'优化失败: {str(e)}'}, status=500)
