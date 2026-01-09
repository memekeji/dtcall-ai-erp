from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.department.models import Department
from apps.oa.models import MeetingRecord

User = get_user_model()


class PersonalSchedule(models.Model):
    """个人日程安排"""
    PRIORITY_CHOICES = (
        (1, '低'),
        (2, '中'),
        (3, '高'),
        (4, '紧急'),
    )
    
    STATUS_CHOICES = (
        ('pending', '待处理'),
        ('in_progress', '进行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    )

    title = models.CharField(max_length=200, verbose_name='日程标题')
    content = models.TextField(blank=True, verbose_name='日程内容')
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='结束时间')
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2, verbose_name='优先级')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    location = models.CharField(max_length=200, blank=True, verbose_name='地点')
    reminder_time = models.DateTimeField(null=True, blank=True, verbose_name='提醒时间')
    is_all_day = models.BooleanField(default=False, verbose_name='全天事件')
    is_private = models.BooleanField(default=False, verbose_name='私人事件')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '个人日程'
        verbose_name_plural = verbose_name
        db_table = 'personal_schedule'
        ordering = ['-start_time']

    def __str__(self):
        return self.title

    @property
    def priority_display(self):
        return dict(self.PRIORITY_CHOICES).get(self.priority, '未知')

    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, '未知')


class WorkRecord(models.Model):
    """工作记录"""
    WORK_TYPES = (
        ('daily', '日常工作'),
        ('project', '项目工作'),
        ('meeting', '会议'),
        ('training', '培训学习'),
        ('other', '其他'),
    )

    title = models.CharField(max_length=200, verbose_name='工作标题')
    content = models.TextField(verbose_name='工作内容')
    work_type = models.CharField(max_length=20, choices=WORK_TYPES, default='daily', verbose_name='工作类型')
    work_date = models.DateField(verbose_name='工作日期')
    start_time = models.TimeField(verbose_name='开始时间')
    end_time = models.TimeField(verbose_name='结束时间')
    duration = models.FloatField(verbose_name='工作时长(小时)')
    progress = models.IntegerField(default=0, verbose_name='完成进度(%)')
    difficulty = models.IntegerField(default=3, verbose_name='难度系数(1-5)')
    result = models.TextField(blank=True, verbose_name='工作成果')
    problem = models.TextField(blank=True, verbose_name='遇到问题')
    next_plan = models.TextField(blank=True, verbose_name='下步计划')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='部门')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '工作记录'
        verbose_name_plural = verbose_name
        db_table = 'personal_work_record'
        ordering = ['-work_date', '-start_time']

    def __str__(self):
        return f"{self.work_date} - {self.title}"

    @property
    def work_type_display(self):
        return dict(self.WORK_TYPES).get(self.work_type, '未知')


class WorkReport(models.Model):
    """工作汇报"""
    REPORT_TYPES = (
        ('daily', '日报'),
        ('weekly', '周报'),
        ('monthly', '月报'),
        ('project', '项目汇报'),
        ('special', '专项汇报'),
    )

    title = models.CharField(max_length=200, verbose_name='汇报标题')
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, verbose_name='汇报类型')
    report_date = models.DateField(verbose_name='汇报日期')
    summary = models.TextField(verbose_name='工作总结')
    completed_work = models.TextField(verbose_name='已完成工作')
    next_work = models.TextField(verbose_name='下期工作计划')
    problems = models.TextField(blank=True, verbose_name='存在问题')
    suggestions = models.TextField(blank=True, verbose_name='意见建议')
    attachments = models.TextField(blank=True, verbose_name='附件列表')
    recipient_users = models.ManyToManyField(User, related_name='received_reports', blank=True, verbose_name='接收人')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='汇报人')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='部门')
    is_submitted = models.BooleanField(default=False, verbose_name='已提交')
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name='提交时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '工作汇报'
        verbose_name_plural = verbose_name
        db_table = 'personal_work_report'
        ordering = ['-report_date']

    def __str__(self):
        return f"{self.report_date} - {self.title}"

    @property
    def report_type_display(self):
        return dict(self.REPORT_TYPES).get(self.report_type, '未知')


