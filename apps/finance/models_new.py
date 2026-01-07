"""
优化后的财务管理模块模型
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.models import (
    SoftDeleteModel, BaseModel, StatusChoices, 
    ApprovalStatusChoices, PaymentStatusChoices
)


class ExpenseCategory(SoftDeleteModel):
    """报销类别"""
    name = models.CharField(max_length=100, verbose_name='类别名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='类别代码')
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='children',
        verbose_name='父类别'
    )
    description = models.TextField(blank=True, verbose_name='类别描述')
    
    # 限额设置
    daily_limit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name='日限额'
    )
    monthly_limit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name='月限额'
    )
    
    # 审批设置
    requires_approval = models.BooleanField(default=True, verbose_name='是否需要审批')
    approval_threshold = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0, 
        verbose_name='审批阈值'
    )
    
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    status = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.ACTIVE, 
        verbose_name='状态'
    )

    class Meta:
        db_table = 'finance_expense_category'
        verbose_name = '报销类别'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['code'], name='idx_exp_cat_code'),
            models.Index(fields=['parent'], name='idx_exp_cat_parent'),
            models.Index(fields=['status'], name='idx_exp_cat_status'),
        ]

    def __str__(self):
        return self.name

    def get_full_name(self):
        """获取完整类别名称"""
        if self.parent:
            return f"{self.parent.get_full_name()} > {self.name}"
        return self.name


class Expense(SoftDeleteModel):
    """优化后的报销模型"""
    code = models.CharField(max_length=100, unique=True, verbose_name='报销编号')
    title = models.CharField(max_length=255, verbose_name='报销标题')
    
    # 使用ForeignKey替代IntegerField
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='expenses', 
        verbose_name='报销人'
    )
    department = models.ForeignKey(
        'user.Department', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='报销部门'
    )
    project = models.ForeignKey(
        'project.Project', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name='关联项目'
    )
    category = models.ForeignKey(
        ExpenseCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name='报销类别'
    )
    
    # 金额信息
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='报销总金额')
    approved_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0, 
        verbose_name='批准金额'
    )
    paid_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0, 
        verbose_name='已付金额'
    )
    
    # 时间字段统一使用DateTimeField
    expense_date = models.DateField(verbose_name='报销日期')
    submit_date = models.DateTimeField(auto_now_add=True, verbose_name='提交日期')
    
    # 审批状态
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
        related_name='approved_expenses',
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    approval_notes = models.TextField(blank=True, verbose_name='审批备注')
    
    # 支付状态
    payment_status = models.CharField(
        max_length=20, 
        choices=PaymentStatusChoices.choices, 
        default=PaymentStatusChoices.UNPAID, 
        verbose_name='支付状态'
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='paid_expenses',
        verbose_name='付款人'
    )
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='付款时间')
    
    # 发票信息
    has_invoice = models.BooleanField(default=False, verbose_name='是否有发票')
    invoice_number = models.CharField(max_length=100, blank=True, verbose_name='发票号码')
    invoice_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name='发票金额'
    )
    
    # 其他信息
    description = models.TextField(blank=True, verbose_name='报销说明')
    remark = models.TextField(blank=True, verbose_name='备注信息')
    attachments = models.TextField(blank=True, verbose_name='附件列表')

    class Meta:
        db_table = 'finance_expense'
        verbose_name = '报销申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code'], name='idx_expense_code'),
            models.Index(fields=['applicant'], name='idx_expense_applicant'),
            models.Index(fields=['approval_status'], name='idx_expense_approval'),
            models.Index(fields=['payment_status'], name='idx_expense_payment'),
            models.Index(fields=['expense_date'], name='idx_expense_date'),
            models.Index(fields=['department'], name='idx_expense_dept'),
            models.Index(fields=['project'], name='idx_expense_project'),
        ]

    def __str__(self):
        return f"{self.code} - {self.title}"

    def save(self, *args, **kwargs):
        # 自动生成报销编号
        if not self.code:
            today = timezone.now().date()
            date_str = today.strftime('%Y%m%d')
            last_expense = Expense.objects.filter(
                code__startswith=f'EXP{date_str}'
            ).order_by('-code').first()
            
            if last_expense and last_expense.code:
                try:
                    last_num = int(last_expense.code[-4:])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            self.code = f'EXP{date_str}{new_num:04d}'
        
        super().save(*args, **kwargs)

    @property
    def remaining_amount(self):
        """剩余未付金额"""
        return self.approved_amount - self.paid_amount

    @property
    def is_fully_paid(self):
        """是否已全额支付"""
        return self.paid_amount >= self.approved_amount

    def get_approval_status_color(self):
        """获取审批状态颜色"""
        status_colors = {
            ApprovalStatusChoices.DRAFT: 'gray',
            ApprovalStatusChoices.PENDING: 'orange',
            ApprovalStatusChoices.IN_REVIEW: 'blue',
            ApprovalStatusChoices.APPROVED: 'green',
            ApprovalStatusChoices.REJECTED: 'red',
            ApprovalStatusChoices.CANCELLED: 'gray',
        }
        return status_colors.get(self.approval_status, 'gray')

    def get_payment_status_color(self):
        """获取支付状态颜色"""
        status_colors = {
            PaymentStatusChoices.UNPAID: 'red',
            PaymentStatusChoices.PARTIAL: 'orange',
            PaymentStatusChoices.PAID: 'green',
            PaymentStatusChoices.REFUNDED: 'blue',
        }
        return status_colors.get(self.payment_status, 'gray')


class ExpenseItem(BaseModel):
    """报销明细"""
    expense = models.ForeignKey(
        Expense, 
        on_delete=models.CASCADE, 
        related_name='items', 
        verbose_name='报销申请'
    )
    category = models.ForeignKey(
        ExpenseCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name='费用类别'
    )
    
    description = models.CharField(max_length=255, verbose_name='费用说明')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='金额')
    expense_date = models.DateField(verbose_name='发生日期')
    
    # 发票信息
    has_invoice = models.BooleanField(default=False, verbose_name='是否有发票')
    invoice_number = models.CharField(max_length=100, blank=True, verbose_name='发票号码')
    
    # 附件
    attachments = models.TextField(blank=True, verbose_name='附件列表')
    remark = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'finance_expense_item'
        verbose_name = '报销明细'
        verbose_name_plural = verbose_name
        ordering = ['expense', 'expense_date']
        indexes = [
            models.Index(fields=['expense'], name='idx_exp_item_expense'),
            models.Index(fields=['category'], name='idx_exp_item_category'),
            models.Index(fields=['expense_date'], name='idx_exp_item_date'),
        ]

    def __str__(self):
        return f"{self.expense.code} - {self.description}"


class Invoice(SoftDeleteModel):
    """优化后的发票模型"""
    code = models.CharField(max_length=100, unique=True, verbose_name='发票编号')
    title = models.CharField(max_length=255, verbose_name='发票标题')
    
    # 使用ForeignKey替代IntegerField
    customer = models.ForeignKey(
        'customer.Customer', 
        on_delete=models.CASCADE, 
        verbose_name='关联客户'
    )
    contract = models.ForeignKey(
        'customer.CustomerContract', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='关联合同'
    )
    project = models.ForeignKey(
        'project.Project', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='关联项目'
    )
    
    # 申请信息
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='invoice_applications',
        verbose_name='申请人'
    )
    department = models.ForeignKey(
        'user.Department', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='申请部门'
    )
    
    # 发票信息
    invoice_type = models.CharField(
        max_length=20,
        choices=[
            ('ordinary', '普通发票'),
            ('special', '专用发票'),
            ('electronic', '电子发票'),
        ],
        default='ordinary',
        verbose_name='发票类型'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='发票金额')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=13.00, verbose_name='税率')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='税额')
    
    # 开票信息
    invoice_title = models.CharField(max_length=200, verbose_name='开票抬头')
    tax_number = models.CharField(max_length=100, verbose_name='纳税人识别号')
    invoice_address = models.CharField(max_length=255, blank=True, verbose_name='开票地址')
    invoice_phone = models.CharField(max_length=50, blank=True, verbose_name='开票电话')
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='开户银行')
    bank_account = models.CharField(max_length=100, blank=True, verbose_name='银行账号')
    
    # 状态信息
    invoice_status = models.CharField(
        max_length=20,
        choices=[
            ('draft', '草稿'),
            ('pending', '待开票'),
            ('issued', '已开票'),
            ('sent', '已发送'),
            ('received', '已收到'),
            ('cancelled', '已作废'),
        ],
        default='draft',
        verbose_name='开票状态'
    )
    
    # 审批状态
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
        related_name='approved_invoices',
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    
    # 开票信息
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='issued_invoices',
        verbose_name='开票人'
    )
    issued_at = models.DateTimeField(null=True, blank=True, verbose_name='开票时间')
    
    # 回款信息
    received_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0, 
        verbose_name='已回款金额'
    )
    payment_status = models.CharField(
        max_length=20, 
        choices=PaymentStatusChoices.choices, 
        default=PaymentStatusChoices.UNPAID, 
        verbose_name='回款状态'
    )
    last_payment_date = models.DateTimeField(null=True, blank=True, verbose_name='最新回款时间')
    
    # 其他信息
    content = models.TextField(blank=True, verbose_name='发票内容')
    remark = models.TextField(blank=True, verbose_name='备注信息')
    attachments = models.TextField(blank=True, verbose_name='附件列表')
    express_number = models.CharField(max_length=100, blank=True, verbose_name='快递单号')

    class Meta:
        db_table = 'finance_invoice'
        verbose_name = '发票管理'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code'], name='idx_invoice_code'),
            models.Index(fields=['customer'], name='idx_invoice_customer'),
            models.Index(fields=['applicant'], name='idx_invoice_applicant'),
            models.Index(fields=['invoice_status'], name='idx_invoice_status'),
            models.Index(fields=['approval_status'], name='idx_invoice_approval'),
            models.Index(fields=['payment_status'], name='idx_invoice_payment'),
        ]

    def __str__(self):
        return f"{self.code} - {self.customer.name}"

    def save(self, *args, **kwargs):
        # 自动生成发票编号
        if not self.code:
            today = timezone.now().date()
            date_str = today.strftime('%Y%m%d')
            last_invoice = Invoice.objects.filter(
                code__startswith=f'INV{date_str}'
            ).order_by('-code').first()
            
            if last_invoice and last_invoice.code:
                try:
                    last_num = int(last_invoice.code[-4:])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            self.code = f'INV{date_str}{new_num:04d}'
        
        # 计算税额
        if self.amount and self.tax_rate:
            self.tax_amount = round(self.amount * self.tax_rate / 100, 2)
        
        super().save(*args, **kwargs)

    @property
    def remaining_amount(self):
        """剩余未回款金额"""
        return self.amount - self.received_amount

    @property
    def is_fully_paid(self):
        """是否已全额回款"""
        return self.received_amount >= self.amount

    def get_invoice_status_color(self):
        """获取开票状态颜色"""
        status_colors = {
            'draft': 'gray',
            'pending': 'orange',
            'issued': 'blue',
            'sent': 'cyan',
            'received': 'green',
            'cancelled': 'red',
        }
        return status_colors.get(self.invoice_status, 'gray')


class PaymentRecord(BaseModel):
    """回款记录"""
    invoice = models.ForeignKey(
        Invoice, 
        on_delete=models.CASCADE, 
        related_name='payment_records', 
        verbose_name='关联发票'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='回款金额')
    payment_date = models.DateField(verbose_name='回款日期')
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('bank_transfer', '银行转账'),
            ('cash', '现金'),
            ('check', '支票'),
            ('online', '在线支付'),
            ('other', '其他'),
        ],
        default='bank_transfer',
        verbose_name='回款方式'
    )
    
    # 银行信息
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='收款银行')
    account_number = models.CharField(max_length=100, blank=True, verbose_name='收款账号')
    transaction_number = models.CharField(max_length=100, blank=True, verbose_name='交易流水号')
    
    # 记录信息
    recorder = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name='记录人'
    )
    remark = models.TextField(blank=True, verbose_name='备注')
    attachments = models.TextField(blank=True, verbose_name='附件列表')
    
    # 审核信息
    is_verified = models.BooleanField(default=False, verbose_name='是否已核实')
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_payments',
        verbose_name='核实人'
    )
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='核实时间')

    class Meta:
        db_table = 'finance_payment_record'
        verbose_name = '回款记录'
        verbose_name_plural = verbose_name
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['invoice'], name='idx_payment_invoice'),
            models.Index(fields=['payment_date'], name='idx_payment_date'),
            models.Index(fields=['recorder'], name='idx_payment_recorder'),
            models.Index(fields=['is_verified'], name='idx_payment_verified'),
        ]

    def __str__(self):
        return f"{self.invoice.code} - ¥{self.amount}"


class Budget(SoftDeleteModel):
    """预算管理"""
    name = models.CharField(max_length=255, verbose_name='预算名称')
    code = models.CharField(max_length=100, unique=True, verbose_name='预算编号')
    
    budget_type = models.CharField(
        max_length=20,
        choices=[
            ('annual', '年度预算'),
            ('quarterly', '季度预算'),
            ('monthly', '月度预算'),
            ('project', '项目预算'),
            ('department', '部门预算'),
        ],
        default='annual',
        verbose_name='预算类型'
    )
    
    # 关联信息
    department = models.ForeignKey(
        'user.Department', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='关联部门'
    )
    project = models.ForeignKey(
        'project.Project', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='关联项目'
    )
    
    # 预算金额
    total_budget = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='预算总额')
    used_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已使用金额')
    
    # 时间范围
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', '草稿'),
            ('active', '生效中'),
            ('completed', '已完成'),
            ('cancelled', '已取消'),
        ],
        default='draft',
        verbose_name='预算状态'
    )
    
    # 负责人
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name='预算负责人'
    )
    
    description = models.TextField(blank=True, verbose_name='预算说明')
    remark = models.TextField(blank=True, verbose_name='备注信息')

    class Meta:
        db_table = 'finance_budget'
        verbose_name = '预算管理'
        verbose_name_plural = verbose_name
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['code'], name='idx_budget_code'),
            models.Index(fields=['budget_type'], name='idx_budget_type'),
            models.Index(fields=['department'], name='idx_budget_dept'),
            models.Index(fields=['project'], name='idx_budget_project'),
            models.Index(fields=['status'], name='idx_budget_status'),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def remaining_budget(self):
        """剩余预算"""
        return self.total_budget - self.used_amount

    @property
    def usage_rate(self):
        """预算使用率"""
        if self.total_budget > 0:
            return round((self.used_amount / self.total_budget) * 100, 2)
        return 0

    @property
    def is_over_budget(self):
        """是否超预算"""
        return self.used_amount > self.total_budget