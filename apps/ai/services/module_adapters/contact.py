from __future__ import annotations

from django.db.models import Q

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard, build_csv_membership_q


class ContactModuleAdapter(AIBaseModuleAdapter):
    resource = 'contact'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'customer_id', 'contact_person', 'phone'}
    allowed_fields = {'customer_id', 'contact_person', 'phone', 'is_primary', 'position', 'email'}

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete'}:
            return {'success': False, 'message': f'暂不支持客户联系人操作: {action.operation}'}
        if action.operation == 'create':
            missing = [field for field in sorted(self.required_create_fields) if action.changes.get(field) in (None, '')]
            if missing:
                return {'success': False, 'message': f'客户联系人创建缺少必填字段: {", ".join(missing)}'}
        elif not action.object_ids:
            return {'success': False, 'message': '客户联系人操作缺少目标记录'}
        if action.operation != 'delete':
            invalid = sorted(set((action.changes or {}).keys()) - self.allowed_fields)
            if invalid:
                return {'success': False, 'message': f'客户联系人操作包含不允许的字段: {", ".join(invalid)}'}
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, partial=False)
            if not normalized['success']:
                return normalized
            customer = self._get_customer_for_action(normalized['payload']['customer_id'], user)
            change_set = []
            if normalized['payload'].get('is_primary'):
                change_set.extend(self._build_primary_reset_change_sets(customer_id=customer.id, exclude_contact_id=None, user=user))
            change_set.append(self._build_change_set('NEW', None, normalized['payload'], 'create'))
            return {'success': True, 'change_set': change_set}

        contact = self._get_contact_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_contact(contact)
        if action.operation == 'delete':
            return {
                'success': True,
                'change_set': [
                    self._build_change_set(
                        getattr(contact, 'id', action.object_ids[0]),
                        before_snapshot,
                        None,
                        'delete',
                        sorted(before_snapshot.keys()),
                    )
                ],
            }

        normalized = self._normalize_payload(action.changes or {}, partial=True)
        if not normalized['success']:
            return normalized

        after_snapshot = dict(before_snapshot)
        after_snapshot.update(normalized['payload'])
        target_customer_id = after_snapshot.get('customer_id') or before_snapshot.get('customer_id')
        will_be_primary = bool(after_snapshot.get('is_primary'))

        change_set = []
        if will_be_primary:
            change_set.extend(
                self._build_primary_reset_change_sets(
                    customer_id=target_customer_id,
                    exclude_contact_id=getattr(contact, 'id', action.object_ids[0]),
                    user=user,
                )
            )
        change_set.append(
            self._build_change_set(
                getattr(contact, 'id', action.object_ids[0]),
                before_snapshot,
                after_snapshot,
                'update',
                sorted(normalized['payload'].keys()),
            )
        )
        return {'success': True, 'change_set': change_set}

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        from apps.customer.models import Contact

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, partial=False)
            if not normalized['success']:
                return normalized
            payload = normalized['payload']
            customer = self._get_customer_for_action(payload['customer_id'], user)
            if payload.get('is_primary'):
                customer.contacts.filter(is_primary=True).update(is_primary=False)
            contact = Contact.objects.create(**payload)
            snapshot = self._snapshot_contact(contact)
            change_set = list(preview['change_set'][:-1])
            change_set.append(self._build_change_set(contact.id, None, snapshot, 'create', sorted(snapshot.keys())))
            return {'success': True, 'message': 'created', 'change_set': change_set}

        contact = self._get_contact_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            contact.delete()
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        normalized = self._normalize_payload(action.changes or {}, partial=True)
        if not normalized['success']:
            return normalized
        payload = normalized['payload']
        target_customer_id = payload.get('customer_id', getattr(contact, 'customer_id', None))
        will_be_primary = bool(payload.get('is_primary', getattr(contact, 'is_primary', False)))
        if will_be_primary and target_customer_id:
            self._get_customer_for_action(target_customer_id, user).contacts.exclude(id=contact.id).filter(is_primary=True).update(is_primary=False)
        for field, value in payload.items():
            setattr(contact, field, value)
        contact.save()
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'customer.add_customer',
            'update': 'customer.change_customer',
            'delete': 'customer.delete_customer',
        }
        result = self.permission_guard.check_action_permission(user, action, permission_map[action.operation])
        return {'allowed': result.allowed, 'message': '权限不足，无法操作客户联系人' if not result.allowed else 'allowed'}

    def _normalize_payload(self, changes, partial=False):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field == 'customer_id':
                    payload[field] = int(value)
                elif field == 'is_primary':
                    payload[field] = self._to_bool(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError):
            return {'success': False, 'message': '客户联系人字段格式无效，请检查客户、联系人姓名和手机号'}

        if not partial:
            payload.setdefault('position', '')
            payload.setdefault('email', None)
            payload.setdefault('is_primary', False)
        return {'success': True, 'payload': payload}

    def _build_primary_reset_change_sets(self, customer_id, exclude_contact_id, user):
        queryset = self._visible_contact_queryset(user).filter(customer_id=customer_id, is_primary=True)
        if exclude_contact_id:
            queryset = queryset.exclude(id=exclude_contact_id)
        change_sets = []
        for contact in queryset:
            before_snapshot = self._snapshot_contact(contact)
            after_snapshot = dict(before_snapshot)
            after_snapshot['is_primary'] = False
            change_sets.append(
                self._build_change_set(
                    getattr(contact, 'id', None),
                    before_snapshot,
                    after_snapshot,
                    'update',
                    ['is_primary'],
                )
            )
        return change_sets

    def _visible_customer_queryset(self, user):
        from apps.customer.models import Customer

        queryset = Customer.objects.filter(delete_time=0)
        if getattr(user, 'is_superuser', False):
            return queryset
        user_id = str(getattr(user, 'id', '') or '')
        return queryset.filter(
            Q(belong_uid=getattr(user, 'id', None)) |
            build_csv_membership_q('share_ids', user_id)
        ).distinct()

    def _visible_contact_queryset(self, user):
        from apps.customer.models import Contact

        queryset = Contact.objects.select_related('customer').filter(customer__delete_time=0)
        if getattr(user, 'is_superuser', False):
            return queryset
        user_id = str(getattr(user, 'id', '') or '')
        return queryset.filter(
            Q(customer__belong_uid=getattr(user, 'id', None)) |
            build_csv_membership_q('customer__share_ids', user_id)
        ).distinct()

    def _get_customer_for_action(self, customer_id, user):
        return self._visible_customer_queryset(user).get(id=customer_id)

    def _get_contact_for_action(self, contact_id, user):
        return self._visible_contact_queryset(user).get(id=contact_id)

    def _snapshot_contact(self, contact):
        return {
            'customer_id': getattr(contact, 'customer_id', None),
            'contact_person': getattr(contact, 'contact_person', ''),
            'phone': getattr(contact, 'phone', ''),
            'is_primary': getattr(contact, 'is_primary', False),
            'position': getattr(contact, 'position', ''),
            'email': getattr(contact, 'email', None),
        }

    def _build_change_set(self, object_pk, before_snapshot, after_snapshot, change_type, changed_fields=None):
        return {
            'app_label': 'customer',
            'model_name': 'Contact',
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot,
            'changed_fields': changed_fields or sorted((after_snapshot or before_snapshot or {}).keys()),
        }

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on', '是'}
