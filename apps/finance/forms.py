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
    PaymentMethodChoices,
)


INVOICE_TYPE_CHOICES = [
    (1, '增值税专用发票'),
    (2, '普通发票'),
    (3, '电子发票'),
]


class ExpenseForm(forms.ModelForm):
    """报销表单"""
    expense_time_input = forms.DateField(
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'})
    )

    class Meta:
        model = Expense
        fields = [
            'code',
            'subject_id',
            'project_id',
            'cost',
            'income_month',
            'remark',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入报销编码'}),
            'subject_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '报销主体ID'}),
            'project_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '项目ID'}),
            'cost': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '报销金额', 'step': '0.01'}),
            'income_month': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '入账月份，如 202604'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.expense_time:
            from datetime import datetime
            self.fields['expense_time_input'].initial = datetime.fromtimestamp(
                int(self.instance.expense_time)
            ).strftime('%Y-%m-%d')

    def clean_cost(self):
        amount = self.cleaned_data['cost']
        if amount <= 0:
            raise ValidationError('报销金额必须大于0')
        return amount

    def save(self, commit=True):
        instance = super().save(commit=False)
        expense_time_input = self.cleaned_data.get('expense_time_input')
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
            'code',
            'customer_id',
            'contract_id',
            'project_id',
            'amount',
            'invoice_type',
            'invoice_title',
            'invoice_tax',
            'invoice_phone',
            'invoice_address',
            'invoice_bank',
            'invoice_account',
            'remark',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入发票号码'}),
            'customer_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '客户ID'}),
            'contract_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '合同ID'}),
            'project_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '项目ID'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '发票金额', 'step': '0.01'}),
            'invoice_type': forms.Select(attrs={'class': 'layui-input'}, choices=INVOICE_TYPE_CHOICES),
            'invoice_title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '开票抬头'}),
            'invoice_tax': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '纳税人识别号'}),
            'invoice_phone': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '联系电话'}),
            'invoice_address': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '开户地址'}),
            'invoice_bank': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '开户银行'}),
            'invoice_account': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '银行账号'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('发票金额必须大于0')
        return amount


class IncomeForm(forms.ModelForm):
    """回款表单"""
    class Meta:
        model = Income
        fields = ['invoice_id', 'amount', 'income_date', 'file_ids', 'remark']
        widgets = {
            'invoice_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '发票ID'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '回款金额', 'step': '0.01'}),
            'income_date': forms.DateTimeInput(attrs={'class': 'layui-input', 'type': 'datetime-local'}),
            'file_ids': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '附件ID，多个用逗号分隔'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('回款金额必须大于0')
        return amount


class PaymentForm(forms.ModelForm):
    """付款表单"""
    class Meta:
        model = Payment
        fields = ['expense_id', 'amount', 'payment_date', 'file_ids', 'remark']
        widgets = {
            'expense_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '报销ID'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '付款金额', 'step': '0.01'}),
            'payment_date': forms.DateTimeInput(attrs={'class': 'layui-input', 'type': 'datetime-local'}),
            'file_ids': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '附件ID，多个用逗号分隔'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('付款金额必须大于0')
        return amount


class InvoiceRequestForm(forms.ModelForm):
    """开票申请表单"""
    class Meta:
        model = InvoiceRequest
        fields = ['order_id', 'amount', 'invoice_type', 'invoice_title', 'tax_number', 'reason', 'remark']
        widgets = {
            'order_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '订单ID'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '开票金额', 'step': '0.01'}),
            'invoice_type': forms.Select(attrs={'class': 'layui-input'}, choices=INVOICE_TYPE_CHOICES),
            'invoice_title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '开票抬头'}),
            'tax_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '纳税人识别号'}),
            'reason': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 4}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('开票金额必须大于0')
        return amount


class OrderFinanceRecordForm(forms.ModelForm):
    """订单财务记录表单"""
    class Meta:
        model = OrderFinanceRecord
        fields = ['order_id', 'total_amount', 'paid_amount', 'payment_status', 'due_date', 'remark']
        widgets = {
            'order_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '订单ID'}),
            'total_amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '订单金额', 'step': '0.01'}),
            'paid_amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '已付金额', 'step': '0.01'}),
            'payment_status': forms.Select(attrs={'class': 'layui-input'}),
            'due_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }


class ExpenseSubmitForm(forms.Form):
    """报销提交表单"""
    expense_id = forms.IntegerField(widget=forms.HiddenInput())


class ExpenseApproveForm(forms.Form):
    """报销审批表单"""
    expense_id = forms.IntegerField(widget=forms.HiddenInput())
    action = forms.ChoiceField(
        choices=[('approved', '通过'), ('rejected', '驳回')])
    approved_amount = forms.DecimalField(
        required=False,
        min_value=Decimal('0'),
        widget=forms.NumberInput(
            attrs={
                'step': '0.01'}))
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 3}))


class ExpensePaymentForm(forms.Form):
    """报销付款表单"""
    expense_id = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(
            attrs={
                'step': '0.01'}))
    payment_method = forms.ChoiceField(choices=PaymentMethodChoices.CHOICES)
    bank_name = forms.CharField(required=False, max_length=100)
    bank_account = forms.CharField(required=False, max_length=100)
    transaction_no = forms.CharField(required=False, max_length=100)
    remark = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 2}))


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
    action = forms.ChoiceField(choices=[('approve', '通过'), ('reject', '驳回')])
