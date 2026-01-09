"""
财务管理模块模型
只包含有数据库表的模型
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import json


class FinanceStatus:
    """财务相关状态常量"""
    EXPENSE_CHECK_PENDING = 0
    EXPENSE_CHECK_PROCESSING = 1
    EXPENSE_CHECK_APPROVED = 2
    EXPENSE_CHECK_REJECTED = 3
    EXPENSE_CHECK_CANCELLED = 4

    PAY_STATUS_PENDING = 0
    PAY_STATUS_PAID = 1

    INVOICE_OPEN_STATUS_NOT = 0
    INVOICE_OPEN_STATUS_DONE = 1
    INVOICE_OPEN_STATUS_VOID = 2

    ENTER_STATUS_NOT = 0
    ENTER_STATUS_PARTIAL = 1
    ENTER_STATUS_FULL = 2

    INVOICE_TYPE_SPECIAL = 1
    INVOICE_TYPE_ORDINARY = 2
    INVOICE_TYPE_ELECTRONIC = 3


class FinanceStatusMapping:
    """财务状态映射字典"""
    CHECK_STATUS_MAP = {
        0: '待审核',
        1: '审核中',
        2: '审核通过',
        3: '审核不通过',
        4: '撤销审核'
    }

    PAY_STATUS_MAP = {
        0: '待打款',
        1: '已打款'
    }

    OPEN_STATUS_MAP = {
        0: '未开票',
        1: '已开票',
        2: '已作废'
    }

    ENTER_STATUS_MAP = {
        0: '未回款',
        1: '部分回款',
        2: '全部回款'
    }

    INVOICE_TYPE_MAP = {
        1: '增值税专用发票',
        2: '普通发票',
        3: '电子发票'
    }


class InvoiceStatusChoices:
    DRAFT = 'draft'
    PENDING = 'pending'
    ISSUED = 'issued'
    CANCELLED = 'cancelled'

    CHOICES = [
        (DRAFT, '草稿'),
        (PENDING, '待开票'),
        (ISSUED, '已开票'),
        (CANCELLED, '已作废'),
    ]


class IncomeStatusChoices:
    UNPAID = 'unpaid'
    PARTIAL = 'partial'
    PAID = 'paid'

    CHOICES = [
        (UNPAID, '未回款'),
        (PARTIAL, '部分回款'),
        (PAID, '全部回款'),
    ]


class PaymentMethodChoices:
    BANK_TRANSFER = 'bank_transfer'
    CASH = 'cash'
    CHECK = 'check'
    ONLINE = 'online'
    OTHER = 'other'

    CHOICES = [
        (BANK_TRANSFER, '银行转账'),
        (CASH, '现金'),
        (CHECK, '支票'),
        (ONLINE, '在线支付'),
        (OTHER, '其他'),
    ]


class Expense(models.Model):
    """报销申请"""
    code = models.CharField(max_length=100, default='', verbose_name='报销编码')
    subject_id = models.IntegerField(default=0, verbose_name='报销企业主体')
    admin_id = models.PositiveIntegerField(default=0, verbose_name='报销人ID')
    did = models.IntegerField(default=0, verbose_name='报销部门ID')
    project_id = models.IntegerField(default=0, verbose_name='关联项目ID')
    cost = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='报销总金额')
    income_month = models.IntegerField(default=0, verbose_name='入账月份')
    expense_time = models.BigIntegerField(default=0, verbose_name='原始单据日期')
    file_ids = models.CharField(max_length=500, default='', verbose_name='附件ID')
    pay_status = models.SmallIntegerField(default=0, verbose_name='打款状态：0待打款,1已打款')
    pay_admin_id = models.IntegerField(default=0, verbose_name='打款人ID')
    pay_time = models.BigIntegerField(default=0, verbose_name='最后打款时间')
    check_status = models.SmallIntegerField(default=0, verbose_name='审核状态:0待审核,1审核中,2审核通过,3审核不通过,4撤销审核')
    check_flow_id = models.IntegerField(default=0, verbose_name='审核流程id')
    check_step_sort = models.IntegerField(default=0, verbose_name='当前审批步骤')
    check_uids = models.CharField(max_length=500, default='', verbose_name='当前审批人ID')
    check_last_uid = models.CharField(max_length=500, default='', verbose_name='上一审批人ID')
    check_history_uids = models.CharField(max_length=500, default='', verbose_name='历史审批人ID')
    check_copy_uids = models.CharField(max_length=500, default='', verbose_name='抄送人ID')
    check_time = models.BigIntegerField(default=0, verbose_name='审核通过时间')
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')
    remark = models.TextField(blank=True, verbose_name='备注')
    auto_generated = models.BooleanField(default=False, verbose_name='是否自动生成')

    class Meta:
        db_table = 'finance_expense'
        verbose_name = '报销申请'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.code

    def get_check_status_display(self):
        return FinanceStatusMapping.CHECK_STATUS_MAP.get(self.check_status, '未知')

    def get_pay_status_display(self):
        return FinanceStatusMapping.PAY_STATUS_MAP.get(self.pay_status, '未知')


class Income(models.Model):
    """回款记录"""
    invoice_id = models.BigIntegerField(default=0, verbose_name='关联发票ID')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='到账金额')
    income_date = models.DateTimeField(verbose_name='到账日期')
    file_ids = models.CharField(max_length=500, default='', verbose_name='附件ID')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')

    class Meta:
        db_table = 'finance_income'
        verbose_name = '回款记录'
        verbose_name_plural = verbose_name
        ordering = ['-income_date']

    def __str__(self):
        return f"回款-{self.id}"


class InvoiceVerifyRecord(models.Model):
    """发票核销记录"""
    invoice_id = models.BigIntegerField(default=0, verbose_name='关联发票ID')
    income = models.ForeignKey(
        Income, 
        on_delete=models.CASCADE, 
        related_name='verify_records',
        verbose_name='关联回款'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='核销金额')
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')

    class Meta:
        db_table = 'finance_invoice_verify_record'
        verbose_name = '发票核销记录'
        verbose_name_plural = verbose_name
        ordering = ['-id']

    def __str__(self):
        return f"核销-{self.id}"


class Invoice(models.Model):
    """发票"""
    code = models.CharField(max_length=100, default='', verbose_name='发票号码')
    customer_id = models.IntegerField(default=0, verbose_name='关联客户ID')
    contract_id = models.BigIntegerField(default=0, verbose_name='关联合同ID')
    project_id = models.BigIntegerField(default=0, verbose_name='关联项目ID')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='发票金额')
    did = models.IntegerField(default=0, verbose_name='发票申请部门')
    admin_id = models.PositiveIntegerField(default=0, verbose_name='发票申请人ID')
    open_status = models.SmallIntegerField(default=0, verbose_name='开票状态：0未开票 1已开票 2已作废')
    open_admin_id = models.IntegerField(default=0, verbose_name='发票开具人')
    open_time = models.BigIntegerField(default=0, verbose_name='发票开具时间')
    delivery = models.CharField(max_length=100, default='', verbose_name='快递单号')
    types = models.SmallIntegerField(default=0, verbose_name='抬头类型：1企业2个人')
    invoice_type = models.SmallIntegerField(default=0, verbose_name='发票类型')
    invoice_subject = models.IntegerField(default=0, verbose_name='关联发票主体ID')
    invoice_title = models.CharField(max_length=100, default='', verbose_name='开票抬头')
    invoice_tax = models.CharField(max_length=100, default='', verbose_name='纳税人识别号')
    invoice_phone = models.CharField(max_length=100, default='', verbose_name='电话号码')
    invoice_address = models.CharField(max_length=100, default='', verbose_name='地址')
    invoice_bank = models.CharField(max_length=100, default='', verbose_name='开户银行')
    invoice_account = models.CharField(max_length=100, default='', verbose_name='银行账号')
    invoice_banking = models.CharField(max_length=100, default='', verbose_name='银行营业网点')
    file_ids = models.CharField(max_length=500, default='', verbose_name='附件ID')
    other_file_ids = models.CharField(max_length=500, default='', verbose_name='其他附件ID')
    enter_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'), verbose_name='已到账金额')
    enter_status = models.SmallIntegerField(default=0, verbose_name='回款状态：0未回款 1部分回款 2全部回款')
    enter_time = models.BigIntegerField(default=0, verbose_name='最新回款时间')
    check_status = models.SmallIntegerField(default=0, verbose_name='审核状态')
    check_flow_id = models.IntegerField(default=0, verbose_name='审核流程id')
    check_step_sort = models.IntegerField(default=0, verbose_name='当前审批步骤')
    check_uids = models.CharField(max_length=500, default='', verbose_name='当前审批人ID')
    check_last_uid = models.CharField(max_length=500, default='', verbose_name='上一审批人ID')
    check_history_uids = models.CharField(max_length=500, default='', verbose_name='历史审批人ID')
    check_copy_uids = models.CharField(max_length=500, default='', verbose_name='抄送人ID')
    check_time = models.BigIntegerField(default=0, verbose_name='审核通过时间')
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')
    remark = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'finance_invoice'
        verbose_name = '发票'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.code

    def get_open_status_display(self):
        return FinanceStatusMapping.OPEN_STATUS_MAP.get(self.open_status, '未知')

    def get_enter_status_display(self):
        return FinanceStatusMapping.ENTER_STATUS_MAP.get(self.enter_status, '未知')

    def get_invoice_type_display(self):
        return FinanceStatusMapping.INVOICE_TYPE_MAP.get(self.invoice_type, '未知')


class Payment(models.Model):
    """付款记录"""
    expense_id = models.BigIntegerField(default=0, verbose_name='关联报销ID')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='打款金额')
    payment_date = models.DateTimeField(verbose_name='打款日期')
    file_ids = models.CharField(max_length=500, default='', verbose_name='附件ID')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')

    class Meta:
        db_table = 'finance_payment'
        verbose_name = '付款记录'
        verbose_name_plural = verbose_name
        ordering = ['-payment_date']

    def __str__(self):
        return f"付款-{self.id}"


class InvoiceRequest(models.Model):
    """开票申请"""
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
        ('invoiced', '已开票'),
    ]

    order_id = models.IntegerField(default=0, verbose_name='关联订单ID')
    applicant_id = models.IntegerField(default=0, verbose_name='申请人ID')
    department_id = models.IntegerField(default=0, verbose_name='申请部门ID')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='开票金额')
    invoice_type = models.SmallIntegerField(default=2, verbose_name='发票类型')
    invoice_title = models.CharField(max_length=200, verbose_name='开票抬头')
    tax_number = models.CharField(max_length=100, blank=True, verbose_name='纳税人识别号')
    reason = models.TextField(verbose_name='申请理由')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='申请状态')
    reviewer_id = models.IntegerField(default=0, verbose_name='审核人ID')
    review_time = models.BigIntegerField(default=0, verbose_name='审核时间')
    review_comment = models.TextField(blank=True, verbose_name='审核意见')
    invoice_id = models.IntegerField(default=0, verbose_name='关联发票ID')
    invoice_time = models.BigIntegerField(default=0, verbose_name='开票时间')
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')
    remark = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'finance_invoice_request'
        verbose_name = '开票申请'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"开票申请-{self.id}"

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, '未知')


class OrderFinanceRecord(models.Model):
    """订单财务记录"""
    PAYMENT_STATUS_CHOICES = [
        ('pending', '待付款'),
        ('partial', '部分付款'),
        ('paid', '已付款'),
        ('overdue', '逾期'),
    ]

    order_id = models.IntegerField(default=0, verbose_name='关联订单ID')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='订单总金额')
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'), verbose_name='已付金额')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', verbose_name='付款状态')
    due_date = models.DateField(null=True, blank=True, verbose_name='付款到期日')
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')
    remark = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'finance_order_record'
        verbose_name = '订单财务记录'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"财务记录-{self.order_id}"

    @property
    def unpaid_amount(self):
        return self.total_amount - self.paid_amount

    def get_payment_status_display(self):
        return dict(self.PAYMENT_STATUS_CHOICES).get(self.payment_status, '未知')
