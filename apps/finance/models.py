"""
财务管理模块模型
只包含有数据库表的模型
"""

from django.db import models
from decimal import Decimal


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
        0: "待审核",
        1: "审核中",
        2: "审核通过",
        3: "审核不通过",
        4: "撤销审核",
    }

    PAY_STATUS_MAP = {0: "待打款", 1: "已打款"}

    OPEN_STATUS_MAP = {0: "未开票", 1: "已开票", 2: "已作废"}

    ENTER_STATUS_MAP = {0: "未回款", 1: "部分回款", 2: "全部回款"}

    INVOICE_TYPE_MAP = {1: "增值税专用发票", 2: "普通发票", 3: "电子发票"}


class InvoiceStatusChoices:
    DRAFT = "draft"
    PENDING = "pending"
    ISSUED = "issued"
    CANCELLED = "cancelled"

    CHOICES = [
        (DRAFT, "草稿"),
        (PENDING, "待开票"),
        (ISSUED, "已开票"),
        (CANCELLED, "已作废"),
    ]


class IncomeStatusChoices:
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"

    CHOICES = [
        (UNPAID, "未回款"),
        (PARTIAL, "部分回款"),
        (PAID, "全部回款"),
    ]


class PaymentMethodChoices:
    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"
    CHECK = "check"
    ONLINE = "online"
    OTHER = "other"

    CHOICES = [
        (BANK_TRANSFER, "银行转账"),
        (CASH, "现金"),
        (CHECK, "支票"),
        (ONLINE, "在线支付"),
        (OTHER, "其他"),
    ]


class Expense(models.Model):
    """报销申请"""

    code = models.CharField(max_length=100, default="", verbose_name="报销编码")
    subject_id = models.IntegerField(default=0, verbose_name="报销企业主体")
    admin_id = models.PositiveIntegerField(default=0, verbose_name="报销人ID")
    did = models.IntegerField(default=0, verbose_name="报销部门ID")
    project_id = models.IntegerField(default=0, verbose_name="关联项目ID")
    cost = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="报销总金额"
    )
    income_month = models.IntegerField(default=0, verbose_name="入账月份")
    expense_time = models.BigIntegerField(default=0, verbose_name="原始单据日期")
    file_ids = models.CharField(max_length=500, default="", verbose_name="附件ID")
    pay_status = models.SmallIntegerField(
        default=0, verbose_name="打款状态：0待打款,1已打款"
    )
    pay_admin_id = models.IntegerField(default=0, verbose_name="打款人ID")
    pay_time = models.BigIntegerField(default=0, verbose_name="最后打款时间")
    check_status = models.SmallIntegerField(
        default=0,
        verbose_name="审核状态:0待审核,1审核中,2审核通过,3审核不通过,4撤销审核",
    )
    check_flow_id = models.IntegerField(default=0, verbose_name="审核流程id")
    check_step_sort = models.IntegerField(default=0, verbose_name="当前审批步骤")
    check_uids = models.CharField(
        max_length=500, default="", verbose_name="当前审批人ID"
    )
    check_last_uid = models.CharField(
        max_length=500, default="", verbose_name="上一审批人ID"
    )
    check_history_uids = models.CharField(
        max_length=500, default="", verbose_name="历史审批人ID"
    )
    check_copy_uids = models.CharField(
        max_length=500, default="", verbose_name="抄送人ID"
    )
    check_time = models.BigIntegerField(default=0, verbose_name="审核通过时间")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")
    auto_generated = models.BooleanField(default=False, verbose_name="是否自动生成")

    class Meta:
        db_table = "finance_expense"
        verbose_name = "报销申请"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return self.code

    def get_check_status_display(self):
        return FinanceStatusMapping.CHECK_STATUS_MAP.get(self.check_status, "未知")

    def get_pay_status_display(self):
        return FinanceStatusMapping.PAY_STATUS_MAP.get(self.pay_status, "未知")


