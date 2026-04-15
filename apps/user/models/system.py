from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class SystemLog(models.Model):
    """操作日志"""
    LOG_TYPES = (
        ('login', '登录'),
        ('logout', '退出'),
        ('create', '创建'),
        ('update', '更新'),
        ('delete', '删除'),
        ('view', '查看'),
        ('export', '导出'),
        ('import', '导入'),
        ('other', '其他'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='操作用户')
    log_type = models.CharField(
        max_length=20,
        choices=LOG_TYPES,
        verbose_name='日志类型')
    module = models.CharField(max_length=100, verbose_name='操作模块')
    action = models.CharField(max_length=200, verbose_name='操作动作')
    content = models.TextField(blank=True, verbose_name='操作内容')
    ip_address = models.GenericIPAddressField(verbose_name='IP地址')
    user_agent = models.TextField(blank=True, verbose_name='用户代理')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')

    class Meta:
        verbose_name = '操作日志'
        verbose_name_plural = verbose_name
        db_table = 'system_log'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.action} - {self.created_at}"


class SystemOperationLog(models.Model):
    """系统操作日志表"""
    id = models.AutoField(primary_key=True, verbose_name='ID')
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='操作人')
    action = models.CharField(max_length=255, default='', verbose_name='操作行为')
    content = models.TextField(verbose_name='操作内容', null=True)
    ip = models.CharField(max_length=64, default='', verbose_name='操作IP')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')

    class Meta:
        db_table = 'system_operation_log'
        verbose_name = '系统操作日志'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.user} - {self.action} - {self.create_time}"


class SystemConfiguration(models.Model):
    """系统配置"""
    key = models.CharField(max_length=100, unique=True, verbose_name='配置键')
    value = models.TextField(verbose_name='配置值')
    description = models.CharField(
        max_length=200, blank=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '系统配置'
        verbose_name_plural = verbose_name
        db_table = 'system_configuration'

    def __str__(self):
        return f"{self.key}: {self.description}"


class SystemModule(models.Model):
    """功能模块"""
    name = models.CharField(max_length=100, verbose_name='模块名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='模块代码')
    description = models.TextField(blank=True, verbose_name='模块描述')
    icon = models.CharField(max_length=50, blank=True, verbose_name='图标')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='父模块')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '功能模块'
        verbose_name_plural = verbose_name
        db_table = 'system_module'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        重写save方法，确保系统管理和用户管理模块始终处于启用状态
        """
        # 系统管理模块始终启用
        if self.code == 'system' or '系统管理' in self.name:
            self.is_active = True
        # 用户管理模块始终启用
        if self.code == 'user' or self.name == '用户管理':
            self.is_active = True
        super().save(*args, **kwargs)
