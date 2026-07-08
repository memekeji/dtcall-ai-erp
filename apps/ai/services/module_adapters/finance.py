from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.ai.services.permission_guard import AIPermissionGuard
from apps.ai.services.module_adapters.base import AIBaseModuleAdapter


class FinanceModuleAdapter(AIBaseModuleAdapter):
    resource = 'finance'
    permission_guard = AIPermissionGuard()
    required_invoice_fields = {'code', 'amount', 'invoice_title'}
    required_payment_fields = {'amount', 'payment_date'}
    required_income_fields = {'amount', 'income_date'}

    def validate(self, action):
        model = self._resolve_model_name(action)
        if not model:
            return {'success': False, 'message': '财务操作缺少目标模型标识'}

        if action.operation == 'approve':
            if model not in {'expense', 'invoice_request'}:
                return {'success': False, 'message': f'暂不支持财务审批模型: {model}'}
            return {'success': True}

        if model == 'invoice':
            return self._validate_model_fields(action, self.allowed_invoice_fields(), self.required_invoice_fields, '发票')
        if model == 'payment':
            return self._validate_model_fields(action, self.allowed_payment_fields(), self.required_payment_fields, '付款记录')
        if model == 'income':
            return self._validate_model_fields(action, self.allowed_income_fields(), self.required_income_fields, '回款记录')
        if model == 'expense':
            invalid_fields = sorted(set(action.changes.keys()) - self.allowed_expense_fields())
            if invalid_fields:
                return {'success': False, 'message': f'报销更新包含不允许的字段: {", ".join(invalid_fields)}'}
            return {'success': True}

        return {'success': False, 'message': f'暂不支持财务模型: {model}'}

    def _validate_model_fields(self, action, allowed_fields, required_fields, label):
        if action.operation == 'create':
            missing_fields = [
                field for field in sorted(required_fields)
                if action.changes.get(field) in (None, '')
            ]
            if missing_fields:
                return {'success': False, 'message': f'{label}创建缺少必填字段: {", ".join(missing_fields)}'}
        elif not action.object_ids:
            return {'success': False, 'message': f'{label}操作缺少目标记录'}

        invalid_fields = sorted(set(action.changes.keys()) - allowed_fields)
        if invalid_fields:
            return {'success': False, 'message': f'{label}更新包含不允许的字段: {", ".join(invalid_fields)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        model = self._resolve_model_name(action)
        if action.operation == 'approve' and model == 'invoice_request':
            request = self._get_invoice_request_for_action(action.object_ids[0], user)
            before_snapshot = self._snapshot_instance(request, fields=['status', 'reviewer_id', 'review_time', 'review_comment', 'invoice_id', 'invoice_time'])
            after_snapshot = dict(before_snapshot)
            after_snapshot.update({
                'status': action.changes.get('status', 'approved'),
                'reviewer_id': getattr(user, 'id', 0) or 0,
                'review_time': 'NOW',
            })
            return self._single_change_set('InvoiceRequest', getattr(request, 'id', action.object_ids[0]), 'update', before_snapshot, after_snapshot, ['status', 'reviewer_id', 'review_time'])

        if action.operation == 'approve' and model == 'expense':
            expense = self._get_expense_for_action(action.object_ids[0], user)
            before_snapshot = self._snapshot_instance(expense, fields=['check_status', 'check_history_uids', 'check_time'])
            after_snapshot = dict(before_snapshot)
            after_snapshot.update({
                'check_status': action.changes.get('check_status', 2),
                'check_time': 'NOW',
            })
            return self._single_change_set('Expense', getattr(expense, 'id', action.object_ids[0]), 'update', before_snapshot, after_snapshot, ['check_status', 'check_time', 'check_history_uids'])

        if model == 'invoice':
            return self._preview_standard_model(
                action, user, 'Invoice', self._get_invoice_for_action, self._normalize_invoice_changes, rollback_model='invoice'
            )
        if model == 'payment':
            return self._preview_standard_model(
                action, user, 'Payment', self._get_payment_for_action, self._normalize_payment_changes, rollback_model='payment'
            )
        if model == 'income':
            return self._preview_standard_model(
                action, user, 'Income', self._get_income_for_action, self._normalize_income_changes, rollback_model='income'
            )

        expense = self._get_expense_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_instance(expense)
        if action.operation == 'delete':
            after_snapshot = {'deleted': True}
            change_type = 'delete'
            changed_fields = ['id']
        else:
            after_snapshot = dict(before_snapshot)
            after_snapshot.update(action.changes)
            change_type = 'update'
            changed_fields = sorted(action.changes.keys())

        return self._single_change_set('Expense', getattr(expense, 'id', action.object_ids[0]), change_type, before_snapshot, after_snapshot, changed_fields, rollback_model='expense')

    def _preview_standard_model(self, action, user, model_name, getter, normalizer, rollback_model):
        if action.operation == 'create':
            normalized = normalizer(action.changes, user)
            if not normalized['success']:
                return normalized
            return self._single_change_set(model_name, 'NEW', 'create', None, normalized['payload'], sorted(normalized['payload'].keys()), rollback_model=rollback_model)

        instance = getter(action.object_ids[0], user)
        before_snapshot = self._snapshot_instance(instance)
        if action.operation == 'delete':
            return self._single_change_set(model_name, getattr(instance, 'id', action.object_ids[0]), 'delete', before_snapshot, None, sorted(before_snapshot.keys()), rollback_model=rollback_model)

        normalized = normalizer(action.changes, user, partial=True)
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(normalized['payload'])
        return self._single_change_set(model_name, getattr(instance, 'id', action.object_ids[0]), 'update', before_snapshot, after_snapshot, sorted(normalized['payload'].keys()), rollback_model=rollback_model)

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        model = self._resolve_model_name(action)
        if action.operation == 'approve' and model == 'invoice_request':
            request = self._get_invoice_request_for_action(action.object_ids[0], user)
            request.status = action.changes.get('status', 'approved')
            request.reviewer_id = getattr(user, 'id', 0) or 0
            request.review_time = int(timezone.now().timestamp())
            request.save(update_fields=['status', 'reviewer_id', 'review_time'])
            return {'success': True, 'message': 'approved', 'change_set': preview['change_set']}

        if action.operation == 'approve' and model == 'expense':
            expense = self._get_expense_for_action(action.object_ids[0], user)
            expense.check_status = action.changes.get('check_status', 2)
            expense.check_time = int(timezone.now().timestamp())
            if hasattr(expense, 'check_history_uids'):
                history = getattr(expense, 'check_history_uids', '') or ''
                uid = str(getattr(user, 'id', 0) or 0)
                expense.check_history_uids = f'{history},{uid}' if history else uid
            expense.save()
            return {'success': True, 'message': 'approved', 'change_set': preview['change_set']}

        if model == 'invoice':
            return self._execute_standard_model(action, user, preview, 'Invoice', self._get_invoice_for_action, self._normalize_invoice_changes)
        if model == 'payment':
            return self._execute_standard_model(action, user, preview, 'Payment', self._get_payment_for_action, self._normalize_payment_changes)
        if model == 'income':
            return self._execute_standard_model(action, user, preview, 'Income', self._get_income_for_action, self._normalize_income_changes)

        expense = self._get_expense_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            if hasattr(expense, 'delete'):
                expense.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        for field, value in action.changes.items():
            setattr(expense, field, value)
        expense.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _execute_standard_model(self, action, user, preview, model_name, getter, normalizer):
        from apps.finance import models as finance_models

        model_cls = getattr(finance_models, model_name)
        if action.operation == 'create':
            normalized = normalizer(action.changes, user)
            if not normalized['success']:
                return normalized
            instance = model_cls.objects.create(**normalized['payload'])
            snapshot = self._snapshot_instance(instance)
            return {'success': True, 'message': 'created', 'change_set': [{
                'app_label': 'finance',
                'model_name': model_name,
                'object_pk': str(instance.id),
                'change_type': 'create',
                'before_snapshot': None,
                'after_snapshot': snapshot,
                'changed_fields': sorted(snapshot.keys()),
                'rollback_metadata': {'model': model_name.lower()},
            }]}

        instance = getter(action.object_ids[0], user)
        if action.operation == 'delete':
            instance.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = normalizer(action.changes, user, partial=True)
        if not normalized['success']:
            return normalized
        for field, value in normalized['payload'].items():
            setattr(instance, field, value)
        instance.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def allowed_expense_fields(self):
        return {
            'code', 'subject_id', 'admin_id', 'did', 'project_id', 'cost', 'income_month',
            'expense_time', 'file_ids', 'pay_status', 'pay_admin_id', 'pay_time', 'check_status',
            'check_flow_id', 'check_step_sort', 'check_uids', 'check_last_uid',
            'check_history_uids', 'check_copy_uids', 'check_time', 'create_time', 'remark',
            'auto_generated',
        }

    def allowed_invoice_fields(self):
        return {
            'code', 'customer_id', 'contract_id', 'project_id', 'amount', 'did', 'admin_id',
            'open_status', 'open_admin_id', 'open_time', 'delivery', 'types', 'invoice_type',
            'invoice_subject', 'invoice_title', 'invoice_tax', 'invoice_phone', 'invoice_address',
            'invoice_bank', 'invoice_account', 'invoice_banking', 'file_ids', 'other_file_ids',
            'enter_amount', 'enter_status', 'enter_time', 'check_status', 'check_flow_id',
            'check_step_sort', 'check_uids', 'check_last_uid', 'check_history_uids',
            'check_copy_uids', 'check_time', 'remark',
        }

    def allowed_payment_fields(self):
        return {
            'expense_id', 'customer_id', 'order_id', 'purchase_order_id', 'purchase_contract_id',
            'project_id', 'amount', 'payment_date', 'file_ids', 'remark',
        }

    def allowed_income_fields(self):
        return {'invoice_id', 'amount', 'income_date', 'file_ids', 'remark'}

    def _resolve_model_name(self, action):
        context = action.context or {}
        model = context.get('model') or context.get('model_name')
        if model:
            return str(model).lower()
        if action.operation == 'approve':
            return 'invoice_request'
        return 'expense'

    def _check_permission(self, action, user):
        model = self._resolve_model_name(action)
        permission_map = {
            ('expense', 'update'): 'finance.change_reimbursement',
            ('expense', 'delete'): 'finance.delete_reimbursement',
            ('expense', 'approve'): 'finance.approve_reimbursement',
            ('invoice_request', 'approve'): 'finance.approve_invoice',
            ('invoice', 'create'): 'finance.add_invoice',
            ('invoice', 'update'): 'finance.change_invoice',
            ('invoice', 'delete'): 'finance.delete_invoice',
            ('payment', 'create'): 'finance.add_payment',
            ('payment', 'update'): 'finance.change_payment',
            ('payment', 'delete'): 'finance.delete_payment',
            ('income', 'create'): 'finance.add_payment_receive',
            ('income', 'update'): 'finance.change_payment_receive',
            ('income', 'delete'): 'finance.delete_payment_receive',
        }
        permission_code = permission_map.get((model, action.operation))
        if not permission_code:
            return {'allowed': False, 'message': '未配置财务操作权限'}
        result = self.permission_guard.check_action_permission(user, action, permission_code)
        return {'allowed': result.allowed, 'message': '权限不足' if not result.allowed else 'allowed'}

    def _normalize_invoice_changes(self, changes, user, partial=False):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {
                    'customer_id', 'contract_id', 'project_id', 'did', 'admin_id', 'open_status',
                    'open_admin_id', 'open_time', 'types', 'invoice_type', 'invoice_subject',
                    'enter_status', 'enter_time', 'check_status', 'check_flow_id',
                    'check_step_sort', 'check_time',
                }:
                    payload[field] = int(value) if value not in (None, '') else 0
                elif field in {'amount', 'enter_amount'}:
                    payload[field] = Decimal(str(value))
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '发票字段格式无效，请检查金额和编号'}

        if not partial:
            payload.setdefault('customer_id', 0)
            payload.setdefault('contract_id', 0)
            payload.setdefault('project_id', 0)
            payload.setdefault('did', 0)
            payload.setdefault('admin_id', getattr(user, 'id', 0) or 0)
            payload.setdefault('open_status', 0)
            payload.setdefault('open_admin_id', 0)
            payload.setdefault('open_time', 0)
            payload.setdefault('delivery', '')
            payload.setdefault('types', 0)
            payload.setdefault('invoice_type', 0)
            payload.setdefault('invoice_subject', 0)
            payload.setdefault('invoice_tax', '')
            payload.setdefault('invoice_phone', '')
            payload.setdefault('invoice_address', '')
            payload.setdefault('invoice_bank', '')
            payload.setdefault('invoice_account', '')
            payload.setdefault('invoice_banking', '')
            payload.setdefault('file_ids', '')
            payload.setdefault('other_file_ids', '')
            payload.setdefault('enter_amount', Decimal('0'))
            payload.setdefault('enter_status', 0)
            payload.setdefault('enter_time', 0)
            payload.setdefault('check_status', 0)
            payload.setdefault('check_flow_id', 0)
            payload.setdefault('check_step_sort', 0)
            payload.setdefault('check_uids', '')
            payload.setdefault('check_last_uid', '')
            payload.setdefault('check_history_uids', '')
            payload.setdefault('check_copy_uids', '')
            payload.setdefault('check_time', 0)
            payload.setdefault('remark', '')
            payload.setdefault('create_time', int(timezone.now().timestamp()))
        return {'success': True, 'payload': self._serialize_payload(payload)}

    def _normalize_payment_changes(self, changes, user, partial=False):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'expense_id', 'customer_id', 'order_id', 'purchase_order_id', 'purchase_contract_id', 'project_id'}:
                    payload[field] = int(value) if value not in (None, '') else 0
                elif field == 'amount':
                    payload[field] = Decimal(str(value))
                elif field == 'payment_date':
                    payload[field] = self._parse_datetime(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '付款记录字段格式无效，请检查金额和打款日期'}

        if not partial:
            payload.setdefault('expense_id', 0)
            payload.setdefault('customer_id', 0)
            payload.setdefault('order_id', 0)
            payload.setdefault('purchase_order_id', 0)
            payload.setdefault('purchase_contract_id', 0)
            payload.setdefault('project_id', 0)
            payload.setdefault('file_ids', '')
            payload.setdefault('remark', '')
            payload.setdefault('create_time', int(timezone.now().timestamp()))
        return {'success': True, 'payload': self._serialize_payload(payload)}

    def _normalize_income_changes(self, changes, user, partial=False):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field == 'invoice_id':
                    payload[field] = int(value) if value not in (None, '') else 0
                elif field == 'amount':
                    payload[field] = Decimal(str(value))
                elif field == 'income_date':
                    payload[field] = self._parse_datetime(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '回款记录字段格式无效，请检查金额和到账日期'}

        if not partial:
            payload.setdefault('invoice_id', 0)
            payload.setdefault('file_ids', '')
            payload.setdefault('remark', '')
            payload.setdefault('create_time', int(timezone.now().timestamp()))
        return {'success': True, 'payload': self._serialize_payload(payload)}

    def _parse_datetime(self, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError('invalid datetime')

    def _serialize_payload(self, payload):
        serialized = {}
        for key, value in (payload or {}).items():
            if isinstance(value, Decimal):
                serialized[key] = format(value, 'f')
            elif isinstance(value, datetime):
                serialized[key] = value.isoformat()
            else:
                serialized[key] = value
        return serialized

    def _single_change_set(self, model_name, object_pk, change_type, before_snapshot, after_snapshot, changed_fields, rollback_model=None):
        item = {
            'app_label': 'finance',
            'model_name': model_name,
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields,
        }
        if rollback_model:
            item['rollback_metadata'] = {'model': rollback_model}
        return {'success': True, 'change_set': [item]}

    def _snapshot_instance(self, instance, fields=None):
        if fields is None:
            meta = getattr(instance, '_meta', None)
            concrete_fields = getattr(meta, 'concrete_fields', None) if meta else None
            if concrete_fields:
                fields = [field.attname for field in concrete_fields if getattr(field, 'attname', None)]
            else:
                fields = [key for key in vars(instance).keys() if not key.startswith('_') and not callable(getattr(instance, key))]
        snapshot = {}
        for field in fields:
            value = getattr(instance, field, None)
            if isinstance(value, Decimal):
                snapshot[field] = format(value, 'f')
            elif isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _get_expense_for_action(self, expense_id, user):
        from apps.finance.models import Expense
        return Expense.objects.get(id=expense_id)

    def _get_invoice_for_action(self, invoice_id, user):
        from apps.finance.models import Invoice
        return Invoice.objects.get(id=invoice_id)

    def _get_payment_for_action(self, payment_id, user):
        from apps.finance.models import Payment
        return Payment.objects.get(id=payment_id)

    def _get_income_for_action(self, income_id, user):
        from apps.finance.models import Income
        return Income.objects.get(id=income_id)

    def _get_invoice_request_for_action(self, request_id, user):
        from apps.finance.models import InvoiceRequest
        return InvoiceRequest.objects.get(id=request_id)
