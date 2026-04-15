from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _


class Admin(AbstractUser):
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    # 重新定义groups和user_permissions字段，启用Django权限系统
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_('The groups this user belongs to.'),
        related_name="admin_set",
        related_query_name="admin",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name="admin_set",
        related_query_name="admin",
    )
    """
    用户模型，继承自Django的AbstractUser
    对应原项目的mimu_admin表结构
    """
    userid = models.CharField(
        max_length=100,
        default='',
        verbose_name='企业微信userid')
    pwd = models.CharField(max_length=100, default='', verbose_name='登录密码')
    salt = models.CharField(max_length=100, default='', verbose_name='密码盐')
    name = models.CharField(max_length=100, default='', verbose_name='员工姓名')
    email = models.CharField(max_length=100, default='', verbose_name='电子邮箱')
    sip_account = models.CharField(
        max_length=255, null=True, verbose_name='SIP账号')
    sip_password = models.CharField(
        max_length=255, null=True, verbose_name='SIP密码')
    mobile = models.CharField(max_length=20, default='', verbose_name='手机号码')
    sex = models.IntegerField(default=0, verbose_name='性别:1男,2女')
    nickname = models.CharField(max_length=100, default='', verbose_name='别名')
    thumb = models.CharField(max_length=255, verbose_name='头像')
    theme = models.CharField(
        max_length=50,
        default='white',
        verbose_name='系统主题')
    did = models.IntegerField(default=0, verbose_name='主部门id')
    pid = models.IntegerField(default=0, verbose_name='上级主管id')
    position_id = models.IntegerField(default=0, verbose_name='职位id')
    position_name = models.CharField(
        max_length=100, default='', verbose_name='职务')
    position_rank = models.IntegerField(default=0, verbose_name='职级')
    type = models.CharField(max_length=20, default='', verbose_name='员工类型')
    is_staff = models.IntegerField(
        default=1, verbose_name='身份类型:1企业员工,2劳务派遣,3兼职员工')
    job_number = models.CharField(
        max_length=255, default='', verbose_name='工号')
    birthday = models.IntegerField(default=0, verbose_name='生日')
    age = models.IntegerField(default=0, verbose_name='年龄')
    work_date = models.IntegerField(default=0, verbose_name='开始工作时间')
    work_location = models.CharField(
        max_length=255, default='', verbose_name='工作地点')
    native_place = models.CharField(
        max_length=255, default='', verbose_name='籍贯')
    nation = models.CharField(max_length=255, default='', verbose_name='民族')
    home_address = models.CharField(
        max_length=255, default='', verbose_name='家庭地址')
    current_address = models.CharField(
        max_length=255, default='', verbose_name='现居地址')
    contact = models.CharField(
        max_length=255,
        default='',
        verbose_name='紧急联系人')
    contact_mobile = models.CharField(
        max_length=255, default='', verbose_name='紧急联系人电话')
    resident_type = models.IntegerField(
        default=0, verbose_name='户口性质:1农村户口,2城镇户口')
    resident_place = models.CharField(
        max_length=255, default='', verbose_name='户口所在地')
    graduate_school = models.CharField(
        max_length=255, default='', verbose_name='毕业学校')
    graduate_day = models.IntegerField(default=0, verbose_name='毕业日期')
    political = models.IntegerField(default=1, verbose_name='政治面貌:1中共党员,2团员')
    marital_status = models.IntegerField(
        default=1, verbose_name='婚姻状况:1未婚,2已婚,3离异')
    idcard = models.CharField(max_length=255, default='', verbose_name='身份证')
    education = models.CharField(max_length=255, default='', verbose_name='学位')
    speciality = models.CharField(
        max_length=255, default='', verbose_name='专业')
    social_account = models.CharField(
        max_length=255, default='', verbose_name='社保账号')
    medical_account = models.CharField(
        max_length=255, default='', verbose_name='医保账号')
    provident_account = models.CharField(
        max_length=255, default='', verbose_name='公积金账号')
    bank_account = models.CharField(
        max_length=255, default='', verbose_name='银行卡号')
    bank_info = models.CharField(
        max_length=255,
        default='',
        verbose_name='开户行')
    file_ids = models.CharField(
        max_length=500,
        default='',
        verbose_name='档案附件')
    desc = models.TextField(null=True, verbose_name='员工个人简介')
    is_hide = models.IntegerField(default=0, verbose_name='是否隐藏联系方式:0否,1是')
    entry_time = models.BigIntegerField(default=0, verbose_name='员工入职日期')
    create_time = models.BigIntegerField(default=0, verbose_name='注册时间')
    update_time = models.BigIntegerField(default=0, verbose_name='更新信息时间')
    last_login_time = models.BigIntegerField(default=0, verbose_name='最后登录时间')
    login_num = models.IntegerField(default=0, verbose_name='登录次数')
    last_login_ip = models.CharField(
        max_length=64, default='', verbose_name='最后登录IP')
    is_lock = models.IntegerField(default=0, verbose_name='是否锁屏:1是0否')
    auth_did = models.IntegerField(default=0, verbose_name='数据权限类型')
    auth_dids = models.CharField(
        max_length=500,
        default='',
        verbose_name='可见部门数据')
    son_dids = models.CharField(
        max_length=500,
        default='',
        verbose_name='可见子部门数据')
    status = models.IntegerField(
        default=1, verbose_name='状态：-1待入职,0禁止登录,1正常,2离职')
    # 使用信号处理外键关系，而不是直接定义外键
    secondary_departments = models.ManyToManyField(
        'Department',
        related_name='secondary_employees',
        blank=True,
        verbose_name='次要部门',
        through='AdminSecondaryDepartment')

    class Meta:
        app_label = 'user'
        db_table = 'mimu_admin'
        verbose_name = '管理员'
        verbose_name_plural = verbose_name

    def has_perm(self, perm, obj=None):
        """
        检查用户是否有指定权限
        使用自定义的AuthBackend进行权限检查
        """
        from apps.user.auth_backend import AdminAuthBackend
        backend = AdminAuthBackend()
        return backend.has_perm(self, perm, obj)

    def has_module_perms(self, app_label):
        """
        检查用户是否有权限访问整个应用
        使用自定义的AuthBackend进行权限检查
        """
        from apps.user.auth_backend import AdminAuthBackend
        backend = AdminAuthBackend()
        return backend.has_module_perms(self, app_label)

    def get_all_permissions(self, obj=None):
        """
        获取用户所有权限
        使用自定义的AuthBackend获取权限
        """
        from apps.user.auth_backend import AdminAuthBackend
        backend = AdminAuthBackend()
        return backend.get_all_permissions(self, obj)

    def get_group_permissions(self, obj=None):
        """
        获取用户组权限（包括部门角色权限）
        使用自定义的AuthBackend获取权限
        """
        from apps.user.auth_backend import AdminAuthBackend
        backend = AdminAuthBackend()
        return backend.get_group_permissions(self, obj)


class AdminSecondaryDepartment(models.Model):
    """管理员次要部门中间表模型"""
    admin = models.ForeignKey(Admin, on_delete=models.CASCADE)
    department = models.ForeignKey('Department', on_delete=models.CASCADE)

    class Meta:
        db_table = 'admin_secondary_departments'
        unique_together = ('admin', 'department')
