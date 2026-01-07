from django import forms
from apps.user.models.position import Position
from django.utils.translation import gettext_lazy as _

class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ['title', 'did', 'desc', 'sort', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'did': forms.NumberInput(attrs={'class': 'form-control'}),
            'desc': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'sort': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}, choices=[(1, '启用'), (0, '禁用')]),
        }
        labels = {
            'title': _('岗位名称'),
            'did': _('部门ID'),
            'desc': _('岗位描述'),
            'sort': _('排序'),
            'status': _('启用状态'),
        }