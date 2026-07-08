from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class ProductionModuleAdapter(AIBaseModuleAdapter):
    resource = 'production'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'name', 'code', 'quantity', 'unit', 'plan_start_date', 'plan_end_date'}
    allowed_fields = {
        'name', 'code', 'product_id', 'bom_id', 'procedure_set_id', 'process_route_id',
        'quantity', 'unit', 'plan_start_date', 'plan_end_date', 'actual_start_date',
        'actual_end_date', 'status', 'priority', 'department_id', 'manager_id',
        'description', 'auto_complete', 'complete_threshold',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持生产计划操作: {action.operation}'}

        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'生产计划创建缺少必填字段: {", ".join(missing)}'}
            return {'success': True}

        if not action.object_ids:
            return {'success': False, 'message': '生产计划操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        invalid = sorted(set(action.changes.keys()) - self.allowed_fields)
        if invalid:
            return {'success': False, 'message': f'生产计划更新包含不允许的字段: {", ".join(invalid)}'}
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
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, self._snapshot_dict(after_snapshot), 'create')]}

        plan = self._get_plan_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_plan(plan)
        if action.operation == 'delete':
            return {'success': True, 'change_set': [self._build_change_set(getattr(plan, 'id', action.object_ids[0]), before_snapshot, None, 'delete', sorted(before_snapshot.keys()))]}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._snapshot_dict(normalized['payload']))
        return {'success': True, 'change_set': [self._build_change_set(getattr(plan, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted(normalized['payload'].keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.production.models import ProductionPlan

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {})
            payload = normalized['payload']
            plan = ProductionPlan.objects.create(**payload, creator=user)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(plan.id, None, self._snapshot_plan(plan), 'create')]}

        plan = self._get_plan_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            plan.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {})
        if not normalized['success']:
            return normalized
        payload = normalized['payload']
        for field, value in payload.items():
            setattr(plan, field, value)
        plan.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'user.add_production_plan',
            'update': 'user.change_production_plan',
            'delete': 'user.delete_production_plan',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作生产计划' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'product_id', 'bom_id', 'procedure_set_id', 'process_route_id', 'department_id', 'manager_id'}:
                    payload[field] = int(value) if value not in (None, '') else None
                elif field in {'status', 'priority'}:
                    payload[field] = int(value)
                elif field in {'quantity', 'complete_threshold'}:
                    payload[field] = Decimal(str(value))
                elif field in {'plan_start_date', 'plan_end_date', 'actual_start_date', 'actual_end_date'}:
                    payload[field] = self._parse_date(value)
                elif field == 'auto_complete':
                    payload[field] = self._to_bool(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '生产计划字段格式无效，请检查日期、数量和负责人'}
        return {'success': True, 'payload': payload}

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on', 'enabled'}
        return bool(value)

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

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'production',
            'model_name': 'ProductionPlan',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or {}).keys()),
        }

    def _snapshot_plan(self, plan):
        return self._snapshot_dict({
            'id': getattr(plan, 'id', None),
            'name': getattr(plan, 'name', ''),
            'code': getattr(plan, 'code', ''),
            'product_id': getattr(plan, 'product_id', None),
            'bom_id': getattr(plan, 'bom_id', None),
            'procedure_set_id': getattr(plan, 'procedure_set_id', None),
            'process_route_id': getattr(plan, 'process_route_id', None),
            'quantity': getattr(plan, 'quantity', Decimal('0')),
            'unit': getattr(plan, 'unit', ''),
            'plan_start_date': getattr(plan, 'plan_start_date', None),
            'plan_end_date': getattr(plan, 'plan_end_date', None),
            'actual_start_date': getattr(plan, 'actual_start_date', None),
            'actual_end_date': getattr(plan, 'actual_end_date', None),
            'status': getattr(plan, 'status', 1),
            'priority': getattr(plan, 'priority', 2),
            'department_id': getattr(plan, 'department_id', None),
            'manager_id': getattr(plan, 'manager_id', None),
            'description': getattr(plan, 'description', ''),
            'creator_id': getattr(plan, 'creator_id', None),
            'auto_complete': getattr(plan, 'auto_complete', False),
            'complete_threshold': getattr(plan, 'complete_threshold', Decimal('100.00')),
        })

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

    def _get_plan_for_action(self, plan_id, user):
        from apps.production.models import ProductionPlan

        queryset = ProductionPlan.objects.all()
        if getattr(user, 'is_superuser', False):
            return queryset.get(id=plan_id)
        user_id = getattr(user, 'id', None)
        return queryset.filter(manager_id=user_id).get(id=plan_id)
