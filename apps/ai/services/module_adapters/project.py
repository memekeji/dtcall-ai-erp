from __future__ import annotations

from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter


class ProjectModuleAdapter(AIBaseModuleAdapter):
    resource = 'project'
    allowed_update_fields = {
        'name',
        'description',
        'status',
        'priority',
        'progress',
        'budget',
        'actual_cost',
        'start_date',
        'end_date',
    }

    def validate(self, action):
        if action.operation == 'delete':
            return {'success': True}

        invalid_fields = sorted(set(action.changes.keys()) - self.allowed_update_fields)
        if invalid_fields:
            return {
                'success': False,
                'message': f'项目更新包含不允许的字段: {", ".join(invalid_fields)}',
            }
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        project = self._get_project_for_action(action.object_ids[0], user)
        before_snapshot = {
            'name': getattr(project, 'name', None),
            'description': getattr(project, 'description', None),
            'status': getattr(project, 'status', None),
            'priority': getattr(project, 'priority', None),
            'progress': getattr(project, 'progress', None),
            'delete_time': getattr(project, 'delete_time', None),
        }

        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['delete_time'] = 'NOW'
            change_type = 'delete'
            changed_fields = ['delete_time']
        else:
            after_snapshot = dict(before_snapshot)
            after_snapshot.update(action.changes)
            change_type = 'update'
            changed_fields = sorted(action.changes.keys())

        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'project',
                    'model_name': 'Project',
                    'object_pk': str(getattr(project, 'id', action.object_ids[0])),
                    'change_type': change_type,
                    'before_snapshot': before_snapshot,
                    'after_snapshot': after_snapshot,
                    'changed_fields': changed_fields,
                }
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        project = self._get_project_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            project.delete_time = timezone.now()
            project.save()
            return {
                'success': True,
                'message': 'deleted',
                'change_set': preview['change_set'],
            }

        for field, value in action.changes.items():
            setattr(project, field, value)
        project.save()
        return {
            'success': True,
            'message': 'updated',
            'change_set': preview['change_set'],
        }

    def _get_project_for_action(self, project_id, user):
        from apps.project.models import Project

        return Project.objects.get(id=project_id)
