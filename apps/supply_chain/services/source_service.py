from django.db import transaction

from apps.inventory.models import PurchaseOrderItem
from apps.production.models import MaterialRequest, ProductionPlan
from apps.supply_chain.models import (
    DemandForecastPlan,
    OutsourceIssueOrder,
    OutsourceIssueStatusLog,
    PRReviewRule,
    PRReviewTask,
    PriceReviewOrder,
)
from apps.supply_chain.services.event_service import log_supply_chain_event
from apps.supply_chain.services.sequence_service import generate_business_code


DEFAULT_PR_RULES = (
    ('PR-FILTER-INTERCO-TAIL', '公司间尾数订单', 'intercompany_tail_order', {'intercompany_tail_order': True}, PRReviewRule.ACTION_FILTER, 10),
    ('PR-FILTER-OUTSOURCE-TAIL', '委外尾数订单', 'outsource_tail_order', {'outsource_tail_order': True}, PRReviewRule.ACTION_FILTER, 20),
    ('PR-FILTER-REWORK', '异常工单 / 返工单', 'rework_order', {'rework_order': True}, PRReviewRule.ACTION_FILTER, 30),
    ('PR-URGENT-SHORTAGE', '紧急缺料订单', 'urgent_shortage', {'is_urgent': True, 'lt_shortage': True}, PRReviewRule.ACTION_URGENT, 40),
    ('PR-NPI-TRIAL', 'NPI试产工单', 'npi_trial', {'npi_trial': True}, PRReviewRule.ACTION_URGENT, 50),
    ('PR-APPROVE-STANDARD', '常规需求审批', 'normal', {'is_urgent': False, 'lt_shortage': False, 'tail_order': False, 'intercompany_tail_order': False, 'outsource_tail_order': False, 'rework_order': False, 'npi_trial': False}, PRReviewRule.ACTION_APPROVE, 90),
)


def ensure_default_pr_rules():
    for code, name, scenario, conditions, action, priority in DEFAULT_PR_RULES:
        PRReviewRule.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'scenario': scenario,
                'condition_json': conditions,
                'recommended_action': action,
                'priority': priority,
                'is_active': True,
            },
        )


@transaction.atomic
def sync_supply_chain_sources(*, user):
    result = {
        'forecast_created': 0,
        'outsource_created': 0,
        'pr_created': 0,
        'price_review_created': 0,
        'sample_created': 0,
        'skipped': [],
    }
    ensure_default_pr_rules()

    plans = ProductionPlan.objects.filter(status__in=[1, 2, 3], product__isnull=False).select_related('product', 'bom')
    for plan in plans:
        snapshot = {
            'plan_code': plan.code,
            'plan_quantity': str(plan.quantity),
            'plan_start_date': str(plan.plan_start_date),
            'plan_end_date': str(plan.plan_end_date),
            'product_code': getattr(plan.product, 'code', ''),
            'bom_code': getattr(plan.bom, 'code', ''),
        }
        _, created = DemandForecastPlan.objects.get_or_create(
            source_type='production_plan',
            source_id=plan.id,
            defaults={
                'name': f'{plan.name}需求预测',
                'code': generate_business_code('DFP'),
                'source_code': plan.code,
                'source_snapshot': snapshot,
                'product': plan.product,
                'period_start': plan.plan_start_date,
                'period_end': plan.plan_end_date,
                'summary': '由生产计划同步，待基于实时业务数据运行预测',
                'created_by': user,
            },
        )
        result['forecast_created'] += int(created)

        if plan.bom_id is None:
            result['skipped'].append(f'生产计划 {plan.code} 未绑定BOM，未生成委外发料单')
            continue
        order, created = OutsourceIssueOrder.objects.get_or_create(
            source_type='production_plan',
            source_id=plan.id,
            defaults={
                'code': generate_business_code('OIO'),
                'source_code': plan.code,
                'source_snapshot': snapshot,
                'product': plan.product,
                'production_plan': plan,
                'quantity': plan.quantity,
                'created_by': user,
            },
        )
        if created:
            OutsourceIssueStatusLog.objects.create(
                issue_order=order,
                from_status='',
                to_status=order.status,
                message=f'从生产计划 {plan.code} 同步',
                operator=user,
            )
            result['outsource_created'] += 1

    requests = MaterialRequest.objects.filter(status=1).select_related('production_plan').prefetch_related('items')
    for material_request in requests:
        evidence = {
            'request_date': str(material_request.request_date),
            'production_plan': material_request.production_plan.code,
            'total_amount': str(material_request.total_amount),
            'items': [
                {
                    'material_code': item.material_code,
                    'material_name': item.material_name,
                    'request_quantity': str(item.request_quantity),
                    'issued_quantity': str(item.issued_quantity),
                }
                for item in material_request.items.all()
            ],
        }
        _, created = PRReviewTask.objects.get_or_create(
            source_type='material_request',
            source_id=material_request.id,
            defaults={
                'code': generate_business_code('PRR'),
                'title': f'领料申请审核 - {material_request.code}',
                'source_code': material_request.code,
                'source_snapshot': evidence,
                'evidence': evidence,
                'created_by': user,
            },
        )
        result['pr_created'] += int(created)

    purchase_items = PurchaseOrderItem.objects.filter(
        purchase_order__status__in=[1, 2, 3, 4],
    ).select_related('purchase_order__supplier', 'item')
    for purchase_item in purchase_items:
        purchase_order = purchase_item.purchase_order
        snapshot = {
            'purchase_order_code': purchase_order.code,
            'item_code': purchase_item.item.code,
            'quantity': str(purchase_item.quantity),
            'unit_price': str(purchase_item.unit_price),
            'supplier_code': purchase_order.supplier.code,
            'order_date': str(purchase_order.order_date),
        }
        _, created = PriceReviewOrder.objects.get_or_create(
            source_type='purchase_order_item',
            source_id=purchase_item.id,
            defaults={
                'code': generate_business_code('PRC'),
                'source_code': f'{purchase_order.code}/{purchase_item.item.code}',
                'source_snapshot': snapshot,
                'purchase_order': purchase_order,
                'inventory_item': purchase_item.item,
                'supplier': purchase_order.supplier,
                'quoted_price': purchase_item.unit_price,
                'created_by': user,
            },
        )
        result['price_review_created'] += int(created)

    log_supply_chain_event(
        event_type='source_sync_completed',
        title='供应链真实来源同步完成',
        object_type='supply_chain_source_sync',
        payload=result,
        operator=user,
    )
    return result
