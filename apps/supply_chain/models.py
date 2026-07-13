from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class SourceTrackedModel(models.Model):
    source_type = models.CharField(max_length=50, blank=True, verbose_name='来源类型')
    source_id = models.PositiveBigIntegerField(null=True, blank=True, verbose_name='来源记录ID')
    source_code = models.CharField(max_length=100, blank=True, verbose_name='来源单号')
    source_snapshot = models.JSONField(default=dict, blank=True, verbose_name='来源快照')

    class Meta:
        abstract = True


class DemandForecastPlan(SourceTrackedModel):
    STATUS_DRAFT = 'draft'
    STATUS_RUNNING = 'running'
    STATUS_GENERATED = 'generated'
    STATUS_REVIEWING = 'reviewing'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_ARCHIVED = 'archived'

    STATUS_CHOICES = (
        (STATUS_DRAFT, '草稿'),
        (STATUS_RUNNING, '计算中'),
        (STATUS_GENERATED, '已生成'),
        (STATUS_REVIEWING, '评审中'),
        (STATUS_APPROVED, '已通过'),
        (STATUS_REJECTED, '已驳回'),
        (STATUS_ARCHIVED, '已归档'),
    )

    name = models.CharField(max_length=100, verbose_name='预测计划名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='预测计划编号')
    product = models.ForeignKey(
        'contract.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='关联产品',
    )
    period_start = models.DateField(verbose_name='周期开始日期')
    period_end = models.DateField(verbose_name='周期结束日期')
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name='状态',
    )
    summary = models.TextField(blank=True, verbose_name='预测摘要')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_demand_forecast_plans',
        verbose_name='创建人',
    )
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'supply_chain_demand_forecast_plan'
        verbose_name = '需求预测计划'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f'{self.code} - {self.name}'


class DemandForecastSnapshot(models.Model):
    forecast_plan = models.ForeignKey(
        DemandForecastPlan,
        on_delete=models.CASCADE,
        related_name='snapshots',
        verbose_name='预测计划',
    )
    product = models.ForeignKey(
        'contract.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='关联产品',
    )
    shipped_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='历史出货量')
    inventory_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='当前库存')
    wip_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='在制数量')
    inbound_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='在途数量')
    prepared_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='已备料数量')
    manual_adjustment = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='人工修正量')
    notes = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'supply_chain_demand_forecast_snapshot'
        verbose_name = '需求预测快照'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']


class DemandForecastResult(models.Model):
    forecast_plan = models.ForeignKey(
        DemandForecastPlan,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='预测计划',
    )
    predicted_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='预测量')
    safety_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='安全库存')
    recommended_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='建议备料量')
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='置信度')
    risk_level = models.CharField(max_length=20, default='unknown', verbose_name='风险等级')
    summary = models.TextField(blank=True, verbose_name='摘要')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'supply_chain_demand_forecast_result'
        verbose_name = '需求预测结果'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']


class MaterialPreparationReview(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = (
        (STATUS_PENDING, '待评审'),
        (STATUS_APPROVED, '已通过'),
        (STATUS_REJECTED, '已驳回'),
    )

    forecast_result = models.ForeignKey(
        DemandForecastResult,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name='预测结果',
    )
    code = models.CharField(max_length=50, unique=True, verbose_name='评审单号')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='状态')
    comment = models.TextField(blank=True, verbose_name='评审意见')
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='material_preparation_reviews',
        verbose_name='评审人',
    )
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'supply_chain_material_preparation_review'
        verbose_name = '备料评审'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']


class OutsourceIssueOrder(SourceTrackedModel):
    STATUS_DRAFT = 'draft'
    STATUS_CHECKING = 'checking'
    STATUS_SHORTAGE = 'shortage'
    STATUS_READY = 'ready'
    STATUS_PICKING = 'picking'
    STATUS_ISSUED = 'issued'
    STATUS_NOTIFIED = 'notified'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = (
        (STATUS_DRAFT, '草稿'),
        (STATUS_CHECKING, '齐套校验中'),
        (STATUS_SHORTAGE, '缺料'),
        (STATUS_READY, '齐套完成'),
        (STATUS_PICKING, '备料中'),
        (STATUS_ISSUED, '已发料'),
        (STATUS_NOTIFIED, '已通知'),
        (STATUS_CLOSED, '已关闭'),
    )

    code = models.CharField(max_length=50, unique=True, verbose_name='委外发料单号')
    product = models.ForeignKey(
        'contract.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='产品',
    )
    supplier = models.ForeignKey(
        'contract.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='供应商',
    )
    production_plan = models.ForeignKey(
        'production.ProductionPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outsource_issue_orders',
        verbose_name='生产计划',
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='委外数量')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name='状态')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_outsource_issue_orders',
        verbose_name='创建人',
    )
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'supply_chain_outsource_issue_order'
        verbose_name = '委外发料单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']


