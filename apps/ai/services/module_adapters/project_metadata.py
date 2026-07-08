from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class ProjectMetadataModuleAdapter(AIBaseModuleAdapter):
    permission_guard = AIPermissionGuard()

    CONFIG = {
        'project_document': {
            'app_label': 'project',
            'model_name': 'ProjectDocument',
            'permission': {
                'create': 'project.add_project_document',
                'update': 'project.change_project_document',
                'delete': 'project.delete_project_document',
            },
            'required_create_fields': {'project_id', 'title'},
            'allowed_fields': {'project_id', 'title', 'content', 'file_path'},
        },
        'project_stage': {
            'app_label': 'project',
            'model_name': 'ProjectStage',
            'permission': {
                'create': 'project.add_project_stage',
                'update': 'project.change_project_stage',
                'delete': 'project.delete_project_stage',
            },
            'required_create_fields': {'name', 'code'},
            'allowed_fields': {'name', 'code', 'description', 'sort_order', 'is_active'},
        },
        'project_category': {
            'app_label': 'project',
            'model_name': 'ProjectCategory',
            'permission': {
                'create': 'project.add_project_category',
                'update': 'project.change_project_category',
                'delete': 'project.delete_project_category',
            },
            'required_create_fields': {'name', 'code'},
            'allowed_fields': {'name', 'code', 'description', 'color', 'sort_order', 'is_active'},
        },
        'work_type': {
            'app_label': 'project',
            'model_name': 'WorkType',
            'permission': {
                'create': 'project.add_work_type',
                'update': 'project.change_work_type',
                'delete': 'project.delete_work_type',
            },
            'required_create_fields': {'name', 'code'},
            'allowed_fields': {'name', 'code', 'description', 'hourly_rate', 'sort_order', 'is_active'},
        },
    }

    def __init__(self, resource='project_document'):
        self.resource = resource

    def validate(self, action):
        config = self.CONFIG[self.resource]
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持项目资料操作: {action.operation}'}
        if action.operation == 'create':
            missing = [field for field in sorted(config['required_create_fields']) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'{self.resource} 创建缺少必填字段: {", ".join(missing)}'}
        elif not action.object_ids:
            return {'success': False, 'message': f'{self.resource} 操作缺少目标记录'}
        if action.operation != 'delete':
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
            after_snapshot = None if self.resource != 'project_document' else {**before_snapshot, 'delete_time': 'NOW'}
            change_type = 'delete'
            changed_fields = sorted(before_snapshot.keys()) if after_snapshot is None else ['delete_time']
            return {'success': True, 'change_set': [self._build_change_set(getattr(instance, 'id', action.object_ids[0]), before_snapshot, after_snapshot, change_type, changed_fields)]}

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
            if self.resource == 'project_document':
                instance.delete_time = timezone.now()
                instance.save(update_fields=['delete_time', 'update_time'])
            else:
                instance.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {}, user, partial=True)
        if not normalized['success']:
            return normalized
        for field, value in normalized['payload'].items():
            setattr(instance, field, value)
        instance.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_code = self.CONFIG[self.resource]['permission'][action.operation]
        result = self.permission_guard.check_action_permission(user, action, permission_code)
        return {'allowed': result.allowed, 'message': '权限不足，无法操作项目资料' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes, user, partial=False):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'project_id', 'sort_order'}:
                    payload[field] = int(value) if value not in (None, '') else 0
                elif field == 'hourly_rate':
                    payload[field] = Decimal(str(value)) if value not in (None, '') else None
                elif field == 'is_active':
                    payload[field] = self._to_bool(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '项目资料字段格式无效，请检查项目、排序和费率'}

        if not partial:
            if self.resource == 'project_document':
                payload.setdefault('content', '')
                payload.setdefault('file_path', '')
                payload.setdefault('creator_id', getattr(user, 'id', 0) or None)
            elif self.resource == 'project_stage':
                payload.setdefault('description', '')
                payload.setdefault('sort_order', 0)
                payload.setdefault('is_active', True)
            elif self.resource == 'project_category':
                payload.setdefault('description', '')
                payload.setdefault('color', '')
                payload.setdefault('sort_order', 0)
                payload.setdefault('is_active', True)
            elif self.resource == 'work_type':
                payload.setdefault('description', '')
                payload.setdefault('hourly_rate', None)
                payload.setdefault('sort_order', 0)
                payload.setdefault('is_active', True)
        return {'success': True, 'payload': self._snapshot_dict(payload)}

    def _get_instance_for_action(self, object_id, user):
        model = self._get_model()
        if self.resource == 'project_document':
            return model.objects.get(id=object_id, delete_time__isnull=True)
        return model.objects.get(id=object_id)

    def _get_model(self):
        from apps.project import models as project_models

        return getattr(project_models, self.CONFIG[self.resource]['model_name'])

    def _snapshot_instance(self, instance):
        if self.resource == 'project_document':
            payload = {
                'project_id': getattr(instance, 'project_id', None),
                'title': getattr(instance, 'title', ''),
                'content': getattr(instance, 'content', ''),
                'file_path': getattr(instance, 'file_path', ''),
                'creator_id': getattr(instance, 'creator_id', None),
                'delete_time': getattr(instance, 'delete_time', None),
            }
        elif self.resource == 'project_stage':
            payload = {
                'name': getattr(instance, 'name', ''),
                'code': getattr(instance, 'code', ''),
                'description': getattr(instance, 'description', ''),
                'sort_order': getattr(instance, 'sort_order', 0),
                'is_active': getattr(instance, 'is_active', True),
            }
        elif self.resource == 'project_category':
            payload = {
                'name': getattr(instance, 'name', ''),
                'code': getattr(instance, 'code', ''),
                'description': getattr(instance, 'description', ''),
                'color': getattr(instance, 'color', ''),
                'sort_order': getattr(instance, 'sort_order', 0),
                'is_active': getattr(instance, 'is_active', True),
            }
        else:
            payload = {
                'name': getattr(instance, 'name', ''),
                'code': getattr(instance, 'code', ''),
                'description': getattr(instance, 'description', ''),
                'hourly_rate': getattr(instance, 'hourly_rate', None),
                'sort_order': getattr(instance, 'sort_order', 0),
                'is_active': getattr(instance, 'is_active', True),
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
            if isinstance(value, Decimal):
                normalized[key] = str(value)
            else:
                normalized[key] = value
        return normalized

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on', '是'}
