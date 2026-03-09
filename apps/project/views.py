from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from .models import Project, ProjectStep, Task, WorkHour, ProjectDocument, ProjectCategory
from django.contrib.auth import get_user_model
from apps.user.models import Admin
from datetime import datetime
import time

User = get_user_model()

class ProjectListView(LoginRequiredMixin, View):
    """项目列表视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        # 检查是否是Ajax请求数据
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        # 普通页面请求返回HTML模板
        categories = ProjectCategory.objects.filter(is_active=True)
        return render(request, 'project/project_list.html', {'categories': categories})

    def get_data_list(self, request):
        # 获取查询参数
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        status = request.GET.get('status', '')
        category_id = request.GET.get('category_id', '')
        keywords = request.GET.get('keywords', '')
        manager_id = request.GET.get('manager_id', '')
        customer_id = request.GET.get('customer_id', '')
        
        # 构建查询条件
        queryset = Project.objects.filter(delete_time__isnull=True)
        
        # 状态筛选
        if status:
            queryset = queryset.filter(status=status)
        
        # 分类筛选
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # 项目经理筛选
        if manager_id:
            queryset = queryset.filter(manager_id=manager_id)
        
        # 客户筛选
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        # 关键词搜索
        if keywords:
            queryset = queryset.filter(
                Q(name__icontains=keywords) |
                Q(code__icontains=keywords) |
                Q(description__icontains=keywords)
            )
        
        # 权限过滤 - 只显示用户有权限查看的项目
        if not request.user.is_superuser:
            # 构建权限查询条件
            permission_q = Q(creator=request.user) | Q(manager=request.user) | Q(members=request.user)
            
            # 添加部门权限检查
            if hasattr(request.user, 'did') and request.user.did:
                permission_q |= Q(department_id=request.user.did)
            
            queryset = queryset.filter(permission_q).distinct()
        
        # 分页
        total = queryset.count()
        start = (page - 1) * limit
        end = start + limit
        projects = queryset.select_related('category', 'manager', 'creator', 'department', 'contract')[start:end]
        
        # 构建返回数据
        data_list = []
        for project in projects:
            # 计算任务统计
            task_stats = project.tasks.aggregate(
                total=Count('id'),
                completed=Count('id', filter=Q(status=3)),
                in_progress=Count('id', filter=Q(status=2))
            )
            
            # 获取客户信息
            customer_name = ''
            if project.customer_id and project.customer_id > 0:
                try:
                    from apps.customer.models import Customer
                    customer = Customer.objects.filter(id=project.customer_id, delete_time=0).first()
                    if customer:
                        customer_name = customer.name
                except Exception:
                    pass
            
            # 开始日期和结束日期优先使用合同中的日期
            start_date = project.contract.sign_date if project.contract else project.start_date
            end_date = project.contract.end_date if project.contract else project.end_date
            
            # 项目经理和创建人
            manager_name = project.manager.username if project.manager else ''
            creator_name = project.creator.username if project.creator else ''
            
            data_list.append({
                'id': project.id,
                'name': project.name,
                'code': project.code,
                'status': project.status,
                'status_display': project.status_display,
                'priority': project.priority,
                'priority_display': project.priority_display,
                'progress': project.progress,
                'category_name': project.category.name if project.category else '',
                'manager_name': manager_name,
                'creator_name': creator_name,
                'department_name': project.department.name if project.department else '',
                'customer_name': customer_name,
                'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
                'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
                'budget': str(project.budget),
                'actual_cost': str(project.actual_cost),
                'is_overdue': project.is_overdue,
                'days_remaining': project.days_remaining,
                'task_total': task_stats['total'] or 0,
                'task_completed': task_stats['completed'] or 0,
                'task_in_progress': task_stats['in_progress'] or 0,
                'create_time': project.create_time.strftime('%Y-%m-%d %H:%M') if project.create_time else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': 'success',
            'count': total,
            'data': data_list
        }, json_dumps_params={'ensure_ascii': False})


class ProjectDetailView(LoginRequiredMixin, View):
    """项目详情视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, project):
            return JsonResponse({'code': 1, 'msg': '没有权限查看此项目'}, json_dumps_params={'ensure_ascii': False})
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Ajax请求返回JSON数据
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'data': {
                    'id': project.id,
                    'name': project.name,
                    'code': project.code,
                    'description': project.description,
                    'status': project.status,
                    'status_display': project.status_display,
                    'priority': project.priority,
                    'priority_display': project.priority_display,
                    'progress': project.progress,
                    'category_name': project.category.name if project.category else '',
                    'manager_name': project.manager.username if project.manager else '',
                    'creator_name': project.creator.username if project.creator else '',
                    'department_name': project.department.name if project.department else '',
                    'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else '',
                    'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else '',
                    'budget': str(project.budget),
                    'actual_cost': str(project.actual_cost),
                    'is_overdue': project.is_overdue,
                    'days_remaining': project.days_remaining,
                    'create_time': project.create_time.strftime('%Y-%m-%d %H:%M') if project.create_time else ''
                }
            })
        
        # 获取项目相关数据
        from apps.project.models import Task, ProjectDocument, WorkHour
        from django.db.models import Sum, Count
        
        # 获取项目任务
        tasks = Task.objects.filter(project=project, delete_time__isnull=True).select_related('assignee', 'creator')
        
        # 获取项目文档
        documents = ProjectDocument.objects.filter(project=project, delete_time__isnull=True).select_related('creator')
        
        # 获取工时统计
        work_hours = WorkHour.objects.filter(task__project=project).select_related('user', 'task')
        total_hours = work_hours.aggregate(total=Sum('hours'))['total'] or 0
        
        # 获取项目成员工时统计
        member_hours = work_hours.values('user__username').annotate(
            total_hours=Sum('hours'),
            task_count=Count('task', distinct=True)
        ).order_by('-total_hours')
        
        # 任务状态统计
        from django.db import models
        from datetime import date
        today = date.today()
        task_stats = tasks.aggregate(
            total_tasks=Count('id'),
            completed_tasks=Count('id', filter=models.Q(status=3)),
            in_progress_tasks=Count('id', filter=models.Q(status=2)),
            pending_tasks=Count('id', filter=models.Q(status=1)),
            overdue_tasks=Count('id', filter=models.Q(status__in=[1, 2], end_date__lt=today)),
            low_priority_tasks=Count('id', filter=models.Q(priority=1)),
            medium_priority_tasks=Count('id', filter=models.Q(priority=2)),
            high_priority_tasks=Count('id', filter=models.Q(priority=3)),
            urgent_priority_tasks=Count('id', filter=models.Q(priority=4))
        )
        
        # 计算项目进度
        if task_stats['total_tasks'] > 0:
            project_progress = round((task_stats['completed_tasks'] / task_stats['total_tasks']) * 100)
        else:
            project_progress = 0
        
        # 获取所有参与项目的成员（项目成员 + 任务成员）
        all_members = set()
        
        # 添加项目成员
        for member in project.members.all():
            all_members.add(member)
        
        # 添加任务负责人
        for task in tasks:
            if task.assignee:
                all_members.add(task.assignee)
            # 添加任务参与者
            for participant in task.participants.all():
                all_members.add(participant)
        
        # 将set转换为list
        all_members = list(all_members)
        
        # 计算任务完成趋势（最近6个月）
        import datetime
        from django.db.models.functions import ExtractMonth, ExtractYear
        task_trend_data = {'months': [], 'created': [], 'completed': []}
        for i in range(5, -1, -1):
            target_date = today - datetime.timedelta(days=30 * i)
            month_start = target_date.replace(day=1)
            if i == 0:
                month_end = today
            else:
                next_month = month_start.replace(day=28) + datetime.timedelta(days=4)
                month_end = next_month.replace(day=1) - datetime.timedelta(days=1)
            
            month_label = month_start.strftime('%Y-%m')
            task_trend_data['months'].append(f"{target_date.month}月")
            
            # 统计该月新增任务数
            created_count = tasks.filter(create_time__gte=month_start, create_time__lte=month_end).count()
            task_trend_data['created'].append(created_count)
            
            # 统计该月完成任务数
            completed_count = tasks.filter(status=3, update_time__gte=month_start, update_time__lte=month_end).count()
            task_trend_data['completed'].append(completed_count)
        
        # 计算团队成员工作量
        member_workload = []
        for member in all_members:
            if member:
                member_tasks = tasks.filter(
                    models.Q(assignee=member) | models.Q(participants=member)
                ).distinct().count()
                member_workload.append({
                    'name': member.username if hasattr(member, 'username') else str(member),
                    'task_count': member_tasks
                })
        # 按任务数降序排序
        member_workload.sort(key=lambda x: x['task_count'], reverse=True)
        
        # 序列化数据为JSON字符串，供前端使用
        import json
        task_trend_data_json = json.dumps(task_trend_data)
        member_workload_json = json.dumps(member_workload)
        
        # 获取关联客户、合同、订单和供应商信息
        related_customers = []
        related_contracts = []
        related_orders = []
        related_suppliers = []
        
        # 获取关联客户
        if project.customer_id and project.customer_id > 0:
            try:
                from apps.customer.models import Customer
                customer = Customer.objects.filter(id=project.customer_id, delete_time=0).first()
                if customer:
                    related_customers.append({
                        'id': customer.id,
                        'name': customer.name
                    })
            except Exception as e:
                pass
        
        # 获取关联合同
        if project.contract:
            related_contracts.append({
                'id': project.contract.id,
                'name': project.contract.name,
                'contract_number': project.contract.contract_number,
                'amount': project.contract.amount,
                'status': project.contract.status,
                'sign_date': project.contract.sign_date.strftime('%Y-%m-%d') if project.contract.sign_date else ''
            })
        
        # 获取关联订单
        try:
            from apps.customer.models import CustomerOrder
            orders = CustomerOrder.objects.filter(
                contract_id=project.contract.id if project.contract else 0,
                delete_time=0
            )[:10]  # 限制显示前10个订单
            for order in orders:
                related_orders.append({
                    'id': order.id,
                    'order_number': order.order_number,
                    'amount': order.amount,
                    'status': order.status,
                    'create_time': order.create_time.strftime('%Y-%m-%d') if order.create_time else ''
                })
        except Exception as e:
            pass
        
        # 获取关联供应商（通过订单关联）
        try:
            from apps.customer.models import CustomerOrder
            from apps.supplier.models import Supplier
            # 获取所有相关订单的供应商ID
            order_supplier_ids = CustomerOrder.objects.filter(
                contract_id=project.contract.id if project.contract else 0,
                delete_time=0
            ).values_list('supplier_id', flat=True).distinct()
            
            # 获取供应商信息
            suppliers = Supplier.objects.filter(id__in=order_supplier_ids, delete_time=0)[:10]  # 限制显示前10个供应商
            for supplier in suppliers:
                related_suppliers.append({
                    'id': supplier.id,
                    'name': supplier.name
                })
        except Exception as e:
            pass
        
        # 获取项目的content_type ID
        from django.contrib.contenttypes.models import ContentType
        project_content_type = ContentType.objects.get_for_model(Project)
        project_content_type_id = project_content_type.id
        
        context = {
            'project': project,
            'tasks': tasks,
            'documents': documents,
            'work_hours': work_hours[:20],
            'total_hours': total_hours,
            'member_hours': member_hours,
            'task_stats': task_stats,
            'task_trend_data_json': task_trend_data_json,
            'member_workload_json': member_workload_json,
            'project_progress': project_progress,
            'related_customers': related_customers,
            'related_contracts': related_contracts,
            'related_orders': related_orders,
            'related_suppliers': related_suppliers,
            'all_members': all_members,
            'project_content_type_id': project_content_type_id
        }
        return render(request, 'project/detail.html', context)
    
    def has_permission(self, user, project):
        """检查用户是否有权限查看项目"""
        if user.is_superuser:
            return True
        
        # 检查用户部门权限
        user_has_dept_permission = False
        if project.department and hasattr(user, 'did') and user.did:
            user_has_dept_permission = project.department.id == user.did
        
        return (
            project.creator == user or
            project.manager == user or
            user in project.members.all() or
            user_has_dept_permission
        )


