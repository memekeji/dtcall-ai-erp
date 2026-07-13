"""
增强的意图识别服务
整合 AI 意图分类器、数据权限控制和自动化数据处理功能
"""

import logging
import re
from typing import Dict, Any
from django.contrib.auth.models import User
from apps.ai.models import AIChat, AIChatMessage
from apps.ai.services.ai_intent_classifier import ai_intent_classifier
from apps.ai.services.query_service import query_service
from apps.user.services.permission_node_mapper import permission_node_mapper
from apps.system.middleware.data_permission_middleware import PermissionChecker

logger = logging.getLogger(__name__)


class EnhancedIntentService:
    """增强的意图处理服务"""

    MUTATING_ACTIONS = {'create', 'update', 'delete', 'approve', 'reject', 'submit', 'publish', 'withdraw', 'stock'}
    MUTATING_INTENTS = {'DATA_CREATE', 'DATA_UPDATE', 'DATA_DELETE'}

    BUSINESS_HANDOFF_CONFIG = {
        'customer': {
            'name': '客户',
            'module': '客户管理',
            'list_url': '/customer/',
            'create_url': '/customer/create/',
            'edit_url_template': '/customer/edit/{id}/',
            'permission_base': 'customer',
        },
        'order': {
            'name': '客户订单',
            'module': '客户管理',
            'list_url': '/customer/orders/',
            'create_url': '/customer/orders/create/',
            'edit_url_template': '/customer/orders/{id}/edit/',
            'permission_base': 'customer_order',
        },
        'contract': {
            'name': '合同',
            'module': '合同管理',
            'list_url': '/contract/sales/',
            'create_url': '/contract/create/',
            'edit_url_template': '/contract/sales/update/{id}/',
            'permission_base': 'contract',
        },
        'project': {
            'name': '项目',
            'module': '项目管理',
            'list_url': '/project/',
            'create_url': '/project/add/',
            'edit_url_template': '/project/edit/{id}/',
            'permission_base': 'project',
        },
        'invoice': {
            'name': '发票',
            'module': '财务管理',
            'list_url': '/finance/invoice/',
            'create_url': '/finance/invoice/add/',
            'edit_url_template': '/finance/invoice/edit/{id}/',
            'permission_base': 'invoice',
        },
        'employee': {
            'name': '员工',
            'module': '人事管理',
            'list_url': '/user/employee/',
            'create_url': '/user/employee/create/',
            'edit_url_template': '/user/employee/update/{id}/',
            'permission': {
                'query': {'full_code': 'user.view_employeefile', 'exists': True},
                'create': {'full_code': 'user.add_employee', 'exists': True},
                'update': {'full_code': 'user.change_employee', 'exists': True},
                'delete': {'full_code': 'user.delete_employee', 'exists': True},
            },
        },
        'department': {
            'name': '部门',
            'module': '组织管理',
            'list_url': '/system/department/',
            'create_url': '/system/department/add/',
            'edit_url_template': '/system/department/{id}/update/',
            'permission': {
                'query': {'full_code': 'department.view_department', 'exists': True},
                'create': {'full_code': 'department.add_department', 'exists': True},
                'update': {'full_code': 'department.change_department', 'exists': True},
                'delete': {'full_code': 'department.delete_department', 'exists': True},
            },
        },
        'reward_punishment': {
            'name': '奖罚记录',
            'module': '人事管理',
            'list_url': '/user/reward-punishment/',
            'create_url': '/user/reward-punishment/add/',
            'edit_url_template': '/user/reward-punishment/{id}/edit/',
            'permission': {
                'query': {'full_code': 'user.view_reward_punishment', 'exists': True},
                'create': {'full_code': 'user.add_reward_punishment', 'exists': True},
                'update': {'full_code': 'user.change_reward_punishment', 'exists': True},
                'delete': {'full_code': 'user.delete_reward_punishment', 'exists': True},
            },
        },
        'employee_care': {
            'name': '员工关怀',
            'module': '人事管理',
            'list_url': '/user/employee-care/',
            'create_url': '/user/employee-care/add/',
            'edit_url_template': '/user/employee-care/{id}/edit/',
            'permission': {
                'query': {'full_code': 'user.view_employee_care', 'exists': True},
                'create': {'full_code': 'user.add_employee_care', 'exists': True},
                'update': {'full_code': 'user.change_employee_care', 'exists': True},
                'delete': {'full_code': 'user.delete_employee_care', 'exists': True},
            },
        },
        'finance': {
            'name': '费用报销',
            'module': '财务管理',
            'list_url': '/finance/expense/',
            'create_url': '/finance/expense/add/',
            'edit_url_template': None,
            'permission_base': 'reimbursement',
        },
        'expense': {
            'name': '报销单',
            'module': '财务管理',
            'list_url': '/finance/expense/',
            'create_url': '/finance/expense/add/',
            'edit_url_template': None,
            'permission': {
                'query': {'full_code': 'finance.view_expense', 'exists': True},
                'create': {'full_code': 'finance.add_reimbursement', 'exists': True},
                'update': {'full_code': 'finance.change_reimbursement', 'exists': True},
                'delete': {'full_code': 'finance.delete_reimbursement', 'exists': True},
                'approve': {'full_code': 'finance.approve_reimbursement', 'exists': True},
            },
        },
        'finance_expense': {
            'name': '报销单',
            'module': '财务管理',
            'list_url': '/finance/expense/',
            'create_url': '/finance/expense/add/',
            'edit_url_template': None,
            'permission': {
                'query': {'full_code': 'finance.view_expense', 'exists': True},
                'create': {'full_code': 'finance.add_reimbursement', 'exists': True},
                'update': {'full_code': 'finance.change_reimbursement', 'exists': True},
                'delete': {'full_code': 'finance.delete_reimbursement', 'exists': True},
                'approve': {'full_code': 'finance.approve_reimbursement', 'exists': True},
            },
        },
        'finance_invoice': {
            'name': '财务发票',
            'module': '财务管理',
            'list_url': '/finance/invoice/',
            'create_url': '/finance/invoice/add/',
            'edit_url_template': '/finance/invoice/edit/{id}/',
            'permission_base': 'invoice',
        },
        'income': {
            'name': '回款记录',
            'module': '财务管理',
            'list_url': '/finance/paymentreceive/',
            'create_url': '/finance/paymentreceive/add/',
            'edit_url_template': '/finance/paymentreceive/',
            'permission': {
                'query': {'full_code': 'finance.view_payment_receive', 'exists': True},
                'create': {'full_code': 'finance.add_payment_receive', 'exists': True},
                'update': {'full_code': 'finance.change_payment_receive', 'exists': True},
                'delete': {'full_code': 'finance.delete_payment_receive', 'exists': True},
            },
        },
        'finance_income': {
            'name': '回款记录',
            'module': '财务管理',
            'list_url': '/finance/paymentreceive/',
            'create_url': '/finance/paymentreceive/add/',
            'edit_url_template': '/finance/paymentreceive/',
            'permission': {
                'query': {'full_code': 'finance.view_payment_receive', 'exists': True},
                'create': {'full_code': 'finance.add_payment_receive', 'exists': True},
                'update': {'full_code': 'finance.change_payment_receive', 'exists': True},
                'delete': {'full_code': 'finance.delete_payment_receive', 'exists': True},
            },
        },
        'finance_order_record': {
            'name': '订单财务记录',
            'module': '财务管理',
            'list_url': '/finance/order-finance/',
            'create_url': None,
            'edit_url_template': None,
            'permission': {
                'query': {'full_code': 'finance.view_orderfinancerecord', 'exists': True},
                'create': {'full_code': 'finance.add_orderfinancerecord', 'exists': True},
                'update': {'full_code': 'finance.change_orderfinancerecord', 'exists': True},
                'delete': {'full_code': 'finance.delete_orderfinancerecord', 'exists': True},
            },
        },
        'finance_account': {
            'name': '资金账户',
            'module': '财务管理',
            'list_url': '/finance/advanced/account/',
            'create_url': '/finance/advanced/account/add/',
            'edit_url_template': '/finance/advanced/account/edit/{id}/',
            'permission': {
                'query': {'full_code': 'finance.view_financeaccount', 'exists': True},
                'create': {'full_code': 'finance.add_financeaccount', 'exists': True},
                'update': {'full_code': 'finance.change_financeaccount', 'exists': True},
                'delete': {'full_code': 'finance.delete_financeaccount', 'exists': True},
            },
        },
        'finance_budget': {
            'name': '预算',
            'module': '财务管理',
            'list_url': '/finance/advanced/budget/',
            'create_url': '/finance/advanced/budget/add/',
            'edit_url_template': '/finance/advanced/budget/edit/{id}/',
            'permission': {
                'query': {'full_code': 'finance.view_financebudget', 'exists': True},
                'create': {'full_code': 'finance.add_financebudget', 'exists': True},
                'update': {'full_code': 'finance.change_financebudget', 'exists': True},
                'delete': {'full_code': 'finance.delete_financebudget', 'exists': True},
            },
        },
        'finance_receivable': {
            'name': '应收账款',
            'module': '财务管理',
            'list_url': '/finance/advanced/receivable/',
            'create_url': '/finance/advanced/receivable/add/',
            'edit_url_template': '/finance/advanced/receivable/edit/{id}/',
            'permission': {
                'query': {'full_code': 'finance.view_accountsreceivable', 'exists': True},
                'create': {'full_code': 'finance.add_accountsreceivable', 'exists': True},
                'update': {'full_code': 'finance.change_accountsreceivable', 'exists': True},
                'delete': {'full_code': 'finance.delete_accountsreceivable', 'exists': True},
            },
        },
        'finance_payable': {
            'name': '应付账款',
            'module': '财务管理',
            'list_url': '/finance/advanced/payable/',
            'create_url': '/finance/advanced/payable/add/',
            'edit_url_template': '/finance/advanced/payable/edit/{id}/',
            'permission': {
                'query': {'full_code': 'finance.view_accountspayable', 'exists': True},
                'create': {'full_code': 'finance.add_accountspayable', 'exists': True},
                'update': {'full_code': 'finance.change_accountspayable', 'exists': True},
                'delete': {'full_code': 'finance.delete_accountspayable', 'exists': True},
            },
        },
        'finance_bank_transaction': {
            'name': '银行流水',
            'module': '财务管理',
            'list_url': '/finance/advanced/bank-transaction/',
            'create_url': '/finance/advanced/bank-transaction/add/',
            'edit_url_template': '/finance/advanced/bank-transaction/edit/{id}/',
            'permission': {
                'query': {'full_code': 'finance.view_banktransaction', 'exists': True},
                'create': {'full_code': 'finance.add_banktransaction', 'exists': True},
                'update': {'full_code': 'finance.change_banktransaction', 'exists': True},
                'delete': {'full_code': 'finance.delete_banktransaction', 'exists': True},
            },
        },
        'production': {
            'name': '生产计划',
            'module': '生产管理',
            'list_url': '/production/task/plan/',
            'create_url': '/production/task/plan/add/',
            'edit_url_template': '/production/task/plan/edit/{id}/',
            'permission_base': 'production_plan',
        },
        'production_plan': {
            'name': '生产计划',
            'module': '生产管理',
            'list_url': '/production/task/plan/',
            'create_url': '/production/task/plan/add/',
            'edit_url_template': '/production/task/plan/edit/{id}/',
            'permission_base': 'production_plan',
        },
        'production_task': {
            'name': '生产任务',
            'module': '生产管理',
            'list_url': '/production/task/execution/',
            'create_url': '/production/task/execution/add/',
            'edit_url_template': '/production/task/execution/edit/{id}/',
            'permission_base': 'production_task',
        },
        'production_equipment': {
            'name': '生产设备',
            'module': '生产管理',
            'list_url': '/production/equipment/',
            'create_url': '/production/equipment/add/',
            'edit_url_template': '/production/equipment/edit/{id}/',
            'permission_base': 'equipment',
        },
        'production_procedure': {
            'name': '生产工序',
            'module': '生产管理',
            'list_url': '/production/procedure/',
            'create_url': '/production/procedure/add/',
            'edit_url_template': '/production/procedure/edit/{id}/',
            'permission_base': 'procedure',
        },
        'procedureset': {
            'name': '工序集',
            'module': '生产管理',
            'list_url': '/production/procedureset/',
            'create_url': '/production/procedureset/add/',
            'edit_url_template': '/production/procedureset/edit/{id}/',
            'permission': {
                'query': {'full_code': 'user.view_procedureset', 'exists': True},
                'create': {'full_code': 'user.add_procedureset', 'exists': True},
                'update': {'full_code': 'user.change_procedureset', 'exists': True},
                'delete': {'full_code': 'user.delete_procedureset', 'exists': True},
            },
        },
        'bom': {
            'name': 'BOM',
            'module': '生产管理',
            'list_url': '/production/bom/',
            'create_url': '/production/bom/add/',
            'edit_url_template': '/production/bom/edit/{id}/',
            'permission': {
                'query': {'full_code': 'user.view_bom', 'exists': True},
                'create': {'full_code': 'user.add_bom', 'exists': True},
                'update': {'full_code': 'user.change_bom', 'exists': True},
                'delete': {'full_code': 'user.delete_bom', 'exists': True},
            },
        },
        'process': {
            'name': '工艺路线',
            'module': '生产管理',
            'list_url': '/production/process/',
            'create_url': '/production/process/add/',
            'edit_url_template': '/production/process/edit/{id}/',
            'permission': {
                'query': {'full_code': 'user.view_process', 'exists': True},
                'create': {'full_code': 'user.add_process', 'exists': True},
                'update': {'full_code': 'user.change_process', 'exists': True},
                'delete': {'full_code': 'user.delete_process', 'exists': True},
            },
        },
        'quality_check': {
            'name': '质量检查',
            'module': '生产管理',
            'list_url': '/production/quality/',
            'create_url': '/production/quality/add/',
            'edit_url_template': '/production/quality/edit/{id}/',
            'permission': {
                'query': {'full_code': 'user.view_quality_check', 'exists': True},
                'create': {'full_code': 'user.add_quality_check', 'exists': True},
                'update': {'full_code': 'user.change_quality_check', 'exists': True},
                'delete': {'full_code': 'user.delete_quality_check', 'exists': True},
            },
        },
        'followup': {
            'name': '跟进记录',
            'module': '客户管理',
            'list_url': '/customer/followup/',
            'create_url': '/customer/followup/create/',
            'edit_url_template': '/customer/followup/{id}/edit/',
            'permission_base': 'follow_record',
        },
        'contact': {
            'name': '客户联系人',
            'module': '客户管理',
            'list_url': '/customer/',
            'create_url': '/customer/',
            'edit_url_template': None,
            'permission': {
                'query': {'full_code': 'customer.view_customer', 'exists': True},
                'create': {'full_code': 'customer.add_customer', 'exists': True},
                'update': {'full_code': 'customer.change_customer', 'exists': True},
                'delete': {'full_code': 'customer.delete_customer', 'exists': True},
            },
        },
        'supplier': {
            'name': '供应商',
            'module': '合同管理',
            'list_url': '/contract/supplier/',
            'create_url': '/contract/supplier/add/',
            'edit_url_template': '/contract/supplier/edit/{id}/',
            'permission_base': 'supplier',
        },
        'product': {
            'name': '产品',
            'module': '合同管理',
            'list_url': '/contract/product/',
            'create_url': '/contract/product/add/',
            'edit_url_template': '/contract/product/edit/{id}/',
            'permission_base': 'product',
        },
        'inventory': {
            'name': '库存物料',
            'module': '库存管理',
            'list_url': '/inventory/inventory/',
            'create_url': '/inventory/item/add/',
            'edit_url_template': '/inventory/item/{id}/',
            'permission': {
                'query': {'full_code': 'inventory.view_inventory', 'exists': True},
                'create': {'full_code': 'inventory.add_inventoryitem', 'exists': True},
                'update': {'full_code': 'inventory.change_inventoryitem', 'exists': True},
                'delete': {'full_code': 'inventory.delete_inventoryitem', 'exists': True},
            },
        },
        'warehouse': {
            'name': '仓库',
            'module': '库存管理',
            'list_url': '/inventory/warehouse/',
            'create_url': '/inventory/warehouse/add/',
            'edit_url_template': '/inventory/warehouse/{id}/',
            'permission': {
                'query': {'full_code': 'inventory.view_warehouse', 'exists': True},
                'create': {'full_code': 'inventory.add_warehouse', 'exists': True},
                'update': {'full_code': 'inventory.change_warehouse', 'exists': True},
                'delete': {'full_code': 'inventory.delete_warehouse', 'exists': True},
            },
        },
        'stockin': {
            'name': '入库单',
            'module': '库存管理',
            'list_url': '/inventory/stockin/',
            'create_url': '/inventory/stockin/add/',
            'edit_url_template': '/inventory/stockin/{id}/',
            'action_urls': {
                'approve': '/inventory/stockin/{id}/',
                'stock': '/inventory/stockin/{id}/',
            },
            'permission': {
                'query': {'full_code': 'inventory.view_stockin', 'exists': True},
                'create': {'full_code': 'inventory.add_stockin', 'exists': True},
                'update': {'full_code': 'inventory.change_stockin', 'exists': True},
                'delete': {'full_code': 'inventory.delete_stockin', 'exists': True},
                'approve': {'full_code': 'inventory.change_stockin', 'exists': True},
                'stock': {'full_code': 'inventory.change_stockin', 'exists': True},
            },
        },
        'stockout': {
            'name': '出库单',
            'module': '库存管理',
            'list_url': '/inventory/stockout/',
            'create_url': '/inventory/stockout/add/',
            'edit_url_template': '/inventory/stockout/{id}/',
            'action_urls': {
                'approve': '/inventory/stockout/{id}/',
                'stock': '/inventory/stockout/{id}/',
            },
            'permission': {
                'query': {'full_code': 'inventory.view_stockout', 'exists': True},
                'create': {'full_code': 'inventory.add_stockout', 'exists': True},
                'update': {'full_code': 'inventory.change_stockout', 'exists': True},
                'delete': {'full_code': 'inventory.delete_stockout', 'exists': True},
                'approve': {'full_code': 'inventory.change_stockout', 'exists': True},
                'stock': {'full_code': 'inventory.change_stockout', 'exists': True},
            },
        },
        'alert': {
            'name': '库存预警',
            'module': '库存管理',
            'list_url': '/inventory/alert/',
            'create_url': None,
            'edit_url_template': None,
            'action_urls': {
                'approve': '/inventory/alert/',
                'reject': '/inventory/alert/',
            },
            'permission': {
                'query': {'full_code': 'inventory.view_inventoryalert', 'exists': True},
                'update': {'full_code': 'inventory.change_inventoryalert', 'exists': True},
                'delete': {'full_code': 'inventory.delete_inventoryalert', 'exists': True},
                'approve': {'full_code': 'inventory.change_inventoryalert', 'exists': True},
                'reject': {'full_code': 'inventory.change_inventoryalert', 'exists': True},
            },
        },
        'approval': {
            'name': '审批',
            'module': '审批管理',
            'list_url': '/approval/my/',
            'create_url': '/approval/apply/',
            'edit_url_template': '/approval/{id}/process/',
            'permission_base': 'approval',
            'skip_permission_gate': True,
        },
        'approval_type': {
            'name': '审批类型',
            'module': '审批管理',
            'list_url': '/approval/approval_type/',
            'create_url': '/approval/approval_type/add/',
            'edit_url_template': '/approval/approval_type/{id}/edit/',
            'permission': {
                'query': {'full_code': 'approval.view_approvaltype', 'exists': True},
                'create': {'full_code': 'approval.add_approvaltype', 'exists': True},
                'update': {'full_code': 'approval.change_approvaltype', 'exists': True},
                'delete': {'full_code': 'approval.delete_approvaltype', 'exists': True},
            },
        },
        'approval_step': {
            'name': '审批步骤',
            'module': '审批管理',
            'list_url': '/approval/approvalflow/',
            'create_url_template': '/approval/approvalflow/{flow_id}/step/add/',
            'edit_url_template': '/approval/approvalflow/{flow_id}/step/{id}/edit/',
            'action_urls': {
                'delete': '/approval/approvalflow/{flow_id}/step/{id}/delete/',
            },
            'permission': {
                'query': {'full_code': 'approval.view_approvalstep', 'exists': True},
                'create': {'full_code': 'approval.add_approvalstep', 'exists': True},
                'update': {'full_code': 'approval.change_approvalstep', 'exists': True},
                'delete': {'full_code': 'approval.delete_approvalstep', 'exists': True},
            },
        },
        'approval_flow': {
            'name': '审批流程',
            'module': '审批管理',
            'list_url': '/approval/approvalflow/',
            'create_url': '/approval/approvalflow/add/',
            'edit_url_template': '/approval/approvalflow/{id}/edit/',
            'permission': {
                'query': {'full_code': 'user.view_approval_flow', 'exists': True},
                'create': {'full_code': 'approval.add_approvalflow', 'exists': True},
                'update': {'full_code': 'approval.change_approvalflow', 'exists': True},
                'delete': {'full_code': 'approval.delete_approvalflow', 'exists': True},
            },
        },
        'approval_task': {
            'name': '待办审批',
            'module': '审批管理',
            'list_url': '/approval/pending/',
            'create_url': None,
            'edit_url_template': '/approval/{id}/process/',
            'permission_base': 'approval',
            'skip_permission_gate': True,
        },
        'meeting_minutes': {
            'name': '会议纪要',
            'module': '办公管理',
            'list_url': '/personal/minutes/',
            'create_url': '/personal/minutes/add/',
            'edit_url_template': '/personal/minutes/{id}/edit/',
            'permission': {
                'query': {'full_code': 'user.view_meeting_minutes', 'exists': True},
                'create': {'full_code': 'user.add_meeting_minutes', 'exists': True},
                'update': {'full_code': 'user.change_meeting_minutes', 'exists': True},
                'delete': {'full_code': 'user.delete_meeting_minutes', 'exists': True},
            },
        },
        'task': {
            'name': '任务',
            'module': '任务管理',
            'list_url': '/task/',
            'create_url': '/task/add/',
            'edit_url_template': '/task/edit/{id}/',
            'permission_base': 'task',
        },
        'workhour': {
            'name': '工时',
            'module': '任务管理',
            'list_url': '/task/workhour/',
            'create_url': '/task/workhour/add/',
            'edit_url_template': '/task/workhour/edit/{id}/',
            'permission_base': 'workhour',
        },
        'message': {
            'name': '站内消息',
            'module': '消息中心',
            'list_url': '/message/page/',
            'create_url': None,
            'edit_url_template': None,
            'permission_base': 'message',
        },
        'notice': {
            'name': '通知公告',
            'module': '办公管理',
            'list_url': '/system/admin_office/notice/',
            'create_url': '/system/admin_office/notice/create/',
            'edit_url_template': '/system/admin_office/notice/{id}/update/',
            'permission_base': 'notice',
        },
        'meeting': {
            'name': '会议',
            'module': '办公管理',
            'list_url': '/oa/meeting/list/',
            'create_url': '/oa/meeting/apply/',
            'edit_url_template': '/oa/meeting/view/{id}/',
            'permission': {
                'query': {'full_code': 'user.view_meeting_record', 'exists': True},
                'create': {'full_code': 'user.apply_meeting', 'exists': True},
                'update': {'full_code': 'user.change_meeting_record', 'exists': True},
                'delete': {'full_code': 'user.delete_meeting_record', 'exists': True},
            },
        },
        'schedule': {
            'name': '工作日程',
            'module': '个人办公',
            'list_url': '/oa/schedule/',
            'create_url': '/oa/schedule/add/',
            'edit_url_template': '/oa/schedule/view/{id}/',
            'permission_base': 'work_calendar',
        },
        'document': {
            'name': '文档',
            'module': '公文管理',
            'list_url': '/system/admin_office/document/',
            'create_url': '/system/admin_office/document/create/',
            'edit_url_template': '/system/admin_office/document/update/{id}/',
            'action_urls': {
                'submit': '/system/admin_office/document/submit/{id}/',
                'approve': '/system/admin_office/document/approve/{id}/',
                'reject': '/system/admin_office/document/reject/{id}/',
                'publish': '/system/admin_office/document/publish/{id}/',
            },
            'permission': {
                'query': {'full_code': 'system.view_document', 'exists': True},
                'create': {'full_code': 'system.add_document', 'exists': True},
                'update': {'full_code': 'system.change_document', 'exists': True},
                'delete': {'full_code': 'system.delete_document', 'exists': True},
                'submit': {'full_code': 'system.change_document', 'exists': True},
                'approve': {'full_code': 'system.change_document_approve', 'exists': True},
                'reject': {'full_code': 'system.change_document_approve', 'exists': True},
                'publish': {'full_code': 'system.change_document_publish', 'exists': True},
            },
        },
        'project_document': {
            'name': '项目文档',
            'module': '项目管理',
            'list_url': '/project/document/',
            'create_url': '/project/document/add/',
            'edit_url_template': '/project/document/edit/{id}/',
            'permission': {
                'query': {'full_code': 'project.view_project_document', 'exists': True},
                'create': {'full_code': 'project.add_project_document', 'exists': True},
                'update': {'full_code': 'project.change_project_document', 'exists': True},
                'delete': {'full_code': 'project.delete_project_document', 'exists': True},
            },
        },
        'project_stage': {
            'name': '项目阶段',
            'module': '项目管理',
            'list_url': '/project/stage/',
            'create_url': '/project/stage/add/',
            'edit_url_template': '/project/stage/edit/{id}/',
            'permission': {
                'query': {'full_code': 'project.view_project_stage', 'exists': True},
                'create': {'full_code': 'project.add_project_stage', 'exists': True},
                'update': {'full_code': 'project.change_project_stage', 'exists': True},
                'delete': {'full_code': 'project.delete_project_stage', 'exists': True},
            },
        },
        'project_category': {
            'name': '项目分类',
            'module': '项目管理',
            'list_url': '/project/category/',
            'create_url': '/project/category/add/',
            'edit_url_template': '/project/category/edit/{id}/',
            'permission': {
                'query': {'full_code': 'project.view_project_category', 'exists': True},
                'create': {'full_code': 'project.add_project_category', 'exists': True},
                'update': {'full_code': 'project.change_project_category', 'exists': True},
                'delete': {'full_code': 'project.delete_project_category', 'exists': True},
            },
        },
        'work_type': {
            'name': '工作类型',
            'module': '项目管理',
            'list_url': '/project/worktype/',
            'create_url': '/project/worktype/add/',
            'edit_url_template': '/project/worktype/edit/{id}/',
            'permission': {
                'query': {'full_code': 'project.view_work_type', 'exists': True},
                'create': {'full_code': 'project.add_work_type', 'exists': True},
                'update': {'full_code': 'project.change_work_type', 'exists': True},
                'delete': {'full_code': 'project.delete_work_type', 'exists': True},
            },
        },
        'ai_model_config': {
            'name': 'AI模型配置',
            'module': 'AI智能中心',
            'list_url': '/ai/model-config/list/',
            'create_url': '/ai/model-config/create/',
            'edit_url_template': '/ai/model-config/update/{id}/',
            'permission': {
                'query': {'full_code': 'user.view_model_config', 'exists': True},
                'create': {'full_code': 'user.add_model_config', 'exists': True},
                'update': {'full_code': 'user.change_model_config', 'exists': True},
                'delete': {'full_code': 'user.delete_model_config', 'exists': True},
            },
        },
        'ai_knowledge_base': {
            'name': '知识库',
            'module': 'AI智能中心',
            'list_url': '/ai/knowledge-base/list/',
            'create_url': '/ai/knowledge-base/create/',
            'edit_url_template': '/ai/knowledge-base/update/{id}/',
            'permission': {
                'query': {'full_code': 'user.view_knowledge_base', 'exists': True},
                'create': {'full_code': 'user.add_knowledge_base', 'exists': True},
                'update': {'full_code': 'user.change_knowledge_base', 'exists': True},
                'delete': {'full_code': 'user.delete_knowledge_base', 'exists': True},
            },
        },
        'ai_workflow': {
            'name': 'AI工作流',
            'module': 'AI智能中心',
            'list_url': '/ai/workflow/list/',
            'create_url': '/ai/workflow/create/',
            'edit_url_template': '/ai/workflow/update/{id}/',
            'permission': {
                'query': {'full_code': 'user.view_ai_workflow', 'exists': True},
                'create': {'full_code': 'user.add_ai_workflow', 'exists': True},
                'update': {'full_code': 'user.change_ai_workflow', 'exists': True},
                'delete': {'full_code': 'user.delete_ai_workflow', 'exists': True},
            },
        },
        'supply_chain_forecast': {
            'name': '需求预测计划',
            'module': '供应链管理',
            'list_url': '/supply-chain/forecast/',
            'create_url': '/supply-chain/forecast/create/',
            'edit_url_template': '/supply-chain/forecast/review/{id}/',
            'permission': {
                'query': {'full_code': 'user.view_supply_chain_forecast', 'exists': True},
                'create': {'full_code': 'user.add_supply_chain_forecast', 'exists': True},
                'update': {'full_code': 'user.approve_supply_chain_forecast', 'exists': True},
            },
        },
        'supply_chain_outsource': {
            'name': '委外发料单',
            'module': '供应链管理',
            'list_url': '/supply-chain/outsource/',
            'create_url': '/supply-chain/outsource/create/',
            'edit_url_template': '/supply-chain/outsource/{id}/status/',
            'permission': {
                'query': {'full_code': 'user.view_supply_chain_outsource', 'exists': True},
                'create': {'full_code': 'user.add_supply_chain_outsource', 'exists': True},
                'update': {'full_code': 'user.change_supply_chain_outsource', 'exists': True},
            },
        },
        'supply_chain_pr_review': {
            'name': 'PR审核任务',
            'module': '供应链管理',
            'list_url': '/supply-chain/pr-review/',
            'create_url': '/supply-chain/pr-review/create/',
            'edit_url_template': '/supply-chain/pr-review/{id}/approve/',
            'permission': {
                'query': {'full_code': 'user.view_supply_chain_pr_review', 'exists': True},
                'create': {'full_code': 'user.add_supply_chain_pr_review', 'exists': True},
                'update': {'full_code': 'user.approve_supply_chain_pr_review', 'exists': True},
            },
        },
        'supply_chain_price_review': {
            'name': '单价复核单',
            'module': '供应链管理',
            'list_url': '/supply-chain/price-review/',
            'create_url': '/supply-chain/price-review/create/',
            'edit_url_template': '/supply-chain/price-review/{id}/analyze/',
            'permission': {
                'query': {'full_code': 'user.view_supply_chain_price_review', 'exists': True},
                'create': {'full_code': 'user.add_supply_chain_price_review', 'exists': True},
                'update': {'full_code': 'user.change_supply_chain_price_review', 'exists': True},
            },
        },
        'supply_chain_sample': {
            'name': '打样申请',
            'module': '供应链管理',
            'list_url': '/supply-chain/sample/',
            'create_url': '/supply-chain/sample/create/',
            'edit_url_template': '/supply-chain/sample/{id}/receive/',
            'permission': {
                'query': {'full_code': 'user.view_supply_chain_sample', 'exists': True},
                'create': {'full_code': 'user.add_supply_chain_sample', 'exists': True},
                'update': {'full_code': 'user.change_supply_chain_sample', 'exists': True},
            },
        },
        'payment': {
            'name': '付款单',
            'module': '财务管理',
            'list_url': '/finance/payment/',
            'create_url': '/finance/payment/add/',
            'edit_url_template': '/finance/payment/view/{id}/',
            'permission': {
                'query': {'full_code': 'finance.view_payment', 'exists': True},
                'create': {'full_code': 'finance.add_payment', 'exists': True},
                'update': {'full_code': 'finance.change_payment', 'exists': True},
                'delete': {'full_code': 'finance.delete_payment', 'exists': True},
            },
        },
        'position': {
            'name': '岗位',
            'module': '人事管理',
            'list_url': '/position/',
            'create_url': '/position/add/',
            'edit_url_template': '/position/edit/{id}/',
            'permission': {
                'query': {'full_code': 'position.view_position', 'exists': True},
                'create': {'full_code': 'position.add_position', 'exists': True},
                'update': {'full_code': 'position.change_position', 'exists': True},
                'delete': {'full_code': 'position.delete_position', 'exists': True},
            },
        },
        'enterprise': {
            'name': '企业信息',
            'module': '企业管理',
            'list_url': '/enterprise/enterprise_list/',
            'create_url': '/enterprise/enterprise_add/',
            'edit_url_template': '/enterprise/enterprise_add/{id}/',
            'skip_permission_gate': True,
        },
        'work_record': {
            'name': '工作记录',
            'module': '个人办公',
            'list_url': '/personal/record/',
            'create_url': '/personal/record/add/',
            'edit_url_template': '/personal/record/{id}/edit/',
            'skip_permission_gate': True,
        },
        'work_report': {
            'name': '工作汇报',
            'module': '个人办公',
            'list_url': '/personal/report/',
            'create_url': '/personal/report/add/',
            'edit_url_template': '/personal/report/{id}/edit/',
            'action_urls': {
                'submit': '/personal/report/{id}/edit/',
            },
            'skip_permission_gate': True,
        },
        'personal_note': {
            'name': '个人笔记',
            'module': '个人办公',
            'list_url': '/personal/note/',
            'create_url': '/personal/note/add/',
            'edit_url_template': '/personal/note/{id}/edit/',
            'skip_permission_gate': True,
        },
        'personal_task': {
            'name': '个人任务',
            'module': '个人办公',
            'list_url': '/personal/task/',
            'create_url': '/personal/task/add/',
            'edit_url_template': '/personal/task/{id}/edit/',
            'action_urls': {
                'submit': '/personal/task/{id}/edit/',
            },
            'skip_permission_gate': True,
        },
        'personal_contact': {
            'name': '个人联系人',
            'module': '个人办公',
            'list_url': '/personal/contact/',
            'create_url': '/personal/contact/add/',
            'edit_url_template': '/personal/contact/{id}/edit/',
            'skip_permission_gate': True,
        },
        'disk': {
            'name': '网盘文件',
            'module': '企业网盘',
            'list_url': '/disk/',
            'create_url': '/disk/upload/',
            'edit_url_template': '/disk/preview/{id}/',
            'permission_base': 'disk_file',
        },
        'disk_folder': {
            'name': '网盘文件夹',
            'module': '企业网盘',
            'list_url': '/disk/',
            'create_url': None,
            'edit_url_template': None,
            'permission_base': 'disk_folder',
        },
        'disk_share': {
            'name': '网盘分享',
            'module': '企业网盘',
            'list_url': '/disk/share/',
            'create_url': None,
            'edit_url_template': None,
            'permission_base': 'share',
            'available': False,
            'unavailable_reason': '网盘分享需要先定位具体文件或文件夹，已阻止直接写操作',
        },
    }

    def __init__(self):
        self.classifier = ai_intent_classifier
        self.query_service = query_service
        self.permission_checker = PermissionChecker()

    @property
    def intelligent_assistant(self):
        """获取智能助手实例（已禁用直接业务执行）"""
        return None

    def _get_intelligent_assistant(self, user):
        """阻止通过智能助手绕过意图识别和权限确认"""
        logger.warning("直接智能助手业务执行已被安全策略禁用")
        return None

    def process_user_request(
            self,
            user: User,
            query: str,
            chat_id: int | None = None,
            context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """处理用户请求"""
        try:
            conversation_context = self._build_conversation_context(user, chat_id, extra_context=context)
            intent_result = self.classifier.classify_intent(user, query)
            intent_result = self._apply_follow_up_context(intent_result, query, conversation_context)
            return self._process_intent_result(user, query, intent_result, conversation_context)

        except Exception as e:
            logger.error(f"处理用户请求失败：{str(e)}")
            return self._create_error_response('处理请求时发生错误，请稍后重试')

    def stream_user_request(
            self,
            user: User,
            query: str,
            chat_id: int | None = None,
            context: Dict[str, Any] | None = None):
        """以流式方式处理用户请求。"""
        try:
            conversation_context = self._build_conversation_context(
                user, chat_id, extra_context=context)
            intent_result = self.classifier.classify_intent(user, query)
            intent_result = self._apply_follow_up_context(
                intent_result, query, conversation_context)

            if not intent_result.get('intent'):
                yield {
                    'type': 'error',
                    'payload': self._create_error_response('无法识别您的意图，请重新描述您的需求')
                }
                return

            if intent_result.get('intent') == 'AI_CHAT':
                yield from self._stream_ai_chat(
                    user,
                    query,
                    conversation_context,
                    intent_result=intent_result,
                )
                return

            payload = self._process_intent_result(
                user,
                query,
                intent_result,
                conversation_context,
            )
            yield {
                'type': 'done',
                'payload': payload,
            }
        except Exception as e:
            logger.error(f"流式处理用户请求失败：{str(e)}")
            yield {
                'type': 'error',
                'payload': self._create_error_response('处理请求时发生错误，请稍后重试')
            }

    def _process_intent_result(
            self,
            user: User,
            query: str,
            intent_result: Dict[str, Any],
            conversation_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if not intent_result.get('intent'):
            return self._create_error_response('无法识别您的意图，请重新描述您的需求')

        if intent_result.get('source') != 'ai' and intent_result.get('intent') != 'UI_ACTION':
            return self._create_confirmation_response(intent_result, query, user)

        if self._is_mutating_intent(intent_result):
            return self._create_confirmation_response(intent_result, query, user)

        permission_result = self._check_data_permission(user, intent_result)
        if not permission_result['has_permission']:
            response = self._decorate_response_with_recognition_meta(
                self._create_permission_denied_response(intent_result, permission_result),
                intent_result,
            )
            return self._attach_mcp_context(response, intent_result, query)

        if intent_result['confidence'] < 0.65 or intent_result.get('requires_confirmation'):
            return self._create_confirmation_response(intent_result, query, user)

        execution_result = self._execute_intent(user, intent_result, query, conversation_context)
        response = self._decorate_response_with_recognition_meta(execution_result, intent_result)
        return self._attach_mcp_context(response, intent_result, query)

    def _apply_follow_up_context(
            self,
            intent_result: Dict[str, Any],
            query: str,
            conversation_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        conversation_context = conversation_context or {}
        previous_query = conversation_context.get('previous_query') or {}
        query_lower = (query or '').lower()
        if not previous_query:
            return intent_result

        previous_specific_intent = previous_query.get('specific_intent')
        is_short_follow_up = len((query or '').strip()) <= 20
        mentions_time_range = any(keyword in query_lower for keyword in ['本月', '这个月', '上月', '上个月', '今天', '昨天', '昨日'])
        mentions_count = any(keyword in query_lower for keyword in ['数量', '多少', '几个', '有几个', '总数'])
        mentions_in_progress = any(keyword in query_lower for keyword in ['进行中', '在进行'])
        mentions_detail = any(keyword in query_lower for keyword in ['明细', '列表', '看一下', '看下', '展开'])
        previous_entities = dict(previous_query.get('entities') or {})
        if previous_query.get('status') and 'status' not in previous_entities:
            previous_entities['status'] = previous_query.get('status')
        if previous_query.get('time_range') and 'time_range' not in previous_entities:
            previous_entities['time_range'] = previous_query.get('time_range')

        if (
            previous_specific_intent in {'order_total', 'order_total_this_month', 'order_total_last_month'} and
            is_short_follow_up and mentions_time_range and
            intent_result.get('intent') == 'AI_CHAT'
        ):
            patched = dict(intent_result)
            patched['intent'] = 'DATA_QUERY'
            patched['action'] = 'summary'
            patched['data_type'] = 'order'
            patched['confidence'] = max(float(patched.get('confidence', 0.0) or 0.0), 0.82)
            patched['requires_confirmation'] = False
            patched['reasoning'] = '承接上一轮订单金额查询的时间范围追问'
            entities = dict(patched.get('entities') or {})
            if any(keyword in query_lower for keyword in ['本月', '这个月']):
                patched['time_range'] = 'this_month'
                entities['time_range'] = 'this_month'
            elif any(keyword in query_lower for keyword in ['上月', '上个月']):
                patched['time_range'] = 'last_month'
                entities['time_range'] = 'last_month'
            elif '今天' in query_lower:
                patched['time_range'] = 'today'
                entities['time_range'] = 'today'
            elif any(keyword in query_lower for keyword in ['昨天', '昨日']):
                patched['time_range'] = 'yesterday'
                entities['time_range'] = 'yesterday'
            patched['entities'] = entities
            return patched

        if intent_result.get('intent') == 'AI_CHAT' and is_short_follow_up:
            if previous_specific_intent in {'approval_task_list', 'approval_task_count'} and mentions_count:
                patched = dict(intent_result)
                patched['intent'] = 'DATA_QUERY'
                patched['action'] = 'count'
                patched['data_type'] = 'approval_task'
                patched['confidence'] = max(float(patched.get('confidence', 0.0) or 0.0), 0.82)
                patched['requires_confirmation'] = False
                patched['reasoning'] = '承接上一轮待审批查询的数量追问'
                patched['entities'] = previous_entities
                return patched

            if previous_specific_intent in {'project_list', 'project_count', 'project_list_in_progress', 'project_count_in_progress'}:
                patched = dict(intent_result)
                if mentions_count or mentions_in_progress:
                    patched['intent'] = 'DATA_QUERY'
                    patched['data_type'] = 'project'
                    patched['action'] = 'count' if mentions_count else 'list'
                    patched['confidence'] = max(float(patched.get('confidence', 0.0) or 0.0), 0.8)
                    patched['requires_confirmation'] = False
                    patched['reasoning'] = '承接上一轮项目查询的状态/数量追问'
                    entities = dict(previous_entities)
                    if previous_specific_intent in {'project_list_in_progress', 'project_count_in_progress'} or mentions_in_progress:
                        entities['status'] = '进行中'
                    patched['entities'] = entities
                    return patched

            if mentions_detail:
                detail_data_type = None
                if previous_specific_intent:
                    if previous_specific_intent.startswith('supplier'):
                        detail_data_type = 'supplier'
                    elif previous_specific_intent.startswith('product'):
                        detail_data_type = 'product'
                    elif previous_specific_intent.startswith('inventory'):
                        detail_data_type = 'inventory'
                    elif previous_specific_intent.startswith('followup'):
                        detail_data_type = 'followup'
                    elif previous_specific_intent.startswith('approval_task'):
                        detail_data_type = 'approval_task'
                    elif previous_specific_intent.startswith('approval'):
                        detail_data_type = 'approval'
                    elif previous_specific_intent.startswith('disk_share'):
                        detail_data_type = 'disk_share'
                    elif previous_specific_intent.startswith('disk'):
                        detail_data_type = 'disk'
                if detail_data_type:
                    patched = dict(intent_result)
                    patched['intent'] = 'DATA_QUERY'
                    patched['data_type'] = detail_data_type
                    patched['action'] = 'list'
                    patched['confidence'] = max(float(patched.get('confidence', 0.0) or 0.0), 0.8)
                    patched['requires_confirmation'] = False
                    patched['reasoning'] = '承接上一轮统计结果的明细追问'
                    patched['entities'] = previous_entities
                    return patched

        return intent_result

    def _check_data_permission(
            self, user: User, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查用户数据权限

        Args:
            user: 当前用户
            intent_result: 意图识别结果

        Returns:
            Dict[str, Any]: 权限检查结果
        """
        if user.is_superuser:
            return {
                'has_permission': True,
                'message': '超级管理员权限',
                'data_scope': 'all'
            }

        intent_type = intent_result.get('intent')
        data_type = intent_result.get('data_type')
        action = intent_result.get('action')

        if intent_type == 'AI_CHAT':
            return {
                'has_permission': True,
                'message': '对话无需权限',
                'data_scope': 'chat'
            }

        if intent_type == 'KNOWLEDGE_BASE':
            return {
                'has_permission': True,
                'message': '知识库查询权限',
                'data_scope': 'knowledge'
            }

        if intent_result.get('intent') == 'UI_ACTION':
            return {'has_permission': True}

        if intent_result.get('action') in {'create', 'update', 'delete'} or intent_result.get('intent') in {'DATA_CREATE', 'DATA_UPDATE', 'DATA_DELETE'}:
            return {
                'has_permission': False,
                'required_permission': 'explicit_confirmation',
                'message': '数据新增、修改、删除需要在业务页面中确认后执行'
            }

        if not data_type:
            return {
                'has_permission': True,
                'message': '通用查询权限',
                'data_scope': 'general'
            }

        permission_map = dict(getattr(self.query_service, 'permission_mapping', {}) or {})
        permission_map.update({
            'approval_task': 'approval.view_approval',
            'production': 'production.view_productionplan',
            'production_plan': 'production.view_productionplan',
            'production_task': 'production.view_productiontask',
            'production_equipment': 'production.view_equipment',
            'production_procedure': 'production.view_productionprocedure',
            'finance': 'finance.view_expense',
            'finance_expense': 'finance.view_expense',
            'expense': 'finance.view_expense',
            'finance_invoice': 'finance.view_invoice',
            'finance_income': 'finance.view_payment_receive',
            'income': 'finance.view_payment_receive',
            'invoice': 'customer.view_customerinvoice',
        })

        required_permission = permission_map.get(data_type)

        if not required_permission:
            return {
                'has_permission': False,
                'required_permission': 'mapped_business_permission',
                'message': f'{data_type} 类型暂未配置 AI 查询权限映射',
                'data_scope': 'forbidden'
            }

        if required_permission == '__authenticated__':
            has_permission = bool(getattr(user, 'is_authenticated', False))
        else:
            has_permission = user.has_perm(required_permission)

        if not has_permission:
            return {
                'has_permission': False,
                'message': f'您没有权限访问{data_type}数据',
                'required_permission': required_permission,
                'data_scope': 'none'
            }

        data_scope = self._get_user_data_scope(user, data_type)

        return {
            'has_permission': True,
            'message': '权限验证通过',
            'data_scope': data_scope,
            'action': action
        }

    def _get_user_data_scope(self, user: User, data_type: str) -> str:
        """
        获取用户的数据范围

        Args:
            user: 当前用户
            data_type: 数据类型

        Returns:
            str: 数据范围描述
        """
        try:
            from apps.system.middleware.data_permission_middleware import DataScopeFilter
            data_scope = DataScopeFilter.get_user_data_scope(user)
            return data_scope.get('scope', 'self')
        except Exception as e:
            logger.error(f"获取数据范围失败：{str(e)}")
            return 'self'

    def _execute_intent(
            self, user: User, intent_result: Dict[str, Any], query: str, conversation_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        执行意图处理

        Args:
            user: 当前用户
            intent_result: 意图识别结果
            query: 原始查询

        Returns:
            Dict[str, Any]: 执行结果
        """
        intent_type = intent_result.get('intent')
        action = intent_result.get('action')
        intent_result.get('data_type')

        if intent_type == 'UI_ACTION':
            return {
                'success': True,
                'intent_type': intent_type,
                'result': '已识别为安全界面操作',
                'ui_action': intent_result.get('action'),
                'confidence': intent_result.get('confidence', 0.0),
                'requires_client_action': True
            }

        if intent_type == 'AI_CHAT':
            return self._handle_ai_chat(user, query, conversation_context)

        if intent_type == 'KNOWLEDGE_BASE':
            return self._handle_knowledge_base(user, query)

        if intent_type in ['DATA_QUERY', 'DATA_CREATE', 'DATA_UPDATE', 'DATA_DELETE']:
            if self._is_mutating_intent(intent_result):
                return self._create_confirmation_response(intent_result, query, user)
            return self._handle_data_query(user, intent_result, query, conversation_context)

        return self._handle_data_query(user, intent_result, query, conversation_context)

    def _handle_data_query(
            self, user: User, intent_result: Dict[str, Any], query: str, conversation_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """处理数据查询"""
        try:
            result = self.query_service.process_query(
                user,
                query,
                intent_result,
                context=conversation_context,
            )

            if result.get('success'):
                return {
                    'success': True,
                    'intent_type': 'DATA_QUERY',
                    'result': result['result'],
                    'data': result.get('data'),
                    'confidence': intent_result.get('confidence', 0.0),
                    'specific_intent': result.get('specific_intent')
                }
            else:
                return self._create_error_response(result.get('message', '查询失败'))

        except Exception as e:
            logger.error(f"数据查询处理失败：{str(e)}")
            return self._create_error_response('数据查询失败，请稍后重试')

    def _build_conversation_context(
            self,
            user: User,
            chat_id: int | None,
            extra_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        base_context = dict(extra_context or {})
        if not chat_id or not hasattr(user, 'pk'):
            return base_context
        try:
            chat = AIChat.objects.get(id=chat_id, user=user)
        except AIChat.DoesNotExist:
            return base_context

        previous_user_message = (
            AIChatMessage.objects.filter(chat=chat, role='user')
            .order_by('-created_at')
            .first()
        )
        previous_assistant_message = (
            AIChatMessage.objects.filter(chat=chat, role='assistant')
            .exclude(runtime_payload={})
            .order_by('-created_at')
            .first()
        )

        base_context.update({
            'previous_user_message': previous_user_message.content if previous_user_message else '',
            'previous_query': previous_assistant_message.runtime_payload if previous_assistant_message else {},
        })
        return base_context

    def _handle_data_create(
            self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        处理数据创建

        Args:
            user: 当前用户
            intent_result: 意图识别结果
            query: 原始查询

        Returns:
            Dict[str, Any]: 创建结果
        """
        return self._create_confirmation_response(intent_result, query, user)

    def _handle_data_update(
            self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        处理数据修改

        Args:
            user: 当前用户
            intent_result: 意图识别结果
            query: 原始查询

        Returns:
            Dict[str, Any]: 修改结果
        """
        return self._create_confirmation_response(intent_result, query, user)

    def _handle_knowledge_base(self, user: User, query: str) -> Dict[str, Any]:
        """
        处理知识库查询

        Args:
            user: 当前用户
            query: 原始查询

        Returns:
            Dict[str, Any]: 查询结果
        """
        return {
            'success': True,
            'message': '知识库功能正在开发中',
            'intent_type': 'KNOWLEDGE_BASE',
            'result': '知识库查询功能即将上线，敬请期待'
        }

    def _handle_ai_chat(
            self,
            user: User,
            query: str,
            conversation_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """处理 AI 对话"""
        try:
            from apps.ai.services.ai_intent_classifier import ai_intent_classifier

            ai_intent_classifier._ensure_ai_client(force_refresh=True)
            ai_config = ai_intent_classifier.ai_config or {}
            if self._is_model_meta_question(query):
                response_text = self._build_model_meta_response(ai_config, conversation_context)
                return {
                    'success': True,
                    'message': response_text,
                    'intent_type': 'AI_CHAT',
                    'result': response_text,
                    'confidence': 1.0
                }
            ai_client = ai_intent_classifier.ai_client
            if ai_client is None:
                return self._create_fallback_response(query)

            messages = [
                {
                    'role': 'system',
                    'content': self._build_ai_chat_system_prompt(query, conversation_context, ai_config),
                },
                {'role': 'user', 'content': query}
            ]

            response = ai_client.chat_completion(messages=messages)
            response_text = response.get('content', '') if isinstance(response, dict) else str(response)

            if not response_text or not response_text.strip():
                logger.warning("AI 返回空响应，使用降级响应")
                return self._create_fallback_response(query)

            return {
                'success': True,
                'message': response_text,
                'intent_type': 'AI_CHAT',
                'result': response_text,
                'confidence': 1.0
            }
        except Exception as e:
            logger.error(f"AI 对话失败：{str(e)}")
            return self._create_fallback_response(query)

    def _stream_ai_chat(
            self,
            user: User,
            query: str,
            conversation_context: Dict[str, Any] | None = None,
            intent_result: Dict[str, Any] | None = None):
        """流式处理 AI 对话。"""
        try:
            from apps.ai.services.ai_intent_classifier import ai_intent_classifier

            ai_intent_classifier._ensure_ai_client(force_refresh=True)
            ai_config = ai_intent_classifier.ai_config or {}
            if self._is_model_meta_question(query):
                response_text = self._build_model_meta_response(ai_config, conversation_context)
                payload = {
                    'success': True,
                    'message': response_text,
                    'result': response_text,
                    'intent_type': 'AI_CHAT',
                    'confidence': 1.0,
                    'source': 'ai',
                    'ai_available': True,
                    'ai_configured': True,
                    'model_provider': ai_config.get('provider'),
                    'model_name': ai_config.get('model_name'),
                }
                payload = self._decorate_response_with_recognition_meta(payload, intent_result)
                payload = self._attach_mcp_context(payload, intent_result or payload, query)
                yield {'type': 'done', 'payload': payload}
                return

            ai_client = ai_intent_classifier.ai_client
            if ai_client is None:
                payload = self._create_fallback_response(query)
                yield {'type': 'done', 'payload': payload}
                return

            messages = [
                {
                    'role': 'system',
                    'content': self._build_ai_chat_system_prompt(query, conversation_context, ai_config),
                },
                {'role': 'user', 'content': query}
            ]

            assistant_text = ''
            for chunk in ai_client.stream_chat_completion(messages=messages):
                if not chunk:
                    continue
                assistant_text += chunk
                yield {'type': 'chunk', 'content': chunk}

            if not assistant_text.strip():
                payload = self._create_fallback_response(query)
                yield {'type': 'done', 'payload': payload}
                return

            payload = {
                'success': True,
                'message': assistant_text,
                'result': assistant_text,
                'intent_type': 'AI_CHAT',
                'confidence': 1.0,
                'source': 'ai',
                'ai_available': True,
                'ai_configured': True,
                'model_provider': ai_config.get('provider'),
                'model_name': ai_config.get('model_name'),
            }
            payload = self._decorate_response_with_recognition_meta(payload, intent_result)
            payload = self._attach_mcp_context(payload, intent_result or payload, query)
            yield {'type': 'done', 'payload': payload}
        except Exception as e:
            logger.error(f"AI 流式对话失败：{str(e)}")
            payload = self._create_fallback_response(query)
            yield {'type': 'done', 'payload': payload}

    def _build_ai_chat_system_prompt(
            self,
            query: str,
            conversation_context: Dict[str, Any] | None,
            ai_config: Dict[str, Any] | None) -> str:
        page_context = (conversation_context or {}).get('page_context') or {}
        previous_user_message = (conversation_context or {}).get('previous_user_message') or ''
        previous_query = (conversation_context or {}).get('previous_query') or {}
        model_name = ai_config.get('model_name') or ', '.join(ai_config.get('model_names') or [])
        prompt_parts = [
            '你是 DTCall 系统内的 AI 助手。',
            '回答时优先结合当前系统、当前页面、当前业务模块，不要把自己描述成通用闲聊助手。',
            '当用户询问在这个项目、这个系统、这个页面里可以做什么时，应优先说明当前页面相关的业务功能、操作建议、数据理解和风险提示。',
            '你可以解释 DTCall 中的客户、合同、项目、审批、财务、生产、网盘等模块。',
            '不要声称会直接新增、修改、删除业务数据；涉及写操作时，应明确说明需要在业务页面内继续完成。',
        ]
        if model_name:
            prompt_parts.append(f'当前接入模型：{model_name}。')
        if page_context:
            title = page_context.get('title') or '未识别'
            module = page_context.get('module') or '综合业务'
            path = page_context.get('path') or ''
            prompt_parts.append(f'当前页面标题：{title}。')
            prompt_parts.append(f'当前业务模块：{module}。')
            if path:
                prompt_parts.append(f'当前页面路径：{path}。')
            if page_context.get('summary'):
                prompt_parts.append(f'页面摘要：{page_context.get("summary")}。')
        if previous_user_message:
            prompt_parts.append(f'上一条用户消息：{previous_user_message}。')
        specific_intent = previous_query.get('specific_intent')
        if specific_intent:
            prompt_parts.append(f'上一轮识别到的业务意图：{specific_intent}。')
        prompt_parts.append(f'请结合以上上下文回答当前问题：{query}')
        return '\n'.join(prompt_parts)

    def _is_model_meta_question(self, query: str) -> bool:
        value = str(query or '').strip().lower()
        if not value:
            return False
        keywords = [
            '什么模型', '啥模型', '哪个模型', '模型是什么', '你是什么模型',
            'model', 'llm', 'api base', 'api_base', 'base url', 'base_url',
        ]
        return any(keyword in value for keyword in keywords)

    def _build_model_meta_response(
            self,
            ai_config: Dict[str, Any],
            conversation_context: Dict[str, Any] | None = None) -> str:
        page_context = (conversation_context or {}).get('page_context') or {}
        model_names = ai_config.get('model_names') or []
        model_name = ai_config.get('model_name') or (', '.join(model_names) if model_names else '未配置')
        api_base = ai_config.get('api_base') or ai_config.get('base_url') or '未配置'
        provider = ai_config.get('provider') or 'openai-compatible'

        parts = [
            f'当前在 DTCall 中接入的是 {provider} 兼容模型。',
            f'模型名称：{model_name}。',
            f'接口地址：{api_base}。',
        ]
        if page_context.get('title'):
            parts.append(f'当前页面：{page_context.get("title")}。')
        parts.append('我会优先结合当前系统页面和业务上下文来回答。')
        return ''.join(parts)

    def _create_fallback_response(self, query: str) -> Dict[str, Any]:
        """创建降级响应（AI 不可用时）"""
        ai_configured = ai_intent_classifier.ai_config is not None
        failure_reason = 'AI 模型服务暂时不可用，请稍后重试。' if ai_configured else '当前未配置可用的 AI 模型，请先完成模型配置。'
        response = (
            'AI 模型服务暂时不可用，我可以继续提供基础帮助。请稍后重试。'
            if ai_configured else
            '当前未配置可用的 AI 模型，我可以继续提供基础帮助。请配置 AI 模型后获得更准确的意图识别和自然语言理解能力。'
        )

        payload = {
            'success': True,
            'message': response,
            'intent_type': 'AI_CHAT',
            'result': response,
            'confidence': 0.35,
            'source': 'safe_fallback',
            'ai_available': False,
            'ai_configured': ai_configured,
            'failure_reason': failure_reason,
            'model_provider': ai_intent_classifier.ai_config.get('provider') if ai_intent_classifier.ai_config else None,
            'model_name': ai_intent_classifier.ai_config.get('model_name') if ai_intent_classifier.ai_config else None,
        }
        payload = self._decorate_response_with_recognition_meta(payload, payload)
        return self._attach_mcp_context(payload, payload, query)

    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            'success': False,
            'message': message,
            'intent_type': None,
            'confidence': 0.0
        }

    def _create_permission_denied_response(
            self, intent_result: Dict[str, Any], permission_result: Dict[str, Any]) -> Dict[str, Any]:
        """创建权限拒绝响应"""
        return {
            'success': False,
            'message': permission_result.get(
                'message',
                '您没有权限执行此操作'),
            'intent_type': intent_result.get('intent'),
            'confidence': intent_result.get('confidence'),
            'requires_permission': permission_result.get('required_permission'),
            'suggestion': '请联系管理员获取相应权限'}

    def _create_confirmation_response(
            self, intent_result: Dict[str, Any], query: str, user: User = None) -> Dict[str, Any]:
        """创建确认响应"""
        intent_type = intent_result.get('intent')
        confidence = intent_result.get('confidence', 0)
        business_task = None

        if self._is_mutating_intent(intent_result):
            business_task = self._build_business_handoff(
                user, intent_result, query) if user else self._build_unknown_business_handoff(intent_result, query)
            if business_task:
                if business_task.get('data_type') and not any(
                        isinstance(option, dict) and option.get('action') == 'clarify_business_type'
                        for option in (business_task.get('options') or [])):
                    options = [
                        {'text': '确认并执行', 'intent': intent_type, 'action': 'confirm_operation'}
                    ] + [
                        option for option in (business_task.get('options') or [])
                        if not (isinstance(option, dict) and option.get('action') == 'confirm_operation')
                    ]
                    business_task = dict(business_task)
                    business_task['options'] = options
                else:
                    options = business_task.get('options', [])
                message = business_task.get('message')
            else:
                options = [
                    {'text': '确认并执行', 'intent': intent_type, 'action': 'confirm_operation'},
                    {'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel'},
                ]
                message = '已识别到数据新增、修改或删除意图。请确认后直接执行，系统会保留本次操作的回退记录。'
        else:
            options = intent_result.get('fallback_options', [])
            if not options:
                options = [
                    {'text': '按普通 AI 对话处理', 'intent': 'AI_CHAT', 'action': 'chat'},
                    {'text': '补充数据查询条件', 'intent': 'DATA_QUERY', 'action': 'query'},
                    {'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel'},
                ]

            if intent_result.get('source') != 'ai':
                failure_reason = intent_result.get('failure_reason')
                if intent_result.get('ai_configured'):
                    if failure_reason in {None, '', 'AI 模型暂时不可用', 'AI 模型服务暂时不可用'}:
                        prefix = 'AI 模型服务暂时不可用。'
                    else:
                        prefix = failure_reason
                    message = f'{prefix} 当前已按安全降级规则识别您的意图。您可以继续补充说明，或稍后再试。'
                else:
                    message = '当前未配置可用的 AI 模型，无法进行高置信度意图识别。请补充说明或先配置 AI 模型。'
            else:
                message = f'我不太确定您的意图（置信度：{confidence:.0%}），请选择：'

        response = {
            'success': True,
            'requires_confirmation': True,
            'message': message,
            'intent_type': intent_type,
            'confidence': confidence,
            'options': options,
            'original_query': query,
            'source': intent_result.get('source'),
            'action': intent_result.get('action'),
            'data_type': intent_result.get('data_type'),
            'entities': intent_result.get('entities') or {},
            'ai_available': intent_result.get('ai_available', False),
            'ai_configured': intent_result.get('ai_configured', False),
            'failure_reason': intent_result.get('failure_reason'),
            'model_provider': intent_result.get('model_provider'),
            'model_name': intent_result.get('model_name'),
        }
        if business_task:
            response['task'] = business_task
            response['requires_client_action'] = True
        response = self._decorate_response_with_recognition_meta(response, intent_result)
        return self._attach_mcp_context(response, intent_result, query)

    def _is_mutating_intent(self, intent_result: Dict[str, Any]) -> bool:
        return (
            intent_result.get('action') in self.MUTATING_ACTIONS or
            intent_result.get('intent') in self.MUTATING_INTENTS
        )

    def _build_business_handoff(
            self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        candidate_data_types = self._get_candidate_data_types(intent_result)
        if intent_result.get('source') != 'ai' and len(candidate_data_types) > 1:
            return self._build_business_type_clarification_handoff(intent_result, query, candidate_data_types)

        data_type = intent_result.get('data_type')
        if not data_type:
            return self._build_unknown_business_handoff(intent_result, query)

        if data_type not in self.BUSINESS_HANDOFF_CONFIG:
            return self._build_unknown_business_handoff(intent_result, query)

        config = self.BUSINESS_HANDOFF_CONFIG.get(data_type)
        if not config:
            return self._build_unknown_business_handoff(intent_result, query)

        action = self._normalize_business_action(intent_result)
        title = self._build_business_title(action, config['name'])
        target_url, disabled_reason = self._resolve_business_target_url(config, action, intent_result)
        permission = self._build_business_permission(config.get('permission') or config.get('permission_base'), action)
        entities = intent_result.get('entities') or {}
        skip_permission_gate = bool(config.get('skip_permission_gate'))
        permission_exists = True if skip_permission_gate else self._business_permission_exists(permission)
        user_has_permission = True if skip_permission_gate else self._user_has_business_permission(user, permission)
        if not skip_permission_gate:
            disabled_reason = self._merge_disabled_reason(disabled_reason, None if permission_exists else '当前业务操作权限节点未配置，已阻止直接打开')
            disabled_reason = self._merge_disabled_reason(disabled_reason, None if user_has_permission else '您当前没有该业务操作权限')
        enabled = bool(target_url and not disabled_reason and config.get('available', True))
        safety_notice = self._get_business_safety_notice(action)
        if action in {'update', 'delete'} and target_url == config.get('list_url'):
            safety_notice = f'{safety_notice} 请先在列表中定位具体记录后再继续操作。'
        message = f'已识别到{title}意图。{safety_notice}'
        if disabled_reason:
            message = f'已识别到{title}意图，但{disabled_reason}。'

        task = {
            'type': 'business_handoff',
            'intent_type': intent_result.get('intent'),
            'action': action,
            'data_type': data_type,
            'module': config.get('module'),
            'title': title,
            'target_url': target_url,
            'list_url': config.get('list_url'),
            'open_mode': 'tab',
            'requires_user_confirmation': True,
            'safety_notice': safety_notice,
            'message': message,
            'prefill': self._sanitize_prefill(entities),
            'permission_required': permission,
            'permission_exists': permission_exists,
            'has_business_permission': user_has_permission,
            'enabled': enabled,
            'disabled_reason': disabled_reason,
            'confidence': intent_result.get('confidence', 0),
            'options': [],
        }
        task['options'] = self._build_business_options(task, config)
        return task

    def _build_business_type_clarification_handoff(
            self,
            intent_result: Dict[str, Any],
            query: str,
            candidate_data_types: list[str]) -> Dict[str, Any]:
        action = self._normalize_business_action(intent_result)
        title = '请确认业务类型'
        business_names = [
            self.BUSINESS_HANDOFF_CONFIG.get(data_type, {}).get('name', data_type)
            for data_type in candidate_data_types
        ]
        message = f'当前为安全降级识别，请先确认具体业务类型。该请求可能是在处理：{"、".join(business_names)}。'
        task = {
            'type': 'business_handoff',
            'intent_type': intent_result.get('intent'),
            'action': action,
            'data_type': intent_result.get('data_type'),
            'module': None,
            'title': title,
            'target_url': None,
            'list_url': None,
            'open_mode': 'tab',
            'requires_user_confirmation': True,
            'safety_notice': 'AI 在规则降级下不会直接进入写操作页面，请先确认业务类型后再继续。',
            'message': message,
            'prefill': self._sanitize_prefill(intent_result.get('entities') or {}),
            'permission_required': None,
            'has_business_permission': False,
            'enabled': False,
            'disabled_reason': None,
            'confidence': intent_result.get('confidence', 0),
            'options': [],
        }
        for data_type in candidate_data_types:
            config = self.BUSINESS_HANDOFF_CONFIG.get(data_type) or {}
            business_name = config.get('name', data_type)
            task['options'].append({
                'text': self._build_business_title(action, business_name),
                'intent': intent_result.get('intent'),
                'action': 'clarify_business_type',
                'data_type': data_type,
                'enabled': True,
                'rewrite_prompt': f'请按{business_name}处理：{query}',
            })
        task['options'].append({'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel', 'enabled': True})
        return task

    def _build_unknown_business_handoff(
            self, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        action = self._normalize_business_action(intent_result)
        title = self._build_business_title(action, '业务数据')
        message = f'已识别到{title}意图，但暂时无法确定具体业务模块。请补充说明客户、项目、合同、订单等业务类型后再继续。'
        task = {
            'type': 'business_handoff',
            'intent_type': intent_result.get('intent'),
            'action': action,
            'data_type': intent_result.get('data_type'),
            'module': None,
            'title': title,
            'target_url': None,
            'list_url': None,
            'open_mode': 'tab',
            'requires_user_confirmation': True,
            'safety_notice': 'AI 不会直接新增、修改或删除业务数据。',
            'message': message,
            'prefill': {},
            'permission_required': None,
            'has_business_permission': False,
            'enabled': False,
            'disabled_reason': '无法确定具体业务模块',
            'confidence': intent_result.get('confidence', 0),
            'options': [],
        }
        task['options'] = [
            {'text': '补充业务类型', 'intent': 'DATA_QUERY', 'action': 'clarify', 'enabled': True},
            {'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel', 'enabled': True},
        ]
        return task

    def _normalize_business_action(self, intent_result: Dict[str, Any]) -> str:
        action = intent_result.get('action')
        intent_type = intent_result.get('intent')
        if action in self.MUTATING_ACTIONS:
            return action
        if intent_type == 'DATA_CREATE':
            return 'create'
        if intent_type == 'DATA_UPDATE':
            return 'update'
        if intent_type == 'DATA_DELETE':
            return 'delete'
        return 'query'

    def _build_business_title(self, action: str, business_name: str) -> str:
        action_names = {
            'create': '新增',
            'update': '修改',
            'delete': '删除',
            'approve': '审批',
            'reject': '驳回',
            'submit': '提交',
            'publish': '发布',
            'withdraw': '撤回',
            'stock': '执行',
            'query': '查看',
        }
        return f"{action_names.get(action, '处理')}{business_name}"

    def _get_business_safety_notice(self, action: str) -> str:
        if action == 'delete':
            return 'AI 会在您确认后直接执行删除，并保留本次操作的单条回退记录。'
        if action in {'update', 'approve', 'reject', 'submit', 'publish', 'withdraw', 'stock'}:
            return 'AI 会在您确认后直接执行修改，并保留本次操作的单条回退记录。'
        return 'AI 会在您确认后直接执行新增，并保留本次操作的单条回退记录。'

    def _resolve_business_target_url(
            self, config: Dict[str, Any], action: str, intent_result: Dict[str, Any]):
        if not config.get('available', True):
            return None, config.get('unavailable_reason') or '该业务模块当前不可用'

        if action == 'create':
            create_url = config.get('create_url')
            if create_url:
                return create_url, None
            create_template = config.get('create_url_template')
            if create_template:
                return self._format_business_url_template(create_template, intent_result)
            return None, '未配置新增页面入口'

        action_urls = config.get('action_urls') or {}
        if action in action_urls:
            template = action_urls.get(action)
            if template:
                formatted_url, format_reason = self._format_business_url_template(template, intent_result)
                if formatted_url:
                    return formatted_url, None
                if format_reason:
                    return None, format_reason
            if config.get('list_url'):
                return config.get('list_url'), None
            return None, '未配置业务动作页面入口'

        if action in {'update', 'delete'}:
            template = config.get('edit_url_template')
            if template:
                formatted_url, format_reason = self._format_business_url_template(template, intent_result)
                if formatted_url:
                    return formatted_url, None
                if format_reason:
                    return None, format_reason
            if config.get('list_url'):
                return config.get('list_url'), None
            return None, '未配置业务列表页面入口'

        return config.get('list_url'), None if config.get('list_url') else '未配置业务页面入口'

    def _extract_record_id(self, intent_result: Dict[str, Any]):
        entities = intent_result.get('entities') or {}
        for key in ('id', 'pk', 'record_id', 'object_id'):
            value = entities.get(key) or intent_result.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return value
        return None

    def _format_business_url_template(
            self, template: str | None, intent_result: Dict[str, Any]) -> tuple[str | None, str | None]:
        if not template:
            return None, '未配置业务页面入口'

        params = self._extract_business_url_params(intent_result)
        required_keys = [match.group(1) for match in re.finditer(r'{(\w+)}', template)]
        missing_keys = [key for key in required_keys if params.get(key) in (None, '')]
        if missing_keys:
            return None, self._build_missing_business_url_reason(missing_keys)

        try:
            return template.format(**params), None
        except KeyError as exc:
            return None, self._build_missing_business_url_reason([str(exc).strip("'")])

    def _extract_business_url_params(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        entities = intent_result.get('entities') or {}

        def pick(*keys):
            for key in keys:
                value = entities.get(key)
                if value not in (None, ''):
                    return value
                value = intent_result.get(key)
                if value not in (None, ''):
                    return value
            return None

        return {
            'id': pick('id', 'pk', 'record_id', 'object_id'),
            'flow_id': pick('flow_id', 'flow_pk', 'approval_flow_id'),
        }

    def _build_missing_business_url_reason(self, missing_keys: list[str]) -> str:
        if 'flow_id' in missing_keys:
            return '缺少所属流程信息，无法定位审批步骤页面'
        if 'id' in missing_keys:
            return '缺少业务记录标识，无法直接定位到目标记录'
        return f"缺少必要参数：{', '.join(missing_keys)}"

    def _build_business_permission(self, permission_config, action: str):
        if not permission_config:
            return None
        if isinstance(permission_config, dict):
            if 'full_code' in permission_config or 'codename' in permission_config:
                return self._normalize_business_permission(permission_config, action)
            selected = permission_config.get(action) or permission_config.get('query')
            if not selected:
                return None
            return self._build_business_permission(selected, action)
        if isinstance(permission_config, str) and '.' in permission_config:
            return self._normalize_business_permission({'full_code': permission_config}, action)

        permission_base = permission_config
        permission_actions = {
            'create': 'add',
            'update': 'change',
            'delete': 'delete',
            'query': 'view',
        }
        permission_action = permission_actions.get(action, 'view')
        codename = f'{permission_action}_{permission_base}'
        return {
            'app_label': 'user',
            'codename': codename,
            'full_code': f'user.{codename}',
            'action': permission_action,
            'name': self._get_permission_display_name(codename),
        }

    def _normalize_business_permission(self, permission_config: Dict[str, Any], action: str):
        full_code = permission_config.get('full_code')
        codename = permission_config.get('codename')
        app_label = permission_config.get('app_label')

        if full_code and '.' in full_code:
            inferred_app_label, inferred_codename = full_code.split('.', 1)
            app_label = app_label or inferred_app_label
            codename = codename or inferred_codename
        elif full_code and not codename:
            codename = full_code

        if codename and not full_code:
            app_label = app_label or 'user'
            full_code = f'{app_label}.{codename}'

        return {
            'app_label': app_label or 'user',
            'codename': codename,
            'full_code': full_code,
            'action': permission_config.get('action') or action,
            'name': permission_config.get('name') or self._get_permission_display_name(codename or full_code or ''),
            'exists': permission_config.get('exists'),
        }

    def _business_permission_exists(self, permission: Dict[str, Any]) -> bool:
        if not permission:
            return False
        if permission.get('exists') is not None:
            return bool(permission.get('exists'))
        codename = permission.get('codename')
        if not codename:
            return False
        try:
            node_map = permission_node_mapper._build_node_permission_map()
            return codename in node_map
        except Exception:
            return False

    def _user_has_business_permission(self, user: User, permission: Dict[str, Any]) -> bool:
        if not permission:
            return False
        if not self._business_permission_exists(permission):
            return False
        if getattr(user, 'is_superuser', False):
            return True
        full_code = permission.get('full_code')
        codename = permission.get('codename')
        try:
            return bool(
                (full_code and user.has_perm(full_code)) or
                (codename and user.has_perm(codename))
            )
        except Exception:
            return False

    def _get_permission_display_name(self, codename: str) -> str:
        try:
            permission = permission_node_mapper.get_full_permission(codename)
            if permission:
                return permission
        except Exception:
            pass
        return codename

    def _merge_disabled_reason(self, current_reason, new_reason):
        if current_reason and new_reason:
            return f'{current_reason}；{new_reason}'
        return current_reason or new_reason

    def _sanitize_prefill(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(entities, dict):
            return {}
        sanitized = {}
        for key, value in entities.items():
            if key in {'password', 'token', 'secret', 'api_key', 'csrfmiddlewaretoken'}:
                continue
            if value is None or isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [item for item in value if isinstance(item, (str, int, float, bool))][:10]
        return sanitized

    def _get_candidate_data_types(self, intent_result: Dict[str, Any]) -> list[str]:
        entities = intent_result.get('entities') or {}
        raw_candidates = entities.get('candidate_data_types') or []
        candidates = []
        for value in raw_candidates:
            data_type = str(value or '').strip().lower()
            if data_type and data_type in self.BUSINESS_HANDOFF_CONFIG and data_type not in candidates:
                candidates.append(data_type)
        primary = intent_result.get('data_type')
        if primary and primary in self.BUSINESS_HANDOFF_CONFIG and primary not in candidates:
            candidates.insert(0, primary)
        return candidates

    def _decorate_response_with_recognition_meta(
            self,
            response: Dict[str, Any],
            intent_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
        payload = dict(response or {})
        meta_source = dict(intent_result or {})
        meta_source.update({
            key: payload.get(key, meta_source.get(key))
            for key in (
                'source',
                'ai_available',
                'ai_configured',
                'failure_reason',
                'model_provider',
                'model_name',
            )
        })
        recognition_meta = self._build_recognition_meta(meta_source)
        if recognition_meta:
            payload['recognition_meta'] = recognition_meta
        for key in (
            'source',
            'ai_available',
            'ai_configured',
            'failure_reason',
            'model_provider',
            'model_name',
        ):
            if key in meta_source and key not in payload:
                payload[key] = meta_source.get(key)
        return payload

    def _build_recognition_meta(self, intent_result: Dict[str, Any] | None) -> Dict[str, Any] | None:
        intent_result = intent_result or {}
        source = intent_result.get('source')
        ai_available = bool(intent_result.get('ai_available', source == 'ai'))
        ai_configured = bool(intent_result.get('ai_configured', source == 'ai'))
        failure_reason = intent_result.get('failure_reason')
        model_provider = intent_result.get('model_provider')
        model_name = intent_result.get('model_name')

        if not any([source, failure_reason, model_provider, model_name, ai_available, ai_configured]):
            return None

        if source == 'ai':
            source_label = 'AI识别'
            status_label = '模型可用'
        else:
            source_label = '规则降级'
            status_label = '模型不可用' if ai_configured else '未配置模型'

        return {
            'source': source or 'unknown',
            'source_label': source_label,
            'status_label': status_label,
            'ai_available': ai_available,
            'ai_configured': ai_configured,
            'failure_reason': failure_reason,
            'model_provider': model_provider,
            'model_name': model_name,
        }

    def _attach_mcp_context(
            self,
            response: Dict[str, Any],
            intent_result: Dict[str, Any] | None,
            query: str) -> Dict[str, Any]:
        from apps.ai.services.project_mcp_service import project_mcp_service

        payload = dict(response or {})
        payload['mcp_context'] = project_mcp_service.build_runtime_context(query, intent_result or payload)
        return payload

    def _build_business_options(
            self, task: Dict[str, Any], config: Dict[str, Any]) -> list:
        options = []
        if task.get('target_url'):
            option_text = f"打开{task.get('title')}"
            if task.get('action') in self.MUTATING_ACTIONS and task.get('target_url') == task.get('list_url'):
                option_text = f"打开{config.get('name')}列表"
                if task.get('action') in {'update', 'delete'}:
                    option_text = f"{option_text}并定位记录"
            options.append({
                'text': option_text,
                'intent': task.get('intent_type'),
                'action': 'open_business_page',
                'target_url': task.get('target_url'),
                'open_mode': task.get('open_mode'),
                'title': task.get('title'),
                'enabled': task.get('enabled', True),
                'disabled_reason': task.get('disabled_reason'),
            })
        if config.get('list_url') and config.get('list_url') != task.get('target_url'):
            options.append({
                'text': f"打开{config.get('name')}列表",
                'intent': 'DATA_QUERY',
                'action': 'open_business_page',
                'target_url': config.get('list_url'),
                'open_mode': task.get('open_mode'),
                'title': f"{config.get('name')}列表",
                'enabled': config.get('available', True),
                'disabled_reason': config.get('unavailable_reason'),
            })
        options.append({'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel', 'enabled': True})
        return options



enhanced_intent_service = EnhancedIntentService()
