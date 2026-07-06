from decimal import Decimal, ROUND_HALF_UP
import re


COMPONENT_FIELD_MAP = (
    ('material', '原材料', 'material_cost'),
    ('process', '加工', 'process_cost'),
    ('labor', '人工', 'labor_cost'),
    ('loss', '损耗', 'loss_cost'),
    ('package', '包装', 'package_cost'),
    ('logistics', '物流', 'logistics_cost'),
    ('profit', '利润', 'profit_cost'),
)


def _to_decimal(value, places='0.0000'):
    return Decimal(str(value or 0)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


DOCUMENT_FIELD_ALIASES = {
    'material_cost': ['原材料成本', '材料成本', '物料成本', '原材料'],
    'process_cost': ['工艺成本', '加工成本', '工序成本'],
    'labor_cost': ['人工成本', '人工'],
    'loss_cost': ['损耗成本', '损耗'],
    'package_cost': ['包装成本', '包装'],
    'logistics_cost': ['物流成本', '运费', '物流'],
    'profit_cost': ['利润', '利润成本', '利润空间'],
}


def parse_price_review_document_text(raw_text):
    raw_text = str(raw_text or '').strip()
    parsed_payload = {}
    for field_name, aliases in DOCUMENT_FIELD_ALIASES.items():
        parsed_value = None
        for alias in aliases:
            match = re.search(rf'{re.escape(alias)}\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)', raw_text, re.IGNORECASE)
            if match:
                parsed_value = _to_decimal(match.group(1))
                break
        if parsed_value is not None:
            parsed_payload[field_name] = f'{parsed_value:.4f}'
    return parsed_payload


def normalize_price_components(parsed_payload):
    parsed_payload = parsed_payload or {}
    rows = []
    for component_type, component_name, field_name in COMPONENT_FIELD_MAP:
        amount = _to_decimal(parsed_payload.get(field_name))
        if amount <= 0:
            continue
        rows.append({
            'component_type': component_type,
            'component_name': component_name,
            'amount': amount,
        })
    return rows


def compare_component_amounts(components, reference_map, tolerance_rate=Decimal('0.10')):
    tolerance_rate = Decimal(str(tolerance_rate or 0))
    rows = []
    for component in components or []:
        reference_amount = _to_decimal((reference_map or {}).get(component.get('component_name')))
        amount = _to_decimal(component.get('amount'))
        upper_limit = reference_amount * (Decimal('1') + tolerance_rate)
        rows.append({
            **component,
            'amount': amount,
            'reference_amount': reference_amount,
            'is_abnormal': bool(reference_amount and amount > upper_limit),
        })
    return rows


def build_price_review_conclusion(
    quoted_price,
    component_rows,
    historical_prices,
    market_price,
    target_price,
    deviation_threshold=Decimal('0.10'),
):
    quoted_price = _to_decimal(quoted_price)
    market_price = _to_decimal(market_price)
    target_price = _to_decimal(target_price)
    deviation_threshold = Decimal(str(deviation_threshold or 0))
    abnormal_items = [
        row['component_name']
        for row in (component_rows or [])
        if row.get('is_abnormal')
    ]

    history = [_to_decimal(price) for price in (historical_prices or [])]
    history_average = (
        sum(history, Decimal('0.0000')) / Decimal(len(history))
        if history else Decimal('0.0000')
    )

    benchmark_prices = [price for price in [history_average, market_price, target_price] if price > 0]
    benchmark_price = (
        sum(benchmark_prices, Decimal('0.0000')) / Decimal(len(benchmark_prices))
        if benchmark_prices else Decimal('0.0000')
    )
    allowed_upper_bound = benchmark_price * (Decimal('1') + deviation_threshold)
    exceeds_benchmark = bool(benchmark_price and quoted_price > allowed_upper_bound)

    if exceeds_benchmark or abnormal_items:
        result = 'exception'
        risk_level = 'high' if exceeds_benchmark and abnormal_items else 'medium'
    else:
        result = 'approved'
        risk_level = 'low'

    negotiation_points = []
    if exceeds_benchmark:
        negotiation_points.append('报价高于历史/市场/目标基准')
    negotiation_points.extend(
        f'{component_name}成本偏高'
        for component_name in abnormal_items
    )

    return {
        'result': result,
        'risk_level': risk_level,
        'abnormal_items': abnormal_items,
        'negotiation_points': negotiation_points,
        'benchmark_price': benchmark_price,
        'history_average': history_average,
        'summary': '建议议价复核' if result == 'exception' else '报价处于合理区间',
    }


def build_price_review_report():
    """Build aggregated price review report data."""
    from apps.supply_chain.models import PriceReviewOrder, PriceReviewConclusion, PriceReviewComponent
    from django.db.models import Count, Sum, Avg, Q
    from decimal import Decimal

    total_orders = PriceReviewOrder.objects.count()
    exception_orders = PriceReviewOrder.objects.filter(status=PriceReviewOrder.STATUS_EXCEPTION).count()
    approved_orders = PriceReviewOrder.objects.filter(status=PriceReviewOrder.STATUS_APPROVED).count()
    exception_rate = round(exception_orders / total_orders * 100, 1) if total_orders else 0

    components = PriceReviewComponent.objects.select_related("review_order__inventory_item")
    cost_summary = {}
    abnormal_count = 0
    total_abnormal_amount = Decimal("0")
    for comp in components:
        ctype = comp.component_type
        if ctype not in cost_summary:
            cost_summary[ctype] = {"total": Decimal("0"), "abnormal": Decimal("0"), "count": 0}
        cost_summary[ctype]["total"] += comp.amount
        cost_summary[ctype]["count"] += 1
        if comp.is_abnormal:
            cost_summary[ctype]["abnormal"] += comp.amount
            abnormal_count += 1
            total_abnormal_amount += (comp.amount - comp.reference_amount)

    cost_breakdown = []
    for ctype, data in sorted(cost_summary.items()):
        avg_val = data["total"] / data["count"] if data["count"] else Decimal("0")
        cost_breakdown.append({
            "component_type": ctype,
            "total_amount": str(data["total"]),
            "avg_amount": str(round(avg_val, 4)),
            "abnormal_amount": str(data["abnormal"]),
            "item_count": data["count"],
        })

    conclusions = PriceReviewConclusion.objects.all()
    high_risk = conclusions.filter(risk_level="high").count()
    medium_risk = conclusions.filter(risk_level="medium").count()

    negotiation_items = set()
    for c in conclusions.filter(result="exception"):
        for item in (c.negotiation_points or []):
            negotiation_items.add(item)

    return {
        "total_orders": total_orders,
        "exception_orders": exception_orders,
        "approved_orders": approved_orders,
        "exception_rate": exception_rate,
        "cost_breakdown": cost_breakdown,
        "abnormal_component_count": abnormal_count,
        "total_abnormal_amount": str(total_abnormal_amount),
        "high_risk_count": high_risk,
        "medium_risk_count": medium_risk,
        "negotiation_items": sorted(negotiation_items),
    }
