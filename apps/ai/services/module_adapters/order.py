from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class OrderModuleAdapter(AIBaseModuleAdapter):
    resource = 'order'
    permission_guard = AIPermissionGuard()

    required_create_fields = {
        'customer_id',
        'order_number',
        'product_name',
        'amount',
        'order_date',
    }
    allowed_update_fields = {
        'customer_id',
        'contract_id',
        'order_number',
        'product_name',
        'amount',
        'order_date',
        'status',
        'description',
        'remark',
        'finance_status',
        'invoice_request_status',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持订单操作: {action.operation}'}

        if action.operation == 'create':
            missing_fields = [
                field for field in sorted(self.required_create_fields)
                if action.changes.get(field) in (None, '')
            ]
            if missing_fields:
                return {
                    'success': False,
                    'message': f'订单创建缺少必填字段: {", ".join(missing_fields)}',
                }
            return {'success': True}

        if action.operation == 'delete':
            if not action.object_ids:
                return {'success': False, 'message': '订单删除缺少目标记录'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '订单更新缺少目标记录'}

        invalid_fields = sorted(set(action.changes.keys()) - self.allowed_update_fields)
        if invalid_fields:
            return {
                'success': False,
                'message': f'订单更新包含不允许的字段: {", ".join(invalid_fields)}',
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
            normalized_payload = self._normalize_create_payload(action.changes, user, resolve_relations=False)
            if not normalized_payload['success']:
                return normalized_payload
            after_snapshot = self._serialize_snapshot(normalized_payload['payload'])
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'customer',
                        'model_name': 'CustomerOrder',
                        'object_pk': 'NEW',
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': after_snapshot,
                        'changed_fields': sorted(after_snapshot.keys()),
                    }
                ],
            }

        order = self._get_order_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_order(order)

        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['delete_time'] = 'NOW'
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'customer',
                        'model_name': 'CustomerOrder',
                        'object_pk': str(getattr(order, 'id', action.object_ids[0])),
                        'change_type': 'delete',
                        'before_snapshot': before_snapshot,
                        'after_snapshot': after_snapshot,
                        'changed_fields': ['delete_time'],
                    }
                ],
            }

        normalized_changes = self._normalize_update_payload(action.changes)
        if not normalized_changes['success']:
            return normalized_changes
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._serialize_snapshot(normalized_changes['payload']))
        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'customer',
                    'model_name': 'CustomerOrder',
                    'object_pk': str(getattr(order, 'id', action.object_ids[0])),
                    'change_type': 'update',
                    'before_snapshot': before_snapshot,
                    'after_snapshot': after_snapshot,
                    'changed_fields': sorted(normalized_changes['payload'].keys()),
                }
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        if action.operation == 'create':
            normalized_payload = self._normalize_create_payload(action.changes, user, resolve_relations=True)
            payload = normalized_payload['payload']
            from apps.customer.models import CustomerOrder
            from apps.finance.models import OrderFinanceRecord

            with transaction.atomic():
                self._assert_order_number_unique(payload['order_number'])
                order = CustomerOrder.objects.create(**payload)
                finance_record = OrderFinanceRecord.objects.create(
                    order_id=order.id,
                    total_amount=order.amount,
                    payment_status='pending',
                    create_time=int(timezone.now().timestamp()),
                    remark='AI创建订单自动生成',
                )

            return {
                'success': True,
                'message': 'created',
                'change_set': [
                    {
                        'app_label': 'customer',
                        'model_name': 'CustomerOrder',
                        'object_pk': str(order.id),
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': self._snapshot_order(order),
                        'changed_fields': sorted(self._snapshot_order(order).keys()),
                    },
                    {
                        'app_label': 'finance',
                        'model_name': 'OrderFinanceRecord',
                        'object_pk': str(finance_record.id),
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': self._serialize_snapshot({
                            'id': finance_record.id,
                            'order_id': finance_record.order_id,
                            'total_amount': finance_record.total_amount,
                            'paid_amount': finance_record.paid_amount,
                            'payment_status': finance_record.payment_status,
                            'due_date': finance_record.due_date,
                            'create_time': finance_record.create_time,
                            'remark': finance_record.remark,
                        }),
                        'changed_fields': [
                            'order_id',
                            'total_amount',
                            'paid_amount',
                            'payment_status',
                            'due_date',
                            'create_time',
                            'remark',
                        ],
                    },
                ],
            }

        order = self._get_order_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            order.delete_time = int(timezone.now().timestamp())
            order.save(update_fields=['delete_time', 'update_time'])
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized_changes = self._normalize_update_payload(action.changes)
        if not normalized_changes['success']:
            return normalized_changes

        update_fields = []
        payload = normalized_changes['payload']
        if 'customer_id' in payload:
            customer = self._get_customer_for_create(payload.pop('customer_id'), user)
            order.customer = customer
            update_fields.append('customer')
        if 'contract_id' in payload:
            order.contract = self._get_contract_or_none(payload.pop('contract_id'))
            update_fields.append('contract')
        if 'order_number' in payload and payload['order_number'] != getattr(order, 'order_number', ''):
            self._assert_order_number_unique(payload['order_number'], exclude_id=getattr(order, 'id', None))

        for field, value in payload.items():
            setattr(order, field, value)
            update_fields.append(field)
        update_fields.append('update_time')
        order.save(update_fields=sorted(set(update_fields)))
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'customer.add_customer_order',
            'update': 'customer.change_customer_order',
            'delete': 'customer.delete_customer_order',
        }
        permission_code = permission_map.get(action.operation)
        if not permission_code:
            return {'allowed': False, 'message': '未配置订单操作权限'}
        result = self.permission_guard.check_action_permission(user, action, permission_code)
        return {'allowed': result.allowed, 'message': '权限不足，无法操作订单' if not result.allowed else 'allowed'}

    def _normalize_create_payload(self, changes, user, resolve_relations):
        normalized = self._normalize_update_payload(changes)
        if not normalized['success']:
            return normalized

        payload = dict(normalized['payload'])
        customer_id = payload.get('customer_id')
        contract_id = payload.get('contract_id')
        if resolve_relations:
            try:
                customer = self._get_customer_for_create(customer_id, user)
            except Exception:
                return {'success': False, 'message': '客户不存在或无权操作'}

            payload.pop('customer_id', None)
            payload.pop('contract_id', None)
            payload.update({
                'customer': customer,
                'contract': self._get_contract_or_none(contract_id),
                'create_user': user,
                'finance_status': payload.get('finance_status') or 'synced',
                'invoice_request_status': payload.get('invoice_request_status') or 'none',
                'status': payload.get('status') or 'pending',
            })
        else:
            payload.update({
                'contract_id': contract_id,
                'create_user_id': getattr(user, 'id', 0) or 0,
                'finance_status': payload.get('finance_status') or 'synced',
                'invoice_request_status': payload.get('invoice_request_status') or 'none',
                'status': payload.get('status') or 'pending',
                'delete_time': 0,
            })
        return {'success': True, 'payload': payload}

    def _normalize_update_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'customer_id', 'contract_id'}:
                    payload[field] = int(value) if value not in (None, '') else None
                elif field == 'amount':
                    payload[field] = self._parse_decimal(value)
                elif field == 'order_date':
                    payload[field] = self._parse_date(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '订单字段格式无效，请检查金额、日期和主键'}
        return {'success': True, 'payload': payload}

    def _snapshot_order(self, order):
        return self._serialize_snapshot({
            'id': getattr(order, 'id', None),
            'customer_id': getattr(order, 'customer_id', None),
            'contract_id': getattr(order, 'contract_id', None),
            'order_number': getattr(order, 'order_number', ''),
            'product_name': getattr(order, 'product_name', ''),
            'amount': getattr(order, 'amount', None),
            'order_date': getattr(order, 'order_date', None),
            'status': getattr(order, 'status', ''),
            'description': getattr(order, 'description', ''),
            'remark': getattr(order, 'remark', ''),
            'finance_status': getattr(order, 'finance_status', ''),
            'invoice_request_status': getattr(order, 'invoice_request_status', ''),
            'delete_time': getattr(order, 'delete_time', 0),
        })

    def _serialize_snapshot(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if hasattr(value, 'id') and field not in {'customer_id', 'contract_id', 'create_user_id'}:
                snapshot[f'{field}_id'] = getattr(value, 'id', None)
                continue
            if isinstance(value, Decimal):
                snapshot[field] = format(value, 'f')
            elif isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            elif isinstance(value, date):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _parse_decimal(self, value):
        return Decimal(str(value))

    def _parse_date(self, value):
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise ValueError('invalid date')

    def _get_customer_for_create(self, customer_id, user):
        customer_queryset = self._visible_customer_queryset(user)
        return customer_queryset.get(id=customer_id)

    def _get_contract_or_none(self, contract_id):
        if not contract_id:
            return None
        from apps.customer.models import CustomerContract

        return CustomerContract.objects.get(id=contract_id, delete_time=0)

    def _get_order_for_action(self, order_id, user):
        from apps.customer.models import CustomerOrder

        return self._scoped_order_queryset(user).get(id=order_id)

    def _scoped_order_queryset(self, user):
        from apps.customer.models import CustomerOrder

        queryset = CustomerOrder.objects.filter(delete_time=0)
        if getattr(user, 'is_superuser', False):
            return queryset
        customer_ids = self._visible_customer_queryset(user).values_list('id', flat=True)
        return queryset.filter(customer_id__in=customer_ids)

    def _visible_customer_queryset(self, user):
        from apps.customer.models import Customer

        queryset = Customer.objects.filter(delete_time=0)
        if getattr(user, 'is_superuser', False):
            return queryset
        visible_dids = self._visible_department_ids(user)
        if visible_dids:
            return queryset.filter(Q(belong_uid=getattr(user, 'id', 0)) | Q(belong_did__in=visible_dids)).distinct()
        return queryset.filter(belong_uid=getattr(user, 'id', 0))

    def _visible_department_ids(self, user):
        ids = []
        for attr in ('auth_dids', 'son_dids'):
            raw_value = getattr(user, attr, '') or ''
            ids.extend([int(item) for item in raw_value.split(',') if str(item).strip().isdigit()])
        auth_did = getattr(user, 'auth_did', 0) or 0
        if auth_did:
            ids.append(int(auth_did))
        return sorted(set(ids))

    def _assert_order_number_unique(self, order_number, exclude_id=None):
        from apps.customer.models import CustomerOrder

        queryset = CustomerOrder.objects.filter(order_number=order_number, delete_time=0)
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        if queryset.exists():
            raise ValueError('订单编号已存在')
