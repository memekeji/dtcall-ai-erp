from django.db import models


class Region(models.Model):
    name = models.CharField(max_length=100, verbose_name='地区名称')
    code = models.CharField(max_length=20, unique=True, verbose_name='地区代码')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='上级地区')
    level = models.IntegerField(default=1, verbose_name='级别')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '地区管理'
        verbose_name_plural = verbose_name
        db_table = 'basedata_region'
        ordering = ['sort_order', 'code']

    def __str__(self):
        return self.name


class Enterprise(models.Model):
    name = models.CharField(max_length=200, verbose_name='企业名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='企业代码')
    legal_name = models.CharField(max_length=200, verbose_name='法定名称')
    tax_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='税号')
    legal_person = models.CharField(max_length=50, verbose_name='法人代表')
    registered_capital = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='注册资本')
    business_scope = models.TextField(blank=True, verbose_name='经营范围')
    address = models.CharField(max_length=500, blank=True, verbose_name='注册地址')
    contact_phone = models.CharField(
        max_length=50, blank=True, verbose_name='联系电话')
    contact_email = models.EmailField(blank=True, verbose_name='联系邮箱')
    website = models.URLField(blank=True, verbose_name='官方网站')
    logo = models.ImageField(
        upload_to='enterprise/logos/',
        blank=True,
        verbose_name='企业Logo')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '企业主体'
        verbose_name_plural = verbose_name
        db_table = 'basedata_enterprise'

    def __str__(self):
        return self.name
