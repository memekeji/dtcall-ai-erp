"""
财务管理模块表单
提供所有财务相关模型的表单定义
"""
from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import (
    ExpenseCategory, Expense, ExpenseItem,
    Invoice, Income, Payment,
    InvoiceRequest, OrderFinanceRecord,
    ReimbursementType, ExpenseType,
    InvoiceTypeChoices, InvoiceStatusChoices,
    PaymentMethodChoices
)


class ExpenseCategoryForm(forms.ModelForm):
    """报销类别表单"""
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'code', 'parent', 'description', 'daily_limit',
                  'monthly_limit', 'requires_approval', 'approval_threshold',
                  'approval_flow', 'sort_order', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入类别名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入类别代码'}),
            'parent': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入描述', 'rows': 3}),
            'daily_limit': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '日限额', 'step': '0.01'}),
            'monthly_limit': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '月限额', 'step': '0.01'}),
            'approval_threshold': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '审批阈值', 'step': '0.01'}),
            'approval_flow': forms.Select(attrs={'class': 'layui-input'}),
            'sort_order': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '排序'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = ExpenseCategory.objects.filter(
            status='active'
        ).exclude(id=self.instance.id) if self.instance.id else ExpenseCategory.objects.filter(status='active')
        self.fields['parent'].empty_label = '无上级类别'
        self.fields['approval_flow'].empty_label = '无需审批流程'


class ExpenseForm(forms.ModelForm):
    """报销表单"""
    class Meta:
        model = Expense
        fields = ['title', 'category', 'project', 'total_amount',
                  'expense_date', 'description', 'remark']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入报销标题'}),
            'category': forms.Select(attrs={'class': 'layui-input'}),
            'project': forms.Select(attrs={'class': 'layui-input'}),
            'total_amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '报销金额', 'step': '0.01'}),
            'expense_date': forms.DateInput(attrs={'class': 'layui-input', 'placeholder': '报销日期', 'format': '%Y-%m-%d'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入报销说明', 'rows': 3}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入备注', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ExpenseCategory.objects.filter(status='active')
        self.fields['category'].empty_label = '请选择类别'
        self.fields['project'].empty_label = '请选择项目（可选）'

    def clean_total_amount(self):
        amount = self.cleaned_data['total_amount']
        if amount <= 0:
            raise ValidationError('报销金额必须大于0')
        return amount


class ExpenseItemForm(forms.ModelForm):
    """报销明细表单"""
    class Meta:
        model = ExpenseItem
        fields = ['category', 'description', 'amount', 'expense_date',
                  'has_invoice', 'invoice_number', 'remark']
        widgets = {
            'category': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '费用说明'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '金额', 'step': '0.01'}),
            'expense_date': forms.DateInput(attrs={'class': 'layui-input', 'format': '%Y-%m-%d'}),
            'invoice_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '发票号码'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ExpenseCategory.objects.filter(status='active')
        self.fields['category'].empty_label = '请选择类别'


class InvoiceForm(forms.ModelForm):
    """发票表单"""
    class Meta:
        model = Invoice
        fields = ['title', 'customer', 'contract', 'project', 'invoice_type',
                  'amount', 'tax_rate', 'invoice_title', 'tax_number',
                  'invoice_address', 'invoice_phone', 'bank_name', 'bank_account',
                  'description', 'remark']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入发票标题'}),
            'customer': forms.Select(attrs={'class': 'layui-input'}),
            'contract': forms.Select(attrs={'class': 'layui-input'}),
            'project': forms.Select(attrs={'class': 'layui-input'}),
            'invoice_type': forms.Select(attrs={'class': 'layui-input'}, choices=InvoiceTypeChoices.CHOICES),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '发票金额', 'step': '0.01'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '税率', 'step': '0.01'}),
            'invoice_title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '开票抬头'}),
            'tax_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '纳税人识别号'}),
            'invoice_address': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '地址'}),
            'invoice_phone': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '电话'}),
            'bank_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '开户银行'}),
            'bank_account': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '银行账号'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['invoice_type'].choices = InvoiceTypeChoices.CHOICES

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('发票金额必须大于0')
        return amount


