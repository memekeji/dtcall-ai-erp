from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class StockDocumentModuleAdapter(AIBaseModuleAdapter):
    permission_guard = AIPermissionGuard()

    required_fields = {
        'stockin': {'code', 'stock_in_type', 'warehouse_id', 'total_quantity'},
        'stockout': {'code', 'stock_out_type', 'warehouse_id', 'total_quantity'},
    }
    allowed_fields = {
        'stockin': {
            'code', 'stock_in_type', 'warehouse_id', 'supplier_id', 'purchase_order_id',
            'production_plan_id', 'total_amount', 'total_quantity', 'status', 'remark',
        },
        'stockout': {
            'code', 'stock_out_type', 'warehouse_id', 'customer_id', 'sales_order_id',
            'production_task_id', 'total_amount', 'total_quantity', 'status', 'remark',
        },
    }

    def __init__(self, resource='stockin'):
        self.resource = resource

    def validate(self, action):
        resource = self._resolve_resource(action)
        if action.operation not in {'create', 'update', 'delete', 'approve', 'stock'}:
            return {'success': False, 'message': f'暂不支持库存单据操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_fields[resource]) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'库存单据创建缺少必填字段: {", ".join(missing)}'}
            invalid = sorted(set(action.changes.keys()) - self.allowed_fields[resource])
            if invalid:
                return {'success': False, 'message': f'库存单据创建包含不允许的字段: {", ".join(invalid)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '库存单据操作缺少目标记录'}

        if action.operation in {'delete', 'approve', 'stock'}:
            return {'success': True}

        invalid = sorted(set(action.changes.keys()) - self.allowed_fields[resource])
        if invalid:
            return {'success': False, 'message': f'库存单据更新包含不允许的字段: {", ".join(invalid)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        resource = self._resolve_resource(action)
        model_name = 'StockIn' if resource == 'stockin' else 'StockOut'

        if action.operation == 'create':
            normalized = self._normalize_payload(resource, action.changes or {})
            if not normalized['success']:
                return normalized
            after_snapshot = self._build_create_snapshot(resource, normalized['payload'])
            return {'success': True, 'change_set': [self._build_change_set(resource, model_name, 'NEW', None, after_snapshot, 'create')]}

        document = self._get_resource_document(resource, action.object_ids[0], user)
        before_snapshot = self._snapshot_document(resource, document)

        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['status'] = 4
            return {'success': True, 'change_set': [self._build_change_set(resource, model_name, getattr(document, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'delete', ['status'])]}

        if action.operation == 'approve':
            after_snapshot = dict(before_snapshot)
            after_snapshot.update({'status': 2, 'checker_id': getattr(user, 'id', None), 'check_time': 'NOW'})
            return {'success': True, 'change_set': [self._build_change_set(resource, model_name, getattr(document, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', ['status', 'checker_id', 'check_time'])]}

        if action.operation == 'stock':
            after_snapshot = dict(before_snapshot)
            stock_field = 'stock_time'
            stocker_field = 'stocker_id'
            after_snapshot.update({'status': 3, stocker_field: getattr(user, 'id', None), stock_field: 'NOW'})
            return {'success': True, 'change_set': [self._build_change_set(resource, model_name, getattr(document, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', ['status', stocker_field, stock_field])]}

        normalized = self._normalize_payload(resource, action.changes or {})
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        return {'success': True, 'change_set': [self._build_change_set(resource, model_name, getattr(document, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        resource = self._resolve_resource(action)
        model_class = self._get_model_class(resource)

        if action.operation == 'create':
            normalized = self._normalize_payload(resource, action.changes or {})
            payload = self._build_create_payload(resource, normalized['payload'])
            document = model_class.objects.create(**payload)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(resource, model_class.__name__, document.id, None, self._snapshot_document(resource, document), 'create')]}

        document = self._get_resource_document(resource, action.object_ids[0], user)

        if action.operation == 'delete':
            document.status = 4
            document.save()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        if action.operation == 'approve':
            document.status = 2
            document.checker_id = getattr(user, 'id', None)
            document.check_time = timezone.now()
            document.save()
            return {'success': True, 'message': 'approved', 'change_set': preview['change_set']}

        if action.operation == 'stock':
            document.status = 3
            document.stocker_id = getattr(user, 'id', None)
            document.stock_time = timezone.now()
            document.save()
            return {'success': True, 'message': 'stocked', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(resource, action.changes or {})
        if not normalized['success']:
            return normalized
        for field, value in normalized['payload'].items():
            setattr(document, field, value)
        document.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        resource = self._resolve_resource(action)
        permission_map = {
            ('stockin', 'create'): 'inventory.add_stockin',
            ('stockin', 'update'): 'inventory.change_stockin',
            ('stockin', 'delete'): 'inventory.delete_stockin',
            ('stockin', 'approve'): 'inventory.change_stockin',
            ('stockin', 'stock'): 'inventory.change_stockin',
            ('stockout', 'create'): 'inventory.add_stockout',
            ('stockout', 'update'): 'inventory.change_stockout',
            ('stockout', 'delete'): 'inventory.delete_stockout',
            ('stockout', 'approve'): 'inventory.change_stockout',
            ('stockout', 'stock'): 'inventory.change_stockout',
        }
        permission_code = permission_map[(resource, action.operation)]
        result = self.permission_guard.check_action_permission(user, action, permission_code)
        return {'allowed': result.allowed, 'message': '权限不足，无法操作库存单据' if not result.allowed else 'allowed'}

    def _normalize_payload(self, resource, changes):
        payload = {}
        integer_fields = {
            'stockin': {'warehouse_id', 'supplier_id', 'purchase_order_id', 'production_plan_id', 'status'},
            'stockout': {'warehouse_id', 'customer_id', 'sales_order_id', 'production_task_id', 'status'},
        }
        decimal_fields = {'total_amount', 'total_quantity'}
        try:
            for field, value in (changes or {}).items():
                if field in integer_fields[resource]:
                    payload[field] = int(value) if value not in (None, '') else None
                elif field in decimal_fields:
                    payload[field] = Decimal(str(value)) if value not in (None, '') else Decimal('0')
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '库存单据字段格式无效，请检查仓库、关联单据和数量金额'}
        return {'success': True, 'payload': payload}

    def _build_create_payload(self, resource, payload):
        if resource == 'stockin':
            return {
                'code': payload.get('code', ''),
                'stock_in_type': payload.get('stock_in_type', 'other'),
                'warehouse_id': payload.get('warehouse_id'),
                'supplier_id': payload.get('supplier_id'),
                'purchase_order_id': payload.get('purchase_order_id'),
                'production_plan_id': payload.get('production_plan_id'),
                'total_amount': payload.get('total_amount', Decimal('0')),
                'total_quantity': payload.get('total_quantity', Decimal('0')),
                'status': payload.get('status', 1) if payload.get('status', None) is not None else 1,
                'remark': payload.get('remark', ''),
            }
        return {
            'code': payload.get('code', ''),
            'stock_out_type': payload.get('stock_out_type', 'other'),
            'warehouse_id': payload.get('warehouse_id'),
            'customer_id': payload.get('customer_id'),
            'sales_order_id': payload.get('sales_order_id'),
            'production_task_id': payload.get('production_task_id'),
            'total_amount': payload.get('total_amount', Decimal('0')),
            'total_quantity': payload.get('total_quantity', Decimal('0')),
            'status': payload.get('status', 1) if payload.get('status', None) is not None else 1,
            'remark': payload.get('remark', ''),
        }

    def _build_create_snapshot(self, resource, payload):
        return self._snapshot_dict(self._build_create_payload(resource, payload))

    def _build_change_set(self, resource, model_name, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'inventory',
            'model_name': model_name,
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _snapshot_document(self, resource, document):
        if resource == 'stockin':
            return self._snapshot_dict({
                'id': getattr(document, 'id', None),
                'code': getattr(document, 'code', ''),
                'stock_in_type': getattr(document, 'stock_in_type', 'other'),
                'warehouse_id': getattr(document, 'warehouse_id', None),
                'supplier_id': getattr(document, 'supplier_id', None),
                'purchase_order_id': getattr(document, 'purchase_order_id', None),
                'production_plan_id': getattr(document, 'production_plan_id', None),
                'total_amount': getattr(document, 'total_amount', Decimal('0')),
                'total_quantity': getattr(document, 'total_quantity', Decimal('0')),
                'status': getattr(document, 'status', 1),
                'checker_id': getattr(document, 'checker_id', None),
                'check_time': getattr(document, 'check_time', None),
                'stocker_id': getattr(document, 'stocker_id', None),
                'stock_time': getattr(document, 'stock_time', None),
                'remark': getattr(document, 'remark', ''),
            })
        return self._snapshot_dict({
            'id': getattr(document, 'id', None),
            'code': getattr(document, 'code', ''),
            'stock_out_type': getattr(document, 'stock_out_type', 'other'),
            'warehouse_id': getattr(document, 'warehouse_id', None),
            'customer_id': getattr(document, 'customer_id', None),
            'sales_order_id': getattr(document, 'sales_order_id', None),
            'production_task_id': getattr(document, 'production_task_id', None),
            'total_amount': getattr(document, 'total_amount', Decimal('0')),
            'total_quantity': getattr(document, 'total_quantity', Decimal('0')),
            'status': getattr(document, 'status', 1),
            'checker_id': getattr(document, 'checker_id', None),
            'check_time': getattr(document, 'check_time', None),
            'stocker_id': getattr(document, 'stocker_id', None),
            'stock_time': getattr(document, 'stock_time', None),
            'remark': getattr(document, 'remark', ''),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, Decimal):
                snapshot[field] = format(value, 'f')
            else:
                snapshot[field] = value
        return snapshot

    def _resolve_resource(self, action):
        return action.resource if action.resource in {'stockin', 'stockout'} else self.resource

    def _get_model_class(self, resource):
        from apps.inventory.models import StockIn, StockOut

        return StockIn if resource == 'stockin' else StockOut

    def _get_document_for_action(self, resource, document_id, user):
        model_class = self._get_model_class(resource)
        return model_class.objects.get(id=document_id)

    def _get_stockin_for_action(self, document_id, user):
        return self._get_document_for_action('stockin', document_id, user)

    def _get_stockout_for_action(self, document_id, user):
        return self._get_document_for_action('stockout', document_id, user)

    def _get_resource_document(self, resource, document_id, user):
        if resource == 'stockin':
            return self._get_stockin_for_action(document_id, user)
        return self._get_stockout_for_action(document_id, user)
