from datetime import date

from django.db import transaction
from django.db.models import F

from apps.supply_chain.models import SupplyChainSequence


def generate_business_code(prefix, current_date=None):
    business_date = current_date or date.today()
    normalized_prefix = str(prefix or '').strip().upper()
    if not normalized_prefix:
        raise ValueError('业务编号前缀不能为空')

    with transaction.atomic():
        sequence, _ = SupplyChainSequence.objects.get_or_create(
            prefix=normalized_prefix,
            business_date=business_date,
            defaults={'current_value': 0},
        )
        SupplyChainSequence.objects.filter(pk=sequence.pk).update(
            current_value=F('current_value') + 1,
        )
        sequence.refresh_from_db(fields=['current_value'])

    return f'{normalized_prefix}-{business_date:%Y%m%d}-{sequence.current_value:03d}'
