from django import forms
from .models import ProjectStage, ProjectCategory, WorkType


class ProjectStageForm(forms.ModelForm):
    class Meta:
        model = ProjectStage
        fields = ['name', 'code', 'description', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入阶段名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入阶段代码'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入阶段描述', 'rows': 3}),
            'sort_order': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '排序号'}),
        }


class ProjectCategoryForm(forms.ModelForm):
    class Meta:
        model = ProjectCategory
        fields = ['name', 'code', 'description', 'color', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入分类名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入分类代码'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入分类描述', 'rows': 3}),
            'color': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '颜色标识，如：#FF0000'}),
            'sort_order': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '排序号'}),
        }


class WorkTypeForm(forms.ModelForm):
    class Meta:
        model = WorkType
        fields = ['name', 'code', 'description', 'hourly_rate', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入类别名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入类别代码'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入类别描述', 'rows': 3}),
            'hourly_rate': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '小时费率', 'step': '0.01'}),
            'sort_order': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '排序号'}),
        }
