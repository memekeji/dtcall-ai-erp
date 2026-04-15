from django.shortcuts import redirect
from django.contrib.auth import logout as auth_logout
from django.shortcuts import render
from apps.user.models import Menu
from dtcall.utils import get_system_config
from django.contrib.auth.decorators import login_required
import logging

logger = logging.getLogger('django')


def _build_menu_tree(
        available_menus,
        user_permissions=None,
        is_superuser=False):
    """构建菜单树结构（统一方法）

    Args:
        available_menus: 可用菜单列表
        user_permissions: 用户权限集合
        is_superuser: 是否超级管理员

    Returns:
        tuple: (top_menus, all_filtered_menus)
    """
    from apps.system.context_processors import get_permission_from_src

    if is_superuser:
        top_menus = [menu for menu in available_menus if menu.pid is None]
        for menu in top_menus:
            menu.submenus_list = [
                submenu for submenu in available_menus if submenu.pid_id == menu.id]
            for submenu in menu.submenus_list:
                submenu.submenus_list = [
                    subsubmenu for subsubmenu in available_menus if subsubmenu.pid_id == submenu.id]
                for subsubmenu in submenu.submenus_list:
                    subsubmenu.submenus_list = [
                        subsubsubmenu for subsubsubmenu in available_menus if subsubsubmenu.pid_id == subsubmenu.id]
        return top_menus, available_menus

    def _check_permission(codename):
        """检查是否有权限，支持view_*和add_*等权限"""
        if not codename:
            return False

        full_perm = f'user.{codename}' if not codename.startswith(
            'user.') else codename
        if full_perm in user_permissions or codename in user_permissions:
            return True

        view_codename = codename
        if codename.startswith('add_'):
            view_codename = 'view_' + codename[4:]
        elif codename.startswith('change_'):
            view_codename = 'view_' + codename[7:]
        elif codename.startswith('delete_'):
            view_codename = 'view_' + codename[7:]

        view_full = f'user.{view_codename}'
        if view_full in user_permissions or view_codename in user_permissions:
            return True

        return False

    def has_menu_access(menu):
        """检查用户是否有权限访问菜单"""
        if menu.permission_required:
            if _check_permission(menu.permission_required):
                return True

        if menu.src and menu.src != 'javascript:;':
            inferred_perm = get_permission_from_src(menu.src)
            if inferred_perm:
                if _check_permission(inferred_perm):
                    return True

        return False

    def get_descendants(menu_id):
        """获取菜单的所有直接子菜单"""
        return [m for m in available_menus if m.pid_id == menu_id]

    def findAuthorizedMenus():
        """递归查找所有有权限的菜单（包括通过后代继承的）"""
        authorized = set()

        def check_menu(menu_id):
            menu = menu_dict.get(menu_id)
            if not menu:
                return False

            has_access = has_menu_access(menu)
            children = get_descendants(menu_id)
            child_has_access = False

            for child in children:
                if check_menu(child.id):
                    child_has_access = True

            if has_access or child_has_access:
                authorized.add(menu_id)
                return True

            return False

        for menu in available_menus:
            if not menu.pid_id:
                check_menu(menu.id)

        return authorized

    menu_dict = {menu.id: menu for menu in available_menus}
    authorized_menu_ids = findAuthorizedMenus()

    filtered_menus = [
        menu for menu in available_menus if menu.id in authorized_menu_ids]

    top_menus = [menu for menu in filtered_menus if menu.pid is None]
    for menu in top_menus:
        menu.submenus_list = [
            submenu for submenu in filtered_menus if submenu.pid_id == menu.id]
        for submenu in menu.submenus_list:
            submenu.submenus_list = [
                subsubmenu for subsubmenu in filtered_menus if subsubmenu.pid_id == submenu.id]
            for subsubmenu in submenu.submenus_list:
                subsubmenu.submenus_list = [
                    subsubsubmenu for subsubsubmenu in filtered_menus if subsubsubmenu.pid_id == subsubmenu.id]

    return top_menus, filtered_menus


