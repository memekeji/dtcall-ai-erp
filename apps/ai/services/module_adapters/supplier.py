from __future__ import annotations

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class SupplierModuleAdapter(AIBaseModuleAdapter):
    resource = 'supplier'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'name', 'code', 'contact_person', 'contact_phone'}
    allowed_fields = {
        'name',
        'code',
        'contact_person',
        'contact_phone',
        'contact_email',
        'address',
        'tax_number',
        'bank_account',
        'bank_name',
        'credit_level',
        'business_scope',
        'is_active',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持供应商操作: {action.operation}'}

        if action.operation == 'create':
            missing_fields = [
                field for field in sorted(self.required_create_fields)
                if action.changes.get(field) in (None, '')
            ]
            if missing_fields:
                return {'success': False, 'message': f'供应商创建缺少必填字段: {", ".join(missing_fields)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '供应商操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        invalid_fields = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid_fields:
            return {'success': False, 'message': f'供应商更新包含不允许的字段: {", ".join(invalid_fields)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        if action.operation == 'create':
            after_snapshot = dict(action.changes or {})
            after_snapshot.setdefault('is_active', True)
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'contract',
                        'model_name': 'Supplier',
                        'object_pk': 'NEW',
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': after_snapshot,
                        'changed_fields': sorted(after_snapshot.keys()),
                    }
                ],
            }

        supplier = self._get_supplier_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_supplier(supplier)

        if action.operation == 'delete':
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'contract',
                        'model_name': 'Supplier',
                        'object_pk': str(getattr(supplier, 'id', action.object_ids[0])),
                        'change_type': 'delete',
                        'before_snapshot': before_snapshot,
                        'after_snapshot': {'deleted': True},
                        'changed_fields': ['id'],
                    }
                ],
            }

        after_snapshot = dict(before_snapshot)
        after_snapshot.update(action.changes or {})
        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'contract',
                    'model_name': 'Supplier',
                    'object_pk': str(getattr(supplier, 'id', action.object_ids[0])),
                    'change_type': 'update',
                    'before_snapshot': before_snapshot,
                    'after_snapshot': after_snapshot,
                    'changed_fields': sorted((action.changes or {}).keys()),
                }
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.contract.models import Supplier

        if action.operation == 'create':
            self._assert_supplier_code_unique(action.changes.get('code'))
            supplier = Supplier.objects.create(**(action.changes or {}))
            snapshot = self._snapshot_supplier(supplier)
            return {
                'success': True,
                'message': 'created',
                'change_set': [
                    {
                        'app_label': 'contract',
                        'model_name': 'Supplier',
                        'object_pk': str(supplier.id),
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': snapshot,
                        'changed_fields': sorted(snapshot.keys()),
                    }
                ],
            }

        supplier = self._get_supplier_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            supplier.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        if 'code' in (action.changes or {}) and action.changes['code'] != getattr(supplier, 'code', ''):
            self._assert_supplier_code_unique(action.changes['code'], exclude_id=getattr(supplier, 'id', None))
        for field, value in (action.changes or {}).items():
            setattr(supplier, field, value)
        supplier.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'contract.add_supplier',
            'update': 'contract.change_supplier',
            'delete': 'contract.delete_supplier',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作供应商' if not result.allowed else 'allowed'}

    def _snapshot_supplier(self, supplier):
        return {
            'id': getattr(supplier, 'id', None),
            'name': getattr(supplier, 'name', ''),
            'code': getattr(supplier, 'code', ''),
            'contact_person': getattr(supplier, 'contact_person', ''),
            'contact_phone': getattr(supplier, 'contact_phone', ''),
            'contact_email': getattr(supplier, 'contact_email', ''),
            'address': getattr(supplier, 'address', ''),
            'tax_number': getattr(supplier, 'tax_number', ''),
            'bank_account': getattr(supplier, 'bank_account', ''),
            'bank_name': getattr(supplier, 'bank_name', ''),
            'credit_level': getattr(supplier, 'credit_level', ''),
            'business_scope': getattr(supplier, 'business_scope', ''),
            'is_active': getattr(supplier, 'is_active', True),
        }

    def _get_supplier_for_action(self, supplier_id, user):
        from apps.contract.models import Supplier

        return Supplier.objects.get(id=supplier_id)

    def _assert_supplier_code_unique(self, code, exclude_id=None):
        from apps.contract.models import Supplier

        queryset = Supplier.objects.filter(code=code)
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        if queryset.exists():
            raise ValueError('供应商编码已存在')