class ProjectAddView(LoginRequiredMixin, View):
    """新增项目视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        categories = ProjectCategory.objects.filter(is_active=True)
        users = Admin.objects.filter(status=1)
        
        # 生成项目编号
        import datetime
        today = datetime.date.today()
        prefix = f"PRJ{today.strftime('%Y%m%d')}"
        
        # 查找今天已有的项目编号
        existing_codes = Project.objects.filter(
            code__startswith=prefix,
            delete_time__isnull=True
        ).values_list('code', flat=True)
        
        # 生成新的编号
        counter = 1
        while True:
            new_code = f"{prefix}{counter:03d}"
            if new_code not in existing_codes:
                break
            counter += 1
        
        # 获取客户ID参数
        customer_id = request.GET.get('customer_id')
        customer = None
        if customer_id:
            try:
                from apps.customer.models import Customer
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                pass
        
        return render(request, 'project/project_form.html', {
            'categories': categories,
            'users': users,
            'is_edit': False,
            'generated_code': new_code,
            'customer': customer
        })
    
    def post(self, request):
        try:
            # 获取表单数据
            name = request.POST.get('name')
            code = request.POST.get('code')
            description = request.POST.get('description', '')
            category_id = request.POST.get('category_id')
            manager_id = request.POST.get('manager_id')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            budget = request.POST.get('budget', 0)
            priority = request.POST.get('priority', 2)
            
            # 验证必填字段
            if not all([name, code, start_date, end_date]):
                return JsonResponse({'code': 1, 'msg': '请填写所有必填字段'}, json_dumps_params={'ensure_ascii': False})
            
            # 验证客户关联（项目必须关联客户）
            customer_id = request.POST.get('customer_id')
            if not customer_id or customer_id == '0':
                return JsonResponse({'code': 1, 'msg': '项目必须关联客户'}, json_dumps_params={'ensure_ascii': False})
            
            # 检查项目编号是否重复
            if Project.objects.filter(code=code).exists():
                return JsonResponse({'code': 1, 'msg': '项目编号已存在'}, json_dumps_params={'ensure_ascii': False})
            
            # 获取用户部门
            from apps.department.models import Department
            user_department = None
            if hasattr(request.user, 'did') and request.user.did:
                try:
                    user_department = Department.objects.get(id=request.user.did)
                except Department.DoesNotExist:
                    pass
            
            # 获取客户ID参数
            customer_id = request.POST.get('customer_id')
            
            # 创建项目
            # 如果未选择项目经理，默认设置为当前用户
            if not manager_id:
                manager_id = request.user.id
            
            project = Project.objects.create(
                name=name,
                code=code,
                description=description,
                category_id=category_id if category_id else None,
                manager_id=manager_id,
                start_date=start_date,
                end_date=end_date,
                budget=budget,
                priority=priority,
                creator=request.user,
                department=user_department,
                customer_id=customer_id if customer_id else 0
            )
            
            # 添加项目成员
            member_ids = request.POST.getlist('member_ids')
            if member_ids:
                project.members.set(member_ids)
            
            # 创建项目主任务
            main_task = Task.objects.create(
                title=f"{project.name} - 主任务",
                description=f"项目 {project.name} 的主要任务",
                project=project,
                assignee=project.manager,
                start_date=project.start_date,
                end_date=project.end_date,
                priority=project.priority,
                creator=request.user,
                status=1  # 未开始
            )
            
            # 如果有项目成员，将他们添加为主任务的参与者
            if member_ids:
                main_task.participants.set(member_ids)
            
            # 需求案例2：创建项目后自动生成待签约合同、待收款、待确认订单、待开票
            try:
                contract_record = self._auto_generate_related_records(project, request.user)
                # 将自动生成的合同关联到项目
                if contract_record:
                    project.contract = contract_record
                    project.save()
            except Exception as auto_gen_error:
                # 记录错误但不影响项目创建
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"自动生成相关记录失败: {str(auto_gen_error)}")
            
            return JsonResponse({'code': 0, 'msg': '项目创建成功', 'data': {'id': project.id, 'main_task_id': main_task.id}}, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'创建失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})

    def _auto_generate_related_records(self, project, user):
        """
        自动生成与项目相关的记录：待签约合同、待收款、待确认订单
        返回创建的合同记录
        """
        import time
        import logging
        logger = logging.getLogger(__name__)
        
        contract_record = None
        
        # 1. 生成待签约合同记录
        if hasattr(self, '_generate_contract_record'):
            self._generate_contract_record(project, user)
        else:
            # 检查是否存在CustomerContract模型（客户合同）
            try:
                from apps.customer.models import CustomerContract
                # 创建待签约合同记录
                contract_record = CustomerContract.objects.create(
                    customer_id=project.customer_id,
                    name=f"{project.name}合同",
                    contract_number=f"CONT-PROJ-{project.code}-{int(time.time())}",
                    amount=project.budget,
                    sign_date=project.start_date if project.start_date else None,
                    end_date=project.end_date if project.end_date else None,
                    status='pending',  # 待签约状态
                    create_user_id=user.id,
                    auto_generated=True  # 标记为自动生成
                )
            except Exception as e:
                logger.error(f"创建合同记录失败: {e}")
        
        # 2. 生成待收款记录
        if hasattr(self, '_generate_payment_record'):
            self._generate_payment_record(project, user)
        else:
            # 创建待收款记录
            try:
                from apps.finance.models import Invoice
                # 确保project已保存到数据库
                if not project.id:
                    project.save()
                # 创建发票记录（待开票，待收款）- 使用实际的Invoice模型字段
                invoice_record = Invoice.objects.create(
                    code=f"INV-PROJ-{project.code}-{int(time.time())}",
                    customer_id=project.customer_id,
                    project_id=project.id,
                    amount=project.budget,
                    admin_id=user.id,
                    did=1,  # 默认部门ID
                    open_status=0,  # 未开票状态
                    enter_status=0,  # 未回款状态
                    invoice_title="",  # 留空，后续填写
                    invoice_tax="",  # 留空，后续填写
                    create_time=int(time.time()),
                    auto_generated=True  # 标记为自动生成
                )
            except Exception as e:
                logger.error(f"创建发票记录失败: {e}")
        
        # 3. 生成待确认订单记录
        if hasattr(self, '_generate_order_record'):
            self._generate_order_record(project, user)
        else:
            # 检查是否存在CustomerOrder模型
            try:
                from apps.customer.models import CustomerOrder
                # 创建客户订单记录（待确认）
                order_record = CustomerOrder.objects.create(
                    customer_id=project.customer_id,
                    order_number=f"PO-{project.code}-{int(time.time())}",
                    product_name=project.name,
                    amount=project.budget,
                    order_date=datetime.now().date(),
                    status='pending',  # 待处理状态
                    description=f"项目订单：{project.name}",
                    create_user_id=user.id,
                    auto_generated=True  # 标记为自动生成
                )
            except Exception as e:
                logger.error(f"创建客户订单记录失败: {e}")
        
        return contract_record


class ProjectDocumentListView(LoginRequiredMixin, View):
    """项目文档列表视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        # 检查是否是Ajax请求数据
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        # 普通页面请求返回HTML模板
        projects = Project.objects.filter(delete_time__isnull=True)
        return render(request, 'project/document.html', {'projects': projects})

    def get_data_list(self, request):
        # 获取查询参数
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        project_id = request.GET.get('project_id', '')
        keywords = request.GET.get('keywords', '')
        
        # 构建查询条件
        queryset = ProjectDocument.objects.filter(delete_time__isnull=True)
        
        # 项目筛选
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        # 关键词搜索
        if keywords:
            queryset = queryset.filter(
                Q(title__icontains=keywords) |
                Q(content__icontains=keywords)
            )
        
        # 权限过滤 - 只显示用户有权限查看的文档
        if not request.user.is_superuser:
            # 构建权限查询条件
            permission_q = (
                Q(creator=request.user) |
                Q(project__creator=request.user) |
                Q(project__manager=request.user) |
                Q(project__members=request.user)
            )
            
            # 添加部门权限检查
            if hasattr(request.user, 'did') and request.user.did:
                permission_q |= Q(project__department_id=request.user.did)
            
            queryset = queryset.filter(permission_q).distinct()
        
        # 分页
        total = queryset.count()
        start = (page - 1) * limit
        end = start + limit
        documents = queryset.select_related('project', 'creator')[start:end]
        
        # 构建返回数据
        data_list = []
        for doc in documents:
            data_list.append({
                'id': doc.id,
                'title': doc.title,
                'project_name': doc.project.name,
                'creator_name': doc.creator.username if doc.creator else '',
                'file_path': doc.file_path,
                'create_time': doc.create_time.strftime('%Y-%m-%d %H:%M')
            })
        
        return JsonResponse({
            'code': 0,
            'msg': 'success',
            'count': total,
            'data': data_list
        })


