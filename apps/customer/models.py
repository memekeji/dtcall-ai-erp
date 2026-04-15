from django.db import models
from django.conf import settings
from apps.user.models import Admin


class SpiderTask(models.Model):
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.CASCADE,
        related_name='spider_tasks',
        verbose_name='关联客户',
        null=True,
        blank=True)
    STATUS_CHOICES = (
        (1, '运行中'),
        (2, '停止'),
    )
    task_name = models.CharField(max_length=255, verbose_name='任务名称')
    spider_keywords = models.TextField(verbose_name='爬虫关键词')
    data_region = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='数据地区限制')
    industry_limit = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='行业限制')
    province = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='省份地区')
    insured_count = models.CharField(max_length=20, choices=[
        ('不限', '不限'),
        ('0', '0'),
        ('1-49', '1-49'),
        ('50-99', '50-99'),
        ('100-999', '100-999'),
        ('1000-4999', '1000-4999'),
        ('5000以上', '5000以上'),
    ], verbose_name='参保人数')
    contact_phone = models.CharField(max_length=50, choices=[
        ('不限', '不限'),
        ('有有效手机号', '有有效手机号'),
        ('有固定电话', '有固定电话'),
        ('有400/800电话', '有400/800电话'),
    ], verbose_name='联系电话')
    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=2,
        verbose_name='状态')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    create_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='创建人')
    delete_time = models.PositiveBigIntegerField(
        default=0, verbose_name='删除时间')

    class Meta:
        verbose_name = '爬虫任务'
        verbose_name_plural = '爬虫任务'

    def __str__(self):
        return self.task_name


class Contact(models.Model):
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.CASCADE,
        related_name='contacts',
        verbose_name='关联客户')
    contact_person = models.CharField(max_length=100, verbose_name='联系人姓名')
    phone = models.CharField(max_length=20, verbose_name='联系电话')
    is_primary = models.BooleanField(default=False, verbose_name='是否主要联系人')
    position = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='职位')
    email = models.EmailField(blank=True, null=True, verbose_name='电子邮箱')

    class Meta:
        verbose_name = '客户联系人'
        verbose_name_plural = '客户联系人'

    def __str__(self):
        return f'{self.contact_person} - {self.phone}'


class CallRecord(models.Model):
    """拨号记录模型"""
    phone = models.CharField(max_length=20, verbose_name='电话号码')
    customer_name = models.CharField(
        blank=True,
        max_length=255,
        null=True,
        verbose_name='客户名称')
    call_time = models.DateTimeField(auto_now_add=True, verbose_name='拨号时间')
    duration = models.IntegerField(default=0, verbose_name='通话时长(秒)')
    status = models.IntegerField(
        choices=[(0, '未接通'), (1, '已通话'), (2, '呼叫失败'), (3, '通话中')],
        default=0,
        verbose_name='通话状态'
    )
    call_count = models.IntegerField(default=0, verbose_name='拨通次数')
    flow_id = models.CharField(
        blank=True,
        max_length=100,
        null=True,
        verbose_name='通话流水号')
    remark = models.TextField(blank=True, null=True, verbose_name='备注')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    create_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='call_records',
        verbose_name='创建人'
    )
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.CASCADE,
        related_name='call_records',
        verbose_name='关联客户',
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):
        # 确保call_time不超过当前时间，解决2052年显示错误
        from django.utils import timezone
        now = timezone.now()
        # 只在call_time超过当前时间时才更新，否则保持原有时间
        if not self.call_time or self.call_time > now:
            self.call_time = now
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = '拨号记录'
        verbose_name_plural = '拨号记录'
        ordering = ['-call_time']

    def __str__(self):
        return f'{self.phone} - {self.get_status_display()} - {self.call_time}'


