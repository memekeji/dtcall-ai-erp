import json
from typing import Any, Iterable

from apps.ai.services.business_audit import record_business_ai_result
from apps.ai.services.business_scenarios import (
    build_business_ai_task_id,
    get_business_ai_task_type,
)


RISK_LEVEL_ALIASES = {
    'high': 'high',
    '严重': 'high',
    '高': 'high',
    '高风险': 'high',
    'medium': 'medium',
    'middle': 'medium',
    '中': 'medium',
    '中等': 'medium',
    '中风险': 'medium',
    'low': 'low',
    '低': 'low',
    '低风险': 'low',
    'none': 'low',
    '无': 'low',
    '无风险': 'low',
}

SUMMARY_KEYS = ('summary', '摘要', 'analysis', '分析', 'result', '结果', 'conclusion', '结论', '建议理由')
RISK_LEVEL_KEYS = ('risk_level', 'risk', '风险等级', '风险级别', '整体风险', 'overall_risk')
RISK_POINT_KEYS = ('risk_points', 'risks', 'issues', '风险点', '异常风险提示', '关键条款缺失或异常', '异常项')
SUGGESTION_KEYS = (
    'suggestions',
    'suggestion',
    'suggested_replies',
    'tags',
    'action_items',
    'key_points',
    '建议',
    '修改建议',
    '审批建议',
    '审核建议',
    '处理建议',
    '回复建议',
    '标签',
    '行动项',
)
ACTION_KEYS = ('recommended_action', 'action', '建议动作', '推荐动作', '审批建议', '审核建议')
CONFIDENCE_KEYS = ('confidence', '置信度', 'score', '评分')


def build_business_ai_result(
    raw_result: Any,
    scenario: str = 'general',
    source_refs: Iterable[Any] | None = None,
    request: Any = None,
    raw_input: Any = None,
) -> dict:
    """
    Normalize a business AI result and record a compact audit entry.
    """
    result = normalize_business_ai_result(raw_result, scenario=scenario, source_refs=source_refs)
    record_business_ai_result(request, result, raw_input=raw_input)
    return result


def normalize_business_ai_result(raw_result: Any, scenario: str = 'general', source_refs: Iterable[Any] | None = None) -> dict:
    """
    Convert varied business AI outputs into a stable API payload.

    Existing business analyzers can return plain text, generic analysis dicts,
    or model-generated JSON text. This function keeps the raw output and exposes
    predictable fields for pages, tests, logging, and later feedback collection.
    """
    payload = _extract_payload(raw_result)
    summary = _first_text(payload, SUMMARY_KEYS) if payload else ''
    risk_points = _coerce_list(_first_value(payload, RISK_POINT_KEYS) if payload else None)
    suggestions = _coerce_list(_first_value(payload, SUGGESTION_KEYS) if payload else None)

    if not summary:
        summary = _fallback_summary(raw_result)

    risk_level = _normalize_risk_level(_first_value(payload, RISK_LEVEL_KEYS) if payload else None)
    recommended_action = _normalize_action(
        _first_value(payload, ACTION_KEYS) if payload else None,
        summary=summary,
        suggestions=suggestions,
        risk_level=risk_level,
    )
    confidence = _normalize_confidence(_first_value(payload, CONFIDENCE_KEYS) if payload else None)

    result = {
        'scenario': scenario or 'general',
        'summary': summary,
        'risk_level': risk_level,
        'risk_points': risk_points,
        'suggestions': suggestions,
        'recommended_action': recommended_action,
        'confidence': confidence,
        'source_refs': list(source_refs or []),
        'requires_confirmation': _requires_confirmation(risk_level, recommended_action),
        'raw_result': raw_result,
    }
    result['feedback_context'] = _build_feedback_context(result)
    result.update(_extra_payload_fields(payload, result))
    return result


def _extract_payload(raw_result: Any) -> dict | None:
    if isinstance(raw_result, dict):
        payload = dict(raw_result)
        analysis_payload = _parse_json_text(payload.get('analysis'))
        if isinstance(analysis_payload, dict):
            return {**analysis_payload, **payload}
        return payload

    parsed = _parse_json_text(raw_result)
    return parsed if isinstance(parsed, dict) else None


def _parse_json_text(value: Any) -> Any:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    if text.startswith('```'):
        text = text.strip('`').strip()
        if text.lower().startswith('json'):
            text = text[4:].strip()

    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _first_value(payload: dict | None, keys: Iterable[str]) -> Any:
    if not payload:
        return None

    for key in keys:
        value = payload.get(key)
        if value not in (None, ''):
            return value
    return None


def _extra_payload_fields(payload: dict | None, current_result: dict) -> dict:
    if not payload:
        return {}

    reserved_keys = set(current_result.keys())
    return {
        key: value
        for key, value in payload.items()
        if key not in reserved_keys
    }


def _build_feedback_context(result: dict) -> dict:
    return {
        'endpoint': '/ai/business-feedback/',
        'payload': {
            'task_id': build_business_ai_task_id(result.get('scenario'), result.get('source_refs')),
            'task_type': get_business_ai_task_type(result.get('scenario')),
            'scenario': result.get('scenario', 'general'),
            'summary': result.get('summary', ''),
            'risk_level': result.get('risk_level', 'unknown'),
            'recommended_action': result.get('recommended_action', 'manual_review'),
            'confidence': result.get('confidence', 0.0),
            'source_refs': result.get('source_refs') or [],
        },
    }


def _first_text(payload: dict | None, keys: Iterable[str]) -> str:
    value = _first_value(payload, keys)
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _fallback_summary(raw_result: Any) -> str:
    if raw_result is None:
        return ''
    if isinstance(raw_result, str):
        return raw_result.strip()
    if isinstance(raw_result, (dict, list)):
        return json.dumps(raw_result, ensure_ascii=False)
    return str(raw_result)


def _coerce_list(value: Any) -> list:
    if value in (None, ''):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [json.dumps(value, ensure_ascii=False)]
    return [str(value).strip()] if str(value).strip() else []


def _normalize_risk_level(value: Any) -> str:
    if value in (None, ''):
        return 'unknown'

    text = str(value).strip().lower()
    if text in RISK_LEVEL_ALIASES:
        return RISK_LEVEL_ALIASES[text]

    for alias, level in RISK_LEVEL_ALIASES.items():
        if alias and alias in text:
            return level
    return 'unknown'


def _normalize_confidence(value: Any) -> float:
    if value in (None, ''):
        return 0.0

    raw_text = str(value)
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0

    if '%' in raw_text and confidence > 1:
        confidence = confidence / 100
    return round(max(0.0, min(1.0, confidence)), 4)


def _normalize_action(value: Any, *, summary: str, suggestions: list, risk_level: str) -> str:
    text = ' '.join([str(value or ''), summary, ' '.join(suggestions)]).lower()

    if any(word in text for word in ('拒绝', '驳回', 'reject', 'deny')):
        return 'reject'
    if any(word in text for word in ('补充', '补交', '更多材料', 'request more', 'more info')):
        return 'request_more_info'
    if any(word in text for word in ('通过', '同意', 'approve', 'accept')):
        return 'approve'
    if risk_level == 'high':
        return 'manual_review'
    return 'manual_review'


def _requires_confirmation(risk_level: str, recommended_action: str) -> bool:
    return risk_level == 'high' or recommended_action in {
        'approve',
        'reject',
        'request_more_info',
    }
