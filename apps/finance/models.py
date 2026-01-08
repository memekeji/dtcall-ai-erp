"""
财务管理模块模型
完整优化的财务管理模型，支持报销、发票、回款、付款等核心功能
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
import json
from apps.common.models import (
    SoftDeleteModel, BaseModel, StatusChoices,
    ApprovalStatusChoices, PaymentStatusChoices
)


class InvoiceTypeChoices:
    """发票类型选择"""
    ORDINARY = 'ordinary'
    SPECIAL = 'special'
    ELECTRONIC = 'electronic'
    CHOICES = [
        (ORDINARY, '普通发票'),
        (SPECIAL, '增值税专用发票'),
        (ELECTRONIC, '电子发票'),
    ]


class InvoiceStatusChoices:
    """发票状态选择"""
    DRAFT = 'draft'
    PENDING = 'pending'
    ISSUED = 'issued'
    SENT = 'sent'
    RECEIVED = 'received'
    CANCELLED = 'cancelled'
    CHOICES = [
        (DRAFT, '草稿'),
        (PENDING, '待开票'),
        (ISSUED, '已开票'),
        (SENT, '已发送'),
        (RECEIVED, '已收到'),
        (CANCELLED, '已作废'),
    ]


class IncomeStatusChoices:
    """回款状态选择"""
    UNPAID = 'unpaid'
    PARTIAL = 'partial'
    PAID = 'paid'
    CHOICES = [
        (UNPAID, '未回款'),
        (PARTIAL, '部分回款'),
        (PAID, '已回款'),
    ]


class PaymentMethodChoices:
    """支付方式选择"""
    BANK_TRANSFER = 'bank_transfer'
    CASH = 'cash'
    CHECK = 'check'
    ONLINE = 'online'
    CHOICES = [
        (BANK_TRANSFER, '银行转账'),
        (CASH, '现金'),
        (CHECK, '支票'),
        (ONLINE, '在线支付'),
    ]


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

    requires_approval = models.BooleanField(default=True, verbose_name='是否需要审批')
    approval_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name='审批阈值'
    )
    approval_flow = models.ForeignKey(
        'approval.ApprovalFlow',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='审批流程'
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
        if self.parent:
            return f"{self.parent.get_full_name()} > {self.name}"
        return self.name


class Expense(SoftDeleteModel):
    """报销申请"""
    code = models.CharField(max_length=100, unique=True, verbose_name='报销编号')
    title = models.CharField(max_length=255, verbose_name='报销标题')

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

    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='报销总金额'
    )
    approved_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name='批准金额'
    )
    paid_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name='已付金额'
    )

    expense_date = models.DateField(verbose_name='报销日期')
    submit_date = models.DateTimeField(auto_now_add=True, verbose_name='提交日期')

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

    has_invoice = models.BooleanField(default=False, verbose_name='是否有发票')
    invoice_number = models.CharField(max_length=100, blank=True, verbose_name='发票号码')
    invoice_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='发票金额'
    )

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
        return self.approved_amount - self.paid_amount

    @property
    def is_fully_paid(self):
        return self.paid_amount >= self.approved_amount

    @property
    def can_submit(self):
        return self.approval_status in [
            ApprovalStatusChoices.DRAFT,
            ApprovalStatusChoices.REJECTED,
            ApprovalStatusChoices.CANCELLED
        ]

    @property
    def can_approve(self):
        return self.approval_status == ApprovalStatusChoices.PENDING

    @property
    def can_pay(self):
        return self.approval_status == ApprovalStatusChoices.APPROVED and \
               self.payment_status in [PaymentStatusChoices.UNPAID, PaymentStatusChoices.PARTIAL]

    def get_approval_status_display(self):
        return dict(ApprovalStatusChoices.choices).get(self.approval_status, '未知')

    def get_payment_status_display(self):
        return dict(PaymentStatusChoices.choices).get(self.payment_status, '未知')


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
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='金额'
    )
    expense_date = models.DateField(verbose_name='发生日期')

    has_invoice = models.BooleanField(default=False, verbose_name='是否有发票')
    invoice_number = models.CharField(max_length=100, blank=True, verbose_name='发票号码')

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
    """发票"""
    code = models.CharField(max_length=100, unique=True, verbose_name='发票编号')
    title = models.CharField(max_length=255, verbose_name='发票标题')

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

    invoice_type = models.CharField(
        max_length=20,
        choices=InvoiceTypeChoices.CHOICES,
        default=InvoiceTypeChoices.ORDINARY,
        verbose_name='发票类型'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='发票金额'
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('13.00'),
        verbose_name='税率'
    )
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name='税额'
    )

    invoice_title = models.CharField(max_length=200, verbose_name='开票抬头')
    tax_number = models.CharField(max_length=100, verbose_name='纳税人识别号')
    invoice_address = models.CharField(max_length=255, blank=True, verbose_name='开票地址')
    invoice_phone = models.CharField(max_length=50, blank=True, verbose_name='开票电话')
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='开户银行')
    bank_account = models.CharField(max_length=100, blank=True, verbose_name='银行账号')

    invoice_status = models.CharField(
        max_length=20,
        choices=InvoiceStatusChoices.CHOICES,
        default=InvoiceStatusChoices.DRAFT,
        verbose_name='开票状态'
    )

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

    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_invoices',
        verbose_name='开票人'
    )
    issued_at = models.DateTimeField(null=True, blank=True, verbose_name='开票时间')

    delivery = models.CharField(max_length=100, blank=True, verbose_name='快递单号')
    delivery_company = models.CharField(max_length=100, blank=True, verbose_name='快递公司')

    enter_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name='已回款金额'
    )
    enter_status = models.CharField(
        max_length=20,
        choices=IncomeStatusChoices.CHOICES,
        default=IncomeStatusChoices.UNPAID,
        verbose_name='回款状态'
    )

    description = models.TextField(blank=True, verbose_name='发票说明')
    remark = models.TextField(blank=True, verbose_name='备注信息')
    attachments = models.TextField(blank=True, verbose_name='附件列表')

    class Meta:
        db_table = 'finance_invoice'
        verbose_name = '发票'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code'], name='idx_invoice_code'),
            models.Index(fields=['customer'], name='idx_invoice_customer'),
            models.Index(fields=['invoice_status'], name='idx_invoice_status'),
            models.Index(fields=['approval_status'], name='idx_invoice_approval'),
            models.Index(fields=['enter_status'], name='idx_invoice_enter'),
        ]

    def __str__(self):
        return f"{self.code} - {self.title}"

    def save(self, *args, **kwargs):
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

        if self.tax_rate and self.amount:
            self.tax_amount = self.amount * self.tax_rate / Decimal('100')

        super().save(*args, **kwargs)

    @property
    def unpaid_amount(self):
        return self.amount - self.enter_amount

    @property
    def is_fully_paid(self):
        return self.enter_amount >= self.amount

    def get_invoice_status_display(self):
        return dict(InvoiceStatusChoices.CHOICES).get(self.invoice_status, '未知')

    def get_enter_status_display(self):
        return dict(IncomeStatusChoices.CHOICES).get(self.enter_status, '未知')


class InvoiceVerifyRecord(BaseModel):
    """发票核销记录"""
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='verify_records',
        verbose_name='关联发票'
    )
    income = models.ForeignKey(
        'Income',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verify_records',
        verbose_name='关联回款'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='核销金额'
    )
    verify_time = models.DateTimeField(auto_now_add=True, verbose_name='核销时间')
    remark = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'finance_invoice_verify'
        verbose_name = '发票核销记录'
        verbose_name_plural = verbose_name
        ordering = ['-verify_time']

    def __str__(self):
        return f"{self.invoice.code} - 核销 {self.amount}"


class Income(SoftDeleteModel):
    """回款记录"""
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='incomes',
        verbose_name='关联发票'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='回款金额'
    )
    income_date = models.DateField(verbose_name='回款日期')

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethodChoices.CHOICES,
        default=PaymentMethodChoices.BANK_TRANSFER,
        verbose_name='支付方式'
    )

    bank_name = models.CharField(max_length=100, blank=True, verbose_name='银行名称')
    bank_account = models.CharField(max_length=100, blank=True, verbose_name='银行账号')
    transaction_no = models.CharField(max_length=100, blank=True, verbose_name='交易流水号')

    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_incomes',
        verbose_name='确认人'
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')

    remark = models.TextField(blank=True, verbose_name='备注')
    attachments = models.TextField(blank=True, verbose_name='附件列表')

    class Meta:
        db_table = 'finance_income'
        verbose_name = '回款记录'
        verbose_name_plural = verbose_name
        ordering = ['-income_date']
        indexes = [
            models.Index(fields=['invoice'], name='idx_income_invoice'),
            models.Index(fields=['income_date'], name='idx_income_date'),
        ]

    def __str__(self):
        return f"回款-{self.invoice.code}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._update_invoice_status()

    def _update_invoice_status(self):
        if self.invoice:
            total_income = self.invoice.incomes.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')

            self.invoice.enter_amount = total_income
            if total_income >= self.invoice.amount:
                self.invoice.enter_status = IncomeStatusChoices.PAID
            elif total_income > 0:
                self.invoice.enter_status = IncomeStatusChoices.PARTIAL
            else:
                self.invoice.enter_status = IncomeStatusChoices.UNPAID
            self.invoice.save(update_fields=['enter_amount', 'enter_status'])

    def get_payment_method_display(self):
        return dict(PaymentMethodChoices.CHOICES).get(self.payment_method, '未知')


class Payment(SoftDeleteModel):
    """付款记录"""
    expense = models.ForeignKey(
        Expense,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='关联报销'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='付款金额'
    )
    payment_date = models.DateField(verbose_name='付款日期')

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethodChoices.CHOICES,
        default=PaymentMethodChoices.BANK_TRANSFER,
        verbose_name='支付方式'
    )

    bank_name = models.CharField(max_length=100, blank=True, verbose_name='银行名称')
    bank_account = models.CharField(max_length=100, blank=True, verbose_name='银行账号')
    transaction_no = models.CharField(max_length=100, blank=True, verbose_name='交易流水号')

    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_payments',
        verbose_name='确认人'
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')

    remark = models.TextField(blank=True, verbose_name='备注')
    attachments = models.TextField(blank=True, verbose_name='附件列表')

    class Meta:
        db_table = 'finance_payment'
        verbose_name = '付款记录'
        verbose_name_plural = verbose_name
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['expense'], name='idx_payment_expense'),
            models.Index(fields=['payment_date'], name='idx_payment_date'),
        ]

    def __str__(self):
        return f"付款-{self.expense.code}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._update_expense_status()

    def _update_expense_status(self):
        if self.expense:
            total_payment = self.expense.payments.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')

            self.expense.paid_amount = total_payment
            if total_payment >= self.expense.approved_amount:
                self.expense.payment_status = PaymentStatusChoices.PAID
            elif total_payment > 0:
                self.expense.payment_status = PaymentStatusChoices.PARTIAL
            self.expense.save(update_fields=['paid_amount', 'payment_status'])

    def get_payment_method_display(self):
        return dict(PaymentMethodChoices.CHOICES).get(self.payment_method, '未知')


class OrderFinanceRecord(SoftDeleteModel):
    """订单财务记录"""
    order = models.OneToOneField(
        'customer.CustomerOrder',
        on_delete=models.CASCADE,
        verbose_name='关联订单'
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='订单总金额'
    )
    paid_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name='已付金额'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.UNPAID,
        verbose_name='付款状态'
    )
    due_date = models.DateField(null=True, blank=True, verbose_name='付款到期日')

    class Meta:
        db_table = 'finance_order_record'
        verbose_name = '订单财务记录'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"财务记录-{self.order.order_number}"

    @property
    def unpaid_amount(self):
        return self.total_amount - self.paid_amount


class InvoiceRequest(SoftDeleteModel):
    """开票申请"""
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
        ('invoiced', '已开票'),
    ]

    order = models.ForeignKey(
        'customer.CustomerOrder',
        on_delete=models.CASCADE,
        verbose_name='关联订单'
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='申请人'
    )
    department_id = models.IntegerField(default=0, verbose_name='申请部门ID')
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='开票金额'
    )
    invoice_type = models.CharField(
        max_length=20,
        choices=InvoiceTypeChoices.CHOICES,
        default=InvoiceTypeChoices.ORDINARY,
        verbose_name='发票类型'
    )
    invoice_title = models.CharField(max_length=200, verbose_name='开票抬头')
    tax_number = models.CharField(max_length=100, blank=True, verbose_name='纳税人识别号')
    reason = models.TextField(verbose_name='申请理由')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='申请状态'
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_invoice_requests',
        verbose_name='审核人'
    )
    review_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    review_comment = models.TextField(blank=True, verbose_name='审核意见')

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='关联发票'
    )
    invoice_time = models.DateTimeField(null=True, blank=True, verbose_name='开票时间')

    class Meta:
        db_table = 'finance_invoice_request'
        verbose_name = '开票申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"开票申请-{self.order.order_number}"


class ReimbursementType(SoftDeleteModel):
    """报销类型"""
    name = models.CharField(max_length=100, verbose_name='报销类型名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='类型代码')
    description = models.TextField(blank=True, verbose_name='类型描述')
    max_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='最大报销金额'
    )
    requires_approval = models.BooleanField(default=True, verbose_name='是否需要审批')
    approval_flow = models.ForeignKey(
        'approval.ApprovalFlow',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='审批流程'
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
        verbose_name='状态'
    )

    class Meta:
        db_table = 'finance_reimbursement_type'
        verbose_name = '报销类型'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class ExpenseType(SoftDeleteModel):
    """费用类型"""
    name = models.CharField(max_length=100, verbose_name='费用类型名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='费用代码')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级费用类型'
    )
    description = models.TextField(blank=True, verbose_name='费用描述')
    budget_control = models.BooleanField(default=False, verbose_name='是否预算控制')
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
        verbose_name='状态'
    )

    class Meta:
        db_table = 'finance_expense_type'
        verbose_name = '费用类型'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name
