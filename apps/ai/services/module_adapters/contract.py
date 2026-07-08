from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


class ContractModuleAdapter(AIBaseModuleAdapter):
    resource = 'contract'
    permission_guard = AIPermissionGuard()

    required_create_fields = {'code', 'name', 'customer', 'cost', 'sign_time', 'start_time', 'end_time'}
    allowed_update_fields = {
        'code',
        'name',
        'cate_id',
        'types',
        'subject_id',
        'customer_id',
        'customer',
        'contact_name',
        'contact_mobile',
        'contact_address',
        'start_time',
        'end_time',
        'prepared_uid',
        'sign_uid',
        'keeper_uid',
        'share_ids',
        'file_ids',
        'sign_time',
        'did',
        'cost',
        'content',
        'is_tax',
        'tax',
        'remark',
        'check_status',
        'check_flow_id',
        'check_step_sort',
        'check_uids',
        'check_last_uid',
        'check_history_uids',
        'check_copy_uids',
        'check_time',
    }

    def validate(self, action):
        if action.operation not in {'create', 'update', 'delete', 'approve'}:
            return {'success': False, 'message': f'暂不支持合同操作: {action.operation}'}

        if action.operation == 'create':
            missing_fields = [
                field for field in sorted(self.required_create_fields)
                if action.changes.get(field) in (None, '')
            ]
            if missing_fields:
                return {
                    'success': False,
                    'message': f'合同创建缺少必填字段: {", ".join(missing_fields)}',
                }
            return {'success': True}

        if action.operation in {'update', 'delete', 'approve'} and not action.object_ids:
            return {'success': False, 'message': '合同操作缺少目标记录'}

        if action.operation == 'delete':
            return {'success': True}

        if action.operation == 'approve':
            return {'success': True}

        invalid_fields = sorted(set(action.changes.keys()) - self.allowed_update_fields)
        if invalid_fields:
            return {
                'success': False,
                'message': f'合同更新包含不允许的字段: {", ".join(invalid_fields)}',
            }
        return {'success': True}

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation

        permission_check = self._check_permission(action, user)
        if not permission_check['allowed']:
            return {'success': False, 'message': permission_check['message']}

        if action.operation == 'create':
            normalized_payload = self._normalize_contract_payload(action.changes, user, require_all=True)
            if not normalized_payload['success']:
                return normalized_payload
            after_snapshot = self._serialize_snapshot(normalized_payload['payload'])
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'contract',
                        'model_name': 'Contract',
                        'object_pk': 'NEW',
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': after_snapshot,
                        'changed_fields': sorted(after_snapshot.keys()),
                    }
                ],
            }

        contract = self._get_contract_for_action(action.object_ids[0], user)
        before_snapshot = self._snapshot_contract(contract)

        if action.operation == 'delete':
            after_snapshot = dict(before_snapshot)
            after_snapshot['delete_time'] = 'NOW'
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'contract',
                        'model_name': 'Contract',
                        'object_pk': str(getattr(contract, 'id', action.object_ids[0])),
                        'change_type': 'delete',
                        'before_snapshot': before_snapshot,
                        'after_snapshot': after_snapshot,
                        'changed_fields': ['delete_time'],
                    }
                ],
            }

        if action.operation == 'approve':
            after_snapshot = dict(before_snapshot)
            history = str(before_snapshot.get('check_history_uids') or '').strip(',')
            uid = str(getattr(user, 'id', 0) or 0)
            after_snapshot.update({
                'check_status': action.changes.get('check_status', 2),
                'check_time': 'NOW',
                'check_history_uids': f'{history},{uid}'.strip(','),
            })
            return {
                'success': True,
                'change_set': [
                    {
                        'app_label': 'contract',
                        'model_name': 'Contract',
                        'object_pk': str(getattr(contract, 'id', action.object_ids[0])),
                        'change_type': 'update',
                        'before_snapshot': before_snapshot,
                        'after_snapshot': after_snapshot,
                        'changed_fields': ['check_status', 'check_time', 'check_history_uids'],
                    }
                ],
            }

        normalized_payload = self._normalize_contract_payload(action.changes, user, require_all=False)
        if not normalized_payload['success']:
            return normalized_payload
        after_snapshot = dict(before_snapshot)
        after_snapshot.update(self._serialize_snapshot(normalized_payload['payload']))
        return {
            'success': True,
            'change_set': [
                {
                    'app_label': 'contract',
                    'model_name': 'Contract',
                    'object_pk': str(getattr(contract, 'id', action.object_ids[0])),
                    'change_type': 'update',
                    'before_snapshot': before_snapshot,
                    'after_snapshot': after_snapshot,
                    'changed_fields': sorted(normalized_payload['payload'].keys()),
                }
            ],
        }

    def execute(self, action, user, operation=None):
        preview = self.preview(action, user)
        if not preview.get('success'):
            return preview

        if action.operation == 'create':
            normalized_payload = self._normalize_contract_payload(action.changes, user, require_all=True)
            payload = normalized_payload['payload']
            from apps.contract.models import Contract

            with transaction.atomic():
                self._assert_contract_code_unique(payload['code'])
                contract = Contract.objects.create(**payload)

            snapshot = self._snapshot_contract(contract)
            return {
                'success': True,
                'message': 'created',
                'change_set': [
                    {
                        'app_label': 'contract',
                        'model_name': 'Contract',
                        'object_pk': str(contract.id),
                        'change_type': 'create',
                        'before_snapshot': None,
                        'after_snapshot': snapshot,
                        'changed_fields': sorted(snapshot.keys()),
                    }
                ],
            }

        contract = self._get_contract_for_action(action.object_ids[0], user)
        if action.operation == 'delete':
            contract.delete_time = int(timezone.now().timestamp())
            contract.save(update_fields=['delete_time', 'update_time'])
            return {'success': True, 'message': 'deleted', 'change_set': preview['change_set']}

        if action.operation == 'approve':
            contract.check_status = action.changes.get('check_status', 2)
            contract.check_time = int(timezone.now().timestamp())
            history = str(getattr(contract, 'check_history_uids', '') or '').strip(',')
            uid = str(getattr(user, 'id', 0) or 0)
            contract.check_history_uids = f'{history},{uid}'.strip(',')
            contract.save(update_fields=['check_status', 'check_time', 'check_history_uids', 'update_time'])
            return {'success': True, 'message': 'approved', 'change_set': preview['change_set']}

        normalized_payload = self._normalize_contract_payload(action.changes, user, require_all=False)
        if not normalized_payload['success']:
            return normalized_payload
        payload = normalized_payload['payload']
        if 'code' in payload and payload['code'] != getattr(contract, 'code', ''):
            self._assert_contract_code_unique(payload['code'], exclude_id=getattr(contract, 'id', None))
        for field, value in payload.items():
            setattr(contract, field, value)
        update_fields = sorted(set(payload.keys()) | {'update_time'})
        contract.save(update_fields=update_fields)
        return {'success': True, 'message': 'updated', 'change_set': preview['change_set']}

    def _check_permission(self, action, user):
        permission_map = {
            'create': 'contract.add_contract',
            'update': 'contract.change_contract',
            'delete': 'contract.delete_contract',
            'approve': 'contract.approve_contract',
        }
        permission_code = permission_map.get(action.operation)
        if not permission_code:
            return {'allowed': False, 'message': '未配置合同操作权限'}
        result = self.permission_guard.check_action_permission(user, action, permission_code)
        return {'allowed': result.allowed, 'message': '权限不足，无法操作合同' if not result.allowed else 'allowed'}

    def _normalize_contract_payload(self, changes, user, require_all):
        payload = {}
        try:
            for field, value in (changes or {}).items():
                if field in {'pid', 'cate_id', 'types', 'customer_id', 'prepared_uid', 'sign_uid', 'keeper_uid', 'did', 'is_tax', 'check_status', 'check_flow_id', 'check_step_sort', 'check_time'}:
                    payload[field] = int(value) if value not in (None, '') else 0
                elif field in {'cost', 'tax'}:
                    payload[field] = Decimal(str(value))
                elif field in {'sign_time', 'start_time', 'end_time'}:
                    payload[field] = self._parse_timestamp(value)
                else:
                    payload[field] = value
        except (TypeError, ValueError, InvalidOperation):
            return {'success': False, 'message': '合同字段格式无效，请检查日期、金额和编号'}

        if require_all:
            missing_fields = [field for field in sorted(self.required_create_fields) if payload.get(field) in (None, '', 0)]
            if missing_fields:
                return {'success': False, 'message': f'合同创建缺少必填字段: {", ".join(missing_fields)}'}

        if payload.get('is_tax') != 1 and 'tax' not in payload:
            payload['tax'] = Decimal('0')
        elif payload.get('is_tax') != 1:
            payload['tax'] = Decimal('0')

        if 'end_time' in payload and 'start_time' in payload and payload['end_time'] <= payload['start_time']:
            return {'success': False, 'message': '合同结束时间必须大于开始时间'}

        if getattr(user, 'is_authenticated', False):
            payload.setdefault('admin_id', getattr(user, 'id', 0) or 0)
            payload.setdefault('prepared_uid', getattr(user, 'id', 0) or 0)
            payload.setdefault('sign_uid', getattr(user, 'id', 0) or 0)
            payload.setdefault('keeper_uid', getattr(user, 'id', 0) or 0)
            payload.setdefault('did', getattr(user, 'did', 0) or getattr(user, 'auth_did', 0) or 0)

        return {'success': True, 'payload': payload}

    def _snapshot_contract(self, contract):
        return self._serialize_snapshot({
            'id': getattr(contract, 'id', None),
            'code': getattr(contract, 'code', ''),
            'name': getattr(contract, 'name', ''),
            'cate_id': getattr(contract, 'cate_id', 0),
            'types': getattr(contract, 'types', 0),
            'subject_id': getattr(contract, 'subject_id', ''),
            'customer_id': getattr(contract, 'customer_id', 0),
            'customer': getattr(contract, 'customer', ''),
            'contact_name': getattr(contract, 'contact_name', ''),
            'contact_mobile': getattr(contract, 'contact_mobile', ''),
            'contact_address': getattr(contract, 'contact_address', ''),
            'start_time': getattr(contract, 'start_time', 0),
            'end_time': getattr(contract, 'end_time', 0),
            'prepared_uid': getattr(contract, 'prepared_uid', 0),
            'sign_uid': getattr(contract, 'sign_uid', 0),
            'keeper_uid': getattr(contract, 'keeper_uid', 0),
            'share_ids': getattr(contract, 'share_ids', ''),
            'file_ids': getattr(contract, 'file_ids', ''),
            'sign_time': getattr(contract, 'sign_time', 0),
            'did': getattr(contract, 'did', 0),
            'cost': getattr(contract, 'cost', Decimal('0')),
            'content': getattr(contract, 'content', ''),
            'is_tax': getattr(contract, 'is_tax', 0),
            'tax': getattr(contract, 'tax', Decimal('0')),
            'remark': getattr(contract, 'remark', ''),
            'check_status': getattr(contract, 'check_status', 0),
            'check_flow_id': getattr(contract, 'check_flow_id', 0),
            'check_step_sort': getattr(contract, 'check_step_sort', 0),
            'check_uids': getattr(contract, 'check_uids', ''),
            'check_last_uid': getattr(contract, 'check_last_uid', ''),
            'check_history_uids': getattr(contract, 'check_history_uids', ''),
            'check_copy_uids': getattr(contract, 'check_copy_uids', ''),
            'check_time': getattr(contract, 'check_time', 0),
            'delete_time': getattr(contract, 'delete_time', 0),
            'admin_id': getattr(contract, 'admin_id', 0),
        })

    def _serialize_snapshot(self, values):
        snapshot = {}
        for field, value in (values or {}).items():
            if isinstance(value, Decimal):
                snapshot[field] = format(value, 'f')
            elif isinstance(value, datetime):
                snapshot[field] = int(value.timestamp())
            elif isinstance(value, date):
                snapshot[field] = int(datetime.combine(value, datetime.min.time()).timestamp())
            else:
                snapshot[field] = value
        return snapshot

    def _parse_timestamp(self, value):
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, datetime):
            return int(value.timestamp())
        if isinstance(value, date):
            return int(datetime.combine(value, datetime.min.time()).timestamp())
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit():
                return int(stripped)
            return int(datetime.fromisoformat(stripped).timestamp())
        raise ValueError('invalid timestamp')

    def _get_contract_for_action(self, contract_id, user):
        from apps.contract.models import Contract

        return self._scoped_contract_queryset(user).get(id=contract_id)

    def _scoped_contract_queryset(self, user):
        from apps.contract.models import Contract

        queryset = Contract.objects.filter(delete_time=0)
        if getattr(user, 'is_superuser', False):
            return queryset
        visible_dids = self._visible_department_ids(user)
        if visible_dids:
            return queryset.filter(Q(admin_id=getattr(user, 'id', 0)) | Q(did__in=visible_dids)).distinct()
        return queryset.filter(admin_id=getattr(user, 'id', 0))

    def _visible_department_ids(self, user):
        ids = []
        for attr in ('auth_dids', 'son_dids'):
            raw_value = getattr(user, attr, '') or ''
            ids.extend([int(item) for item in raw_value.split(',') if str(item).strip().isdigit()])
        auth_did = getattr(user, 'auth_did', 0) or 0
        if auth_did:
            ids.append(int(auth_did))
        return sorted(set(ids))

    def _assert_contract_code_unique(self, code, exclude_id=None):
        from apps.contract.models import Contract

        queryset = Contract.objects.filter(code=code, delete_time=0)
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        if queryset.exists():
            raise ValueError('合同编号已存在')
