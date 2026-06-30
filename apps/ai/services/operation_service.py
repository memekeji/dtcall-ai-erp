from __future__ import annotations

import secrets

from django.utils import timezone

from apps.ai.models import AIOperation, AIOperationChangeSet, AIOperationConfirmation
from apps.ai.services.action_gateway import AIActionGateway


class AIOperationService:
    def create_preview_operation(self, user, chat, user_message, ai_message, payload):
        action_plan = payload.get('action_plan')
        confirmation = payload.get('confirmation') or {}
        if not action_plan or not confirmation.get('required'):
            return None

        token = secrets.token_urlsafe(16)
        operation = AIOperation.objects.create(
            user=user,
            chat=chat,
            user_message=user_message,
            ai_message=ai_message,
            operation_type=action_plan.get('operation', ''),
            resource_type=action_plan.get('resource', ''),
            status='preview',
            preview_payload=action_plan,
            confirmed_payload={},
            confirmation_token=token,
            requires_confirmation=True,
        )
        AIOperationConfirmation.objects.create(
            operation=operation,
            token=token,
        )
        return operation

    def confirm_operation(self, operation_id, token, user):
        operation = AIOperation.objects.select_related('confirmation').get(id=operation_id)
        confirmation = operation.confirmation

        if confirmation.token != token:
            return {
                'success': False,
                'message': '确认令牌无效',
            }

        if confirmation.is_used:
            return {
                'success': False,
                'message': '确认令牌已使用',
            }

        confirmation.is_used = True
        confirmation.confirmed_by = user
        confirmation.confirmed_at = timezone.now()
        confirmation.save(update_fields=['is_used', 'confirmed_by', 'confirmed_at'])

        operation.status = 'confirmed'
        operation.confirmed_payload = dict(operation.preview_payload or {})
        operation.save(update_fields=['status', 'confirmed_payload', 'updated_at'])

        gateway = AIActionGateway()
        gateway_result = gateway.execute_confirmed_action(operation, user)
        for index, item in enumerate(gateway_result.get('change_set', []), start=1):
            AIOperationChangeSet.objects.create(
                operation=operation,
                sequence=index,
                app_label=item.get('app_label', ''),
                model_name=item.get('model_name', ''),
                object_pk=str(item.get('object_pk', '')),
                change_type=item.get('change_type', 'update'),
                before_snapshot=item.get('before_snapshot'),
                after_snapshot=item.get('after_snapshot'),
                changed_fields=item.get('changed_fields', []),
                is_rollback_supported=True,
                rollback_metadata=item.get('rollback_metadata', {}),
            )

        operation.status = 'executed'
        operation.executed_at = timezone.now()
        operation.save(update_fields=['status', 'executed_at', 'updated_at'])
        return {
            'success': bool(gateway_result.get('success')),
            'message': gateway_result.get('message', ''),
            'operation_id': operation.id,
            'gateway_result': gateway_result,
        }


operation_service = AIOperationService()
