"""
优化后的客户模型
"""
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.common.models import (
    SoftDeleteModel, StatusChoices, PriorityChoices, 
    OrderStatusChoices, ApprovalStatusChoices, GenderChoices
)


class CustomerSource(SoftDeleteModel):
    """客户来源"""
    title = models.CharField(max_length=100, verbose_name='来源名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='来源代码')
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    status = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.ACTIVE, 
        verbose_name='状态'
    )

    class Meta:
        db_table = 'customer_source'
        verbose_name = '客户来源'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'id']
        indexes = [
            models.Index(fields=['status'], name='idx_customer_source_status'),
            models.Index(fields=['sort_order'], name='idx_customer_source_sort'),
        ]

    def __str__(self):
        return self.title


class CustomerGrade(SoftDeleteModel):
    """客户等级"""
    title = models.CharField(max_length=100, verbose_name='等级名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='等级代码')
    level = models.IntegerField(default=1, verbose_name='等级数值')
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    status = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.ACTIVE, 
        verbose_name='状态'
    )

    class Meta:
        db_table = 'customer_grade'
        verbose_name = '客户等级'
        verbose_name_plural = verbose_name
        ordering = ['level', 'sort_order']
        indexes = [
            models.Index(fields=['level'], name='idx_customer_grade_level'),
            models.Index(fields=['status'], name='idx_customer_grade_status'),
        ]

    def __str__(self):
        return self.title


