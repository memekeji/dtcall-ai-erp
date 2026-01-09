"""
财务管理模块服务层
提供业务逻辑封装和公共服务
"""
from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone
from decimal import Decimal
import logging
from typing import Dict, List, Tuple
from datetime import timedelta

from .models import (
    Expense, ExpenseItem,
    Invoice, Income, Payment,
    InvoiceRequest,
    ApprovalStatusChoices,
    InvoiceStatusChoices, IncomeStatusChoices,
    PaymentMethodChoices, InvoiceVerifyRecord
)

logger = logging.getLogger(__name__)


class ExpenseService:
    """报销服务类"""

    @staticmethod
    def create_expense(applicant, data: Dict) -> Expense:
        """创建报销单"""
        with transaction.atomic():
            expense = Expense.objects.create(
                applicant=applicant,
                title=data.get('title', ''),
                category_id=data.get('category_id'),
                project_id=data.get('project_id'),
                total_amount=Decimal(str(data.get('total_amount', 0))),
                expense_date=data.get('expense_date'),
                description=data.get('description', ''),
                remark=data.get('remark', ''),
                approval_status=ApprovalStatusChoices.DRAFT
            )

            items_data = data.get('items', [])
            for item_data in items_data:
                ExpenseItem.objects.create(
                    expense=expense,
                    category_id=item_data.get('category_id'),
                    description=item_data.get('description', ''),
                    amount=Decimal(str(item_data.get('amount', 0))),
                    expense_date=item_data.get('expense_date'),
                    remark=item_data.get('remark', '')
                )

            return expense

    @staticmethod
    def submit_expense(expense_id: int, user) -> Tuple[bool, str]:
        """提交报销"""
        try:
            expense = Expense.objects.get(id=expense_id)
            if not expense.can_submit:
                return False, '当前状态不允许提交'

            if expense.category and expense.category.requires_approval:
                expense.approval_status = ApprovalStatusChoices.PENDING
            else:
                expense.approval_status = ApprovalStatusChoices.APPROVED
                expense.approved_by = user
                expense.approved_at = timezone.now()

            expense.save()
            return True, '提交成功'
        except Expense.DoesNotExist:
            return False, '报销单不存在'

    @staticmethod
    def approve_expense(expense_id: int, user, action: str,
                        approved_amount: Decimal = None, notes: str = '') -> Tuple[bool, str]:
        """审批报销"""
        try:
            expense = Expense.objects.get(id=expense_id)
            if not expense.can_approve:
                return False, '当前状态不允许审批'

            if action == 'approve':
                expense.approval_status = ApprovalStatusChoices.APPROVED
                expense.approved_amount = approved_amount or expense.total_amount
            else:
                expense.approval_status = ApprovalStatusChoices.REJECTED
                expense.approved_amount = Decimal('0')

            expense.approved_by = user
            expense.approved_at = timezone.now()
            expense.approval_notes = notes
            expense.save()

            return True, '审批成功'
        except Expense.DoesNotExist:
            return False, '报销单不存在'

    @staticmethod
    def pay_expense(expense_id: int, user, amount: Decimal,
                    payment_method: str = 'bank_transfer',
                    bank_name: str = '', bank_account: str = '',
                    transaction_no: str = '', remark: str = '') -> Tuple[bool, str, Payment]:
        """付款"""
        try:
            expense = Expense.objects.get(id=expense_id)
            if not expense.can_pay:
                return False, '当前状态不允许付款', None

            payment = Payment.objects.create(
                expense=expense,
                amount=amount,
                payment_date=timezone.now().date(),
                payment_method=payment_method,
                bank_name=bank_name,
                bank_account=bank_account,
                transaction_no=transaction_no,
                remark=remark,
                confirmed_by=user,
                confirmed_at=timezone.now()
            )

            return True, '付款成功', payment
        except Expense.DoesNotExist:
            return False, '报销单不存在', None

    @staticmethod
    def get_expense_statistics(start_date=None, end_date=None) -> Dict:
        """获取报销统计"""
        queryset = Expense.objects.all()

        if start_date:
            queryset = queryset.filter(expense_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(expense_date__lte=end_date)

        stats = queryset.aggregate(
            total_count=Count('id'),
            total_amount=Sum('total_amount'),
            approved_amount=Sum('approved_amount'),
            paid_amount=Sum('paid_amount')
        )

        by_status = {}
        for status, _ in ApprovalStatusChoices.choices:
            by_status[status] = queryset.filter(approval_status=status).count()

        return {
            'total_count': stats['total_count'] or 0,
            'total_amount': float(stats['total_amount'] or 0),
            'approved_amount': float(stats['approved_amount'] or 0),
            'paid_amount': float(stats['paid_amount'] or 0),
            'by_status': by_status
        }

    @staticmethod
    def batch_approve(expense_ids: List[int], user, action: str) -> Tuple[int, int]:
        """批量审批"""
        expenses = Expense.objects.filter(
            id__in=expense_ids,
            can_approve=True
        )

        success_count = 0
        fail_count = 0

        for expense in expenses:
            try:
                if action == 'approve':
                    expense.approval_status = ApprovalStatusChoices.APPROVED
                    expense.approved_amount = expense.total_amount
                else:
                    expense.approval_status = ApprovalStatusChoices.REJECTED
                    expense.approved_amount = Decimal('0')

                expense.approved_by = user
                expense.approved_at = timezone.now()
                expense.save()
                success_count += 1
            except Exception as e:
                logger.error(f'审批报销 {expense.id} 失败: {str(e)}')
                fail_count += 1

        return success_count, fail_count


class InvoiceService:
    """发票服务类"""

    @staticmethod
    def create_invoice(applicant, data: Dict) -> Invoice:
        """创建发票"""
        invoice = Invoice.objects.create(
            applicant=applicant,
            title=data.get('title', ''),
            customer_id=data.get('customer_id'),
            contract_id=data.get('contract_id'),
            project_id=data.get('project_id'),
            invoice_type=data.get('invoice_type', 'ordinary'),
            amount=Decimal(str(data.get('amount', 0))),
            tax_rate=Decimal(str(data.get('tax_rate', 13))),
            invoice_title=data.get('invoice_title', ''),
            tax_number=data.get('tax_number', ''),
            invoice_address=data.get('invoice_address', ''),
            invoice_phone=data.get('invoice_phone', ''),
            bank_name=data.get('bank_name', ''),
            bank_account=data.get('bank_account', ''),
            description=data.get('description', ''),
            remark=data.get('remark', ''),
            invoice_status=InvoiceStatusChoices.DRAFT
        )
        return invoice

    @staticmethod
    def issue_invoice(invoice_id: int, user) -> Tuple[bool, str]:
        """开具发票"""
        try:
            invoice = Invoice.objects.get(id=invoice_id)
            if invoice.invoice_status != InvoiceStatusChoices.PENDING:
                return False, '当前状态不允许开票'

            invoice.invoice_status = InvoiceStatusChoices.ISSUED
            invoice.issued_by = user
            invoice.issued_at = timezone.now()
            invoice.save()

            return True, '开票成功'
        except Invoice.DoesNotExist:
            return False, '发票不存在'

    @staticmethod
    def get_invoice_statistics(start_date=None, end_date=None) -> Dict:
        """获取发票统计"""
        queryset = Invoice.objects.all()

        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        stats = queryset.aggregate(
            total_count=Count('id'),
            total_amount=Sum('amount'),
            enter_amount=Sum('enter_amount')
        )

        by_status = {}
        for status, _ in InvoiceStatusChoices.CHOICES:
            by_status[status] = queryset.filter(invoice_status=status).count()

        return {
            'total_count': stats['total_count'] or 0,
            'total_amount': float(stats['total_amount'] or 0),
            'enter_amount': float(stats['enter_amount'] or 0),
            'by_status': by_status
        }


class IncomeService:
    """回款服务类"""

    @staticmethod
    def create_income(data: Dict) -> Income:
        """创建回款"""
        income = Income.objects.create(
            invoice_id=data.get('invoice_id'),
            amount=Decimal(str(data.get('amount', 0))),
            income_date=data.get('income_date'),
            payment_method=data.get('payment_method', 'bank_transfer'),
            bank_name=data.get('bank_name', ''),
            bank_account=data.get('bank_account', ''),
            transaction_no=data.get('transaction_no', ''),
            remark=data.get('remark', '')
        )
        return income

    @staticmethod
    def verify_income(income_id: int, verify_data: List[Dict]) -> Tuple[bool, str]:
        """核销回款"""
        try:
            income = Income.objects.get(id=income_id)
            total_verify = sum(Decimal(str(item.get('amount', 0))) for item in verify_data)

            if total_verify > income.amount:
                return False, '核销金额超出回款金额'

            for item in verify_data:
                invoice_id = item.get('invoice_id')
                amount = Decimal(str(item.get('amount', 0)))

                if amount <= 0:
                    continue

                InvoiceVerifyRecord.objects.create(
                    invoice_id=invoice_id,
                    income=income,
                    amount=amount
                )

                invoice = Invoice.objects.get(id=invoice_id)
                invoice.enter_amount += amount
                if invoice.enter_amount >= invoice.amount:
                    invoice.enter_status = IncomeStatusChoices.PAID
                else:
                    invoice.enter_status = IncomeStatusChoices.PARTIAL
                invoice.save()

            return True, '核销成功'
        except Income.DoesNotExist:
            return False, '回款记录不存在'

    @staticmethod
    def get_income_statistics(start_date=None, end_date=None) -> Dict:
        """获取回款统计"""
        queryset = Income.objects.all()

        if start_date:
            queryset = queryset.filter(income_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(income_date__lte=end_date)

        stats = queryset.aggregate(
            total_count=Count('id'),
            total_amount=Sum('amount')
        )

        by_method = {}
        for method, _ in PaymentMethodChoices.CHOICES:
            by_method[method] = queryset.filter(payment_method=method).aggregate(
                total=Sum('amount')
            )['total'] or 0

        return {
            'total_count': stats['total_count'] or 0,
            'total_amount': float(stats['total_amount'] or 0),
            'by_method': by_method
        }


class InvoiceRequestService:
    """开票申请服务类"""

    @staticmethod
    def create_request(applicant, data: Dict) -> InvoiceRequest:
        """创建开票申请"""
        request = InvoiceRequest.objects.create(
            applicant=applicant,
            order_id=data.get('order_id'),
            department_id=data.get('department_id', 0),
            amount=Decimal(str(data.get('amount', 0))),
            invoice_type=data.get('invoice_type', 'ordinary'),
            invoice_title=data.get('invoice_title', ''),
            tax_number=data.get('tax_number', ''),
            reason=data.get('reason', ''),
            status='pending'
        )
        return request

    @staticmethod
    def approve_request(request_id: int, user, action: str, comment: str = '') -> Tuple[bool, str]:
        """审批开票申请"""
        try:
            request = InvoiceRequest.objects.get(id=request_id)
            if request.status != 'pending':
                return False, '该申请已被处理'

            request.status = action
            request.reviewer = user
            request.review_time = timezone.now()
            request.review_comment = comment
            request.save()

            if action == 'approved':
                invoice = Invoice.objects.create(
                    title=f"开票-{request.order.order_number}",
                    customer=request.order.customer,
                    applicant=request.applicant,
                    department_id=request.department_id,
                    invoice_type=request.invoice_type,
                    amount=request.amount,
                    invoice_title=request.invoice_title,
                    tax_number=request.tax_number,
                    invoice_status=InvoiceStatusChoices.PENDING
                )
                request.invoice = invoice
                request.invoice_time = timezone.now()
                request.status = 'invoiced'
                request.save()

            return True, '审批成功'
        except InvoiceRequest.DoesNotExist:
            return False, '申请不存在'


class FinanceStatisticsService:
    """财务统计服务类"""

    @staticmethod
    def get_dashboard_statistics() -> Dict:
        """获取仪表盘统计数据"""
        today = timezone.now().date()
        month_start = today.replace(day=1)

        expense_stats = ExpenseService.get_expense_statistics(start_date=month_start)
        invoice_stats = InvoiceService.get_invoice_statistics(start_date=month_start)
        income_stats = IncomeService.get_income_statistics(start_date=month_start)

        pending_expenses = Expense.objects.filter(
            approval_status=ApprovalStatusChoices.PENDING
        ).count()

        pending_invoices = Invoice.objects.filter(
            invoice_status=InvoiceStatusChoices.PENDING
        ).count()

        pending_requests = InvoiceRequest.objects.filter(
            status='pending'
        ).count()

        return {
            'expense': expense_stats,
            'invoice': invoice_stats,
            'income': income_stats,
            'pending': {
                'expenses': pending_expenses,
                'invoices': pending_invoices,
                'requests': pending_requests
            }
        }

    @staticmethod
    def get_monthly_trend(months: int = 12) -> Dict:
        """获取月度趋势数据"""
        today = timezone.now().date()
        trends = []

        for i in range(months):
            month_start = today.replace(day=1)
            if i > 0:
                month_start = month_start - timedelta(days=1)
                month_start = month_start.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

            expense_stats = ExpenseService.get_expense_statistics(
                start_date=month_start, end_date=month_end
            )
            income_stats = IncomeService.get_income_statistics(
                start_date=month_start, end_date=month_end
            )

            trends.append({
                'month': month_start.strftime('%Y-%m'),
                'expense_amount': expense_stats['total_amount'],
                'income_amount': income_stats['total_amount'],
                'expense_count': expense_stats['total_count'],
                'income_count': income_stats['total_count']
            })

        return trends