class Income(models.Model):
    """回款记录"""

    invoice_id = models.BigIntegerField(default=0, verbose_name="关联发票ID")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="到账金额"
    )
    income_date = models.DateTimeField(verbose_name="到账日期")
    file_ids = models.CharField(max_length=500, default="", verbose_name="附件ID")
    remark = models.TextField(blank=True, verbose_name="备注")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")

    class Meta:
        db_table = "finance_income"
        verbose_name = "回款记录"
        verbose_name_plural = verbose_name
        ordering = ["-income_date"]

    def __str__(self):
        return f"回款-{self.id}"


class InvoiceVerifyRecord(models.Model):
    """发票核销记录"""

    invoice_id = models.BigIntegerField(default=0, verbose_name="关联发票ID")
    income = models.ForeignKey(
        Income,
        on_delete=models.CASCADE,
        related_name="verify_records",
        verbose_name="关联回款",
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="核销金额"
    )
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")

    class Meta:
        db_table = "finance_invoice_verify_record"
        verbose_name = "发票核销记录"
        verbose_name_plural = verbose_name
        ordering = ["-id"]

    def __str__(self):
        return f"核销-{self.id}"


class Invoice(models.Model):
    """发票"""

    code = models.CharField(max_length=100, default="", verbose_name="发票号码")
    customer_id = models.IntegerField(default=0, verbose_name="关联客户ID")
    contract_id = models.BigIntegerField(default=0, verbose_name="关联合同ID")
    project_id = models.BigIntegerField(default=0, verbose_name="关联项目ID")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="发票金额"
    )
    did = models.IntegerField(default=0, verbose_name="发票申请部门")
    admin_id = models.PositiveIntegerField(default=0, verbose_name="发票申请人ID")
    open_status = models.SmallIntegerField(
        default=0, verbose_name="开票状态：0未开票 1已开票 2已作废"
    )
    open_admin_id = models.IntegerField(default=0, verbose_name="发票开具人")
    open_time = models.BigIntegerField(default=0, verbose_name="发票开具时间")
    delivery = models.CharField(max_length=100, default="", verbose_name="快递单号")
    types = models.SmallIntegerField(default=0, verbose_name="抬头类型：1企业2个人")
    invoice_type = models.SmallIntegerField(default=0, verbose_name="发票类型")
    invoice_subject = models.IntegerField(default=0, verbose_name="关联发票主体ID")
    invoice_title = models.CharField(
        max_length=100, default="", verbose_name="开票抬头"
    )
    invoice_tax = models.CharField(
        max_length=100, default="", verbose_name="纳税人识别号"
    )
    invoice_phone = models.CharField(
        max_length=100, default="", verbose_name="电话号码"
    )
    invoice_address = models.CharField(max_length=100, default="", verbose_name="地址")
    invoice_bank = models.CharField(max_length=100, default="", verbose_name="开户银行")
    invoice_account = models.CharField(
        max_length=100, default="", verbose_name="银行账号"
    )
    invoice_banking = models.CharField(
        max_length=100, default="", verbose_name="银行营业网点"
    )
    file_ids = models.CharField(max_length=500, default="", verbose_name="附件ID")
    other_file_ids = models.CharField(
        max_length=500, default="", verbose_name="其他附件ID"
    )
    enter_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="已到账金额"
    )
    enter_status = models.SmallIntegerField(
        default=0, verbose_name="回款状态：0未回款 1部分回款 2全部回款"
    )
    enter_time = models.BigIntegerField(default=0, verbose_name="最新回款时间")
    check_status = models.SmallIntegerField(default=0, verbose_name="审核状态")
    check_flow_id = models.IntegerField(default=0, verbose_name="审核流程id")
    check_step_sort = models.IntegerField(default=0, verbose_name="当前审批步骤")
    check_uids = models.CharField(
        max_length=500, default="", verbose_name="当前审批人ID"
    )
    check_last_uid = models.CharField(
        max_length=500, default="", verbose_name="上一审批人ID"
    )
    check_history_uids = models.CharField(
        max_length=500, default="", verbose_name="历史审批人ID"
    )
    check_copy_uids = models.CharField(
        max_length=500, default="", verbose_name="抄送人ID"
    )
    check_time = models.BigIntegerField(default=0, verbose_name="审核通过时间")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_invoice"
        verbose_name = "发票"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return self.code

    def get_open_status_display(self):
        return FinanceStatusMapping.OPEN_STATUS_MAP.get(self.open_status, "未知")

    def get_enter_status_display(self):
        return FinanceStatusMapping.ENTER_STATUS_MAP.get(self.enter_status, "未知")

    def get_invoice_type_display(self):
        return FinanceStatusMapping.INVOICE_TYPE_MAP.get(self.invoice_type, "未知")