class Customer(models.Model):
    # AI 智能字段扩展 (不破坏原有结构，通过新增 nullable 字段或复用)
    ai_score = models.FloatField(default=0.0, verbose_name='AI客户意向评分', help_text='AI预测的成单概率0-100')
    ai_intent_tags = models.JSONField(default=list, blank=True, verbose_name='AI意向标签', help_text='从沟通记录中自动提取的标签')
    ai_next_followup_suggestion = models.TextField(blank=True, null=True, verbose_name='AI跟进建议')

    # 调整为AutoField匹配原表int UNSIGNED AUTO_INCREMENT约束
    id = models.AutoField(primary_key=True, verbose_name='ID')
    name = models.CharField(
        max_length=255,
        default='',
        blank=True,
        verbose_name='客户名称')

    customer_source = models.ForeignKey(
        'CustomerSource',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='source_id',
        verbose_name='客户来源')
    grade_id = models.PositiveIntegerField(default=0, verbose_name='客户等级ID')
    industry_id = models.PositiveIntegerField(default=0, verbose_name='所属行业ID')
    services_id = models.PositiveIntegerField(default=0, verbose_name='客户意向ID')
    province = models.CharField(
        max_length=100,
        verbose_name='省份',
        default='',
        blank=True)
    city = models.CharField(
        max_length=100,
        verbose_name='城市',
        default='',
        blank=True)
    district = models.CharField(
        max_length=100,
        verbose_name='区/县',
        default='',
        blank=True)
    town = models.CharField(
        max_length=100,
        verbose_name='乡镇/街道',
        default='',
        blank=True)
    address = models.CharField(
        max_length=255,
        verbose_name='详细地址',
        default='',
        blank=True)
    principal = models.ForeignKey(
        Admin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_principals',
        verbose_name='客户负责人')
    intent_status = models.PositiveIntegerField(
        default=0, blank=True, verbose_name='意向状态')  # 原数据库字段类型为int UNSIGNED

    admin_id = models.PositiveIntegerField(
        default=0, blank=True, verbose_name='录入人ID')
    belong_uid = models.PositiveIntegerField(
        default=0, blank=True, verbose_name='所属人ID')
    belong_did = models.PositiveIntegerField(
        default=0, blank=True, verbose_name='所属部门ID')
    belong_time = models.PositiveBigIntegerField(
        default=0, blank=True, verbose_name='获取时间')
    distribute_time = models.PositiveBigIntegerField(
        default=0, verbose_name='最新分配时间')
    follow_time = models.PositiveBigIntegerField(
        default=0, verbose_name='最新跟进时间')
    next_time = models.PositiveBigIntegerField(
        default=0, blank=True, verbose_name='下次跟进时间')
    discard_time = models.BigIntegerField(
        default=0, blank=True, verbose_name='废弃时间')
    share_ids = models.CharField(
        max_length=500,
        default='',
        blank=True,
        verbose_name='共享人员ID')
    file_ids = models.CharField(
        max_length=500,
        default='',
        blank=True,
        verbose_name='附件ids')  # 补充原表mimu_customer的file_ids字段
    content = models.TextField(blank=True, verbose_name='客户描述')
    market = models.TextField(blank=True, verbose_name='主要经营业务')
    remark = models.TextField(blank=True, verbose_name='备注信息')
    tax_bank = models.CharField(
        max_length=255,
        verbose_name='开户银行',
        default='',
        blank=True)
    tax_banksn = models.CharField(
        max_length=255,
        verbose_name='银行账号',
        default='',
        blank=True)
    tax_num = models.CharField(
        max_length=50,
        verbose_name='纳税人识别号',
        default='',
        blank=True)
    tax_mobile = models.CharField(
        max_length=20,
        verbose_name='税务联系电话',
        default='',
        blank=True)
    tax_address = models.CharField(
        max_length=255,
        verbose_name='税务地址',
        default='',
        blank=True)
    is_lock = models.BooleanField(default=False, verbose_name='锁定状态')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.PositiveBigIntegerField(
        default=0, verbose_name='删除时间')  # 原表为bigint UNSIGNED DEFAULT 0

    class Meta:
        db_table = 'mimu_customer'
        verbose_name = '客户表'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['name'], name='idx_customer_name'),
            models.Index(
                fields=['create_time'],
                name='idx_customer_create_time'),
            models.Index(
                fields=['follow_time'],
                name='idx_customer_follow_time'),
            models.Index(
                fields=['delete_time'],
                name='idx_customer_delete_time'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(name__isnull=False) & ~models.Q(name=''),
                name='customer_name_not_empty'
            ),
        ]

    def __str__(self):
        return self.name or f'客户#{self.id}'

    @property
    def is_deleted(self):
        """检查客户是否已删除"""
        return self.delete_time > 0

    @property
    def primary_contact(self):
        """获取主要联系人"""
        return self.contacts.filter(is_primary=True).first()

    @property
    def latest_follow_record(self):
        """获取最新跟进记录"""
        return self.follow_records.first()

    def get_status_display_color(self):
        """获取客户状态显示颜色"""
        # 基于客户的当前状态返回不同的颜色
        if self.discard_time > 0:
            return 'gray'  # 废弃客户
        elif self.belong_uid == 0:
            return 'blue'   # 公海客户
        else:
            return 'green'  # 个人客户

    def get_belong_time_display(self):
        """获取获取时间的显示格式"""
        if self.belong_time and self.belong_time > 0:
            from datetime import datetime
            return datetime.fromtimestamp(
                self.belong_time).strftime('%Y-%m-%d %H:%M:%S')
        return ''

    def get_follow_time_display(self):
        """获取最新跟进时间的显示格式"""
        if self.follow_time and self.follow_time > 0:
            from datetime import datetime
            return datetime.fromtimestamp(
                self.follow_time).strftime('%Y-%m-%d %H:%M:%S')
        return ''

    def get_next_time_display(self):
        """获取下次跟进时间的显示格式"""
        if self.next_time and self.next_time > 0:
            from datetime import datetime
            return datetime.fromtimestamp(
                self.next_time).strftime('%Y-%m-%d %H:%M:%S')
        return ''


