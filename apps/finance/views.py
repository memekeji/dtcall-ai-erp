"""
财务管理模块视图
只使用有数据库表的模型
"""

from django.shortcuts import render, get_object_or_404
from django.views.generic import CreateView, UpdateView
from django.views import View
from django.http import JsonResponse, HttpResponseRedirect, Http404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
import json
import logging
import time

from .forms import (
    AccountsPayableForm,
    AccountsReceivableForm,
    BankReconciliationForm,
    BankTransactionForm,
    CostAllocationForm,
    FinanceAccountForm,
    FinanceBudgetForm,
    FinancialPeriodCloseForm,
    FinancialReportForm,
    ChartOfAccountForm,
    LedgerVoucherLineForm,
    CashFlowPlanForm,
    FinancialRatioForm,
    ExpenseAccrualForm,
    FixedAssetForm,
    IncomeForm,
    InvoiceForm,
    LedgerVoucherForm,
    PaymentForm,
    TaxRecordForm,
)
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
    LedgerVoucher,
    OrderFinanceRecord,
    Payment,
    TaxRecord,
)
from .services import (
    AdvancedFinanceService,
    FinanceStatisticsService,
    IncomeService,
    PaymentService,
)
from apps.common.utils import timestamp_to_date, safe_int, build_error_response
from apps.common.constants import ApiResponseCode, CommonConstant
from apps.customer.models import CustomerOrder

logger = logging.getLogger(__name__)


class FinancePermissionMixin(PermissionRequiredMixin):
    """财务模块权限混合类"""

    permission_required = []

    def has_permission(self):
        if not self.permission_required:
            return True
        perms = (
            self.permission_required
            if isinstance(self.permission_required, list)
            else [self.permission_required]
        )
        return self.request.user.has_perms(perms)


class FinanceIndexView(LoginRequiredMixin, View):
    """财务模块首页"""

    login_url = "/user/login/"
    redirect_field_name = "next"

    def get(self, request):
        return render(request, "finance/index.html")


class ExpenseListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """报销列表"""

    login_url = "/user/login/"
    permission_required = "finance.view_expense"

    def get(self, request):
        if "datalist" in request.path:
            return self.get_datalist(request)
        return render(request, "finance/expense_list.html")

    def get_datalist(self, request):
        try:
            tab = request.GET.get("tab", "0")
            page = safe_int(request.GET.get("page"), 1)
            limit = safe_int(request.GET.get("limit"), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = Expense.objects.all().order_by("-create_time")
            uid = request.user.id

            if tab == "1":
                queryset = queryset.filter(admin_id=uid)
            elif tab == "2":
                queryset = queryset.filter(
                    check_status=FinanceStatus.EXPENSE_CHECK_PENDING
                ).filter(Q(check_uids__contains=str(uid)) | Q(check_last_uid=str(uid)))

            search_code = request.GET.get("code")
            if search_code:
                queryset = queryset.filter(code__icontains=search_code)

            diff_time = request.GET.get("diff_time")
            if diff_time and "~" in diff_time:
                start, end = diff_time.split("~")
                start_ts = int(time.mktime(time.strptime(start.strip(), "%Y-%m-%d")))
                end_ts = (
                    int(time.mktime(time.strptime(end.strip(), "%Y-%m-%d"))) + 86400
                )
                queryset = queryset.filter(expense_time__range=[start_ts, end_ts])

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = []
            for expense in page_obj:
                expense_date = (
                    timestamp_to_date(expense.expense_time)
                    if expense.expense_time
                    else None
                )
                data.append(
                    {
                        "id": expense.id,
                        "code": expense.code,
                        "cost": float(expense.cost),
                        "check_status": expense.check_status,
                        "check_status_display": expense.get_check_status_display(),
                        "pay_status": expense.pay_status,
                        "pay_status_display": expense.get_pay_status_display(),
                        "expense_time": expense.expense_time,
                        "expense_date": (
                            expense_date.strftime("%Y-%m-%d") if expense_date else ""
                        ),
                        "admin_id": expense.admin_id,
                        "did": expense.did,
                        "project_id": expense.project_id,
                        "create_time": expense.create_time,
                    }
                )

            return JsonResponse(
                {
                    "code": ApiResponseCode.CODE_SUCCESS,
                    "msg": "",
                    "count": paginator.count,
                    "data": data,
                }
            )
        except Exception as e:
            logger.error(f"获取报销列表失败: {str(e)}", exc_info=True)
            return build_error_response(f"获取数据失败: {str(e)}")


class ReimbursementListView(LoginRequiredMixin, View):
    """报销管理（旧路由兼容）"""

    login_url = "/user/login/"

    def get(self, request):
        return render(request, "finance/expense_list.html")


class ExpenseCreateView(LoginRequiredMixin, View):
    """创建报销"""

    login_url = "/user/login/"

    def get(self, request):
        return render(request, "finance/expense_form.html")

    def post(self, request):
        try:
            data = request.POST.dict()
            data["admin_id"] = request.user.id

            # 生成报销编码
            from django.utils import timezone
            import random

            code = f'BX{timezone.now().strftime("%Y%m%d%H%M%S")}{random.randint(1000, 9999)}'
            data["code"] = data.get("code", code)

            expense = Expense.objects.create(**data)

            return JsonResponse(
                {
                    "code": ApiResponseCode.CODE_SUCCESS,
                    "msg": "创建成功",
                    "data": {"id": expense.id},
                }
            )
        except Exception as e:
            logger.error(f"创建报销失败: {str(e)}", exc_info=True)
            return build_error_response(f"创建失败: {str(e)}")


class ExpenseSubmitView(LoginRequiredMixin, FinancePermissionMixin, View):
    """提交报销审批"""

    login_url = "/user/login/"
    permission_required = "finance.submit_expense"

    def post(self, request):
        try:
            data = json.loads(request.body)
            expense_id = data.get("expense_id")

            if not expense_id:
                return build_error_response("缺少报销ID")

            expense = get_object_or_404(Expense, id=expense_id)

            if expense.check_status not in [0, 3, 4]:
                return build_error_response("当前状态不允许提交")

            expense.check_status = FinanceStatus.EXPENSE_CHECK_PROCESSING
            expense.save()

            return JsonResponse(
                {"code": ApiResponseCode.CODE_SUCCESS, "msg": "提交成功"}
            )
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except Exception as e:
            logger.error(f"提交报销失败: {str(e)}", exc_info=True)
            return build_error_response(f"提交失败: {str(e)}")


class ExpenseApproveView(LoginRequiredMixin, FinancePermissionMixin, View):
    """审批报销"""

    login_url = "/user/login/"
    permission_required = "finance.approve_expense"

    def post(self, request):
        try:
            data = json.loads(request.body)
            expense_id = data.get("expense_id")
            action = data.get("action")
            data.get("notes", "")

            if not expense_id or not action:
                return build_error_response("参数不完整")

            expense = get_object_or_404(Expense, id=expense_id)

            if expense.check_status != FinanceStatus.EXPENSE_CHECK_PROCESSING:
                return build_error_response("当前状态不允许审批")

            if action == "approved":
                expense.check_status = FinanceStatus.EXPENSE_CHECK_APPROVED
                expense.check_time = int(time.time())
            else:
                expense.check_status = FinanceStatus.EXPENSE_CHECK_REJECTED

            expense.check_history_uids += f",{request.user.id}"
            expense.save()

            return JsonResponse(
                {"code": ApiResponseCode.CODE_SUCCESS, "msg": "审批操作成功"}
            )
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except Exception as e:
            logger.error(f"审批报销失败: {str(e)}", exc_info=True)
            return build_error_response(f"审批失败: {str(e)}")


class InvoiceListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """发票列表"""

    login_url = "/user/login/"
    permission_required = "finance.view_invoice"

    def get(self, request):
        if "datalist" in request.path:
            return self.get_datalist(request)
        return render(request, "finance/invoice_list.html")

    def get_datalist(self, request):
        try:
            page = safe_int(request.GET.get("page"), 1)
            limit = safe_int(request.GET.get("limit"), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = Invoice.objects.all().order_by("-create_time")

            search_code = request.GET.get("code")
            if search_code:
                queryset = queryset.filter(code__icontains=search_code)

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = []
            for invoice in page_obj:
                data.append(
                    {
                        "id": invoice.id,
                        "code": invoice.code,
                        "amount": float(invoice.amount),
                        "invoice_type": invoice.invoice_type,
                        "invoice_type_display": invoice.get_invoice_type_display(),
                        "open_status": invoice.open_status,
                        "open_status_display": invoice.get_open_status_display(),
                        "enter_amount": float(invoice.enter_amount),
                        "enter_status": invoice.enter_status,
                        "enter_status_display": invoice.get_enter_status_display(),
                        "invoice_title": invoice.invoice_title,
                        "customer_id": invoice.customer_id,
                        "create_time": invoice.create_time,
                    }
                )

            return JsonResponse(
                {
                    "code": ApiResponseCode.CODE_SUCCESS,
                    "msg": "",
                    "count": paginator.count,
                    "data": data,
                }
            )
        except Exception as e:
            logger.error(f"获取发票列表失败: {str(e)}", exc_info=True)
            return build_error_response(f"获取数据失败: {str(e)}")


class ReceiveInvoiceListView(LoginRequiredMixin, View):
    """收票列表"""

    login_url = "/user/login/"

    def get(self, request):
        return render(request, "finance/receiveinvoice_list.html")


class InvoiceCreateView(LoginRequiredMixin, FinancePermissionMixin, CreateView):
    """创建发票"""

    login_url = "/user/login/"
    permission_required = "finance.add_invoice"
    model = Invoice
    form_class = InvoiceForm
    template_name = "finance/invoice_form.html"
    success_url = reverse_lazy("finance:invoice_list")


class InvoiceUpdateView(LoginRequiredMixin, FinancePermissionMixin, UpdateView):
    """更新发票"""

    login_url = "/user/login/"
    permission_required = "finance.change_invoice"
    model = Invoice
    form_class = InvoiceForm
    template_name = "finance/invoice_form.html"
    success_url = reverse_lazy("finance:invoice_list")


class IncomeListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """回款列表"""

    login_url = "/user/login/"
    permission_required = "finance.view_income"

    def get(self, request):
        if "datalist" in request.path:
            return self.get_datalist(request)
        return render(request, "finance/income_list.html")

    def get_datalist(self, request):
        try:
            page = safe_int(request.GET.get("page"), 1)
            limit = safe_int(request.GET.get("limit"), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = Income.objects.all().order_by("-income_date")

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = []
            for income in page_obj:
                invoice = Invoice.objects.filter(id=income.invoice_id).first()
                data.append(
                    {
                        "id": income.id,
                        "invoice_id": income.invoice_id,
                        "invoice_code": invoice.code if invoice else "",
                        "invoice_title": invoice.invoice_title if invoice else "",
                        "amount": float(income.amount),
                        "income_date": (
                            income.income_date.strftime("%Y-%m-%d %H:%M:%S")
                            if income.income_date
                            else ""
                        ),
                        "remark": income.remark,
                        "create_time": income.create_time,
                    }
                )

            return JsonResponse(
                {
                    "code": ApiResponseCode.CODE_SUCCESS,
                    "msg": "",
                    "count": paginator.count,
                    "data": data,
                }
            )
        except Exception as e:
            logger.error(f"获取回款列表失败: {str(e)}", exc_info=True)
            return build_error_response(f"获取数据失败: {str(e)}")


class IncomeCreateView(LoginRequiredMixin, FinancePermissionMixin, CreateView):
    """创建回款"""

    login_url = "/user/login/"
    permission_required = "finance.add_income"
    model = Income
    form_class = IncomeForm
    template_name = "finance/income_form.html"
    success_url = reverse_lazy("finance:income_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invoices"] = Invoice.objects.exclude(
            enter_status=FinanceStatus.ENTER_STATUS_FULL
        ).order_by("-create_time")[:200]
        return context

    def form_valid(self, form):
        self.object = IncomeService.create_income(form.cleaned_data)
        return HttpResponseRedirect(self.get_success_url())


class PaymentListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """付款列表"""

    login_url = "/user/login/"
    permission_required = "finance.view_payment"

    def get(self, request):
        if "datalist" in request.path:
            return self.get_datalist(request)
        return render(request, "finance/payment_list.html")

    def get_datalist(self, request):
        try:
            page = safe_int(request.GET.get("page"), 1)
            limit = safe_int(request.GET.get("limit"), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = Payment.objects.all().order_by("-payment_date")

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = []
            for payment in page_obj:
                expense = Expense.objects.filter(id=payment.expense_id).first()
                data.append(
                    {
                        "id": payment.id,
                        "expense_id": payment.expense_id,
                        "expense_code": expense.code if expense else "",
                        "amount": float(payment.amount),
                        "payment_date": (
                            payment.payment_date.strftime("%Y-%m-%d %H:%M:%S")
                            if payment.payment_date
                            else ""
                        ),
                        "remark": payment.remark,
                        "create_time": payment.create_time,
                    }
                )

            return JsonResponse(
                {
                    "code": ApiResponseCode.CODE_SUCCESS,
                    "msg": "",
                    "count": paginator.count,
                    "data": data,
                }
            )
        except Exception as e:
            logger.error(f"获取付款列表失败: {str(e)}", exc_info=True)
            return build_error_response(f"获取数据失败: {str(e)}")


class PaymentCreateView(LoginRequiredMixin, FinancePermissionMixin, CreateView):
    """创建付款"""

    login_url = "/user/login/"
    permission_required = "finance.add_payment"
    model = Payment
    form_class = PaymentForm
    template_name = "finance/payment_form.html"
    success_url = reverse_lazy("finance:payment_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["expenses"] = Expense.objects.filter(
            check_status=FinanceStatus.EXPENSE_CHECK_APPROVED,
            pay_status=FinanceStatus.PAY_STATUS_PENDING,
        ).order_by("-create_time")[:200]
        return context

    def form_valid(self, form):
        try:
            self.object = PaymentService.create_payment(
                form.cleaned_data, self.request.user
            )
            return HttpResponseRedirect(self.get_success_url())
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)


class PaymentReceiveListView(LoginRequiredMixin, View):
    """收付款列表"""

    login_url = "/user/login/"

    def get(self, request):
        return render(request, "finance/paymentreceive_list.html")


class PaymentReceiveCreateView(IncomeCreateView):
    """创建收款记录（旧路由兼容）"""

    success_url = reverse_lazy("finance:paymentreceive_list")


ADVANCED_FINANCE_CONFIG = {
    "account": {
        "title": "资金账户",
        "model": FinanceAccount,
        "form": FinanceAccountForm,
        "fields": [
            "id",
            "name",
            "account_type_display",
            "bank_name",
            "account_no",
            "currency",
            "opening_balance",
            "current_balance",
            "status_display",
            "create_time",
        ],
        "search_fields": ["name", "bank_name", "account_no"],
        "permission": "finance.view_financeaccount",
        "add_permission": "finance.add_financeaccount",
        "change_permission": "finance.change_financeaccount",
        "delete_permission": "finance.delete_financeaccount",
        "order_by": "-create_time",
    },
    "budget": {
        "title": "预算管理",
        "model": FinanceBudget,
        "form": FinanceBudgetForm,
        "fields": [
            "id",
            "name",
            "department_id",
            "project_id",
            "period_type_display",
            "budget_amount",
            "used_amount",
            "remaining_amount",
            "usage_rate",
            "status_display",
            "start_date",
            "end_date",
        ],
        "search_fields": ["name"],
        "permission": "finance.view_financebudget",
        "add_permission": "finance.add_financebudget",
        "change_permission": "finance.change_financebudget",
        "delete_permission": "finance.delete_financebudget",
        "order_by": "-create_time",
    },
    "receivable": {
        "title": "应收账款",
        "model": AccountsReceivable,
        "form": AccountsReceivableForm,
        "fields": [
            "id",
            "code",
            "customer_id",
            "order_id",
            "invoice_id",
            "amount",
            "received_amount",
            "remaining_amount",
            "due_date",
            "status_display",
            "create_time",
        ],
        "search_fields": ["code"],
        "permission": "finance.view_accountsreceivable",
        "add_permission": "finance.add_accountsreceivable",
        "change_permission": "finance.change_accountsreceivable",
        "delete_permission": "finance.delete_accountsreceivable",
        "order_by": "-create_time",
    },
    "payable": {
        "title": "应付账款",
        "model": AccountsPayable,
        "form": AccountsPayableForm,
        "fields": [
            "id",
            "code",
            "supplier_id",
            "expense_id",
            "amount",
            "paid_amount",
            "remaining_amount",
            "due_date",
            "status_display",
            "create_time",
        ],
        "search_fields": ["code"],
        "permission": "finance.view_accountspayable",
        "add_permission": "finance.add_accountspayable",
        "change_permission": "finance.change_accountspayable",
        "delete_permission": "finance.delete_accountspayable",
        "order_by": "-create_time",
    },
    "bank-transaction": {
        "title": "银行流水",
        "model": BankTransaction,
        "form": BankTransactionForm,
        "fields": [
            "id",
            "account_name",
            "transaction_date",
            "direction_display",
            "amount",
            "counterparty",
            "transaction_no",
            "purpose",
            "match_status_display",
            "related_type",
            "related_id",
        ],
        "search_fields": ["counterparty", "transaction_no", "purpose"],
        "permission": "finance.view_banktransaction",
        "add_permission": "finance.add_banktransaction",
        "change_permission": "finance.change_banktransaction",
        "delete_permission": "finance.delete_banktransaction",
        "order_by": "-transaction_date",
    },
    "bank-reconciliation": {
        "title": "银行对账",
        "model": BankReconciliation,
        "form": BankReconciliationForm,
        "fields": [
            "id",
            "account_name",
            "period",
            "book_balance",
            "bank_balance",
            "difference_amount",
            "status_display",
            "reconciled_by",
            "reconciled_time",
            "create_time",
        ],
        "search_fields": ["period"],
        "permission": "finance.view_bankreconciliation",
        "add_permission": "finance.add_bankreconciliation",
        "change_permission": "finance.change_bankreconciliation",
        "delete_permission": "finance.delete_bankreconciliation",
        "order_by": "-create_time",
    },
    "ledger-voucher": {
        "title": "总账凭证",
        "model": LedgerVoucher,
        "form": LedgerVoucherForm,
        "fields": [
            "id",
            "voucher_no",
            "voucher_date",
            "summary",
            "debit_amount",
            "credit_amount",
            "source_type",
            "source_id",
            "status_display",
            "posted_by",
            "posted_time",
        ],
        "search_fields": ["voucher_no", "summary"],
        "permission": "finance.view_ledgervoucher",
        "add_permission": "finance.add_ledgervoucher",
        "change_permission": "finance.change_ledgervoucher",
        "delete_permission": "finance.delete_ledgervoucher",
        "order_by": "-voucher_date",
    },
    "chart-account": {
        "title": "会计科目",
        "model": ChartOfAccount,
        "form": ChartOfAccountForm,
        "fields": [
            "id",
            "code",
            "name",
            "account_type_display",
            "level",
            "is_leaf",
            "balance_direction_display",
            "status_display",
            "create_time",
        ],
        "search_fields": ["code", "name"],
        "permission": "finance.view_chartofaccount",
        "add_permission": "finance.add_chartofaccount",
        "change_permission": "finance.change_chartofaccount",
        "delete_permission": "finance.delete_chartofaccount",
        "order_by": "code",
    },
    "voucher-line": {
        "title": "凭证明细",
        "model": LedgerVoucherLine,
        "form": LedgerVoucherLineForm,
        "fields": [
            "id",
            "voucher_no",
            "account_code",
            "account_name",
            "summary",
            "debit_amount",
            "credit_amount",
            "auxiliary_type",
            "auxiliary_id",
            "create_time",
        ],
        "search_fields": [
            "voucher__voucher_no",
            "account__code",
            "account__name",
            "summary",
        ],
        "permission": "finance.view_ledgervoucherline",
        "add_permission": "finance.add_ledgervoucherline",
        "change_permission": "finance.change_ledgervoucherline",
        "delete_permission": "finance.delete_ledgervoucherline",
        "order_by": "-create_time",
    },
    "tax": {
        "title": "税务管理",
        "model": TaxRecord,
        "form": TaxRecordForm,
        "fields": [
            "id",
            "period",
            "tax_type_display",
            "taxable_amount",
            "tax_rate",
            "tax_amount",
            "due_date",
            "status_display",
            "create_time",
        ],
        "search_fields": ["period"],
        "permission": "finance.view_taxrecord",
        "add_permission": "finance.add_taxrecord",
        "change_permission": "finance.change_taxrecord",
        "delete_permission": "finance.delete_taxrecord",
        "order_by": "-create_time",
    },
    "fixed-asset": {
        "title": "固定资产财务档案",
        "model": FixedAsset,
        "form": FixedAssetForm,
        "fields": [
            "id",
            "asset_code",
            "name",
            "category",
            "original_value",
            "accumulated_depreciation",
            "net_value",
            "monthly_depreciation",
            "status_display",
            "create_time",
        ],
        "search_fields": [
            "asset__asset_number",
            "asset__name",
            "asset__category__name",
        ],
        "permission": "finance.view_fixedasset",
        "add_permission": "finance.add_fixedasset",
        "change_permission": "finance.change_fixedasset",
        "delete_permission": "finance.delete_fixedasset",
        "order_by": "-create_time",
    },
    "cost-allocation": {
        "title": "成本分摊",
        "model": CostAllocation,
        "form": CostAllocationForm,
        "fields": [
            "id",
            "allocation_no",
            "period",
            "source_type",
            "total_amount",
            "department_id",
            "project_id",
            "allocation_basis",
            "status_display",
            "create_time",
        ],
        "search_fields": ["allocation_no", "period", "allocation_basis"],
        "permission": "finance.view_costallocation",
        "add_permission": "finance.add_costallocation",
        "change_permission": "finance.change_costallocation",
        "delete_permission": "finance.delete_costallocation",
        "order_by": "-create_time",
    },
    "cash-flow-plan": {
        "title": "现金流计划",
        "model": CashFlowPlan,
        "form": CashFlowPlanForm,
        "fields": [
            "id",
            "plan_no",
            "flow_type_display",
            "category",
            "expected_date",
            "expected_amount",
            "actual_amount",
            "variance_amount",
            "account_name",
            "status_display",
        ],
        "search_fields": ["plan_no", "category", "account__name"],
        "permission": "finance.view_cashflowplan",
        "add_permission": "finance.add_cashflowplan",
        "change_permission": "finance.change_cashflowplan",
        "delete_permission": "finance.delete_cashflowplan",
        "order_by": "expected_date",
    },
    "financial-ratio": {
        "title": "财务指标",
        "model": FinancialRatio,
        "form": FinancialRatioForm,
        "fields": [
            "id",
            "period",
            "ratio_type_display",
            "name",
            "value",
            "target_value",
            "warning_value",
            "unit",
            "status_display",
        ],
        "search_fields": ["period", "name"],
        "permission": "finance.view_financialratio",
        "add_permission": "finance.add_financialratio",
        "change_permission": "finance.change_financialratio",
        "delete_permission": "finance.delete_financialratio",
        "order_by": "-period",
    },
    "expense-accrual": {
        "title": "费用计提",
        "model": ExpenseAccrual,
        "form": ExpenseAccrualForm,
        "fields": [
            "id",
            "accrual_no",
            "period",
            "expense_type",
            "amount",
            "department_id",
            "project_id",
            "status_display",
            "accrued_by",
            "accrued_time",
        ],
        "search_fields": ["accrual_no", "period", "expense_type"],
        "permission": "finance.view_expenseaccrual",
        "add_permission": "finance.add_expenseaccrual",
        "change_permission": "finance.change_expenseaccrual",
        "delete_permission": "finance.delete_expenseaccrual",
        "order_by": "-create_time",
    },
    "period-close": {
        "title": "期间结账",
        "model": FinancialPeriodClose,
        "form": FinancialPeriodCloseForm,
        "fields": [
            "id",
            "period",
            "income_amount",
            "expense_amount",
            "profit_amount",
            "status_display",
            "closed_by",
            "closed_time",
            "create_time",
        ],
        "search_fields": ["period"],
        "permission": "finance.view_financialperiodclose",
        "add_permission": "finance.add_financialperiodclose",
        "change_permission": "finance.change_financialperiodclose",
        "delete_permission": "finance.delete_financialperiodclose",
        "order_by": "-period",
    },
    "financial-report": {
        "title": "财务报表",
        "model": FinancialReport,
        "form": FinancialReportForm,
        "fields": [
            "id",
            "report_no",
            "report_type_display",
            "period",
            "total_assets",
            "total_liabilities",
            "total_equity",
            "revenue_amount",
            "cost_amount",
            "profit_amount",
            "status_display",
        ],
        "search_fields": ["report_no", "period"],
        "permission": "finance.view_financialreport",
        "add_permission": "finance.add_financialreport",
        "change_permission": "finance.change_financialreport",
        "delete_permission": "finance.delete_financialreport",
        "order_by": "-period",
    },
}


def get_advanced_config(module):
    try:
        return ADVANCED_FINANCE_CONFIG[module]
    except KeyError as exc:
        raise Http404("财务模块不存在") from exc


def format_advanced_value(obj, field):
    if field == "account_name":
        return (
            obj.account.name if getattr(obj, "account_id", None) and obj.account else ""
        )
    if field.endswith("_display"):
        display_method = f"get_{field[:-8]}_display"
        if hasattr(obj, display_method):
            return getattr(obj, display_method)()
    value = getattr(obj, field)
    if callable(value):
        value = value()
    if hasattr(value, "strftime"):
        return (
            value.strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(value, "hour")
            else value.strftime("%Y-%m-%d")
        )
    if hasattr(value, "quantize"):
        return float(value)
    return value


class AdvancedFinanceListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """专业财务扩展列表"""

    login_url = "/user/login/"

    def dispatch(self, request, *args, **kwargs):
        self.module = kwargs.get("module")
        self.config = get_advanced_config(self.module)
        self.permission_required = self.config["permission"]
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, module):
        if "datalist" in request.path:
            return self.get_datalist(request)
        return render(
            request,
            "finance/advanced_finance_list.html",
            {
                "module": module,
                "title": self.config["title"],
                "fields": self.config["fields"],
            },
        )

    def get_datalist(self, request):
        try:
            page = safe_int(request.GET.get("page"), 1)
            limit = safe_int(request.GET.get("limit"), CommonConstant.DEFAULT_PAGE_SIZE)
            keyword = request.GET.get("keyword", "").strip()
            queryset = (
                self.config["model"].objects.all().order_by(self.config["order_by"])
            )
            if keyword:
                query = Q()
                for field in self.config["search_fields"]:
                    query |= Q(**{f"{field}__icontains": keyword})
                queryset = queryset.filter(query)
            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)
            data = []
            for obj in page_obj:
                row = {
                    field: format_advanced_value(obj, field)
                    for field in self.config["fields"]
                }
                row["id"] = obj.id
                data.append(row)
            return JsonResponse(
                {
                    "code": ApiResponseCode.CODE_SUCCESS,
                    "msg": "",
                    "count": paginator.count,
                    "data": data,
                }
            )
        except Exception as e:
            logger.error(f"获取{self.config['title']}列表失败: {str(e)}", exc_info=True)
            return build_error_response(f"获取数据失败: {str(e)}")


class AdvancedFinanceCreateView(LoginRequiredMixin, FinancePermissionMixin, CreateView):
    """专业财务扩展创建"""

    login_url = "/user/login/"
    template_name = "finance/advanced_finance_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.module = kwargs.get("module")
        self.config = get_advanced_config(self.module)
        self.model = self.config["model"]
        self.form_class = self.config["form"]
        self.permission_required = self.config["add_permission"]
        self.success_url = reverse_lazy(
            "finance:advanced_finance_list", kwargs={"module": self.module}
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"module": self.module, "title": self.config["title"]})
        return context

    def form_valid(self, form):
        if self.module == "bank-transaction":
            self.object = AdvancedFinanceService.save_bank_transaction(form)
        elif self.module == "bank-reconciliation":
            self.object = AdvancedFinanceService.save_bank_reconciliation(
                form, self.request.user
            )
        elif self.module == "ledger-voucher":
            self.object = AdvancedFinanceService.save_ledger_voucher(
                form, self.request.user
            )
        elif self.module == "tax":
            self.object = AdvancedFinanceService.save_tax_record(form)
        elif self.module == "period-close":
            self.object = AdvancedFinanceService.save_period_close(
                form, self.request.user
            )
        elif self.module == "financial-report":
            self.object = AdvancedFinanceService.save_financial_report(
                form, self.request.user
            )
        elif self.module == "expense-accrual":
            self.object = AdvancedFinanceService.save_expense_accrual(
                form, self.request.user
            )
        else:
            self.object = form.save(commit=False)
            AdvancedFinanceService.save_with_create_time(self.object)
        return HttpResponseRedirect(self.get_success_url())


