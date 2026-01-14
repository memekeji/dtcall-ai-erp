"""
通用查询服务
负责处理用户查询，包括意图识别、查询生成、权限检查和结果处理
"""

import logging
from typing import Dict, Any, List, Optional
from django.db import models
from django.contrib.auth.models import User
from django.apps import apps

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
            # 通用问候
            'greeting': self.handle_greeting,
            # AI聊天
            'ai_chat': self.handle_ai_chat,
            # 客户相关
            'customer_count': self.handle_customer_count,
            'customer_count_deal': self.handle_customer_count_deal,
            'customer_count_potential': self.handle_customer_count_potential,
            'customer_list': self.handle_customer_list,
            'customer_list_deal': self.handle_customer_list_deal,
            'customer_list_potential': self.handle_customer_list_potential,
            'customer_deal_last_month': self.handle_customer_deal_last_month,
            'customer_deal_this_month': self.handle_customer_deal_this_month,
            'customer_detail': self.handle_customer_detail,
            'add_order': self.handle_add_order,
            'add_followup': self.handle_add_followup,
            
            # 订单相关
            'order_count': self.handle_order_count,
            'order_count_completed': self.handle_order_count_completed,
            'order_count_in_progress': self.handle_order_count_in_progress,
            'order_list': self.handle_order_list,
            'order_total': self.handle_order_total,
            'order_total_last_month': self.handle_order_total_last_month,
            'order_total_this_month': self.handle_order_total_this_month,
            
            # 合同相关
            'contract_count': self.handle_contract_count,
            'contract_count_effective': self.handle_contract_count_effective,
            'contract_count_expired': self.handle_contract_count_expired,
            'contract_list': self.handle_contract_list,
            'contract_total': self.handle_contract_total,
            
            # 项目相关
            'project_count': self.handle_project_count,
            'project_count_in_progress': self.handle_project_count_in_progress,
            'project_count_completed': self.handle_project_count_completed,
            'project_count_paused': self.handle_project_count_paused,
            'project_list': self.handle_project_list,
            'project_list_in_progress': self.handle_project_list_in_progress,
            'project_list_completed': self.handle_project_list_completed,
            'project_progress': self.handle_project_progress,
            
            # 发票相关
            'invoice_count': self.handle_invoice_count,
            'invoice_count_issued': self.handle_invoice_count_issued,
            'invoice_count_unissued': self.handle_invoice_count_unissued,
            'invoice_list': self.handle_invoice_list,
            
            # 员工相关
            'employee_count': self.handle_employee_count,
            'employee_count_active': self.handle_employee_count_active,
            'employee_count_inactive': self.handle_employee_count_inactive,
            'employee_list': self.handle_employee_list,
            
            # 部门相关
            'department_count': self.handle_department_count,
            'department_list': self.handle_department_list,
            
            # 财务相关
            'finance_expense_count': self.handle_finance_expense_count,
            'finance_expense_list': self.handle_finance_expense_list,
            'finance_invoice_count': self.handle_finance_invoice_count,
            'finance_invoice_list': self.handle_finance_invoice_list,
            'finance_income_count': self.handle_finance_income_count,
            'finance_income_list': self.handle_finance_income_list,
            'finance_order_record_count': self.handle_finance_order_record_count,
            'finance_order_record_list': self.handle_finance_order_record_list,
            
            # 生产相关
            'production_plan_count': self.handle_production_plan_count,
            'production_plan_list': self.handle_production_plan_list,
            'production_task_count': self.handle_production_task_count,
            'production_task_list': self.handle_production_task_list,
            'production_equipment_count': self.handle_production_equipment_count,
            'production_equipment_list': self.handle_production_equipment_list,
            'production_procedure_count': self.handle_production_procedure_count,
            'production_procedure_list': self.handle_production_procedure_list,
        }
        
        # 权限映射
        self.permission_mapping = {
            'customer': 'customer.view_customer',
            'order': 'customer.view_customerorder',
            'contract': 'contract.view_contract',
            'project': 'project.view_project',
            'invoice': 'customer.view_customerinvoice',
            'employee': 'user.view_employeefile',
            'department': 'user.view_department',
            'finance': 'finance.view_finance',
            'production': 'production.view_production',
        }
    
    def process_query(self, user: User, query: str) -> Dict[str, Any]:
        """
        处理用户查询
        
        Args:
            user: 当前用户
            query: 用户查询文本
            
        Returns:
            Dict[str, Any]: 查询结果
        """
        try:
            # 1. 直接使用query_service自己的意图识别方法获取具体意图
            specific_intent, specific_entities = self.recognize_intent(query)
            
            # 2. 权限检查
            if not self.check_permission(user, 'data_query'):
                return {
                    'success': False,
                    'message': '您没有权限访问该数据',
                    'suggestion': '请联系管理员获取相应权限'
                }
            
            # 3. 执行查询
            result = None
            
            if specific_intent:
                # 执行具体意图
                result = self.execute_query(specific_intent, specific_entities, user)
            else:
                # 如果无法获取具体意图，使用默认AI聊天响应
                result = self.execute_query('ai_chat', {}, user)
            
            # 4. 格式化结果为可读字符串
            formatted_result = self.format_result(result)
            
            return {
                'success': True,
                'intent': 'data_query',
                'confidence': 1.0,
                'result': formatted_result,
                'entities': specific_entities
            }
            
        except Exception as e:
            logger.error(f"处理查询失败: {str(e)}")
            return {
                'success': False,
                'message': f'查询过程中发生错误: {str(e)}'
            }
    
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
        
        # 检查数据添加意图
        if any(keyword in query_lower for keyword in ['添加', '新增', '创建', '增加']):
            # 提取客户名称
            import re
            customer_name_pattern = r'[\u4e00-\u9fa5]+'
            customer_name_matches = re.findall(customer_name_pattern, query_lower)
            customer_name = None
            if customer_name_matches:
                # 尝试找到最可能是客户名称的匹配项
                for match in customer_name_matches:
                    if match not in ['客户', '订单', '合同', '项目', '发票', '查询', '列出', '展示', '查看', '数量', '有多少', '几个', '统计', '关联', '所有', '的', '添加', '帮我', '新增', '创建', '增加', '跟进记录']:
                        customer_name = match
                        entities['customer_name'] = customer_name
                        break
            
            if '订单' in query_lower:
                intent = 'add_order'
            elif '跟进记录' in query_lower or '跟进' in query_lower:
                intent = 'add_followup'
        # 通用问候意图
        elif any(keyword in query_lower for keyword in ['你好', '您好', 'hi', 'hello', '早上好', '下午好', '晚上好']):
            intent = 'greeting'
        # 订单相关意图（优先于客户相关意图，因为订单查询可能包含客户名称）
        elif '订单' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                # 检查是否有客户名称关联查询
                import re
                customer_name_pattern = r'[\u4e00-\u9fa5\w]+'
                customer_name_matches = re.findall(customer_name_pattern, query_lower)
                customer_name = None
                if customer_name_matches:
                    # 尝试找到最可能是客户名称的匹配项
                    exclude_words = ['客户', '订单', '合同', '项目', '发票', '查询', '列出', '展示', '查看', '数量', '有多少', '几个', '统计', '关联', '所有', '的', '我', '有', '几', '个', '多少', '这个', '那个']
                    for match in customer_name_matches:
                        if match not in exclude_words and len(match) > 1:  # 排除单个字符
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
                customer_name_matches = re.findall(customer_name_pattern, query_lower)
                customer_name = None
                if customer_name_matches:
                    # 尝试找到最可能是客户名称的匹配项
                    exclude_words = ['客户', '订单', '合同', '项目', '发票', '查询', '列出', '展示', '查看', '数量', '有多少', '几个', '统计', '关联', '所有', '的', '我', '有', '几', '个', '多少', '我有', '有几', '几个', '多少个', '我有几个', '我有多少', '有多少']
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
        elif '生产' in query_lower or '计划' in query_lower or '任务' in query_lower or '设备' in query_lower or '工序' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                if '计划' in query_lower:
                    intent = 'production_plan_count'
                elif '任务' in query_lower:
                    intent = 'production_task_count'
                elif '设备' in query_lower:
                    intent = 'production_equipment_count'
                elif '工序' in query_lower:
                    intent = 'production_procedure_count'
            elif '列表' in query_lower or '有哪些' in query_lower:
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
        
        # 1. 基于意图的权限检查
        data_type = intent.split('_')[0]
        permission = self.permission_mapping.get(data_type)
        
        if permission:
            # 2. 使用Django内置权限系统检查
            has_perm = user.has_perm(permission)
            logger.info(f"用户 {user.username} 访问 {intent} 权限检查结果: {has_perm}")
            return has_perm
        
        # 3. 如果没有找到权限映射，尝试基于实体类型检查
        # 这是为了兼容旧的意图识别逻辑
        logger.warning(f"用户 {user.username} 访问 {intent} 未找到对应权限映射，默认允许访问")
        return True
    
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
                    items.append(f"{i}. {item.get('name', '')} ({item.get('source', '')})")
                elif data_type == 'order':
                    items.append(f"{i}. 订单号：{item.get('order_number', '')}，金额：{item.get('amount', '')}元")
                elif data_type == 'contract':
                    items.append(f"{i}. 合同名称：{item.get('customer_name', '')}，金额：{item.get('amount', '')}元")
                elif data_type == 'project':
                    items.append(f"{i}. 项目名称：{item.get('name', '')}，状态：{item.get('status', '')}")
                elif data_type == 'employee':
                    items.append(f"{i}. {item.get('name', '')}，部门：{item.get('department', '')}")
                elif data_type == 'department':
                    items.append(f"{i}. {item.get('name', '')}")
                elif data_type == 'invoice':
                    items.append(f"{i}. 发票号：{item.get('invoice_no', '')}，金额：{item.get('amount', '')}元")
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
                contracts = result.get('contracts', [])
                invoices = result.get('invoices', [])
                
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
    
    def execute_query(self, intent: str, entities: Dict[str, Any], user: User) -> Any:
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
    def handle_greeting(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理问候语"""
        return {
            'type': 'greeting',
            'value': '你好！我是您的智能助手，很高兴为您服务。请问有什么可以帮助您的吗？',
            'data_type': 'general'
        }
    
    def handle_ai_chat(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理AI聊天意图"""
        return {
            'type': 'ai_chat',
            'value': '您好！我是您的智能助手，我可以帮助您查询数据、管理客户、处理订单等。请问有什么可以帮助您的吗？',
            'data_type': 'general'
        }
    
    def handle_customer_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理客户数量查询"""
        from apps.customer.models import Customer
        
        # 构建查询集，考虑用户权限
        queryset = Customer.objects.filter(delete_time=0)  # 只查询未删除的客户
        
        # 添加实体关联计数（与客户列表视图保持一致）
        queryset = queryset.annotate(
            order_count=models.Count('orders', filter=models.Q(orders__delete_time=0)),
            contract_count=models.Count('contracts', filter=models.Q(contracts__delete_time=0)),
            project_count=models.Count('projects'),
            invoice_count=models.Count('invoices', filter=models.Q(invoices__delete_time=0))
        )
        
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
    
    def handle_customer_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理客户列表查询"""
        from apps.customer.models import Customer
        
        # 构建查询集，考虑用户权限
        queryset = Customer.objects.filter(delete_time=0)  # 只查询未删除的客户
        
        # 添加实体关联计数（与客户列表视图保持一致）
        queryset = queryset.annotate(
            order_count=models.Count('orders', filter=models.Q(orders__delete_time=0)),
            contract_count=models.Count('contracts', filter=models.Q(contracts__delete_time=0)),
            project_count=models.Count('projects'),
            invoice_count=models.Count('invoices', filter=models.Q(invoices__delete_time=0))
        )
        
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
            'belong_to': customer.principal.name if customer.principal else '未分配'  # 使用principal字段获取负责人名称
        } for customer in customers]
        
        return {
            'type': 'list',
            'items': customer_list,
            'total': queryset.count(),
            'page': page,
            'page_size': page_size,
            'data_type': 'customer'
        }
    
    def handle_order_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
            customer_queryset = customer_queryset.filter(name__icontains=customer_name)
        
        # 获取符合条件的客户ID列表
        customer_ids = customer_queryset.values_list('id', flat=True)
        
        # 构建订单查询集，只查询未删除的订单
        queryset = CustomerOrder.objects.filter(delete_time=0, customer_id__in=customer_ids)
        
        count = queryset.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'order'
        }
    
    def handle_order_total(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理订单总额查询"""
        from apps.customer.models import CustomerOrder, Customer
        
        # 构建查询集，考虑用户权限
        queryset = CustomerOrder.objects.all()
        
        # 如果不是超级管理员，只计算归属自己的客户的订单总额
        if not user.is_superuser:
            # 获取当前用户的客户ID列表
            user_customer_ids = Customer.objects.filter(belong_uid=user.id).values_list('id', flat=True)
            queryset = queryset.filter(customer_id__in=user_customer_ids)
        
        total_amount = queryset.aggregate(total=models.Sum('amount'))['total'] or 0
        return {
            'type': 'sum',
            'value': total_amount,
            'data_type': 'order',
            'field': 'amount'
        }
    
    def handle_contract_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理合同数量查询"""
        from apps.contract.models import Contract
        count = Contract.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'contract'
        }
    
    def handle_project_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理项目数量查询"""
        from apps.project.models import Project
        count = Project.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'project'
        }
    
    def handle_invoice_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理发票数量查询"""
        from apps.customer.models import CustomerInvoice
        count = CustomerInvoice.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'invoice'
        }
    
    def handle_employee_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理员工数量查询"""
        from apps.user.models import EmployeeFile
        count = EmployeeFile.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'employee'
        }
    
    def handle_project_count_in_progress(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_project_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_project_list_in_progress(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_customer_deal_last_month(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
        admin_ids = [customer.belong_uid for customer in customers if customer.belong_uid]
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
    
    def handle_customer_count_deal(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
        customer_ids = order_queryset.filter(customer_id__in=user_customer_ids).values_list('customer_id', flat=True).distinct()
        
        # 计算成交客户数量
        count = Customer.objects.filter(id__in=customer_ids).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'customer',
            'status': '成交'
        }
    
    def handle_customer_count_potential(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
        customer_ids_with_orders = order_queryset.filter(customer_id__in=user_customer_ids).values_list('customer_id', flat=True).distinct()
        
        # 查询没有订单但有意向的客户
        count = Customer.objects.filter(id__in=user_customer_ids).exclude(id__in=customer_ids_with_orders).filter(intent_status__gt=0).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'customer',
            'status': '潜在'
        }
    
    def handle_customer_list_deal(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
        customer_ids = order_queryset.filter(customer_id__in=user_customer_ids).values_list('customer_id', flat=True).distinct()
        
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
    
    def handle_customer_list_potential(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
        customer_ids_with_orders = order_queryset.filter(customer_id__in=user_customer_ids).values_list('customer_id', flat=True).distinct()
        
        # 查询没有订单但有意向的客户
        customers = Customer.objects.filter(id__in=user_customer_ids).exclude(id__in=customer_ids_with_orders).filter(intent_status__gt=0)[:5]
        customer_list = [{
            'id': customer.id,
            'name': customer.name,
            'source': customer.customer_source.title if customer.customer_source else '',
            'status': customer.intent_status
        } for customer in customers]
        return {
            'type': 'list',
            'items': customer_list,
            'total': Customer.objects.filter(id__in=user_customer_ids).exclude(id__in=customer_ids_with_orders).filter(intent_status__gt=0).count(),
            'data_type': 'customer',
            'status': '潜在'
        }
    
    def handle_customer_deal_this_month(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理本月成交客户查询"""
        from apps.customer.models import Customer, CustomerOrder
        from apps.user.models import Admin
        from datetime import datetime, timedelta
        
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
        admin_ids = [customer.belong_uid for customer in customers if customer.belong_uid]
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
    
    def handle_customer_detail(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
        customer = customer_queryset.filter(name__icontains=customer_name).first()
        if not customer:
            return {
                'type': 'error',
                'message': f'未找到名称包含{customer_name}的客户',
                'data_type': 'customer'
            }
        
        # 获取客户的所有订单
        orders = CustomerOrder.objects.filter(customer=customer).order_by('-order_date')
        order_list = [{
            'order_id': order.id,
            'order_number': order.order_number,
            'amount': order.amount,
            'status': order.status,
            'order_date': order.order_date.strftime('%Y-%m-%d %H:%M:%S') if order.order_date else '',
            'delivery_date': order.delivery_date.strftime('%Y-%m-%d') if order.delivery_date else ''
        } for order in orders]
        
        # 获取客户的所有合同
        contracts = Contract.objects.filter(customer__icontains=customer.name).order_by('-sign_time')
        import time
        contract_list = [{
            'contract_id': contract.id,
            'contract_no': contract.code,
            'amount': contract.cost,
            'status': contract.check_status,
            'sign_date': time.strftime('%Y-%m-%d', time.localtime(contract.sign_time)) if contract.sign_time else ''
        } for contract in contracts]
        
        # 获取客户的所有发票
        invoices = CustomerInvoice.objects.filter(customer=customer).order_by('-issue_date')
        invoice_list = [{
            'invoice_id': invoice.id,
            'invoice_no': invoice.invoice_no,
            'amount': invoice.amount,
            'status': invoice.status,
            'issue_date': invoice.issue_date.strftime('%Y-%m-%d') if invoice.issue_date else ''
        } for invoice in invoices]
        
        # 计算统计数据
        total_orders = orders.count()
        total_order_amount = orders.aggregate(total=models.Sum('amount'))['total'] or 0
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
    def handle_order_count_completed(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理已完成订单数量查询"""
        from apps.customer.models import CustomerOrder
        count = CustomerOrder.objects.filter(status='已完成').count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'order',
            'status': '已完成'
        }
    
    def handle_order_count_in_progress(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理进行中订单数量查询"""
        from apps.customer.models import CustomerOrder
        count = CustomerOrder.objects.filter(status='进行中').count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'order',
            'status': '进行中'
        }
    
    def handle_order_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理订单列表查询"""
        from apps.customer.models import CustomerOrder, Customer
        
        # 构建查询集，考虑用户权限
        queryset = CustomerOrder.objects.all().select_related('customer')
        
        # 如果不是超级管理员，只显示归属自己的客户的订单
        if not user.is_superuser:
            # 获取当前用户的客户ID列表
            user_customer_ids = Customer.objects.filter(belong_uid=user.id).values_list('id', flat=True)
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
    
    def handle_order_total_last_month(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_order_total_this_month(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    def handle_contract_count_effective(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_contract_count_expired(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_contract_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_contract_total(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理合同总额查询"""
        from apps.contract.models import Contract
        total_amount = Contract.objects.aggregate(total=models.Sum('cost'))['total'] or 0
        return {
            'type': 'sum',
            'value': total_amount,
            'data_type': 'contract',
            'field': 'cost'
        }
    
    # 项目相关处理函数
    def handle_project_count_completed(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_project_count_paused(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_project_list_completed(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_project_progress(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    def handle_invoice_count_issued(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理已开具发票数量查询"""
        from apps.customer.models import CustomerInvoice
        count = CustomerInvoice.objects.filter(status='已开具').count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'invoice',
            'status': '已开具'
        }
    
    def handle_invoice_count_unissued(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理未开具发票数量查询"""
        from apps.customer.models import CustomerInvoice
        count = CustomerInvoice.objects.filter(status='未开具').count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'invoice',
            'status': '未开具'
        }
    
    def handle_invoice_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理发票列表查询"""
        from apps.customer.models import CustomerInvoice, Customer
        
        # 构建查询集，考虑用户权限
        queryset = CustomerInvoice.objects.all().select_related('customer')
        
        # 如果不是超级管理员，只显示归属自己的客户的发票
        if not user.is_superuser:
            # 获取当前用户的客户ID列表
            user_customer_ids = Customer.objects.filter(belong_uid=user.id).values_list('id', flat=True)
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
    
    def handle_add_order(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理添加订单请求"""
        from apps.customer.models import Customer, CustomerOrder
        from datetime import datetime
        
        # 验证必填字段
        customer_name = entities.get('customer_name')
        if not customer_name:
            return {
                'type': 'error',
                'message': '请提供客户名称',
                'data_type': 'order'
            }
        
        # 查找客户
        customer = Customer.objects.filter(name__icontains=customer_name).first()
        if not customer:
            return {
                'type': 'error',
                'message': f'未找到名称包含{customer_name}的客户',
                'data_type': 'order'
            }
        
        # 检查用户权限，确保只有客户归属者或管理员才能添加订单
        if not user.is_superuser and customer.belong_uid != user.id:
            return {
                'type': 'error',
                'message': '您没有权限为该客户添加订单',
                'data_type': 'order'
            }
        
        # 创建新订单
        try:
            # 这里可以根据实际需求从entities中提取更多订单信息
            # 目前默认创建一个基本订单
            order = CustomerOrder.objects.create(
                customer=customer,
                order_number=f'ORD-{datetime.now().strftime("%Y%m%d%H%M%S")}',
                amount=0.0,
                status='待处理',
                order_date=datetime.now()
            )
            
            return {
                'type': 'success',
                'message': f'成功为客户{customer_name}添加订单，订单号：{order.order_number}',
                'order_id': order.id,
                'order_number': order.order_number,
                'data_type': 'order'
            }
        except Exception as e:
            logger.error(f'添加订单失败: {str(e)}')
            return {
                'type': 'error',
                'message': '添加订单失败，请稍后重试',
                'data_type': 'order'
            }
    
    def handle_add_followup(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理添加客户跟进记录请求"""
        from apps.customer.models import Customer
        from datetime import datetime
        
        # 验证必填字段
        customer_name = entities.get('customer_name')
        if not customer_name:
            return {
                'type': 'error',
                'message': '请提供客户名称',
                'data_type': 'followup'
            }
        
        # 查找客户
        customer = Customer.objects.filter(name__icontains=customer_name).first()
        if not customer:
            return {
                'type': 'error',
                'message': f'未找到名称包含{customer_name}的客户',
                'data_type': 'followup'
            }
        
        # 检查用户权限，确保只有客户归属者或管理员才能添加跟进记录
        if not user.is_superuser and customer.belong_uid != user.id:
            return {
                'type': 'error',
                'message': '您没有权限为该客户添加跟进记录',
                'data_type': 'followup'
            }
        
        # 创建新跟进记录
        try:
            # 检查是否存在客户跟进记录表
            from django.apps import apps
            FollowupModel = None
            
            # 尝试获取客户跟进记录表
            try:
                FollowupModel = apps.get_model('customer', 'CustomerFollowup')
            except LookupError:
                try:
                    FollowupModel = apps.get_model('customer', 'Followup')
                except LookupError:
                    pass
            
            if FollowupModel:
                # 如果存在跟进记录表，创建新记录
                followup = FollowupModel.objects.create(
                    customer=customer,
                    followup_type='电话',  # 默认跟进类型
                    content='系统自动创建的跟进记录',  # 默认内容，实际应用中应该从entities中提取
                    followup_person=user.username,
                    create_time=datetime.now()
                )
                return {
                    'type': 'success',
                    'message': f'成功为客户{customer_name}添加跟进记录',
                    'followup_id': followup.id,
                    'data_type': 'followup'
                }
            else:
                # 如果不存在跟进记录表，返回提示
                return {
                    'type': 'error',
                    'message': '客户跟进记录功能尚未实现',
                    'data_type': 'followup'
                }
        except Exception as e:
            logger.error(f'添加跟进记录失败: {str(e)}')
            return {
                'type': 'error',
                'message': '添加跟进记录失败，请稍后重试',
                'data_type': 'followup'
            }
    
    # 员工相关处理函数
    def handle_employee_count_active(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_employee_count_inactive(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_employee_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    def handle_department_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理部门数量查询"""
        from apps.department.models import Department
        count = Department.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'department'
        }
    
    def handle_department_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    def handle_finance_expense_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理报销数量查询"""
        from apps.finance.models import Expense
        count = Expense.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'finance_expense'
        }
    
    def handle_finance_expense_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_finance_invoice_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理发票数量查询"""
        from apps.finance.models import Invoice
        count = Invoice.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'finance_invoice'
        }
    
    def handle_finance_invoice_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_finance_income_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理回款数量查询"""
        from apps.finance.models import Income
        count = Income.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'finance_income'
        }
    
    def handle_finance_income_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_finance_order_record_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理订单财务记录数量查询"""
        from apps.finance.models import OrderFinanceRecord
        count = OrderFinanceRecord.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'finance_order_record'
        }
    
    def handle_finance_order_record_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    def handle_production_plan_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产计划数量查询"""
        from apps.production.models import ProductionPlan
        count = ProductionPlan.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'production_plan'
        }
    
    def handle_production_plan_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_production_task_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产任务数量查询"""
        from apps.production.models import ProductionTask
        count = ProductionTask.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'production_task'
        }
    
    def handle_production_task_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_production_equipment_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产设备数量查询"""
        from apps.production.models import Equipment
        count = Equipment.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'production_equipment'
        }
    
    def handle_production_equipment_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def handle_production_procedure_count(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产工序数量查询"""
        from apps.production.models import ProductionProcedure
        count = ProductionProcedure.objects.count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'production_procedure'
        }
    
    def handle_production_procedure_list(self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
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
    
    def format_result(self, result: Dict[str, Any]) -> str:
        """格式化查询结果为自然语言
        
        Args:
            result: 查询结果
            
        Returns:
            str: 格式化后的自然语言
        """
        result_type = result.get('type')
        data_type = result.get('data_type')
        
        if result_type == 'count':
            value = result.get('value')
            data_type_names = {
                'customer': '客户',
                'order': '订单',
                'contract': '合同',
                'project': '项目',
                'invoice': '发票',
                'employee': '员工',
                'department': '部门',
                'finance_expense': '报销',
                'finance_invoice': '发票',
                'finance_income': '回款',
                'finance_order_record': '订单财务记录',
                'production_plan': '生产计划',
                'production_task': '生产任务',
                'production_equipment': '生产设备',
                'production_procedure': '生产工序'
            }
            data_type_name = data_type_names.get(data_type, data_type)
            status = result.get('status')
            if status:
                return f"您有{value}个{status}的{data_type_name}。"
            else:
                return f"您有{value}个{data_type_name}。"
        
        elif result_type == 'sum':
            value = result.get('value')
            data_type_names = {
                'order': '订单',
                'contract': '合同',
                'invoice': '发票'
            }
            field_names = {
                'amount': '总额'
            }
            data_type_name = data_type_names.get(data_type, data_type)
            field_name = field_names.get(result.get('field'), result.get('field'))
            time_range = result.get('time_range')
            
            if time_range == 'last_month':
                return f"上个月{data_type_name}{field_name}为{value}。"
            elif time_range == 'this_month':
                return f"本月{data_type_name}{field_name}为{value}。"
            else:
                return f"{data_type_name}{field_name}为{value}。"
        
        elif result_type == 'list':
            items = result.get('items', [])
            total = result.get('total', 0)
            data_type_names = {
                'customer': '客户',
                'order': '订单',
                'contract': '合同',
                'project': '项目',
                'invoice': '发票',
                'employee': '员工',
                'department': '部门',
                'finance_expense': '报销',
                'finance_invoice': '发票',
                'finance_income': '回款',
                'finance_order_record': '订单财务记录',
                'production_plan': '生产计划',
                'production_task': '生产任务',
                'production_equipment': '生产设备',
                'production_procedure': '生产工序'
            }
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
            
            # 格式化列表
            item_list = []
            for item in items:
                if data_type == 'customer':
                    item_list.append(f"{item['name']}（{item['status']}）")
                elif data_type == 'project':
                    if event == 'progress':
                        item_list.append(f"{item['name']}（进度：{item['progress']}%）")
                    else:
                        item_list.append(f"{item['name']}（{item['status']}）")
                elif data_type == 'order':
                    item_list.append(f"{item['customer_name']}（{item['amount']}元，{item['status']}）")
                elif data_type == 'contract':
                    item_list.append(f"{item['contract_no']}（{item['customer_name']}，{item['amount']}元）")
                elif data_type == 'invoice':
                    item_list.append(f"{item['invoice_no']}（{item['customer_name']}，{item['amount']}元）")
                elif data_type == 'employee':
                    item_list.append(f"{item['name']}（{item['department']}，{item['position']}）")
                elif data_type == 'department':
                    item_list.append(f"{item['name']}（上级：{item['parent']}）")
                elif data_type == 'finance_expense':
                    item_list.append(f"{item['code']}（{item['cost']}元，{item['pay_status']}）")
                elif data_type == 'finance_invoice':
                    item_list.append(f"{item['code']}（{item['amount']}元，{item['open_status']}）")
                elif data_type == 'finance_income':
                    item_list.append(f"{item['invoice_code']}（{item['amount']}元，{item['income_date']}）")
                elif data_type == 'finance_order_record':
                    item_list.append(f"{item['order_number']}（{item['total_amount']}元，{item['payment_status']}）")
                elif data_type == 'production_plan':
                    item_list.append(f"{item['name']}（{item['code']}，{item['status']}）")
                elif data_type == 'production_task':
                    item_list.append(f"{item['name']}（{item['code']}，{item['status']}，完成率：{item['completion_rate']}%）")
                elif data_type == 'production_equipment':
                    item_list.append(f"{item['name']}（{item['code']}，{item['status']}）")
                elif data_type == 'production_procedure':
                    item_list.append(f"{item['name']}（{item['code']}，标准工时：{item['standard_time']}小时）")
                else:
                    item_list.append(f"{item.get('name', item.get('id', '未知'))}")
            
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


# 全局查询服务实例
query_service = QueryService()