class CustomerGrade(models.Model):
    id = models.AutoField(primary_key=True, verbose_name='ID')
    title = models.CharField(max_length=100, default='', verbose_name='客户等级名称')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.PositiveSmallIntegerField(
        default=1, verbose_name='状态')  # 对应原表tinyint(1) UNSIGNED
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.PositiveBigIntegerField(
        default=0, verbose_name='删除时间')

    class Meta:
        db_table = 'mimu_customer_grade'
        verbose_name = '客户等级'
        verbose_name_plural = verbose_name
        unique_together = ('title',)  # 确保客户等级名称的唯一性

    def __str__(self):
        return self.title


class CustomerSource(models.Model):
    # 调整为AutoField匹配原表int UNSIGNED AUTO_INCREMENT约束
    id = models.AutoField(primary_key=True, verbose_name='ID')
    title = models.CharField(max_length=100, default='', verbose_name='客户渠道名称')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.PositiveSmallIntegerField(
        default=1, verbose_name='状态')  # 原表为tinyint(1) UNSIGNED DEFAULT 1
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.PositiveBigIntegerField(
        default=0, verbose_name='删除时间')  # 原表为bigint UNSIGNED DEFAULT 0

    class Meta:
        db_table = 'mimu_customer_source'
        verbose_name = '客户来源'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title