class AdvancedFinanceUpdateView(LoginRequiredMixin, FinancePermissionMixin, UpdateView):
    """专业财务扩展编辑"""

    login_url = "/user/login/"
    template_name = "finance/advanced_finance_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.module = kwargs.get("module")
        self.config = get_advanced_config(self.module)
        self.model = self.config["model"]
        self.form_class = self.config["form"]
        self.permission_required = self.config["change_permission"]
        self.success_url = reverse_lazy(
            "finance:advanced_finance_list", kwargs={"module": self.module}
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"module": self.module, "title": self.config["title"]})
        return context

    def form_valid(self, form):
        if self.module == "bank-transaction":
            self.object = AdvancedFinanceService.save_bank_transaction(form)
        elif self.module == "bank-reconciliation":
            self.object = AdvancedFinanceService.save_bank_reconciliation(
                form, self.request.user
            )
        elif self.module == "ledger-voucher":
            self.object = AdvancedFinanceService.save_ledger_voucher(
                form, self.request.user
            )
        elif self.module == "tax":
            self.object = AdvancedFinanceService.save_tax_record(form)
        elif self.module == "period-close":
            self.object = AdvancedFinanceService.save_period_close(
                form, self.request.user
            )
        elif self.module == "financial-report":
            self.object = AdvancedFinanceService.save_financial_report(
                form, self.request.user
            )
        elif self.module == "expense-accrual":
            self.object = AdvancedFinanceService.save_expense_accrual(
                form, self.request.user
            )
        else:
            self.object = form.save(commit=False)
            AdvancedFinanceService.save_with_create_time(self.object)
        return HttpResponseRedirect(self.get_success_url())


