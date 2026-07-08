from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class WorkHourModuleAdapter(AIBaseModuleAdapter):
    resource = 'workhour'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'task_id', 'work_date', 'hours'}
    allowed_fields = {'task_id', 'user_id', 'work_date', 'hours', 'description'}

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持工时操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'工时创建缺少必填字段: {", ".join(missing)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '工时操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'工时更新包含不允许的字段: {", ".join(invalid)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, user)
            if not normalized['success']:
                return normalized
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, self._snapshot_dict(normalized['payload']), 'create')]}

        workhour = self._get_workhour_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_workhour(workhour)
        if action.operation == 'delete':
            return {'success': True, 'change_set': [self._build_change_set(getattr(workhour, 'id', action.object_ids[0]), before_snapshot, {'deleted': True}, 'delete', ['id'])]}

        normalized = self._normalize_payload(action.changes or {}, user)
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        return {'success': True, 'change_set': [self._build_change_set(getattr(workhour, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.project.models import WorkHour

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, user)
            payload = normalized['payload']
            workhour = WorkHour.objects.create(**payload)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(workhour.id, None, self._snapshot_workhour(workhour), 'create')]}

        workhour = self._get_workhour_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            workhour.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {}, user)
        if not normalized['success']:
            return normalized
        payload = normalized['payload']
        for field, value in payload.items():
            setattr(workhour, field, value)
        workhour.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'project',
            'model_name': 'WorkHour',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'project.add_workhour',
            'update': 'project.change_workhour',
            'delete': 'project.delete_workhour',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作工时' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes, user):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'task_id', 'user_id'}:
                    payload[field] = int(value)
                elif field == 'hours':
                    payload[field] = Decimal(str(value))
                elif field == 'work_date':
                    payload[field] = self._parse_date(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '工时字段格式无效，请检查日期、任务和工时'}
        payload.setdefault('user_id', getattr(user, 'id', 0) or 0)
        return {'success': True, 'payload': payload}

    def _parse_date(self, value):
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise ValueError('invalid date')

    def _snapshot_workhour(self, workhour):
        return self._snapshot_dict({
            'id': getattr(workhour, 'id', None),
            'task_id': getattr(workhour, 'task_id', None),
            'user_id': getattr(workhour, 'user_id', None),
            'work_date': getattr(workhour, 'work_date', None),
            'hours': getattr(workhour, 'hours', Decimal('0')),
            'description': getattr(workhour, 'description', ''),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, Decimal):
                snapshot[field] = format(value, 'f')
            elif isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            elif isinstance(value, date):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _get_workhour_for_action(self, workhour_id, user):
        from apps.project.models import WorkHour

        queryset = WorkHour.objects.all()
        if getattr(user, 'is_superuser', False):
            return queryset.get(id=workhour_id)
        return queryset.filter(user=user).get(id=workhour_id)
