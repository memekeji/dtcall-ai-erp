import logging
from typing import Any

from apps.ai.models import AILog


logger = logging.getLogger(__name__)

SUMMARY_PREVIEW_LIMIT = 160


def record_business_ai_result(request: Any, normalized_result: dict, raw_input: Any = None):
    """
    Record a compact audit entry for business AI results.

    The audit log intentionally stores only normalized metadata and a short
    summary preview. It must never block the business response path.
    """
    try:
        if not isinstance(normalized_result, dict):
            return None

        return AILog.objects.create(
            log_type='model_call',
            user=_get_authenticated_user(request),
            content=_build_log_content(normalized_result, raw_input),
            ip_address=_get_client_ip(request),
        )
    except Exception:
        logger.debug('Failed to record business AI audit log', exc_info=True)
        return None


def _build_log_content(normalized_result: dict, raw_input: Any = None) -> dict:
    content = {
        'event': 'business_ai_result',
        'scenario': normalized_result.get('scenario', 'general'),
        'risk_level': normalized_result.get('risk_level', 'unknown'),
        'recommended_action': normalized_result.get('recommended_action', 'manual_review'),
        'confidence': normalized_result.get('confidence', 0.0),
        'requires_confirmation': bool(normalized_result.get('requires_confirmation', False)),
        'source_refs': normalized_result.get('source_refs') or [],
        'risk_point_count': len(normalized_result.get('risk_points') or []),
        'suggestion_count': len(normalized_result.get('suggestions') or []),
        'summary_preview': _preview(normalized_result.get('summary', '')),
    }

    if raw_input is not None:
        content['raw_input_type'] = type(raw_input).__name__
        if isinstance(raw_input, dict):
            content['raw_input_keys'] = sorted(str(key) for key in raw_input.keys())

    return content


def _preview(value: Any) -> str:
    text = str(value or '').strip()
    if len(text) <= SUMMARY_PREVIEW_LIMIT:
        return text
    return f'{text[:SUMMARY_PREVIEW_LIMIT]}...'


def _get_authenticated_user(request: Any):
    user = getattr(request, 'user', None) if request else None
    if user and getattr(user, 'is_authenticated', False) and getattr(user, '_meta', None):
        return user
    return None


def _get_client_ip(request: Any):
    meta = getattr(request, 'META', None) if request else None
    if not meta:
        return None

    forwarded_for = meta.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip() or None
    return meta.get('REMOTE_ADDR')