class ProjectEditView(LoginRequiredMixin, View):
    """编辑项目视图"""
    login_url = '/user/login/'
    
    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, project):
            return JsonResponse({'code': 1, 'msg': '没有权限编辑此项目'}, json_dumps_params={'ensure_ascii': False})
        
        categories = ProjectCategory.objects.filter(is_active=True)
        users = Admin.objects.filter(status=1)
        
        # 获取项目关联的客户信息
        customer = None
        if project.customer_id and project.customer_id > 0:
            try:
                from apps.customer.models import Customer
                customer = Customer.objects.filter(id=project.customer_id, delete_time=0).first()
            except Exception as e:
                pass
        
        return render(request, 'project/project_form.html', {
            'project': project,
            'categories': categories,
            'users': users,
            'is_edit': True,
            'customer': customer
        })
    
    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, project):
            return JsonResponse({'code': 1, 'msg': '没有权限编辑此项目'}, json_dumps_params={'ensure_ascii': False})
        
        try:
            # 获取表单数据
            name = request.POST.get('name')
            code = request.POST.get('code')
            description = request.POST.get('description', '')
            category_id = request.POST.get('category_id')
            manager_id = request.POST.get('manager_id')
            customer_id = request.POST.get('customer_id', '')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            budget = request.POST.get('budget', 0)
            priority = request.POST.get('priority', 2)
            status = request.POST.get('status', project.status)
            progress = request.POST.get('progress', project.progress)
            actual_cost = request.POST.get('actual_cost', project.actual_cost)
            
            # 验证必填字段
            if not all([name, code, start_date, end_date]):
                return JsonResponse({'code': 1, 'msg': '请填写所有必填字段'}, json_dumps_params={'ensure_ascii': False})
            
            # 检查项目编号是否重复（排除当前项目）
            if Project.objects.filter(code=code).exclude(id=project_id).exists():
                return JsonResponse({'code': 1, 'msg': '项目编号已存在'}, json_dumps_params={'ensure_ascii': False})
            
            # 更新项目
            project.name = name
            project.code = code
            project.description = description
            project.category_id = category_id if category_id else None
            project.manager_id = manager_id if manager_id else None
            project.customer_id = customer_id if customer_id else 0
            project.start_date = start_date
            project.end_date = end_date
            project.budget = budget
            project.priority = priority
            project.status = status
            project.progress = progress
            project.actual_cost = actual_cost
            project.save()
            
            # 更新项目成员（处理新的员工选择器传递的participant_ids）
            member_ids = []
            participant_ids = request.POST.get('participant_ids')
            if participant_ids:
                member_ids = participant_ids.split(',')
            else:
                # 兼容旧的checkbox方式
                member_ids = request.POST.getlist('member_ids')
            
            if member_ids:
                project.members.set(member_ids)
            
            return JsonResponse({'code': 0, 'msg': '项目更新成功'}, json_dumps_params={'ensure_ascii': False})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'更新失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})
    
    def has_permission(self, user, project):
        """检查用户是否有权限编辑项目"""
        if user.is_superuser:
            return True
        return (
            project.creator == user or
            project.manager == user
        )


