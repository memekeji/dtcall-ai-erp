from __future__ import annotations

from apps.ai.services.action_contracts import AIActionRequest


class AIConfirmationService:
    RESOURCE_NORMALIZERS = {
        'disk_share': ('disk', {'model': 'share'}),
        'disk_folder': ('disk', {'model': 'folder'}),
        'finance_invoice': ('finance', {'model': 'invoice'}),
        'finance_expense': ('finance', {'model': 'expense'}),
        'finance_income': ('finance', {'model': 'income'}),
        'finance_order_record': ('finance', {'model': 'order_record'}),
        'expense': ('finance', {'model': 'expense'}),
        'income': ('finance', {'model': 'income'}),
        'invoice': ('finance', {'model': 'invoice'}),
        'payment': ('finance', {'model': 'payment'}),
    }

    def build_action_request(self, intent_result: dict) -> AIActionRequest | None:
        action = intent_result.get('action')
        resource = intent_result.get('data_type')
        if not action or not resource:
            return None

        entities = dict(intent_result.get('entities') or {})
        normalized_resource, normalized_context = self._normalize_resource(
            resource,
            entities.get('context') or {},
        )
        object_ids = entities.get('object_ids') or []
        changes = entities.get('changes') or {}

        return AIActionRequest(
            resource=normalized_resource,
            operation=action,
            object_ids=object_ids,
            changes=changes,
            filters=entities.get('filters') or {},
            context=normalized_context,
        )

    def _normalize_resource(self, resource: str, context: dict) -> tuple[str, dict]:
        merged_context = dict(context or {})
        normalized = self.RESOURCE_NORMALIZERS.get(resource)
        if not normalized:
            return resource, merged_context

        normalized_resource, inferred_context = normalized
        for key, value in (inferred_context or {}).items():
            merged_context.setdefault(key, value)
        return normalized_resource, merged_context

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