class IncomeForm(forms.ModelForm):
    """回款表单"""
    class Meta:
        model = Income
        fields = ['invoice', 'amount', 'income_date', 'payment_method',
                  'bank_name', 'bank_account', 'transaction_no', 'remark']
        widgets = {
            'invoice': forms.Select(attrs={'class': 'layui-input'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '回款金额', 'step': '0.01'}),
            'income_date': forms.DateInput(attrs={'class': 'layui-input', 'format': '%Y-%m-%d'}),
            'payment_method': forms.Select(attrs={'class': 'layui-input'}),
            'bank_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '银行名称'}),
            'bank_account': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '银行账号'}),
            'transaction_no': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '交易流水号'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment_method'].choices = PaymentMethodChoices.CHOICES

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('回款金额必须大于0')
        return amount


class PaymentForm(forms.ModelForm):
    """付款表单"""
    class Meta:
        model = Payment
        fields = ['expense', 'amount', 'payment_date', 'payment_method',
                  'bank_name', 'bank_account', 'transaction_no', 'remark']
        widgets = {
            'expense': forms.Select(attrs={'class': 'layui-input'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '付款金额', 'step': '0.01'}),
            'payment_date': forms.DateInput(attrs={'class': 'layui-input', 'format': '%Y-%m-%d'}),
            'payment_method': forms.Select(attrs={'class': 'layui-input'}),
            'bank_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '银行名称'}),
            'bank_account': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '银行账号'}),
            'transaction_no': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '交易流水号'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment_method'].choices = PaymentMethodChoices.CHOICES

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('付款金额必须大于0')
        return amount


class InvoiceRequestForm(forms.ModelForm):
    """开票申请表单"""
    class Meta:
        model = InvoiceRequest
        fields = ['order', 'amount', 'invoice_type', 'invoice_title',
                  'tax_number', 'reason']
        widgets = {
            'order': forms.Select(attrs={'class': 'layui-input'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '开票金额', 'step': '0.01'}),
            'invoice_type': forms.Select(attrs={'class': 'layui-input'}),
            'invoice_title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '开票抬头'}),
            'tax_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '纳税人识别号'}),
            'reason': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '申请理由', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['invoice_type'].choices = InvoiceTypeChoices.CHOICES

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('开票金额必须大于0')
        return amount


class OrderFinanceRecordForm(forms.ModelForm):
    """订单财务记录表单"""
    class Meta:
        model = OrderFinanceRecord
        fields = ['order', 'total_amount', 'paid_amount', 'payment_status', 'due_date']
        widgets = {
            'order': forms.Select(attrs={'class': 'layui-input'}),
            'total_amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '订单金额', 'step': '0.01'}),
            'paid_amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '已付金额', 'step': '0.01'}),
            'payment_status': forms.Select(attrs={'class': 'layui-input'}),
            'due_date': forms.DateInput(attrs={'class': 'layui-input', 'format': '%Y-%m-%d'}),
        }


class ReimbursementTypeForm(forms.ModelForm):
    """报销类型表单"""
    class Meta:
        model = ReimbursementType
        fields = ['name', 'code', 'description', 'max_amount',
                  'requires_approval', 'approval_flow', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入报销类型名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入类型代码'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入类型描述', 'rows': 3}),
            'max_amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '最大报销金额', 'step': '0.01'}),
            'approval_flow': forms.Select(attrs={'class': 'layui-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['approval_flow'].queryset = []
        self.fields['approval_flow'].empty_label = "无需审批流程"


class ExpenseTypeForm(forms.ModelForm):
    """费用类型表单"""
    class Meta:
        model = ExpenseType
        fields = ['name', 'code', 'parent', 'description', 'budget_control', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入费用类型名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入费用代码'}),
            'parent': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入费用描述', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = ExpenseType.objects.filter(status='active')
        self.fields['parent'].empty_label = "无上级费用类型"


class ExpenseSubmitForm(forms.Form):
    """报销提交表单"""
    expense_id = forms.IntegerField(widget=forms.HiddenInput())


class ExpenseApproveForm(forms.Form):
    """报销审批表单"""
    expense_id = forms.IntegerField(widget=forms.HiddenInput())
    action = forms.ChoiceField(choices=[('approved', '通过'), ('rejected', '驳回')])
    approved_amount = forms.DecimalField(required=False, min_value=Decimal('0'), widget=forms.NumberInput(attrs={'step': '0.01'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))


class ExpensePaymentForm(forms.Form):
    """报销付款表单"""
    expense_id = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(min_value=Decimal('0.01'), widget=forms.NumberInput(attrs={'step': '0.01'}))
    payment_method = forms.ChoiceField(choices=PaymentMethodChoices.CHOICES)
    bank_name = forms.CharField(required=False, max_length=100)
    bank_account = forms.CharField(required=False, max_length=100)
    transaction_no = forms.CharField(required=False, max_length=100)
    remark = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))


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
