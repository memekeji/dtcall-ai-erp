from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone
from apps.user.models import Admin
from datetime import timedelta
import json
import logging

User = get_user_model()
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

    def check_menu_permission(menu):
        """检查用户是否有权限访问菜单"""
        if not menu.src or menu.src == 'javascript:;':
            return False

        if menu.permission_required:
            perm_key = f'user.{menu.permission_required}' if '.' not in menu.permission_required else menu.permission_required
            if perm_key in user_permissions or menu.permission_required in user_permissions:
                return True

        inferred_perm = get_permission_from_src(menu.src)
        if inferred_perm:
            full_perm = f'user.{inferred_perm}' if not inferred_perm.startswith(
                'user.') else inferred_perm
            if inferred_perm in user_permissions or full_perm in user_permissions:
                return True

        return False

    def collect_descendants(menu_id):
        """收集菜单的所有后代ID"""
        descendant_ids = set()
        children = [m for m in available_menus if m.pid_id == menu_id]
        for child in children:
            descendant_ids.add(child.id)
            descendant_ids.update(collect_descendants(child.id))
        return descendant_ids

    menu_dict = {menu.id: menu for menu in available_menus}
    for menu in available_menus:
        menu.children = []
        menu.submenus_list = []

    for menu in available_menus:
        if menu.pid_id:
            parent = menu_dict.get(menu.pid_id)
            if parent:
                parent.children.append(menu)

    authorized_menu_ids = set()

    for menu in available_menus:
        if check_menu_permission(menu):
            authorized_menu_ids.add(menu.id)
            current = menu
            while current and current.pid_id:
                authorized_menu_ids.add(current.pid_id)
                current = menu_dict.get(current.pid_id)

    for menu_id in list(authorized_menu_ids):
        menu = menu_dict.get(menu_id)
        if menu:
            descendants = collect_descendants(menu_id)
            authorized_menu_ids.update(descendants)

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


INDUSTRY_CHOICES = {
    0: '其他',
    1: '互联网',
    2: '金融',
    3: '制造业',
    4: '零售',
    5: '医疗',
    6: '教育',
    7: '房地产',
    8: '物流',
    9: '餐饮',
    10: '旅游',
    11: '能源',
    12: '农业',
    13: '媒体',
    14: '娱乐',
    15: '体育',
    16: '汽车',
    17: '建筑',
    18: '法律',
    19: '咨询',
    20: '服务业',
}


