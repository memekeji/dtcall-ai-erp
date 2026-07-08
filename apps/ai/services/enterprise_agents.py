from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from apps.ai.models import (
    AIOperation,
    AIOperationChangeSet,
    AIKnowledgeBase,
    AIModelConfig,
    AIWorkflow,
)
from apps.ai.services.action_contracts import AIActionRequest
from apps.ai.services.action_gateway import AIActionGateway
from apps.ai.services.business_result import build_business_ai_result
from apps.ai.services.operation_service import operation_service
from apps.contract.contract_review_service import contract_review_service
from apps.customer.models import Contact, Customer, FollowRecord
from apps.inventory.models import InventoryItem
from apps.production.ai_views import default_production_analysis_tool
from apps.production.models import ProductionPlan, ProductionTask
from apps.project.models import Project, Task, WorkHour
from apps.project.risk_analysis import default_project_analysis_tool
from apps.supply_chain.services.inventory_analysis_service import build_inventory_analysis_summary
from apps.ai.utils.analysis_tools import default_customer_analysis_tool


@dataclass(frozen=True)
class AgentActionDefinition:
    id: str
    label: str
    description: str
    execution_mode: str
    risk_level: str
    fields: list[dict[str, Any]] = field(default_factory=list)
    resource: str | None = None
    operation: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    handler_name: str | None = None


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    description: str
    domain: str
    icon: str
    status: str
    audience: str
    highlights: list[str] = field(default_factory=list)
    actions: list[AgentActionDefinition] = field(default_factory=list)


