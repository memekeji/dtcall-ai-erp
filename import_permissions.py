#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入权限管理设计数据到数据库
根据 权限管理详细设计文档.md 创建角色和权限配置
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 支持命令行指定 settings 参数
if len(sys.argv) > 1 and sys.argv[1].startswith('--settings='):
    settings_module = sys.argv[1].split('=')[1]
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from apps.user.models import GroupExtension, Menu
from django.utils import timezone
from datetime import datetime


# 系统角色定义
ROLES = [
    {
        'name': '系统管理员',
        'code': 'system_admin',
        'description': '拥有系统所有权限，可以管理系统配置、用户、角色等',
        'permissions': ['*']  # * 表示所有权限
    },
    {
        'name': '人事管理员',
        'code': 'hr_admin',
        'description': '负责人事管理相关功能，包括员工、部门、岗位、奖罚等',
        'permissions': [
            '人事管理.*',  # 所有人事管理权限
        ]
    },
    {
        'name': '财务管理员',
        'code': 'finance_admin',
        'description': '负责财务管理相关功能，包括报销、开票、回款、付款等',
        'permissions': [
            '财务管理.*',
        ]
    },
    {
        'name': '客户经理',
        'code': 'customer_manager',
        'description': '负责客户管理相关功能，包括客户列表、客户公海、客户订单等',
        'permissions': [
            '客户管理.*',
            '合同管理.*',
        ]
    },
    {
        'name': '项目经理',
        'code': 'project_manager',
        'description': '负责项目管理相关功能，包括项目列表、任务管理、工时管理等',
        'permissions': [
            '项目管理.*',
        ]
    },
    {
        'name': '生产主管',
        'code': 'production_manager',
        'description': '负责生产管理相关功能，包括生产计划、任务、资源调度等',
        'permissions': [
            '生产管理.*',
        ]
    },
    {
        'name': '行政专员',
        'code': 'admin_staff',
        'description': '负责行政办公相关功能，包括固定资产、车辆、会议管理等',
        'permissions': [
            '行政办公.*',
            '个人办公.*',
        ]
    },
    {
        'name': 'AI工程师',
        'code': 'ai_engineer',
        'description': '负责AI智能中心相关功能，包括知识库、模型配置、工作流等',
        'permissions': [
            'AI智能中心.*',
        ]
    },
    {
        'name': '普通员工',
        'code': 'employee',
        'description': '基础权限，可以访问个人办公、企业网盘等',
        'permissions': [
            '个人办公.*',
            '企业网盘.*',
            '工作台.*',
        ]
    },
]

