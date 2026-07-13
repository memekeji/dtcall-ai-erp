from __future__ import annotations

from django.utils import timezone

from apps.ai.services.action_contracts import AIActionRequest
from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class ApprovalModuleAdapter(AIBaseModuleAdapter):
    resource = 'approval'
    permission_guard = AIPermissionGuard()
    required_create_fields = {'title', 'flow_id'}
    allowed_create_fields = {'title', 'flow_id', 'type_id', 'content', 'reviewer_id'}

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

        if action.operation == 'create':
            flow = self._get_create_flow(action, user)
            if flow is None:
                return {'success': False, 'message': '审批流程不存在、已停用或当前用户无权发起'}
            after_snapshot = self._build_create_snapshot(
                action,
                user,
                resolve_flow=False,
                flow=flow,
            )
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'approval',
                        'model_name': 'Approval',
                        'object_pk': 'NEW',
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': after_snapshot,
                        'changed_fields': sorted(after_snapshot.keys()),
                    }
                ],
            }

        approval = self._get_approval_for_action(action.object_ids[0], user)
        if action.operation in {'approve', 'reject'}:
            task_action = self._build_pending_task_action(approval, action, user)
            if task_action is None:
                return {'success': False, 'message': '当前用户没有可处理的审批任务'}
            from apps.ai.services.module_adapters.approval_task import ApprovalTaskModuleAdapter

            return ApprovalTaskModuleAdapter().preview(task_action, user)
        if action.operation == 'withdraw':
            validation = self._validate_withdraw(approval, user)
            if not validation.get('success'):
                return validation

        before_snapshot = self._snapshot_approval(approval)
        after_snapshot = dict(before_snapshot)
        changed_fields = []

        if action.operation == 'withdraw':
            after_snapshot.update({
                'status': 0,
                'current_step_order': 0,
            })
            changed_fields = ['status', 'current_step_order']
        elif action.operation == 'approve':
            after_snapshot.update({
                'status': 2,
                'current_step_order': (getattr(approval, 'current_step_order', 0) or 0) + 1,
            })
            changed_fields = ['status', 'current_step_order']
        elif action.operation == 'reject':
            after_snapshot.update({
                'status': 3,
            })
            changed_fields = ['status']

        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'approval',
                    'model_name': 'Approval',
                    'object_pk': str(getattr(approval, 'id', action.object_ids[0])),
                    'change_type': 'update',
                    'before_snapshot': before_snapshot,
                    'after_snapshot': after_snapshot,
                    'changed_fields': changed_fields,
                }
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        if action.operation == 'create':
            from apps.approval.models import Approval
            from apps.approval.views import _ensure_initial_tasks

            create_snapshot = self._build_create_snapshot(action, user, resolve_flow=True)
            approval = Approval.objects.create(
                title=action.changes.get('title', ''),
                flow_id=action.changes.get('flow_id'),
                type_id=create_snapshot.get('type_id', 0) or 0,
                applicant_id=getattr(user, 'id', 0) or 0,
                status=create_snapshot.get('status', 0),
                content=action.changes.get('content', ''),
                reviewer_id=action.changes.get('reviewer_id'),
                current_step_order=create_snapshot.get('current_step_order', 0),
            )
            _ensure_initial_tasks(approval)
            approval.refresh_from_db()
            approval_snapshot = self._snapshot_approval(approval)
            return {
                'success': True,
                'message': 'created',
                'change_set': [
                    {
                        'app_label': 'approval',
                        'model_name': 'Approval',
                        'object_pk': str(approval.id),
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': approval_snapshot,
                        'changed_fields': sorted(approval_snapshot.keys()),
                    }
                ],
            }

        approval = self._get_approval_for_action(action.object_ids[0], user)
        if action.operation in {'approve', 'reject'}:
            task_action = self._build_pending_task_action(approval, action, user)
            if task_action is None:
                return {'success': False, 'message': '当前用户没有可处理的审批任务'}
            from apps.ai.services.module_adapters.approval_task import ApprovalTaskModuleAdapter

            return ApprovalTaskModuleAdapter().execute(task_action, user, operation=operation)

        if action.operation == 'withdraw':
            validation = self._validate_withdraw(approval, user)
            if not validation.get('success'):
                return validation
            from apps.approval.models import ApprovalRecord
            from apps.approval.views import _cancel_pending_tasks
            from apps.ai.services.module_adapters.approval_task import ApprovalTaskModuleAdapter

            state_adapter = ApprovalTaskModuleAdapter()
            before_state = state_adapter._snapshot_related_state(approval)
            now = timezone.now()
            _cancel_pending_tasks(approval, 'withdraw', now)
            approval.status = 0
            approval.current_step_order = 0
            approval.save(update_fields=['status', 'current_step_order', 'update_time'])
            ApprovalRecord.objects.create(
                approval=approval,
                step_order=0,
                step_name='申请人撤回',
                action='withdraw',
                comment=action.changes.get('comment', ''),
                handler=user,
            )
            after_state = state_adapter._snapshot_related_state(approval)
            return {
                'success': True,
                'message': 'withdrawn',
                'change_set': state_adapter._build_state_change_sets(before_state, after_state),
            }

        return {
            'success': False,
            'message': f'暂不支持审批动作: {action.operation}',
        }

    def _get_approval_for_action(self, approval_id, user):
        from apps.approval.models import Approval

        return Approval.objects.get(id=approval_id)

    def _build_pending_task_action(self, approval, action, user):
        from apps.approval.views import _get_user_pending_task

        task = _get_user_pending_task(approval, user)
        if task is None:
            return None
        return AIActionRequest(
            resource='approval_task',
            operation=action.operation,
            object_ids=[task.id],
            changes={'comment': action.changes.get('comment', '')},
        )

    def _validate_withdraw(self, approval, user):
        from apps.approval.views import _can_withdraw_approval

        if not _can_withdraw_approval(approval, user):
            return {
                'success': False,
                'message': '仅申请人可撤回尚未进入下一节点处理的审批',
            }
        return {'success': True}

    def validate(self, action):
        if action.operation not in {'create', 'withdraw', 'approve', 'reject'}:
            return {'success': False, 'message': f'暂不支持审批动作: {action.operation}'}
        if action.operation == 'create':
            missing_fields = [
                field for field in sorted(self.required_create_fields)
                if action.changes.get(field) in (None, '')
            ]
            if missing_fields:
                return {'success': False, 'message': f'审批创建缺少必填字段: {", ".join(missing_fields)}'}
            invalid_fields = sorted(set(action.changes.keys()) - self.allowed_create_fields)
            if invalid_fields:
                return {'success': False, 'message': f'审批创建包含不允许的字段: {", ".join(invalid_fields)}'}
            return {'success': True}
        if not action.object_ids:
            return {'success': False, 'message': '审批操作缺少目标记录'}
        return {'success': True}

    def _check_permission(self, action, user):
        if not hasattr(user, 'is_authenticated'):
            return {'allowed': True, 'message': 'allowed'}
        allowed = bool(getattr(user, 'is_authenticated', False))
        return {
            'allowed': allowed,
            'message': '未登录，无法操作审批' if not allowed else 'allowed',
        }

    def _snapshot_approval(self, approval):
        return {
            'title': getattr(approval, 'title', ''),
            'flow_id': getattr(approval, 'flow_id', None),
            'type_id': getattr(approval, 'type_id', 0),
            'applicant_id': getattr(approval, 'applicant_id', 0),
            'status': getattr(approval, 'status', 0),
            'content': getattr(approval, 'content', ''),
            'reviewer_id': getattr(approval, 'reviewer_id', None),
            'current_step_order': getattr(approval, 'current_step_order', 1),
        }

    def _build_create_snapshot(self, action, user, resolve_flow=True, flow=None):
        if resolve_flow and flow is None:
            flow = self._get_create_flow(action, user)
        has_steps = bool(flow and flow.steps.exists())
        return {
            'title': action.changes.get('title', ''),
            'flow_id': action.changes.get('flow_id'),
            'type_id': action.changes.get('type_id') or getattr(flow, 'approval_type_id', 0) or 0,
            'applicant_id': getattr(user, 'id', 0) or 0,
            'status': 1 if has_steps else 2,
            'content': action.changes.get('content', ''),
            'reviewer_id': action.changes.get('reviewer_id'),
            'current_step_order': 1 if has_steps else 0,
        }

    def _get_create_flow(self, action, user=None):
        from apps.approval.models import ApprovalFlow

        flow_id = action.changes.get('flow_id')
        if not flow_id:
            return None
        flow = ApprovalFlow.objects.filter(id=flow_id, is_active=True).first()
        if flow is None:
            return None
        from apps.ai.services.confirmation_service import confirmation_service

        if not confirmation_service._user_can_initiate_approval_flow(user, flow):
            return None
        return flow
