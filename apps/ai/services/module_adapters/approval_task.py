from __future__ import annotations

from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class ApprovalTaskModuleAdapter(AIBaseModuleAdapter):
    resource = 'approval_task'
    permission_guard = AIPermissionGuard()

    def validate(self, action):
        if action.operation not in {'approve', 'reject'}:
            return {'success': False, 'message': f'暂不支持待办审批操作: {action.operation}'}
        if not action.object_ids:
            return {'success': False, 'message': '待办审批操作缺少目标记录'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation
        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        task = self._get_task_for_action(action.object_ids[0], user)
        before_task = self._snapshot_task(task)
        after_task = dict(before_task)
        after_task.update({
            'status': 'completed',
            'result': action.operation,
            'comment': action.changes.get('comment', ''),
            'completed_at': 'NOW',
            'handler_id': getattr(user, 'id', 0) or 0,
        })

        change_set = [self._build_task_change_set(getattr(task, 'id', action.object_ids[0]), before_task, after_task)]

        approval = getattr(task, 'approval', None)
        if approval is not None:
            before_approval = self._snapshot_approval(approval)
            after_approval = dict(before_approval)
            if action.operation == 'reject':
                after_approval.update({'status': 3, 'current_step_order': 0})
                changed_fields = ['status', 'current_step_order']
            else:
                next_step = max(int(getattr(task.step, 'step_order', 0) or 0) + 1, int(getattr(approval, 'current_step_order', 0) or 0))
                after_approval.update({'status': 1, 'current_step_order': next_step})
                changed_fields = ['status', 'current_step_order']
            change_set.append(self._build_approval_change_set(getattr(approval, 'id', None), before_approval, after_approval, changed_fields))

        return {'success': True, 'change_set': change_set}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        task = self._get_task_for_action(action.object_ids[0], user)
        return self._execute_flow_action(task, action, user)

    def _execute_flow_action(self, task, action, user):
        from apps.approval.models import ApprovalRecord
        from apps.approval.views import _activate_next_steps, _cancel_pending_tasks

        approval = task.approval
        before_state = self._snapshot_related_state(approval)
        now = timezone.now()
        task.status = 'completed'
        task.result = action.operation
        task.comment = action.changes.get('comment', '')
        task.completed_at = now
        task.handler = user
        task.save(update_fields=['status', 'result', 'comment', 'completed_at', 'handler', 'updated_at'])

        current_step = task.step
        if action.operation == 'reject':
            _cancel_pending_tasks(approval, 'reject', now)
            approval.status = 3
            approval.current_step_order = 0
            approval.save(update_fields=['status', 'current_step_order', 'update_time'])
        else:
            pending_tasks = approval.tasks.filter(step=current_step, status='pending')
            if current_step.approval_mode in {'single', 'any'} or current_step.step_type == 'orsign':
                pending_tasks.update(
                    status='cancelled',
                    result='cancelled',
                    completed_at=now,
                    updated_at=now,
                )
                _activate_next_steps(approval, current_step)
            elif not pending_tasks.exists():
                _activate_next_steps(approval, current_step)

        ApprovalRecord.objects.create(
            approval=approval,
            step_order=current_step.step_order,
            step_name=current_step.step_name,
            action=action.operation,
            comment=action.changes.get('comment', ''),
            handler=user,
        )
        after_state = self._snapshot_related_state(approval)
        return {
            'success': True,
            'message': action.operation,
            'change_set': self._build_state_change_sets(before_state, after_state),
        }

    def _check_permission(self, action, user):
        allowed = bool(getattr(user, 'is_authenticated', False))
        return {
            'allowed': allowed,
            'message': '未登录，无法处理待办审批' if not allowed else 'allowed',
        }

    def _get_task_for_action(self, task_id, user):
        from apps.approval.models import ApprovalTask

        task = ApprovalTask.objects.select_related('approval', 'step').get(
            id=task_id,
            status='pending',
        )
        handler_id = getattr(task, 'handler_id', None)
        user_id = getattr(user, 'id', None)
        if handler_id and user_id and handler_id != user_id and not getattr(user, 'is_superuser', False):
            raise ApprovalTask.DoesNotExist()
        return task

    def _snapshot_related_state(self, approval):
        return {
            'approval': {
                str(approval.id): self._snapshot_model(approval),
            },
            'tasks': {
                str(task.id): self._snapshot_model(task)
                for task in approval.tasks.all().order_by('id')
            },
            'records': {
                str(record.id): self._snapshot_model(record)
                for record in approval.records.all().order_by('id')
            },
        }

    def _snapshot_model(self, instance):
        return {
            field.attname: self._json_value(getattr(instance, field.attname))
            for field in instance._meta.concrete_fields
        }

    def _json_value(self, value):
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
            return value
        return str(value)

    def _build_state_change_sets(self, before_state, after_state):
        change_sets = []
        for state_key, model_name in (
                ('approval', 'Approval'),
                ('tasks', 'ApprovalTask'),
                ('records', 'ApprovalRecord')):
            before_items = before_state.get(state_key) or {}
            after_items = after_state.get(state_key) or {}
            for object_pk in sorted(set(before_items) | set(after_items), key=lambda value: int(value)):
                before = before_items.get(object_pk)
                after = after_items.get(object_pk)
                if before == after:
                    continue
                if before is None:
                    change_type = 'create'
                elif after is None:
                    change_type = 'delete'
                else:
                    change_type = 'update'
                changed_fields = sorted(
                    field for field in set(before or {}) | set(after or {})
                    if (before or {}).get(field) != (after or {}).get(field)
                )
                change_sets.append({
                    'app_label': 'approval',
                    'model_name': model_name,
                    'object_pk': object_pk,
                    'change_type': change_type,
                    'before_snapshot': before,
                    'after_snapshot': after,
                    'changed_fields': changed_fields,
                })
        return change_sets

    def _snapshot_task(self, task):
        return {
            'approval_id': getattr(task, 'approval_id', getattr(getattr(task, 'approval', None), 'id', None)),
            'step_id': getattr(task, 'step_id', None),
            'handler_id': getattr(task, 'handler_id', getattr(getattr(task, 'handler', None), 'id', None)),
            'status': getattr(task, 'status', 'pending'),
            'result': getattr(task, 'result', ''),
            'comment': getattr(task, 'comment', ''),
            'completed_at': getattr(task, 'completed_at', None),
        }

    def _snapshot_approval(self, approval):
        return {
            'status': getattr(approval, 'status', 0),
            'current_step_order': getattr(approval, 'current_step_order', 0),
        }

    def _build_task_change_set(self, object_pk, before_snapshot, after_snapshot):
        return {
            'app_label': 'approval',
            'model_name': 'ApprovalTask',
            'object_pk': str(object_pk),
            'change_type': 'update',
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': ['status', 'result', 'comment', 'completed_at', 'handler_id'],
        }

    def _build_approval_change_set(self, object_pk, before_snapshot, after_snapshot, changed_fields):
        return {
            'app_label': 'approval',
            'model_name': 'Approval',
            'object_pk': str(object_pk),
            'change_type': 'update',
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields,
        }
