from __future__ import annotations

from apps.ai.services.action_contracts import AIActionRequest


class AIConfirmationService:
    def build_action_request(self, intent_result: dict) -> AIActionRequest | None:
        action = intent_result.get('action')
        resource = intent_result.get('data_type')
        if not action or not resource:
            return None

        entities = dict(intent_result.get('entities') or {})
        object_ids = entities.get('object_ids') or []
        changes = entities.get('changes') or {}

        return AIActionRequest(
            resource=resource,
            operation=action,
            object_ids=object_ids,
            changes=changes,
            filters=entities.get('filters') or {},
            context=entities.get('context') or {},
        )

    def build_confirmation_payload(self, intent_result: dict) -> dict:
        action_request = self.build_action_request(intent_result)
        if not action_request or not intent_result.get('requires_confirmation'):
            return {}

        return {
            'action_plan': {
                'resource': action_request.resource,
                'operation': action_request.operation,
                'object_ids': action_request.object_ids,
                'changes': action_request.changes,
                'filters': action_request.filters,
                'context': action_request.context,
            },
            'confirmation': {
                'required': True,
                'message': intent_result.get('message', '该操作需要确认后执行。'),
            },
        }


confirmation_service = AIConfirmationService()
