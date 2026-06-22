from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Approval(models.Model):
    """审批表"""
    STATUS_CHOICES = (
        (0, '待审批'),
        (1, '审批中'),
        (2, '已通过'),
        (3, '已拒绝'),
        (4, '已取消'),
    )

    title = models.CharField(max_length=255, default='', verbose_name='审批标题')
    flow = models.ForeignKey(
        'ApprovalFlow',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='审批流程')
    type_id = models.PositiveIntegerField(default=0, verbose_name='审批类型ID')
    applicant_id = models.PositiveIntegerField(default=0, verbose_name='申请人ID')
    status = models.PositiveSmallIntegerField(
        default=0, choices=STATUS_CHOICES, verbose_name='审批状态')
    content = models.TextField(blank=True, default='', verbose_name='申请内容')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    reviewer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='审核人',
        null=True,
        blank=True)
    current_step_order = models.IntegerField(default=1, verbose_name='当前步骤')

    class Meta:
        db_table = 'mimu_approval'
        verbose_name = '审批表'
        verbose_name_plural = '审批表'

    def __str__(self):
        return self.title


class ApprovalRecord(models.Model):
    """审批记录表"""
    ACTION_CHOICES = (
        ('submit', '提交'),
        ('approve', '通过'),
        ('reject', '拒绝'),
        ('cancel', '取消'),
        ('delegate', '委托'),
        ('return', '退回'),
        ('transfer', '转办'),
        ('add_before', '前加签'),
        ('add_after', '后加签'),
        ('withdraw', '撤回'),
        ('execute', '办理'),
        ('external_approve', '外部审批'),
        ('urge', '催办'),
        ('timeout', '超时'),
        ('force_end', '强制结束'),
        ('archive', '归档'),
    )

    approval = models.ForeignKey(
        Approval,
        on_delete=models.CASCADE,
        related_name='records',
        verbose_name='审批')
    step_order = models.IntegerField(default=1, verbose_name='步骤序号')
    step_name = models.CharField(max_length=100, verbose_name='步骤名称')
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name='操作类型')
    comment = models.TextField(blank=True, verbose_name='审批意见')
    handler = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approval_handled_records',
        verbose_name='处理人')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='处理时间')

    class Meta:
        db_table = 'mimu_approval_record'
        verbose_name = '审批记录'
        verbose_name_plural = '审批记录'
        ordering = ['create_time']

    def __str__(self):
        return f'{self.approval.title} - {self.get_action_display()}'


class ApprovalTask(models.Model):
    """审批任务/节点实例"""
    STATUS_CHOICES = (
        ('pending', '待处理'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
        ('delegated', '已委托'),
        ('returned', '已退回'),
    )

    approval = models.ForeignKey(
        Approval,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='审批')
    step = models.ForeignKey(
        'ApprovalStep',
        on_delete=models.CASCADE,
        verbose_name='审批步骤')
    handler = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approval_tasks',
        verbose_name='处理人')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='任务状态')
    result = models.CharField(max_length=50, blank=True, default='', verbose_name='处理结果')
    comment = models.TextField(blank=True, default='', verbose_name='处理意见')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')

    class Meta:
        db_table = 'basedata_approval_task'
        verbose_name = '审批任务'
        verbose_name_plural = '审批任务'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.approval.title} - {self.step.step_name}'


class ApprovalType(models.Model):
    """审批类型"""
    name = models.CharField(max_length=100, verbose_name='类型名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='类型代码')
    description = models.TextField(blank=True, verbose_name='类型描述')
    icon = models.CharField(max_length=50, blank=True, verbose_name='图标')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'basedata_approval_type'
        verbose_name = '审批类型'
        verbose_name_plural = '审批类型'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class ApprovalFlow(models.Model):
    """审批流程"""
    name = models.CharField(max_length=100, verbose_name='流程名称')
    code = models.CharField(
        max_length=50,
        default='FLOW_001',
        unique=True,
        verbose_name='流程代码')
    description = models.TextField(blank=True, verbose_name='流程描述')
    approval_type = models.ForeignKey(
        ApprovalType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='审批类型')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    initiator_departments = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='可发起流程的部门ID，多个用逗号分隔',
        verbose_name='发起部门')
    initiator_roles = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='可发起流程的角色ID，多个用逗号分隔',
        verbose_name='发起角色')
    initiator_users = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='可发起流程的用户ID，多个用逗号分隔',
        verbose_name='发起用户')
    form_fields = models.TextField(
        blank=True, default='[]', verbose_name='自定义表单字段')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'basedata_approval_flow'
        verbose_name = '审批流程'
        verbose_name_plural = '审批流程'

    def __str__(self):
        return self.name


