# -*- coding: utf-8 -*-
"""
在线沟通协作信息视图
用于在一对一沟通时展示双方之间的跨模块协作数据
"""
from datetime import datetime
from django.db.models import Q
from rest_framework import views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class UserCollaborationView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        target_user_id = request.query_params.get('target_user_id')
        if not target_user_id:
            return Response({'error': '缺少target_user_id参数'}, status=400)

        try:
            target_user_id = int(target_user_id)
        except (TypeError, ValueError):
            return Response({'error': 'target_user_id必须是整数'}, status=400)

        from apps.user.models import Admin

        try:
            target_user = Admin.objects.get(id=target_user_id, status=1)
        except Admin.DoesNotExist:
            return Response({'error': '目标用户不存在'}, status=404)

        current_user = request.user
        module_builders = [
            self._get_customer_collaboration,
            self._get_project_collaboration,
            self._get_contract_collaboration,
            self._get_approval_collaboration,
            self._get_finance_collaboration,
            self._get_task_collaboration,
            self._get_production_collaboration,
        ]
        modules = []
        for builder in module_builders:
            module_data = builder(current_user, target_user)
            if module_data['count'] > 0:
                modules.append(module_data)

        return Response({
            'target_user': {
                'id': target_user.id,
                'name': target_user.name or target_user.username,
                'username': target_user.username,
                'department': self._department_name(target_user),
            },
            'modules': modules,
        })

    def _department_name(self, user):
        department = getattr(user, 'department', None)
        if department:
            return department.name
        return ''

    def _format_item(
        self,
        obj,
        title,
        url,
        status='',
        status_display='',
        date_value='',
        item_type='',
        item_type_label='',
        quick_actions=None,
        summary='',
        extra=None,
    ):
        payload = {
            'id': obj.id,
            'title': title,
            'status': status,
            'status_display': status_display,
            'url': url,
            'date': date_value,
            'item_type': item_type,
            'item_type_label': item_type_label or item_type,
            'quick_actions': quick_actions or ['view'],
            'summary': summary,
        }
        if extra:
            payload.update(extra)
        return payload

    def _format_date(self, value, fmt='%Y-%m-%d'):
        if not value:
            return ''

        if hasattr(value, 'strftime'):
            return value.strftime(fmt)

        try:
            return datetime.fromtimestamp(int(value)).strftime(fmt)
        except (TypeError, ValueError, OSError, OverflowError):
            return str(value)

    def _customer_shared_q(self, user1, user2):
        return (
            Q(principal=user1, admin_id=user2.id) |
            Q(principal=user2, admin_id=user1.id) |
            Q(principal__in=[user1, user2], admin_id__in=[user1.id, user2.id])
        )

    def _get_customer_collaboration(self, user1, user2):
        from apps.customer.models import Customer, FollowRecord

        followed_ids = FollowRecord.objects.filter(
            follow_user__in=[user1, user2],
            customer__principal__in=[user1, user2],
        ).values_list('customer_id', flat=True)

        customers = list(
            Customer.objects.filter(
                self._customer_shared_q(user1, user2) |
                Q(id__in=followed_ids)
            ).distinct().order_by('-create_time')[:10]
        )
        items = [
            self._format_item(
                customer,
                title=customer.name,
                url=f'/customer/detail/{customer.id}/',
                status=str(customer.intent_status),
                status_display=getattr(customer, 'intent_status_display', '') or '',
                date_value=customer.create_time.strftime('%Y-%m-%d') if customer.create_time else '',
                item_type='customer',
                item_type_label='客户',
                quick_actions=['view', 'follow', 'contact'],
                summary='可直接查看客户详情、记录跟进或发起协同',
            )
            for customer in customers
        ]

        # 追加跟进记录（双方共同客户的跟进历史）
        if customers:
            customer_ids = [c.id for c in customers]
            follow_records = list(
                FollowRecord.objects.select_related("customer", "follow_user").filter(
                    customer_id__in=customer_ids,
                    follow_user__in=[user1, user2],
                ).order_by("-follow_time")[:8]
            )
            for fr in follow_records:
                display = fr.get_follow_type_display()
                name = fr.customer.name
                items.append(
                    self._format_item(
                        fr,
                        title=display + " - " + name,
                        url="/customer/detail/" + str(fr.customer_id) + "/",
                        date_value=self._format_date(fr.follow_time),
                        item_type="follow",
                        item_type_label="跟进记录",
                        quick_actions=["view", "follow"],
                        summary="客户：" + name,
                        extra={"customer_id": fr.customer_id, "follow_user": fr.follow_user.name if fr.follow_user else ""},
                    )
                )

        return {
            'module': 'customer',
            'name': '客户协作',
            'icon': 'layui-icon-user',
            'count': len(items),
            'items': items,
        }

    def _get_project_collaboration(self, user1, user2):
        from apps.project.models import Project, ProjectDocument

        projects = list(
            Project.objects.filter(
                (
                    Q(manager=user1) &
                    (Q(creator=user2) | Q(members=user2))
                ) |
                (
                    Q(manager=user2) &
                    (Q(creator=user1) | Q(members=user1))
                ) |
                (
                    Q(creator=user1) & Q(members=user2)
                ) |
                (
                    Q(creator=user2) & Q(members=user1)
                )
            ).distinct().order_by('-create_time')[:10]
        )

        documents = list(
            ProjectDocument.objects.select_related('project').filter(
                Q(project__manager__in=[user1, user2]) &
                Q(project__creator__in=[user1, user2])
            ).distinct().order_by('-create_time')[:6]
        )
        items = [
            self._format_item(
                project,
                title=project.name,
                url=f'/project/detail/{project.id}/',
                status=project.status,
                status_display=project.status_display,
                date_value=project.create_time.strftime('%Y-%m-%d') if project.create_time else '',
                item_type='project',
                item_type_label='项目',
                quick_actions=['view', 'docs', 'activities'],
                summary=(project.description or '查看项目进展、成员协作与动态').strip(),
                extra={
                    'project_id': project.id,
                },
            )
            for project in projects
        ]
        items.extend([
            self._format_item(
                document,
                title=document.title,
                url=f'/project/document/detail/{document.id}/',
                date_value=document.create_time.strftime('%Y-%m-%d') if document.create_time else '',
                item_type='document',
                item_type_label='项目文档',
                quick_actions=['view', 'share'],
                summary=(document.project.name + ' / 文档资料') if document.project else '项目文档',
                extra={
                    'project_id': document.project_id,
                    'project_name': document.project.name if document.project else '',
                },
            )
            for document in documents
        ])
        return {
            'module': 'project',
            'name': '项目协作',
            'icon': 'layui-icon-template-1',
            'count': len(items),
            'items': items[:10],
        }

    def _get_contract_collaboration(self, user1, user2):
        from apps.customer.models import CustomerContract

        contracts = list(
            CustomerContract.objects.filter(
                Q(create_user__in=[user1, user2]) &
                (
                    Q(customer__principal__in=[user1, user2]) |
                    Q(customer__admin_id__in=[user1.id, user2.id])
                )
            ).distinct().order_by('-create_time')[:10]
        )
        items = [
            self._format_item(
                contract,
                title=contract.name or f'合同{contract.contract_number}',
                url=f'/customer/orders/{contract.id}/detail/',
                status=contract.status,
                status_display=contract.get_status_display(),
                date_value=contract.sign_date.strftime('%Y-%m-%d') if contract.sign_date else '',
                item_type='contract',
                item_type_label='合同',
                quick_actions=['view', 'download', 'sign'],
                summary=(f'合同编号 {contract.contract_number}' if contract.contract_number else '合同资料').strip(),
            )
            for contract in contracts
        ]
        return {
            'module': 'contract',
            'name': '合同协作',
            'icon': 'layui-icon-file',
            'count': len(items),
            'items': items,
        }

    def _get_approval_collaboration(self, user1, user2):
        from apps.approval.models import Approval, ApprovalRecord, ApprovalTask

        approval_ids = set(
            ApprovalRecord.objects.filter(handler__in=[user1, user2]).values_list(
                'approval_id', flat=True
            )
        )
        approval_ids.update(
            ApprovalTask.objects.filter(handler__in=[user1, user2]).values_list(
                'approval_id', flat=True
            )
        )
        approvals = list(
            Approval.objects.filter(
                (
                    Q(applicant_id=user1.id) & (
                        Q(reviewer=user2) | Q(id__in=approval_ids)
                    )
                ) |
                (
                    Q(applicant_id=user2.id) & (
                        Q(reviewer=user1) | Q(id__in=approval_ids)
                    )
                )
            ).distinct().order_by('-create_time')[:10]
        )
        items = [
            self._format_item(
                approval,
                title=approval.title or f'审批{approval.id}',
                url=f'/approval/{approval.id}/',
                status=approval.status,
                status_display=approval.get_status_display(),
                date_value=approval.create_time.strftime('%Y-%m-%d') if approval.create_time else '',
                item_type='approval',
                item_type_label='审批单',
                quick_actions=['view', 'approve'],
                summary='接收方可直接查看详情并处理审批',
            )
            for approval in approvals
        ]

        # 追加审批任务（双方在审批流程中的处理节点）
        if approvals:
            approval_ids_list = [a.id for a in approvals]
            approval_tasks = list(
                ApprovalTask.objects.select_related("approval", "step", "handler").filter(
                    approval_id__in=approval_ids_list,
                    handler__in=[user1, user2],
                ).order_by("-completed_at", "-approval__create_time")[:8]
            )
            for at in approval_tasks:
                status_display_val = ""
                if hasattr(at, "get_status_display"):
                    status_display_val = at.get_status_display()
                step_name = at.step.step_name if at.step else ""
                handler_name = at.handler.name if at.handler else ""
                title_str = at.approval.title if at.approval.title else str(at.approval.id)
                items.append(
                    self._format_item(
                        at,
                        title=step_name + " - " + handler_name,
                        url="/approval/" + str(at.approval_id) + "/",
                        status=at.status,
                        status_display=status_display_val,
                        date_value=self._format_date(at.completed_at or getattr(at, "create_time", None)),
                        item_type="approval_task",
                        item_type_label="审批任务",
                        quick_actions=["view", "approve"],
                        summary="审批：" + title_str,
                        extra={"approval_id": at.approval_id, "step_name": step_name},
                    )
                )

        return {
            'module': 'approval',
            'name': '审批协作',
            'icon': 'layui-icon-audit',
            'count': len(items),
            'items': items,
        }

    def _split_int_values(self, value):
        result = set()
        for part in str(value or '').split(','):
            part = part.strip()
            if part.isdigit():
                result.add(int(part))
        return result

    def _field_contains_user_id(self, value, user_id):
        return int(user_id) in self._split_int_values(value)

    def _matches_finance_collaboration(self, item, owner_id, collaborator_id):
        if item.admin_id != owner_id:
            return False

        if str(item.check_last_uid or '').strip() == str(collaborator_id):
            return True

        return (
            self._field_contains_user_id(item.check_uids, collaborator_id) or
            self._field_contains_user_id(item.check_history_uids, collaborator_id)
        )

    def _get_finance_collaboration(self, user1, user2):
        from apps.finance.models import Expense, Invoice

        expense_candidates = Expense.objects.filter(
            admin_id__in=[user1.id, user2.id]
        ).order_by('-create_time')
        expenses = [
            expense for expense in expense_candidates
            if self._matches_finance_collaboration(expense, user1.id, user2.id) or
            self._matches_finance_collaboration(expense, user2.id, user1.id)
        ][:6]

        invoice_candidates = Invoice.objects.filter(
            admin_id__in=[user1.id, user2.id]
        ).order_by('-create_time')
        invoices = [
            invoice for invoice in invoice_candidates
            if self._matches_finance_collaboration(invoice, user1.id, user2.id) or
            self._matches_finance_collaboration(invoice, user2.id, user1.id)
        ][:4]

        items = [
            self._format_item(
                expense,
                title=f'报销-{expense.code or expense.id}',
                url=f'/finance/expense/view/{expense.id}/',
                status=expense.check_status,
                status_display=expense.get_check_status_display(),
                date_value=self._format_date(expense.create_time),
                item_type='expense',
                item_type_label='报销',
                quick_actions=['view', 'approve_finance'],
                summary='报销审核与财务处理',
            )
            for expense in expenses
        ]
        items.extend([
            self._format_item(
                invoice,
                title=f'开票-{invoice.code or invoice.id}',
                url=f'/finance/invoice/view/{invoice.id}/',
                status=invoice.check_status,
                status_display=invoice.get_open_status_display(),
                date_value=self._format_date(invoice.create_time),
                item_type='invoice',
                item_type_label='开票',
                quick_actions=['view'],
                summary=(invoice.invoice_title or '开票处理').strip(),
            )
            for invoice in invoices
        ])
        return {
            'module': 'finance',
            'name': '财务协作',
            'icon': 'layui-icon-rmb',
            'count': len(items),
            'items': items[:10],
        }

    def _get_task_collaboration(self, user1, user2):
        from apps.project.models import Task

        tasks = list(
            Task.objects.filter(
                (
                    Q(assignee=user1) &
                    (Q(creator=user2) | Q(participants=user2))
                ) |
                (
                    Q(assignee=user2) &
                    (Q(creator=user1) | Q(participants=user1))
                ) |
                (
                    Q(creator=user1) & Q(participants=user2)
                ) |
                (
                    Q(creator=user2) & Q(participants=user1)
                )
            ).distinct().order_by('-create_time')[:10]
        )
        items = [
            self._format_item(
                task,
                title=task.title,
                url=f'/task/detail/{task.id}/',
                status=task.status,
                status_display=task.status_display,
                date_value=task.create_time.strftime('%Y-%m-%d') if task.create_time else '',
                item_type='task',
                item_type_label='任务',
                quick_actions=['view', 'claim', 'comment'],
                summary=(task.project.name if getattr(task, 'project', None) else '任务协同').strip(),
                extra={
                    'assignee_id': task.assignee_id if hasattr(task, 'assignee_id') else None,
                },
            )
            for task in tasks
        ]
        return {
            'module': 'task',
            'name': '任务协作',
            'icon': 'layui-icon-list',
            'count': len(items),
            'items': items,
        }

    def _get_production_collaboration(self, user1, user2):
        from apps.production.models import BOM, ProcessRoute, ProductionPlan, ProductionTask

        plans = list(
            ProductionPlan.objects.filter(
                (
                    Q(manager=user1) & Q(creator=user2)
                ) |
                (
                    Q(manager=user2) & Q(creator=user1)
                ) |
                (
                    Q(manager__in=[user1, user2]) & Q(creator__in=[user1, user2])
                )
            ).distinct().order_by('-create_time')[:10]
        )

        tasks = list(
            ProductionTask.objects.select_related('plan').filter(
                (
                    Q(assignee=user1) & Q(creator=user2)
                ) |
                (
                    Q(assignee=user2) & Q(creator=user1)
                ) |
                (
                    Q(plan__manager__in=[user1, user2]) &
                    Q(plan__creator__in=[user1, user2])
                )
            ).distinct().order_by('-create_time')[:6]
        )
        routes = list(
            ProcessRoute.objects.filter(creator__in=[user1, user2]).order_by('-create_time')[:4]
        )
        boms = list(
            BOM.objects.filter(creator__in=[user1, user2]).order_by('-create_time')[:4]
        )
        items = [
            self._format_item(
                plan,
                title=plan.name or f'生产计划{plan.code}',
                url=f'/production/task/plan/detail/{plan.id}/',
                status=plan.status,
                status_display=plan.get_status_display(),
                date_value=plan.create_time.strftime('%Y-%m-%d') if plan.create_time else '',
                item_type='plan',
                item_type_label='生产计划',
                quick_actions=['view', 'update'],
                summary='生产计划与整体进度',
                extra={
                    'progress': float(plan.completion_rate) if hasattr(plan, 'completion_rate') else 0,
                },
            )
            for plan in plans
        ]
        items.extend([
            self._format_item(
                task,
                title=task.name,
                url=f'/production/task/plan/detail/{task.plan_id or task.id}/',
                status=task.status,
                status_display=task.get_status_display(),
                date_value=task.create_time.strftime('%Y-%m-%d') if task.create_time else '',
                item_type='task',
                item_type_label='生产任务',
                quick_actions=['view', 'update'],
                summary=(task.plan.name if getattr(task, 'plan', None) else '生产任务').strip(),
                extra={
                    'progress': float(task.progress_rate) if hasattr(task, 'progress_rate') else 0,
                },
            )
            for task in tasks
        ])
        items.extend([
            self._format_item(
                route,
                title=route.name,
                url=f'/production/process/detail/{route.id}/',
                status=route.status,
                status_display=route.status_display,
                date_value=route.create_time.strftime('%Y-%m-%d') if route.create_time else '',
                item_type='route',
                item_type_label='工艺路线',
                quick_actions=['view', 'share'],
                summary=f'工艺路线 {route.code}',
            )
            for route in routes
        ])
        items.extend([
            self._format_item(
                bom,
                title=bom.name,
                url=f'/production/bom/detail/{bom.id}/',
                date_value=bom.create_time.strftime('%Y-%m-%d') if bom.create_time else '',
                item_type='bom',
                item_type_label='BOM',
                quick_actions=['view', 'share'],
                summary=f'BOM {bom.code}',
            )
            for bom in boms
        ])
        return {
            'module': 'production',
            'name': '生产协作',
            'icon': 'layui-icon-engine',
            'count': len(items),
            'items': items[:10],
        }