class ProjectDeleteView(LoginRequiredMixin, View):
    """删除项目视图"""
    login_url = '/user/login/'
    
    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, project):
            return JsonResponse({'code': 1, 'msg': '没有权限删除此项目'}, json_dumps_params={'ensure_ascii': False})
        
        try:
            # 软删除
            project.delete_time = timezone.now()
            project.save()
            
            return JsonResponse({'code': 0, 'msg': '项目删除成功'}, json_dumps_params={'ensure_ascii': False})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})
    
    def has_permission(self, user, project):
        """检查用户是否有权限删除项目"""
        if user.is_superuser:
            return True
        return project.creator == user


class ProjectDocumentAddView(LoginRequiredMixin, View):
    """新增项目文档视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        projects = Project.objects.filter(delete_time__isnull=True)
        # 获取URL参数中的project_id，用于预选项目
        selected_project_id = request.GET.get('project_id', '')
        
        return render(request, 'project/document_form.html', {
            'projects': projects,
            'selected_project_id': selected_project_id,
            'is_edit': False
        })
    
    def post(self, request):
        try:
            # 获取表单数据
            title = request.POST.get('title')
            content = request.POST.get('content', '')
            project_id = request.POST.get('project_id')
            file_path = request.POST.get('file_path', '')
            
            # 验证必填字段
            if not all([title, project_id]):
                return JsonResponse({'code': 1, 'msg': '请填写标题和选择项目'}, json_dumps_params={'ensure_ascii': False})
            
            # 创建文档
            document = ProjectDocument.objects.create(
                title=title,
                content=content,
                project_id=project_id,
                file_path=file_path,
                creator=request.user
            )
            
            return JsonResponse({'code': 0, 'msg': '文档创建成功', 'data': {'id': document.id}}, json_dumps_params={'ensure_ascii': False})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'创建失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})


class ProjectDocumentEditView(LoginRequiredMixin, View):
    """编辑项目文档视图"""
    login_url = '/user/login/'
    
    def get(self, request, doc_id):
        document = get_object_or_404(ProjectDocument, id=doc_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, document):
            return JsonResponse({'code': 1, 'msg': '没有权限编辑此文档'}, json_dumps_params={'ensure_ascii': False})
        
        projects = Project.objects.filter(delete_time__isnull=True)
        return render(request, 'project/document_form.html', {
            'document': document,
            'projects': projects,
            'is_edit': True
        })
    
    def post(self, request, doc_id):
        document = get_object_or_404(ProjectDocument, id=doc_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, document):
            return JsonResponse({'code': 1, 'msg': '没有权限编辑此文档'})
        
        try:
            # 获取表单数据
            title = request.POST.get('title')
            content = request.POST.get('content', '')
            project_id = request.POST.get('project_id')
            file_path = request.POST.get('file_path', '')
            
            # 验证必填字段
            if not all([title, project_id]):
                return JsonResponse({'code': 1, 'msg': '请填写标题和选择项目'}, json_dumps_params={'ensure_ascii': False})
            
            # 更新文档
            document.title = title
            document.content = content
            document.project_id = project_id
            document.file_path = file_path
            document.save()
            
            return JsonResponse({'code': 0, 'msg': '文档更新成功'}, json_dumps_params={'ensure_ascii': False})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'更新失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})
    
    def has_permission(self, user, document):
        """检查用户是否有权限编辑文档"""
        if user.is_superuser:
            return True
        return (
            document.creator == user or
            document.project.creator == user or
            document.project.manager == user
        )


class ProjectDocumentDeleteView(LoginRequiredMixin, View):
    """删除项目文档视图"""
    login_url = '/user/login/'
    
    def post(self, request, doc_id):
        document = get_object_or_404(ProjectDocument, id=doc_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, document):
            return JsonResponse({'code': 1, 'msg': '没有权限删除此文档'}, json_dumps_params={'ensure_ascii': False})
        
        try:
            # 软删除
            document.delete_time = timezone.now()
            document.save()
            
            return JsonResponse({'code': 0, 'msg': '文档删除成功'}, json_dumps_params={'ensure_ascii': False})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})
    
    def has_permission(self, user, document):
        """检查用户是否有权限删除文档"""
        if user.is_superuser:
            return True
        return (
            document.creator == user or
            document.project.creator == user
        )


class ProjectDocumentDetailView(LoginRequiredMixin, View):
    """项目文档详情视图"""
    login_url = '/user/login/'
    
    def get(self, request, doc_id):
        document = get_object_or_404(ProjectDocument, id=doc_id, delete_time__isnull=True)
        
        # 检查权限
        if not self.has_permission(request.user, document):
            return JsonResponse({'code': 1, 'msg': '没有权限查看此文档'})
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Ajax请求返回JSON数据
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'data': {
                    'id': document.id,
                    'title': document.title,
                    'content': document.content,
                    'project_name': document.project.name,
                    'creator_name': document.creator.username if document.creator else '',
                    'file_path': document.file_path,
                    'create_time': document.create_time.strftime('%Y-%m-%d %H:%M')
                }
            })
        
        # 普通请求返回HTML页面
        return render(request, 'project/document_detail.html', {'document': document})
    
    def has_permission(self, user, document):
        """检查用户是否有权限查看文档"""
        if user.is_superuser:
            return True
        return (
            document.creator == user or
            document.project.creator == user or
            document.project.manager == user or
            user in document.project.members.all()
        )


class ProjectCategoryListView(LoginRequiredMixin, View):
    """项目分类列表视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'project/category_list.html')

    def get_data_list(self, request):
        try:
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 20))
            keywords = request.GET.get('keywords', '')
            
            queryset = ProjectCategory.objects.all()
            
            if keywords:
                queryset = queryset.filter(
                    Q(name__icontains=keywords) |
                    Q(description__icontains=keywords)
                )
            
            total = queryset.count()
            start = (page - 1) * limit
            end = start + limit
            categories = queryset[start:end]
            
            data_list = []
            for category in categories:
                create_time_str = ''
                if hasattr(category, 'create_time'):
                    create_time_str = category.create_time.strftime('%Y-%m-%d %H:%M')
                elif hasattr(category, 'created_at'):
                    create_time_str = category.created_at.strftime('%Y-%m-%d %H:%M')
                data_list.append({
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'sort': category.sort_order,
                    'status': category.is_active,
                    'status_display': '启用' if category.is_active else '禁用',
                    'create_time': create_time_str
                })
            
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'count': total,
                'data': data_list
            })
        except Exception as e:
            return JsonResponse({
                'code': 1,
                'msg': f'获取数据失败: {str(e)}',
                'count': 0,
                'data': []
            })