class Payment(models.Model):
    """付款记录"""

    expense_id = models.BigIntegerField(default=0, verbose_name="关联报销ID")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="打款金额"
    )
    payment_date = models.DateTimeField(verbose_name="打款日期")
    file_ids = models.CharField(max_length=500, default="", verbose_name="附件ID")
    remark = models.TextField(blank=True, verbose_name="备注")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")

    class Meta:
        db_table = "finance_payment"
        verbose_name = "付款记录"
        verbose_name_plural = verbose_name
        ordering = ["-payment_date"]

    def __str__(self):
        return f"付款-{self.id}"


class InvoiceRequest(models.Model):
    """开票申请"""

    STATUS_CHOICES = [
        ("pending", "待审核"),
        ("approved", "已批准"),
        ("rejected", "已拒绝"),
        ("invoiced", "已开票"),
    ]

    order_id = models.IntegerField(default=0, verbose_name="关联订单ID")
    applicant_id = models.IntegerField(default=0, verbose_name="申请人ID")
    department_id = models.IntegerField(default=0, verbose_name="申请部门ID")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="开票金额"
    )
    invoice_type = models.SmallIntegerField(default=2, verbose_name="发票类型")
    invoice_title = models.CharField(max_length=200, verbose_name="开票抬头")
    tax_number = models.CharField(
        max_length=100, blank=True, verbose_name="纳税人识别号"
    )
    reason = models.TextField(verbose_name="申请理由")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="申请状态",
    )
    reviewer_id = models.IntegerField(default=0, verbose_name="审核人ID")
    review_time = models.BigIntegerField(default=0, verbose_name="审核时间")
    review_comment = models.TextField(blank=True, verbose_name="审核意见")
    invoice_id = models.IntegerField(default=0, verbose_name="关联发票ID")
    invoice_time = models.BigIntegerField(default=0, verbose_name="开票时间")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_invoice_request"
        verbose_name = "开票申请"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return f"开票申请-{self.id}"

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class TaxRecord(models.Model):
    """税务管理"""

    TAX_TYPE_CHOICES = [
        ("vat", "增值税"),
        ("income_tax", "企业所得税"),
        ("surtax", "附加税"),
        ("stamp", "印花税"),
        ("other", "其他税费"),
    ]
    STATUS_CHOICES = [
        ("draft", "待申报"),
        ("declared", "已申报"),
        ("paid", "已缴纳"),
        ("overdue", "已逾期"),
    ]

    period = models.CharField(max_length=20, verbose_name="税务期间")
    tax_type = models.CharField(
        max_length=30, choices=TAX_TYPE_CHOICES, verbose_name="税种"
    )
    taxable_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="计税金额"
    )
    tax_rate = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0"), verbose_name="税率"
    )
    tax_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="税额"
    )
    declared_date = models.DateField(null=True, blank=True, verbose_name="申报日期")
    paid_date = models.DateField(null=True, blank=True, verbose_name="缴纳日期")
    due_date = models.DateField(null=True, blank=True, verbose_name="截止日期")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", verbose_name="状态"
    )
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_tax_record"
        verbose_name = "税务管理"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return f"{self.period}-{self.get_tax_type_display()}"

    def get_tax_type_display(self):
        return dict(self.TAX_TYPE_CHOICES).get(self.tax_type, "未知")

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class FixedAsset(models.Model):
    """固定资产财务档案"""

    STATUS_CHOICES = [
        ("active", "计提中"),
        ("paused", "暂停计提"),
        ("disposed", "已处置"),
    ]

    asset = models.OneToOneField(
        "system.Asset",
        on_delete=models.PROTECT,
        related_name="finance_profile",
        null=True,
        blank=True,
        verbose_name="行政固定资产",
    )
    salvage_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="残值"
    )
    depreciation_months = models.PositiveIntegerField(
        default=36, verbose_name="折旧月数"
    )
    accumulated_depreciation = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="累计折旧"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active", verbose_name="财务状态"
    )
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_fixed_asset"
        verbose_name = "固定资产财务档案"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return self.asset_code

    @property
    def asset_code(self):
        return self.asset.asset_number if self.asset_id and self.asset else ""

    @property
    def name(self):
        return self.asset.name if self.asset_id and self.asset else ""

    @property
    def category(self):
        if self.asset_id and self.asset and self.asset.category_id:
            return self.asset.category.name
        return ""

    @property
    def purchase_date(self):
        return self.asset.purchase_date if self.asset_id and self.asset else None

    @property
    def original_value(self):
        return (
            self.asset.purchase_price if self.asset_id and self.asset else Decimal("0")
        )

    @property
    def net_value(self):
        return self.original_value - self.accumulated_depreciation

    @property
    def monthly_depreciation(self):
        if self.depreciation_months <= 0:
            return Decimal("0")
        depreciable = self.original_value - self.salvage_value
        if depreciable <= 0:
            return Decimal("0")
        return depreciable / Decimal(self.depreciation_months)

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class CostAllocation(models.Model):
    """成本分摊"""

    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("allocated", "已分摊"),
        ("void", "已作废"),
    ]

    allocation_no = models.CharField(
        max_length=100, default="", verbose_name="分摊编号"
    )
    period = models.CharField(max_length=20, verbose_name="分摊期间")
    source_type = models.CharField(
        max_length=30, default="", blank=True, verbose_name="来源类型"
    )
    source_id = models.BigIntegerField(default=0, verbose_name="来源ID")
    total_amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="分摊总额"
    )
    department_id = models.IntegerField(default=0, verbose_name="部门ID")
    project_id = models.IntegerField(default=0, verbose_name="项目ID")
    allocation_basis = models.CharField(
        max_length=100, default="", blank=True, verbose_name="分摊依据"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", verbose_name="状态"
    )
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_cost_allocation"
        verbose_name = "成本分摊"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return self.allocation_no or f"分摊-{self.id}"

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class FinancialPeriodClose(models.Model):
    """期间结账"""

    STATUS_CHOICES = [
        ("open", "未结账"),
        ("closing", "结账中"),
        ("closed", "已结账"),
        ("reopened", "已反结账"),
    ]

    period = models.CharField(max_length=20, unique=True, verbose_name="会计期间")
    income_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="收入金额"
    )
    expense_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="费用金额"
    )
    profit_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="利润金额"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="open", verbose_name="状态"
    )
    closed_by = models.IntegerField(default=0, verbose_name="结账人ID")
    closed_time = models.PositiveBigIntegerField(default=0, verbose_name="结账时间")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_period_close"
        verbose_name = "期间结账"
        verbose_name_plural = verbose_name
        ordering = ["-period"]

    def __str__(self):
        return self.period

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class FinancialReport(models.Model):
    """财务报表"""

    REPORT_TYPE_CHOICES = [
        ("balance_sheet", "资产负债表"),
        ("income_statement", "利润表"),
        ("cash_flow", "现金流量表"),
        ("management", "经营分析报表"),
    ]
    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("generated", "已生成"),
        ("approved", "已确认"),
    ]

    report_no = models.CharField(max_length=100, default="", verbose_name="报表编号")
    report_type = models.CharField(
        max_length=30, choices=REPORT_TYPE_CHOICES, verbose_name="报表类型"
    )
    period = models.CharField(max_length=20, verbose_name="报表期间")
    total_assets = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="资产总额"
    )
    total_liabilities = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="负债总额"
    )
    total_equity = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="权益总额"
    )
    revenue_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="收入金额"
    )
    cost_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="成本费用"
    )
    profit_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="利润金额"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", verbose_name="状态"
    )
    generated_by = models.IntegerField(default=0, verbose_name="生成人ID")
    generated_time = models.PositiveBigIntegerField(default=0, verbose_name="生成时间")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_report"
        verbose_name = "财务报表"
        verbose_name_plural = verbose_name
        ordering = ["-period", "-create_time"]

    def __str__(self):
        return self.report_no or f"{self.period}-{self.get_report_type_display()}"

    def get_report_type_display(self):
        return dict(self.REPORT_TYPE_CHOICES).get(self.report_type, "未知")

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class ChartOfAccount(models.Model):
    """会计科目"""

    ACCOUNT_TYPE_CHOICES = [
        ("asset", "资产"),
        ("liability", "负债"),
        ("equity", "权益"),
        ("income", "收入"),
        ("cost", "成本"),
        ("expense", "费用"),
    ]
    STATUS_CHOICES = [
        ("active", "启用"),
        ("disabled", "停用"),
    ]

    code = models.CharField(max_length=50, unique=True, verbose_name="科目编码")
    name = models.CharField(max_length=100, verbose_name="科目名称")
    account_type = models.CharField(
        max_length=20, choices=ACCOUNT_TYPE_CHOICES, verbose_name="科目类型"
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="上级科目",
    )
    level = models.PositiveSmallIntegerField(default=1, verbose_name="科目级次")
    is_leaf = models.BooleanField(default=True, verbose_name="是否末级")
    balance_direction = models.CharField(
        max_length=10,
        choices=[("debit", "借方"), ("credit", "贷方")],
        default="debit",
        verbose_name="余额方向",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active", verbose_name="状态"
    )
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_chart_of_account"
        verbose_name = "会计科目"
        verbose_name_plural = verbose_name
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"

    def get_account_type_display(self):
        return dict(self.ACCOUNT_TYPE_CHOICES).get(self.account_type, "未知")

    def get_balance_direction_display(self):
        return dict([("debit", "借方"), ("credit", "贷方")]).get(
            self.balance_direction, "未知"
        )

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class LedgerVoucherLine(models.Model):
    """凭证明细"""

    voucher = models.ForeignKey(
        "LedgerVoucher",
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="总账凭证",
    )
    account = models.ForeignKey(
        ChartOfAccount,
        on_delete=models.PROTECT,
        related_name="voucher_lines",
        verbose_name="会计科目",
    )
    summary = models.CharField(
        max_length=200, default="", blank=True, verbose_name="摘要"
    )
    debit_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="借方金额"
    )
    credit_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="贷方金额"
    )
    auxiliary_type = models.CharField(
        max_length=30, default="", blank=True, verbose_name="辅助核算类型"
    )
    auxiliary_id = models.BigIntegerField(default=0, verbose_name="辅助核算ID")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_ledger_voucher_line"
        verbose_name = "凭证明细"
        verbose_name_plural = verbose_name
        ordering = ["voucher_id", "id"]

    def __str__(self):
        return f"{self.voucher_id}-{self.account_id}"

    @property
    def voucher_no(self):
        return self.voucher.voucher_no if self.voucher_id and self.voucher else ""

    @property
    def account_code(self):
        return self.account.code if self.account_id and self.account else ""

    @property
    def account_name(self):
        return self.account.name if self.account_id and self.account else ""


