"""
财务管理模块表单
仅保留与当前数据库模型一致的表单定义。
"""

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import (
    Expense,
    Invoice,
    Income,
    Payment,
    InvoiceRequest,
    OrderFinanceRecord,
    FinanceAccount,
    FinanceBudget,
    AccountsReceivable,
    AccountsPayable,
    BankTransaction,
    BankReconciliation,
    LedgerVoucher,
    TaxRecord,
    FixedAsset,
    CostAllocation,
    FinancialPeriodClose,
    FinancialReport,
    ChartOfAccount,
    LedgerVoucherLine,
    CashFlowPlan,
    FinancialRatio,
    ExpenseAccrual,
)


INVOICE_TYPE_CHOICES = [
    (1, "增值税专用发票"),
    (2, "普通发票"),
    (3, "电子发票"),
]


class ExpenseForm(forms.ModelForm):
    """报销表单"""

    expense_time_input = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"class": "layui-input", "type": "date"}),
    )

    class Meta:
        model = Expense
        fields = [
            "code",
            "subject_id",
            "project_id",
            "cost",
            "income_month",
            "file_ids",
            "remark",
        ]
        widgets = {
            "code": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "请输入报销编码"}
            ),
            "subject_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "报销主体ID"}
            ),
            "project_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "项目ID"}
            ),
            "cost": forms.NumberInput(
                attrs={
                    "class": "layui-input",
                    "placeholder": "报销金额",
                    "step": "0.01",
                }
            ),
            "income_month": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "入账月份，如 202604"}
            ),
            "file_ids": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "附件ID，多个用逗号分隔"}
            ),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.expense_time:
            from datetime import datetime

            self.fields["expense_time_input"].initial = datetime.fromtimestamp(
                int(self.instance.expense_time)
            ).strftime("%Y-%m-%d")

    def clean_cost(self):
        amount = self.cleaned_data["cost"]
        if amount <= 0:
            raise ValidationError("报销金额必须大于0")
        return amount

    def save(self, commit=True):
        instance = super().save(commit=False)
        expense_time_input = self.cleaned_data.get("expense_time_input")
        if expense_time_input:
            import time

            instance.expense_time = int(time.mktime(expense_time_input.timetuple()))
        if commit:
            instance.save()
        return instance


class InvoiceForm(forms.ModelForm):
    """发票表单"""

    class Meta:
        model = Invoice
        fields = [
            "code",
            "customer_id",
            "contract_id",
            "project_id",
            "amount",
            "invoice_type",
            "invoice_title",
            "invoice_tax",
            "invoice_phone",
            "invoice_address",
            "invoice_bank",
            "invoice_account",
            "remark",
        ]
        widgets = {
            "code": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "请输入发票号码"}
            ),
            "customer_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "客户ID"}
            ),
            "contract_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "合同ID"}
            ),
            "project_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "项目ID"}
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "layui-input",
                    "placeholder": "发票金额",
                    "step": "0.01",
                }
            ),
            "invoice_type": forms.Select(
                attrs={"class": "layui-input"}, choices=INVOICE_TYPE_CHOICES
            ),
            "invoice_title": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "开票抬头"}
            ),
            "invoice_tax": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "纳税人识别号"}
            ),
            "invoice_phone": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "联系电话"}
            ),
            "invoice_address": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "开户地址"}
            ),
            "invoice_bank": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "开户银行"}
            ),
            "invoice_account": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "银行账号"}
            ),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 3}),
        }

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise ValidationError("发票金额必须大于0")
        return amount

    def clean_customer_id(self):
        customer_id = self.cleaned_data.get("customer_id") or 0
        if customer_id <= 0:
            raise ValidationError("请选择关联客户")
        return customer_id


class IncomeForm(forms.ModelForm):
    """回款表单"""

    account_id = forms.IntegerField(required=False)

    class Meta:
        model = Income
        fields = ["invoice_id", "account_id", "amount", "income_date", "file_ids", "remark"]
        widgets = {
            "invoice_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "发票ID"}
            ),
            "account_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "资金账户ID"}
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "layui-input",
                    "placeholder": "回款金额",
                    "step": "0.01",
                }
            ),
            "income_date": forms.DateTimeInput(
                attrs={"class": "layui-input", "type": "datetime-local"}
            ),
            "file_ids": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "附件ID，多个用逗号分隔"}
            ),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 3}),
        }

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise ValidationError("回款金额必须大于0")
        return amount


