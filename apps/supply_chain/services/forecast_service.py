from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum


def _to_decimal(value):
    return Decimal(str(value or 0))


def build_snapshot_payload(
    shipped_quantity,
    inventory_quantity,
    wip_quantity,
    inbound_quantity,
    prepared_quantity,
    manual_adjustment,
):
    inventory_quantity = _to_decimal(inventory_quantity)
    wip_quantity = _to_decimal(wip_quantity)
    inbound_quantity = _to_decimal(inbound_quantity)
    prepared_quantity = _to_decimal(prepared_quantity)

    return {
        'shipped_quantity': _to_decimal(shipped_quantity),
        'inventory_quantity': inventory_quantity,
        'wip_quantity': wip_quantity,
        'inbound_quantity': inbound_quantity,
        'prepared_quantity': prepared_quantity,
        'manual_adjustment': _to_decimal(manual_adjustment),
        'total_supply': inventory_quantity + wip_quantity + inbound_quantity + prepared_quantity,
    }


def build_live_forecast_inputs(plan):
    from apps.inventory.models import Inventory, InventoryItem, PurchaseOrderItem, SalesOrderItem
    from apps.production.models import ProductionPlan

    product = plan.product
    inventory_item = None
    if product is not None:
        inventory_item = InventoryItem.objects.filter(code=product.code).first()

    history_start = plan.period_start - timedelta(days=90)
    shipped_quantity = Decimal('0')
    period_order_quantity = Decimal('0')
    inventory_quantity = Decimal('0')
    inbound_quantity = Decimal('0')
    if inventory_item is not None:
        shipped_quantity = SalesOrderItem.objects.filter(
            item=inventory_item,
            sales_order__order_date__gte=history_start,
            sales_order__order_date__lt=plan.period_start,
            sales_order__status__in=[2, 3, 4],
        ).aggregate(total=Sum('shipped_quantity'))['total'] or Decimal('0')
        period_order_quantity = SalesOrderItem.objects.filter(
            item=inventory_item,
            sales_order__order_date__range=[plan.period_start, plan.period_end],
            sales_order__status__in=[1, 2, 3, 4],
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        inventory_quantity = Inventory.objects.filter(item=inventory_item).aggregate(
            total=Sum('available_quantity'),
        )['total'] or Decimal('0')
        inbound_quantity = PurchaseOrderItem.objects.filter(
            item=inventory_item,
            purchase_order__status__in=[1, 2, 3],
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        received_quantity = PurchaseOrderItem.objects.filter(
            item=inventory_item,
            purchase_order__status__in=[1, 2, 3],
        ).aggregate(total=Sum('received_quantity'))['total'] or Decimal('0')
        inbound_quantity = max(inbound_quantity - received_quantity, Decimal('0'))

    active_plans = ProductionPlan.objects.filter(
        product=product,
        status__in=[1, 2, 3],
    ) if product is not None else ProductionPlan.objects.none()
    planned_quantity = active_plans.filter(
        plan_start_date__lte=plan.period_end,
        plan_end_date__gte=plan.period_start,
    ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    wip_quantity = active_plans.filter(status=3).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    source_plan_quantity = Decimal(str(plan.source_snapshot.get('plan_quantity') or 0))
    historical_monthly_average = (shipped_quantity / Decimal('3')).quantize(Decimal('0.01'))
    predicted_quantity = max(
        source_plan_quantity,
        planned_quantity,
        period_order_quantity,
        historical_monthly_average,
    )
    period_days = max((plan.period_end - plan.period_start).days + 1, 1)
    avg_daily_demand = (
        shipped_quantity / Decimal('90')
        if shipped_quantity > 0
        else predicted_quantity / Decimal(period_days)
    ).quantize(Decimal('0.01'))

    return {
        'shipped_quantity': shipped_quantity,
        'inventory_quantity': inventory_quantity,
        'wip_quantity': wip_quantity,
        'inbound_quantity': inbound_quantity,
        'prepared_quantity': Decimal('0'),
        'predicted_quantity': predicted_quantity,
        'avg_daily_demand': avg_daily_demand,
        'source_note': (
            f'系统实时快照：近90天出货 {shipped_quantity}，当前可用库存 {inventory_quantity}，'
            f'在制 {wip_quantity}，采购在途 {inbound_quantity}，周期订单 {period_order_quantity}'
        ),
        'inventory_item_code': inventory_item.code if inventory_item else '',
    }


def calculate_safety_stock(avg_daily_demand, coverage_days=7):
    return (_to_decimal(avg_daily_demand) * _to_decimal(coverage_days)).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )


def calculate_recommended_preparation_quantity(
    predicted_quantity,
    safety_stock,
    inventory_quantity,
    wip_quantity,
    inbound_quantity,
    prepared_quantity,
    manual_adjustment=0,
):
    predicted_quantity = _to_decimal(predicted_quantity)
    safety_stock = _to_decimal(safety_stock)
    inventory_quantity = _to_decimal(inventory_quantity)
    wip_quantity = _to_decimal(wip_quantity)
    inbound_quantity = _to_decimal(inbound_quantity)
    prepared_quantity = _to_decimal(prepared_quantity)
    manual_adjustment = _to_decimal(manual_adjustment)

    demand_total = predicted_quantity + safety_stock + manual_adjustment
    supply_total = inventory_quantity + wip_quantity + inbound_quantity + prepared_quantity
    gap = demand_total - supply_total
    if gap < 0:
        return Decimal('0')
    return gap.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_forecast_accuracy(predicted_quantity, actual_quantity):
    predicted_quantity = _to_decimal(predicted_quantity)
    actual_quantity = _to_decimal(actual_quantity)
    if actual_quantity <= 0:
        return Decimal('0.00')
    ratio = (Decimal('1') - abs(actual_quantity - predicted_quantity) / actual_quantity) * Decimal('100')
    if ratio < 0:
        ratio = Decimal('0')
    return ratio.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def build_forecast_trend_data(product=None):
    """Build historical forecast trend data for a product."""
    from apps.supply_chain.models import DemandForecastPlan, DemandForecastResult, MaterialPreparationReview
    from django.db.models import Avg

    base = DemandForecastResult.objects.select_related(
        "forecast_plan__product",
    ).prefetch_related("forecast_plan__results", "reviews")
    if product:
        base = base.filter(forecast_plan__product=product)

    results = base.order_by("forecast_plan__create_time")
    trend_rows = []
    for result in results:
        plan = result.forecast_plan
        reviews = list(result.reviews.all())
        review_status = reviews[0].status if reviews else "pending"
        trend_rows.append({
            "plan_code": plan.code,
            "plan_name": plan.name,
            "created": plan.create_time.strftime("%Y-%m-%d"),
            "predicted": str(result.predicted_quantity),
            "recommended": str(result.recommended_quantity),
            "confidence": str(result.confidence),
            "risk_level": result.risk_level,
            "review_status": review_status,
            "summary": result.summary,
        })

    global_avg_confidence = base.aggregate(avg=Avg("confidence"))["avg"]
    return {
        "trend_rows": trend_rows,
        "total_results": len(trend_rows),
        "average_confidence": (
            round(float(global_avg_confidence), 2)
            if global_avg_confidence else 0
        ),
    }
