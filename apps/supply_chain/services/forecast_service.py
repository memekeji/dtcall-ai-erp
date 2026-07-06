from decimal import Decimal, ROUND_HALF_UP


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