class CashFlowPlan(models.Model):
    """现金流计划"""

    FLOW_TYPE_CHOICES = [("in", "流入"), ("out", "流出")]
    STATUS_CHOICES = [
        ("planned", "计划中"),
        ("completed", "已完成"),
        ("cancelled", "已取消"),
    ]

    plan_no = models.CharField(max_length=100, default="", verbose_name="计划编号")
    flow_type = models.CharField(
        max_length=10, choices=FLOW_TYPE_CHOICES, verbose_name="流向"
    )
    category = models.CharField(
        max_length=100, default="", blank=True, verbose_name="类别"
    )
    expected_date = models.DateField(verbose_name="预计日期")
    expected_amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="预计金额"
    )
    actual_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="实际金额"
    )
    account = models.ForeignKey(
        "FinanceAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cash_flow_plans",
        verbose_name="资金账户",
    )
    source_type = models.CharField(
        max_length=30, default="", blank=True, verbose_name="来源类型"
    )
    source_id = models.BigIntegerField(default=0, verbose_name="来源ID")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="planned", verbose_name="状态"
    )
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_cash_flow_plan"
        verbose_name = "现金流计划"
        verbose_name_plural = verbose_name
        ordering = ["expected_date", "-create_time"]

    def __str__(self):
        return self.plan_no or f"现金流计划-{self.id}"

    @property
    def variance_amount(self):
        return self.actual_amount - self.expected_amount

    def get_flow_type_display(self):
        return dict(self.FLOW_TYPE_CHOICES).get(self.flow_type, "未知")

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class FinancialRatio(models.Model):
    """财务指标"""

    RATIO_TYPE_CHOICES = [
        ("profitability", "盈利能力"),
        ("solvency", "偿债能力"),
        ("operation", "营运能力"),
        ("growth", "成长能力"),
        ("cash", "现金能力"),
    ]
    STATUS_CHOICES = [
        ("normal", "正常"),
        ("warning", "预警"),
        ("risk", "风险"),
    ]

    period = models.CharField(max_length=20, verbose_name="指标期间")
    ratio_type = models.CharField(
        max_length=30, choices=RATIO_TYPE_CHOICES, verbose_name="指标类型"
    )
    name = models.CharField(max_length=100, verbose_name="指标名称")
    value = models.DecimalField(
        max_digits=15, decimal_places=4, default=Decimal("0"), verbose_name="指标值"
    )
    target_value = models.DecimalField(
        max_digits=15, decimal_places=4, default=Decimal("0"), verbose_name="目标值"
    )
    warning_value = models.DecimalField(
        max_digits=15, decimal_places=4, default=Decimal("0"), verbose_name="预警值"
    )
    unit = models.CharField(max_length=20, default="%", blank=True, verbose_name="单位")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="normal", verbose_name="状态"
    )
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_financial_ratio"
        verbose_name = "财务指标"
        verbose_name_plural = verbose_name
        ordering = ["-period", "ratio_type"]

    def __str__(self):
        return f"{self.period}-{self.name}"

    def get_ratio_type_display(self):
        return dict(self.RATIO_TYPE_CHOICES).get(self.ratio_type, "未知")

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class ExpenseAccrual(models.Model):
    """费用计提"""

    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("accrued", "已计提"),
        ("reversed", "已冲销"),
    ]

    accrual_no = models.CharField(max_length=100, default="", verbose_name="计提编号")
    period = models.CharField(max_length=20, verbose_name="计提期间")
    expense_type = models.CharField(max_length=100, verbose_name="费用类型")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="计提金额"
    )
    department_id = models.IntegerField(default=0, verbose_name="部门ID")
    project_id = models.IntegerField(default=0, verbose_name="项目ID")
    voucher = models.ForeignKey(
        "LedgerVoucher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_accruals",
        verbose_name="关联凭证",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", verbose_name="状态"
    )
    accrued_by = models.IntegerField(default=0, verbose_name="计提人ID")
    accrued_time = models.PositiveBigIntegerField(default=0, verbose_name="计提时间")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_expense_accrual"
        verbose_name = "费用计提"
        verbose_name_plural = verbose_name
        ordering = ["-period", "-create_time"]

    def __str__(self):
        return self.accrual_no or f"费用计提-{self.id}"

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class OrderFinanceRecord(models.Model):
    """订单财务记录"""

    PAYMENT_STATUS_CHOICES = [
        ("pending", "待付款"),
        ("partial", "部分付款"),
        ("paid", "已付款"),
        ("overdue", "逾期"),
    ]

    order_id = models.IntegerField(default=0, verbose_name="关联订单ID")
    total_amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="订单总金额"
    )
    paid_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="已付金额"
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending",
        verbose_name="付款状态",
    )
    due_date = models.DateField(null=True, blank=True, verbose_name="付款到期日")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_order_record"
        verbose_name = "订单财务记录"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"财务记录-{self.order_id}"

    @property
    def unpaid_amount(self):
        return self.total_amount - self.paid_amount

    def get_payment_status_display(self):
        return dict(self.PAYMENT_STATUS_CHOICES).get(self.payment_status, "未知")


