from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from apps.inventory.models import Inventory, InventoryItem


def _to_decimal(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def build_inventory_analysis_rows():
    rows = []
    for item in InventoryItem.objects.all().order_by('code'):
        inventory_total = Inventory.objects.filter(item=item).aggregate(
            total_quantity=Sum('quantity'),
            total_available=Sum('available_quantity'),
        )
        available_quantity = _to_decimal(inventory_total.get('total_available'))
        total_quantity = _to_decimal(inventory_total.get('total_quantity'))
        safety_stock = _to_decimal(item.safety_stock)
        reorder_point = _to_decimal(item.reorder_point)

        if available_quantity <= safety_stock and safety_stock > 0:
            risk_level = 'high'
            status = '低于安全库存'
        elif reorder_point and available_quantity <= reorder_point:
            risk_level = 'medium'
            status = '接近再订货点'
        else:
            risk_level = 'low'
            status = '库存正常'

        rows.append({
            'item': item,
            'total_quantity': total_quantity,
            'available_quantity': available_quantity,
            'safety_stock': safety_stock,
            'reorder_point': reorder_point,
            'risk_level': risk_level,
            'status': status,
            'coverage_gap': (safety_stock - available_quantity) if safety_stock > available_quantity else Decimal('0.00'),
        })
    return rows


def build_inventory_analysis_summary():
    rows = build_inventory_analysis_rows()
    return {
        'rows': rows,
        'high_risk_count': sum(1 for row in rows if row['risk_level'] == 'high'),
        'medium_risk_count': sum(1 for row in rows if row['risk_level'] == 'medium'),
        'total_items': len(rows),
    }


def build_inventory_deep_analysis():
    """Deep inventory analysis: turnover rate, dead stock, ABC classification."""
    from apps.inventory.models import Inventory, InventoryItem
    from apps.supply_chain.models import OutsourceIssueItem
    from django.db.models import Sum, Q
    from django.utils import timezone
    from decimal import Decimal
    import datetime

    rows = []
    items = InventoryItem.objects.all().order_by("-standard_cost")
    total_value = Decimal("0")

    for item in items:
        inv = Inventory.objects.filter(item=item).aggregate(
            total_qty=Sum("quantity"),
            avail_qty=Sum("available_quantity"),
        )
        total_qty = _to_decimal(inv.get("total_qty"))
        avail_qty = _to_decimal(inv.get("avail_qty"))
        standard_cost = _to_decimal(getattr(item, "standard_cost", 0) or 0)
        item_value = avail_qty * standard_cost
        total_value += item_value

        rows.append({
            "item": item,
            "total_qty": total_qty,
            "avail_qty": avail_qty,
            "standard_cost": standard_cost,
            "item_value": item_value,
        })

    rows.sort(key=lambda r: r["item_value"], reverse=True)
    cumulative = Decimal("0")
    abc_rows = []
    for r in rows:
        cumulative += r["item_value"]
        pct = float(cumulative / total_value * 100) if total_value else 0
        if pct <= 70:
            abc = "A"
        elif pct <= 90:
            abc = "B"
        else:
            abc = "C"
        r["abc_class"] = abc
        r["cumulative_pct"] = round(pct, 1)
        abc_rows.append(r)

    ninety_days_ago = timezone.now() - datetime.timedelta(days=90)
    moved_items = set(
        OutsourceIssueItem.objects.filter(
            issue_order__create_time__gte=ninety_days_ago,
        ).values_list("material_code", flat=True)
    )
    for r in abc_rows:
        code = getattr(r["item"], "code", "")
        r["is_dead_stock"] = code not in moved_items and r["avail_qty"] > 0

    dead_stock_count = sum(1 for r in abc_rows if r.get("is_dead_stock"))
    dead_stock_value = sum(r["item_value"] for r in abc_rows if r.get("is_dead_stock"))

    safety_breach = sum(1 for r in abc_rows if r["avail_qty"] <= _to_decimal(getattr(r["item"], "safety_stock", 0) or 0))

    return {
        "rows": abc_rows,
        "total_value": str(total_value),
        "dead_stock_count": dead_stock_count,
        "dead_stock_value": str(dead_stock_value),
        "safety_breach_count": safety_breach,
        "class_a_count": sum(1 for r in abc_rows if r["abc_class"] == "A"),
        "class_b_count": sum(1 for r in abc_rows if r["abc_class"] == "B"),
        "class_c_count": sum(1 for r in abc_rows if r["abc_class"] == "C"),
    }

