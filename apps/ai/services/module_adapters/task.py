from __future__ import annotations

from datetime import date, datetime

from django.db.models import Q
from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class TaskModuleAdapter(AIBaseModuleAdapter):
    resource = 'task'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'title'}
    allowed_fields = {
        'title', 'description', 'project_id', 'step_id', 'assignee_id',
        'start_date', 'end_date', 'estimated_hours', 'actual_hours',
        'status', 'priority', 'progress',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持任务操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'任务创建缺少必填字段: {", ".join(missing)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '任务操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'任务更新包含不允许的字段: {", ".join(invalid)}'}
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
            after_snapshot['creator_id'] = getattr(user, 'id', 0) or 0
            after_snapshot['delete_time'] = None
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, self._snapshot_dict(after_snapshot), 'create')]}

        task = self._get_task_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_task(task)
        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['delete_time'] = 'NOW'
            return {'success': True, 'change_set': [self._build_change_set(getattr(task, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'delete', ['delete_time'])]}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        return {'success': True, 'change_set': [self._build_change_set(getattr(task, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.project.models import Task

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            payload = normalized['payload']
            task = Task.objects.create(**payload, creator=user)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(task.id, None, self._snapshot_task(task), 'create')]}

        task = self._get_task_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            task.delete_time = timezone.now()
            task.save(update_fields=['delete_time', 'update_time'])
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        payload = normalized['payload']
        for field, value in payload.items():
            setattr(task, field, value)
        task.save(update_fields=sorted(set(payload.keys()) | {'update_time'}))
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'project',
            'model_name': 'Task',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'project.add_task',
            'update': 'project.change_task',
            'delete': 'project.delete_task',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作任务' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'project_id', 'step_id', 'assignee_id'}:
                    payload[field] = int(value) if value not in (None, '') else None
                elif field in {'estimated_hours', 'actual_hours', 'status', 'priority', 'progress'}:
                    payload[field] = int(value)
                elif field in {'start_date', 'end_date'}:
                    payload[field] = self._parse_date(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '任务字段格式无效，请检查日期、负责人和状态'}
        return {'success': True, 'payload': payload}

    def _parse_date(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise ValueError('invalid date')

    def _snapshot_task(self, task):
        return self._snapshot_dict({
            'id': getattr(task, 'id', None),
            'title': getattr(task, 'title', ''),
            'description': getattr(task, 'description', ''),
            'project_id': getattr(task, 'project_id', None),
            'step_id': getattr(task, 'step_id', None),
            'assignee_id': getattr(task, 'assignee_id', None),
            'start_date': getattr(task, 'start_date', None),
            'end_date': getattr(task, 'end_date', None),
            'estimated_hours': getattr(task, 'estimated_hours', 0),
            'actual_hours': getattr(task, 'actual_hours', 0),
            'status': getattr(task, 'status', 1),
            'priority': getattr(task, 'priority', 2),
            'progress': getattr(task, 'progress', 0),
            'creator_id': getattr(task, 'creator_id', None),
            'delete_time': getattr(task, 'delete_time', None),
        })

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            elif isinstance(value, date):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _get_task_for_action(self, task_id, user):
        from apps.project.models import Task

        queryset = Task.objects.filter(delete_time__isnull=True)
        if getattr(user, 'is_superuser', False):
            return queryset.get(id=task_id)
        return queryset.filter(
            Q(creator=user) | Q(assignee=user) | Q(participants=user) | Q(project__manager=user)
        ).distinct().get(id=task_id)
