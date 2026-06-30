from __future__ import annotations

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter


class ApprovalModuleAdapter(AIBaseModuleAdapter):
    resource = 'approval'

    def preview(self, action, user):
        approval = self._get_approval_for_action(action.object_ids[0], user)

        if action.operation != 'withdraw':
            return {
                'success': False,
                'message': f'暂不支持审批动作: {action.operation}',
            }

        before_snapshot = {
            'status': getattr(approval, 'status', None),
            'current_step_order': getattr(approval, 'current_step_order', None),
        }
        after_snapshot = {
            'status': 0,
            'current_step_order': 0,
        }
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
                    'changed_fields': ['status', 'current_step_order'],
                }
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview
        return {
            'success': True,
            'message': 'withdrawn',
            'change_set': preview['change_set'],
        }

    def _get_approval_for_action(self, approval_id, user):
        from apps.approval.models import Approval

        return Approval.objects.get(id=approval_id)
