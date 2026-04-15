from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class MessageCategory(models.Model):
    """消息分类/类型"""
    TYPE_CHOICES = (
        ('announcement', '公告通知'),
        ('approval', '审批通知'),
        ('task', '任务通知'),
        ('system', '系统通知'),
        ('comment', '评论回复通知'),
    )

    name = models.CharField(max_length=50, verbose_name='分类名称')
    code = models.CharField(max_length=30, unique=True, verbose_name='分类代码')
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name='消息类型')
    icon = models.CharField(
        max_length=50,
        default='layui-icon-notice',
        verbose_name='图标')
    description = models.CharField(
        max_length=200, blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'message_category'
        verbose_name = '消息分类'
        verbose_name_plural = '消息分类'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class Message(models.Model):
    """消息模型"""
    PRIORITY_CHOICES = (
        (1, '低'),
        (2, '普通'),
        (3, '高'),
        (4, '紧急'),
    )

    category = models.ForeignKey(
        MessageCategory,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='消息分类'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='received_messages',
        verbose_name='接收用户'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notification_sent_messages',
        verbose_name='发送者'
    )
    title = models.CharField(max_length=200, verbose_name='消息标题')
    content = models.TextField(verbose_name='消息内容')
    priority = models.IntegerField(
        default=2,
        choices=PRIORITY_CHOICES,
        verbose_name='优先级')
    is_broadcast = models.BooleanField(default=False, verbose_name='是否广播消息')
    target_users = models.TextField(
        blank=True,
        default='',
        help_text='目标用户ID列表，JSON格式',
        verbose_name='目标用户')
    target_departments = models.TextField(
        blank=True,
        default='',
        help_text='目标部门ID列表，JSON格式',
        verbose_name='目标部门')

    related_object_type = models.CharField(
        max_length=100, blank=True, verbose_name='关联对象类型')
    related_object_id = models.BigIntegerField(
        null=True, blank=True, verbose_name='关联对象ID')
    action_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='跳转链接')

    expire_time = models.DateTimeField(
        null=True, blank=True, verbose_name='过期时间')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    # AI功能
    ai_summary = models.TextField(blank=True, null=True, verbose_name='AI消息摘要')
    ai_suggested_replies = models.JSONField(blank=True, null=True, verbose_name='AI建议回复', default=list)

    class Meta:
        db_table = 'message'
        verbose_name = '消息'
        verbose_name_plural = '消息'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['is_active']),
            models.Index(fields=['related_object_type', 'related_object_id']),
        ]

    def __str__(self):
        return self.title


class MessageUserRelation(models.Model):
    """用户消息关系（存储用户的阅读状态、标星等）"""
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='user_relations',
        verbose_name='消息'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='message_relations',
        verbose_name='用户'
    )
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    is_starred = models.BooleanField(default=False, verbose_name='是否标星')
    read_time = models.DateTimeField(
        null=True, blank=True, verbose_name='阅读时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'message_user_relation'
        verbose_name = '用户消息关系'
        verbose_name_plural = '用户消息关系'
        unique_together = ('message', 'user')
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'is_starred']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.message.title}'


class NotificationPreference(models.Model):
    """用户通知偏好设置"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preference',
        verbose_name='用户'
    )
    enable_email = models.BooleanField(default=True, verbose_name='启用邮件通知')
    enable_browser = models.BooleanField(default=True, verbose_name='启用浏览器通知')
    quiet_hours_start = models.TimeField(
        null=True, blank=True, verbose_name='免打扰开始时间')
    quiet_hours_end = models.TimeField(
        null=True, blank=True, verbose_name='免打扰结束时间')
    notify_announcement = models.BooleanField(
        default=True, verbose_name='公告通知')
    notify_approval = models.BooleanField(default=True, verbose_name='审批通知')
    notify_task = models.BooleanField(default=True, verbose_name='任务通知')
    notify_comment = models.BooleanField(default=True, verbose_name='评论通知')
    notify_system = models.BooleanField(default=True, verbose_name='系统通知')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'notification_preference'
        verbose_name = '用户通知偏好'
        verbose_name_plural = '用户通知偏好'

    def __str__(self):
        return f'{self.user.username}的通知偏好'