class ProjectCategoryAddView(LoginRequiredMixin, View):
    """新增项目分类视图"""
    login_url = '/user/login/'
    
    def get(self, request):
        return render(request, 'project/category_form.html')
    
    def post(self, request):
        try:
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            sort = request.POST.get('sort', 0)
            is_active = request.POST.get('status') == '1'
            
            if not name:
                return JsonResponse({'code': 1, 'msg': '分类名称不能为空'})
            
            if ProjectCategory.objects.filter(name=name).exists():
                return JsonResponse({'code': 1, 'msg': '分类名称已存在'})
            
            ProjectCategory.objects.create(
                name=name,
                description=description,
                sort_order=int(sort),
                is_active=is_active
            )
            
            return JsonResponse({'code': 0, 'msg': '分类创建成功'})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'创建失败: {str(e)}'})


class ProjectCategoryEditView(LoginRequiredMixin, View):
    """编辑项目分类视图"""
    login_url = '/user/login/'
    
    def get(self, request, category_id):
        try:
            category = get_object_or_404(ProjectCategory, id=category_id)
            return render(request, 'project/category_form.html', {'category': category})
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'获取分类信息失败: {str(e)}'})
    
    def post(self, request, category_id):
        try:
            category = get_object_or_404(ProjectCategory, id=category_id)
            
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            sort = request.POST.get('sort', 0)
            is_active = request.POST.get('status') == '1'
            
            if not name:
                return JsonResponse({'code': 1, 'msg': '分类名称不能为空'})
            
            if ProjectCategory.objects.filter(name=name).exclude(id=category_id).exists():
                return JsonResponse({'code': 1, 'msg': '分类名称已存在'})
            
            category.name = name
            category.description = description
            category.sort_order = int(sort)
            category.is_active = is_active
            category.save()
            
            return JsonResponse({'code': 0, 'msg': '分类更新成功'})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'更新失败: {str(e)}'})


