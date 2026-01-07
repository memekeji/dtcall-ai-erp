from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.conf import settings
from apps.common.models import (
    SoftDeleteModel, BaseModel, StatusChoices, 
    GenderChoices, PriorityChoices
)

from apps.department.models import Department
from apps.user.models.position import Position


# 扩展Django内置的Group模型，添加必要的字段
class GroupExtension(models.Model):
    """Group模型扩展，添加描述和状态字段"""
    group = models.OneToOneField(
        Group, 
        on_delete=models.CASCADE, 
        primary_key=True, 
        related_name='extension'
    )
    description = models.TextField(blank=True, verbose_name='角色描述')
    status = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '角色扩展信息'
        verbose_name_plural = verbose_name


class DepartmentGroup(models.Model):
    """部门与角色的关联模型"""
    department = models.ForeignKey(
        Department, 
        on_delete=models.CASCADE, 
        verbose_name='部门',
        related_name='department_groups'
    )
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE, 
        verbose_name='角色',
        related_name='department_groups'
    )
    is_default = models.BooleanField(default=False, verbose_name='是否默认角色')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '部门角色关联'
        verbose_name_plural = verbose_name
        db_table = 'department_group'
        unique_together = ('department', 'group')  # 确保每个部门-角色组合唯一


class DepartmentNew(SoftDeleteModel):
    """优化后的部门模型（新版本）"""
    name = models.CharField(max_length=100, verbose_name='部门名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='部门代码')
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='children',
        verbose_name='上级部门'
    )
    
    # 使用ManyToManyField替代逗号分隔的ID
    leaders = models.ManyToManyField(
        'UserNew', 
        blank=True, 
        related_name='led_departments', 
        verbose_name='部门负责人'
    )
    
    phone = models.CharField(max_length=20, blank=True, verbose_name='部门电话')
    email = models.EmailField(blank=True, verbose_name='部门邮箱')
    address = models.CharField(max_length=500, blank=True, verbose_name='部门地址')
    description = models.TextField(blank=True, verbose_name='部门描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    status = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.ACTIVE, 
        verbose_name='状态'
    )
    
    class Meta:
        db_table = 'department_new'
        verbose_name = '部门（新）'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['code'], name='idx_dept_code'),
            models.Index(fields=['parent'], name='idx_dept_parent'),
            models.Index(fields=['status'], name='idx_dept_status'),
            models.Index(fields=['sort_order'], name='idx_dept_sort'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['code'],
                condition=models.Q(is_deleted=False),
                name='unique_dept_code_active'
            ),
        ]

    def __str__(self):
        return self.name

    def get_full_name(self):
        """获取完整部门名称"""
        if self.parent:
            return f"{self.parent.get_full_name()} > {self.name}"
        return self.name

    @property
    def level(self):
        """获取部门层级"""
        level = 0
        parent = self.parent
        while parent:
            level += 1
            parent = parent.parent
        return level


class PositionNew(SoftDeleteModel):
    """优化后的职位模型（新版本）"""
    title = models.CharField(max_length=100, verbose_name='职位名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='职位代码')
    department = models.ForeignKey(
        Department, 
        on_delete=models.CASCADE, 
        verbose_name='所属部门'
    )
    level = models.IntegerField(default=1, verbose_name='职位等级')
    description = models.TextField(blank=True, verbose_name='职位描述')
    requirements = models.TextField(blank=True, verbose_name='任职要求')
    responsibilities = models.TextField(blank=True, verbose_name='工作职责')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    status = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.ACTIVE, 
        verbose_name='状态'
    )

    class Meta:
        db_table = 'position_new'
        verbose_name = '职位（新）'
        verbose_name_plural = verbose_name
        ordering = ['department', 'level', 'sort_order']
        indexes = [
            models.Index(fields=['code'], name='idx_position_code'),
            models.Index(fields=['department'], name='idx_position_dept'),
            models.Index(fields=['level'], name='idx_position_level'),
            models.Index(fields=['status'], name='idx_position_status'),
        ]

    def __str__(self):
        return f"{self.department.name} - {self.title}"


