from decimal import Decimal

from apps.message.services import MessageService
from apps.supply_chain.models import SupplyChainEventLog


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def log_supply_chain_event(event_type, title, object_type='', object_id=None, payload=None, operator=None):
    return SupplyChainEventLog.objects.create(
        event_type=event_type,
        title=title,
        object_type=object_type,
        object_id=object_id,
        payload=_json_safe(payload or {}),
        operator=operator,
    )


def send_supply_chain_notification(
    *,
    title,
    content,
    user_ids,
    related_object_type,
    related_object_id,
    action_url='',
    sender=None,
    priority=2,
):
    if not user_ids:
        return None
    return MessageService.send_notification(
        title=title,
        content=content,
        category_code='system',
        user_ids=user_ids,
        sender=sender,
        priority=priority,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        action_url=action_url,
    )
