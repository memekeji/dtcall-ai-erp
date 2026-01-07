"""
优化后的OA办公模块模型
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.common.models import (
    SoftDeleteModel, BaseModel, StatusChoices, 
    PriorityChoices, ApprovalStatusChoices
)


class MeetingRecordParticipant(models.Model):
    """会议记录参会人员关联表"""
    meetingrecord = models.ForeignKey('MeetingRecord', on_delete=models.CASCADE, db_column='meetingrecord_id')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='user_id')
    
    class Meta:
        db_table = 'oa_meeting_record_participants'
        unique_together = ('meetingrecord', 'user')
        verbose_name = '会议记录与会人员'
        verbose_name_plural = '会议记录与会人员'


class MeetingRecordAttendee(models.Model):
    """会议记录实际出席人员关联表"""
    meetingrecord = models.ForeignKey('MeetingRecord', on_delete=models.CASCADE, db_column='meetingrecord_id')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='user_id')
    
    class Meta:
        db_table = 'oa_meeting_record_attendees'
        unique_together = ('meetingrecord', 'user')
        verbose_name = '会议记录实际出席人员'
        verbose_name_plural = '会议记录实际出席人员'


class MeetingRecordSharedUser(models.Model):
    """会议记录共享人员关联表"""
    meetingrecord = models.ForeignKey('MeetingRecord', on_delete=models.CASCADE, db_column='meetingrecord_id')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='user_id')
    
    class Meta:
        db_table = 'oa_meeting_record_shared_users'
        unique_together = ('meetingrecord', 'user')
        verbose_name = '会议记录共享人员'
        verbose_name_plural = '会议记录共享人员'


class MeetingRoom(SoftDeleteModel):
    """会议室管理"""
    name = models.CharField(max_length=100, verbose_name='会议室名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='会议室编号')
    location = models.CharField(max_length=200, verbose_name='会议室位置')
    capacity = models.IntegerField(default=10, verbose_name='容纳人数')
    
    # 设备配置
    has_projector = models.BooleanField(default=False, verbose_name='是否有投影仪')
    has_whiteboard = models.BooleanField(default=False, verbose_name='是否有白板')
    has_tv = models.BooleanField(default=False, verbose_name='是否有电视')
    has_phone = models.BooleanField(default=False, verbose_name='是否有电话')
    has_wifi = models.BooleanField(default=True, verbose_name='是否有WiFi')
    
    equipment_list = models.TextField(blank=True, verbose_name='设备清单')
    description = models.TextField(blank=True, verbose_name='会议室描述')
    
    # 管理信息
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='管理员'
    )
    
    status = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.ACTIVE, 
        verbose_name='状态'
    )

    class Meta:
        db_table = 'oa_meeting_room'
        verbose_name = '会议室'
        verbose_name_plural = verbose_name
        ordering = ['code']
        indexes = [
            models.Index(fields=['code'], name='idx_room_code'),
            models.Index(fields=['status'], name='idx_room_status'),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def is_available(self, start_time, end_time, exclude_meeting=None):
        """检查会议室是否可用"""
        from django.db.models import Q
        
        conflicts = MeetingRecord.objects.filter(
            room=self,
            meeting_date__lt=end_time,
            meeting_end_time__gt=start_time,
            status__in=['confirmed', 'in_progress']
        )
        
        if exclude_meeting:
            conflicts = conflicts.exclude(id=exclude_meeting.id)
        
        return not conflicts.exists()


class MeetingRecord(SoftDeleteModel):
    """优化后的会议记录模型"""
    title = models.CharField(max_length=255, verbose_name='会议主题')
    meeting_type = models.CharField(
        max_length=20,
        choices=[
            ('regular', '例会'),
            ('project', '项目会议'),
            ('training', '培训会议'),
            ('review', '评审会议'),
            ('emergency', '紧急会议'),
            ('other', '其他'),
        ],
        default='regular',
        verbose_name='会议类型'
    )
    
    # 时间安排
    meeting_date = models.DateTimeField(verbose_name='会议开始时间')
    meeting_end_time = models.DateTimeField(verbose_name='会议结束时间')
    duration = models.IntegerField(default=60, verbose_name='会议时长(分钟)')
    
    # 地点信息
    room = models.ForeignKey(
        MeetingRoom, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='会议室'
    )
    location = models.CharField(max_length=200, blank=True, verbose_name='会议地点')
    
    # 使用ForeignKey替代IntegerField
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='hosted_meetings', 
        verbose_name='主持人'
    )
    recorder = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='recorded_meetings', 
        verbose_name='记录人'
    )
    department = models.ForeignKey(
        'user.Department', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='组织部门'
    )
    
    # 使用ManyToManyField替代逗号分隔的ID
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        related_name='attended_meetings', 
        verbose_name='参会人员',
        through='MeetingRecordParticipant'
    )
    attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        related_name='signed_meetings', 
        verbose_name='实际出席人员',
        through='MeetingRecordAttendee'
    )
    
    # 会议状态
    status = models.CharField(
        max_length=20,
        choices=[
            ('scheduled', '已安排'),
            ('confirmed', '已确认'),
            ('in_progress', '进行中'),
            ('completed', '已完成'),
            ('cancelled', '已取消'),
            ('postponed', '已延期'),
        ],
        default='scheduled',
        verbose_name='会议状态'
    )
    
    # 会议内容
    agenda = models.TextField(blank=True, verbose_name='会议议程')
    content = models.TextField(blank=True, verbose_name='会议内容')
    resolution = models.TextField(blank=True, verbose_name='会议决议')
    action_items = models.TextField(blank=True, verbose_name='行动项')
    next_meeting = models.DateTimeField(null=True, blank=True, verbose_name='下次会议时间')
    
    # 附件和共享
    attachments = models.TextField(blank=True, verbose_name='会议附件')
    shared_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        related_name='shared_meetings', 
        verbose_name='共享人员',
        through='MeetingRecordSharedUser'
    )
    
    # 会议评价
    rating = models.IntegerField(
        choices=[(i, f'{i}分') for i in range(1, 6)], 
        null=True, 
        blank=True, 
        verbose_name='会议评分'
    )
    feedback = models.TextField(blank=True, verbose_name='会议反馈')

    class Meta:
        db_table = 'oa_meeting_record'
        verbose_name = '会议记录'
        verbose_name_plural = verbose_name
        ordering = ['-meeting_date']
        indexes = [
            models.Index(fields=['meeting_date'], name='idx_meeting_date'),
            models.Index(fields=['host'], name='idx_meeting_host'),
            models.Index(fields=['department'], name='idx_meeting_dept'),
            models.Index(fields=['status'], name='idx_meeting_status'),
            models.Index(fields=['room'], name='idx_meeting_room'),
        ]

    def __str__(self):
        return f"{self.title} - {self.meeting_date.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        # 自动计算会议时长
        if self.meeting_date and self.meeting_end_time:
            duration = self.meeting_end_time - self.meeting_date
            self.duration = int(duration.total_seconds() / 60)
        
        super().save(*args, **kwargs)

    @property
    def attendance_rate(self):
        """出席率"""
        total_participants = self.participants.count()
        actual_attendees = self.attendees.count()
        if total_participants > 0:
            return round((actual_attendees / total_participants) * 100, 2)
        return 0

    @property
    def is_past(self):
        """是否已过期"""
        return timezone.now() > self.meeting_end_time

    def get_status_color(self):
        """获取状态颜色"""
        status_colors = {
            'scheduled': 'blue',
            'confirmed': 'green',
            'in_progress': 'orange',
            'completed': 'green',
            'cancelled': 'red',
            'postponed': 'gray',
        }
        return status_colors.get(self.status, 'gray')


class Announcement(SoftDeleteModel):
    """公告通知"""
    title = models.CharField(max_length=255, verbose_name='公告标题')
    content = models.TextField(verbose_name='公告内容')
    
    announcement_type = models.CharField(
        max_length=20,
        choices=[
            ('notice', '通知公告'),
            ('news', '新闻动态'),
            ('policy', '制度政策'),
            ('activity', '活动通知'),
            ('urgent', '紧急通知'),
        ],
        default='notice',
        verbose_name='公告类型'
    )
    
    priority = models.IntegerField(
        choices=PriorityChoices.choices, 
        default=PriorityChoices.MEDIUM, 
        verbose_name='优先级'
    )
    
    # 发布信息
    publisher = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='published_announcements',
        verbose_name='发布人'
    )
    department = models.ForeignKey(
        'user.Department', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='发布部门'
    )
    
    # 发布范围
    target_type = models.CharField(
        max_length=20,
        choices=[
            ('all', '全体人员'),
            ('department', '指定部门'),
            ('user', '指定人员'),
            ('role', '指定角色'),
        ],
        default='all',
        verbose_name='发布范围'
    )
    target_departments = models.ManyToManyField(
        'user.Department', 
        blank=True, 
        related_name='received_announcements',
        verbose_name='目标部门'
    )
    target_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        related_name='received_announcements',
        verbose_name='目标用户'
    )
    
    # 发布设置
    publish_date = models.DateTimeField(verbose_name='发布时间')
    expire_date = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')
    is_top = models.BooleanField(default=False, verbose_name='是否置顶')
    is_published = models.BooleanField(default=False, verbose_name='是否已发布')
    
    # 统计信息
    view_count = models.IntegerField(default=0, verbose_name='查看次数')
    
    # 附件
    attachments = models.TextField(blank=True, verbose_name='附件列表')

    class Meta:
        db_table = 'oa_announcement'
        verbose_name = '公告通知'
        verbose_name_plural = verbose_name
        ordering = ['-is_top', '-publish_date']
        indexes = [
            models.Index(fields=['announcement_type'], name='idx_announce_type'),
            models.Index(fields=['publisher'], name='idx_announce_publisher'),
            models.Index(fields=['publish_date'], name='idx_announce_publish'),
            models.Index(fields=['is_published'], name='idx_announce_published'),
            models.Index(fields=['is_top'], name='idx_announce_top'),
        ]

    def __str__(self):
        return self.title

    @property
    def is_expired(self):
        """是否已过期"""
        if self.expire_date:
            return timezone.now() > self.expire_date
        return False

    def get_priority_color(self):
        """获取优先级颜色"""
        priority_colors = {
            PriorityChoices.LOW: 'gray',
            PriorityChoices.MEDIUM: 'blue',
            PriorityChoices.HIGH: 'orange',
            PriorityChoices.URGENT: 'red',
        }
        return priority_colors.get(self.priority, 'gray')


class AnnouncementReadRecord(BaseModel):
    """公告阅读记录"""
    announcement = models.ForeignKey(
        Announcement, 
        on_delete=models.CASCADE, 
        related_name='read_records',
        verbose_name='公告'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name='阅读用户'
    )
    read_time = models.DateTimeField(auto_now_add=True, verbose_name='阅读时间')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')

    class Meta:
        db_table = 'oa_announcement_read_record'
        verbose_name = '公告阅读记录'
        verbose_name_plural = verbose_name
        unique_together = ['announcement', 'user']
        indexes = [
            models.Index(fields=['announcement'], name='idx_read_announce'),
            models.Index(fields=['user'], name='idx_read_user'),
            models.Index(fields=['read_time'], name='idx_read_time'),
        ]

    def __str__(self):
        return f"{self.user.name} - {self.announcement.title}"


class Message(SoftDeleteModel):
    """优化后的消息模型"""
    # 恢复auto_now_add=True
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间', db_index=True)
    title = models.CharField(max_length=255, verbose_name='消息标题')
    content = models.TextField(verbose_name='消息内容')
    
    message_type = models.CharField(
        max_length=20,
        choices=[
            ('system', '系统消息'),
            ('notice', '通知消息'),
            ('personal', '个人消息'),
            ('group', '群组消息'),
        ],
        default='system',
        verbose_name='消息类型'
    )
    
    # 发送信息
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='sent_messages',
        verbose_name='发送人'
    )
    
    # 接收信息
    receiver_type = models.CharField(
        max_length=20,
        choices=[
            ('user', '指定用户'),
            ('department', '指定部门'),
            ('role', '指定角色'),
            ('all', '全体用户'),
        ],
        default='user',
        verbose_name='接收类型'
    )
    receivers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        related_name='received_messages',
        verbose_name='接收用户'
    )
    receiver_departments = models.ManyToManyField(
        'user.Department', 
        blank=True, 
        related_name='received_messages',
        verbose_name='接收部门'
    )
    
    # 消息设置
    priority = models.IntegerField(
        choices=PriorityChoices.choices, 
        default=PriorityChoices.MEDIUM, 
        verbose_name='优先级'
    )
    is_draft = models.BooleanField(default=False, verbose_name='是否草稿')
    send_time = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')
    
    # 附件
    attachments = models.TextField(blank=True, verbose_name='附件列表')
    
    # 关联消息（回复/转发）
    parent_message = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='replies',
        verbose_name='父消息'
    )

    class Meta:
        db_table = 'oa_message'
        verbose_name = '消息管理'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender'], name='idx_msg_sender'),
            models.Index(fields=['message_type'], name='idx_msg_type'),
            models.Index(fields=['send_time'], name='idx_msg_send_time'),
            models.Index(fields=['is_draft'], name='idx_msg_draft'),
            models.Index(fields=['priority'], name='idx_msg_priority'),
        ]

    def __str__(self):
        return self.title

    def get_priority_color(self):
        """获取优先级颜色"""
        priority_colors = {
            PriorityChoices.LOW: 'gray',
            PriorityChoices.MEDIUM: 'blue',
            PriorityChoices.HIGH: 'orange',
            PriorityChoices.URGENT: 'red',
        }
        return priority_colors.get(self.priority, 'gray')


class MessageReadRecord(BaseModel):
    """消息阅读记录"""
    message = models.ForeignKey(
        Message, 
        on_delete=models.CASCADE, 
        related_name='read_records',
        verbose_name='消息'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name='阅读用户'
    )
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    read_time = models.DateTimeField(null=True, blank=True, verbose_name='阅读时间')

    class Meta:
        db_table = 'oa_message_read_record'
        verbose_name = '消息阅读记录'
        verbose_name_plural = verbose_name
        unique_together = ['message', 'user']
        indexes = [
            models.Index(fields=['message'], name='idx_msg_read_message'),
            models.Index(fields=['user'], name='idx_msg_read_user'),
            models.Index(fields=['is_read'], name='idx_msg_read_status'),
        ]

    def __str__(self):
        return f"{self.user.name} - {self.message.title}"


class ApprovalFlow(SoftDeleteModel):
    """审批流程"""
    name = models.CharField(max_length=100, verbose_name='流程名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='流程代码')
    description = models.TextField(blank=True, verbose_name='流程描述')
    
    flow_type = models.CharField(
        max_length=20,
        choices=[
            ('expense', '报销审批'),
            ('leave', '请假审批'),
            ('purchase', '采购审批'),
            ('contract', '合同审批'),
            ('other', '其他审批'),
        ],
        default='other',
        verbose_name='流程类型'
    )
    
    # 流程设置
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    is_default = models.BooleanField(default=False, verbose_name='是否默认流程')
    
    # 适用范围
    departments = models.ManyToManyField(
        'user.Department', 
        blank=True, 
        verbose_name='适用部门'
    )
    
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name='创建人'
    )

    class Meta:
        db_table = 'oa_approval_flow'
        verbose_name = '审批流程'
        verbose_name_plural = verbose_name
        ordering = ['code']
        indexes = [
            models.Index(fields=['code'], name='idx_flow_code'),
            models.Index(fields=['flow_type'], name='idx_flow_type'),
            models.Index(fields=['is_active'], name='idx_flow_active'),
        ]

    def __str__(self):
        return self.name


class ApprovalStep(BaseModel):
    """审批步骤"""
    flow = models.ForeignKey(
        ApprovalFlow, 
        on_delete=models.CASCADE, 
        related_name='steps',
        verbose_name='审批流程'
    )
    name = models.CharField(max_length=100, verbose_name='步骤名称')
    step_order = models.IntegerField(verbose_name='步骤顺序')
    
    # 审批人设置
    approver_type = models.CharField(
        max_length=20,
        choices=[
            ('user', '指定用户'),
            ('role', '指定角色'),
            ('department_leader', '部门负责人'),
            ('direct_supervisor', '直属上级'),
        ],
        default='user',
        verbose_name='审批人类型'
    )
    approvers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        verbose_name='审批人'
    )
    
    # 步骤设置
    is_required = models.BooleanField(default=True, verbose_name='是否必须')
    can_skip = models.BooleanField(default=False, verbose_name='是否可跳过')
    timeout_hours = models.IntegerField(default=24, verbose_name='超时时间(小时)')

    class Meta:
        db_table = 'oa_approval_step'
        verbose_name = '审批步骤'
        verbose_name_plural = verbose_name
        ordering = ['flow', 'step_order']
        indexes = [
            models.Index(fields=['flow'], name='idx_step_flow'),
            models.Index(fields=['step_order'], name='idx_step_order'),
        ]

    def __str__(self):
        return f"{self.flow.name} - {self.name}"


class ApprovalRequest(SoftDeleteModel):
    """审批申请"""
    title = models.CharField(max_length=255, verbose_name='申请标题')
    content = models.TextField(verbose_name='申请内容')
    
    # 申请信息
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='approval_requests',
        verbose_name='申请人'
    )
    department = models.ForeignKey(
        'user.Department', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='申请部门'
    )
    
    # 流程信息
    flow = models.ForeignKey(
        ApprovalFlow, 
        on_delete=models.CASCADE, 
        verbose_name='审批流程'
    )
    current_step = models.ForeignKey(
        ApprovalStep, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='当前步骤'
    )
    
    # 状态信息
    status = models.CharField(
        max_length=20, 
        choices=ApprovalStatusChoices.choices, 
        default=ApprovalStatusChoices.PENDING, 
        verbose_name='审批状态'
    )
    
    # 时间信息
    submit_time = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    # 附件
    attachments = models.TextField(blank=True, verbose_name='附件列表')

    class Meta:
        db_table = 'oa_approval_request'
        verbose_name = '审批申请'
        verbose_name_plural = verbose_name
        ordering = ['-submit_time']
        indexes = [
            models.Index(fields=['applicant'], name='idx_approval_applicant'),
            models.Index(fields=['flow'], name='idx_approval_flow'),
            models.Index(fields=['status'], name='idx_approval_status'),
            models.Index(fields=['submit_time'], name='idx_approval_submit'),
        ]

    def __str__(self):
        return self.title

    def get_status_color(self):
        """获取状态颜色"""
        status_colors = {
            ApprovalStatusChoices.DRAFT: 'gray',
            ApprovalStatusChoices.PENDING: 'orange',
            ApprovalStatusChoices.IN_REVIEW: 'blue',
            ApprovalStatusChoices.APPROVED: 'green',
            ApprovalStatusChoices.REJECTED: 'red',
            ApprovalStatusChoices.CANCELLED: 'gray',
        }
        return status_colors.get(self.status, 'gray')


class ApprovalRecord(BaseModel):
    """审批记录"""
    request = models.ForeignKey(
        ApprovalRequest, 
        on_delete=models.CASCADE, 
        related_name='approval_records',
        verbose_name='审批申请'
    )
    step = models.ForeignKey(
        ApprovalStep, 
        on_delete=models.CASCADE, 
        verbose_name='审批步骤'
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name='审批人'
    )
    
    # 审批结果
    result = models.CharField(
        max_length=20,
        choices=[
            ('approved', '同意'),
            ('rejected', '拒绝'),
            ('returned', '退回'),
        ],
        verbose_name='审批结果'
    )
    comment = models.TextField(blank=True, verbose_name='审批意见')
    approval_time = models.DateTimeField(auto_now_add=True, verbose_name='审批时间')

    class Meta:
        db_table = 'oa_approval_record'
        verbose_name = '审批记录'
        verbose_name_plural = verbose_name
        ordering = ['-approval_time']
        indexes = [
            models.Index(fields=['request'], name='idx_approval_rec_request'),
            models.Index(fields=['approver'], name='idx_approval_rec_approver'),
            models.Index(fields=['result'], name='idx_approval_rec_result'),
        ]

    def __str__(self):
        return f"{self.request.title} - {self.approver.name}"