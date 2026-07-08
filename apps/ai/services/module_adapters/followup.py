from __future__ import annotations

from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class FollowupModuleAdapter(AIBaseModuleAdapter):
    resource = 'followup'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'customer_id', 'content'}
    allowed_fields = {'customer_id', 'follow_type', 'content', 'next_follow_time'}

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持跟进记录操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'跟进记录创建缺少必填字段: {", ".join(missing)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '跟进记录操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'跟进记录更新包含不允许的字段: {", ".join(invalid)}'}
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

        followup = self._get_followup_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_followup(followup)
        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['delete_time'] = 'NOW'
            return {'success': True, 'change_set': [self._build_change_set(getattr(followup, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'delete', ['delete_time'])]}

        normalized = self._normalize_payload(action.changes or {}, user)
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        return {'success': True, 'change_set': [self._build_change_set(getattr(followup, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.customer.models import FollowRecord

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, user)
            payload = normalized['payload']
            followup = FollowRecord.objects.create(**payload)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(followup.id, None, self._snapshot_followup(followup), 'create')]}

        followup = self._get_followup_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            followup.delete_time = int(timezone.now().timestamp())
            followup.save(update_fields=['delete_time', 'update_time'])
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {}, user)
        if not normalized['success']:
            return normalized
        payload = normalized['payload']
        for field, value in payload.items():
            setattr(followup, field, value)
        followup.save(update_fields=sorted(set(payload.keys()) | {'update_time'}))
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'user.add_follow_record',
            'update': 'user.change_follow_record',
            'delete': 'user.delete_follow_record',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作跟进记录' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes, user):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field == 'customer_id':
                    payload[field] = int(value)
                elif field == 'next_follow_time':
                    payload[field] = self._parse_datetime(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '跟进记录字段格式无效，请检查客户和下次跟进时间'}
        payload.setdefault('follow_user_id', getattr(user, 'id', 0) or 0)
        payload.setdefault('follow_type', 'phone')
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
            'app_label': 'customer',
            'model_name': 'FollowRecord',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _snapshot_followup(self, followup):
        return self._snapshot_dict({
            'id': getattr(followup, 'id', None),
            'customer_id': getattr(followup, 'customer_id', None),
            'follow_type': getattr(followup, 'follow_type', 'phone'),
            'content': getattr(followup, 'content', ''),
            'follow_user_id': getattr(followup, 'follow_user_id', None),
            'follow_time': getattr(followup, 'follow_time', None),
            'next_follow_time': getattr(followup, 'next_follow_time', None),
            'ai_summary': getattr(followup, 'ai_summary', None),
            'ai_sentiment': getattr(followup, 'ai_sentiment', None),
            'ai_key_points': getattr(followup, 'ai_key_points', []),
            'create_time': getattr(followup, 'create_time', None),
            'update_time': getattr(followup, 'update_time', None),
            'delete_time': getattr(followup, 'delete_time', 0),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _get_followup_for_action(self, followup_id, user):
        from apps.customer.models import FollowRecord

        queryset = FollowRecord.objects.filter(delete_time=0)
        if getattr(user, 'is_superuser', False):
            return queryset.get(id=followup_id)
        user_id = getattr(user, 'id', None)
        return queryset.filter(
            Q(follow_user_id=user_id) |
            Q(customer__belong_uid=user_id)
        ).distinct().get(id=followup_id)
