from django.db import transaction
from django.utils import timezone

from apps.supply_chain.models import SupplyChainAIInsight


def get_ai_insight(scope, object_type, object_id=0):
    return SupplyChainAIInsight.objects.filter(
        scope=scope,
        object_type=object_type,
        object_id=object_id,
    ).first()


@transaction.atomic
def refresh_ai_insight(*, scope, object_type, object_id, generator, user=None, input_hash=''):
    insight = SupplyChainAIInsight.objects.select_for_update().filter(
        scope=scope,
        object_type=object_type,
        object_id=object_id,
    ).first()
    try:
        result = generator()
        if isinstance(result, str):
            result = {'content': result}
        if not isinstance(result, dict):
            raise ValueError('AI返回格式无效')
        if result.get('error'):
            raise ValueError(str(result['error']))
        content = str(result.get('content') or result.get('summary') or '').strip()
        if not content:
            raise ValueError('AI未返回有效结论')
        values = {
            'status': SupplyChainAIInsight.STATUS_SUCCESS,
            'input_hash': input_hash,
            'content': content,
            'result_payload': result,
            'error_message': '',
            'generated_by': user,
            'generated_at': timezone.now(),
        }
    except Exception as exc:
        values = {
            'status': SupplyChainAIInsight.STATUS_ERROR,
            'input_hash': input_hash,
            'content': insight.content if insight else '',
            'result_payload': insight.result_payload if insight else {},
            'error_message': str(exc),
            'generated_by': user,
            'generated_at': timezone.now(),
        }

    if insight is None:
        insight = SupplyChainAIInsight.objects.create(
            scope=scope,
            object_type=object_type,
            object_id=object_id,
            **values,
        )
    else:
        for field_name, value in values.items():
            setattr(insight, field_name, value)
        insight.save(update_fields=[*values.keys(), 'update_time'])
    return insight
