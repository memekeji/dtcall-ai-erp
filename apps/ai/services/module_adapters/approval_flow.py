from __future__ import annotations

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class ApprovalFlowModuleAdapter(AIBaseModuleAdapter):
    resource = 'approval_flow'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'name', 'code'}
    allowed_fields = {'name', 'code', 'description', 'approval_type_id', 'is_active'}

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持审批流程操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'审批流程创建缺少必填字段: {", ".join(missing)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '审批流程操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'审批流程更新包含不允许的字段: {", ".join(invalid)}'}
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
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, self._snapshot_dict(normalized['payload']), 'create')]}

        flow = self._get_flow_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_flow(flow)
        if action.operation == 'delete':
            return {'success': True, 'change_set': [self._build_change_set(getattr(flow, 'id', action.object_ids[0]), before_snapshot, None, 'delete', sorted(before_snapshot.keys()))]}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        return {'success': True, 'change_set': [self._build_change_set(getattr(flow, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.approval.models import ApprovalFlow

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            payload = normalized['payload']
            flow = ApprovalFlow.objects.create(**payload)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(flow.id, None, self._snapshot_flow(flow), 'create')]}

        flow = self._get_flow_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            flow.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        payload = normalized['payload']
        for field, value in payload.items():
            setattr(flow, field, value)
        flow.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'approval.add_approvalflow',
            'update': 'approval.change_approvalflow',
            'delete': 'approval.delete_approvalflow',
        }
        if not getattr(user, 'is_authenticated', False):
            return {'allowed': False, 'message': '权限不足，无法操作审批流程'}
        if getattr(user, 'is_superuser', False):
            return {'allowed': True, 'message': 'allowed'}
        permission_code = permission_map[action.operation]
        allowed = bool(getattr(user, 'has_perm', lambda code: False)(permission_code))
        return {'allowed': allowed, 'message': '权限不足，无法操作审批流程' if not allowed else 'allowed'}

    def _normalize_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field == 'approval_type_id':
                    payload[field] = int(value) if value not in (None, '') else None
                elif field == 'is_active':
                    payload[field] = self._to_bool(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '审批流程字段格式无效'}
        return {'success': True, 'payload': payload}

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on', 'enabled'}
        return bool(value)

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'approval',
            'model_name': 'ApprovalFlow',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _snapshot_flow(self, flow):
        return self._snapshot_dict({
            'id': getattr(flow, 'id', None),
            'name': getattr(flow, 'name', ''),
            'code': getattr(flow, 'code', ''),
            'description': getattr(flow, 'description', ''),
            'approval_type_id': getattr(flow, 'approval_type_id', None),
            'is_active': getattr(flow, 'is_active', True),
        })

    def _snapshot_dict(self, values):
        return dict(values or {})

    def _get_flow_for_action(self, flow_id, user):
        from apps.approval.models import ApprovalFlow

        return ApprovalFlow.objects.get(id=flow_id)