class PaymentForm(forms.ModelForm):
    """付款表单"""

    account_id = forms.IntegerField(required=False)
    customer_id = forms.IntegerField(required=False)
    order_id = forms.IntegerField(required=False)
    purchase_order_id = forms.IntegerField(required=False)
    purchase_contract_id = forms.IntegerField(required=False)
    project_id = forms.IntegerField(required=False)

    class Meta:
        model = Payment
        fields = [
            "expense_id",
            "account_id",
            "customer_id",
            "order_id",
            "purchase_order_id",
            "purchase_contract_id",
            "project_id",
            "amount",
            "payment_date",
            "file_ids",
            "remark",
        ]
        widgets = {
            "expense_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "报销ID"}
            ),
            "account_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "资金账户ID"}
            ),
            "customer_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "客户ID"}
            ),
            "order_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "订单ID"}
            ),
            "purchase_order_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "采购订单ID"}
            ),
            "purchase_contract_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "采购合同ID"}
            ),
            "project_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "项目ID"}
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "layui-input",
                    "placeholder": "付款金额",
                    "step": "0.01",
                }
            ),
            "payment_date": forms.DateTimeInput(
                attrs={"class": "layui-input", "type": "datetime-local"}
            ),
            "file_ids": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "附件ID，多个用逗号分隔"}
            ),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        relation_fields = [
            "expense_id",
            "customer_id",
            "order_id",
            "purchase_order_id",
            "purchase_contract_id",
            "project_id",
        ]
        for field_name in relation_fields + ["file_ids"]:
            self.fields[field_name].required = False

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise ValidationError("付款金额必须大于0")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        relation_values = [
            cleaned_data.get("expense_id"),
            cleaned_data.get("customer_id"),
            cleaned_data.get("order_id"),
            cleaned_data.get("purchase_order_id"),
            cleaned_data.get("purchase_contract_id"),
            cleaned_data.get("project_id"),
        ]
        if not any(value for value in relation_values if value):
            raise ValidationError("至少关联一项业务对象")
        return cleaned_data


