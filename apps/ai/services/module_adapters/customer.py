from __future__ import annotations

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter


class CustomerModuleAdapter(AIBaseModuleAdapter):
    resource = 'customer'
    allowed_update_fields = {
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
        invalid_fields = sorted(set(action.changes.keys()) - self.allowed_update_fields)
        if invalid_fields:
            return {
                'success': False,
                'message': f'客户更新包含不允许的字段: {", ".join(invalid_fields)}',
            }
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        customer = self._get_customer_for_update(action.object_ids[0], user)
        before_snapshot = {field: getattr(customer, field, None) for field in action.changes.keys()}
        after_snapshot = {**before_snapshot, **action.changes}
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
                    'changed_fields': sorted(action.changes.keys()),
                }
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview
        return {
            'success': True,
            'message': 'updated',
            'change_set': preview['change_set'],
        }

    def _get_customer_for_update(self, customer_id, user):
        from apps.customer.models import Customer

        return Customer.objects.get(id=customer_id)