class CustomerIndustry(SoftDeleteModel):
    """客户行业"""
    name = models.CharField(max_length=100, verbose_name='行业名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='行业代码')
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        verbose_name='父级行业'
    )
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    status = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.ACTIVE, 
        verbose_name='状态'
    )

    class Meta:
        db_table = 'customer_industry'
        verbose_name = '客户行业'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class Customer(SoftDeleteModel):
    """客户主表"""
    # 基本信息
    name = models.CharField(max_length=255, verbose_name='客户名称', db_index=True)
    code = models.CharField(max_length=100, unique=True, blank=True, verbose_name='客户编号')
    
    # 关联信息
    source = models.ForeignKey(
        CustomerSource, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name='客户来源'
    )
    grade = models.ForeignKey(
        CustomerGrade, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name='客户等级'
    )
    industry = models.ForeignKey(
        CustomerIndustry, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name='所属行业'
    )
    
    # 负责人信息
    principal = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_customers', 
        verbose_name='客户负责人'
    )
    department = models.ForeignKey(
        'department.Department', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name='所属部门'
    )
    
    # 地址信息
    province = models.CharField(max_length=100, blank=True, verbose_name='省份')
    city = models.CharField(max_length=100, blank=True, verbose_name='城市')
    district = models.CharField(max_length=100, blank=True, verbose_name='区/县')
    town = models.CharField(max_length=100, blank=True, verbose_name='乡镇/街道')
    address = models.CharField(max_length=500, blank=True, verbose_name='详细地址')
    
    # 状态信息
    status = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.ACTIVE, 
        verbose_name='客户状态'
    )
    intent_level = models.CharField(
        max_length=20, 
        choices=PriorityChoices.choices, 
        default=PriorityChoices.MEDIUM, 
        verbose_name='意向等级'
    )
    
    # 业务信息
    content = models.TextField(blank=True, verbose_name='客户描述')
    market = models.TextField(blank=True, verbose_name='主要经营业务')
    remark = models.TextField(blank=True, verbose_name='备注信息')
    
    # 税务信息
    tax_number = models.CharField(max_length=50, blank=True, verbose_name='纳税人识别号')
    tax_address = models.CharField(max_length=255, blank=True, verbose_name='税务地址')
    tax_phone = models.CharField(max_length=20, blank=True, verbose_name='税务联系电话')
    bank_name = models.CharField(max_length=255, blank=True, verbose_name='开户银行')
    bank_account = models.CharField(max_length=255, blank=True, verbose_name='银行账号')
    
    # 跟进信息
    last_follow_at = models.DateTimeField(null=True, blank=True, verbose_name='最新跟进时间')
    next_follow_at = models.DateTimeField(null=True, blank=True, verbose_name='下次跟进时间')
    assigned_at = models.DateTimeField(null=True, blank=True, verbose_name='分配时间')
    
    # 共享信息
    shared_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        related_name='shared_customers', 
        verbose_name='共享用户'
    )
    
    # 锁定状态
    is_locked = models.BooleanField(default=False, verbose_name='是否锁定')
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='locked_customers', 
        verbose_name='锁定人'
    )
    locked_at = models.DateTimeField(null=True, blank=True, verbose_name='锁定时间')

    class Meta:
        db_table = 'customer'
        verbose_name = '客户'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['name'], name='idx_customer_name'),
            models.Index(fields=['code'], name='idx_customer_code'),
            models.Index(fields=['status'], name='idx_customer_status'),
            models.Index(fields=['principal'], name='idx_customer_principal'),
            models.Index(fields=['last_follow_at'], name='idx_customer_last_follow'),
            models.Index(fields=['next_follow_at'], name='idx_customer_next_follow'),
            models.Index(fields=['created_at'], name='idx_customer_created'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['name'],
                condition=models.Q(is_deleted=False),
                name='unique_customer_name_active'
            ),
            models.UniqueConstraint(
                fields=['code'],
                condition=models.Q(is_deleted=False, code__isnull=False) & ~models.Q(code=''),
                name='unique_customer_code_active'
            ),
        ]

    def __str__(self):
        return self.name or f'客户#{self.id}'

    def save(self, *args, **kwargs):
        # 自动生成客户编号
        if not self.code:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last_customer = Customer.objects.filter(
                code__startswith=f'CUS{date_str}'
            ).order_by('-code').first()
            
            if last_customer and last_customer.code:
                try:
                    last_num = int(last_customer.code[-4:])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            self.code = f'CUS{date_str}{new_num:04d}'
        
        super().save(*args, **kwargs)

    @property
    def primary_contact(self):
        """获取主要联系人"""
        return self.contacts.filter(is_primary=True).first()

    @property
    def latest_follow_record(self):
        """获取最新跟进记录"""
        return self.follow_records.first()

    def get_status_color(self):
        """获取状态颜色"""
        status_colors = {
            StatusChoices.ACTIVE: 'green',
            StatusChoices.INACTIVE: 'red',
            StatusChoices.PENDING: 'orange',
        }
        return status_colors.get(self.status, 'gray')

    def get_intent_color(self):
        """获取意向等级颜色"""
        intent_colors = {
            PriorityChoices.LOW: 'gray',
            PriorityChoices.MEDIUM: 'blue',
            PriorityChoices.HIGH: 'orange',
            PriorityChoices.URGENT: 'red',
        }
        return intent_colors.get(self.intent_level, 'gray')


class CustomerContact(SoftDeleteModel):
    """客户联系人"""
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='contacts', 
        verbose_name='关联客户'
    )
    name = models.CharField(max_length=100, verbose_name='联系人姓名')
    phone = models.CharField(max_length=20, verbose_name='联系电话', db_index=True)
    mobile = models.CharField(max_length=20, blank=True, verbose_name='手机号码')
    email = models.EmailField(blank=True, verbose_name='电子邮箱')
    position = models.CharField(max_length=100, blank=True, verbose_name='职位')
    department = models.CharField(max_length=100, blank=True, verbose_name='部门')
    gender = models.IntegerField(
        choices=GenderChoices.choices, 
        default=GenderChoices.UNKNOWN, 
        verbose_name='性别'
    )
    birthday = models.DateField(null=True, blank=True, verbose_name='生日')
    address = models.CharField(max_length=500, blank=True, verbose_name='地址')
    remark = models.TextField(blank=True, verbose_name='备注')
    is_primary = models.BooleanField(default=False, verbose_name='是否主要联系人')
    is_decision_maker = models.BooleanField(default=False, verbose_name='是否决策人')

    class Meta:
        db_table = 'customer_contact'
        verbose_name = '客户联系人'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['customer'], name='idx_contact_customer'),
            models.Index(fields=['phone'], name='idx_contact_phone'),
            models.Index(fields=['is_primary'], name='idx_contact_primary'),
        ]

    def __str__(self):
        return f'{self.customer.name}-{self.name}'


