from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
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
from apps.approval.models import ApprovalTask
from apps.contract.contract_review_service import contract_review_service
from apps.customer.models import Contact, Customer, FollowRecord
from apps.customer.models import CustomerOrder
from apps.department.models import Department
from apps.disk.models import DiskFile, DiskFolder, DiskShare
from apps.inventory.models import InventoryItem
from apps.message.models import Message
from apps.oa.models import MeetingRecord
from apps.personal.models import PersonalTask, WorkReport
from apps.production.ai_views import default_production_analysis_tool
from apps.production.models import ProductionPlan, ProductionTask
from apps.project.risk_analysis import project_risk_analysis_service, serialize_risk_analysis
from apps.project.models import Project, Task, WorkHour
from apps.supply_chain.services.inventory_analysis_service import build_inventory_analysis_summary
from apps.system.models import Document, DocumentCategory, Notice
from apps.ai.utils.analysis_tools import default_customer_analysis_tool
from apps.user.models import Admin, Position


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
    module: str
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
            'module_breakdown': self._build_module_breakdown(enterprise_agents),
            'enterprise_agents': enterprise_agents,
            'foundation_resources': self._build_foundation_resources(),
            'recent_operations': self._get_recent_operations(),
        }

    def get_agent_detail(self, agent_id: str, user) -> dict[str, Any]:
        agent = self._get_agent(agent_id)
        return {
            'agent': {
                **self._serialize_agent(agent),
                'actions': [self._serialize_action(agent.id, action, user=user, with_options=True) for action in agent.actions],
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
                module='客户管理',
                domain='客户 / 销售',
                icon='layui-icon-dialogue',
                status='online',
                audience='销售、客服、销售主管',
                highlights=['客户画像', '跟进建议', '联系人补齐', '跟进落账'],
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
                    AgentActionDefinition(
                        id='log_followup_record',
                        label='登记跟进记录',
                        description='把电话、拜访或微信沟通沉淀为正式跟进记录。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='followup',
                        operation='create',
                        fields=[
                            self._select_field('customer_id', '客户', 'customers', required=True),
                            self._select_field(
                                'follow_type',
                                '跟进方式',
                                static_options=[
                                    {'value': 'phone', 'label': '电话'},
                                    {'value': 'visit', 'label': '拜访'},
                                    {'value': 'wechat', 'label': '微信'},
                                ],
                            ),
                            self._textarea_field('content', '跟进内容', required=True),
                            self._datetime_local_field('next_follow_time', '下次跟进时间'),
                        ],
                    ),
                    AgentActionDefinition(
                        id='create_customer_contact',
                        label='新增客户联系人',
                        description='补齐关键客户联系人，避免销售线索卡在单点联系。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='contact',
                        operation='create',
                        fields=[
                            self._select_field('customer_id', '客户', 'customers', required=True),
                            self._text_field('contact_person', '联系人姓名', required=True),
                            self._text_field('phone', '联系电话', required=True),
                            self._text_field('position', '职位'),
                            self._text_field('email', '邮箱'),
                            self._select_field(
                                'is_primary',
                                '设为主联系人',
                                static_options=[
                                    {'value': '1', 'label': '是'},
                                    {'value': '0', 'label': '否'},
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='project_risk_agent',
                name='项目风险智能体',
                description='识别项目延期、资源与质量风险，并能快速拆出整改任务。',
                module='项目管理',
                domain='项目 / 管理',
                icon='layui-icon-rate-half',
                status='online',
                audience='项目经理、PMO、部门负责人',
                highlights=['风险评估', '风险点汇总', '整改任务', '状态调整'],
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
                    AgentActionDefinition(
                        id='adjust_project_status',
                        label='调整项目状态',
                        description='对高风险项目进行状态、进度和优先级调整，先预览再执行。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='project',
                        operation='update',
                        fields=[
                            self._select_field('project_id', '项目', 'projects', required=True),
                            self._select_field(
                                'status',
                                '项目状态',
                                static_options=[
                                    {'value': '1', 'label': '未开始'},
                                    {'value': '2', 'label': '进行中'},
                                    {'value': '3', 'label': '已完成'},
                                    {'value': '4', 'label': '已关闭'},
                                    {'value': '5', 'label': '已暂停'},
                                ],
                            ),
                            self._number_field('progress', '完成进度(%)'),
                            self._select_field(
                                'priority',
                                '优先级',
                                static_options=[
                                    {'value': '1', 'label': '低'},
                                    {'value': '2', 'label': '中'},
                                    {'value': '3', 'label': '高'},
                                    {'value': '4', 'label': '紧急'},
                                ],
                            ),
                            self._date_field('end_date', '计划结束日期'),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='production_dispatch_agent',
                name='生产排产智能体',
                description='读取生产计划与任务负载，给出排产优化建议，并支持关键计划调整。',
                module='生产管理',
                domain='生产',
                icon='layui-icon-chart',
                status='online',
                audience='生产计划员、车间主管、运营经理',
                highlights=['排产优化', '瓶颈识别', '计划调整', '任务补建'],
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
                    AgentActionDefinition(
                        id='create_production_task',
                        label='补建生产任务',
                        description='对已确定的计划快速补建执行任务。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='production_task',
                        operation='create',
                        fields=[
                            self._select_field('plan_id', '生产计划', 'production_plans', required=True),
                            self._text_field('name', '任务名称', required=True),
                            self._text_field('code', '任务编号', required=True),
                            self._number_field('procedure_id', '工序ID', required=True),
                            self._number_field('quantity', '计划数量', required=True),
                            self._datetime_local_field('plan_start_time', '计划开始时间', required=True),
                            self._datetime_local_field('plan_end_time', '计划结束时间', required=True),
                            self._select_field('assignee_id', '负责人', 'employees'),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='inventory_health_agent',
                name='库存健康智能体',
                description='汇总库存风险、缺口和阈值设置，帮助供应链团队快速修正库存策略。',
                module='供应链管理',
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
                module='合同管理',
                domain='合同 / 法务',
                icon='layui-icon-file-b',
                status='online',
                audience='法务、销售内勤、合同管理员',
                highlights=['条款风险', '签约建议', '交叉核验', '审批确认'],
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
                    AgentActionDefinition(
                        id='approve_contract',
                        label='提交合同通过',
                        description='对已完成复核的合同发起通过动作，执行前给出变更预览。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='contract',
                        operation='approve',
                        fields=[
                            self._select_field('contract_id', '合同', 'contracts', required=True),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='finance_ops_agent',
                name='财务执行智能体',
                description='辅助收付款录入与字段校验，将高风险财务动作纳入预览确认流程。',
                module='财务管理',
                domain='财务',
                icon='layui-icon-rmb',
                status='online',
                audience='财务专员、出纳、财务主管',
                highlights=['字段校验', '付款录入', '回款录入', '报销审批'],
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
                    AgentActionDefinition(
                        id='approve_expense_record',
                        label='审批报销记录',
                        description='对报销单执行审批确认，适合财务复核后的正式通过。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='finance',
                        operation='approve',
                        context={'model': 'expense'},
                        fields=[
                            self._number_field('expense_id', '报销ID', required=True),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='approval_workbench_agent',
                name='审批办理智能体',
                description='集中处理待办审批，快速识别积压项，并将通过/驳回动作纳入可审计执行链路。',
                module='审批中心',
                domain='审批 / 流程',
                icon='layui-icon-auz',
                status='online',
                audience='审批人、部门负责人、流程管理员',
                highlights=['积压识别', '审批通过', '审批驳回'],
                actions=[
                    AgentActionDefinition(
                        id='approval_backlog_analysis',
                        label='待办积压分析',
                        description='识别待办审批中的高优先积压项和超时风险。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='approval_backlog_analysis',
                    ),
                    AgentActionDefinition(
                        id='approve_approval_task',
                        label='通过审批任务',
                        description='对待办审批进行通过处理，先生成变更预览。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='approval_task',
                        operation='approve',
                        fields=[
                            self._select_field('task_id', '审批任务', 'approval_tasks', required=True),
                            self._textarea_field('comment', '审批意见'),
                        ],
                    ),
                    AgentActionDefinition(
                        id='reject_approval_task',
                        label='驳回审批任务',
                        description='对待办审批进行驳回处理，执行前先确认。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='approval_task',
                        operation='reject',
                        fields=[
                            self._select_field('task_id', '审批任务', 'approval_tasks', required=True),
                            self._textarea_field('comment', '驳回原因', required=True),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='workforce_planning_agent',
                name='组织人效智能体',
                description='围绕组织编制、岗位配置和人员投入给出结构化分析，并支持快速补建岗位和部门。',
                module='人事管理',
                domain='人事 / 组织',
                icon='layui-icon-user',
                status='online',
                audience='HRBP、部门负责人、人事经理',
                highlights=['组织结构', '岗位缺口', '岗位补建', '部门新增'],
                actions=[
                    AgentActionDefinition(
                        id='workforce_structure_analysis',
                        label='组织结构分析',
                        description='统计在岗人数、启用岗位和部门覆盖情况，识别编制压力。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='workforce_structure_analysis',
                    ),
                    AgentActionDefinition(
                        id='create_position',
                        label='新增岗位',
                        description='低风险补建岗位，快速完成组织编制准备。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='position',
                        operation='create',
                        fields=[
                            self._text_field('title', '岗位名称', required=True),
                            self._select_field('did', '所属部门', 'departments'),
                            self._textarea_field('desc', '岗位说明'),
                            self._number_field('sort', '排序值'),
                        ],
                    ),
                    AgentActionDefinition(
                        id='create_department',
                        label='新增部门',
                        description='对组织结构新增部门，先预览负责人和状态变更。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='department',
                        operation='create',
                        fields=[
                            self._text_field('name', '部门名称', required=True),
                            self._number_field('pid', '上级部门ID'),
                            self._text_field('code', '部门编码'),
                            self._select_field('manager_id', '负责人', 'employees'),
                            self._text_field('phone', '联系电话'),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='meeting_coordination_agent',
                name='会议协同智能体',
                description='面向行政与管理团队，识别会议排期压力并快速落地会议记录与协同安排。',
                module='行政办公',
                domain='行政 / 会议',
                icon='layui-icon-template-1',
                status='online',
                audience='行政专员、部门助理、管理层',
                highlights=['排期扫描', '会议创建', '协同安排'],
                actions=[
                    AgentActionDefinition(
                        id='meeting_schedule_analysis',
                        label='会议排期扫描',
                        description='识别近期会议密集时段和潜在排期冲突。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='meeting_schedule_analysis',
                    ),
                    AgentActionDefinition(
                        id='create_meeting',
                        label='创建会议记录',
                        description='对正式会议进行创建登记，先看预览再执行。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='meeting',
                        operation='create',
                        fields=[
                            self._text_field('title', '会议主题', required=True),
                            self._datetime_local_field('meeting_date', '会议开始时间', required=True),
                            self._datetime_local_field('meeting_end_time', '会议结束时间', required=True),
                            self._text_field('location', '会议地点'),
                            self._select_field('host_id', '主持人', 'employees'),
                            self._select_field('recorder_id', '记录人', 'employees'),
                            self._textarea_field('agenda', '会议议程'),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='document_flow_agent',
                name='公文流转智能体',
                description='围绕企业公文起草、审核发布和积压扫描提供固定入口，减少行政流转过程中的断点。',
                module='行政办公',
                domain='行政 / 公文',
                icon='layui-icon-read',
                status='online',
                audience='行政专员、办公室主任、部门负责人',
                highlights=['流转扫描', '公文起草', '发布确认'],
                actions=[
                    AgentActionDefinition(
                        id='document_flow_analysis',
                        label='公文流转扫描',
                        description='统计待审核、待发布和高优先级公文，识别当前流转压力。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='document_flow_analysis',
                    ),
                    AgentActionDefinition(
                        id='create_document',
                        label='新建公文草稿',
                        description='快速起草标准公文，直接落地为正式草稿记录。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='document',
                        operation='create',
                        fields=[
                            self._text_field('title', '公文标题', required=True),
                            self._text_field('document_number', '公文编号', required=True),
                            self._select_field('category_id', '公文分类', 'document_categories', required=True),
                            self._textarea_field('content', '公文内容', required=True),
                            self._textarea_field('summary', '公文摘要'),
                            self._select_field('department_id', '起草部门', 'departments'),
                            self._select_field(
                                'urgency',
                                '紧急程度',
                                static_options=[
                                    {'value': 'normal', 'label': '普通'},
                                    {'value': 'urgent', 'label': '紧急'},
                                    {'value': 'very_urgent', 'label': '特急'},
                                ],
                            ),
                            self._select_field(
                                'security_level',
                                '密级',
                                static_options=[
                                    {'value': 'public', 'label': '公开'},
                                    {'value': 'internal', 'label': '内部'},
                                    {'value': 'confidential', 'label': '机密'},
                                    {'value': 'secret', 'label': '秘密'},
                                ],
                            ),
                        ],
                    ),
                    AgentActionDefinition(
                        id='publish_document',
                        label='发布公文',
                        description='对已完成审批的公文进行发布，执行前先查看变更预览。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='document',
                        operation='publish',
                        fields=[
                            self._select_field('document_id', '待发布公文', 'documents', required=True),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='admin_communication_agent',
                name='公告触达智能体',
                description='统一承接公告发布与消息触达，确保重要信息能在企业内部快速落地。',
                module='行政办公',
                domain='行政 / 公告消息',
                icon='layui-icon-notice',
                status='online',
                audience='行政办公、运营、人事、管理者',
                highlights=['触达分析', '公告发布', '定向消息'],
                actions=[
                    AgentActionDefinition(
                        id='communication_delivery_analysis',
                        label='触达压力分析',
                        description='统计近期公告与消息发出情况，识别过载或空白时段。',
                        execution_mode='analysis',
                        risk_level='low',
                        handler_name='communication_delivery_analysis',
                    ),
                    AgentActionDefinition(
                        id='publish_notice',
                        label='发布公告',
                        description='对全员公告进行预览确认，控制广域通知风险。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='notice',
                        operation='create',
                        fields=[
                            self._text_field('title', '公告标题', required=True),
                            self._textarea_field('content', '公告内容', required=True),
                            self._text_field('notice_type', '公告类型'),
                            self._select_field(
                                'is_top',
                                '是否置顶',
                                static_options=[
                                    {'value': '1', 'label': '是'},
                                    {'value': '0', 'label': '否'},
                                ],
                            ),
                        ],
                    ),
                    AgentActionDefinition(
                        id='send_message',
                        label='发送定向消息',
                        description='发送单点或定向业务消息，适合催办、提醒和协同指令。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='message',
                        operation='create',
                        fields=[
                            self._text_field('title', '消息标题', required=True),
                            self._textarea_field('content', '消息内容', required=True),
                            self._select_field('user_id', '接收人', 'employees'),
                            self._number_field('priority', '优先级'),
                            self._text_field('action_url', '跳转链接'),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='disk_collaboration_agent',
                name='网盘协同智能体',
                description='围绕文件资产整理、命名治理和安全分享提供标准化智能入口，减少网盘协同中的重复动作。',
                module='企业网盘',
                domain='网盘 / 文件协同',
                icon='layui-icon-file',
                status='online',
                audience='行政、项目经理、销售支持、全员协同',
                highlights=['资产扫描', '文件改名', '外发分享'],
                actions=[
                    AgentActionDefinition(
                        id='disk_asset_analysis',
                        label='网盘资产扫描',
                        description='汇总文件、文件夹和分享使用情况，识别高频协同与过期资产。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='disk_asset_analysis',
                    ),
                    AgentActionDefinition(
                        id='rename_disk_file',
                        label='重命名网盘文件',
                        description='对现有网盘文件做低风险命名修正，适合整理归档。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='disk',
                        operation='update',
                        context={'model': 'file'},
                        fields=[
                            self._select_field('file_id', '文件', 'disk_files', required=True),
                            self._text_field('name', '新文件名', required=True),
                        ],
                    ),
                    AgentActionDefinition(
                        id='share_disk_file',
                        label='创建文件分享',
                        description='对网盘文件生成对外分享，先预览权限和分享设置再执行。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='disk',
                        operation='create',
                        context={'model': 'share', 'share_type': 'file'},
                        fields=[
                            self._select_field('file_id', '文件', 'disk_files', required=True),
                            self._select_field(
                                'permission_type',
                                '分享权限',
                                static_options=[
                                    {'value': 'view', 'label': '仅查看'},
                                    {'value': 'download', 'label': '可下载'},
                                    {'value': 'edit', 'label': '可编辑'},
                                ],
                            ),
                            self._select_field(
                                'allow_download',
                                '允许下载',
                                static_options=[
                                    {'value': '1', 'label': '是'},
                                    {'value': '0', 'label': '否'},
                                ],
                            ),
                            self._number_field('access_limit', '访问次数限制'),
                            self._number_field('download_limit', '下载次数限制'),
                            self._text_field('password', '提取密码'),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='personal_execution_agent',
                name='个人执行智能体',
                description='帮助员工围绕待办、汇报和个人节奏进行自驱管理，把零散执行动作沉淀成结构化记录。',
                module='个人办公',
                domain='个人 / 执行',
                icon='layui-icon-engine',
                status='online',
                audience='全员、主管、项目成员',
                highlights=['待办聚焦', '任务创建', '汇报提交'],
                actions=[
                    AgentActionDefinition(
                        id='personal_focus_analysis',
                        label='个人待办聚焦',
                        description='识别逾期任务、高优先事项和未提交汇报。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='personal_focus_analysis',
                    ),
                    AgentActionDefinition(
                        id='create_personal_task',
                        label='创建个人任务',
                        description='快速登记个人待办，形成持续执行清单。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='personal_task',
                        operation='create',
                        fields=[
                            self._text_field('title', '任务标题', required=True),
                            self._textarea_field('description', '任务描述'),
                            self._select_field(
                                'priority',
                                '优先级',
                                static_options=[
                                    {'value': '1', 'label': '低'},
                                    {'value': '2', 'label': '中'},
                                    {'value': '3', 'label': '高'},
                                    {'value': '4', 'label': '紧急'},
                                ],
                            ),
                            self._datetime_local_field('due_date', '截止时间'),
                            self._number_field('estimated_hours', '预估工时'),
                        ],
                    ),
                    AgentActionDefinition(
                        id='submit_work_report',
                        label='提交工作汇报',
                        description='对已填写完成的日报/周报执行提交动作。',
                        execution_mode='direct',
                        risk_level='low',
                        resource='work_report',
                        operation='submit',
                        fields=[
                            self._select_field('report_id', '工作汇报', 'work_reports', required=True),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='employee_masterdata_agent',
                name='员工主数据智能体',
                description='覆盖员工主数据新增、状态调整和信息体检，帮助人事团队把员工资料维护为正式可审计记录。',
                module='人事管理',
                domain='人事 / 员工主数据',
                icon='layui-icon-username',
                status='online',
                audience='HR、HRBP、用人主管',
                highlights=['主数据体检', '员工新增', '状态调整'],
                actions=[
                    AgentActionDefinition(
                        id='employee_masterdata_analysis',
                        label='员工主数据体检',
                        description='统计在岗、锁定、缺岗位和联系方式缺失员工，识别主数据风险。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='employee_masterdata_analysis',
                    ),
                    AgentActionDefinition(
                        id='create_employee',
                        label='新增员工档案',
                        description='为新员工建立基础主数据档案，快速完成入库。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='employee',
                        operation='create',
                        fields=[
                            self._text_field('username', '登录账号', required=True),
                            self._text_field('name', '员工姓名', required=True),
                            self._text_field('mobile', '手机号'),
                            self._text_field('email', '邮箱'),
                            self._select_field('did', '所属部门', 'departments'),
                            self._select_field('position_id', '岗位', 'positions'),
                            self._text_field('job_number', '工号'),
                            self._text_field('work_location', '工作地点'),
                        ],
                    ),
                    AgentActionDefinition(
                        id='adjust_employee_status',
                        label='调整员工状态',
                        description='对员工启停用和锁定状态进行调整，执行前先确认。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='employee',
                        operation='update',
                        fields=[
                            self._select_field('employee_id', '员工', 'employees', required=True),
                            self._select_field(
                                'status',
                                '员工状态',
                                static_options=[
                                    {'value': '1', 'label': '启用'},
                                    {'value': '0', 'label': '停用'},
                                ],
                            ),
                            self._select_field(
                                'is_lock',
                                '锁定状态',
                                static_options=[
                                    {'value': '0', 'label': '正常'},
                                    {'value': '1', 'label': '锁定'},
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            AgentDefinition(
                id='order_fulfillment_agent',
                name='订单履约智能体',
                description='聚焦客户订单的履约状态、财务同步和交付压力，帮助业务团队尽快推进关键订单。',
                module='客户管理',
                domain='订单 / 履约',
                icon='layui-icon-cart',
                status='online',
                audience='销售、交付、运营、财务协同',
                highlights=['履约扫描', '订单补建', '财务联动'],
                actions=[
                    AgentActionDefinition(
                        id='order_delivery_analysis',
                        label='订单履约扫描',
                        description='识别待同步财务、待开票和待处理订单。',
                        execution_mode='analysis',
                        risk_level='medium',
                        handler_name='order_delivery_analysis',
                    ),
                    AgentActionDefinition(
                        id='create_sales_order',
                        label='创建销售订单',
                        description='正式创建客户订单，先预览订单和财务联动变更。',
                        execution_mode='confirm',
                        risk_level='high',
                        resource='order',
                        operation='create',
                        fields=[
                            self._select_field('customer_id', '客户', 'customers', required=True),
                            self._text_field('order_number', '订单编号', required=True),
                            self._text_field('product_name', '产品名称', required=True),
                            self._number_field('amount', '订单金额', required=True),
                            self._date_field('order_date', '订单日期', required=True),
                            self._textarea_field('description', '订单描述'),
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
            'module': agent.module,
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

    def _serialize_action(self, agent_id: str, action: AgentActionDefinition, user=None, with_options: bool = False) -> dict[str, Any]:
        fields = []
        for field_config in action.fields:
            item = dict(field_config)
            if with_options and item.get('type') == 'select':
                item['options'] = self._resolve_options(item, user=user)
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
            'module_count': len({agent['module'] for agent in enterprise_agents}),
            'analysis_action_count': analysis_action_count,
            'direct_action_count': direct_action_count,
            'confirm_action_count': confirm_action_count,
            'recent_execution_count': len(recent_operations),
            'pending_confirmation_count': sum(1 for item in recent_operations if item['status'] == 'preview'),
        }

    def _build_module_breakdown(self, enterprise_agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for agent in enterprise_agents:
            bucket = buckets.setdefault(agent['module'], {
                'module': agent['module'],
                'agent_count': 0,
                'analysis_count': 0,
                'direct_count': 0,
                'confirm_count': 0,
            })
            bucket['agent_count'] += 1
            bucket['analysis_count'] += agent['analysis_count']
            bucket['direct_count'] += agent['direct_count']
            bucket['confirm_count'] += agent['confirm_count']
        return sorted(buckets.values(), key=lambda item: (-item['agent_count'], item['module']))

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

    def _build_action_log_followup_record(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='followup',
            operation='create',
            changes=self._without_empty({
                'customer_id': params.get('customer_id'),
                'follow_type': params.get('follow_type'),
                'content': params.get('content'),
                'next_follow_time': params.get('next_follow_time'),
            }),
        )

    def _build_action_create_customer_contact(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='contact',
            operation='create',
            changes=self._without_empty({
                'customer_id': params.get('customer_id'),
                'contact_person': params.get('contact_person'),
                'phone': params.get('phone'),
                'position': params.get('position'),
                'email': params.get('email'),
                'is_primary': self._normalize_bool_string(params.get('is_primary')),
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

    def _build_action_adjust_project_status(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='project',
            operation='update',
            object_ids=[params.get('project_id')] if params.get('project_id') not in (None, '') else [],
            changes=self._without_empty({
                'status': params.get('status'),
                'progress': params.get('progress'),
                'priority': params.get('priority'),
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

    def _build_action_create_production_task(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='production_task',
            operation='create',
            changes=self._without_empty({
                'plan_id': params.get('plan_id'),
                'name': params.get('name'),
                'code': params.get('code'),
                'procedure_id': params.get('procedure_id'),
                'quantity': params.get('quantity'),
                'plan_start_time': params.get('plan_start_time'),
                'plan_end_time': params.get('plan_end_time'),
                'assignee_id': params.get('assignee_id'),
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

    def _build_action_approve_contract(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='contract',
            operation='approve',
            object_ids=[params.get('contract_id')] if params.get('contract_id') not in (None, '') else [],
            changes={'check_status': 2},
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

    def _build_action_approve_expense_record(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='finance',
            operation='approve',
            object_ids=[params.get('expense_id')] if params.get('expense_id') not in (None, '') else [],
            changes={'check_status': 2},
            context=action.context,
        )

    def _build_action_approve_approval_task(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='approval_task',
            operation='approve',
            object_ids=[params.get('task_id')] if params.get('task_id') not in (None, '') else [],
            changes=self._without_empty({'comment': params.get('comment')}),
        )

    def _build_action_reject_approval_task(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='approval_task',
            operation='reject',
            object_ids=[params.get('task_id')] if params.get('task_id') not in (None, '') else [],
            changes=self._without_empty({'comment': params.get('comment')}),
        )

    def _build_action_create_position(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='position',
            operation='create',
            changes=self._without_empty({
                'title': params.get('title'),
                'did': params.get('did'),
                'desc': params.get('desc'),
                'sort': params.get('sort'),
            }),
        )

    def _build_action_create_department(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='department',
            operation='create',
            changes=self._without_empty({
                'name': params.get('name'),
                'pid': params.get('pid'),
                'code': params.get('code'),
                'manager_id': params.get('manager_id'),
                'phone': params.get('phone'),
            }),
        )

    def _build_action_create_meeting(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='meeting',
            operation='create',
            changes=self._without_empty({
                'title': params.get('title'),
                'meeting_date': params.get('meeting_date'),
                'meeting_end_time': params.get('meeting_end_time'),
                'location': params.get('location'),
                'host_id': params.get('host_id'),
                'recorder_id': params.get('recorder_id'),
                'agenda': params.get('agenda'),
            }),
        )

    def _build_action_publish_notice(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='notice',
            operation='create',
            changes=self._without_empty({
                'title': params.get('title'),
                'content': params.get('content'),
                'notice_type': params.get('notice_type'),
                'is_top': self._normalize_bool_string(params.get('is_top')),
                'is_published': True,
            }),
        )

    def _build_action_send_message(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='message',
            operation='create',
            changes=self._without_empty({
                'title': params.get('title'),
                'content': params.get('content'),
                'user_id': params.get('user_id'),
                'priority': params.get('priority'),
                'action_url': params.get('action_url'),
            }),
        )

    def _build_action_create_personal_task(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='personal_task',
            operation='create',
            changes=self._without_empty({
                'title': params.get('title'),
                'description': params.get('description'),
                'priority': params.get('priority'),
                'due_date': params.get('due_date'),
                'estimated_hours': params.get('estimated_hours'),
            }),
        )

    def _build_action_submit_work_report(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='work_report',
            operation='submit',
            object_ids=[params.get('report_id')] if params.get('report_id') not in (None, '') else [],
        )

    def _build_action_create_sales_order(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='order',
            operation='create',
            changes=self._without_empty({
                'customer_id': params.get('customer_id'),
                'order_number': params.get('order_number'),
                'product_name': params.get('product_name'),
                'amount': params.get('amount'),
                'order_date': params.get('order_date'),
                'description': params.get('description'),
            }),
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

    def _build_action_create_document(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='document',
            operation='create',
            changes=self._without_empty({
                'title': params.get('title'),
                'document_number': params.get('document_number'),
                'category_id': params.get('category_id'),
                'content': params.get('content'),
                'summary': params.get('summary'),
                'department_id': params.get('department_id'),
                'urgency': params.get('urgency'),
                'security_level': params.get('security_level'),
            }),
        )

    def _build_action_publish_document(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='document',
            operation='publish',
            object_ids=[params.get('document_id')] if params.get('document_id') not in (None, '') else [],
        )

    def _build_action_rename_disk_file(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='disk',
            operation='update',
            object_ids=[params.get('file_id')] if params.get('file_id') not in (None, '') else [],
            changes=self._without_empty({
                'name': params.get('name'),
            }),
            context=action.context,
        )

    def _build_action_share_disk_file(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='disk',
            operation='create',
            object_ids=[params.get('file_id')] if params.get('file_id') not in (None, '') else [],
            changes=self._without_empty({
                'permission_type': params.get('permission_type'),
                'allow_download': self._normalize_bool_string(params.get('allow_download')),
                'access_limit': params.get('access_limit'),
                'download_limit': params.get('download_limit'),
                'password': params.get('password'),
            }),
            context=action.context,
        )

    def _build_action_create_employee(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        position_name = ''
        if params.get('position_id') not in (None, ''):
            position_name = Position.objects.filter(id=params.get('position_id')).values_list('title', flat=True).first() or ''
        return AIActionRequest(
            resource='employee',
            operation='create',
            changes=self._without_empty({
                'username': params.get('username'),
                'name': params.get('name'),
                'mobile': params.get('mobile'),
                'email': params.get('email'),
                'did': params.get('did'),
                'position_id': params.get('position_id'),
                'position_name': position_name,
                'job_number': params.get('job_number'),
                'work_location': params.get('work_location'),
            }),
        )

    def _build_action_adjust_employee_status(self, agent_id: str, action: AgentActionDefinition, params: dict[str, Any]) -> AIActionRequest:
        return AIActionRequest(
            resource='employee',
            operation='update',
            object_ids=[params.get('employee_id')] if params.get('employee_id') not in (None, '') else [],
            changes=self._without_empty({
                'status': params.get('status'),
                'is_lock': params.get('is_lock'),
            }),
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
        analysis = project_risk_analysis_service.analyze_project(
            project,
            trigger_source='agent_center',
            triggered_by=user,
        )
        return serialize_risk_analysis(analysis)

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

    def _execute_approval_backlog_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        queryset = ApprovalTask.objects.filter(status='pending').select_related('approval', 'step', 'handler').order_by('created_at')
        if not getattr(user, 'is_superuser', False):
            queryset = queryset.filter(handler=user)
        total_pending = queryset.count()
        stale_count = queryset.filter(created_at__lt=timezone.now() - timedelta(days=2)).count()
        top_items = list(queryset[:5])
        raw_result = {
            'summary': f'当前待处理审批 {total_pending} 条，其中超 48 小时未处理 {stale_count} 条。',
            'risk_level': 'high' if stale_count else 'medium' if total_pending >= 5 else 'low',
            'risk_points': [
                f"{item.approval.title} / {item.step.step_name}"
                for item in top_items
            ],
            'suggestions': [
                '优先处理超 48 小时未办结审批',
                '对高金额或关键业务审批保留明确意见说明',
            ],
            'confidence': 0.9,
        }
        return build_business_ai_result(raw_result, scenario='approval_assessment', source_refs=[{'type': 'approval_task'}], raw_input={'pending_count': total_pending})

    def _execute_workforce_structure_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        active_departments = Department.objects.filter(status=1).count()
        active_positions = Position.objects.filter(status=1).count()
        active_employees = Admin.objects.filter(status=1).count()
        occupied_position_ids = {
            position_id for position_id in Admin.objects.exclude(position_id__in=(None, 0)).values_list('position_id', flat=True)
        }
        vacant_positions = Position.objects.filter(status=1).exclude(id__in=occupied_position_ids)[:5]
        vacancy_gap = max(active_positions - active_employees, 0)
        raw_result = {
            'summary': f'当前启用部门 {active_departments} 个、启用岗位 {active_positions} 个、在岗员工 {active_employees} 人。',
            'risk_level': 'medium' if vacancy_gap else 'low',
            'risk_points': [f'岗位空缺：{item.title}' for item in vacant_positions],
            'suggestions': [
                '优先补齐长时间空缺的关键岗位',
                '新建部门前同步明确负责人和岗位配置',
            ],
            'confidence': 0.86,
        }
        return build_business_ai_result(raw_result, scenario='general', source_refs=[{'type': 'employee'}], raw_input={'department_count': active_departments, 'position_count': active_positions})

    def _execute_meeting_schedule_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        now = timezone.now()
        queryset = MeetingRecord.objects.filter(is_deleted=False, meeting_date__gte=now).order_by('meeting_date')
        today_count = queryset.filter(meeting_date__date=now.date()).count()
        week_count = queryset.filter(meeting_date__date__lte=now.date() + timedelta(days=7)).count()
        top_items = list(queryset[:5])
        raw_result = {
            'summary': f'今日排期会议 {today_count} 场，未来 7 天排期会议 {week_count} 场。',
            'risk_level': 'medium' if today_count >= 4 or week_count >= 12 else 'low',
            'risk_points': [
                f"{item.title} / {item.meeting_date.strftime('%m-%d %H:%M') if item.meeting_date else '未定'}"
                for item in top_items
            ],
            'suggestions': [
                '高密度时段优先合并相近主题会议',
                '关键会议安排固定记录人与纪要责任人',
            ],
            'confidence': 0.84,
        }
        return build_business_ai_result(raw_result, scenario='general', source_refs=[{'type': 'meeting'}], raw_input={'today_count': today_count, 'week_count': week_count})

    def _execute_communication_delivery_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        recent_notices = list(Notice.objects.order_by('-id')[:5])
        recent_messages = list(Message.objects.filter(is_active=True).order_by('-id')[:10])
        raw_result = {
            'summary': f'近期公告 {len(recent_notices)} 条，当前抽样有效消息 {len(recent_messages)} 条。',
            'risk_level': 'medium' if len(recent_messages) >= 10 else 'low',
            'risk_points': [f'公告：{item.title}' for item in recent_notices[:3]],
            'suggestions': [
                '高频通知建议拆分为公告和定向消息两类',
                '重要事项优先使用置顶公告，事务催办使用定向消息',
            ],
            'confidence': 0.81,
        }
        return build_business_ai_result(raw_result, scenario='general', source_refs=[{'type': 'notice'}], raw_input={'notice_count': len(recent_notices)})

    def _execute_document_flow_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        queryset = Document.objects.select_related('category', 'department').order_by('-updated_at')
        total_count = queryset.count()
        pending_count = queryset.filter(status__in=['pending', 'reviewing']).count()
        published_count = queryset.filter(status='published').count()
        urgent_count = queryset.filter(urgency__in=['urgent', 'very_urgent']).count()
        top_items = list(queryset[:5])
        raw_result = {
            'summary': f'当前公文总量 {total_count} 份，待审核/流转 {pending_count} 份，已发布 {published_count} 份，高优先级 {urgent_count} 份。',
            'risk_level': 'high' if pending_count >= 8 else 'medium' if pending_count or urgent_count else 'low',
            'risk_points': [
                f"{item.title} / {item.get_status_display()} / {item.get_urgency_display()}"
                for item in top_items
            ],
            'suggestions': [
                '优先处理待审核且紧急程度为紧急/特急的公文',
                '发布前核对编号、分类和起草部门，避免流转返工',
            ],
            'confidence': 0.85,
        }
        return build_business_ai_result(raw_result, scenario='general', source_refs=[{'type': 'document'}], raw_input={'total_count': total_count, 'pending_count': pending_count})

    def _execute_disk_asset_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        file_queryset = DiskFile.objects.filter(delete_time__isnull=True)
        folder_queryset = DiskFolder.objects.filter(delete_time__isnull=True)
        share_queryset = DiskShare.objects.filter(is_active=True)
        if not getattr(user, 'is_superuser', False):
            file_queryset = file_queryset.filter(owner=user)
            folder_queryset = folder_queryset.filter(owner=user)
            share_queryset = share_queryset.filter(creator=user)

        file_count = file_queryset.count()
        folder_count = folder_queryset.count()
        active_share_count = share_queryset.count()
        expiring_share_count = share_queryset.filter(
            expire_time__isnull=False,
            expire_time__lte=timezone.now() + timedelta(days=7),
        ).count()
        top_files = list(file_queryset.order_by('-update_time')[:5])
        raw_result = {
            'summary': f'当前可用文件 {file_count} 份、文件夹 {folder_count} 个、有效分享 {active_share_count} 条，其中 7 天内到期分享 {expiring_share_count} 条。',
            'risk_level': 'medium' if expiring_share_count or active_share_count >= 20 else 'low',
            'risk_points': [
                f"{item.name} / {item.get_full_path()}"
                for item in top_files
            ],
            'suggestions': [
                '对高频协同文件统一命名规则，减少搜索和版本识别成本',
                '及时清理即将到期或长期无访问的分享链接',
            ],
            'confidence': 0.84,
        }
        return build_business_ai_result(raw_result, scenario='general', source_refs=[{'type': 'disk'}], raw_input={'file_count': file_count, 'share_count': active_share_count})

    def _execute_employee_masterdata_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        queryset = Admin.objects.filter(is_superuser=False)
        active_count = queryset.filter(status=1).count()
        locked_count = queryset.filter(is_lock=1).count()
        no_position_count = queryset.filter(position_id=0).count()
        missing_contact_count = queryset.filter(mobile='', email='').count()
        top_items = list(queryset.order_by('-id')[:5])
        raw_result = {
            'summary': f'当前员工档案 {queryset.count()} 份，在岗 {active_count} 人，锁定 {locked_count} 人，无岗位映射 {no_position_count} 人，联系方式缺失 {missing_contact_count} 人。',
            'risk_level': 'high' if missing_contact_count >= 5 else 'medium' if locked_count or no_position_count else 'low',
            'risk_points': [
                f"{item.name or item.username} / {item.position_name or '未配置岗位'}"
                for item in top_items
            ],
            'suggestions': [
                '新建员工时同步补齐部门、岗位和工号，避免后续流程断链',
                '定期核对停用、锁定和联系方式缺失人员，保证主数据可用性',
            ],
            'confidence': 0.86,
        }
        return build_business_ai_result(raw_result, scenario='general', source_refs=[{'type': 'employee'}], raw_input={'active_count': active_count, 'locked_count': locked_count})

    def _execute_personal_focus_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        task_queryset = PersonalTask.objects.filter(user_id=getattr(user, 'id', 0) or 0)
        report_queryset = WorkReport.objects.filter(user_id=getattr(user, 'id', 0) or 0)
        overdue_count = sum(1 for item in task_queryset if item.is_overdue)
        high_priority_count = task_queryset.filter(priority__gte=3, status__in=['todo', 'in_progress']).count()
        draft_reports = report_queryset.filter(is_submitted=False).count()
        raw_result = {
            'summary': f'当前高优任务 {high_priority_count} 条，逾期任务 {overdue_count} 条，未提交汇报 {draft_reports} 条。',
            'risk_level': 'high' if overdue_count else 'medium' if draft_reports or high_priority_count >= 5 else 'low',
            'risk_points': [
                f'逾期任务 {overdue_count} 条' if overdue_count else '',
                f'未提交汇报 {draft_reports} 条' if draft_reports else '',
            ],
            'suggestions': [
                '先处理高优先级且临近截止时间的个人任务',
                '日报/周报完成后立即提交，避免执行信息滞后',
            ],
            'confidence': 0.88,
        }
        raw_result['risk_points'] = [item for item in raw_result['risk_points'] if item]
        return build_business_ai_result(raw_result, scenario='general', source_refs=[{'type': 'personal_task'}], raw_input={'overdue_count': overdue_count, 'draft_reports': draft_reports})

    def _execute_order_delivery_analysis(self, user, params: dict[str, Any]) -> dict[str, Any]:
        queryset = CustomerOrder.objects.filter(delete_time=0).select_related('customer').order_by('-order_date')
        pending_orders = queryset.filter(status='pending').count()
        finance_pending = queryset.filter(finance_status='pending').count()
        invoice_pending = queryset.filter(invoice_request_status__in=['none', 'requested']).count()
        top_items = list(queryset[:5])
        raw_result = {
            'summary': f'待处理订单 {pending_orders} 条，财务待同步 {finance_pending} 条，待开票处理 {invoice_pending} 条。',
            'risk_level': 'high' if finance_pending >= 5 else 'medium' if pending_orders else 'low',
            'risk_points': [
                f"{item.order_number} / {item.customer.name} / {item.get_status_display()}"
                for item in top_items
            ],
            'suggestions': [
                '先同步财务状态异常或未开票的高金额订单',
                '新建订单时同步录入描述，减少后续履约歧义',
            ],
            'confidence': 0.87,
        }
        return build_business_ai_result(raw_result, scenario='general', source_refs=[{'type': 'order'}], raw_input={'pending_orders': pending_orders, 'finance_pending': finance_pending})

    def _resolve_options(self, field_config: dict[str, Any], user=None) -> list[dict[str, Any]]:
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
            return self._safe_option_queryset(Admin.objects.order_by('-id')[:60], label_field='name')
        if provider == 'approval_tasks':
            queryset = ApprovalTask.objects.filter(status='pending').select_related('approval', 'step').order_by('created_at')
            if user is not None and not getattr(user, 'is_superuser', False):
                queryset = queryset.filter(handler=user)
            return self._safe_option_queryset(queryset[:50], label_field='id', extra_label_getter=lambda item: f"{item.approval.title} / {item.step.step_name}")
        if provider == 'departments':
            return self._safe_option_queryset(Department.objects.filter(status=1).order_by('name')[:80], label_field='name')
        if provider == 'document_categories':
            return self._safe_option_queryset(DocumentCategory.objects.filter(is_active=True).order_by('code')[:60], label_field='name', extra_field='code')
        if provider == 'documents':
            return self._safe_option_queryset(Document.objects.order_by('-updated_at')[:60], label_field='title', extra_field='document_number')
        if provider == 'disk_files':
            queryset = DiskFile.objects.filter(delete_time__isnull=True).order_by('-update_time')
            if user is not None and not getattr(user, 'is_superuser', False):
                queryset = queryset.filter(owner=user)
            return self._safe_option_queryset(queryset[:60], label_field='name', extra_label_getter=lambda item: item.get_full_path())
        if provider == 'disk_folders':
            queryset = DiskFolder.objects.filter(delete_time__isnull=True).order_by('name')
            if user is not None and not getattr(user, 'is_superuser', False):
                queryset = queryset.filter(owner=user)
            return self._safe_option_queryset(queryset[:60], label_field='name', extra_label_getter=lambda item: item.get_full_path())
        if provider == 'positions':
            return self._safe_option_queryset(Position.objects.filter(status=1).order_by('title')[:80], label_field='title')
        if provider == 'work_reports':
            queryset = WorkReport.objects.order_by('-report_date')
            if user is not None and getattr(user, 'id', None):
                queryset = queryset.filter(user_id=getattr(user, 'id', None))
            return self._safe_option_queryset(queryset[:40], label_field='title', extra_label_getter=lambda item: f"{item.title} ({item.report_date})")
        return []

    def _safe_option_queryset(self, queryset, label_field: str, extra_field: str | None = None, extra_label_getter=None) -> list[dict[str, Any]]:
        items = []
        try:
            for item in queryset:
                label = getattr(item, label_field, '') or getattr(item, 'username', '') or f'#{item.id}'
                if extra_label_getter is not None:
                    label = extra_label_getter(item)
                elif extra_field and getattr(item, extra_field, ''):
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

    def _datetime_local_field(self, field_id: str, label: str, required: bool = False) -> dict[str, Any]:
        return {'id': field_id, 'name': field_id, 'label': label, 'type': 'datetime-local', 'required': required}

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

    def _normalize_bool_string(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


enterprise_agent_service = EnterpriseAgentService()
