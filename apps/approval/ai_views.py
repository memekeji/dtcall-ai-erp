import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Approval
from apps.ai.services.business_result import build_business_ai_result
from apps.ai.utils.analysis_tools import default_approval_analysis_tool

logger = logging.getLogger(__name__)


@login_required
def ai_approval_assessment(request, approval_id):
    """
    智能审批风险评估API
    """
    try:
        approval = Approval.objects.select_related('flow__approval_type').get(id=approval_id)
        approval_type = approval.flow.approval_type if approval.flow else None

        approval_data = {
            'type': approval_type.name if approval_type else '',
            'content': approval.content,
            'amount': getattr(approval, 'amount', ''),
        }

        history_approvals = Approval.objects.filter(
            type_id=approval.type_id,
            status=2
        ).exclude(id=approval.id)[:5]
        history_data = [
            {"content": a.content, "amount": getattr(a, 'amount', '')}
            for a in history_approvals
        ]

        result = default_approval_analysis_tool.assess_approval(approval_data, history_data)
        normalized_result = build_business_ai_result(
            result,
            scenario='approval_assessment',
            source_refs=[{'type': 'approval', 'id': approval.id}],
            request=request,
            raw_input=approval_data,
        )

        return JsonResponse({'code': 0, 'msg': '评估成功', 'data': normalized_result})
    except Approval.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '审批不存在'}, status=404)
    except Exception as e:
        logger.error(f"审批评估失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'评估失败: {str(e)}'}, status=500)