class CustomerFollowRecord(SoftDeleteModel):
    """客户跟进记录"""
    FOLLOW_TYPE_CHOICES = [
        ('phone', '电话沟通'),
        ('visit', '上门拜访'),
        ('email', '邮件联系'),
        ('meeting', '会议洽谈'),
        ('wechat', '微信沟通'),
        ('qq', 'QQ沟通'),
        ('other', '其他'),
    ]
    
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='follow_records', 
        verbose_name='关联客户'
    )
    follow_type = models.CharField(
        max_length=20, 
        choices=FOLLOW_TYPE_CHOICES, 
        default='phone', 
        verbose_name='跟进类型'
    )
    title = models.CharField(max_length=200, verbose_name='跟进主题')
    content = models.TextField(verbose_name='跟进内容')
    result = models.TextField(blank=True, verbose_name='跟进结果')
    next_plan = models.TextField(blank=True, verbose_name='下步计划')
    
    follow_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name='跟进人'
    )
    follow_time = models.DateTimeField(verbose_name='跟进时间', db_index=True)
    next_follow_time = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name='下次跟进时间',
        db_index=True
    )
    
    # 跟进评价
    satisfaction = models.IntegerField(
        choices=[(i, f'{i}分') for i in range(1, 6)], 
        null=True, 
        blank=True, 
        verbose_name='满意度评分'
    )
    intent_change = models.CharField(
        max_length=20,
        choices=[
            ('increase', '意向增强'),
            ('decrease', '意向减弱'),
            ('unchanged', '无变化'),
        ],
        default='unchanged',
        verbose_name='意向变化'
    )

    class Meta:
        db_table = 'customer_follow_record'
        verbose_name = '客户跟进记录'
        verbose_name_plural = verbose_name
        ordering = ['-follow_time']
        indexes = [
            models.Index(fields=['customer'], name='idx_follow_customer'),
            models.Index(fields=['follow_user'], name='idx_follow_user'),
            models.Index(fields=['follow_time'], name='idx_follow_time'),
            models.Index(fields=['next_follow_time'], name='idx_follow_next_time'),
        ]

    def __str__(self):
        return f'{self.customer.name} - {self.title}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # 更新客户的最新跟进时间
        self.customer.last_follow_at = self.follow_time
        if self.next_follow_time:
            self.customer.next_follow_at = self.next_follow_time
        self.customer.save(update_fields=['last_follow_at', 'next_follow_at'])


