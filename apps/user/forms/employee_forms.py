"""
员工人事管理表单
"""
from django import forms
from django.contrib.auth import get_user_model
from apps.department.models import Department
from apps.user.models.position import Position
from apps.user.models import Admin, EmployeeFile, EmployeeTransfer, EmployeeDimission, RewardPunishment, EmployeeCare, EmployeeContract

User = get_user_model()


class EmployeeForm(forms.ModelForm):
    """员工表单 - 用于Admin模型的创建和编辑"""
    password = forms.CharField(
        max_length=128, 
        required=False, 
        widget=forms.PasswordInput(attrs={'class': 'layui-input', 'placeholder': '请输入密码'}),
        label='密码'
    )
    
    class Meta:
        model = Admin
        fields = [
            'username', 'password', 'name', 'email', 'mobile', 'sex', 'thumb',
            'did', 'position_name', 'type', 'job_number', 'status', 'entry_time',
            'secondary_departments', 'position_id', 'pid', 'sip_account',
            'sip_password', 'desc'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入用户名'}),
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入姓名'}),
            'email': forms.EmailInput(attrs={'class': 'layui-input', 'placeholder': '请输入邮箱'}),
            'mobile': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入手机号'}),
            'sex': forms.Select(attrs={'class': 'layui-input'}, choices=[(1, '男'), (2, '女')]),
            'did': forms.Select(attrs={'class': 'layui-input'}),
            'position_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入职位'}),
            'type': forms.Select(attrs={'class': 'layui-input'}),
            'job_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入工号'}),
            'status': forms.Select(attrs={'class': 'layui-input'}, choices=[(1, '正常'), (0, '禁止登录'), (-1, '待入职'), (2, '离职')]),
            'entry_time': forms.DateInput(attrs={'class': 'layui-input', 'placeholder': '请输入入职日期'}),
            'secondary_departments': forms.SelectMultiple(attrs={'class': 'layui-input'}),
            'position_id': forms.Select(attrs={'class': 'layui-input'}),
            'pid': forms.Select(attrs={'class': 'layui-input'}),
            'sip_account': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入SIP账号'}),
            'sip_password': forms.PasswordInput(attrs={'class': 'layui-input', 'placeholder': '请输入SIP密码'}),
            'desc': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入备注信息', 'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 设置部门选择框的选项
        departments = Department.objects.filter(status=1).order_by('name')
        self.fields['did'].widget.choices = [(0, '请选择主部门')] + [(dept.id, dept.name) for dept in departments]
        self.fields['did'].required = True  # 主部门必填
        
        # 设置次要部门选择框的查询集
        self.fields['secondary_departments'].queryset = Department.objects.filter(status=1).order_by('name')
        self.fields['secondary_departments'].required = False  # 次要部门非必填
        
        # 设置岗位职称选择框的选项
        positions = Position.objects.filter(status=True).order_by('title')
        self.fields['position_id'].widget.choices = [(0, '请选择岗位职称')] + [(pos.id, pos.title) for pos in positions]
        self.fields['position_id'].required = True  # 岗位职称必填
        
        # 设置上级主管选择框的选项
        admins = Admin.objects.filter(status=1).order_by('name')
        self.fields['pid'].widget.choices = [(0, '请选择上级主管')] + [(admin.id, admin.name) for admin in admins]
        self.fields['pid'].required = False  # 上级主管非必填
        
        # 设置员工类型选择
        self.fields['type'].widget.choices = [
            ('', '请选择员工类型'),
            ('正式员工', '正式员工'),
            ('试用员工', '试用员工'),
            ('实习员工', '实习员工'),
            ('外包员工', '外包员工'),
        ]
        self.fields['type'].required = True  # 员工类型必填
        
        # 设置状态选择
        self.fields['status'].choices = [
            (1, '正常'),
            (0, '禁止登录'),
            (-1, '待入职'),
            (2, '离职'),
        ]
        self.fields['status'].required = True  # 状态必填
        
        # 设置其他必填字段
        self.fields['username'].required = True  # 登录账号必填
        self.fields['name'].required = True  # 员工姓名必填
        self.fields['mobile'].required = True  # 手机号码必填
        self.fields['entry_time'].required = True  # 入职日期必填
        
        # 密码字段处理
        if self.instance and self.instance.pk:
            # 编辑模式：密码非必填
            self.fields['password'].required = False
            
            # 显示当前SIP密码（明文存储）
            self.initial['sip_password'] = self.instance.sip_password
            
            # 初始化次要部门
            if self.instance.secondary_departments.exists():
                self.initial['secondary_departments'] = list(self.instance.secondary_departments.values_list('id', flat=True))
        else:
            # 创建模式：密码必填
            self.fields['password'].required = True
        
        # 非必填字段
        self.fields['email'].required = False  # 电子邮箱非必填
        self.fields['thumb'].required = False  # 头像非必填
        self.fields['position_name'].required = False  # 职位非必填
        self.fields['job_number'].required = False  # 工号非必填
        self.fields['sip_account'].required = False  # SIP账号非必填
        self.fields['sip_password'].required = False  # SIP密码非必填
        self.fields['desc'].required = False  # 备注信息非必填
    
    def clean(self):
        cleaned_data = super().clean()
        
        if self.instance and self.instance.pk:
            # 处理登录密码
            if not cleaned_data.get('password'):
                # 密码字段为空，移除密码字段，避免覆盖原密码
                cleaned_data.pop('password', None)
            
            # 处理SIP密码
            if not cleaned_data.get('sip_password'):
                # SIP密码字段为空，移除SIP密码字段，避免覆盖原SIP密码
                cleaned_data.pop('sip_password', None)
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # 只有在提供了新密码时，才设置密码
        if 'password' in self.cleaned_data and self.cleaned_data['password']:
            user.set_password(self.cleaned_data['password'])
        
        # 只有在提供了新SIP密码时，才设置SIP密码
        if 'sip_password' in self.cleaned_data and self.cleaned_data['sip_password']:
            user.sip_password = self.cleaned_data['sip_password']
        
        # 更新position_name字段为对应Position模型的title
        if 'position_id' in self.cleaned_data and self.cleaned_data['position_id']:
            try:
                position = Position.objects.get(id=self.cleaned_data['position_id'])
                user.position_name = position.title
            except Position.DoesNotExist:
                user.position_name = ''
        
        if commit:
            user.save()
            # 处理次要部门
            if 'secondary_departments' in self.cleaned_data:
                user.secondary_departments.set(self.cleaned_data['secondary_departments'])
        
        return user