class UserNew(AbstractUser, SoftDeleteModel):
    """优化后的用户模型（新版本）"""
    # 基本信息
    employee_id = models.CharField(max_length=50, unique=True, verbose_name='工号')
    name = models.CharField(max_length=100, verbose_name='员工姓名')
    mobile = models.CharField(max_length=20, unique=True, verbose_name='手机号码')
    
    # 关联信息 - 使用ForeignKey替代IntegerField
    department = models.ForeignKey(
        Department, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='employees',
        verbose_name='主部门'
    )
    supervisor = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='subordinates',
        verbose_name='直属上级'
    )
    position = models.ForeignKey(
        Position, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name='职位'
    )
    
    # 个人信息
    gender = models.IntegerField(
        choices=GenderChoices.choices, 
        default=GenderChoices.UNKNOWN, 
        verbose_name='性别'
    )
    birthday = models.DateField(null=True, blank=True, verbose_name='生日')
    entry_date = models.DateField(null=True, blank=True, verbose_name='入职日期')
    
    # 联系信息
    work_phone = models.CharField(max_length=20, blank=True, verbose_name='工作电话')
    personal_email = models.EmailField(blank=True, verbose_name='个人邮箱')
    address = models.CharField(max_length=500, blank=True, verbose_name='家庭地址')
    emergency_contact = models.CharField(max_length=100, blank=True, verbose_name='紧急联系人')
    emergency_phone = models.CharField(max_length=20, blank=True, verbose_name='紧急联系电话')
    
    # 工作信息
    work_location = models.CharField(max_length=255, blank=True, verbose_name='工作地点')
    employee_type = models.CharField(
        max_length=20,
        choices=[
            ('full_time', '全职员工'),
            ('part_time', '兼职员工'),
            ('contract', '合同工'),
            ('intern', '实习生'),
        ],
        default='full_time',
        verbose_name='员工类型'
    )
    
    # 教育背景
    education = models.CharField(
        max_length=20,
        choices=[
            ('high_school', '高中'),
            ('college', '大专'),
            ('bachelor', '本科'),
            ('master', '硕士'),
            ('doctor', '博士'),
        ],
        blank=True,
        verbose_name='学历'
    )
    major = models.CharField(max_length=100, blank=True, verbose_name='专业')
    graduate_school = models.CharField(max_length=255, blank=True, verbose_name='毕业学校')
    graduate_date = models.DateField(null=True, blank=True, verbose_name='毕业日期')
    
    # 身份信息
    id_card = models.CharField(max_length=18, blank=True, verbose_name='身份证号')
    nationality = models.CharField(max_length=50, default='中国', verbose_name='国籍')
    ethnicity = models.CharField(max_length=50, blank=True, verbose_name='民族')
    political_status = models.CharField(
        max_length=20,
        choices=[
            ('masses', '群众'),
            ('party_member', '中共党员'),
            ('league_member', '共青团员'),
            ('democratic_party', '民主党派'),
        ],
        default='masses',
        verbose_name='政治面貌'
    )
    marital_status = models.CharField(
        max_length=20,
        choices=[
            ('single', '未婚'),
            ('married', '已婚'),
            ('divorced', '离异'),
            ('widowed', '丧偶'),
        ],
        default='single',
        verbose_name='婚姻状况'
    )
    
    # 银行和社保信息
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='开户银行')
    bank_account = models.CharField(max_length=50, blank=True, verbose_name='银行账号')
    social_security_number = models.CharField(max_length=50, blank=True, verbose_name='社保账号')
    medical_insurance_number = models.CharField(max_length=50, blank=True, verbose_name='医保账号')
    housing_fund_number = models.CharField(max_length=50, blank=True, verbose_name='公积金账号')
    
    # 系统设置
    avatar = models.ImageField(upload_to='avatars/', blank=True, verbose_name='头像')
    theme = models.CharField(
        max_length=20, 
        choices=[
            ('light', '浅色主题'),
            ('dark', '深色主题'),
            ('auto', '自动'),
        ],
        default='light', 
        verbose_name='系统主题'
    )
    language = models.CharField(
        max_length=10,
        choices=[
            ('zh-cn', '简体中文'),
            ('zh-tw', '繁体中文'),
            ('en', 'English'),
        ],
        default='zh-cn',
        verbose_name='语言设置'
    )
    
    # 状态信息
    employee_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', '待入职'),
            ('active', '在职'),
            ('inactive', '停职'),
            ('resigned', '离职'),
        ],
        default='pending',
        verbose_name='员工状态'
    )
    
    # 权限设置
    data_permission_type = models.CharField(
        max_length=20,
        choices=[
            ('all', '全部数据'),
            ('department', '本部门数据'),
            ('self', '个人数据'),
            ('custom', '自定义'),
        ],
        default='department',
        verbose_name='数据权限类型'
    )
    visible_departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name='visible_to_users',
        verbose_name='可见部门'
    )
    
    # 登录信息
    last_login_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='最后登录IP')
    login_count = models.IntegerField(default=0, verbose_name='登录次数')
    
    # 其他信息
    bio = models.TextField(blank=True, verbose_name='个人简介')
    skills = models.TextField(blank=True, verbose_name='技能特长')
    remark = models.TextField(blank=True, verbose_name='备注信息')
    
    # 解决反向访问器冲突
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_name='usernew_set',
        related_query_name='usernew',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='usernew_set',
        related_query_name='usernew',
    )

    class Meta:
        db_table = 'user_new'
        verbose_name = '用户（新）'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['employee_id'], name='idx_user_employee_id'),
            models.Index(fields=['mobile'], name='idx_user_mobile'),
            models.Index(fields=['email'], name='idx_user_email'),
            models.Index(fields=['department'], name='idx_user_department'),
            models.Index(fields=['employee_status'], name='idx_user_status'),
            models.Index(fields=['entry_date'], name='idx_user_entry_date'),
            models.Index(fields=['supervisor'], name='idx_user_supervisor'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['employee_id'],
                condition=models.Q(is_deleted=False),
                name='unique_user_employee_id_active'
            ),
            models.UniqueConstraint(
                fields=['mobile'],
                condition=models.Q(is_deleted=False),
                name='unique_user_mobile_active'
            ),
        ]

    def __str__(self):
        return f"{self.name}({self.employee_id})"

    def save(self, *args, **kwargs):
        # 自动生成工号
        if not self.employee_id:
            from django.utils import timezone
            year = timezone.now().year
            last_user = UserNew.objects.filter(
                employee_id__startswith=f'EMP{year}'
            ).order_by('-employee_id').first()
            
            if last_user and last_user.employee_id:
                try:
                    last_num = int(last_user.employee_id[-4:])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            self.employee_id = f'EMP{year}{new_num:04d}'
        
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        """获取完整姓名"""
        return self.name or self.username

    @property
    def age(self):
        """计算年龄"""
        if self.birthday:
            from datetime import date
            today = date.today()
            return today.year - self.birthday.year - (
                (today.month, today.day) < (self.birthday.month, self.birthday.day)
            )
        return None

    @property
    def work_years(self):
        """计算工作年限"""
        if self.entry_date:
            from datetime import date
            today = date.today()
            years = today.year - self.entry_date.year
            if (today.month, today.day) < (self.entry_date.month, self.entry_date.day):
                years -= 1
            return max(0, years)
        return 0
    
    @property
    def did(self):
        """兼容旧代码，返回部门ID"""
        return self.department.id if self.department else None

    def get_subordinates(self, include_indirect=False):
        """获取下属员工"""
        if include_indirect:
            # 递归获取所有下属
            subordinates = []
            direct_subordinates = self.subordinates.filter(is_deleted=False)
            subordinates.extend(direct_subordinates)
            for subordinate in direct_subordinates:
                subordinates.extend(subordinate.get_subordinates(include_indirect=True))
            return subordinates
        else:
            return self.subordinates.filter(is_deleted=False)

    def can_manage_user(self, user):
        """检查是否可以管理指定用户"""
        if self.is_superuser:
            return True
        
        # 检查是否是直属上级
        if user.supervisor == self:
            return True
        
        # 检查是否是部门负责人
        if user.department and self in user.department.leaders.all():
            return True
        
        return False






