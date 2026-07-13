"""
通用查询服务
负责处理用户查询，包括意图识别、查询生成、权限检查和结果处理
"""

import logging
import re
from datetime import timedelta
from typing import Dict, Any
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.utils import timezone

from apps.ai.services.permission_guard import build_csv_membership_q

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
            'finance_account_count': self.handle_finance_account_count,
            'finance_account_list': self.handle_finance_account_list,
            'finance_budget_count': self.handle_finance_budget_count,
            'finance_budget_list': self.handle_finance_budget_list,
            'finance_receivable_count': self.handle_finance_receivable_count,
            'finance_receivable_list': self.handle_finance_receivable_list,
            'finance_payable_count': self.handle_finance_payable_count,
            'finance_payable_list': self.handle_finance_payable_list,
            'finance_bank_transaction_count': self.handle_finance_bank_transaction_count,
            'finance_bank_transaction_list': self.handle_finance_bank_transaction_list,
            'ai_model_config_count': self.handle_ai_model_config_count,
            'ai_model_config_list': self.handle_ai_model_config_list,
            'ai_knowledge_base_count': self.handle_ai_knowledge_base_count,
            'ai_knowledge_base_list': self.handle_ai_knowledge_base_list,
            'ai_task_count': self.handle_ai_task_count,
            'ai_task_list': self.handle_ai_task_list,
            'ai_workflow_count': self.handle_ai_workflow_count,
            'ai_workflow_list': self.handle_ai_workflow_list,
            'supply_chain_forecast_count': self.handle_supply_chain_forecast_count,
            'supply_chain_forecast_list': self.handle_supply_chain_forecast_list,
            'supply_chain_outsource_count': self.handle_supply_chain_outsource_count,
            'supply_chain_outsource_list': self.handle_supply_chain_outsource_list,
            'supply_chain_pr_review_count': self.handle_supply_chain_pr_review_count,
            'supply_chain_pr_review_list': self.handle_supply_chain_pr_review_list,
            'supply_chain_price_review_count': self.handle_supply_chain_price_review_count,
            'supply_chain_price_review_list': self.handle_supply_chain_price_review_list,
            'supply_chain_sample_count': self.handle_supply_chain_sample_count,
            'supply_chain_sample_list': self.handle_supply_chain_sample_list,
            'production_plan_count': self.handle_production_plan_count,
            'production_plan_list': self.handle_production_plan_list,
            'production_task_count': self.handle_production_task_count,
            'production_task_list': self.handle_production_task_list,
            'production_equipment_count': self.handle_production_equipment_count,
            'production_equipment_list': self.handle_production_equipment_list,
            'production_procedure_count': self.handle_production_procedure_count,
            'production_procedure_list': self.handle_production_procedure_list,
            'reward_punishment_count': self.handle_reward_punishment_count,
            'reward_punishment_list': self.handle_reward_punishment_list,
            'employee_care_count': self.handle_employee_care_count,
            'employee_care_list': self.handle_employee_care_list,
            'procedureset_count': self.handle_procedureset_count,
            'procedureset_list': self.handle_procedureset_list,
            'bom_count': self.handle_bom_count,
            'bom_list': self.handle_bom_list,
            'process_count': self.handle_process_count,
            'process_list': self.handle_process_list,
            'quality_check_count': self.handle_quality_check_count,
            'quality_check_list': self.handle_quality_check_list,
            'datacollection_count': self.handle_datacollection_count,
            'datacollection_list': self.handle_datacollection_list,
            'supplier_count': self.handle_supplier_count,
            'supplier_list': self.handle_supplier_list,
            'product_count': self.handle_product_count,
            'product_list': self.handle_product_list,
            'inventory_count': self.handle_inventory_count,
            'inventory_list': self.handle_inventory_list,
            'warehouse_count': self.handle_warehouse_count,
            'warehouse_list': self.handle_warehouse_list,
            'stockin_count': self.handle_stockin_count,
            'stockin_list': self.handle_stockin_list,
            'stockout_count': self.handle_stockout_count,
            'stockout_list': self.handle_stockout_list,
            'alert_count': self.handle_alert_count,
            'alert_list': self.handle_alert_list,
            'followup_count': self.handle_followup_count,
            'followup_list': self.handle_followup_list,
            'approval_count': self.handle_approval_count,
            'approval_list': self.handle_approval_list,
            'approval_type_count': self.handle_approval_type_count,
            'approval_type_list': self.handle_approval_type_list,
            'approval_step_count': self.handle_approval_step_count,
            'approval_step_list': self.handle_approval_step_list,
            'approval_record_count': self.handle_approval_record_count,
            'approval_record_list': self.handle_approval_record_list,
            'approval_flow_edge_count': self.handle_approval_flow_edge_count,
            'approval_flow_edge_list': self.handle_approval_flow_edge_list,
            'approval_flow_count': self.handle_approval_flow_count,
            'approval_flow_list': self.handle_approval_flow_list,
            'approval_task_count': self.handle_approval_task_count,
            'approval_task_list': self.handle_approval_task_list,
            'workhour_count': self.handle_workhour_count,
            'workhour_list': self.handle_workhour_list,
            'task_count': self.handle_task_count,
            'task_list': self.handle_task_list,
            'message_count': self.handle_message_count,
            'message_list': self.handle_message_list,
            'notice_count': self.handle_notice_count,
            'notice_list': self.handle_notice_list,
            'contact_count': self.handle_contact_count,
            'contact_list': self.handle_contact_list,
            'project_document_count': self.handle_project_document_count,
            'project_document_list': self.handle_project_document_list,
            'project_stage_count': self.handle_project_stage_count,
            'project_stage_list': self.handle_project_stage_list,
            'project_category_count': self.handle_project_category_count,
            'project_category_list': self.handle_project_category_list,
            'work_type_count': self.handle_work_type_count,
            'work_type_list': self.handle_work_type_list,
            'document_count': self.handle_document_count,
            'document_list': self.handle_document_list,
            'document_category_count': self.handle_document_category_count,
            'document_category_list': self.handle_document_category_list,
            'asset_count': self.handle_asset_count,
            'asset_list': self.handle_asset_list,
            'asset_category_count': self.handle_asset_category_count,
            'asset_category_list': self.handle_asset_category_list,
            'asset_brand_count': self.handle_asset_brand_count,
            'asset_brand_list': self.handle_asset_brand_list,
            'asset_repair_count': self.handle_asset_repair_count,
            'asset_repair_list': self.handle_asset_repair_list,
            'vehicle_count': self.handle_vehicle_count,
            'vehicle_list': self.handle_vehicle_list,
            'vehicle_maintenance_count': self.handle_vehicle_maintenance_count,
            'vehicle_maintenance_list': self.handle_vehicle_maintenance_list,
            'vehicle_fee_count': self.handle_vehicle_fee_count,
            'vehicle_fee_list': self.handle_vehicle_fee_list,
            'vehicle_oil_count': self.handle_vehicle_oil_count,
            'vehicle_oil_list': self.handle_vehicle_oil_list,
            'seal_count': self.handle_seal_count,
            'seal_list': self.handle_seal_list,
            'seal_application_count': self.handle_seal_application_count,
            'seal_application_list': self.handle_seal_application_list,
            'payment_count': self.handle_payment_count,
            'payment_list': self.handle_payment_list,
            'meeting_room_count': self.handle_meeting_room_count,
            'meeting_room_list': self.handle_meeting_room_list,
            'meeting_reservation_count': self.handle_meeting_reservation_count,
            'meeting_reservation_list': self.handle_meeting_reservation_list,
            'meeting_minutes_count': self.handle_meeting_minutes_count,
            'meeting_minutes_list': self.handle_meeting_minutes_list,
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
            'enterprise_count': self.handle_enterprise_count,
            'enterprise_list': self.handle_enterprise_list,
            'position_count': self.handle_position_count,
            'position_list': self.handle_position_list,
            'work_record_count': self.handle_work_record_count,
            'work_record_list': self.handle_work_record_list,
            'work_report_count': self.handle_work_report_count,
            'work_report_list': self.handle_work_report_list,
            'personal_task_count': self.handle_personal_task_count,
            'personal_task_list': self.handle_personal_task_list,
            'personal_note_count': self.handle_personal_note_count,
            'personal_note_list': self.handle_personal_note_list,
            'personal_contact_count': self.handle_personal_contact_count,
            'personal_contact_list': self.handle_personal_contact_list,
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
            'finance_expense': 'finance.view_expense',
            'finance_invoice': 'finance.view_invoice',
            'finance_income': 'finance.view_payment_receive',
            'finance_order_record': 'finance.view_orderfinancerecord',
            'finance_account': 'finance.view_financeaccount',
            'finance_budget': 'finance.view_financebudget',
            'finance_receivable': 'finance.view_accountsreceivable',
            'finance_payable': 'finance.view_accountspayable',
            'finance_bank_transaction': 'finance.view_banktransaction',
            'ai_model_config': 'user.view_model_config',
            'ai_knowledge_base': 'user.view_knowledge_base',
            'ai_task': 'user.view_ai_task',
            'ai_workflow': 'user.view_ai_workflow',
            'supply_chain_forecast': 'user.view_supply_chain_forecast',
            'supply_chain_outsource': 'user.view_supply_chain_outsource',
            'supply_chain_pr_review': 'user.view_supply_chain_pr_review',
            'supply_chain_price_review': 'user.view_supply_chain_price_review',
            'supply_chain_sample': 'user.view_supply_chain_sample',
            'production': 'production.view_productionplan',
            'production_plan': 'production.view_productionplan',
            'production_task': 'production.view_productiontask',
            'production_equipment': 'production.view_equipment',
            'production_procedure': 'production.view_productionprocedure',
            'reward_punishment': 'user.view_reward_punishment',
            'employee_care': 'user.view_employee_care',
            'procedureset': 'user.view_procedureset',
            'bom': 'user.view_bom',
            'process': 'user.view_process',
            'quality_check': 'user.view_quality_check',
            'datacollection': 'user.view_datacollection',
            'supplier': 'contract.view_supplier',
            'product': 'contract.view_product',
            'inventory': 'inventory.view_inventory',
            'warehouse': 'inventory.view_warehouse',
            'stockin': 'inventory.view_stockin',
            'stockout': 'inventory.view_stockout',
            'alert': 'inventory.view_inventoryalert',
            'followup': 'customer.view_followrecord',
            'disk': 'disk.view_disk_file',
            'disk_folder': 'disk.view_disk_folder',
            'disk_share': 'disk.view_share',
            'approval': 'approval.view_approval',
            'approval_type': 'approval.view_approvaltype',
            'approval_step': 'approval.view_approvalstep',
            'approval_record': 'approval.view_approvalrecord',
            'approval_flow_edge': 'approval.view_approvalflowedge',
            'approval_flow': 'approval.view_approvalflow',
            'approval_task': 'approval.view_approvaltask',
            'task': 'task.view_task',
            'workhour': 'task.view_workhour',
            'message': 'message.view_message',
            'notice': 'user.view_notice',
            'contact': 'customer.view_customer',
            'project_document': 'project.view_project_document',
            'project_stage': 'project.view_project_stage',
            'project_category': 'project.view_project_category',
            'work_type': 'project.view_work_type',
            'document': 'system.view_document',
            'document_category': 'user.view_document_category',
            'asset': 'user.view_asset',
            'asset_category': 'user.view_asset',
            'asset_brand': 'user.view_asset',
            'asset_repair': 'user.view_asset_repair',
            'vehicle': 'user.view_vehicle_info',
            'vehicle_maintenance': 'user.view_vehicle_maintenance',
            'vehicle_fee': 'user.view_vehicle_fee',
            'vehicle_oil': 'user.view_vehicle_oil',
            'seal': 'user.view_seal_management',
            'seal_application': 'user.view_seal_application',
            'payment': 'finance.view_payment',
            'meeting_room': 'user.view_meeting_room',
            'meeting_reservation': '__authenticated__',
            'meeting_minutes': 'user.view_meeting_minutes',
            'meeting': 'oa.view_meetingrecord',
            'schedule': '__authenticated__',
            'enterprise': '__authenticated__',
            'position': 'position.view_position',
            'work_record': '__authenticated__',
            'work_report': '__authenticated__',
            'personal_task': '__authenticated__',
            'personal_note': '__authenticated__',
            'personal_contact': '__authenticated__',
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
            'finance_account_count': 'finance.view_financeaccount',
            'finance_account_list': 'finance.view_financeaccount',
            'finance_budget_count': 'finance.view_financebudget',
            'finance_budget_list': 'finance.view_financebudget',
            'finance_receivable_count': 'finance.view_accountsreceivable',
            'finance_receivable_list': 'finance.view_accountsreceivable',
            'finance_payable_count': 'finance.view_accountspayable',
            'finance_payable_list': 'finance.view_accountspayable',
            'finance_bank_transaction_count': 'finance.view_banktransaction',
            'finance_bank_transaction_list': 'finance.view_banktransaction',
            'ai_model_config_count': 'user.view_model_config',
            'ai_model_config_list': 'user.view_model_config',
            'ai_knowledge_base_count': 'user.view_knowledge_base',
            'ai_knowledge_base_list': 'user.view_knowledge_base',
            'ai_task_count': 'user.view_ai_task',
            'ai_task_list': 'user.view_ai_task',
            'ai_workflow_count': 'user.view_ai_workflow',
            'ai_workflow_list': 'user.view_ai_workflow',
            'supply_chain_forecast_count': 'user.view_supply_chain_forecast',
            'supply_chain_forecast_list': 'user.view_supply_chain_forecast',
            'supply_chain_outsource_count': 'user.view_supply_chain_outsource',
            'supply_chain_outsource_list': 'user.view_supply_chain_outsource',
            'supply_chain_pr_review_count': 'user.view_supply_chain_pr_review',
            'supply_chain_pr_review_list': 'user.view_supply_chain_pr_review',
            'supply_chain_price_review_count': 'user.view_supply_chain_price_review',
            'supply_chain_price_review_list': 'user.view_supply_chain_price_review',
            'supply_chain_sample_count': 'user.view_supply_chain_sample',
            'supply_chain_sample_list': 'user.view_supply_chain_sample',
            'production_plan_count': 'production.view_productionplan',
            'production_plan_list': 'production.view_productionplan',
            'production_task_count': 'production.view_productiontask',
            'production_task_list': 'production.view_productiontask',
            'production_equipment_count': 'production.view_equipment',
            'production_equipment_list': 'production.view_equipment',
            'production_procedure_count': 'production.view_productionprocedure',
            'production_procedure_list': 'production.view_productionprocedure',
            'reward_punishment_count': 'user.view_reward_punishment',
            'reward_punishment_list': 'user.view_reward_punishment',
            'employee_care_count': 'user.view_employee_care',
            'employee_care_list': 'user.view_employee_care',
            'procedureset_count': 'user.view_procedureset',
            'procedureset_list': 'user.view_procedureset',
            'bom_count': 'user.view_bom',
            'bom_list': 'user.view_bom',
            'process_count': 'user.view_process',
            'process_list': 'user.view_process',
            'quality_check_count': 'user.view_quality_check',
            'quality_check_list': 'user.view_quality_check',
            'datacollection_count': 'user.view_datacollection',
            'datacollection_list': 'user.view_datacollection',
            'supplier_count': 'contract.view_supplier',
            'supplier_list': 'contract.view_supplier',
            'product_count': 'contract.view_product',
            'product_list': 'contract.view_product',
            'inventory_count': 'inventory.view_inventory',
            'inventory_list': 'inventory.view_inventory',
            'warehouse_count': 'inventory.view_warehouse',
            'warehouse_list': 'inventory.view_warehouse',
            'stockin_count': 'inventory.view_stockin',
            'stockin_list': 'inventory.view_stockin',
            'stockout_count': 'inventory.view_stockout',
            'stockout_list': 'inventory.view_stockout',
            'alert_count': 'inventory.view_inventoryalert',
            'alert_list': 'inventory.view_inventoryalert',
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
            'approval_type_count': 'approval.view_approvaltype',
            'approval_type_list': 'approval.view_approvaltype',
            'approval_step_count': 'approval.view_approvalstep',
            'approval_step_list': 'approval.view_approvalstep',
            'approval_record_count': 'approval.view_approvalrecord',
            'approval_record_list': 'approval.view_approvalrecord',
            'approval_flow_edge_count': 'approval.view_approvalflowedge',
            'approval_flow_edge_list': 'approval.view_approvalflowedge',
            'approval_flow_count': 'approval.view_approvalflow',
            'approval_flow_list': 'approval.view_approvalflow',
            'approval_task_count': 'approval.view_approvaltask',
            'approval_task_list': 'approval.view_approvaltask',
            'workhour_count': 'task.view_workhour',
            'workhour_list': 'task.view_workhour',
            'task_count': 'task.view_task',
            'task_list': 'task.view_task',
            'message_count': 'message.view_message',
            'message_list': 'message.view_message',
            'notice_count': 'user.view_notice',
            'notice_list': 'user.view_notice',
            'contact_count': 'customer.view_customer',
            'contact_list': 'customer.view_customer',
            'project_document_count': 'project.view_project_document',
            'project_document_list': 'project.view_project_document',
            'project_stage_count': 'project.view_project_stage',
            'project_stage_list': 'project.view_project_stage',
            'project_category_count': 'project.view_project_category',
            'project_category_list': 'project.view_project_category',
            'work_type_count': 'project.view_work_type',
            'work_type_list': 'project.view_work_type',
            'document_count': 'system.view_document',
            'document_list': 'system.view_document',
            'document_category_count': 'user.view_document_category',
            'document_category_list': 'user.view_document_category',
            'asset_count': 'user.view_asset',
            'asset_list': 'user.view_asset',
            'asset_category_count': 'user.view_asset',
            'asset_category_list': 'user.view_asset',
            'asset_brand_count': 'user.view_asset',
            'asset_brand_list': 'user.view_asset',
            'asset_repair_count': 'user.view_asset_repair',
            'asset_repair_list': 'user.view_asset_repair',
            'vehicle_count': 'user.view_vehicle_info',
            'vehicle_list': 'user.view_vehicle_info',
            'vehicle_maintenance_count': 'user.view_vehicle_maintenance',
            'vehicle_maintenance_list': 'user.view_vehicle_maintenance',
            'vehicle_fee_count': 'user.view_vehicle_fee',
            'vehicle_fee_list': 'user.view_vehicle_fee',
            'vehicle_oil_count': 'user.view_vehicle_oil',
            'vehicle_oil_list': 'user.view_vehicle_oil',
            'seal_count': 'user.view_seal_management',
            'seal_list': 'user.view_seal_management',
            'seal_application_count': 'user.view_seal_application',
            'seal_application_list': 'user.view_seal_application',
            'payment_count': 'finance.view_payment',
            'payment_list': 'finance.view_payment',
            'meeting_room_count': 'user.view_meeting_room',
            'meeting_room_list': 'user.view_meeting_room',
            'meeting_reservation_count': '__authenticated__',
            'meeting_reservation_list': '__authenticated__',
            'meeting_minutes_count': 'user.view_meeting_minutes',
            'meeting_minutes_list': 'user.view_meeting_minutes',
            'meeting_count': 'oa.view_meetingrecord',
            'meeting_list': 'oa.view_meetingrecord',
            'schedule_count': '__authenticated__',
            'schedule_list': '__authenticated__',
            'enterprise_count': '__authenticated__',
            'enterprise_list': '__authenticated__',
            'position_count': 'position.view_position',
            'position_list': 'position.view_position',
            'work_record_count': '__authenticated__',
            'work_record_list': '__authenticated__',
            'work_report_count': '__authenticated__',
            'work_report_list': '__authenticated__',
            'personal_task_count': '__authenticated__',
            'personal_task_list': '__authenticated__',
            'personal_note_count': '__authenticated__',
            'personal_note_list': '__authenticated__',
            'personal_contact_count': '__authenticated__',
            'personal_contact_list': '__authenticated__',
        }

    def process_query(
            self,
            user: User,
            query: str,
            intent_result: Dict[str, Any] | None = None,
            context: Dict[str, Any] | None = None) -> Dict[str, Any]:
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
            specific_intent, specific_entities = self.resolve_specific_intent(query, intent_result, context=context)
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
            intent_result: Dict[str, Any] | None = None,
            context: Dict[str, Any] | None = None) -> tuple[str, Dict[str, Any]]:
        intent_result = intent_result or {}
        context = context or {}
        entities = dict(intent_result.get('entities') or {})
        data_type = intent_result.get('data_type')
        action = intent_result.get('action') or 'query'

        if intent_result.get('time_range'):
            entities['time_range'] = intent_result.get('time_range')
        if intent_result.get('status'):
            entities['status'] = intent_result.get('status')
        if intent_result.get('customer_name'):
            entities['customer_name'] = intent_result.get('customer_name')

        data_type, action, entities = self._apply_query_context(
            query, data_type, action, entities, context)

        if action in {'list', 'detail', 'summary', 'query', 'count'}:
            action = self._infer_query_action(query, action)
        else:
            action = 'list'

        specific_intent = self._map_data_type_to_specific_intent(data_type, action, entities)
        if specific_intent:
            logger.info(
                f"AI意图映射: intent={intent_result.get('intent')} data_type={data_type} action={action} specific_intent={specific_intent}")
            return specific_intent, entities

        if data_type or intent_result.get('source') == 'ai':
            logger.warning(
                f"AI意图未映射到可执行查询处理器: data_type={data_type}, action={action}")
            return 'ai_chat', entities

        return self.recognize_intent(query)

    def _apply_query_context(
            self,
            query: str,
            data_type: str | None,
            action: str,
            entities: Dict[str, Any],
            context: Dict[str, Any]) -> tuple[str | None, str, Dict[str, Any]]:
        query_lower = (query or '').lower()
        merged_entities = dict(entities or {})
        previous = context.get('previous_query') or {}
        previous_intent = previous.get('specific_intent') or previous.get('intent')
        previous_entities = dict(previous.get('entities') or {})
        if previous.get('status') and 'status' not in previous_entities:
            previous_entities['status'] = previous.get('status')
        if previous.get('time_range') and 'time_range' not in previous_entities:
            previous_entities['time_range'] = previous.get('time_range')

        previous_specific = self._get_data_type_from_specific_intent(previous_intent)
        if not data_type and previous_specific:
            follow_up_keywords = ['本月', '这个月', '上月', '上个月', '今天', '昨天', '昨日', '数量', '多少', '几个', '有几个', '明细', '列表', '看下', '看一下', '继续', '还有', '最近', '前']
            numeric_follow_up = re.fullmatch(r'前\s*[0-9一二三四五六七八九十]+\s*个', query_lower)
            if any(keyword in query_lower for keyword in follow_up_keywords) or numeric_follow_up:
                data_type = previous_specific
                merged_entities = {**previous_entities, **merged_entities}

        # 显式金额类问法优先路由到订单金额查询，避免误落到报销列表
        if any(keyword in query_lower for keyword in ['成交订单', '订单成交', '订单金额', '订单总额', '成交金额', '成交额']):
            data_type = 'order'
            if any(keyword in query_lower for keyword in ['总额', '金额', '成交额', '合计', '汇总']):
                action = 'summary'
            elif '多少' in query_lower:
                action = 'count'

        if any(keyword in query_lower for keyword in ['合同金额', '合同总额', '合同金额总和', '合同总金额', '签约金额', '签约总额']):
            data_type = 'contract'
            action = 'summary'

        # 承接短追问中的时间范围，如“而且是问的本月的”
        if (
            previous_intent in {'order_total', 'order_total_this_month', 'order_total_last_month'} and
            any(keyword in query_lower for keyword in ['本月', '这个月', '上月', '上个月', '今天', '昨日', '昨天']) and
            not any(keyword in query_lower for keyword in ['客户', '合同', '项目', '报销', '发票', '回款', '审批', '网盘'])
        ):
            data_type = 'order'
            action = 'summary'

        if previous_intent in {'approval_task_list', 'approval_task_count'} and any(keyword in query_lower for keyword in ['数量', '多少', '几个', '有几个', '总数']):
            data_type = 'approval_task'
            action = 'count'
            merged_entities = {**previous_entities, **merged_entities}

        if previous_intent in {'project_list_in_progress', 'project_count_in_progress'} and any(keyword in query_lower for keyword in ['数量', '多少', '几个', '有几个']):
            data_type = 'project'
            action = 'count'
            merged_entities = {**previous_entities, **merged_entities}
            merged_entities.setdefault('status', '进行中')

        if previous_intent in {'project_list', 'project_count'} and any(keyword in query_lower for keyword in ['进行中', '在进行']):
            data_type = 'project'
            merged_entities = {**previous_entities, **merged_entities}
            merged_entities['status'] = '进行中'
            action = 'count' if any(keyword in query_lower for keyword in ['数量', '多少', '几个', '有几个']) else 'list'

        if previous_intent in {'disk_share_list', 'disk_share_count'} and any(keyword in query_lower for keyword in ['数量', '多少', '几个', '有几个']):
            data_type = 'disk_share'
            action = 'count'
            merged_entities = {**previous_entities, **merged_entities}

        if any(keyword in query_lower for keyword in ['本月', '这个月']):
            merged_entities['time_range'] = 'this_month'
        elif any(keyword in query_lower for keyword in ['上月', '上个月']):
            merged_entities['time_range'] = 'last_month'
        elif '今天' in query_lower:
            merged_entities['time_range'] = 'today'
        elif any(keyword in query_lower for keyword in ['昨天', '昨日']):
            merged_entities['time_range'] = 'yesterday'

        return data_type, action, merged_entities

    def _infer_query_action(self, query: str, action: str) -> str:
        query_lower = (query or '').lower()
        if action == 'summary':
            return 'summary'
        if action == 'count':
            return 'count'
        if any(keyword in query_lower for keyword in ['总额', '金额', '成交额', '合计', '汇总']):
            return 'summary'
        if any(keyword in query_lower for keyword in ['多少', '数量', '总数', '统计', '合计']):
            return 'count'
        if any(keyword in query_lower for keyword in ['看', '看看', '看下', '看一下', '查', '查下', '查一下', '列出', '展示', '明细', '记录', '有哪些']):
            return 'list'
        return 'list'

    def _map_data_type_to_specific_intent(self, data_type: str | None, action: str, entities: Dict[str, Any] | None = None) -> str | None:
        if not data_type:
            return None
        entities = entities or {}
        action_type = 'count' if action == 'count' else 'summary' if action == 'summary' else 'list'
        mapping = {
            'customer': {'count': 'customer_count', 'list': 'customer_list'},
            'order': {'count': 'order_count', 'list': 'order_list', 'summary': 'order_total'},
            'contract': {'count': 'contract_count', 'list': 'contract_list'},
            'project': {'count': 'project_count', 'list': 'project_list'},
            'invoice': {'count': 'invoice_count', 'list': 'invoice_list'},
            'employee': {'count': 'employee_count', 'list': 'employee_list'},
            'department': {'count': 'department_count', 'list': 'department_list'},
            'finance': {'count': 'finance_expense_count', 'list': 'finance_expense_list'},
            'finance_expense': {'count': 'finance_expense_count', 'list': 'finance_expense_list'},
            'finance_invoice': {'count': 'finance_invoice_count', 'list': 'finance_invoice_list'},
            'finance_income': {'count': 'finance_income_count', 'list': 'finance_income_list'},
            'finance_order_record': {'count': 'finance_order_record_count', 'list': 'finance_order_record_list'},
            'finance_account': {'count': 'finance_account_count', 'list': 'finance_account_list'},
            'finance_budget': {'count': 'finance_budget_count', 'list': 'finance_budget_list'},
            'finance_receivable': {'count': 'finance_receivable_count', 'list': 'finance_receivable_list'},
            'finance_payable': {'count': 'finance_payable_count', 'list': 'finance_payable_list'},
            'finance_bank_transaction': {'count': 'finance_bank_transaction_count', 'list': 'finance_bank_transaction_list'},
            'ai_model_config': {'count': 'ai_model_config_count', 'list': 'ai_model_config_list'},
            'ai_knowledge_base': {'count': 'ai_knowledge_base_count', 'list': 'ai_knowledge_base_list'},
            'ai_task': {'count': 'ai_task_count', 'list': 'ai_task_list'},
            'ai_workflow': {'count': 'ai_workflow_count', 'list': 'ai_workflow_list'},
            'supply_chain_forecast': {'count': 'supply_chain_forecast_count', 'list': 'supply_chain_forecast_list'},
            'supply_chain_outsource': {'count': 'supply_chain_outsource_count', 'list': 'supply_chain_outsource_list'},
            'supply_chain_pr_review': {'count': 'supply_chain_pr_review_count', 'list': 'supply_chain_pr_review_list'},
            'supply_chain_price_review': {'count': 'supply_chain_price_review_count', 'list': 'supply_chain_price_review_list'},
            'supply_chain_sample': {'count': 'supply_chain_sample_count', 'list': 'supply_chain_sample_list'},
            'expense': {'count': 'finance_expense_count', 'list': 'finance_expense_list'},
            'income': {'count': 'finance_income_count', 'list': 'finance_income_list'},
            'production': {'count': 'production_plan_count', 'list': 'production_plan_list'},
            'production_plan': {'count': 'production_plan_count', 'list': 'production_plan_list'},
            'production_task': {'count': 'production_task_count', 'list': 'production_task_list'},
            'production_equipment': {'count': 'production_equipment_count', 'list': 'production_equipment_list'},
            'production_procedure': {'count': 'production_procedure_count', 'list': 'production_procedure_list'},
            'reward_punishment': {'count': 'reward_punishment_count', 'list': 'reward_punishment_list'},
            'employee_care': {'count': 'employee_care_count', 'list': 'employee_care_list'},
            'procedureset': {'count': 'procedureset_count', 'list': 'procedureset_list'},
            'bom': {'count': 'bom_count', 'list': 'bom_list'},
            'process': {'count': 'process_count', 'list': 'process_list'},
            'quality_check': {'count': 'quality_check_count', 'list': 'quality_check_list'},
            'datacollection': {'count': 'datacollection_count', 'list': 'datacollection_list'},
            'supplier': {'count': 'supplier_count', 'list': 'supplier_list'},
            'product': {'count': 'product_count', 'list': 'product_list'},
            'inventory': {'count': 'inventory_count', 'list': 'inventory_list'},
            'warehouse': {'count': 'warehouse_count', 'list': 'warehouse_list'},
            'stockin': {'count': 'stockin_count', 'list': 'stockin_list'},
            'stockout': {'count': 'stockout_count', 'list': 'stockout_list'},
            'alert': {'count': 'alert_count', 'list': 'alert_list'},
            'followup': {'count': 'followup_count', 'list': 'followup_list'},
            'disk': {'count': 'disk_count', 'list': 'disk_list'},
            'disk_folder': {'count': 'disk_folder_count', 'list': 'disk_folder_list'},
            'disk_share': {'count': 'disk_share_count', 'list': 'disk_share_list'},
            'approval': {'count': 'approval_count', 'list': 'approval_list'},
            'approval_type': {'count': 'approval_type_count', 'list': 'approval_type_list'},
            'approval_step': {'count': 'approval_step_count', 'list': 'approval_step_list'},
            'approval_record': {'count': 'approval_record_count', 'list': 'approval_record_list'},
            'approval_flow_edge': {'count': 'approval_flow_edge_count', 'list': 'approval_flow_edge_list'},
            'approval_flow': {'count': 'approval_flow_count', 'list': 'approval_flow_list'},
            'approval_task': {'count': 'approval_task_count', 'list': 'approval_task_list'},
            'task': {'count': 'task_count', 'list': 'task_list'},
            'workhour': {'count': 'workhour_count', 'list': 'workhour_list'},
            'message': {'count': 'message_count', 'list': 'message_list'},
            'notice': {'count': 'notice_count', 'list': 'notice_list'},
            'contact': {'count': 'contact_count', 'list': 'contact_list'},
            'project_document': {'count': 'project_document_count', 'list': 'project_document_list'},
            'project_stage': {'count': 'project_stage_count', 'list': 'project_stage_list'},
            'project_category': {'count': 'project_category_count', 'list': 'project_category_list'},
            'work_type': {'count': 'work_type_count', 'list': 'work_type_list'},
            'document': {'count': 'document_count', 'list': 'document_list'},
            'document_category': {'count': 'document_category_count', 'list': 'document_category_list'},
            'asset': {'count': 'asset_count', 'list': 'asset_list'},
            'asset_category': {'count': 'asset_category_count', 'list': 'asset_category_list'},
            'asset_brand': {'count': 'asset_brand_count', 'list': 'asset_brand_list'},
            'asset_repair': {'count': 'asset_repair_count', 'list': 'asset_repair_list'},
            'vehicle': {'count': 'vehicle_count', 'list': 'vehicle_list'},
            'vehicle_maintenance': {'count': 'vehicle_maintenance_count', 'list': 'vehicle_maintenance_list'},
            'vehicle_fee': {'count': 'vehicle_fee_count', 'list': 'vehicle_fee_list'},
            'vehicle_oil': {'count': 'vehicle_oil_count', 'list': 'vehicle_oil_list'},
            'seal': {'count': 'seal_count', 'list': 'seal_list'},
            'seal_application': {'count': 'seal_application_count', 'list': 'seal_application_list'},
            'payment': {'count': 'payment_count', 'list': 'payment_list'},
            'meeting_room': {'count': 'meeting_room_count', 'list': 'meeting_room_list'},
            'meeting_reservation': {'count': 'meeting_reservation_count', 'list': 'meeting_reservation_list'},
            'meeting_minutes': {'count': 'meeting_minutes_count', 'list': 'meeting_minutes_list'},
            'meeting': {'count': 'meeting_count', 'list': 'meeting_list'},
            'schedule': {'count': 'schedule_count', 'list': 'schedule_list'},
            'enterprise': {'count': 'enterprise_count', 'list': 'enterprise_list'},
            'position': {'count': 'position_count', 'list': 'position_list'},
            'work_record': {'count': 'work_record_count', 'list': 'work_record_list'},
            'work_report': {'count': 'work_report_count', 'list': 'work_report_list'},
            'personal_task': {'count': 'personal_task_count', 'list': 'personal_task_list'},
            'personal_note': {'count': 'personal_note_count', 'list': 'personal_note_list'},
            'personal_contact': {'count': 'personal_contact_count', 'list': 'personal_contact_list'},
        }
        specific_intent = mapping.get(data_type, {}).get(action_type)
        if data_type == 'contract' and action_type == 'summary':
            return 'contract_total'
        if data_type == 'order' and action_type == 'summary':
            if entities.get('time_range') == 'this_month':
                return 'order_total_this_month'
            if entities.get('time_range') == 'last_month':
                return 'order_total_last_month'
        if data_type == 'project':
            status = entities.get('status')
            if status == '进行中':
                return 'project_count_in_progress' if action_type == 'count' else 'project_list_in_progress'
            if status == '已完成':
                return 'project_count_completed' if action_type == 'count' else 'project_list_completed'
            if status == '已暂停' and action_type == 'count':
                return 'project_count_paused'
        return specific_intent

    def _get_data_type_from_specific_intent(self, specific_intent: str | None) -> str | None:
        if not specific_intent:
            return None
        prefixes = [
            'customer',
            'order',
            'contract',
            'project_document',
            'project_stage',
            'project_category',
            'work_type',
            'project',
            'seal_application',
            'invoice',
            'asset_repair',
            'asset_category',
            'asset_brand',
            'asset',
            'vehicle_maintenance',
            'vehicle_fee',
            'vehicle_oil',
            'vehicle',
            'seal',
            'employee',
            'department',
            'finance_expense',
            'finance_invoice',
            'finance_income',
            'finance_order_record',
            'finance_bank_transaction',
            'finance_receivable',
            'finance_payable',
            'finance_account',
            'finance_budget',
            'ai_model_config',
            'ai_knowledge_base',
            'ai_workflow',
            'ai_task',
            'supply_chain_price_review',
            'supply_chain_pr_review',
            'supply_chain_forecast',
            'supply_chain_outsource',
            'supply_chain_sample',
            'production_plan',
            'production_task',
            'production_equipment',
            'production_procedure',
            'reward_punishment',
            'employee_care',
            'procedureset',
            'bom',
            'process',
            'quality_check',
            'datacollection',
            'supplier',
            'product',
            'inventory',
            'warehouse',
            'stockin',
            'stockout',
            'alert',
            'followup',
            'approval_type',
            'approval_step',
            'approval_record',
            'approval_flow_edge',
            'approval_flow',
            'approval_task',
            'approval',
            'task',
            'message',
            'notice',
            'contact',
            'document_category',
            'document',
            'payment',
            'meeting_reservation',
            'meeting_minutes',
            'meeting_room',
            'meeting',
            'schedule',
            'enterprise',
            'position',
            'work_record',
            'work_report',
            'personal_task',
            'personal_note',
            'personal_contact',
            'disk_folder',
            'disk_share',
            'disk',
        ]
        for prefix in prefixes:
            if specific_intent.startswith(prefix):
                return prefix
        return None

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
        owned_scope_keywords = ['我负责的', '我名下的', '我的']

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
        elif any(keyword in query_lower for keyword in ['我分享的文件链接', '我分享的链接', '我创建的分享', '我发起的分享']):
            entities['scope'] = 'created_by_me'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'disk_share_count'
            else:
                intent = 'disk_share_list'
        elif any(keyword in query_lower for keyword in ['共享给我的网盘文件', '共享给我的文件', '别人分享给我的文件', '分享给我的文件']):
            entities['scope'] = 'shared_to_me'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'disk_count'
            else:
                intent = 'disk_list'
        elif any(keyword in query_lower for keyword in ['网盘文件夹', '共享文件夹', '文件夹']):
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'disk_folder_count'
            else:
                intent = 'disk_folder_list'
        elif any(keyword in query_lower for keyword in ['项目资料', '项目附件', '项目文件', '项目文档']):
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'project_document_count'
            else:
                intent = 'project_document_list'
        elif any(keyword in query_lower for keyword in ['网盘', '共享文件', '共享资料', '文件', '资料', '附件']):
            if '收藏' in query_lower or '星标' in query_lower:
                entities['status'] = 'starred'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'disk_count'
            else:
                intent = 'disk_list'
        elif any(keyword in query_lower for keyword in ['已审批', '已处理审批', '我审批的', '我已审批的', '审批过的流程']):
            entities['status'] = 'completed'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'approval_task_count'
            else:
                intent = 'approval_task_list'
        elif any(keyword in query_lower for keyword in ['待审批', '待办审批', '审批任务', '待办流程']):
            entities['status'] = 'pending'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'approval_task_count'
            else:
                intent = 'approval_task_list'
        elif any(keyword in query_lower for keyword in ['流程连线', '审批连线', '节点连线', '流程路径']):
            self._extract_approval_detail_entities(query_lower, entities, 'approval_flow_edge')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'approval_flow_edge_count'
            else:
                intent = 'approval_flow_edge_list'
        elif any(keyword in query_lower for keyword in ['审批步骤', '流程步骤', '审批节点', '流程节点']):
            self._extract_approval_detail_entities(query_lower, entities, 'approval_step')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'approval_step_count'
            else:
                intent = 'approval_step_list'
        elif any(keyword in query_lower for keyword in ['审批类型', '流程类型']):
            self._extract_approval_detail_entities(query_lower, entities, 'approval_type')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'approval_type_count'
            else:
                intent = 'approval_type_list'
        elif any(keyword in query_lower for keyword in ['审批记录', '流程记录', '审批历史', '流转记录']):
            self._extract_approval_detail_entities(query_lower, entities, 'approval_record')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'approval_record_count'
            else:
                intent = 'approval_record_list'
        elif any(keyword in query_lower for keyword in ['审批流', '审批流程', '流程配置', '流程模板']):
            self._extract_approval_detail_entities(query_lower, entities, 'approval_flow')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'approval_flow_count'
            else:
                intent = 'approval_flow_list'
        elif '审批' in query_lower or '流程' in query_lower:
            if any(keyword in query_lower for keyword in ['我发起的', '我提交的', '我的审批', '我发起但未结束的', '我发起但是未结束的']):
                entities['scope'] = 'created_by_me'
            if any(keyword in query_lower for keyword in ['未结束', '进行中', '处理中', '还没结束']):
                entities['status'] = 'ongoing'
            elif '已通过' in query_lower:
                entities['status'] = 'approved'
            elif '已拒绝' in query_lower or '已驳回' in query_lower:
                entities['status'] = 'rejected'
            elif '已取消' in query_lower or '已撤回' in query_lower:
                entities['status'] = 'cancelled'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'approval_count'
            else:
                intent = 'approval_list'
        elif '消息' in query_lower or '站内信' in query_lower or '通知消息' in query_lower:
            if '未读' in query_lower:
                entities['status'] = 'unread'
            elif '已读' in query_lower:
                entities['status'] = 'read'
            elif '标星' in query_lower or '收藏' in query_lower:
                entities['status'] = 'starred'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'message_count'
            else:
                intent = 'message_list'
        elif any(keyword in query_lower for keyword in ['公告', '通知公告', '公司通知', '系统通知', '紧急通知']):
            self._extract_notice_entities(query_lower, entities)
            if '已发布' in query_lower:
                entities['status'] = 'published'
            elif '未发布' in query_lower or '草稿' in query_lower:
                entities['status'] = 'draft'
            elif '置顶' in query_lower:
                entities['status'] = 'top'
            if any(keyword in query_lower for keyword in ['最近', '近期']):
                entities['time_range'] = 'recent'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'notice_count'
            else:
                intent = 'notice_list'
        elif ('工作记录' in query_lower or '工作日志' in query_lower or '履职记录' in query_lower):
            self._extract_work_record_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'work_record_count'
            else:
                intent = 'work_record_list'
        elif any(keyword in query_lower for keyword in ['会议室预订', '会议室预约', '会议预订', '会议预约']):
            self._extract_meeting_reservation_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'meeting_reservation_count'
            else:
                intent = 'meeting_reservation_list'
        elif '会议室' in query_lower:
            self._extract_meeting_room_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'meeting_room_count'
            else:
                intent = 'meeting_room_list'
        elif '会议纪要' in query_lower:
            if any(keyword in query_lower for keyword in owned_scope_keywords):
                entities['scope'] = 'owned_by_me'
            if '今天' in query_lower:
                entities['time_range'] = 'today'
            elif any(keyword in query_lower for keyword in ['本周', '这周']):
                entities['time_range'] = 'this_week'
            elif any(keyword in query_lower for keyword in ['上周', '上一周']):
                entities['time_range'] = 'last_week'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'meeting_minutes_count'
            else:
                intent = 'meeting_minutes_list'
        elif '会议' in query_lower:
            if '今天' in query_lower:
                entities['time_range'] = 'today'
            elif any(keyword in query_lower for keyword in ['本周', '这周']):
                entities['time_range'] = 'this_week'
            elif any(keyword in query_lower for keyword in ['上周', '上一周']):
                entities['time_range'] = 'last_week'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'meeting_count'
            else:
                intent = 'meeting_list'
        elif any(keyword in query_lower for keyword in ['资产报修', '资产维修记录', '报修记录']):
            self._extract_asset_repair_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'asset_repair_count'
            else:
                intent = 'asset_repair_list'
        elif any(keyword in query_lower for keyword in ['车辆维修记录', '车辆保养记录', '维修保养记录']):
            self._extract_vehicle_maintenance_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'vehicle_maintenance_count'
            else:
                intent = 'vehicle_maintenance_list'
        elif any(keyword in query_lower for keyword in ['车辆费用', '车辆保险费', '车辆燃油费', '停车费', '过路费', '车辆罚款']):
            self._extract_vehicle_fee_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'vehicle_fee_count'
            else:
                intent = 'vehicle_fee_list'
        elif any(keyword in query_lower for keyword in ['车辆油耗', '加油记录', '油耗记录']):
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'vehicle_oil_count'
            else:
                intent = 'vehicle_oil_list'
        elif any(keyword in query_lower for keyword in ['固定资产', '资产台账', '资产管理']):
            self._extract_asset_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'asset_count'
            else:
                intent = 'asset_list'
        elif any(keyword in query_lower for keyword in ['车辆', '车牌', '用车']):
            self._extract_vehicle_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'vehicle_count'
            else:
                intent = 'vehicle_list'
        elif any(keyword in query_lower for keyword in ['用章申请', '盖章申请', '印章申请']):
            self._extract_seal_application_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'seal_application_count'
            else:
                intent = 'seal_application_list'
        elif any(keyword in query_lower for keyword in ['印章', '公章', '专用章', '法人章']):
            self._extract_seal_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'seal_count'
            else:
                intent = 'seal_list'
        elif (
                '日程' in query_lower or
                '排期' in query_lower or
                ('安排' in query_lower and not any(keyword in query_lower for keyword in ['会议', '审批', '流程', '通知公告']))
        ):
            if '今天' in query_lower:
                entities['time_range'] = 'today'
            elif any(keyword in query_lower for keyword in ['本周', '这周']):
                entities['time_range'] = 'this_week'
            if '外勤' in query_lower:
                entities['labor_type'] = 2
            elif '案头' in query_lower or '办公室' in query_lower:
                entities['labor_type'] = 1
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'schedule_count'
            else:
                intent = 'schedule_list'
        elif any(keyword in query_lower for keyword in ['奖罚', '奖惩', '奖励记录', '处罚记录']):
            self._extract_reward_punishment_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'reward_punishment_count'
            else:
                intent = 'reward_punishment_list'
        elif any(keyword in query_lower for keyword in ['员工关怀', '关怀记录', '生日关怀', '节日关怀']):
            self._extract_employee_care_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'employee_care_count'
            else:
                intent = 'employee_care_list'
        elif any(keyword in query_lower for keyword in ['工序集', '工序组合', '工序套']):
            self._extract_production_detail_entities(query_lower, entities, 'procedureset')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'procedureset_count'
            else:
                intent = 'procedureset_list'
        elif any(keyword in query_lower for keyword in ['bom', '物料清单', 'bom清单']):
            self._extract_production_detail_entities(query_lower, entities, 'bom')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'bom_count'
            else:
                intent = 'bom_list'
        elif any(keyword in query_lower for keyword in ['工艺路线', '生产路线', '路线模板']):
            self._extract_production_detail_entities(query_lower, entities, 'process')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'process_count'
            else:
                intent = 'process_list'
        elif any(keyword in query_lower for keyword in ['质量检查', '质检记录', '质量管理']):
            self._extract_production_detail_entities(query_lower, entities, 'quality_check')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'quality_check_count'
            else:
                intent = 'quality_check_list'
        elif any(keyword in query_lower for keyword in ['数据采集', '采集记录', '采集数据']):
            self._extract_production_detail_entities(query_lower, entities, 'datacollection')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'datacollection_count'
            else:
                intent = 'datacollection_list'
        elif any(keyword in query_lower for keyword in ['ai模型配置', '模型配置', '可用ai模型', '可用模型']):
            self._extract_ai_center_entities(query_lower, entities, 'ai_model_config')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'ai_model_config_count'
            else:
                intent = 'ai_model_config_list'
        elif any(keyword in query_lower for keyword in ['知识库', 'ai知识库']):
            self._extract_ai_center_entities(query_lower, entities, 'ai_knowledge_base')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'ai_knowledge_base_count'
            else:
                intent = 'ai_knowledge_base_list'
        elif any(keyword in query_lower for keyword in ['ai任务', '智能任务']):
            self._extract_ai_center_entities(query_lower, entities, 'ai_task')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'ai_task_count'
            else:
                intent = 'ai_task_list'
        elif any(keyword in query_lower for keyword in ['ai工作流', '智能工作流', '工作流']):
            self._extract_ai_center_entities(query_lower, entities, 'ai_workflow')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'ai_workflow_count'
            else:
                intent = 'ai_workflow_list'
        elif any(keyword in query_lower for keyword in ['需求预测', '预测计划', '备料评审']):
            self._extract_supply_chain_entities(query_lower, entities, 'forecast')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'supply_chain_forecast_count'
            else:
                intent = 'supply_chain_forecast_list'
        elif any(keyword in query_lower for keyword in ['委外发料', '委外发料单', '齐套']):
            self._extract_supply_chain_entities(query_lower, entities, 'outsource')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'supply_chain_outsource_count'
            else:
                intent = 'supply_chain_outsource_list'
        elif any(keyword in query_lower for keyword in ['pr审核', 'pr审查', 'pr复核', 'pr智能审核', '采购申请审核']):
            self._extract_supply_chain_entities(query_lower, entities, 'pr_review')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'supply_chain_pr_review_count'
            else:
                intent = 'supply_chain_pr_review_list'
        elif any(keyword in query_lower for keyword in ['单价复核', '核价', '价格复核', '报价复核']):
            self._extract_supply_chain_entities(query_lower, entities, 'price_review')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'supply_chain_price_review_count'
            else:
                intent = 'supply_chain_price_review_list'
        elif any(keyword in query_lower for keyword in ['打样申请', '打样', '样品申请', '样品']):
            self._extract_supply_chain_entities(query_lower, entities, 'sample')
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'supply_chain_sample_count'
            else:
                intent = 'supply_chain_sample_list'
        # 个人任务相关意图（优先于通用任务）
        elif '个人任务' in query_lower or '我的待办' in query_lower or ('待办' in query_lower and '审批' not in query_lower and '流程' not in query_lower):
            has_explicit_personal_scope = '个人' in query_lower or '我的' in query_lower
            if has_explicit_personal_scope:
                if any(keyword in query_lower for keyword in ['已完成', '完成的', '完成态']):
                    entities['status'] = 'completed'
                elif any(keyword in query_lower for keyword in ['待办', '未完成', '待处理']):
                    entities['status'] = 'todo'
                elif '进行中' in query_lower:
                    entities['status'] = 'in_progress'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'personal_task_count'
            else:
                intent = 'personal_task_list'

        elif ('任务' in query_lower or '待办' in query_lower) and '生产' not in query_lower:
            if any(keyword in query_lower for keyword in owned_scope_keywords):
                entities['scope'] = 'owned_by_me'
            if any(keyword in query_lower for keyword in ['已完成', '完成的', '完成态']):
                entities['status'] = 'completed'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'task_count'
            else:
                intent = 'task_list'

        # 个人笔记相关意图
        elif '个人笔记' in query_lower or '我的笔记' in query_lower or ('笔记' in query_lower and '项目' not in query_lower and '会议' not in query_lower):
            if '重要' in query_lower:
                entities['is_important'] = True
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'personal_note_count'
            else:
                intent = 'personal_note_list'

        # 个人通讯录相关意图
        elif '个人通讯录' in query_lower or '我的联系人' in query_lower or '私人通讯录' in query_lower or '私人联系人' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'personal_contact_count'
            else:
                intent = 'personal_contact_list'


            # 企业信息相关意图
        elif (('企业' in query_lower or '公司' in query_lower) and
              not any(kw in query_lower for kw in ['客户', '订单', '项目', '合同', '产品', '供应商'])):
            if ('数量' in query_lower or '几个' in query_lower or '几家' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'enterprise_count'
            else:
                intent = 'enterprise_list'

        # 岗位职称相关意图
        elif ('岗位' in query_lower or '职称' in query_lower or '职位' in query_lower) and '招聘' not in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'position_count'
            else:
                intent = 'position_list'

        # 工作汇报相关意图
        elif '工作汇报' in query_lower or '工作报告' in query_lower or ('工作总结' in query_lower and '项目' not in query_lower):
            self._extract_work_report_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'work_report_count'
            else:
                intent = 'work_report_list'
        elif ('日报' in query_lower or '周报' in query_lower or '月报' in query_lower) and '项目' not in query_lower:
            self._extract_work_report_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'work_report_count'
            else:
                intent = 'work_report_list'

        elif any(keyword in query_lower for keyword in ['订单财务记录', '订单财务', '订单回款记录', '订单付款记录']):
            if '待付款' in query_lower:
                entities['status'] = 'pending'
            elif '部分付款' in query_lower:
                entities['status'] = 'partial'
            elif '已付款' in query_lower or '已付' in query_lower:
                entities['status'] = 'paid'
            elif '逾期' in query_lower:
                entities['status'] = 'overdue'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'finance_order_record_count'
            else:
                intent = 'finance_order_record_list'

            # 订单相关意图（优先于客户相关意图，因为订单查询可能包含客户名称）
        elif '订单' in query_lower:
            customer_name = self._extract_customer_name_from_order_query(query_lower)
            if customer_name:
                entities['customer_name'] = customer_name
            self._extract_order_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                if entities.get('status') in {'completed', '已完成'}:
                    intent = 'order_count_completed'
                elif entities.get('status') in {'processing', 'in_progress'}:
                    intent = 'order_count_in_progress'
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
        elif '跟进' in query_lower or '回访' in query_lower:
            self._extract_followup_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'followup_count'
            else:
                intent = 'followup_list'

        elif '客户' in query_lower:
            if '对接人' in query_lower or '联系人' in query_lower:
                if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                    intent = 'contact_count'
                else:
                    intent = 'contact_list'
                return intent, entities
            if any(keyword in query_lower for keyword in owned_scope_keywords):
                entities['scope'] = 'owned_by_me'
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
            self._extract_contract_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                if entities.get('status') == 'effective':
                    intent = 'contract_count_effective'
                elif entities.get('status') == 'expired':
                    intent = 'contract_count_expired'
                else:
                    intent = 'contract_count'
            elif '列表' in query_lower or '有哪些' in query_lower or '列出' in query_lower or '展示' in query_lower or '查看' in query_lower:
                intent = 'contract_list'
            elif '金额' in query_lower or '总额' in query_lower:
                intent = 'contract_total'

        elif any(keyword in query_lower for keyword in ['项目阶段', '阶段配置', '阶段列表', '阶段管理']):
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'project_stage_count'
            else:
                intent = 'project_stage_list'
        elif any(keyword in query_lower for keyword in ['项目分类', '分类配置', '分类列表', '分类管理']):
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'project_category_count'
            else:
                intent = 'project_category_list'
        elif any(keyword in query_lower for keyword in ['工作类型', '工作类别', '类型配置', '工时类型']):
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'work_type_count'
            else:
                intent = 'work_type_list'

        # 项目相关意图
        elif '项目文档' in query_lower or ('项目' in query_lower and '文档' in query_lower):
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'project_document_count'
            else:
                intent = 'project_document_list'
        elif '项目' in query_lower:
            if any(keyword in query_lower for keyword in owned_scope_keywords):
                entities['scope'] = 'owned_by_me'
            self._extract_project_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                if entities.get('status') in {'in_progress', '进行中'}:
                    intent = 'project_count_in_progress'
                elif entities.get('status') in {'completed', '已完成'}:
                    intent = 'project_count_completed'
                elif entities.get('status') == 'paused':
                    intent = 'project_count_paused'
                else:
                    intent = 'project_count'
            elif '进度' in query_lower or '完成率' in query_lower:
                intent = 'project_progress'
            elif '列表' in query_lower or '有哪些' in query_lower or '列出' in query_lower or '展示' in query_lower or '查看' in query_lower or '看' in query_lower or '查' in query_lower:
                if entities.get('status') in {'in_progress', '进行中'}:
                    intent = 'project_list_in_progress'
                elif entities.get('status') in {'completed', '已完成'}:
                    intent = 'project_list_completed'
                else:
                    intent = 'project_list'

        # 发票相关意图
        elif '发票' in query_lower:
            self._extract_finance_invoice_entities(query_lower, entities)
            if entities.get('enter_status'):
                intent = 'finance_invoice_count' if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower) else 'finance_invoice_list'
            elif any(keyword in query_lower for keyword in ['未开票', '已开票', '已作废']):
                if '未开票' in query_lower:
                    entities['status'] = 'unissued'
                    intent = 'finance_invoice_count' if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower) else 'finance_invoice_list'
                elif '已开票' in query_lower:
                    entities['status'] = 'issued'
                    intent = 'finance_invoice_count' if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower) else 'finance_invoice_list'
                elif '已作废' in query_lower:
                    entities['status'] = 'void'
                    intent = 'finance_invoice_count' if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower) else 'finance_invoice_list'
            elif ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
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
            self._extract_employee_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                # 检查是否有状态筛选
                if entities.get('status') == 'active':
                    intent = 'employee_count_active'
                elif entities.get('status') == 'inactive':
                    intent = 'employee_count_inactive'
                else:
                    intent = 'employee_count'
            elif '列表' in query_lower or '有哪些' in query_lower:
                intent = 'employee_list'

        # 部门相关意图
        elif '部门' in query_lower:
            self._extract_enabled_status_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                intent = 'department_count'
            elif '列表' in query_lower or '有哪些' in query_lower:
                intent = 'department_list'

        elif '供应商' in query_lower:
            self._extract_enabled_status_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'supplier_count'
            else:
                intent = 'supplier_list'

        elif '资产品牌' in query_lower or '资产牌子' in query_lower:
            self._extract_enabled_status_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'asset_brand_count'
            else:
                intent = 'asset_brand_list'

        elif '产品' in query_lower or '商品' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'product_count'
            else:
                intent = 'product_list'

        elif '入库' in query_lower:
            self._extract_stock_movement_entities(query_lower, entities, 'in')
            if '待入库确认' in query_lower or '待执行入库' in query_lower or '待入库' in query_lower:
                entities['status'] = 'approved'
            elif '已入库' in query_lower:
                entities['status'] = 'stocked'
            elif '待审核' in query_lower:
                entities['status'] = 'pending'
            elif '已取消' in query_lower:
                entities['status'] = 'cancelled'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'stockin_count'
            else:
                intent = 'stockin_list'

        elif '出库' in query_lower:
            self._extract_stock_movement_entities(query_lower, entities, 'out')
            if '待出库确认' in query_lower or '待执行出库' in query_lower or '待出库' in query_lower:
                entities['status'] = 'approved'
            elif '已出库' in query_lower:
                entities['status'] = 'stocked'
            elif '待审核' in query_lower:
                entities['status'] = 'pending'
            elif '已取消' in query_lower:
                entities['status'] = 'cancelled'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'stockout_count'
            else:
                intent = 'stockout_list'

        elif '仓库' in query_lower:
            self._extract_enabled_status_entities(query_lower, entities)
            self._extract_warehouse_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'warehouse_count'
            else:
                intent = 'warehouse_list'

        elif '预警' in query_lower:
            if '未处理' in query_lower or '待处理' in query_lower:
                entities['status'] = 'pending'
            elif '已处理' in query_lower:
                entities['status'] = 'processed'
            elif '已忽略' in query_lower or '忽略' in query_lower:
                entities['status'] = 'ignored'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'alert_count'
            else:
                intent = 'alert_list'

        elif '库存' in query_lower or '存货' in query_lower or '物料' in query_lower:
            self._extract_inventory_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'inventory_count'
            else:
                intent = 'inventory_list'

        elif '客户联系人' in query_lower or '对接人' in query_lower or '联系人' in query_lower:
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'contact_count'
            else:
                intent = 'contact_list'

        elif '公文分类' in query_lower or '文档分类' in query_lower:
            self._extract_enabled_status_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'document_category_count'
            else:
                intent = 'document_category_list'

        elif '资产分类' in query_lower or '资产类别' in query_lower:
            self._extract_enabled_status_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'asset_category_count'
            else:
                intent = 'asset_category_list'

        elif '公文' in query_lower or '文档' in query_lower:
            if '待发布' in query_lower:
                entities['status'] = 'approved'
            elif '已发布' in query_lower:
                entities['status'] = 'published'
            elif '草稿' in query_lower:
                entities['status'] = 'draft'
            elif '待审核' in query_lower:
                entities['status'] = 'pending'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'document_count'
            else:
                intent = 'document_list'

        elif any(keyword in query_lower for keyword in ['资金账户', '财务账户', '银行账户', '现金账户']):
            self._extract_advanced_finance_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'finance_account_count'
            else:
                intent = 'finance_account_list'

        elif any(keyword in query_lower for keyword in ['预算', '预算管理']):
            self._extract_advanced_finance_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'finance_budget_count'
            else:
                intent = 'finance_budget_list'

        elif any(keyword in query_lower for keyword in ['应收账款', '应收款', '应收']):
            self._extract_advanced_finance_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'finance_receivable_count'
            else:
                intent = 'finance_receivable_list'

        elif any(keyword in query_lower for keyword in ['应付账款', '应付款', '应付']):
            self._extract_advanced_finance_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'finance_payable_count'
            else:
                intent = 'finance_payable_list'

        elif any(keyword in query_lower for keyword in ['银行流水', '资金流水', '账户流水', '流水记录']):
            self._extract_advanced_finance_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'finance_bank_transaction_count'
            else:
                intent = 'finance_bank_transaction_list'

        # 财务相关意图
        elif '财务' in query_lower or '报销' in query_lower or '发票' in query_lower or '回款' in query_lower or '打款' in query_lower:
            self._extract_time_range_entities(query_lower, entities)
            if '报销' in query_lower:
                self._extract_finance_expense_entities(query_lower, entities)
            if '发票' in query_lower:
                self._extract_finance_invoice_entities(query_lower, entities)
            if '待打款' in query_lower:
                entities['status'] = 'pending_payment'
            elif '已打款' in query_lower:
                entities['status'] = 'paid'
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                if '报销' in query_lower:
                    intent = 'finance_expense_count'
                elif '发票' in query_lower:
                    intent = 'finance_invoice_count'
                elif '回款' in query_lower or '收入' in query_lower:
                    intent = 'finance_income_count'
                elif '订单' in query_lower:
                    intent = 'finance_order_record_count'
                else:
                    intent = 'finance_expense_count'
            elif '列表' in query_lower or '有哪些' in query_lower or '查' in query_lower or '看' in query_lower or '记录' in query_lower:
                if '报销' in query_lower:
                    intent = 'finance_expense_list'
                elif '发票' in query_lower:
                    intent = 'finance_invoice_list'
                elif '回款' in query_lower or '收入' in query_lower:
                    intent = 'finance_income_list'
                elif '订单' in query_lower:
                    intent = 'finance_order_record_list'
                else:
                    intent = 'finance_expense_list'

        elif '付款' in query_lower or '付款记录' in query_lower:
            self._extract_time_range_entities(query_lower, entities)
            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower or '统计' in query_lower):
                intent = 'payment_count'
            else:
                intent = 'payment_list'

        # 生产相关意图
        elif '生产' in query_lower or '生产计划' in query_lower or '生产任务' in query_lower or '设备' in query_lower or '工序' in query_lower:
            if '今天' in query_lower or '今日' in query_lower:
                entities['time_range'] = 'today'
            elif any(keyword in query_lower for keyword in ['本周', '这周']):
                entities['time_range'] = 'this_week'

            if '维修中' in query_lower:
                entities['status'] = 'maintenance'
            elif '停用' in query_lower:
                entities['status'] = 'disabled'
            elif '报废' in query_lower:
                entities['status'] = 'scrapped'
            elif '正常' in query_lower:
                entities['status'] = 'normal'
            elif '已暂停' in query_lower or '已挂起' in query_lower:
                entities['status'] = 'paused'
            elif '已完成' in query_lower:
                entities['status'] = 'completed'
            elif '进行中' in query_lower:
                entities['status'] = 'in_progress'
            elif '已审核' in query_lower:
                entities['status'] = 'approved'
            elif '待完成' in query_lower or '未完成' in query_lower:
                entities['status'] = 'unfinished'
            elif '待开始' in query_lower:
                entities['status'] = 'pending'

            if ('数量' in query_lower or '几个' in query_lower or '多少' in query_lower):
                if '计划' in query_lower:
                    intent = 'production_plan_count'
                elif '任务' in query_lower:
                    intent = 'production_task_count'
                elif '设备' in query_lower:
                    intent = 'production_equipment_count'
                elif '工序' in query_lower:
                    intent = 'production_procedure_count'
                else:
                    intent = 'production_plan_count'
            elif '列表' in query_lower or '有哪些' in query_lower or '查询' in query_lower or '查看' in query_lower or '查' in query_lower or '看' in query_lower:
                if '计划' in query_lower:
                    intent = 'production_plan_list'
                elif '任务' in query_lower:
                    intent = 'production_task_list'
                elif '设备' in query_lower:
                    intent = 'production_equipment_list'
                elif '工序' in query_lower:
                    intent = 'production_procedure_list'
                else:
                    intent = 'production_plan_list'

        if intent == 'contract_count' and any(keyword in query_lower for keyword in ['金额', '总额', '总和', '总金额', '签约额', '签约金额']):
            return 'contract_total', entities

        return intent, entities

    def _extract_customer_name_from_order_query(self, query_lower: str) -> str | None:
        direct_match = re.search(r'(.+?)的订单', query_lower)
        if direct_match:
            customer_name = direct_match.group(1).strip()
            customer_name = re.sub(r'^(查询|查下|查一下|查看|看下|看一下|列出|展示)', '', customer_name).strip()
            customer_name = re.sub(r'(有哪些|有多少|几个|数量|统计)$', '', customer_name).strip()
            if customer_name and customer_name not in {'我', '我的', '全部', '所有'}:
                return customer_name

        customer_name_matches = re.findall(r'[\u4e00-\u9fa5\w]+', query_lower)
        exclude_words = {
            '客户', '订单', '合同', '项目', '发票', '查询', '列出', '展示', '查看', '数量',
            '有多少', '几个', '统计', '关联', '所有', '的', '我', '有', '几', '个',
            '多少', '这个', '那个', '哪些', '有什么'
        }
        for match in customer_name_matches:
            if match not in exclude_words and len(match) > 1:
                return match
        return None

    def _extract_notice_entities(self, query_lower: str, entities: Dict[str, Any]) -> None:
        if any(keyword in query_lower for keyword in ['紧急通知', '紧急公告', '急件通知', '急件公告']):
            entities['notice_type'] = 'urgent'
        elif any(keyword in query_lower for keyword in ['系统通知', '系统公告', '平台通知', '平台公告']):
            entities['notice_type'] = 'system'
        elif any(keyword in query_lower for keyword in ['公司公告', '公司通知', '企业公告', '企业通知', '公司动态']):
            entities['notice_type'] = 'company'

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
            data_type = self._get_data_type_from_specific_intent(intent) or intent.split('_')[0]
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


    def handle_enterprise_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.enterprise.models import Enterprise
        count = Enterprise.objects.filter(status=1).count()
        return {
            "type": "count",
            "value": count,
            "data_type": "enterprise"
        }

    def handle_enterprise_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.enterprise.models import Enterprise
        queryset = Enterprise.objects.filter(status=1).order_by("-create_time")
        items = [{
            "id": e.id,
            "name": e.title,
            "city": e.city or "",
            "bank": e.bank or "",
            "status": "启用" if e.status == 1 else "禁用"
        } for e in queryset[:5]]
        return {
            "type": "list",
            "items": items,
            "total": queryset.count(),
            "data_type": "enterprise"
        }

    def handle_position_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.user.models.position import Position
        count = Position.objects.filter(status=1).count()
        return {
            "type": "count",
            "value": count,
            "data_type": "position"
        }

    def handle_position_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.user.models.position import Position
        queryset = Position.objects.filter(status=1).order_by("sort")
        items = [{
            "id": p.id,
            "name": p.title,
            "description": p.desc or "",
            "status": "启用" if p.status == 1 else "禁用"
        } for p in queryset[:5]]
        return {
            "type": "list",
            "items": items,
            "total": queryset.count(),
            "data_type": "position"
        }

    def handle_work_record_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import WorkRecord
        queryset = WorkRecord.objects.filter(user=user)
        queryset = self._apply_work_record_filters(queryset, entities)
        return {
            "type": "count",
            "value": queryset.count(),
            "data_type": "work_record"
        }

    def handle_work_record_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import WorkRecord
        queryset = WorkRecord.objects.filter(user=user)
        queryset = self._apply_work_record_filters(queryset, entities)
        items = [{
            "id": r.id,
            "title": r.title,
            "work_type": r.work_type_display if hasattr(r, "work_type_display") else r.work_type,
            "work_date": r.work_date.strftime("%Y-%m-%d") if r.work_date else "",
            "duration": r.duration
        } for r in queryset.order_by("-work_date", "-start_time")[:5]]
        return {
            "type": "list",
            "items": items,
            "total": queryset.count(),
            "data_type": "work_record"
        }

    def handle_work_report_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import WorkReport
        queryset = WorkReport.objects.filter(user=user)
        queryset = self._apply_work_report_filters(queryset, entities)
        return {
            "type": "count",
            "value": queryset.count(),
            "data_type": "work_report"
        }

    def handle_work_report_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import WorkReport
        queryset = WorkReport.objects.filter(user=user)
        queryset = self._apply_work_report_filters(queryset, entities)
        items = [{
            "id": r.id,
            "title": r.title,
            "report_type": r.report_type_display if hasattr(r, "report_type_display") else r.report_type,
            "report_date": r.report_date.strftime("%Y-%m-%d") if r.report_date else "",
            "is_submitted": r.is_submitted
        } for r in queryset.order_by("-report_date")[:5]]
        return {
            "type": "list",
            "items": items,
            "total": queryset.count(),
            "data_type": "work_report"
        }



    def handle_personal_task_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import PersonalTask
        queryset = PersonalTask.objects.filter(user=user)
        queryset = self._apply_personal_task_filters(queryset, entities)
        return {
            "type": "count",
            "value": queryset.count(),
            "data_type": "personal_task"
        }

    def handle_personal_task_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import PersonalTask
        queryset = PersonalTask.objects.filter(user=user)
        queryset = self._apply_personal_task_filters(queryset, entities)
        items = [{
            "id": t.id,
            "title": t.title,
            "status": t.status_display if hasattr(t, "status_display") else t.status,
            "priority": t.priority_display if hasattr(t, "priority_display") else t.priority,
            "due_date": t.due_date.strftime("%Y-%m-%d") if t.due_date else "",
        } for t in queryset.order_by("-priority", "due_date")[:5]]
        return {
            "type": "list",
            "items": items,
            "total": queryset.count(),
            "data_type": "personal_task"
        }

    def handle_personal_note_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import PersonalNote
        queryset = PersonalNote.objects.filter(user=user)
        queryset = self._apply_personal_note_filters(queryset, entities)
        return {
            "type": "count",
            "value": queryset.count(),
            "data_type": "personal_note"
        }

    def handle_personal_note_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import PersonalNote
        queryset = PersonalNote.objects.filter(user=user)
        queryset = self._apply_personal_note_filters(queryset, entities)
        items = [{
            "id": n.id,
            "title": n.title,
            "category": n.category_display if hasattr(n, "category_display") else n.category,
            "is_important": n.is_important,
        } for n in queryset.order_by("-updated_at")[:5]]
        return {
            "type": "list",
            "items": items,
            "total": queryset.count(),
            "data_type": "personal_note"
        }

    def handle_personal_contact_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import PersonalContact
        queryset = PersonalContact.objects.filter(user=user)
        return {
            "type": "count",
            "value": queryset.count(),
            "data_type": "personal_contact"
        }

    def handle_personal_contact_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import PersonalContact
        queryset = PersonalContact.objects.filter(user=user).order_by("name")[:5]
        items = [{
            "id": c.id,
            "name": c.name,
            "company": c.company or "",
            "phone": c.phone or c.mobile or "",
            "is_important": c.is_important,
        } for c in queryset]
        return {
            "type": "list",
            "items": items,
            "total": PersonalContact.objects.filter(user=user).count(),
            "data_type": "personal_contact"
        }



    def _format_timestamp_or_datetime(self, value, fmt):
        if hasattr(value, 'strftime'):
            return value.strftime(fmt)
        try:
            import time
            return time.strftime(fmt, time.localtime(value))
        except (TypeError, ValueError, OSError):
            return ''

    def _extract_order_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['待处理', '待确认']):
            entities['status'] = 'pending'
        elif '已确认' in query_lower:
            entities['status'] = 'confirmed'
        elif any(keyword in query_lower for keyword in ['处理中', '进行中']):
            entities['status'] = 'processing'
        elif '已发货' in query_lower:
            entities['status'] = 'shipped'
        elif '已交付' in query_lower:
            entities['status'] = 'delivered'
        elif '已完成' in query_lower:
            entities['status'] = 'completed'
        elif '已取消' in query_lower:
            entities['status'] = 'cancelled'

    def _extract_time_range_entities(self, query_lower, entities):
        if '今天' in query_lower or '今日' in query_lower:
            entities['time_range'] = 'today'
        elif any(keyword in query_lower for keyword in ['本周', '这周']):
            entities['time_range'] = 'this_week'
        elif any(keyword in query_lower for keyword in ['上周', '上一周']):
            entities['time_range'] = 'last_week'
        elif '本月' in query_lower or '这个月' in query_lower:
            entities['time_range'] = 'this_month'
        elif '上月' in query_lower or '上个月' in query_lower:
            entities['time_range'] = 'last_month'
        elif any(keyword in query_lower for keyword in ['最近', '近期']):
            entities['time_range'] = 'recent'

    def _extract_enabled_status_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['停用', '禁用', '未启用']):
            entities['status'] = 'inactive'
        elif any(keyword in query_lower for keyword in ['启用', '可用', '正常']):
            entities['status'] = 'active'

    def _extract_warehouse_entities(self, query_lower, entities):
        warehouse_type_mapping = {
            '主仓': 'main',
            '主仓库': 'main',
            '分仓': 'branch',
            '分仓库': 'branch',
            '虚拟仓': 'virtual',
            '虚拟仓库': 'virtual',
            '生产仓': 'production',
            '生产仓库': 'production',
            '质检仓': 'quality',
            '质检仓库': 'quality',
        }
        for keyword, warehouse_type in warehouse_type_mapping.items():
            if keyword in query_lower:
                entities['warehouse_type'] = warehouse_type
                break

    def _extract_stock_movement_entities(self, query_lower, entities, direction):
        if direction == 'in':
            type_mapping = {
                '采购入库': 'purchase',
                '生产入库': 'production',
                '退货入库': 'return',
                '调拨入库': 'transfer',
                '其他入库': 'other',
            }
        else:
            type_mapping = {
                '销售出库': 'sale',
                '生产领料': 'production',
                '生产出库': 'production',
                '调拨出库': 'transfer',
                '报废出库': 'scrap',
                '其他出库': 'other',
            }
        for keyword, stock_type in type_mapping.items():
            if keyword in query_lower:
                entities['stock_type'] = stock_type
                break

    def _extract_inventory_entities(self, query_lower, entities):
        if '锁定' in query_lower:
            entities['status'] = 'locked'
        elif '隔离' in query_lower or '待检' in query_lower:
            entities['status'] = 'quarantine'
        elif '正常' in query_lower or '可用' in query_lower:
            entities['status'] = 'normal'

    def _extract_employee_entities(self, query_lower, entities):
        if '离职' in query_lower:
            entities['status'] = 'inactive'
        elif any(keyword in query_lower for keyword in ['禁用', '停用', '禁止登录']):
            entities['status'] = 'disabled'
        elif any(keyword in query_lower for keyword in ['待入职', '未入职']):
            entities['status'] = 'pending'
        elif any(keyword in query_lower for keyword in ['在职', '正常员工', '启用员工']):
            entities['status'] = 'active'

    def _extract_reward_punishment_entities(self, query_lower, entities):
        self._extract_time_range_entities(query_lower, entities)
        if any(keyword in query_lower for keyword in ['奖励', '表彰', '嘉奖']):
            entities['type'] = 'reward'
        elif any(keyword in query_lower for keyword in ['处罚', '惩罚', '处分']):
            entities['type'] = 'punishment'

    def _extract_employee_care_entities(self, query_lower, entities):
        self._extract_time_range_entities(query_lower, entities)
        care_type_mapping = {
            'birthday': ['生日关怀', '生日'],
            'holiday': ['节日关怀', '节日'],
            'illness': ['生病慰问', '病假慰问', '住院慰问'],
            'family': ['家庭关怀', '家属关怀'],
            'achievement': ['成就祝贺', '获奖祝贺', '晋升祝贺'],
        }
        for care_type, keywords in care_type_mapping.items():
            if any(keyword in query_lower for keyword in keywords):
                entities['care_type'] = care_type
                break

    def _extract_production_detail_entities(self, query_lower, entities, data_type):
        self._extract_time_range_entities(query_lower, entities)
        if data_type in {'procedureset', 'bom'}:
            self._extract_enabled_status_entities(query_lower, entities)
            return
        if data_type == 'process':
            status_mapping = {
                'pending': ['待审核'],
                'approved': ['已审核'],
                'in_progress': ['执行中', '进行中'],
                'completed': ['已完成'],
                'cancelled': ['已取消'],
            }
            for status, keywords in status_mapping.items():
                if any(keyword in query_lower for keyword in keywords):
                    entities['status'] = status
                    break
            return
        if data_type == 'quality_check':
            if any(keyword in query_lower for keyword in ['不合格', '异常质检']):
                entities['status'] = 'unqualified'
            elif any(keyword in query_lower for keyword in ['合格']):
                entities['status'] = 'qualified'
            elif any(keyword in query_lower for keyword in ['待检']):
                entities['status'] = 'pending'
            return
        if data_type == 'datacollection':
            if any(keyword in query_lower for keyword in ['异常', '超标', '不正常']):
                entities['status'] = 'abnormal'
            elif any(keyword in query_lower for keyword in ['正常', '合规']):
                entities['status'] = 'normal'

    def _extract_approval_detail_entities(self, query_lower, entities, data_type):
        self._extract_time_range_entities(query_lower, entities)
        if data_type in {'approval_type', 'approval_flow'}:
            self._extract_enabled_status_entities(query_lower, entities)
            return

        flow_match = re.search(r'([\u4e00-\u9fffA-Za-z0-9_-]+)审批流程', query_lower)
        if flow_match:
            entities['flow_name'] = flow_match.group(1)

        flow_id_match = re.search(r'流程\s*(\d+)', query_lower)
        if flow_id_match:
            entities['flow_id'] = int(flow_id_match.group(1))

        if data_type == 'approval_step':
            step_type_mapping = {
                'condition': ['条件步骤', '条件节点', '条件审批', '条件分支'],
                'department_head': ['部门负责人', '主管审批'],
                'specific_user': ['指定用户', '指定审批人'],
                'cc': ['抄送'],
                'notification': ['通知节点', '通知步骤'],
                'countersign': ['会签'],
                'orsign': ['或签'],
                'execute': ['办理节点', '执行节点', '办理步骤'],
                'external': ['外部审批'],
            }
            for step_type, keywords in step_type_mapping.items():
                if any(keyword in query_lower for keyword in keywords):
                    entities['step_type'] = step_type
                    break
            return

        if data_type == 'approval_record':
            action_mapping = {
                'approve': ['通过', '同意', '批准'],
                'reject': ['拒绝', '驳回'],
                'return': ['退回'],
                'withdraw': ['撤回'],
                'transfer': ['转办', '转交'],
                'delegate': ['委托'],
                'urge': ['催办'],
                'timeout': ['超时'],
                'force_end': ['强制结束'],
                'archive': ['归档'],
            }
            for action, keywords in action_mapping.items():
                if any(keyword in query_lower for keyword in keywords):
                    entities['action'] = action
                    break
            return

        if data_type == 'approval_flow_edge':
            edge_type_mapping = {
                'condition': ['条件连线', '条件流转', '条件分支'],
                'success': ['通过连线', '通过路径'],
                'reject': ['拒绝连线', '驳回路径'],
                'return': ['退回连线', '退回路径'],
            }
            for edge_type, keywords in edge_type_mapping.items():
                if any(keyword in query_lower for keyword in keywords):
                    entities['edge_type'] = edge_type
                    break

    def _extract_asset_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['维修中', '维修的', '报修']):
            entities['status'] = 'repair'
        elif any(keyword in query_lower for keyword in ['报废', '已废弃']):
            entities['status'] = 'scrap'
        elif any(keyword in query_lower for keyword in ['丢失', '遗失']):
            entities['status'] = 'lost'
        elif any(keyword in query_lower for keyword in ['正常', '可用']):
            entities['status'] = 'normal'

    def _extract_vehicle_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['维修中', '维修的', '检修']):
            entities['status'] = 'repair'
        elif any(keyword in query_lower for keyword in ['报废', '已废弃']):
            entities['status'] = 'scrap'
        elif any(keyword in query_lower for keyword in ['正常', '可用']):
            entities['status'] = 'normal'

    def _extract_asset_repair_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['待处理', '待维修', '未处理']):
            entities['status'] = 'pending'
        elif any(keyword in query_lower for keyword in ['处理中', '维修中']):
            entities['status'] = 'processing'
        elif any(keyword in query_lower for keyword in ['已完成', '已维修', '完成的']):
            entities['status'] = 'completed'
        elif any(keyword in query_lower for keyword in ['已取消', '已撤销', '取消的']):
            entities['status'] = 'cancelled'

    def _extract_vehicle_maintenance_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['保养记录', '车辆保养', '保养的']):
            entities['maintenance_type'] = 'maintain'
        elif any(keyword in query_lower for keyword in ['维修记录', '车辆维修', '维修的']):
            entities['maintenance_type'] = 'repair'

    def _extract_vehicle_fee_entities(self, query_lower, entities):
        fee_type_mapping = {
            '燃油费': 'fuel',
            '油费': 'fuel',
            '保险费': 'insurance',
            '保险': 'insurance',
            '车船税': 'tax',
            '停车费': 'parking',
            '过路费': 'toll',
            '通行费': 'toll',
            '罚款': 'fine',
            '违章': 'fine',
            '其他': 'other',
        }
        for keyword, fee_type in fee_type_mapping.items():
            if keyword in query_lower:
                entities['fee_type'] = fee_type
                break

    def _extract_meeting_room_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['可用', '启用', '正常', '空闲']):
            entities['status'] = 'active'
        elif any(keyword in query_lower for keyword in ['停用', '禁用', '不可用']):
            entities['status'] = 'inactive'
        if '投影' in query_lower:
            entities['has_projector'] = True
        if '白板' in query_lower:
            entities['has_whiteboard'] = True
        if '电视' in query_lower:
            entities['has_tv'] = True
        if '电话' in query_lower:
            entities['has_phone'] = True
        if any(keyword in query_lower for keyword in ['wifi', 'wi-fi', '无线']):
            entities['has_wifi'] = True

    def _extract_meeting_reservation_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['待审核', '待审批', '待处理']):
            entities['status'] = 'pending'
        elif any(keyword in query_lower for keyword in ['已通过', '审核通过', '审批通过']):
            entities['status'] = 'approved'
        elif any(keyword in query_lower for keyword in ['已拒绝', '已驳回', '审核不通过', '审批不通过']):
            entities['status'] = 'rejected'
        elif any(keyword in query_lower for keyword in ['已取消', '已撤销']):
            entities['status'] = 'cancelled'

        if '今天' in query_lower:
            entities['time_range'] = 'today'
        elif any(keyword in query_lower for keyword in ['本周', '这周']):
            entities['time_range'] = 'this_week'
        elif any(keyword in query_lower for keyword in ['上周', '上一周']):
            entities['time_range'] = 'last_week'

    def _extract_seal_entities(self, query_lower, entities):
        self._extract_enabled_status_entities(query_lower, entities)
        seal_type_mapping = {
            '公司公章': 'company',
            '公章': 'company',
            '合同专用章': 'contract',
            '合同章': 'contract',
            '财务专用章': 'finance',
            '财务章': 'finance',
            '法人章': 'legal',
        }
        for keyword, seal_type in seal_type_mapping.items():
            if keyword in query_lower:
                entities['seal_type'] = seal_type
                break

    def _extract_seal_application_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['待审核', '待审批', '待处理']):
            entities['status'] = 'pending'
        elif any(keyword in query_lower for keyword in ['已通过', '审核通过', '审批通过']):
            entities['status'] = 'approved'
        elif any(keyword in query_lower for keyword in ['已拒绝', '已驳回', '审核不通过', '审批不通过']):
            entities['status'] = 'rejected'
        elif any(keyword in query_lower for keyword in ['已用章', '已盖章']):
            entities['status'] = 'used'
        elif any(keyword in query_lower for keyword in ['已取消', '已撤销', '已撤回']):
            entities['status'] = 'cancelled'

    def _extract_finance_expense_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['审核通过', '审批通过', '已通过']):
            entities['check_status'] = 'approved'
        elif any(keyword in query_lower for keyword in ['审核中', '审批中']):
            entities['check_status'] = 'reviewing'
        elif any(keyword in query_lower for keyword in ['待审核', '待审批']):
            entities['check_status'] = 'pending'
        elif any(keyword in query_lower for keyword in ['审核不通过', '审批不通过', '已驳回', '驳回']):
            entities['check_status'] = 'rejected'
        elif any(keyword in query_lower for keyword in ['撤销审核', '已撤销']):
            entities['check_status'] = 'cancelled'

    def _extract_finance_invoice_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['部分回款', '部分到账']):
            entities['enter_status'] = 'partial'
        elif any(keyword in query_lower for keyword in ['全部回款', '全额回款', '已回款']):
            entities['enter_status'] = 'full'
        elif any(keyword in query_lower for keyword in ['未回款', '未到账']):
            entities['enter_status'] = 'none'
        if any(keyword in query_lower for keyword in ['审核通过', '审批通过', '已通过']):
            entities['check_status'] = 'approved'
        elif any(keyword in query_lower for keyword in ['审核中', '审批中']):
            entities['check_status'] = 'reviewing'
        elif any(keyword in query_lower for keyword in ['待审核', '待审批']):
            entities['check_status'] = 'pending'

    def _extract_advanced_finance_entities(self, query_lower, entities):
        self._extract_time_range_entities(query_lower, entities)
        if any(keyword in query_lower for keyword in ['未匹配', '未对上']):
            entities['match_status'] = 'unmatched'
        elif any(keyword in query_lower for keyword in ['已匹配', '已对上']):
            entities['match_status'] = 'matched'

        if any(keyword in query_lower for keyword in ['收入流水', '收入方向', '收款流水', '入账']):
            entities['direction'] = 'in'
        elif any(keyword in query_lower for keyword in ['支出流水', '支出方向', '付款流水', '出账']):
            entities['direction'] = 'out'

        if any(keyword in query_lower for keyword in ['停用', '禁用']):
            entities['status'] = 'inactive'
        elif any(keyword in query_lower for keyword in ['启用', '可用', '正常']):
            entities['status'] = 'active'
        elif any(keyword in query_lower for keyword in ['草稿']):
            entities['status'] = 'draft'
        elif any(keyword in query_lower for keyword in ['执行中', '生效中']):
            entities['status'] = 'active'
        elif any(keyword in query_lower for keyword in ['已关闭', '关闭']):
            entities['status'] = 'closed'
        elif any(keyword in query_lower for keyword in ['逾期', '已逾期']):
            entities['status'] = 'overdue'
        elif any(keyword in query_lower for keyword in ['坏账']):
            entities['status'] = 'bad_debt'
        elif any(keyword in query_lower for keyword in ['部分收款', '部分付款']):
            entities['status'] = 'partial'
        elif any(keyword in query_lower for keyword in ['已结清', '结清']):
            entities['status'] = 'settled'
        elif any(keyword in query_lower for keyword in ['待收款', '待收']):
            entities['status'] = 'pending'
        elif any(keyword in query_lower for keyword in ['待付款', '待付']):
            entities['status'] = 'pending'

    def _extract_supply_chain_entities(self, query_lower, entities, data_type):
        self._extract_time_range_entities(query_lower, entities)
        if any(keyword in query_lower for keyword in ['异常', '有问题', '风险']):
            entities['is_abnormal'] = True

        status_keywords = {
            'forecast': [
                ('reviewing', ['评审中', '待评审']),
                ('approved', ['已通过', '通过的', '已批准']),
                ('rejected', ['已驳回', '已拒绝', '驳回']),
                ('running', ['计算中', '运行中']),
                ('generated', ['已生成', '生成的']),
                ('archived', ['已归档', '归档']),
                ('draft', ['草稿']),
            ],
            'outsource': [
                ('shortage', ['缺料', '欠料']),
                ('ready', ['齐套完成', '已齐套', '齐套']),
                ('checking', ['齐套校验中', '校验中']),
                ('picking', ['备料中', '拣料中']),
                ('issued', ['已发料']),
                ('notified', ['已通知']),
                ('closed', ['已关闭', '关闭']),
                ('draft', ['草稿']),
            ],
            'pr_review': [
                ('manual_review', ['人工复核', '人工审核']),
                ('auto_approved', ['自动通过']),
                ('rule_matched', ['规则命中', '命中规则']),
                ('done', ['已处理', '处理完']),
                ('rejected', ['已拒绝', '已驳回']),
                ('pending', ['待识别', '待审核', '待处理']),
            ],
            'price_review': [
                ('exception', ['异常待处理', '异常']),
                ('reviewing', ['复核中', '审核中']),
                ('parsing', ['解析中']),
                ('breakdown', ['拆解中']),
                ('approved', ['已通过', '通过的']),
                ('draft', ['草稿']),
            ],
            'sample': [
                ('pickup_pending', ['待领样', '待领取']),
                ('picked_up', ['已领样', '已领取']),
                ('received', ['已到货', '到货']),
                ('ordered', ['已下单', '下单']),
                ('closed', ['已关闭', '关闭']),
                ('draft', ['草稿']),
            ],
        }
        for status, keywords in status_keywords.get(data_type, []):
            if any(keyword in query_lower for keyword in keywords):
                entities['status'] = status
                break

    def _extract_ai_center_entities(self, query_lower, entities, data_type):
        self._extract_time_range_entities(query_lower, entities)
        if data_type == 'ai_model_config':
            if any(keyword in query_lower for keyword in ['可用', '启用', '激活']):
                entities['is_active'] = True
            elif any(keyword in query_lower for keyword in ['停用', '禁用']):
                entities['is_active'] = False
            if '默认' in query_lower:
                entities['is_default'] = True
            return

        if data_type in {'ai_knowledge_base', 'ai_workflow'}:
            if any(keyword in query_lower for keyword in ['已发布', '发布的']):
                entities['status'] = 'published'
            elif any(keyword in query_lower for keyword in ['草稿']):
                entities['status'] = 'draft'
            elif any(keyword in query_lower for keyword in ['已归档', '归档']):
                entities['status'] = 'archived'
            return

        if data_type == 'ai_task':
            if any(keyword in query_lower for keyword in ['失败', '执行失败']):
                entities['status'] = 'failed'
            elif any(keyword in query_lower for keyword in ['执行中', '运行中']):
                entities['status'] = 'running'
            elif any(keyword in query_lower for keyword in ['已完成', '完成的']):
                entities['status'] = 'completed'
            elif any(keyword in query_lower for keyword in ['待执行', '待处理']):
                entities['status'] = 'pending'

    def _extract_contract_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['审核中', '审批中']):
            entities['status'] = 'reviewing'
        elif any(keyword in query_lower for keyword in ['待审核', '待审批']):
            entities['status'] = 'pending'
        elif any(keyword in query_lower for keyword in ['审核通过', '审批通过', '已生效']):
            entities['status'] = 'effective'
        elif any(keyword in query_lower for keyword in ['审核不通过', '审批不通过', '已驳回']):
            entities['status'] = 'rejected'
        elif '已过期' in query_lower:
            entities['status'] = 'expired'

    def _extract_project_entities(self, query_lower, entities):
        if '进行中' in query_lower or '在进行' in query_lower:
            entities['status'] = '进行中'
        elif '已完成' in query_lower:
            entities['status'] = '已完成'
        elif '暂停' in query_lower:
            entities['status'] = 'paused'
        elif '未开始' in query_lower or '待开始' in query_lower:
            entities['status'] = 'pending'
        elif '已关闭' in query_lower:
            entities['status'] = 'closed'

    def _extract_work_record_entities(self, query_lower, entities):
        if '今天' in query_lower:
            entities['time_range'] = 'today'
        elif any(keyword in query_lower for keyword in ['本周', '这周']):
            entities['time_range'] = 'this_week'
        elif any(keyword in query_lower for keyword in ['上周', '上一周']):
            entities['time_range'] = 'last_week'

        if '项目' in query_lower:
            entities['work_type'] = 'project'
        elif '会议' in query_lower:
            entities['work_type'] = 'meeting'
        elif '培训' in query_lower or '学习' in query_lower:
            entities['work_type'] = 'training'
        elif '日常' in query_lower:
            entities['work_type'] = 'daily'

    def _extract_work_report_entities(self, query_lower, entities):
        has_submission_status = False
        if any(keyword in query_lower for keyword in ['已提交', '已上交']):
            entities['is_submitted'] = True
            has_submission_status = True
        elif any(keyword in query_lower for keyword in ['草稿', '未提交']):
            entities['is_submitted'] = False
            has_submission_status = True

        if has_submission_status:
            if '日报' in query_lower:
                entities['report_type'] = 'daily'
            elif '周报' in query_lower:
                entities['report_type'] = 'weekly'
            elif '月报' in query_lower:
                entities['report_type'] = 'monthly'

    def _extract_followup_entities(self, query_lower, entities):
        if any(keyword in query_lower for keyword in ['电话跟进', '电话回访', '电话沟通']):
            entities['follow_type'] = 'phone'
        elif any(keyword in query_lower for keyword in ['上门拜访', '拜访跟进', '到访跟进']):
            entities['follow_type'] = 'visit'
        elif '邮件跟进' in query_lower:
            entities['follow_type'] = 'email'
        elif any(keyword in query_lower for keyword in ['会议跟进', '洽谈跟进']):
            entities['follow_type'] = 'meeting'

    def _apply_contract_filters(self, queryset, entities):
        status = entities.get('status')
        status_mapping = {
            'pending': 0,
            'reviewing': 1,
            'effective': 2,
            'approved': 2,
            'rejected': 3,
            'cancelled': 4,
        }
        if status == 'expired':
            import time
            queryset = queryset.filter(end_time__lt=int(time.time()), delete_time=0)
        elif status in status_mapping:
            queryset = queryset.filter(check_status=status_mapping[status])
        elif isinstance(status, int):
            queryset = queryset.filter(check_status=status)
        return queryset.filter(delete_time=0)

    def _apply_project_filters(self, queryset, entities, user):
        if entities.get('scope') == 'owned_by_me':
            queryset = queryset.filter(manager=user)

        status = entities.get('status')
        status_mapping = {
            'pending': 1,
            'in_progress': 2,
            'completed': 3,
            'closed': 4,
            'paused': 5,
            '进行中': 2,
            '已完成': 3,
            '已暂停': 5,
        }
        mapped_status = status_mapping.get(status, status if isinstance(status, int) else None)
        if mapped_status is not None:
            queryset = queryset.filter(status=mapped_status)
        return queryset

    def _apply_work_record_filters(self, queryset, entities):
        work_type = entities.get('work_type')
        if work_type:
            queryset = queryset.filter(work_type=work_type)

        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                queryset = queryset.filter(work_date__range=(start_at.date(), (end_at - timedelta(seconds=1)).date()))
        return queryset

    def _apply_work_report_filters(self, queryset, entities):
        report_type = entities.get('report_type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)

        if 'is_submitted' in entities:
            queryset = queryset.filter(is_submitted=entities['is_submitted'])
        return queryset

    def _apply_personal_task_filters(self, queryset, entities):
        status = entities.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def _apply_personal_note_filters(self, queryset, entities):
        if 'is_important' in entities:
            queryset = queryset.filter(is_important=entities['is_important'])
        return queryset

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
                build_csv_membership_q('share_ids', user.id)
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
                build_csv_membership_q('share_ids', user.id)
            )

        if entities.get('scope') == 'owned_by_me':
            queryset = queryset.filter(belong_uid=user.id)

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
        from apps.user.models import Admin
        queryset = self._apply_employee_filters(Admin.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
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
            'status': 'in_progress'
        }

    def handle_project_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理项目列表查询"""
        from apps.project.models import Project

        # 构建查询集
        queryset = Project.objects.all().select_related('manager')

        # 应用筛选条件
        queryset = self._apply_project_filters(queryset, entities, user)

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
            'status': 'in_progress'
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
            'status': 'completed'
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
            'status': 'in_progress'
        }

    def handle_order_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理订单列表查询"""
        from apps.customer.models import CustomerOrder, Customer

        # 构建查询集，考虑用户权限
        queryset = CustomerOrder.objects.filter(delete_time=0).select_related('customer')

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

        customer_name = entities.get('customer_name')
        if customer_name:
            queryset = queryset.filter(customer__name__icontains=customer_name)

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
            'delivery_date': getattr(order, 'delivery_date', None).strftime('%Y-%m-%d') if getattr(order, 'delivery_date', None) else '',
            'payment_date': getattr(order, 'payment_date', None).strftime('%Y-%m-%d') if getattr(order, 'payment_date', None) else '',
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
        queryset = self._apply_contract_filters(queryset, entities)

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
            'create_time': self._format_timestamp_or_datetime(contract.create_time, '%Y-%m-%d %H:%M:%S') if contract.create_time else ''
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
            'status': 'completed'
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
            'status': 'paused'
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
            'status': 'completed'
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
        queryset = self._apply_employee_filters(Admin.objects.all(), entities)
        employees = queryset[:5]
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
            'total': queryset.count(),
            'data_type': 'employee'
        }

    # 部门相关处理函数
    def handle_department_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理部门数量查询"""
        from apps.department.models import Department
        queryset = self._apply_department_filters(Department.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'department'
        }

    def handle_department_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理部门列表查询"""
        from apps.department.models import Department
        queryset = self._apply_department_filters(Department.objects.all(), entities)
        departments = queryset[:5]
        department_list = [{
            'id': department.id,
            'name': department.name,
            'parent': department.pid  # 上级部门ID
        } for department in departments]
        return {
            'type': 'list',
            'items': department_list,
            'total': queryset.count(),
            'data_type': 'department'
        }

    # 财务相关处理函数
    def handle_finance_expense_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理报销数量查询"""
        from apps.finance.models import Expense
        queryset = self._apply_finance_expense_filters(Expense.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'finance_expense',
            'status': entities.get('status'),
        }

    def handle_finance_expense_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理报销列表查询"""
        from apps.finance.models import Expense
        queryset = self._apply_finance_expense_filters(Expense.objects.all(), entities)
        expenses = queryset[:5]
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
            'total': queryset.count(),
            'data_type': 'finance_expense',
            'status': entities.get('status'),
        }

    def handle_finance_invoice_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理发票数量查询"""
        from apps.finance.models import Invoice
        queryset = self._apply_finance_invoice_filters(Invoice.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'finance_invoice',
            'status': entities.get('status'),
        }

    def handle_finance_invoice_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理发票列表查询"""
        from apps.finance.models import Invoice
        queryset = self._apply_finance_invoice_filters(Invoice.objects.all(), entities)
        invoices = queryset[:5]
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
            'total': queryset.count(),
            'data_type': 'finance_invoice',
            'status': entities.get('status'),
        }

    def handle_finance_income_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理回款数量查询"""
        from apps.finance.models import Income
        queryset = self._apply_datetime_range_filter(Income.objects.all(), entities, 'income_date')
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'finance_income'
        }

    def handle_finance_income_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理回款列表查询"""
        from apps.finance.models import Income
        incomes = self._apply_datetime_range_filter(Income.objects.all(), entities, 'income_date')[:5]
        income_list = [{
            'id': income.id,
            'invoice_code': getattr(getattr(income, 'invoice', None), 'code', ''),
            'amount': income.amount,
            'income_date': income.income_date.strftime('%Y-%m-%d')
        } for income in incomes]
        return {
            'type': 'list',
            'items': income_list,
            'total': self._apply_datetime_range_filter(Income.objects.all(), entities, 'income_date').count(),
            'data_type': 'finance_income'
        }

    def handle_finance_order_record_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理订单财务记录数量查询"""
        from apps.finance.models import OrderFinanceRecord
        count = self._filter_finance_order_record_queryset(OrderFinanceRecord.objects.all(), entities).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'finance_order_record'
        }

    def handle_finance_order_record_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理订单财务记录列表查询"""
        from apps.finance.models import OrderFinanceRecord
        queryset = self._filter_finance_order_record_queryset(OrderFinanceRecord.objects.all(), entities)
        records = queryset[:5]
        record_list = [{
            'id': record.id,
            'order_number': getattr(getattr(record, 'order', None), 'order_number', '') or f'订单{record.order_id}',
            'total_amount': record.total_amount,
            'paid_amount': record.paid_amount,
            'payment_status': record.payment_status
        } for record in records]
        return {
            'type': 'list',
            'items': record_list,
            'total': queryset.count(),
            'data_type': 'finance_order_record'
        }

    def handle_finance_account_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import FinanceAccount
        queryset = self._apply_advanced_finance_filters(FinanceAccount.objects.all(), entities, 'finance_account')
        return self._build_advanced_finance_count(queryset, 'finance_account', entities)

    def handle_finance_account_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import FinanceAccount
        queryset = self._apply_advanced_finance_filters(FinanceAccount.objects.all(), entities, 'finance_account')
        return self._build_advanced_finance_list(queryset, 'finance_account', entities)

    def handle_finance_budget_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import FinanceBudget
        queryset = self._apply_advanced_finance_filters(FinanceBudget.objects.all(), entities, 'finance_budget')
        return self._build_advanced_finance_count(queryset, 'finance_budget', entities)

    def handle_finance_budget_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import FinanceBudget
        queryset = self._apply_advanced_finance_filters(FinanceBudget.objects.all(), entities, 'finance_budget')
        return self._build_advanced_finance_list(queryset, 'finance_budget', entities)

    def handle_finance_receivable_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import AccountsReceivable
        queryset = self._apply_advanced_finance_filters(AccountsReceivable.objects.all(), entities, 'finance_receivable')
        return self._build_advanced_finance_count(queryset, 'finance_receivable', entities)

    def handle_finance_receivable_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import AccountsReceivable
        queryset = self._apply_advanced_finance_filters(AccountsReceivable.objects.all(), entities, 'finance_receivable')
        return self._build_advanced_finance_list(queryset, 'finance_receivable', entities)

    def handle_finance_payable_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import AccountsPayable
        queryset = self._apply_advanced_finance_filters(AccountsPayable.objects.all(), entities, 'finance_payable')
        return self._build_advanced_finance_count(queryset, 'finance_payable', entities)

    def handle_finance_payable_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import AccountsPayable
        queryset = self._apply_advanced_finance_filters(AccountsPayable.objects.all(), entities, 'finance_payable')
        return self._build_advanced_finance_list(queryset, 'finance_payable', entities)

    def handle_finance_bank_transaction_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import BankTransaction
        queryset = self._apply_advanced_finance_filters(
            BankTransaction.objects.select_related('account').all(),
            entities,
            'finance_bank_transaction',
        )
        return self._build_advanced_finance_count(queryset, 'finance_bank_transaction', entities)

    def handle_finance_bank_transaction_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import BankTransaction
        queryset = self._apply_advanced_finance_filters(
            BankTransaction.objects.select_related('account').all(),
            entities,
            'finance_bank_transaction',
        )
        return self._build_advanced_finance_list(queryset, 'finance_bank_transaction', entities)

    def handle_ai_model_config_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.ai.models import AIModelConfig
        queryset = self._apply_ai_center_filters(AIModelConfig.objects.all(), entities, 'ai_model_config')
        return self._build_ai_center_count(queryset, 'ai_model_config', entities)

    def handle_ai_model_config_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.ai.models import AIModelConfig
        queryset = self._apply_ai_center_filters(AIModelConfig.objects.all(), entities, 'ai_model_config')
        return self._build_ai_center_list(queryset, 'ai_model_config', entities)

    def handle_ai_knowledge_base_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.ai.models import AIKnowledgeBase
        queryset = self._apply_ai_center_filters(
            AIKnowledgeBase.objects.select_related('creator').all(),
            entities,
            'ai_knowledge_base',
        )
        return self._build_ai_center_count(queryset, 'ai_knowledge_base', entities)

    def handle_ai_knowledge_base_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.ai.models import AIKnowledgeBase
        queryset = self._apply_ai_center_filters(
            AIKnowledgeBase.objects.select_related('creator').all(),
            entities,
            'ai_knowledge_base',
        )
        return self._build_ai_center_list(queryset, 'ai_knowledge_base', entities)

    def handle_ai_task_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.ai.models import AITask
        queryset = self._apply_ai_center_filters(AITask.objects.select_related('user').all(), entities, 'ai_task')
        return self._build_ai_center_count(queryset, 'ai_task', entities)

    def handle_ai_task_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.ai.models import AITask
        queryset = self._apply_ai_center_filters(AITask.objects.select_related('user').all(), entities, 'ai_task')
        return self._build_ai_center_list(queryset, 'ai_task', entities)

    def handle_ai_workflow_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.ai.models import AIWorkflow
        queryset = self._apply_ai_center_filters(AIWorkflow.objects.select_related('owner').all(), entities, 'ai_workflow')
        return self._build_ai_center_count(queryset, 'ai_workflow', entities)

    def handle_ai_workflow_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.ai.models import AIWorkflow
        queryset = self._apply_ai_center_filters(AIWorkflow.objects.select_related('owner').all(), entities, 'ai_workflow')
        return self._build_ai_center_list(queryset, 'ai_workflow', entities)

    def handle_supply_chain_forecast_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.supply_chain.models import DemandForecastPlan
        queryset = self._apply_supply_chain_filters(
            DemandForecastPlan.objects.select_related('product').all(),
            entities,
            'supply_chain_forecast',
        )
        return self._build_supply_chain_count(queryset, 'supply_chain_forecast', entities)

    def handle_supply_chain_forecast_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.supply_chain.models import DemandForecastPlan
        queryset = self._apply_supply_chain_filters(
            DemandForecastPlan.objects.select_related('product').all(),
            entities,
            'supply_chain_forecast',
        )
        return self._build_supply_chain_list(queryset, 'supply_chain_forecast', entities)

    def handle_supply_chain_outsource_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.supply_chain.models import OutsourceIssueOrder
        queryset = self._apply_supply_chain_filters(
            OutsourceIssueOrder.objects.select_related('product', 'supplier').all(),
            entities,
            'supply_chain_outsource',
        )
        return self._build_supply_chain_count(queryset, 'supply_chain_outsource', entities)

    def handle_supply_chain_outsource_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.supply_chain.models import OutsourceIssueOrder
        queryset = self._apply_supply_chain_filters(
            OutsourceIssueOrder.objects.select_related('product', 'supplier').all(),
            entities,
            'supply_chain_outsource',
        )
        return self._build_supply_chain_list(queryset, 'supply_chain_outsource', entities)

    def handle_supply_chain_pr_review_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.supply_chain.models import PRReviewTask
        queryset = self._apply_supply_chain_filters(PRReviewTask.objects.all(), entities, 'supply_chain_pr_review')
        return self._build_supply_chain_count(queryset, 'supply_chain_pr_review', entities)

    def handle_supply_chain_pr_review_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.supply_chain.models import PRReviewTask
        queryset = self._apply_supply_chain_filters(PRReviewTask.objects.all(), entities, 'supply_chain_pr_review')
        return self._build_supply_chain_list(queryset, 'supply_chain_pr_review', entities)

    def handle_supply_chain_price_review_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.supply_chain.models import PriceReviewOrder
        queryset = self._apply_supply_chain_filters(
            PriceReviewOrder.objects.select_related('inventory_item', 'supplier').all(),
            entities,
            'supply_chain_price_review',
        )
        return self._build_supply_chain_count(queryset, 'supply_chain_price_review', entities)

    def handle_supply_chain_price_review_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.supply_chain.models import PriceReviewOrder
        queryset = self._apply_supply_chain_filters(
            PriceReviewOrder.objects.select_related('inventory_item', 'supplier').all(),
            entities,
            'supply_chain_price_review',
        )
        return self._build_supply_chain_list(queryset, 'supply_chain_price_review', entities)

    def handle_supply_chain_sample_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.supply_chain.models import SampleRequest
        queryset = self._apply_supply_chain_filters(
            SampleRequest.objects.select_related('supplier', 'engineer').all(),
            entities,
            'supply_chain_sample',
        )
        return self._build_supply_chain_count(queryset, 'supply_chain_sample', entities)

    def handle_supply_chain_sample_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.supply_chain.models import SampleRequest
        queryset = self._apply_supply_chain_filters(
            SampleRequest.objects.select_related('supplier', 'engineer').all(),
            entities,
            'supply_chain_sample',
        )
        return self._build_supply_chain_list(queryset, 'supply_chain_sample', entities)

    # 生产相关处理函数
    def handle_production_plan_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产计划数量查询"""
        from apps.production.models import ProductionPlan
        queryset = self._apply_production_plan_filters(ProductionPlan.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'production_plan'
        }

    def handle_production_plan_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产计划列表查询"""
        from apps.production.models import ProductionPlan
        queryset = self._apply_production_plan_filters(ProductionPlan.objects.all(), entities)
        plans = queryset[:5]
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
            'total': queryset.count(),
            'data_type': 'production_plan'
        }

    def handle_production_task_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产任务数量查询"""
        from apps.production.models import ProductionTask
        queryset = self._apply_production_task_filters(ProductionTask.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'production_task'
        }

    def handle_production_task_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产任务列表查询"""
        from apps.production.models import ProductionTask
        queryset = self._apply_production_task_filters(
            ProductionTask.objects.select_related('procedure').all(),
            entities,
        )
        tasks = queryset[:5]
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
            'total': queryset.count(),
            'data_type': 'production_task'
        }

    def handle_production_equipment_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产设备数量查询"""
        from apps.production.models import Equipment
        queryset = self._apply_production_equipment_filters(Equipment.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'production_equipment'
        }

    def handle_production_equipment_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        """处理生产设备列表查询"""
        from apps.production.models import Equipment
        queryset = self._apply_production_equipment_filters(Equipment.objects.all(), entities)
        equipments = queryset[:5]
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
            'total': queryset.count(),
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

    def handle_reward_punishment_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.user.models.employee import RewardPunishment

        queryset = self._apply_reward_punishment_filters(
            RewardPunishment.objects.select_related('employee', 'executor').all(),
            entities,
        )
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'reward_punishment',
            'status': entities.get('type'),
        }

    def handle_reward_punishment_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.user.models.employee import RewardPunishment

        queryset = self._apply_reward_punishment_filters(
            RewardPunishment.objects.select_related('employee', 'executor').all(),
            entities,
        )
        items = [{
            'id': item.id,
            'title': item.title,
            'type': item.get_type_display() if hasattr(item, 'get_type_display') else item.type,
            'level': item.get_level_display() if hasattr(item, 'get_level_display') else item.level,
            'employee': getattr(item.employee, 'username', ''),
            'executor': getattr(item.executor, 'username', ''),
            'effective_date': item.effective_date.strftime('%Y-%m-%d') if item.effective_date else '',
        } for item in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'reward_punishment',
            'status': entities.get('type'),
        }

    def handle_employee_care_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.user.models.employee import EmployeeCare

        queryset = self._apply_employee_care_filters(
            EmployeeCare.objects.select_related('employee', 'executor').all(),
            entities,
        )
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'employee_care',
            'status': entities.get('care_type'),
        }

    def handle_employee_care_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.user.models.employee import EmployeeCare

        queryset = self._apply_employee_care_filters(
            EmployeeCare.objects.select_related('employee', 'executor').all(),
            entities,
        )
        items = [{
            'id': item.id,
            'title': item.title,
            'care_type': item.get_care_type_display() if hasattr(item, 'get_care_type_display') else item.care_type,
            'employee': getattr(item.employee, 'username', ''),
            'executor': getattr(item.executor, 'username', ''),
            'care_date': item.care_date.strftime('%Y-%m-%d') if item.care_date else '',
        } for item in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'employee_care',
            'status': entities.get('care_type'),
        }

    def handle_procedureset_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.production.models import ProcedureSet

        queryset = self._apply_active_status_filter(ProcedureSet.objects.all(), entities, 'status')
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'procedureset',
            'status': entities.get('status'),
        }

    def handle_procedureset_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.production.models import ProcedureSet

        queryset = self._apply_active_status_filter(ProcedureSet.objects.all(), entities, 'status')
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'status': '启用' if item.status else '停用',
            'total_time': item.total_time,
        } for item in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'procedureset',
            'status': entities.get('status'),
        }

    def handle_bom_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.production.models import BOM

        queryset = self._apply_active_status_filter(BOM.objects.all(), entities, 'status')
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'bom',
            'status': entities.get('status'),
        }

    def handle_bom_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.production.models import BOM

        queryset = self._apply_active_status_filter(
            BOM.objects.select_related('product', 'creator').all(),
            entities,
            'status',
        )
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'status': '启用' if item.status else '停用',
            'product': getattr(getattr(item, 'product', None), 'name', ''),
        } for item in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'bom',
            'status': entities.get('status'),
        }

    def handle_process_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.production.models import ProcessRoute

        queryset = self._apply_process_filters(ProcessRoute.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'process',
            'status': entities.get('status'),
        }

    def handle_process_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.production.models import ProcessRoute

        queryset = self._apply_process_filters(ProcessRoute.objects.select_related('product').all(), entities)
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'status': item.status_display,
            'product': getattr(getattr(item, 'product', None), 'name', ''),
        } for item in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'process',
            'status': entities.get('status'),
        }

    def handle_quality_check_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.production.models import QualityCheck

        queryset = self._apply_quality_check_filters(QualityCheck.objects.select_related('task').all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'quality_check',
            'status': entities.get('status'),
        }

    def handle_quality_check_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.production.models import QualityCheck

        queryset = self._apply_quality_check_filters(
            QualityCheck.objects.select_related('task', 'created_by').all(),
            entities,
        )
        items = [{
            'id': item.id,
            'task': getattr(getattr(item, 'task', None), 'name', ''),
            'result': item.result_display if hasattr(item, 'result_display') else item.result,
            'check_time': item.check_time.strftime('%Y-%m-%d %H:%M') if item.check_time else '',
            'inspector': getattr(getattr(item, 'created_by', None), 'username', ''),
        } for item in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'quality_check',
            'status': entities.get('status'),
        }

    def handle_datacollection_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.production.models import DataCollection

        queryset = self._apply_datacollection_filters(
            DataCollection.objects.select_related('task', 'equipment').all(),
            entities,
        )
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'datacollection',
            'status': entities.get('status'),
        }

    def handle_datacollection_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.production.models import DataCollection

        queryset = self._apply_datacollection_filters(
            DataCollection.objects.select_related('task', 'equipment', 'created_by').all(),
            entities,
        )
        items = [{
            'id': item.id,
            'parameter_name': item.parameter_name,
            'parameter_value': item.parameter_value,
            'unit': item.unit,
            'equipment': getattr(getattr(item, 'equipment', None), 'name', ''),
            'task': getattr(getattr(item, 'task', None), 'name', ''),
            'status': '正常' if item.is_normal else '异常',
            'collect_time': item.collect_time.strftime('%Y-%m-%d %H:%M') if item.collect_time else '',
        } for item in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'datacollection',
            'status': entities.get('status'),
        }

    def handle_supplier_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.contract.models import Supplier
        count = self._apply_active_status_filter(Supplier.objects.all(), entities, 'is_active').count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'supplier'
        }

    def handle_supplier_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.contract.models import Supplier
        queryset = self._apply_active_status_filter(Supplier.objects.all(), entities, 'is_active')
        suppliers = queryset[:5]
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
            'total': queryset.count(),
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
        count = self._apply_inventory_filters(Inventory.objects.all(), entities).count()
        return {
            'type': 'count',
            'value': count,
            'data_type': 'inventory'
        }

    def handle_inventory_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.inventory.models import Inventory
        queryset = self._apply_inventory_filters(
            Inventory.objects.select_related('item', 'warehouse', 'location').all(),
            entities,
        )
        inventories = queryset[:5]
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
            'total': queryset.count(),
            'data_type': 'inventory'
        }

    def handle_warehouse_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.inventory.models import Warehouse
        queryset = self._apply_warehouse_filters(Warehouse.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'warehouse'
        }

    def handle_warehouse_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.inventory.models import Warehouse
        queryset = self._apply_warehouse_filters(Warehouse.objects.all(), entities).order_by('code')
        items = [{
            'id': warehouse.id,
            'name': warehouse.name,
            'code': warehouse.code,
            'address': warehouse.address,
            'status': warehouse.get_status_display() if hasattr(warehouse, 'get_status_display') else warehouse.status,
        } for warehouse in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'warehouse'
        }

    def handle_stockin_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.inventory.models import StockIn
        queryset = self._apply_stock_movement_filters(StockIn.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'stockin'
        }

    def handle_stockin_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.inventory.models import StockIn
        queryset = self._apply_stock_movement_filters(
            StockIn.objects.select_related('warehouse', 'supplier').order_by('-create_time'),
            entities,
        )
        items = [{
            'id': stock_in.id,
            'stock_in_no': stock_in.code,
            'stock_in_type': stock_in.get_stock_in_type_display() if hasattr(stock_in, 'get_stock_in_type_display') else stock_in.stock_in_type,
            'warehouse_name': stock_in.warehouse.name if stock_in.warehouse else '',
            'supplier_name': stock_in.supplier.name if stock_in.supplier else '',
            'total_amount': stock_in.total_amount,
            'total_quantity': stock_in.total_quantity,
            'status': stock_in.get_status_display() if hasattr(stock_in, 'get_status_display') else stock_in.status,
        } for stock_in in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'stockin'
        }

    def handle_stockout_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.inventory.models import StockOut
        queryset = self._apply_stock_movement_filters(StockOut.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'stockout'
        }

    def handle_stockout_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.inventory.models import StockOut
        queryset = self._apply_stock_movement_filters(
            StockOut.objects.select_related('warehouse', 'customer').order_by('-create_time'),
            entities,
        )
        items = [{
            'id': stock_out.id,
            'stock_out_no': stock_out.code,
            'stock_out_type': stock_out.get_stock_out_type_display() if hasattr(stock_out, 'get_stock_out_type_display') else stock_out.stock_out_type,
            'warehouse_name': stock_out.warehouse.name if stock_out.warehouse else '',
            'customer_name': stock_out.customer.name if stock_out.customer else '',
            'total_amount': stock_out.total_amount,
            'total_quantity': stock_out.total_quantity,
            'status': stock_out.get_status_display() if hasattr(stock_out, 'get_status_display') else stock_out.status,
        } for stock_out in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'stockout'
        }

    def handle_alert_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.inventory.models import InventoryAlert
        return {
            'type': 'count',
            'value': self._filter_alert_queryset(InventoryAlert.objects.all(), entities).count(),
            'data_type': 'alert'
        }

    def handle_alert_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.inventory.models import InventoryAlert
        queryset = self._filter_alert_queryset(
            InventoryAlert.objects.select_related('item', 'warehouse', 'handler').order_by('-create_time'),
            entities,
        )
        items = [{
            'id': alert.id,
            'product_name': alert.item.name if alert.item else '',
            'product_code': alert.item.code if alert.item else '',
            'warehouse_name': alert.warehouse.name if alert.warehouse else '',
            'alert_type': alert.get_alert_type_display() if hasattr(alert, 'get_alert_type_display') else alert.alert_type,
            'current_quantity': alert.current_quantity,
            'threshold_value': alert.threshold_value,
            'status': '已处理' if alert.status == 2 else ('已忽略' if alert.status == 3 else '未处理'),
        } for alert in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'alert'
        }

    def _filter_finance_order_record_queryset(self, queryset, entities: Dict[str, Any]):
        status = (entities or {}).get('status')
        if status in {'pending', 'partial', 'paid', 'overdue'}:
            queryset = queryset.filter(payment_status=status)
        return queryset

    def _filter_alert_queryset(self, queryset, entities: Dict[str, Any]):
        status = (entities or {}).get('status')
        status_mapping = {
            'pending': 1,
            '未处理': 1,
            'processed': 2,
            '已处理': 2,
            'ignored': 3,
            '已忽略': 3,
        }
        mapped_status = status_mapping.get(status)
        if mapped_status is not None:
            queryset = queryset.filter(status=mapped_status)
        return queryset

    def handle_contact_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.customer.models import Contact

        queryset = self._filter_contact_queryset(Contact.objects.select_related('customer'), user)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'contact'
        }

    def handle_contact_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.customer.models import Contact

        queryset = self._filter_contact_queryset(
            Contact.objects.select_related('customer').order_by('-is_primary', 'id'),
            user,
        )
        items = [{
            'id': contact.id,
            'name': contact.contact_person,
            'phone': contact.phone,
            'email': contact.email or '',
            'position': contact.position or '',
            'customer_name': contact.customer.name if contact.customer else '',
            'is_primary': contact.is_primary,
        } for contact in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'contact'
        }

    def handle_document_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import Document

        queryset = self._filter_document_queryset(Document.objects.all(), user)
        queryset = self._apply_document_filters(queryset, entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'document'
        }

    def handle_document_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import Document

        queryset = self._filter_document_queryset(
            Document.objects.select_related('author', 'category', 'department', 'current_reviewer').prefetch_related('target_users', 'target_departments'),
            user,
        )
        queryset = self._apply_document_filters(queryset, entities)
        items = [{
            'id': item.id,
            'title': item.title,
            'document_number': item.document_number,
            'category': item.category.name if item.category else '',
            'author': item.author.username if item.author else '',
            'department': item.department.name if item.department else '',
            'status': item.get_status_display() if hasattr(item, 'get_status_display') else item.status,
            'urgency': item.get_urgency_display() if hasattr(item, 'get_urgency_display') else item.urgency,
            'publish_time': item.publish_time.strftime('%Y-%m-%d %H:%M') if item.publish_time else '',
        } for item in queryset.order_by('-created_at')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'document'
        }

    def handle_document_category_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import DocumentCategory

        queryset = self._apply_active_status_filter(DocumentCategory.objects.all(), entities, 'is_active')
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'document_category'
        }

    def handle_document_category_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import DocumentCategory

        queryset = self._apply_active_status_filter(DocumentCategory.objects.all(), entities, 'is_active')
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'description': item.description or '',
            'is_active': item.is_active,
            'status': '启用' if item.is_active else '停用',
        } for item in queryset.order_by('code')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'document_category'
        }

    def handle_asset_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import Asset

        queryset = self._apply_office_status_filters(Asset.objects.all(), entities, {'normal', 'repair', 'scrap', 'lost'})
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'asset'
        }

    def handle_asset_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import Asset

        queryset = self._apply_office_status_filters(
            Asset.objects.select_related('category', 'brand', 'responsible_person', 'department'),
            entities,
            {'normal', 'repair', 'scrap', 'lost'},
        )
        items = [{
            'id': item.id,
            'asset_number': item.asset_number,
            'name': item.name,
            'category': item.category.name if item.category else '',
            'brand': item.brand.name if item.brand else '',
            'model': item.model or '',
            'location': item.location or '',
            'responsible_person': item.responsible_person.username if item.responsible_person else '',
            'department': item.department.name if item.department else '',
            'purchase_price': item.purchase_price,
            'status': item.get_status_display() if hasattr(item, 'get_status_display') else item.status,
        } for item in queryset.order_by('-created_at')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'asset'
        }

    def handle_asset_category_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import AssetCategory

        queryset = self._apply_active_status_filter(AssetCategory.objects.all(), entities, 'is_active')
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'asset_category'
        }

    def handle_asset_category_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import AssetCategory

        queryset = self._apply_active_status_filter(
            AssetCategory.objects.select_related('parent'),
            entities,
            'is_active',
        )
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'parent': item.parent.name if item.parent else '',
            'description': item.description or '',
            'sort_order': item.sort_order,
            'is_active': item.is_active,
            'status': '启用' if item.is_active else '停用',
        } for item in queryset.order_by('sort_order', 'name')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'asset_category'
        }

    def handle_asset_brand_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import AssetBrand

        queryset = self._apply_active_status_filter(AssetBrand.objects.all(), entities, 'is_active')
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'asset_brand'
        }

    def handle_asset_brand_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import AssetBrand

        queryset = self._apply_active_status_filter(AssetBrand.objects.all(), entities, 'is_active')
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'description': item.description or '',
            'is_active': item.is_active,
            'status': '启用' if item.is_active else '停用',
        } for item in queryset.order_by('name')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'asset_brand'
        }

    def handle_vehicle_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import Vehicle

        queryset = self._apply_office_status_filters(Vehicle.objects.all(), entities, {'normal', 'repair', 'scrap'})
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'vehicle'
        }

    def handle_vehicle_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import Vehicle

        queryset = self._apply_office_status_filters(
            Vehicle.objects.select_related('driver'),
            entities,
            {'normal', 'repair', 'scrap'},
        )
        items = [{
            'id': item.id,
            'license_plate': item.license_plate,
            'brand': item.brand,
            'model': item.model,
            'color': item.color,
            'driver': item.driver.username if item.driver else '',
            'purchase_price': item.purchase_price,
            'insurance_expire': item.insurance_expire.strftime('%Y-%m-%d') if item.insurance_expire else '',
            'annual_inspection': item.annual_inspection.strftime('%Y-%m-%d') if item.annual_inspection else '',
            'status': item.get_status_display() if hasattr(item, 'get_status_display') else item.status,
        } for item in queryset.order_by('-created_at')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'vehicle'
        }

    def handle_asset_repair_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import AssetRepair

        queryset = self._apply_asset_repair_filters(AssetRepair.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'asset_repair'
        }

    def handle_asset_repair_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import AssetRepair

        queryset = self._apply_asset_repair_filters(
            AssetRepair.objects.select_related('asset', 'reporter', 'repair_person'),
            entities,
        )
        items = [{
            'id': item.id,
            'asset_name': item.asset.name if item.asset else '',
            'asset_number': item.asset.asset_number if item.asset else '',
            'reporter': item.reporter.username if item.reporter else '',
            'repair_person': item.repair_person.username if item.repair_person else '',
            'fault_description': item.fault_description,
            'repair_description': item.repair_description,
            'repair_cost': item.repair_cost,
            'report_time': item.report_time.strftime('%Y-%m-%d %H:%M') if item.report_time else '',
            'status': item.get_status_display() if hasattr(item, 'get_status_display') else item.status,
        } for item in queryset.order_by('-report_time')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'asset_repair'
        }

    def handle_vehicle_maintenance_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import VehicleMaintenance

        queryset = self._apply_vehicle_maintenance_filters(VehicleMaintenance.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'vehicle_maintenance'
        }

    def handle_vehicle_maintenance_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import VehicleMaintenance

        queryset = self._apply_vehicle_maintenance_filters(
            VehicleMaintenance.objects.select_related('vehicle', 'operator'),
            entities,
        )
        items = [{
            'id': item.id,
            'license_plate': item.vehicle.license_plate if item.vehicle else '',
            'maintenance_type': item.get_maintenance_type_display() if hasattr(item, 'get_maintenance_type_display') else item.maintenance_type,
            'maintenance_date': item.maintenance_date.strftime('%Y-%m-%d') if item.maintenance_date else '',
            'mileage': item.mileage,
            'cost': item.cost,
            'service_provider': item.service_provider,
            'description': item.description,
            'operator': item.operator.username if item.operator else '',
        } for item in queryset.order_by('-maintenance_date')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'vehicle_maintenance'
        }

    def handle_vehicle_fee_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import VehicleFee

        queryset = self._apply_vehicle_fee_filters(VehicleFee.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'vehicle_fee'
        }

    def handle_vehicle_fee_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import VehicleFee

        queryset = self._apply_vehicle_fee_filters(
            VehicleFee.objects.select_related('vehicle', 'operator'),
            entities,
        )
        items = [{
            'id': item.id,
            'license_plate': item.vehicle.license_plate if item.vehicle else '',
            'fee_type': item.get_fee_type_display() if hasattr(item, 'get_fee_type_display') else item.fee_type,
            'amount': item.amount,
            'fee_date': item.fee_date.strftime('%Y-%m-%d') if item.fee_date else '',
            'description': item.description,
            'operator': item.operator.username if item.operator else '',
        } for item in queryset.order_by('-fee_date')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'vehicle_fee'
        }

    def handle_vehicle_oil_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import VehicleOil

        return {
            'type': 'count',
            'value': VehicleOil.objects.count(),
            'data_type': 'vehicle_oil'
        }

    def handle_vehicle_oil_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import VehicleOil

        queryset = VehicleOil.objects.select_related('vehicle', 'operator')
        items = [{
            'id': item.id,
            'license_plate': item.vehicle.license_plate if item.vehicle else '',
            'oil_amount': item.oil_amount,
            'oil_cost': item.oil_cost,
            'mileage': item.mileage,
            'oil_date': item.oil_date.strftime('%Y-%m-%d') if item.oil_date else '',
            'gas_station': item.gas_station,
            'operator': item.operator.username if item.operator else '',
        } for item in queryset.order_by('-oil_date')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'vehicle_oil'
        }

    def handle_seal_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import Seal

        queryset = self._apply_seal_filters(Seal.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'seal'
        }

    def handle_seal_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import Seal

        queryset = self._apply_seal_filters(Seal.objects.select_related('keeper'), entities)
        items = [{
            'id': item.id,
            'name': item.name,
            'seal_type': item.get_seal_type_display() if hasattr(item, 'get_seal_type_display') else item.seal_type,
            'keeper': item.keeper.username if item.keeper else '',
            'location': item.location or '',
            'is_active': item.is_active,
            'status': '启用' if item.is_active else '停用',
        } for item in queryset.order_by('name')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'seal'
        }

    def handle_seal_application_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import SealApplication

        queryset = self._apply_seal_application_filters(SealApplication.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'seal_application'
        }

    def handle_seal_application_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import SealApplication

        queryset = self._apply_seal_application_filters(
            SealApplication.objects.select_related('seal', 'applicant', 'approver'),
            entities,
        )
        items = [{
            'id': item.id,
            'seal_name': item.seal.name if item.seal else '',
            'document_title': item.document_title,
            'purpose': item.purpose,
            'applicant': item.applicant.username if item.applicant else '',
            'approver': item.approver.username if item.approver else '',
            'use_date': item.use_date.strftime('%Y-%m-%d') if item.use_date else '',
            'copies': item.copies,
            'status': item.get_status_display() if hasattr(item, 'get_status_display') else item.status,
        } for item in queryset.order_by('-created_at')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'seal_application'
        }

    def handle_project_document_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.project.models import ProjectDocument

        queryset = self._filter_project_document_queryset(
            ProjectDocument.objects.select_related('project', 'creator'),
            user,
        )
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'project_document',
        }

    def handle_project_document_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.project.models import ProjectDocument

        queryset = self._filter_project_document_queryset(
            ProjectDocument.objects.select_related(
                'project',
                'creator',
                'project__creator',
                'project__manager',
                'project__department',
            ),
            user,
        )
        items = [{
            'id': item.id,
            'title': item.title,
            'project_name': item.project.name if item.project else '',
            'project_code': item.project.code if item.project else '',
            'creator': item.creator.username if item.creator else '',
            'file_path': item.file_path or '',
            'create_time': item.create_time.strftime('%Y-%m-%d %H:%M') if item.create_time else '',
        } for item in queryset.order_by('-create_time')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'project_document',
        }

    def handle_project_stage_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.project.models import ProjectStage
        queryset = ProjectStage.objects.filter(is_active=True)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'project_stage',
        }

    def handle_project_stage_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.project.models import ProjectStage
        queryset = ProjectStage.objects.filter(is_active=True).order_by('sort_order', 'name')
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'description': item.description,
            'sort_order': item.sort_order,
            'is_active': item.is_active,
        } for item in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'project_stage',
        }

    def handle_project_category_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.project.models import ProjectCategory
        queryset = ProjectCategory.objects.filter(is_active=True)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'project_category',
        }

    def handle_project_category_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.project.models import ProjectCategory
        queryset = ProjectCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'description': item.description,
            'color': item.color,
            'sort_order': item.sort_order,
            'is_active': item.is_active,
        } for item in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'project_category',
        }

    def handle_work_type_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.project.models import WorkType
        queryset = WorkType.objects.filter(is_active=True)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'work_type',
        }

    def handle_work_type_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.project.models import WorkType
        queryset = WorkType.objects.filter(is_active=True).order_by('sort_order', 'name')
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'description': item.description,
            'hourly_rate': str(item.hourly_rate) if item.hourly_rate is not None else '',
            'sort_order': item.sort_order,
            'is_active': item.is_active,
        } for item in queryset[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'work_type',
        }

    def handle_payment_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import Payment

        queryset = self._apply_datetime_range_filter(Payment.objects.all(), entities, 'payment_date')
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'payment'
        }

    def handle_payment_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.finance.models import Expense, Payment

        queryset = self._apply_datetime_range_filter(Payment.objects.all(), entities, 'payment_date').order_by('-payment_date')
        expense_ids = list(queryset.values_list('expense_id', flat=True)[:5])
        expense_map = {
            expense.id: expense
            for expense in Expense.objects.filter(id__in=expense_ids)
        } if expense_ids else {}
        items = []
        for payment in queryset[:5]:
            expense = expense_map.get(payment.expense_id)
            items.append({
                'id': payment.id,
                'expense_id': payment.expense_id,
                'expense_code': expense.code if expense else '',
                'amount': payment.amount,
                'payment_date': payment.payment_date.strftime('%Y-%m-%d') if payment.payment_date else '',
                'remark': payment.remark or '',
            })
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'payment'
        }

    def handle_followup_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.customer.models import FollowRecord
        queryset = self._filter_followup_queryset(FollowRecord.objects.select_related('customer', 'follow_user'), user)
        queryset = self._apply_followup_filters(queryset, entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'followup'
        }

    def handle_followup_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.customer.models import FollowRecord
        queryset = self._filter_followup_queryset(FollowRecord.objects.select_related('customer', 'follow_user'), user)
        queryset = self._apply_followup_filters(queryset, entities)
        followup_list = [{
            'id': followup.id,
            'customer': followup.customer.name if followup.customer else '',
            'follow_type': followup.get_follow_type_display() if hasattr(followup, 'get_follow_type_display') else followup.follow_type,
            'follow_time': followup.follow_time.strftime('%Y-%m-%d %H:%M') if followup.follow_time else '',
            'next_follow_time': followup.next_follow_time.strftime('%Y-%m-%d %H:%M') if followup.next_follow_time else '',
            'creator': getattr(followup.follow_user, 'username', '') if followup.follow_user else ''
        } for followup in queryset[:5]]
        return {
            'type': 'list',
            'items': followup_list,
            'total': queryset.count(),
            'data_type': 'followup'
        }

    def handle_approval_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import Approval
        queryset = self._filter_approval_queryset(Approval.objects.all(), user)
        if entities.get('scope') == 'created_by_me':
            queryset = queryset.filter(applicant_id=getattr(user, 'id', None))
        queryset = self._apply_approval_filters(queryset, entities)
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
        if entities.get('scope') == 'created_by_me':
            queryset = queryset.filter(applicant_id=getattr(user, 'id', None))
        queryset = self._apply_approval_filters(queryset, entities)
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

    def handle_approval_type_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalType
        queryset = self._apply_approval_type_filters(ApprovalType.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'approval_type',
            'status': entities.get('status'),
        }

    def handle_approval_type_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalType
        queryset = self._apply_approval_type_filters(ApprovalType.objects.all(), entities)
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'status': '启用' if item.is_active else '停用',
            'description': item.description or '',
        } for item in queryset.order_by('sort_order', 'name')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'approval_type',
            'status': entities.get('status'),
        }

    def handle_approval_step_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalStep
        queryset = self._apply_approval_step_filters(
            ApprovalStep.objects.select_related('flow', 'approver').all(),
            entities,
        )
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'approval_step',
            'status': entities.get('step_type'),
        }

    def handle_approval_step_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalStep
        queryset = self._apply_approval_step_filters(
            ApprovalStep.objects.select_related('flow', 'approver').all(),
            entities,
        )
        items = [{
            'id': item.id,
            'step_name': item.step_name,
            'flow': item.flow.name if item.flow else '',
            'step_type': item.get_step_type_display() if hasattr(item, 'get_step_type_display') else item.step_type,
            'step_order': item.step_order,
            'approver': item.approver.username if item.approver else '',
        } for item in queryset.order_by('flow__name', 'step_order', 'id')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'approval_step',
            'status': entities.get('step_type'),
        }

    def handle_approval_record_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import Approval, ApprovalRecord

        queryset = ApprovalRecord.objects.select_related('approval', 'handler').all()
        if not getattr(user, 'is_superuser', False):
            approval_ids = self._filter_approval_queryset(Approval.objects.all(), user).values_list('id', flat=True)
            queryset = queryset.filter(approval_id__in=approval_ids)
        queryset = self._apply_approval_record_filters(queryset, entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'approval_record',
            'status': entities.get('action'),
        }

    def handle_approval_record_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import Approval, ApprovalRecord

        queryset = ApprovalRecord.objects.select_related('approval', 'handler').all()
        if not getattr(user, 'is_superuser', False):
            approval_ids = self._filter_approval_queryset(Approval.objects.all(), user).values_list('id', flat=True)
            queryset = queryset.filter(approval_id__in=approval_ids)
        queryset = self._apply_approval_record_filters(queryset, entities)
        items = [{
            'id': item.id,
            'approval_title': item.approval.title if item.approval else '未知审批',
            'step_name': item.step_name,
            'action': item.get_action_display() if hasattr(item, 'get_action_display') else item.action,
            'handler': item.handler.username if item.handler else '',
        } for item in queryset.order_by('-create_time', '-id')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'approval_record',
            'status': entities.get('action'),
        }

    def handle_approval_flow_edge_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalFlowEdge

        queryset = self._apply_approval_flow_edge_filters(
            ApprovalFlowEdge.objects.select_related('flow', 'from_step', 'to_step').all(),
            entities,
        )
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'approval_flow_edge',
            'status': entities.get('edge_type'),
        }

    def handle_approval_flow_edge_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalFlowEdge

        queryset = self._apply_approval_flow_edge_filters(
            ApprovalFlowEdge.objects.select_related('flow', 'from_step', 'to_step').all(),
            entities,
        )
        items = [{
            'id': item.id,
            'flow': item.flow.name if item.flow else '',
            'from_node': item.from_step.step_name if item.from_step else item.from_node,
            'to_node': item.to_step.step_name if item.to_step else item.to_node,
            'edge_type': item.get_edge_type_display() if hasattr(item, 'get_edge_type_display') else item.edge_type,
            'label': item.label or '',
        } for item in queryset.order_by('flow__name', 'sort_order', 'id')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'approval_flow_edge',
            'status': entities.get('edge_type'),
        }

    def handle_approval_flow_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalFlow
        queryset = self._apply_approval_type_filters(ApprovalFlow.objects.all(), entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'approval_flow',
        }

    def handle_approval_flow_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.approval.models import ApprovalFlow
        queryset = self._apply_approval_type_filters(
            ApprovalFlow.objects.select_related('approval_type').all(),
            entities,
        )
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
        queryset = self._apply_approval_task_filters(queryset, entities)
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
        queryset = self._apply_approval_task_filters(queryset, entities)
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

    def handle_workhour_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.project.models import WorkHour

        queryset = self._filter_workhour_queryset(
            WorkHour.objects.select_related('user', 'task', 'task__project'),
            user,
        )
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'workhour',
        }

    def handle_workhour_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.project.models import WorkHour

        queryset = self._filter_workhour_queryset(
            WorkHour.objects.select_related('user', 'task', 'task__project'),
            user,
        )
        items = [{
            'id': item.id,
            'user_name': item.user.username if item.user else '',
            'task_title': item.task.title if item.task else '',
            'project_name': item.task.project.name if item.task and item.task.project else '无项目',
            'work_date': item.work_date.strftime('%Y-%m-%d') if item.work_date else '',
            'hours': item.hours,
            'description': item.description,
        } for item in queryset.order_by('-work_date', '-create_time')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'workhour',
        }

    def handle_task_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.task.models import Task
        queryset = self._filter_task_queryset(Task.objects.all(), user)
        queryset = self._apply_task_filters(queryset, entities, user)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'task',
        }

    def handle_task_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.task.models import Task
        queryset = self._filter_task_queryset(Task.objects.select_related('assignee'), user)
        queryset = self._apply_task_filters(queryset, entities, user)
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
        if entities.get('status') == 'unread':
            queryset = queryset.filter(user_relations__user=user, user_relations__is_read=False)
        elif entities.get('status') == 'read':
            queryset = queryset.filter(user_relations__user=user, user_relations__is_read=True)
        elif entities.get('status') == 'starred':
            queryset = queryset.filter(user_relations__user=user, user_relations__is_starred=True)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'message',
            'status': entities.get('status'),
        }

    def handle_message_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.message.models import Message, MessageUserRelation
        queryset = self._filter_message_queryset(
            Message.objects.select_related('sender').filter(is_active=True),
            user,
        )
        if entities.get('status') == 'unread':
            queryset = queryset.filter(user_relations__user=user, user_relations__is_read=False)
        elif entities.get('status') == 'read':
            queryset = queryset.filter(user_relations__user=user, user_relations__is_read=True)
        elif entities.get('status') == 'starred':
            queryset = queryset.filter(user_relations__user=user, user_relations__is_starred=True)
        message_ids = list(queryset.values_list('id', flat=True)[:5])
        relation_map = {
            relation.message_id: relation
            for relation in MessageUserRelation.objects.filter(user=user, message_id__in=message_ids)
        } if message_ids else {}
        items_queryset = queryset.filter(id__in=message_ids).order_by('-created_at') if message_ids else queryset.none()
        items = [{
            'id': item.id,
            'title': item.title,
            'sender': item.sender.username if item.sender else '',
            'is_read': relation_map.get(item.id).is_read if relation_map.get(item.id) else False,
            'is_starred': relation_map.get(item.id).is_starred if relation_map.get(item.id) else False,
        } for item in items_queryset]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'message',
            'status': entities.get('status'),
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

    def handle_meeting_room_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.oa.models import MeetingRoom

        queryset = self._apply_meeting_room_filters(
            MeetingRoom.objects.filter(is_deleted=False),
            entities,
        )
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'meeting_room',
        }

    def handle_meeting_room_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.oa.models import MeetingRoom

        queryset = self._apply_meeting_room_filters(
            MeetingRoom.objects.select_related('manager').filter(is_deleted=False),
            entities,
        )
        items = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'location': item.location,
            'capacity': item.capacity,
            'equipment': item.get_equipment_display() if hasattr(item, 'get_equipment_display') else '',
            'manager': item.manager.username if item.manager else '',
            'status': item.get_status_display() if hasattr(item, 'get_status_display') else item.status,
        } for item in queryset.order_by('code')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'meeting_room',
        }

    def handle_meeting_reservation_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import MeetingReservation

        queryset = self._filter_meeting_reservation_queryset(MeetingReservation.objects.all(), user)
        queryset = self._apply_meeting_reservation_filters(queryset, entities)
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'meeting_reservation',
            'status': entities.get('status'),
        }

    def handle_meeting_reservation_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.system.models import MeetingReservation

        queryset = self._filter_meeting_reservation_queryset(
            MeetingReservation.objects.select_related('meeting_room', 'organizer'),
            user,
        )
        queryset = self._apply_meeting_reservation_filters(queryset, entities)
        items = [{
            'id': item.id,
            'title': item.title,
            'meeting_room': item.meeting_room.name if item.meeting_room else '',
            'organizer': item.organizer.username if item.organizer else '',
            'start_time': item.start_time.strftime('%Y-%m-%d %H:%M') if item.start_time else '',
            'end_time': item.end_time.strftime('%Y-%m-%d %H:%M') if item.end_time else '',
            'status': item.get_status_display() if hasattr(item, 'get_status_display') else item.status,
        } for item in queryset.order_by('-start_time')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'meeting_reservation',
            'status': entities.get('status'),
        }

    def handle_meeting_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.oa.models import MeetingRecord
        queryset = self._filter_meeting_queryset(MeetingRecord.objects.all(), user)
        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                queryset = queryset.filter(meeting_date__range=(start_at, end_at))
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
        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                queryset = queryset.filter(meeting_date__range=(start_at, end_at))
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

    def handle_meeting_minutes_count(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import MeetingMinutes

        queryset = self._filter_meeting_minutes_queryset(
            MeetingMinutes.objects.select_related('recorder', 'user'),
            user,
            entities,
        )
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': 'meeting_minutes',
        }

    def handle_meeting_minutes_list(
            self, entities: Dict[str, Any], user: User) -> Dict[str, Any]:
        from apps.personal.models import MeetingMinutes

        queryset = self._filter_meeting_minutes_queryset(
            MeetingMinutes.objects.select_related('recorder', 'user'),
            user,
            entities,
        )
        items = [{
            'id': item.id,
            'title': item.title,
            'meeting_type': item.meeting_type_display if hasattr(item, 'meeting_type_display') else item.meeting_type,
            'meeting_date': item.meeting_date.strftime('%Y-%m-%d %H:%M') if item.meeting_date else '',
            'recorder': item.recorder.username if item.recorder else '',
            'is_public': item.is_public,
        } for item in queryset.order_by('-meeting_date', '-id')[:5]]
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': 'meeting_minutes',
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
        queryset = self._apply_disk_filters(queryset, entities, user)
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
        queryset = self._apply_disk_filters(queryset, entities, user)
        status = entities.get('status')
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
        if entities.get('scope') == 'created_by_me':
            queryset = queryset.filter(creator=user)
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
        if entities.get('scope') == 'created_by_me':
            queryset = queryset.filter(creator=user)
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
            'approval_type': '审批类型',
            'approval_step': '审批步骤',
            'approval_record': '审批记录',
            'approval_flow_edge': '流程连线',
            'notice': '通知公告',
            'document': '文档',
            'document_category': '公文分类',
            'asset': '固定资产',
            'asset_category': '资产分类',
            'asset_brand': '资产品牌',
            'asset_repair': '资产报修记录',
            'vehicle': '车辆',
            'vehicle_maintenance': '车辆维修保养记录',
            'vehicle_fee': '车辆费用记录',
            'vehicle_oil': '车辆油耗记录',
            'seal': '印章',
            'seal_application': '用章申请',
            'department': '部门',
            'message': '站内消息',
            'employee': '员工',
            'finance_expense': '报销',
            'finance_invoice': '发票',
            'finance_income': '回款',
            'finance_order_record': '订单财务记录',
            'finance_account': '资金账户',
            'finance_budget': '预算',
            'finance_receivable': '应收账款',
            'finance_payable': '应付账款',
            'finance_bank_transaction': '银行流水',
            'ai_model_config': 'AI模型配置',
            'ai_knowledge_base': '知识库',
            'ai_task': 'AI任务',
            'ai_workflow': 'AI工作流',
            'supply_chain_forecast': '需求预测计划',
            'supply_chain_outsource': '委外发料单',
            'supply_chain_pr_review': 'PR审核任务',
            'supply_chain_price_review': '单价复核单',
            'supply_chain_sample': '打样申请',
            'production_plan': '生产计划',
            'production_task': '生产任务',
            'production_equipment': '生产设备',
            'production_procedure': '生产工序',
            'reward_punishment': '奖罚记录',
            'employee_care': '员工关怀',
            'procedureset': '工序集',
            'bom': 'BOM',
            'process': '工艺路线',
            'quality_check': '质量检查',
            'datacollection': '数据采集',
            'approval_flow': '审批流程',
            'approval_task': '待办审批',
            'meeting_room': '会议室',
            'meeting_reservation': '会议室预订',
            'meeting': '会议',
            'schedule': '工作日程',
            'enterprise': '企业信息',
            'position': '岗位职称',
            'work_record': '工作记录',
            'work_report': '工作汇报',
            'personal_task': '个人任务',
            'personal_note': '个人笔记',
            'personal_contact': '个人通讯录',
            'disk': '网盘文件',
            'disk_folder': '网盘文件夹',
            'disk_share': '网盘分享',
            'project_document': '项目文档',
            'project_stage': '项目阶段',
            'project_category': '项目分类',
            'work_type': '工作类型',
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

            item_str = '、'.join(str(item) for item in item_list if item is not None)

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
            elif data_type == 'finance_account':
                name = item.get('name', '未知')
                balance = item.get('current_balance', 0)
                status = item.get('status', '')
                return f"{name}（余额¥{balance:,.2f}，{status}）"
            elif data_type == 'finance_budget':
                name = item.get('name', '未知')
                amount = item.get('budget_amount', 0)
                used = item.get('used_amount', 0)
                return f"{name}（预算¥{amount:,.2f}，已用¥{used:,.2f}）"
            elif data_type == 'finance_receivable':
                code = item.get('code', '未知')
                amount = item.get('amount', 0)
                status = item.get('status', '')
                return f"{code}（应收¥{amount:,.2f}，{status}）"
            elif data_type == 'finance_payable':
                code = item.get('code', '未知')
                amount = item.get('amount', 0)
                status = item.get('status', '')
                return f"{code}（应付¥{amount:,.2f}，{status}）"
            elif data_type == 'finance_bank_transaction':
                no = item.get('transaction_no', '未知')
                direction = item.get('direction', '')
                amount = item.get('amount', 0)
                return f"{no}（{direction}，¥{amount:,.2f}）"
            elif data_type == 'ai_model_config':
                name = item.get('name', '未知')
                provider = item.get('provider', '')
                primary_model = item.get('primary_model', '')
                active = '启用' if item.get('is_active') else '停用'
                parts = [part for part in [provider, primary_model, active] if part]
                if parts:
                    return f"{name}（{'，'.join(parts)}）"
                return name
            elif data_type == 'ai_knowledge_base':
                name = item.get('name', '未知')
                status = item.get('status', '')
                return f"{name}（{status}）"
            elif data_type == 'ai_task':
                task_type = item.get('task_type', '未知')
                status = item.get('status', '')
                user = item.get('user', '')
                if user:
                    return f"{task_type}（{user}，{status}）"
                return f"{task_type}（{status}）"
            elif data_type == 'ai_workflow':
                name = item.get('name', '未知')
                status = item.get('status', '')
                visibility = '公开' if item.get('is_public') else '私有'
                return f"{name}（{status}，{visibility}）"
            elif data_type == 'supply_chain_forecast':
                name = item.get('name', '未知')
                code = item.get('code', '')
                status = item.get('status', '')
                if code:
                    return f"{name}（{code}，{status}）"
                return f"{name}（{status}）"
            elif data_type == 'supply_chain_outsource':
                code = item.get('code', '未知')
                quantity = item.get('quantity', 0)
                status = item.get('status', '')
                product = item.get('product', '')
                if product:
                    return f"{code}（{product}，数量{quantity}，{status}）"
                return f"{code}（数量{quantity}，{status}）"
            elif data_type == 'supply_chain_pr_review':
                title = item.get('title', item.get('code', '未知'))
                code = item.get('code', '')
                status = item.get('status', '')
                abnormal = '异常' if item.get('is_abnormal') else '正常'
                if code:
                    return f"{title}（{code}，{abnormal}，{status}）"
                return f"{title}（{abnormal}，{status}）"
            elif data_type == 'supply_chain_price_review':
                code = item.get('code', '未知')
                price = item.get('quoted_price', 0)
                status = item.get('status', '')
                item_name = item.get('item_name', '')
                if item_name:
                    return f"{code}（{item_name}，报价¥{price:,.4f}，{status}）"
                return f"{code}（报价¥{price:,.4f}，{status}）"
            elif data_type == 'supply_chain_sample':
                material = item.get('material_name', item.get('code', '未知'))
                code = item.get('code', '')
                quantity = item.get('quantity', 0)
                status = item.get('status', '')
                if code:
                    return f"{material}（{code}，数量{quantity}，{status}）"
                return f"{material}（数量{quantity}，{status}）"
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
            elif data_type == 'approval_type':
                name = item.get('name', '未知')
                code = item.get('code', '')
                status = item.get('status', '')
                if code:
                    return f"{name}（{code}，{status}）"
                return f"{name}（{status}）"
            elif data_type == 'approval_step':
                step_name = item.get('step_name', '未知步骤')
                flow = item.get('flow', '')
                step_type = item.get('step_type', '')
                if flow and step_type:
                    return f"{step_name}（{flow}，{step_type}）"
                if step_type:
                    return f"{step_name}（{step_type}）"
                return step_name
            elif data_type == 'approval_record':
                title = item.get('approval_title', '未知审批')
                action = item.get('action', '')
                step_name = item.get('step_name', '')
                if step_name:
                    return f"{title}（{step_name}，{action}）"
                return f"{title}（{action}）"
            elif data_type == 'approval_flow_edge':
                flow = item.get('flow', '未知流程')
                from_node = item.get('from_node', '')
                to_node = item.get('to_node', '')
                edge_type = item.get('edge_type', '')
                return f"{flow}（{from_node}->{to_node}，{edge_type}）"
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
            elif data_type == 'meeting_room':
                name = item.get('name', '未知会议室')
                location = item.get('location', '')
                capacity = item.get('capacity', 0)
                status = item.get('status', '')
                if location:
                    return f"{name}（{location}，{capacity}人，{status}）"
                return f"{name}（{capacity}人，{status}）"
            elif data_type == 'meeting_reservation':
                title = item.get('title', '未知预订')
                room = item.get('meeting_room', '')
                start_time = item.get('start_time', '')
                status = item.get('status', '')
                parts = [part for part in [room, start_time, status] if part]
                if parts:
                    return f"{title}（{'，'.join(parts)}）"
                return title
            elif data_type == 'notice':
                title = item.get('title', '未知')
                publisher = item.get('publisher', '')
                date = item.get('publish_date', '')
                if publisher:
                    return f"{title}（{publisher}，{date}）"
                return f"{title}（{date}）"
            elif data_type == 'project_document':
                title = item.get('title', '未知')
                project_name = item.get('project_name', '')
                creator = item.get('creator', '')
                if project_name and creator:
                    return f"{title}（{project_name}，{creator}）"
                if project_name:
                    return f"{title}（{project_name}）"
                return title
            elif data_type in {'project_stage', 'project_category', 'work_type', 'document_category', 'asset_category', 'asset_brand'}:
                name = item.get('name', '未知')
                code = item.get('code', '')
                description = item.get('description', '')
                status = item.get('status', '')
                parts = []
                if code:
                    parts.append(code)
                if status:
                    parts.append(status)
                if description:
                    parts.append(description[:20])
                if parts:
                    return f"{name}（{'，'.join(parts)}）"
                return name
            elif data_type == 'document':
                title = item.get('title', '未知')
                size = item.get('file_size', 0)
                user = item.get('upload_user', '')
                if user:
                    return f"{title}（{user}，{size}）"
                return f"{title}（{size}）"
            elif data_type == 'asset':
                name = item.get('name', '未知')
                asset_number = item.get('asset_number', '')
                status = item.get('status', '')
                if asset_number:
                    return f"{name}（{asset_number}，{status}）"
                return f"{name}（{status}）"
            elif data_type == 'asset_repair':
                asset_name = item.get('asset_name', '未知资产')
                fault = item.get('fault_description', '')
                status = item.get('status', '')
                if fault:
                    return f"{asset_name}（{fault[:20]}，{status}）"
                return f"{asset_name}（{status}）"
            elif data_type == 'vehicle':
                license_plate = item.get('license_plate', '未知')
                brand = item.get('brand', '')
                model = item.get('model', '')
                status = item.get('status', '')
                vehicle_name = ' '.join(part for part in [brand, model] if part)
                if vehicle_name:
                    return f"{license_plate}（{vehicle_name}，{status}）"
                return f"{license_plate}（{status}）"
            elif data_type == 'vehicle_maintenance':
                license_plate = item.get('license_plate', '未知车辆')
                maintenance_type = item.get('maintenance_type', '')
                cost = item.get('cost', 0)
                description = item.get('description', '')
                if description:
                    return f"{license_plate}（{maintenance_type}，¥{cost}，{description[:20]}）"
                return f"{license_plate}（{maintenance_type}，¥{cost}）"
            elif data_type == 'vehicle_fee':
                license_plate = item.get('license_plate', '未知车辆')
                fee_type = item.get('fee_type', '')
                amount = item.get('amount', 0)
                fee_date = item.get('fee_date', '')
                if fee_date:
                    return f"{license_plate}（{fee_type}，¥{amount}，{fee_date}）"
                return f"{license_plate}（{fee_type}，¥{amount}）"
            elif data_type == 'vehicle_oil':
                license_plate = item.get('license_plate', '未知车辆')
                oil_amount = item.get('oil_amount', 0)
                oil_cost = item.get('oil_cost', 0)
                gas_station = item.get('gas_station', '')
                if gas_station:
                    return f"{license_plate}（{oil_amount}升，¥{oil_cost}，{gas_station}）"
                return f"{license_plate}（{oil_amount}升，¥{oil_cost}）"
            elif data_type == 'seal':
                name = item.get('name', '未知')
                seal_type = item.get('seal_type', '')
                status = item.get('status', '')
                if seal_type:
                    return f"{name}（{seal_type}，{status}）"
                return f"{name}（{status}）"
            elif data_type == 'seal_application':
                title = item.get('document_title', '未知')
                seal_name = item.get('seal_name', '')
                status = item.get('status', '')
                if seal_name:
                    return f"{title}（{seal_name}，{status}）"
                return f"{title}（{status}）"
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
            elif data_type == 'reward_punishment':
                title = item.get('title', '未知')
                record_type = item.get('type', '')
                employee = item.get('employee', '')
                if employee:
                    return f"{title}（{employee}，{record_type}）"
                return f"{title}（{record_type}）"
            elif data_type == 'employee_care':
                title = item.get('title', '未知')
                care_type = item.get('care_type', '')
                employee = item.get('employee', '')
                if employee:
                    return f"{title}（{employee}，{care_type}）"
                return f"{title}（{care_type}）"
            elif data_type == 'procedureset':
                name = item.get('name', '未知')
                code = item.get('code', '')
                status = item.get('status', '')
                if code:
                    return f"{name}（{code}，{status}）"
                return f"{name}（{status}）"
            elif data_type == 'bom':
                name = item.get('name', '未知')
                code = item.get('code', '')
                status = item.get('status', '')
                if code:
                    return f"{name}（{code}，{status}）"
                return f"{name}（{status}）"
            elif data_type == 'process':
                name = item.get('name', '未知')
                code = item.get('code', '')
                status = item.get('status', '')
                if code:
                    return f"{name}（{code}，{status}）"
                return f"{name}（{status}）"
            elif data_type == 'quality_check':
                task = item.get('task', '未知任务')
                result = item.get('result', '')
                return f"{task}（{result}）"
            elif data_type == 'datacollection':
                parameter = item.get('parameter_name', '未知参数')
                value = item.get('parameter_value', '')
                unit = item.get('unit', '')
                status = item.get('status', '')
                return f"{parameter}（{value}{unit}，{status}）"
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
            elif data_type == 'enterprise':
                name = item.get('name', item.get('title', '未知'))
                city = item.get('city', '')
                if city:
                    return f"{name}（{city}）"
                return name
            elif data_type == 'position':
                name = item.get('name', item.get('title', '未知'))
                desc = item.get('description', '')
                if desc:
                    return f"{name}（{desc}）"
                return name
            elif data_type == 'work_record':
                title = item.get('title', '未知')
                work_type = item.get('work_type', '')
                work_date = item.get('work_date', '')
                if work_date:
                    return f"{title}（{work_date}，{work_type}）"
                return f"{title}（{work_type}）"
            elif data_type == 'personal_task':
                title = item.get('title', '未知')
                status = item.get('status', '')
                due_date = item.get('due_date', '')
                if due_date:
                    return f"{title}（{status}，截止：{due_date}）"
                return f"{title}（{status}）"
            elif data_type == 'personal_note':
                title = item.get('title', '未知')
                category = item.get('category', '')
                important = '★' if item.get('is_important') else ''
                if important:
                    return f"{important} {title}（{category}）"
                return f"{title}（{category}）"
            elif data_type == 'personal_contact':
                name = item.get('name', '未知')
                company = item.get('company', '')
                phone = item.get('phone', '')
                if company:
                    return f"{name}（{company}，{phone}）"
                return f"{name}（{phone}）"
            elif data_type == 'work_report':
                title = item.get('title', '未知')
                report_type = item.get('report_type', '')
                submitted = '已提交' if item.get('is_submitted') else '草稿'
                return f"{title}（{report_type}，{submitted}）"
            else:
                return item.get(
                    'name', item.get(
                        'title', item.get(
                            'id', '未知')))
        except Exception as e:
            logger.warning(f"格式化列表项失败: {e}")
            return str(item.get('name', item.get('id', '未知')))

    def _filter_approval_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(
            Q(applicant_id=getattr(user, 'id', None)) |
            Q(reviewer=user) |
            Q(tasks__handler=user)
        ).distinct()

    def _apply_approval_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'ongoing':
            queryset = queryset.filter(status__in=[0, 1])
        elif status == 'approved':
            queryset = queryset.filter(status=2)
        elif status == 'rejected':
            queryset = queryset.filter(status=3)
        elif status == 'cancelled':
            queryset = queryset.filter(status=4)
        return queryset

    def _apply_approval_type_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        keyword = entities.get('keyword') or entities.get('name')
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        return queryset

    def _apply_approval_step_filters(self, queryset, entities):
        step_type = entities.get('step_type')
        if step_type:
            queryset = queryset.filter(step_type=step_type)
        flow_id = entities.get('flow_id')
        if flow_id:
            queryset = queryset.filter(flow_id=flow_id)
        flow_name = entities.get('flow_name')
        if flow_name:
            queryset = queryset.filter(flow__name__icontains=flow_name)
        return queryset

    def _apply_approval_record_filters(self, queryset, entities):
        action = entities.get('action')
        if action:
            queryset = queryset.filter(action=action)
        flow_name = entities.get('flow_name')
        if flow_name:
            queryset = queryset.filter(approval__flow__name__icontains=flow_name)
        return self._apply_datetime_range_filter(queryset, entities, 'create_time')

    def _apply_approval_flow_edge_filters(self, queryset, entities):
        edge_type = entities.get('edge_type')
        if edge_type:
            queryset = queryset.filter(edge_type=edge_type)
        flow_id = entities.get('flow_id')
        if flow_id:
            queryset = queryset.filter(flow_id=flow_id)
        flow_name = entities.get('flow_name')
        if flow_name:
            queryset = queryset.filter(flow__name__icontains=flow_name)
        return queryset

    def _filter_approval_task_queryset(self, queryset, user):
        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(handler=user)

    def _apply_approval_task_filters(self, queryset, entities):
        status = entities.get('status')
        if status in {'pending', '待处理', '待审批'}:
            queryset = queryset.filter(status='pending')
        elif status in {'completed', '已审批', '已处理'}:
            queryset = queryset.filter(status='completed')
        elif status == 'cancelled':
            queryset = queryset.filter(status='cancelled')
        return queryset

    def _filter_workhour_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(
            Q(user=user) |
            Q(task__assignee=user) |
            Q(task__creator=user) |
            Q(task__project__manager=user)
        ).distinct()

    def _filter_task_queryset(self, queryset, user):
        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(assignee_id=getattr(user, 'id', None))

    def _apply_task_filters(self, queryset, entities, user):
        scope = entities.get('scope')
        if scope == 'owned_by_me':
            queryset = queryset.filter(assignee_id=getattr(user, 'id', None))

        status = entities.get('status')
        if status == 'completed':
            queryset = queryset.filter(status=1)
        elif status in {'pending', 'todo'}:
            queryset = queryset.filter(status=0)
        return queryset

    def _filter_message_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(
            Q(user=user) |
            Q(is_broadcast=True) |
            Q(user_relations__user=user)
        ).distinct()

    def _filter_meeting_reservation_queryset(self, queryset, user):
        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(organizer=user)


    def _filter_followup_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset.filter(delete_time=0, customer__delete_time=0)
        user_id = getattr(user, 'id', None)
        return queryset.filter(
            Q(follow_user=user) |
            Q(customer__belong_uid=user_id) |
            build_csv_membership_q('customer__share_ids', user_id)
        ).filter(
            delete_time=0,
            customer__delete_time=0,
        ).distinct()

    def _apply_followup_filters(self, queryset, entities):
        follow_type = entities.get('follow_type')
        if follow_type:
            queryset = queryset.filter(follow_type=follow_type)
        return queryset

    def _filter_contact_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset
        return queryset.filter(
            Q(customer__belong_uid=getattr(user, 'id', None)) |
            build_csv_membership_q('customer__share_ids', getattr(user, 'id', None))
        ).filter(customer__delete_time=0).distinct()

    def _filter_document_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset

        user_dept_id = self._get_user_department_id(user)
        published_scope = (
            Q(status='published') &
            (
                Q(target_users__id=user.id) |
                (Q(target_departments__id=user_dept_id) if user_dept_id else Q(pk__in=[])) |
                (Q(target_users__isnull=True) & Q(target_departments__isnull=True))
            )
        )
        return queryset.filter(
            Q(author=user) |
            Q(current_reviewer=user) |
            published_scope
        ).distinct()

    def _apply_document_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'approved':
            queryset = queryset.filter(status='approved')
        elif status == 'published':
            queryset = queryset.filter(status='published')
        elif status == 'draft':
            queryset = queryset.filter(status='draft')
        elif status == 'pending':
            queryset = queryset.filter(status__in=['pending', 'reviewing'])
        elif status == 'rejected':
            queryset = queryset.filter(status='rejected')
        return queryset

    def _filter_project_document_queryset(self, queryset, user):
        from django.db.models import Q

        if getattr(user, 'is_superuser', False):
            return queryset

        user_dept_id = self._get_user_department_id(user)
        permission_q = (
            Q(creator=user) |
            Q(project__creator=user) |
            Q(project__manager=user) |
            Q(project__members=user)
        )
        if user_dept_id:
            permission_q |= Q(project__department_id=user_dept_id)

        return queryset.filter(
            permission_q,
            delete_time__isnull=True,
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

    def _filter_meeting_minutes_queryset(self, queryset, user, entities):
        from django.db.models import Q

        if not getattr(user, 'is_superuser', False):
            if entities.get('scope') == 'owned_by_me':
                queryset = queryset.filter(Q(user=user) | Q(recorder=user))
            else:
                queryset = queryset.filter(Q(user=user) | Q(recorder=user) | Q(is_public=True))

        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                queryset = queryset.filter(meeting_date__range=(start_at, end_at))
        return queryset.distinct()

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

    def _apply_disk_filters(self, queryset, entities, user):
        from django.db.models import Q

        scope = entities.get('scope')
        if scope == 'shared_to_me':
            user_dept_id = self._get_user_department_id(user)
            scope_filter = Q(shared_users__id=user.id) | Q(folder__shared_users__id=user.id)
            if user_dept_id:
                scope_filter |= Q(shared_departments__id=user_dept_id) | Q(folder__shared_departments__id=user_dept_id)
            queryset = queryset.filter(scope_filter).exclude(owner=user).distinct()

        status = entities.get('status')
        if status == 'starred':
            queryset = queryset.filter(is_starred=True)
        return queryset

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

        notice_type = entities.get('notice_type')
        if notice_type in {'company', 'system', 'urgent'}:
            queryset = queryset.filter(notice_type=notice_type)

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

    def _apply_production_plan_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'pending':
            queryset = queryset.filter(status=1)
        elif status == 'approved':
            queryset = queryset.filter(status=2)
        elif status == 'in_progress':
            queryset = queryset.filter(status=3)
        elif status == 'completed':
            queryset = queryset.filter(status=4)
        elif status == 'cancelled':
            queryset = queryset.filter(status=5)
        elif status == 'paused':
            queryset = queryset.filter(status=6)

        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                queryset = queryset.filter(plan_start_date__range=(start_at.date(), end_at.date()))
        return queryset

    def _apply_production_task_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'pending':
            queryset = queryset.filter(status=1)
        elif status == 'in_progress':
            queryset = queryset.filter(status=2)
        elif status == 'completed':
            queryset = queryset.filter(status=3)
        elif status == 'paused':
            queryset = queryset.filter(status=4)
        elif status == 'cancelled':
            queryset = queryset.filter(status=5)
        elif status == 'unfinished':
            queryset = queryset.filter(status__in=[1, 2, 4, 6])

        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                queryset = queryset.filter(plan_start_time__range=(start_at, end_at))
        return queryset

    def _apply_production_equipment_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'normal':
            queryset = queryset.filter(status=1)
        elif status == 'maintenance':
            queryset = queryset.filter(status=2)
        elif status == 'disabled':
            queryset = queryset.filter(status=3)
        elif status == 'scrapped':
            queryset = queryset.filter(status=4)
        return queryset

    def _apply_active_status_filter(self, queryset, entities, field_name):
        status = entities.get('status')
        if status == 'active':
            return queryset.filter(**{field_name: True})
        if status == 'inactive':
            return queryset.filter(**{field_name: False})
        return queryset

    def _apply_employee_filters(self, queryset, entities):
        status = entities.get('status')
        status_mapping = {
            'pending': -1,
            'disabled': 0,
            'active': 1,
            'inactive': 2,
        }
        mapped_status = status_mapping.get(status, status if isinstance(status, int) else None)
        if mapped_status is not None:
            queryset = queryset.filter(status=mapped_status)
        return queryset

    def _apply_reward_punishment_filters(self, queryset, entities):
        record_type = entities.get('type')
        if record_type in {'reward', 'punishment'}:
            queryset = queryset.filter(type=record_type)
        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                queryset = queryset.filter(
                    effective_date__range=(start_at.date(), (end_at - timedelta(seconds=1)).date())
                )
        return queryset

    def _apply_employee_care_filters(self, queryset, entities):
        care_type = entities.get('care_type')
        if care_type:
            queryset = queryset.filter(care_type=care_type)
        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                queryset = queryset.filter(
                    care_date__range=(start_at.date(), (end_at - timedelta(seconds=1)).date())
                )
        return queryset

    def _apply_process_filters(self, queryset, entities):
        status_mapping = {
            'pending': 1,
            'approved': 2,
            'in_progress': 3,
            'completed': 4,
            'cancelled': 5,
        }
        status = entities.get('status')
        mapped_status = status_mapping.get(status, status if isinstance(status, int) else None)
        if mapped_status is not None:
            queryset = queryset.filter(status=mapped_status)
        return queryset

    def _apply_quality_check_filters(self, queryset, entities):
        status = entities.get('status')
        status_mapping = {
            'qualified': 1,
            'unqualified': 2,
            'pending': 3,
        }
        mapped_status = status_mapping.get(status, status if isinstance(status, int) else None)
        if mapped_status is not None:
            queryset = queryset.filter(result=mapped_status)
        return self._apply_datetime_range_filter(queryset, entities, 'check_time')

    def _apply_datacollection_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'normal':
            queryset = queryset.filter(is_normal=True)
        elif status == 'abnormal':
            queryset = queryset.filter(is_normal=False)
        return self._apply_datetime_range_filter(queryset, entities, 'collect_time')

    def _apply_department_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'active':
            queryset = queryset.filter(status=1)
        elif status == 'inactive':
            queryset = queryset.filter(status=0)
        return queryset

    def _apply_office_status_filters(self, queryset, entities, allowed_statuses):
        status = entities.get('status')
        if status in allowed_statuses:
            queryset = queryset.filter(status=status)
        return queryset

    def _apply_asset_repair_filters(self, queryset, entities):
        status = entities.get('status')
        if status in {'pending', 'processing', 'completed', 'cancelled'}:
            queryset = queryset.filter(status=status)
        return queryset

    def _apply_vehicle_maintenance_filters(self, queryset, entities):
        maintenance_type = entities.get('maintenance_type')
        if maintenance_type in {'repair', 'maintain'}:
            queryset = queryset.filter(maintenance_type=maintenance_type)
        return queryset

    def _apply_vehicle_fee_filters(self, queryset, entities):
        fee_type = entities.get('fee_type')
        if fee_type in {'fuel', 'insurance', 'tax', 'parking', 'toll', 'fine', 'other'}:
            queryset = queryset.filter(fee_type=fee_type)
        return queryset

    def _apply_meeting_room_filters(self, queryset, entities):
        status = entities.get('status')
        if status in {'active', 'inactive', 'pending', 'deleted'}:
            queryset = queryset.filter(status=status)
        for field_name in ['has_projector', 'has_whiteboard', 'has_tv', 'has_phone', 'has_wifi']:
            if field_name in entities:
                queryset = queryset.filter(**{field_name: bool(entities[field_name])})
        return queryset

    def _apply_meeting_reservation_filters(self, queryset, entities):
        status = entities.get('status')
        if status in {'pending', 'approved', 'rejected', 'cancelled'}:
            queryset = queryset.filter(status=status)

        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                queryset = queryset.filter(start_time__range=(start_at, end_at))
        return queryset

    def _apply_seal_filters(self, queryset, entities):
        queryset = self._apply_active_status_filter(queryset, entities, 'is_active')
        seal_type = entities.get('seal_type')
        if seal_type:
            queryset = queryset.filter(seal_type=seal_type)
        return queryset

    def _apply_seal_application_filters(self, queryset, entities):
        status = entities.get('status')
        if status in {'pending', 'approved', 'rejected', 'used', 'cancelled'}:
            queryset = queryset.filter(status=status)
        return queryset

    def _apply_finance_expense_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'pending_payment':
            queryset = queryset.filter(pay_status=0)
        elif status == 'paid':
            queryset = queryset.filter(pay_status=1)

        check_status = entities.get('check_status')
        check_status_mapping = {
            'pending': 0,
            'reviewing': 1,
            'approved': 2,
            'rejected': 3,
            'cancelled': 4,
        }
        mapped_check_status = check_status_mapping.get(check_status, check_status if isinstance(check_status, int) else None)
        if mapped_check_status is not None:
            queryset = queryset.filter(check_status=mapped_check_status)
        return queryset

    def _apply_finance_invoice_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'unissued':
            queryset = queryset.filter(open_status=0)
        elif status == 'issued':
            queryset = queryset.filter(open_status=1)
        elif status == 'void':
            queryset = queryset.filter(open_status=2)

        enter_status = entities.get('enter_status')
        enter_status_mapping = {
            'none': 0,
            'partial': 1,
            'full': 2,
        }
        mapped_enter_status = enter_status_mapping.get(enter_status, enter_status if isinstance(enter_status, int) else None)
        if mapped_enter_status is not None:
            queryset = queryset.filter(enter_status=mapped_enter_status)

        check_status = entities.get('check_status')
        check_status_mapping = {
            'pending': 0,
            'reviewing': 1,
            'approved': 2,
            'rejected': 3,
            'cancelled': 4,
        }
        mapped_check_status = check_status_mapping.get(check_status, check_status if isinstance(check_status, int) else None)
        if mapped_check_status is not None:
            queryset = queryset.filter(check_status=mapped_check_status)
        return queryset

    def _apply_advanced_finance_filters(self, queryset, entities, data_type):
        status = entities.get('status')
        status_mappings = {
            'finance_account': {'inactive': 'disabled'},
            'finance_budget': {'active': 'active', 'draft': 'draft', 'closed': 'closed'},
            'finance_receivable': {
                'pending': 'pending',
                'partial': 'partial',
                'settled': 'settled',
                'overdue': 'overdue',
                'bad_debt': 'bad_debt',
            },
            'finance_payable': {
                'pending': 'pending',
                'partial': 'partial',
                'settled': 'settled',
                'overdue': 'overdue',
            },
        }
        mapped_status = status_mappings.get(data_type, {}).get(status, status)
        if data_type in status_mappings and mapped_status:
            queryset = queryset.filter(status=mapped_status)

        if data_type == 'finance_bank_transaction':
            direction = entities.get('direction')
            if direction in {'in', 'out'}:
                queryset = queryset.filter(direction=direction)
            match_status = entities.get('match_status')
            if match_status in {'matched', 'unmatched'}:
                queryset = queryset.filter(match_status=match_status)
            queryset = self._apply_datetime_range_filter(queryset, entities, 'transaction_date')
        return queryset

    def _build_advanced_finance_count(self, queryset, data_type, entities):
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': data_type,
            'status': entities.get('status'),
        }

    def _build_advanced_finance_list(self, queryset, data_type, entities):
        fields = {
            'finance_account': ['id', 'name', 'account_type', 'bank_name', 'account_no', 'currency', 'current_balance', 'status'],
            'finance_budget': ['id', 'name', 'period_type', 'budget_amount', 'used_amount', 'status', 'start_date', 'end_date'],
            'finance_receivable': ['id', 'code', 'amount', 'received_amount', 'due_date', 'status'],
            'finance_payable': ['id', 'code', 'amount', 'paid_amount', 'due_date', 'status'],
            'finance_bank_transaction': ['id', 'transaction_no', 'transaction_date', 'direction', 'amount', 'counterparty', 'purpose', 'match_status'],
        }
        items = []
        for item in queryset[:5]:
            row = {field: getattr(item, field, '') for field in fields[data_type]}
            if data_type == 'finance_bank_transaction':
                row['account'] = getattr(getattr(item, 'account', None), 'name', '')
            for date_field in ['start_date', 'end_date', 'due_date', 'transaction_date']:
                if hasattr(row.get(date_field), 'strftime'):
                    row[date_field] = row[date_field].strftime('%Y-%m-%d')
            items.append(row)
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': data_type,
            'status': entities.get('status'),
        }

    def _apply_ai_center_filters(self, queryset, entities, data_type):
        status = entities.get('status')
        if status:
            queryset = queryset.filter(status=status)
        if data_type == 'ai_model_config':
            if 'is_active' in entities:
                queryset = queryset.filter(is_active=entities['is_active'])
            if 'is_default' in entities:
                queryset = queryset.filter(is_default=entities['is_default'])
        return self._apply_datetime_range_filter(queryset, entities, 'created_at')

    def _build_ai_center_count(self, queryset, data_type, entities):
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': data_type,
            'status': entities.get('status'),
        }

    def _build_ai_center_list(self, queryset, data_type, entities):
        fields = {
            'ai_model_config': ['id', 'name', 'is_default', 'is_active'],
            'ai_knowledge_base': ['id', 'name', 'description', 'status'],
            'ai_task': ['id', 'task_type', 'status', 'error_message'],
            'ai_workflow': ['id', 'name', 'description', 'status', 'is_public'],
        }
        items = []
        for item in queryset[:5]:
            row = {field: getattr(item, field, '') for field in fields[data_type]}
            if data_type == 'ai_model_config':
                row['provider'] = item.provider
                row['primary_model'] = item.primary_model_name()
            elif data_type == 'ai_knowledge_base':
                row['creator'] = getattr(getattr(item, 'creator', None), 'username', '')
            elif data_type == 'ai_task':
                row['user'] = getattr(getattr(item, 'user', None), 'username', '')
            elif data_type == 'ai_workflow':
                row['owner'] = getattr(getattr(item, 'owner', None), 'username', '')
            items.append(row)
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': data_type,
            'status': entities.get('status'),
        }

    def _apply_supply_chain_filters(self, queryset, entities, data_type):
        status = entities.get('status')
        if status:
            queryset = queryset.filter(status=status)
        if 'is_abnormal' in entities and data_type == 'supply_chain_pr_review':
            queryset = queryset.filter(is_abnormal=entities['is_abnormal'])
        return self._apply_datetime_range_filter(queryset, entities, 'create_time')

    def _build_supply_chain_count(self, queryset, data_type, entities):
        return {
            'type': 'count',
            'value': queryset.count(),
            'data_type': data_type,
            'status': entities.get('status'),
        }

    def _build_supply_chain_list(self, queryset, data_type, entities):
        fields = {
            'supply_chain_forecast': ['id', 'code', 'name', 'status', 'period_start', 'period_end', 'summary'],
            'supply_chain_outsource': ['id', 'code', 'quantity', 'status'],
            'supply_chain_pr_review': ['id', 'code', 'title', 'source_code', 'status', 'is_abnormal', 'recommended_action'],
            'supply_chain_price_review': ['id', 'code', 'quoted_price', 'status', 'ai_summary'],
            'supply_chain_sample': ['id', 'code', 'material_name', 'specification', 'quantity', 'required_date', 'status'],
        }
        items = []
        for item in queryset[:5]:
            row = {field: getattr(item, field, '') for field in fields[data_type]}
            if data_type in {'supply_chain_forecast', 'supply_chain_outsource'}:
                row['product'] = getattr(getattr(item, 'product', None), 'name', '')
            if data_type in {'supply_chain_outsource', 'supply_chain_price_review', 'supply_chain_sample'}:
                row['supplier'] = getattr(getattr(item, 'supplier', None), 'name', '')
            if data_type == 'supply_chain_price_review':
                row['item_name'] = getattr(getattr(item, 'inventory_item', None), 'name', '')
            if data_type == 'supply_chain_sample':
                engineer = getattr(item, 'engineer', None)
                row['engineer'] = getattr(engineer, 'name', '') or getattr(engineer, 'username', '')
            for date_field in ['period_start', 'period_end', 'required_date']:
                if hasattr(row.get(date_field), 'strftime'):
                    row[date_field] = row[date_field].strftime('%Y-%m-%d')
            items.append(row)
        return {
            'type': 'list',
            'items': items,
            'total': queryset.count(),
            'data_type': data_type,
            'status': entities.get('status'),
        }

    def _apply_warehouse_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'active':
            queryset = queryset.filter(status=1)
        elif status == 'inactive':
            queryset = queryset.filter(status=0)

        warehouse_type = entities.get('warehouse_type')
        if warehouse_type:
            queryset = queryset.filter(warehouse_type=warehouse_type)
        return queryset

    def _apply_inventory_filters(self, queryset, entities):
        status = entities.get('status')
        if status in {'normal', 'locked', 'quarantine'}:
            queryset = queryset.filter(status=status)
        return queryset

    def _apply_stock_movement_filters(self, queryset, entities):
        status = entities.get('status')
        if status == 'pending':
            queryset = queryset.filter(status=1)
        elif status == 'approved':
            queryset = queryset.filter(status=2)
        elif status == 'stocked':
            queryset = queryset.filter(status=3)
        elif status == 'cancelled':
            queryset = queryset.filter(status=4)

        stock_type = entities.get('stock_type')
        if stock_type:
            if hasattr(queryset.model, 'stock_in_type'):
                queryset = queryset.filter(stock_in_type=stock_type)
            elif hasattr(queryset.model, 'stock_out_type'):
                queryset = queryset.filter(stock_out_type=stock_type)
        return queryset

    def _apply_datetime_range_filter(self, queryset, entities, field_name):
        time_range = entities.get('time_range')
        if time_range:
            start_at, end_at = self._resolve_time_range(time_range)
            if start_at and end_at:
                return queryset.filter(**{f'{field_name}__range': (start_at, end_at)})
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
