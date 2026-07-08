from __future__ import annotations

from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class MeetingModuleAdapter(AIBaseModuleAdapter):
    resource = 'meeting'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'title', 'meeting_date', 'meeting_end_time'}
    allowed_fields = {
        'title', 'meeting_type', 'meeting_date', 'meeting_end_time', 'room_id',
        'location', 'host_id', 'recorder_id', 'department_id', 'status',
        'agenda', 'content', 'summary', 'resolution', 'action_items',
        'next_meeting', 'attachments', 'rating', 'feedback',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持会议操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'会议创建缺少必填字段: {", ".join(missing)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '会议操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'会议更新包含不允许的字段: {", ".join(invalid)}'}
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

        meeting = self._get_meeting_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_meeting(meeting)
        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot.update({'deleted_at': 'NOW', 'is_deleted': True})
            return {'success': True, 'change_set': [self._build_change_set(getattr(meeting, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'delete', ['deleted_at', 'is_deleted'])]}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        return {'success': True, 'change_set': [self._build_change_set(getattr(meeting, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.oa.models import MeetingRecord

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            payload = normalized['payload']
            meeting = MeetingRecord.objects.create(**payload)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(meeting.id, None, self._snapshot_meeting(meeting), 'create')]}

        meeting = self._get_meeting_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            meeting.deleted_at = timezone.now()
            meeting.is_deleted = True
            meeting.save(update_fields=['deleted_at', 'is_deleted', 'updated_at'])
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        payload = normalized['payload']
        for field, value in payload.items():
            setattr(meeting, field, value)
        meeting.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        if not getattr(user, 'is_authenticated', False):
            return {'allowed': False, 'message': '权限不足，无法操作会议'}
        if getattr(user, 'is_superuser', False):
            return {'allowed': True, 'message': 'allowed'}

        if action.operation == 'create':
            allowed = bool(getattr(user, 'has_perm', lambda code: False)('user.apply_meeting'))
            return {'allowed': allowed, 'message': '权限不足，无法操作会议' if not allowed else 'allowed'}

        permission_map = {
            'update': 'user.change_meeting_record',
            'delete': 'user.delete_meeting_record',
        }
        allowed = bool(getattr(user, 'has_perm', lambda code: False)(permission_map[action.operation]))
        return {'allowed': allowed, 'message': '权限不足，无法操作会议' if not allowed else 'allowed'}

    def _normalize_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'room_id', 'host_id', 'recorder_id', 'department_id', 'rating'}:
                    payload[field] = int(value) if value not in (None, '') else None
                elif field in {'meeting_date', 'meeting_end_time', 'next_meeting'}:
                    payload[field] = self._parse_datetime(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '会议字段格式无效，请检查时间、人员和会议室'}
        return {'success': True, 'payload': payload}

    def _parse_datetime(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError('invalid datetime')

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'oa',
            'model_name': 'MeetingRecord',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _snapshot_meeting(self, meeting):
        return self._snapshot_dict({
            'id': getattr(meeting, 'id', None),
            'title': getattr(meeting, 'title', ''),
            'meeting_type': getattr(meeting, 'meeting_type', 'regular'),
            'meeting_date': getattr(meeting, 'meeting_date', None),
            'meeting_end_time': getattr(meeting, 'meeting_end_time', None),
            'room_id': getattr(meeting, 'room_id', None),
            'location': getattr(meeting, 'location', ''),
            'host_id': getattr(meeting, 'host_id', None),
            'recorder_id': getattr(meeting, 'recorder_id', None),
            'department_id': getattr(meeting, 'department_id', None),
            'status': getattr(meeting, 'status', 'scheduled'),
            'agenda': getattr(meeting, 'agenda', ''),
            'content': getattr(meeting, 'content', ''),
            'summary': getattr(meeting, 'summary', ''),
            'resolution': getattr(meeting, 'resolution', ''),
            'action_items': getattr(meeting, 'action_items', ''),
            'next_meeting': getattr(meeting, 'next_meeting', None),
            'attachments': getattr(meeting, 'attachments', ''),
            'rating': getattr(meeting, 'rating', None),
            'feedback': getattr(meeting, 'feedback', ''),
            'deleted_at': getattr(meeting, 'deleted_at', None),
            'is_deleted': getattr(meeting, 'is_deleted', False),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _get_meeting_for_action(self, meeting_id, user):
        from apps.oa.models import MeetingRecord

        queryset = MeetingRecord.objects.filter(is_deleted=False)
        if getattr(user, 'is_superuser', False):
            return queryset.get(id=meeting_id)
        return queryset.filter(
            Q(host_id=getattr(user, 'id', None)) |
            Q(recorder_id=getattr(user, 'id', None)) |
            Q(participants=user) |
            Q(shared_users=user)
        ).distinct().get(id=meeting_id)
