from django import forms
from .models.admin import Admin
from apps.department.models import Department
from apps.user.models.position import Position
from django.db import models
from django.contrib.auth.models import Group

class EmployeeForm(forms.ModelForm):
    # 主部门选择
    did = forms.IntegerField(
        label="主部门",
        widget=forms.Select(attrs={'class': 'layui-select'}),
        required=True
    )
    
    # 次要部门选择（多选）
    secondary_departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.filter(status=1),
        required=False,
        label="次要部门",
        widget=forms.SelectMultiple(attrs={'class': 'layui-select'})
    )
    
    # 岗位职称选择
    position_id = forms.IntegerField(
        label="岗位职称",
        widget=forms.Select(attrs={'class': 'layui-select'}),
        required=True
    )
    
    # 上级主管选择
    pid = forms.IntegerField(
        required=False,
        label="上级主管",
        widget=forms.Select(attrs={'class': 'layui-select'})
    )
    
    # 身份类型选择
    is_staff = forms.ChoiceField(
        choices=[(1, "企业员工"), (2, "劳务派遣"), (3, "兼职员工")],
        label="身份类型",
        widget=forms.Select(attrs={'class': 'layui-select'})
    )
    
    # 员工类型选择
    type = forms.ChoiceField(
        choices=[("正式员工", "正式员工"), ("试用员工", "试用员工"), ("实习员工", "实习员工"), ("外包员工", "外包员工")],
        label="员工类型",
        widget=forms.Select(attrs={'class': 'layui-select'})
    )
    
    # 性别选择
    sex = forms.ChoiceField(
        choices=[(0, "未知"), (1, "男"), (2, "女")],
        label="性别",
        widget=forms.Select(attrs={'class': 'layui-select'})
    )
    
    # 状态选择
    status = forms.ChoiceField(
        choices=[(1, "正常"), (0, "禁止登录"), (2, "离职")],
        label="状态",
        widget=forms.Select(attrs={'class': 'layui-select'})
    )
    
    # 角色选择
    role_id = forms.IntegerField(
        label="角色",
        widget=forms.Select(attrs={'class': 'layui-select'}),
        required=False,  # 可选，但建议必须选择
        help_text="选择员工的系统角色"
    )
    
    class Meta:
        model = Admin
        fields = [
            'username', 'pwd', 'name', 'sex', 'mobile', 'email', 'did', 'secondary_departments',
            'position_id', 'pid', 'entry_time', 'is_staff', 'type', 'job_number', 'sip_account',
            'sip_password', 'status', 'desc', 'role_id'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入登录账号'}),
            'pwd': forms.PasswordInput(attrs={'class': 'layui-input', 'placeholder': '请输入密码'}),
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入员工姓名'}),
            'mobile': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入手机号码'}),
            'email': forms.EmailInput(attrs={'class': 'layui-input', 'placeholder': '请输入电子邮箱'}),
            'job_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入工号'}),
            'sip_account': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入SIP账号'}),
            'sip_password': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入SIP密码'}),
            'entry_time': forms.NumberInput(
                attrs={'class': 'layui-input', 'placeholder': '请输入入职日期(YYYYMMDD格式)'}
            ),
            'desc': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入员工备注信息', 'rows': 4, 'required': False})
        }
        labels = {
            'username': '登录账号',
            'pwd': '登录密码',
            'name': '员工姓名',
            'mobile': '手机号码',
            'email': '电子邮箱',
            'job_number': '工号',
            'sip_account': 'SIP账号',
            'sip_password': 'SIP密码',
            'entry_time': '入职日期',
            'desc': '备注信息',
            'role_id': '系统角色'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 设置选择框选项和初始值
        self.fields['did'].widget.choices = [(0, '请选择部门')] + [(dept.id, dept.name) for dept in Department.objects.filter(status=1).order_by('sort')]
        self.fields['position_id'].widget.choices = [(0, '请选择岗位')] + [(pos.id, pos.title) for pos in Position.objects.filter(status=1).order_by('sort')]
        self.fields['pid'].widget.choices = [(0, '无上级')] + [(admin.id, admin.name) for admin in Admin.objects.filter(status=1).order_by('name')]
        # 设置角色选择框选项
        self.fields['role_id'].widget.choices = [
            ('', '请选择角色')
        ] + [
            (role.id, role.name) for role in Group.objects.all()
        ]
        
        # 显式设置desc字段为非必填
        self.fields['desc'].required = False
        
        # 设置初始值
        if self.instance.pk:
            if hasattr(self.instance, 'secondary_departments'):
                self.fields['secondary_departments'].initial = self.instance.secondary_departments.all()
            if hasattr(self.instance, 'did') and self.instance.did:
                self.fields['did'].initial = self.instance.did
            if hasattr(self.instance, 'position_id') and self.instance.position_id:
                self.fields['position_id'].initial = self.instance.position_id
            if hasattr(self.instance, 'pid') and self.instance.pid:
                self.fields['pid'].initial = self.instance.pid
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # 处理密码加密，统一存储到pwd字段
        if self.cleaned_data.get('pwd'):
            from django.contrib.auth.hashers import make_password
            instance.pwd = make_password(self.cleaned_data['pwd'])
        
        # 处理日期格式转换 - 修复entry_time字段处理
        if self.cleaned_data.get('entry_time'):
            if isinstance(self.cleaned_data['entry_time'], str):
                from datetime import datetime
                try:
                    entry_date = datetime.strptime(self.cleaned_data['entry_time'], '%Y-%m-%d')
                    instance.entry_time = int(entry_date.strftime('%Y%m%d'))
                except ValueError:
                    # 如果日期格式不正确，尝试直接转换为整数
                    try:
                        instance.entry_time = int(self.cleaned_data['entry_time'])
                    except (ValueError, TypeError):
                        # 如果转换失败，设置为0
                        instance.entry_time = 0
            elif hasattr(self.cleaned_data['entry_time'], 'strftime'):
                instance.entry_time = int(self.cleaned_data['entry_time'].strftime('%Y%m%d'))
            else:
                # 直接使用整数值
                try:
                    instance.entry_time = int(self.cleaned_data['entry_time'])
                except (ValueError, TypeError):
                    instance.entry_time = 0
        else:
            # 如果没有提供entry_time，设置为0
            instance.entry_time = 0
        
        # 更新position_name字段为对应Position模型的title
        if self.cleaned_data.get('position_id'):
            try:
                position = Position.objects.get(id=self.cleaned_data['position_id'])
                instance.position_name = position.title
            except Position.DoesNotExist:
                instance.position_name = ''
        
        if commit:
            instance.save()
            # 保存次要部门关系
            if hasattr(instance, 'secondary_departments'):
                instance.secondary_departments.set(self.cleaned_data['secondary_departments'])
            else:
                # 如果模型没有secondary_departments字段，需要创建多对多关系表
                pass
            
            # 保存角色关系
            # 使用新的权限系统，角色分配逻辑需要调整
            # 原代码中使用UserRole表存储用户与角色的关联
            # 实际项目中可能需要修改为使用system应用中的关联表
            role_id = self.cleaned_data.get('role_id')
            if role_id:
                # 这里只是为了保持代码结构，实际功能需要根据项目需求调整
                pass
        return instance
    
    def clean_did(self):
        did = self.cleaned_data.get('did')
        if not Department.objects.filter(id=did, status=1).exists():
            raise forms.ValidationError("选择的部门不存在或已禁用")
        return did
    
    def clean_position_id(self):
        position_id = self.cleaned_data.get('position_id')
        if not Position.objects.filter(id=position_id, status=1).exists():
            raise forms.ValidationError("选择的岗位不存在或已禁用")
        return position_id
    
    def clean_pid(self):
        pid = self.cleaned_data.get('pid')
        if pid and not Admin.objects.filter(id=pid, status=1).exists():
            raise forms.ValidationError("选择的主管不存在或已禁用")
        return pid
    
    def clean_role_id(self):
        role_id = self.cleaned_data.get('role_id')
        if role_id and not Group.objects.filter(id=role_id).exists():
            raise forms.ValidationError("选择的角色不存在")
        return role_id