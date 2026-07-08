from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Q

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class ProductionResourceModuleAdapter(AIBaseModuleAdapter):
    permission_guard = AIPermissionGuard()

    CONFIG = {
        'production_task': {
            'model_name': 'ProductionTask',
            'permission': {
                'create': 'user.add_production_task',
                'update': 'user.change_production_task',
                'delete': 'user.delete_production_task',
            },
            'required_create_fields': {'plan_id', 'name', 'code', 'procedure_id', 'quantity', 'plan_start_time', 'plan_end_time'},
            'allowed_fields': {
                'plan_id', 'name', 'code', 'procedure_id', 'equipment_id', 'quantity',
                'completed_quantity', 'qualified_quantity', 'defective_quantity',
                'plan_start_time', 'plan_end_time', 'actual_start_time', 'actual_end_time',
                'status', 'assignee_id', 'description', 'suspended_by_id', 'suspended_time',
                'suspend_reason',
            },
            'int_fields': {'plan_id', 'procedure_id', 'equipment_id', 'status', 'assignee_id', 'suspended_by_id'},
            'decimal_fields': {'quantity', 'completed_quantity', 'qualified_quantity', 'defective_quantity'},
            'datetime_fields': {'plan_start_time', 'plan_end_time', 'actual_start_time', 'actual_end_time', 'suspended_time'},
            'create_defaults': {
                'equipment_id': None,
                'completed_quantity': Decimal('0'),
                'qualified_quantity': Decimal('0'),
                'defective_quantity': Decimal('0'),
                'status': 1,
                'assignee_id': None,
                'description': '',
                'suspended_by_id': None,
                'suspended_time': None,
                'suspend_reason': '',
            },
        },
        'production_equipment': {
            'model_name': 'Equipment',
            'permission': {
                'create': 'user.add_equipment',
                'update': 'user.change_equipment',
                'delete': 'user.delete_equipment',
            },
            'required_create_fields': {'name', 'code'},
            'allowed_fields': {
                'name', 'code', 'model', 'manufacturer', 'purchase_date', 'purchase_cost',
                'department_id', 'location', 'status', 'responsible_person_id',
                'maintenance_cycle', 'last_maintenance', 'next_maintenance', 'description',
            },
            'int_fields': {'department_id', 'status', 'responsible_person_id', 'maintenance_cycle'},
            'decimal_fields': {'purchase_cost'},
            'date_fields': {'purchase_date', 'last_maintenance', 'next_maintenance'},
            'create_defaults': {
                'model': '',
                'manufacturer': '',
                'purchase_date': None,
                'purchase_cost': Decimal('0'),
                'department_id': None,
                'location': '',
                'status': 1,
                'responsible_person_id': None,
                'maintenance_cycle': 30,
                'last_maintenance': None,
                'next_maintenance': None,
                'description': '',
            },
        },
        'production_procedure': {
            'model_name': 'ProductionProcedure',
            'permission': {
                'create': 'user.add_procedure',
                'update': 'user.change_procedure',
                'delete': 'user.delete_procedure',
            },
            'required_create_fields': {'name', 'code'},
            'allowed_fields': {'name', 'code', 'description', 'standard_time', 'cost_per_hour', 'department_id', 'sort', 'status'},
            'int_fields': {'department_id', 'sort'},
            'decimal_fields': {'standard_time', 'cost_per_hour'},
            'bool_fields': {'status'},
            'create_defaults': {
                'description': '',
                'standard_time': Decimal('0'),
                'cost_per_hour': Decimal('0'),
                'department_id': None,
                'sort': 0,
                'status': True,
            },
        },
    }

    def __init__(self, resource='production_task'):
        self.resource = resource

    def validate(self, action):
        config = self.CONFIG[self.resource]
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持生产资源操作: {action.operation}'}
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
            return {
                'success': True,
                'change_set': [
                    self._build_change_set(
                        getattr(instance, 'id', action.object_ids[0]),
                        before_snapshot,
                        None,
                        'delete',
                        sorted(before_snapshot.keys()),
                    )
                ],
            }

        normalized = self._normalize_payload(action.changes or {}, user, partial=True)
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(normalized['payload'])
        return {
            'success': True,
            'change_set': [
                self._build_change_set(
                    getattr(instance, 'id', action.object_ids[0]),
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
        return {'allowed': result.allowed, 'message': f'权限不足，无法操作{self.resource}' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes, user, partial=False):
        config = self.CONFIG[self.resource]
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in config.get('int_fields', set()):
                    payload[field] = int(value) if value not in (None, '') else None
                elif field in config.get('decimal_fields', set()):
                    payload[field] = Decimal(str(value)) if value not in (None, '') else Decimal('0')
                elif field in config.get('date_fields', set()):
                    payload[field] = self._parse_date(value)
                elif field in config.get('datetime_fields', set()):
                    payload[field] = self._parse_datetime(value)
                elif field in config.get('bool_fields', set()):
                    payload[field] = self._to_bool(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': f'{self.resource} 字段格式无效，请检查编号、日期、时间和数值'}

        if not partial:
            defaults = dict(config.get('create_defaults') or {})
            for field, default_value in defaults.items():
                payload.setdefault(field, default_value)
            if self.resource == 'production_task':
                payload.setdefault('creator_id', getattr(user, 'id', 0) or None)
            elif self.resource in {'production_equipment', 'production_procedure'}:
                payload.setdefault('creator_id', getattr(user, 'id', 0) or None)

        return {'success': True, 'payload': self._snapshot_dict(payload)}

    def _get_model(self):
        from apps.production import models as production_models

        return getattr(production_models, self.CONFIG[self.resource]['model_name'])

    def _get_instance_for_action(self, object_id, user):
        model = self._get_model()
        queryset = model.objects.all()
        if self.resource == 'production_task' and not getattr(user, 'is_superuser', False):
            user_id = getattr(user, 'id', None)
            queryset = queryset.filter(
                Q(assignee_id=user_id) |
                Q(creator_id=user_id) |
                Q(plan__manager_id=user_id)
            ).distinct()
        return queryset.get(id=object_id)

    def _snapshot_instance(self, instance):
        if self.resource == 'production_task':
            payload = {
                'plan_id': getattr(instance, 'plan_id', None),
                'name': getattr(instance, 'name', ''),
                'code': getattr(instance, 'code', ''),
                'procedure_id': getattr(instance, 'procedure_id', None),
                'equipment_id': getattr(instance, 'equipment_id', None),
                'quantity': getattr(instance, 'quantity', Decimal('0')),
                'completed_quantity': getattr(instance, 'completed_quantity', Decimal('0')),
                'qualified_quantity': getattr(instance, 'qualified_quantity', Decimal('0')),
                'defective_quantity': getattr(instance, 'defective_quantity', Decimal('0')),
                'plan_start_time': getattr(instance, 'plan_start_time', None),
                'plan_end_time': getattr(instance, 'plan_end_time', None),
                'actual_start_time': getattr(instance, 'actual_start_time', None),
                'actual_end_time': getattr(instance, 'actual_end_time', None),
                'status': getattr(instance, 'status', 1),
                'assignee_id': getattr(instance, 'assignee_id', None),
                'description': getattr(instance, 'description', ''),
                'creator_id': getattr(instance, 'creator_id', None),
                'suspended_by_id': getattr(instance, 'suspended_by_id', None),
                'suspended_time': getattr(instance, 'suspended_time', None),
                'suspend_reason': getattr(instance, 'suspend_reason', ''),
            }
        elif self.resource == 'production_equipment':
            payload = {
                'name': getattr(instance, 'name', ''),
                'code': getattr(instance, 'code', ''),
                'model': getattr(instance, 'model', ''),
                'manufacturer': getattr(instance, 'manufacturer', ''),
                'purchase_date': getattr(instance, 'purchase_date', None),
                'purchase_cost': getattr(instance, 'purchase_cost', Decimal('0')),
                'department_id': getattr(instance, 'department_id', None),
                'location': getattr(instance, 'location', ''),
                'status': getattr(instance, 'status', 1),
                'responsible_person_id': getattr(instance, 'responsible_person_id', None),
                'maintenance_cycle': getattr(instance, 'maintenance_cycle', 30),
                'last_maintenance': getattr(instance, 'last_maintenance', None),
                'next_maintenance': getattr(instance, 'next_maintenance', None),
                'description': getattr(instance, 'description', ''),
                'creator_id': getattr(instance, 'creator_id', None),
            }
        else:
            payload = {
                'name': getattr(instance, 'name', ''),
                'code': getattr(instance, 'code', ''),
                'description': getattr(instance, 'description', ''),
                'standard_time': getattr(instance, 'standard_time', Decimal('0')),
                'cost_per_hour': getattr(instance, 'cost_per_hour', Decimal('0')),
                'department_id': getattr(instance, 'department_id', None),
                'sort': getattr(instance, 'sort', 0),
                'status': getattr(instance, 'status', True),
                'creator_id': getattr(instance, 'creator_id', None),
            }
        return self._snapshot_dict(payload)

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'production',
            'model_name': self.CONFIG[self.resource]['model_name'],
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or before_snapshot or {}).keys()),
        }

    def _snapshot_dict(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, Decimal):
                snapshot[field] = format(value, 'f')
            elif isinstance(value, datetime):
                snapshot[field] = value.isoformat()
            elif isinstance(value, date):
                snapshot[field] = value.isoformat()
            else:
                snapshot[field] = value
        return snapshot

    def _parse_date(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        return date.fromisoformat(str(value))

    def _parse_datetime(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, datetime):
            return value
        raw = str(value).strip().replace('T', ' ')
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        raise ValueError('invalid datetime')

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on', '是'}