class InvoiceRequestForm(forms.ModelForm):
    """开票申请表单"""

    class Meta:
        model = InvoiceRequest
        fields = [
            "order_id",
            "amount",
            "invoice_type",
            "invoice_title",
            "tax_number",
            "reason",
            "remark",
        ]
        widgets = {
            "order_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "订单ID"}
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "layui-input",
                    "placeholder": "开票金额",
                    "step": "0.01",
                }
            ),
            "invoice_type": forms.Select(
                attrs={"class": "layui-input"}, choices=INVOICE_TYPE_CHOICES
            ),
            "invoice_title": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "开票抬头"}
            ),
            "tax_number": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "纳税人识别号"}
            ),
            "reason": forms.Textarea(attrs={"class": "layui-textarea", "rows": 4}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise ValidationError("开票金额必须大于0")
        return amount

    def clean_order_id(self):
        order_id = self.cleaned_data.get("order_id") or 0
        if order_id <= 0:
            raise ValidationError("请选择关联订单")
        return order_id


class OrderFinanceRecordForm(forms.ModelForm):
    """订单财务记录表单"""

    class Meta:
        model = OrderFinanceRecord
        fields = [
            "order_id",
            "total_amount",
            "paid_amount",
            "payment_status",
            "due_date",
            "remark",
        ]
        widgets = {
            "order_id": forms.NumberInput(
                attrs={"class": "layui-input", "placeholder": "订单ID"}
            ),
            "total_amount": forms.NumberInput(
                attrs={
                    "class": "layui-input",
                    "placeholder": "订单金额",
                    "step": "0.01",
                }
            ),
            "paid_amount": forms.NumberInput(
                attrs={
                    "class": "layui-input",
                    "placeholder": "已付金额",
                    "step": "0.01",
                }
            ),
            "payment_status": forms.Select(attrs={"class": "layui-input"}),
            "due_date": forms.DateInput(attrs={"class": "layui-input", "type": "date"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }


class FinanceAccountForm(forms.ModelForm):
    """资金账户表单"""

    class Meta:
        model = FinanceAccount
        fields = [
            "name",
            "account_type",
            "bank_name",
            "account_no",
            "currency",
            "opening_balance",
            "current_balance",
            "status",
            "remark",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "layui-input"}),
            "account_type": forms.Select(attrs={"class": "layui-input"}),
            "bank_name": forms.TextInput(attrs={"class": "layui-input"}),
            "account_no": forms.TextInput(attrs={"class": "layui-input"}),
            "currency": forms.TextInput(attrs={"class": "layui-input"}),
            "opening_balance": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "current_balance": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean_currency(self):
        currency = (self.cleaned_data.get("currency") or "CNY").strip().upper()
        if len(currency) > 10:
            raise ValidationError("币种长度不能超过10位")
        return currency


class FinanceBudgetForm(forms.ModelForm):
    """预算管理表单"""

    class Meta:
        model = FinanceBudget
        fields = [
            "name",
            "department_id",
            "project_id",
            "period_type",
            "start_date",
            "end_date",
            "budget_amount",
            "used_amount",
            "warning_rate",
            "status",
            "remark",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "layui-input"}),
            "department_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "project_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "period_type": forms.Select(attrs={"class": "layui-input"}),
            "start_date": forms.DateInput(
                attrs={"class": "layui-input", "type": "date"}
            ),
            "end_date": forms.DateInput(attrs={"class": "layui-input", "type": "date"}),
            "budget_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "used_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "warning_rate": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        budget_amount = cleaned_data.get("budget_amount") or Decimal("0")
        used_amount = cleaned_data.get("used_amount") or Decimal("0")
        warning_rate = cleaned_data.get("warning_rate") or Decimal("0")
        if start_date and end_date and start_date > end_date:
            raise ValidationError("预算开始日期不能晚于结束日期")
        if budget_amount <= 0:
            raise ValidationError("预算金额必须大于0")
        if used_amount < 0:
            raise ValidationError("已用金额不能小于0")
        if used_amount > budget_amount:
            raise ValidationError("已用金额不能大于预算金额")
        if warning_rate < 0 or warning_rate > 100:
            raise ValidationError("预警比例必须在0到100之间")
        return cleaned_data


class AccountsReceivableForm(forms.ModelForm):
    """应收账款表单"""

    class Meta:
        model = AccountsReceivable
        fields = [
            "code",
            "customer_id",
            "order_id",
            "invoice_id",
            "amount",
            "received_amount",
            "due_date",
            "status",
            "remark",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "layui-input"}),
            "customer_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "order_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "invoice_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "amount": forms.NumberInput(attrs={"class": "layui-input", "step": "0.01"}),
            "received_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "due_date": forms.DateInput(attrs={"class": "layui-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get("amount") or Decimal("0")
        received_amount = cleaned_data.get("received_amount") or Decimal("0")
        if amount <= 0:
            raise ValidationError("应收金额必须大于0")
        if received_amount < 0:
            raise ValidationError("已收金额不能小于0")
        if received_amount > amount:
            raise ValidationError("已收金额不能大于应收金额")
        return cleaned_data


class AccountsPayableForm(forms.ModelForm):
    """应付账款表单"""

    class Meta:
        model = AccountsPayable
        fields = [
            "code",
            "supplier_id",
            "expense_id",
            "amount",
            "paid_amount",
            "due_date",
            "status",
            "remark",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "layui-input"}),
            "supplier_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "expense_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "amount": forms.NumberInput(attrs={"class": "layui-input", "step": "0.01"}),
            "paid_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "due_date": forms.DateInput(attrs={"class": "layui-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get("amount") or Decimal("0")
        paid_amount = cleaned_data.get("paid_amount") or Decimal("0")
        if amount <= 0:
            raise ValidationError("应付金额必须大于0")
        if paid_amount < 0:
            raise ValidationError("已付金额不能小于0")
        if paid_amount > amount:
            raise ValidationError("已付金额不能大于应付金额")
        return cleaned_data