class PersonalNote(models.Model):
    """个人笔记"""
    CATEGORIES = (
        ('work', '工作笔记'),
        ('study', '学习笔记'),
        ('meeting', '会议纪要'),
        ('idea', '想法记录'),
        ('other', '其他'),
    )

    title = models.CharField(max_length=200, verbose_name='笔记标题')
    content = models.TextField(verbose_name='笔记内容')
    category = models.CharField(max_length=20, choices=CATEGORIES, default='work', verbose_name='笔记分类')
    tags = models.CharField(max_length=200, blank=True, verbose_name='标签')
    is_important = models.BooleanField(default=False, verbose_name='重要标记')
    is_private = models.BooleanField(default=True, verbose_name='私人笔记')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '个人笔记'
        verbose_name_plural = verbose_name
        db_table = 'personal_note'
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    @property
    def category_display(self):
        return dict(self.CATEGORIES).get(self.category, '未知')


class PersonalTask(models.Model):
    """个人任务"""
    PRIORITY_CHOICES = (
        (1, '低'),
        (2, '中'),
        (3, '高'),
        (4, '紧急'),
    )
    
    STATUS_CHOICES = (
        ('todo', '待办'),
        ('in_progress', '进行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    )

    title = models.CharField(max_length=200, verbose_name='任务标题')
    description = models.TextField(blank=True, verbose_name='任务描述')
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2, verbose_name='优先级')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo', verbose_name='状态')
    due_date = models.DateTimeField(null=True, blank=True, verbose_name='截止时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    progress = models.IntegerField(default=0, verbose_name='完成进度(%)')
    estimated_hours = models.FloatField(null=True, blank=True, verbose_name='预估工时')
    actual_hours = models.FloatField(null=True, blank=True, verbose_name='实际工时')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '个人任务'
        verbose_name_plural = verbose_name
        db_table = 'personal_task'
        ordering = ['-priority', 'due_date']

    def __str__(self):
        return self.title

    @property
    def priority_display(self):
        return dict(self.PRIORITY_CHOICES).get(self.priority, '未知')

    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, '未知')

    @property
    def is_overdue(self):
        if self.due_date and self.status not in ['completed', 'cancelled']:
            return timezone.now() > self.due_date
        return False


class PersonalContact(models.Model):
    """个人通讯录"""
    name = models.CharField(max_length=100, verbose_name='姓名')
    company = models.CharField(max_length=200, blank=True, verbose_name='公司')
    position = models.CharField(max_length=100, blank=True, verbose_name='职位')
    phone = models.CharField(max_length=20, blank=True, verbose_name='电话')
    mobile = models.CharField(max_length=20, blank=True, verbose_name='手机')
    email = models.EmailField(blank=True, verbose_name='邮箱')
    address = models.TextField(blank=True, verbose_name='地址')
    notes = models.TextField(blank=True, verbose_name='备注')
    tags = models.CharField(max_length=200, blank=True, verbose_name='标签')
    is_important = models.BooleanField(default=False, verbose_name='重要联系人')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '个人通讯录'
        verbose_name_plural = verbose_name
        db_table = 'personal_contact'
        ordering = ['name']

    def __str__(self):
        return self.name


class MeetingMinutes(models.Model):
    """会议纪要"""
    MEETING_TYPE_CHOICES = (
        ('regular', '例会'),
        ('project', '项目会议'),
        ('training', '培训会议'),
        ('review', '评审会议'),
        ('emergency', '紧急会议'),
        ('other', '其他'),
    )
    
    title = models.CharField(max_length=200, verbose_name='会议主题')
    meeting_type = models.CharField(max_length=20, choices=MEETING_TYPE_CHOICES, default='regular', verbose_name='会议类型')
    meeting_date = models.DateTimeField(verbose_name='会议时间')
    location = models.CharField(max_length=200, blank=True, verbose_name='会议地点')
    host = models.CharField(max_length=100, blank=True, verbose_name='主持人')
    recorder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recorded_meeting_minutes', verbose_name='记录人')
    attendees = models.TextField(blank=True, verbose_name='参会人员')
    content = models.TextField(blank=True, verbose_name='会议内容')
    decisions = models.TextField(blank=True, verbose_name='会议决议')
    action_items = models.TextField(blank=True, verbose_name='行动项')
    attachments = models.TextField(blank=True, verbose_name='附件')
    is_public = models.BooleanField(default=True, verbose_name='是否公开')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    meeting_record = models.ForeignKey(MeetingRecord, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='关联会议记录')

    class Meta:
        verbose_name = '会议纪要'
        verbose_name_plural = verbose_name
        db_table = 'personal_meeting_minutes'
        ordering = ['-meeting_date']

    def __str__(self):
        return self.title