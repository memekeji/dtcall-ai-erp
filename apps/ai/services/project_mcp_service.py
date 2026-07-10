from __future__ import annotations

from typing import Any


class ProjectMCPService:
    """项目级 MCP 能力目录服务。"""

    RESOURCE_METADATA = {
        'customer': {'label': '客户', 'module': '客户管理', 'aliases': ['客户', '客资', '线索']},
        'order': {'label': '客户订单', 'module': '客户管理', 'aliases': ['订单', '销售单', '成交订单']},
        'contract': {'label': '合同', 'module': '合同管理', 'aliases': ['合同', '协议', '签约']},
        'project': {'label': '项目', 'module': '项目管理', 'aliases': ['项目', '交付项目']},
        'invoice': {'label': '发票', 'module': '财务管理', 'aliases': ['发票', '开票']},
        'finance_expense': {'label': '报销单', 'module': '财务管理', 'aliases': ['报销', '费用', '报销单']},
        'finance_invoice': {'label': '开票申请', 'module': '财务管理', 'aliases': ['开票申请', '财务发票']},
        'finance_income': {'label': '回款', 'module': '财务管理', 'aliases': ['回款', '收入']},
        'finance_order_record': {'label': '订单财务记录', 'module': '财务管理', 'aliases': ['订单财务', '财务记录']},
        'finance_account': {'label': '资金账户', 'module': '财务管理', 'aliases': ['资金账户', '银行账户', '账户余额']},
        'finance_budget': {'label': '预算', 'module': '财务管理', 'aliases': ['预算', '预算管理']},
        'finance_receivable': {'label': '应收账款', 'module': '财务管理', 'aliases': ['应收', '应收款', '应收账款']},
        'finance_payable': {'label': '应付账款', 'module': '财务管理', 'aliases': ['应付', '应付款', '应付账款']},
        'finance_bank_transaction': {'label': '银行流水', 'module': '财务管理', 'aliases': ['银行流水', '银行交易', '账户流水']},
        'supplier': {'label': '供应商', 'module': '合同管理', 'aliases': ['供应商']},
        'product': {'label': '产品', 'module': '合同管理', 'aliases': ['产品', '商品']},
        'inventory': {'label': '库存', 'module': '库存管理', 'aliases': ['库存', '物料', '存货']},
        'warehouse': {'label': '仓库', 'module': '库存管理', 'aliases': ['仓库']},
        'stockin': {'label': '入库单', 'module': '库存管理', 'aliases': ['入库']},
        'stockout': {'label': '出库单', 'module': '库存管理', 'aliases': ['出库']},
        'alert': {'label': '库存预警', 'module': '库存管理', 'aliases': ['预警', '库存预警']},
        'approval': {'label': '审批单', 'module': '审批管理', 'aliases': ['审批', '流程', '申请单']},
        'approval_flow': {'label': '审批流程', 'module': '审批管理', 'aliases': ['审批流程', '审批流']},
        'approval_task': {'label': '待办审批', 'module': '审批管理', 'aliases': ['待审批', '待办审批', '待审批流程']},
        'task': {'label': '任务', 'module': '任务管理', 'aliases': ['任务', '待办任务']},
        'workhour': {'label': '工时', 'module': '任务管理', 'aliases': ['工时']},
        'message': {'label': '站内消息', 'module': '消息中心', 'aliases': ['消息', '站内信']},
        'notice': {'label': '公告', 'module': '办公管理', 'aliases': ['公告', '通知公告']},
        'contact': {'label': '联系人', 'module': '客户管理', 'aliases': ['联系人', '客户联系人', '对接人']},
        'project_document': {'label': '项目文档', 'module': '项目管理', 'aliases': ['项目文档', '项目资料', '项目文件']},
        'project_stage': {'label': '项目阶段', 'module': '项目管理', 'aliases': ['项目阶段']},
        'project_category': {'label': '项目分类', 'module': '项目管理', 'aliases': ['项目分类']},
        'work_type': {'label': '工作类型', 'module': '项目管理', 'aliases': ['工作类型']},
        'document': {'label': '公文', 'module': '公文管理', 'aliases': ['公文', '文档']},
        'payment': {'label': '付款单', 'module': '财务管理', 'aliases': ['付款', '打款']},
        'meeting': {'label': '会议', 'module': '办公管理', 'aliases': ['会议', '会议纪要']},
        'schedule': {'label': '日程', 'module': '个人办公', 'aliases': ['日程', '排期', '安排']},
        'disk': {'label': '网盘文件', 'module': '企业网盘', 'aliases': ['网盘文件', '文件', '资料', '附件']},
        'disk_folder': {'label': '网盘文件夹', 'module': '企业网盘', 'aliases': ['文件夹', '网盘文件夹']},
        'disk_share': {'label': '网盘分享', 'module': '企业网盘', 'aliases': ['分享链接', '共享链接', '网盘分享']},
        'enterprise': {'label': '企业信息', 'module': '企业信息', 'aliases': ['企业信息', '公司信息']},
        'position': {'label': '岗位', 'module': '人事管理', 'aliases': ['岗位', '职位']},
        'work_record': {'label': '工作记录', 'module': '个人办公', 'aliases': ['工作记录', '工作日志']},
        'work_report': {'label': '工作汇报', 'module': '个人办公', 'aliases': ['工作汇报', '周报', '日报', '月报']},
        'production_plan': {'label': '生产计划', 'module': '生产管理', 'aliases': ['生产计划', '排产计划']},
        'production_task': {'label': '生产任务', 'module': '生产管理', 'aliases': ['生产任务', '生产工单', '派工单']},
        'production_equipment': {'label': '生产设备', 'module': '生产管理', 'aliases': ['设备', '生产设备', '机台', '机器设备']},
        'production_procedure': {'label': '工序', 'module': '生产管理', 'aliases': ['工序', '生产工序', '工艺工序']},
        'employee': {'label': '员工', 'module': '人事管理', 'aliases': ['员工', '人员']},
        'department': {'label': '部门', 'module': '组织管理', 'aliases': ['部门', '组织架构']},
        'followup': {'label': '跟进记录', 'module': '客户管理', 'aliases': ['跟进', '跟进记录', '回访']},
        'personal_task': {'label': '个人任务', 'module': '个人办公', 'aliases': ['个人任务', '我的待办']},
        'personal_note': {'label': '个人笔记', 'module': '个人办公', 'aliases': ['个人笔记', '笔记']},
        'personal_contact': {'label': '个人联系人', 'module': '个人办公', 'aliases': ['个人联系人', '私人通讯录', '我的联系人', '私人联系人']},
        'ai_model_config': {'label': 'AI模型配置', 'module': 'AI智能中心', 'aliases': ['AI模型配置', '模型配置', '模型列表']},
        'ai_knowledge_base': {'label': '知识库', 'module': 'AI智能中心', 'aliases': ['知识库', '知识库列表']},
        'ai_task': {'label': 'AI任务', 'module': 'AI智能中心', 'aliases': ['AI任务', '智能任务']},
        'ai_workflow': {'label': 'AI工作流', 'module': 'AI智能中心', 'aliases': ['AI工作流', '工作流']},
        'supply_chain_forecast': {'label': '需求预测计划', 'module': '供应链管理', 'aliases': ['需求预测', '预测计划', '备料预测']},
        'supply_chain_outsource': {'label': '委外发料单', 'module': '供应链管理', 'aliases': ['委外发料', '委外单', '委外发料单']},
        'supply_chain_pr_review': {'label': 'PR审核任务', 'module': '供应链管理', 'aliases': ['PR审核', 'PR复核', '采购申请审核']},
        'supply_chain_price_review': {'label': '单价复核单', 'module': '供应链管理', 'aliases': ['单价复核', '价格复核', '询价复核']},
        'supply_chain_sample': {'label': '打样申请', 'module': '供应链管理', 'aliases': ['打样', '打样申请', '样品申请']},
    }
    QUERY_SUMMARY_RESOURCES = {'order', 'contract'}

    def get_capability_catalog(self) -> list[dict[str, Any]]:
        capabilities = []
        capabilities.extend(self._build_query_capabilities())
        capabilities.extend(self._build_write_capabilities())
        return capabilities

    def build_prompt_context(self, max_items: int = 24) -> str:
        lines = ['项目MCP能力目录（用于意图识别与执行规划）：']
        for capability in self.get_capability_catalog()[:max_items]:
            operations = ', '.join(capability.get('operations') or [])
            skills = ', '.join(capability.get('skill_tags') or [])
            lines.append(
                f"- {capability['resource']} | {capability['module']} | {capability['intent_mode']} | "
                f"ops={operations} | permission={capability.get('permission_code') or '按模块控制'} | skills={skills}"
            )
        return '\n'.join(lines)

    def build_runtime_context(self, query: str, intent_result: dict[str, Any] | None = None) -> dict[str, Any]:
        intent_result = intent_result or {}
        matched_capabilities = self.match_capabilities(query, intent_result)
        skill_hints = []
        for capability in matched_capabilities:
            for tag in capability.get('skill_tags') or []:
                if tag not in skill_hints:
                    skill_hints.append(tag)

        return {
            'enabled': True,
            'protocol': 'project-mcp',
            'matched_capabilities': matched_capabilities,
            'skill_hints': skill_hints,
        }

    def match_capabilities(self, query: str, intent_result: dict[str, Any] | None = None, limit: int = 5) -> list[dict[str, Any]]:
        intent_result = intent_result or {}
        query_lower = str(query or '').lower()
        catalog = self.get_capability_catalog()
        resources = self._collect_candidate_resources(query_lower, intent_result)
        desired_operations = self._resolve_desired_operations(intent_result)

        matched = []
        if resources:
            for resource in resources:
                for capability in catalog:
                    if capability['resource'] != resource:
                        continue
                    operations = capability.get('operations') or []
                    if desired_operations and not any(operation in operations for operation in desired_operations):
                        continue
                    matched.append(self._public_capability(capability))
        else:
            for capability in catalog:
                operations = capability.get('operations') or []
                if desired_operations and not any(operation in operations for operation in desired_operations):
                    continue
                matched.append(self._public_capability(capability))

        if matched:
            return matched[:limit]

        for capability in catalog:
            if self._matches_alias(query_lower, capability['resource']):
                matched.append(self._public_capability(capability))
        return matched[:limit]

    def _build_query_capabilities(self) -> list[dict[str, Any]]:
        capabilities = []
        permission_mapping = self._get_query_permission_mapping()
        for resource, metadata in self.RESOURCE_METADATA.items():
            permission_code = permission_mapping.get(resource)
            if permission_code is None:
                continue
            base_capability = {
                'resource': resource,
                'module': metadata['module'],
                'label': metadata['label'],
                'intent_mode': 'query',
                'execution_mode': 'query_service',
                'permission_code': permission_code,
                'skill_tags': self._skill_tags_for_query(resource),
                'aliases': metadata['aliases'],
            }
            capabilities.append({
                **base_capability,
                'id': f'query.{resource}.list',
                'operations': ['list', 'detail'],
            })
            capabilities.append({
                **base_capability,
                'id': f'query.{resource}.count',
                'operations': ['count'],
            })
            if resource in self.QUERY_SUMMARY_RESOURCES:
                capabilities.append({
                    **base_capability,
                    'id': f'query.{resource}.summary',
                    'operations': ['summary'],
                })
        return capabilities

    def _build_write_capabilities(self) -> list[dict[str, Any]]:
        capabilities = []
        for resource, config in self._get_business_handoff_config().items():
            module = config.get('module') or self.RESOURCE_METADATA.get(resource, {}).get('module') or '业务模块'
            label = config.get('name') or self.RESOURCE_METADATA.get(resource, {}).get('label') or resource
            aliases = self.RESOURCE_METADATA.get(resource, {}).get('aliases') or [label]
            permission_base = config.get('permission_base')
            action_urls = config.get('action_urls') or {}
            if config.get('create_url'):
                capabilities.append({
                    'id': f'write.{resource}.create',
                    'resource': resource,
                    'module': module,
                    'label': label,
                    'intent_mode': 'write',
                    'execution_mode': 'business_handoff',
                    'operations': ['create'],
                    'permission_code': self._resolve_write_permission_code(config, 'create', permission_base),
                    'target_url': config.get('create_url'),
                    'skill_tags': self._skill_tags_for_write(resource, 'create'),
                    'aliases': aliases,
                })
            if config.get('edit_url_template') or config.get('list_url'):
                capabilities.append({
                    'id': f'write.{resource}.update',
                    'resource': resource,
                    'module': module,
                    'label': label,
                    'intent_mode': 'write',
                    'execution_mode': 'business_handoff',
                    'operations': ['update'],
                    'permission_code': self._resolve_write_permission_code(config, 'update', permission_base),
                    'target_url': config.get('edit_url_template') or config.get('list_url'),
                    'skill_tags': self._skill_tags_for_write(resource, 'update'),
                    'aliases': aliases,
                })
                capabilities.append({
                    'id': f'write.{resource}.delete',
                    'resource': resource,
                    'module': module,
                    'label': label,
                    'intent_mode': 'write',
                    'execution_mode': 'business_handoff',
                    'operations': ['delete'],
                    'permission_code': self._resolve_write_permission_code(config, 'delete', permission_base),
                    'target_url': config.get('edit_url_template') or config.get('list_url'),
                    'skill_tags': self._skill_tags_for_write(resource, 'delete'),
                    'aliases': aliases,
                })
            for operation, target_url in action_urls.items():
                capabilities.append({
                    'id': f'write.{resource}.{operation}',
                    'resource': resource,
                    'module': module,
                    'label': label,
                    'intent_mode': 'write',
                    'execution_mode': 'business_handoff',
                    'operations': [operation],
                    'permission_code': self._resolve_write_permission_code(config, operation, permission_base),
                    'target_url': target_url,
                    'skill_tags': self._skill_tags_for_write(resource, operation),
                    'aliases': aliases,
                })
        return capabilities

    def _collect_candidate_resources(self, query_lower: str, intent_result: dict[str, Any]) -> list[str]:
        resources = []
        primary = intent_result.get('data_type')
        if primary:
            resources.append(primary)
        for candidate in (intent_result.get('entities') or {}).get('candidate_data_types') or []:
            if candidate not in resources:
                resources.append(candidate)
        for resource, metadata in self.RESOURCE_METADATA.items():
            if any(alias.lower() in query_lower for alias in metadata.get('aliases') or []):
                if resource not in resources:
                    resources.append(resource)
        return resources

    def _resolve_desired_operations(self, intent_result: dict[str, Any]) -> list[str]:
        action = intent_result.get('action')
        if action in {'create', 'update', 'delete', 'approve', 'reject', 'submit', 'publish', 'withdraw', 'stock', 'list', 'detail', 'count', 'summary'}:
            return [action]
        if intent_result.get('intent') == 'DATA_QUERY':
            return ['list', 'count', 'summary']
        if intent_result.get('intent') == 'DATA_CREATE':
            return ['create']
        if intent_result.get('intent') == 'DATA_UPDATE':
            return ['update', 'approve', 'reject', 'submit', 'publish', 'withdraw', 'stock']
        if intent_result.get('intent') == 'DATA_DELETE':
            return ['delete']
        return []

    def _public_capability(self, capability: dict[str, Any]) -> dict[str, Any]:
        return {
            'id': capability['id'],
            'resource': capability['resource'],
            'label': capability['label'],
            'module': capability['module'],
            'intent_mode': capability['intent_mode'],
            'execution_mode': capability['execution_mode'],
            'operations': list(capability.get('operations') or []),
            'permission_code': capability.get('permission_code'),
            'target_url': capability.get('target_url'),
            'skill_tags': list(capability.get('skill_tags') or []),
        }

    def _skill_tags_for_query(self, resource: str) -> list[str]:
        tags = ['query_execute', 'permission_guard']
        if resource in {'order', 'customer', 'contract', 'followup', 'contact'}:
            tags.append('crm_query')
        if resource in {'approval', 'approval_flow', 'approval_task'}:
            tags.append('approval_query')
        if resource.startswith('disk'):
            tags.append('file_query')
        if resource.startswith('production'):
            tags.append('production_query')
        return tags

    def _skill_tags_for_write(self, resource: str, operation: str) -> list[str]:
        tags = ['record_write', 'permission_guard', 'confirm_before_write']
        if operation in {'update', 'delete'}:
            tags.append('rollback_supported')
        if operation in {'approve', 'reject', 'submit', 'publish', 'withdraw', 'stock'}:
            tags.extend(['workflow_action', 'rollback_supported'])
        if resource in {'approval', 'approval_flow', 'approval_task'}:
            tags.append('approval_flow_control')
        if resource.startswith('disk'):
            tags.append('file_write')
        return tags

    def _build_write_permission_code(self, permission_base: str | None, action_prefix: str) -> str | None:
        if not permission_base:
            return None
        return f'user.{action_prefix}_{permission_base}'

    def _resolve_write_permission_code(self, config: dict[str, Any], action: str, permission_base: str | None) -> str | None:
        permission_config = config.get('permission')
        if isinstance(permission_config, dict):
            selected = permission_config.get(action) or permission_config.get('query')
            if isinstance(selected, dict):
                return selected.get('full_code') or selected.get('codename')
            if isinstance(selected, str):
                return selected
        action_prefix_map = {'create': 'add', 'update': 'change', 'delete': 'delete'}
        return self._build_write_permission_code(permission_base, action_prefix_map.get(action, action))

    def _get_query_permission_mapping(self) -> dict[str, str]:
        from apps.ai.services.query_service import QueryService

        return dict(QueryService().permission_mapping)

    def _get_business_handoff_config(self) -> dict[str, dict[str, Any]]:
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        return dict(EnhancedIntentService.BUSINESS_HANDOFF_CONFIG)

    def _matches_alias(self, query_lower: str, resource: str) -> bool:
        metadata = self.RESOURCE_METADATA.get(resource) or {}
        aliases = metadata.get('aliases') or []
        return any(alias.lower() in query_lower for alias in aliases)


project_mcp_service = ProjectMCPService()