class ProjectCategoryDeleteView(LoginRequiredMixin, View):
    """删除项目分类视图"""
    login_url = '/user/login/'
    
    def post(self, request, category_id):
        try:
            category = get_object_or_404(ProjectCategory, id=category_id)
            
            # 检查是否有项目使用此分类
            if Project.objects.filter(category=category).exists():
                return JsonResponse({'code': 1, 'msg': '该分类下还有项目，无法删除'})
            
            category.delete()
            return JsonResponse({'code': 0, 'msg': '分类删除成功'})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})



class ProjectDocumentEditView(LoginRequiredMixin, View):
    """编辑项目文档视图"""
    login_url = '/user/login/'
    
    def get(self, request, doc_id):
        try:
            document = get_object_or_404(ProjectDocument, id=doc_id, delete_time__isnull=True)
            projects = Project.objects.filter(delete_time__isnull=True)
            
            # 检查权限
            if not self.has_permission(request.user, document):
                return JsonResponse({'code': 1, 'msg': '没有权限编辑此文档'})
            
            return render(request, 'project/document_form.html', {
                'document': document,
                'projects': projects,
                'is_edit': True
            })
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'获取文档信息失败: {str(e)}'})
    
    def post(self, request, doc_id):
        try:
            document = get_object_or_404(ProjectDocument, id=doc_id, delete_time__isnull=True)
            
            # 检查权限
            if not self.has_permission(request.user, document):
                return JsonResponse({'code': 1, 'msg': '没有权限编辑此文档'})
            
            title = request.POST.get('title')
            project_id = request.POST.get('project_id')
            content = request.POST.get('content', '')
            file_path = request.POST.get('file_path', '')
            
            if not title:
                return JsonResponse({'code': 1, 'msg': '文档标题不能为空'})
            
            if not project_id:
                return JsonResponse({'code': 1, 'msg': '请选择所属项目'})
            
            project = get_object_or_404(Project, id=project_id, delete_time__isnull=True)
            
            document.title = title
            document.project = project
            document.content = content
            if file_path:  # 只有上传了新文件才更新文件路径
                document.file_path = file_path
            document.save()
            
            return JsonResponse({'code': 0, 'msg': '文档更新成功'})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'更新失败: {str(e)}'})
    
    def has_permission(self, user, document):
        """检查用户是否有权限编辑文档"""
        if user.is_superuser:
            return True
        return (
            document.creator == user or
            document.project.creator == user or
            document.project.manager == user or
            user in document.project.members.all()
        )


