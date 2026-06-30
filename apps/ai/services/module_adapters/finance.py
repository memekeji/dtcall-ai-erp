from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from apps.ai.services.permission_guard import AIPermissionGuard
from apps.ai.services.module_adapters.base import AIBaseModuleAdapter


class FinanceModuleAdapter(AIBaseModuleAdapter):
    resource = 'finance'
    permission_guard = AIPermissionGuard()

    def validate(self, action):
        model = self._resolve_model_name(action)
        if not model:
            return {
                'success': False,
                'message': '财务操作缺少目标模型标识',
            }

        if action.operation == 'approve':
            if model not in {'expense', 'invoice_request'}:
                return {
                    'success': False,
                    'message': f'暂不支持财务审批模型: {model}',
                }
            return {'success': True}

        if model not in {'expense'}:
            return {
                'success': False,
                'message': f'暂不支持财务模型: {model}',
            }

        invalid_fields = sorted(set(action.changes.keys()) - self.allowed_expense_fields())
        if invalid_fields:
            return {
                'success': False,
                'message': f'报销更新包含不允许的字段: {", ".join(invalid_fields)}',
            }
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {
                'success': False,
                'message': permission_check['message'],
            }

        model = self._resolve_model_name(action)
        if action.operation == 'approve' and model == 'invoice_request':
            request = self._get_invoice_request_for_action(action.object_ids[0], user)
            before_snapshot = self._snapshot_instance(request, fields=[
                'status',
                'reviewer_id',
                'review_time',
                'review_comment',
                'invoice_id',
                'invoice_time',
            ])
            after_snapshot = dict(before_snapshot)
            after_snapshot.update({
                'status': action.changes.get('status', 'approved'),
                'reviewer_id': getattr(user, 'id', 0) or 0,
                'review_time': 'NOW',
            })
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'finance',
                        'model_name': 'InvoiceRequest',
                        'object_pk': str(getattr(request, 'id', action.object_ids[0])),
                        'change_type': 'update',
                        'before_snapshot': before_snapshot,
                        'after_snapshot': after_snapshot,
                        'changed_fields': ['status', 'reviewer_id', 'review_time'],
                    }
                ],
            }

        if action.operation == 'approve' and model == 'expense':
            expense = self._get_expense_for_action(action.object_ids[0], user)
            before_snapshot = self._snapshot_instance(expense, fields=[
                'check_status',
                'check_history_uids',
                'check_time',
            ])
            after_snapshot = dict(before_snapshot)
            after_snapshot.update({
                'check_status': action.changes.get('check_status', 2),
                'check_time': 'NOW',
            })
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'finance',
                        'model_name': 'Expense',
                        'object_pk': str(getattr(expense, 'id', action.object_ids[0])),
                        'change_type': 'update',
                        'before_snapshot': before_snapshot,
                        'after_snapshot': after_snapshot,
                        'changed_fields': ['check_status', 'check_time', 'check_history_uids'],
                    }
                ],
            }

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

        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'finance',
                    'model_name': 'Expense',
                    'object_pk': str(getattr(expense, 'id', action.object_ids[0])),
                    'change_type': change_type,
                    'before_snapshot': before_snapshot,
                    'after_snapshot': after_snapshot,
                    'changed_fields': changed_fields,
                    'rollback_metadata': {
                        'model': 'expense',
                    },
                }
            ],
        }

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

        expense = self._get_expense_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            if hasattr(expense, 'delete'):
                expense.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        for field, value in action.changes.items():
            setattr(expense, field, value)
        expense.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def allowed_expense_fields(self):
        return {
            'code',
            'subject_id',
            'admin_id',
            'did',
            'project_id',
            'cost',
            'income_month',
            'expense_time',
            'file_ids',
            'pay_status',
            'pay_admin_id',
            'pay_time',
            'check_status',
            'check_flow_id',
            'check_step_sort',
            'check_uids',
            'check_last_uid',
            'check_history_uids',
            'check_copy_uids',
            'check_time',
            'create_time',
            'remark',
            'auto_generated',
        }

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
        }
        permission_code = permission_map.get((model, action.operation))
        if not permission_code:
            return {'allowed': False, 'message': '未配置财务操作权限'}
        result = self.permission_guard.check_action_permission(user, action, permission_code)
        return {'allowed': result.allowed, 'message': '权限不足' if not result.allowed else 'allowed'}

    def _snapshot_instance(self, instance, fields=None):
        if fields is None:
            meta = getattr(instance, '_meta', None)
            concrete_fields = getattr(meta, 'concrete_fields', None) if meta else None
            if concrete_fields:
                fields = [
                    field.attname
                    for field in concrete_fields
                    if getattr(field, 'attname', None)
                ]
            else:
                fields = [key for key in vars(instance).keys() if not key.startswith('_') and not callable(getattr(instance, key))]
        snapshot = {}
        for field in fields:
            snapshot[field] = getattr(instance, field, None)
        return snapshot

    def _get_expense_for_action(self, expense_id, user):
        from apps.finance.models import Expense

        return Expense.objects.get(id=expense_id)

    def _get_invoice_request_for_action(self, request_id, user):
        from apps.finance.models import InvoiceRequest

        return InvoiceRequest.objects.get(id=request_id)
