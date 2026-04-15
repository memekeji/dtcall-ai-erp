from django import forms
from django.contrib.auth import get_user_model
from apps.department.models import Department
from .models import DiskFile, DiskFolder, DiskShare

User = get_user_model()


class DiskFolderForm(forms.ModelForm):
    class Meta:
        model = DiskFolder
        fields = [
            'name',
            'parent',
            'department',
            'is_public',
            'permission_level']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入文件夹名称',
                    'maxlength': '200'}),
            'parent': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'department': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'is_public': forms.CheckboxInput(
                attrs={
                    'lay-skin': 'switch',
                    'lay-text': '是|否'}),
            'permission_level': forms.Select(
                attrs={
                    'class': 'layui-input'},
                choices=DiskFolder.PERMISSION_LEVELS),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['parent'].queryset = DiskFolder.objects.filter(
                owner=user, delete_time__isnull=True
            ).order_by('name')
            self.fields['parent'].empty_label = "根目录"
            self.fields['department'].queryset = Department.objects.all()
            self.fields['department'].empty_label = "无部门"


class DiskFileUploadForm(forms.ModelForm):
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'layui-input',
            'accept': '*/*'
        }),
        required=False
    )

    class Meta:
        model = DiskFile
        fields = ['name', 'folder', 'department', 'is_public']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '文件名称（可选，默认使用原文件名）',
                    'maxlength': '200'}),
            'folder': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'department': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'is_public': forms.CheckboxInput(
                attrs={
                    'lay-skin': 'switch',
                    'lay-text': '是|否'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['folder'].queryset = DiskFolder.objects.filter(
                owner=user, delete_time__isnull=True
            ).order_by('name')
            self.fields['folder'].empty_label = "根目录"
            self.fields['department'].queryset = Department.objects.all()
            self.fields['department'].empty_label = "无部门"


class DiskShareForm(forms.ModelForm):
    class Meta:
        model = DiskShare
        fields = [
            'share_type',
            'password',
            'expire_time',
            'permission_type',
            'allow_download',
            'access_limit',
            'download_limit']
        widgets = {
            'share_type': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'password': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '分享密码（可选，不设置则无需密码）',
                    'maxlength': '20'}),
            'expire_time': forms.DateTimeInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'datetime-local',
                            'placeholder': '过期时间（可选，不设置则永不过期）'}),
            'permission_type': forms.Select(
                attrs={
                    'class': 'layui-input'},
                choices=DiskShare.PERMISSION_TYPES),
            'allow_download': forms.CheckboxInput(
                attrs={
                    'lay-skin': 'switch',
                    'lay-text': '允许|禁止'}),
            'access_limit': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '访问次数限制（0表示无限制）',
                    'min': '0'}),
            'download_limit': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '下载次数限制（0表示无限制）',
                    'min': '0'}),
        }


class FileSearchForm(forms.Form):
    keyword = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'layui-input',
            'placeholder': '搜索文件名'
        })
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
        widget=forms.DateInput(attrs={
            'class': 'layui-input',
            'type': 'date',
            'placeholder': '开始日期'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'layui-input',
            'type': 'date',
            'placeholder': '结束日期'
        })
    )
    size_min = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'layui-input',
            'placeholder': '最小文件大小(KB)',
            'min': '0'
        })
    )
    size_max = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'layui-input',
            'placeholder': '最大文件大小(KB)',
            'min': '0'
        })
    )


class FileMoveForm(forms.Form):
    target_folder_id = forms.IntegerField(
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['target_folder_id'].widget = forms.Select(
                attrs={'class': 'layui-input'})
            self.fields['target_folder_id'].queryset = DiskFolder.objects.filter(
                owner=user, delete_time__isnull=True).order_by('name')
            self.fields['target_folder_id'].empty_label = "根目录"


class FolderRenameForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'layui-input',
            'placeholder': '请输入文件夹名称',
            'maxlength': '200'
        })
    )

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise forms.ValidationError('文件夹名称不能为空')
        if len(name) > 200:
            raise forms.ValidationError('文件夹名称不能超过200个字符')
        return name


class FileRenameForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'layui-input',
            'placeholder': '请输入文件名称',
            'maxlength': '200'
        })
    )

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise forms.ValidationError('文件名称不能为空')
        if len(name) > 200:
            raise forms.ValidationError('文件名称不能超过200个字符')
        return name


class SharePasswordForm(forms.Form):
    password = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'layui-input',
            'placeholder': '请输入提取密码',
            'type': 'password'
        })
    )