class ApprovalStep(models.Model):
    """审批步骤"""
    STEP_TYPE_CHOICES = (
        ('department_head', '部门负责人'),
        ('specific_user', '指定用户'),
        ('department', '指定部门'),
        ('role', '指定角色'),
        ('level', '指定级别'),
        ('cc', '抄送'),
        ('notification', '通知'),
        ('custom', '自定义条件'),
        ('countersign', '多人会签'),
        ('orsign', '多人或签'),
        ('execute', '办理/执行'),
        ('external', '外部审批'),
        ('condition', '条件分支'),
        ('status_update', '状态更新'),
        ('writeback', '数据回写'),
        ('archive', '归档通知'),
        ('intervention', '异常干预'),
    )

    ACTION_TYPE_CHOICES = (
        ('approve', '审批'),
        ('review', '审阅'),
        ('sign', '会签'),
        ('notify', '通知'),
        ('execute', '办理'),
        ('external', '外部审批'),
        ('archive', '归档'),
        ('system', '系统动作'),
    )

    APPROVAL_MODE_CHOICES = (
        ('single', '单人审批'),
        ('all', '全部同意'),
        ('any', '任一同意'),
    )

    TIMEOUT_ACTION_CHOICES = (
        ('none', '无'),
        ('auto_approve', '自动通过'),
        ('auto_reject', '自动拒绝'),
        ('escalate', '升级处理'),
    )

    flow = models.ForeignKey(
        ApprovalFlow,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name='所属流程')
    step_name = models.CharField(max_length=100, verbose_name='步骤名称')
    step_order = models.IntegerField(verbose_name='步骤顺序')
    step_type = models.CharField(
        max_length=20,
        choices=STEP_TYPE_CHOICES,
        default='department_head',
        verbose_name='步骤类型')
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPE_CHOICES,
        default='approve',
        verbose_name='操作类型')
    approver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='审批人',
        related_name='approval_steps')
    approver_role = models.CharField(
        max_length=100, blank=True, verbose_name='审批角色')
    approver_department = models.CharField(
        max_length=100, blank=True, verbose_name='审批部门')
    approver_level = models.CharField(
        max_length=100, blank=True, verbose_name='审批级别')
    cc_users = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='多个用户ID用逗号分隔',
        verbose_name='抄送用户')
    notification_users = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='多个用户ID用逗号分隔',
        verbose_name='通知用户')
    cc_roles = models.CharField(
        max_length=500,
        blank=True,
        help_text='多个角色用逗号分隔',
        verbose_name='抄送角色')
    cc_departments = models.CharField(
        max_length=500,
        blank=True,
        help_text='多个部门用逗号分隔',
        verbose_name='抄送部门')
    condition_field = models.CharField(
        max_length=100, blank=True, verbose_name='条件字段')
    condition_operator = models.CharField(
        max_length=20,
        blank=True,
        help_text='如：>, <, =, >=, <=, in, not_in',
        verbose_name='条件操作符')
    condition_value = models.CharField(
        max_length=200, blank=True, verbose_name='条件值')
    time_limit_hours = models.IntegerField(
        null=True, blank=True, verbose_name='处理时限(小时)')
    auto_approve_on_timeout = models.BooleanField(
        default=False, verbose_name='超时自动通过')
    approval_mode = models.CharField(
        max_length=20,
        choices=APPROVAL_MODE_CHOICES,
        default='single',
        verbose_name='审批方式')
    timeout_action = models.CharField(
        max_length=20,
        choices=TIMEOUT_ACTION_CHOICES,
        default='none',
        verbose_name='超时策略')
    config_json = models.TextField(default='{}', verbose_name='扩展配置')
    description = models.TextField(blank=True, verbose_name='步骤说明')
    is_required = models.BooleanField(default=True, verbose_name='是否必须')
    is_parallel = models.BooleanField(default=False, verbose_name='是否并行处理')
    allow_delegate = models.BooleanField(default=True, verbose_name='允许委托')
    allow_skip = models.BooleanField(default=False, verbose_name='允许跳过')
    require_comment = models.BooleanField(default=True, verbose_name='需要审批意见')
    comment_hint = models.CharField(
        max_length=200,
        default='请输入审批意见',
        verbose_name='意见提示文字')
    node_x = models.IntegerField(default=0, verbose_name='画布X坐标')
    node_y = models.IntegerField(default=0, verbose_name='画布Y坐标')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'basedata_approval_step'
        verbose_name = '审批步骤'
        verbose_name_plural = '审批步骤'
        ordering = ['step_order']

    def __str__(self):
        return f'{self.flow.name} - {self.step_name}'


class ApprovalFlowEdge(models.Model):
    """审批流程连线"""
    EDGE_TYPE_CHOICES = (
        ('success', '通过'),
        ('condition', '条件'),
        ('reject', '拒绝'),
        ('return', '退回'),
    )

    flow = models.ForeignKey(
        ApprovalFlow,
        on_delete=models.CASCADE,
        related_name='edges',
        verbose_name='所属流程')
    from_node = models.CharField(max_length=50, verbose_name='源节点')
    to_node = models.CharField(max_length=50, verbose_name='目标节点')
    source_port = models.CharField(
        max_length=30, blank=True, default='output_2', verbose_name='源连接点')
    target_port = models.CharField(
        max_length=30, blank=True, default='input_2', verbose_name='目标连接点')
    from_step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='outgoing_edges',
        verbose_name='源步骤')
    to_step = models.ForeignKey(
        ApprovalStep,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='incoming_edges',
        verbose_name='目标步骤')
    edge_type = models.CharField(
        max_length=20,
        choices=EDGE_TYPE_CHOICES,
        default='success',
        verbose_name='连线类型')
    label = models.CharField(
        max_length=100, blank=True, default='', verbose_name='连线标签')
    condition_field = models.CharField(
        max_length=100, blank=True, default='', verbose_name='条件字段')
    condition_operator = models.CharField(
        max_length=20, blank=True, default='', verbose_name='条件操作符')
    condition_value = models.CharField(
        max_length=200, blank=True, default='', verbose_name='条件值')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'basedata_approval_flow_edge'
        verbose_name = '审批流程连线'
        verbose_name_plural = '审批流程连线'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.flow.name}: {self.from_node} -> {self.to_node}'
