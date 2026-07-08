from __future__ import annotations

from decimal import Decimal, InvalidOperation

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class InventoryModuleAdapter(AIBaseModuleAdapter):
    resource = 'inventory'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'name', 'code', 'unit'}
    allowed_fields = {
        'name',
        'code',
        'category_id',
        'specification',
        'unit',
        'weight',
        'length',
        'width',
        'height',
        'volume',
        'barcode',
        'qr_code',
        'standard_cost',
        'average_cost',
        'latest_cost',
        'retail_price',
        'wholesale_price',
        'min_stock',
        'max_stock',
        'reorder_point',
        'safety_stock',
        'shelf_life',
        'status',
        'image',
        'description',
    }
    decimal_fields = {
        'weight',
        'length',
        'width',
        'height',
        'volume',
        'standard_cost',
        'average_cost',
        'latest_cost',
        'retail_price',
        'wholesale_price',
        'min_stock',
        'max_stock',
        'reorder_point',
        'safety_stock',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持库存物料操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'库存物料创建缺少必填字段: {", ".join(missing)}'}
            invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
            if invalid:
                return {'success': False, 'message': f'库存物料创建包含不允许的字段: {", ".join(invalid)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '库存物料操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'库存物料更新包含不允许的字段: {", ".join(invalid)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            if not normalized['success']:
                return normalized
            after_snapshot = self._build_create_snapshot(normalized['payload'])
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, after_snapshot, 'create')]}

        item = self._get_item_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_item(item)

        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['status'] = 0
            return {
                'success': True,
                'change_set': [
                    self._build_change_set(
                        getattr(item, 'id', action.object_ids[0]),
                        before_snapshot,
                        after_snapshot,
                        'delete',
                        ['status'],
                    )
                ],
            }

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        return {
            'success': True,
            'change_set': [
                self._build_change_set(
                    getattr(item, 'id', action.object_ids[0]),
                    before_snapshot,
                    after_snapshot,
                    'update',
                    sorted(normalized['payload'].keys()),
                )
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.inventory.models import InventoryItem

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            payload = self._build_create_payload(normalized['payload'])
            item = InventoryItem.objects.create(**payload)
            return {
                'success': True,
                'message': 'created',
                'change_set': [self._build_change_set(item.id, None, self._snapshot_item(item), 'create')],
            }

        item = self._get_item_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            item.status = 0
            item.save()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        for field, value in normalized['payload'].items():
            setattr(item, field, value)
        item.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'inventory.add_inventoryitem',
            'update': 'inventory.change_inventoryitem',
            'delete': 'inventory.delete_inventoryitem',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作库存物料' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'category_id', 'shelf_life', 'status'}:
                    payload[field] = int(value) if value not in (None, '') else 0
                elif field in self.decimal_fields:
                    payload[field] = Decimal(str(value)) if value not in (None, '') else Decimal('0')
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '库存物料字段格式无效，请检查分类、价格和库存阈值'}
        return {'success': True, 'payload': payload}

    def _build_create_payload(self, payload):
        return {
            'name': payload.get('name', ''),
            'code': payload.get('code', ''),
            'category_id': payload.get('category_id'),
            'specification': payload.get('specification', ''),
            'unit': payload.get('unit', ''),
            'weight': payload.get('weight', Decimal('0')),
            'length': payload.get('length', Decimal('0')),
            'width': payload.get('width', Decimal('0')),
            'height': payload.get('height', Decimal('0')),
            'volume': payload.get('volume', Decimal('0')),
            'barcode': payload.get('barcode', ''),
            'qr_code': payload.get('qr_code', ''),
            'standard_cost': payload.get('standard_cost', Decimal('0')),
            'average_cost': payload.get('average_cost', Decimal('0')),
            'latest_cost': payload.get('latest_cost', Decimal('0')),
            'retail_price': payload.get('retail_price', Decimal('0')),
            'wholesale_price': payload.get('wholesale_price', Decimal('0')),
            'min_stock': payload.get('min_stock', Decimal('0')),
            'max_stock': payload.get('max_stock', Decimal('0')),
            'reorder_point': payload.get('reorder_point', Decimal('0')),
            'safety_stock': payload.get('safety_stock', Decimal('0')),
            'shelf_life': payload.get('shelf_life', 0) or 0,
            'status': payload.get('status', 1) if payload.get('status', None) not in (None, '') else 1,
            'image': payload.get('image', ''),
            'description': payload.get('description', ''),
        }

    def _build_create_snapshot(self, payload):
        return self._snapshot_dict(self._build_create_payload(payload))

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'inventory',
            'model_name': 'InventoryItem',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _snapshot_item(self, item):
        return self._snapshot_dict({
            'id': getattr(item, 'id', None),
            'name': getattr(item, 'name', ''),
            'code': getattr(item, 'code', ''),
            'category_id': getattr(item, 'category_id', None),
            'specification': getattr(item, 'specification', ''),
            'unit': getattr(item, 'unit', ''),
            'weight': getattr(item, 'weight', Decimal('0')),
            'length': getattr(item, 'length', Decimal('0')),
            'width': getattr(item, 'width', Decimal('0')),
            'height': getattr(item, 'height', Decimal('0')),
            'volume': getattr(item, 'volume', Decimal('0')),
            'barcode': getattr(item, 'barcode', ''),
            'qr_code': getattr(item, 'qr_code', ''),
            'standard_cost': getattr(item, 'standard_cost', Decimal('0')),
            'average_cost': getattr(item, 'average_cost', Decimal('0')),
            'latest_cost': getattr(item, 'latest_cost', Decimal('0')),
            'retail_price': getattr(item, 'retail_price', Decimal('0')),
            'wholesale_price': getattr(item, 'wholesale_price', Decimal('0')),
            'min_stock': getattr(item, 'min_stock', Decimal('0')),
            'max_stock': getattr(item, 'max_stock', Decimal('0')),
            'reorder_point': getattr(item, 'reorder_point', Decimal('0')),
            'safety_stock': getattr(item, 'safety_stock', Decimal('0')),
            'shelf_life': getattr(item, 'shelf_life', 0),
            'status': getattr(item, 'status', 1),
            'image': getattr(item, 'image', ''),
            'description': getattr(item, 'description', ''),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, Decimal):
                snapshot[field] = format(value, 'f')
            else:
                snapshot[field] = value
        return snapshot

    def _get_item_for_action(self, item_id, user):
        from apps.inventory.models import InventoryItem

        return InventoryItem.objects.get(id=item_id)
