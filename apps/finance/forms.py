from django import forms
from .models import ReimbursementType, ExpenseType
from apps.approval.models import ApprovalFlow


class ReimbursementTypeForm(forms.ModelForm):
    class Meta:
        model = ReimbursementType
        fields = ['name', 'code', 'description', 'max_amount', 'requires_approval', 'approval_flow', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入报销类型名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入类型代码'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入类型描述', 'rows': 3}),
            'max_amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '最大报销金额', 'step': '0.01'}),
            'approval_flow': forms.Select(attrs={'class': 'layui-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['approval_flow'].queryset = ApprovalFlow.objects.filter(is_active=True)
        self.fields['approval_flow'].empty_label = "无需审批流程"


class ExpenseTypeForm(forms.ModelForm):
    class Meta:
        model = ExpenseType
        fields = ['name', 'code', 'parent', 'description', 'budget_control', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入费用类型名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入费用代码'}),
            'parent': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入费用描述', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = ExpenseType.objects.all()
        self.fields['parent'].empty_label = "无上级费用类型"
