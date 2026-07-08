from __future__ import annotations

from decimal import Decimal, InvalidOperation

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class WarehouseModuleAdapter(AIBaseModuleAdapter):
    resource = 'warehouse'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'name', 'code'}
    allowed_fields = {
        'name',
        'code',
        'warehouse_type',
        'address',
        'manager_id',
        'phone',
        'email',
        'capacity',
        'used_capacity',
        'status',
        'is_default',
        'remark',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持仓库操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'仓库创建缺少必填字段: {", ".join(missing)}'}
        elif not action.object_ids:
            return {'success': False, 'message': '仓库操作缺少目标记录'}

        if action.operation != 'delete':
            invalid = sorted(set((action.changes or {}).keys()) - self.allowed_fields)
            if invalid:
                return {'success': False, 'message': f'仓库操作包含不允许的字段: {", ".join(invalid)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, partial=False)
            if not normalized['success']:
                return normalized
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, normalized['payload'], 'create')]}

        warehouse = self._get_warehouse_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_warehouse(warehouse)
        if action.operation == 'delete':
            return {'success': True, 'change_set': [self._build_change_set(getattr(warehouse, 'id', action.object_ids[0]), before_snapshot, None, 'delete', sorted(before_snapshot.keys()))]}

        normalized = self._normalize_payload(action.changes or {}, partial=True)
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(normalized['payload'])
        return {'success': True, 'change_set': [self._build_change_set(getattr(warehouse, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.inventory.models import Warehouse

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, partial=False)
            if not normalized['success']:
                return normalized
            warehouse = Warehouse.objects.create(**normalized['payload'])
            snapshot = self._snapshot_warehouse(warehouse)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(warehouse.id, None, snapshot, 'create', sorted(snapshot.keys()))]}

        warehouse = self._get_warehouse_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            warehouse.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {}, partial=True)
        if not normalized['success']:
            return normalized
        for field, value in normalized['payload'].items():
            setattr(warehouse, field, value)
        warehouse.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'inventory.add_warehouse',
            'update': 'inventory.change_warehouse',
            'delete': 'inventory.delete_warehouse',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作仓库' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes, partial=False):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'manager_id', 'status'}:
                    payload[field] = int(value) if value not in (None, '') else 0
                elif field in {'capacity', 'used_capacity'}:
                    payload[field] = Decimal(str(value))
                elif field == 'is_default':
                    payload[field] = self._to_bool(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '仓库字段格式无效，请检查管理员、容量和状态'}

        if not partial:
            payload.setdefault('warehouse_type', 'main')
            payload.setdefault('address', '')
            payload.setdefault('manager_id', None)
            payload.setdefault('phone', '')
            payload.setdefault('email', '')
            payload.setdefault('capacity', Decimal('0'))
            payload.setdefault('used_capacity', Decimal('0'))
            payload.setdefault('status', 1)
            payload.setdefault('is_default', False)
            payload.setdefault('remark', '')
        return {'success': True, 'payload': self._snapshot_dict(payload)}

    def _get_warehouse_for_action(self, warehouse_id, user):
        from apps.inventory.models import Warehouse

        return Warehouse.objects.get(id=warehouse_id)

    def _snapshot_warehouse(self, warehouse):
        return self._snapshot_dict({
            'name': getattr(warehouse, 'name', ''),
            'code': getattr(warehouse, 'code', ''),
            'warehouse_type': getattr(warehouse, 'warehouse_type', 'main'),
            'address': getattr(warehouse, 'address', ''),
            'manager_id': getattr(warehouse, 'manager_id', None),
            'phone': getattr(warehouse, 'phone', ''),
            'email': getattr(warehouse, 'email', ''),
            'capacity': getattr(warehouse, 'capacity', 0),
            'used_capacity': getattr(warehouse, 'used_capacity', 0),
            'status': getattr(warehouse, 'status', 1),
            'is_default': getattr(warehouse, 'is_default', False),
            'remark': getattr(warehouse, 'remark', ''),
        })

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'inventory',
            'model_name': 'Warehouse',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or before_snapshot or {}).keys()),
        }

    def _snapshot_dict(self, payload):
        normalized = {}
        for key, value in (payload or {}).items():
            if isinstance(value, Decimal):
                normalized[key] = str(value)
            else:
                normalized[key] = value
        return normalized

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on', '是'}