class EmployeeFileForm(forms.ModelForm):
    class Meta:
        model = EmployeeFile
        fields = [
            'employee', 'id_card', 'birth_date', 'gender', 'nationality', 'native_place',
            'address', 'education', 'graduate_school', 'major', 'graduation_date',
            'marital_status', 'emergency_contact', 'emergency_phone', 'bank_account',
            'bank_name', 'social_security_number', 'housing_fund_number',
            'work_experience', 'skills', 'remarks'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'layui-input'}),
            'id_card': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入身份证号'}),
            'birth_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'layui-input'}),
            'nationality': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入民族'}),
            'native_place': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入籍贯'}),
            'address': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入现住址', 'rows': 3}),
            'education': forms.Select(attrs={'class': 'layui-input'}),
            'graduate_school': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入毕业院校'}),
            'major': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入专业'}),
            'graduation_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'marital_status': forms.Select(attrs={'class': 'layui-input'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入紧急联系人'}),
            'emergency_phone': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入紧急联系电话'}),
            'bank_account': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入银行账号'}),
            'bank_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入开户银行'}),
            'social_security_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入社保号'}),
            'housing_fund_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入公积金号'}),
            'work_experience': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入工作经历', 'rows': 4}),
            'skills': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入技能特长', 'rows': 3}),
            'remarks': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入备注', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Admin.objects.filter(status=1).order_by('username')


class EmployeeTransferForm(forms.ModelForm):
    class Meta:
        model = EmployeeTransfer
        fields = [
            'employee', 'from_department', 'to_department', 'from_position', 
            'to_position', 'transfer_reason', 'transfer_date'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'layui-input'}),
            'from_department': forms.Select(attrs={'class': 'layui-input'}),
            'to_department': forms.Select(attrs={'class': 'layui-input'}),
            'from_position': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入原职位'}),
            'to_position': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入新职位'}),
            'transfer_reason': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入调动原因', 'rows': 4}),
            'transfer_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Admin.objects.filter(status=1).order_by('username')
        self.fields['from_department'].queryset = Department.objects.filter(status=1).order_by('name')
        self.fields['to_department'].queryset = Department.objects.filter(status=1).order_by('name')


class EmployeeDimissionForm(forms.ModelForm):
    class Meta:
        model = EmployeeDimission
        fields = [
            'employee', 'dimission_type', 'dimission_reason', 'apply_date', 
            'dimission_date', 'handover_person', 'handover_content'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'layui-input'}),
            'dimission_type': forms.Select(attrs={'class': 'layui-input'}),
            'dimission_reason': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入离职原因', 'rows': 4}),
            'apply_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'dimission_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'handover_person': forms.Select(attrs={'class': 'layui-input'}),
            'handover_content': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入交接内容', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Admin.objects.filter(status=1).order_by('username')
        self.fields['handover_person'].queryset = Admin.objects.filter(status=1).order_by('username')
        self.fields['handover_person'].empty_label = "请选择交接人"


class RewardPunishmentForm(forms.ModelForm):
    class Meta:
        model = RewardPunishment
        fields = [
            'employee', 'type', 'level', 'title', 'reason', 
            'amount', 'effective_date', 'remarks'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'layui-input'}),
            'type': forms.Select(attrs={'class': 'layui-input'}),
            'level': forms.Select(attrs={'class': 'layui-input'}),
            'title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入标题'}),
            'reason': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入原因', 'rows': 4}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入金额', 'step': '0.01'}),
            'effective_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'remarks': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入备注', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Admin.objects.filter(status=1).order_by('username')


class EmployeeCareForm(forms.ModelForm):
    class Meta:
        model = EmployeeCare
        fields = [
            'employee', 'care_type', 'title', 'content', 
            'care_date', 'amount', 'remarks'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'layui-input'}),
            'care_type': forms.Select(attrs={'class': 'layui-input'}),
            'title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入关怀标题'}),
            'content': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入关怀内容', 'rows': 4}),
            'care_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入关怀金额', 'step': '0.01'}),
            'remarks': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入备注', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Admin.objects.filter(status=1).order_by('username')


class EmployeeContractForm(forms.ModelForm):
    class Meta:
        model = EmployeeContract
        fields = [
            'employee', 'contract_type', 'contract_number', 'start_date', 
            'end_date', 'salary', 'position', 'department', 'remarks'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'layui-input'}),
            'contract_type': forms.Select(attrs={'class': 'layui-input'}),
            'contract_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入合同编号'}),
            'start_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'salary': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入薪资', 'step': '0.01'}),
            'position': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入职位'}),
            'department': forms.Select(attrs={'class': 'layui-input'}),
            'remarks': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入备注', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Admin.objects.filter(status=1).order_by('username')