class CustomerField(models.Model):
    FIELD_TYPES = [
        ('text', '单行文本'),
        ('number', '数字'),
        ('date', '日期'),
        ('datetime', '日期时间'),
        ('textarea', '多行文本'),
        ('select', '下拉选择'),
        ('checkbox', '复选框'),
        ('radio', '单选框'),
    ]
    name = models.CharField(max_length=100, verbose_name='字段名称')
    field_name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='字段标识')
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPES,
        verbose_name='字段类型')
    options = models.TextField(blank=True, null=True, verbose_name='选项配置')
    is_required = models.BooleanField(default=False, verbose_name='是否必填')
    is_unique = models.BooleanField(default=False, verbose_name='是否唯一')
    is_list_display = models.BooleanField(default=False, verbose_name='是否列表显示')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='是否启用')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.PositiveBigIntegerField(
        default=0, verbose_name='删除时间')

    class Meta:
        db_table = 'mimu_customer_field'
        verbose_name = '客户自定义字段'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class CustomerCustomFieldValue(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='custom_fields',
        verbose_name='客户')
    field = models.ForeignKey(
        CustomerField,
        on_delete=models.CASCADE,
        verbose_name='自定义字段')
    value = models.TextField(blank=True, null=True, verbose_name='字段值')

    class Meta:
        db_table = 'mimu_customer_custom_field_value'
        verbose_name = '客户自定义字段值'
        verbose_name_plural = verbose_name
        unique_together = ('customer', 'field')

    def __str__(self):
        return f'{self.customer.name} - {self.field.name}: {self.value}'


