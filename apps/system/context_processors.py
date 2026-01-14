import logging
from apps.user.models import SystemConfiguration as SystemConfig, Menu
from django.contrib.auth import get_user_model
from django.core.cache import cache
from apps.common.cache_service import SystemCache

logger = logging.getLogger('django')

User = get_user_model()

SYSTEM_CONFIG_CACHE_TIMEOUT = 30 * 60
MENU_CACHE_TIMEOUT = 10 * 60
PERMISSION_CACHE_TIMEOUT = 5 * 60


def system_config(request):
    """系统配置上下文处理器"""
    from apps.system.views import STATIC_SYSTEM_CONFIGS
    
    configs = SystemCache.get_configs()
    
    if configs is None:
        config_items = SystemConfig.objects.filter(is_active=True)
        db_configs = {item.key: item for item in config_items}
        SystemCache.set_configs(db_configs)
        configs = db_configs
    
    config_dict = {}
    for static_config in STATIC_SYSTEM_CONFIGS:
        key = static_config['key']
        if key in configs:
            config_dict[key] = configs[key]
        else:
            config_obj = SystemConfig(key=key, value=static_config['value'], is_active=True)
            config_dict[key] = config_obj
    
    return {'configs': config_dict}


MENU_URL_TO_PERMISSION_MAP = {
    '/dashboard/': 'view_workbench',
    '/home/main/': 'view_workbench',
    '/system/config/': 'view_config',
    '/system/storage/': 'view_storage_config',
    '/system/department/': 'view_department',
    '/system/module/': 'view_module',
    '/system/menu/': 'view_menu',
    '/system/log/': 'view_operation_log',
    '/system/attachment/': 'view_attachment',
    '/system/backup/': 'view_backup',
    '/system/permission/role/': 'view_role',
    '/system/position/': 'view_position',
    '/system/employee/': 'view_employee',
    '/system/reward_punishment/': 'view_reward_punishment',
    '/system/employee_care/': 'view_employee_care',
    '/oa/assets/': 'view_asset',
    '/oa/assets/list/': 'view_asset',
    '/oa/assets/return/': 'view_asset_return',
    '/oa/assets/repair/': 'view_asset_repair',
    '/oa/assets/scrap/': 'view_asset_scrap',
    '/oa/vehicle/info/': 'view_vehicle_info',
    '/oa/vehicle/apply/': 'view_vehicle_apply',
    '/oa/vehicle/maintenance/': 'view_vehicle_maintenance',
    '/oa/vehicle/dispatch/': 'view_vehicle_dispatch',
    '/oa/vehicle/upkeep/': 'view_vehicle_upkeep',
    '/oa/vehicle/fee/': 'view_vehicle_fee',
    '/oa/vehicle/oil/': 'view_vehicle_oil',
    '/oa/meeting/': 'view_meeting_room',
    '/oa/meeting/room/': 'view_meeting_room',
    '/oa/meeting/record/': 'view_meeting_record',
    '/oa/meeting/minutes/': 'view_meeting_minutes',
    '/oa/document/draft/': 'view_document_draft',
    '/oa/document/approve/': 'view_document_approve',
    '/oa/document/publish/': 'view_document_publish',
    '/oa/document/view/': 'view_document_view',
    '/oa/document/category/': 'view_document_category',
    '/oa/seal/management/': 'view_seal_management',
    '/oa/seal/application/': 'view_seal_application',
    '/oa/seal/record/': 'view_seal_record',
    '/notice/': 'view_notice',
    '/notice/list/': 'view_notice',
    '/notice/type/': 'view_notice_type',
    '/news/': 'view_company_news',
    '/schedule/': 'view_schedule',
    '/calendar/': 'view_work_calendar',
    '/report/': 'view_report',
    '/adm/finance/reimbursement/': 'view_reimbursement',
    '/adm/finance/invoice/': 'view_invoice',
    '/adm/finance/receive_invoice/': 'view_receive_invoice',
    '/adm/finance/payment_receive/': 'view_payment_receive',
    '/adm/finance/payment/': 'view_payment',
    '/adm/contract/': 'view_contract',
    '/adm/contract/list/': 'view_contract',
    '/adm/contract/sales/': 'view_contract',
    '/adm/contract/purchase/': 'view_contract',
    '/adm/contract/audit/': 'view_contract',
    '/adm/contract/template/': 'view_contract',
    '/adm/contract/category/': 'view_contract',
    '/customer/': 'view_customer',
    '/customer/list/': 'view_customer',
    '/customer/public/': 'view_public_customer',
    '/customer/spider/': 'view_spider_task',
    '/customer/robot/': 'view_ai_robot',
    '/customer/abandoned/': 'view_abandoned_customer',
    '/project/': 'view_project',
    '/project/list/': 'view_project',
    '/project/category/': 'view_project_category',
    '/project/stage/': 'view_project_stage',
    '/project/document/': 'view_project_document',
    '/project/task/': 'view_task',
    '/project/workhour/': 'view_workhour',
    '/project/risk_prediction/': 'view_risk_prediction',
    '/project/progress_analysis/': 'view_progress_analysis',
    '/production/': 'view_production_plan',
    '/production/plan/': 'view_production_plan',
    '/production/task/': 'view_production_task',
    '/production/procedure/': 'view_procedure',
    '/production/bom/': 'view_bom',
    '/production/quality/': 'view_quality_check',
    '/production/data/': 'view_datacollection',
    '/production/equipment/': 'view_equipment',
    '/production/monitor/': 'view_equipment_monitor',
    '/production/process/': 'view_process',
    '/production/product/': 'view_production_product',
    '/production/sop/': 'view_sop',
    '/production/analysis/': 'view_performance_analysis',
    '/production/procedureset/': 'view_procedureset',
    '/production/resource_dispatch/': 'view_resource_dispatch',
    '/ai/': 'view_ai_task',
    '/ai/robot/': 'view_ai_robot',
    '/ai/model/': 'view_model_config',
    '/ai/workflow/': 'view_ai_workflow',
    '/ai/task/': 'view_ai_task',
    '/ai/knowledge/': 'view_knowledge_base',
    '/ai/knowledge-base/': 'view_knowledge_base',
    '/ai/config/models/': 'view_model_config',
    '/ai/tasks/': 'view_ai_task',
    '/disk/': 'view_disk_index',
    '/disk/home/': 'view_disk_index',
    '/disk/file/': 'view_disk_index',
    '/disk/folder/': 'view_disk_index',
    '/disk/share/': 'view_share_management',
    '/disk/collection/': 'view_disk_index',
    '/disk/starred/': 'view_starred_file',
    '/disk/personal/': 'view_personal_file',
    '/disk/recycle/': 'view_recycle',
    '/approval/': 'view_approval_type',
    '/approval/type/': 'view_approval_type',
    '/approval/flow/': 'view_approval_flow',
    '/approval/my/': 'view_approval_request',
    '/approval/apply/': 'view_approval_request',
    '/approval/record/': 'view_approval_record',
    '/approval/pending/': 'view_approval_request',
    '/approval/approval_type/': 'view_approval_type',
    '/approval/approvalflow/': 'view_approval_flow',
    '/contract/': 'view_contract',
    '/contract/audit/': 'view_contract',
    '/contract/productcategory/': 'view_contract',
    '/contract/product/': 'view_product',
    '/contract/service/': 'view_service',
    '/contract/supplier/': 'view_supplier',
    '/contract/purchase_category/': 'view_purchase_category',
    '/contract/purchase/': 'view_purchase_item',
    '/contract/archive/': 'view_contract_archive',
    '/contract/cancel/': 'view_contract',
    '/contract/template/': 'view_contract_template',
    '/contract/category/': 'view_contract_category',
    '/user/group/': 'view_group',
    '/user/login/': 'view_user',
    '/user/login-submit/': 'view_user',
    '/user/logout/': 'view_user',
    '/user/admin/': 'view_admin',
    '/user/admin/list/': 'view_admin',
    '/user/employee/': 'view_employee',
    '/user/employee/list/': 'view_employee',
    '/user/employee_care/': 'view_employee_care',
    '/user/employee-care/': 'view_employee_care',
    '/user/reward_punishment/': 'view_reward_punishment',
    '/user/reward-punishment/': 'view_reward_punishment',
    '/user/menu/': 'view_menu',
    '/user/menu/list/': 'view_menu',
    '/user/department_role/': 'view_department_role',
    '/user/employee_transfer/': 'view_employee_transfer',
    '/user/employee_dimission/': 'view_employee_dimission',
    '/user/employee_contract/': 'view_employee_contract',
    '/user/group/list/': 'view_group',
    '/user/group/2/permission/': 'view_group_permission',
    '/user/menu/1095/permissions/': 'view_menu_permission',
    '/user/menu/1237/permissions/': 'view_menu_permission',
    '/user/menu/1238/permissions/': 'view_menu_permission',
    '/position/': 'view_position',
    '/position/list/': 'view_position',
    '/adm/customer/spider_task/': 'view_spider_task',
    '/adm/customer/followup/': 'view_follow_record',
    '/adm/customer/callrecord/': 'view_call_record',
    '/adm/production/baseinfo/': 'view_production_baseinfo',
    '/adm/production/procedure/': 'view_procedure',
    '/adm/production/procedureset/': 'view_procedureset',
    '/adm/production/bom/': 'view_bom',
    '/adm/production/equipment/': 'view_equipment',
    '/adm/production/data/': 'view_datacollection',
    '/adm/production/analysis/': 'view_performance_analysis',
    '/adm/production/sop/': 'view_sop',
    '/adm/production/task/': 'view_production_task',
    '/adm/production/task/plan/': 'view_production_plan',
    '/adm/production/task/execution/': 'view_production_task',
    '/adm/production/technology/': 'view_resource_dispatch',
    '/adm/production/quality/': 'view_quality_check',
    '/adm/production/equipment/monitor/': 'view_equipment_monitor',
    '/adm/finance/statistics/reimbursement/': 'view_reimbursement_record',
    '/adm/finance/statistics/invoice/': 'view_invoice_record',
    '/adm/finance/statistics/receiveinvoice/': 'view_receive_invoice_record',
    '/adm/finance/statistics/paymentreceive/': 'view_payment_receive_record',
    '/adm/finance/statistics/payment/': 'view_payment_record',
    '/adm/project/category/datalist/': 'view_project_category',
    '/adm/task/datalist/': 'view_task',
    '/project/datalist/': 'view_project',
    '/system/admin_office/asset/': 'view_asset',
    '/system/admin_office/notice/': 'view_notice',
    '/system/admin_office/asset/brand/': 'view_asset',
    '/system/admin_office/asset/category/': 'view_asset',
    '/system/admin_office/notice/news/': 'view_company_news',
    '/system/permission/': 'view_permission',
    '/data_screen/': 'view_data_screen',
    '/finance_screen/': 'view_finance_screen',
    '/business_screen/': 'view_business_screen',
    '/production_screen/': 'view_production_screen',
    '/personal/schedule/': 'view_schedule',
    '/personal/daily/': 'view_daily',
    '/personal/worklog/': 'view_worklog',
    '/personal/portrait/': 'view_portrait',
    '/personal/notice/': 'view_notice',
    '/personal/email/': 'view_email',
    '/personal/file/': 'view_diskfile',
    '/finance/': 'view_finance',
    '/contract/purchase_item/': 'view_purchase_item',
    '/contract/service/': 'view_service',
    '/contract/supplier/': 'view_supplier',
    '/contract/purchase_category/': 'view_purchase_category',
    '/customer/order/': 'view_customer_order',
    '/customer/follow/': 'view_follow_record',
    '/customer/call/': 'view_call_record',
    '/customer/field/': 'view_customer_field',
    '/customer/source/': 'view_customer_source',
    '/customer/grade/': 'view_customer_grade',
    '/customer/intent/': 'view_customer_intent',
    '/customer/follow_field/': 'view_follow_field',
    '/customer/order_field/': 'view_order_field',
    '/customer/abandoned/': 'view_abandoned_customer',
    '/customer/public/': 'view_public_customer',
    '/disk/starred/': 'view_starred_file',
    '/disk/personal/': 'view_personal_file',
    '/disk/share/': 'view_shared_file',
    '/disk/recycle/': 'view_recycle',
}


