from django import forms
from django.contrib.auth import get_user_model
from apps.user.models import Admin
from .models import (
    DiskFile, DiskFolder, DiskShare, DiskPermission
)

User = get_user_model()


class DiskFolderForm(forms.ModelForm):
    class Meta:
        model = DiskFolder
        fields = ['name', 'parent', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入文件夹名称'}),
            'parent': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '文件夹描述', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['parent'].queryset = DiskFolder.objects.filter(
                owner=user, is_deleted=False
            ).order_by('name')
            self.fields['parent'].empty_label = "根目录"


class DiskFileUploadForm(forms.ModelForm):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'layui-input', 'accept': '*/*'})
    )
    
    class Meta:
        model = DiskFile
        fields = ['name', 'folder', 'description', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '文件名称（可选，默认使用原文件名）'}),
            'folder': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '文件描述', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['folder'].queryset = DiskFolder.objects.filter(
                owner=user, is_deleted=False
            ).order_by('name')
            self.fields['folder'].empty_label = "根目录"


class DiskShareForm(forms.ModelForm):
    class Meta:
        model = DiskShare
        fields = ['share_type', 'password', 'expire_time', 'download_limit', 'description']
        widgets = {
            'share_type': forms.Select(attrs={'class': 'layui-input'}),
            'password': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '分享密码（可选）'}),
            'expire_time': forms.DateTimeInput(attrs={'class': 'layui-input', 'type': 'datetime-local'}),
            'download_limit': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '下载次数限制（0表示无限制）'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '分享说明', 'rows': 3}),
        }


class DiskPermissionForm(forms.ModelForm):
    class Meta:
        model = DiskPermission
        fields = ['user', 'permission_type']
        widgets = {
            'user': forms.Select(attrs={'class': 'layui-input'}),
            'permission_type': forms.Select(attrs={'class': 'layui-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = Admin.objects.filter(status=1).order_by('name')


class FileSearchForm(forms.Form):
    keyword = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '搜索文件名或内容'})
    )
    file_type = forms.ChoiceField(
        choices=[
            ('', '全部类型'),
            ('image', '图片'),
            ('document', '文档'),
            ('video', '视频'),
            ('audio', '音频'),
            ('archive', '压缩包'),
            ('other', '其他'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'layui-input'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'})
    )
    size_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '最小文件大小(KB)'})
    )
    size_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '最大文件大小(KB)'})
    )