# 权限节点定义（基于文档中的详细说明）
PERMISSION_NODES = {
    '工作台': ['view_dashboard', 'view_data_screen', 'view_finance_screen', 'view_business_screen', 'view_production_screen'],
    '系统管理': {
        '系统配置': ['view_config', 'add_config', 'change_config'],
        '功能模块': ['view_module', 'add_module', 'change_module'],
        '菜单管理': ['view_menu', 'add_menu', 'change_menu', 'delete_menu', 'order_menu'],
        '操作日志': ['view_log', 'view_log_detail'],
        '附件管理': ['view_attachment', 'download_attachment', 'delete_attachment'],
        '备份数据': ['view_backup', 'add_backup', 'change_backup', 'restore_backup', 'download_backup', 'delete_backup', 'policy_backup', 'batch_delete_backup'],
    },
    '人事管理': {
        '角色管理': ['view_role', 'add_role', 'change_role', 'config_role', 'toggle_role', 'delete_role'],
        '部门管理': ['view_department', 'add_department', 'change_department', 'delete_department', 'toggle_department', 'manage_department_role'],
        '岗位职称': ['view_position', 'add_position', 'change_position', 'delete_position', 'toggle_position'],
        '员工管理': ['view_employee', 'add_employee', 'change_employee', 'delete_employee', 'import_employee'],
        '奖罚管理': ['view_reward', 'add_reward', 'change_reward', 'delete_reward'],
        '员工关怀': ['view_care', 'add_care', 'change_care', 'delete_care'],
    },
    '行政办公': {
        '固定资产': {
            '资产管理': ['view_asset', 'add_asset', 'change_asset', 'delete_asset'],
            '资产归还': ['view_return', 'add_return', 'change_return', 'delete_return'],
            '资产维修': ['view_repair', 'add_repair', 'change_repair', 'delete_repair'],
            '资产报废': ['view_scrap', 'add_scrap', 'change_scrap', 'delete_scrap'],
        },
        '车辆管理': {
            '车辆信息': ['view_vehicle', 'add_vehicle', 'change_vehicle', 'delete_vehicle'],
            '用车申请': ['view_vehicle_apply', 'add_vehicle_apply', 'change_vehicle_apply', 'delete_vehicle_apply'],
            '车辆维修': ['view_vehicle_repair', 'add_vehicle_repair', 'change_vehicle_repair', 'delete_vehicle_repair'],
            '车辆调度': ['view_vehicle_dispatch', 'add_vehicle_dispatch', 'change_vehicle_dispatch', 'delete_vehicle_dispatch'],
            '车辆保养': ['view_vehicle_maintenance', 'add_vehicle_maintenance', 'change_vehicle_maintenance', 'delete_vehicle_maintenance'],
            '车辆费用': ['view_vehicle_fee', 'add_vehicle_fee', 'change_vehicle_fee', 'delete_vehicle_fee'],
            '车辆油耗': ['view_vehicle_oil', 'add_vehicle_oil', 'change_vehicle_oil', 'delete_vehicle_oil'],
        },
        '会议管理': {
            '会议室管理': ['view_meeting_room', 'add_meeting_room', 'change_meeting_room', 'delete_meeting_room', 'apply_meeting'],
            '会议记录': ['view_meeting_record', 'add_meeting_minutes', 'change_meeting_record', 'delete_meeting_record'],
            '会议纪要': ['view_meeting_minutes', 'add_meeting_minutes', 'change_meeting_minutes', 'delete_meeting_minutes'],
        },
        '公文管理': {
            '公文起草': ['view_draft', 'add_draft', 'change_draft', 'delete_draft'],
            '公文审核': ['view_approve', 'add_approve', 'change_approve', 'delete_approve'],
            '公文发布': ['view_publish', 'add_publish', 'change_publish', 'delete_publish'],
            '公文查看': ['view_detail'],
            '公文分类': ['view_category', 'add_category', 'change_category', 'delete_category'],
        },
        '用章管理': {
            '印章管理': ['view_seal', 'add_seal', 'change_seal', 'delete_seal'],
            '用章申请': ['view_seal_apply', 'add_seal_apply', 'change_seal_apply', 'delete_seal_apply'],
            '用章记录': ['view_seal_record', 'add_seal_record', 'change_seal_record', 'delete_seal_record'],
        },
        '公告列表': ['view_notice', 'view_notice_detail', 'add_notice', 'change_notice', 'delete_notice'],
        '通知类型': ['view_notice_type', 'add_notice_type', 'change_notice_type', 'delete_notice_type'],
    },
    '个人办公': {
        '日程安排': ['view_schedule', 'add_schedule', 'change_schedule', 'delete_schedule'],
        '工作日历': ['view_calendar', 'add_calendar', 'change_calendar', 'delete_calendar'],
        '工作汇报': ['view_report', 'add_report', 'change_report', 'delete_report'],
    },
    '财务管理': {
        '报销管理': ['view_expense', 'add_expense', 'change_expense', 'delete_expense', 'approve_expense', 'batch_approve_expense', 'export_expense'],
        '开票管理': ['view_invoice', 'add_invoice', 'change_invoice', 'delete_invoice', 'view_invoice_detail', 'export_invoice', 'approve_invoice', 'download_invoice'],
        '收票管理': ['view_receipt', 'add_receipt', 'change_receipt', 'delete_receipt', 'view_receipt_detail', 'export_receipt'],
        '回款管理': ['view_payment', 'add_payment', 'change_payment', 'delete_payment', 'view_payment_detail', 'export_payment'],
        '付款管理': ['view_pay', 'add_pay', 'change_pay', 'delete_pay', 'view_pay_detail', 'export_pay'],
        '报销类型': ['view_expense_type', 'add_expense_type', 'change_expense_type', 'delete_expense_type'],
        '费用类型': ['view_cost_type', 'add_cost_type', 'change_cost_type', 'delete_cost_type'],
        '财务统计': {
            '报销记录': ['view_expense_record'],
            '开票记录': ['view_invoice_record'],
            '收票记录': ['view_receipt_record'],
            '回款记录': ['view_payment_record'],
            '付款记录': ['view_pay_record'],
        },
    },
    '客户管理': {
        '客户列表': ['view_customer', 'view_customer_detail', 'add_customer', 'change_customer', 'delete_customer', 
                    'batch_import', 'batch_delete', 'dial', 'follow_customer', 'add_customer_order', 
                    'add_customer_contract', 'add_customer_invoice', 'add_customer_finance', 'add_customer_project'],
        '客户公海': {
            '公海列表': ['view_pool', 'add_pool_customer', 'claim_customer', 'view_pool_detail', 'move_to_abandon'],
            '爬虫任务': ['view_spider', 'add_spider', 'change_spider', 'delete_spider'],
            'AI机器人': ['config_robot'],
        },
        '废弃客户': ['view_abandon', 'recover_customer'],
        '客户订单': ['view_order', 'view_order_detail', 'add_order', 'receive_order', 'change_order', 'delete_order'],
        '跟进记录': ['view_follow', 'add_follow', 'change_follow', 'delete_follow'],
        '拨号记录': ['view_dial'],
        '客户字段': ['view_customer_field', 'add_customer_field', 'change_customer_field', 'delete_customer_field'],
        '客户来源': ['view_source', 'add_source', 'change_source', 'delete_source'],
        '客户等级': ['view_grade', 'add_grade', 'change_grade', 'delete_grade'],
        '客户意向': ['view_intent', 'add_intent', 'change_intent', 'delete_intent'],
        '跟进字段': ['view_follow_field', 'add_follow_field', 'change_follow_field', 'delete_follow_field'],
        '订单字段': ['view_order_field', 'add_order_field', 'change_order_field', 'delete_order_field'],
    },
    '合同管理': {
        '合同列表': ['view_contract', 'view_contract_detail', 'add_contract', 'change_contract', 'delete_contract', 'approve_contract'],
        '合同模板': ['view_template', 'add_template', 'change_template', 'delete_template', 'approve_template'],
        '合同归档': ['archive_contract'],
        '合同分类': ['view_contract_category', 'add_contract_category', 'change_contract_category', 'delete_contract_category'],
        '产品管理': ['view_product', 'add_product', 'change_product', 'delete_product'],
        '服务管理': ['view_service', 'add_service', 'change_service', 'delete_service'],
        '供应商管理': ['view_supplier', 'add_supplier', 'change_supplier', 'delete_supplier'],
        '采购分类': ['view_purchase_category', 'add_purchase_category', 'change_purchase_category', 'delete_purchase_category'],
        '采购项目': ['view_purchase_item', 'add_purchase_item', 'change_purchase_item', 'delete_purchase_item'],
    },
    '项目管理': {
        '项目列表': ['view_project', 'view_project_detail', 'add_project', 'change_project', 'delete_project', 'add_project_task', 'add_project_document'],
        '项目分类': ['view_project_category', 'add_project_category', 'change_project_category', 'delete_project_category'],
        '任务列表': ['view_task', 'add_task', 'change_task', 'delete_task'],
        '工时管理': ['view_work_hour', 'add_work_hour', 'change_work_hour', 'delete_work_hour'],
        '文档列表': ['view_document', 'add_document', 'change_document', 'delete_document'],
        '风险预测': ['view_risk', 'add_risk', 'change_risk', 'delete_risk'],
        '进度分析': ['view_progress', 'add_progress', 'change_progress', 'delete_progress'],
        '项目阶段': ['view_stage', 'add_stage', 'change_stage', 'delete_stage'],
        '工作类型': ['view_work_type', 'add_work_type', 'change_work_type', 'delete_work_type'],
    },
    '生产管理': {
        '基础信息': {
            '基本工序': ['view_procedure', 'add_procedure', 'change_procedure', 'delete_procedure'],
            '工序集': ['view_procedure_set', 'add_procedure_set', 'change_procedure_set', 'delete_procedure_set'],
            'BOM管理': ['view_bom', 'add_bom', 'change_bom', 'delete_bom'],
            '设备管理': ['view_equipment', 'add_equipment', 'change_equipment', 'delete_equipment'],
            '数据采集': ['view_collection', 'add_collection', 'change_collection', 'delete_collection'],
            '性能分析': ['view_performance', 'add_performance', 'change_performance', 'delete_performance'],
            'SOP管理': ['view_sop', 'add_sop', 'change_sop', 'delete_sop'],
            '产品管理': ['view_production_product', 'add_production_product', 'change_production_product', 'delete_production_product'],
            '工艺路线': ['view_process_route', 'add_process_route', 'change_process_route', 'delete_process_route'],
        },
        '生产任务': {
            '生产计划': ['view_plan', 'add_plan', 'change_plan', 'delete_plan'],
            '生产任务': ['view_production_task', 'add_production_task', 'change_production_task', 'delete_production_task'],
            '资源调度': ['view_dispatch', 'add_dispatch', 'change_dispatch', 'delete_dispatch'],
            '质量管理': ['view_quality', 'add_quality', 'change_quality', 'delete_quality'],
            '设备监控': ['view_monitor', 'add_monitor', 'change_monitor', 'delete_monitor'],
        },
    },
    'AI智能中心': {
        '知识库管理': ['view_knowledge', 'add_knowledge', 'change_knowledge', 'delete_knowledge'],
        'AI模型配置': ['view_model', 'add_model', 'change_model', 'delete_model'],
        'AI任务管理': ['view_ai_task'],
        'AI工作流': ['view_workflow', 'add_workflow', 'change_workflow', 'delete_workflow'],
    },
    '企业网盘': {
        '网盘首页': ['view_disk', 'add_disk_file', 'change_disk_file', 'delete_disk_file'],
        '个人文件': ['view_personal_file', 'add_personal_file', 'change_personal_file', 'delete_personal_file'],
        '共享文件': ['view_shared_file', 'add_shared_file', 'change_shared_file', 'delete_shared_file'],
        '收藏文件': ['view_starred_file', 'add_starred_file', 'change_starred_file', 'delete_starred_file'],
        '分享管理': ['view_share', 'add_share', 'change_share', 'delete_share'],
        '回收站': ['view_recycle', 'clear_recycle'],
    },
}


