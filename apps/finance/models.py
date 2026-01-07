from django.db import models
from django.conf import settings
from apps.customer.models import CustomerOrder, CustomerContract
from apps.project.models import Project


class ReimbursementType(models.Model):
    """报销类型 - 从basedata迁移"""
    name = models.CharField(max_length=100, verbose_name='报销类型名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='类型代码')
    description = models.TextField(blank=True, verbose_name='类型描述')
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='最大报销金额')
    requires_approval = models.BooleanField(default=True, verbose_name='是否需要审批')
    approval_flow = models.ForeignKey('approval.ApprovalFlow', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='审批流程')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '报销类型'
        verbose_name_plural = verbose_name
        db_table = 'basedata_reimbursement_type'

    def __str__(self):
        return self.name


class ExpenseType(models.Model):
    """费用类型 - 从basedata迁移"""
    name = models.CharField(max_length=100, verbose_name='费用类型名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='费用代码')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name='上级费用类型')
    description = models.TextField(blank=True, verbose_name='费用描述')
    budget_control = models.BooleanField(default=False, verbose_name='是否预算控制')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '费用类型'
        verbose_name_plural = verbose_name
        db_table = 'basedata_expense_type'

    def __str__(self):
        return self.name


class Expense(models.Model):
    subject_id = models.IntegerField(default=0, verbose_name='报销企业主体')
    code = models.CharField(max_length=100, default='', verbose_name='报销编码')
    cost = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='报销总金额')
    income_month = models.IntegerField(verbose_name='入账月份', default=0)
    expense_time = models.BigIntegerField(default=0, verbose_name='原始单据日期')
    admin_id = models.PositiveIntegerField(default=0, verbose_name='报销人ID')
    did = models.IntegerField(verbose_name='报销部门ID', default=0)
    project_id = models.IntegerField(verbose_name='关联项目ID', default=0)
    file_ids = models.CharField(max_length=500, verbose_name='附件ID', default='')
    pay_status = models.SmallIntegerField(verbose_name='打款状态：0待打款,1已打款', default=0)
    pay_admin_id = models.IntegerField(verbose_name='打款人ID', default=0)
    pay_time = models.BigIntegerField(verbose_name='最后打款时间', default=0)
    remark = models.TextField(blank=True, verbose_name='备注')
    check_status = models.SmallIntegerField(verbose_name='审核状态:0待审核,1审核中,2审核通过,3审核不通过,4撤销审核', default=0)
    check_flow_id = models.IntegerField(verbose_name='审核流程id', default=0)
    check_step_sort = models.IntegerField(verbose_name='当前审批步骤', default=0)
    check_uids = models.CharField(max_length=500, verbose_name='当前审批人ID', default='')
    check_last_uid = models.CharField(max_length=500, verbose_name='上一审批人ID', default='')
    check_history_uids = models.CharField(max_length=500, verbose_name='历史审批人ID', default='')
    check_copy_uids = models.CharField(max_length=500, verbose_name='抄送人ID', default='')
    check_time = models.BigIntegerField(verbose_name='审核通过时间', default=0)
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')
    auto_generated = models.BooleanField(default=False, verbose_name='是否自动生成')

