"""
智能数据助手服务 V5 - 完整CRUD权限版
- 真实 AI 意图分析
- 完整增删改查支持
- 数据权限安全保障（与登录账号一致）
"""

import re
import json
import logging
from datetime import datetime, timedelta
from django.db.models import Q, Sum, Avg, Max, Min

logger = logging.getLogger(__name__)


class IntelligentDataAssistant:
    """智能数据助手 - 理解自然语言并执行数据操作"""

    def __init__(self, ai_client=None, user=None):
        self.ai_client = ai_client
        self.user = user
        self._models_cache = {}
        self.model_mappings = self._init_model_mappings()
        self._permission_cache = {}

        self.operation_keywords = {
            'QUERY': [
                '查询',
                '找',
                '看看',
                '有多少',
                '统计',
                '汇总',
                '列表',
                '查看',
                '搜索',
                '筛选',
                '获取',
                '显示',
                '列出',
                '获取到',
                '看看有没有'],
            'CREATE': [
                '创建',
                '新增',
                '添加',
                '增加',
                '录入',
                '新建',
                '开',
                '登记',
                '备案',
                '添加一个',
                '增加一个'],
            'UPDATE': [
                '修改',
                '更新',
                '编辑',
                '调整',
                '变更',
                '改',
                '换',
                '把...改成',
                '把...改为',
                '更新为'],
            'DELETE': [
                '删除',
                '移除',
                '清除',
                '取消',
                '作废',
                '去掉']}

        self.statistics_keywords = [
            '统计',
            '汇总',
            '合计',
            '总数',
            '总金额',
            '总数量',
            '平均',
            '最大',
            '最小',
            '求和']

    def _init_model_mappings(self):
        """初始化数据模型映射"""
        mappings = {}

        try:
            from apps.customer.models import Customer, Contact, FollowRecord, CustomerOrder
            mappings['客户'] = {
                'model': Customer,
                'fields': [
                    'name',
                    'phone',
                    'company',
                    'industry',
                    'level',
                    'source',
                    'status'],
                'keywords': [
                    '客户',
                    '顾客',
                    '客户信息'],
                'primary_field': 'name',
                'display_fields': [
                    'name',
                    'phone',
                    'company',
                    'level',
                    'status'],
                'search_fields': [
                    'name',
                    'phone',
                    'company'],
                'date_field': 'created_at',
                'amount_field': None,
                'permission_check': 'customer',
                'can_add': 'customer.add_customer',
                'can_change': 'customer.change_customer',
                'can_delete': 'customer.delete_customer',
                'owner_field': 'created_by'}
            mappings['联系人'] = {
                'model': Contact,
                'fields': [
                    'name',
                    'phone',
                    'email',
                    'position',
                    'customer'],
                'keywords': [
                    '联系人',
                    '联系方式'],
                'primary_field': 'name',
                'display_fields': [
                    'name',
                    'phone',
                    'position',
                    'customer'],
                'search_fields': [
                    'name',
                    'phone',
                    'email'],
                'date_field': 'created_at',
                'amount_field': None,
                'permission_check': 'contact',
                'can_add': 'customer.add_contact',
                'can_change': 'customer.change_contact',
                'can_delete': 'customer.delete_contact',
                'owner_field': 'created_by'}
            mappings['跟进记录'] = {
                'model': FollowRecord,
                'fields': [
                    'customer',
                    'content',
                    'type',
                    'next_plan',
                    'created_at'],
                'keywords': [
                    '跟进',
                    '沟通记录',
                    '拜访',
                    '回访'],
                'primary_field': 'id',
                'display_fields': [
                    'customer',
                    'content',
                    'type',
                    'created_at'],
                'search_fields': ['content'],
                'date_field': 'created_at',
                'amount_field': None,
                'permission_check': 'followup',
                'can_add': 'customer.add_followrecord',
                'can_change': 'customer.change_followrecord',
                'can_delete': 'customer.delete_followrecord',
                'owner_field': 'created_by'}
            mappings['订单'] = {
                'model': CustomerOrder,
                'fields': [
                    'order_no',
                    'customer',
                    'amount',
                    'status',
                    'order_date'],
                'keywords': [
                    '订单',
                    '销售订单'],
                'primary_field': 'order_no',
                'display_fields': [
                    'order_no',
                    'customer',
                    'amount',
                    'status',
                    'order_date'],
                'search_fields': [
                    'order_no',
                    'customer__name'],
                'date_field': 'order_date',
                'amount_field': 'amount',
                'permission_check': 'order',
                'can_add': 'customer.add_customerorder',
                'can_change': 'customer.change_customerorder',
                'can_delete': 'customer.delete_customerorder',
                'owner_field': 'created_by'}
        except Exception as e:
            logger.warning(f"加载客户模块失败: {e}")

        try:
            from apps.contract.models import Contract, Product, Services, Supplier
            mappings['合同'] = {
                'model': Contract,
                'fields': [
                    'name',
                    'customer',
                    'amount',
                    'status',
                    'sign_date'],
                'keywords': [
                    '合同',
                    '合约',
                    '协议'],
                'primary_field': 'name',
                'display_fields': [
                    'name',
                    'customer',
                    'amount',
                    'status',
                    'sign_date'],
                'search_fields': [
                    'name',
                    'customer__name'],
                'date_field': 'sign_date',
                'amount_field': 'amount',
                'permission_check': 'contract',
                'can_add': 'contract.add_contract',
                'can_change': 'contract.change_contract',
                'can_delete': 'contract.delete_contract',
                'owner_field': 'created_by'}
            mappings['产品'] = {
                'model': Product,
                'fields': [
                    'name',
                    'category',
                    'specification',
                    'price',
                    'stock'],
                'keywords': [
                    '产品',
                    '商品',
                    '货物'],
                'primary_field': 'name',
                'display_fields': [
                    'name',
                    'category',
                    'price',
                    'stock'],
                'search_fields': [
                    'name',
                    'specification'],
                'date_field': 'created_at',
                'amount_field': 'price',
                'permission_check': 'product',
                'can_add': 'contract.add_product',
                'can_change': 'contract.change_product',
                'can_delete': 'contract.delete_product',
                'owner_field': 'created_by'}
            mappings['服务项目'] = {
                'model': Services,
                'fields': [
                    'name',
                    'category',
                    'price',
                    'duration'],
                'keywords': [
                    '服务',
                    '服务项目'],
                'primary_field': 'name',
                'display_fields': [
                    'name',
                    'category',
                    'price',
                    'duration'],
                'search_fields': ['name'],
                'date_field': 'created_at',
                'amount_field': 'price',
                'permission_check': 'service',
                'can_add': 'contract.add_services',
                'can_change': 'contract.change_services',
                'can_delete': 'contract.delete_services',
                'owner_field': 'created_by'}
            mappings['供应商'] = {
                'model': Supplier,
                'fields': [
                    'name',
                    'contact',
                    'phone',
                    'address'],
                'keywords': [
                    '供应商',
                    '供货商',
                    '厂商'],
                'primary_field': 'name',
                'display_fields': [
                    'name',
                    'contact',
                    'phone',
                    'category'],
                'search_fields': [
                    'name',
                    'contact'],
                'date_field': 'created_at',
                'amount_field': None,
                'permission_check': 'supplier',
                'can_add': 'contract.add_supplier',
                'can_change': 'contract.change_supplier',
                'can_delete': 'contract.delete_supplier',
                'owner_field': 'created_by'}
        except Exception as e:
            logger.warning(f"加载合同模块失败: {e}")

        try:
            from apps.project.models import Project, Task, WorkHour
            mappings['项目'] = {
                'model': Project,
                'fields': [
                    'name',
                    'category',
                    'status',
                    'start_date',
                    'budget',
                    'progress'],
                'keywords': [
                    '项目',
                    '工程项目'],
                'primary_field': 'name',
                'display_fields': [
                    'name',
                    'category',
                    'status',
                    'progress',
                    'start_date'],
                'search_fields': [
                    'name',
                    'description'],
                'date_field': 'start_date',
                'amount_field': 'budget',
                'permission_check': 'project',
                'can_add': 'project.add_project',
                'can_change': 'project.change_project',
                'can_delete': 'project.delete_project',
                'owner_field': 'created_by'}
            mappings['任务'] = {
                'model': Task,
                'fields': [
                    'title',
                    'project',
                    'assignee',
                    'status',
                    'priority',
                    'progress'],
                'keywords': [
                    '任务',
                    '工作',
                    '待办',
                    'todo'],
                'primary_field': 'title',
                'display_fields': [
                    'title',
                    'project',
                    'assignee',
                    'status',
                    'priority'],
                'search_fields': [
                    'title',
                    'description'],
                'date_field': 'start_date',
                'amount_field': None,
                'permission_check': 'task',
                'can_add': 'project.add_task',
                'can_change': 'project.change_task',
                'can_delete': 'project.delete_task',
                'owner_field': 'created_by'}
            mappings['工时记录'] = {
                'model': WorkHour,
                'fields': [
                    'task',
                    'user',
                    'date',
                    'hours'],
                'keywords': [
                    '工时',
                    '工时记录',
                    '打卡'],
                'primary_field': 'id',
                'display_fields': [
                    'task',
                    'user',
                    'date',
                    'hours'],
                'search_fields': ['description'],
                'date_field': 'date',
                'amount_field': None,
                'permission_check': 'workhour',
                'can_add': 'project.add_workhour',
                'can_change': 'project.change_workhour',
                'can_delete': 'project.delete_workhour',
                'owner_field': 'user'}
        except Exception as e:
            logger.warning(f"加载项目模块失败: {e}")

        try:
            from apps.finance.models import Expense, Income, Invoice, Payment
            mappings['支出'] = {
                'model': Expense,
                'fields': [
                    'title',
                    'amount',
                    'category',
                    'date',
                    'status'],
                'keywords': [
                    '支出',
                    '费用',
                    '开销',
                    '报销'],
                'primary_field': 'title',
                'display_fields': [
                    'title',
                    'amount',
                    'category',
                    'date',
                    'status'],
                'search_fields': [
                    'title',
                    'remark'],
                'date_field': 'date',
                'amount_field': 'amount',
                'permission_check': 'expense',
                'can_add': 'finance.add_expense',
                'can_change': 'finance.change_expense',
                'can_delete': 'finance.delete_expense',
                'owner_field': 'created_by'}
            mappings['收入'] = {
                'model': Income,
                'fields': [
                    'title',
                    'amount',
                    'customer',
                    'date',
                    'status'],
                'keywords': [
                    '收入',
                    '收款',
                    '进账',
                    '回款'],
                'primary_field': 'title',
                'display_fields': [
                    'title',
                    'amount',
                    'customer',
                    'date',
                    'status'],
                'search_fields': [
                    'title',
                    'customer__name'],
                'date_field': 'date',
                'amount_field': 'amount',
                'permission_check': 'income',
                'can_add': 'finance.add_income',
                'can_change': 'finance.change_income',
                'can_delete': 'finance.delete_income',
                'owner_field': 'created_by'}
            mappings['发票'] = {
                'model': Invoice,
                'fields': [
                    'invoice_no',
                    'customer',
                    'amount',
                    'type',
                    'status',
                    'date'],
                'keywords': [
                    '发票',
                    '收据',
                    '开票'],
                'primary_field': 'invoice_no',
                'display_fields': [
                    'invoice_no',
                    'customer',
                    'amount',
                    'type',
                    'status',
                    'date'],
                'search_fields': [
                    'invoice_no',
                    'customer__name'],
                'date_field': 'date',
                'amount_field': 'amount',
                'permission_check': 'invoice',
                'can_add': 'finance.add_invoice',
                'can_change': 'finance.change_invoice',
                'can_delete': 'finance.delete_invoice',
                'owner_field': 'created_by'}
            mappings['付款记录'] = {
                'model': Payment,
                'fields': [
                    'payment_no',
                    'amount',
                    'payment_method',
                    'status',
                    'payment_date'],
                'keywords': [
                    '付款',
                    '支付',
                    '转账'],
                'primary_field': 'payment_no',
                'display_fields': [
                    'payment_no',
                    'amount',
                    'payment_method',
                    'status'],
                'search_fields': ['payment_no'],
                'date_field': 'payment_date',
                'amount_field': 'amount',
                'permission_check': 'payment',
                'can_add': 'finance.add_payment',
                'can_change': 'finance.change_payment',
                'can_delete': 'finance.delete_payment',
                'owner_field': 'created_by'}
        except Exception as e:
            logger.warning(f"加载财务模块失败: {e}")

        try:
            from apps.inventory.models import Warehouse, InventoryItem, StockIn, StockOut, InventoryAlert
            mappings['仓库'] = {
                'model': Warehouse,
                'fields': [
                    'name',
                    'address',
                    'manager',
                    'status'],
                'keywords': [
                    '仓库',
                    '库房'],
                'primary_field': 'name',
                'display_fields': [
                    'name',
                    'address',
                    'manager',
                    'status'],
                'search_fields': [
                    'name',
                    'address'],
                'date_field': 'created_at',
                'amount_field': None,
                'permission_check': 'warehouse',
                'can_add': 'inventory.add_warehouse',
                'can_change': 'inventory.change_warehouse',
                'can_delete': 'inventory.delete_warehouse',
                'owner_field': 'created_by'}
            mappings['库存'] = {
                'model': InventoryItem,
                'fields': [
                    'product',
                    'warehouse',
                    'quantity',
                    'available_quantity'],
                'keywords': [
                    '库存',
                    '存货'],
                'primary_field': 'id',
                'display_fields': [
                    'product',
                    'warehouse',
                    'quantity'],
                'search_fields': ['product__name'],
                'date_field': 'updated_at',
                'amount_field': None,
                'permission_check': 'inventory',
                'can_add': 'inventory.add_inventoryitem',
                'can_change': 'inventory.change_inventoryitem',
                'can_delete': 'inventory.delete_inventoryitem',
                'owner_field': 'created_by'}
            mappings['入库单'] = {
                'model': StockIn,
                'fields': [
                    'stock_in_no',
                    'warehouse',
                    'total_amount',
                    'status',
                    'stock_in_date'],
                'keywords': [
                    '入库',
                    '进货入库'],
                'primary_field': 'stock_in_no',
                'display_fields': [
                    'stock_in_no',
                    'warehouse',
                    'total_amount',
                    'status'],
                'search_fields': ['stock_in_no'],
                'date_field': 'stock_in_date',
                'amount_field': 'total_amount',
                'permission_check': 'stockin',
                'can_add': 'inventory.add_stockin',
                'can_change': 'inventory.change_stockin',
                'can_delete': 'inventory.delete_stockin',
                'owner_field': 'created_by'}
            mappings['出库单'] = {
                'model': StockOut,
                'fields': [
                    'stock_out_no',
                    'warehouse',
                    'total_amount',
                    'status',
                    'stock_out_date'],
                'keywords': [
                    '出库',
                    '发货'],
                'primary_field': 'stock_out_no',
                'display_fields': [
                    'stock_out_no',
                    'warehouse',
                    'total_amount',
                    'status'],
                'search_fields': ['stock_out_no'],
                'date_field': 'stock_out_date',
                'amount_field': 'total_amount',
                'permission_check': 'stockout',
                'can_add': 'inventory.add_stockout',
                'can_change': 'inventory.change_stockout',
                'can_delete': 'inventory.delete_stockout',
                'owner_field': 'created_by'}
            mappings['库存预警'] = {
                'model': InventoryAlert,
                'fields': [
                    'product',
                    'warehouse',
                    'alert_type',
                    'current_quantity'],
                'keywords': [
                    '库存预警',
                    '库存报警'],
                'primary_field': 'id',
                'display_fields': [
                    'product',
                    'warehouse',
                    'alert_type',
                    'current_quantity'],
                'search_fields': ['product__name'],
                'date_field': 'created_at',
                'amount_field': None,
                'permission_check': 'alert',
                'can_add': 'inventory.add_inventionalert',
                'can_change': 'inventory.change_inventionalert',
                'can_delete': 'inventory.delete_inventionalert',
                'owner_field': 'created_by'}
        except Exception as e:
            logger.warning(f"加载库存模块失败: {e}")

        try:
            from apps.approval.models import ApprovalRecord
            mappings['审批'] = {
                'model': ApprovalRecord,
                'fields': [
                    'title',
                    'type',
                    'applicant',
                    'status',
                    'created_at'],
                'keywords': [
                    '审批',
                    '申请',
                    '待审批',
                    '审核'],
                'primary_field': 'title',
                'display_fields': [
                    'title',
                    'type',
                    'applicant',
                    'status',
                    'created_at'],
                'search_fields': ['title'],
                'date_field': 'created_at',
                'amount_field': None,
                'permission_check': 'approval',
                'can_add': 'approval.add_approvalrecord',
                'can_change': 'approval.change_approvalrecord',
                'can_delete': 'approval.delete_approvalrecord',
                'owner_field': 'applicant'}
        except Exception as e:
            logger.warning(f"加载审批模块失败: {e}")

        try:
            from apps.system.models import Notice, Document
            mappings['通知公告'] = {
                'model': Notice,
                'fields': [
                    'title',
                    'publisher',
                    'publish_date',
                    'status'],
                'keywords': [
                    '通知',
                    '公告',
                    '通告'],
                'primary_field': 'title',
                'display_fields': [
                    'title',
                    'publisher',
                    'publish_date',
                    'status'],
                'search_fields': [
                    'title',
                    'content'],
                'date_field': 'publish_date',
                'amount_field': None,
                'permission_check': 'notice',
                'can_add': 'system.add_notice',
                'can_change': 'system.change_notice',
                'can_delete': 'system.delete_notice',
                'owner_field': 'publisher'}
            mappings['文档'] = {
                'model': Document,
                'fields': [
                    'title',
                    'category',
                    'upload_user',
                    'file_size',
                    'upload_date'],
                'keywords': [
                    '文档',
                    '文件',
                    '资料'],
                'primary_field': 'title',
                'display_fields': [
                    'title',
                    'category',
                    'file_size',
                    'upload_user'],
                'search_fields': [
                    'title',
                    'file_name'],
                'date_field': 'upload_date',
                'amount_field': None,
                'permission_check': 'document',
                'can_add': 'system.add_document',
                'can_change': 'system.change_document',
                'can_delete': 'system.delete_document',
                'owner_field': 'upload_user'}
        except Exception as e:
            logger.warning(f"加载系统模块失败: {e}")

        try:
            from apps.department.models import Department
            mappings['部门'] = {
                'model': Department,
                'fields': [
                    'name',
                    'code',
                    'manager',
                    'status'],
                'keywords': [
                    '部门',
                    '科室',
                    '组织架构'],
                'primary_field': 'name',
                'display_fields': [
                    'name',
                    'code',
                    'manager',
                    'status'],
                'search_fields': [
                    'name',
                    'code'],
                'date_field': 'created_at',
                'amount_field': None,
                'permission_check': 'department',
                'can_add': 'user.add_department',
                'can_change': 'user.change_department',
                'can_delete': 'user.delete_department',
                'owner_field': 'created_by'}
        except Exception as e:
            logger.warning(f"加载部门模块失败: {e}")

        return mappings

    def _check_operation_permission(self, permission_code):
        """检查用户是否拥有指定操作权限"""
        if not self.user:
            return False
        if self.user.is_superuser:
            return True
        if not permission_code:
            return True
        return self.user.has_perm(permission_code)

    def _get_user_data_scope(self):
        """获取用户的数据权限范围"""
        if not self.user:
            return {
                'scope': 'none',
                'can_view_all': False,
                'can_view_department': False,
                'can_view_self': False}

        if self.user.is_superuser:
            return {
                'scope': 'all',
                'can_view_all': True,
                'can_view_department': True,
                'can_view_self': True}

        from apps.system.middleware.data_permission_middleware import DataScopeFilter
        return DataScopeFilter.get_user_data_scope(self.user)

    def _apply_data_filter(self, queryset, model, owner_field='created_by'):
        """根据用户权限过滤数据"""
        if not self.user:
            return queryset.none()

        if self.user.is_superuser:
            return queryset

        data_scope = self._get_user_data_scope()

        if data_scope.get('can_view_all'):
            return queryset

        if data_scope.get('can_view_department'):
            employee = getattr(self.user, 'employee', None)
            if employee and hasattr(model, 'department'):
                from django.db.models import Q
                return queryset.filter(
                    Q(**{owner_field: self.user}) |
                    Q(department=employee.department_id)
                ).distinct()

        if data_scope.get('can_view_self'):
            return queryset.filter(**{owner_field: self.user})

        return queryset.none()

    def _check_data_ownership(self, instance, owner_field='created_by'):
        """检查用户是否有权操作该数据"""
        if not self.user:
            return False

        if self.user.is_superuser:
            return True

        if hasattr(instance, owner_field):
            owner = getattr(instance, owner_field)
            if owner == self.user:
                return True

        employee = getattr(self.user, 'employee', None)
        if employee and hasattr(instance, 'department'):
            instance_dept = getattr(instance, 'department', None)
            if instance_dept and hasattr(employee, 'department_id'):
                if instance_dept.id == employee.department_id:
                    return True

        return False

    def process(self, user_message, user=None):
        """处理用户消息"""
        if user:
            self.user = user

        try:
            parsed_intent = self._ai_parse_intent(user_message)

            if not parsed_intent or 'operation' not in parsed_intent:
                parsed_intent = self._rule_based_parse(user_message)

            parsed_intent.get('target')
            operation = parsed_intent.get('operation', 'CONVERSATION')

            if operation == 'QUERY':
                if parsed_intent.get('is_statistics'):
                    return self._handle_statistics(parsed_intent)
                return self._handle_query(parsed_intent)
            elif operation == 'CREATE':
                return self._handle_create(parsed_intent, user_message)
            elif operation == 'UPDATE':
                return self._handle_update(parsed_intent, user_message)
            elif operation == 'DELETE':
                return self._handle_delete(parsed_intent)
            else:
                return self._handle_conversation(user_message)

        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            return {"success": False, "message": f"处理请求时发生错误: {str(e)}"}

    def _ai_parse_intent(self, user_message):
        """使用 AI 解析意图 - 增强版"""
        system_prompt = """你是一个企业数据查询助手。请分析用户的消息，精准提取操作意图。

## 常见用户话术示例
- "查询所有客户" → QUERY, 客户
- "查看本月新增合同" → QUERY, 合同, 本月
- "统计本月收入" → QUERY, 收入, 统计
- "有哪些客户" → QUERY, 客户
- "看看进行中的项目" → QUERY, 项目, 进行中
- "我有多少订单" → QUERY, 订单
- "列出本周的任务" → QUERY, 任务, 本周
- "帮我查一下客户" → QUERY, 客户
- "搜索北京的客户" → QUERY, 客户, 北京
- "创建一个客户名称为张三" → CREATE, 客户, 张三
- "新增一个订单" → CREATE, 订单
- "把客户张三的金额改成10000" → UPDATE, 客户, 张三, 10000
- "删除客户李四" → DELETE, 客户, 李四

## 支持的操作类型
- QUERY: 查询数据（查询、查看、搜索、统计、有多少、看看有哪些、帮我查、列出）
- CREATE: 创建数据（新增、添加、创建、新建）
- UPDATE: 修改数据（修改、更新、改成、改为）
- DELETE: 删除数据（删除、移除、作废）

## 支持的数据类型
客户、联系人、跟进记录、订单、合同、产品、服务项目、供应商、项目、任务、工时记录、支出、收入、发票、付款记录、仓库、库存、入库单、出库单、库存预警、审批、通知公告、文档、部门

## 时间条件
今天、昨天、本周、上周、本月、上月、本年、去年、最近7天、最近30天

## 状态条件（重要！必须正确映射）
- 进行中/启用/正常 = 1
- 已完成/完成/通过 = 2
- 已取消/取消/作废 = 3
- 禁用/停用 = 0
- 待审批/待审核/草稿 = 0

## 输出格式（JSON）
{
  "operation": "QUERY",
  "target": "客户",
  "search_keyword": "北京",
  "is_statistics": true/false,
  "conditions": {"status": 1}
}

注意：
- target 必须是支持的数据类型之一
- operation 必须是 QUERY/CREATE/UPDATE/DELETE 之一
- 从用户消息中提取搜索关键词
- 如果是统计查询，设置 is_statistics: true

请直接返回JSON：
"""

        try:
            if self.ai_client:
                response = self.ai_client.chat_completion([
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message}
                ])

                json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"AI 解析失败: {e}")

        return None

    def _rule_based_parse(self, user_message):
        """规则匹配解析 - 大幅增强版"""
        message = user_message.lower()
        original_message = user_message

        operation = 'CONVERSATION'

        operation_patterns = {
            'QUERY': [
                '查询', '找', '看看', '有多少', '统计', '汇总', '列表', '查看', '搜索', '筛选',
                '获取', '显示', '列出', '获取到', '看看有没有', '看看有', '查一下', '帮我查',
                '有哪些', '有多少', '多少个', '几个', '看看', '给我看', '展示', '列出所有',
                '有什么', '看看有什么', '都有', '都有哪些'
            ],
            'CREATE': [
                '创建', '新增', '添加', '增加', '录入', '新建', '开', '登记', '备案',
                '添加一个', '增加一个', '新建一个', '新增一个', '创建一个', '添加一条',
                '我想创建', '我要添加', '麻烦添加', '帮我新建', '帮我创建一个'
            ],
            'UPDATE': [
                '修改', '更新', '编辑', '调整', '变更', '改', '换', '把...改成', '把...改为',
                '更新为', '改成', '改为', '修改为', '变更成', '调整到', '改一下', '更新一下',
                '把...修改', '把...更新', '帮我修改', '帮我改一下', '把...改成', '把...改为'
            ],
            'DELETE': [
                '删除', '移除', '清除', '取消', '作废', '去掉', '删除掉', '清除掉',
                '把...删除', '把...移除', '帮我删除', '删掉', '不要了', '去掉这个'
            ]
        }

        for op, keywords in operation_patterns.items():
            if any(kw in message for kw in keywords):
                operation = op
                break

        target = None
        for name, config in self.model_mappings.items():
            if any(kw in message for kw in config['keywords']):
                target = name
                break

        if not target:
            target = self._smart_detect_target(original_message)

        is_statistics = any(kw in message for kw in self.statistics_keywords)

        conditions = {}
        conditions.update(self._parse_time_enhanced(original_message))
        conditions.update(self._parse_status_enhanced(original_message))

        keyword = self._extract_keyword_enhanced(original_message, target)

        return {
            'operation': operation,
            'target': target,
            'conditions': conditions,
            'is_statistics': is_statistics,
            'search_keyword': keyword,
            'original_message': original_message
        }

    def _smart_detect_target(self, message):
        """智能检测目标数据类型"""
        message_lower = message.lower()

        patterns = {
            '客户': ['客户', '顾客', '顾客信息', '客户信息', '我的客户'],
            '联系人': ['联系人', '联系方式', '联系人信息'],
            '跟进记录': ['跟进', '沟通记录', '拜访记录', '回访记录'],
            '订单': ['订单', '销售订单', '订单记录', '我的订单'],
            '合同': ['合同', '合约', '协议', '合同书'],
            '产品': ['产品', '商品', '货物', '货品', '产品信息'],
            '服务项目': ['服务', '服务项目', '服务记录'],
            '供应商': ['供应商', '供货商', '厂商', '供应商信息'],
            '项目': ['项目', '工程项目', '项目信息', '我的项目'],
            '任务': ['任务', '待办', 'todo', '工作', '待办事项'],
            '工时记录': ['工时', '工时记录', '打卡', '上班时间'],
            '支出': ['支出', '费用', '开销', '报销', '支出记录'],
            '收入': ['收入', '收款', '进账', '回款', '收入记录'],
            '发票': ['发票', '收据', '开票', '发票信息'],
            '付款记录': ['付款', '支付', '转账', '付款记录'],
            '仓库': ['仓库', '库房', '库存位置'],
            '库存': ['库存', '存货', '库存情况', '库存信息'],
            '入库单': ['入库', '入库单', '进货入库'],
            '出库单': ['出库', '出库单', '发货'],
            '库存预警': ['库存预警', '库存报警', '库存提醒'],
            '审批': ['审批', '申请', '待审批', '审核', '审批单'],
            '通知公告': ['通知', '公告', '通告', '通知公告'],
            '文档': ['文档', '文件', '资料', '附件'],
            '部门': ['部门', '科室', '组织架构', '部门信息']
        }

        for target, keywords in patterns.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return target

        return None

    def _parse_time_enhanced(self, message):
        """增强的时间解析"""
        conditions = {}
        today = datetime.now().date()

        time_patterns = {
            '今天': (
                today,
                today),
            '今日': (
                today,
                today),
            '昨天': (
                today -
                timedelta(
                    days=1),
                today -
                timedelta(
                    days=1)),
            '昨日': (
                today -
                timedelta(
                    days=1),
                today -
                timedelta(
                    days=1)),
            '前一天': (
                today -
                timedelta(
                    days=1),
                today -
                timedelta(
                    days=1)),
            '前天': (
                today -
                timedelta(
                    days=2),
                today -
                timedelta(
                    days=2)),
            '本周': (
                today -
                timedelta(
                    days=today.weekday()),
                today),
            '这周': (
                today -
                timedelta(
                    days=today.weekday()),
                today),
            '上周': (
                today -
                timedelta(
                    days=today.weekday() +
                    7),
                today -
                timedelta(
                    days=today.weekday() +
                    1)),
            '下周': (
                today +
                timedelta(
                    days=7 -
                    today.weekday()),
                today +
                timedelta(
                    days=13 -
                    today.weekday())),
            '本月': (
                today.replace(
                    day=1),
                today),
            '这个月': (
                today.replace(
                    day=1),
                today),
            '上月': None,
            '上个月': None,
            '下月': (
                today.replace(
                    month=today.month %
                    12 +
                    1,
                    day=1) if today.month != 12 else today.replace(
                    year=today.year +
                    1,
                    month=1,
                    day=1),
                today.replace(
                    month=today.month %
                    12 +
                    1,
                    day=28) if today.month != 12 else today.replace(
                    year=today.year +
                    1,
                    month=1,
                    day=28)),
            '本年': (
                today.replace(
                    month=1,
                    day=1),
                today),
            '今年': (
                today.replace(
                    month=1,
                    day=1),
                today),
            '去年': (
                today.replace(
                    year=today.year -
                    1,
                    month=1,
                    day=1),
                today.replace(
                    year=today.year -
                    1,
                    month=12,
                    day=31)),
            '最近7天': (
                today -
                timedelta(
                    days=7),
                today),
            '过去7天': (
                today -
                timedelta(
                    days=7),
                today),
            '7天内': (
                today -
                timedelta(
                    days=7),
                today),
            '最近30天': (
                today -
                timedelta(
                    days=30),
                today),
            '过去30天': (
                today -
                timedelta(
                    days=30),
                today),
            '30天内': (
                today -
                timedelta(
                    days=30),
                today),
            '最近': (
                today -
                timedelta(
                    days=30),
                today),
            '这一周': (
                today -
                timedelta(
                    days=today.weekday()),
                today),
            '上一周': (
                today -
                timedelta(
                    days=today.weekday() +
                    7),
                today -
                timedelta(
                    days=today.weekday() +
                    1)),
        }

        first_day = today.replace(day=1)
        last_month_end = first_day - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        time_patterns['上月'] = (last_month_start, last_month_end)
        time_patterns['上个月'] = (last_month_start, last_month_end)

        for time_str, (start, end) in time_patterns.items():
            if start and time_str in message:
                conditions['date'] = {'start': start, 'end': end}
                conditions['time_keyword'] = time_str
                break

        return conditions

    def _parse_status_enhanced(self, message):
        """增强的状态解析"""
        conditions = {}

        status_patterns = {
            '进行中': 1, '进行': 1, '启用': 1, '正常': 1, '启用中': 1, '活跃': 1,
            '已完成': 2, '完成': 2, '已结束': 2, '结束': 2, '完成': 2, '已完成': 2,
            '已取消': 3, '取消': 3, '已作废': 3, '作废': 3,
            '禁用': 0, '停用': 0, '禁用中': 0, '未启用': 0,
            '待审批': 0, '待审核': 0, '审批中': 0, '审核中': 0, '待处理': 0,
            '已审批': 1, '已通过': 1, '通过': 1, '批准': 1, '已同意': 1,
            '拒绝': 2, '已拒绝': 2, '不通过': 2, '驳回': 2,
            '草稿': 4, 'draft': 4,
            '待付款': 5, '未付款': 5,
            '已付款': 6, '已支付': 6,
        }

        for status_str, status_val in status_patterns.items():
            if status_str in message:
                conditions['status'] = status_val
                conditions['status_keyword'] = status_str
                break

        return conditions

    def _extract_keyword_enhanced(self, message, target):
        """增强的关键词提取"""
        remove_phrases = [
            '查询', '查看', '搜索', '找', '看看', '列出', '显示', '获取', '帮我', '给我',
            '查找', '看看有没有', '看看有', '有哪些', '多少', '几个', '统计', '汇总',
            '帮我查一下', '帮我找', '帮我看看', '麻烦', '请', '我想', '我要', '帮我',
            '给我看一下', '展示', '列出所有', '看看所有', '查一下', '找一下'
        ]

        keywords_to_remove = [
            '的', '是', '有', '在', '和', '与', '及', '或', '这', '那', '这个', '那个',
            '一下', '一点', '什么', '哪些', '哪个', '请帮我', '请问', '我要查', '查询一下'
        ]

        msg = message
        for phrase in remove_phrases:
            msg = msg.replace(phrase, ' ')
        for kw in keywords_to_remove:
            msg = msg.replace(kw, ' ')

        msg = re.sub(r'[\d\W]+', ' ', msg)
        msg = msg.strip()

        if len(msg) >= 2:
            return msg

        return None

    def _handle_query(self, intent):
        """处理查询"""
        target = intent.get('target')
        if not target:
            return {"success": False, "message": "请告诉我要查询什么数据"}

        config = self.model_mappings.get(target)
        if not config:
            return {"success": False, "message": f"暂不支持查询 {target}"}

        permission_check = config.get('permission_check')
        if not self._check_operation_permission(
                f'user.view_{permission_check}'):
            return {"success": False, "message": f"您没有查看{target}的权限"}

        data_type_map = {
            '客户': 'customer',
            '联系人': 'contact',
            '跟进记录': 'followup',
            '订单': 'order',
            '合同': 'contract',
            '产品': 'product',
            '服务项目': 'service',
            '供应商': 'supplier',
            '项目': 'project',
            '任务': 'task',
            '工时记录': 'workhour',
            '支出': 'expense',
            '收入': 'income',
            '发票': 'invoice',
            '付款记录': 'payment',
            '仓库': 'warehouse',
            '库存': 'inventory',
            '入库单': 'stockin',
            '出库单': 'stockout',
            '库存预警': 'alert',
            '审批': 'approval',
            '通知公告': 'notice',
            '文档': 'document',
            '部门': 'department'}

        try:
            model = config['model']
            queryset = model.objects.all()

            owner_field = config.get('owner_field', 'created_by')
            queryset = self._apply_data_filter(queryset, model, owner_field)

            keyword = intent.get('search_keyword')
            if keyword:
                search_fields = config.get('search_fields', [])
                if search_fields:
                    q = Q()
                    for field in search_fields:
                        if '__' in field:
                            q |= Q(**{f'{field}__icontains': keyword})
                        elif hasattr(model, field):
                            q |= Q(**{f'{field}__icontains': keyword})
                    queryset = queryset.filter(q)

            conditions = intent.get('conditions', {})
            if 'status' in conditions:
                queryset = queryset.filter(status=conditions['status'])

            if 'date' in conditions:
                date_range = conditions['date']
                date_field = config.get('date_field', 'created_at')
                if hasattr(model, date_field):
                    queryset = queryset.filter(
                        **{f'{date_field}__range': (date_range['start'], date_range['end'])})

            date_field = config.get('date_field', 'created_at')
            if hasattr(model, date_field):
                queryset = queryset.order_by(f'-{date_field}')

            limit = intent.get('limit', 10)
            count = queryset.count()

            if count == 0:
                return {
                    "success": True,
                    "message": f"没有找到符合条件的 {target} 记录",
                    "type": "list",
                    "data_type": data_type_map.get(target, target),
                    "items": [],
                    "total": 0
                }

            results = list(queryset[:limit].values())
            formatted = self._format_for_query_service(results, config, target)

            msg = f"找到 {count} 条{target}"
            if count > limit:
                msg += f"，显示前 {limit} 条"

            return {
                "success": True,
                "message": msg,
                "type": "list",
                "data_type": data_type_map.get(target, target),
                "items": formatted,
                "total": count,
                "has_more": count > limit
            }

        except Exception as e:
            logger.error(f"查询失败: {e}")
            return {"success": False, "message": f"查询失败: {str(e)}"}

    def _handle_create(self, intent, user_message):
        """处理创建数据"""
        target = intent.get('target')
        if not target:
            return {"success": False, "message": "请告诉我要创建什么数据"}

        config = self.model_mappings.get(target)
        if not config:
            return {"success": False, "message": f"暂不支持创建 {target}"}

        can_add_perm = config.get('can_add')
        if not self._check_operation_permission(can_add_perm):
            return {"success": False, "message": f"您没有创建{target}的权限"}

        try:
            model = config['model']

            create_data = self._parse_create_data(user_message, config)
            if not create_data:
                return {"success": False, "message": f"请提供创建{target}所需的完整信息"}

            if hasattr(model, 'created_by') and self.user:
                create_data['created_by'] = self.user

            if hasattr(model, 'owner') and self.user:
                create_data['owner'] = self.user

            instance = model.objects.create(**create_data)

            return {
                "success": True,
                "message": f"成功创建{target}：{getattr(instance, config.get('primary_field', 'id'), '记录')}",
                "operation": "CREATE",
                "data_id": instance.id}

        except Exception as e:
            logger.error(f"创建失败: {e}")
            return {"success": False, "message": f"创建失败: {str(e)}"}

    def _parse_create_data(self, user_message, config):
        """从用户消息中解析创建数据"""
        config['model']
        fields = config.get('fields', [])

        create_data = {}

        name_match = re.search(
            r'(?:名称|名字|叫|名称为)[：:]*([^\s，,。]{2,20})',
            user_message)
        if name_match:
            create_data['name'] = name_match.group(1)

        amount_match = re.search(
            r'(?:金额|总额|价格|预算)[为是:]*(?:人民币|¥|￥)?(\d+(?:\.\d+)?)',
            user_message)
        if amount_match and 'amount' in fields:
            create_data['amount'] = float(amount_match.group(1))

        phone_match = re.search(r'(?:电话|手机)[为是:]*(1[3-9]\d{9})', user_message)
        if phone_match:
            create_data['phone'] = phone_match.group(1)

        if 'status' in fields:
            if '启用' in user_message or '正常' in user_message:
                create_data['status'] = 1
            elif '禁用' in user_message:
                create_data['status'] = 0

        return create_data

    def _handle_update(self, intent, user_message):
        """处理更新数据"""
        target = intent.get('target')
        if not target:
            return {"success": False, "message": "请告诉我要修改什么数据"}

        config = self.model_mappings.get(target)
        if not config:
            return {"success": False, "message": f"暂不支持修改 {target}"}

        can_change_perm = config.get('can_change')
        if not self._check_operation_permission(can_change_perm):
            return {"success": False, "message": f"您没有修改{target}的权限"}

        try:
            model = config['model']
            owner_field = config.get('owner_field', 'created_by')

            keyword = intent.get('search_keyword')
            search_fields = config.get('search_fields', [])

            queryset = model.objects.all()
            queryset = self._apply_data_filter(queryset, model, owner_field)

            if keyword and search_fields:
                q = Q()
                for field in search_fields:
                    if hasattr(model, field):
                        q |= Q(**{f'{field}__icontains': keyword})
                queryset = queryset.filter(q)

            instance = queryset.first()
            if not instance:
                return {"success": False, "message": f"未找到您有权修改的{target}记录"}

            if not self._check_data_ownership(instance, owner_field):
                data_scope = self._get_user_data_scope()
                if not data_scope.get('can_view_all'):
                    return {
                        "success": False,
                        "message": f"您没有权限修改这条{target}记录"}

            update_data = self._parse_update_data(user_message, config)
            if not update_data:
                return {"success": False, "message": f"请提供要修改的内容"}

            for key, value in update_data.items():
                setattr(instance, key, value)
            instance.save()

            return {
                "success": True,
                "message": f"成功修改{target}：{getattr(instance, config.get('primary_field', 'id'), '记录')}",
                "operation": "UPDATE",
                "data_id": instance.id}

        except Exception as e:
            logger.error(f"修改失败: {e}")
            return {"success": False, "message": f"修改失败: {str(e)}"}

    def _parse_update_data(self, user_message, config):
        """从用户消息中解析更新数据"""
        fields = config.get('fields', [])
        update_data = {}

        amount_match = re.search(
            r'(?:金额|总额|价格|预算)[为是:]*(?:人民币|¥|￥)?(\d+(?:\.\d+)?)',
            user_message)
        if amount_match and 'amount' in fields:
            update_data['amount'] = float(amount_match.group(1))

        if 'status' in fields:
            if '启用' in user_message or '正常' in user_message:
                update_data['status'] = 1
            elif '禁用' in user_message or '停用' in user_message:
                update_data['status'] = 0
            elif '完成' in user_message or '已完成' in user_message:
                update_data['status'] = 2
            elif '取消' in user_message or '已取消' in user_message:
                update_data['status'] = 3

        progress_match = re.search(r'(?:进度)[为是:]*(?:到)?(\d+)%?', user_message)
        if progress_match and 'progress' in fields:
            update_data['progress'] = int(progress_match.group(1))

        return update_data

    def _handle_delete(self, intent):
        """处理删除数据"""
        target = intent.get('target')
        if not target:
            return {"success": False, "message": "请告诉我要删除什么数据"}

        config = self.model_mappings.get(target)
        if not config:
            return {"success": False, "message": f"暂不支持删除 {target}"}

        can_delete_perm = config.get('can_delete')
        if not self._check_operation_permission(can_delete_perm):
            return {"success": False, "message": f"您没有删除{target}的权限"}

        try:
            model = config['model']
            owner_field = config.get('owner_field', 'created_by')

            keyword = intent.get('search_keyword')
            search_fields = config.get('search_fields', [])

            queryset = model.objects.all()
            queryset = self._apply_data_filter(queryset, model, owner_field)

            if keyword and search_fields:
                q = Q()
                for field in search_fields:
                    if hasattr(model, field):
                        q |= Q(**{f'{field}__icontains': keyword})
                queryset = queryset.filter(q)

            instance = queryset.first()
            if not instance:
                return {"success": False, "message": f"未找到您有权删除的{target}记录"}

            if not self._check_data_ownership(instance, owner_field):
                data_scope = self._get_user_data_scope()
                if not data_scope.get('can_view_all'):
                    return {
                        "success": False,
                        "message": f"您没有权限删除这条{target}记录"}

            instance_name = getattr(
                instance, config.get(
                    'primary_field', 'id'), '记录')
            instance.delete()

            return {
                "success": True,
                "message": f"成功删除{target}：{instance_name}",
                "operation": "DELETE"
            }

        except Exception as e:
            logger.error(f"删除失败: {e}")
            return {"success": False, "message": f"删除失败: {str(e)}"}

    def _handle_statistics(self, intent):
        """处理统计"""
        target = intent.get('target')
        if not target:
            return {"success": False, "message": "请告诉我要统计什么数据"}

        config = self.model_mappings.get(target)
        if not config:
            return {"success": False, "message": f"暂不支持统计 {target}"}

        permission_check = config.get('permission_check')
        if not self._check_operation_permission(
                f'user.view_{permission_check}'):
            return {"success": False, "message": f"您没有查看{target}的权限"}

        data_type_map = {
            '客户': 'customer',
            '联系人': 'contact',
            '跟进记录': 'followup',
            '订单': 'order',
            '合同': 'contract',
            '产品': 'product',
            '服务项目': 'service',
            '供应商': 'supplier',
            '项目': 'project',
            '任务': 'task',
            '工时记录': 'workhour',
            '支出': 'expense',
            '收入': 'income',
            '发票': 'invoice',
            '付款记录': 'payment',
            '仓库': 'warehouse',
            '库存': 'inventory',
            '入库单': 'stockin',
            '出库单': 'stockout',
            '库存预警': 'alert',
            '审批': 'approval',
            '通知公告': 'notice',
            '文档': 'document',
            '部门': 'department'}

        try:
            model = config['model']
            queryset = model.objects.all()

            owner_field = config.get('owner_field', 'created_by')
            queryset = self._apply_data_filter(queryset, model, owner_field)

            conditions = intent.get('conditions', {})
            if 'status' in conditions:
                queryset = queryset.filter(status=conditions['status'])

            if 'date' in conditions:
                date_range = conditions['date']
                date_field = config.get('date_field', 'created_at')
                if hasattr(model, date_field):
                    queryset = queryset.filter(
                        **{f'{date_field}__range': (date_range['start'], date_range['end'])})

            amount_field = config.get('amount_field')

            if amount_field and hasattr(model, amount_field):
                total = queryset.aggregate(
                    Sum(amount_field))[f'{amount_field}__sum'] or 0
                avg = queryset.aggregate(Avg(amount_field))[
                    f'{amount_field}__avg'] or 0
                max_val = queryset.aggregate(
                    Max(amount_field))[f'{amount_field}__max'] or 0
                min_val = queryset.aggregate(
                    Min(amount_field))[f'{amount_field}__min'] or 0

                count = queryset.count()
                message = f"{target}统计：共{count}条，总额¥{total:,.2f}，平均¥{avg:,.2f}，最高¥{max_val:,.2f}，最低¥{min_val:,.2f}"

                return {
                    "success": True,
                    "message": message,
                    "type": "sum",
                    "data_type": data_type_map.get(target, target),
                    "value": total,
                    "field": amount_field,
                    "count": count,
                    "statistics": True
                }
            else:
                count = queryset.count()
                message = f"{target}统计：共{count}条"

                return {
                    "success": True,
                    "message": message,
                    "type": "count",
                    "data_type": data_type_map.get(target, target),
                    "value": count,
                    "statistics": True
                }

        except Exception as e:
            logger.error(f"统计失败: {e}")
            return {"success": False, "message": f"统计失败: {str(e)}"}

    def _format_for_query_service(self, results, config, target):
        """格式化结果"""
        formatted = []
        display_fields = config.get('display_fields', [])

        for item in results:
            formatted_item = {}
            for field in display_fields:
                if field in item and item[field] is not None:
                    value = item[field]
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d')
                    formatted_item[field] = value

            if not formatted_item and item:
                formatted_item = {
                    k: v for k, v in item.items() if v is not None}

            formatted.append(formatted_item)

        return formatted

    def _handle_conversation(self, user_message):
        """处理对话"""
        if not self.ai_client:
            return {"success": False, "message": "AI 对话未配置"}

        try:
            supported_types = "、".join(self.model_mappings.keys())
            context = f"""你是一个智能企业助手，可以帮助用户查询和管理业务数据。

支持查询的数据类型：{supported_types}

用户问的是: """

            response = self.ai_client.chat_completion([
                {'role': 'system', 'content': context},
                {'role': 'user', 'content': user_message}
            ])

            return {
                "success": True,
                "message": response,
                "is_conversation": True
            }
        except Exception as e:
            logger.error(f"AI 对话失败: {e}")
            return {"success": False, "message": f"AI 对话失败: {str(e)}"}

    def get_supported_operations(self):
        """获取支持的操作"""
        return {
            "targets": list(self.model_mappings.keys()),
            "operations": ["查询", "创建", "修改", "删除", "统计"],
            "examples": [
                "查询所有客户",
                "查看本月新增合同",
                "统计本月收入",
                "创建一个客户名称为张三",
                "把客户张三的金额改成10000",
                "删除客户张三"
            ]
        }