def import_roles_and_permissions():
    """导入角色和权限配置"""
    print("=" * 70)
    print("开始导入权限管理数据")
    print("=" * 70)
    
    # 获取内容类型
    content_type_map = {}
    for model in [Menu, Group, Permission]:
        ct = ContentType.objects.get_for_model(model)
        content_type_map[model.__name__] = ct
    
    created_roles = 0
    updated_roles = 0
    
    for role_data in ROLES:
        try:
            group, is_created = Group.objects.get_or_create(
                name=role_data['name'],
                defaults={
                    'name': role_data['name']
                }
            )
            
            # 创建或更新 GroupExtension
            extension, ext_created = GroupExtension.objects.update_or_create(
                group=group,
                defaults={
                    'description': role_data['description'],
                    'status': True
                }
            )
            
            if is_created:
                created_roles += 1
                print(f"  ✓ 创建角色: {role_data['name']}")
            else:
                updated_roles += 1
                print(f"  → 更新角色: {role_data['name']}")
                
        except Exception as e:
            print(f"  ✗ 创建角色 {role_data['name']} 失败: {e}")
    
    print()
    print("=" * 70)
    print(f"角色导入完成!")
    print(f"  - 新建角色: {created_roles}")
    print(f"  - 更新角色: {updated_roles}")
    print("=" * 70)
    
    # 显示角色统计
    total_groups = Group.objects.count()
    print(f"\n角色统计:")
    print(f"  - 总角色数: {total_groups}")
    
    return True