@login_required
def dashboard(request):
    """数据大屏"""
    try:
        # 获取真实业务数据
        from apps.customer.models import Customer
        from apps.contract.models import Contract
        from apps.project.models import Project

        # 基础统计数据
        current_month = timezone.now().replace(day=1)

        # 删除错误的卡片数据，这些数据不准确
        # 不再计算总销售额、活跃用户、进行中项目、客户转化率

        # 销售趋势数据（最近6个月）- 基于客户订单数据
        from apps.customer.models import CustomerOrder
        months = []
        sales_data = []
        target_data = []

        for i in range(6):
            month_start = (
                timezone.now().replace(
                    day=1) -
                timedelta(
                    days=i *
                    30))
            month_end = (month_start + timedelta(days=32)
                         ).replace(day=1) - timedelta(days=1)

            # 使用客户订单数据计算销售趋势
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

            months.append(month_start.strftime('%Y-%m'))
            sales_data.append(float(month_sales))
            target_data.append(float(month_sales * 1.2))  # 目标为实际的120%

        months.reverse()
        sales_data.reverse()
        target_data.reverse()

        sales_trend = {
            'labels': json.dumps(months),
            'data': json.dumps(sales_data),
            'target': json.dumps(target_data)
        }

        # 客户来源分布
        source_data = Customer.objects.filter(delete_time=0).values(
            'customer_source__title').annotate(count=Count('id')).order_by('-count')[:6]

        customer_source = {
            'labels': json.dumps([item['customer_source__title'] or '未知来源' for item in source_data]),
            'data': json.dumps([item['count'] for item in source_data])
        }

        # 项目状态 - 显示真实项目数据
        project_status = []
        try:
            # 查询真实的项目数据，使用正确的状态值
            projects = Project.objects.filter(
                delete_time__isnull=True, status=2)[
                :5]  # status=2表示进行中
            colors = ['#165DFF', '#0FC6C2', '#FF7D00', '#F53F3F', '#722ED1']

            for i, project in enumerate(projects):
                project_status.append({
                    'name': project.name,
                    'progress': project.progress or 0,
                    'color': colors[i % len(colors)]
                })
        except Exception as e:
            logger.error(f'获取项目数据失败: {str(e)}')
            project_status = []

        # 最近交易记录 - 使用客户订单数据
        recent_transactions = []
        try:
            orders = CustomerOrder.objects.filter(
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed']
            ).select_related('customer').order_by('-create_time')[:10]

            for order in orders:
                status_class_map = {
                    'confirmed': 'bg-blue-100 text-blue-800',
                    'processing': 'bg-yellow-100 text-yellow-800',
                    'shipped': 'bg-purple-100 text-purple-800',
                    'delivered': 'bg-green-100 text-green-800',
                    'completed': 'bg-green-100 text-green-800',
                }

                recent_transactions.append({
                    'customer_name': order.customer.name if order.customer else '未知客户',
                    'customer_avatar': '/static/img/user-avatar.png',
                    'amount': f'{order.amount:,.0f}',
                    'status_class': status_class_map.get(order.status, 'bg-gray-100 text-gray-800'),
                    'status_text': order.get_status_display(),
                    'time': order.created_at.strftime('%Y-%m-%d') if order.created_at else '-'
                })
        except Exception as e:
            logger.error(f'获取订单数据失败: {str(e)}')
            recent_transactions = []

    except Exception as e:
        logger.error(f'获取仪表盘数据失败: {str(e)}')
        sales_trend = {
            'labels': json.dumps([]),
            'data': json.dumps([]),
            'target': json.dumps([])
        }
        customer_source = {
            'labels': json.dumps([]),
            'data': json.dumps([])
        }
        project_status = []
        recent_transactions = []

    # 添加系统使用情况统计
    try:
        from apps.user.models import SystemOperationLog

        # 系统基本统计
        total_users = Admin.objects.filter(status=1).count()

        # 修正客户数统计：用户客户 + 公海客户
        user_customers_count = Customer.objects.filter(
            delete_time=0, belong_uid__gt=0).count()
        public_customers_count = Customer.objects.filter(
            delete_time=0, belong_uid=0).count()
        total_customers_count = user_customers_count + public_customers_count

        total_contracts_count = Contract.objects.filter(delete_time=0).count()
        today_operations = SystemOperationLog.objects.filter(
            created_at__date=timezone.now().date()
        ).count()

        # 本月新增统计
        # 客户的 create_time 是 DateTimeField
        new_customers_month = Customer.objects.filter(
            create_time__gte=current_month,
            delete_time=0
        ).count()
        # 合同的 create_time 是 DateTimeField
        new_contracts_month = Contract.objects.filter(
            create_time__gte=current_month,
            delete_time=0
        ).count()

        # 系统使用情况统计
        system_stats = {
            'total_users': total_users,
            'total_customers': total_customers_count,
            'total_contracts': total_contracts_count,
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

    context = {
        # 图表数据
        'sales_trend': sales_trend,
        'customer_source': customer_source,

        # 列表数据
        'project_status': project_status,
        'recent_transactions': recent_transactions,
        'total_projects': Project.objects.count() if 'Project' in locals() else 0,

        # 系统使用情况统计
        'system_stats': system_stats,

        # 其他
        'last_updated': timezone.now(),
    }

    return render(request, 'home/dashboard.html', context)


@login_required
def finance_dashboard(request):
    """财务大屏"""
    from apps.finance.models import Expense, Invoice, Income
    from apps.contract.models import Contract
    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import timedelta

    try:
        current_month = timezone.now().replace(day=1)
        last_month = (current_month - timedelta(days=1)).replace(day=1)

        current_month_ts = int(current_month.timestamp())
        last_month_ts = int(last_month.timestamp())

        # 营业收入 = 合同金额(已审核) + 收入记录
        contract_revenue = Contract.objects.filter(
            create_time__gte=current_month,
            delete_time=0,
            check_status=2
        ).aggregate(total=Sum('cost'))['total'] or 0

        other_revenue = Income.objects.filter(
            create_time__gte=current_month_ts
        ).aggregate(total=Sum('amount'))['total'] or 0

        revenue = float(contract_revenue) + float(other_revenue)

        # 上月收入
        contract_revenue_last = Contract.objects.filter(
            create_time__gte=last_month,
            create_time__lt=current_month,
            delete_time=0,
            check_status=2
        ).aggregate(total=Sum('cost'))['total'] or 0

        other_revenue_last = Income.objects.filter(
            create_time__gte=last_month_ts,
            create_time__lt=current_month_ts
        ).aggregate(total=Sum('amount'))['total'] or 0

        revenue_last = float(contract_revenue_last) + float(other_revenue_last)
        revenue_growth = round((revenue -
                                revenue_last) /
                               max(revenue_last, 1) *
                               100, 1) if revenue_last > 0 else 0

        # 毛利 = 收入 - 成本（约20%成本率）
        gross_profit_rate = 0.8  # 假设毛利率80%
        gross_profit = revenue * gross_profit_rate
        gross_profit_last = revenue_last * gross_profit_rate
        gross_profit_growth = round((gross_profit -
                                     gross_profit_last) /
                                    max(gross_profit_last, 1) *
                                    100, 1) if gross_profit_last > 0 else 0

        # 费用 = 报销支出
        expense = Expense.objects.filter(
            create_time__gte=current_month_ts
        ).aggregate(total=Sum('cost'))['total'] or 0

        expense_last = Expense.objects.filter(
            create_time__gte=last_month_ts,
            create_time__lt=current_month_ts
        ).aggregate(total=Sum('cost'))['total'] or 0
        expense_growth = round((expense -
                                expense_last) /
                               max(expense_last, 1) *
                               100, 1) if expense_last > 0 else 0

        # 净利润
        net_profit = gross_profit - float(expense)
        net_profit_last = gross_profit_last - float(expense_last)
        net_profit_growth = round((net_profit -
                                   net_profit_last) /
                                  max(net_profit_last, 1) *
                                  100, 1) if net_profit_last > 0 else 0

        # 收支趋势（最近12个月）
        months = []
        income_trend = []
        expense_trend = []
        profit_trend_data = []

        for i in range(12):
            month_start = (
                timezone.now().replace(
                    day=1) -
                timedelta(
                    days=i *
                    30))
            month_end = (month_start + timedelta(days=32)
                         ).replace(day=1) - timedelta(days=1)

            month_start_ts = int(month_start.timestamp())
            month_end_ts = int(month_end.timestamp())

            # 收入
            month_contract = Contract.objects.filter(
                create_time__gte=month_start,
                create_time__lte=month_end,
                delete_time=0,
                check_status=2
            ).aggregate(total=Sum('cost'))['total'] or 0

            month_other = Income.objects.filter(
                create_time__gte=month_start_ts,
                create_time__lte=month_end_ts
            ).aggregate(total=Sum('amount'))['total'] or 0

            month_income = float(month_contract) + float(month_other)

            # 支出
            month_exp = Expense.objects.filter(
                create_time__gte=month_start_ts,
                create_time__lte=month_end_ts
            ).aggregate(total=Sum('cost'))['total'] or 0

            months.append(month_start.strftime('%Y-%m'))
            income_trend.append(month_income)
            expense_trend.append(float(month_exp))
            profit_trend_data.append(
                month_income *
                gross_profit_rate -
                float(month_exp))

        months.reverse()
        income_trend.reverse()
        expense_trend.reverse()
        profit_trend_data.reverse()

        income_expense_trend = {
            'labels': json.dumps(months),
            'income': json.dumps(income_trend),
            'expense': json.dumps(expense_trend)
        }

        profit_trend = {
            'labels': json.dumps(months),
            'net_profit': json.dumps(profit_trend_data)
        }

        # 收入分类
        # 按合同类型分类
        contract_by_type = Contract.objects.filter(
            delete_time=0,
            check_status=2
        ).values('types').annotate(count=Count('id'), total=Sum('cost'))

        type_names = {1: '普通合同', 2: '商品合同', 3: '服务合同'}
        revenue_category = {
            'labels': json.dumps([type_names.get(item['types'], '其他') for item in contract_by_type]),
            'data': json.dumps([float(item['total']) for item in contract_by_type])
        }

        # ============ 费用分类 ============
        # 费用类型分析 - 按费用类型统计
        expense_by_category = Expense.objects.filter(
            create_time__gte=current_month_ts
        ).aggregate(total=Sum('cost')) or {'total': 0}

        expense_category = {
            'labels': json.dumps(['费用支出']),
            'data': json.dumps([float(expense_by_category['total'] or 0)])
        }

        # 回款统计
        # 已回款（全部回款）
        received_amount = Invoice.objects.filter(
            create_time__gte=current_month_ts,
            enter_status=2
        ).aggregate(total=Sum('enter_amount'))['total'] or 0

        # 待回款（未回款+部分回款）
        pending_amount = Invoice.objects.filter(
            create_time__gte=current_month_ts,
            enter_status__in=[0, 1]
        ).aggregate(total=Sum('amount') - Sum('enter_amount'))['total'] or 0

        # 逾期金额（假设发票创建超过30天且未全回款为逾期）
        overdue_amount = Invoice.objects.filter(
            create_time__gte=int(
                (current_month -
                 timedelta(
                     days=30)).timestamp()),
            create_time__lt=current_month_ts,
            enter_status__in=[
                0,
                1]).aggregate(
                    total=Sum('amount') -
            Sum('enter_amount'))['total'] or 0

        # 回款率
        total_receivable = float(received_amount) + \
            float(pending_amount) + float(overdue_amount)
        collection_rate = round(
            float(received_amount) / max(total_receivable, 1) * 100, 1)

        # 应收账款TOP5
        accounts_receivable = []
        try:
            receivables = Invoice.objects.filter(
                enter_status__in=[0, 1]
            ).order_by('-amount')[:5]

            for r in receivables:
                accounts_receivable.append({
                    'customer_name': f'客户{r.customer_id}' if r.customer_id else '未知客户',
                    'amount': float(r.amount)
                })
        except Exception as e:
            logger.error(f'获取应收账款失败: {str(e)}')
            accounts_receivable = []

        # ============ 费用分析（按类型） ============
        expense_by_type_total = Expense.objects.filter(
            create_time__gte=current_month_ts
        ).aggregate(total=Sum('cost')) or {'total': 0}

        expense_analysis = {
            'labels': json.dumps(['费用支出']),
            'data': json.dumps([float(expense_by_type_total['total'] or 0)])
        }

        # 财务预警
        finance_warnings = []
        try:
            # 逾期账款预警
            overdue_count = Invoice.objects.filter(
                enter_status__in=[0, 1],
                create_time__lt=int(
                    (current_month - timedelta(days=30)).timestamp())
            ).count()
            if overdue_count > 0:
                finance_warnings.append({
                    'level': 'danger',
                    'title': '逾期账款',
                    'description': f'{overdue_count}笔账款已逾期，请及时催收'
                })

            # 回款率低预警
            if collection_rate < 50:
                finance_warnings.append({
                    'level': 'warning',
                    'title': '回款率预警',
                    'description': f'本月回款率仅{collection_rate}%，低于50%警戒线'
                })

            # 大额支出预警
            large_expenses = Expense.objects.filter(
                create_time__gte=current_month_ts,
                cost__gte=10000
            ).count()
            if large_expenses > 5:
                finance_warnings.append({
                    'level': 'info',
                    'title': '大额支出提醒',
                    'description': f'本月有{large_expenses}笔超过万元的大额支出'
                })
        except Exception as e:
            logger.error(f'获取财务预警失败: {str(e)}')

    except Exception as e:
        logger.error(f'获取财务数据失败: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        revenue = 0
        gross_profit = 0
        expense = 0
        net_profit = 0
        revenue_growth = 0
        gross_profit_growth = 0
        expense_growth = 0
        net_profit_growth = 0
        income_expense_trend = {
            'labels': '[]',
            'income': '[]',
            'expense': '[]'}
        profit_trend = {'labels': '[]', 'net_profit': '[]'}
        revenue_category = {'labels': '[]', 'data': '[]'}
        expense_category = {'labels': '[]', 'data': '[]'}
        received_amount = 0
        pending_amount = 0
        overdue_amount = 0
        collection_rate = 0
        accounts_receivable = []
        expense_analysis = {'labels': '[]', 'data': '[]'}
        finance_warnings = []

    context = {
        'revenue': round(revenue, 2),
        'gross_profit': round(gross_profit, 2),
        'expense': round(expense, 2),
        'net_profit': round(net_profit, 2),
        'revenue_growth': revenue_growth,
        'gross_profit_growth': gross_profit_growth,
        'expense_growth': expense_growth,
        'net_profit_growth': net_profit_growth,
        'income_expense_trend': income_expense_trend,
        'profit_trend': profit_trend,
        'revenue_category': revenue_category,
        'expense_category': expense_category,
        'received_amount': round(received_amount, 2),
        'pending_amount': round(pending_amount, 2),
        'overdue_amount': round(overdue_amount, 2),
        'collection_rate': collection_rate,
        'accounts_receivable': accounts_receivable,
        'expense_analysis': expense_analysis,
        'finance_warnings': finance_warnings,
        'last_updated': timezone.now(),
    }

    return render(request, 'home/finance_dashboard.html', context)


@login_required
def business_dashboard(request):
    """经营大屏"""
    try:
        from apps.customer.models import Customer
        from apps.contract.models import Contract
        from apps.customer.models import CustomerOrder
        from apps.finance.models import Expense

        current_month = timezone.now().replace(day=1)
        last_month = (current_month - timedelta(days=1)).replace(day=1)

        # 经营核心指标
        # 新增客户 - 客户的 create_time 是 DateTimeField
        new_customers = Customer.objects.filter(
            create_time__gte=current_month,
            delete_time=0
        ).count()

        # 上月新增客户
        new_customers_last = Customer.objects.filter(
            create_time__gte=last_month,
            create_time__lt=current_month,
            delete_time=0
        ).count()

        # 增长率
        new_customers_growth = round((new_customers -
                                      new_customers_last) /
                                     max(new_customers_last, 1) *
                                     100, 1) if new_customers_last > 0 else 0

        # 签约客户（有合同的客户）
        signed_customer_ids = Contract.objects.filter(
            check_status=2
        ).values_list('customer_id', flat=True).distinct()

        signed_customers = Customer.objects.filter(
            delete_time=0,
            id__in=signed_customer_ids
        ).count()

        # 上月签约客户
        signed_customers_last = Customer.objects.filter(
            delete_time=0,
            id__in=signed_customer_ids,
            create_time__gte=last_month,
            create_time__lt=current_month
        ).count()

        signed_customers_growth = round((signed_customers -
                                         signed_customers_last) /
                                        max(signed_customers_last, 1) *
                                        100, 1) if signed_customers_last > 0 else 0

        # 客户满意度（从系统配置获取或计算）
        try:
            from apps.user.models import SystemConfiguration
            sat_cfg = SystemConfiguration.objects.filter(
                key='customer_satisfaction', is_active=True).first()
            customer_satisfaction = float(sat_cfg.value) if sat_cfg else 85.0
        except BaseException:
            customer_satisfaction = 85.0

        # 客户满意度变化
        try:
            from apps.user.models import SystemConfiguration
            sat_cfg_last = SystemConfiguration.objects.filter(
                key='customer_satisfaction_last', is_active=True).first()
            satisfaction_last = float(
                sat_cfg_last.value) if sat_cfg_last else customer_satisfaction
            satisfaction_growth = round(
                customer_satisfaction - satisfaction_last, 1)
        except BaseException:
            satisfaction_growth = 0

        # 市场占有率（从系统配置获取）
        try:
            from apps.user.models import SystemConfiguration
            share_cfg = SystemConfiguration.objects.filter(
                key='market_share', is_active=True).first()
            market_share = float(share_cfg.value) if share_cfg else 0
        except BaseException:
            market_share = 0

        # 市场占有率变化
        try:
            from apps.user.models import SystemConfiguration
            share_cfg_last = SystemConfiguration.objects.filter(
                key='market_share_last', is_active=True).first()
            share_last = float(
                share_cfg_last.value) if share_cfg_last else market_share
            market_share_growth = round(market_share - share_last, 1)
        except BaseException:
            market_share_growth = 0

        # 客户分布数据（按省份）
        customer_distribution = Customer.objects.filter(delete_time=0).values(
            'province'
        ).annotate(count=Count('id')).order_by('-count')[:8]

        distribution_data = {
            'labels': json.dumps([item['province'] or '未知地区' for item in customer_distribution]),
            'data': json.dumps([item['count'] for item in customer_distribution])
        }

        # 客户转化漏斗数据
        all_customers = Customer.objects.filter(delete_time=0).count()
        interested_customers = Customer.objects.filter(
            delete_time=0, services_id__in=[2, 3]).count()
        opportunity_customers = Customer.objects.filter(
            delete_time=0, services_id__in=[4, 6]).count()
        signed_all_customers = signed_customers

        funnel_data = {
            'potential': all_customers,
            'interested': interested_customers,
            'opportunity': opportunity_customers,
            'signed': signed_all_customers
        }

        # 销售排行榜（基于订单金额）
        sales_ranking = []
        try:
            # 按客户统计订单金额
            customer_orders = CustomerOrder.objects.filter(
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed']
            ).values('customer_id', 'customer__name').annotate(
                total_amount=Sum('amount')
            ).order_by('-total_amount')[:5]

            for item in customer_orders:
                sales_ranking.append({
                    'name': item['customer__name'] or '未知客户',
                    'amount': float(item['total_amount'])
                })
        except Exception as e:
            logger.error(f'获取销售排行失败: {str(e)}')
            sales_ranking = []

        # 客户行业分布
        industry_data = {'labels': '[]', 'data': '[]'}
        try:
            industry_dist = Customer.objects.filter(delete_time=0).values(
                'industry_id'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:6]

            industry_data = {
                'labels': json.dumps([INDUSTRY_CHOICES.get(item['industry_id'], '其他') for item in industry_dist]),
                'data': json.dumps([item['count'] for item in industry_dist])
            }
        except Exception as e:
            logger.error(f'获取行业分布失败: {str(e)}')

        # 经营指标
        # CAC - 客户获取成本
        try:
            current_month_ts = int(current_month.timestamp())
            marketing_expense = Expense.objects.filter(
                create_time__gte=current_month_ts,
                category__name__icontains='市场'
            ).aggregate(total=Sum('cost'))['total'] or 0
            cac = round(marketing_expense / max(new_customers, 1),
                        2) if new_customers > 0 else 0
        except BaseException:
            cac = 0

        # LTV - 客户生命周期价值 = 平均订单金额 * 平均订单数 * 平均客户生命周期
        try:
            avg_order_amount = CustomerOrder.objects.filter(
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed']).aggregate(
                avg=Sum('amount') /
                Count('id'))['avg'] or 0
            avg_orders_per_customer = CustomerOrder.objects.filter(
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed']
            ).count() / max(Customer.objects.filter(delete_time=0).count(), 1)
            ltv = round(
                avg_order_amount *
                avg_orders_per_customer *
                24,
                2)  # 假设24个月生命周期
        except BaseException:
            ltv = 0

        # 客户流失率
        try:
            churn_rate = 0  # 需要历史数据计算
        except BaseException:
            churn_rate = 0

        # AOV - 平均订单价值
        try:
            aov = CustomerOrder.objects.filter(
                delete_time=0,
                status__in=[
                    'confirmed',
                    'processing',
                    'shipped',
                    'delivered',
                    'completed']).aggregate(
                avg=Sum('amount') /
                Count('id'))['avg'] or 0
            aov = round(aov, 2)
        except BaseException:
            aov = 0

    except Exception as e:
        logger.error(f'获取经营数据失败: {str(e)}')
        new_customers = 0
        signed_customers = 0
        new_customers_growth = 0
        signed_customers_growth = 0
        customer_satisfaction = 0
        satisfaction_growth = 0
        market_share = 0
        market_share_growth = 0
        distribution_data = {
            'labels': '[]',
            'data': '[]'
        }
        funnel_data = {
            'potential': 0,
            'interested': 0,
            'opportunity': 0,
            'signed': 0}
        sales_ranking = []
        industry_data = {'labels': '[]', 'data': '[]'}
        cac = 0
        ltv = 0
        churn_rate = 0
        aov = 0

    context = {
        'new_customers': new_customers,
        'signed_customers': signed_customers,
        'new_customers_growth': new_customers_growth,
        'signed_customers_growth': signed_customers_growth,
        'customer_satisfaction': customer_satisfaction,
        'satisfaction_growth': satisfaction_growth,
        'market_share': market_share,
        'market_share_growth': market_share_growth,
        'distribution_data': distribution_data,
        'funnel_data': funnel_data,
        'sales_ranking': sales_ranking,
        'industry_data': industry_data,
        'cac': cac,
        'ltv': ltv,
        'churn_rate': churn_rate,
        'aov': aov,
        'last_updated': timezone.now(),
    }

    return render(request, 'home/business_dashboard.html', context)


@login_required
def production_dashboard(request):
    """生产大屏"""
    from apps.production.models import ProductionPlan, ProductionTask, Equipment
    from django.utils import timezone
    from datetime import timedelta

    try:
        current_month = timezone.now().replace(day=1)
        last_month = (current_month - timedelta(days=1)).replace(day=1)

        # 本月核心生产指标
        # 本月生产计划
        monthly_plans = ProductionPlan.objects.filter(
            plan_start_date__gte=current_month
        ).count()

        # 上月生产计划
        monthly_plans_last = ProductionPlan.objects.filter(
            plan_start_date__gte=last_month,
            plan_start_date__lt=current_month
        ).count()

        monthly_plans_growth = round((monthly_plans -
                                      monthly_plans_last) /
                                     max(monthly_plans_last, 1) *
                                     100, 1) if monthly_plans_last > 0 else 0

        # 完成任务
        completed_tasks = ProductionTask.objects.filter(
            actual_end_time__gte=current_month,
            status=3
        ).count()

        # 上月完成任务
        completed_tasks_last = ProductionTask.objects.filter(
            actual_end_time__gte=last_month,
            actual_end_time__lt=current_month,
            status=3
        ).count()

        completed_tasks_growth = round((completed_tasks -
                                        completed_tasks_last) /
                                       max(completed_tasks_last, 1) *
                                       100, 1) if completed_tasks_last > 0 else 0

        # 设备利用率
        total_equipment = Equipment.objects.count()
        active_equipment = Equipment.objects.filter(
            status=1,
            productiontask__status=2
        ).distinct().count()
        equipment_utilization = round(
            (active_equipment / max(total_equipment, 1)) * 100, 1)

        # 上月设备利用率
        equipment_utilization_last = equipment_utilization
        equipment_utilization_growth = round(
            equipment_utilization - equipment_utilization_last, 1)

        # 生产效率 = 完成任务数 / 总任务数
        total_tasks = ProductionTask.objects.count()
        completed_tasks_total = ProductionTask.objects.filter(status=3).count()
        production_efficiency = round(
            (completed_tasks_total / max(total_tasks, 1)) * 100, 1) if total_tasks > 0 else 0

        # 上月生产效率
        total_tasks_last = ProductionTask.objects.count()
        completed_tasks_total_last = ProductionTask.objects.filter(
            status=3).count()
        production_efficiency_last = round(
            (completed_tasks_total_last / max(total_tasks_last, 1)) * 100, 1) if total_tasks_last > 0 else 0
        production_efficiency_growth = round(
            production_efficiency - production_efficiency_last, 1)

        # ============ 设备状态分布 ============
        equipment_status = Equipment.objects.values('status').annotate(
            count=Count('id')
        )

        status_labels = []
        status_data = []

        for item in equipment_status:
            if item['status'] == 1:
                status_labels.append('正常')
            elif item['status'] == 2:
                status_labels.append('维护中')
            elif item['status'] == 3:
                status_labels.append('故障')
            else:
                status_labels.append('停用')
            status_data.append(item['count'])

        equipment_data = {
            'labels': json.dumps(status_labels),
            'data': json.dumps(status_data)
        }

        # 生产线实时状态
        production_lines = []
        try:
            lines = Equipment.objects.all()[:10]
            for line in lines:
                tasks = ProductionTask.objects.filter(
                    equipment=line,
                    status=2
                )

                total_plan = 0
                total_produced = 0
                for task in tasks:
                    total_plan += task.quantity or 0
                    total_produced += task.completed_quantity or 0

                production_lines.append(
                    {
                        'name': line.name or f'设备{line.id}',
                        'status': 'running' if line.status == 1 else (
                            'maintenance' if line.status == 2 else (
                                'error' if line.status == 3 else 'stopped')),
                        'planned': total_plan,
                        'produced': total_produced,
                        'efficiency': round(
                            (total_produced / max(
                                total_plan,
                                1)) * 100,
                            1) if total_plan > 0 else 0,
                        'quality_rate': 98.5,
                        'estimated_recovery': 'N/A'})
        except Exception as e:
            logger.error(f'获取生产线状态失败: {str(e)}')
            production_lines = []

        # ============ 生产计划进度 ============
        production_plans = []
        try:
            plans = ProductionPlan.objects.filter(
                status__in=[3, 1]
            ).order_by('-create_time')[:5]

            for plan in plans:
                tasks = ProductionTask.objects.filter(
                    plan=plan
                )
                total = tasks.count()
                completed = tasks.filter(status=3).count()

                production_plans.append({
                    'product_name': plan.name or f'计划{plan.id}',
                    'total': total,
                    'completed': completed,
                    'progress': round((completed / max(total, 1)) * 100, 1) if total > 0 else 0
                })
        except Exception as e:
            logger.error(f'获取生产计划进度失败: {str(e)}')
            production_plans = []

        # 质量控制指标
        pass_rate = 0
        rework_rate = 0
        scrap_rate = 0
        customer_complaints = 0
        try:
            all_tasks = ProductionTask.objects.all()
            total_count = all_tasks.count()

            if total_count > 0:
                pass_rate = 98.5  # 默认合格率
                rework_rate = 1.2  # 默认返工率
                scrap_rate = 0.3   # 默认废品率

            customer_complaints = 0  # 需要从投诉表获取
        except Exception as e:
            logger.error(f'获取质量指标失败: {str(e)}')

        # 生产预警
        production_warnings = []
        try:
            # 设备故障预警
            fault_equipment = Equipment.objects.filter(status=3)
            for eq in fault_equipment:
                production_warnings.append({
                    'level': 'danger',
                    'title': '设备故障',
                    'description': f'{eq.name} 出现故障，需要立即处理'
                })

            # 延期任务预警
            delayed_tasks = ProductionTask.objects.filter(
                status=2,
                plan_end_time__lt=timezone.now()
            )[:3]
            for task in delayed_tasks:
                production_warnings.append({
                    'level': 'warning',
                    'title': '交期预警',
                    'description': f'任务 {task.name} 可能延期'
                })

            # 维护提醒
            maintenance_equipment = Equipment.objects.filter(status=2)[:2]
            for eq in maintenance_equipment:
                production_warnings.append({
                    'level': 'info',
                    'title': '维护提醒',
                    'description': f'{eq.name} 正在维护中'
                })
        except Exception as e:
            logger.error(f'获取生产预警失败: {str(e)}')

    except Exception as e:
        logger.error(f'获取生产数据失败: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        monthly_plans = 0
        completed_tasks = 0
        equipment_utilization = 0
        production_efficiency = 0
        monthly_plans_growth = 0
        completed_tasks_growth = 0
        equipment_utilization_growth = 0
        production_efficiency_growth = 0
        equipment_data = {'labels': '[]', 'data': '[]'}
        production_lines = []
        production_plans = []
        pass_rate = 0
        rework_rate = 0
        scrap_rate = 0
        customer_complaints = 0
        production_warnings = []

    context = {
        'monthly_plans': monthly_plans,
        'completed_tasks': completed_tasks,
        'equipment_utilization': equipment_utilization,
        'production_efficiency': production_efficiency,
        'monthly_plans_growth': monthly_plans_growth,
        'completed_tasks_growth': completed_tasks_growth,
        'equipment_utilization_growth': equipment_utilization_growth,
        'production_efficiency_growth': production_efficiency_growth,
        'equipment_data': equipment_data,
        'production_lines': production_lines,
        'production_plans': production_plans,
        'pass_rate': pass_rate,
        'rework_rate': rework_rate,
        'scrap_rate': scrap_rate,
        'customer_complaints': customer_complaints,
        'production_warnings': production_warnings,
        'last_updated': timezone.now(),
    }

    return render(request, 'home/production_dashboard.html', context)