def _get_menus_for_user(request):
    """获取当前用户的菜单数据（统一方法）

    Returns:
        tuple: (top_menus, menus)
    """
    all_menus = Menu.objects.filter(
        status=1).select_related('module').order_by('sort')

    available_menus = []
    for menu in all_menus:
        if menu.is_available():
            available_menus.append(menu)

    is_superuser = getattr(request.user, 'is_superuser', False)
    user_permissions = request.user.get_all_permissions()

    if is_superuser or '*' in user_permissions:
        top_menus, menus = _build_menu_tree(available_menus, None, True)
    else:
        top_menus, menus = _build_menu_tree(
            available_menus, user_permissions, False)

    return top_menus, menus


@login_required
def dashboard(request):
    web_config = get_system_config('web', 'web_config')

    try:
        top_menus, menus = _get_menus_for_user(request)
    except Exception as e:
        logger.error(f'加载菜单失败: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        context = {
            'web_config': web_config,
            'menus': [],
            'database_menus': [],
            'layout_selected': []
        }
        return render(request, 'home/dashboard.html', context)

    from apps.task.models import Task
    from apps.approval.models import Approval
    from apps.message.models import MessageUserRelation
    from apps.customer.models import Customer, CustomerSource
    from apps.contract.models import Contract
    from apps.user.models import SystemOperationLog, Admin as User
    from django.db.models import Count
    import datetime
    import random
    from django.core.cache import cache
    from apps.project.models import Project
    from apps.customer.models import CustomerOrder
    from django.db.models import Sum

    is_superuser = getattr(request.user, 'is_superuser', False)

    cache_key = f'dashboard_data_{request.user.id}_{datetime.datetime.now().date()}'

    cached_dashboard_data = cache.get(cache_key)

    if cached_dashboard_data:
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
        todo_count = Task.objects.filter(
            assignee=request.user, status=0).count()
        approval_count = Approval.objects.filter(
            reviewer=request.user, status=0).count()
        message_count = MessageUserRelation.objects.filter(
            user=request.user, is_read=False).count()

        try:
            approval_processing = Approval.objects.filter(status=1).count()
        except Exception as e:
            logger.error(f'计算审批中数量失败: {str(e)}')
            approval_processing = 0

        try:
            completed_task_count = Task.objects.filter(
                assignee=request.user, status=2).count()
        except Exception as e:
            logger.error(f'计算最近完成任务数量失败: {str(e)}')
            completed_task_count = 0

        try:
            if is_superuser:
                total_users = User.objects.filter(is_active=True).count()
                total_customers = Customer.objects.filter(
                    delete_time=0).count()
                total_contracts = Contract.objects.filter(
                    delete_time=0).count()
                today_operations = SystemOperationLog.objects.filter(
                    create_time__date=datetime.datetime.now().date()
                ).count()

                current_month = datetime.datetime.now().replace(day=1)
                new_customers_month = Customer.objects.filter(
                    create_time__gte=current_month,
                    delete_time=0
                ).count()
                new_contracts_month = Contract.objects.filter(
                    create_time__gte=current_month,
                    delete_time=0
                ).count()

                source_counts = Customer.objects.filter(
                    delete_time=0).values('customer_source').annotate(
                    count=Count('id'))
                source_ids = [item['customer_source']
                              for item in source_counts if item['customer_source'] is not None]
                sources = {
                    s.id: s.title for s in CustomerSource.objects.filter(
                        id__in=source_ids)}
                pie_data = [
                    {
                        'name': sources.get(
                            item['customer_source'],
                            '未知来源'),
                        'value': item['count']} for item in source_counts if item['customer_source'] is not None]
            else:
                from django.db.models import Q

                total_users = User.objects.filter(
                    is_active=True, groups__admin=request.user).distinct().count()

                customer_filter = Q(delete_time=0) & (
                    Q(belong_uid=request.user.id) |
                    Q(share_ids__contains=str(request.user.id))
                )
                total_customers = Customer.objects.filter(
                    customer_filter).count()

                contract_filter = Q(delete_time=0) & (
                    Q(admin_id=request.user.id) |
                    Q(prepared_uid=request.user.id) |
                    Q(sign_uid=request.user.id) |
                    Q(share_ids__icontains=f',{request.user.id},') |
                    Q(share_ids__startswith=f'{request.user.id},') |
                    Q(share_ids__endswith=f',{request.user.id}') |
                    Q(share_ids=request.user.id)
                )
                total_contracts = Contract.objects.filter(
                    contract_filter).count()

                today_operations = SystemOperationLog.objects.filter(
                    create_time__date=datetime.datetime.now().date(),
                    user_id=request.user.id
                ).count()

                current_month = datetime.datetime.now().replace(day=1)
                new_customers_month = Customer.objects.filter(
                    create_time__gte=current_month,
                    delete_time=0,
                    belong_uid=request.user.id
                ).count()
                new_contracts_month = Contract.objects.filter(
                    create_time__gte=current_month,
                    delete_time=0
                ).filter(
                    Q(admin_id=request.user.id) |
                    Q(prepared_uid=request.user.id) |
                    Q(sign_uid=request.user.id) |
                    Q(share_ids__icontains=f',{request.user.id},') |
                    Q(share_ids__startswith=f'{request.user.id},') |
                    Q(share_ids__endswith=f',{request.user.id}') |
                    Q(share_ids=request.user.id)
                ).count()

                source_counts = Customer.objects.filter(customer_filter).values(
                    'customer_source').annotate(count=Count('id'))
                source_ids = [item['customer_source']
                              for item in source_counts if item['customer_source'] is not None]
                sources = {
                    s.id: s.title for s in CustomerSource.objects.filter(
                        id__in=source_ids)}
                pie_data = [
                    {
                        'name': sources.get(
                            item['customer_source'],
                            '未知来源'),
                        'value': item['count']} for item in source_counts if item['customer_source'] is not None]

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
            import traceback
            logger.error(traceback.format_exc())
            system_stats = {
                'total_users': 0,
                'total_customers': 0,
                'total_contracts': 0,
                'today_operations': 0,
                'new_customers_month': 0,
                'new_contracts_month': 0,
            }
            pie_data = []

        try:
            months = []
            for i in range(6):
                month = (
                    datetime.datetime.now() -
                    datetime.timedelta(
                        days=i *
                        30)).strftime('%Y-%m')
                months.append(month)
            months.reverse()

            trend_data = {
                'months': months,
                'sales': [random.randint(10000, 50000) for _ in months]
            }
        except Exception as e:
            logger.error(f'获取图表数据失败: {str(e)}')
            trend_data = {'months': [], 'sales': []}

        recent_approvals = Approval.objects.filter(
            reviewer=request.user).order_by('-create_time')[:5]
        pending_tasks = Task.objects.filter(
            assignee=request.user, status=0).order_by('-created_at')[:5]

        try:
            login_admin = request.user
        except Exception as e:
            logger.error(f'获取登录用户失败: {str(e)}')
            login_admin = None

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

    layout_selected = [
        {'row': 1, 'name': 'count'},
        {'row': 1, 'name': 'event'},
        {'row': 1, 'name': 'note'},
        {'row': 2, 'name': 'fastentry'},
        {'row': 2, 'name': 'approve'}
    ]

    statistics = [
        {'name': '待办任务', 'value': todo_count},
        {'name': '待审批', 'value': approval_count},
        {'name': '未读消息', 'value': message_count},
        {'name': '审批中', 'value': approval_processing},
        {'name': '最近完成任务', 'value': completed_task_count}
    ]

    from apps.customer.models import Customer, CustomerOrder
    from apps.project.models import Project
    from django.db.models import Sum

    try:
        from django.db.models import Q

        customer_filter = Q(delete_time=0) & (
            Q(belong_uid=request.user.id) |
            Q(share_ids__contains=str(request.user.id))
        )

        if is_superuser:
            total_sales = CustomerOrder.objects.filter(
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed']).aggregate(
                total=Sum('amount'))['total'] or 0
        else:
            total_sales = CustomerOrder.objects.filter(
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed'],
                customer__in=Customer.objects.filter(customer_filter)).aggregate(
                total=Sum('amount'))['total'] or 0
        total_sales = float(total_sales)
    except Exception as e:
        logger.error(f'获取总销售额失败: {str(e)}')
        total_sales = 0

    try:
        if is_superuser:
            active_users = SystemOperationLog.objects.filter(
                create_time__date=datetime.datetime.now().date()
            ).values('user_id').distinct().count()
        else:
            active_users = 1
    except Exception as e:
        logger.error(f'获取活跃用户数失败: {str(e)}')
        active_users = 0

    try:
        if is_superuser:
            ongoing_projects = Project.objects.filter(
                delete_time__isnull=True, status=2).count()
        else:
            ongoing_projects = Project.objects.filter(
                delete_time__isnull=True, status=2, manager=request.user).count()
    except Exception as e:
        logger.error(f'获取进行中项目数失败: {str(e)}')
        ongoing_projects = 0

    try:
        if is_superuser:
            total_customers_count = Customer.objects.filter(
                delete_time=0).count()
            customers_with_orders = CustomerOrder.objects.filter(
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed']).values('customer_id').distinct().count()
        else:
            total_customers_count = Customer.objects.filter(
                customer_filter).count()
            customers_with_orders = CustomerOrder.objects.filter(
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed'],
                customer__in=Customer.objects.filter(customer_filter)
            ).values('customer_id').distinct().count()
        conversion_rate = round((customers_with_orders /
                                 max(total_customers_count, 1)) *
                                100, 2) if total_customers_count > 0 else 0
    except Exception as e:
        logger.error(f'获取客户转化率失败: {str(e)}')
        conversion_rate = 0

    try:
        last_month = (
            datetime.datetime.now().replace(
                day=1) -
            datetime.timedelta(
                days=1)).replace(
            day=1)

        if is_superuser:
            current_month_sales = CustomerOrder.objects.filter(
                create_time__gte=datetime.datetime.now().replace(
                    day=1), delete_time=0, status__in=[
                    'confirmed', 'processing', 'shipped', 'delivered', 'completed']).aggregate(
                total=Sum('amount'))['total'] or 0

            last_month_sales = CustomerOrder.objects.filter(
                create_time__gte=last_month, create_time__lt=datetime.datetime.now().replace(
                    day=1), delete_time=0, status__in=[
                    'confirmed', 'processing', 'shipped', 'delivered', 'completed']).aggregate(
                total=Sum('amount'))['total'] or 0
        else:
            current_month_sales = CustomerOrder.objects.filter(
                create_time__gte=datetime.datetime.now().replace(
                    day=1),
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed'],
                customer__in=Customer.objects.filter(customer_filter)).aggregate(
                total=Sum('amount'))['total'] or 0

            last_month_sales = CustomerOrder.objects.filter(
                create_time__gte=last_month,
                create_time__lt=datetime.datetime.now().replace(
                    day=1),
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed'],
                customer__in=Customer.objects.filter(customer_filter)).aggregate(
                total=Sum('amount'))['total'] or 0

        sales_growth = round((float(current_month_sales) -
                              float(last_month_sales)) /
                             max(float(last_month_sales), 1) *
                             100, 2) if float(last_month_sales) > 0 else 0

        if is_superuser:
            current_month_active_users = SystemOperationLog.objects.filter(
                create_time__gte=datetime.datetime.now().replace(day=1)
            ).values('user_id').distinct().count()

            last_month_active_users = SystemOperationLog.objects.filter(
                create_time__gte=last_month,
                create_time__lt=datetime.datetime.now().replace(day=1)
            ).values('user_id').distinct().count()

            current_month_projects = Project.objects.filter(
                create_time__gte=datetime.datetime.now().replace(day=1),
                delete_time__isnull=True
            ).count()

            last_month_projects = Project.objects.filter(
                create_time__gte=last_month,
                create_time__lt=datetime.datetime.now().replace(day=1),
                delete_time__isnull=True
            ).count()
        else:
            current_month_active_users = 1

            last_month_active_users = 1

            current_month_projects = Project.objects.filter(
                create_time__gte=datetime.datetime.now().replace(day=1),
                delete_time__isnull=True,
                manager=request.user
            ).count()

            last_month_projects = Project.objects.filter(
                create_time__gte=last_month,
                create_time__lt=datetime.datetime.now().replace(day=1),
                delete_time__isnull=True,
                manager=request.user
            ).count()

        users_growth = round((current_month_active_users -
                              last_month_active_users) /
                             max(last_month_active_users, 1) *
                             100, 2) if last_month_active_users > 0 else 0

        projects_growth = round((current_month_projects -
                                 last_month_projects) /
                                max(last_month_projects, 1) *
                                100, 2) if last_month_projects > 0 else 0

        conversion_growth = round(conversion_rate - 0, 2)

    except Exception as e:
        logger.error(f'计算增长率失败: {str(e)}')
        sales_growth = 0
        users_growth = 0
        projects_growth = 0
        conversion_growth = 0

    months = []
    sales_trend_data = []
    target_data = []

    for i in range(6):
        month_start = (
            datetime.datetime.now().replace(
                day=1) -
            datetime.timedelta(
                days=i *
                30))
        month_end = (month_start + datetime.timedelta(days=32)
                     ).replace(day=1) - datetime.timedelta(days=1)

        if is_superuser:
            month_sales = CustomerOrder.objects.filter(
                create_time__gte=month_start,
                create_time__lte=month_end,
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed']).aggregate(
                total=Sum('amount'))['total'] or 0
        else:
            month_sales = CustomerOrder.objects.filter(
                create_time__gte=month_start,
                create_time__lte=month_end,
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed'],
                customer__in=Customer.objects.filter(customer_filter)).aggregate(
                total=Sum('amount'))['total'] or 0

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

    customer_source = {
        'labels': [item['name'] for item in pie_data],
        'data': [item['value'] for item in pie_data]
    }

    try:
        if is_superuser:
            projects = Project.objects.filter(
                delete_time__isnull=True, status=2).order_by('-progress')[:5]
        else:
            projects = Project.objects.filter(
                delete_time__isnull=True, status=2, manager=request.user).order_by('-progress')[:5]
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

    try:
        if is_superuser:
            total_projects = Project.objects.filter(
                delete_time__isnull=True).count()
        else:
            total_projects = Project.objects.filter(
                delete_time__isnull=True, manager=request.user).count()
    except Exception as e:
        logger.error(f'获取项目总数失败: {str(e)}')
        total_projects = 0

    try:
        if is_superuser:
            orders = CustomerOrder.objects.filter(
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed']
            ).select_related('customer').order_by('-create_time')[:10]
        else:
            orders = CustomerOrder.objects.filter(
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed'],
                customer__in=Customer.objects.filter(customer_filter)
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

    last_updated = datetime.datetime.now()

    context = {
        'web_config': web_config,
        'database_menus': top_menus,
        'layout_selected': layout_selected,
        'statistics': statistics,
        'recent_approvals': recent_approvals,
        'pending_tasks': pending_tasks,
        'login_admin': login_admin,
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
        'system_stats': system_stats,
    }
    return render(request, 'home/dashboard.html', context)


@login_required
def main(request):
    web_config = get_system_config('web', 'web_config')

    try:
        top_menus, menus = _get_menus_for_user(request)
    except Exception as e:
        logger.error(f'加载菜单失败: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        context = {
            'web_config': web_config,
            'menus': [],
            'database_menus': []
        }
        return render(request, 'home/main.html', context)

    context = {
        'web_config': web_config,
        'database_menus': top_menus,
        'menus': menus
    }
    return render(request, 'home/main.html', context)


def logout(request):
    auth_logout(request)
    return redirect('user:login')
