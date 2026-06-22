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
        permissions = [
            ('view_message_center', '查看消息中心'),
            ('create_message', '发送消息'),
            ('mark_message_read', '标记已读'),
            ('star_message', '标星消息'),
            ('batch_message_operation', '批量操作'),
            ('view_message_preference', '查看通知偏好'),
            ('change_message_preference', '编辑通知偏好'),
            ('view_message_stats', '查看消息统计'),
        ]
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


class Conversation(models.Model):
    """统一沟通会话"""

    TYPE_DIRECT = 'direct'
    TYPE_GROUP = 'group'
    TYPE_DEPARTMENT = 'department'
    TYPE_SYSTEM = 'system'

    TYPE_CHOICES = (
        (TYPE_DIRECT, '单聊'),
        (TYPE_GROUP, '群聊'),
        (TYPE_DEPARTMENT, '部门群'),
        (TYPE_SYSTEM, '系统通知'),
    )

    conversation_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name='会话类型',
        db_index=True,
    )
    name = models.CharField(max_length=120, blank=True, verbose_name='会话名称')
    direct_key = models.CharField(
        max_length=120,
        unique=True,
        null=True,
        blank=True,
        verbose_name='单聊唯一键',
        help_text='排序后的两个用户ID组成的稳定键',
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_conversations',
        verbose_name='群主',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_conversations',
        verbose_name='创建人',
    )
    members = models.ManyToManyField(
        User,
        through='ConversationMember',
        related_name='conversations',
        verbose_name='会话成员',
    )
    last_message = models.ForeignKey(
        'ConversationMessage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='最后一条消息',
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='最后消息时间',
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name='扩展信息')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'message_conversation'
        verbose_name = '沟通会话'
        verbose_name_plural = '沟通会话'
        ordering = ['-last_message_at', '-created_at']
        permissions = [
            ('view_conversation_center', '查看沟通中心'),
            ('start_direct_conversation', '发起单聊'),
            ('create_group_conversation', '创建群聊'),
            ('manage_group_conversation', '管理群聊'),
            ('send_conversation_message', '发送沟通消息'),
            ('convert_message_to_task', '消息转任务'),
            ('view_message_read_receipts', '查看消息已读回执'),
        ]
        indexes = [
            models.Index(fields=['conversation_type', 'is_active']),
            models.Index(fields=['last_message_at']),
        ]

    def __str__(self):
        return self.name or self.get_conversation_type_display()


class ConversationMember(models.Model):
    """会话成员及个人会话状态"""

    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_MEMBER = 'member'

    ROLE_CHOICES = (
        (ROLE_OWNER, '群主'),
        (ROLE_ADMIN, '管理员'),
        (ROLE_MEMBER, '成员'),
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='member_relations',
        verbose_name='会话',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversation_memberships',
        verbose_name='成员',
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_MEMBER,
        verbose_name='成员角色',
    )
    is_muted = models.BooleanField(default=False, verbose_name='是否免打扰')
    is_pinned = models.BooleanField(default=False, verbose_name='是否置顶')
    is_archived = models.BooleanField(default=False, verbose_name='是否归档')
    last_read_message = models.ForeignKey(
        'ConversationMessage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='最后已读消息',
    )
    last_read_at = models.DateTimeField(null=True, blank=True, verbose_name='最后已读时间')
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='加入时间')
    left_at = models.DateTimeField(null=True, blank=True, verbose_name='离开时间')

    class Meta:
        db_table = 'message_conversation_member'
        verbose_name = '会话成员'
        verbose_name_plural = '会话成员'
        unique_together = ('conversation', 'user')
        indexes = [
            models.Index(fields=['user', 'left_at']),
            models.Index(fields=['conversation', 'left_at']),
            models.Index(fields=['conversation', 'role']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.conversation}'


class ConversationMessage(models.Model):
    """会话消息"""

    TYPE_TEXT = 'text'
    TYPE_IMAGE = 'image'
    TYPE_FILE = 'file'
    TYPE_SYSTEM = 'system'
    TYPE_TASK = 'task'

    TYPE_CHOICES = (
        (TYPE_TEXT, '文本'),
        (TYPE_IMAGE, '图片'),
        (TYPE_FILE, '文件'),
        (TYPE_SYSTEM, '系统'),
        (TYPE_TASK, '任务'),
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='会话',
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversation_messages',
        verbose_name='发送人',
    )
    message_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_TEXT,
        verbose_name='消息类型',
    )
    content = models.TextField(blank=True, verbose_name='消息内容')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='扩展信息')
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name='引用消息',
    )
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'message_conversation_message'
        verbose_name = '会话消息'
        verbose_name_plural = '会话消息'
        ordering = ['created_at', 'id']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['message_type']),
        ]

    def __str__(self):
        return self.content[:50] or self.get_message_type_display()


class ConversationMessageReceipt(models.Model):
    """会话消息送达和已读回执"""

    STATUS_DELIVERED = 'delivered'
    STATUS_READ = 'read'

    STATUS_CHOICES = (
        (STATUS_DELIVERED, '已送达'),
        (STATUS_READ, '已读'),
    )

    message = models.ForeignKey(
        ConversationMessage,
        on_delete=models.CASCADE,
        related_name='receipts',
        verbose_name='消息',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversation_message_receipts',
        verbose_name='用户',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DELIVERED,
        verbose_name='回执状态',
    )
    delivered_at = models.DateTimeField(auto_now_add=True, verbose_name='送达时间')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='已读时间')

    class Meta:
        db_table = 'message_conversation_receipt'
        verbose_name = '消息回执'
        verbose_name_plural = '消息回执'
        unique_together = ('message', 'user')
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['message', 'status']),
        ]

    @property
    def is_read(self):
        return self.status == self.STATUS_READ

    def __str__(self):
        return f'{self.user.username} - {self.message_id} - {self.status}'


class ConversationTaskLink(models.Model):
    """会话消息转任务关联"""

    message = models.ForeignKey(
        ConversationMessage,
        on_delete=models.CASCADE,
        related_name='task_links',
        verbose_name='来源消息',
    )
    task = models.ForeignKey(
        'project.Task',
        on_delete=models.CASCADE,
        related_name='conversation_links',
        verbose_name='关联任务',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_conversation_task_links',
        verbose_name='创建人',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'message_conversation_task_link'
        verbose_name = '消息转任务关联'
        verbose_name_plural = '消息转任务关联'
        unique_together = ('message', 'task')
        indexes = [
            models.Index(fields=['message']),
            models.Index(fields=['task']),
        ]

    def __str__(self):
        return f'{self.message_id} -> {self.task_id}'
