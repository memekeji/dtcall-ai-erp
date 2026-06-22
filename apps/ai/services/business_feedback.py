import json
from typing import Any

from apps.ai.models import AIFeedback
from apps.ai.services.business_scenarios import (
    build_business_ai_task_id,
    get_business_ai_task_type,
)

TEXT_LIMIT = 8000
COMMENT_LIMIT = 1000


def record_business_ai_feedback(request: Any, payload: dict):
    if not isinstance(payload, dict):
        raise ValueError('反馈数据格式不正确')

    payload = _flatten_feedback_context(payload)
    rating = _normalize_rating(payload.get('rating'))
    scenario = str(payload.get('scenario') or 'general')
    source_refs = payload.get('source_refs') or []
    task_type = payload.get('task_type') or get_business_ai_task_type(scenario)

    feedback = AIFeedback.objects.create(
        task_id=payload.get('task_id') or build_business_ai_task_id(scenario, source_refs),
        task_type=task_type if task_type in _valid_task_types() else 'other',
        user=_get_authenticated_user(request),
        rating=rating,
        comment=_truncate(payload.get('comment', ''), COMMENT_LIMIT),
        ai_output=_build_ai_output(payload),
        input_content=_build_input_content(scenario, source_refs),
        model_config_id=None,
    )
    return feedback


def _flatten_feedback_context(payload: dict) -> dict:
    feedback_context = payload.get('feedback_context')
    if not isinstance(feedback_context, dict):
        return payload

    context_payload = feedback_context.get('payload')
    if not isinstance(context_payload, dict):
        return payload

    merged = dict(context_payload)
    for key, value in payload.items():
        if key != 'feedback_context':
            merged[key] = value
    return merged


def _normalize_rating(value: Any) -> int:
    try:
        rating = int(value)
    except (TypeError, ValueError):
        raise ValueError('评分必须是 1-5 的整数')

    if rating < 1 or rating > 5:
        raise ValueError('评分必须是 1-5 的整数')
    return rating


def _valid_task_types() -> set[str]:
    return {value for value, _label in AIFeedback.TASK_TYPES}


def _build_ai_output(payload: dict) -> str:
    safe_payload = {
        'scenario': payload.get('scenario'),
        'summary': payload.get('summary') or payload.get('ai_output') or '',
        'risk_level': payload.get('risk_level'),
        'recommended_action': payload.get('recommended_action'),
        'confidence': payload.get('confidence'),
        'source_refs': payload.get('source_refs') or [],
    }
    return _truncate(json.dumps(safe_payload, ensure_ascii=False), TEXT_LIMIT)


def _build_input_content(scenario: str, source_refs: Any) -> str:
    return _truncate(
        json.dumps(
            {
                'scenario': scenario,
                'source_refs': source_refs if isinstance(source_refs, list) else [],
            },
            ensure_ascii=False,
        ),
        TEXT_LIMIT,
    )


def _truncate(value: Any, limit: int) -> str:
    text = str(value or '').strip()
    if len(text) <= limit:
        return text
    return f'{text[:limit]}...'


def _get_authenticated_user(request: Any):
    user = getattr(request, 'user', None) if request else None
    if user and getattr(user, 'is_authenticated', False) and getattr(user, '_meta', None):
        return user
    return None