class BankTransactionForm(forms.ModelForm):
    """银行流水表单"""

    class Meta:
        model = BankTransaction
        fields = [
            "account",
            "transaction_date",
            "direction",
            "amount",
            "counterparty",
            "transaction_no",
            "purpose",
            "match_status",
            "related_type",
            "related_id",
            "remark",
        ]
        widgets = {
            "account": forms.Select(attrs={"class": "layui-input"}),
            "transaction_date": forms.DateTimeInput(
                attrs={"class": "layui-input", "type": "datetime-local"}
            ),
            "direction": forms.Select(attrs={"class": "layui-input"}),
            "amount": forms.NumberInput(attrs={"class": "layui-input", "step": "0.01"}),
            "counterparty": forms.TextInput(attrs={"class": "layui-input"}),
            "transaction_no": forms.TextInput(attrs={"class": "layui-input"}),
            "purpose": forms.TextInput(attrs={"class": "layui-input"}),
            "match_status": forms.Select(attrs={"class": "layui-input"}),
            "related_type": forms.TextInput(attrs={"class": "layui-input"}),
            "related_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get("amount") or Decimal("0")
        if amount <= 0:
            raise ValidationError("流水金额必须大于0")
        return amount


class BankReconciliationForm(forms.ModelForm):
    """银行对账表单"""

    class Meta:
        model = BankReconciliation
        fields = [
            "account",
            "period",
            "book_balance",
            "bank_balance",
            "status",
            "remark",
        ]
        widgets = {
            "account": forms.Select(attrs={"class": "layui-input"}),
            "period": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "例如 2026-06"}
            ),
            "book_balance": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "bank_balance": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }


class LedgerVoucherForm(forms.ModelForm):
    """总账凭证表单"""

    class Meta:
        model = LedgerVoucher
        fields = [
            "voucher_no",
            "voucher_date",
            "summary",
            "debit_amount",
            "credit_amount",
            "source_type",
            "source_id",
            "status",
            "remark",
        ]
        widgets = {
            "voucher_no": forms.TextInput(attrs={"class": "layui-input"}),
            "voucher_date": forms.DateInput(
                attrs={"class": "layui-input", "type": "date"}
            ),
            "summary": forms.TextInput(attrs={"class": "layui-input"}),
            "debit_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "credit_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "source_type": forms.TextInput(attrs={"class": "layui-input"}),
            "source_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        debit = cleaned_data.get("debit_amount") or Decimal("0")
        credit = cleaned_data.get("credit_amount") or Decimal("0")
        if debit != credit:
            raise ValidationError("凭证借贷金额必须相等")
        return cleaned_data


class TaxRecordForm(forms.ModelForm):
    """税务管理表单"""

    class Meta:
        model = TaxRecord
        fields = [
            "period",
            "tax_type",
            "taxable_amount",
            "tax_rate",
            "tax_amount",
            "declared_date",
            "paid_date",
            "due_date",
            "status",
            "remark",
        ]
        widgets = {
            "period": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "例如 2026-06"}
            ),
            "tax_type": forms.Select(attrs={"class": "layui-input"}),
            "taxable_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "tax_rate": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "tax_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "declared_date": forms.DateInput(
                attrs={"class": "layui-input", "type": "date"}
            ),
            "paid_date": forms.DateInput(
                attrs={"class": "layui-input", "type": "date"}
            ),
            "due_date": forms.DateInput(attrs={"class": "layui-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        taxable_amount = cleaned_data.get("taxable_amount") or Decimal("0")
        tax_rate = cleaned_data.get("tax_rate") or Decimal("0")
        tax_amount = cleaned_data.get("tax_amount") or Decimal("0")
        if taxable_amount < 0:
            raise ValidationError("计税金额不能小于0")
        if tax_rate < 0 or tax_rate > 100:
            raise ValidationError("税率必须在0到100之间")
        if tax_amount < 0:
            raise ValidationError("税额不能小于0")
        return cleaned_data


class FixedAssetForm(forms.ModelForm):
    """固定资产财务档案表单"""

    class Meta:
        model = FixedAsset
        fields = [
            "asset",
            "salvage_value",
            "depreciation_months",
            "accumulated_depreciation",
            "status",
            "remark",
        ]
        widgets = {
            "asset": forms.Select(attrs={"class": "layui-input"}),
            "salvage_value": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "depreciation_months": forms.NumberInput(attrs={"class": "layui-input"}),
            "accumulated_depreciation": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        asset = cleaned_data.get("asset")
        original_value = asset.purchase_price if asset else Decimal("0")
        salvage_value = cleaned_data.get("salvage_value") or Decimal("0")
        accumulated = cleaned_data.get("accumulated_depreciation") or Decimal("0")
        months = cleaned_data.get("depreciation_months") or 0
        if not asset:
            raise ValidationError("请选择行政固定资产")
        if FixedAsset.objects.filter(asset=asset).exclude(pk=self.instance.pk).exists():
            raise ValidationError("该行政固定资产已存在财务档案")
        if original_value <= 0:
            raise ValidationError("行政资产购买价格必须大于0")
        if salvage_value < 0 or salvage_value > original_value:
            raise ValidationError("残值不能小于0且不能大于资产原值")
        if accumulated < 0 or accumulated > original_value:
            raise ValidationError("累计折旧不能小于0且不能大于资产原值")
        if months <= 0:
            raise ValidationError("折旧月数必须大于0")
        return cleaned_data


class CostAllocationForm(forms.ModelForm):
    """成本分摊表单"""

    class Meta:
        model = CostAllocation
        fields = [
            "allocation_no",
            "period",
            "source_type",
            "source_id",
            "total_amount",
            "department_id",
            "project_id",
            "allocation_basis",
            "status",
            "remark",
        ]
        widgets = {
            "allocation_no": forms.TextInput(attrs={"class": "layui-input"}),
            "period": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "例如 2026-06"}
            ),
            "source_type": forms.TextInput(attrs={"class": "layui-input"}),
            "source_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "total_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "department_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "project_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "allocation_basis": forms.TextInput(attrs={"class": "layui-input"}),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean_total_amount(self):
        amount = self.cleaned_data.get("total_amount") or Decimal("0")
        if amount <= 0:
            raise ValidationError("分摊总额必须大于0")
        return amount


class FinancialPeriodCloseForm(forms.ModelForm):
    """期间结账表单"""

    class Meta:
        model = FinancialPeriodClose
        fields = [
            "period",
            "income_amount",
            "expense_amount",
            "profit_amount",
            "status",
            "remark",
        ]
        widgets = {
            "period": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "例如 2026-06"}
            ),
            "income_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "expense_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "profit_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }


class FinancialReportForm(forms.ModelForm):
    """财务报表表单"""

    class Meta:
        model = FinancialReport
        fields = [
            "report_no",
            "report_type",
            "period",
            "total_assets",
            "total_liabilities",
            "total_equity",
            "revenue_amount",
            "cost_amount",
            "profit_amount",
            "status",
            "remark",
        ]
        widgets = {
            "report_no": forms.TextInput(attrs={"class": "layui-input"}),
            "report_type": forms.Select(attrs={"class": "layui-input"}),
            "period": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "例如 2026-06"}
            ),
            "total_assets": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "total_liabilities": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "total_equity": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "revenue_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "cost_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "profit_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }


