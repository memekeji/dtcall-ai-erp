# -*- coding: utf-8 -*-
"""
协同分享视图 - 用于在线沟通中快速分享各模块内容
"""
from datetime import datetime
from django.db.models import Q
from rest_framework import views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


class ShareableContentView(views.APIView):
    """
    获取可分享的内容列表(带权限控制)
    支持项目、客户、合同、审批、任务、文件、生产、财务等模块
    """
    permission_classes = [IsAuthenticated]

    def _format_created_at(self, value):
        """兼容 datetime 与整型时间戳的创建时间格式化。"""
        if not value:
            return ''

        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%d %H:%M')

        try:
            return datetime.fromtimestamp(int(value)).strftime('%Y-%m-%d %H:%M')
        except (TypeError, ValueError, OSError, OverflowError):
            return str(value)

    def _build_item(
        self,
        *,
        module,
        item_type,
        item_type_label,
        id,
        title,
        url='',
        created_at='',
        status='',
        status_display='',
        quick_actions=None,
        summary='',
        extra=None,
    ):
        payload = {
            'id': id,
            'title': title,
            'name': title,
            'url': url,
            'module': module,
            'item_type': item_type,
            'item_type_label': item_type_label,
            'created_at': created_at,
            'status': status,
            'status_display': status_display,
            'quick_actions': quick_actions or ['view'],
            'summary': summary,
        }
        if extra:
            payload.update(extra)
        return payload

    def _build_type_filters(self, items):
        type_map = {'all': {'id': 'all', 'label': '全部', 'count': len(items)}}
        for item in items:
            item_type = item.get('item_type')
            item_type_label = item.get('item_type_label') or item_type
            if item_type not in type_map:
                type_map[item_type] = {
                    'id': item_type,
                    'label': item_type_label,
                    'count': 0,
                }
            type_map[item_type]['count'] += 1
        return list(type_map.values())

    def get(self, request):
        """获取可分享内容"""
        module = request.query_params.get('module', '')
        keyword = request.query_params.get('search', '')
        page_size = int(request.query_params.get('page_size', 50))
        
        if not module:
            return Response({'error': '缺少module参数'}, status=400)
        
        user = request.user
        
        # 根据模块类型获取数据
        handlers = {
            'project': self._get_projects,
            'customer': self._get_customers,
            'contract': self._get_contracts,
            'approval': self._get_approvals,
            'task': self._get_tasks,
            'file': self._get_files,
            'disk': self._get_files,  # 兼容旧的disk命名
            'production': self._get_productions,
            'finance': self._get_finances,
        }
        
        handler = handlers.get(module)
        if not handler:
            return Response({'error': f'不支持的模块: {module}'}, status=400)
        
        try:
            items = handler(user, keyword, page_size)
            return Response({
                'results': items,
                'count': len(items),
                'type_filters': self._build_type_filters(items),
            })
        except Exception as e:
            logger.error(f'获取{module}模块数据失败: {e}', exc_info=True)
            return Response({'error': str(e)}, status=500)

    def _get_projects(self, user, keyword, page_size):
        """获取项目列表"""
        try:
            from apps.project.models import Project, ProjectDocument
            
            # 根据权限获取项目:管理员看所有,普通用户看自己相关的
            if user.is_superuser:
                projects = Project.objects.all()
            else:
                projects = Project.objects.filter(
                    Q(manager=user) | Q(creator=user)
                ).distinct()
            
            if keyword:
                projects = projects.filter(
                    Q(name__icontains=keyword) | Q(description__icontains=keyword)
                )
            
            projects = list(projects.order_by('-create_time')[:page_size])

            if user.is_superuser:
                documents = ProjectDocument.objects.select_related('project').all()
            else:
                documents = ProjectDocument.objects.select_related('project').filter(
                    Q(project__manager=user) | Q(project__creator=user)
                ).distinct()

            if keyword:
                documents = documents.filter(
                    Q(title__icontains=keyword) |
                    Q(content__icontains=keyword) |
                    Q(project__name__icontains=keyword)
                )

            documents = list(documents.order_by('-create_time')[:page_size])

            items = [
                self._build_item(
                    module='project',
                    item_type='project',
                    item_type_label='项目',
                    id=p.id,
                    title=p.name,
                    url=f'/project/detail/{p.id}/',
                    created_at=self._format_created_at(p.create_time),
                    status=p.status if hasattr(p, 'status') else '',
                    status_display=p.status_display if hasattr(p, 'status_display') else '',
                    quick_actions=['view', 'docs', 'activities'],
                    summary=(p.description or '查看项目进展、文档与动态').strip(),
                    extra={
                        'code': p.code,
                        'priority_display': getattr(p, 'priority_display', ''),
                        'progress': getattr(p, 'progress', 0),
                    },
                )
                for p in projects
            ]
            items.extend([
                self._build_item(
                    module='project',
                    item_type='document',
                    item_type_label='项目文档',
                    id=d.id,
                    title=d.title,
                    url=f'/project/document/detail/{d.id}/',
                    created_at=self._format_created_at(d.create_time),
                    quick_actions=['view', 'share'],
                    summary=(d.project.name + ' / 文档资料') if d.project else '项目文档',
                    extra={
                        'project_id': d.project_id,
                        'project_name': d.project.name if d.project else '',
                    },
                )
                for d in documents
            ])
            return items[: page_size * 2]
        except Exception as e:
            logger.error(f'获取项目数据失败: {e}', exc_info=True)
            return []

    def _get_customers(self, user, keyword, page_size):
        """获取客户列表"""
        try:
            from apps.customer.models import Customer
            
            # 根据权限获取客户:管理员看所有,普通用户看自己负责的
            if user.is_superuser:
                customers = Customer.objects.all()
            else:
                customers = Customer.objects.filter(
                    Q(principal=user) | Q(admin_id=user.id)
                ).distinct()
            
            if keyword:
                customers = customers.filter(Q(name__icontains=keyword))
            
            customers = customers.order_by('-create_time')[:page_size]

            return [
                self._build_item(
                    module='customer',
                    item_type='customer',
                    item_type_label='客户',
                    id=c.id,
                    title=c.name,
                    url=f'/customer/detail/{c.id}/',
                    created_at=self._format_created_at(c.create_time),
                    status_display=c.get_intent_status_display() if hasattr(c, 'get_intent_status_display') else '',
                    quick_actions=['view', 'follow', 'contact'],
                    summary=(getattr(c, 'company_name', '') or '可直接查看客户详情并发起协同').strip(),
                    extra={
                        'mobile': getattr(c, 'mobile', ''),
                    },
                )
                for c in customers
            ]
        except Exception as e:
            logger.error(f'获取客户数据失败: {e}', exc_info=True)
            return []

    def _get_contracts(self, user, keyword, page_size):
        """获取合同列表"""
        try:
            from apps.customer.models import CustomerContract
            
            # 根据权限获取合同:管理员看所有,普通用户看自己参与的
            if user.is_superuser:
                contracts = CustomerContract.objects.all()
            else:
                contracts = CustomerContract.objects.filter(
                    Q(create_user=user)
                ).distinct()
            
            if keyword:
                contracts = contracts.filter(
                    Q(name__icontains=keyword) | Q(contract_number__icontains=keyword)
                )
            
            contracts = contracts.order_by('-create_time')[:page_size]

            return [
                self._build_item(
                    module='contract',
                    item_type='contract',
                    item_type_label='合同',
                    id=c.id,
                    title=c.name or f'合同{c.contract_number}',
                    url=f'/customer/orders/{c.id}/detail/',
                    created_at=self._format_created_at(c.create_time),
                    status=c.status if hasattr(c, 'status') else '',
                    status_display=c.get_status_display() if hasattr(c, 'get_status_display') else '',
                    quick_actions=['view', 'download', 'sign'],
                    summary=(f'合同编号 {c.contract_number}' if c.contract_number else '合同资料').strip(),
                    extra={
                        'has_file': bool(hasattr(c, 'file') and c.file) or bool(hasattr(c, 'attachment') and c.attachment),
                    },
                )
                for c in contracts
            ]
        except Exception as e:
            logger.error(f'获取合同数据失败: {e}', exc_info=True)
            return []

    def _get_approvals(self, user, keyword, page_size):
        """获取审批列表"""
        try:
            from apps.approval.models import Approval, ApprovalRecord, ApprovalTask
            
            # 根据权限获取审批:管理员看所有,普通用户看自己发起或审批的
            if user.is_superuser:
                approvals = Approval.objects.all()
            else:
                handled_ids = set(
                    ApprovalRecord.objects.filter(handler=user).values_list('approval_id', flat=True)
                )
                handled_ids.update(
                    ApprovalTask.objects.filter(handler=user).values_list('approval_id', flat=True)
                )
                approvals = Approval.objects.filter(
                    Q(applicant_id=user.id) |
                    Q(reviewer=user) |
                    Q(id__in=handled_ids)
                ).distinct()
            
            if keyword:
                approvals = approvals.filter(Q(title__icontains=keyword))
            
            approvals = approvals.order_by('-create_time')[:page_size]

            return [
                self._build_item(
                    module='approval',
                    item_type='approval',
                    item_type_label='审批单',
                    id=a.id,
                    title=a.title or f'审批{a.id}',
                    url=f'/approval/{a.id}/',
                    created_at=self._format_created_at(a.create_time),
                    status=a.status if hasattr(a, 'status') else 'pending',
                    status_display=a.get_status_display() if hasattr(a, 'get_status_display') else '',
                    quick_actions=['view', 'approve'],
                    summary='接收方可直接查看详情并处理审批',
                )
                for a in approvals
            ]
        except Exception as e:
            logger.error(f'获取审批数据失败: {e}', exc_info=True)
            return []

    def _get_tasks(self, user, keyword, page_size):
        """获取任务列表"""
        try:
            from apps.project.models import Task
            
            # 根据权限获取任务:管理员看所有,普通用户看自己的任务
            if user.is_superuser:
                tasks = Task.objects.all()
            else:
                tasks = Task.objects.filter(
                    Q(assignee=user) | Q(creator=user)
                ).distinct()
            
            if keyword:
                tasks = tasks.filter(
                    Q(title__icontains=keyword) | Q(description__icontains=keyword)
                )
            
            tasks = tasks.order_by('-create_time')[:page_size]

            return [
                self._build_item(
                    module='task',
                    item_type='task',
                    item_type_label='任务',
                    id=t.id,
                    title=t.title,
                    url=f'/task/detail/{t.id}/',
                    created_at=self._format_created_at(t.create_time),
                    status=t.status if hasattr(t, 'status') else '',
                    status_display=t.get_status_display() if hasattr(t, 'get_status_display') else '',
                    quick_actions=['view', 'claim', 'comment'],
                    summary=(t.project.name if getattr(t, 'project', None) else '任务协同').strip(),
                    extra={
                        'assignee_id': t.assignee_id if hasattr(t, 'assignee_id') else None,
                    },
                )
                for t in tasks
            ]
        except Exception as e:
            logger.error(f'获取任务数据失败: {e}', exc_info=True)
            return []

    def _get_files(self, user, keyword, page_size):
        """获取文件列表"""
        try:
            from apps.disk.models import DiskFile
            
            # 根据权限获取文件:管理员看所有,普通用户看自己的文件
            if user.is_superuser:
                files = DiskFile.objects.all()
            else:
                files = DiskFile.objects.filter(
                    Q(owner=user) | Q(shared_users=user) | Q(is_public=True)
                ).distinct()
            
            if keyword:
                files = files.filter(Q(name__icontains=keyword) | Q(original_name__icontains=keyword))
            
            files = files.order_by('-create_time')[:page_size]

            return [
                self._build_item(
                    module='file',
                    item_type='file',
                    item_type_label='文件',
                    id=f.id,
                    title=f.original_name or f.name,
                    url=f'/disk/file/preview/{f.id}/',
                    created_at=self._format_created_at(f.create_time),
                    quick_actions=['preview', 'download', 'share'],
                    summary='支持在线预览与下载',
                    extra={
                        'file_name': f.original_name or f.name,
                    },
                )
                for f in files
            ]
        except Exception as e:
            logger.error(f'获取文件数据失败: {e}', exc_info=True)
            return []

    def _get_productions(self, user, keyword, page_size):
        """获取生产计划列表"""
        try:
            from apps.production.models import BOM, ProcessRoute, ProductionPlan, ProductionTask
            
            # 根据权限获取生产计划:管理员看所有,普通用户看自己负责的
            if user.is_superuser:
                plans = ProductionPlan.objects.all()
            else:
                plans = ProductionPlan.objects.filter(
                    Q(manager=user) | Q(creator=user)
                ).distinct()
            
            if keyword:
                plans = plans.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword))
            
            plans = list(plans.order_by('-create_time')[:page_size])

            if user.is_superuser:
                tasks = ProductionTask.objects.select_related('plan').all()
                routes = ProcessRoute.objects.all()
                boms = BOM.objects.all()
            else:
                tasks = ProductionTask.objects.select_related('plan').filter(
                    Q(assignee=user) | Q(creator=user) | Q(plan__manager=user)
                ).distinct()
                routes = ProcessRoute.objects.filter(creator=user)
                boms = BOM.objects.filter(creator=user)

            if keyword:
                tasks = tasks.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword))
                routes = routes.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword))
                boms = boms.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword))

            tasks = list(tasks.order_by('-create_time')[:page_size])
            routes = list(routes.order_by('-create_time')[: max(1, page_size // 2)])
            boms = list(boms.order_by('-create_time')[: max(1, page_size // 2)])

            items = [
                self._build_item(
                    module='production',
                    item_type='plan',
                    item_type_label='生产计划',
                    id=p.id,
                    title=p.name,
                    url=f'/production/task/plan/detail/{p.id}/',
                    created_at=self._format_created_at(p.create_time),
                    status=p.status if hasattr(p, 'status') else '',
                    status_display=p.get_status_display() if hasattr(p, 'get_status_display') else '',
                    quick_actions=['view', 'update'],
                    summary='生产计划与整体进度',
                    extra={
                        'progress': float(p.completion_rate) if hasattr(p, 'completion_rate') else 0,
                    },
                )
                for p in plans
            ]
            items.extend([
                self._build_item(
                    module='production',
                    item_type='task',
                    item_type_label='生产任务',
                    id=t.plan_id or t.id,
                    title=t.name,
                    url=f'/production/task/plan/detail/{t.plan_id or t.id}/',
                    created_at=self._format_created_at(t.create_time),
                    status=t.status if hasattr(t, 'status') else '',
                    status_display=t.get_status_display() if hasattr(t, 'get_status_display') else '',
                    quick_actions=['view', 'update'],
                    summary=(t.plan.name if getattr(t, 'plan', None) else '生产任务').strip(),
                    extra={
                        'progress': float(t.progress_rate) if hasattr(t, 'progress_rate') else 0,
                    },
                )
                for t in tasks
            ])
            items.extend([
                self._build_item(
                    module='production',
                    item_type='route',
                    item_type_label='工艺路线',
                    id=r.id,
                    title=r.name,
                    url=f'/production/process/detail/{r.id}/',
                    created_at=self._format_created_at(r.create_time),
                    status=r.status,
                    status_display=r.status_display,
                    quick_actions=['view', 'share'],
                    summary=f'工艺路线 {r.code}',
                )
                for r in routes
            ])
            items.extend([
                self._build_item(
                    module='production',
                    item_type='bom',
                    item_type_label='BOM',
                    id=b.id,
                    title=b.name,
                    url=f'/production/bom/detail/{b.id}/',
                    created_at=self._format_created_at(b.create_time),
                    quick_actions=['view', 'share'],
                    summary=f'BOM {b.code}',
                )
                for b in boms
            ])
            return items[: page_size * 3]
        except Exception as e:
            logger.error(f'获取生产数据失败: {e}', exc_info=True)
            return []

    def _get_finances(self, user, keyword, page_size):
        """获取财务记录列表"""
        try:
            from apps.finance.models import Expense, Invoice
            
            # 根据权限获取财务:管理员看所有,普通用户看自己的报销
            if user.is_superuser:
                expenses = Expense.objects.all()
                invoices = Invoice.objects.all()
            else:
                expenses = Expense.objects.filter(Q(admin_id=user.id)).distinct()
                invoices = Invoice.objects.filter(Q(admin_id=user.id)).distinct()

            if keyword:
                expenses = expenses.filter(Q(code__icontains=keyword))
                invoices = invoices.filter(
                    Q(code__icontains=keyword) |
                    Q(invoice_title__icontains=keyword)
                )

            expenses = list(expenses.order_by('-create_time')[:page_size])
            invoices = list(invoices.order_by('-create_time')[:page_size])

            items = [
                self._build_item(
                    module='finance',
                    item_type='expense',
                    item_type_label='报销',
                    id=e.id,
                    title=f'报销-{e.code}',
                    url=f'/finance/expense/view/{e.id}/',
                    created_at=self._format_created_at(e.create_time),
                    status=e.check_status if hasattr(e, 'check_status') else 'pending',
                    status_display=e.get_check_status_display() if hasattr(e, 'get_check_status_display') else (e.get_pay_status_display() if hasattr(e, 'get_pay_status_display') else ''),
                    quick_actions=['view', 'approve_finance'],
                    summary='报销审核与财务处理',
                    extra={
                        'check_status': e.check_status if hasattr(e, 'check_status') else 'pending',
                    },
                )
                for e in expenses
            ]
            items.extend([
                self._build_item(
                    module='finance',
                    item_type='invoice',
                    item_type_label='开票',
                    id=i.id,
                    title=f'开票-{i.code}',
                    url=f'/finance/invoice/view/{i.id}/',
                    created_at=self._format_created_at(i.create_time),
                    status=i.check_status if hasattr(i, 'check_status') else '',
                    status_display=i.get_open_status_display() if hasattr(i, 'get_open_status_display') else '',
                    quick_actions=['view'],
                    summary=(i.invoice_title or '开票处理').strip(),
                    extra={
                        'check_status': i.check_status if hasattr(i, 'check_status') else '',
                        'open_status': getattr(i, 'open_status', ''),
                    },
                )
                for i in invoices
            ])
            return items[: page_size * 2]
        except Exception as e:
            logger.error(f'获取财务数据失败: {e}', exc_info=True)
            return []
