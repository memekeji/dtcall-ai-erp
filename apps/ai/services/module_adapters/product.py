from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class ProductModuleAdapter(AIBaseModuleAdapter):
    resource = 'product'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'name', 'code', 'price'}
    allowed_fields = {'name', 'code', 'cate_id', 'specs', 'unit', 'price', 'remark'}

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持产品操作: {action.operation}'}

        if action.operation == 'create':
            missing_fields = [
                field for field in sorted(self.required_create_fields)
                if action.changes.get(field) in (None, '')
            ]
            if missing_fields:
                return {'success': False, 'message': f'产品创建缺少必填字段: {", ".join(missing_fields)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '产品操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        invalid_fields = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid_fields:
            return {'success': False, 'message': f'产品更新包含不允许的字段: {", ".join(invalid_fields)}'}
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
            after_snapshot = dict(normalized['payload'])
            after_snapshot['admin_id'] = getattr(user, 'id', 0) or 0
            after_snapshot['delete_time'] = None
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'contract',
                        'model_name': 'Product',
                        'object_pk': 'NEW',
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': self._snapshot_dict(after_snapshot),
                        'changed_fields': sorted(after_snapshot.keys()),
                    }
                ],
            }

        product = self._get_product_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_product(product)

        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['delete_time'] = 'NOW'
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'contract',
                        'model_name': 'Product',
                        'object_pk': str(getattr(product, 'id', action.object_ids[0])),
                        'change_type': 'delete',
                        'before_snapshot': before_snapshot,
                        'after_snapshot': after_snapshot,
                        'changed_fields': ['delete_time'],
                    }
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
                {
                    'app_label': 'contract',
                    'model_name': 'Product',
                    'object_pk': str(getattr(product, 'id', action.object_ids[0])),
                    'change_type': 'update',
                    'before_snapshot': before_snapshot,
                    'after_snapshot': after_snapshot,
                    'changed_fields': sorted(normalized['payload'].keys()),
                }
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.contract.models import Product

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            payload = normalized['payload']
            self._assert_product_code_unique(payload['code'])
            product = Product.objects.create(
                **payload,
                admin=user,
            )
            snapshot = self._snapshot_product(product)
            return {
                'success': True,
                'message': 'created',
                'change_set': [
                    {
                        'app_label': 'contract',
                        'model_name': 'Product',
                        'object_pk': str(product.id),
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': snapshot,
                        'changed_fields': sorted(snapshot.keys()),
                    }
                ],
            }

        product = self._get_product_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            product.delete_time = timezone.now()
            product.save(update_fields=['delete_time', 'update_time'])
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        payload = normalized['payload']
        if 'code' in payload and payload['code'] != getattr(product, 'code', ''):
            self._assert_product_code_unique(payload['code'], exclude_id=getattr(product, 'id', None))
        if 'cate_id' in payload:
            product.cate_id = payload.pop('cate_id')
        for field, value in payload.items():
            setattr(product, field, value)
        product.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'contract.add_product',
            'update': 'contract.change_product',
            'delete': 'contract.delete_product',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作产品' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field == 'price':
                    payload[field] = Decimal(str(value))
                elif field == 'cate_id':
                    payload[field] = int(value) if value not in (None, '') else None
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '产品字段格式无效，请检查价格和分类'}
        return {'success': True, 'payload': payload}

    def _snapshot_product(self, product):
        return self._snapshot_dict({
            'id': getattr(product, 'id', None),
            'name': getattr(product, 'name', ''),
            'code': getattr(product, 'code', ''),
            'cate_id': getattr(product, 'cate_id', None),
            'specs': getattr(product, 'specs', ''),
            'unit': getattr(product, 'unit', ''),
            'price': getattr(product, 'price', Decimal('0')),
            'remark': getattr(product, 'remark', ''),
            'admin_id': getattr(product, 'admin_id', None),
            'delete_time': getattr(product, 'delete_time', None),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, Decimal):
                snapshot[field] = format(value, 'f')
            else:
                snapshot[field] = value
        return snapshot

    def _get_product_for_action(self, product_id, user):
        from apps.contract.models import Product

        queryset = Product.objects.filter(delete_time__isnull=True)
        if getattr(user, 'is_superuser', False):
            return queryset.get(id=product_id)
        return queryset.get(id=product_id, admin=user)

    def _assert_product_code_unique(self, code, exclude_id=None):
        from apps.contract.models import Product

        queryset = Product.objects.filter(code=code, delete_time__isnull=True)
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        if queryset.exists():
            raise ValueError('产品编码已存在')
