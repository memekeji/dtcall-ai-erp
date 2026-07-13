from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard, build_csv_membership_q


class CustomerModuleAdapter(AIBaseModuleAdapter):
    resource = 'customer'
    permission_guard = AIPermissionGuard()
    required_create_fields = {'name'}
    allowed_fields = {
        'name',
        'province',
        'city',
        'district',
        'town',
        'address',
        'content',
        'market',
        'remark',
        'tax_bank',
        'tax_banksn',
        'tax_num',
        'tax_mobile',
        'tax_address',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持客户操作: {action.operation}'}
        if action.operation == 'create':
            missing = [
                field for field in sorted(self.required_create_fields)
                if action.changes.get(field) in (None, '')
            ]
            if missing:
                return {'success': False, 'message': f'客户创建缺少必填字段: {", ".join(missing)}'}
        elif not action.object_ids:
            return {'success': False, 'message': '客户操作缺少目标记录'}
        if action.operation != 'delete':
            invalid_fields = sorted(set((action.changes or {}).keys()) - self.allowed_fields)
            if invalid_fields:
                return {
                    'success': False,
                    'message': f'客户操作包含不允许的字段: {", ".join(invalid_fields)}',
                }
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        if action.operation == 'create':
            after_snapshot = self._build_create_snapshot(action.changes or {}, user)
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'customer',
                        'model_name': 'Customer',
                        'object_pk': 'NEW',
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': after_snapshot,
                        'changed_fields': sorted(after_snapshot.keys()),
                    }
                ],
            }

        customer = self._get_customer_for_update(action.object_ids[0], user)
        before_snapshot = self._snapshot_customer(customer)
        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot.update({
                'belong_uid': 0,
                'belong_did': 0,
                'share_ids': '',
            })
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'customer',
                        'model_name': 'Customer',
                        'object_pk': str(getattr(customer, 'id', action.object_ids[0])),
                        'change_type': 'delete',
                        'before_snapshot': before_snapshot,
                        'after_snapshot': after_snapshot,
                        'changed_fields': ['belong_uid', 'belong_did', 'share_ids'],
                    }
                ],
            }

        after_snapshot = dict(before_snapshot)
        after_snapshot.update(action.changes or {})
        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'customer',
                    'model_name': 'Customer',
                    'object_pk': str(getattr(customer, 'id', action.object_ids[0])),
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

        from apps.customer.models import Customer

        if action.operation == 'create':
            customer = Customer.objects.create(**self._build_create_payload(action.changes or {}, user))
            return {
                'success': True,
                'message': 'created',
                'change_set': [
                    {
                        'app_label': 'customer',
                        'model_name': 'Customer',
                        'object_pk': str(customer.id),
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': self._snapshot_customer(customer),
                        'changed_fields': sorted(self._snapshot_customer(customer).keys()),
                    }
                ],
            }

        customer = self._get_customer_for_update(action.object_ids[0], user)
        if action.operation == 'delete':
            customer.belong_uid = 0
            customer.belong_did = 0
            customer.share_ids = ''
            customer.save(update_fields=['belong_uid', 'belong_did', 'share_ids', 'update_time'])
            return {
                'success': True,
                'message': 'deleted',
                'change_set': preview['change_set'],
            }

        for field, value in (action.changes or {}).items():
            setattr(customer, field, value)
        customer.save(update_fields=sorted(set((action.changes or {}).keys()) | {'update_time'}))
        return {
            'success': True,
            'message': 'updated',
            'change_set': preview['change_set'],
        }

    def _check_permission(self, action, user):
        if not hasattr(user, 'is_authenticated'):
            return {'allowed': True, 'message': 'allowed'}
        permission_map = {
            'create': 'customer.add_customer',
            'update': 'customer.change_customer',
            'delete': 'customer.delete_customer',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作客户' if not result.allowed else 'allowed'}

    def _build_create_payload(self, changes, user):
        timestamp = int(timezone.now().timestamp())
        payload = {
            'name': changes.get('name', ''),
            'province': changes.get('province', ''),
            'city': changes.get('city', ''),
            'district': changes.get('district', ''),
            'town': changes.get('town', ''),
            'address': changes.get('address', ''),
            'content': changes.get('content', ''),
            'market': changes.get('market', ''),
            'remark': changes.get('remark', ''),
            'tax_bank': changes.get('tax_bank', ''),
            'tax_banksn': changes.get('tax_banksn', ''),
            'tax_num': changes.get('tax_num', ''),
            'tax_mobile': changes.get('tax_mobile', ''),
            'tax_address': changes.get('tax_address', ''),
            'admin_id': getattr(user, 'id', 0) or 0,
            'belong_uid': getattr(user, 'id', 0) or 0,
            'belong_did': getattr(user, 'did', None) or getattr(user, 'department_id', None) or 0,
            'belong_time': timestamp,
            'distribute_time': timestamp,
            'follow_time': 0,
            'next_time': 0,
            'delete_time': 0,
            'intent_status': 1,
            'share_ids': '',
            'file_ids': '',
        }
        return payload

    def _build_create_snapshot(self, changes, user):
        return self._snapshot_customer(type('CustomerPreview', (), self._build_create_payload(changes, user))())

    def _snapshot_customer(self, customer):
        return {
            'id': getattr(customer, 'id', None),
            'name': getattr(customer, 'name', ''),
            'province': getattr(customer, 'province', ''),
            'city': getattr(customer, 'city', ''),
            'district': getattr(customer, 'district', ''),
            'town': getattr(customer, 'town', ''),
            'address': getattr(customer, 'address', ''),
            'content': getattr(customer, 'content', ''),
            'market': getattr(customer, 'market', ''),
            'remark': getattr(customer, 'remark', ''),
            'tax_bank': getattr(customer, 'tax_bank', ''),
            'tax_banksn': getattr(customer, 'tax_banksn', ''),
            'tax_num': getattr(customer, 'tax_num', ''),
            'tax_mobile': getattr(customer, 'tax_mobile', ''),
            'tax_address': getattr(customer, 'tax_address', ''),
            'admin_id': getattr(customer, 'admin_id', 0),
            'belong_uid': getattr(customer, 'belong_uid', 0),
            'belong_did': getattr(customer, 'belong_did', 0),
            'belong_time': getattr(customer, 'belong_time', 0),
            'distribute_time': getattr(customer, 'distribute_time', 0),
            'follow_time': getattr(customer, 'follow_time', 0),
            'next_time': getattr(customer, 'next_time', 0),
            'share_ids': getattr(customer, 'share_ids', ''),
            'file_ids': getattr(customer, 'file_ids', ''),
            'intent_status': getattr(customer, 'intent_status', 0),
            'delete_time': getattr(customer, 'delete_time', 0),
        }

    def _get_customer_for_update(self, customer_id, user):
        from apps.customer.models import Customer

        queryset = Customer.objects.filter(delete_time=0)
        if getattr(user, 'is_superuser', False):
            return queryset.get(id=customer_id)
        user_id = str(getattr(user, 'id', '') or '')
        return queryset.filter(
            Q(belong_uid=getattr(user, 'id', None)) |
            build_csv_membership_q('share_ids', user_id)
        ).distinct().get(id=customer_id)