class UserLoginLog(BaseModel):
    """用户登录日志"""
    user = models.ForeignKey(UserNew, on_delete=models.CASCADE, verbose_name='用户')
    login_type = models.CharField(
        max_length=20,
        choices=[
            ('web', 'Web登录'),
            ('mobile', '移动端登录'),
            ('api', 'API登录'),
            ('sso', '单点登录'),
        ],
        default='web',
        verbose_name='登录类型'
    )
    ip_address = models.GenericIPAddressField(verbose_name='登录IP')
    user_agent = models.TextField(blank=True, verbose_name='用户代理')
    device_info = models.TextField(blank=True, verbose_name='设备信息')
    location = models.CharField(max_length=200, blank=True, verbose_name='登录地点')
    is_success = models.BooleanField(default=True, verbose_name='是否成功')
    failure_reason = models.CharField(max_length=200, blank=True, verbose_name='失败原因')
    session_duration = models.IntegerField(null=True, blank=True, verbose_name='会话时长(秒)')
    logout_time = models.DateTimeField(null=True, blank=True, verbose_name='登出时间')

    class Meta:
        db_table = 'user_login_log'
        verbose_name = '用户登录日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user'], name='idx_login_log_user'),
            models.Index(fields=['created_at'], name='idx_login_log_created'),
            models.Index(fields=['ip_address'], name='idx_login_log_ip'),
            models.Index(fields=['is_success'], name='idx_login_log_success'),
        ]

    def __str__(self):
        return f"{self.user.name} - {self.created_at}"
