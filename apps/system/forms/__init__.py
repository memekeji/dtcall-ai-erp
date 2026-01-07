"""
系统应用表单模块
"""

# 导入系统配置相关表单（已迁移到user应用）
from apps.user.models import SystemConfiguration, SystemModule
from apps.system.models import SystemBackup, SystemTask, BackupPolicy

# 重新定义表单以使用user应用中的模型
from django import forms

class SystemConfigForm(forms.ModelForm):
    class Meta:
        model = SystemConfiguration
        fields = ['key', 'value', 'description', 'is_active']
        widgets = {
            'key': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入配置键'}),
            'value': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入配置值', 'rows': 4}),
            'description': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入描述'}),
        }


class SystemModuleForm(forms.ModelForm):
    class Meta:
        model = SystemModule
        fields = ['name', 'code', 'description', 'icon', 'sort_order', 'is_active', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入模块名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入模块代码'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入模块描述', 'rows': 3}),
            'icon': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入图标类名'}),
            'sort_order': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '排序号'}),
            'parent': forms.Select(attrs={'class': 'layui-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = SystemModule.objects.filter(parent__isnull=True)
        self.fields['parent'].empty_label = "无父模块"
        
        # 如果是系统管理或用户管理模块，禁用is_active字段并设置为True
        if self.instance and hasattr(self.instance, 'code'):
            if self.instance.code == 'system' or '系统管理' in self.instance.name:
                self.fields['is_active'].disabled = True
                self.initial['is_active'] = True
            if self.instance.code == 'user' or self.instance.name == '用户管理':
                self.fields['is_active'].disabled = True
                self.initial['is_active'] = True


class SystemBackupForm(forms.ModelForm):
    class Meta:
        model = SystemBackup
        fields = ['name', 'backup_type', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入备份名称'}),
            'backup_type': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入备份描述', 'rows': 3}),
        }


class SystemTaskForm(forms.ModelForm):
    class Meta:
        model = SystemTask
        fields = ['name', 'command', 'cron_expression', 'description', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入任务名称'}),
            'command': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入执行命令', 'rows': 3}),
            'cron_expression': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入Cron表达式，如：0 0 * * *'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入任务描述', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'layui-input'}, choices=[
                ('enabled', '启用'),
                ('disabled', '禁用'),
                ('running', '运行中'),
                ('paused', '暂停'),
                ('error', '错误')
            ]),
        }


class BackupPolicyForm(forms.ModelForm):
    class Meta:
        model = BackupPolicy
        fields = ['name', 'is_active', 'interval', 'hour', 'minute', 'week_day', 'month_day', 'keep_count', 'backup_type', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入策略名称'}),
            'is_active': forms.Select(attrs={'class': 'layui-input'}, choices=[
                (True, '启用'),
                (False, '禁用')
            ]),
            'interval': forms.Select(attrs={'class': 'layui-input'}),
            'hour': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '0-23', 'min': 0, 'max': 23}),
            'minute': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '0-59', 'min': 0, 'max': 59}),
            'week_day': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '0-6（0表示周日）', 'min': 0, 'max': 6}),
            'month_day': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '1-31', 'min': 1, 'max': 31}),
            'keep_count': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '保留最新备份份数', 'min': 1}),
            'backup_type': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入策略描述', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 设置默认值
        if not self.instance.pk:
            self.initial['hour'] = 2
            self.initial['minute'] = 0
            self.initial['week_day'] = 0
            self.initial['month_day'] = 1
            self.initial['keep_count'] = 7
            self.initial['is_active'] = True
            self.initial['backup_type'] = 'full'

# 导入行政办公相关表单
from .admin_office_forms import *