def _normalize_permission(permission_code):
    """标准化权限代码"""
    if not permission_code:
        return None
    if '.' in permission_code:
        return permission_code
    return f'user.{permission_code}'


def get_permission_from_src(src):
    """从菜单src URL推断权限codename"""
    if not src or not src.startswith('/') or src == 'javascript:;':
        return None
    
    src = src.rstrip('/')
    
    if src in MENU_URL_TO_PERMISSION_MAP:
        return MENU_URL_TO_PERMISSION_MAP[src]
    
    parts = src.strip('/').split('/')
    
    if len(parts) >= 2:
        app = parts[0]
        module = parts[1]
        
        url_key = f'/{app}/{module}/'
        if url_key in MENU_URL_TO_PERMISSION_MAP:
            return MENU_URL_TO_PERMISSION_MAP[url_key]
        
        if module == 'statistics':
            if len(parts) >= 3:
                feature = parts[2]
                return {
                    'reimbursement': 'view_reimbursement_record',
                    'invoice': 'view_invoice_record',
                    'receive_invoice': 'view_receive_invoice_record',
                    'receiveinvoice': 'view_receive_invoice_record',
                    'payment_receive': 'view_payment_receive_record',
                    'paymentreceive': 'view_payment_receive_record',
                    'payment': 'view_payment_record',
                }.get(feature)
        
        if module == 'admin_office':
            if len(parts) >= 3:
                feature = parts[2]
                if feature in ['asset', 'asset_brand', 'asset_category']:
                    return 'view_asset'
                elif feature in ['notice', 'news']:
                    return 'view_notice' if feature == 'notice' else 'view_company_news'
        
        if module == 'datalist':
            if len(parts) >= 3:
                feature = parts[2]
                if feature == 'category':
                    return 'view_project_category'
                return f'view_{feature}'
        
        if app == 'adm':
            if module in ['project', 'task', 'customer', 'production', 'finance']:
                if module == 'project' and len(parts) >= 3:
                    sub_module = parts[2]
                    if sub_module == 'category':
                        return 'view_project_category'
                    return f'view_{sub_module}'
                return f'view_{module}'
    
    if len(parts) >= 1:
        app = parts[0]
        url_key = f'/{app}/'
        if url_key in MENU_URL_TO_PERMISSION_MAP:
            return MENU_URL_TO_PERMISSION_MAP[url_key]
        
        if len(parts) >= 2:
            module = parts[1]
            return f'view_{module}'
        return f'view_{app}'
    
    return None