class CustomerOrder(SoftDeleteModel):
    """客户订单"""
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='orders', 
        verbose_name='关联客户'
    )
    order_number = models.CharField(max_length=100, unique=True, verbose_name='订单编号')
    title = models.CharField(max_length=255, verbose_name='订单标题')
    product_name = models.CharField(max_length=255, verbose_name='产品名称')
    product_spec = models.TextField(blank=True, verbose_name='产品规格')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name='数量')
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='单价')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='订单总额')
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='优惠金额')
    final_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='最终金额')
    
    order_date = models.DateField(verbose_name='订单日期', db_index=True)
    delivery_date = models.DateField(null=True, blank=True, verbose_name='交付日期')
    
    status = models.CharField(
        max_length=20, 
        choices=OrderStatusChoices.choices, 
        default=OrderStatusChoices.PENDING, 
        verbose_name='订单状态'
    )
    
    description = models.TextField(blank=True, verbose_name='订单描述')
    remark = models.TextField(blank=True, verbose_name='备注信息')
    
    # 负责人
    sales_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sales_orders', 
        verbose_name='销售人员'
    )
    
    # 审批信息
    approval_status = models.CharField(
        max_length=20, 
        choices=ApprovalStatusChoices.choices, 
        default=ApprovalStatusChoices.DRAFT, 
        verbose_name='审批状态'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_orders', 
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')

    class Meta:
        db_table = 'customer_order'
        verbose_name = '客户订单'
        verbose_name_plural = verbose_name
        ordering = ['-order_date']
        indexes = [
            models.Index(fields=['customer'], name='idx_order_customer'),
            models.Index(fields=['order_number'], name='idx_order_number'),
            models.Index(fields=['order_date'], name='idx_order_date'),
            models.Index(fields=['status'], name='idx_order_status'),
            models.Index(fields=['sales_user'], name='idx_order_sales_user'),
        ]

    def __str__(self):
        return f'{self.customer.name} - {self.order_number}'

    def save(self, *args, **kwargs):
        # 自动生成订单编号
        if not self.order_number:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last_order = CustomerOrder.objects.filter(
                order_number__startswith=f'ORD{date_str}'
            ).order_by('-order_number').first()
            
            if last_order and last_order.order_number:
                try:
                    last_num = int(last_order.order_number[-4:])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            self.order_number = f'ORD{date_str}{new_num:04d}'
        
        # 计算最终金额
        if self.total_amount is not None and self.discount_amount is not None:
            self.final_amount = self.total_amount - self.discount_amount
        
        super().save(*args, **kwargs)

    def get_status_color(self):
        """获取状态颜色"""
        status_colors = {
            OrderStatusChoices.PENDING: 'orange',
            OrderStatusChoices.CONFIRMED: 'blue',
            OrderStatusChoices.PROCESSING: 'cyan',
            OrderStatusChoices.SHIPPED: 'purple',
            OrderStatusChoices.DELIVERED: 'green',
            OrderStatusChoices.COMPLETED: 'green',
            OrderStatusChoices.CANCELLED: 'red',
        }
        return status_colors.get(self.status, 'gray')


class CustomerContract(SoftDeleteModel):
    """客户合同"""
    CONTRACT_TYPE_CHOICES = [
        ('sales', '销售合同'),
        ('service', '服务合同'),
        ('maintenance', '维护合同'),
        ('consulting', '咨询合同'),
        ('framework', '框架合同'),
        ('other', '其他'),
    ]
    
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('pending', '待审核'),
        ('approved', '已审核'),
        ('signed', '已签订'),
        ('executing', '执行中'),
        ('completed', '已完成'),
        ('terminated', '已终止'),
        ('expired', '已过期'),
    ]
    
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='contracts', 
        verbose_name='关联客户'
    )
    contract_number = models.CharField(max_length=100, unique=True, verbose_name='合同编号')
    title = models.CharField(max_length=255, verbose_name='合同标题')
    contract_type = models.CharField(
        max_length=20, 
        choices=CONTRACT_TYPE_CHOICES, 
        default='sales', 
        verbose_name='合同类型'
    )
    
    # 金额信息
    contract_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='合同金额')
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已付金额')
    
    # 时间信息
    sign_date = models.DateField(verbose_name='签订日期', db_index=True)
    start_date = models.DateField(null=True, blank=True, verbose_name='开始日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='结束日期')
    
    # 状态
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='draft', 
        verbose_name='合同状态'
    )
    
    # 内容
    description = models.TextField(blank=True, verbose_name='合同描述')
    terms = models.TextField(blank=True, verbose_name='合同条款')
    remark = models.TextField(blank=True, verbose_name='备注信息')
    
    # 负责人
    sales_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sales_contracts', 
        verbose_name='销售人员'
    )
    
    # 审批信息
    approval_status = models.CharField(
        max_length=20, 
        choices=ApprovalStatusChoices.choices, 
        default=ApprovalStatusChoices.DRAFT, 
        verbose_name='审批状态'
    )

    class Meta:
        db_table = 'customer_contract'
        verbose_name = '客户合同'
        verbose_name_plural = verbose_name
        ordering = ['-sign_date']
        indexes = [
            models.Index(fields=['customer'], name='idx_contract_customer'),
            models.Index(fields=['contract_number'], name='idx_contract_number'),
            models.Index(fields=['sign_date'], name='idx_contract_sign_date'),
            models.Index(fields=['status'], name='idx_contract_status'),
            models.Index(fields=['sales_user'], name='idx_contract_sales_user'),
        ]

    def __str__(self):
        return f'{self.customer.name} - {self.title}'

    def save(self, *args, **kwargs):
        # 自动生成合同编号（日期+序号格式：YYYYMMDD+4位序号）
        if not self.contract_number:
            from django.utils import timezone
            
            # 使用签订日期或当前日期
            if self.sign_date:
                date_str = self.sign_date.strftime('%Y%m%d')
            else:
                date_str = timezone.now().strftime('%Y%m%d')
            
            # 查找当日已存在的最大序号
            last_contract = CustomerContract.objects.filter(
                contract_number__startswith=date_str
            ).order_by('-contract_number').first()
            
            if last_contract and last_contract.contract_number:
                try:
                    # 提取序号部分（假设编号格式为YYYYMMDDXXXX）
                    if len(last_contract.contract_number) >= 12:
                        last_num = int(last_contract.contract_number[8:12])
                        new_num = last_num + 1
                    else:
                        new_num = 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            # 生成新编号：YYYYMMDD + 4位序号
            self.contract_number = f'{date_str}{new_num:04d}'
        
        super().save(*args, **kwargs)
    
    def clean_contract_number(self):
        """验证合同编号格式"""
        contract_number = self.contract_number
        
        # 检查编号是否为空
        if not contract_number:
            raise ValidationError('合同编号不能为空')
        
        # 检查编号长度（YYYYMMDDXXXX格式应为12位）
        if len(contract_number) != 12:
            raise ValidationError('合同编号格式不正确，应为12位（YYYYMMDD+4位序号）')
        
        # 检查前8位是否为有效日期
        try:
            from datetime import datetime
            date_part = contract_number[:8]
            datetime.strptime(date_part, '%Y%m%d')
        except ValueError:
            raise ValidationError('合同编号中的日期格式不正确')
        
        # 检查后4位是否为数字
        try:
            int(contract_number[8:])
        except ValueError:
            raise ValidationError('合同编号中的序号部分应为数字')
        
        # 检查编号是否已存在（排除当前记录）
        existing = CustomerContract.objects.filter(
            contract_number=contract_number
        ).exclude(pk=self.pk).first()
        
        if existing:
            raise ValidationError('合同编号已存在，请使用其他编号')

    @property
    def remaining_amount(self):
        """剩余金额"""
        return self.contract_amount - self.paid_amount

    @property
    def payment_progress(self):
        """付款进度百分比"""
        if self.contract_amount > 0:
            return round((self.paid_amount / self.contract_amount) * 100, 2)
        return 0

    def get_status_color(self):
        """获取状态颜色"""
        status_colors = {
            'draft': 'gray',
            'pending': 'orange',
            'approved': 'blue',
            'signed': 'green',
            'executing': 'cyan',
            'completed': 'green',
            'terminated': 'red',
            'expired': 'red',
        }
        return status_colors.get(self.status, 'gray')


# 保留原有的SpiderTask模型以兼容现有代码
class SpiderTask(SoftDeleteModel):
    """爬虫任务"""
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='spider_tasks', 
        verbose_name='关联客户', 
        null=True, 
        blank=True
    )
    
    STATUS_CHOICES = [
        ('running', '运行中'),
        ('stopped', '已停止'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    
    task_name = models.CharField(max_length=255, verbose_name='任务名称')
    spider_keywords = models.TextField(verbose_name='爬虫关键词')
    data_region = models.CharField(max_length=255, blank=True, verbose_name='数据地区限制')
    industry_limit = models.CharField(max_length=255, blank=True, verbose_name='行业限制')
    province = models.CharField(max_length=255, blank=True, verbose_name='省份地区')
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='stopped', 
        verbose_name='状态'
    )
    
    create_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name='创建人'
    )

    class Meta:
        db_table = 'customer_spider_task'
        verbose_name = '爬虫任务'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.task_name