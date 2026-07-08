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
        now = timezone.now()
        task.status = 'completed'
        task.result = action.operation
        task.comment = action.changes.get('comment', '')
        task.completed_at = now
        task.handler = user
        task.save(update_fields=['status', 'result', 'comment', 'completed_at', 'handler', 'updated_at'])

        approval = getattr(task, 'approval', None)
        if approval is not None:
            if action.operation == 'reject':
                approval.status = 3
                approval.current_step_order = 0
            else:
                approval.status = 1
                approval.current_step_order = max(
                    int(getattr(task.step, 'step_order', 0) or 0) + 1,
                    int(getattr(approval, 'current_step_order', 0) or 0),
                )
            if hasattr(approval, 'save'):
                approval.save(update_fields=['status', 'current_step_order', 'update_time'])

        return {'success': True, 'message': action.operation, 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        result = self.permission_guard.check_action_permission(user, action, 'approval.change_approvaltask')
        return {'allowed': result.allowed, 'message': '权限不足，无法处理待办审批' if not result.allowed else 'allowed'}

    def _get_task_for_action(self, task_id, user):
        from apps.approval.models import ApprovalTask

        task = ApprovalTask.objects.select_related('approval', 'step').get(id=task_id)
        handler_id = getattr(task, 'handler_id', None)
        user_id = getattr(user, 'id', None)
        if handler_id and user_id and handler_id != user_id and not getattr(user, 'is_superuser', False):
            raise ApprovalTask.DoesNotExist()
        return task

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
