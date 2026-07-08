from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class ScheduleModuleAdapter(AIBaseModuleAdapter):
    resource = 'schedule'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'title', 'start_time', 'end_time'}
    allowed_fields = {
        'work_id', 'title', 'start_time', 'end_time', 'labor_time', 'did',
        'labor_type', 'cid', 'tid', 'content',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持日程操作: {action.operation}'}
        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'日程创建缺少必填字段: {", ".join(missing)}'}
            return {'success': True}
        if not action.object_ids:
            return {'success': False, 'message': '日程操作缺少目标记录'}
        if action.operation == 'delete':
            return {'success': True}
        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'日程更新包含不允许的字段: {", ".join(invalid)}'}
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
            after_snapshot = self._snapshot_dict(normalized['payload'])
            after_snapshot['delete_time'] = 0
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, after_snapshot, 'create')]}

        schedule = self._get_schedule_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_schedule(schedule)
        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['delete_time'] = 'NOW'
            return {'success': True, 'change_set': [self._build_change_set(getattr(schedule, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'delete', ['delete_time'])]}

        normalized = self._normalize_payload(action.changes or {}, user)
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        return {'success': True, 'change_set': [self._build_change_set(getattr(schedule, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.oa.models import Schedule

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, user)
            payload = normalized['payload']
            now_ts = int(timezone.now().timestamp())
            payload.setdefault('create_time', now_ts)
            payload.setdefault('update_time', now_ts)
            schedule = Schedule.objects.create(**payload)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(schedule.id, None, self._snapshot_schedule(schedule), 'create')]}

        schedule = self._get_schedule_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            schedule.delete_time = int(timezone.now().timestamp())
            schedule.save(update_fields=['delete_time'])
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {}, user)
        if not normalized['success']:
            return normalized
        payload = normalized['payload']
        payload['update_time'] = int(timezone.now().timestamp())
        for field, value in payload.items():
            setattr(schedule, field, value)
        schedule.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'oa',
            'model_name': 'Schedule',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'user.add_work_calendar',
            'update': 'user.change_work_calendar',
            'delete': 'user.delete_work_calendar',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作日程' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes, user):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'work_id', 'did', 'labor_type', 'cid', 'tid'}:
                    payload[field] = int(value) if value not in (None, '') else None
                elif field == 'labor_time':
                    payload[field] = float(value)
                elif field in {'start_time', 'end_time'}:
                    payload[field] = self._parse_datetime(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '日程字段格式无效，请检查时间和工时'}
        payload.setdefault('admin_id', getattr(user, 'id', 0) or 0)
        payload.setdefault('did', getattr(user, 'did', 0) or getattr(user, 'auth_did', 0) or payload.get('did') or 0)
        payload.setdefault('delete_time', 0)
        return {'success': True, 'payload': payload}

    def _parse_datetime(self, value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError('invalid datetime')

    def _snapshot_schedule(self, schedule):
        return self._snapshot_dict({
            'id': getattr(schedule, 'id', None),
            'work_id': getattr(schedule, 'work_id', 0),
            'title': getattr(schedule, 'title', ''),
            'start_time': getattr(schedule, 'start_time', None),
            'end_time': getattr(schedule, 'end_time', None),
            'labor_time': getattr(schedule, 'labor_time', 0),
            'admin_id': getattr(schedule, 'admin_id', 0),
            'did': getattr(schedule, 'did', 0),
            'labor_type': getattr(schedule, 'labor_type', 0),
            'cid': getattr(schedule, 'cid', None),
            'tid': getattr(schedule, 'tid', None),
            'content': getattr(schedule, 'content', ''),
            'delete_time': getattr(schedule, 'delete_time', 0),
            'create_time': getattr(schedule, 'create_time', 0),
            'update_time': getattr(schedule, 'update_time', 0),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _get_schedule_for_action(self, schedule_id, user):
        from apps.oa.models import Schedule

        queryset = Schedule.objects.filter(delete_time=0)
        if getattr(user, 'is_superuser', False):
            return queryset.get(id=schedule_id)
        return queryset.get(id=schedule_id, admin_id=getattr(user, 'id', 0) or 0)
