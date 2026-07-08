from __future__ import annotations

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class EmployeeModuleAdapter(AIBaseModuleAdapter):
    resource = 'employee'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'username', 'name'}
    allowed_fields = {
        'username',
        'name',
        'nickname',
        'mobile',
        'email',
        'did',
        'pid',
        'position_id',
        'position_name',
        'job_number',
        'type',
        'work_location',
        'status',
        'is_lock',
        'desc',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持员工操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'员工创建缺少必填字段: {", ".join(missing)}'}
            invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
            if invalid:
                return {'success': False, 'message': f'员工创建包含不允许的字段: {", ".join(invalid)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '员工操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'员工更新包含不允许的字段: {", ".join(invalid)}'}
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
            after_snapshot = self._build_create_snapshot(normalized['payload'])
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, after_snapshot, 'create')]}

        employee = self._get_employee_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_employee(employee)

        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot.update({'status': 0, 'is_active': False, 'is_lock': 1})
            return {
                'success': True,
                'change_set': [
                    self._build_change_set(
                        getattr(employee, 'id', action.object_ids[0]),
                        before_snapshot,
                        after_snapshot,
                        'delete',
                        ['status', 'is_active', 'is_lock'],
                    )
                ],
            }

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(normalized['payload'])
        return {
            'success': True,
            'change_set': [
                self._build_change_set(
                    getattr(employee, 'id', action.object_ids[0]),
                    before_snapshot,
                    after_snapshot,
                    'update',
                    sorted(normalized['payload'].keys()),
                )
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.user.models.admin import Admin

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            payload = self._build_create_payload(normalized['payload'])
            employee = Admin(**payload)
            if hasattr(employee, 'set_unusable_password'):
                employee.set_unusable_password()
            employee.save()
            return {
                'success': True,
                'message': 'created',
                'change_set': [self._build_change_set(employee.id, None, self._snapshot_employee(employee), 'create')],
            }

        employee = self._get_employee_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            employee.status = 0
            if hasattr(employee, 'is_active'):
                employee.is_active = False
            employee.is_lock = 1
            employee.save()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        for field, value in normalized['payload'].items():
            setattr(employee, field, value)
        employee.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'user.add_employee',
            'update': 'user.change_employee',
            'delete': 'user.delete_employee',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作员工' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'did', 'pid', 'position_id', 'status', 'is_lock'}:
                    payload[field] = int(value) if value not in (None, '') else 0
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '员工字段格式无效，请检查部门、状态和职位信息'}
        return {'success': True, 'payload': payload}

    def _build_create_payload(self, payload):
        create_payload = {
            'username': payload.get('username', ''),
            'name': payload.get('name', ''),
            'nickname': payload.get('nickname', ''),
            'mobile': payload.get('mobile', ''),
            'email': payload.get('email', ''),
            'did': payload.get('did', 0) or 0,
            'pid': payload.get('pid', 0) or 0,
            'position_id': payload.get('position_id', 0) or 0,
            'position_name': payload.get('position_name', ''),
            'job_number': payload.get('job_number', ''),
            'type': payload.get('type', ''),
            'work_location': payload.get('work_location', ''),
            'status': payload.get('status', 1) if payload.get('status', None) not in (None, '') else 1,
            'is_lock': payload.get('is_lock', 0) if payload.get('is_lock', None) not in (None, '') else 0,
            'desc': payload.get('desc', ''),
            'thumb': '',
            'is_active': True,
        }
        return create_payload

    def _build_create_snapshot(self, payload):
        snapshot = self._build_create_payload(payload)
        snapshot['is_active'] = snapshot.get('status', 1) == 1
        return snapshot

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'user',
            'model_name': 'Admin',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _snapshot_employee(self, employee):
        return {
            'id': getattr(employee, 'id', None),
            'username': getattr(employee, 'username', ''),
            'name': getattr(employee, 'name', ''),
            'nickname': getattr(employee, 'nickname', ''),
            'mobile': getattr(employee, 'mobile', ''),
            'email': getattr(employee, 'email', ''),
            'did': getattr(employee, 'did', 0),
            'pid': getattr(employee, 'pid', 0),
            'position_id': getattr(employee, 'position_id', 0),
            'position_name': getattr(employee, 'position_name', ''),
            'job_number': getattr(employee, 'job_number', ''),
            'type': getattr(employee, 'type', ''),
            'work_location': getattr(employee, 'work_location', ''),
            'status': getattr(employee, 'status', 1),
            'is_lock': getattr(employee, 'is_lock', 0),
            'desc': getattr(employee, 'desc', ''),
            'is_active': getattr(employee, 'is_active', True),
        }

    def _get_employee_for_action(self, employee_id, user):
        from apps.user.models.admin import Admin

        queryset = Admin.objects.filter(is_superuser=False)
        return queryset.get(id=employee_id)
