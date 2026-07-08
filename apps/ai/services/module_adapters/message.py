from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class MessageModuleAdapter(AIBaseModuleAdapter):
    resource = 'message'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'title', 'content'}
    allowed_fields = {
        'category_id', 'user_id', 'title', 'content', 'priority', 'is_broadcast',
        'target_users', 'target_departments', 'related_object_type',
        'related_object_id', 'action_url', 'expire_time',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持消息操作: {action.operation}'}
        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'消息创建缺少必填字段: {", ".join(missing)}'}
            return {'success': True}
        if not action.object_ids:
            return {'success': False, 'message': '消息操作缺少目标记录'}
        if action.operation == 'delete':
            return {'success': True}
        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'消息更新包含不允许的字段: {", ".join(invalid)}'}
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
            after_snapshot['sender_id'] = getattr(user, 'id', 0) or 0
            after_snapshot['is_active'] = True
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, after_snapshot, 'create')]}

        message = self._get_message_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_message(message)
        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['is_active'] = False
            return {'success': True, 'change_set': [self._build_change_set(getattr(message, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'delete', ['is_active'])]}

        normalized = self._normalize_payload(action.changes or {}, user)
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        return {'success': True, 'change_set': [self._build_change_set(getattr(message, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.message.models import Message

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, user)
            payload = normalized['payload']
            message = Message.objects.create(**payload, sender=user)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(message.id, None, self._snapshot_message(message), 'create')]}

        message = self._get_message_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            message.is_active = False
            message.save(update_fields=['is_active'])
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {}, user)
        if not normalized['success']:
            return normalized
        for field, value in normalized['payload'].items():
            setattr(message, field, value)
        message.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'message',
            'model_name': 'Message',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'message.create_message',
            'update': 'message.create_message',
            'delete': 'message.delete_message',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作消息' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes, user):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'category_id', 'user_id', 'related_object_id'}:
                    payload[field] = int(value) if value not in (None, '') else None
                elif field == 'expire_time':
                    payload[field] = self._parse_datetime(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '消息字段格式无效'}
        return {'success': True, 'payload': payload}

    def _parse_datetime(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError('invalid datetime')

    def _snapshot_message(self, message):
        return self._snapshot_dict({
            'id': getattr(message, 'id', None),
            'category_id': getattr(message, 'category_id', None),
            'user_id': getattr(message, 'user_id', None),
            'sender_id': getattr(message, 'sender_id', None),
            'title': getattr(message, 'title', ''),
            'content': getattr(message, 'content', ''),
            'priority': getattr(message, 'priority', 2),
            'is_broadcast': getattr(message, 'is_broadcast', False),
            'target_users': getattr(message, 'target_users', ''),
            'target_departments': getattr(message, 'target_departments', ''),
            'related_object_type': getattr(message, 'related_object_type', ''),
            'related_object_id': getattr(message, 'related_object_id', None),
            'action_url': getattr(message, 'action_url', ''),
            'expire_time': getattr(message, 'expire_time', None),
            'is_active': getattr(message, 'is_active', True),
            'ai_summary': getattr(message, 'ai_summary', None),
            'ai_suggested_replies': getattr(message, 'ai_suggested_replies', []),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _get_message_for_action(self, message_id, user):
        from apps.message.models import Message

        queryset = Message.objects.filter(is_active=True)
        if getattr(user, 'is_superuser', False):
            return queryset.get(id=message_id)
        return queryset.filter(sender=user).get(id=message_id)