class ChartOfAccountForm(forms.ModelForm):
    """会计科目表单"""

    class Meta:
        model = ChartOfAccount
        fields = [
            "code",
            "name",
            "account_type",
            "parent",
            "level",
            "is_leaf",
            "balance_direction",
            "status",
            "remark",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "layui-input"}),
            "name": forms.TextInput(attrs={"class": "layui-input"}),
            "account_type": forms.Select(attrs={"class": "layui-input"}),
            "parent": forms.Select(attrs={"class": "layui-input"}),
            "level": forms.NumberInput(attrs={"class": "layui-input"}),
            "is_leaf": forms.CheckboxInput(attrs={"lay-skin": "switch"}),
            "balance_direction": forms.Select(attrs={"class": "layui-input"}),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        parent = cleaned_data.get("parent")
        level = cleaned_data.get("level") or 1
        if parent and self.instance.pk == parent.pk:
            raise ValidationError("上级科目不能选择自身")
        if level <= 0:
            raise ValidationError("科目级次必须大于0")
        return cleaned_data


class LedgerVoucherLineForm(forms.ModelForm):
    """凭证明细表单"""

    class Meta:
        model = LedgerVoucherLine
        fields = [
            "voucher",
            "account",
            "summary",
            "debit_amount",
            "credit_amount",
            "auxiliary_type",
            "auxiliary_id",
            "remark",
        ]
        widgets = {
            "voucher": forms.Select(attrs={"class": "layui-input"}),
            "account": forms.Select(attrs={"class": "layui-input"}),
            "summary": forms.TextInput(attrs={"class": "layui-input"}),
            "debit_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "credit_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "auxiliary_type": forms.TextInput(attrs={"class": "layui-input"}),
            "auxiliary_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        debit = cleaned_data.get("debit_amount") or Decimal("0")
        credit = cleaned_data.get("credit_amount") or Decimal("0")
        if debit < 0 or credit < 0:
            raise ValidationError("借贷金额不能小于0")
        if debit == 0 and credit == 0:
            raise ValidationError("借方金额和贷方金额不能同时为0")
        if debit > 0 and credit > 0:
            raise ValidationError("同一明细不能同时填写借方和贷方金额")
        return cleaned_data


class CashFlowPlanForm(forms.ModelForm):
    """现金流计划表单"""

    class Meta:
        model = CashFlowPlan
        fields = [
            "plan_no",
            "flow_type",
            "category",
            "expected_date",
            "expected_amount",
            "actual_amount",
            "account",
            "source_type",
            "source_id",
            "status",
            "remark",
        ]
        widgets = {
            "plan_no": forms.TextInput(attrs={"class": "layui-input"}),
            "flow_type": forms.Select(attrs={"class": "layui-input"}),
            "category": forms.TextInput(attrs={"class": "layui-input"}),
            "expected_date": forms.DateInput(
                attrs={"class": "layui-input", "type": "date"}
            ),
            "expected_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "actual_amount": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.01"}
            ),
            "account": forms.Select(attrs={"class": "layui-input"}),
            "source_type": forms.TextInput(attrs={"class": "layui-input"}),
            "source_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        expected_amount = cleaned_data.get("expected_amount") or Decimal("0")
        actual_amount = cleaned_data.get("actual_amount") or Decimal("0")
        if expected_amount <= 0:
            raise ValidationError("预计金额必须大于0")
        if actual_amount < 0:
            raise ValidationError("实际金额不能小于0")
        return cleaned_data


