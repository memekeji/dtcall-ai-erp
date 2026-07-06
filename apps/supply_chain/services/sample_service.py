from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def _to_decimal(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def generate_sample_request_code(current_date=None, sequence=1):
    current_date = current_date or date.today()
    return f'SMP-{current_date:%Y%m%d}-{int(sequence):03d}'


def build_receipt_payload(
    material_name,
    specification,
    engineer_name,
    location,
    received_quantity,
):
    received_quantity = _to_decimal(received_quantity)
    location = location or '待确认地点'
    engineer_name = engineer_name or '相关工程师'
    material_name = material_name or '样品'
    specification = specification or ''
    spec_text = f'（{specification}）' if specification else ''

    return {
        'request_status': 'pickup_pending',
        'received_quantity': received_quantity,
        'notification_title': f'样品到货提醒: {material_name}',
        'notification_message': (
            f'{engineer_name}，{material_name}{spec_text} 已到货 {received_quantity} 件，'
            f'请前往 {location} 领样。'
        ),
    }


def is_pickup_overdue(received_at, pickup_deadline_hours=24, current_time=None):
    current_time = current_time or received_at
    if not received_at or not current_time:
        return False
    elapsed_seconds = (current_time - received_at).total_seconds()
    return elapsed_seconds > int(pickup_deadline_hours or 0) * 3600


def get_sample_statistics():
    """Return monthly/quarterly sample statistics."""
    from apps.supply_chain.models import SampleRequest, SampleReceipt, SamplePickupRecord
    from django.db.models import Count, Avg, Q
    from django.utils import timezone
    import datetime

    now = timezone.now()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (this_month_start - datetime.timedelta(days=1)).replace(day=1)
    three_months_ago = now - datetime.timedelta(days=90)

    total_all = SampleRequest.objects.count()
    this_month_total = SampleRequest.objects.filter(create_time__gte=this_month_start).count()
    picked_up = SampleRequest.objects.filter(status=SampleRequest.STATUS_PICKED_UP).count()
    closed = SampleRequest.objects.filter(status=SampleRequest.STATUS_CLOSED).count()
    success_count = picked_up + closed
    success_rate = round(success_count / total_all * 100, 1) if total_all else 0

    receipts = SampleReceipt.objects.filter(received_at__gte=three_months_ago)
    total_receipts = receipts.count()
    if total_receipts:
        from django.db.models import F
        avg_delivery_hours = sum(
            (r.received_at - r.sample_request.create_time).total_seconds() / 3600
            for r in receipts.select_related("sample_request")
            if r.sample_request and r.sample_request.create_time
        ) / total_receipts
    else:
        avg_delivery_hours = 0

    pickups = SamplePickupRecord.objects.filter(picked_at__isnull=False, picked_at__gte=three_months_ago)
    total_pickups = pickups.count()
    if total_pickups:
        avg_pickup_hours = sum(
            (p.picked_at - p.sample_request.receipts.order_by("received_at").first().received_at).total_seconds() / 3600
            for p in pickups.select_related("sample_request__receipts")
            if p.sample_request and p.sample_request.receipts.exists()
        ) / total_pickups
    else:
        avg_pickup_hours = 0

    overdue = SampleRequest.objects.filter(
        status=SampleRequest.STATUS_PICKUP_PENDING,
        receipts__isnull=False,
    ).count()

    monthly_data = []
    for offset in range(5, -1, -1):
        m_start = (this_month_start.replace(day=1) - datetime.timedelta(days=offset * 31)).replace(day=1)
        m_end = (m_start + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
        m_total = SampleRequest.objects.filter(create_time__gte=m_start, create_time__lte=m_end).count()
        m_done = SampleRequest.objects.filter(
            create_time__gte=m_start, create_time__lte=m_end,
            status__in=[SampleRequest.STATUS_PICKED_UP, SampleRequest.STATUS_CLOSED],
        ).count()
        monthly_data.append({
            "month": m_start.strftime("%Y-%m"),
            "label": m_start.strftime("%m月"),
            "total": m_total,
            "done": m_done,
            "rate": round(m_done / m_total * 100, 1) if m_total else 0,
        })

    return {
        "total_all": total_all,
        "this_month_total": this_month_total,
        "success_count": success_count,
        "success_rate": success_rate,
        "avg_delivery_hours": round(avg_delivery_hours, 1),
        "avg_pickup_hours": round(avg_pickup_hours, 1),
        "overdue_count": overdue,
        "monthly_data": monthly_data,
    }


def build_reminder_message(sample_request, receipt, reminder_count):
    """Build overdue second-reminder notification payload."""
    engineer_name = (
        getattr(sample_request.engineer, "name", "")
        or getattr(sample_request.engineer, "username", "")
        or "相关工程师"
    )
    material = sample_request.material_name or "样品"
    spec = f"（{sample_request.specification}）" if sample_request.specification else ""
    location = receipt.location or "待确认地点"
    return {
        "notification_title": f"【二次提醒】样品待领: {material}",
        "notification_message": (
            f"{engineer_name}，{material}{spec} 已于 {receipt.received_at.strftime('%m月%d日 %H:%M')} 到货，"
            f"这是第 {reminder_count + 1} 次提醒，请尽快前往 {location} 领样以免超期。"
        ),
    }
