from __future__ import annotations

import re

from apps.ai.services.action_contracts import AIActionRequest


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
        object_ids = entities.get('object_ids') or []
        changes = entities.get('changes') or {}
        if normalized_resource == 'approval' and action == 'create':
            changes, normalized_context = self._normalize_approval_create_payload(
                entities,
                changes,
                normalized_context,
                user=user,
                query=intent_result.get('original_query') or intent_result.get('query') or '',
            )

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
        return normalized_changes, normalized_context

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