class FinanceAccount(models.Model):
    """资金账户"""

    ACCOUNT_TYPE_CHOICES = [
        ("bank", "银行账户"),
        ("cash", "现金账户"),
        ("third_party", "第三方支付账户"),
        ("other", "其他账户"),
    ]
    STATUS_CHOICES = [
        ("active", "启用"),
        ("disabled", "停用"),
    ]

    name = models.CharField(max_length=100, verbose_name="账户名称")
    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPE_CHOICES,
        default="bank",
        verbose_name="账户类型",
    )
    bank_name = models.CharField(
        max_length=100, default="", blank=True, verbose_name="开户银行"
    )
    account_no = models.CharField(
        max_length=100, default="", blank=True, verbose_name="账号"
    )
    currency = models.CharField(max_length=10, default="CNY", verbose_name="币种")
    opening_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="期初余额"
    )
    current_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="当前余额"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active", verbose_name="状态"
    )
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_account"
        verbose_name = "资金账户"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return self.name

    def get_account_type_display(self):
        return dict(self.ACCOUNT_TYPE_CHOICES).get(self.account_type, "未知")

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class FinanceBudget(models.Model):
    """预算管理"""

    PERIOD_CHOICES = [
        ("month", "月度"),
        ("quarter", "季度"),
        ("year", "年度"),
    ]
    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("active", "执行中"),
        ("closed", "已关闭"),
    ]

    name = models.CharField(max_length=100, verbose_name="预算名称")
    department_id = models.IntegerField(default=0, verbose_name="部门ID")
    project_id = models.IntegerField(default=0, verbose_name="项目ID")
    period_type = models.CharField(
        max_length=20, choices=PERIOD_CHOICES, default="month", verbose_name="预算周期"
    )
    start_date = models.DateField(verbose_name="开始日期")
    end_date = models.DateField(verbose_name="结束日期")
    budget_amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="预算金额"
    )
    used_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="已用金额"
    )
    warning_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("80"), verbose_name="预警比例"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", verbose_name="状态"
    )
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_budget"
        verbose_name = "预算管理"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return self.name

    @property
    def remaining_amount(self):
        return self.budget_amount - self.used_amount

    @property
    def usage_rate(self):
        if self.budget_amount <= 0:
            return Decimal("0")
        return self.used_amount / self.budget_amount * Decimal("100")

    def get_period_type_display(self):
        return dict(self.PERIOD_CHOICES).get(self.period_type, "未知")

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class AccountsReceivable(models.Model):
    """应收账款"""

    STATUS_CHOICES = [
        ("pending", "待收款"),
        ("partial", "部分收款"),
        ("settled", "已结清"),
        ("overdue", "已逾期"),
        ("bad_debt", "坏账"),
    ]

    code = models.CharField(max_length=100, default="", verbose_name="应收编号")
    customer_id = models.IntegerField(default=0, verbose_name="客户ID")
    order_id = models.IntegerField(default=0, verbose_name="订单ID")
    invoice_id = models.BigIntegerField(default=0, verbose_name="发票ID")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="应收金额"
    )
    received_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="已收金额"
    )
    due_date = models.DateField(null=True, blank=True, verbose_name="到期日期")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="状态"
    )
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_accounts_receivable"
        verbose_name = "应收账款"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return self.code or f"应收-{self.id}"

    @property
    def remaining_amount(self):
        return self.amount - self.received_amount

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class AccountsPayable(models.Model):
    """应付账款"""

    STATUS_CHOICES = [
        ("pending", "待付款"),
        ("partial", "部分付款"),
        ("settled", "已结清"),
        ("overdue", "已逾期"),
    ]

    code = models.CharField(max_length=100, default="", verbose_name="应付编号")
    supplier_id = models.IntegerField(default=0, verbose_name="供应商ID")
    expense_id = models.BigIntegerField(default=0, verbose_name="报销ID")
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="应付金额"
    )
    paid_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="已付金额"
    )
    due_date = models.DateField(null=True, blank=True, verbose_name="到期日期")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="状态"
    )
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_accounts_payable"
        verbose_name = "应付账款"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return self.code or f"应付-{self.id}"

    @property
    def remaining_amount(self):
        return self.amount - self.paid_amount

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class BankTransaction(models.Model):
    """银行流水"""

    DIRECTION_CHOICES = [
        ("in", "收入"),
        ("out", "支出"),
    ]
    MATCH_STATUS_CHOICES = [
        ("unmatched", "未匹配"),
        ("matched", "已匹配"),
    ]

    account = models.ForeignKey(
        FinanceAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="资金账户",
    )
    transaction_date = models.DateTimeField(verbose_name="交易时间")
    direction = models.CharField(
        max_length=10, choices=DIRECTION_CHOICES, verbose_name="收支方向"
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name="交易金额"
    )
    counterparty = models.CharField(
        max_length=100, default="", blank=True, verbose_name="交易对方"
    )
    transaction_no = models.CharField(
        max_length=100, default="", blank=True, verbose_name="交易流水号"
    )
    purpose = models.CharField(
        max_length=200, default="", blank=True, verbose_name="用途"
    )
    match_status = models.CharField(
        max_length=20,
        choices=MATCH_STATUS_CHOICES,
        default="unmatched",
        verbose_name="匹配状态",
    )
    related_type = models.CharField(
        max_length=30, default="", blank=True, verbose_name="关联业务类型"
    )
    related_id = models.BigIntegerField(default=0, verbose_name="关联业务ID")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_bank_transaction"
        verbose_name = "银行流水"
        verbose_name_plural = verbose_name
        ordering = ["-transaction_date"]

    def __str__(self):
        return self.transaction_no or f"流水-{self.id}"

    def get_direction_display(self):
        return dict(self.DIRECTION_CHOICES).get(self.direction, "未知")

    def get_match_status_display(self):
        return dict(self.MATCH_STATUS_CHOICES).get(self.match_status, "未知")


