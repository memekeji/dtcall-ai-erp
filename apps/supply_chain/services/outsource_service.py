from decimal import Decimal, ROUND_HALF_UP


def _to_decimal(value):
    return Decimal(str(value or 0))


def build_issue_item_payload(bom_item, plan_quantity, inventory_lookup):
    bom_quantity = _to_decimal(bom_item.get('quantity'))
    plan_quantity = _to_decimal(plan_quantity)
    required_quantity = (bom_quantity * plan_quantity).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )

    inventory_data = (inventory_lookup or {}).get(bom_item.get('material_code'), {})
    available_quantity = _to_decimal(inventory_data.get('available_quantity'))
    shortage_quantity = required_quantity - available_quantity
    if shortage_quantity < 0:
        shortage_quantity = Decimal('0')

    specification = inventory_data.get('specification') or bom_item.get('specification') or ''
    status = 'shortage' if shortage_quantity > 0 else 'ready'

    return {
        'material_name': bom_item.get('material_name', ''),
        'material_code': bom_item.get('material_code', ''),
        'specification': specification,
        'required_quantity': required_quantity,
        'available_quantity': available_quantity.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'shortage_quantity': shortage_quantity.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'status': status,
    }


def summarize_issue_order_status(items):
    statuses = {item.get('status') for item in items or []}
    if not statuses:
        return 'checking'
    if 'shortage' in statuses or 'spec_mismatch' in statuses:
        return 'shortage'
    if statuses == {'ready'}:
        return 'ready'
    return 'checking'