class FinancialRatioForm(forms.ModelForm):
    """财务指标表单"""

    class Meta:
        model = FinancialRatio
        fields = [
            "period",
            "ratio_type",
            "name",
            "value",
            "target_value",
            "warning_value",
            "unit",
            "status",
            "remark",
        ]
        widgets = {
            "period": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "例如 2026-06"}
            ),
            "ratio_type": forms.Select(attrs={"class": "layui-input"}),
            "name": forms.TextInput(attrs={"class": "layui-input"}),
            "value": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.0001"}
            ),
            "target_value": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.0001"}
            ),
            "warning_value": forms.NumberInput(
                attrs={"class": "layui-input", "step": "0.0001"}
            ),
            "unit": forms.TextInput(attrs={"class": "layui-input"}),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }


class ExpenseAccrualForm(forms.ModelForm):
    """费用计提表单"""

    class Meta:
        model = ExpenseAccrual
        fields = [
            "accrual_no",
            "period",
            "expense_type",
            "amount",
            "department_id",
            "project_id",
            "voucher",
            "status",
            "remark",
        ]
        widgets = {
            "accrual_no": forms.TextInput(attrs={"class": "layui-input"}),
            "period": forms.TextInput(
                attrs={"class": "layui-input", "placeholder": "例如 2026-06"}
            ),
            "expense_type": forms.TextInput(attrs={"class": "layui-input"}),
            "amount": forms.NumberInput(attrs={"class": "layui-input", "step": "0.01"}),
            "department_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "project_id": forms.NumberInput(attrs={"class": "layui-input"}),
            "voucher": forms.Select(attrs={"class": "layui-input"}),
            "status": forms.Select(attrs={"class": "layui-input"}),
            "remark": forms.Textarea(attrs={"class": "layui-textarea", "rows": 2}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get("amount") or Decimal("0")
        if amount <= 0:
            raise ValidationError("计提金额必须大于0")
        return amount


class ExpenseSubmitForm(forms.Form):
    """报销提交表单"""

    expense_id = forms.IntegerField(widget=forms.HiddenInput())


class ExpenseApproveForm(forms.Form):
    """报销审批表单"""

    expense_id = forms.IntegerField(widget=forms.HiddenInput())
    action = forms.ChoiceField(choices=[("approved", "通过"), ("rejected", "驳回")])
    approved_amount = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        widget=forms.NumberInput(attrs={"step": "0.01"}),
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class ExpensePaymentForm(forms.Form):
    """报销付款表单"""

    expense_id = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        min_value=Decimal("0.01"), widget=forms.NumberInput(attrs={"step": "0.01"})
    )
    remark = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class InvoiceIssueForm(forms.Form):
    """发票开具表单"""

    invoice_id = forms.IntegerField(widget=forms.HiddenInput())


class IncomeVerifyForm(forms.Form):
    """回款核销表单"""

    income_id = forms.IntegerField(widget=forms.HiddenInput())
    verify_data = forms.JSONField(widget=forms.HiddenInput())


class BatchApprovalForm(forms.Form):
    """批量审批表单"""

    expense_ids = forms.JSONField(widget=forms.HiddenInput())
    action = forms.ChoiceField(choices=[("approve", "通过"), ("reject", "驳回")])