class OutsourceIssueItem(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_READY = 'ready'
    STATUS_SHORTAGE = 'shortage'
    STATUS_SPEC_MISMATCH = 'spec_mismatch'

    STATUS_CHOICES = (
        (STATUS_PENDING, '待校验'),
        (STATUS_READY, '齐套'),
        (STATUS_SHORTAGE, '缺料'),
        (STATUS_SPEC_MISMATCH, '规格不符'),
    )

    issue_order = models.ForeignKey(
        OutsourceIssueOrder,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='委外发料单',
    )
    bom_item = models.ForeignKey(
        'production.BOMItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='BOM明细',
    )
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='库存物料',
    )
    material_name = models.CharField(max_length=100, blank=True, verbose_name='物料名称')
    material_code = models.CharField(max_length=50, blank=True, verbose_name='物料编码')
    specification = models.CharField(max_length=100, blank=True, verbose_name='规格型号')
    required_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='应发数量')
    available_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='可用数量')
    issued_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='已发数量')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='状态')
    remark = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'supply_chain_outsource_issue_item'
        verbose_name = '委外发料明细'
        verbose_name_plural = verbose_name

    @property
    def shortage_quantity(self):
        shortage = Decimal(self.required_quantity or 0) - Decimal(self.available_quantity or 0)
        return shortage if shortage > 0 else Decimal('0')


class OutsourceIssueStatusLog(models.Model):
    issue_order = models.ForeignKey(
        OutsourceIssueOrder,
        on_delete=models.CASCADE,
        related_name='status_logs',
        verbose_name='委外发料单',
    )
    from_status = models.CharField(max_length=20, blank=True, verbose_name='原状态')
    to_status = models.CharField(max_length=20, verbose_name='新状态')
    message = models.CharField(max_length=255, blank=True, verbose_name='说明')
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='操作人',
    )
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'supply_chain_outsource_issue_status_log'
        verbose_name = '委外发料状态日志'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']


class PRReviewRule(models.Model):
    ACTION_FILTER = 'filter'
    ACTION_MANUAL = 'manual_review'
    ACTION_APPROVE = 'approve'
    ACTION_URGENT = 'urgent_approve'

    ACTION_CHOICES = (
        (ACTION_FILTER, '自动过滤'),
        (ACTION_MANUAL, '人工复核'),
        (ACTION_APPROVE, '进入审批'),
        (ACTION_URGENT, '紧急审批'),
    )

    name = models.CharField(max_length=100, verbose_name='规则名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='规则编码')
    scenario = models.CharField(max_length=50, blank=True, verbose_name='适用场景')
    condition_json = models.JSONField(default=dict, blank=True, verbose_name='条件配置')
    recommended_action = models.CharField(max_length=20, choices=ACTION_CHOICES, default=ACTION_MANUAL, verbose_name='建议动作')
    priority = models.IntegerField(default=100, verbose_name='优先级')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'supply_chain_pr_review_rule'
        verbose_name = 'PR审核规则'
        verbose_name_plural = verbose_name
        ordering = ['priority', 'id']


class PRReviewTask(SourceTrackedModel):
    STATUS_PENDING = 'pending'
    STATUS_RULE_MATCHED = 'rule_matched'
    STATUS_AUTO_APPROVED = 'auto_approved'
    STATUS_MANUAL_REVIEW = 'manual_review'
    STATUS_DONE = 'done'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = (
        (STATUS_PENDING, '待识别'),
        (STATUS_RULE_MATCHED, '规则命中'),
        (STATUS_AUTO_APPROVED, '自动通过'),
        (STATUS_MANUAL_REVIEW, '人工复核'),
        (STATUS_DONE, '已处理'),
        (STATUS_REJECTED, '已拒绝'),
    )

    code = models.CharField(max_length=50, unique=True, verbose_name='审核任务编号')
    title = models.CharField(max_length=200, verbose_name='任务标题')
    source_type = models.CharField(max_length=50, blank=True, verbose_name='来源类型')
    source_code = models.CharField(max_length=50, blank=True, verbose_name='来源单号')
    matched_rules = models.ManyToManyField(PRReviewRule, blank=True, verbose_name='命中规则')
    is_abnormal = models.BooleanField(default=False, verbose_name='是否异常')
    recommended_action = models.CharField(max_length=20, blank=True, default='', verbose_name='建议动作')
    evidence = models.JSONField(default=dict, blank=True, verbose_name='审核依据')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='状态')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_pr_review_tasks',
        verbose_name='创建人',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_pr_review_tasks',
        verbose_name='复核人',
    )
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'supply_chain_pr_review_task'
        verbose_name = 'PR审核任务'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']