class BankReconciliation(models.Model):
    """银行对账"""

    STATUS_CHOICES = [
        ("draft", "待对账"),
        ("balanced", "已平衡"),
        ("difference", "有差异"),
    ]

    account = models.ForeignKey(
        FinanceAccount,
        on_delete=models.PROTECT,
        related_name="reconciliations",
        verbose_name="资金账户",
    )
    period = models.CharField(max_length=20, verbose_name="对账期间")
    book_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="账面余额"
    )
    bank_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="银行余额"
    )
    difference_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="差异金额"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", verbose_name="状态"
    )
    reconciled_by = models.IntegerField(default=0, verbose_name="对账人ID")
    reconciled_time = models.BigIntegerField(default=0, verbose_name="对账时间")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_bank_reconciliation"
        verbose_name = "银行对账"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]
        unique_together = ("account", "period")

    def __str__(self):
        return f"{self.account_id}-{self.period}"

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")


class LedgerVoucher(models.Model):
    """总账凭证"""

    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("posted", "已过账"),
        ("void", "已作废"),
    ]

    voucher_no = models.CharField(max_length=100, default="", verbose_name="凭证号")
    voucher_date = models.DateField(verbose_name="凭证日期")
    summary = models.CharField(max_length=200, verbose_name="摘要")
    debit_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="借方金额"
    )
    credit_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0"), verbose_name="贷方金额"
    )
    source_type = models.CharField(
        max_length=30, default="", blank=True, verbose_name="来源类型"
    )
    source_id = models.BigIntegerField(default=0, verbose_name="来源ID")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft", verbose_name="状态"
    )
    posted_by = models.IntegerField(default=0, verbose_name="过账人ID")
    posted_time = models.BigIntegerField(default=0, verbose_name="过账时间")
    create_time = models.PositiveBigIntegerField(default=0, verbose_name="创建时间")
    remark = models.TextField(blank=True, verbose_name="备注")

    class Meta:
        db_table = "finance_ledger_voucher"
        verbose_name = "总账凭证"
        verbose_name_plural = verbose_name
        ordering = ["-voucher_date", "-id"]

    def __str__(self):
        return self.voucher_no or f"凭证-{self.id}"

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "未知")
