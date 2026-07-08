"""
财务管理模块视图
只使用有数据库表的模型
"""

import csv
import io
import json
import logging
import os
import re
import time
from decimal import Decimal

from django.shortcuts import render, get_object_or_404
from django.views.generic import CreateView, UpdateView
from django.views import View
from django.http import JsonResponse, HttpResponseRedirect, Http404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

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
    ExpenseForm,
    FixedAssetForm,
    IncomeForm,
    InvoiceForm,
    InvoiceRequestForm,
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
    FinanceStatusMapping,
    TaxRecord,
)
from .services import (
    AdvancedFinanceService,
    BankTransactionService,
    ExpenseService,
    FinanceLinkageService,
    FinanceStatisticsService,
    IncomeService,
    InvoiceService,
    InvoiceRequestService,
    PaymentService,
)
from apps.common.utils import timestamp_to_date, safe_int, build_error_response
from apps.common.constants import ApiResponseCode, CommonConstant
from apps.customer.models import Customer, CustomerContract, CustomerOrder
from apps.user.models import Admin, SystemConfiguration

logger = logging.getLogger(__name__)


FINANCE_BANK_IMPORT_ALIAS_CONFIG_KEY = "finance_bank_import_field_aliases"


DEFAULT_IMPORT_FIELD_ALIASES = {
    "transaction_no": {
        "transactionno",
        "transaction_no",
        "流水号",
        "交易流水号",
        "银行流水号",
        "凭证号",
    },
    "transaction_date": {
        "transactiondate",
        "transaction_date",
        "交易时间",
        "交易日期",
        "记账时间",
        "入账时间",
        "流水时间",
    },
    "direction": {
        "direction",
        "收支方向",
        "借贷方向",
        "交易方向",
        "收入支出",
        "收支",
    },
    "amount": {
        "amount",
        "交易金额",
        "发生额",
        "金额",
        "收支金额",
    },
    "counterparty": {
        "counterparty",
        "交易对方",
        "对方户名",
        "对方名称",
        "对手方",
        "往来单位",
    },
    "customer_name": {"customername", "customer_name", "客户名称", "客户", "回款客户"},
    "supplier_name": {"suppliername", "supplier_name", "供应商名称", "供应商", "付款供应商"},
    "order_number": {"ordernumber", "order_number", "订单号", "客户订单", "销售订单号"},
    "contract_number": {"contractnumber", "contract_number", "合同号", "合同编号"},
    "invoice_code": {"invoicecode", "invoice_code", "发票号", "发票编号", "发票代码"},
    "purpose": {"purpose", "用途", "摘要", "备注", "交易摘要", "业务摘要"},
}


def normalize_import_header(value):
    return re.sub(r"[\s_\-()/\\（）]+", "", str(value or "").strip().lower())


def clean_import_value(value):
    if value is None:
        return ""
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, float):
        if value != value:
            return ""
        if value.is_integer():
            return str(int(value))
        return str(value)
    return str(value).strip()


