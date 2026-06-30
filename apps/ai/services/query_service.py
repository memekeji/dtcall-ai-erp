"""
通用查询服务
负责处理用户查询，包括意图识别、查询生成、权限检查和结果处理
"""

import logging
from datetime import timedelta
from typing import Dict, Any
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_default_page_size():
    """获取系统配置的默认分页大小"""
    try:
        from apps.system.config_service import config_service
        return config_service.get_int_config('default_page_size', 20)
    except Exception:
        return 20


class QueryService:
    """通用查询服务"""

    def __init__(self):
        self.intent_handlers = {
            'greeting': self.handle_greeting,
            'ai_chat': self.handle_ai_chat,
            'customer_count': self.handle_customer_count,
            'customer_count_deal': self.handle_customer_count_deal,
            'customer_count_potential': self.handle_customer_count_potential,
            'customer_list': self.handle_customer_list,
            'customer_list_deal': self.handle_customer_list_deal,
            'customer_list_potential': self.handle_customer_list_potential,
            'customer_deal_last_month': self.handle_customer_deal_last_month,
            'customer_deal_this_month': self.handle_customer_deal_this_month,
            'customer_detail': self.handle_customer_detail,
            'order_count': self.handle_order_count,
            'order_count_completed': self.handle_order_count_completed,
            'order_count_in_progress': self.handle_order_count_in_progress,
            'order_list': self.handle_order_list,
            'order_total': self.handle_order_total,
            'order_total_last_month': self.handle_order_total_last_month,
            'order_total_this_month': self.handle_order_total_this_month,
            'contract_count': self.handle_contract_count,
            'contract_count_effective': self.handle_contract_count_effective,
            'contract_count_expired': self.handle_contract_count_expired,
            'contract_list': self.handle_contract_list,
            'contract_total': self.handle_contract_total,
            'project_count': self.handle_project_count,
            'project_count_in_progress': self.handle_project_count_in_progress,
            'project_count_completed': self.handle_project_count_completed,
            'project_count_paused': self.handle_project_count_paused,
            'project_list': self.handle_project_list,
            'project_list_in_progress': self.handle_project_list_in_progress,
            'project_list_completed': self.handle_project_list_completed,
            'project_progress': self.handle_project_progress,
            'invoice_count': self.handle_invoice_count,
            'invoice_count_issued': self.handle_invoice_count_issued,
            'invoice_count_unissued': self.handle_invoice_count_unissued,
            'invoice_list': self.handle_invoice_list,
            'employee_count': self.handle_employee_count,
            'employee_count_active': self.handle_employee_count_active,
            'employee_count_inactive': self.handle_employee_count_inactive,
            'employee_list': self.handle_employee_list,
            'department_count': self.handle_department_count,
            'department_list': self.handle_department_list,
            'finance_expense_count': self.handle_finance_expense_count,
            'finance_expense_list': self.handle_finance_expense_list,
            'finance_invoice_count': self.handle_finance_invoice_count,
            'finance_invoice_list': self.handle_finance_invoice_list,
            'finance_income_count': self.handle_finance_income_count,
            'finance_income_list': self.handle_finance_income_list,
            'finance_order_record_count': self.handle_finance_order_record_count,
            'finance_order_record_list': self.handle_finance_order_record_list,
            'production_plan_count': self.handle_production_plan_count,
            'production_plan_list': self.handle_production_plan_list,
            'production_task_count': self.handle_production_task_count,
            'production_task_list': self.handle_production_task_list,
            'production_equipment_count': self.handle_production_equipment_count,
            'production_equipment_list': self.handle_production_equipment_list,
            'production_procedure_count': self.handle_production_procedure_count,
            'production_procedure_list': self.handle_production_procedure_list,
            'supplier_count': self.handle_supplier_count,
            'supplier_list': self.handle_supplier_list,
            'product_count': self.handle_product_count,
            'product_list': self.handle_product_list,
            'inventory_count': self.handle_inventory_count,
            'inventory_list': self.handle_inventory_list,
            'followup_count': self.handle_followup_count,
            'followup_list': self.handle_followup_list,
            'approval_count': self.handle_approval_count,
            'approval_list': self.handle_approval_list,
            'approval_flow_count': self.handle_approval_flow_count,
            'approval_flow_list': self.handle_approval_flow_list,
            'approval_task_count': self.handle_approval_task_count,
            'approval_task_list': self.handle_approval_task_list,
            'task_count': self.handle_task_count,
            'task_list': self.handle_task_list,
            'message_count': self.handle_message_count,
            'message_list': self.handle_message_list,
            'notice_count': self.handle_notice_count,
            'notice_list': self.handle_notice_list,
            'meeting_count': self.handle_meeting_count,
            'meeting_list': self.handle_meeting_list,
            'schedule_count': self.handle_schedule_count,
            'schedule_list': self.handle_schedule_list,
            'disk_count': self.handle_disk_count,
            'disk_list': self.handle_disk_list,
            'disk_folder_count': self.handle_disk_folder_count,
            'disk_folder_list': self.handle_disk_folder_list,
            'disk_share_count': self.handle_disk_share_count,
            'disk_share_list': self.handle_disk_share_list,
        }

        # 权限映射
        self.permission_mapping = {
            'customer': 'customer.view_customer',
            'order': 'customer.view_customerorder',
            'contract': 'contract.view_contract',
            'project': 'project.view_project',
            'invoice': 'customer.view_customerinvoice',
            'employee': 'user.view_employeefile',
            'department': 'department.view_department',
            'finance': 'finance.view_expense',
            'production': 'production.view_productionplan',
            'supplier': 'contract.view_supplier',
            'product': 'contract.view_product',
            'inventory': 'inventory.view_inventory',
            'followup': 'customer.view_followrecord',
            'disk': 'disk.view_disk_file',
            'disk_folder': 'disk.view_disk_folder',
            'disk_share': 'disk.view_share',
            'approval': 'approval.view_approval',
            'approval_flow': 'approval.view_approvalflow',
            'approval_task': 'approval.view_approvaltask',
            'task': 'task.view_task',
            'workhour': 'task.view_workhour',
            'message': 'message.view_message',
            'notice': 'user.view_notice',
            'document': 'oa.view_document',
            'meeting': 'oa.view_meetingrecord',
            'schedule': '__authenticated__',
        }
        self.specific_intent_permissions = {
            'customer_count': 'customer.view_customer',
            'customer_list': 'customer.view_customer',
            'order_count': 'customer.view_customerorder',
            'order_list': 'customer.view_customerorder',
            'contract_count': 'contract.view_contract',
            'contract_list': 'contract.view_contract',
            'project_count': 'project.view_project',
            'project_list': 'project.view_project',
            'invoice_count': 'customer.view_customerinvoice',
            'invoice_list': 'customer.view_customerinvoice',
            'employee_count': 'user.view_employeefile',
            'employee_list': 'user.view_employeefile',
            'department_count': 'department.view_department',
            'department_list': 'department.view_department',
            'finance_expense_count': 'finance.view_expense',
            'finance_expense_list': 'finance.view_expense',
            'finance_invoice_count': 'finance.view_invoice',
            'finance_invoice_list': 'finance.view_invoice',
            'finance_income_count': 'finance.view_income',
            'finance_income_list': 'finance.view_income',
            'finance_order_record_count': 'finance.view_orderfinancerecord',
            'finance_order_record_list': 'finance.view_orderfinancerecord',
            'production_plan_count': 'production.view_productionplan',
            'production_plan_list': 'production.view_productionplan',
            'production_task_count': 'production.view_productiontask',
            'production_task_list': 'production.view_productiontask',
            'production_equipment_count': 'production.view_equipment',
            'production_equipment_list': 'production.view_equipment',
            'production_procedure_count': 'production.view_productionprocedure',
            'production_procedure_list': 'production.view_productionprocedure',
            'supplier_count': 'contract.view_supplier',
            'supplier_list': 'contract.view_supplier',
            'product_count': 'contract.view_product',
            'product_list': 'contract.view_product',
            'inventory_count': 'inventory.view_inventory',
            'inventory_list': 'inventory.view_inventory',
            'followup_count': 'customer.view_followrecord',
            'followup_list': 'customer.view_followrecord',
            'disk_count': 'disk.view_disk_file',
            'disk_list': 'disk.view_disk_file',
            'disk_folder_count': 'disk.view_disk_folder',
            'disk_folder_list': 'disk.view_disk_folder',
            'disk_share_count': 'disk.view_share',
            'disk_share_list': 'disk.view_share',
            'approval_count': 'approval.view_approval',
            'approval_list': 'approval.view_approval',
            'approval_flow_count': 'approval.view_approvalflow',
            'approval_flow_list': 'approval.view_approvalflow',
            'approval_task_count': 'approval.view_approvaltask',
            'approval_task_list': 'approval.view_approvaltask',
            'task_count': 'task.view_task',
            'task_list': 'task.view_task',
            'message_count': 'message.view_message',
            'message_list': 'message.view_message',
            'notice_count': 'user.view_notice',
            'notice_list': 'user.view_notice',
            'meeting_count': 'oa.view_meetingrecord',
            'meeting_list': 'oa.view_meetingrecord',
            'schedule_count': '__authenticated__',
            'schedule_list': '__authenticated__',
        }

    def process_query(
            self,
            user: User,
            query: str,
            intent_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        处理用户查询

        Args:
            user: 当前用户
            query: 用户查询文本
            intent_result: AI 意图识别结果

        Returns:
            Dict[str, Any]: 查询结果
        """
        try:
            intent_result = intent_result or {}
            specific_intent, specific_entities = self.resolve_specific_intent(query, intent_result)
            if specific_entities.get('requires_business_page_confirmation'):
                return {
                    'success': False,
                    'message': '数据新增、修改、删除需要在对应业务页面核对并确认后执行',
                    'requires_confirmation': True
                }

            if not self.check_permission(user, 'data_query'):
                return {
                    'success': False,
                    'message': '您没有权限访问该数据',
                    'suggestion': '请联系管理员获取相应权限'
                }

            if specific_intent and not self.check_permission(user, specific_intent):
                return {
                    'success': False,
                    'message': '您没有权限访问该数据',
                    'suggestion': '请联系管理员获取相应权限'
                }

            result = None

            if specific_intent:
                result = self.execute_query(
                    specific_intent, specific_entities, user)
            else:
                result = self.execute_query('ai_chat', {}, user)

            formatted_result = self.format_result(result)

            return {
                'success': True,
                'intent': 'data_query',
                'specific_intent': specific_intent,
                'confidence': intent_result.get('confidence', 1.0),
                'result': formatted_result,
                'entities': specific_entities
            }

        except Exception as e:
            logger.error(f"处理查询失败: {str(e)}")
            return {
                'success': False,
                'message': '查询过程中发生错误，请稍后重试'
            }

    def resolve_specific_intent(
            self,
            query: str,
            intent_result: Dict[str, Any] | None = None) -> tuple[str, Dict[str, Any]]:
        intent_result = intent_result or {}
        entities = dict(intent_result.get('entities') or {})
        data_type = intent_result.get('data_type')
        action = intent_result.get('action') or 'query'

        if intent_result.get('time_range'):
            entities['time_range'] = intent_result.get('time_range')
        if intent_result.get('status'):
            entities['status'] = intent_result.get('status')
        if intent_result.get('customer_name'):
            entities['customer_name'] = intent_result.get('customer_name')

        if action in {'list', 'detail', 'summary', 'query', 'count'}:
            action = self._infer_query_action(query, action)
        else:
            action = 'list'

        specific_intent = self._map_data_type_to_specific_intent(data_type, action)
        if specific_intent:
            logger.info(
                f"AI意图映射: intent={intent_result.get('intent')} data_type={data_type} action={action} specific_intent={specific_intent}")
            return specific_intent, entities

        if data_type or intent_result.get('source') == 'ai':
            logger.warning(
                f"AI意图未映射到可执行查询处理器: data_type={data_type}, action={action}")
            return 'ai_chat', entities

        return self.recognize_intent(query)

    def _infer_query_action(self, query: str, action: str) -> str:
        query_lower = (query or '').lower()
        if action == 'count' or any(keyword in query_lower for keyword in ['多少', '数量', '总数', '统计', '合计']):
            return 'count'
        return 'list'

    def _map_data_type_to_specific_intent(self, data_type: str | None, action: str) -> str | None:
        if not data_type:
            return None
        action_type = 'count' if action == 'count' else 'list'
        mapping = {
            'customer': {'count': 'customer_count', 'list': 'customer_list'},
            'order': {'count': 'order_count', 'list': 'order_list'},
            'contract': {'count': 'contract_count', 'list': 'contract_list'},
            'project': {'count': 'project_count', 'list': 'project_list'},
            'invoice': {'count': 'invoice_count', 'list': 'invoice_list'},
            'employee': {'count': 'employee_count', 'list': 'employee_list'},
            'department': {'count': 'department_count', 'list': 'department_list'},
            'finance': {'count': 'finance_expense_count', 'list': 'finance_expense_list'},
            'production': {'count': 'production_plan_count', 'list': 'production_plan_list'},
            'supplier': {'count': 'supplier_count', 'list': 'supplier_list'},
            'product': {'count': 'product_count', 'list': 'product_list'},
            'inventory': {'count': 'inventory_count', 'list': 'inventory_list'},
            'followup': {'count': 'followup_count', 'list': 'followup_list'},
            'disk': {'count': 'disk_count', 'list': 'disk_list'},
            'disk_folder': {'count': 'disk_folder_count', 'list': 'disk_folder_list'},
            'disk_share': {'count': 'disk_share_count', 'list': 'disk_share_list'},
            'approval': {'count': 'approval_count', 'list': 'approval_list'},
            'approval_flow': {'count': 'approval_flow_count', 'list': 'approval_flow_list'},
            'approval_task': {'count': 'approval_task_count', 'list': 'approval_task_list'},
            'task': {'count': 'task_count', 'list': 'task_list'},
            'workhour': {'count': None, 'list': None},
            'message': {'count': 'message_count', 'list': 'message_list'},
            'notice': {'count': 'notice_count', 'list': 'notice_list'},
            'document': {'count': None, 'list': None},
            'meeting': {'count': 'meeting_count', 'list': 'meeting_list'},
            'schedule': {'count': 'schedule_count', 'list': 'schedule_list'},
        }
        return mapping.get(data_type, {}).get(action_type)

    def recognize_intent(self, query: str) -> tuple[str, Dict[str, Any]]:
        """识别用户意图

        Args:
            query: 用户查询文本

        Returns:
            tuple[str, Dict[str, Any]]: 意图和实体
        """
        query_lower = query.lower()
        entities = {}
        intent = None

        if any(keyword in query_lower for keyword in ['添加', '新增', '创建', '增加', '修改', '更新', '删除', '移除', '作废']):
            return 'ai_chat', {'requires_business_page_confirmation': True}
        # 通用问候意图
        if any(keyword in query_lower for keyword in ['你好', '您好', 'hi', 'hello', '早上好', '下午好', '晚上好']):
            intent = 'greeting'
        elif any(keyword in query_lower for keyword in ['网盘分享', '文件分享', '分享链接', '共享链接', '分享码', '提取码']):
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'disk_share_count'
            else:
                intent = 'disk_share_list'
        elif any(keyword in query_lower for keyword in ['网盘文件夹', '共享文件夹', '文件夹']):
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'disk_folder_count'
            else:
                intent = 'disk_folder_list'
        elif any(keyword in query_lower for keyword in ['网盘', '共享文件', '共享资料', '文件', '资料', '附件']):
            if '收藏' in query_lower or '星标' in query_lower:
                entities['status'] = 'starred'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'disk_count'
            else:
                intent = 'disk_list'
        elif any(keyword in query_lower for keyword in ['待审批', '待办审批', '审批任务', '待办流程']):
            entities['status'] = 'pending'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'approval_task_count'
            else:
                intent = 'approval_task_list'
        elif any(keyword in query_lower for keyword in ['审批流', '审批流程', '流程配置', '流程模板']):
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'approval_flow_count'
            else:
                intent = 'approval_flow_list'
        elif '审批' in query_lower or '流程' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'approval_count'
            else:
                intent = 'approval_list'
        elif '消息' in query_lower or '站内信' in query_lower or '通知消息' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'message_count'
            else:
                intent = 'message_list'
        elif '公告' in query_lower or '通知公告' in query_lower:
            if '已发布' in query_lower:
                entities['status'] = 'published'
            elif '未发布' in query_lower or '草稿' in query_lower:
                entities['status'] = 'draft'
            elif '置顶' in query_lower:
                entities['status'] = 'top'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'notice_count'
            else:
                intent = 'notice_list'
        elif '会议' in query_lower or '会议纪要' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'meeting_count'
            else:
                intent = 'meeting_list'
        elif (
                '日程' in query_lower or
                '排期' in query_lower or
                ('安排' in query_lower and not any(keyword in query_lower for keyword in ['会议', '审批', '流程', '通知公告']))
        ):
            if '外勤' in query_lower:
                entities['labor_type'] = 2
            elif '案头' in query_lower or '办公室' in query_lower:
                entities['labor_type'] = 1
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'schedule_count'
            else:
                intent = 'schedule_list'
        elif ('任务' in query_lower or '待办' in query_lower) and '生产' not in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'task_count'
            else:
                intent = 'task_list'
        # 订单相关意图（优先于客户相关意图，因为订单查询可能包含客户名称）
        elif '订单' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                # 检查是否有客户名称关联查询
                import re
                customer_name_pattern = r'[\u4e00-\u9fa5\w]+'
                customer_name_matches = re.findall(
                    customer_name_pattern, query_lower)
                customer_name = None
                if customer_name_matches:
                    # 尝试找到最可能是客户名称的匹配项
                    exclude_words = [
                        '客户',
                        '订单',
                        '合同',
                        '项目',
                        '发票',
                        '查询',
                        '列出',
                        '展示',
                        '查看',
                        '数量',
                        '有多少',
                        '几个',
                        '统计',
                        '关联',
                        '所有',
                        '的',
                        '我',
                        '有',
                        '几',
                        '个',
                        '多少',
                        '这个',
                        '那个']
                    for match in customer_name_matches:
                        if match not in exclude_words and len(
                                match) > 1:  # 排除单个字符
                            customer_name = match
                            entities['customer_name'] = customer_name
                            break

                # 检查是否有状态筛选
                if '已完成' in query_lower:
                    intent = 'order_count_completed'
                    entities['status'] = '已完成'
                elif '进行中' in query_lower:
                    intent = 'order_count_in_progress'
                    entities['status'] = '进行中'
                else:
                    intent = 'order_count'
            elif ('总额' in query_lower or '金额' in query_lower or '订单额' in query_lower):
                # 检查是否有时间范围
                if '上个月' in query_lower or '上月' in query_lower:
                    intent = 'order_total_last_month'
                    entities['time_range'] = 'last_month'
                elif '本月' in query_lower:
                    intent = 'order_total_this_month'
                    entities['time_range'] = 'this_month'
                else:
                    intent = 'order_total'
            elif '列表' in query_lower or '有哪些' in query_lower or '列出' in query_lower or '展示' in query_lower or '查看' in query_lower:
                intent = 'order_list'
        # 处理单独的金额查询，默认查询订单总额
        elif ('总额' in query_lower or '金额' in query_lower) and not ('客户' in query_lower or '合同' in query_lower or '项目' in query_lower):
            intent = 'order_total'

        # 客户相关意图
        elif '客户' in query_lower:
            # 先检查是否是数量查询，优先级高于客户名称查询
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                # 检查是否有状态筛选
                if '成交' in query_lower or '签约' in query_lower:
                    intent = 'customer_count_deal'
                    entities['status'] = '成交'
                elif '潜在' in query_lower:
                    intent = 'customer_count_potential'
                    entities['status'] = '潜在'
                else:
                    intent = 'customer_count'
            # 再检查是否是列表查询
            elif '列表' in query_lower or '有哪些' in query_lower or '列出' in query_lower or '展示' in query_lower or '查看' in query_lower:
                # 检查是否有状态筛选
                if '成交' in query_lower or '签约' in query_lower:
                    intent = 'customer_list_deal'
                    entities['status'] = '成交'
                elif '潜在' in query_lower:
                    intent = 'customer_list_potential'
                    entities['status'] = '潜在'
                else:
                    intent = 'customer_list'
            # 再检查是否是成交客户查询
            elif '成交' in query_lower or '签约' in query_lower:
                # 检查是否有时间范围
                if '上个月' in query_lower or '上月' in query_lower:
                    intent = 'customer_deal_last_month'
                    entities['time_range'] = 'last_month'
                elif '本月' in query_lower:
                    intent = 'customer_deal_this_month'
                    entities['time_range'] = 'this_month'
            # 最后检查是否是客户详情查询
            else:
                # 提取客户名称
                import re
                customer_name_pattern = r'[\u4e00-\u9fa5]{2,}'  # 至少2个中文字符
                customer_name_matches = re.findall(
                    customer_name_pattern, query_lower)
                customer_name = None
                if customer_name_matches:
                    # 尝试找到最可能是客户名称的匹配项
                    exclude_words = [
                        '客户',
                        '订单',
                        '合同',
                        '项目',
                        '发票',
                        '查询',
                        '列出',
                        '展示',
                        '查看',
                        '数量',
                        '有多少',
                        '几个',
                        '统计',
                        '关联',
                        '所有',
                        '的',
                        '我',
                        '有',
                        '几',
                        '个',
                        '多少',
                        '我有',
                        '有几',
                        '几个',
                        '多少个',
                        '我有几个',
                        '我有多少',
                        '有多少']
                    for match in customer_name_matches:
                        if match not in exclude_words:
                            customer_name = match
                            entities['customer_name'] = customer_name
                            break

                if customer_name:
                    # 按客户名称查询意图
                    intent = 'customer_detail'

        # 合同相关意图
        elif '合同' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                # 检查是否有状态筛选
                if '已生效' in query_lower:
                    intent = 'contract_count_effective'
                    entities['status'] = '已生效'
                elif '已过期' in query_lower:
                    intent = 'contract_count_expired'
                    entities['status'] = '已过期'
                else:
                    intent = 'contract_count'
            elif '列表' in query_lower or '有哪些' in query_lower or '列出' in query_lower or '展示' in query_lower or '查看' in query_lower:
                intent = 'contract_list'
            elif '金额' in query_lower or '总额' in query_lower:
                intent = 'contract_total'

        # 项目相关意图
        elif '项目' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                # 检查是否有状态筛选
                if '进行中' in query_lower or '在进行' in query_lower:
                    intent = 'project_count_in_progress'
                    entities['status'] = '进行中'
                elif '已完成' in query_lower:
                    intent = 'project_count_completed'
                    entities['status'] = '已完成'
                elif '已暂停' in query_lower:
                    intent = 'project_count_paused'
                    entities['status'] = '已暂停'
                else:
                    intent = 'project_count'
            elif '列表' in query_lower or '有哪些' in query_lower or '列出' in query_lower or '展示' in query_lower or '查看' in query_lower:
                # 检查是否有状态筛选
                if '进行中' in query_lower or '在进行' in query_lower:
                    intent = 'project_list_in_progress'
                    entities['status'] = '进行中'
                elif '已完成' in query_lower:
                    intent = 'project_list_completed'
                    entities['status'] = '已完成'
                else:
                    intent = 'project_list'
            elif '进度' in query_lower or '完成率' in query_lower:
                intent = 'project_progress'

        # 发票相关意图
        elif '发票' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                # 检查是否有状态筛选
                if '已开具' in query_lower:
                    intent = 'invoice_count_issued'
                    entities['status'] = '已开具'
                elif '未开具' in query_lower:
                    intent = 'invoice_count_unissued'
                    entities['status'] = '未开具'
                else:
                    intent = 'invoice_count'
            elif '列表' in query_lower or '有哪些' in query_lower or '列出' in query_lower or '展示' in query_lower or '查看' in query_lower:
                intent = 'invoice_list'

        # 员工相关意图
        elif '员工' in query_lower or '人事' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                # 检查是否有状态筛选
                if '在职' in query_lower:
                    intent = 'employee_count_active'
                    entities['status'] = '在职'
                elif '离职' in query_lower:
                    intent = 'employee_count_inactive'
                    entities['status'] = '离职'
                else:
                    intent = 'employee_count'
            elif '列表' in query_lower or '有哪些' in query_lower:
                intent = 'employee_list'

        # 部门相关意图
        elif '部门' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                intent = 'department_count'
            elif '列表' in query_lower or '有哪些' in query_lower:
                intent = 'department_list'

        # 财务相关意图
        elif '财务' in query_lower or '报销' in query_lower or '发票' in query_lower or '回款' in query_lower or '打款' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                if '报销' in query_lower:
                    intent = 'finance_expense_count'
                elif '发票' in query_lower:
                    intent = 'finance_invoice_count'
                elif '回款' in query_lower or '收入' in query_lower:
                    intent = 'finance_income_count'
                elif '订单' in query_lower:
                    intent = 'finance_order_record_count'
            elif '列表' in query_lower or '有哪些' in query_lower:
                if '报销' in query_lower:
                    intent = 'finance_expense_list'
                elif '发票' in query_lower:
                    intent = 'finance_invoice_list'
                elif '回款' in query_lower or '收入' in query_lower:
                    intent = 'finance_income_list'
                elif '订单' in query_lower:
                    intent = 'finance_order_record_list'

        # 生产相关意图
        elif '生产' in query_lower or '生产计划' in query_lower or '生产任务' in query_lower or '设备' in query_lower or '工序' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                if '计划' in query_lower:
                    intent = 'production_plan_count'
                elif '任务' in query_lower:
                    intent = 'production_task_count'
                elif '设备' in query_lower:
                    intent = 'production_equipment_count'
                elif '工序' in query_lower:
                    intent = 'production_procedure_count'
            elif '列表' in query_lower or '有哪些' in query_lower or '查询' in query_lower or '查看' in query_lower or '查' in query_lower or '看' in query_lower:
                if '计划' in query_lower:
                    intent = 'production_plan_list'
                elif '任务' in query_lower:
                    intent = 'production_task_list'
                elif '设备' in query_lower:
                    intent = 'production_equipment_list'
                elif '工序' in query_lower:
                    intent = 'production_procedure_list'

        return intent, entities

    def check_permission(self, user: User, intent: str) -> bool:
        """
        检查用户权限
        使用部门-角色-权限三维权限校验逻辑

        Args:
            user: 当前用户
            intent: 查询意图

        Returns:
            bool: 是否有权限
        """
        # 超级管理员拥有所有权限
        if user.is_superuser:
            logger.info(f"超级管理员 {user.username} 访问所有权限")
            return True

        # 处理data_query意图，它是一个高层意图，需要进一步处理
        if intent == 'data_query':
            # data_query是高层意图，所有登录用户都可以访问
            # 具体的业务权限会在后续处理中检查
            logger.info(f"用户 {user.username} 访问 data_query 高层意图，允许访问")
            return True

        if intent in {'greeting', 'ai_chat'}:
            return True

        # 1. 基于具体意图的权限检查
        permission = self.specific_intent_permissions.get(intent)
        if not permission:
            data_type = intent.split('_')[0]
            permission = self.permission_mapping.get(data_type)

        if permission:
            if permission == '__authenticated__':
                has_access = bool(getattr(user, 'is_authenticated', False))
                logger.info(f"用户 {user.username} 访问 {intent} 登录态检查结果: {has_access}")
                return has_access
            # 2. 使用Django内置权限系统检查
            has_perm = user.has_perm(permission)
            logger.info(f"用户 {user.username} 访问 {intent} 权限检查结果: {has_perm}")
            return has_perm

        # 3. 未找到权限映射时拒绝访问，避免 AI 查询绕过具体业务权限
        logger.warning(f"用户 {user.username} 访问 {intent} 未找到对应权限映射，拒绝访问")
        return False

    def format_result(self, result: Dict[str, Any]) -> str:
        """格式化查询结果为可读字符串

        Args:
            result: 查询结果字典

        Returns:
            str: 格式化后的可读字符串
        """
        result_type = result.get('type', '')
        data_type = result.get('data_type', '')

        # 映射数据类型到中文
        data_type_map = {
            'customer': '客户',
            'order': '订单',
            'contract': '合同',
            'project': '项目',
            'invoice': '发票',
            'employee': '员工',
            'department': '部门',
            'finance': '财务',
            'production': '生产'
        }

        data_type_cn = data_type_map.get(data_type, data_type)

        if result_type == 'count':
            value = result.get('value', 0)
            status = result.get('status', '')
            status_text = f'成交的' if status == '成交' else f'潜在的' if status == '潜在' else ''
            return f'共有{value}个{status_text}{data_type_cn}'

        elif result_type == 'list':
            # 兼容不同的结果格式，支持'data'或'items'字段
            data = result.get('data') or result.get('items', [])
            if not data:
                return f'暂无{data_type_cn}数据'

            items = []
            for i, item in enumerate(data, 1):
                if data_type == 'customer':
                    items.append(
                        f"{i}. {item.get('name', '')} ({item.get('source', '')})")
                elif data_type == 'order':
                    items.append(
                        f"{i}. 订单号：{item.get('order_number', '')}，金额：{item.get('amount', '')}元")
                elif data_type == 'contract':
                    items.append(
                        f"{i}. 合同名称：{item.get('customer_name', '')}，金额：{item.get('amount', '')}元")
                elif data_type == 'project':
                    items.append(
                        f"{i}. 项目名称：{item.get('name', '')}，状态：{item.get('status', '')}")
                elif data_type == 'employee':
                    items.append(
                        f"{i}. {item.get('name', '')}，部门：{item.get('department', '')}")
                elif data_type == 'department':
                    items.append(f"{i}. {item.get('name', '')}")
                elif data_type == 'invoice':
                    items.append(
                        f"{i}. 发票号：{item.get('invoice_no', '')}，金额：{item.get('amount', '')}元")
                else:
                    items.append(f"{i}. {str(item)}")

            return f"{data_type_cn}列表：\n" + "\n".join(items)

        elif result_type == 'total':
            value = result.get('value', 0)
            time_range = result.get('time_range', '')
            time_text = f'上月' if time_range == 'last_month' else f'本月' if time_range == 'this_month' else ''
            return f'{time_text}{data_type_cn}总金额为{value}元'

        elif result_type == 'sum':
            value = result.get('value', 0)
            time_range = result.get('time_range', '')
            time_text = f'上月' if time_range == 'last_month' else f'本月' if time_range == 'this_month' else ''
            field = result.get('field', '金额')
            return f'{time_text}{data_type_cn}{field}总和为{value}元'

        elif result_type == 'progress':
            value = result.get('value', 0)
            project_name = result.get('project_name', '')
            return f'{project_name}的进度为{value}%'

        elif result_type == 'detail':
            # 处理详情类型结果
            if data_type == 'customer':
                customer = result.get('customer', {})
                statistics = result.get('statistics', {})
                orders = result.get('orders', [])
                result.get('contracts', [])
                result.get('invoices', [])

                # 构建客户基本信息
                base_info = f"客户详情：\n名称：{customer.get('name', '')}\n电话：{customer.get('phone', '')}\n邮箱：{customer.get('email', '')}\n地址：{customer.get('address', '')}\n来源：{customer.get('source', '')}\n状态：{customer.get('status', '')}\n创建时间：{customer.get('create_time', '')}\n"

                # 构建统计信息
                stats_info = f"\n统计信息：\n总订单数：{statistics.get('total_orders', 0)}\n总订单金额：{statistics.get('total_order_amount', 0)}元\n总合同数：{statistics.get('total_contracts', 0)}\n总发票数：{statistics.get('total_invoices', 0)}\n"

                # 构建订单列表
                orders_info = "\n最近订单：\n"
                for i, order in enumerate(orders[:3], 1):
                    orders_info += f"{i}. 订单号：{order.get('order_number', '')}，金额：{order.get('amount', '')}元，状态：{order.get('status', '')}\n"

                return base_info + stats_info + orders_info
            else:
                return str(result)

        elif result_type == 'greeting':
            value = result.get('value', '')
            return value
        elif result_type == 'ai_chat':
            value = result.get('value', '')
            return value

        # 默认处理
        return str(result)

    def execute_query(self,
                      intent: str,
                      entities: Dict[str,
                                     Any],
                      user: User) -> Any:
        """执行查询

        Args:
            intent: 查询意图
            entities: 实体
            user: 当前用户

        Returns:
            Any: 查询结果
        """
        # 获取处理函数
        handler = self.intent_handlers.get(intent)
        if not handler:
            raise NotImplementedError(f"未实现的意图: {intent}")

        # 执行查询
        return handler(entities, user)

    # 意图处理函数
    def handle_greeting(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理问候语"""
        return {
            'type': 'greeting',
            'value': '你好！我是您的智能助手，很高兴为您服务。请问有什么可以帮助您的吗？',
            'data_type': 'general'
        }

    def handle_ai_chat(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理AI聊天意图"""
        return {
            'type': 'ai_chat',
            'value': '您好！我是您的智能助手，我可以帮助您查询数据、管理客户、处理订单等。请问有什么可以帮助您的吗？',
            'data_type': 'general'
        }

    def handle_customer_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理客户数量查询"""
        from apps.customer.models import Customer

        # 构建查询集，考虑用户权限
        queryset = Customer.objects.filter(delete_time=0)  # 只查询未删除的客户

        # 添加实体关联计数（与客户列表视图保持一致）
        queryset = queryset.annotate(
            order_count=models.Count(
                'orders',
                filter=models.Q(
                    orders__delete_time=0)),
            contract_count=models.Count(
                'contracts',
                filter=models.Q(
                    contracts__delete_time=0)),
            project_count=models.Count('projects'),
            invoice_count=models.Count(
                'invoices',
                filter=models.Q(
                    invoices__delete_time=0)))

        # 数据权限过滤：与客户列表视图保持一致
        if hasattr(user, 'is_superuser') and user.is_superuser:
            # 超级管理员：排除已移入公海的客户（belong_uid=0）
            queryset = queryset.filter(belong_uid__gt=0)
        else:
            # 普通用户：只能查看自己的客户及共享给自己的客户
            queryset = queryset.filter(
                models.Q(belong_uid=user.id) |
                models.Q(share_ids__contains=str(user.id))
            )

        count = queryset.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'customer'
        }

    def handle_customer_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理客户列表查询"""
        from apps.customer.models import Customer

        # 构建查询集，考虑用户权限
        queryset = Customer.objects.filter(delete_time=0)  # 只查询未删除的客户

        # 添加实体关联计数（与客户列表视图保持一致）
        queryset = queryset.annotate(
            order_count=models.Count(
                'orders',
                filter=models.Q(
                    orders__delete_time=0)),
            contract_count=models.Count(
                'contracts',
                filter=models.Q(
                    contracts__delete_time=0)),
            project_count=models.Count('projects'),
            invoice_count=models.Count(
                'invoices',
                filter=models.Q(
                    invoices__delete_time=0)))

        # 数据权限过滤：与客户列表视图保持一致
        if hasattr(user, 'is_superuser') and user.is_superuser:
            # 超级管理员：排除已移入公海的客户（belong_uid=0）
            queryset = queryset.filter(belong_uid__gt=0)
        else:
            # 普通用户：只能查看自己的客户及共享给自己的客户
            queryset = queryset.filter(
                models.Q(belong_uid=user.id) |
                models.Q(share_ids__contains=str(user.id))
            )

        # 应用筛选条件
        # 注意：Customer模型中没有customer_status字段，使用intent_status字段代替
        status = entities.get('status')
        if status:
            queryset = queryset.filter(intent_status=status)

        # 应用排序
        queryset = queryset.order_by('-create_time')  # 默认按创建时间降序排列

        # 应用分页
        page = entities.get('page', 1)
        page_size = entities.get('page_size', get_default_page_size())
        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        customers = queryset[start_index:end_index]
        customer_list = [{
            'id': customer.id,
            'name': customer.name,
            'source': customer.customer_source.title if customer.customer_source else '',  # 使用title属性
            'status': customer.intent_status,  # 使用intent_status字段代替customer_status
            'phone': '',  # Customer模型中没有phone字段
            'email': '',  # Customer模型中没有email字段
            'address': customer.address,
            'create_time': customer.create_time.strftime('%Y-%m-%d %H:%M:%S') if customer.create_time else '',
            # 使用principal字段获取负责人名称
            'belong_to': customer.principal.name if customer.principal else '未分配'
        } for customer in customers]

        return {
            'type': 'list',
            'items': customer_list,
            'total': queryset.count(),
            'page': page,
            'page_size': page_size,
            'data_type': 'customer'
        }

    def handle_order_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理订单数量查询，支持按客户名称模糊匹配"""
        from apps.customer.models import CustomerOrder, Customer

        # 构建客户查询集，考虑用户权限和软删除
        customer_queryset = Customer.objects.filter(delete_time=0)  # 只查询未删除的客户

        # 如果不是超级管理员，只显示归属自己的客户
        if not user.is_superuser:
            customer_queryset = customer_queryset.filter(belong_uid=user.id)

        # 处理实体中的客户名称模糊匹配
        customer_name = entities.get('customer_name')
        if customer_name:
            # 支持模糊匹配客户名称
            customer_queryset = customer_queryset.filter(
                name__icontains=customer_name)

        # 获取符合条件的客户ID列表
        customer_ids = customer_queryset.values_list('id', flat=True)

        # 构建订单查询集，只查询未删除的订单
        queryset = CustomerOrder.objects.filter(
            delete_time=0, customer_id__in=customer_ids)

        count = queryset.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'order'
        }

    def handle_order_total(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理订单总额查询"""
        from apps.customer.models import CustomerOrder, Customer

        # 构建查询集，考虑用户权限
        queryset = CustomerOrder.objects.all()

        # 如果不是超级管理员，只计算归属自己的客户的订单总额
        if not user.is_superuser:
            # 获取当前用户的客户ID列表
            user_customer_ids = Customer.objects.filter(
                belong_uid=user.id).values_list(
                'id', flat=True)
            queryset = queryset.filter(customer_id__in=user_customer_ids)

        total_amount = queryset.aggregate(
            total=models.Sum('amount'))['total'] or 0
        return {
            'type': 'sum',
            'value': total_amount,
            'data_type': 'order',
            'field': 'amount'
        }

    def handle_contract_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理合同数量查询"""
        from apps.contract.models import Contract
        count = Contract.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'contract'
        }

    def handle_project_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理项目数量查询"""
        from apps.project.models import Project
        count = Project.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'project'
        }

    def handle_invoice_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理发票数量查询"""
        from apps.customer.models import CustomerInvoice
        count = CustomerInvoice.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'invoice'
        }

    def handle_employee_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理员工数量查询"""
        from apps.user.models import EmployeeFile
        count = EmployeeFile.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'employee'
        }

    def handle_project_count_in_progress(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理进行中项目数量查询"""
        from apps.project.models import Project
        # 查询进行中项目数量，使用数字状态值2
        count = Project.objects.filter(status=2).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'project',
            'status': '进行中'
        }

    def handle_project_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理项目列表查询"""
        from apps.project.models import Project

        # 构建查询集
        queryset = Project.objects.all().select_related('manager')

        # 应用筛选条件
        status = entities.get('status')
        if status:
            queryset = queryset.filter(status=status)

        manager = entities.get('manager')
        if manager:
            queryset = queryset.filter(manager__username__icontains=manager)

        project_name = entities.get('project_name')
        if project_name:
            queryset = queryset.filter(name__icontains=project_name)

        # 应用排序
        queryset = queryset.order_by('-start_date')  # 默认按开始日期降序排列

        # 应用分页
        page = entities.get('page', 1)
        page_size = entities.get('page_size', get_default_page_size())
        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        projects = queryset[start_index:end_index]
        project_list = [{
            'id': project.id,
            'name': project.name,
            'status': project.status_display,  # 使用status_display属性获取显示名称
            'manager': project.manager.username if project.manager else '',
            'progress': project.progress or 0,
            'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else '',
            'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else '',
            'create_time': project.create_time.strftime('%Y-%m-%d %H:%M:%S') if project.create_time else '',
            'update_time': project.update_time.strftime('%Y-%m-%d %H:%M:%S') if project.update_time else ''
        } for project in projects]

        return {
            'type': 'list',
            'items': project_list,
            'total': queryset.count(),
            'page': page,
            'page_size': page_size,
            'data_type': 'project'
        }

    def handle_project_list_in_progress(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理进行中项目列表查询"""
        from apps.project.models import Project
        # 查询前5个进行中项目，使用数字状态值2
        projects = Project.objects.filter(status=2)[:5]
        project_list = [{
            'id': project.id,
            'name': project.name,
            'status': project.status_display,  # 使用status_display属性获取显示名称
            'manager': project.manager.username if project.manager else '',
            'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else '',
            'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else ''
        } for project in projects]
        return {
            'type': 'list',
            'items': project_list,
            'total': Project.objects.filter(status=2).count(),
            'data_type': 'project',
            'status': '进行中'
        }

    def handle_customer_deal_last_month(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理上个月成交客户查询"""
        from apps.customer.models import Customer, CustomerOrder
        from apps.user.models import Admin
        from datetime import datetime, timedelta

        # 计算上个月的时间范围
        today = datetime.today()
        first_day_of_current_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_current_month - timedelta(days=1)
        first_day_of_last_month = last_day_of_last_month.replace(day=1)

        # 查询上个月有订单的客户
        # 先获取上个月有订单的客户ID
        order_customer_ids = CustomerOrder.objects.filter(
            order_date__gte=first_day_of_last_month,
            order_date__lte=last_day_of_last_month
        ).values_list('customer_id', flat=True).distinct()

        # 查询客户信息
        customers = Customer.objects.filter(id__in=order_customer_ids)[:5]

        # 获取所有相关的管理员ID
        admin_ids = [
            customer.belong_uid for customer in customers if customer.belong_uid]
        # 批量查询管理员信息
        admins = Admin.objects.filter(id__in=admin_ids)
        admin_dict = {admin.id: admin.username for admin in admins}

        customer_list = [{
            'id': customer.id,
            'name': customer.name,
            'status': customer.intent_status,
            'belong_user': customer.principal.name if customer.principal else ''
        } for customer in customers]

        return {
            'type': 'list',
            'items': customer_list,
            'total': len(order_customer_ids),
            'data_type': 'customer',
            'time_range': 'last_month',
            'event': 'deal'
        }

    def handle_customer_count_deal(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理成交客户数量查询"""
        from apps.customer.models import Customer
        # 成交客户应该是指有订单的客户，而不是通过customer_status字段
        from apps.customer.models import CustomerOrder

        # 构建基础查询集
        customer_queryset = Customer.objects.all()
        order_queryset = CustomerOrder.objects.all()

        # 如果不是超级管理员，只查询归属自己的客户
        if not user.is_superuser:
            customer_queryset = customer_queryset.filter(belong_uid=user.id)

        # 获取当前用户的客户ID列表
        user_customer_ids = customer_queryset.values_list('id', flat=True)

        # 获取有订单的客户ID
        customer_ids = order_queryset.filter(
            customer_id__in=user_customer_ids).values_list(
            'customer_id', flat=True).distinct()

        # 计算成交客户数量
        count = Customer.objects.filter(id__in=customer_ids).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'customer',
            'status': '成交'
        }

    def handle_customer_count_potential(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理潜在客户数量查询"""
        from apps.customer.models import Customer
        # 潜在客户应该是指有意向但还没有订单的客户
        from apps.customer.models import CustomerOrder

        # 构建基础查询集
        customer_queryset = Customer.objects.all()
        order_queryset = CustomerOrder.objects.all()

        # 如果不是超级管理员，只查询归属自己的客户
        if not user.is_superuser:
            customer_queryset = customer_queryset.filter(belong_uid=user.id)

        # 获取当前用户的客户ID列表
        user_customer_ids = customer_queryset.values_list('id', flat=True)

        # 获取有订单的客户ID
        customer_ids_with_orders = order_queryset.filter(
            customer_id__in=user_customer_ids).values_list(
            'customer_id', flat=True).distinct()

        # 查询没有订单但有意向的客户
        count = Customer.objects.filter(
            id__in=user_customer_ids).exclude(
            id__in=customer_ids_with_orders).filter(
            intent_status__gt=0).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'customer',
            'status': '潜在'
        }

    def handle_customer_list_deal(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理成交客户列表查询"""
        from apps.customer.models import Customer, CustomerOrder

        # 构建基础查询集
        customer_queryset = Customer.objects.all()
        order_queryset = CustomerOrder.objects.all()

        # 如果不是超级管理员，只查询归属自己的客户
        if not user.is_superuser:
            customer_queryset = customer_queryset.filter(belong_uid=user.id)

        # 获取当前用户的客户ID列表
        user_customer_ids = customer_queryset.values_list('id', flat=True)

        # 获取有订单的客户ID
        customer_ids = order_queryset.filter(
            customer_id__in=user_customer_ids).values_list(
            'customer_id', flat=True).distinct()

        # 查询成交客户信息
        customers = Customer.objects.filter(id__in=customer_ids)[:5]
        customer_list = [{
            'id': customer.id,
            'name': customer.name,
            'source': customer.customer_source.title if customer.customer_source else '',
            'status': customer.intent_status
        } for customer in customers]

        return {
            'type': 'list',
            'items': customer_list,
            'total': Customer.objects.filter(id__in=customer_ids).count(),
            'data_type': 'customer',
            'status': '成交'
        }

    def handle_customer_list_potential(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理潜在客户列表查询"""
        from apps.customer.models import Customer, CustomerOrder

        # 构建基础查询集
        customer_queryset = Customer.objects.all()
        order_queryset = CustomerOrder.objects.all()

        # 如果不是超级管理员，只查询归属自己的客户
        if not user.is_superuser:
            customer_queryset = customer_queryset.filter(belong_uid=user.id)

        # 获取当前用户的客户ID列表
        user_customer_ids = customer_queryset.values_list('id', flat=True)

        # 获取有订单的客户ID
        customer_ids_with_orders = order_queryset.filter(
            customer_id__in=user_customer_ids).values_list(
            'customer_id', flat=True).distinct()

        # 查询没有订单但有意向的客户
        customers = Customer.objects.filter(
            id__in=user_customer_ids).exclude(
            id__in=customer_ids_with_orders).filter(
            intent_status__gt=0)[
                :5]
        customer_list = [{
            'id': customer.id,
            'name': customer.name,
            'source': customer.customer_source.title if customer.customer_source else '',
            'status': customer.intent_status
        } for customer in customers]
        return {
            'type': 'list',
            'items': customer_list,
            'total': Customer.objects.filter(
                id__in=user_customer_ids).exclude(
                id__in=customer_ids_with_orders).filter(
                intent_status__gt=0).count(),
            'data_type': 'customer',
            'status': '潜在'}

    def handle_customer_deal_this_month(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理本月成交客户查询"""
        from apps.customer.models import Customer, CustomerOrder
        from apps.user.models import Admin
        from datetime import datetime

        # 计算本月的时间范围
        today = datetime.today()
        first_day_of_current_month = today.replace(day=1)

        # 查询本月有订单的客户
        # 先获取本月有订单的客户ID
        order_customer_ids = CustomerOrder.objects.filter(
            order_date__gte=first_day_of_current_month
        ).values_list('customer_id', flat=True).distinct()

        # 查询客户信息
        customers = Customer.objects.filter(id__in=order_customer_ids)[:5]

        # 获取所有相关的管理员ID
        admin_ids = [
            customer.belong_uid for customer in customers if customer.belong_uid]
        # 批量查询管理员信息
        admins = Admin.objects.filter(id__in=admin_ids)
        admin_dict = {admin.id: admin.username for admin in admins}

        customer_list = [{
            'id': customer.id,
            'name': customer.name,
            'status': customer.intent_status,
            'belong_user': customer.principal.name if customer.principal else ''
        } for customer in customers]

        return {
            'type': 'list',
            'items': customer_list,
            'total': len(order_customer_ids),
            'data_type': 'customer',
            'time_range': 'this_month',
            'event': 'deal'
        }

    def handle_customer_detail(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理客户详情查询，包括关联的订单、合同、发票等"""
        from apps.customer.models import Customer, CustomerOrder, CustomerInvoice
        from apps.contract.models import Contract
        from django.db import models

        # 获取客户名称
        customer_name = entities.get('customer_name')
        if not customer_name:
            return {
                'type': 'error',
                'message': '请提供客户名称',
                'data_type': 'customer'
            }

        # 构建查询集，考虑用户权限
        customer_queryset = Customer.objects.all()
        if not user.is_superuser:
            customer_queryset = customer_queryset.filter(belong_uid=user.id)

        # 查找客户
        customer = customer_queryset.filter(
            name__icontains=customer_name).first()
        if not customer:
            return {
                'type': 'error',
                'message': f'未找到名称包含{customer_name}的客户',
                'data_type': 'customer'
            }

        # 获取客户的所有订单
        orders = CustomerOrder.objects.filter(
            customer=customer).order_by('-order_date')
        order_list = [{
            'order_id': order.id,
            'order_number': order.order_number,
            'amount': order.amount,
            'status': order.status,
            'order_date': order.order_date.strftime('%Y-%m-%d %H:%M:%S') if order.order_date else '',
            'delivery_date': order.delivery_date.strftime('%Y-%m-%d') if order.delivery_date else ''
        } for order in orders]

        # 获取客户的所有合同
        contracts = Contract.objects.filter(
            customer__icontains=customer.name).order_by('-sign_time')
        import time
        contract_list = [
            {
                'contract_id': contract.id,
                'contract_no': contract.code,
                'amount': contract.cost,
                'status': contract.check_status,
                'sign_date': time.strftime(
                    '%Y-%m-%d',
                    time.localtime(
                        contract.sign_time)) if contract.sign_time else ''} for contract in contracts]

        # 获取客户的所有发票
        invoices = CustomerInvoice.objects.filter(
            customer=customer).order_by('-issue_date')
        invoice_list = [{
            'invoice_id': invoice.id,
            'invoice_no': invoice.invoice_no,
            'amount': invoice.amount,
            'status': invoice.status,
            'issue_date': invoice.issue_date.strftime('%Y-%m-%d') if invoice.issue_date else ''
        } for invoice in invoices]

        # 计算统计数据
        total_orders = orders.count()
        total_order_amount = orders.aggregate(
            total=models.Sum('amount'))['total'] or 0
        total_contracts = contracts.count()
        total_invoices = invoices.count()

        # 构建响应
        return {
            'type': 'detail',
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'email': customer.email,
                'address': customer.address,
                'source': customer.customer_source.title if customer.customer_source else '',
                'status': customer.intent_status,
                'create_time': customer.create_time.strftime('%Y-%m-%d %H:%M:%S') if customer.create_time else ''
            },
            'orders': order_list,
            'contracts': contract_list,
            'invoices': invoice_list,
            'statistics': {
                'total_orders': total_orders,
                'total_order_amount': total_order_amount,
                'total_contracts': total_contracts,
                'total_invoices': total_invoices
            },
            'data_type': 'customer'
        }

    # 订单相关处理函数
    def handle_order_count_completed(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理已完成订单数量查询"""
        from apps.customer.models import CustomerOrder
        count = CustomerOrder.objects.filter(status='已完成').count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'order',
            'status': '已完成'
        }

    def handle_order_count_in_progress(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理进行中订单数量查询"""
        from apps.customer.models import CustomerOrder
        count = CustomerOrder.objects.filter(status='进行中').count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'order',
            'status': '进行中'
        }

    def handle_order_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理订单列表查询"""
        from apps.customer.models import CustomerOrder, Customer

        # 构建查询集，考虑用户权限
        queryset = CustomerOrder.objects.all().select_related('customer')

        # 如果不是超级管理员，只显示归属自己的客户的订单
        if not user.is_superuser:
            # 获取当前用户的客户ID列表
            user_customer_ids = Customer.objects.filter(
                belong_uid=user.id).values_list(
                'id', flat=True)
            queryset = queryset.filter(customer_id__in=user_customer_ids)

        # 应用筛选条件
        status = entities.get('status')
        if status:
            queryset = queryset.filter(status=status)

        customer_id = entities.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        # 应用排序
        queryset = queryset.order_by('-order_date')  # 默认按订单日期降序排列

        # 应用分页
        page = entities.get('page', 1)
        page_size = entities.get('page_size', get_default_page_size())
        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        orders = queryset[start_index:end_index]
        order_list = [{
            'id': order.id,
            'customer_name': order.customer.name if order.customer else '',
            'amount': order.amount,
            'status': order.status,
            'order_number': order.order_number,
            'order_date': order.order_date.strftime('%Y-%m-%d %H:%M:%S') if order.order_date else '',
            'delivery_date': order.delivery_date.strftime('%Y-%m-%d') if order.delivery_date else '',
            'payment_date': order.payment_date.strftime('%Y-%m-%d') if order.payment_date else '',
            'create_time': order.create_time.strftime('%Y-%m-%d %H:%M:%S') if order.create_time else ''
        } for order in orders]

        return {
            'type': 'list',
            'items': order_list,
            'total': queryset.count(),
            'page': page,
            'page_size': page_size,
            'data_type': 'order'
        }

    def handle_order_total_last_month(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理上个月订单总额查询"""
        from apps.customer.models import CustomerOrder
        from datetime import datetime, timedelta

        # 计算上个月的时间范围
        today = datetime.today()
        first_day_of_current_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_current_month - timedelta(days=1)
        first_day_of_last_month = last_day_of_last_month.replace(day=1)

        total_amount = CustomerOrder.objects.filter(
            order_date__gte=first_day_of_last_month,
            order_date__lte=last_day_of_last_month
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        return {
            'type': 'sum',
            'value': total_amount,
            'data_type': 'order',
            'field': 'amount',
            'time_range': 'last_month'
        }

    def handle_order_total_this_month(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理本月订单总额查询"""
        from apps.customer.models import CustomerOrder
        from datetime import datetime

        # 计算本月的时间范围
        today = datetime.today()
        first_day_of_current_month = today.replace(day=1)

        total_amount = CustomerOrder.objects.filter(
            order_date__gte=first_day_of_current_month
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        return {
            'type': 'sum',
            'value': total_amount,
            'data_type': 'order',
            'field': 'amount',
            'time_range': 'this_month'
        }

    # 合同相关处理函数
    def handle_contract_count_effective(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理已生效合同数量查询"""
        from apps.contract.models import Contract
        # 已生效合同应该是指审核通过且未过期的合同
        import time
        current_time = int(time.time())
        count = Contract.objects.filter(
            check_status=2,  # 审核通过
            end_time__gt=current_time,  # 未过期
            delete_time=0  # 未删除
        ).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'contract',
            'status': '已生效'
        }

    def handle_contract_count_expired(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理已过期合同数量查询"""
        from apps.contract.models import Contract
        import time
        current_time = int(time.time())
        count = Contract.objects.filter(
            end_time__lt=current_time,  # 已过期
            delete_time=0  # 未删除
        ).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'contract',
            'status': '已过期'
        }

    def handle_contract_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理合同列表查询"""
        from apps.contract.models import Contract
        import time

        # 构建查询集
        queryset = Contract.objects.all()

        # 应用筛选条件
        status = entities.get('status')
        if status:
            queryset = queryset.filter(check_status=status)

        customer = entities.get('customer')
        if customer:
            queryset = queryset.filter(customer__icontains=customer)

        # 应用排序
        queryset = queryset.order_by('-sign_time')  # 默认按签约时间降序排列

        # 应用分页
        page = entities.get('page', 1)
        page_size = entities.get('page_size', get_default_page_size())
        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        contracts = queryset[start_index:end_index]
        contract_list = [{
            'id': contract.id,
            'customer_name': contract.customer,  # customer是CharField，直接存储客户名称
            'contract_no': contract.code,
            'amount': contract.cost,  # 金额字段是cost
            'status': contract.check_status,  # 状态字段是check_status
            'sign_date': time.strftime('%Y-%m-%d', time.localtime(contract.sign_time)) if contract.sign_time else '',
            'start_time': time.strftime('%Y-%m-%d', time.localtime(contract.start_time)) if contract.start_time else '',
            'end_time': time.strftime('%Y-%m-%d', time.localtime(contract.end_time)) if contract.end_time else '',
            'create_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(contract.create_time)) if contract.create_time else ''
        } for contract in contracts]

        return {
            'type': 'list',
            'items': contract_list,
            'total': queryset.count(),
            'page': page,
            'page_size': page_size,
            'data_type': 'contract'
        }

    def handle_contract_total(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理合同总额查询"""
        from apps.contract.models import Contract
        total_amount = Contract.objects.aggregate(
            total=models.Sum('cost'))['total'] or 0
        return {
            'type': 'sum',
            'value': total_amount,
            'data_type': 'contract',
            'field': 'cost'
        }

    # 项目相关处理函数
    def handle_project_count_completed(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理已完成项目数量查询"""
        from apps.project.models import Project
        # 使用数字状态值3表示已完成
        count = Project.objects.filter(status=3).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'project',
            'status': '已完成'
        }

    def handle_project_count_paused(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理已暂停项目数量查询"""
        from apps.project.models import Project
        # 使用数字状态值5表示已暂停
        count = Project.objects.filter(status=5).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'project',
            'status': '已暂停'
        }

    def handle_project_list_completed(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理已完成项目列表查询"""
        from apps.project.models import Project
        # 使用数字状态值3表示已完成
        projects = Project.objects.filter(status=3)[:5]
        project_list = [{
            'id': project.id,
            'name': project.name,
            'status': project.status_display,  # 使用status_display属性获取显示名称
            'manager': project.manager.username if project.manager else '',
            'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else '',
            'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else ''
        } for project in projects]
        return {
            'type': 'list',
            'items': project_list,
            'total': Project.objects.filter(status=3).count(),
            'data_type': 'project',
            'status': '已完成'
        }

    def handle_project_progress(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理项目进度查询"""
        from apps.project.models import Project
        # 查询所有项目的进度信息
        projects = Project.objects.all()[:5]
        project_progress_list = [{
            'id': project.id,
            'name': project.name,
            'progress': project.progress or 0,
            'status': project.status_display  # 使用status_display属性获取显示名称
        } for project in projects]
        return {
            'type': 'list',
            'items': project_progress_list,
            'total': Project.objects.count(),
            'data_type': 'project',
            'event': 'progress'
        }

    # 发票相关处理函数
    def handle_invoice_count_issued(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理已开具发票数量查询"""
        from apps.customer.models import CustomerInvoice
        count = CustomerInvoice.objects.filter(status='已开具').count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'invoice',
            'status': '已开具'
        }

    def handle_invoice_count_unissued(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理未开具发票数量查询"""
        from apps.customer.models import CustomerInvoice
        count = CustomerInvoice.objects.filter(status='未开具').count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'invoice',
            'status': '未开具'
        }

    def handle_invoice_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理发票列表查询"""
        from apps.customer.models import CustomerInvoice, Customer

        # 构建查询集，考虑用户权限
        queryset = CustomerInvoice.objects.all().select_related('customer')

        # 如果不是超级管理员，只显示归属自己的客户的发票
        if not user.is_superuser:
            # 获取当前用户的客户ID列表
            user_customer_ids = Customer.objects.filter(
                belong_uid=user.id).values_list(
                'id', flat=True)
            queryset = queryset.filter(customer_id__in=user_customer_ids)

        # 应用筛选条件
        status = entities.get('status')
        if status:
            queryset = queryset.filter(status=status)

        customer_id = entities.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        invoice_no = entities.get('invoice_no')
        if invoice_no:
            queryset = queryset.filter(invoice_no__icontains=invoice_no)

        # 应用排序
        queryset = queryset.order_by('-issue_date')  # 默认按开票日期降序排列

        # 应用分页
        page = entities.get('page', 1)
        page_size = entities.get('page_size', get_default_page_size())
        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        invoices = queryset[start_index:end_index]
        invoice_list = [{
            'id': invoice.id,
            'customer_name': invoice.customer.name if invoice.customer else '',
            'invoice_no': invoice.invoice_no,
            'amount': invoice.amount,
            'status': invoice.status,
            'issue_date': invoice.issue_date.strftime('%Y-%m-%d') if invoice.issue_date else '',
            'due_date': invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else '',
            'create_time': invoice.create_time.strftime('%Y-%m-%d %H:%M:%S') if invoice.create_time else ''
        } for invoice in invoices]

        return {
            'type': 'list',
            'items': invoice_list,
            'total': queryset.count(),
            'page': page,
            'page_size': page_size,
            'data_type': 'invoice'
        }

    def handle_add_order(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理添加订单请求"""
        return {
            'type': 'error',
            'message': '订单创建需要在对应业务页面核对并确认后执行',
            'data_type': 'order',
            'requires_confirmation': True
        }

    def handle_add_followup(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理添加客户跟进记录请求"""
        return {
            'type': 'error',
            'message': '跟进记录创建需要在对应业务页面核对并确认后执行',
            'data_type': 'followup',
            'requires_confirmation': True
        }

    # 员工相关处理函数
    def handle_employee_count_active(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理在职员工数量查询"""
        from apps.user.models import Admin
        # 在职员工是status=1
        count = Admin.objects.filter(status=1).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'employee',
            'status': '在职'
        }

    def handle_employee_count_inactive(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理离职员工数量查询"""
        from apps.user.models import Admin
        # 离职员工是status=2
        count = Admin.objects.filter(status=2).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'employee',
            'status': '离职'
        }

    def handle_employee_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理员工列表查询"""
        from apps.user.models import Admin
        employees = Admin.objects.all()[:5]
        employee_list = [{
            'id': employee.id,
            'name': employee.name,
            'department': employee.did,  # 部门ID
            'position': employee.position_name,
            'status': '在职' if employee.status == 1 else '离职' if employee.status == 2 else '其他'
        } for employee in employees]
        return {
            'type': 'list',
            'items': employee_list,
            'total': Admin.objects.count(),
            'data_type': 'employee'
        }

    # 部门相关处理函数
    def handle_department_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理部门数量查询"""
        from apps.department.models import Department
        count = Department.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'department'
        }

    def handle_department_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理部门列表查询"""
        from apps.department.models import Department
        departments = Department.objects.all()[:5]
        department_list = [{
            'id': department.id,
            'name': department.name,
            'parent': department.pid  # 上级部门ID
        } for department in departments]
        return {
            'type': 'list',
            'items': department_list,
            'total': Department.objects.count(),
            'data_type': 'department'
        }

    # 财务相关处理函数
    def handle_finance_expense_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理报销数量查询"""
        from apps.finance.models import Expense
        count = Expense.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'finance_expense'
        }

    def handle_finance_expense_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理报销列表查询"""
        from apps.finance.models import Expense
        expenses = Expense.objects.all()[:5]
        expense_list = [{
            'id': expense.id,
            'code': expense.code,
            'cost': expense.cost,
            'pay_status': '已打款' if expense.pay_status == 1 else '待打款',
            'check_status': expense.check_status
        } for expense in expenses]
        return {
            'type': 'list',
            'items': expense_list,
            'total': Expense.objects.count(),
            'data_type': 'finance_expense'
        }

    def handle_finance_invoice_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理发票数量查询"""
        from apps.finance.models import Invoice
        count = Invoice.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'finance_invoice'
        }

    def handle_finance_invoice_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理发票列表查询"""
        from apps.finance.models import Invoice
        invoices = Invoice.objects.all()[:5]
        invoice_list = [{
            'id': invoice.id,
            'code': invoice.code,
            'amount': invoice.amount,
            'open_status': '已开票' if invoice.open_status == 1 else '未开票',
            'invoice_type': invoice.invoice_type
        } for invoice in invoices]
        return {
            'type': 'list',
            'items': invoice_list,
            'total': Invoice.objects.count(),
            'data_type': 'finance_invoice'
        }

    def handle_finance_income_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理回款数量查询"""
        from apps.finance.models import Income
        count = Income.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'finance_income'
        }

    def handle_finance_income_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理回款列表查询"""
        from apps.finance.models import Income
        incomes = Income.objects.all()[:5]
        income_list = [{
            'id': income.id,
            'invoice_code': income.invoice.code,
            'amount': income.amount,
            'income_date': income.income_date.strftime('%Y-%m-%d')
        } for income in incomes]
        return {
            'type': 'list',
            'items': income_list,
            'total': Income.objects.count(),
            'data_type': 'finance_income'
        }

    def handle_finance_order_record_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理订单财务记录数量查询"""
        from apps.finance.models import OrderFinanceRecord
        count = OrderFinanceRecord.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'finance_order_record'
        }

    def handle_finance_order_record_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理订单财务记录列表查询"""
        from apps.finance.models import OrderFinanceRecord
        records = OrderFinanceRecord.objects.all()[:5]
        record_list = [{
            'id': record.id,
            'order_number': record.order.order_number,
            'total_amount': record.total_amount,
            'paid_amount': record.paid_amount,
            'payment_status': record.payment_status
        } for record in records]
        return {
            'type': 'list',
            'items': record_list,
            'total': OrderFinanceRecord.objects.count(),
            'data_type': 'finance_order_record'
        }

    # 生产相关处理函数
    def handle_production_plan_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产计划数量查询"""
        from apps.production.models import ProductionPlan
        count = ProductionPlan.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'production_plan'
        }

    def handle_production_plan_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产计划列表查询"""
        from apps.production.models import ProductionPlan
        plans = ProductionPlan.objects.all()[:5]
        plan_list = [{
            'id': plan.id,
            'code': plan.code,
            'name': plan.name,
            'status': plan.status_display,
            'product': plan.product.name if plan.product else ''
        } for plan in plans]
        return {
            'type': 'list',
            'items': plan_list,
            'total': ProductionPlan.objects.count(),
            'data_type': 'production_plan'
        }

    def handle_production_task_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产任务数量查询"""
        from apps.production.models import ProductionTask
        count = ProductionTask.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'production_task'
        }

    def handle_production_task_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产任务列表查询"""
        from apps.production.models import ProductionTask
        tasks = ProductionTask.objects.all()[:5]
        task_list = [{
            'id': task.id,
            'code': task.code,
            'name': task.name,
            'status': task.status_display,
            'procedure': task.procedure.name,
            'completion_rate': task.completion_rate
        } for task in tasks]
        return {
            'type': 'list',
            'items': task_list,
            'total': ProductionTask.objects.count(),
            'data_type': 'production_task'
        }

    def handle_production_equipment_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产设备数量查询"""
        from apps.production.models import Equipment
        count = Equipment.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'production_equipment'
        }

    def handle_production_equipment_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产设备列表查询"""
        from apps.production.models import Equipment
        equipments = Equipment.objects.all()[:5]
        equipment_list = [{
            'id': equipment.id,
            'code': equipment.code,
            'name': equipment.name,
            'status': equipment.status_display,
            'department': equipment.department.name if equipment.department else ''
        } for equipment in equipments]
        return {
            'type': 'list',
            'items': equipment_list,
            'total': Equipment.objects.count(),
            'data_type': 'production_equipment'
        }

    def handle_production_procedure_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产工序数量查询"""
        from apps.production.models import ProductionProcedure
        count = ProductionProcedure.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'production_procedure'
        }

    def handle_production_procedure_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产工序列表查询"""
        from apps.production.models import ProductionProcedure
        procedures = ProductionProcedure.objects.all()[:5]
        procedure_list = [{
            'id': procedure.id,
            'code': procedure.code,
            'name': procedure.name,
            'standard_time': procedure.standard_time,
            'department': procedure.department.name if procedure.department else ''
        } for procedure in procedures]
        return {
            'type': 'list',
            'items': procedure_list,
            'total': ProductionProcedure.objects.count(),
            'data_type': 'production_procedure'
        }

    def handle_supplier_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.contract.models import Supplier
        count = Supplier.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'supplier'
        }

    def handle_supplier_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.contract.models import Supplier
        suppliers = Supplier.objects.all()[:5]
        supplier_list = [{
            'id': supplier.id,
            'code': supplier.code,
            'name': supplier.name,
            'contact_person': supplier.contact_person,
            'contact_phone': supplier.contact_phone,
            'is_active': supplier.is_active
        } for supplier in suppliers]
        return {
            'type': 'list',
            'items': supplier_list,
            'total': Supplier.objects.count(),
            'data_type': 'supplier'
        }

    def handle_product_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.contract.models import Product
        count = Product.objects.filter(delete_time__isnull=True).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'product'
        }

    def handle_product_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.contract.models import Product
        products = Product.objects.filter(delete_time__isnull=True)[:5]
        product_list = [{
            'id': product.id,
            'code': product.code,
            'name': product.name,
            'specs': product.specs,
            'unit': product.unit,
            'price': product.price
        } for product in products]
        return {
            'type': 'list',
            'items': product_list,
            'total': Product.objects.filter(delete_time__isnull=True).count(),
            'data_type': 'product'
        }

    def handle_inventory_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.inventory.models import Inventory
        count = Inventory.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'inventory'
        }

    def handle_inventory_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.inventory.models import Inventory
        inventories = Inventory.objects.select_related('item', 'warehouse', 'location').all()[:5]
        inventory_list = [{
            'id': inventory.id,
            'item_code': inventory.item.code,
            'item_name': inventory.item.name,
            'warehouse': inventory.warehouse.name,
            'location': inventory.location.name if inventory.location else '',
            'available_quantity': inventory.available_quantity
        } for inventory in inventories]
        return {
            'type': 'list',
            'items': inventory_list,
            'total': Inventory.objects.count(),
            'data_type': 'inventory'
        }

    def handle_followup_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.customer.models import CustomerFollowUp
        count = CustomerFollowUp.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'followup'
        }

    def handle_followup_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.customer.models import CustomerFollowUp
        followups = CustomerFollowUp.objects.select_related('customer', 'creator').all()[:5]
        followup_list = [{
            'id': followup.id,
            'customer': followup.customer.name if followup.customer else '',
            'follow_type': followup.follow_type,
            'next_follow_time': followup.next_follow_time.strftime('%Y-%m-%d %H:%M') if followup.next_follow_time else '',
            'creator': followup.creator.username if followup.creator else ''
        } for followup in followups]
        return {
            'type': 'list',
            'items': followup_list,
            'total': CustomerFollowUp.objects.count(),
            'data_type': 'followup'
        }

    def handle_approval_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import Approval
        queryset = self._filter_approval_queryset(Approval.objects.all(), user)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'approval',
        }

    def handle_approval_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import Approval
        queryset = self._filter_approval_queryset(
            Approval.objects.select_related('flow', 'reviewer'),
            user,
        )
        items = []
        for item in queryset.order_by('-create_time')[:5]:
            items.append({
                'id': item.id,
                'title': item.title,
                'status': item.get_status_display() if hasattr(item, 'get_status_display') else item.status,
                'applicant': item.applicant_id,
                'reviewer': item.reviewer.username if item.reviewer else '',
            })
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'approval',
        }

    def handle_approval_flow_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalFlow
        queryset = ApprovalFlow.objects.all()
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'approval_flow',
        }

    def handle_approval_flow_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalFlow
        queryset = ApprovalFlow.objects.select_related('approval_type').all()
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'status': '启用' if item.is_active else '停用',
        } for item in queryset.order_by('-created_at')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'approval_flow',
        }

    def handle_approval_task_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalTask
        queryset = self._filter_approval_task_queryset(ApprovalTask.objects.all(), user)
        if entities.get('status') in {'pending', '待处理', '待审批'}:
            queryset = queryset.filter(status='pending')
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'approval_task',
            'status': entities.get('status'),
        }

    def handle_approval_task_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalTask
        queryset = self._filter_approval_task_queryset(
            ApprovalTask.objects.select_related('approval', 'handler', 'step'),
            user,
        )
        if entities.get('status') in {'pending', '待处理', '待审批'}:
            queryset = queryset.filter(status='pending')
        items = []
        for item in queryset.order_by('-created_at')[:5]:
            items.append({
                'id': item.id,
                'title': item.approval.title if item.approval else '未知审批',
                'status': item.get_status_display() if hasattr(item, 'get_status_display') else item.status,
                'handler': item.handler.username if item.handler else '',
            })
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'approval_task',
            'status': entities.get('status'),
        }

    def handle_task_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.task.models import Task
        queryset = self._filter_task_queryset(Task.objects.all(), user)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'task',
        }

    def handle_task_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.task.models import Task
        queryset = self._filter_task_queryset(Task.objects.select_related('assignee'), user)
        items = [{
            'id': item.id,
            'title': item.title,
            'status': item.get_status_display() if hasattr(item, 'get_status_display') else item.status,
            'assignee': item.assignee.username if item.assignee else '',
        } for item in queryset.order_by('-created_at')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'task',
        }

    def handle_message_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.message.models import Message
        queryset = self._filter_message_queryset(Message.objects.filter(is_active=True), user)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'message',
        }

    def handle_message_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.message.models import Message
        queryset = self._filter_message_queryset(
            Message.objects.select_related('sender').filter(is_active=True),
            user,
        )
        items = [{
            'id': item.id,
            'title': item.title,
            'sender': item.sender.username if item.sender else '',
            'is_read': False,
        } for item in queryset.order_by('-created_at')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'message',
        }

    def handle_notice_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import Notice

        queryset = self._filter_notice_queryset(Notice.objects.all(), user)
        queryset = self._apply_notice_filters(queryset, entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'notice',
            'status': entities.get('status'),
        }

    def handle_notice_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import Notice

        queryset = self._filter_notice_queryset(
            Notice.objects.select_related('author').prefetch_related('target_users', 'target_departments'),
            user,
        )
        queryset = self._apply_notice_filters(queryset, entities)
        items = [{
            'id': item.id,
            'title': item.title,
            'notice_type': item.get_notice_type_display() if hasattr(item, 'get_notice_type_display') else item.notice_type,
            'author': item.author.username if item.author else '',
            'is_published': item.is_published,
            'is_top': item.is_top,
            'publish_time': item.publish_time.strftime('%Y-%m-%d %H:%M') if item.publish_time else '',
        } for item in queryset.order_by('-is_top', '-publish_time', '-created_at')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'notice',
            'status': entities.get('status'),
        }

    def handle_meeting_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.oa.models import MeetingRecord
        queryset = self._filter_meeting_queryset(MeetingRecord.objects.all(), user)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'meeting',
        }

    def handle_meeting_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.oa.models import MeetingRecord
        queryset = self._filter_meeting_queryset(
            MeetingRecord.objects.select_related('host', 'recorder', 'room'),
            user,
        )
        items = [{
            'id': item.id,
            'title': item.title,
            'status': item.get_status_display() if hasattr(item, 'get_status_display') else item.status,
            'host': item.host.username if item.host else '',
        } for item in queryset.order_by('-meeting_date')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'meeting',
        }

    def handle_schedule_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.oa.models import Schedule

        queryset = self._filter_schedule_queryset(
            Schedule.objects.filter(delete_time=0),
            user,
        )
        queryset = self._apply_schedule_filters(queryset, entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'schedule',
        }

    def handle_schedule_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.oa.models import Schedule

        queryset = self._filter_schedule_queryset(
            Schedule.objects.filter(delete_time=0),
            user,
        )
        queryset = self._apply_schedule_filters(queryset, entities)
        ordered_items = list(queryset.order_by('-start_time')[:5])

        admin_ids = {item.admin_id for item in ordered_items}
        user_model = get_user_model()
        admin_map = {
            admin.id: admin for admin in user_model.objects.filter(id__in=admin_ids)
        } if admin_ids else {}
        items = []
        for item in ordered_items:
            admin = admin_map.get(item.admin_id)
            items.append({
                'id': item.id,
                'title': item.title,
                'start_time': item.start_time.strftime('%Y-%m-%d %H:%M') if item.start_time else '',
                'end_time': item.end_time.strftime('%Y-%m-%d %H:%M') if item.end_time else '',
                'labor_time': item.labor_time,
                'labor_type': '案头工作' if item.labor_type == 1 else '外勤工作',
                'admin_name': getattr(admin, 'username', '') if admin else '',
            })
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'schedule',
        }

    def handle_disk_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.disk.models import DiskFile
        queryset = self._filter_disk_file_queryset(DiskFile.objects.filter(delete_time__isnull=True), user)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'disk',
        }

    def handle_disk_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.disk.models import DiskFile
        queryset = self._filter_disk_file_queryset(
            DiskFile.objects.select_related('folder', 'owner', 'department').filter(delete_time__isnull=True),
            user,
        )
        status = entities.get('status')
        if status == 'starred':
            queryset = queryset.filter(is_starred=True)
        items = list(queryset.order_by('-update_time')[:5])
        disk_items = [{
            'id': item.id,
            'name': item.name,
            'folder': item.folder.name if item.folder else '',
            'owner': item.owner.username if item.owner else '',
            'is_public': item.is_public,
            'size': item.get_size_display() if hasattr(item, 'get_size_display') else '',
        } for item in items]
        return {
            'type': 'list',
            'items': disk_items,
            'total': queryset.count(),
            'data_type': 'disk',
            'status': status,
        }

    def handle_disk_folder_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.disk.models import DiskFolder
        queryset = self._filter_disk_folder_queryset(
            DiskFolder.objects.filter(delete_time__isnull=True),
            user,
        )
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'disk_folder',
        }

    def handle_disk_folder_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.disk.models import DiskFolder
        queryset = self._filter_disk_folder_queryset(
            DiskFolder.objects.select_related('parent', 'owner', 'department').filter(delete_time__isnull=True),
            user,
        )
        items = [{
            'id': item.id,
            'name': item.name,
            'folder': item.parent.name if item.parent else '',
            'owner': item.owner.username if item.owner else '',
            'is_public': item.is_public,
        } for item in queryset.order_by('-update_time')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'disk_folder',
        }

    def handle_disk_share_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.disk.models import DiskShare
        queryset = self._filter_disk_share_queryset(DiskShare.objects.all(), user)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'disk_share',
        }

    def handle_disk_share_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.disk.models import DiskShare
        queryset = self._filter_disk_share_queryset(
            DiskShare.objects.select_related('file', 'folder', 'creator'),
            user,
        )
        items = list(queryset.order_by('-create_time')[:5])
        share_items = []
        for item in items:
            source = item.file.name if item.file else (item.folder.name if item.folder else '')
            share_items.append({
                'id': item.id,
                'name': source or '未知',
                'permission_type': item.permission_type,
                'share_type': item.share_type,
                'is_active': item.is_active,
                'creator': item.creator.username if item.creator else '',
            })
        return {
            'type': 'list',
            'items': share_items,
            'total': queryset.count(),
            'data_type': 'disk_share',
        }

    def format_result(self, result: Dict[str, Any]) -> str:
        """格式化查询结果为自然语言

        Args:
            result: 查询结果

        Returns:
            str: 格式化后的自然语言
        """
        result_type = result.get('type')
        data_type = result.get('data_type')

        data_type_names = {
            'customer': '客户',
            'contact': '联系人',
            'followup': '跟进记录',
            'order': '订单',
            'contract': '合同',
            'product': '产品',
            'service': '服务项目',
            'supplier': '供应商',
            'project': '项目',
            'task': '任务',
            'workhour': '工时记录',
            'expense': '支出',
            'income': '收入',
            'invoice': '发票',
            'payment': '付款记录',
            'warehouse': '仓库',
            'inventory': '库存',
            'stockin': '入库单',
            'stockout': '出库单',
            'alert': '库存预警',
            'approval': '审批',
            'notice': '通知公告',
            'document': '文档',
            'department': '部门',
            'message': '站内消息',
            'employee': '员工',
            'finance_expense': '报销',
            'finance_invoice': '发票',
            'finance_income': '回款',
            'finance_order_record': '订单财务记录',
            'production_plan': '生产计划',
            'production_task': '生产任务',
            'production_equipment': '生产设备',
            'production_procedure': '生产工序',
            'approval_flow': '审批流程',
            'approval_task': '待办审批',
            'meeting': '会议',
            'schedule': '工作日程',
            'disk': '网盘文件',
            'disk_folder': '网盘文件夹',
            'disk_share': '网盘分享',
            'supplier': '供应商',
            'product': '产品',
            'inventory': '库存',
            'followup': '跟进记录'
        }

        if result_type == 'count':
            value = result.get('value')
            data_type_name = data_type_names.get(data_type, data_type)
            status = result.get('status')
            if status:
                return f"您有{value}个{status}的{data_type_name}。"
            else:
                return f"您有{value}个{data_type_name}。"

        elif result_type == 'sum':
            value = result.get('value')
            field_names = {
                'amount': '总额',
                'budget': '预算总额',
                'price': '总价',
                'total_amount': '总金额',
                'cost': '成本总额'
            }
            data_type_name = data_type_names.get(data_type, data_type)
            field_name = field_names.get(
                result.get('field'), result.get(
                    'field', '金额'))
            time_range = result.get('time_range')

            if isinstance(value, (int, float)):
                value_str = f"¥{value:,.2f}"
            else:
                value_str = str(value)

            if time_range == 'last_month':
                return f"上个月{data_type_name}{field_name}为{value_str}。"
            elif time_range == 'this_month':
                return f"本月{data_type_name}{field_name}为{value_str}。"
            else:
                return f"{data_type_name}{field_name}为{value_str}。"

        elif result_type == 'list':
            items = result.get('items', [])
            total = result.get('total', 0)
            data_type_name = data_type_names.get(data_type, data_type)
            status = result.get('status')
            time_range = result.get('time_range')
            event = result.get('event')

            if not items:
                if status:
                    return f"暂无{status}的{data_type_name}数据。"
                elif time_range and event:
                    if event == 'deal':
                        if time_range == 'last_month':
                            return f"暂无上个月成交的{data_type_name}数据。"
                        elif time_range == 'this_month':
                            return f"暂无本月成交的{data_type_name}数据。"
                    elif event == 'progress':
                        return f"暂无{data_type_name}进度数据。"
                else:
                    return f"暂无{data_type_name}数据。"

            item_list = []
            for item in items:
                formatted = self._format_list_item(data_type, item, event)
                if formatted:
                    item_list.append(formatted)

            item_str = '、'.join(item_list)

            if status:
                return f"共有{total}个{status}的{data_type_name}，前{len(items)}个是：{item_str}。"
            elif time_range and event:
                if event == 'deal':
                    if time_range == 'last_month':
                        return f"上个月共有{total}个成交{data_type_name}，前{len(items)}个是：{item_str}。"
                    elif time_range == 'this_month':
                        return f"本月共有{total}个成交{data_type_name}，前{len(items)}个是：{item_str}。"
                elif event == 'progress':
                    return f"共有{total}个{data_type_name}，前{len(items)}个的进度信息：{item_str}。"
            else:
                return f"共有{total}个{data_type_name}，前{len(items)}个是：{item_str}。"

        return "查询结果无法格式化。"

    def _format_list_item(self, data_type: str,
                          item: Dict[str, Any], event: str = None) -> str:
        """格式化列表项为自然语言"""
        try:
            if data_type == 'customer':
                name = item.get('name', '未知')
                status = item.get('status', '')
                if status:
                    return f"{name}（{status}）"
                return name
            elif data_type == 'contact':
                name = item.get('name', '未知')
                phone = item.get('phone', '')
                if phone:
                    return f"{name}（{phone}）"
                return name
            elif data_type == 'followup':
                content = item.get('content', '')[:20]
                return f"{content}..."
            elif data_type == 'order':
                customer = item.get(
                    'customer_name', item.get(
                        'customer', '未知'))
                amount = item.get('amount', 0)
                status = item.get('status', '')
                return f"{customer}（¥{amount:,.2f}，{status}）"
            elif data_type == 'contract':
                name = item.get('name', item.get('contract_no', '未知'))
                customer = item.get('customer_name', '')
                amount = item.get('amount', 0)
                if customer:
                    return f"{name}（{customer}，¥{amount:,.2f}）"
                return f"{name}（¥{amount:,.2f}）"
            elif data_type == 'product':
                name = item.get('name', '未知')
                price = item.get('price', 0)
                stock = item.get('stock', 0)
                return f"{name}（¥{price:,.2f}，库存{stock}）"
            elif data_type == 'service':
                name = item.get('name', '未知')
                price = item.get('price', 0)
                return f"{name}（¥{price:,.2f}）"
            elif data_type == 'supplier':
                name = item.get('name', '未知')
                contact = item.get('contact', item.get('phone', ''))
                if contact:
                    return f"{name}（{contact}）"
                return name
            elif data_type == 'project':
                name = item.get('name', '未知')
                if event == 'progress':
                    progress = item.get('progress', 0)
                    return f"{name}（进度：{progress}%）"
                status = item.get('status', '')
                if status:
                    return f"{name}（{status}）"
                return name
            elif data_type == 'task':
                title = item.get('title', '未知')
                status = item.get('status', '')
                assignee = item.get('assignee', '')
                if assignee:
                    return f"{title}（{assignee}，{status}）"
                return f"{title}（{status}）"
            elif data_type == 'notice':
                title = item.get('title', '未知')
                notice_type = item.get('notice_type', '')
                if item.get('is_top'):
                    notice_type = f"置顶{notice_type}" if notice_type else '置顶'
                if notice_type:
                    return f"{title}（{notice_type}）"
                return title
            elif data_type == 'schedule':
                title = item.get('title', '未知')
                start_time = item.get('start_time', '')
                labor_type = item.get('labor_type', '')
                if start_time and labor_type:
                    return f"{title}（{start_time}，{labor_type}）"
                if start_time:
                    return f"{title}（{start_time}）"
                return title
            elif data_type == 'workhour':
                task = item.get('task', '未知')
                hours = item.get('hours', 0)
                date = item.get('date', '')
                return f"{task}（{hours}小时，{date}）"
            elif data_type == 'expense':
                title = item.get('title', item.get('name', '未知'))
                amount = item.get('amount', item.get('cost', 0))
                status = item.get('status', item.get('pay_status', ''))
                return f"{title}（¥{amount:,.2f}，{status}）"
            elif data_type == 'income':
                title = item.get('title', '未知')
                amount = item.get('amount', 0)
                customer = item.get('customer', item.get('customer_name', ''))
                if customer:
                    return f"{title}（{customer}，¥{amount:,.2f}）"
                return f"{title}（¥{amount:,.2f}）"
            elif data_type == 'invoice':
                no = item.get('invoice_no', item.get('invoice_code', '未知'))
                customer = item.get('customer_name', item.get('customer', ''))
                amount = item.get('amount', 0)
                if customer:
                    return f"{no}（{customer}，¥{amount:,.2f}）"
                return f"{no}（¥{amount:,.2f}）"
            elif data_type == 'payment':
                no = item.get('payment_no', '未知')
                amount = item.get('amount', 0)
                method = item.get('payment_method', '')
                status = item.get('status', '')
                return f"{no}（¥{amount:,.2f}，{method}，{status}）"
            elif data_type == 'warehouse':
                name = item.get('name', '未知')
                address = item.get('address', '')
                status = item.get('status', '')
                if address:
                    return f"{name}（{address}，{status}）"
                return f"{name}（{status}）"
            elif data_type == 'inventory':
                product = item.get('product', item.get('product_name', '未知'))
                quantity = item.get('quantity', 0)
                warehouse = item.get('warehouse', '')
                if warehouse:
                    return f"{product}（{warehouse}，{quantity}）"
                return f"{product}（{quantity}）"
            elif data_type == 'stockin':
                no = item.get('stock_in_no', '未知')
                amount = item.get('total_amount', 0)
                status = item.get('status', '')
                return f"{no}（¥{amount:,.2f}，{status}）"
            elif data_type == 'stockout':
                no = item.get('stock_out_no', '未知')
                amount = item.get('total_amount', 0)
                status = item.get('status', '')
                return f"{no}（¥{amount:,.2f}，{status}）"
            elif data_type == 'alert':
                product = item.get('product', item.get('product_name', '未知'))
                alert_type = item.get('alert_type', '')
                current = item.get('current_quantity', 0)
                return f"{product}（{alert_type}，当前{current}）"
            elif data_type == 'approval':
                title = item.get('title', '未知')
                status = item.get('status', '')
                applicant = item.get('applicant', '')
                if applicant:
                    return f"{title}（{applicant}，{status}）"
                return f"{title}（{status}）"
            elif data_type == 'approval_flow':
                name = item.get('name', '未知')
                code = item.get('code', '')
                status = item.get('status', '')
                if code:
                    return f"{name}（{code}，{status}）"
                return f"{name}（{status}）"
            elif data_type == 'approval_task':
                title = item.get('title', '未知')
                status = item.get('status', '')
                handler = item.get('handler', '')
                if handler:
                    return f"{title}（{handler}，{status}）"
                return f"{title}（{status}）"
            elif data_type == 'notice':
                title = item.get('title', '未知')
                publisher = item.get('publisher', '')
                date = item.get('publish_date', '')
                if publisher:
                    return f"{title}（{publisher}，{date}）"
                return f"{title}（{date}）"
            elif data_type == 'document':
                title = item.get('title', '未知')
                size = item.get('file_size', 0)
                user = item.get('upload_user', '')
                if user:
                    return f"{title}（{user}，{size}）"
                return f"{title}（{size}）"
            elif data_type == 'department':
                name = item.get('name', '未知')
                parent = item.get('parent', '')
                if parent:
                    return f"{name}（上级：{parent}）"
                return name
            elif data_type == 'message':
                title = item.get('title', '未知')
                sender = item.get('sender', '')
                is_read = item.get('is_read', False)
                status = '已读' if is_read else '未读'
                if sender:
                    return f"{title}（{sender}，{status}）"
                return f"{title}（{status}）"
            elif data_type == 'meeting':
                title = item.get('title', '未知')
                status = item.get('status', '')
                host = item.get('host', '')
                if host:
                    return f"{title}（{host}，{status}）"
                return f"{title}（{status}）"
            elif data_type == 'employee':
                name = item.get('name', '未知')
                dept = item.get('department', '')
                position = item.get('position', '')
                if dept and position:
                    return f"{name}（{dept}，{position}）"
                elif dept:
                    return f"{name}（{dept}）"
                return name
            elif data_type == 'production_plan':
                name = item.get('name', '未知')
                code = item.get('code', '')
                status = item.get('status', '')
                if code:
                    return f"{name}（{code}，{status}）"
                return f"{name}（{status}）"
            elif data_type == 'production_task':
                name = item.get('name', '未知')
                code = item.get('code', '')
                status = item.get('status', '')
                rate = item.get('completion_rate', 0)
                if code:
                    return f"{name}（{code}，{status}，完成率{rate}%）"
                return f"{name}（{status}，完成率{rate}%）"
            elif data_type == 'production_equipment':
                name = item.get('name', '未知')
                code = item.get('code', '')
                status = item.get('status', '')
                if code:
                    return f"{name}（{code}，{status}）"
                return f"{name}（{status}）"
            elif data_type == 'production_procedure':
                name = item.get('name', '未知')
                code = item.get('code', '')
                time = item.get('standard_time', 0)
                if code:
                    return f"{name}（{code}，标准工时{time}小时）"
                return f"{name}（标准工时{time}小时）"
            elif data_type == 'disk':
                name = item.get('name', '未知')
                folder = item.get('folder', '')
                owner = item.get('owner', '')
                if folder and owner:
                    return f"{name}（{folder}，{owner}）"
                if folder:
                    return f"{name}（{folder}）"
                return name
            elif data_type == 'disk_folder':
                name = item.get('name', '未知')
                owner = item.get('owner', '')
                folder = item.get('folder', '')
                if folder and owner:
                    return f"{name}（上级：{folder}，{owner}）"
                if owner:
                    return f"{name}（{owner}）"
                return name
            elif data_type == 'disk_share':
                name = item.get('name', '未知')
                permission_type = item.get('permission_type', '')
                share_type = item.get('share_type', '')
                if permission_type:
                    return f"{name}（{share_type}，{permission_type}）"
                return f"{name}（{share_type}）"
            else:
                return item.get(
                    'name', item.get(
                        'title', item.get(
                            'id', '未知')))
        except Exception as e:
            logger.warning(f"格式化列表项失败: {e}")
            return item.get('name', item.get('id', '未知'))

    def _filter_approval_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(
            Q(applicant_id=getattr(user, 'id', None)) |
            Q(reviewer=user) |
            Q(tasks__handler=user)
        ).distinct()

    def _filter_approval_task_queryset(self, queryset, user):
        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(handler=user)

    def _filter_task_queryset(self, queryset, user):
        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(assignee_id=getattr(user, 'id', None))

    def _filter_message_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(
            Q(user=user) |
            Q(is_broadcast=True) |
            Q(user_relations__user=user)
        ).distinct()

    def _filter_meeting_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(
            Q(host=user) |
            Q(recorder=user) |
            Q(participants=user) |
            Q(attendees=user) |
            Q(shared_users=user)
        ).distinct()

    def _filter_notice_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset

        user_dept_id = self._get_user_department_id(user)
        now = timezone.now()
        published_scope = (
            Q(is_published=True) &
            (Q(expire_time__isnull=True) | Q(expire_time__gte=now)) &
            (
                Q(target_users__id=user.id) |
                (Q(target_departments__id=user_dept_id) if user_dept_id else Q(pk__in=[])) |
                (Q(target_users__isnull=True) & Q(target_departments__isnull=True))
            )
        )
        return queryset.filter(
            Q(author=user) |
            published_scope
        ).distinct()

    def _filter_schedule_queryset(self, queryset, user):
        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(admin_id=getattr(user, 'id', None))

    def _filter_disk_folder_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset

        user_dept_id = self._get_user_department_id(user)
        return queryset.filter(
            Q(owner=user) |
            Q(shared_users__id=user.id) |
            (Q(shared_departments__id=user_dept_id) if user_dept_id else Q()) |
            Q(parent__shared_users__id=user.id) |
            (Q(parent__shared_departments__id=user_dept_id) if user_dept_id else Q())
        ).distinct()

    def _filter_disk_file_queryset(self, queryset, user):
        from django.db.models import Q
        from apps.disk.models import DiskFolder

        if getattr(user, 'is_superuser', False):
            return queryset

        user_dept_id = self._get_user_department_id(user)
        shared_folder_ids = list(
            DiskFolder.objects.filter(
                Q(shared_users__id=user.id) |
                Q(shared_departments__id=user_dept_id) if user_dept_id else Q(shared_users__id=user.id)
            ).values_list('id', flat=True).distinct()
        )
        return queryset.filter(
            Q(owner=user) |
            Q(shared_users__id=user.id) |
            (Q(shared_departments__id=user_dept_id) if user_dept_id else Q()) |
            Q(folder__shared_users__id=user.id) |
            (Q(folder__shared_departments__id=user_dept_id) if user_dept_id else Q()) |
            Q(folder__id__in=shared_folder_ids)
        ).distinct()

    def _filter_disk_share_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset
        user_dept_id = self._get_user_department_id(user)
        return queryset.filter(
            Q(creator=user) |
            Q(file__owner=user) |
            Q(folder__owner=user) |
            Q(file__shared_users__id=user.id) |
            Q(folder__shared_users__id=user.id) |
            (Q(file__shared_departments__id=user_dept_id) if user_dept_id else Q()) |
            (Q(folder__shared_departments__id=user_dept_id) if user_dept_id else Q())
        ).distinct()

    def _get_user_department_id(self, user):
        dept_id = getattr(user, 'did', None)
        if dept_id:
            return dept_id
        employee = getattr(user, 'employee', None)
        return getattr(employee, 'department_id', None)

    def _apply_notice_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'published':
            queryset = queryset.filter(is_published=True)
        elif status == 'draft':
            queryset = queryset.filter(is_published=False)
        elif status == 'top':
            queryset = queryset.filter(is_top=True)

        keyword = entities.get('keyword') or entities.get('keywords')
        if keyword:
            queryset = queryset.filter(
                models.Q(title__icontains=keyword) |
                models.Q(content__icontains=keyword)
            )

        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                queryset = queryset.filter(created_at__range=(start_at, end_at))
        return queryset

    def _apply_schedule_filters(self, queryset, entities):
        labor_type = entities.get('labor_type')
        if labor_type:
            queryset = queryset.filter(labor_type=labor_type)

        keyword = entities.get('keyword') or entities.get('keywords')
        if keyword:
            queryset = queryset.filter(
                models.Q(title__icontains=keyword) |
                models.Q(content__icontains=keyword)
            )

        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                queryset = queryset.filter(start_time__range=(start_at, end_at))
        return queryset

    def _resolve_time_range(self, time_range):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if time_range == 'today':
            return today_start, today_start + timedelta(days=1)
        if time_range == 'yesterday':
            return today_start - timedelta(days=1), today_start
        if time_range == 'this_week':
            start = today_start - timedelta(days=today_start.weekday())
            return start, start + timedelta(days=7)
        if time_range == 'last_week':
            end = today_start - timedelta(days=today_start.weekday())
            return end - timedelta(days=7), end
        if time_range == 'this_month':
            start = today_start.replace(day=1)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
            return start, end
        if time_range == 'last_month':
            current_month_start = today_start.replace(day=1)
            last_month_end = current_month_start
            last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
            return last_month_start, last_month_end
        if time_range == 'recent':
            return now - timedelta(days=30), now
        return None, None


# 全局查询服务实例
query_service = QueryService()
