import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Inventory, StockTransaction
from apps.ai.services.business_result import build_business_ai_result
from apps.ai.utils.analysis_tools import default_inventory_analysis_tool

logger = logging.getLogger(__name__)


def _normalize_inventory_ai_result(raw_result, inventory, request=None, raw_input=None):
    source_refs = [{'type': 'inventory', 'id': inventory.id}]
    item_id = getattr(inventory, 'item_id', None) or getattr(getattr(inventory, 'item', None), 'id', None)
    if item_id:
        source_refs.append({'type': 'inventory_item', 'id': item_id})

    return build_business_ai_result(
        raw_result,
        scenario='inventory_forecast',
        source_refs=source_refs,
        request=request,
        raw_input=raw_input,
    )


@login_required
def ai_inventory_forecast(request, inventory_id):
    """
    智能库存需求预测API
    """
    try:
        inventory = Inventory.objects.select_related('item', 'item__category').get(id=inventory_id)

        item = inventory.item
        product_data = {
            'name': item.name if item else '',
            'category': item.category.name if item and item.category else '',
            'current_stock': inventory.quantity,
            'warning_stock': item.min_stock if item else 0,
        }

        records = StockTransaction.objects.filter(
            item=inventory.item,
            warehouse=inventory.warehouse,
        ).order_by('-create_time')[:20]
        history_sales = [{
            'type': r.transaction_type,
            'quantity': r.quantity,
            'date': r.create_time.strftime('%Y-%m-%d'),
        } for r in records]

        result = default_inventory_analysis_tool.forecast_demand(product_data, history_sales)
        normalized_result = _normalize_inventory_ai_result(
            result,
            inventory,
            request=request,
            raw_input={'product': product_data, 'history_count': len(history_sales)},
        )

        return JsonResponse({'code': 0, 'msg': '预测成功', 'data': normalized_result})
    except Inventory.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '库存记录不存在'}, status=404)
    except Exception as e:
        logger.error(f"库存预测失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'预测失败: {str(e)}'}, status=500)