def parse_bool_flag(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_alias_config(raw_aliases):
    if not isinstance(raw_aliases, dict):
        raise ValueError("字段模板必须是JSON对象")

    normalized = {}
    for field in DEFAULT_IMPORT_FIELD_ALIASES:
        values = raw_aliases.get(field)
        if values is None:
            continue
        if not isinstance(values, list):
            raise ValueError(f"{field} 的别名必须是数组")
        aliases = []
        for value in values:
            text = normalize_import_header(value)
            if text and text not in aliases:
                aliases.append(text)
        normalized[field] = aliases
    return normalized


def get_bank_import_field_aliases():
    aliases = {
        field: [normalize_import_header(value) for value in sorted(values)]
        for field, values in DEFAULT_IMPORT_FIELD_ALIASES.items()
    }
    config = SystemConfiguration.objects.filter(
        key=FINANCE_BANK_IMPORT_ALIAS_CONFIG_KEY, is_active=True
    ).first()
    if not config or not config.value:
        return aliases
    try:
        custom_aliases = normalize_alias_config(json.loads(config.value))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("银行导入字段模板配置无效: %s", exc)
        return aliases

    for field, values in custom_aliases.items():
        merged = []
        for value in values + aliases.get(field, []):
            if value and value not in merged:
                merged.append(value)
        aliases[field] = merged
    return aliases


def save_bank_import_field_aliases(raw_aliases):
    aliases = normalize_alias_config(raw_aliases)
    config, _ = SystemConfiguration.objects.get_or_create(
        key=FINANCE_BANK_IMPORT_ALIAS_CONFIG_KEY,
        defaults={"description": "财务银行导入字段别名模板", "is_active": True, "value": "{}"},
    )
    config.value = json.dumps(aliases, ensure_ascii=False)
    config.description = "财务银行导入字段别名模板"
    config.is_active = True
    config.save(update_fields=["value", "description", "is_active", "updated_at"])
    return aliases


def read_uploaded_table(uploaded_file):
    extension = os.path.splitext(uploaded_file.name or "")[1].lower()
    if extension == ".csv":
        raw_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        last_error = None
        for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
            try:
                text = raw_bytes.decode(encoding)
                rows = list(csv.DictReader(io.StringIO(text)))
                return rows
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ValueError(f"CSV文件编码无法识别: {last_error}")

    if extension in {".xlsx", ".xls"}:
        import pandas as pd

        dataframe = pd.read_excel(uploaded_file, dtype=object).fillna("")
        uploaded_file.seek(0)
        return dataframe.to_dict(orient="records")

    raise ValueError("仅支持 .csv、.xlsx、.xls 文件")


def map_uploaded_bank_rows(rows, field_aliases=None):
    aliases_map = field_aliases or get_bank_import_field_aliases()
    mapped_rows = []
    for row in rows:
        normalized_row = {field: "" for field in aliases_map}
        for raw_key, raw_value in (row or {}).items():
            normalized_key = normalize_import_header(raw_key)
            if not normalized_key:
                continue
            for target_field, aliases in aliases_map.items():
                if normalized_key in aliases:
                    normalized_row[target_field] = clean_import_value(raw_value)
                    break
        if any(value for value in normalized_row.values()):
            mapped_rows.append(normalized_row)
    return mapped_rows


def get_bank_accounts():
    accounts = FinanceAccount.objects.filter(account_type="bank").order_by("-id")
    if accounts.exists():
        return accounts
    return FinanceAccount.objects.order_by("-id")


def serialize_invoice_request(invoice_request):
    order = (
        CustomerOrder.objects.select_related("customer", "invoice_request_user")
        .filter(id=invoice_request.order_id)
        .first()
    )
    applicant = Admin.objects.filter(id=invoice_request.applicant_id).first()
    reviewer = Admin.objects.filter(id=invoice_request.reviewer_id).first()
    create_time = (
        timestamp_to_date(invoice_request.create_time)
        if invoice_request.create_time
        else ""
    )
    review_time = (
        timestamp_to_date(invoice_request.review_time)
        if invoice_request.review_time
        else ""
    )
    return {
        "id": invoice_request.id,
        "order_id": invoice_request.order_id,
        "order_number": order.order_number if order else "",
        "customer_name": (
            order.customer.name if order and getattr(order, "customer_id", 0) else ""
        ),
        "amount": float(invoice_request.amount),
        "invoice_type": invoice_request.invoice_type,
        "invoice_type_display": FinanceStatusMapping.INVOICE_TYPE_MAP.get(
            invoice_request.invoice_type, str(invoice_request.invoice_type)
        ),
        "invoice_title": invoice_request.invoice_title,
        "tax_number": invoice_request.tax_number,
        "reason": invoice_request.reason,
        "status": invoice_request.status,
        "status_display": invoice_request.get_status_display(),
        "applicant_id": invoice_request.applicant_id,
        "applicant": applicant.name if applicant else "",
        "reviewer_id": invoice_request.reviewer_id,
        "reviewer": reviewer.name if reviewer else "",
        "review_comment": invoice_request.review_comment,
        "invoice_id": invoice_request.invoice_id,
        "create_time": create_time,
        "review_time": review_time,
    }


def serialize_invoice(invoice):
    from apps.project.models import Project

    customer = Customer.objects.filter(id=invoice.customer_id).first()
    contract = CustomerContract.objects.filter(id=invoice.contract_id).first()
    project = Project.objects.filter(id=invoice.project_id).first()
    remaining_amount = invoice.amount - invoice.enter_amount
    return {
        "id": invoice.id,
        "code": invoice.code,
        "customer_id": invoice.customer_id,
        "customer_name": customer.name if customer else "",
        "contract_id": invoice.contract_id,
        "contract_number": contract.contract_number if contract else "",
        "contract_name": contract.name if contract else "",
        "project_id": invoice.project_id,
        "project_name": project.name if project else "",
        "project_code": getattr(project, "code", ""),
        "amount": float(invoice.amount),
        "enter_amount": float(invoice.enter_amount),
        "remaining_amount": float(remaining_amount),
        "invoice_type_display": invoice.get_invoice_type_display(),
        "open_status_display": invoice.get_open_status_display(),
        "enter_status_display": invoice.get_enter_status_display(),
        "open_status": invoice.open_status,
        "enter_status": invoice.enter_status,
        "invoice_title": invoice.invoice_title,
        "invoice_tax": invoice.invoice_tax,
        "invoice_phone": invoice.invoice_phone,
        "invoice_address": invoice.invoice_address,
        "invoice_bank": invoice.invoice_bank,
        "invoice_account": invoice.invoice_account,
        "delivery": invoice.delivery,
        "remark": invoice.remark,
        "file_ids": invoice.file_ids,
        "other_file_ids": invoice.other_file_ids,
        "create_time": timestamp_to_date(invoice.create_time),
        "open_time": timestamp_to_date(invoice.open_time) if invoice.open_time else "",
        "enter_time": timestamp_to_date(invoice.enter_time)
        if invoice.enter_time
        else "",
        "check_time": timestamp_to_date(invoice.check_time)
        if invoice.check_time
        else "",
    }


def serialize_payment(payment):
    from apps.contract.models import Purchase
    from apps.inventory.models import PurchaseOrder
    from apps.project.models import Project

    expense = Expense.objects.filter(id=payment.expense_id).first()
    customer = Customer.objects.filter(id=payment.customer_id).first()
    order = (
        CustomerOrder.objects.select_related("customer")
        .filter(id=payment.order_id)
        .first()
    )
    purchase_order = PurchaseOrder.objects.filter(id=payment.purchase_order_id).first()
    purchase_contract = Purchase.objects.filter(id=payment.purchase_contract_id).first()
    project = Project.objects.filter(id=payment.project_id).first()

    relation_parts = []
    if expense:
        relation_parts.append(f"报销：{expense.code}")
    elif payment.expense_id:
        relation_parts.append(f"报销ID：{payment.expense_id}")

    effective_customer = customer or (order.customer if order and order.customer_id else None)
    if effective_customer:
        relation_parts.append(f"客户：{effective_customer.name}")
    elif payment.customer_id:
        relation_parts.append(f"客户ID：{payment.customer_id}")

    if order:
        relation_parts.append(f"订单：{order.order_number}")
    elif payment.order_id:
        relation_parts.append(f"订单ID：{payment.order_id}")

    if purchase_order:
        relation_parts.append(f"采购订单：{purchase_order.code}")
    elif payment.purchase_order_id:
        relation_parts.append(f"采购订单ID：{payment.purchase_order_id}")

    if purchase_contract:
        relation_parts.append(f"采购合同：{purchase_contract.code}")
    elif payment.purchase_contract_id:
        relation_parts.append(f"采购合同ID：{payment.purchase_contract_id}")

    if project:
        relation_parts.append(f"项目：{project.name}")
    elif payment.project_id:
        relation_parts.append(f"项目ID：{payment.project_id}")

    payment_date = payment.payment_date
    if isinstance(payment_date, str):
        payment_date = parse_datetime(payment_date) or payment_date

    return {
        "id": payment.id,
        "expense_id": payment.expense_id,
        "customer_id": payment.customer_id or (effective_customer.id if effective_customer else 0),
        "order_id": payment.order_id,
        "purchase_order_id": payment.purchase_order_id,
        "purchase_contract_id": payment.purchase_contract_id,
        "project_id": payment.project_id,
        "expense_code": expense.code if expense else "",
        "customer_name": effective_customer.name if effective_customer else "",
        "order_number": order.order_number if order else "",
        "purchase_order_code": purchase_order.code if purchase_order else "",
        "purchase_contract_code": purchase_contract.code if purchase_contract else "",
        "project_name": project.name if project else "",
        "relation_summary": " / ".join(relation_parts),
        "amount": float(payment.amount),
        "payment_date": (
            payment_date.strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(payment_date, "strftime")
            else payment_date or ""
        ),
        "remark": payment.remark,
        "create_time": timestamp_to_date(payment.create_time),
    }


def serialize_income(income):
    invoice = Invoice.objects.filter(id=income.invoice_id).first()
    transaction = (
        BankTransaction.objects.select_related("account")
        .filter(related_type="income", related_id=income.id)
        .first()
    )
    invoice_detail = serialize_invoice(invoice) if invoice else None

    invoice_code = ""
    invoice_title = ""
    customer_name = ""
    invoice_amount = 0
    entered_amount = 0
    remaining_amount = 0
    if invoice_detail:
        invoice_code = invoice_detail.get("code", "")
        invoice_title = invoice_detail.get("invoice_title", "")
        customer_name = invoice_detail.get("customer_name", "")
        invoice_amount = invoice_detail.get("amount", 0)
        entered_amount = invoice_detail.get("enter_amount", 0)
        remaining_amount = invoice_detail.get("remaining_amount", 0)

    income_date = income.income_date
    if isinstance(income_date, str):
        income_date = parse_datetime(income_date) or income_date

    return {
        "id": income.id,
        "invoice_id": income.invoice_id,
        "invoice_code": invoice_code,
        "invoice_title": invoice_title,
        "customer_name": customer_name,
        "invoice_amount": invoice_amount,
        "entered_amount": entered_amount,
        "remaining_amount": remaining_amount,
        "amount": float(income.amount),
        "income_date": (
            income_date.strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(income_date, "strftime")
            else income_date or ""
        ),
        "account_name": (
            transaction.account.name
            if transaction and getattr(transaction, "account_id", 0)
            else ""
        ),
        "bank_name": (
            transaction.account.bank_name
            if transaction and getattr(transaction, "account_id", 0)
            else ""
        ),
        "transaction_no": transaction.transaction_no if transaction else "",
        "match_status_display": (
            transaction.get_match_status_display() if transaction else "未生成流水"
        ),
        "file_ids": income.file_ids,
        "remark": income.remark,
        "create_time": timestamp_to_date(income.create_time),
    }


def serialize_expense(expense):
    from apps.project.models import Project

    project = Project.objects.filter(id=expense.project_id).first()
    applicant = Admin.objects.filter(id=expense.admin_id).first()
    pay_admin = Admin.objects.filter(id=expense.pay_admin_id).first()

    return {
        "id": expense.id,
        "code": expense.code,
        "subject_id": expense.subject_id,
        "admin_id": expense.admin_id,
        "admin_name": applicant.name if applicant else "",
        "did": expense.did,
        "project_id": expense.project_id,
        "project_name": project.name if project else "",
        "income_month": expense.income_month,
        "cost": float(expense.cost),
        "check_status": expense.check_status,
        "check_status_display": expense.get_check_status_display(),
        "pay_status": expense.pay_status,
        "pay_status_display": expense.get_pay_status_display(),
        "check_flow_id": expense.check_flow_id,
        "check_step_sort": expense.check_step_sort,
        "check_uids": expense.check_uids,
        "check_last_uid": expense.check_last_uid,
        "check_history_uids": expense.check_history_uids,
        "check_copy_uids": expense.check_copy_uids,
        "pay_admin_name": pay_admin.name if pay_admin else "",
        "expense_time": timestamp_to_date(expense.expense_time),
        "create_time": timestamp_to_date(expense.create_time),
        "check_time": timestamp_to_date(expense.check_time),
        "pay_time": timestamp_to_date(expense.pay_time),
        "remark": expense.remark,
        "file_ids": expense.file_ids,
    }


def format_finance_amount(value) -> str:
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    return f"¥{amount:,.2f}"


def build_finance_statistics_context(stat_type: str) -> dict:
    today = timezone.now().date()
    month_start = today.replace(day=1)
    month_start_dt = timezone.datetime.combine(month_start, timezone.datetime.min.time())
    month_start_ts = int(month_start_dt.timestamp())

    base_context = {
        "period_text": f"统计范围：累计数据，本月窗口从 {month_start.strftime('%Y-%m-%d')} 开始",
    }

    if stat_type == "reimbursement":
        total_stats = ExpenseService.get_expense_statistics()
        month_stats = ExpenseService.get_expense_statistics(start_ts=month_start_ts)
        pending_amount = (
            Expense.objects.filter(check_status=FinanceStatus.EXPENSE_CHECK_PENDING).aggregate(
                total=Sum("cost")
            )["total"]
            or Decimal("0")
        )
        return {
            **base_context,
            "page_title": "报销统计",
            "page_subtitle": "集中看审批进度、打款情况和本月报销规模，方便财务快速判断积压点。",
            "manage_path": "/reimbursement/",
            "manage_label": "进入报销管理",
            "table_id": "reimbursementDetailTable",
            "data_path": "/reimbursement/datalist/",
            "table_columns_json": json.dumps(
                [
                    {"field": "code", "title": "报销编码", "width": 180, "fixed": "left"},
                    {"field": "cost", "title": "报销金额", "width": 120, "kind": "currency"},
                    {"field": "expense_date", "title": "报销日期", "width": 120, "align": "center"},
                    {
                        "field": "check_status_display",
                        "title": "审核状态",
                        "width": 120,
                        "kind": "text_or_empty",
                    },
                    {
                        "field": "pay_status_display",
                        "title": "打款状态",
                        "width": 120,
                        "kind": "text_or_empty",
                    },
                    {"field": "create_time", "title": "创建时间", "width": 160, "align": "center"},
                ],
                ensure_ascii=False,
            ),
            "summary_cards": [
                {
                    "label": "报销笔数",
                    "value": str(total_stats["total_count"]),
                    "note": f"本月新增 {month_stats['total_count']} 笔",
                },
                {
                    "label": "报销金额",
                    "value": format_finance_amount(total_stats["total_amount"]),
                    "note": f"本月金额 {format_finance_amount(month_stats['total_amount'])}",
                },
                {
                    "label": "待审核金额",
                    "value": format_finance_amount(pending_amount),
                    "note": f"审批中 {total_stats['processing_count']} 笔",
                },
                {
                    "label": "已打款金额",
                    "value": format_finance_amount(total_stats["paid_amount"]),
                    "note": f"待支付 {total_stats['unpaid_count']} 笔",
                },
            ],
        }

    if stat_type == "invoice":
        total_stats = InvoiceService.get_invoice_statistics()
        month_stats = InvoiceService.get_invoice_statistics(start_ts=month_start_ts)
        return {
            **base_context,
            "page_title": "发票统计",
            "page_subtitle": "把开票总额、回款完成度和状态分布放在一页里，便于核对开票与回款闭环。",
            "manage_path": "/invoice/",
            "manage_label": "进入发票管理",
            "table_id": "invoiceDetailTable",
            "data_path": "/invoice/datalist/",
            "table_columns_json": json.dumps(
                [
                    {"field": "code", "title": "发票号码", "width": 180, "fixed": "left"},
                    {"field": "customer_name", "title": "客户", "width": 180, "kind": "text_or_empty"},
                    {"field": "invoice_title", "title": "开票抬头", "minWidth": 220, "kind": "text_or_empty"},
                    {"field": "amount", "title": "发票金额", "width": 120, "kind": "currency"},
                    {"field": "open_status_display", "title": "开票状态", "width": 110, "kind": "text_or_empty"},
                    {"field": "enter_status_display", "title": "回款状态", "width": 110, "kind": "text_or_empty"},
                    {"field": "create_time", "title": "创建时间", "width": 160, "align": "center"},
                ],
                ensure_ascii=False,
            ),
            "summary_cards": [
                {
                    "label": "发票数量",
                    "value": str(total_stats["total_count"]),
                    "note": f"本月新增 {month_stats['total_count']} 张",
                },
                {
                    "label": "开票金额",
                    "value": format_finance_amount(total_stats["total_amount"]),
                    "note": f"本月新增 {format_finance_amount(month_stats['total_amount'])}",
                },
                {
                    "label": "已回款金额",
                    "value": format_finance_amount(total_stats["enter_amount"]),
                    "note": f"回款完成 {total_stats['paid_count']} 张",
                },
                {
                    "label": "待回款金额",
                    "value": format_finance_amount(total_stats["uncollected_amount"]),
                    "note": f"部分回款 {total_stats['partial_count']} 张",
                },
            ],
        }

    if stat_type == "receiveinvoice":
        total_stats = InvoiceService.get_invoice_statistics()
        month_stats = InvoiceService.get_invoice_statistics(start_ts=month_start_ts)
        return {
            **base_context,
            "page_title": "收票统计",
            "page_subtitle": "这是收票旧入口的兼容统计页，当前数据与发票记录保持一致，但展示风格已回到统一财务面板。",
            "manage_path": "/receiveinvoice/",
            "manage_label": "进入收票管理",
            "table_id": "receiveInvoiceDetailTable",
            "data_path": "/receiveinvoice/datalist/",
            "table_columns_json": json.dumps(
                [
                    {"field": "code", "title": "发票号码", "width": 180, "fixed": "left"},
                    {"field": "customer_name", "title": "客户", "width": 180, "kind": "text_or_empty"},
                    {"field": "invoice_title", "title": "开票抬头", "minWidth": 220, "kind": "text_or_empty"},
                    {"field": "amount", "title": "发票金额", "width": 120, "kind": "currency"},
                    {"field": "open_status_display", "title": "开票状态", "width": 110, "kind": "text_or_empty"},
                    {"field": "enter_status_display", "title": "处理状态", "width": 110, "kind": "text_or_empty"},
                    {"field": "create_time", "title": "创建时间", "width": 160, "align": "center"},
                ],
                ensure_ascii=False,
            ),
            "summary_cards": [
                {
                    "label": "收票数量",
                    "value": str(total_stats["total_count"]),
                    "note": f"本月新增 {month_stats['total_count']} 张",
                },
                {
                    "label": "收票金额",
                    "value": format_finance_amount(total_stats["total_amount"]),
                    "note": f"本月新增 {format_finance_amount(month_stats['total_amount'])}",
                },
                {
                    "label": "已开票",
                    "value": str(total_stats["opened_count"]),
                    "note": f"未开票 {total_stats['not_open_count']} 张",
                },
                {
                    "label": "回款完成",
                    "value": str(total_stats["paid_count"]),
                    "note": f"待回款 {total_stats['unpaid_count']} 张",
                },
            ],
        }

    if stat_type == "paymentreceive":
        total_stats = IncomeService.get_income_statistics()
        month_stats = IncomeService.get_income_statistics(start_date=month_start_dt)
        avg_amount = (total_stats["total_amount"] / total_stats["total_count"]) if total_stats["total_count"] else 0
        return {
            **base_context,
            "page_title": "收款统计",
            "page_subtitle": "从回款笔数、到账规模和本月节奏三个角度看回款情况，方便财务快速追踪现金流入。",
            "manage_path": "/paymentreceive/",
            "manage_label": "进入收款管理",
            "table_id": "paymentReceiveDetailTable",
            "data_path": "/paymentreceive/datalist/",
            "table_columns_json": json.dumps(
                [
                    {"field": "invoice_code", "title": "关联发票", "width": 180, "fixed": "left", "kind": "text_or_empty"},
                    {"field": "invoice_title", "title": "开票抬头", "minWidth": 220, "kind": "text_or_empty"},
                    {"field": "amount", "title": "收款金额", "width": 120, "kind": "currency"},
                    {"field": "income_date", "title": "收款日期", "width": 170, "align": "center"},
                    {"field": "remark", "title": "备注", "minWidth": 220, "kind": "text_or_empty"},
                    {"field": "create_time", "title": "创建时间", "width": 160, "align": "center"},
                ],
                ensure_ascii=False,
            ),
            "summary_cards": [
                {
                    "label": "收款笔数",
                    "value": str(total_stats["total_count"]),
                    "note": f"本月新增 {month_stats['total_count']} 笔",
                },
                {
                    "label": "收款金额",
                    "value": format_finance_amount(total_stats["total_amount"]),
                    "note": f"本月到账 {format_finance_amount(month_stats['total_amount'])}",
                },
                {
                    "label": "本月收款",
                    "value": format_finance_amount(month_stats["total_amount"]),
                    "note": "按自然月累计",
                },
                {
                    "label": "平均单笔",
                    "value": format_finance_amount(avg_amount),
                    "note": "累计平均值",
                },
            ],
        }

    if stat_type == "payment":
        total_stats = PaymentService.get_payment_statistics()
        month_stats = PaymentService.get_payment_statistics(start_date=month_start_dt)
        avg_amount = (total_stats["total_amount"] / total_stats["total_count"]) if total_stats["total_count"] else 0
        return {
            **base_context,
            "page_title": "付款统计",
            "page_subtitle": "从付款笔数、支出规模和关联业务摘要观察本月支出节奏，方便财务核对对外付款。",
            "manage_path": "/payment/",
            "manage_label": "进入付款管理",
            "table_id": "paymentDetailTable",
            "data_path": "/payment/datalist/",
            "table_columns_json": json.dumps(
                [
                    {"field": "relation_summary", "title": "业务关联", "minWidth": 280, "fixed": "left", "kind": "text_or_empty"},
                    {"field": "amount", "title": "付款金额", "width": 120, "kind": "currency"},
                    {"field": "payment_date", "title": "付款日期", "width": 170, "align": "center"},
                    {"field": "customer_name", "title": "客户", "width": 180, "kind": "text_or_empty"},
                    {"field": "remark", "title": "备注", "minWidth": 220, "kind": "text_or_empty"},
                    {"field": "create_time", "title": "创建时间", "width": 160, "align": "center"},
                ],
                ensure_ascii=False,
            ),
            "summary_cards": [
                {
                    "label": "付款笔数",
                    "value": str(total_stats["total_count"]),
                    "note": f"本月新增 {month_stats['total_count']} 笔",
                },
                {
                    "label": "付款金额",
                    "value": format_finance_amount(total_stats["total_amount"]),
                    "note": f"本月支出 {format_finance_amount(month_stats['total_amount'])}",
                },
                {
                    "label": "本月付款",
                    "value": format_finance_amount(month_stats["total_amount"]),
                    "note": "按自然月累计",
                },
                {
                    "label": "平均单笔",
                    "value": format_finance_amount(avg_amount),
                    "note": "累计平均值",
                },
            ],
        }

    raise Http404("未知统计类型")


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

            diff_time = request.GET.get("diff_time") or request.GET.get("date_range")
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
                        "income_month": expense.income_month,
                        "expense_time": expense.expense_time,
                        "expense_date": (
                            expense_date.strftime("%Y-%m-%d") if expense_date else ""
                        ),
                        "admin_id": expense.admin_id,
                        "did": expense.did,
                        "project_id": expense.project_id,
                        "create_time": timestamp_to_date(expense.create_time),
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


class ExpenseCreateView(LoginRequiredMixin, FinancePermissionMixin, CreateView):
    """创建报销"""

    login_url = "/user/login/"
    permission_required = "finance.add_expense"
    model = Expense
    form_class = ExpenseForm
    template_name = "finance/expense_form.html"
    success_url = reverse_lazy("finance:reimbursement_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.project.models import Project

        context["projects"] = Project.objects.order_by("-id")[:200]
        return context

    def form_valid(self, form):
        import random

        self.object = form.save(commit=False)
        self.object.admin_id = self.request.user.id
        self.object.did = getattr(self.request.user, "did", 0) or 0
        self.object.create_time = int(time.time())
        if not self.object.code:
            self.object.code = (
                f'BX{timezone.now().strftime("%Y%m%d%H%M%S")}{random.randint(1000, 9999)}'
            )
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


class ExpenseUpdateView(LoginRequiredMixin, UpdateView):
    """编辑报销"""

    login_url = "/user/login/"
    model = Expense
    form_class = ExpenseForm
    template_name = "finance/expense_form.html"
    success_url = reverse_lazy("finance:reimbursement_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.project.models import Project

        context["projects"] = Project.objects.order_by("-id")[:200]
        return context

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())


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
            status = request.GET.get("status")
            if status not in (None, ""):
                queryset = queryset.filter(open_status=status)

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            customer_ids = [invoice.customer_id for invoice in page_obj if invoice.customer_id]
            customer_map = {
                customer.id: customer
                for customer in Customer.objects.filter(id__in=customer_ids)
            }
            data = []
            for invoice in page_obj:
                customer = customer_map.get(invoice.customer_id)
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
                        "customer_name": customer.name if customer else "",
                        "create_time": timestamp_to_date(invoice.create_time),
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.project.models import Project

        context["customers"] = Customer.objects.order_by("-id")[:200]
        context["contracts"] = CustomerContract.objects.order_by("-id")[:200]
        context["projects"] = Project.objects.order_by("-id")[:200]
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.admin_id = self.request.user.id
        self.object.did = getattr(self.request.user, "did", 0) or 0
        if not self.object.create_time:
            self.object.create_time = int(time.time())
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


class InvoiceUpdateView(LoginRequiredMixin, FinancePermissionMixin, UpdateView):
    """更新发票"""

    login_url = "/user/login/"
    permission_required = "finance.change_invoice"
    model = Invoice
    form_class = InvoiceForm
    template_name = "finance/invoice_form.html"
    success_url = reverse_lazy("finance:invoice_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.project.models import Project

        context["customers"] = Customer.objects.order_by("-id")[:200]
        context["contracts"] = CustomerContract.objects.order_by("-id")[:200]
        context["projects"] = Project.objects.order_by("-id")[:200]
        return context


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
            keywords = (request.GET.get("keywords") or "").strip()
            if keywords:
                invoice_ids = list(
                    Invoice.objects.filter(
                        Q(code__icontains=keywords) | Q(invoice_title__icontains=keywords)
                    ).values_list("id", flat=True)
                )
                queryset = queryset.filter(
                    Q(remark__icontains=keywords) | Q(invoice_id__in=invoice_ids)
                )

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
                        "create_time": timestamp_to_date(income.create_time),
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

    def get_initial(self):
        initial = super().get_initial()
        invoice_id = safe_int(self.request.GET.get("invoice_id"), 0)
        if invoice_id:
            initial["invoice_id"] = invoice_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invoices"] = Invoice.objects.exclude(
            enter_status=FinanceStatus.ENTER_STATUS_FULL
        ).order_by("-create_time")[:200]
        context["accounts"] = FinanceAccount.objects.filter(status="active").order_by("id")
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
            keywords = (request.GET.get("keywords") or "").strip()
            if keywords:
                expense_ids = list(
                    Expense.objects.filter(code__icontains=keywords).values_list("id", flat=True)
                )
                customer_ids = list(
                    Customer.objects.filter(name__icontains=keywords).values_list("id", flat=True)
                )
                order_ids = list(
                    CustomerOrder.objects.filter(order_number__icontains=keywords).values_list(
                        "id", flat=True
                    )
                )
                queryset = queryset.filter(
                    Q(remark__icontains=keywords)
                    | Q(expense_id__in=expense_ids)
                    | Q(customer_id__in=customer_ids)
                    | Q(order_id__in=order_ids)
                )

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = [serialize_payment(payment) for payment in page_obj]

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

    def get_initial(self):
        initial = super().get_initial()
        for field in [
            "expense_id",
            "customer_id",
            "order_id",
            "purchase_order_id",
            "purchase_contract_id",
            "project_id",
        ]:
            value = safe_int(self.request.GET.get(field), 0)
            if value:
                initial[field] = value
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.contract.models import Purchase
        from apps.inventory.models import PurchaseOrder
        from apps.project.models import Project

        context["expenses"] = Expense.objects.filter(
            check_status=FinanceStatus.EXPENSE_CHECK_APPROVED,
            pay_status=FinanceStatus.PAY_STATUS_PENDING,
        ).order_by("-create_time")[:200]
        context["accounts"] = FinanceAccount.objects.filter(status="active").order_by("id")
        context["customers"] = Customer.objects.order_by("-id")[:200]
        context["orders"] = CustomerOrder.objects.select_related("customer").order_by("-id")[:200]
        context["purchase_orders"] = PurchaseOrder.objects.select_related("supplier").order_by("-id")[:200]
        context["purchase_contracts"] = Purchase.objects.order_by("-id")[:200]
        context["projects"] = Project.objects.select_related("customer").order_by("-id")[:200]
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


class BankTransactionImportView(LoginRequiredMixin, FinancePermissionMixin, View):
    """银行流水导入"""

    login_url = "/user/login/"
    permission_required = "finance.add_banktransaction"

    def get(self, request):
        return render(
            request,
            "finance/bank_transaction_import.html",
            {
                "accounts": get_bank_accounts(),
                "field_aliases_json": json.dumps(
                    get_bank_import_field_aliases(), ensure_ascii=False
                ),
            },
        )

    def post(self, request):
        try:
            if request.content_type and "application/json" in request.content_type:
                payload = json.loads(request.body)
                account_id = safe_int(payload.get("account_id"), 0)
                rows = payload.get("rows") or []
                auto_create_related = bool(payload.get("auto_create_related"))
            else:
                uploaded_file = request.FILES.get("file")
                if not uploaded_file:
                    return build_error_response("请选择导入文件")
                account_id = safe_int(request.POST.get("account_id"), 0)
                rows = map_uploaded_bank_rows(read_uploaded_table(uploaded_file))
                auto_create_related = parse_bool_flag(
                    request.POST.get("auto_create_related")
                )
            if not account_id:
                return build_error_response("缺少资金账户")
            if not isinstance(rows, list) or not rows:
                return build_error_response("缺少导入流水数据")
            result = BankTransactionService.import_transactions(
                account_id=account_id,
                rows=rows,
                auto_create_related=auto_create_related,
                user=request.user,
            )
            return JsonResponse({"code": ApiResponseCode.CODE_SUCCESS, "data": result})
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except ValueError as e:
            return build_error_response(str(e))
        except Exception as e:
            logger.error(f"导入银行流水失败: {str(e)}", exc_info=True)
            return build_error_response(f"导入失败: {str(e)}")


class BankReconciliationImportView(LoginRequiredMixin, FinancePermissionMixin, View):
    """银行流水对账导入"""

    login_url = "/user/login/"
    permission_required = "finance.add_bankreconciliation"

    def get(self, request):
        return render(
            request,
            "finance/bank_reconciliation_import.html",
            {
                "accounts": get_bank_accounts(),
                "field_aliases_json": json.dumps(
                    get_bank_import_field_aliases(), ensure_ascii=False
                ),
            },
        )

    def post(self, request):
        try:
            if request.content_type and "application/json" in request.content_type:
                payload = json.loads(request.body)
                account_id = safe_int(payload.get("account_id"), 0)
                period = (payload.get("period") or "").strip()
                bank_balance = payload.get("bank_balance")
                rows = payload.get("rows") or []
            else:
                uploaded_file = request.FILES.get("file")
                if not uploaded_file:
                    return build_error_response("请选择对账文件")
                account_id = safe_int(request.POST.get("account_id"), 0)
                period = (request.POST.get("period") or "").strip()
                bank_balance = request.POST.get("bank_balance")
                rows = map_uploaded_bank_rows(read_uploaded_table(uploaded_file))
            if not account_id:
                return build_error_response("缺少资金账户")
            if not period:
                return build_error_response("缺少对账期间")
            if not isinstance(rows, list) or not rows:
                return build_error_response("缺少对账流水数据")
            result = BankTransactionService.import_reconciliation(
                account_id=account_id,
                period=period,
                rows=rows,
                bank_balance=bank_balance,
            )
            return JsonResponse({"code": ApiResponseCode.CODE_SUCCESS, "data": result})
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except ValueError as e:
            return build_error_response(str(e))
        except Exception as e:
            logger.error(f"导入银行对账失败: {str(e)}", exc_info=True)
            return build_error_response(f"导入失败: {str(e)}")


class BankReconciliationCompareView(LoginRequiredMixin, FinancePermissionMixin, View):
    """银行对账比对详情"""

    login_url = "/user/login/"
    permission_required = "finance.view_bankreconciliation"

    def get(self, request, id):
        reconciliation = get_object_or_404(BankReconciliation, id=id)
        detail = BankTransactionService.get_reconciliation_detail(reconciliation)
        return JsonResponse({"code": ApiResponseCode.CODE_SUCCESS, "data": detail})


class BankImportTemplateConfigView(LoginRequiredMixin, FinancePermissionMixin, View):
    """银行导入字段模板配置"""

    login_url = "/user/login/"
    permission_required = "finance.add_banktransaction"

    def get(self, request):
        return JsonResponse(
            {
                "code": ApiResponseCode.CODE_SUCCESS,
                "data": {"aliases": get_bank_import_field_aliases()},
            }
        )

    def post(self, request):
        try:
            payload = json.loads(request.body)
            aliases = save_bank_import_field_aliases(payload.get("aliases") or {})
            return JsonResponse(
                {
                    "code": ApiResponseCode.CODE_SUCCESS,
                    "msg": "保存成功",
                    "data": {"aliases": get_bank_import_field_aliases(), "custom_aliases": aliases},
                }
            )
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except ValueError as e:
            return build_error_response(str(e))
        except Exception as e:
            logger.error(f"保存银行导入字段模板失败: {str(e)}", exc_info=True)
            return build_error_response(f"保存失败: {str(e)}")


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
            elif tab == "3":
                queryset = queryset.filter(reviewer_id=uid).exclude(status="pending")

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = [serialize_invoice_request(req) for req in page_obj]

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


class InvoiceRequestCreateView(LoginRequiredMixin, FinancePermissionMixin, CreateView):
    """创建开票申请"""

    login_url = "/user/login/"
    permission_required = "finance.add_invoicerequest"
    model = InvoiceRequest
    form_class = InvoiceRequestForm
    template_name = "finance/invoice_request_form.html"
    success_url = reverse_lazy("finance:invoice_request_list")

    def get_initial(self):
        initial = super().get_initial()
        order_id = safe_int(self.request.GET.get("order_id"), 0)
        if order_id:
            order = CustomerOrder.objects.select_related("customer").filter(id=order_id).first()
            if order:
                initial.update(
                    {
                        "order_id": order.id,
                        "amount": order.amount,
                        "invoice_title": order.customer.name if order.customer_id else "",
                    }
                )
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["orders"] = CustomerOrder.objects.select_related("customer").order_by("-id")[:200]
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.applicant_id = self.request.user.id
        self.object.department_id = getattr(self.request.user, "did", 0) or 0
        self.object.create_time = int(time.time())
        self.object.save()
        CustomerOrder.objects.filter(id=self.object.order_id).update(
            invoice_request_status="requested",
            invoice_request_user_id=self.request.user.id,
            invoice_request_time=timezone.now(),
        )
        return HttpResponseRedirect(self.get_success_url())


class InvoiceRequestApprovalView(LoginRequiredMixin, FinancePermissionMixin, View):
    """审批开票申请"""

    login_url = "/user/login/"
    permission_required = "finance.change_invoicerequest"

    def post(self, request):
        try:
            data = json.loads(request.body)
            request_id = data.get("request_id")
            action = data.get("action")
            comment = data.get("comment", "")
            if not request_id or not action:
                return build_error_response("参数不完整")
            success, message = InvoiceRequestService.approve_request(
                int(request_id), request.user, action, comment
            )
            if not success:
                return build_error_response(message)
            return JsonResponse({"code": ApiResponseCode.CODE_SUCCESS, "msg": message})
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except Exception as e:
            logger.error(f"审批开票申请失败: {str(e)}", exc_info=True)
            return build_error_response(f"审批失败: {str(e)}")


def invoice_request_detail(request, id):
    """开票申请详情"""
    invoice_request = get_object_or_404(InvoiceRequest, id=id)
    detail = serialize_invoice_request(invoice_request)
    return render(
        request,
        "finance/invoice_request_detail.html",
        {
            "invoice_request": invoice_request,
            "detail": detail,
        },
    )


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
            keywords = (request.GET.get("keywords") or "").strip()
            page = safe_int(request.GET.get("page"), 1)
            limit = safe_int(request.GET.get("limit"), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = OrderFinanceRecord.objects.all().order_by("-create_time")

            if status:
                queryset = queryset.filter(payment_status=status)
            if keywords:
                order_ids = list(
                    CustomerOrder.objects.filter(
                        Q(order_number__icontains=keywords)
                        | Q(customer__name__icontains=keywords)
                    ).values_list("id", flat=True)
                )
                queryset = queryset.filter(order_id__in=order_ids)

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
        return render(
            request,
            "finance/statistics/dashboard.html",
            build_finance_statistics_context("reimbursement"),
        )


class InvoiceStatisticsView(LoginRequiredMixin, View):
    """发票统计"""

    login_url = "/user/login/"

    def get(self, request):
        return render(
            request,
            "finance/statistics/dashboard.html",
            build_finance_statistics_context("invoice"),
        )


class ReceiveInvoiceStatisticsView(LoginRequiredMixin, View):
    """收票统计"""

    login_url = "/user/login/"

    def get(self, request):
        return render(
            request,
            "finance/statistics/dashboard.html",
            build_finance_statistics_context("receiveinvoice"),
        )


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
        return render(
            request,
            "finance/statistics/dashboard.html",
            build_finance_statistics_context("paymentreceive"),
        )


class PaymentStatisticsView(LoginRequiredMixin, View):
    """付款统计"""

    login_url = "/user/login/"

    def get(self, request):
        return render(
            request,
            "finance/statistics/dashboard.html",
            build_finance_statistics_context("payment"),
        )


class BatchApprovalView(LoginRequiredMixin, FinancePermissionMixin, View):
    """批量审批"""

    login_url = "/user/login/"
    permission_required = "finance.approve_expense"

    def post(self, request):
        try:
            data = json.loads(request.body)
            expense_ids = data.get("expense_ids", []) or data.get("ids", [])
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
    return render(
        request,
        "finance/expense_detail.html",
        {"expense": expense, "detail": serialize_expense(expense)},
    )


def invoice_detail(request, id):
    """发票详情"""
    invoice = get_object_or_404(Invoice, id=id)
    return render(
        request,
        "finance/invoice_detail.html",
        {"invoice": invoice, "detail": serialize_invoice(invoice)},
    )


def payment_detail(request, id):
    """付款详情"""
    payment = get_object_or_404(Payment, id=id)
    return render(
        request,
        "finance/payment_detail.html",
        {"payment": payment, "detail": serialize_payment(payment)},
    )


def income_detail(request, id):
    """回款详情"""
    income = get_object_or_404(Income, id=id)
    return render(
        request,
        "finance/income_detail.html",
        {"income": income, "detail": serialize_income(income)},
    )


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
            payment_id = obj.id
            order_id = obj.order_id
            BankTransactionService.delete_related_transaction("payment", payment_id)
            obj.delete()
            has_payment = Payment.objects.filter(expense_id=expense_id).exists()
            if expense_id and not has_payment:
                Expense.objects.filter(id=expense_id).update(
                    pay_status=FinanceStatus.PAY_STATUS_PENDING,
                    pay_admin_id=0,
                    pay_time=0,
                )
            if order_id:
                FinanceLinkageService.apply_payment_to_order(Payment(order_id=order_id))

            return JsonResponse({"code": 0, "msg": "删除成功"})
        except json.JSONDecodeError:
            return build_error_response("无效的JSON数据")
        except Exception as e:
            logger.error(f"删除付款失败: {str(e)}", exc_info=True)
            return build_error_response(f"删除失败: {str(e)}")
