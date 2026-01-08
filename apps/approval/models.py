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
    flow = models.ForeignKey('ApprovalFlow', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='审批流程')
    type_id = models.PositiveIntegerField(default=0, verbose_name='审批类型ID')
    applicant_id = models.PositiveIntegerField(default=0, verbose_name='申请人ID')
    status = models.PositiveSmallIntegerField(default=0, choices=STATUS_CHOICES, verbose_name='审批状态')
    content = models.TextField(blank=True, default='', verbose_name='申请内容')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='审核人', null=True, blank=True)

    class Meta:
        db_table = 'mimu_approval'
        verbose_name = '审批表'
        verbose_name_plural = '审批表'

    def __str__(self):
        return self.title


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
    code = models.CharField(max_length=50, default='FLOW_001', unique=True, verbose_name='流程代码')
    description = models.TextField(blank=True, verbose_name='流程描述')
    approval_type = models.ForeignKey(ApprovalType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='审批类型')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    initiator_departments = models.CharField(max_length=500, blank=True, default='', help_text='可发起流程的部门ID，多个用逗号分隔', verbose_name='发起部门')
    initiator_roles = models.CharField(max_length=500, blank=True, default='', help_text='可发起流程的角色ID，多个用逗号分隔', verbose_name='发起角色')
    initiator_users = models.CharField(max_length=500, blank=True, default='', help_text='可发起流程的用户ID，多个用逗号分隔', verbose_name='发起用户')
    form_fields = models.TextField(blank=True, default='[]', verbose_name='自定义表单字段')
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
    )
    
    ACTION_TYPE_CHOICES = (
        ('approve', '审批'),
        ('review', '审阅'),
        ('sign', '会签'),
        ('notify', '通知'),
    )

    flow = models.ForeignKey(ApprovalFlow, on_delete=models.CASCADE, related_name='steps', verbose_name='所属流程')
    step_name = models.CharField(max_length=100, verbose_name='步骤名称')
    step_order = models.IntegerField(verbose_name='步骤顺序')
    step_type = models.CharField(max_length=20, choices=STEP_TYPE_CHOICES, default='department_head', verbose_name='步骤类型')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPE_CHOICES, default='approve', verbose_name='操作类型')
    approver = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name='审批人', related_name='approval_steps')
    approver_role = models.CharField(max_length=100, blank=True, verbose_name='审批角色')
    approver_department = models.CharField(max_length=100, blank=True, verbose_name='审批部门')
    approver_level = models.CharField(max_length=100, blank=True, verbose_name='审批级别')
    cc_users = models.CharField(max_length=500, blank=True, default='', help_text='多个用户ID用逗号分隔', verbose_name='抄送用户')
    notification_users = models.CharField(max_length=500, blank=True, default='', help_text='多个用户ID用逗号分隔', verbose_name='通知用户')
    cc_roles = models.CharField(max_length=500, blank=True, help_text='多个角色用逗号分隔', verbose_name='抄送角色')
    cc_departments = models.CharField(max_length=500, blank=True, help_text='多个部门用逗号分隔', verbose_name='抄送部门')
    condition_field = models.CharField(max_length=100, blank=True, verbose_name='条件字段')
    condition_operator = models.CharField(max_length=20, blank=True, help_text='如：>, <, =, >=, <=, in, not_in', verbose_name='条件操作符')
    condition_value = models.CharField(max_length=200, blank=True, verbose_name='条件值')
    time_limit_hours = models.IntegerField(null=True, blank=True, verbose_name='处理时限(小时)')
    auto_approve_on_timeout = models.BooleanField(default=False, verbose_name='超时自动通过')
    description = models.TextField(blank=True, verbose_name='步骤说明')
    is_required = models.BooleanField(default=True, verbose_name='是否必须')
    is_parallel = models.BooleanField(default=False, verbose_name='是否并行处理')
    allow_delegate = models.BooleanField(default=True, verbose_name='允许委托')
    allow_skip = models.BooleanField(default=False, verbose_name='允许跳过')
    require_comment = models.BooleanField(default=True, verbose_name='需要审批意见')
    comment_hint = models.CharField(max_length=200, default='请输入审批意见', verbose_name='意见提示文字')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'basedata_approval_step'
        verbose_name = '审批步骤'
        verbose_name_plural = '审批步骤'
        ordering = ['step_order']

    def __str__(self):
        return f'{self.flow.name} - {self.step_name}'
