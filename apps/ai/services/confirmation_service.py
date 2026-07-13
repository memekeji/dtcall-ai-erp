from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from apps.ai.services.action_contracts import AIActionRequest
from apps.ai.services.permission_guard import build_csv_membership_q


class AIConfirmationService:
    RESOURCE_NORMALIZERS = {
        'disk_share': ('disk', {'model': 'share'}),
        'disk_folder': ('disk', {'model': 'folder'}),
        'finance_invoice': ('finance', {'model': 'invoice'}),
        'finance_expense': ('finance', {'model': 'expense'}),
        'finance_income': ('finance', {'model': 'income'}),
        'finance_order_record': ('finance', {'model': 'order_record'}),
        'expense': ('finance', {'model': 'expense'}),
        'income': ('finance', {'model': 'income'}),
        'invoice': ('finance', {'model': 'invoice'}),
        'payment': ('finance', {'model': 'payment'}),
    }

    APPROVAL_REQUEST_TYPE_KEYWORDS = {
        'leave': ('请假', '休假', '假期'),
        'leave_request': ('请假', '休假', '假期'),
        'vacation': ('请假', '休假', '假期'),
        'business_trip': ('出差', '差旅'),
        'trip': ('出差', '差旅'),
        'reimbursement': ('报销', '费用'),
        'expense': ('报销', '费用'),
        'purchase': ('采购',),
    }
    APPROVAL_REQUEST_TYPE_ALIASES = {
        '请假': 'leave_request',
        '请个假': 'leave_request',
        '休假': 'leave_request',
        '假期': 'leave_request',
        '年假': 'leave_request',
        '事假': 'leave_request',
        '病假': 'leave_request',
        '婚假': 'leave_request',
        'leave': 'leave_request',
        'leave_request': 'leave_request',
        'vacation': 'leave_request',
        '出差': 'business_trip',
        '差旅': 'business_trip',
        'business_trip': 'business_trip',
        'trip': 'business_trip',
        '报销': 'reimbursement',
        '费用': 'reimbursement',
        'reimbursement': 'reimbursement',
        'expense': 'reimbursement',
        '采购': 'purchase',
        'purchase': 'purchase',
    }
    ENTITY_CHANGE_BLACKLIST = {
        'changes',
        'context',
        'filters',
        'object_ids',
        'candidate_data_types',
        'permission_required',
        'permission_exists',
        'has_business_permission',
    }

    def build_action_request(self, intent_result: dict, user=None) -> AIActionRequest | None:
        action = intent_result.get('action')
        resource = intent_result.get('data_type')
        if not action or not resource:
            return None

        entities = dict(intent_result.get('entities') or {})
        normalized_resource, normalized_context = self._normalize_resource(
            resource,
            entities.get('context') or {},
        )
        object_ids = self._normalize_object_ids(entities, normalized_resource)
        changes = dict(entities.get('changes') or {})
        query = intent_result.get('original_query') or intent_result.get('query') or ''
        if action == 'create':
            changes, normalized_context = self._normalize_create_payload(
                normalized_resource,
                entities,
                changes,
                normalized_context,
                user=user,
                query=query,
            )
        elif action == 'update':
            changes = self._seed_changes_from_entities(entities, changes)
            changes = self._normalize_registered_update_changes(
                normalized_resource,
                entities,
                changes,
                user=user,
                query=query,
            )
            changes = self._filter_create_changes_for_resource(normalized_resource, changes)
        elif action == 'delete':
            changes = {}

        return AIActionRequest(
            resource=normalized_resource,
            operation=action,
            object_ids=object_ids,
            changes=changes,
            filters=entities.get('filters') or {},
            context=normalized_context,
        )

    def _normalize_resource(self, resource: str, context: dict) -> tuple[str, dict]:
        merged_context = dict(context or {})
        normalized = self.RESOURCE_NORMALIZERS.get(resource)
        if not normalized:
            return resource, merged_context

        normalized_resource, inferred_context = normalized
        for key, value in (inferred_context or {}).items():
            merged_context.setdefault(key, value)
        return normalized_resource, merged_context

    def build_confirmation_payload(self, intent_result: dict, user=None) -> dict:
        action_request = self.build_action_request(intent_result, user=user)
        if not action_request or not intent_result.get('requires_confirmation'):
            return {}

        return {
            'action_plan': {
                'resource': action_request.resource,
                'operation': action_request.operation,
                'object_ids': action_request.object_ids,
                'changes': action_request.changes,
                'filters': action_request.filters,
                'context': action_request.context,
            },
            'confirmation': {
                'required': True,
                'message': intent_result.get('message', '该操作需要确认后执行。'),
            },
        }

    def _normalize_create_payload(
            self,
            resource: str,
            entities: dict,
            changes: dict,
            context: dict,
            user=None,
            query: str = '') -> tuple[dict, dict]:
        normalized_changes = self._seed_changes_from_entities(entities, changes)
        normalized_context = dict(context or {})

        if resource == 'approval':
            normalized_changes, normalized_context = self._normalize_approval_create_payload(
                entities,
                normalized_changes,
                normalized_context,
                user=user,
                query=query,
            )
        elif resource == 'customer':
            normalized_changes, normalized_context = self._normalize_customer_create_payload(
                entities, normalized_changes, normalized_context, query=query)
        elif resource == 'personal_task':
            normalized_changes, normalized_context = self._normalize_personal_task_create_payload(
                entities, normalized_changes, normalized_context, query=query)
        elif resource == 'inventory':
            normalized_changes, normalized_context = self._normalize_inventory_create_payload(
                entities, normalized_changes, normalized_context)
        elif resource == 'order':
            normalized_changes, normalized_context = self._normalize_order_create_payload(
                entities, normalized_changes, normalized_context, user=user)
        elif resource == 'document':
            normalized_changes, normalized_context = self._normalize_document_create_payload(
                entities, normalized_changes, normalized_context, user=user, query=query)
        elif resource == 'meeting':
            normalized_changes, normalized_context = self._normalize_meeting_create_payload(
                entities, normalized_changes, normalized_context, user=user, query=query)
        elif resource in {'production', 'production_plan'}:
            normalized_changes, normalized_context = self._normalize_production_create_payload(
                entities, normalized_changes, normalized_context, user=user, query=query)

        normalized_changes = self._normalize_registered_create_changes(
            resource,
            entities,
            normalized_changes,
            user=user,
            query=query,
        )

        return self._filter_create_changes_for_resource(resource, normalized_changes), normalized_context

    def _normalize_approval_create_payload(
            self,
            entities: dict,
            changes: dict,
            context: dict,
            user=None,
            query: str = '') -> tuple[dict, dict]:
        normalized_changes = dict(changes or {})
        normalized_context = dict(context or {})

        request_type = self._normalize_approval_request_type(entities, query=query)
        reason = str(
            entities.get('reason') or
            entities.get('approval_reason') or
            entities.get('leave_reason') or
            entities.get('trip_reason') or
            entities.get('reimbursement_reason') or
            normalized_changes.get('reason') or
            normalized_changes.get('approval_reason') or
            self._extract_approval_reason(query, request_type) or
            ''
        ).strip()
        flow = self._resolve_approval_flow(user, request_type)
        if flow:
            normalized_changes.setdefault('flow_id', flow.id)
            if getattr(flow, 'approval_type_id', None):
                normalized_changes.setdefault('type_id', flow.approval_type_id)
            normalized_context.setdefault('resolved_flow_name', flow.name)

        if not normalized_changes.get('title'):
            normalized_changes['title'] = self._build_approval_title(request_type, reason, flow)
        if reason and not normalized_changes.get('content'):
            normalized_changes['content'] = self._build_approval_content(request_type, reason)

        if request_type:
            normalized_context.setdefault('approval_request_type', request_type)
        if reason:
            normalized_context.setdefault('approval_reason', reason)
        normalized_changes.pop('request_type', None)
        normalized_changes.pop('approval_type', None)
        normalized_changes.pop('type', None)
        normalized_changes.pop('reason', None)
        normalized_changes.pop('approval_reason', None)
        return normalized_changes, normalized_context

    def _normalize_customer_create_payload(
            self,
            entities: dict,
            changes: dict,
            context: dict,
            query: str = '') -> tuple[dict, dict]:
        normalized_changes = dict(changes or {})
        name = self._pick_value(
            normalized_changes,
            'name',
            fallback=self._pick_value(
                entities,
                'name',
                'customer_name',
                fallback=self._extract_named_value(
                    query,
                    [
                        r'(?:名字叫|名称叫|客户(?:名字|名称)?(?:叫|是|为))\s*([^\s，。；,;]+)',
                        r'新增(?:一个)?客户\s*([^\s，。；,;]+)',
                    ],
                ),
            ),
        )
        if name and not normalized_changes.get('name'):
            normalized_changes['name'] = name

        description = self._pick_value(entities, 'content', 'description', 'remark', 'notes')
        if description and not normalized_changes.get('content'):
            normalized_changes['content'] = description
        for alias in ('customer_name', 'description', 'notes'):
            normalized_changes.pop(alias, None)
        return normalized_changes, dict(context or {})

    def _normalize_personal_task_create_payload(
            self,
            entities: dict,
            changes: dict,
            context: dict,
            query: str = '') -> tuple[dict, dict]:
        normalized_changes = dict(changes or {})
        explicit_changes = dict(entities.get('changes') or {})
        due_source = self._pick_value(
            explicit_changes,
            'due_date',
            fallback=self._pick_value(entities, 'due_date', 'due_time', 'deadline', 'end_time', 'time'),
        )
        title = self._pick_value(
            explicit_changes,
            'title',
            fallback=self._pick_value(
                entities,
                'task_content',
                'task_description',
                'content',
                'title',
                'name',
                'description',
                fallback=self._extract_personal_task_title(query, due_source=due_source),
            ),
        )
        if title:
            normalized_changes['title'] = str(title).strip()

        description = self._pick_value(entities, 'task_description', 'description', 'remark')
        if description and description != normalized_changes.get('title') and not normalized_changes.get('description'):
            normalized_changes['description'] = description

        parsed_due = self._parse_natural_datetime(due_source or query)
        if parsed_due:
            normalized_changes['due_date'] = parsed_due.strftime('%Y-%m-%d %H:%M:%S')

        for alias in (
                'task_content', 'content', 'due_time', 'deadline', 'end_time', 'time',
                'customer_id', 'customer_name'):
            normalized_changes.pop(alias, None)
        return normalized_changes, dict(context or {})

    def _normalize_inventory_create_payload(
            self,
            entities: dict,
            changes: dict,
            context: dict) -> tuple[dict, dict]:
        normalized_changes = dict(changes or {})
        code = self._pick_value(normalized_changes, 'code', fallback=self._pick_value(entities, 'code', 'item_code', 'material_code', 'inventory_code'))
        if code and not normalized_changes.get('code'):
            normalized_changes['code'] = code
        normalized_changes.pop('item_code', None)
        normalized_changes.pop('material_code', None)
        normalized_changes.pop('inventory_code', None)

        name = self._pick_value(normalized_changes, 'name', fallback=self._pick_value(entities, 'name', 'item_name', 'material_name', 'title'))
        if not name and code:
            name = code
        if name and not normalized_changes.get('name'):
            normalized_changes['name'] = name

        unit = self._pick_value(normalized_changes, 'unit', fallback=self._pick_value(entities, 'unit', 'uom'))
        if not unit:
            unit = '个'
        normalized_changes.setdefault('unit', unit)
        return normalized_changes, dict(context or {})

    def _normalize_order_create_payload(
            self,
            entities: dict,
            changes: dict,
            context: dict,
            user=None) -> tuple[dict, dict]:
        normalized_changes = dict(changes or {})
        normalized_context = dict(context or {})

        customer_name = self._pick_value(entities, 'customer_name', 'customer')
        if customer_name and not normalized_context.get('customer_name'):
            normalized_context['customer_name'] = customer_name
        normalized_changes.pop('customer_name', None)
        normalized_changes.pop('customer', None)

        if not normalized_changes.get('customer_id') and customer_name:
            customer_id = self._resolve_customer_id_for_user(customer_name, user)
            if customer_id:
                normalized_changes['customer_id'] = customer_id
                normalized_context.setdefault('resolved_customer_id', customer_id)

        if entities.get('amount') not in (None, '') and not normalized_changes.get('amount'):
            normalized_changes['amount'] = entities.get('amount')
        normalized_changes.setdefault('order_number', self._generate_order_number())
        normalized_changes.setdefault(
            'product_name',
            self._pick_value(entities, 'product_name', 'product', 'title', fallback='AI创建订单'),
        )
        normalized_changes.setdefault('order_date', self._local_now().date().isoformat())

        description = self._pick_value(entities, 'description', 'content', 'remark')
        if description and not normalized_changes.get('description'):
            normalized_changes['description'] = description
        return normalized_changes, normalized_context

    def _normalize_document_create_payload(
            self,
            entities: dict,
            changes: dict,
            context: dict,
            user=None,
            query: str = '') -> tuple[dict, dict]:
        normalized_changes = dict(changes or {})

        title = self._pick_value(
            normalized_changes,
            'title',
            fallback=self._pick_value(
                entities,
                'title',
                'document_title',
                'name',
                fallback=self._extract_named_value(
                    query,
                    [
                        r'标题(?:是|为|叫)?\s*([^\n，。；]+)',
                        r'起草(?:一份|一个)?(?:公文|通知|通告)\s*[，,]?\s*([^\n，。；]+)',
                    ],
                ),
            ),
        )
        if not title:
            title = 'AI起草公文'
        normalized_changes.setdefault('title', title)
        normalized_changes.setdefault('document_number', self._generate_document_number())
        category_id = normalized_changes.get('category_id') or self._resolve_document_category_id(title, query=query)
        if category_id:
            normalized_changes.setdefault('category_id', category_id)
        if not normalized_changes.get('content'):
            normalized_changes['content'] = self._pick_value(
                entities,
                'content',
                'summary',
                'description',
                fallback=f'{title}\n\n请相关部门按要求落实执行。',
            )
        department_id = self._get_user_department_id(user)
        if department_id and not normalized_changes.get('department_id'):
            normalized_changes['department_id'] = department_id
        return normalized_changes, dict(context or {})

    def _normalize_meeting_create_payload(
            self,
            entities: dict,
            changes: dict,
            context: dict,
            user=None,
            query: str = '') -> tuple[dict, dict]:
        normalized_changes = dict(changes or {})
        title = self._pick_value(
            normalized_changes,
            'title',
            fallback=self._pick_value(
                entities,
                'title',
                'meeting_title',
                '主题',
                fallback=self._extract_named_value(
                    query,
                    [
                        r'(?:主题(?:是|为|叫)?)([^，。；]+)',
                        r'(?:安排|新增|创建)(?:一个|一场|一次)?([^，。；]*?(?:会议|例会))',
                        r'([^，。；]*?(?:会议|例会))',
                    ],
                ),
            ),
        )
        if title and not normalized_changes.get('title'):
            normalized_changes['title'] = str(title).strip()

        meeting_date_source = self._pick_value(entities, 'meeting_date', 'date')
        meeting_time_source = self._pick_value(entities, 'meeting_time', '时间', 'time')
        if meeting_date_source and meeting_time_source:
            parsed_date = self._parse_natural_datetime(meeting_date_source)
            parsed_time = self._parse_natural_datetime(meeting_time_source)
            meeting_start = (
                datetime.combine(parsed_date.date(), parsed_time.time())
                if parsed_date and parsed_time
                else parsed_date or parsed_time
            )
        else:
            meeting_start = self._parse_natural_datetime(
                meeting_date_source or meeting_time_source or query
            )
        if meeting_start and not normalized_changes.get('meeting_date'):
            normalized_changes['meeting_date'] = meeting_start.strftime('%Y-%m-%d %H:%M:%S')

        end_source = self._pick_value(entities, 'meeting_end_time', 'end_time')
        meeting_end = self._parse_natural_datetime(end_source) if end_source else None
        if meeting_start and not meeting_end:
            meeting_end = meeting_start + timedelta(hours=1)
        if meeting_end and not normalized_changes.get('meeting_end_time'):
            normalized_changes['meeting_end_time'] = meeting_end.strftime('%Y-%m-%d %H:%M:%S')

        location = self._pick_value(entities, 'location', 'meeting_location', 'address')
        if location and not normalized_changes.get('location'):
            normalized_changes['location'] = location
        normalized_changes.setdefault('meeting_type', 'regular')
        normalized_changes.setdefault('status', 'scheduled')

        user_id = getattr(user, 'id', None)
        if user_id:
            normalized_changes.setdefault('host_id', user_id)
            normalized_changes.setdefault('recorder_id', user_id)
        department_id = self._get_user_department_id(user)
        if department_id:
            normalized_changes.setdefault('department_id', department_id)
        return normalized_changes, dict(context or {})

    def _normalize_production_create_payload(
            self,
            entities: dict,
            changes: dict,
            context: dict,
            user=None,
            query: str = '') -> tuple[dict, dict]:
        normalized_changes = dict(changes or {})
        name = self._pick_value(
            normalized_changes,
            'name',
            fallback=self._pick_value(
                entities,
                'name',
                'title',
                'plan_name',
                fallback=self._extract_named_value(
                    query,
                    [
                        r'(?:生产计划(?:名称)?(?:是|为|叫)?)([^，。；]+)',
                        r'(?:新增|创建)(?:一个)?生产计划\s*([^\s，。；,;]+)',
                    ],
                ),
            ),
        )
        if name and not normalized_changes.get('name'):
            normalized_changes['name'] = name
        normalized_changes.setdefault('code', self._generate_production_plan_code())
        normalized_changes.setdefault('quantity', 1)
        normalized_changes.setdefault('unit', '件')

        planned_date = self._parse_natural_datetime(
            self._pick_value(entities, 'plan_start_date', 'start_date', 'date', 'time') or query
        )
        start_date = planned_date.date().isoformat() if planned_date else self._local_now().date().isoformat()
        normalized_changes.setdefault('plan_start_date', start_date)
        normalized_changes.setdefault('plan_end_date', start_date)
        normalized_changes.setdefault('status', 1)
        normalized_changes.setdefault('priority', 2)

        manager_id = getattr(user, 'id', None)
        if manager_id:
            normalized_changes.setdefault('manager_id', manager_id)
        department_id = self._get_user_department_id(user)
        if department_id:
            normalized_changes.setdefault('department_id', department_id)
        return normalized_changes, dict(context or {})

    def _seed_changes_from_entities(self, entities: dict, changes: dict) -> dict:
        normalized_changes = dict(changes or {})
        for key, value in (entities or {}).items():
            if key in self.ENTITY_CHANGE_BLACKLIST or key in normalized_changes:
                continue
            if value in (None, '') or not self._is_simple_entity_value(value):
                continue
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', str(key or '')):
                continue
            normalized_changes[key] = value
        return normalized_changes

    def _filter_create_changes_for_resource(self, resource: str, changes: dict) -> dict:
        try:
            adapter = self._get_registered_adapter(resource)
        except (ImportError, KeyError):
            return dict(changes or {})

        allowed_fields = self._adapter_allowed_fields(adapter, resource)
        if not allowed_fields:
            return dict(changes or {})
        return {
            key: value
            for key, value in (changes or {}).items()
            if key in allowed_fields
        }

    def _normalize_registered_create_changes(
            self, resource: str, entities: dict, changes: dict, user=None, query: str = '') -> dict:
        try:
            adapter = self._get_registered_adapter(resource)
        except (ImportError, KeyError):
            return dict(changes or {})
        normalizer = getattr(adapter, 'normalize_create_changes', None)
        if not callable(normalizer):
            return dict(changes or {})
        return normalizer(entities, changes, user=user, query=query)

    def _normalize_registered_update_changes(
            self, resource: str, entities: dict, changes: dict, user=None, query: str = '') -> dict:
        try:
            adapter = self._get_registered_adapter(resource)
        except (ImportError, KeyError):
            return dict(changes or {})
        normalizer = getattr(adapter, 'normalize_update_changes', None)
        if not callable(normalizer):
            return dict(changes or {})
        return normalizer(entities, changes, user=user, query=query)

    def _normalize_object_ids(self, entities: dict, resource: str) -> list:
        candidates = [
            (entities or {}).get('object_ids'),
            (entities or {}).get('object_id'),
            (entities or {}).get(f'{resource}_id'),
            (entities or {}).get('record_id'),
            (entities or {}).get('id'),
        ]
        raw_ids = next((value for value in candidates if value not in (None, '', [])), [])
        if isinstance(raw_ids, str):
            raw_ids = [item.strip() for item in raw_ids.split(',') if item.strip()]
        elif not isinstance(raw_ids, (list, tuple, set)):
            raw_ids = [raw_ids]

        normalized = []
        for value in raw_ids:
            if isinstance(value, str) and value.isdigit():
                value = int(value)
            if value not in normalized:
                normalized.append(value)
        return normalized

    def _get_registered_adapter(self, resource: str):
        gateway = getattr(self, '_action_gateway', None)
        if gateway is None:
            from apps.ai.services.action_gateway import AIActionGateway

            gateway = AIActionGateway()
            self._action_gateway = gateway
        return gateway.get_adapter(resource)

    def _adapter_allowed_fields(self, adapter, resource: str) -> set[str]:
        allowed_fields: set[str] = set()
        adapter_resource = getattr(adapter, 'resource', resource)
        for attribute in ('allowed_create_fields', 'allowed_fields', 'allowed_update_fields'):
            configured = getattr(adapter, attribute, None)
            if isinstance(configured, dict):
                configured = configured.get(resource) or configured.get(adapter_resource)
            if configured:
                allowed_fields.update(configured)

        config = getattr(adapter, 'CONFIG', None)
        if isinstance(config, dict):
            resource_config = config.get(resource) or config.get(adapter_resource) or {}
            allowed_fields.update(resource_config.get('allowed_fields') or set())

        allowed_fields.update(getattr(adapter, 'required_create_fields', None) or set())
        return allowed_fields

    def _is_simple_entity_value(self, value) -> bool:
        return isinstance(value, (str, int, float, bool))

    def _pick_value(self, payload: dict, *keys, fallback=None):
        for key in keys:
            value = (payload or {}).get(key)
            if value not in (None, ''):
                return value
        return fallback

    def _extract_named_value(self, text: str, patterns: list[str]) -> str:
        value = str(text or '').strip()
        if not value:
            return ''
        for pattern in patterns:
            match = re.search(pattern, value)
            if not match:
                continue
            result = re.sub(r'^[：:，,\s]+|[：:，,\s]+$', '', match.group(1)).strip()
            if result:
                return result
        return ''

    def _extract_personal_task_title(self, query: str, due_source=None) -> str:
        value = str(query or '').strip()
        if not value:
            return ''
        value = re.sub(
            r'^(?:请|麻烦)?\s*(?:帮我|给我)?\s*'
            r'(?:新增|创建|新建|添加|安排)\s*'
            r'(?:一个|一条|一项|项)?\s*(?:个人)?任务[\s，,:\uff1a]*',
            '',
            value,
        )
        due_text = str(due_source or '').strip()
        if due_text and value.startswith(due_text):
            value = value[len(due_text):]
        value = re.sub(
            r'^(?:(?:今天|今日|明天|后天|昨天)\s*'
            r'(?:凌晨|早上|上午|中午|下午|晚上)?\s*'
            r'(?:\d{1,2}\s*点(?:\d{1,2}分?)?半?|\d{1,2}:\d{2})?'
            r'|(?:凌晨|早上|上午|中午|下午|晚上)\s*'
            r'(?:\d{1,2}\s*点(?:\d{1,2}分?)?半?|\d{1,2}:\d{2}))[\s，,]*',
            '',
            value,
        )
        return re.sub(r'^[：:，,\s]+|[：:，,。；;\s]+$', '', value).strip()

    def _local_now(self) -> datetime:
        current = timezone.now()
        if timezone.is_aware(current):
            current = timezone.localtime(current)
        return current.replace(tzinfo=None)

    def _parse_natural_datetime(self, raw_value) -> datetime | None:
        value = str(raw_value or '').strip()
        if not value:
            return None
        value = value.replace('T', ' ').replace('/', '-')
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
            try:
                parsed = datetime.strptime(value, fmt)
                if fmt == '%Y-%m-%d':
                    return datetime.combine(parsed.date(), datetime.min.time())
                return parsed
            except ValueError:
                continue

        now = self._local_now()
        base_date = now.date()
        lowered_value = value.lower()
        if '后天' in value or 'day after tomorrow' in lowered_value:
            base_date = base_date + timedelta(days=2)
        elif '明天' in value or 'tomorrow' in lowered_value:
            base_date = base_date + timedelta(days=1)
        elif '昨天' in value or 'yesterday' in lowered_value:
            base_date = base_date - timedelta(days=1)
        elif '今天' in value or '今日' in value or 'today' in lowered_value:
            base_date = base_date

        hour = 9
        minute = 0
        match = re.search(r'(\d{1,2})\s*点(?:(\d{1,2})分?)?(半)?', value)
        if match:
            hour = int(match.group(1))
            if match.group(3):
                minute = 30
            elif match.group(2):
                minute = int(match.group(2))
            if '下午' in value or '晚上' in value:
                if hour < 12:
                    hour += 12
            elif '中午' in value and hour < 11:
                hour += 12
        elif any(token in value for token in ('下午', '晚上')):
            hour = 15

        english_time = None if match else re.search(
            r'(?<!\d)(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?!\d)',
            lowered_value,
        )
        if english_time:
            hour = int(english_time.group(1))
            minute = int(english_time.group(2) or 0)
            meridiem = english_time.group(3)
            if meridiem == 'pm' and hour < 12:
                hour += 12
            elif meridiem == 'am' and hour == 12:
                hour = 0
            if hour > 23 or minute > 59:
                return None

        relative_tokens = ('today', 'tomorrow', 'yesterday')
        if (
                any(token in value for token in ('今天', '今日', '明天', '后天', '昨天')) or
                any(token in lowered_value for token in relative_tokens) or
                match or english_time):
            return datetime.combine(base_date, datetime.min.time()).replace(hour=hour, minute=minute)
        return None

    def _resolve_customer_id_for_user(self, customer_name: str, user) -> int | None:
        try:
            from apps.customer.models import Customer
        except ModuleNotFoundError:
            return None

        queryset = Customer.objects.filter(delete_time=0)
        if not getattr(user, 'is_superuser', False):
            user_id = getattr(user, 'id', None)
            if not user_id:
                return None
            visible_dids = self._visible_department_ids(user)
            scope = Q(belong_uid=user_id) | build_csv_membership_q('share_ids', user_id)
            if visible_dids:
                scope |= Q(belong_did__in=visible_dids)
            queryset = queryset.filter(scope).distinct()

        exact = queryset.filter(name=customer_name).order_by('id').first()
        if exact:
            return exact.id
        fuzzy = queryset.filter(name__icontains=customer_name).order_by('id').first()
        if fuzzy:
            return fuzzy.id
        return None

    def _resolve_document_category_id(self, title: str, query: str = '') -> int | None:
        try:
            from apps.system.models import DocumentCategory
        except ModuleNotFoundError:
            return None

        try:
            queryset = DocumentCategory.objects.filter(is_active=True).order_by('id')
            if not queryset.exists():
                return None

            text = f'{title} {query}'.strip()
            for keyword in ('通知', '通告', '纪要', '制度', '公告'):
                if keyword not in text:
                    continue
                match = queryset.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword)).first()
                if match:
                    return match.id
            first = queryset.first()
            return first.id if first else None
        except Exception:
            return None

    def _generate_document_number(self) -> str:
        year = self._local_now().year
        return f'GW-{year}-{int(timezone.now().timestamp())}'

    def _generate_order_number(self) -> str:
        try:
            from apps.common.utils import generate_order_number
        except ModuleNotFoundError:
            return f'ORD-{int(timezone.now().timestamp())}'
        return generate_order_number()

    def _generate_production_plan_code(self) -> str:
        year = self._local_now().year
        return f'PLAN-{year}-{int(timezone.now().timestamp())}'

    def _get_user_department_id(self, user):
        for attr in ('department_id', 'did', 'auth_did'):
            value = getattr(user, attr, None)
            if value not in (None, '', 0):
                return value
        return None

    def _visible_department_ids(self, user) -> list[int]:
        values = []
        for attr in ('auth_dids', 'son_dids'):
            raw_value = getattr(user, attr, '') or ''
            values.extend(int(item) for item in str(raw_value).split(',') if item.strip().isdigit())
        department_id = self._get_user_department_id(user)
        if department_id:
            values.append(int(department_id))
        return sorted(set(values))

    def _normalize_approval_request_type(self, entities: dict, query: str = '') -> str:
        raw_values = [
            entities.get('request_type'),
            entities.get('type'),
            entities.get('approval_type'),
        ]
        for raw_value in raw_values:
            request_type = self._canonical_approval_request_type(raw_value)
            if request_type:
                return request_type
        return self._infer_approval_request_type_from_text(query)

    def _canonical_approval_request_type(self, value) -> str:
        cleaned = str(value or '').strip().lower()
        if not cleaned:
            return ''
        if cleaned in self.APPROVAL_REQUEST_TYPE_ALIASES:
            return self.APPROVAL_REQUEST_TYPE_ALIASES[cleaned]
        for request_type, keywords in self.APPROVAL_REQUEST_TYPE_KEYWORDS.items():
            if any(keyword and keyword.lower() in cleaned for keyword in keywords):
                return self.APPROVAL_REQUEST_TYPE_ALIASES.get(request_type, request_type)
        return cleaned

    def _infer_approval_request_type_from_text(self, text: str) -> str:
        value = str(text or '').strip().lower()
        if not value:
            return ''
        for keyword, request_type in self.APPROVAL_REQUEST_TYPE_ALIASES.items():
            if keyword and keyword.lower() in value:
                return request_type
        return ''

    def _extract_approval_reason(self, text: str, request_type: str) -> str:
        value = str(text or '').strip()
        if not value or request_type not in {'leave_request', 'business_trip', 'reimbursement', 'purchase'}:
            return ''

        for pattern in [
                r'(?:因为|由于|原因是|事由是|理由是)\s*([^，。；;,.]+)',
                r'(?:我要|我想|需要|准备|打算)\s*去?\s*([^，。；;,.]+)',
        ]:
            match = re.search(pattern, value)
            if match:
                reason = self._clean_approval_reason(match.group(1), request_type)
                if reason:
                    return reason

        known_reasons = {
            '婚假': '结婚',
            '结婚': '结婚',
            '生病': '生病',
            '看病': '看病',
            '病假': '生病',
            '产检': '产检',
            '陪产': '陪产',
            '家里有事': '家里有事',
            '个人原因': '个人原因',
            '调休': '调休',
            '年假': '年假',
            '事假': '事假',
        }
        for keyword, reason in known_reasons.items():
            if keyword in value:
                return reason

        return self._clean_approval_reason(value, request_type)

    def _clean_approval_reason(self, value: str, request_type: str) -> str:
        reason = str(value or '').strip()
        if not reason:
            return ''
        removals = [
            '当前页面url', '用户请求', '帮我', '请帮我', '麻烦', '我要', '我想',
            '需要', '准备', '打算', '申请', '发起', '创建', '新增', '提交',
            '请个假', '请假', '休假', '假期', '出差', '差旅', '报销', '采购',
            '审批', '流程', '去',
        ]
        for item in removals:
            reason = reason.replace(item, '')
        reason = re.sub(r'[:：,，.。;；\s]+', '', reason)
        if not reason or len(reason) > 40:
            return ''
        return reason

    def _build_approval_title(self, request_type: str, reason: str, flow=None) -> str:
        prefix_map = {
            'leave': '请假申请',
            'leave_request': '请假申请',
            'vacation': '请假申请',
            'business_trip': '出差申请',
            'trip': '出差申请',
            'reimbursement': '报销申请',
            'expense': '报销申请',
            'purchase': '采购申请',
        }
        prefix = prefix_map.get(request_type)
        if not prefix and flow and getattr(flow, 'name', ''):
            prefix = str(flow.name).strip()
        prefix = prefix or '审批申请'
        if reason:
            return f'{prefix}（{reason}）'
        return prefix

    def _build_approval_content(self, request_type: str, reason: str) -> str:
        label_map = {
            'leave': '请假事由',
            'leave_request': '请假事由',
            'vacation': '请假事由',
            'business_trip': '出差事由',
            'trip': '出差事由',
            'reimbursement': '申请事由',
            'expense': '申请事由',
            'purchase': '申请事由',
        }
        label = label_map.get(request_type, '申请事由')
        return f'{label}：{reason}'

    def _resolve_approval_flow(self, user, request_type: str):
        try:
            from apps.approval.models import ApprovalFlow
        except ModuleNotFoundError:
            return None

        flows = [
            flow for flow in ApprovalFlow.objects.filter(is_active=True).select_related('approval_type')
            if self._user_can_initiate_approval_flow(user, flow)
        ]
        if not flows:
            return None

        keywords = self.APPROVAL_REQUEST_TYPE_KEYWORDS.get(request_type, ())
        if keywords:
            ranked = []
            for flow in flows:
                haystack = ' '.join([
                    str(getattr(flow, 'name', '') or ''),
                    str(getattr(flow, 'code', '') or ''),
                    str(getattr(flow, 'description', '') or ''),
                    str(getattr(getattr(flow, 'approval_type', None), 'name', '') or ''),
                    str(getattr(getattr(flow, 'approval_type', None), 'code', '') or ''),
                ]).lower()
                score = sum(1 for keyword in keywords if keyword and keyword.lower() in haystack)
                if score:
                    ranked.append((score, flow))
            if ranked:
                ranked.sort(key=lambda item: (-item[0], item[1].id))
                return ranked[0][1]

        if len(flows) == 1:
            return flows[0]
        return None

    def _user_can_initiate_approval_flow(self, user, flow) -> bool:
        if not flow:
            return False
        if getattr(user, 'is_superuser', False):
            return True

        initiator_departments = str(getattr(flow, 'initiator_departments', '') or '').strip()
        initiator_roles = str(getattr(flow, 'initiator_roles', '') or '').strip()
        initiator_users = str(getattr(flow, 'initiator_users', '') or '').strip()
        if not initiator_departments and not initiator_roles and not initiator_users:
            return True
        if not user:
            return False

        user_id = getattr(user, 'id', None)
        if initiator_users and user_id:
            allowed_user_ids = {
                int(item.strip()) for item in initiator_users.split(',')
                if item.strip().isdigit()
            }
            if user_id in allowed_user_ids:
                return True

        user_dept_id = getattr(user, 'did', None)
        if initiator_departments and user_dept_id:
            allowed_dept_ids = {
                int(item.strip()) for item in initiator_departments.split(',')
                if item.strip().isdigit()
            }
            if user_dept_id in allowed_dept_ids:
                return True

        if initiator_roles:
            user_roles = []
            if hasattr(user, 'roles'):
                try:
                    user_roles = [role.code for role in user.roles.all()]
                except Exception:
                    user_roles = []
            elif hasattr(user, 'role_codes'):
                user_roles = list(getattr(user, 'role_codes') or [])
            allowed_roles = {item.strip() for item in initiator_roles.split(',') if item.strip()}
            if allowed_roles.intersection(user_roles):
                return True

        return False


confirmation_service = AIConfirmationService()