class PRReviewEvidence(models.Model):
    review_task = models.ForeignKey(
        PRReviewTask,
        on_delete=models.CASCADE,
        related_name='evidence_items',
        verbose_name='审核任务',
    )
    rule = models.ForeignKey(
        PRReviewRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='规则',
    )
    label = models.CharField(max_length=100, verbose_name='依据标签')
    value = models.CharField(max_length=255, blank=True, verbose_name='依据值')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'supply_chain_pr_review_evidence'
        verbose_name = 'PR审核依据'
        verbose_name_plural = verbose_name


class PriceReviewOrder(SourceTrackedModel):
    STATUS_DRAFT = 'draft'
    STATUS_PARSING = 'parsing'
    STATUS_BREAKDOWN = 'breakdown'
    STATUS_REVIEWING = 'reviewing'
    STATUS_EXCEPTION = 'exception'
    STATUS_APPROVED = 'approved'

    STATUS_CHOICES = (
        (STATUS_DRAFT, '草稿'),
        (STATUS_PARSING, '解析中'),
        (STATUS_BREAKDOWN, '拆解中'),
        (STATUS_REVIEWING, '复核中'),
        (STATUS_EXCEPTION, '异常待处理'),
        (STATUS_APPROVED, '已通过'),
    )

    code = models.CharField(max_length=50, unique=True, verbose_name='复核单号')
    purchase_order = models.ForeignKey(
        'inventory.PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='price_reviews',
        verbose_name='采购订单',
    )
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='物料',
    )
    supplier = models.ForeignKey(
        'contract.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='供应商',
    )
    quoted_price = models.DecimalField(max_digits=14, decimal_places=4, default=0, verbose_name='报价单价')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name='状态')
    ai_summary = models.TextField(blank=True, verbose_name='AI摘要')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_price_review_orders',
        verbose_name='创建人',
    )
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'supply_chain_price_review_order'
        verbose_name = '单价复核单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']


class PriceReviewDocument(models.Model):
    review_order = models.ForeignKey(
        PriceReviewOrder,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='复核单',
    )
    file_name = models.CharField(max_length=255, verbose_name='文件名')
    file_path = models.CharField(max_length=500, blank=True, verbose_name='文件路径')
    raw_text = models.TextField(blank=True, verbose_name='OCR文本')
    parsed_payload = models.JSONField(default=dict, blank=True, verbose_name='结构化结果')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'supply_chain_price_review_document'
        verbose_name = '单价复核文档'
        verbose_name_plural = verbose_name


class PriceReviewComponent(models.Model):
    review_order = models.ForeignKey(
        PriceReviewOrder,
        on_delete=models.CASCADE,
        related_name='components',
        verbose_name='复核单',
    )
    component_type = models.CharField(max_length=50, verbose_name='成本项类型')
    component_name = models.CharField(max_length=100, verbose_name='成本项名称')
    amount = models.DecimalField(max_digits=14, decimal_places=4, default=0, verbose_name='金额')
    reference_amount = models.DecimalField(max_digits=14, decimal_places=4, default=0, verbose_name='参考金额')
    is_abnormal = models.BooleanField(default=False, verbose_name='是否异常')
    remark = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'supply_chain_price_review_component'
        verbose_name = '单价复核拆解项'
        verbose_name_plural = verbose_name


class PriceReviewConclusion(models.Model):
    review_order = models.OneToOneField(
        PriceReviewOrder,
        on_delete=models.CASCADE,
        related_name='conclusion',
        verbose_name='复核单',
    )
    result = models.CharField(max_length=20, default='pending', verbose_name='结论')
    risk_level = models.CharField(max_length=20, default='unknown', verbose_name='风险等级')
    summary = models.TextField(blank=True, verbose_name='摘要')
    abnormal_items = models.JSONField(default=list, blank=True, verbose_name='异常项')
    negotiation_points = models.JSONField(default=list, blank=True, verbose_name='议价点')
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='复核人',
    )
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'supply_chain_price_review_conclusion'
        verbose_name = '单价复核结论'
        verbose_name_plural = verbose_name


