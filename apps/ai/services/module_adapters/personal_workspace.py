from __future__ import annotations

from datetime import datetime

from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter


class PersonalWorkspaceModuleAdapter(AIBaseModuleAdapter):
    CONFIG = {
        'work_record': {
            'app_label': 'personal',
            'model_name': 'WorkRecord',
            'required_create_fields': {'title', 'content', 'work_date', 'start_time', 'end_time', 'duration'},
            'allowed_fields': {'title', 'content', 'work_type', 'work_date', 'start_time', 'end_time', 'duration', 'progress', 'difficulty', 'result', 'problem', 'next_plan'},
        },
        'work_report': {
            'app_label': 'personal',
            'model_name': 'WorkReport',
            'required_create_fields': {'title', 'report_type', 'report_date', 'summary', 'completed_work', 'next_work'},
            'allowed_fields': {'title', 'report_type', 'report_date', 'summary', 'completed_work', 'next_work', 'problems', 'suggestions', 'attachments'},
            'actions': {'submit'},
        },
        'personal_note': {
            'app_label': 'personal',
            'model_name': 'PersonalNote',
            'required_create_fields': {'title', 'content'},
            'allowed_fields': {'title', 'content', 'category', 'tags', 'is_important', 'is_private'},
        },
        'personal_task': {
            'app_label': 'personal',
            'model_name': 'PersonalTask',
            'required_create_fields': {'title'},
            'allowed_fields': {'title', 'description', 'priority', 'status', 'due_date', 'progress', 'estimated_hours', 'actual_hours'},
            'actions': {'submit'},
        },
        'personal_contact': {
            'app_label': 'personal',
            'model_name': 'PersonalContact',
            'required_create_fields': {'name'},
            'allowed_fields': {'name', 'company', 'position', 'phone', 'mobile', 'email', 'address', 'notes', 'tags', 'is_important'},
        },
    }

    def __init__(self, resource='personal_task'):
        self.resource = resource

    def validate(self, action):
        config = self.CONFIG[self.resource]
        supported = {'create', 'update', 'delete'} | set(config.get('actions') or set())
        if action.operation not in supported:
            return {'success': False, 'message': f'暂不支持个人办公操作: {action.operation}'}
        if action.operation == 'create':
            missing = [field for field in sorted(config['required_create_fields']) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'{self.resource} 创建缺少必填字段: {", ".join(missing)}'}
        elif not action.object_ids:
            return {'success': False, 'message': f'{self.resource} 操作缺少目标记录'}
        if action.operation in {'create', 'update'}:
            invalid = sorted(set((action.changes or {}).keys()) - config['allowed_fields'])
            if invalid:
                return {'success': False, 'message': f'{self.resource} 操作包含不允许的字段: {", ".join(invalid)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation
        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, user, partial=False)
            if not normalized['success']:
                return normalized
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, normalized['payload'], 'create')]}

        instance = self._get_instance_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_instance(instance)
        if action.operation == 'delete':
            return {'success': True, 'change_set': [self._build_change_set(getattr(instance, 'id', action.object_ids[0]), before_snapshot, None, 'delete', sorted(before_snapshot.keys()))]}

        if action.operation == 'submit':
            after_snapshot = dict(before_snapshot)
            if self.resource == 'personal_task':
                after_snapshot.update({'status': 'completed', 'progress': 100, 'completed_at': 'NOW'})
                changed_fields = ['status', 'progress', 'completed_at']
            elif self.resource == 'work_report':
                after_snapshot.update({'is_submitted': True, 'submitted_at': 'NOW'})
                changed_fields = ['is_submitted', 'submitted_at']
            else:
                changed_fields = ['status']
            return {'success': True, 'change_set': [self._build_change_set(getattr(instance, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', changed_fields)]}

        normalized = self._normalize_payload(action.changes or {}, user, partial=True)
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(normalized['payload'])
        return {'success': True, 'change_set': [self._build_change_set(getattr(instance, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        model = self._get_model()
        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, user, partial=False)
            if not normalized['success']:
                return normalized
            instance = model.objects.create(**normalized['payload'])
            snapshot = self._snapshot_instance(instance)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(instance.id, None, snapshot, 'create', sorted(snapshot.keys()))]}

        instance = self._get_instance_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            instance.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        if action.operation == 'submit':
            if self.resource == 'personal_task':
                instance.status = 'completed'
                instance.progress = 100
                instance.completed_at = timezone.now()
                instance.save()
            elif self.resource == 'work_report':
                instance.is_submitted = True
                instance.submitted_at = timezone.now()
                instance.save()
            return {'success': True, 'message': 'submitted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {}, user, partial=True)
        if not normalized['success']:
            return normalized
        for field, value in normalized['payload'].items():
            setattr(instance, field, value)
        if self.resource == 'personal_task' and getattr(instance, 'status', '') == 'completed' and not getattr(instance, 'completed_at', None):
            instance.completed_at = timezone.now()
        instance.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        if not getattr(user, 'is_authenticated', False):
            return {'allowed': False, 'message': '未登录，无法操作个人办公数据'}
        return {'allowed': True, 'message': 'allowed'}

    def _normalize_payload(self, changes, user, partial=False):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'progress', 'difficulty', 'priority'}:
                    payload[field] = int(value) if value not in (None, '') else 0
                elif field in {'duration', 'estimated_hours', 'actual_hours'}:
                    payload[field] = float(value) if value not in (None, '') else 0
                elif field in {'is_important', 'is_private'}:
                    payload[field] = self._to_bool(value)
                elif field == 'due_date':
                    payload[field] = self._parse_datetime(value)
                elif field in {'work_date', 'report_date'}:
                    payload[field] = self._parse_date(value)
                elif field in {'start_time', 'end_time'}:
                    payload[field] = self._parse_time(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '个人办公字段格式无效，请检查日期、时间和数值'}

        if not partial:
            payload['user_id'] = getattr(user, 'id', 0) or 0
            if self.resource in {'work_record', 'work_report'}:
                payload['department_id'] = getattr(user, 'department_id', None)
            if self.resource == 'work_record':
                payload.setdefault('work_type', 'daily')
                payload.setdefault('progress', 0)
                payload.setdefault('difficulty', 3)
                payload.setdefault('result', '')
                payload.setdefault('problem', '')
                payload.setdefault('next_plan', '')
            elif self.resource == 'work_report':
                payload.setdefault('problems', '')
                payload.setdefault('suggestions', '')
                payload.setdefault('attachments', '')
                payload.setdefault('is_submitted', False)
                payload.setdefault('submitted_at', None)
            elif self.resource == 'personal_note':
                payload.setdefault('category', 'work')
                payload.setdefault('tags', '')
                payload.setdefault('is_important', False)
                payload.setdefault('is_private', True)
            elif self.resource == 'personal_task':
                payload.setdefault('description', '')
                payload.setdefault('priority', 2)
                payload.setdefault('status', 'todo')
                payload.setdefault('due_date', None)
                payload.setdefault('completed_at', None)
                payload.setdefault('progress', 0)
                payload.setdefault('estimated_hours', None)
                payload.setdefault('actual_hours', None)
            elif self.resource == 'personal_contact':
                payload.setdefault('company', '')
                payload.setdefault('position', '')
                payload.setdefault('phone', '')
                payload.setdefault('mobile', '')
                payload.setdefault('email', '')
                payload.setdefault('address', '')
                payload.setdefault('notes', '')
                payload.setdefault('tags', '')
                payload.setdefault('is_important', False)
        return {'success': True, 'payload': self._snapshot_dict(payload)}

    def _get_instance_for_action(self, object_id, user):
        model = self._get_model()
        return model.objects.get(id=object_id, user_id=getattr(user, 'id', 0) or 0)

    def _get_model(self):
        from apps.personal import models as personal_models

        return getattr(personal_models, self.CONFIG[self.resource]['model_name'])

    def _snapshot_instance(self, instance):
        if self.resource == 'work_record':
            payload = {
                'title': getattr(instance, 'title', ''),
                'content': getattr(instance, 'content', ''),
                'work_type': getattr(instance, 'work_type', 'daily'),
                'work_date': getattr(instance, 'work_date', None),
                'start_time': getattr(instance, 'start_time', None),
                'end_time': getattr(instance, 'end_time', None),
                'duration': getattr(instance, 'duration', 0),
                'progress': getattr(instance, 'progress', 0),
                'difficulty': getattr(instance, 'difficulty', 3),
                'result': getattr(instance, 'result', ''),
                'problem': getattr(instance, 'problem', ''),
                'next_plan': getattr(instance, 'next_plan', ''),
                'user_id': getattr(instance, 'user_id', None),
                'department_id': getattr(instance, 'department_id', None),
            }
        elif self.resource == 'work_report':
            payload = {
                'title': getattr(instance, 'title', ''),
                'report_type': getattr(instance, 'report_type', 'daily'),
                'report_date': getattr(instance, 'report_date', None),
                'summary': getattr(instance, 'summary', ''),
                'completed_work': getattr(instance, 'completed_work', ''),
                'next_work': getattr(instance, 'next_work', ''),
                'problems': getattr(instance, 'problems', ''),
                'suggestions': getattr(instance, 'suggestions', ''),
                'attachments': getattr(instance, 'attachments', ''),
                'user_id': getattr(instance, 'user_id', None),
                'department_id': getattr(instance, 'department_id', None),
                'is_submitted': getattr(instance, 'is_submitted', False),
                'submitted_at': getattr(instance, 'submitted_at', None),
            }
        elif self.resource == 'personal_note':
            payload = {
                'title': getattr(instance, 'title', ''),
                'content': getattr(instance, 'content', ''),
                'category': getattr(instance, 'category', 'work'),
                'tags': getattr(instance, 'tags', ''),
                'is_important': getattr(instance, 'is_important', False),
                'is_private': getattr(instance, 'is_private', True),
                'user_id': getattr(instance, 'user_id', None),
            }
        elif self.resource == 'personal_task':
            payload = {
                'title': getattr(instance, 'title', ''),
                'description': getattr(instance, 'description', ''),
                'priority': getattr(instance, 'priority', 2),
                'status': getattr(instance, 'status', 'todo'),
                'due_date': getattr(instance, 'due_date', None),
                'completed_at': getattr(instance, 'completed_at', None),
                'progress': getattr(instance, 'progress', 0),
                'estimated_hours': getattr(instance, 'estimated_hours', None),
                'actual_hours': getattr(instance, 'actual_hours', None),
                'user_id': getattr(instance, 'user_id', None),
            }
        else:
            payload = {
                'name': getattr(instance, 'name', ''),
                'company': getattr(instance, 'company', ''),
                'position': getattr(instance, 'position', ''),
                'phone': getattr(instance, 'phone', ''),
                'mobile': getattr(instance, 'mobile', ''),
                'email': getattr(instance, 'email', ''),
                'address': getattr(instance, 'address', ''),
                'notes': getattr(instance, 'notes', ''),
                'tags': getattr(instance, 'tags', ''),
                'is_important': getattr(instance, 'is_important', False),
                'user_id': getattr(instance, 'user_id', None),
            }
        return self._snapshot_dict(payload)

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        config = self.CONFIG[self.resource]
        return {
            'app_label': config['app_label'],
            'model_name': config['model_name'],
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or before_snapshot or {}).keys()),
        }

    def _snapshot_dict(self, payload):
        normalized = {}
        for key, value in (payload or {}).items():
            if hasattr(value, 'isoformat'):
                normalized[key] = value.isoformat()
            else:
                normalized[key] = value
        return normalized

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on', '是'}

    def _parse_date(self, value):
        if hasattr(value, 'isoformat') and not isinstance(value, str):
            return value
        return datetime.strptime(str(value), '%Y-%m-%d').date()

    def _parse_time(self, value):
        if hasattr(value, 'isoformat') and not isinstance(value, str):
            return value
        raw = str(value)
        time_format = '%H:%M:%S' if len(raw.split(':')) == 3 else '%H:%M'
        return datetime.strptime(raw, time_format).time()

    def _parse_datetime(self, value):
        if value in (None, ''):
            return None
        if hasattr(value, 'isoformat') and not isinstance(value, str):
            return value
        raw = str(value).strip().replace('T', ' ')
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        raise ValueError('invalid datetime')
