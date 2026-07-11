from django.conf import settings
from django.db import models


class AIOperation(models.Model):
    STATUS_CHOICES = [
        ('preview', '预览'),
        ('confirmed', '已确认'),
        ('executed', '已执行'),
        ('failed', '执行失败'),
        ('cancelled', '已取消'),
        ('rolled_back', '已回退'),
    ]

    ROLLBACK_STATUS_CHOICES = [
        ('not_requested', '未请求'),
        ('pending', '进行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_operations',
        verbose_name='操作用户',
    )
    chat = models.ForeignKey(
        'ai.AIChat',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operations',
        verbose_name='关联会话',
    )
    user_message = models.ForeignKey(
        'ai.AIChatMessage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_operations',
        verbose_name='用户消息',
    )
    ai_message = models.ForeignKey(
        'ai.AIChatMessage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assistant_operations',
        verbose_name='AI消息',
    )
    operation_type = models.CharField(max_length=50, verbose_name='操作类型')
    resource_type = models.CharField(max_length=50, verbose_name='资源类型')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='preview',
        verbose_name='状态',
    )
    preview_payload = models.JSONField(default=dict, blank=True, verbose_name='预览载荷')
    confirmed_payload = models.JSONField(default=dict, blank=True, verbose_name='确认载荷')
    confirmation_token = models.CharField(max_length=120, blank=True, default='', verbose_name='确认令牌')
    requires_confirmation = models.BooleanField(default=True, verbose_name='是否需要确认')
    rollback_status = models.CharField(
        max_length=20,
        choices=ROLLBACK_STATUS_CHOICES,
        default='not_requested',
        verbose_name='回退状态',
    )
    rollback_reason = models.TextField(blank=True, default='', verbose_name='回退原因')
    executed_at = models.DateTimeField(null=True, blank=True, verbose_name='执行时间')
    rolled_back_at = models.DateTimeField(null=True, blank=True, verbose_name='回退时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ai_operation'
        verbose_name = 'AI操作'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.resource_type}:{self.operation_type}:{self.status}'


class AIOperationChangeSet(models.Model):
    CHANGE_TYPE_CHOICES = [
        ('create', '创建'),
        ('update', '更新'),
        ('delete', '删除'),
    ]

    operation = models.ForeignKey(
        AIOperation,
        on_delete=models.CASCADE,
        related_name='change_sets',
        verbose_name='所属操作',
    )
    sequence = models.PositiveIntegerField(default=1, verbose_name='顺序')
    app_label = models.CharField(max_length=50, verbose_name='应用')
    model_name = models.CharField(max_length=100, verbose_name='模型')
    object_pk = models.CharField(max_length=100, verbose_name='对象主键')
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPE_CHOICES, verbose_name='变更类型')
    before_snapshot = models.JSONField(null=True, blank=True, verbose_name='变更前快照')
    after_snapshot = models.JSONField(null=True, blank=True, verbose_name='变更后快照')
    changed_fields = models.JSONField(default=list, blank=True, verbose_name='变更字段')
    is_rollback_supported = models.BooleanField(default=True, verbose_name='支持回退')
    rollback_metadata = models.JSONField(default=dict, blank=True, verbose_name='回退元数据')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'ai_operation_change_set'
        verbose_name = 'AI操作变更集'
        verbose_name_plural = verbose_name
        ordering = ['sequence', 'id']

    def __str__(self):
        return f'{self.app_label}.{self.model_name}#{self.object_pk}:{self.change_type}'


class AIOperationConfirmation(models.Model):
    operation = models.OneToOneField(
        AIOperation,
        on_delete=models.CASCADE,
        related_name='confirmation',
        verbose_name='所属操作',
    )
    token = models.CharField(max_length=120, unique=True, verbose_name='确认令牌')
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_ai_operations',
        verbose_name='确认人',
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')
    is_used = models.BooleanField(default=False, verbose_name='是否已使用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'ai_operation_confirmation'
        verbose_name = 'AI操作确认'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.token


class AIOperationRollback(models.Model):
    STATUS_CHOICES = [
        ('pending', '进行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]

    operation = models.ForeignKey(
        AIOperation,
        on_delete=models.CASCADE,
        related_name='rollbacks',
        verbose_name='所属操作',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_ai_rollbacks',
        verbose_name='请求人',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    result_summary = models.JSONField(default=dict, blank=True, verbose_name='结果摘要')
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')

    class Meta:
        db_table = 'ai_operation_rollback'
        verbose_name = 'AI操作回退记录'
        verbose_name_plural = verbose_name
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.operation_id}:{self.status}'
