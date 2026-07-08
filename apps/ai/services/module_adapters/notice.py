from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class NoticeModuleAdapter(AIBaseModuleAdapter):
    resource = 'notice'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'title', 'content'}
    allowed_fields = {'title', 'content', 'notice_type', 'is_top', 'is_published', 'publish_time', 'expire_time'}

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持公告操作: {action.operation}'}
        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'公告创建缺少必填字段: {", ".join(missing)}'}
            return {'success': True}
        if not action.object_ids:
            return {'success': False, 'message': '公告操作缺少目标记录'}
        if action.operation == 'delete':
            return {'success': True}
        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'公告更新包含不允许的字段: {", ".join(invalid)}'}
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
            after_snapshot = dict(normalized['payload'])
            after_snapshot['author_id'] = getattr(user, 'id', 0) or 0
            if after_snapshot.get('is_published') and not after_snapshot.get('publish_time'):
                after_snapshot['publish_time'] = 'NOW'
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, self._snapshot_dict(after_snapshot), 'create')]}

        notice = self._get_notice_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_notice(notice)
        if action.operation == 'delete':
            return {'success': True, 'change_set': [self._build_change_set(getattr(notice, 'id', action.object_ids[0]), before_snapshot, {'deleted': True}, 'delete', ['id'])]}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        if normalized['payload'].get('is_published') and not after_snapshot.get('publish_time'):
            after_snapshot['publish_time'] = 'NOW'
        return {'success': True, 'change_set': [self._build_change_set(getattr(notice, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.system.models import Notice

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            payload = normalized['payload']
            if payload.get('is_published') and not payload.get('publish_time'):
                payload['publish_time'] = timezone.now()
            notice = Notice.objects.create(**payload, author=user)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(notice.id, None, self._snapshot_notice(notice), 'create')]}

        notice = self._get_notice_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            notice.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        payload = normalized['payload']
        if payload.get('is_published') and not getattr(notice, 'publish_time', None) and 'publish_time' not in payload:
            payload['publish_time'] = timezone.now()
        for field, value in payload.items():
            setattr(notice, field, value)
        notice.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'system',
            'model_name': 'Notice',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'system.add_notice',
            'update': 'system.change_notice',
            'delete': 'system.delete_notice',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作公告' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'publish_time', 'expire_time'}:
                    payload[field] = self._parse_datetime(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '公告时间格式无效'}
        return {'success': True, 'payload': payload}

    def _parse_datetime(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError('invalid datetime')

    def _snapshot_notice(self, notice):
        return self._snapshot_dict({
            'id': getattr(notice, 'id', None),
            'title': getattr(notice, 'title', ''),
            'content': getattr(notice, 'content', ''),
            'notice_type': getattr(notice, 'notice_type', 'company'),
            'is_top': getattr(notice, 'is_top', False),
            'is_published': getattr(notice, 'is_published', False),
            'publish_time': getattr(notice, 'publish_time', None),
            'expire_time': getattr(notice, 'expire_time', None),
            'author_id': getattr(notice, 'author_id', None),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _get_notice_for_action(self, notice_id, user):
        from apps.system.models import Notice

        queryset = Notice.objects.all()
        if getattr(user, 'is_superuser', False):
            return queryset.get(id=notice_id)
        return queryset.get(id=notice_id, author=user)