class SampleRequest(SourceTrackedModel):
    STATUS_DRAFT = 'draft'
    STATUS_ORDERED = 'ordered'
    STATUS_RECEIVED = 'received'
    STATUS_PICKUP_PENDING = 'pickup_pending'
    STATUS_PICKED_UP = 'picked_up'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = (
        (STATUS_DRAFT, '草稿'),
        (STATUS_ORDERED, '已下单'),
        (STATUS_RECEIVED, '已到货'),
        (STATUS_PICKUP_PENDING, '待领样'),
        (STATUS_PICKED_UP, '已领样'),
        (STATUS_CLOSED, '已关闭'),
    )

    code = models.CharField(max_length=50, unique=True, verbose_name='打样编号')
    material_name = models.CharField(max_length=100, verbose_name='物料名称')
    specification = models.CharField(max_length=100, blank=True, verbose_name='规格型号')
    supplier = models.ForeignKey(
        'contract.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='供应商',
    )
    engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='engineering_sample_requests',
        verbose_name='研发工程师',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_samples',
        verbose_name='申请人',
    )
    required_date = models.DateField(verbose_name='要求交期')
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=1, verbose_name='打样数量')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name='状态')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'supply_chain_sample_request'
        verbose_name = '打样申请'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']


class SampleReceipt(models.Model):
    sample_request = models.ForeignKey(
        SampleRequest,
        on_delete=models.CASCADE,
        related_name='receipts',
        verbose_name='打样申请',
    )
    received_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='到货数量')
    received_at = models.DateTimeField(default=timezone.now, verbose_name='到货时间')
    location = models.CharField(max_length=100, blank=True, verbose_name='领样地点')
    photo_path = models.CharField(max_length=500, blank=True, verbose_name='照片路径')
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_samples',
        verbose_name='登记人',
    )
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    pickup_reminded_at = models.DateTimeField(null=True, blank=True, verbose_name='上次提醒时间')
    reminder_count = models.IntegerField(default=0, verbose_name='提醒次数')

    class Meta:
        db_table = 'supply_chain_sample_receipt'
        verbose_name = '样品到货'
        verbose_name_plural = verbose_name
        ordering = ['-received_at']


class SamplePickupRecord(models.Model):
    sample_request = models.ForeignKey(
        SampleRequest,
        on_delete=models.CASCADE,
        related_name='pickup_records',
        verbose_name='打样申请',
    )
    picked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='picked_samples',
        verbose_name='领样人',
    )
    picked_at = models.DateTimeField(null=True, blank=True, verbose_name='领样时间')
    is_overdue = models.BooleanField(default=False, verbose_name='是否超时')
    note = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'supply_chain_sample_pickup_record'
        verbose_name = '样品领样记录'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']


class SupplyChainEventLog(models.Model):
    event_type = models.CharField(max_length=50, verbose_name='事件类型')
    title = models.CharField(max_length=200, verbose_name='事件标题')
    object_type = models.CharField(max_length=50, blank=True, verbose_name='对象类型')
    object_id = models.PositiveBigIntegerField(null=True, blank=True, verbose_name='对象ID')
    payload = models.JSONField(default=dict, blank=True, verbose_name='事件载荷')
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='操作人',
    )
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'supply_chain_event_log'
        verbose_name = '供应链事件日志'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']


class SupplyChainSequence(models.Model):
    prefix = models.CharField(max_length=20, verbose_name='业务前缀')
    business_date = models.DateField(verbose_name='业务日期')
    current_value = models.PositiveIntegerField(default=0, verbose_name='当前序号')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'supply_chain_sequence'
        verbose_name = '供应链业务序列'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=['prefix', 'business_date'],
                name='supply_chain_unique_sequence_day',
            ),
        ]


class SupplyChainAIInsight(models.Model):
    STATUS_SUCCESS = 'success'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = (
        (STATUS_SUCCESS, '成功'),
        (STATUS_ERROR, '失败'),
    )

    scope = models.CharField(max_length=50, verbose_name='分析范围')
    object_type = models.CharField(max_length=50, verbose_name='对象类型')
    object_id = models.PositiveBigIntegerField(default=0, verbose_name='对象ID')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='状态')
    input_hash = models.CharField(max_length=64, blank=True, verbose_name='输入摘要')
    content = models.TextField(blank=True, verbose_name='分析结论')
    result_payload = models.JSONField(default=dict, blank=True, verbose_name='结构化结果')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='生成人',
    )
    generated_at = models.DateTimeField(default=timezone.now, verbose_name='生成时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'supply_chain_ai_insight'
        verbose_name = '供应链AI分析记录'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=['scope', 'object_type', 'object_id'],
                name='supply_chain_unique_ai_insight',
            ),
        ]
        indexes = [
            models.Index(fields=['scope', 'status', '-generated_at']),
        ]

