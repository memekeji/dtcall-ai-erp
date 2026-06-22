"""
财务管理模块服务层
封装当前财务模型可用的业务能力。
"""

from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Tuple

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .models import (
    AccountsPayable,
    AccountsReceivable,
    BankReconciliation,
    BankTransaction,
    CostAllocation,
    Expense,
    FinanceAccount,
    FinanceBudget,
    FinanceStatus,
    FinancialPeriodClose,
    FinancialReport,
    ChartOfAccount,
    LedgerVoucherLine,
    CashFlowPlan,
    FinancialRatio,
    ExpenseAccrual,
    FixedAsset,
    Income,
    Invoice,
    InvoiceRequest,
    InvoiceVerifyRecord,
    LedgerVoucher,
    OrderFinanceRecord,
    Payment,
    TaxRecord,
)


class ExpenseService:
    """报销服务类"""

    @staticmethod
    def mark_paid(
        expense_id: int,
        user,
        amount: Decimal,
        payment_date=None,
        file_ids: str = "",
        remark: str = "",
    ) -> Tuple[bool, str, Payment]:
        """登记报销付款并更新报销付款状态。"""
        try:
            expense = Expense.objects.get(id=expense_id)
        except Expense.DoesNotExist:
            return False, "报销单不存在", None

        if expense.check_status != FinanceStatus.EXPENSE_CHECK_APPROVED:
            return False, "仅审核通过的报销允许付款", None

        with transaction.atomic():
            payment = Payment.objects.create(
                expense_id=expense.id,
                amount=amount,
                payment_date=payment_date or timezone.now(),
                file_ids=file_ids,
                remark=remark,
                create_time=int(timezone.now().timestamp()),
            )
            expense.pay_status = FinanceStatus.PAY_STATUS_PAID
            expense.pay_admin_id = getattr(user, "id", 0) or 0
            expense.pay_time = int(payment.payment_date.timestamp())
            expense.save(update_fields=["pay_status", "pay_admin_id", "pay_time"])

        return True, "付款成功", payment

    @staticmethod
    def get_expense_statistics(start_ts=None, end_ts=None) -> Dict:
        queryset = Expense.objects.all()
        if start_ts:
            queryset = queryset.filter(expense_time__gte=start_ts)
        if end_ts:
            queryset = queryset.filter(expense_time__lte=end_ts)

        stats = queryset.aggregate(total_count=Count("id"), total_amount=Sum("cost"))
        paid_amount = Payment.objects.filter(
            expense_id__in=queryset.values("id")
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        return {
            "total_count": stats["total_count"] or 0,
            "total_amount": float(stats["total_amount"] or Decimal("0")),
            "approved_count": queryset.filter(
                check_status=FinanceStatus.EXPENSE_CHECK_APPROVED
            ).count(),
            "pending_count": queryset.filter(
                check_status=FinanceStatus.EXPENSE_CHECK_PENDING
            ).count(),
            "processing_count": queryset.filter(
                check_status=FinanceStatus.EXPENSE_CHECK_PROCESSING
            ).count(),
            "rejected_count": queryset.filter(
                check_status=FinanceStatus.EXPENSE_CHECK_REJECTED
            ).count(),
            "paid_amount": float(paid_amount),
            "unpaid_count": queryset.filter(
                check_status=FinanceStatus.EXPENSE_CHECK_APPROVED,
                pay_status=FinanceStatus.PAY_STATUS_PENDING,
            ).count(),
        }

    @staticmethod
    def batch_approve(expense_ids: List[int], user, action: str) -> Tuple[int, int]:
        expenses = Expense.objects.filter(
            id__in=expense_ids, check_status=FinanceStatus.EXPENSE_CHECK_PROCESSING
        )
        success_count = 0
        fail_count = 0
        now_ts = int(timezone.now().timestamp())

        for expense in expenses:
            if action == "approve":
                expense.check_status = FinanceStatus.EXPENSE_CHECK_APPROVED
                expense.check_time = now_ts
            else:
                expense.check_status = FinanceStatus.EXPENSE_CHECK_REJECTED
            expense.check_history_uids = (
                f"{expense.check_history_uids},{user.id}"
                if expense.check_history_uids
                else str(user.id)
            )
            expense.save(
                update_fields=["check_status", "check_time", "check_history_uids"]
            )
            success_count += 1

        fail_count = len(expense_ids) - success_count
        return success_count, fail_count


class InvoiceService:
    """发票服务类"""

    @staticmethod
    def issue_invoice(invoice_id: int, user) -> Tuple[bool, str]:
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return False, "发票不存在"

        if invoice.open_status == FinanceStatus.INVOICE_OPEN_STATUS_DONE:
            return False, "发票已开具"

        invoice.open_status = FinanceStatus.INVOICE_OPEN_STATUS_DONE
        invoice.open_admin_id = getattr(user, "id", 0) or 0
        invoice.open_time = int(timezone.now().timestamp())
        invoice.save(update_fields=["open_status", "open_admin_id", "open_time"])
        return True, "开票成功"

    @staticmethod
    def refresh_income_status(invoice: Invoice) -> Invoice:
        paid_amount = Income.objects.filter(invoice_id=invoice.id).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        invoice.enter_amount = min(paid_amount, invoice.amount)
        if invoice.enter_amount <= 0:
            invoice.enter_status = FinanceStatus.ENTER_STATUS_NOT
        elif invoice.enter_amount < invoice.amount:
            invoice.enter_status = FinanceStatus.ENTER_STATUS_PARTIAL
        else:
            invoice.enter_status = FinanceStatus.ENTER_STATUS_FULL
        latest_income = (
            Income.objects.filter(invoice_id=invoice.id)
            .order_by("-income_date")
            .first()
        )
        invoice.enter_time = (
            int(latest_income.income_date.timestamp()) if latest_income else 0
        )
        invoice.save(update_fields=["enter_amount", "enter_status", "enter_time"])
        return invoice

    @staticmethod
    def get_invoice_statistics(start_ts=None, end_ts=None) -> Dict:
        queryset = Invoice.objects.all()
        if start_ts:
            queryset = queryset.filter(create_time__gte=start_ts)
        if end_ts:
            queryset = queryset.filter(create_time__lte=end_ts)

        stats = queryset.aggregate(
            total_count=Count("id"),
            total_amount=Sum("amount"),
            enter_amount=Sum("enter_amount"),
        )
        total_amount = stats["total_amount"] or Decimal("0")
        enter_amount = stats["enter_amount"] or Decimal("0")

        return {
            "total_count": stats["total_count"] or 0,
            "total_amount": float(total_amount),
            "enter_amount": float(enter_amount),
            "uncollected_amount": float(max(total_amount - enter_amount, Decimal("0"))),
            "not_open_count": queryset.filter(
                open_status=FinanceStatus.INVOICE_OPEN_STATUS_NOT
            ).count(),
            "opened_count": queryset.filter(
                open_status=FinanceStatus.INVOICE_OPEN_STATUS_DONE
            ).count(),
            "void_count": queryset.filter(
                open_status=FinanceStatus.INVOICE_OPEN_STATUS_VOID
            ).count(),
            "unpaid_count": queryset.filter(
                enter_status=FinanceStatus.ENTER_STATUS_NOT
            ).count(),
            "partial_count": queryset.filter(
                enter_status=FinanceStatus.ENTER_STATUS_PARTIAL
            ).count(),
            "paid_count": queryset.filter(
                enter_status=FinanceStatus.ENTER_STATUS_FULL
            ).count(),
        }


class IncomeService:
    """回款服务类"""

    @staticmethod
    def create_income(data: Dict) -> Income:
        with transaction.atomic():
            income = Income.objects.create(
                invoice_id=data.get("invoice_id") or 0,
                amount=Decimal(str(data.get("amount") or 0)),
                income_date=data.get("income_date") or timezone.now(),
                file_ids=data.get("file_ids", ""),
                remark=data.get("remark", ""),
                create_time=int(timezone.now().timestamp()),
            )
            if income.invoice_id:
                invoice = Invoice.objects.filter(id=income.invoice_id).first()
                if invoice:
                    InvoiceService.refresh_income_status(invoice)
            return income

    @staticmethod
    def delete_income(income: Income) -> None:
        invoice_id = income.invoice_id
        with transaction.atomic():
            income.delete()
            if invoice_id:
                invoice = Invoice.objects.filter(id=invoice_id).first()
                if invoice:
                    InvoiceService.refresh_income_status(invoice)

    @staticmethod
    def verify_income(income_id: int, verify_data: List[Dict]) -> Tuple[bool, str]:
        try:
            income = Income.objects.get(id=income_id)
        except Income.DoesNotExist:
            return False, "回款记录不存在"

        total_verify = sum(Decimal(str(item.get("amount", 0))) for item in verify_data)
        if total_verify > income.amount:
            return False, "核销金额超出回款金额"

        with transaction.atomic():
            for item in verify_data:
                invoice_id = item.get("invoice_id")
                amount = Decimal(str(item.get("amount", 0)))
                if not invoice_id or amount <= 0:
                    continue
                invoice = (
                    Invoice.objects.select_for_update().filter(id=invoice_id).first()
                )
                if not invoice:
                    continue
                InvoiceVerifyRecord.objects.create(
                    invoice_id=invoice.id,
                    income=income,
                    amount=amount,
                    create_time=int(timezone.now().timestamp()),
                )
                InvoiceService.refresh_income_status(invoice)

        return True, "核销成功"

    @staticmethod
    def get_income_statistics(start_date=None, end_date=None) -> Dict:
        queryset = Income.objects.all()
        if start_date:
            queryset = queryset.filter(income_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(income_date__lte=end_date)
        stats = queryset.aggregate(total_count=Count("id"), total_amount=Sum("amount"))
        return {
            "total_count": stats["total_count"] or 0,
            "total_amount": float(stats["total_amount"] or Decimal("0")),
        }


class PaymentService:
    """付款服务类"""

    @staticmethod
    def create_payment(data: Dict, user=None) -> Payment:
        expense_id = data.get("expense_id") or 0
        amount = Decimal(str(data.get("amount") or 0))
        expense = Expense.objects.filter(id=expense_id).first() if expense_id else None
        if expense:
            success, message, payment = ExpenseService.mark_paid(
                expense.id,
                user,
                amount,
                payment_date=data.get("payment_date") or timezone.now(),
                file_ids=data.get("file_ids", ""),
                remark=data.get("remark", ""),
            )
            if not success:
                raise ValueError(message)
            return payment

        return Payment.objects.create(
            expense_id=expense_id,
            amount=amount,
            payment_date=data.get("payment_date") or timezone.now(),
            file_ids=data.get("file_ids", ""),
            remark=data.get("remark", ""),
            create_time=int(timezone.now().timestamp()),
        )

    @staticmethod
    def get_payment_statistics(start_date=None, end_date=None) -> Dict:
        queryset = Payment.objects.all()
        if start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(payment_date__lte=end_date)
        stats = queryset.aggregate(total_count=Count("id"), total_amount=Sum("amount"))
        return {
            "total_count": stats["total_count"] or 0,
            "total_amount": float(stats["total_amount"] or Decimal("0")),
        }


class InvoiceRequestService:
    """开票申请服务类"""

    @staticmethod
    def approve_request(
        request_id: int, user, action: str, comment: str = ""
    ) -> Tuple[bool, str]:
        try:
            request = InvoiceRequest.objects.get(id=request_id)
        except InvoiceRequest.DoesNotExist:
            return False, "申请不存在"

        if request.status != "pending":
            return False, "该申请已被处理"

        request.status = action
        request.reviewer_id = getattr(user, "id", 0) or 0
        request.review_time = int(timezone.now().timestamp())
        request.review_comment = comment
        request.save(
            update_fields=["status", "reviewer_id", "review_time", "review_comment"]
        )

        if action == "approved":
            invoice = Invoice.objects.create(
                customer_id=0,
                amount=request.amount,
                admin_id=request.applicant_id,
                invoice_type=request.invoice_type,
                invoice_title=request.invoice_title,
                invoice_tax=request.tax_number,
                open_status=FinanceStatus.INVOICE_OPEN_STATUS_NOT,
                create_time=int(timezone.now().timestamp()),
                remark=request.reason,
            )
            request.invoice_id = invoice.id
            request.invoice_time = int(timezone.now().timestamp())
            request.status = "invoiced"
            request.save(update_fields=["invoice_id", "invoice_time", "status"])

        return True, "审批成功"


class AdvancedFinanceService:
    """专业财务扩展服务类"""

    @staticmethod
    def save_with_create_time(instance):
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_bank_transaction(form) -> BankTransaction:
        with transaction.atomic():
            instance = form.save(commit=False)
            old_instance = None
            if instance.pk:
                old_instance = BankTransaction.objects.select_for_update().get(
                    pk=instance.pk
                )
                old_account_id = old_instance.account_id
                old_amount = old_instance.amount
                old_direction = old_instance.direction
            if not instance.create_time:
                instance.create_time = int(timezone.now().timestamp())
            instance.save()
            if old_instance:
                AdvancedFinanceService.apply_account_balance(
                    old_account_id,
                    old_amount,
                    old_direction,
                    reverse=True,
                )
            AdvancedFinanceService.apply_account_balance(
                instance.account_id, instance.amount, instance.direction
            )
            return instance

    @staticmethod
    def delete_bank_transaction(instance: BankTransaction) -> None:
        with transaction.atomic():
            transaction_obj = BankTransaction.objects.select_for_update().get(
                pk=instance.pk
            )
            AdvancedFinanceService.apply_account_balance(
                transaction_obj.account_id,
                transaction_obj.amount,
                transaction_obj.direction,
                reverse=True,
            )
            transaction_obj.delete()

    @staticmethod
    def apply_account_balance(
        account_id: int, amount: Decimal, direction: str, reverse=False
    ) -> None:
        account = FinanceAccount.objects.select_for_update().get(pk=account_id)
        change_amount = amount if direction == "in" else -amount
        if reverse:
            change_amount = -change_amount
        account.current_balance = (
            account.current_balance or Decimal("0")
        ) + change_amount
        account.save(update_fields=["current_balance"])

    @staticmethod
    def save_bank_reconciliation(form, user=None) -> BankReconciliation:
        instance = form.save(commit=False)
        instance.difference_amount = (instance.bank_balance or Decimal("0")) - (
            instance.book_balance or Decimal("0")
        )
        instance.status = (
            "balanced" if instance.difference_amount == Decimal("0") else "difference"
        )
        instance.reconciled_by = getattr(user, "id", 0) or 0
        instance.reconciled_time = int(timezone.now().timestamp())
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_ledger_voucher(form, user=None) -> LedgerVoucher:
        instance = form.save(commit=False)
        if instance.status == "posted" and not instance.posted_time:
            instance.posted_by = getattr(user, "id", 0) or 0
            instance.posted_time = int(timezone.now().timestamp())
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_tax_record(form) -> TaxRecord:
        instance = form.save(commit=False)
        if not instance.tax_amount and instance.taxable_amount and instance.tax_rate:
            instance.tax_amount = (
                instance.taxable_amount * instance.tax_rate / Decimal("100")
            )
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_period_close(form, user=None) -> FinancialPeriodClose:
        instance = form.save(commit=False)
        instance.profit_amount = (instance.income_amount or Decimal("0")) - (
            instance.expense_amount or Decimal("0")
        )
        if instance.status == "closed" and not instance.closed_time:
            instance.closed_by = getattr(user, "id", 0) or 0
            instance.closed_time = int(timezone.now().timestamp())
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_financial_report(form, user=None) -> FinancialReport:
        instance = form.save(commit=False)
        instance.total_equity = (instance.total_assets or Decimal("0")) - (
            instance.total_liabilities or Decimal("0")
        )
        instance.profit_amount = (instance.revenue_amount or Decimal("0")) - (
            instance.cost_amount or Decimal("0")
        )
        if instance.status in ["generated", "approved"] and not instance.generated_time:
            instance.generated_by = getattr(user, "id", 0) or 0
            instance.generated_time = int(timezone.now().timestamp())
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance

    @staticmethod
    def save_expense_accrual(form, user=None) -> ExpenseAccrual:
        instance = form.save(commit=False)
        if instance.status == "accrued" and not instance.accrued_time:
            instance.accrued_by = getattr(user, "id", 0) or 0
            instance.accrued_time = int(timezone.now().timestamp())
        if not instance.create_time:
            instance.create_time = int(timezone.now().timestamp())
        instance.save()
        return instance


class FinanceStatisticsService:
    """财务统计服务类"""

    @staticmethod
    def get_dashboard_statistics() -> Dict:
        today = timezone.now().date()
        month_start = today.replace(day=1)
        month_start_dt = timezone.datetime.combine(month_start, timezone.datetime.min.time())
        month_start_ts = int(month_start_dt.timestamp())

        # ---- 本月统计（带月度过滤） ----
        expense_stats = ExpenseService.get_expense_statistics(start_ts=month_start_ts)
        invoice_stats = InvoiceService.get_invoice_statistics(start_ts=month_start_ts)
        income_stats = IncomeService.get_income_statistics(start_date=month_start_dt)
        payment_stats = PaymentService.get_payment_statistics(start_date=month_start_dt)

        # 本月订单财务统计
        month_order_qs = OrderFinanceRecord.objects.filter(create_time__gte=month_start_ts)
        month_order_stats = month_order_qs.aggregate(
            total_count=Count("id"),
            total_amount=Sum("total_amount"),
            paid_amount=Sum("paid_amount"),
        )
        month_order_total = month_order_stats["total_amount"] or Decimal("0")
        month_order_paid = month_order_stats["paid_amount"] or Decimal("0")

        # 本月应收统计
        month_receivable_qs = AccountsReceivable.objects.filter(create_time__gte=month_start_ts)
        month_receivable_stats = month_receivable_qs.aggregate(
            total_count=Count("id"),
            total_amount=Sum("amount"),
            received_amount=Sum("received_amount"),
        )

        # 本月应付统计
        month_payable_qs = AccountsPayable.objects.filter(create_time__gte=month_start_ts)
        month_payable_stats = month_payable_qs.aggregate(
            total_count=Count("id"),
            total_amount=Sum("amount"),
            paid_amount=Sum("paid_amount"),
        )

        # 本月银行流水统计
        month_bank_qs = BankTransaction.objects.filter(transaction_date__gte=month_start)
        month_bank_stats = month_bank_qs.aggregate(
            total_count=Count("id"), total_amount=Sum("amount")
        )

        # 本月凭证统计
        month_voucher_qs = LedgerVoucher.objects.filter(create_time__gte=month_start_ts)
        month_voucher_stats = month_voucher_qs.aggregate(
            total_count=Count("id"),
            debit_amount=Sum("debit_amount"),
            credit_amount=Sum("credit_amount"),
        )

        # 本月税务统计
        month_tax_qs = TaxRecord.objects.filter(create_time__gte=month_start_ts)
        month_tax_stats = month_tax_qs.aggregate(
            total_count=Count("id"), total_amount=Sum("tax_amount")
        )

        # 本月费用分配统计
        month_allocation_qs = CostAllocation.objects.filter(create_time__gte=month_start_ts)
        month_allocation_stats = month_allocation_qs.aggregate(
            total_count=Count("id"), total_amount=Sum("total_amount")
        )

        # 本月预提统计
        month_accrual_qs = ExpenseAccrual.objects.filter(create_time__gte=month_start_ts)
        month_accrual_stats = month_accrual_qs.aggregate(
            total_count=Count("id"), total_amount=Sum("amount")
        )

        # 本月现金流计划统计
        month_cash_flow_qs = CashFlowPlan.objects.filter(create_time__gte=month_start_ts)
        month_cash_flow_stats = month_cash_flow_qs.aggregate(
            total_count=Count("id"),
            expected_amount=Sum("expected_amount"),
            actual_amount=Sum("actual_amount"),
        )

        # 本月凭证行统计
        month_voucher_line_qs = LedgerVoucherLine.objects.filter(create_time__gte=month_start_ts)
        month_voucher_line_stats = month_voucher_line_qs.aggregate(
            total_count=Count("id"),
            debit_amount=Sum("debit_amount"),
            credit_amount=Sum("credit_amount"),
        )

        # ---- 累计统计（全量，适合账号/资产/预算等基础数据） ----
        account_stats = FinanceAccount.objects.aggregate(
            total_count=Count("id"), total_balance=Sum("current_balance")
        )
        budget_stats = FinanceBudget.objects.aggregate(
            total_count=Count("id"),
            total_amount=Sum("budget_amount"),
            used_amount=Sum("used_amount"),
        )
        asset_stats = FixedAsset.objects.aggregate(
            total_count=Count("id"),
            original_value=Sum("asset__purchase_price"),
            accumulated_depreciation=Sum("accumulated_depreciation"),
        )
        report_stats = FinancialReport.objects.aggregate(total_count=Count("id"))
        ratio_stats = FinancialRatio.objects.aggregate(total_count=Count("id"))
        subject_stats = ChartOfAccount.objects.aggregate(total_count=Count("id"))

        # ---- 计算派生值 ----
        asset_original = asset_stats["original_value"] or Decimal("0")
        asset_depreciation = asset_stats["accumulated_depreciation"] or Decimal("0")
        asset_net_value = max(asset_original - asset_depreciation, Decimal("0"))
        budget_total = budget_stats["total_amount"] or Decimal("0")
        budget_used = budget_stats["used_amount"] or Decimal("0")
        receivable_monthly_total = month_receivable_stats["total_amount"] or Decimal("0")
        receivable_monthly_received = month_receivable_stats["received_amount"] or Decimal("0")
        payable_monthly_total = month_payable_stats["total_amount"] or Decimal("0")
        payable_monthly_paid = month_payable_stats["paid_amount"] or Decimal("0")
        today_date = timezone.now().date()

        # 预算预警计数
        budget_warning_count = 0
        for budget in FinanceBudget.objects.filter(status="active"):
            if budget.usage_rate >= budget.warning_rate:
                budget_warning_count += 1

        return {
            # 统计期间信息
            "period": {
                "type": "monthly",
                "start": month_start.isoformat(),
                "end": today.isoformat(),
            },
            # 本月统计
            "expense_stats": expense_stats,
            "invoice_stats": invoice_stats,
            "income_stats": income_stats,
            "payment_stats": payment_stats,
            "order_stats": {
                "total_count": month_order_stats["total_count"] or 0,
                "total_amount": float(month_order_total),
                "paid_amount": float(month_order_paid),
                "unpaid_amount": float(
                    max(month_order_total - month_order_paid, Decimal("0"))
                ),
                "pending_count": month_order_qs.filter(payment_status="pending").count(),
                "overdue_count": month_order_qs.filter(payment_status="overdue").count(),
            },
            "receivable_stats": {
                "total_count": month_receivable_stats["total_count"] or 0,
                "total_amount": float(receivable_monthly_total),
                "received_amount": float(receivable_monthly_received),
                "remaining_amount": float(
                    max(receivable_monthly_total - receivable_monthly_received, Decimal("0"))
                ),
                "overdue_count": month_receivable_qs.filter(status="overdue").count(),
            },
            "payable_stats": {
                "total_count": month_payable_stats["total_count"] or 0,
                "total_amount": float(payable_monthly_total),
                "paid_amount": float(payable_monthly_paid),
                "remaining_amount": float(
                    max(payable_monthly_total - payable_monthly_paid, Decimal("0"))
                ),
                "overdue_count": month_payable_qs.filter(status="overdue").count(),
            },
            "bank_stats": {
                "total_count": month_bank_stats["total_count"] or 0,
                "total_amount": float(month_bank_stats["total_amount"] or Decimal("0")),
                "unmatched_count": month_bank_qs.filter(match_status="unmatched").count(),
                "difference_count": BankReconciliation.objects.filter(
                    status="difference"
                ).count(),
            },
            "voucher_stats": {
                "total_count": month_voucher_stats["total_count"] or 0,
                "debit_amount": float(month_voucher_stats["debit_amount"] or Decimal("0")),
                "credit_amount": float(month_voucher_stats["credit_amount"] or Decimal("0")),
                "draft_count": month_voucher_qs.filter(status="draft").count(),
                "posted_count": month_voucher_qs.filter(status="posted").count(),
            },
            "tax_stats": {
                "total_count": month_tax_stats["total_count"] or 0,
                "total_amount": float(month_tax_stats["total_amount"] or Decimal("0")),
                "pending_count": month_tax_qs.filter(status="draft").count(),
                "overdue_count": month_tax_qs.filter(status="overdue").count(),
            },
            "allocation_stats": {
                "total_count": month_allocation_stats["total_count"] or 0,
                "total_amount": float(month_allocation_stats["total_amount"] or Decimal("0")),
                "draft_count": month_allocation_qs.filter(status="draft").count(),
            },
            "accrual_stats": {
                "total_count": month_accrual_stats["total_count"] or 0,
                "total_amount": float(month_accrual_stats["total_amount"] or Decimal("0")),
                "draft_count": month_accrual_qs.filter(status="draft").count(),
                "accrued_count": month_accrual_qs.filter(status="accrued").count(),
            },
            "cash_flow_stats": {
                "total_count": month_cash_flow_stats["total_count"] or 0,
                "expected_amount": float(
                    month_cash_flow_stats["expected_amount"] or Decimal("0")
                ),
                "actual_amount": float(
                    month_cash_flow_stats["actual_amount"] or Decimal("0")
                ),
                "planned_count": month_cash_flow_qs.filter(status="planned").count(),
                "overdue_count": month_cash_flow_qs.filter(
                    status="planned", expected_date__lt=today_date
                ).count(),
            },
            "voucher_line_stats": {
                "total_count": month_voucher_line_stats["total_count"] or 0,
                "debit_amount": float(
                    month_voucher_line_stats["debit_amount"] or Decimal("0")
                ),
                "credit_amount": float(
                    month_voucher_line_stats["credit_amount"] or Decimal("0")
                ),
            },
            # 待处理统计（全量）
            "pending": {
                "expenses": Expense.objects.filter(
                    check_status=FinanceStatus.EXPENSE_CHECK_PENDING
                ).count(),
                "expense_payments": Expense.objects.filter(
                    check_status=FinanceStatus.EXPENSE_CHECK_APPROVED,
                    pay_status=FinanceStatus.PAY_STATUS_PENDING,
                ).count(),
                "invoices": Invoice.objects.filter(
                    open_status=FinanceStatus.INVOICE_OPEN_STATUS_NOT
                ).count(),
                "requests": InvoiceRequest.objects.filter(status="pending").count(),
            },
            # 累计统计（基础数据，适合账号/资产/预算/报表等）
            "account_stats": {
                "total_count": account_stats["total_count"] or 0,
                "active_count": FinanceAccount.objects.filter(status="active").count(),
                "total_balance": float(account_stats["total_balance"] or Decimal("0")),
            },
            "budget_stats": {
                "total_count": budget_stats["total_count"] or 0,
                "total_amount": float(budget_total),
                "used_amount": float(budget_used),
                "remaining_amount": float(
                    max(budget_total - budget_used, Decimal("0"))
                ),
                "warning_count": budget_warning_count,
            },
            "asset_stats": {
                "total_count": asset_stats["total_count"] or 0,
                "original_value": float(asset_original),
                "accumulated_depreciation": float(asset_depreciation),
                "net_value": float(asset_net_value),
                "active_count": FixedAsset.objects.filter(status="active").count(),
            },
            "period_close_stats": {
                "open_count": FinancialPeriodClose.objects.exclude(
                    status="closed"
                ).count(),
                "closed_count": FinancialPeriodClose.objects.filter(
                    status="closed"
                ).count(),
            },
            "report_stats": {
                "total_count": report_stats["total_count"] or 0,
                "draft_count": FinancialReport.objects.filter(status="draft").count(),
                "approved_count": FinancialReport.objects.filter(
                    status="approved"
                ).count(),
            },
            "ratio_stats": {
                "total_count": ratio_stats["total_count"] or 0,
                "warning_count": FinancialRatio.objects.filter(
                    status="warning"
                ).count(),
                "risk_count": FinancialRatio.objects.filter(status="risk").count(),
            },
            "subject_stats": {
                "total_count": subject_stats["total_count"] or 0,
                "active_count": ChartOfAccount.objects.filter(status="active").count(),
            },
            # 风险统计（全量）
            "risk_stats": {
                "overdue_receivables": AccountsReceivable.objects.filter(
                    due_date__lt=today_date
                )
                .exclude(status__in=["settled", "bad_debt"])
                .count(),
                "overdue_payables": AccountsPayable.objects.filter(
                    due_date__lt=today_date
                )
                .exclude(status="settled")
                .count(),
                "bank_differences": BankReconciliation.objects.filter(
                    status="difference"
                ).count(),
                "unposted_vouchers": LedgerVoucher.objects.filter(
                    status="draft"
                ).count(),
                "overdue_taxes": TaxRecord.objects.filter(status="overdue").count(),
                "open_periods": FinancialPeriodClose.objects.exclude(
                    status="closed"
                ).count(),
                "draft_reports": FinancialReport.objects.filter(status="draft").count(),
                "overdue_cash_plans": CashFlowPlan.objects.filter(
                    status="planned", expected_date__lt=today_date
                ).count(),
                "risk_ratios": FinancialRatio.objects.filter(status="risk").count(),
            },
        }

    @staticmethod
    def get_monthly_trend(months: int = 12) -> List[Dict]:
        today = timezone.now().date().replace(day=1)
        trends = []
        from dateutil.relativedelta import relativedelta

        for i in range(months - 1, -1, -1):
            month_start = today - relativedelta(months=i)
            month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
            start_dt = timezone.datetime.combine(month_start, timezone.datetime.min.time())
            end_dt = timezone.datetime.combine(month_end, timezone.datetime.max.time())

            start_ts = int(start_dt.timestamp())
            end_ts = int(end_dt.timestamp())

            expense_s = ExpenseService.get_expense_statistics(start_ts, end_ts)
            income_s = IncomeService.get_income_statistics(start_dt, end_dt)
            invoice_s = InvoiceService.get_invoice_statistics(start_ts, end_ts)
            payment_s = PaymentService.get_payment_statistics(start_dt, end_dt)

            # 月度订单财务统计
            month_orders = OrderFinanceRecord.objects.filter(
                create_time__gte=start_ts, create_time__lte=end_ts
            )
            order_month_total = month_orders.aggregate(
                total=Sum("total_amount"), paid=Sum("paid_amount")
            )

            # 月度应收应付统计
            month_receivable = AccountsReceivable.objects.filter(
                create_time__gte=start_ts, create_time__lte=end_ts
            ).aggregate(total=Sum("amount"), received=Sum("received_amount"))
            month_payable = AccountsPayable.objects.filter(
                create_time__gte=start_ts, create_time__lte=end_ts
            ).aggregate(total=Sum("amount"), paid=Sum("paid_amount"))

            trends.append(
                {
                    "month": month_start.strftime("%Y-%m"),
                    "year_month": month_start.strftime("%Y-%m"),
                    "expense_amount": expense_s["total_amount"],
                    "expense_count": expense_s["total_count"],
                    "income_amount": income_s["total_amount"],
                    "income_count": income_s["total_count"],
                    "invoice_amount": invoice_s["total_amount"],
                    "invoice_count": invoice_s["total_count"],
                    "payment_amount": payment_s["total_amount"],
                    "payment_count": payment_s["total_count"],
                    "order_amount": float(order_month_total["total"] or Decimal("0")),
                    "order_paid": float(order_month_total["paid"] or Decimal("0")),
                    "receivable_amount": float(month_receivable["total"] or Decimal("0")),
                    "receivable_received": float(month_receivable["received"] or Decimal("0")),
                    "payable_amount": float(month_payable["total"] or Decimal("0")),
                    "payable_paid": float(month_payable["paid"] or Decimal("0")),
                }
            )

        return trends
