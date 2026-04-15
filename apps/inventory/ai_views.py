import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Inventory, InventoryRecord
from apps.ai.utils.analysis_tools import default_inventory_analysis_tool

logger = logging.getLogger(__name__)

@login_required
def ai_inventory_forecast(request, inventory_id):
    """
    智能库存需求预测API
    """
    try:
        inventory = Inventory.objects.get(id=inventory_id, delete_time=0)
        
        product_data = {
            'name': inventory.product.name if inventory.product else '',
            'category': inventory.product.category.name if inventory.product and inventory.product.category else '',
            'current_stock': inventory.stock,
            'warning_stock': inventory.warning_stock,
        }
        
        # 简单获取最近的库存出入库记录
        records = InventoryRecord.objects.filter(inventory=inventory)[:20]
        history_sales = [{"type": r.type, "quantity": r.quantity, "date": r.create_time.strftime('%Y-%m-%d')} for r in records]
        
        result = default_inventory_analysis_tool.forecast_demand(product_data, history_sales)
        
        return JsonResponse({'code': 0, 'msg': '预测成功', 'data': result})
    except Inventory.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '库存记录不存在'}, status=404)
    except Exception as e:
        logger.error(f"库存预测失败: {str(e)}")
        return JsonResponse({'code': 500, 'msg': f'预测失败: {str(e)}'}, status=500)