class ProjectDocumentDeleteView(LoginRequiredMixin, View):
    """删除项目文档视图"""
    login_url = '/user/login/'
    
    def post(self, request, doc_id):
        try:
            document = get_object_or_404(ProjectDocument, id=doc_id, delete_time__isnull=True)
            
            # 检查权限
            if not self.has_permission(request.user, document):
                return JsonResponse({'code': 1, 'msg': '没有权限删除此文档'})
            
            # 软删除
            from django.utils import timezone
            document.delete_time = timezone.now()
            document.save()
            
            return JsonResponse({'code': 0, 'msg': '文档删除成功'})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})
    
    def has_permission(self, user, document):
        """检查用户是否有权限删除文档"""
        if user.is_superuser:
            return True
        return (
            document.creator == user or
            document.project.creator == user or
            document.project.manager == user
        )


class ProjectDocumentDetailView(LoginRequiredMixin, View):
    """项目文档详情视图"""
    login_url = '/user/login/'
    
    def get(self, request, doc_id):
        try:
            document = get_object_or_404(ProjectDocument, id=doc_id, delete_time__isnull=True)
            
            # 检查权限
            if not self.has_permission(request.user, document):
                return JsonResponse({'code': 1, 'msg': '没有权限查看此文档'})
            
            return render(request, 'project/document_detail.html', {'document': document})
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'获取文档详情失败: {str(e)}'})
    
    def has_permission(self, user, document):
        """检查用户是否有权限查看文档"""
        if user.is_superuser:
            return True
        return (
            document.creator == user or
            document.project.creator == user or
            document.project.manager == user or
            user in document.project.members.all()
        )


