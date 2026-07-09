from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class AlertModuleAdapter(AIBaseModuleAdapter):
    resource = 'alert'
    permission_guard = AIPermissionGuard()
    allowed_update_fields = {'status', 'handle_remark'}

    def validate(self, action):
        if action.operation not in {'update', 'delete', 'approve', 'reject'}:
            return {'success': False, 'message': f'暂不支持库存预警操作: {action.operation}'}
        if not action.object_ids:
            return {'success': False, 'message': '库存预警操作缺少目标记录'}
        if action.operation == 'update':
            invalid = sorted(set((action.changes or {}).keys()) - self.allowed_update_fields)
            if invalid:
                return {'success': False, 'message': f'库存预警更新包含不允许的字段: {", ".join(invalid)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        alert = self._get_alert_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_alert(alert)

        if action.operation == 'delete':
            return {
                'success': True,
                'change_set': [
                    self._build_change_set(
                        getattr(alert, 'id', action.object_ids[0]),
                        before_snapshot,
                        None,
                        'delete',
                        sorted(before_snapshot.keys()),
                    )
                ],
            }

        after_snapshot = dict(before_snapshot)
        if action.operation == 'update':
            normalized = self._normalize_update_payload(action.changes or {})
            if not normalized.get('success'):
                return normalized
            after_snapshot.update(normalized['payload'])
            changed_fields = sorted(normalized['payload'].keys())
        else:
            after_snapshot.update({
                'status': 2 if action.operation == 'approve' else 3,
                'handler_id': getattr(user, 'id', None),
                'handle_time': 'NOW',
                'handle_remark': action.changes.get('handle_remark', before_snapshot.get('handle_remark', '')),
            })
            changed_fields = ['status', 'handler_id', 'handle_time', 'handle_remark']

        return {
            'success': True,
            'change_set': [
                self._build_change_set(
                    getattr(alert, 'id', action.object_ids[0]),
                    before_snapshot,
                    after_snapshot,
                    'update',
                    changed_fields,
                )
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        alert = self._get_alert_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            alert.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        if action.operation == 'update':
            normalized = self._normalize_update_payload(action.changes or {})
            if not normalized.get('success'):
                return normalized
            for field, value in normalized['payload'].items():
                setattr(alert, field, value)
            alert.save()
            return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

        alert.status = 2 if action.operation == 'approve' else 3
        alert.handler_id = getattr(user, 'id', None)
        alert.handle_time = timezone.now()
        alert.handle_remark = action.changes.get('handle_remark', getattr(alert, 'handle_remark', ''))
        alert.save()
        return {'success': True, 'message': action.operation, 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'update': 'inventory.change_inventoryalert',
            'delete': 'inventory.delete_inventoryalert',
            'approve': 'inventory.change_inventoryalert',
            'reject': 'inventory.change_inventoryalert',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法处理库存预警' if not result.allowed else 'allowed'}

    def _get_alert_for_action(self, alert_id, user):
        from apps.inventory.models import InventoryAlert

        return InventoryAlert.objects.select_related('item', 'warehouse', 'handler').get(id=alert_id)

    def _normalize_update_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field == 'status':
                    payload[field] = int(value) if value not in (None, '') else 1
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '库存预警字段格式无效，请检查状态和处理说明'}
        return {'success': True, 'payload': payload}

    def _snapshot_alert(self, alert):
        return self._snapshot_dict({
            'item_id': getattr(alert, 'item_id', None),
            'warehouse_id': getattr(alert, 'warehouse_id', None),
            'alert_type': getattr(alert, 'alert_type', ''),
            'current_quantity': getattr(alert, 'current_quantity', Decimal('0')),
            'threshold_value': getattr(alert, 'threshold_value', Decimal('0')),
            'message': getattr(alert, 'message', ''),
            'status': getattr(alert, 'status', 1),
            'handler_id': getattr(alert, 'handler_id', getattr(getattr(alert, 'handler', None), 'id', None)),
            'handle_time': getattr(alert, 'handle_time', None),
            'handle_remark': getattr(alert, 'handle_remark', ''),
            'create_time': getattr(alert, 'create_time', None),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, Decimal):
                snapshot[field] = format(value, 'f')
            elif isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'inventory',
            'model_name': 'InventoryAlert',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or before_snapshot or {}).keys()),
        }
