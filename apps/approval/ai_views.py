import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Approval
from apps.ai.utils.analysis_tools import default_approval_analysis_tool

logger = logging.getLogger(__name__)

@login_required
def ai_approval_assessment(request, approval_id):
    """
    智能审批风险评估API
    """
    try:
        approval = Approval.objects.get(id=approval_id, delete_time=0)
        
        approval_data = {
            'type': approval.type.name if approval.type else '',
            'content': approval.content,
            'amount': getattr(approval, 'amount', ''),
        }
        
        # 简单获取同类型历史审批记录
        history_approvals = Approval.objects.filter(type=approval.type, status=2)[:5] # status=2 means approved
        history_data = [{"content": a.content, "amount": getattr(a, 'amount', '')} for a in history_approvals]
        
        result = default_approval_analysis_tool.assess_approval(approval_data, history_data)
        
        return JsonResponse({'code': 0, 'msg': '评估成功', 'data': result})
    except Approval.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '审批不存在'}, status=404)
    except Exception as e:
        logger.error(f"审批评估失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'评估失败: {str(e)}'}, status=500)