class ProjectDocumentUploadView(LoginRequiredMixin, View):
    """项目文档文件上传视图"""
    login_url = '/user/login/'
    
    def post(self, request):
        try:
            import os
            import uuid
            from django.conf import settings
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            
            if 'file' not in request.FILES:
                return JsonResponse({'code': 1, 'msg': '没有选择文件'})
            
            file = request.FILES['file']
            
            # 检查文件大小（50MB）
            if file.size > 50 * 1024 * 1024:
                return JsonResponse({'code': 1, 'msg': '文件大小不能超过50MB'})
            
            # 检查文件类型
            allowed_extensions = ['.doc', '.docx', '.pdf', '.txt', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']
            file_extension = os.path.splitext(file.name)[1].lower()
            if file_extension not in allowed_extensions:
                return JsonResponse({'code': 1, 'msg': '不支持的文件格式'})
            
            # 生成唯一文件名
            unique_filename = f"{uuid.uuid4().hex}{file_extension}"
            
            # 创建上传目录
            upload_dir = 'documents'
            if not os.path.exists(os.path.join(settings.MEDIA_ROOT, upload_dir)):
                os.makedirs(os.path.join(settings.MEDIA_ROOT, upload_dir))
            
            # 保存文件
            file_path = os.path.join(upload_dir, unique_filename)
            saved_path = default_storage.save(file_path, ContentFile(file.read()))
            
            # 生成访问URL
            file_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)
            
            return JsonResponse({
                'code': 0,
                'msg': '文件上传成功',
                'data': {
                    'file_path': saved_path,
                    'file_url': file_url,
                    'original_name': file.name,
                    'file_size': file.size
                }
            })
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'上传失败: {str(e)}'})


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q

from .models import ProjectStage, ProjectCategory, WorkType
from .forms import ProjectStageForm, ProjectCategoryForm, WorkTypeForm
from apps.common.views_utils import generic_list_view, generic_form_view


@login_required
def project_stage_list(request):
    return generic_list_view(
        request,
        ProjectStage,
        'project/project_stage_list.html',
        search_fields=['name', 'code']
    )


@login_required
def project_stage_form(request, pk=None):
    return generic_form_view(
        request,
        ProjectStage,
        ProjectStageForm,
        'project/project_stage_form.html',
        'project:project_stage_list',
        pk
    )


@login_required
def project_category_list(request):
    return generic_list_view(
        request,
        ProjectCategory,
        'project/project_category_list.html',
        search_fields=['name', 'code']
    )


@login_required
def project_category_form(request, pk=None):
    return generic_form_view(
        request,
        ProjectCategory,
        ProjectCategoryForm,
        'project/project_category_form.html',
        'basedata:project_category_list',
        pk
    )


@login_required
def work_type_list(request):
    return generic_list_view(
        request,
        WorkType,
        'project/work_type_list.html',
        search_fields=['name', 'code']
    )


@login_required
def work_type_form(request, pk=None):
    return generic_form_view(
        request,
        WorkType,
        WorkTypeForm,
        'project/work_type_form.html',
        'project:work_type_list',
        pk
    )