from __future__ import annotations

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class DepartmentModuleAdapter(AIBaseModuleAdapter):
    resource = 'department'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'name'}
    allowed_fields = {
        'name',
        'pid',
        'code',
        'manager_id',
        'leader_ids',
        'phone',
        'remark',
        'sort',
        'status',
        'is_active',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持部门操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'部门创建缺少必填字段: {", ".join(missing)}'}
            invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
            if invalid:
                return {'success': False, 'message': f'部门创建包含不允许的字段: {", ".join(invalid)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '部门操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'部门更新包含不允许的字段: {", ".join(invalid)}'}
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

        department = self._get_department_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_department(department)

        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot.update({'status': 0, 'is_active': False})
            return {
                'success': True,
                'change_set': [
                    self._build_change_set(
                        getattr(department, 'id', action.object_ids[0]),
                        before_snapshot,
                        after_snapshot,
                        'delete',
                        ['status', 'is_active'],
                    )
                ],
            }

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(normalized['payload'])
        if 'status' in normalized['payload']:
            after_snapshot['is_active'] = normalized['payload']['status'] == 1
        return {
            'success': True,
            'change_set': [
                self._build_change_set(
                    getattr(department, 'id', action.object_ids[0]),
                    before_snapshot,
                    after_snapshot,
                    'update',
                    sorted(set(normalized['payload'].keys()) | ({'is_active'} if 'status' in normalized['payload'] else set())),
                )
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.department.models import Department

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            payload = self._build_create_payload(normalized['payload'])
            department = Department.objects.create(**payload)
            return {
                'success': True,
                'message': 'created',
                'change_set': [self._build_change_set(department.id, None, self._snapshot_department(department), 'create')],
            }

        department = self._get_department_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            department.status = 0
            department.is_active = False
            department.save()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        payload = normalized['payload']
        for field, value in payload.items():
            setattr(department, field, value)
        if 'status' in payload and 'is_active' not in payload:
            department.is_active = payload['status'] == 1
        department.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'department.add_department',
            'update': 'department.change_department',
            'delete': 'department.delete_department',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作部门' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'pid', 'manager_id', 'sort', 'status'}:
                    payload[field] = int(value) if value not in (None, '') else 0
                elif field == 'is_active':
                    payload[field] = self._to_bool(value)
                elif field == 'leader_ids' and isinstance(value, (list, tuple)):
                    payload[field] = ','.join(str(item) for item in value if item not in (None, ''))
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '部门字段格式无效，请检查上级部门、负责人和状态'}
        return {'success': True, 'payload': payload}

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on', 'enabled'}
        return bool(value)

    def _build_create_payload(self, payload):
        status = payload.get('status', 1) if payload.get('status', None) not in (None, '') else 1
        is_active = payload.get('is_active')
        if is_active is None:
            is_active = status == 1
        return {
            'name': payload.get('name', ''),
            'pid': payload.get('pid', 0) or 0,
            'code': payload.get('code', ''),
            'manager_id': payload.get('manager_id'),
            'leader_ids': payload.get('leader_ids', ''),
            'phone': payload.get('phone', ''),
            'remark': payload.get('remark', ''),
            'sort': payload.get('sort', 0) or 0,
            'status': status,
            'is_active': is_active,
        }

    def _build_create_snapshot(self, payload):
        snapshot = self._build_create_payload(payload)
        snapshot['level'] = 0 if snapshot.get('pid', 0) == 0 else None
        return snapshot

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'department',
            'model_name': 'Department',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _snapshot_department(self, department):
        manager_id = getattr(department, 'manager_id', None)
        if manager_id is None and hasattr(department, 'manager') and getattr(department, 'manager', None) is not None:
            manager_id = getattr(department.manager, 'id', None)
        return {
            'id': getattr(department, 'id', None),
            'name': getattr(department, 'name', ''),
            'pid': getattr(department, 'pid', 0),
            'code': getattr(department, 'code', ''),
            'manager_id': manager_id,
            'leader_ids': getattr(department, 'leader_ids', ''),
            'phone': getattr(department, 'phone', ''),
            'remark': getattr(department, 'remark', ''),
            'sort': getattr(department, 'sort', 0),
            'status': getattr(department, 'status', 1),
            'level': getattr(department, 'level', 0),
            'is_active': getattr(department, 'is_active', True),
        }

    def _get_department_for_action(self, department_id, user):
        from apps.department.models import Department

        return Department.objects.get(id=department_id)
