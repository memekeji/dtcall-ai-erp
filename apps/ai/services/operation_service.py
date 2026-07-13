from __future__ import annotations

import secrets

from django.db import transaction
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
        operation = AIOperation.objects.select_related('confirmation').get(id=operation_id, user=user)
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

        if operation.status != 'preview':
            return {
                'success': False,
                'message': '该操作已处理，无法再次确认',
            }

        self._repair_preview_payload_if_needed(operation, user)

        with transaction.atomic():
            confirmation.is_used = True
            confirmation.confirmed_by = user
            confirmation.confirmed_at = timezone.now()
            confirmation.save(update_fields=['is_used', 'confirmed_by', 'confirmed_at'])

            operation.status = 'confirmed'
            operation.confirmed_payload = dict(operation.preview_payload or {})
            operation.save(update_fields=['status', 'confirmed_payload', 'updated_at'])

            gateway = AIActionGateway()
            gateway_result = gateway.execute_confirmed_action(operation, user)
            success = bool(gateway_result.get('success'))
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

            operation.status = 'executed' if success else 'failed'
            update_fields = ['status', 'updated_at']
            if success:
                operation.executed_at = timezone.now()
                update_fields.append('executed_at')
            operation.save(update_fields=update_fields)
        return {
            'success': success,
            'message': gateway_result.get('message', ''),
            'operation_id': operation.id,
            'gateway_result': gateway_result,
        }

    def _repair_preview_payload_if_needed(self, operation, user):
        preview_payload = dict(operation.preview_payload or {})
        changes = dict(preview_payload.get('changes') or {})
        resource_type = getattr(operation, 'resource_type', preview_payload.get('resource', ''))
        operation_type = getattr(operation, 'operation_type', preview_payload.get('operation', ''))
        if (
                resource_type != 'approval' or
                operation_type != 'create' or
                (changes.get('title') and changes.get('flow_id'))):
            return

        ai_message = getattr(operation, 'ai_message', None)
        runtime_payload = dict(getattr(ai_message, 'runtime_payload', None) or {})
        if not runtime_payload:
            return

        user_message = getattr(operation, 'user_message', None)
        original_query = getattr(user_message, 'content', '') or runtime_payload.get('original_query') or runtime_payload.get('query') or ''
        repair_payload = dict(runtime_payload)
        repair_payload.setdefault('requires_confirmation', True)
        repair_payload.setdefault('action', operation_type)
        repair_payload.setdefault('data_type', resource_type)
        repair_payload.setdefault('original_query', original_query)
        repair_payload.setdefault('query', original_query)

        from apps.ai.services.confirmation_service import confirmation_service

        repaired = confirmation_service.build_confirmation_payload(repair_payload, user=user)
        action_plan = repaired.get('action_plan') or {}
        repaired_changes = dict(action_plan.get('changes') or {})
        if not (repaired_changes.get('title') and repaired_changes.get('flow_id')):
            return

        operation.preview_payload = action_plan
        operation.save(update_fields=['preview_payload', 'updated_at'])


    def match_pending_operation_command(self, message: str):
        normalised = (message or "").strip()
        if not normalised:
            return None
        exact_confirm = {"确认", "执行", "继续", "可以", "好的", "行", "好", "嗯", "对", "是", "yes", "ok", "确定", "就这么办", "没问题"}
        exact_cancel = {"取消", "不要了", "算了", "不执行", "撤回", "不了", "别执行", "停下", "中止", "停止", "撤销"}
        exact_rollback = {"回退", "撤销上一步", "回滚", "回退刚才", "撤销刚才"}
        if normalised in exact_confirm:
            return "confirm"
        if normalised in exact_cancel:
            return "cancel"
        if normalised in exact_rollback:
            return "rollback"
        if len(normalised) <= 20:
            if any(kw in normalised for kw in ["确认执行", "确定执行", "确认提交", "执行吧", "就这么办"]):
                return "confirm"
            if any(kw in normalised for kw in ["取消操作", "取消吧", "不要执行", "别执行", "算了吧"]):
                return "cancel"
            if any(kw in normalised for kw in ["回退", "回滚", "撤销"]):
                return "rollback"
            if any(kw in normalised for kw in ["查", "看", "列表", "明细", "多少", "几个", "项目", "客户", "合同", "审批"]):
                return None
        return None

    def get_latest_preview_operation(self, user, chat_id=None):
        filters = {"user": user, "status": "preview"}
        if chat_id is not None:
            filters["chat_id"] = chat_id
        from apps.ai.models_operation import AIOperation
        return AIOperation.objects.filter(**filters).order_by("-created_at").first()

    def get_latest_executed_operation(self, user, chat_id=None):
        filters = {"user": user, "status": "executed"}
        if chat_id is not None:
            filters["chat_id"] = chat_id
        from apps.ai.models_operation import AIOperation
        return AIOperation.objects.filter(**filters).order_by("-executed_at", "-created_at").first()

    def cancel_operation(self, operation_id, token, user):
        from apps.ai.models_operation import AIOperation
        operation = AIOperation.objects.select_related("confirmation").get(
            id=operation_id,
            user=user,
        )
        confirmation = operation.confirmation
        if confirmation.token != token:
            return {"success": False, "message": "确认令牌无效"}
        if getattr(confirmation, "is_used", False):
            return {"success": False, "message": "确认令牌已使用"}
        if operation.status != "preview":
            return {"success": False, "message": "该操作已处理，无法取消"}
        operation.status = "cancelled"
        operation.save(update_fields=["status", "updated_at"])
        return {
            "success": True,
            "message": "已取消上一步待确认操作，本次不会写入任何数据。",
            "operation_id": operation.id,
        }

operation_service = AIOperationService()