def get_menus(request):
    """获取当前用户可访问的菜单列表"""
    user = request.user
    
    if not user.is_authenticated:
        return {'menus': []}
    
    cache_key = f'menus_user_{user.id}'
    cached_menus = cache.get(cache_key)
    if cached_menus is not None:
        return {'menus': cached_menus}
    
    all_menus = Menu.objects.filter(status=1).select_related('module', 'pid').order_by('sort')
    
    available_menus = [menu for menu in all_menus if menu.is_available()]
    
    if getattr(user, 'is_superuser', False):
        logger.debug(f"用户 {user.username} 是超级管理员，显示所有菜单")
        cache.set(cache_key, available_menus, MENU_CACHE_TIMEOUT)
        return {'menus': available_menus}
    
    user_permissions = set(user.get_all_permissions())
    
    logger.debug(f"用户 {user.username} 权限数: {len(user_permissions)}")
    
    menu_dict = {menu.id: menu for menu in available_menus}
    
    for menu in available_menus:
        menu.children = []
    
    menu_tree = {}
    for menu in available_menus:
        if menu.pid_id:
            parent = menu_dict.get(menu.pid_id)
            if parent:
                parent.children.append(menu)
        else:
            menu_tree[menu.id] = menu
    
    def check_menu_permission(menu):
        """检查用户是否有权限访问菜单"""
        perm_codename = None
        
        if menu.permission_required:
            perm_codename = menu.permission_required
        else:
            perm_codename = get_permission_from_src(menu.src)
        
        if not perm_codename:
            return None
        
        normalized_perm = _normalize_permission(perm_codename)
        
        if normalized_perm in user_permissions:
            return True
        
        if perm_codename in user_permissions:
            return True
        
        return False
    
    def check_child_permissions(menu):
        """递归检查子菜单权限"""
        if not hasattr(menu, 'children') or not menu.children:
            result = check_menu_permission(menu)
            return result if result is not None else False
        
        for child in menu.children:
            if check_child_permissions(child):
                return True
        
        return None
    
    def filter_menu(menu):
        """递归过滤用户有权访问的菜单"""
        has_access = check_child_permissions(menu)
        
        if has_access is False:
            return None
        
        if hasattr(menu, 'children') and menu.children:
            filtered_children = []
            for child in menu.children:
                filtered_child = filter_menu(child)
                if filtered_child:
                    filtered_children.append(filtered_child)
            
            if not filtered_children:
                return None
            
            menu.children = filtered_children
            menu.children.sort(key=lambda x: x.sort if hasattr(x, 'sort') else 0)
        
        return menu
    
    authorized_menus = []
    for menu_id, menu in menu_tree.items():
        filtered_menu = filter_menu(menu)
        if filtered_menu:
            authorized_menus.append(filtered_menu)
    
    authorized_menus.sort(key=lambda x: x.sort if hasattr(x, 'sort') else 0)
    
    logger.debug(f"用户 {user.username} 显示 {len(authorized_menus)} 个一级菜单")
    
    cache.set(cache_key, authorized_menus, MENU_CACHE_TIMEOUT)
    
    return {'menus': authorized_menus}