class EnterpriseAgentService:
    def __init__(self) -> None:
        self._agents = self._build_registry()

    def get_center_payload(self, user) -> dict[str, Any]:
        enterprise_agents = [self._serialize_agent(agent) for agent in self._agents.values()]
        summary = self._build_summary(enterprise_agents)
        return {
            'summary': summary,
            'enterprise_agents': enterprise_agents,
            'foundation_resources': self._build_foundation_resources(),
            'recent_operations': self._get_recent_operations(),
        }

    def get_agent_detail(self, agent_id: str, user) -> dict[str, Any]:
        agent = self._get_agent(agent_id)
        return {
            'agent': {
                **self._serialize_agent(agent),
                'actions': [self._serialize_action(agent.id, action, with_options=True) for action in agent.actions],
                'recent_operations': self._get_recent_operations(agent_id=agent.id, limit=8),
            }
        }

    def execute(self, user, agent_id: str, action_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        agent = self._get_agent(agent_id)
        action = self._get_action(agent, action_id)

        if action.execution_mode == 'analysis':
            handler = getattr(self, f'_execute_{action.handler_name or action.id}')
            result = handler(user, params)
            return {
                'success': True,
                'result_type': 'business_result',
                'agent_id': agent_id,
                'action_id': action_id,
                'data': result,
            }

        action_request = self._build_action_request(agent.id, action, params)
        if action.execution_mode == 'direct':
            return self._execute_direct_action(user, agent.id, action, action_request)
        if action.execution_mode == 'confirm':
            return self._preview_confirm_action(user, agent.id, action, action_request)
        return {'success': False, 'message': '未知的动作执行模式'}

    def _build_registry(self) -> dict[str, AgentDefinition]:
        registry = [
            AgentDefinition(
                id='customer_followup_agent',
                name='客户跟进智能体',
                description='围绕客户分类、画像与回访动作，帮助销售团队形成可执行的跟进节奏。',
                domain='客户 / 销售',
                icon='layui-icon-dialogue',
                status='online',
                audience='销售、客服、销售主管',
                highlights=['客户画像', '跟进建议', '自动建任务'],
                actions=[
                    AgentActionDefinition(
                        id='profile_analysis',
                        label='客户画像分析',
                        description='生成客户画像、近期风险与跟进建议。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='customer_profile_analysis',
                        fields=[self._select_field('customer_id', '客户', 'customers', required=True)],
                    ),
                    AgentActionDefinition(
                        id='create_followup_task',
                        label='创建跟进任务',
                        description='为客户创建低风险跟进任务，可直接执行。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='task',
                        operation='create',
                        fields=[
                            self._text_field('title', '任务标题', required=True),
                            self._textarea_field('description', '任务说明'),
                            self._select_field('assignee_id', '负责人', 'employees'),
                            self._date_field('end_date', '截止日期'),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='project_risk_agent',
                name='项目风险智能体',
                description='识别项目延期、资源与质量风险，并能快速拆出整改任务。',
                domain='项目 / 管理',
                icon='layui-icon-rate-half',
                status='online',
                audience='项目经理、PMO、部门负责人',
                highlights=['风险评估', '风险点汇总', '整改任务'],
                actions=[
                    AgentActionDefinition(
                        id='project_risk_analysis',
                        label='项目风险评估',
                        description='分析项目进度、工时与任务完成情况。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='project_risk_analysis',
                        fields=[self._select_field('project_id', '项目', 'projects', required=True)],
                    ),
                    AgentActionDefinition(
                        id='create_project_remediation_task',
                        label='创建整改任务',
                        description='基于风险结论直接创建项目整改任务。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='task',
                        operation='create',
                        fields=[
                            self._select_field('project_id', '项目', 'projects', required=True),
                            self._text_field('title', '任务标题', required=True),
                            self._textarea_field('description', '整改要求'),
                            self._select_field('assignee_id', '负责人', 'employees'),
                            self._date_field('end_date', '截止日期'),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='production_dispatch_agent',
                name='生产排产智能体',
                description='读取生产计划与任务负载，给出排产优化建议，并支持关键计划调整。',
                domain='生产',
                icon='layui-icon-chart',
                status='online',
                audience='生产计划员、车间主管、运营经理',
                highlights=['排产优化', '瓶颈识别', '计划调整需确认'],
                actions=[
                    AgentActionDefinition(
                        id='production_plan_analysis',
                        label='计划优化分析',
                        description='分析当前生产计划、任务状态和交付压力。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='production_plan_analysis',
                        fields=[self._select_field('plan_id', '生产计划', 'production_plans', required=True)],
                    ),
                    AgentActionDefinition(
                        id='adjust_production_plan',
                        label='调整生产计划',
                        description='调整优先级与计划结束日期，需预览确认。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='production',
                        operation='update',
                        fields=[
                            self._select_field('plan_id', '生产计划', 'production_plans', required=True),
                            self._select_field(
                                'priority',
                                '优先级',
                                static_options=[
                                    {'value': '1', 'label': '高'},
                                    {'value': '2', 'label': '中'},
                                    {'value': '3', 'label': '低'},
                                ],
                            ),
                            self._date_field('plan_end_date', '计划结束日期'),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='inventory_health_agent',
                name='库存健康智能体',
                description='汇总库存风险、缺口和阈值设置，帮助供应链团队快速修正库存策略。',
                domain='库存 / 供应链',
                icon='layui-icon-component',
                status='online',
                audience='仓储、采购、供应链经理',
                highlights=['库存体检', '补货建议', '阈值直改'],
                actions=[
                    AgentActionDefinition(
                        id='inventory_risk_analysis',
                        label='库存风险总览',
                        description='统计高风险库存并输出补货建议。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='inventory_risk_analysis',
                    ),
                    AgentActionDefinition(
                        id='update_inventory_thresholds',
                        label='更新库存阈值',
                        description='更新安全库存和再订货点，属于低风险直执动作。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='inventory',
                        operation='update',
                        fields=[
                            self._select_field('item_id', '物料', 'inventory_items', required=True),
                            self._number_field('safety_stock', '安全库存'),
                            self._number_field('reorder_point', '再订货点'),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='contract_review_agent',
                name='合同审查智能体',
                description='调用现有合同审查能力，对条款风险、缺失项和签署建议进行结构化输出。',
                domain='合同 / 法务',
                icon='layui-icon-file-b',
                status='online',
                audience='法务、销售内勤、合同管理员',
                highlights=['条款风险', '签约建议', '关键信息交叉核验'],
                actions=[
                    AgentActionDefinition(
                        id='contract_quick_review',
                        label='合同快速审查',
                        description='对合同正文进行快速风险审查并给出建议。',
                        execution_mode='analysis',
                        risk_level='high',
                        handler_name='contract_quick_review',
                        fields=[self._select_field('contract_id', '合同', 'contracts', required=True)],
                    ),
                ],
            ),
            AgentDefinition(
                id='finance_ops_agent',
                name='财务执行智能体',
                description='辅助收付款录入与字段校验，将高风险财务动作纳入预览确认流程。',
                domain='财务',
                icon='layui-icon-rmb',
                status='online',
                audience='财务专员、出纳、财务主管',
                highlights=['字段校验', '付款录入', '回款录入'],
                actions=[
                    AgentActionDefinition(
                        id='finance_entry_analysis',
                        label='财务录入校验',
                        description='检查金额、日期与备注完整性，给出录入建议。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='finance_entry_analysis',
                        fields=[
                            self._number_field('amount', '金额', required=True),
                            self._date_field('record_date', '业务日期', required=True),
                            self._textarea_field('remark', '备注'),
                        ],
                    ),
                    AgentActionDefinition(
                        id='create_payment_record',
                        label='新增付款记录',
                        description='高风险财务动作，生成预览后确认执行。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='finance',
                        operation='create',
                        context={'model': 'payment'},
                        fields=[
                            self._number_field('amount', '付款金额', required=True),
                            self._date_field('payment_date', '付款日期', required=True),
                            self._number_field('customer_id', '客户ID'),
                            self._number_field('project_id', '项目ID'),
                            self._textarea_field('remark', '备注'),
                        ],
                    ),
                    AgentActionDefinition(
                        id='create_income_record',
                        label='新增回款记录',
                        description='高风险财务动作，生成预览后确认执行。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='finance',
                        operation='create',
                        context={'model': 'income'},
                        fields=[
                            self._number_field('amount', '回款金额', required=True),
                            self._date_field('income_date', '回款日期', required=True),
                            self._number_field('invoice_id', '发票ID'),
                            self._textarea_field('remark', '备注'),
                        ],
                    ),
                ],
            ),
        ]
        return {item.id: item for item in registry}

    def _serialize_agent(self, agent: AgentDefinition) -> dict[str, Any]:
        return {
            'id': agent.id,
            'name': agent.name,
            'description': agent.description,
            'domain': agent.domain,
            'icon': agent.icon,
            'status': agent.status,
            'audience': agent.audience,
            'highlights': list(agent.highlights),
            'action_count': len(agent.actions),
            'analysis_count': sum(1 for action in agent.actions if action.execution_mode == 'analysis'),
            'direct_count': sum(1 for action in agent.actions if action.execution_mode == 'direct'),
            'confirm_count': sum(1 for action in agent.actions if action.execution_mode == 'confirm'),
        }

    def _serialize_action(self, agent_id: str, action: AgentActionDefinition, with_options: bool = False) -> dict[str, Any]:
        fields = []
        for field_config in action.fields:
            item = dict(field_config)
            if with_options and item.get('type') == 'select':
                item['options'] = self._resolve_options(item)
            elif with_options:
                item.setdefault('options', item.get('static_options', []))
            item.pop('options_provider', None)
            item.pop('static_options', None)
            fields.append(item)
        return {
            'id': action.id,
            'agent_id': agent_id,
            'label': action.label,
            'description': action.description,
            'execution_mode': action.execution_mode,
            'risk_level': action.risk_level,
            'fields': fields,
        }

    def _build_summary(self, enterprise_agents: list[dict[str, Any]]) -> dict[str, Any]:
        direct_action_count = sum(agent['direct_count'] for agent in enterprise_agents)
        confirm_action_count = sum(agent['confirm_count'] for agent in enterprise_agents)
        analysis_action_count = sum(agent['analysis_count'] for agent in enterprise_agents)
        recent_operations = self._get_recent_operations(limit=100)
        return {
            'enterprise_agent_count': len(enterprise_agents),
            'analysis_action_count': analysis_action_count,
            'direct_action_count': direct_action_count,
            'confirm_action_count': confirm_action_count,
            'recent_execution_count': len(recent_operations),
            'pending_confirmation_count': sum(1 for item in recent_operations if item['status'] == 'preview'),
        }

    def _build_foundation_resources(self) -> list[dict[str, Any]]:
        resources: list[dict[str, Any]] = []
        try:
            workflows = AIWorkflow.objects.filter(status='published').select_related('owner').order_by('-created_at')[:6]
            for workflow in workflows:
                resources.append({
                    'type': 'workflow',
                    'name': workflow.name,
                    'description': workflow.description or '已发布工作流',
                    'link': f'/ai/workflow/html/{workflow.id}/',
                    'meta': workflow.owner.username if getattr(workflow, 'owner', None) else '系统',
                })
        except Exception:
            pass

        try:
            model_configs = AIModelConfig.objects.filter(is_active=True).order_by('-is_default', '-updated_at')[:4]
            for config in model_configs:
                resources.append({
                    'type': 'model',
                    'name': config.name,
                    'description': f"{config.get_provider_display()} / {config.primary_model_name()}",
                    'link': f'/ai/model-config/detail/{config.id}/',
                    'meta': '模型配置',
                })
        except Exception:
            pass

        try:
            knowledge_bases = AIKnowledgeBase.objects.filter(status='published').select_related('creator').order_by('-created_at')[:4]
            for kb in knowledge_bases:
                resources.append({
                    'type': 'knowledge',
                    'name': kb.name,
                    'description': kb.description or '知识检索与问答',
                    'link': f'/ai/knowledge-base/detail/{kb.id}/',
                    'meta': kb.creator.username if getattr(kb, 'creator', None) else '系统',
                })
        except Exception:
            pass
        return resources

    def _get_recent_operations(self, agent_id: str | None = None, limit: int = 12) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        try:
            queryset = AIOperation.objects.order_by('-created_at')[:80]
            for operation in queryset:
                payload = dict(operation.confirmed_payload or operation.preview_payload or {})
                if payload.get('source') != 'agent_center':
                    continue
                if agent_id and payload.get('agent_id') != agent_id:
                    continue
                items.append({
                    'id': operation.id,
                    'agent_id': payload.get('agent_id', ''),
                    'action_id': payload.get('action_id', ''),
                    'status': operation.status,
                    'resource_type': operation.resource_type,
                    'operation_type': operation.operation_type,
                    'created_at': operation.created_at.strftime('%Y-%m-%d %H:%M') if getattr(operation, 'created_at', None) else '',
                    'executed_at': operation.executed_at.strftime('%Y-%m-%d %H:%M') if getattr(operation, 'executed_at', None) else '',
                    'can_rollback': operation.status == 'executed',
                })
                if len(items) >= limit:
                    break
        except Exception:
            return []
        return items

    def _execute_direct_action(self, user, agent_id: str, action: AgentActionDefinition, action_request: AIActionRequest) -> dict[str, Any]:
        gateway = AIActionGateway()
        adapter = gateway.get_adapter(action_request.resource)
        payload = self._build_operation_payload(agent_id, action.id, action_request)
        operation = AIOperation.objects.create(
            user=user,
            operation_type=action_request.operation,
            resource_type=action_request.resource,
            status='confirmed',
            preview_payload=payload,
            confirmed_payload=payload,
            requires_confirmation=False,
        )
        result = adapter.execute(action_request, user, operation=operation)
        for index, item in enumerate(result.get('change_set', []), start=1):
            AIOperationChangeSet.objects.create(
                operation=operation,
                sequence=index,
                app_label=item.get('app_label', ''),
                model_name=item.get('model_name', ''),
                object_pk=str(item.get('object_pk', '')),
                change_type=item.get('change_type', 'update'),
                before_snapshot=item.get('before_snapshot'),
                after_snapshot=item.get('after_snapshot'),
                changed_fields=item.get('changed_fields', []),
                is_rollback_supported=True,
                rollback_metadata=item.get('rollback_metadata', {}),
            )

        operation.status = 'executed' if result.get('success') else 'failed'
        operation.executed_at = timezone.now()
        operation.save(update_fields=['status', 'executed_at', 'updated_at'])
        return {
            'success': bool(result.get('success')),
            'result_type': 'operation',
            'message': result.get('message', ''),
            'operation': {
                'id': operation.id,
                'status': operation.status,
                'can_rollback': operation.status == 'executed',
            },
            'change_set': result.get('change_set', []),
        }

    def _preview_confirm_action(self, user, agent_id: str, action: AgentActionDefinition, action_request: AIActionRequest) -> dict[str, Any]:
        gateway = AIActionGateway()
        adapter = gateway.get_adapter(action_request.resource)
        preview = adapter.preview(action_request, user)
        if not preview.get('success'):
            return preview

        payload = {
            'action_plan': self._build_operation_payload(agent_id, action.id, action_request),
            'confirmation': {
                'required': True,
                'message': f'{action.label} 将修改业务数据，请确认后执行。',
            },
        }
        operation = operation_service.create_preview_operation(
            user=user,
            chat=None,
            user_message=None,
            ai_message=None,
            payload=payload,
        )
        return {
            'success': True,
            'result_type': 'confirmation_required',
            'message': payload['confirmation']['message'],
            'operation': {
                'id': operation.id if operation else None,
                'token': operation.confirmation_token if operation else '',
                'status': 'preview',
            },
            'preview_change_set': preview.get('change_set', []),
        }

    def _build_operation_payload(self, agent_id: str, action_id: str, action_request: AIActionRequest) -> dict[str, Any]:
        return {
            'source': 'agent_center',
            'agent_id': agent_id,
            'action_id': action_id,
            'resource': action_request.resource,
            'operation': action_request.operation,
            'object_ids': action_request.object_ids,
            'changes': action_request.changes,
            'filters': action_request.filters,
            'context': action_request.context,
        }

    def _build_action_request(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        handler = getattr(self, f'_build_action_{action.id}')
        return handler(agent_id, action, params)

    def _build_action_create_followup_task(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='task',
            operation='create',
            changes=self._without_empty({
                'title': params.get('title'),
                'description': params.get('description'),
                'assignee_id': params.get('assignee_id'),
                'end_date': params.get('end_date'),
            }),
        )

    def _build_action_create_project_remediation_task(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='task',
            operation='create',
            changes=self._without_empty({
                'project_id': params.get('project_id'),
                'title': params.get('title'),
                'description': params.get('description'),
                'assignee_id': params.get('assignee_id'),
                'end_date': params.get('end_date'),
            }),
        )

    def _build_action_adjust_production_plan(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='production',
            operation='update',
            object_ids=[params.get('plan_id')] if params.get('plan_id') not in (None, '') else [],
            changes=self._without_empty({
                'priority': params.get('priority'),
                'plan_end_date': params.get('plan_end_date'),
            }),
        )

    def _build_action_update_inventory_thresholds(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='inventory',
            operation='update',
            object_ids=[params.get('item_id')] if params.get('item_id') not in (None, '') else [],
            changes=self._without_empty({
                'safety_stock': params.get('safety_stock'),
                'reorder_point': params.get('reorder_point'),
            }),
        )

    def _build_action_create_payment_record(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='finance',
            operation='create',
            changes=self._without_empty({
                'amount': params.get('amount'),
                'payment_date': params.get('payment_date'),
                'customer_id': params.get('customer_id'),
                'project_id': params.get('project_id'),
                'remark': params.get('remark'),
            }),
            context=action.context,
        )

    def _build_action_create_income_record(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='finance',
            operation='create',
            changes=self._without_empty({
                'amount': params.get('amount'),
                'income_date': params.get('income_date'),
                'invoice_id': params.get('invoice_id'),
                'remark': params.get('remark'),
            }),
            context=action.context,
        )

    def _execute_customer_profile_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        customer = Customer.objects.get(id=params['customer_id'], delete_time=0)
        contacts = Contact.objects.filter(customer=customer)
        follow_records = FollowRecord.objects.filter(customer=customer, delete_time=0).order_by('-follow_time')[:20]
        customer_data = {
            'id': customer.id,
            'name': customer.name,
            'customer_source': customer.customer_source_id,
            'grade': customer.grade_id,
            'industry': customer.industry_id,
            'area': f"{customer.province}{customer.city}",
            'customer_status': 0 if customer.discard_time == 0 else 1,
            'intent_status': customer.intent_status,
            'address': customer.address,
            'contacts': [
                {
                    'contact_person': item.contact_person,
                    'phone': item.phone,
                    'email': item.email,
                    'position': item.position,
                    'is_primary': item.is_primary,
                }
                for item in contacts
            ],
        }
        follow_data = [
            {
                'follow_type': record.follow_type,
                'follow_content': record.follow_content,
                'follow_user': record.follow_user.username if record.follow_user else '',
            }
            for record in follow_records
        ]
        raw_result = default_customer_analysis_tool.generate_customer_profile(customer_data, follow_data)
        return build_business_ai_result(
            raw_result,
            scenario='customer_profile',
            source_refs=[{'type': 'customer', 'id': customer.id}],
            raw_input={'customer': customer_data, 'follow_count': len(follow_data)},
        )

    def _execute_project_risk_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        project = Project.objects.get(id=params['project_id'], delete_time__isnull=True)
        task_queryset = Task.objects.filter(project=project, delete_time__isnull=True)
        work_hour_queryset = WorkHour.objects.filter(project=project, delete_time__isnull=True)
        task_data = [
            {
                'id': task.id,
                'title': task.title,
                'status': task.status,
                'priority': task.priority,
                'progress': task.progress,
                'assignee_id': task.assignee_id,
                'start_date': task.start_date,
                'end_date': task.end_date,
            }
            for task in task_queryset
        ]
        project_data = {
            'id': project.id,
            'name': project.name,
            'code': getattr(project, 'code', ''),
            'status': getattr(project, 'status', ''),
            'progress': getattr(project, 'progress', 0),
            'start_date': getattr(project, 'start_date', None),
            'end_date': getattr(project, 'end_date', None),
            'manager_id': getattr(project, 'manager_id', None),
            'department_id': getattr(project, 'department_id', None),
        }
        task_stats = {
            'total_tasks': task_queryset.count(),
            'completed_tasks': task_queryset.filter(status='completed').count(),
            'in_progress_tasks': task_queryset.filter(status='in_progress').count(),
            'pending_tasks': task_queryset.filter(status='pending').count(),
        }
        total_hours = work_hour_queryset.aggregate(total=Sum('hours'))
        raw_result = default_project_analysis_tool.predict_project_risk(
            project_data=project_data,
            task_data=task_data,
            task_stats=task_stats,
            total_hours=total_hours,
        )
        return build_business_ai_result(
            raw_result,
            scenario='project_risk_prediction',
            source_refs=[{'type': 'project', 'id': project.id}],
            raw_input={'project': project_data, 'task_count': len(task_data)},
        )

    def _execute_production_plan_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        plan = ProductionPlan.objects.get(id=params['plan_id'])
        tasks = ProductionTask.objects.filter(plan=plan)[:10]
        raw_result = default_production_analysis_tool.optimize_plan(
            {
                'name': plan.name,
                'start_time': plan.plan_start_date.strftime('%Y-%m-%d') if plan.plan_start_date else '',
                'end_time': plan.plan_end_date.strftime('%Y-%m-%d') if plan.plan_end_date else '',
                'priority': plan.priority,
            },
            [{'name': task.name, 'status': task.status} for task in tasks],
        )
        return build_business_ai_result(
            raw_result,
            scenario='production_optimization',
            source_refs=[{'type': 'production_plan', 'id': plan.id}],
            raw_input={'plan_id': plan.id, 'task_count': len(tasks)},
        )

    def _execute_inventory_risk_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        summary = build_inventory_analysis_summary()
        risk_rows = summary.get('risk_rows', [])
        top_rows = risk_rows[:5]
        raw_result = {
            'summary': f"共扫描 {summary.get('total_items', 0)} 个库存物料，其中高风险 {summary.get('high_risk_count', 0)} 个，中风险 {summary.get('medium_risk_count', 0)} 个。",
            'risk_level': 'high' if summary.get('high_risk_count', 0) else 'medium' if summary.get('medium_risk_count', 0) else 'low',
            'risk_points': [
                f"{row['item'].name}: {row['status']}，可用库存 {row['available_quantity']}"
                for row in top_rows
            ],
            'suggestions': [
                '优先修正高风险物料的安全库存与再订货点',
                '结合近 30 天出入库情况校准阈值',
            ],
            'recommended_action': 'follow_up',
            'confidence': 0.92,
        }
        return build_business_ai_result(raw_result, scenario='inventory_forecast', source_refs=[{'type': 'inventory'}], raw_input=summary)

    def _execute_contract_quick_review(self, user, params: dict[str, Any]) -> dict[str, Any]:
        from apps.contract.models import Contract

        contract = Contract.objects.get(id=params['contract_id'])
        raw_result = contract_review_service.quick_review(contract.content or contract.remark or contract.name or '')
        return build_business_ai_result(
            raw_result,
            scenario='contract_risk_analysis',
            source_refs=[{'type': 'contract', 'id': contract.id}],
            raw_input={'contract_id': contract.id, 'name': contract.name},
        )

    def _execute_finance_entry_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        amount = Decimal(str(params.get('amount') or 0))
        remark = str(params.get('remark') or '').strip()
        raw_result = {
            'summary': f'金额 {amount:.2f}，业务日期 {params.get("record_date")}，可用于财务录入。',
            'risk_level': 'medium' if not remark else 'low',
            'risk_points': ['备注为空，建议补充业务背景'] if not remark else [],
            'suggestions': [
                '确认关联客户、项目或发票编号',
                '保留付款 / 回款凭证附件',
            ],
            'recommended_action': 'manual_review' if not remark else 'follow_up',
            'confidence': 0.88,
        }
        return build_business_ai_result(raw_result, scenario='general', source_refs=[{'type': 'finance'}], raw_input=params)

    def _resolve_options(self, field_config: dict[str, Any]) -> list[dict[str, Any]]:
        if field_config.get('static_options'):
            return list(field_config['static_options'])
        provider = field_config.get('options_provider')
        if provider == 'customers':
            return self._safe_option_queryset(Customer.objects.filter(delete_time=0).order_by('-id')[:50], label_field='name')
        if provider == 'projects':
            return self._safe_option_queryset(Project.objects.filter(delete_time__isnull=True).order_by('-id')[:50], label_field='name')
        if provider == 'production_plans':
            return self._safe_option_queryset(ProductionPlan.objects.order_by('-id')[:50], label_field='name')
        if provider == 'inventory_items':
            return self._safe_option_queryset(InventoryItem.objects.order_by('code')[:60], label_field='name', extra_field='code')
        if provider == 'contracts':
            from apps.contract.models import Contract

            return self._safe_option_queryset(Contract.objects.order_by('-id')[:50], label_field='name', extra_field='code')
        if provider == 'employees':
            from apps.user.models import Admin

            return self._safe_option_queryset(Admin.objects.order_by('-id')[:60], label_field='name')
        return []

    def _safe_option_queryset(self, queryset, label_field: str, extra_field: str | None = None) -> list[dict[str, Any]]:
        items = []
        try:
            for item in queryset:
                label = getattr(item, label_field, '') or getattr(item, 'username', '') or f'#{item.id}'
                if extra_field and getattr(item, extra_field, ''):
                    label = f"{label} ({getattr(item, extra_field)})"
                items.append({'value': str(item.id), 'label': str(label)})
        except Exception:
            return []
        return items

    def _get_agent(self, agent_id: str) -> AgentDefinition:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise KeyError(f'未找到企业智能体: {agent_id}') from exc

    def _get_action(self, agent: AgentDefinition, action_id: str) -> AgentActionDefinition:
        for action in agent.actions:
            if action.id == action_id:
                return action
        raise KeyError(f'未找到智能体动作: {agent.id}.{action_id}')

    def _without_empty(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in payload.items()
            if value not in (None, '', [])
        }

    def _text_field(self, field_id: str, label: str, required: bool = False) -> dict[str, Any]:
        return {'id': field_id, 'name': field_id, 'label': label, 'type': 'text', 'required': required}

    def _textarea_field(self, field_id: str, label: str, required: bool = False) -> dict[str, Any]:
        return {'id': field_id, 'name': field_id, 'label': label, 'type': 'textarea', 'required': required}

    def _date_field(self, field_id: str, label: str, required: bool = False) -> dict[str, Any]:
        return {'id': field_id, 'name': field_id, 'label': label, 'type': 'date', 'required': required}

    def _number_field(self, field_id: str, label: str, required: bool = False) -> dict[str, Any]:
        return {'id': field_id, 'name': field_id, 'label': label, 'type': 'number', 'required': required}

    def _select_field(
        self,
        field_id: str,
        label: str,
        options_provider: str | None = None,
        required: bool = False,
        static_options: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            'id': field_id,
            'name': field_id,
            'label': label,
            'type': 'select',
            'required': required,
            'options_provider': options_provider,
            'static_options': static_options or [],
        }


enterprise_agent_service = EnterpriseAgentService()
