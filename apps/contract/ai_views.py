import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Contract
from apps.ai.utils.analysis_tools import default_contract_analysis_tool

logger = logging.getLogger(__name__)

@login_required
def ai_contract_risk_analysis(request, contract_id):
    """
    智能合同风险分析API
    """
    try:
        contract = Contract.objects.get(id=contract_id, delete_time=0)
        
        contract_data = {
            'name': contract.name,
            'amount': contract.amount,
            'content': contract.content or contract.remark,
        }
        
        result = default_contract_analysis_tool.analyze_risk(contract_data)
        
        return JsonResponse({'code': 0, 'msg': '分析成功', 'data': result})
    except Contract.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '合同不存在'}, status=404)
    except Exception as e:
        logger.error(f"合同分析失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'分析失败: {str(e)}'}, status=500)

@login_required
def ai_contract_term_extraction(request, contract_id):
    """
    智能合同条款提取API
    """
    try:
        contract = Contract.objects.get(id=contract_id, delete_time=0)
        
        result = default_contract_analysis_tool.extract_key_terms(contract.content or contract.remark)
        
        return JsonResponse({'code': 0, 'msg': '提取成功', 'data': result})
    except Contract.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '合同不存在'}, status=404)
    except Exception as e:
        logger.error(f"条款提取失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'提取失败: {str(e)}'}, status=500)
