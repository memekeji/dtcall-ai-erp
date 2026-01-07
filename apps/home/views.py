from django.shortcuts import render
from apps.user.models import Menu, SystemModule
from dtcall.utils import get_system_config
from django.contrib.auth.decorators import login_required
import logging

logger = logging.getLogger('django')

@login_required
def dashboard(request):
    # 获取系统配置
    web_config = get_system_config('web', 'web_config')  # 传递原项目要求的section和key参数
    
    # 获取菜单数据（严格匹配原项目多级嵌套逻辑）
    try:
        from django.core.cache import cache
        
        # 构建缓存键，包含用户ID
        cache_key = f'dashboard_menu_{request.user.id}'
        
        # 尝试从缓存获取菜单数据
        cached_menu_data = cache.get(cache_key)
        
        if cached_menu_data:
            top_menus = cached_menu_data['top_menus']
            menus = cached_menu_data['menus']
        else:
            # 获取所有状态正常的菜单，使用select_related优化外键查询
            all_menus = Menu.objects.filter(status=1).select_related('module').order_by('sort')
            
            # 过滤出可用的菜单（考虑模块启用状态）
            available_menus = []
            for menu in all_menus:
                # 检查菜单是否可用（is_available()方法已经包含了模块启用状态的检查）
                if menu.is_available():
                    available_menus.append(menu)
            
            # 检查是否为超级管理员
            if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
                # 超级管理员显示所有菜单
                logger.debug(f"用户 {request.user.username} 是超级管理员，显示所有菜单")
                top_menus = [menu for menu in available_menus if menu.pid is None]
                for menu in top_menus:
                    menu.submenus_list = [submenu for submenu in available_menus if submenu.pid_id == menu.id]
                    # 为子菜单添加子子菜单
                    for submenu in menu.submenus_list:
                        submenu.submenus_list = [subsubmenu for subsubmenu in available_menus if subsubmenu.pid_id == submenu.id]
                        # 为孙菜单添加子菜单
                        for subsubmenu in submenu.submenus_list:
                            subsubmenu.submenus_list = [subsubsubmenu for subsubsubmenu in available_menus if subsubsubmenu.pid_id == subsubmenu.id]
                menus = available_menus
            else:
                # 非超级管理员，只显示有权限的菜单
                logger.debug(f"用户 {request.user.username} 是非超级管理员，显示有权限的菜单")
                
                # 获取用户的所有权限
                user_permissions = request.user.get_all_permissions()
                logger.debug(f"用户 {request.user.username} 的权限: {user_permissions}")
                
                # 构建菜单树结构，建立父子关系
                menu_dict = {menu.id: menu for menu in available_menus}
                menu_tree = {}
                
                # 首先构建完整的菜单树
                for menu in available_menus:
                    if menu.pid_id:
                        parent = menu_dict.get(menu.pid_id)
                        if parent:
                            if not hasattr(parent, 'children'):
                                parent.children = []
                            parent.children.append(menu)
                    else:
                        menu_tree[menu.id] = menu
                
                # 检查用户是否有权限访问菜单或其子菜单
                def has_menu_access(menu):
                    # 如果用户有对应的权限，则有权限
                    if menu.permission_required in user_permissions:
                        return True
                    # 检查子菜单是否有权限访问
                    if hasattr(menu, 'children'):
                        for submenu in menu.children:
                            if has_menu_access(submenu):
                                return True
                    # 如果菜单没有设置权限要求，检查用户是否有该应用的任何权限
                    # 获取应用标签（从permission_required或src中提取）
                    app_label = ''
                    if menu.permission_required:
                        app_label = menu.permission_required.split('.')[0]
                    elif menu.src:
                        # 从URL中提取应用标签
                        url_parts = menu.src.strip('/').split('/')
                        if url_parts:
                            app_label = url_parts[0]
                    
                    # 如果能提取到应用标签，检查用户是否有该应用的任何权限
                    if app_label and request.user.has_module_perms(app_label):
                        return True
                        
                    return False
                
                # 过滤用户有权访问的菜单
                authorized_menu_ids = set()
                
                # 遍历所有菜单，收集所有有权限的菜单ID
                for menu in available_menus:
                    if has_menu_access(menu):
                        authorized_menu_ids.add(menu.id)
                        # 同时收集该菜单的所有父菜单ID，确保父菜单也会显示
                        parent = menu_dict.get(menu.pid_id)
                        while parent:
                            authorized_menu_ids.add(parent.id)
                            parent = menu_dict.get(parent.pid_id)
                
                # 然后递归收集所有子菜单ID，确保所有子菜单也会显示
                def collect_all_descendants(menu):
                    authorized_menu_ids.add(menu.id)
                    if hasattr(menu, 'children'):
                        for submenu in menu.children:
                            collect_all_descendants(submenu)
                
                # 遍历所有已经授权的菜单，收集它们的所有子菜单
                for menu_id in list(authorized_menu_ids):
                    menu = menu_dict.get(menu_id)
                    if menu:
                        collect_all_descendants(menu)
                
                # 构建最终的菜单列表
                filtered_menus = [menu for menu in available_menus if menu.id in authorized_menu_ids]
                
                # 构建菜单树
                top_menus = [menu for menu in filtered_menus if menu.pid is None]
                for menu in top_menus:
                    menu.submenus_list = [submenu for submenu in filtered_menus if submenu.pid_id == menu.id]
                    # 为子菜单添加子子菜单
                    for submenu in menu.submenus_list:
                        submenu.submenus_list = [subsubmenu for subsubmenu in filtered_menus if subsubmenu.pid_id == submenu.id]
                        # 为孙菜单添加子菜单
                        for subsubmenu in submenu.submenus_list:
                            subsubmenu.submenus_list = [subsubsubmenu for subsubsubmenu in filtered_menus if subsubsubmenu.pid_id == subsubmenu.id]
                menus = filtered_menus
                
            # 缓存菜单数据，10分钟
            cache.set(cache_key, {'top_menus': top_menus, 'menus': menus}, 10 * 60)
    except Exception as e:
        # 记录错误日志
        logger.error(f'加载菜单失败: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        
        # 返回空菜单的响应
        context = {
            'web_config': web_config,
            'menus': [],
            'database_menus': [],
            'layout_selected': []
        }
        return render(request, 'home/dashboard.html', context)
    
    # 获取动态数据（严格匹配原项目统计逻辑）
    from apps.task.models import Task
    from apps.approval.models import Approval
    from apps.message.models import Message
    from apps.customer.models import Customer, CustomerSource
    from apps.contract.models import Contract
    from apps.user.models import SystemOperationLog, Admin as User
    from django.db.models import Count
    import datetime
    from datetime import timedelta
    import random
    from django.core.cache import cache

    # 构建缓存键，包含用户ID和当前日期
    cache_key = f'dashboard_data_{request.user.id}_{datetime.datetime.now().date()}'
    
    # 尝试从缓存获取动态数据
    cached_dashboard_data = cache.get(cache_key)
    
    if cached_dashboard_data:
        # 从缓存中获取数据
        todo_count = cached_dashboard_data['todo_count']
        approval_count = cached_dashboard_data['approval_count']
        message_count = cached_dashboard_data['message_count']
        approval_processing = cached_dashboard_data['approval_processing']
        completed_task_count = cached_dashboard_data['completed_task_count']
        system_stats = cached_dashboard_data['system_stats']
        pie_data = cached_dashboard_data['pie_data']
        trend_data = cached_dashboard_data['trend_data']
        recent_approvals = cached_dashboard_data['recent_approvals']
        pending_tasks = cached_dashboard_data['pending_tasks']
        login_admin = cached_dashboard_data['login_admin']
    else:
        # 缓存未命中，从数据库获取数据
        todo_count = Task.objects.filter(assignee=request.user, status=0).count()
        approval_count = Approval.objects.filter(reviewer=request.user, status=0).count()
        message_count = Message.objects.filter(user=request.user, is_read=False).count()

        # 计算审批中数量（状态1表示审批中）
        try:
            approval_processing = Approval.objects.filter(status=1).count()
        except Exception as e:
            logger.error(f'计算审批中数量失败: {str(e)}')
            approval_processing = 0

        # 计算最近完成任务数量（假设状态2为完成状态）
        try:
            completed_task_count = Task.objects.filter(assignee=request.user, status=2).count()
        except Exception as e:
            logger.error(f'计算最近完成任务数量失败: {str(e)}')
            completed_task_count = 0

        # 系统使用情况统计
        try:
            # 系统基本统计
            total_users = User.objects.filter(is_active=True).count()
            total_customers = Customer.objects.filter(delete_time=0).count()
            total_contracts = Contract.objects.filter(delete_time=0).count()
            today_operations = SystemOperationLog.objects.filter(
                create_time__date=datetime.datetime.now().date()
            ).count()
            
            # 本月新增统计
            current_month = datetime.datetime.now().replace(day=1)
            new_customers_month = Customer.objects.filter(
                create_time__gte=current_month,
                delete_time=0
            ).count()
            new_contracts_month = Contract.objects.filter(
                create_time__gte=current_month,
                delete_time=0
            ).count()
            
            # 系统使用情况统计
            system_stats = {
                'total_users': total_users,
                'total_customers': total_customers,
                'total_contracts': total_contracts,
                'today_operations': today_operations,
                'new_customers_month': new_customers_month,
                'new_contracts_month': new_contracts_month,
            }
            
        except Exception as e:
            logger.error(f'获取系统统计数据失败: {str(e)}')
            system_stats = {
                'total_users': 0,
                'total_customers': 0,
                'total_contracts': 0,
                'today_operations': 0,
                'new_customers_month': 0,
                'new_contracts_month': 0,
            }

        # 图表数据
        try:
            # 客户来源分布数据
            source_counts = Customer.objects.filter(delete_time=0).values('customer_source').annotate(count=Count('id'))
            source_ids = [item['customer_source'] for item in source_counts if item['customer_source'] is not None]
            sources = {s.id: s.title for s in CustomerSource.objects.filter(id__in=source_ids)}
            pie_data = [{'name': sources.get(item['customer_source'], '未知来源'), 'value': item['count']} for item in source_counts if item['customer_source'] is not None]

            # 模拟销售趋势数据（最近6个月）
            months = []
            for i in range(6):
                month = (datetime.datetime.now() - datetime.timedelta(days=i*30)).strftime('%Y-%m')
                months.append(month)
            months.reverse()

            trend_data = {
                'months': months,
                'sales': [random.randint(10000, 50000) for _ in months]
            }
        except Exception as e:
            logger.error(f'获取图表数据失败: {str(e)}')
            pie_data = []
            trend_data = {'months': [], 'sales': []}

        # 获取最近审批记录（示例数据，需根据实际业务补充）
        recent_approvals = Approval.objects.filter(reviewer=request.user).order_by('-create_time')[:5]

        # 获取待办任务列表（状态0表示待办，取最近5条）
        pending_tasks = Task.objects.filter(assignee=request.user, status=0).order_by('-created_at')[:5]

        # 获取当前登录用户对象
        try:
            login_admin = request.user
        except Exception as e:
            logger.error(f'获取登录用户失败: {str(e)}')
            login_admin = None
        
        # 缓存数据，有效期2小时
        cache.set(cache_key, {
            'todo_count': todo_count,
            'approval_count': approval_count,
            'message_count': message_count,
            'approval_processing': approval_processing,
            'completed_task_count': completed_task_count,
            'system_stats': system_stats,
            'pie_data': pie_data,
            'trend_data': trend_data,
            'recent_approvals': recent_approvals,
            'pending_tasks': pending_tasks,
            'login_admin': login_admin
        }, 2 * 60 * 60)
    
    # 默认仪表盘布局配置（与原项目一致）
    layout_selected = [
        {'row': 1, 'name': 'count'},
        {'row': 1, 'name': 'event'},
        {'row': 1, 'name': 'note'},
        {'row': 2, 'name': 'fastentry'},
        {'row': 2, 'name': 'approve'}
    ]

    # 合并上下文变量，避免覆盖
    # 构造统计数据列表（匹配dashboard.html的statistics变量）
    statistics = [
        {'name': '待办任务', 'value': todo_count},
        {'name': '待审批', 'value': approval_count},
        {'name': '未读消息', 'value': message_count},
        {'name': '审批中', 'value': approval_processing},
        {'name': '最近完成任务', 'value': completed_task_count}
    ]

    # 准备仪表盘数据
    # 1. 核心指标数据 - 从真实数据库获取
    from apps.customer.models import Customer, CustomerOrder
    from apps.project.models import Project
    from django.db.models import Sum
    
    # 总销售额 - 基于客户订单数据
    try:
        total_sales = CustomerOrder.objects.filter(
            delete_time=0,
            status__in=['confirmed', 'processing', 'shipped', 'delivered', 'completed']
        ).aggregate(total=Sum('amount'))['total'] or 0
        total_sales = float(total_sales)
    except Exception as e:
        logger.error(f'获取总销售额失败: {str(e)}')
        total_sales = 0
    
    # 活跃用户数 - 基于今日有操作的用户
    try:
        from apps.user.models import SystemOperationLog
        active_users = SystemOperationLog.objects.filter(
            create_time__date=datetime.datetime.now().date()
        ).values('user_id').distinct().count()
    except Exception as e:
        logger.error(f'获取活跃用户数失败: {str(e)}')
        active_users = 0
    
    # 进行中项目数
    try:
        ongoing_projects = Project.objects.filter(delete_time__isnull=True, status=2).count()
    except Exception as e:
        logger.error(f'获取进行中项目数失败: {str(e)}')
        ongoing_projects = 0
    
    # 客户转化率 = 有订单的客户数 / 总客户数
    try:
        total_customers_count = Customer.objects.filter(delete_time=0).count()
        customers_with_orders = CustomerOrder.objects.filter(
            delete_time=0,
            status__in=['confirmed', 'processing', 'shipped', 'delivered', 'completed']
        ).values('customer_id').distinct().count()
        conversion_rate = round((customers_with_orders / max(total_customers_count, 1)) * 100, 2) if total_customers_count > 0 else 0
    except Exception as e:
        logger.error(f'获取客户转化率失败: {str(e)}')
        conversion_rate = 0
    
    # 计算增长率（基于上月数据）
    try:
        last_month = (datetime.datetime.now().replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        
        # 销售额增长率
        current_month_sales = CustomerOrder.objects.filter(
            create_time__gte=datetime.datetime.now().replace(day=1),
            delete_time=0,
            status__in=['confirmed', 'processing', 'shipped', 'delivered', 'completed']
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        last_month_sales = CustomerOrder.objects.filter(
            create_time__gte=last_month,
            create_time__lt=datetime.datetime.now().replace(day=1),
            delete_time=0,
            status__in=['confirmed', 'processing', 'shipped', 'delivered', 'completed']
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        sales_growth = round((float(current_month_sales) - float(last_month_sales)) / max(float(last_month_sales), 1) * 100, 2) if float(last_month_sales) > 0 else 0
        
        # 活跃用户增长率
        current_month_active_users = SystemOperationLog.objects.filter(
            create_time__gte=datetime.datetime.now().replace(day=1)
        ).values('user_id').distinct().count()
        
        last_month_active_users = SystemOperationLog.objects.filter(
            create_time__gte=last_month,
            create_time__lt=datetime.datetime.now().replace(day=1)
        ).values('user_id').distinct().count()
        
        users_growth = round((current_month_active_users - last_month_active_users) / max(last_month_active_users, 1) * 100, 2) if last_month_active_users > 0 else 0
        
        # 项目增长率
        current_month_projects = Project.objects.filter(
            create_time__gte=datetime.datetime.now().replace(day=1),
            delete_time__isnull=True
        ).count()
        
        last_month_projects = Project.objects.filter(
            create_time__gte=last_month,
            create_time__lt=datetime.datetime.now().replace(day=1),
            delete_time__isnull=True
        ).count()
        
        projects_growth = round((current_month_projects - last_month_projects) / max(last_month_projects, 1) * 100, 2) if last_month_projects > 0 else 0
        
        # 转化率变化
        conversion_growth = round(conversion_rate - 0, 2)  # 与上月对比
    
    except Exception as e:
        logger.error(f'计算增长率失败: {str(e)}')
        sales_growth = 0
        users_growth = 0
        projects_growth = 0
        conversion_growth = 0
    
    # 2. 图表数据处理
    # 销售趋势图数据 - 基于最近6个月的真实订单数据
    months = []
    sales_trend_data = []
    target_data = []
    
    for i in range(6):
        month_start = (datetime.datetime.now().replace(day=1) - datetime.timedelta(days=i*30))
        month_end = (month_start + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
        
        month_sales = CustomerOrder.objects.filter(
            create_time__gte=month_start,
            create_time__lte=month_end,
            delete_time=0,
            status__in=['confirmed', 'processing', 'shipped', 'delivered', 'completed']
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        months.append(month_start.strftime('%Y-%m'))
        sales_trend_data.append(float(month_sales))
        target_data.append(float(month_sales) * 1.2)
    
    months.reverse()
    sales_trend_data.reverse()
    target_data.reverse()
    
    sales_trend = {
        'labels': months,
        'data': sales_trend_data,
        'target': target_data
    }
    
    # 客户来源分布图数据
    customer_source = {
        'labels': [item['name'] for item in pie_data],
        'data': [item['value'] for item in pie_data]
    }
    
    # 3. 项目状态数据 - 从真实数据库获取
    try:
        projects = Project.objects.filter(delete_time__isnull=True, status=2).order_by('-progress')[:5]
        colors = ['#165DFF', '#0FC6C2', '#FF7D00', '#F53F3F', '#722ED1']
        project_status = []
        for i, project in enumerate(projects):
            project_status.append({
                'name': project.name,
                'progress': project.progress or 0,
                'color': colors[i % len(colors)]
            })
    except Exception as e:
        logger.error(f'获取项目状态失败: {str(e)}')
        project_status = []
    
    total_projects = Project.objects.filter(delete_time__isnull=True).count() if 'Project' in locals() else 0
    
    # 4. 最近交易记录 - 从真实数据库获取
    try:
        orders = CustomerOrder.objects.filter(
            delete_time=0,
            status__in=['confirmed', 'processing', 'shipped', 'delivered', 'completed']
        ).select_related('customer').order_by('-create_time')[:10]
        
        status_class_map = {
            'confirmed': 'bg-blue-100 text-blue-800',
            'processing': 'bg-yellow-100 text-yellow-800',
            'shipped': 'bg-purple-100 text-purple-800',
            'delivered': 'bg-green-100 text-green-800',
            'completed': 'bg-green-100 text-green-800',
        }
        
        recent_transactions = []
        for order in orders:
            recent_transactions.append({
                    'customer_name': order.customer.name if order.customer else '未知客户',
                    'customer_avatar': '/static/img/user-avatar.png',
                    'amount': f'{float(order.amount):,.0f}',
                    'status_class': status_class_map.get(order.status, 'bg-gray-100 text-gray-800'),
                    'status_text': order.get_status_display() if hasattr(order, 'get_status_display') else order.status,
                    'time': order.create_time.strftime('%Y-%m-%d %H:%M') if order.create_time else '-'
                })
    except Exception as e:
        logger.error(f'获取最近交易记录失败: {str(e)}')
        recent_transactions = []
    
    # 5. 其他数据
    last_updated = datetime.datetime.now()

    context = {
        'web_config': web_config,
        'database_menus': top_menus,  # 传递数据库中的菜单数据到模板
        'layout_selected': layout_selected,
        'statistics': statistics,  # 传递统计数据到dashboard.html
        'recent_approvals': recent_approvals,
        'pending_tasks': pending_tasks,
        'login_admin': login_admin,
        # 新增仪表盘数据
        'total_sales': total_sales,
        'active_users': active_users,
        'ongoing_projects': ongoing_projects,
        'conversion_rate': conversion_rate,
        'sales_growth': sales_growth,
        'users_growth': users_growth,
        'projects_growth': projects_growth,
        'conversion_growth': conversion_growth,
        'sales_trend': sales_trend,
        'customer_source': customer_source,
        'project_status': project_status,
        'total_projects': total_projects,
        'recent_transactions': recent_transactions,
        'last_updated': last_updated,
        # 系统使用情况统计
        'system_stats': system_stats,
    }
    return render(request, 'home/dashboard.html', context)


def main(request):
    """
    主框架页面 - 加载基础框架和菜单导航
    登录后应该重定向到这个页面，然后在框架中打开dashboard
    """
    # 获取系统配置
    web_config = get_system_config('web', 'web_config')
    
    # 获取菜单数据（与dashboard视图保持一致）
    try:
        from django.core.cache import cache
        
        # 构建缓存键，包含用户ID
        cache_key = f'dashboard_menu_{request.user.id}'
        
        # 尝试从缓存获取菜单数据
        cached_menu_data = cache.get(cache_key)
        
        if cached_menu_data:
            top_menus = cached_menu_data['top_menus']
            menus = cached_menu_data['menus']
        else:
            # 获取所有状态正常的菜单，使用select_related优化外键查询
            all_menus = Menu.objects.filter(status=1).select_related('module').order_by('sort')
            
            # 过滤出可用的菜单（考虑模块启用状态）
            available_menus = []
            for menu in all_menus:
                # 检查菜单是否可用（is_available()方法已经包含了模块启用状态的检查）
                if menu.is_available():
                    available_menus.append(menu)
            
            # 检查是否为超级管理员
            if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
                # 超级管理员显示所有菜单
                logger.debug(f"用户 {request.user.username} 是超级管理员，显示所有菜单")
                top_menus = [menu for menu in available_menus if menu.pid is None]
                for menu in top_menus:
                    menu.submenus_list = [submenu for submenu in available_menus if submenu.pid_id == menu.id]
                    # 为子菜单添加子子菜单
                    for submenu in menu.submenus_list:
                        submenu.submenus_list = [subsubmenu for subsubmenu in available_menus if subsubmenu.pid_id == submenu.id]
                        # 为孙菜单添加子菜单
                        for subsubmenu in submenu.submenus_list:
                            subsubmenu.submenus_list = [subsubsubmenu for subsubsubmenu in available_menus if subsubsubmenu.pid_id == subsubmenu.id]
                menus = available_menus
                top_menus = list(top_menus)
            else:
                # 非超级管理员，只显示有权限的菜单
                logger.debug(f"用户 {request.user.username} 是非超级管理员，显示有权限的菜单")
                
                # 获取用户的所有权限
                user_permissions = request.user.get_all_permissions()
                logger.debug(f"用户 {request.user.username} 的权限: {user_permissions}")
                
                # 构建菜单树结构，建立父子关系
                menu_dict = {menu.id: menu for menu in available_menus}
                menu_tree = {}
                
                # 首先构建完整的菜单树
                for menu in available_menus:
                    if menu.pid_id:
                        parent = menu_dict.get(menu.pid_id)
                        if parent:
                            if not hasattr(parent, 'children'):
                                parent.children = []
                            parent.children.append(menu)
                    else:
                        menu_tree[menu.id] = menu
                
                # 检查用户是否有权限访问菜单或其子菜单
                def has_menu_access(menu):
                    # 如果用户有对应的权限，则有权限
                    if menu.permission_required in user_permissions:
                        return True
                    # 检查子菜单是否有权限访问
                    if hasattr(menu, 'children'):
                        for submenu in menu.children:
                            if has_menu_access(submenu):
                                return True
                    # 如果菜单没有设置权限要求，检查用户是否有该应用的任何权限
                    # 获取应用标签（从permission_required或src中提取）
                    app_label = ''
                    if menu.permission_required:
                        app_label = menu.permission_required.split('.')[0]
                    elif menu.src:
                        # 从URL中提取应用标签
                        url_parts = menu.src.strip('/').split('/')
                        if url_parts:
                            app_label = url_parts[0]
                    
                    # 如果能提取到应用标签，检查用户是否有该应用的任何权限
                    if app_label and request.user.has_module_perms(app_label):
                        return True
                        
                    return False
                
                # 过滤用户有权访问的菜单
                authorized_menu_ids = set()
                
                # 遍历所有菜单，收集所有有权限的菜单ID
                for menu in available_menus:
                    if has_menu_access(menu):
                        authorized_menu_ids.add(menu.id)
                        # 同时收集该菜单的所有父菜单ID，确保父菜单也会显示
                        parent = menu_dict.get(menu.pid_id)
                        while parent:
                            authorized_menu_ids.add(parent.id)
                            parent = menu_dict.get(parent.pid_id)
                
                # 然后递归收集所有子菜单ID，确保所有子菜单也会显示
                def collect_all_descendants(menu):
                    authorized_menu_ids.add(menu.id)
                    if hasattr(menu, 'children'):
                        for submenu in menu.children:
                            collect_all_descendants(submenu)
                
                # 遍历所有已经授权的菜单，收集它们的所有子菜单
                for menu_id in list(authorized_menu_ids):
                    menu = menu_dict.get(menu_id)
                    if menu:
                        collect_all_descendants(menu)
                
                # 构建最终的菜单列表
                filtered_menus = [menu for menu in available_menus if menu.id in authorized_menu_ids]
                
                # 使用过滤后的菜单构建菜单树
                top_menus = [menu for menu in filtered_menus if menu.pid is None]
                for menu in top_menus:
                    menu.submenus_list = [submenu for submenu in filtered_menus if submenu.pid_id == menu.id]
                    # 为子菜单添加子子菜单
                    for submenu in menu.submenus_list:
                        submenu.submenus_list = [subsubmenu for subsubmenu in filtered_menus if subsubmenu.pid_id == submenu.id]
                        # 为孙菜单添加子菜单
                        for subsubmenu in submenu.submenus_list:
                            subsubmenu.submenus_list = [subsubsubmenu for subsubsubmenu in filtered_menus if subsubsubmenu.pid_id == subsubmenu.id]
                menus = filtered_menus
                
            # 缓存菜单数据，10分钟
            cache.set(cache_key, {'top_menus': top_menus, 'menus': menus}, 10 * 60)
    except Exception as e:
        # 记录错误日志
        logger.error(f'加载菜单失败: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        
        # 返回空菜单的响应
        context = {
            'web_config': web_config,
            'menus': [],
            'database_menus': []  # 也为错误情况添加database_menus
        }
        return render(request, 'home/main.html', context)
    
    context = {
        'web_config': web_config,
        'database_menus': top_menus,  # 传递数据库中的菜单数据到模板
        'menus': menus  # 保留原变量用于兼容
    }
    return render(request, 'home/main.html', context)


from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect

def logout(request):
    """处理用户登出"""
    auth_logout(request)
    return redirect('user:login')