class AdvancedFinanceDeleteView(LoginRequiredMixin, FinancePermissionMixin, View):
    """专业财务扩展删除"""

    login_url = "/user/login/"

    def dispatch(self, request, *args, **kwargs):
        self.module = kwargs.get("module")
        self.config = get_advanced_config(self.module)
        self.permission_required = self.config["delete_permission"]
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, module):
        try:
            data = json.loads(request.body)
            obj_id = data.get("id")
            if not obj_id:
                return build_error_response("缺少ID参数")
            obj = get_object_or_404(self.config["model"], id=obj_id)
            if self.module == "bank-transaction":
                AdvancedFinanceService.delete_bank_transaction(obj)
            else:
                obj.delete()
            return JsonResponse(
                {"code": ApiResponseCode.CODE_SUCCESS, "msg": "删除成功"}
            )
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except Exception as e:
            logger.error(f"删除{self.config['title']}失败: {str(e)}", exc_info=True)
            return build_error_response(f"删除失败: {str(e)}")


class InvoiceRequestListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """开票申请列表"""

    login_url = "/user/login/"
    permission_required = "finance.view_invoicerequest"

    def get(self, request):
        if "datalist" in request.path:
            return self.get_datalist(request)
        return render(request, "finance/invoice_request_list.html")

    def get_datalist(self, request):
        try:
            tab = request.GET.get("tab", "0")
            page = safe_int(request.GET.get("page"), 1)
            limit = safe_int(request.GET.get("limit"), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = InvoiceRequest.objects.all().order_by("-create_time")
            uid = request.user.id

            if tab == "1":
                queryset = queryset.filter(applicant_id=uid)
            elif tab == "2":
                queryset = queryset.filter(status="pending")

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = []
            for req in page_obj:
                data.append(
                    {
                        "id": req.id,
                        "order_id": req.order_id,
                        "amount": float(req.amount),
                        "invoice_type": req.invoice_type,
                        "status": req.status,
                        "status_display": req.get_status_display(),
                        "applicant_id": req.applicant_id,
                        "create_time": req.create_time,
                    }
                )

            return JsonResponse(
                {
                    "code": ApiResponseCode.CODE_SUCCESS,
                    "msg": "",
                    "count": paginator.count,
                    "data": data,
                }
            )
        except Exception as e:
            logger.error(f"获取开票申请列表失败: {str(e)}", exc_info=True)
            return build_error_response(f"获取数据失败: {str(e)}")


class OrderFinanceRecordListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """订单财务记录列表"""

    login_url = "/user/login/"
    permission_required = "finance.view_orderfinancerecord"

    def get(self, request):
        if "datalist" in request.path:
            return self.get_datalist(request)
        return render(request, "finance/order_finance_list.html")

    def get_datalist(self, request):
        try:
            status = request.GET.get("status")
            page = safe_int(request.GET.get("page"), 1)
            limit = safe_int(request.GET.get("limit"), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = OrderFinanceRecord.objects.all().order_by("-create_time")

            if status:
                queryset = queryset.filter(payment_status=status)

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            order_ids = [record.order_id for record in page_obj if record.order_id]
            orders = CustomerOrder.objects.filter(id__in=order_ids).select_related("customer")
            order_map = {order.id: order for order in orders}

            data = []
            for record in page_obj:
                order = order_map.get(record.order_id)
                create_time = timestamp_to_date(record.create_time) if record.create_time else None
                data.append(
                    {
                        "id": record.id,
                        "order_id": record.order_id,
                        "order_number": order.order_number if order else f"订单{record.order_id}",
                        "customer_name": order.customer.name if order and order.customer_id else "",
                        "total_amount": float(record.total_amount),
                        "paid_amount": float(record.paid_amount),
                        "unpaid_amount": float(record.unpaid_amount),
                        "payment_status": record.payment_status,
                        "payment_status_display": record.get_payment_status_display(),
                        "due_date": (
                            record.due_date.strftime("%Y-%m-%d")
                            if record.due_date
                            else ""
                        ),
                        "create_time": (
                            create_time.strftime("%Y-%m-%d %H:%M:%S")
                            if create_time
                            else ""
                        ),
                    }
                )

            return JsonResponse(
                {
                    "code": ApiResponseCode.CODE_SUCCESS,
                    "msg": "",
                    "count": paginator.count,
                    "data": data,
                }
            )
        except Exception as e:
            logger.error(f"获取订单财务记录列表失败: {str(e)}", exc_info=True)
            return build_error_response(f"获取数据失败: {str(e)}")


class FinanceStatisticsView(LoginRequiredMixin, FinancePermissionMixin, View):
    """财务统计"""

    login_url = "/user/login/"
    permission_required = "finance.view_statistics"

    def get(self, request):
        try:
            stats = FinanceStatisticsService.get_dashboard_statistics()
            return JsonResponse({"code": ApiResponseCode.CODE_SUCCESS, "data": stats})
        except Exception as e:
            logger.error(f"获取统计数据失败: {str(e)}", exc_info=True)
            return build_error_response(f"获取统计数据失败: {str(e)}")


class ReimbursementStatisticsView(LoginRequiredMixin, View):
    """报销统计"""

    login_url = "/user/login/"

    def get(self, request):
        return render(request, "finance/statistics/reimbursement.html")


class InvoiceStatisticsView(LoginRequiredMixin, View):
    """发票统计"""

    login_url = "/user/login/"

    def get(self, request):
        return render(request, "finance/statistics/invoice.html")


class ReceiveInvoiceStatisticsView(LoginRequiredMixin, View):
    """收票统计"""

    login_url = "/user/login/"

    def get(self, request):
        return render(request, "finance/statistics/receiveinvoice.html")


class PaymentReceiveStatisticsView(LoginRequiredMixin, View):
    """收付款统计"""

    login_url = "/user/login/"

    def get(self, request):
        if request.path.endswith("/paymentreceive/statistics/"):
            from django.utils import timezone

            today = timezone.now().date()
            month_start = today.replace(day=1)
            month_start_dt = timezone.datetime.combine(month_start, timezone.datetime.min.time())
            total_stats = IncomeService.get_income_statistics()
            month_stats = IncomeService.get_income_statistics(start_date=month_start_dt)
            total_count = total_stats.get("total_count", 0)
            total_amount = total_stats.get("total_amount", 0)
            avg_amount = total_amount / total_count if total_count else 0
            return JsonResponse(
                {
                    "total_paymentreceive": total_count,
                    "total_amount": total_amount,
                    "this_month_amount": month_stats.get("total_amount", 0),
                    "avg_amount": avg_amount,
                }
            )
        return render(request, "finance/statistics/paymentreceive.html")


class PaymentStatisticsView(LoginRequiredMixin, View):
    """付款统计"""

    login_url = "/user/login/"

    def get(self, request):
        return render(request, "finance/statistics/payment.html")


class BatchApprovalView(LoginRequiredMixin, FinancePermissionMixin, View):
    """批量审批"""

    login_url = "/user/login/"
    permission_required = "finance.approve_expense"

    def post(self, request):
        try:
            data = json.loads(request.body)
            expense_ids = data.get("expense_ids", [])
            action = data.get("action")

            if not expense_ids or not action:
                return build_error_response("参数不完整")

            expenses = Expense.objects.filter(
                id__in=expense_ids, check_status=FinanceStatus.EXPENSE_CHECK_PROCESSING
            )
            results = []

            for expense in expenses:
                try:
                    if action == "approve":
                        expense.check_status = FinanceStatus.EXPENSE_CHECK_APPROVED
                        expense.check_time = int(time.time())
                    else:
                        expense.check_status = FinanceStatus.EXPENSE_CHECK_REJECTED

                    expense.check_history_uids += f",{request.user.id}"
                    expense.save()

                    results.append({"id": expense.id, "success": True})
                except Exception as e:
                    results.append(
                        {"id": expense.id, "success": False, "error": str(e)}
                    )

            return JsonResponse(
                {
                    "code": 0 if all(r["success"] for r in results) else 1,
                    "msg": f'成功审批 {sum(1 for r in results if r["success"])} 条记录',
                    "data": results,
                }
            )
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except Exception as e:
            logger.error(f"批量审批失败: {str(e)}", exc_info=True)
            return build_error_response(f"批量审批失败: {str(e)}")


def expense_detail(request, id):
    """报销详情"""
    expense = get_object_or_404(Expense, id=id)
    return render(request, "finance/expense_detail.html", {"expense": expense})


def invoice_detail(request, id):
    """发票详情"""
    invoice = get_object_or_404(Invoice, id=id)
    return render(request, "finance/invoice_detail.html", {"invoice": invoice})


class ExpenseDeleteView(LoginRequiredMixin, View):
    """删除报销"""

    def post(self, request):
        try:
            data = json.loads(request.body)
            obj_id = data.get("id")
            if not obj_id:
                return build_error_response("缺少ID参数")

            obj = get_object_or_404(Expense, id=obj_id)
            obj.delete()

            return JsonResponse({"code": 0, "msg": "删除成功"})
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except Exception as e:
            logger.error(f"删除报销失败: {str(e)}", exc_info=True)
            return build_error_response(f"删除失败: {str(e)}")


class InvoiceDeleteView(LoginRequiredMixin, View):
    """删除发票"""

    def post(self, request):
        try:
            data = json.loads(request.body)
            obj_id = data.get("id")
            if not obj_id:
                return build_error_response("缺少ID参数")

            obj = get_object_or_404(Invoice, id=obj_id)
            obj.delete()

            return JsonResponse({"code": 0, "msg": "删除成功"})
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except Exception as e:
            logger.error(f"删除发票失败: {str(e)}", exc_info=True)
            return build_error_response(f"删除失败: {str(e)}")


class IncomeDeleteView(LoginRequiredMixin, View):
    """删除回款"""

    def post(self, request):
        try:
            data = json.loads(request.body)
            obj_id = data.get("id")
            if not obj_id:
                return build_error_response("缺少ID参数")

            obj = get_object_or_404(Income, id=obj_id)
            IncomeService.delete_income(obj)

            return JsonResponse({"code": 0, "msg": "删除成功"})
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except Exception as e:
            logger.error(f"删除回款失败: {str(e)}", exc_info=True)
            return build_error_response(f"删除失败: {str(e)}")


class PaymentDeleteView(LoginRequiredMixin, View):
    """删除付款"""

    def post(self, request):
        try:
            data = json.loads(request.body)
            obj_id = data.get("id")
            if not obj_id:
                return build_error_response("缺少ID参数")

            obj = get_object_or_404(Payment, id=obj_id)
            expense_id = obj.expense_id
            obj.delete()
            has_payment = Payment.objects.filter(expense_id=expense_id).exists()
            if expense_id and not has_payment:
                Expense.objects.filter(id=expense_id).update(
                    pay_status=FinanceStatus.PAY_STATUS_PENDING,
                    pay_admin_id=0,
                    pay_time=0,
                )

            return JsonResponse({"code": 0, "msg": "删除成功"})
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except Exception as e:
            logger.error(f"删除付款失败: {str(e)}", exc_info=True)
            return build_error_response(f"删除失败: {str(e)}")
