from django import forms
from .models import ApprovalType, ApprovalFlow, ApprovalStep


class ApprovalTypeForm(forms.ModelForm):
    class Meta:
        model = ApprovalType
        fields = ['name', 'description', 'icon', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入类型名称'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入类型描述',
                    'rows': 3}),
            'icon': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入图标类名'}),
            'sort_order': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '排序号'}),
            'is_active': forms.CheckboxInput(
                attrs={
                    'class': 'layui-input'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.code:
            instance.code = self.generate_approval_code()
        if commit:
            instance.save()
        return instance

    def generate_approval_code(self):
        last_approval = ApprovalType.objects.filter(
            code__startswith='APPROVAL_'
        ).order_by('-code').first()

        if last_approval and last_approval.code.startswith('APPROVAL_'):
            try:
                last_num = int(last_approval.code.split('_')[1])
                new_num = last_num + 1
            except (IndexError, ValueError):
                new_num = 1
        else:
            new_num = 1

        return f'APPROVAL_{new_num:03d}'


class ApprovalFlowForm(forms.ModelForm):
    class Meta:
        model = ApprovalFlow
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入流程名称'}),
            'code': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入流程代码'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入流程描述',
                    'rows': 3}),
            'is_active': forms.CheckboxInput(
                attrs={
                    'class': 'layui-input'}),
        }


class ApprovalStepForm(forms.ModelForm):
    class Meta:
        model = ApprovalStep
        fields = [
            'step_name',
            'step_order',
            'step_type',
            'action_type',
            'approver_role',
            'approver_department',
            'approver_level',
            'cc_roles',
            'cc_departments',
            'condition_field',
            'condition_operator',
            'condition_value',
            'time_limit_hours',
            'auto_approve_on_timeout',
            'description',
            'is_required',
            'is_parallel',
            'allow_delegate',
            'allow_skip']
        widgets = {
            'step_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入步骤名称'}),
            'step_order': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '步骤顺序'}),
            'step_type': forms.Select(attrs={'class': 'layui-input'}),
            'action_type': forms.Select(attrs={'class': 'layui-input'}),
            'approver_role': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入审批角色'}),
            'approver_department': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入审批部门'}),
            'approver_level': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入审批级别'}),
            'cc_roles': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '多个角色用逗号分隔'}),
            'cc_departments': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '多个部门用逗号分隔'}),
            'condition_field': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '条件字段名'}),
            'condition_operator': forms.Select(attrs={'class': 'layui-input'}, choices=[
                ('', '请选择'),
                ('>', '大于'),
                ('<', '小于'),
                ('=', '等于'),
                ('>=', '大于等于'),
                ('<=', '小于等于'),
                ('in', '包含'),
                ('not_in', '不包含'),
            ]),
            'condition_value': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '条件值'}),
            'time_limit_hours': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '处理时限(小时)'}),
            'auto_approve_on_timeout': forms.CheckboxInput(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '步骤说明', 'rows': 3}),
            'is_required': forms.CheckboxInput(attrs={'class': 'layui-input'}),
            'is_parallel': forms.CheckboxInput(attrs={'class': 'layui-input'}),
            'allow_delegate': forms.CheckboxInput(attrs={'class': 'layui-input'}),
            'allow_skip': forms.CheckboxInput(attrs={'class': 'layui-input'}),
        }