class FollowRecord(models.Model):
    """客户跟进记录模型"""
    FOLLOW_TYPE_CHOICES = [
        ('phone', '电话沟通'),
        ('visit', '上门拜访'),
        ('email', '邮件联系'),
        ('meeting', '会议洽谈'),
        ('other', '其他'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='follow_records',
        verbose_name='关联客户')
    follow_type = models.CharField(
        max_length=20,
        choices=FOLLOW_TYPE_CHOICES,
        default='phone',
        verbose_name='跟进类型')
    content = models.TextField(verbose_name='跟进内容')
    follow_user = models.ForeignKey(
        Admin, on_delete=models.CASCADE, verbose_name='跟进人')
    follow_time = models.DateTimeField(auto_now_add=True, verbose_name='跟进时间')
    next_follow_time = models.DateTimeField(
        blank=True, null=True, verbose_name='下次跟进时间')
        
    # AI 智能分析扩展字段
    ai_summary = models.TextField(blank=True, null=True, verbose_name='AI自动总结')
    ai_sentiment = models.CharField(max_length=20, blank=True, null=True, verbose_name='客户情绪分析')
    ai_key_points = models.JSONField(default=list, blank=True, verbose_name='提取的关键点')
    
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.PositiveBigIntegerField(
        default=0, verbose_name='删除时间')

    class Meta:
        db_table = 'mimu_customer_follow_record'
        verbose_name = '客户跟进记录'
        verbose_name_plural = verbose_name
        ordering = ['-follow_time']

    def __str__(self):
        return f'{self.customer.name} - {self.get_follow_type_display()}'


class CustomerOrder(models.Model):
    """客户订单模型"""
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('confirmed', '已确认'),
        ('processing', '处理中'),
        ('shipped', '已发货'),
        ('delivered', '已交付'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]

    FINANCE_STATUS_CHOICES = [
        ('pending', '待同步'),
        ('synced', '已同步'),
        ('invoiced', '已开票'),
    ]

    INVOICE_REQUEST_STATUS_CHOICES = [
        ('none', '未申请'),
        ('requested', '已申请'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name='关联客户')
    contract = models.ForeignKey(
        'CustomerContract',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='关联合同')
    order_number = models.CharField(
        max_length=100, unique=True, verbose_name='订单编号')
    product_name = models.CharField(max_length=255, verbose_name='产品名称')
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='订单金额')
    order_date = models.DateField(verbose_name='订单日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='订单状态')
    description = models.TextField(blank=True, verbose_name='订单描述')
    remark = models.TextField(blank=True, verbose_name='备注信息')

    # 财务相关字段
    finance_status = models.CharField(
        max_length=20,
        choices=FINANCE_STATUS_CHOICES,
        default='pending',
        verbose_name='财务状态')
    invoice_request_status = models.CharField(
        max_length=20,
        choices=INVOICE_REQUEST_STATUS_CHOICES,
        default='none',
        verbose_name='开票申请状态')
    invoice_request_time = models.DateTimeField(
        null=True, blank=True, verbose_name='开票申请时间')
    invoice_request_user = models.ForeignKey(
        Admin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_requests',
        verbose_name='开票申请人')

    create_user = models.ForeignKey(
        Admin, on_delete=models.CASCADE, verbose_name='创建人')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.PositiveBigIntegerField(
        default=0, verbose_name='删除时间')
    auto_generated = models.BooleanField(default=False, verbose_name='是否自动生成')

    class Meta:
        db_table = 'mimu_customer_order'
        verbose_name = '客户订单'
        verbose_name_plural = verbose_name
        ordering = ['-order_date']

    def __str__(self):
        return f'{self.customer.name} - {self.order_number}'


class CustomerContract(models.Model):
    """客户合同模型"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('pending', '待审核'),
        ('approved', '已审核'),
        ('signed', '已签订'),
        ('executing', '执行中'),
        ('completed', '已完成'),
        ('terminated', '已终止'),
    ]

    TYPE_CHOICES = [
        ('sales', '销售合同'),
        ('service', '服务合同'),
        ('maintenance', '维护合同'),
        ('consulting', '咨询合同'),
        ('other', '其他'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='contracts',
        verbose_name='关联客户')
    contract_number = models.CharField(
        max_length=100, unique=True, verbose_name='合同编号')
    name = models.CharField(max_length=255, verbose_name='合同名称')
    category_id = models.IntegerField(default=0, verbose_name='分类id')
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='合同金额')
    sign_date = models.DateField(verbose_name='签订日期')
    end_date = models.DateField(blank=True, null=True, verbose_name='到期日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='合同状态')
    contract_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        blank=True,
        verbose_name='合同类型')
    description = models.TextField(blank=True, verbose_name='合同描述')
    remark = models.TextField(blank=True, verbose_name='备注信息')
    create_user = models.ForeignKey(
        Admin, on_delete=models.CASCADE, verbose_name='创建人')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.PositiveBigIntegerField(
        default=0, verbose_name='删除时间')
    auto_generated = models.BooleanField(default=False, verbose_name='是否自动生成')

    class Meta:
        db_table = 'mimu_customer_contract'
        verbose_name = '客户合同'
        verbose_name_plural = verbose_name
        ordering = ['-sign_date']

    def __str__(self):
        return f'{self.customer.name} - {self.name}'


class FollowRecordCustomFieldValue(models.Model):
    """跟进记录自定义字段值模型"""
    follow_record = models.ForeignKey(
        'FollowRecord',
        on_delete=models.CASCADE,
        related_name='custom_fields',
        verbose_name='跟进记录')
    field = models.ForeignKey(
        'FollowField',
        on_delete=models.CASCADE,
        verbose_name='自定义字段')
    value = models.TextField(blank=True, null=True, verbose_name='字段值')

    class Meta:
        db_table = 'mimu_follow_record_custom_field_value'
        verbose_name = '跟进记录自定义字段值'
        verbose_name_plural = verbose_name
        unique_together = ('follow_record', 'field')

    def __str__(self):
        return f'{self.follow_record.customer.name} - {self.field.name}: {self.value}'


class CustomerOrderCustomFieldValue(models.Model):
    """订单自定义字段值模型"""
    order = models.ForeignKey(
        'CustomerOrder',
        on_delete=models.CASCADE,
        related_name='custom_fields',
        verbose_name='订单')
    field = models.ForeignKey(
        'OrderField',
        on_delete=models.CASCADE,
        verbose_name='自定义字段')
    value = models.TextField(blank=True, null=True, verbose_name='字段值')

    class Meta:
        db_table = 'mimu_customer_order_custom_field_value'
        verbose_name = '订单自定义字段值'
        verbose_name_plural = verbose_name
        unique_together = ('order', 'field')

    def __str__(self):
        return f'{self.order.customer.name} - {self.order.order_number} - {self.field.name}: {self.value}'


class CustomerInvoice(models.Model):
    """客户发票模型"""
    TYPE_CHOICES = [
        ('ordinary', '普通发票'),
        ('special', '专用发票'),
        ('electronic', '电子发票'),
    ]

    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('issued', '已开票'),
        ('sent', '已发送'),
        ('received', '已收到'),
        ('paid', '已付款'),
        ('cancelled', '已作废'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name='关联客户')
    invoice_number = models.CharField(
        max_length=100, unique=True, verbose_name='发票编号')
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='发票金额')
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=13.00,
        verbose_name='税率')
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='税额')
    invoice_date = models.DateField(verbose_name='开票日期')
    invoice_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='ordinary',
        verbose_name='发票类型')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='发票状态')
    contract_number = models.CharField(
        max_length=100, blank=True, verbose_name='关联合同编号')
    content = models.TextField(blank=True, verbose_name='发票内容')
    remark = models.TextField(blank=True, verbose_name='备注信息')
    create_user = models.ForeignKey(
        Admin, on_delete=models.CASCADE, verbose_name='创建人')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.PositiveBigIntegerField(
        default=0, verbose_name='删除时间')
    auto_generated = models.BooleanField(default=False, verbose_name='是否自动生成')

    class Meta:
        db_table = 'mimu_customer_invoice'
        verbose_name = '客户发票'
        verbose_name_plural = verbose_name
        ordering = ['-invoice_date']

    def __str__(self):
        return f'{self.customer.name} - {self.invoice_number}'


class CustomerIntent(models.Model):
    """客户意向"""
    id = models.AutoField(primary_key=True, verbose_name='ID')
    name = models.CharField(max_length=100, default='', verbose_name='意向名称')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.PositiveSmallIntegerField(default=1, verbose_name='状态')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.PositiveBigIntegerField(
        default=0, verbose_name='删除时间')

    class Meta:
        db_table = 'mimu_customer_intent'
        verbose_name = '客户意向'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class FollowField(models.Model):
    """跟进字段 - 从basedata迁移"""
    FIELD_TYPES = (
        ('text', '文本'),
        ('number', '数字'),
        ('date', '日期'),
        ('datetime', '日期时间'),
        ('select', '下拉选择'),
        ('textarea', '多行文本'),
        ('checkbox', '复选框'),
        ('radio', '单选框'),
        ('file', '文件上传'),
    )

    name = models.CharField(max_length=100, verbose_name='字段名称')
    field_name = models.CharField(max_length=50, verbose_name='字段标识')
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPES,
        verbose_name='字段类型')
    options = models.TextField(blank=True, verbose_name='选项值')
    is_required = models.BooleanField(default=True, verbose_name='是否必填')
    is_list_display = models.BooleanField(default=True, verbose_name='是否列表显示')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '跟进字段'
        verbose_name_plural = verbose_name
        db_table = 'basedata_follow_field'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class OrderField(models.Model):
    """订单字段 - 从basedata迁移"""
    FIELD_TYPES = (
        ('text', '文本'),
        ('number', '数字'),
        ('decimal', '小数'),
        ('date', '日期'),
        ('datetime', '日期时间'),
        ('select', '下拉选择'),
        ('textarea', '多行文本'),
        ('checkbox', '复选框'),
        ('radio', '单选框'),
    )

    name = models.CharField(max_length=100, verbose_name='字段名称')
    field_name = models.CharField(max_length=50, verbose_name='字段标识')
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPES,
        verbose_name='字段类型')
    options = models.TextField(blank=True, verbose_name='选项值')
    is_required = models.BooleanField(default=True, verbose_name='是否必填')
    is_summary = models.BooleanField(default=False, verbose_name='是否统计字段')
    is_list_display = models.BooleanField(default=True, verbose_name='是否列表显示')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '订单字段'
        verbose_name_plural = verbose_name
        db_table = 'basedata_order_field'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name