class Invoice(models.Model):
    code = models.CharField(max_length=100, verbose_name='发票号码', default='')
    # 实现深度集成的外键关联
    customer = models.ForeignKey('customer.Customer', on_delete=models.CASCADE, null=True, blank=True, related_name='finance_invoices', verbose_name='关联客户')
    contract = models.ForeignKey('customer.CustomerContract', on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_invoices', verbose_name='关联合同')
    project = models.ForeignKey('project.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_invoices', verbose_name='关联项目')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='发票金额')
    did = models.IntegerField(verbose_name='发票申请部门', default=0)
    admin_id = models.PositiveIntegerField(default=0, verbose_name='发票申请人ID')
    open_status = models.SmallIntegerField(verbose_name='开票状态：0未开票 1已开票 2已作废', default=0)
    open_admin_id = models.IntegerField(verbose_name='发票开具人', default=0)
    open_time = models.BigIntegerField(verbose_name='发票开具时间', default=0)
    delivery = models.CharField(max_length=100, verbose_name='快递单号', default='')
    types = models.SmallIntegerField(verbose_name='抬头类型：1企业2个人', default=0)
    invoice_type = models.SmallIntegerField(verbose_name='发票类型：1增值税专用发票,2普通发票,3专用发票', default=0)
    invoice_subject = models.IntegerField(verbose_name='关联发票主体ID', default=0)
    invoice_title = models.CharField(max_length=100, verbose_name='开票抬头', default='')
    invoice_tax = models.CharField(max_length=100, verbose_name='纳税人识别号', default='')
    invoice_phone = models.CharField(max_length=100, verbose_name='电话号码', default='')
    invoice_address = models.CharField(max_length=100, verbose_name='地址', default='')
    invoice_bank = models.CharField(max_length=100, verbose_name='开户银行', default='')
    invoice_account = models.CharField(max_length=100, verbose_name='银行账号', default='')
    invoice_banking = models.CharField(max_length=100, verbose_name='银行营业网点', default='')
    file_ids = models.CharField(max_length=500, verbose_name='附件ID', default='')
    other_file_ids = models.CharField(max_length=500, verbose_name='其他附件ID', default='')
    remark = models.TextField(blank=True, verbose_name='备注')
    enter_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='已到账金额')
    enter_status = models.SmallIntegerField(verbose_name='回款状态：0未回款 1部分回款 2全部回款', default=0)
    enter_time = models.BigIntegerField(verbose_name='最新回款时间', default=0)
    check_status = models.SmallIntegerField(verbose_name='审核状态:0待审核,1审核中,2审核通过,3审核不通过,4撤销审核', default=0)
    check_flow_id = models.IntegerField(verbose_name='审核流程id', default=0)
    check_step_sort = models.IntegerField(verbose_name='当前审批步骤', default=0)
    check_uids = models.CharField(max_length=500, verbose_name='当前审批人ID', default='')
    check_last_uid = models.CharField(max_length=500, verbose_name='上一审批人ID', default='')
    check_history_uids = models.CharField(max_length=500, verbose_name='历史审批人ID', default='')
    check_copy_uids = models.CharField(max_length=500, verbose_name='抄送人ID', default='')
    check_time = models.BigIntegerField(verbose_name='审核通过时间', default=0)
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')

class Income(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, verbose_name='关联发票')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='到账金额')
    income_date = models.DateTimeField(verbose_name='到账日期')
    file_ids = models.CharField(max_length=500, verbose_name='附件ID', default='')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')

    class Meta:
        db_table = 'finance_income'
        verbose_name = '回款记录'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'回款-{self.invoice.code}'


class Payment(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, verbose_name='关联报销')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='打款金额')
    payment_date = models.DateTimeField(verbose_name='打款日期')
    file_ids = models.CharField(max_length=500, verbose_name='附件ID', default='')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.PositiveBigIntegerField(default=0, verbose_name='创建时间')

    class Meta:
        db_table = 'finance_payment'
        verbose_name = '打款记录'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'打款-{self.expense.code}'


class OrderFinanceRecord(models.Model):
    """订单财务记录"""
    PAYMENT_STATUS_CHOICES = [
        ('pending', '待付款'),
        ('partial', '部分付款'),
        ('paid', '已付款'),
        ('overdue', '逾期'),
    ]
    
    order = models.OneToOneField('customer.CustomerOrder', on_delete=models.CASCADE, verbose_name='关联订单')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='订单总金额')
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已付金额')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', verbose_name='付款状态')
    due_date = models.DateField(null=True, blank=True, verbose_name='付款到期日')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'finance_order_record'
        verbose_name = '订单财务记录'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'财务记录-{self.order.order_number}'

    @property
    def unpaid_amount(self):
        return self.total_amount - self.paid_amount


class InvoiceRequest(models.Model):
    """开票申请"""
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
        ('invoiced', '已开票'),
    ]
    
    order = models.ForeignKey('customer.CustomerOrder', on_delete=models.CASCADE, verbose_name='关联订单')
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='申请人')
    department_id = models.IntegerField(verbose_name='申请部门ID', default=0)
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='开票金额')
    invoice_type = models.SmallIntegerField(verbose_name='发票类型：1增值税专用发票,2普通发票', default=2)
    invoice_title = models.CharField(max_length=200, verbose_name='开票抬头')
    tax_number = models.CharField(max_length=100, verbose_name='纳税人识别号', blank=True)
    reason = models.TextField(verbose_name='申请理由')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='申请状态')
    
    # 审核相关
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_invoice_requests', verbose_name='审核人')
    review_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    review_comment = models.TextField(blank=True, verbose_name='审核意见')
    
    # 开票相关
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='关联发票')
    invoice_time = models.DateTimeField(null=True, blank=True, verbose_name='开票时间')
    
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'finance_invoice_request'
        verbose_name = '开票申请'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'开票申请-{self.order.order_number}'