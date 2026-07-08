from __future__ import annotations

from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter


class EnterpriseModuleAdapter(AIBaseModuleAdapter):
    resource = 'enterprise'

    required_create_fields = {'title'}
    allowed_fields = {'title', 'city', 'bank', 'bank_sn', 'tax_num', 'phone', 'address', 'remark', 'status'}

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持企业信息操作: {action.operation}'}
        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'企业信息创建缺少必填字段: {", ".join(missing)}'}
        elif not action.object_ids:
            return {'success': False, 'message': '企业信息操作缺少目标记录'}
        if action.operation != 'delete':
            invalid = sorted(set((action.changes or {}).keys()) - self.allowed_fields)
            if invalid:
                return {'success': False, 'message': f'企业信息操作包含不允许的字段: {", ".join(invalid)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation
        permission_check = self._check_permission(user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        if action.operation == 'create':
            payload = self._normalize_payload(action.changes or {}, partial=False)
            return {'success': True, 'change_set': [self._build_change_set('NEW', None, payload, 'create')]}

        enterprise = self._get_enterprise_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_enterprise(enterprise)
        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['status'] = -1
            after_snapshot['update_time'] = 'NOW'
            return {'success': True, 'change_set': [self._build_change_set(getattr(enterprise, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', ['status', 'update_time'])]}

        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._normalize_payload(action.changes or {}, partial=True))
        return {'success': True, 'change_set': [self._build_change_set(getattr(enterprise, 'id', action.object_ids[0]), before_snapshot, after_snapshot, 'update', sorted((action.changes or {}).keys()))]}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.enterprise.models import Enterprise

        if action.operation == 'create':
            enterprise = Enterprise.objects.create(**self._normalize_payload(action.changes or {}, partial=False))
            snapshot = self._snapshot_enterprise(enterprise)
            return {'success': True, 'message': 'created', 'change_set': [self._build_change_set(enterprise.id, None, snapshot, 'create', sorted(snapshot.keys()))]}

        enterprise = self._get_enterprise_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            enterprise.status = -1
            enterprise.update_time = timezone.now().timestamp()
            enterprise.save(update_fields=['status', 'update_time'])
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        for field, value in self._normalize_payload(action.changes or {}, partial=True).items():
            setattr(enterprise, field, value)
        enterprise.update_time = timezone.now().timestamp()
        enterprise.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, user):
        return {
            'allowed': bool(getattr(user, 'is_authenticated', False)),
            'message': '未登录，无法操作企业信息',
        }

    def _normalize_payload(self, changes, partial=False):
        payload = {field: value for field, value in (changes or {}).items()}
        if not partial:
            payload.setdefault('city', '')
            payload.setdefault('bank', '')
            payload.setdefault('bank_sn', '')
            payload.setdefault('tax_num', '')
            payload.setdefault('phone', '')
            payload.setdefault('address', '')
            payload.setdefault('remark', '')
            payload.setdefault('status', 1)
            payload.setdefault('create_time', timezone.now().timestamp())
            payload.setdefault('update_time', payload['create_time'])
        return payload

    def _get_enterprise_for_action(self, enterprise_id, user):
        from apps.enterprise.models import Enterprise

        return Enterprise.objects.get(id=enterprise_id)

    def _snapshot_enterprise(self, enterprise):
        return {
            'title': getattr(enterprise, 'title', ''),
            'city': getattr(enterprise, 'city', ''),
            'bank': getattr(enterprise, 'bank', ''),
            'bank_sn': getattr(enterprise, 'bank_sn', ''),
            'tax_num': getattr(enterprise, 'tax_num', ''),
            'phone': getattr(enterprise, 'phone', ''),
            'address': getattr(enterprise, 'address', ''),
            'remark': getattr(enterprise, 'remark', ''),
            'status': getattr(enterprise, 'status', 1),
            'create_time': getattr(enterprise, 'create_time', 0),
            'update_time': getattr(enterprise, 'update_time', 0),
        }

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'enterprise',
            'model_name': 'Enterprise',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or before_snapshot or {}).keys()),
        }
