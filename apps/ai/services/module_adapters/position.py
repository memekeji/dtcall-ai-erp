from __future__ import annotations

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class PositionModuleAdapter(AIBaseModuleAdapter):
    resource = 'position'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'title'}
    allowed_fields = {'title', 'did', 'desc', 'sort', 'status'}

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持岗位操作: {action.operation}'}
        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'岗位创建缺少必填字段: {", ".join(missing)}'}
        elif not action.object_ids:
            return {'success': False, 'message': '岗位操作缺少目标记录'}
        if action.operation != 'delete':
            invalid = sorted(set((action.changes or {}).keys()) - self.allowed_fields)
            if invalid:
                return {'success': False, 'message': f'岗位操作包含不允许的字段: {", ".join(invalid)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation
        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        if action.operation == 'create':
            payload = self._normalize_payload(action.changes or {}, partial=False)
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, payload, 'create')]}

        position = self._get_position_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_position(position)
        if action.operation == 'delete':
            return {'success': True, 'change_set': [self._build_change_set(getattr(position, 'id', action.object_ids[0]), before_snapshot, None, 'delete', sorted(before_snapshot.keys()))]}

        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._normalize_payload(action.changes or {}, partial=True))
        return {'success': True, 'change_set': [self._build_change_set(getattr(position, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted((action.changes or {}).keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.user.models.position import Position

        if action.operation == 'create':
            position = Position.objects.create(**self._normalize_payload(action.changes or {}, partial=False))
            snapshot = self._snapshot_position(position)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(position.id, None, snapshot, 'create', sorted(snapshot.keys()))]}

        position = self._get_position_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            position.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        for field, value in self._normalize_payload(action.changes or {}, partial=True).items():
            setattr(position, field, value)
        position.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'position.add_position',
            'update': 'position.change_position',
            'delete': 'position.delete_position',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作岗位' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes, partial=False):
        payload = {}
        for field, value in (changes or {}).items():
            if field in {'did', 'sort', 'status'}:
                payload[field] = int(value) if value not in (None, '') else 0
            else:
                payload[field] = value
        if not partial:
            payload.setdefault('did', 0)
            payload.setdefault('desc', '')
            payload.setdefault('sort', 0)
            payload.setdefault('status', 1)
        return payload

    def _get_position_for_action(self, position_id, user):
        from apps.user.models.position import Position

        return Position.objects.get(id=position_id)

    def _snapshot_position(self, position):
        return {
            'title': getattr(position, 'title', ''),
            'did': getattr(position, 'did', 0),
            'desc': getattr(position, 'desc', ''),
            'sort': getattr(position, 'sort', 0),
            'status': getattr(position, 'status', 1),
        }

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'user',
            'model_name': 'Position',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or before_snapshot or {}).keys()),
        }
