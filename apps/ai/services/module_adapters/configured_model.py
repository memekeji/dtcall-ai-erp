from __future__ import annotations

import json
import secrets
from datetime import date, datetime, time
from decimal import Decimal

from django.apps import apps
from django.db import models
from django.utils import timezone

from apps.ai.services.module_adapters.base import AIBaseModuleAdapter
from apps.ai.services.permission_guard import AIPermissionGuard


def _user_id(user):
    return getattr(user, 'id', None)


def _user_name(user):
    return getattr(user, 'name', None) or getattr(user, 'username', '') or ''


def _generated_code(prefix):
    def factory(_user):
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        return f'{prefix}-{timestamp}-{secrets.token_hex(2).upper()}'

    return factory


class ConfiguredModelModuleAdapter(AIBaseModuleAdapter):
    permission_guard = AIPermissionGuard()

    CONFIG = {
        'ai_knowledge_base': {
            'app_label': 'ai', 'model_name': 'AIKnowledgeBase',
            'required': {'name'},
            'allowed': {'name', 'description', 'status'},
            'create_defaults': {'creator_id': _user_id},
            'scope_field': 'creator_id',
            'aliases': {'name': ('knowledge_base_name', 'title')},
        },
        'ai_model_config': {
            'app_label': 'ai', 'model_name': 'AIModelConfig',
            'required': {'api_base'},
            'allowed': {'name', 'api_base', 'api_key', 'model_names', 'is_default', 'is_active'},
        },
        'ai_workflow': {
            'app_label': 'ai', 'model_name': 'AIWorkflow',
            'required': {'name'},
            'allowed': {'name', 'description', 'status', 'is_public'},
            'create_defaults': {'owner_id': _user_id, 'created_by_id': _user_id},
            'scope_field': 'owner_id',
            'aliases': {'name': ('workflow_name', 'title')},
        },
        'approval_step': {
            'app_label': 'approval', 'model_name': 'ApprovalStep',
            'required': {'flow_id', 'step_name', 'step_order'},
            'allowed': {
                'flow_id', 'step_name', 'step_order', 'step_type', 'action_type',
                'approver_id', 'approver_role', 'approver_department', 'approver_level',
                'cc_users', 'notification_users', 'cc_roles', 'cc_departments',
                'condition_field', 'condition_operator', 'condition_value',
                'time_limit_hours', 'auto_approve_on_timeout', 'approval_mode',
                'timeout_action', 'config_json', 'description', 'is_required',
                'is_parallel', 'allow_delegate', 'allow_skip', 'require_comment',
                'comment_hint', 'node_x', 'node_y',
            },
            'aliases': {
                'flow_id': ('approval_flow_id',),
                'step_name': ('name', 'title'),
                'step_order': ('order', 'sequence'),
            },
        },
        'approval_type': {
            'app_label': 'approval', 'model_name': 'ApprovalType',
            'required': {'name', 'code'},
            'allowed': {'name', 'code', 'description', 'icon', 'sort_order', 'is_active'},
            'aliases': {'name': ('type_name', 'title'), 'code': ('type_code',)},
        },
        'bom': {
            'app_label': 'production', 'model_name': 'BOM',
            'required': {'name', 'code'},
            'allowed': {'name', 'code', 'product_id', 'version', 'description', 'status'},
            'create_defaults': {'creator_id': _user_id},
            'aliases': {'name': ('bom_name', 'title'), 'code': ('bom_code',)},
        },
        'procedureset': {
            'app_label': 'production', 'model_name': 'ProcedureSet',
            'required': {'name', 'code'},
            'allowed': {'name', 'code', 'description', 'total_time', 'total_cost', 'status'},
            'create_defaults': {'creator_id': _user_id},
            'aliases': {'name': ('procedure_set_name', 'set_name', 'title'), 'code': ('procedure_set_code', 'set_code')},
        },
        'process': {
            'app_label': 'production', 'model_name': 'ProcessRoute',
            'required': {'name', 'code'},
            'allowed': {
                'name', 'code', 'description', 'product_id', 'total_time', 'total_cost',
                'status', 'version', 'effective_date', 'expiry_date',
            },
            'create_defaults': {'creator_id': _user_id},
            'aliases': {'name': ('process_name', 'route_name', 'title'), 'code': ('process_code', 'route_code')},
        },
        'quality_check': {
            'app_label': 'production', 'model_name': 'QualityCheck',
            'required': {'task_id', 'check_quantity', 'qualified_quantity', 'defective_quantity'},
            'allowed': {
                'task_id', 'check_time', 'check_quantity', 'qualified_quantity',
                'defective_quantity', 'result', 'defect_description',
                'improvement_suggestion',
            },
            'create_defaults': {'created_by_id': _user_id},
            'aliases': {
                'task_id': ('production_task_id',),
                'check_quantity': ('quantity', 'checked_quantity'),
                'qualified_quantity': ('qualified',),
                'defective_quantity': ('defective', 'unqualified_quantity'),
            },
        },
        'employee_care': {
            'app_label': 'user', 'model_name': 'EmployeeCare',
            'required': {'employee_id', 'care_type', 'title', 'content', 'care_date'},
            'allowed': {
                'employee_id', 'care_type', 'title', 'content', 'care_date',
                'amount', 'remarks',
            },
            'create_defaults': {'executor_id': _user_id},
            'aliases': {
                'employee_id': ('user_id', 'staff_id'),
                'care_type': ('type',),
                'care_date': ('date',),
            },
        },
        'reward_punishment': {
            'app_label': 'user', 'model_name': 'RewardPunishment',
            'required': {'employee_id', 'type', 'level', 'title', 'reason', 'effective_date'},
            'allowed': {
                'employee_id', 'type', 'level', 'title', 'reason', 'amount',
                'effective_date', 'remarks',
            },
            'create_defaults': {'executor_id': _user_id},
            'aliases': {
                'employee_id': ('user_id', 'staff_id'),
                'effective_date': ('date',),
            },
        },
        'finance_account': {
            'app_label': 'finance', 'model_name': 'FinanceAccount',
            'required': {'name'},
            'allowed': {
                'name', 'account_type', 'bank_name', 'account_no', 'currency',
                'opening_balance', 'current_balance', 'status', 'remark',
            },
            'aliases': {
                'name': ('account_name', 'title'),
                'opening_balance': ('initial_balance',),
                'current_balance': ('balance',),
                'account_no': ('account_number', 'bank_account'),
            },
        },
        'finance_bank_transaction': {
            'app_label': 'finance', 'model_name': 'BankTransaction',
            'required': {'account_id', 'transaction_date', 'direction', 'amount'},
            'allowed': {
                'account_id', 'transaction_date', 'direction', 'amount', 'counterparty',
                'transaction_no', 'purpose', 'match_status', 'related_type',
                'related_id', 'remark',
            },
            'aliases': {
                'account_id': ('finance_account_id',),
                'transaction_date': ('date', 'time'),
                'direction': ('transaction_type', 'type'),
            },
        },
        'finance_budget': {
            'app_label': 'finance', 'model_name': 'FinanceBudget',
            'required': {'name', 'start_date', 'end_date', 'budget_amount'},
            'allowed': {
                'name', 'department_id', 'project_id', 'period_type', 'start_date',
                'end_date', 'budget_amount', 'used_amount', 'warning_rate', 'status',
                'remark',
            },
            'aliases': {
                'name': ('budget_name', 'title'),
                'budget_amount': ('amount', 'total_amount'),
                'start_date': ('period_start',),
                'end_date': ('period_end',),
            },
        },
        'finance_receivable': {
            'app_label': 'finance', 'model_name': 'AccountsReceivable',
            'required': {'amount'},
            'allowed': {
                'code', 'customer_id', 'order_id', 'invoice_id', 'amount',
                'received_amount', 'due_date', 'status', 'remark',
            },
            'create_defaults': {'code': _generated_code('AR')},
            'aliases': {'amount': ('receivable_amount', 'total_amount')},
        },
        'finance_payable': {
            'app_label': 'finance', 'model_name': 'AccountsPayable',
            'required': {'amount'},
            'allowed': {
                'code', 'supplier_id', 'expense_id', 'amount', 'paid_amount',
                'due_date', 'status', 'remark',
            },
            'create_defaults': {'code': _generated_code('AP')},
            'aliases': {'amount': ('payable_amount', 'total_amount')},
        },
        'meeting_minutes': {
            'app_label': 'personal', 'model_name': 'MeetingMinutes',
            'required': {'title', 'meeting_date'},
            'allowed': {
                'title', 'meeting_type', 'meeting_date', 'location', 'host',
                'attendees', 'content', 'decisions', 'action_items', 'attachments',
                'is_public', 'meeting_record_id',
            },
            'create_defaults': {
                'host': _user_name, 'recorder_id': _user_id, 'user_id': _user_id,
            },
            'scope_field': 'user_id',
            'aliases': {
                'title': ('meeting_title', 'name'),
                'meeting_date': ('date', 'meeting_time', 'time'),
                'content': ('summary', 'description'),
                'host': ('host_name',),
            },
        },
        'supply_chain_forecast': {
            'app_label': 'supply_chain', 'model_name': 'DemandForecastPlan',
            'required': {'name', 'period_start', 'period_end'},
            'allowed': {
                'source_type', 'source_id', 'source_code', 'source_snapshot', 'name',
                'code', 'product_id', 'period_start', 'period_end', 'version',
                'status', 'summary',
            },
            'create_defaults': {'code': _generated_code('FC'), 'created_by_id': _user_id},
            'aliases': {
                'name': ('plan_name', 'forecast_name', 'title'),
                'period_start': ('start_date',),
                'period_end': ('end_date',),
            },
        },
        'supply_chain_outsource': {
            'app_label': 'supply_chain', 'model_name': 'OutsourceIssueOrder',
            'required': set(),
            'allowed': {
                'source_type', 'source_id', 'source_code', 'source_snapshot', 'code',
                'product_id', 'supplier_id', 'production_plan_id', 'quantity', 'status',
            },
            'create_defaults': {'code': _generated_code('OS'), 'created_by_id': _user_id},
            'aliases': {'quantity': ('issue_quantity', 'amount')},
        },
        'supply_chain_pr_review': {
            'app_label': 'supply_chain', 'model_name': 'PRReviewTask',
            'required': {'title'},
            'allowed': {
                'source_id', 'source_snapshot', 'code', 'title', 'source_type',
                'source_code', 'is_abnormal', 'recommended_action', 'evidence',
                'status', 'reviewer_id',
            },
            'create_defaults': {'code': _generated_code('PR'), 'created_by_id': _user_id},
            'aliases': {'title': ('name', 'review_title')},
        },
        'supply_chain_price_review': {
            'app_label': 'supply_chain', 'model_name': 'PriceReviewOrder',
            'required': set(),
            'allowed': {
                'source_type', 'source_id', 'source_code', 'source_snapshot', 'code',
                'purchase_order_id', 'inventory_item_id', 'supplier_id', 'quoted_price',
                'status', 'ai_summary',
            },
            'create_defaults': {'code': _generated_code('PX'), 'created_by_id': _user_id},
            'aliases': {'quoted_price': ('price', 'amount')},
        },
        'supply_chain_sample': {
            'app_label': 'supply_chain', 'model_name': 'SampleRequest',
            'required': {'material_name', 'required_date'},
            'allowed': {
                'source_type', 'source_id', 'source_code', 'source_snapshot', 'code',
                'material_name', 'specification', 'supplier_id', 'engineer_id',
                'required_date', 'quantity', 'status', 'remark',
            },
            'create_defaults': {'code': _generated_code('SA'), 'requested_by_id': _user_id},
            'aliases': {
                'material_name': ('name', 'item_name'),
                'required_date': ('date', 'due_date', 'require_date'),
                'quantity': ('sample_quantity',),
            },
        },
    }

    def __init__(self, resource):
        if resource not in self.CONFIG:
            raise KeyError(f'Unknown configured resource: {resource}')
        self.resource = resource

    @property
    def allowed_fields(self):
        return set(self.CONFIG[self.resource]['allowed'])

    @property
    def required_create_fields(self):
        return set(self.CONFIG[self.resource]['required'])

    def validate(self, action):
        supported = set(self._permission_mapping())
        if action.operation not in supported:
            return {'success': False, 'message': f'暂不支持 {self.resource} 操作: {action.operation}'}
        if action.operation == 'create':
            defaults = self.CONFIG[self.resource].get('create_defaults') or {}
            missing = [
                field for field in sorted(self.required_create_fields)
                if action.changes.get(field) in (None, '') and field not in defaults
            ]
            if missing:
                return {'success': False, 'message': f'{self.resource} 创建缺少必填字段: {", ".join(missing)}'}
        elif not action.object_ids:
            return {'success': False, 'message': f'{self.resource} 操作缺少目标记录'}
        if action.operation != 'delete':
            invalid = sorted(set(action.changes or {}) - self.allowed_fields)
            if invalid:
                return {'success': False, 'message': f'{self.resource} 包含不允许的字段: {", ".join(invalid)}'}
        return {'success': True}

    def normalize_create_changes(self, entities, changes, user=None, query=''):
        normalized = self._normalize_aliases(entities, changes)
        for key, value in (self.CONFIG[self.resource].get('create_defaults') or {}).items():
            if key not in self.allowed_fields or normalized.get(key) not in (None, ''):
                continue
            normalized[key] = value(user) if callable(value) else value
        return normalized

    def normalize_update_changes(self, entities, changes, user=None, query=''):
        return self._normalize_aliases(entities, changes)

    def _normalize_aliases(self, entities, changes):
        normalized = dict(changes or {})
        for target, aliases in (self.CONFIG[self.resource].get('aliases') or {}).items():
            if normalized.get(target) in (None, ''):
                for alias in aliases:
                    value = normalized.get(alias)
                    if value in (None, ''):
                        value = (entities or {}).get(alias)
                    if value not in (None, ''):
                        normalized[target] = value
                        break
            for alias in aliases:
                normalized.pop(alias, None)
        return normalized

    def preview(self, action, user):
        validation = self.validate(action)
        if not validation.get('success'):
            return validation
        permission = self._check_permission(action, user)
        if not permission['allowed']:
            return {'success': False, 'message': permission['message']}

        if action.operation == 'create':
            normalized = self._normalize_payload(action.changes or {}, user, partial=False)
            if not normalized['success']:
                return normalized
            return {
                'success': True,
                'change_set': [self._build_change_set('NEW', None, normalized['payload'], 'create')],
            }

        instance = self._get_instance(action.object_ids[0], user)
        before = self._snapshot_instance(instance)
        if action.operation == 'delete':
            return {
                'success': True,
                'change_set': [self._build_change_set(instance.pk, before, None, 'delete')],
            }

        normalized = self._normalize_payload(action.changes or {}, user, partial=True)
        if not normalized['success']:
            return normalized
        after = dict(before)
        after.update(self._snapshot_dict(normalized['payload']))
        return {
            'success': True,
            'change_set': [self._build_change_set(instance.pk, before, after, 'update')],
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
            return {
                'success': True,
                'message': 'created',
                'change_set': [self._build_change_set(instance.pk, None, snapshot, 'create')],
            }

        instance = self._get_instance(action.object_ids[0], user)
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

    def _permission_mapping(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        handoff = EnhancedIntentService.BUSINESS_HANDOFF_CONFIG.get(self.resource) or {}
        configured = handoff.get('permission') or {}
        mapping = {}
        for operation in ('create', 'update', 'delete'):
            selected = configured.get(operation)
            if isinstance(selected, dict) and selected.get('full_code'):
                mapping[operation] = selected['full_code']
            elif isinstance(selected, str):
                mapping[operation] = selected
        return mapping

    def _check_permission(self, action, user):
        permission_code = self._permission_mapping().get(action.operation)
        if not permission_code:
            return {'allowed': False, 'message': '该资源未配置可执行权限'}
        queryset = None
        if action.operation != 'create' and action.object_ids:
            queryset = self._scoped_queryset(user).filter(pk=action.object_ids[0])
        checked = self.permission_guard.check_action_permission(
            user,
            action,
            permission_code,
            queryset=queryset,
            exact_permission=True,
        )
        messages = {
            'unauthenticated': '未登录，无法执行操作',
            'missing_permission': '当前用户没有该操作权限',
            'out_of_scope': '目标记录不在当前用户数据范围内',
        }
        return {'allowed': checked.allowed, 'message': messages.get(checked.reason, checked.reason)}

    def _scoped_queryset(self, user):
        queryset = self._get_model().objects.all()
        scope_field = self.CONFIG[self.resource].get('scope_field')
        if scope_field and not getattr(user, 'is_superuser', False):
            queryset = queryset.filter(**{scope_field: getattr(user, 'id', None)})
        return queryset

    def _get_instance(self, object_id, user):
        return self._scoped_queryset(user).get(pk=object_id)

    def _get_model(self):
        config = self.CONFIG[self.resource]
        return apps.get_model(config['app_label'], config['model_name'])

    def _normalize_payload(self, changes, user, partial):
        payload = {}
        try:
            for key, value in (changes or {}).items():
                payload[key] = self._convert_field_value(key, value)
            if not partial:
                for key, value in (self.CONFIG[self.resource].get('create_defaults') or {}).items():
                    if key not in payload or payload[key] in (None, ''):
                        payload[key] = value(user) if callable(value) else value
                for field in self.required_create_fields:
                    if payload.get(field) in (None, ''):
                        return {'success': False, 'message': f'{self.resource} 创建缺少必填字段: {field}'}
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return {'success': False, 'message': f'{self.resource} 字段格式无效: {exc}'}
        return {'success': True, 'payload': payload}

    def _convert_field_value(self, key, value):
        model = self._get_model()
        try:
            field = model._meta.get_field(key)
        except Exception:
            field_name = key[:-3] if key.endswith('_id') else key
            field = model._meta.get_field(field_name)

        if value == '' and getattr(field, 'null', False):
            return None
        if isinstance(field, models.JSONField) and isinstance(value, str):
            return json.loads(value)
        if isinstance(field, models.BooleanField):
            return str(value).strip().lower() in {'1', 'true', 'yes', 'on', '是', '启用'}
        if isinstance(field, models.DateTimeField) and isinstance(value, str):
            from apps.ai.services.confirmation_service import confirmation_service

            parsed = confirmation_service._parse_natural_datetime(value)
            return parsed or field.to_python(value)
        if isinstance(field, models.DateField) and not isinstance(field, models.DateTimeField) and isinstance(value, str):
            from apps.ai.services.confirmation_service import confirmation_service

            parsed = confirmation_service._parse_natural_datetime(value)
            return parsed.date() if parsed else field.to_python(value)
        return field.to_python(value)

    def _snapshot_instance(self, instance):
        payload = {}
        for field in instance._meta.concrete_fields:
            payload[field.attname] = self._json_value(getattr(instance, field.attname))
        return payload

    def _snapshot_dict(self, payload):
        return {key: self._json_value(value) for key, value in payload.items()}

    def _json_value(self, value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (date, datetime, time)):
            return value.isoformat()
        if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
            return value
        return str(value)

    def _build_change_set(self, object_pk, before, after, change_type):
        config = self.CONFIG[self.resource]
        if change_type == 'create':
            changed_fields = sorted((after or {}).keys())
        elif change_type == 'delete':
            changed_fields = sorted((before or {}).keys())
        else:
            changed_fields = sorted(set((before or {})) | set((after or {})))
        return {
            'app_label': config['app_label'],
            'model_name': config['model_name'],
            'object_pk': str(object_pk),
            'change_type': change_type,
            'before_snapshot': before,
            'after_snapshot': after,
            'changed_fields': changed_fields,
        }