def update_menu_permissions():
    """更新菜单权限配置"""
    print("\n" + "=" * 70)
    print("更新菜单权限节点配置")
    print("=" * 70)
    
    # 将权限节点添加到菜单的 permission_required 字段
    # 这里我们根据菜单标题匹配并设置权限
    
    # 先获取所有菜单
    menus = Menu.objects.all()
    menu_map = {menu.title: menu for menu in menus}
    
    updated_count = 0
    
    for menu_title, permissions in PERMISSION_NODES.items():
        # 查找匹配的菜单
        matching_menus = [m for m in menus if menu_title in m.title]
        
        for menu in matching_menus:
            if isinstance(permissions, list):
                # 一级菜单，直接设置权限
                menu.permission_required = ','.join(permissions)
                menu.save()
                updated_count += 1
            elif isinstance(permissions, dict):
                # 二级或三级菜单，需要递归处理
                # 这里只更新一级菜单的权限节点配置标识
                menu.permission_required = 'has_children'
                menu.save()
                updated_count += 1
    
    print(f"  更新菜单权限: {updated_count} 个")
    print("=" * 70)
    
    return updated_count


def assign_all_permissions_to_admin():
    """为系统管理员角色分配所有权限"""
    print("\n" + "=" * 70)
    print("为系统管理员分配所有权限")
    print("=" * 70)
    
    try:
        admin_group = Group.objects.get(name='系统管理员')
        
        # 获取所有权限
        all_permissions = Permission.objects.all()
        
        # 清空现有权限并重新分配
        admin_group.permissions.clear()
        admin_group.permissions.set(all_permissions)
        
        print(f"  ✓ 已为系统管理员分配 {all_permissions.count()} 个权限")
        print("=" * 70)
        return True
    except Group.DoesNotExist:
        print("  ✗ 系统管理员角色不存在")
        return False


if __name__ == '__main__':
    import_roles_and_permissions()
    update_menu_permissions()
    assign_all_permissions_to_admin()
    
    print("\n" + "=" * 70)
    print("权限管理数据导入完成!")
    print("=" * 70)
