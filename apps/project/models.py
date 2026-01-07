from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.department.models import Department
from apps.customer.models import CustomerContract

class MediumTextField(models.TextField):
    def db_type(self, connection):
        return 'mediumtext'


class ProjectStage(models.Model):
    """项目阶段 - 从basedata迁移"""
    name = models.CharField(max_length=100, verbose_name='阶段名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='阶段代码')
    description = models.TextField(blank=True, verbose_name='阶段描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '项目阶段'
        verbose_name_plural = verbose_name
        db_table = 'basedata_project_stage'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class ProjectCategory(models.Model):
    """项目分类 - 从basedata迁移"""
    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='分类代码')
    description = models.TextField(blank=True, verbose_name='分类描述')
    color = models.CharField(max_length=20, blank=True, verbose_name='颜色标识')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '项目分类'
        verbose_name_plural = verbose_name
        db_table = 'basedata_project_category'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class WorkType(models.Model):
    """工作类别 - 从basedata迁移"""
    name = models.CharField(max_length=100, verbose_name='类别名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='类别代码')
    description = models.TextField(blank=True, verbose_name='类别描述')
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='小时费率')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '工作类别'
        verbose_name_plural = verbose_name
        db_table = 'basedata_work_type'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Project(models.Model):
    """项目模型"""
    STATUS_CHOICES = (
        (0, '未设置'),
        (1, '未开始'),
        (2, '进行中'),
        (3, '已完成'),
        (4, '已关闭'),
        (5, '已暂停'),
    )
    
    PRIORITY_CHOICES = (
        (1, '低'),
        (2, '中'),
        (3, '高'),
        (4, '紧急'),
    )
    
    name = models.CharField(max_length=255, verbose_name='项目名称')
    code = models.CharField(max_length=100, unique=True, verbose_name='项目编号')
    description = models.TextField(blank=True, verbose_name='项目描述')
    category = models.ForeignKey('ProjectCategory', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='项目分类')
    
    # 关联信息 - 实现深度集成
    customer = models.ForeignKey('customer.Customer', on_delete=models.CASCADE, null=True, blank=True, related_name='projects', verbose_name='关联客户')
    contract = models.ForeignKey('customer.CustomerContract', on_delete=models.SET_NULL, null=True, blank=True, related_name='projects', verbose_name='关联合同')
    
    # 项目负责人和团队
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='managed_projects', verbose_name='项目经理')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='project_members', verbose_name='项目成员')
    
    # 时间和预算
    start_date = models.DateField(null=True, blank=True, verbose_name='开始日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='结束日期')
    budget = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='项目预算')
    actual_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='实际成本')
    
    # 状态和优先级
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=1, verbose_name='项目状态')
    priority = models.PositiveSmallIntegerField(choices=PRIORITY_CHOICES, default=2, verbose_name='优先级')
    progress = models.PositiveSmallIntegerField(default=0, verbose_name='完成进度(%)')
    
    # 部门和创建信息
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='所属部门')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_projects', verbose_name='创建人')
    
    # 时间戳
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')
    auto_generated = models.BooleanField(default=False, verbose_name='是否自动生成')

    class Meta:
        db_table = 'project'
        verbose_name = '项目'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, '未知')
    
    @property
    def priority_display(self):
        return dict(self.PRIORITY_CHOICES).get(self.priority, '未知')
    
    @property
    def is_overdue(self):
        """是否已逾期"""
        if self.status in [3, 4] or not self.end_date:  # 已完成或已关闭或没有结束日期
            return False
        return timezone.now().date() > self.end_date
    
    @property
    def days_remaining(self):
        """剩余天数"""
        if self.status in [3, 4] or not self.end_date:
            return 0
        delta = self.end_date - timezone.now().date()
        return max(0, delta.days)

class ProjectStep(models.Model):
    """项目阶段"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='steps', verbose_name='所属项目')
    name = models.CharField(max_length=255, verbose_name='阶段名称')
    description = models.TextField(blank=True, verbose_name='阶段描述')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='阶段负责人')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='step_members', verbose_name='阶段成员')
    
    start_date = models.DateField(null=True, blank=True, verbose_name='开始日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='结束日期')
    sort = models.SmallIntegerField(default=0, verbose_name='排序')
    is_current = models.BooleanField(default=False, verbose_name='是否当前阶段')
    progress = models.PositiveSmallIntegerField(default=0, verbose_name='完成进度(%)')
    
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'project_step'
        verbose_name = '项目阶段'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class Task(models.Model):
    """任务模型"""
    STATUS_CHOICES = (
        (1, '未开始'),
        (2, '进行中'),
        (3, '已完成'),
        (4, '已延期'),
        (5, '已取消'),
    )
    
    PRIORITY_CHOICES = (
        (1, '低'),
        (2, '中'),
        (3, '高'),
        (4, '紧急'),
    )
    
    title = models.CharField(max_length=255, verbose_name='任务标题')
    description = models.TextField(blank=True, verbose_name='任务描述')
    
    # 关联信息
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks', verbose_name='所属项目')
    step = models.ForeignKey(ProjectStep, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks', verbose_name='所属阶段')
    
    # 任务负责人和参与者
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='assigned_tasks', verbose_name='负责人')
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='participated_tasks', verbose_name='参与人员')
    
    # 时间信息
    start_date = models.DateField(null=True, blank=True, verbose_name='开始日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='结束日期')
    estimated_hours = models.PositiveIntegerField(default=0, verbose_name='预估工时(小时)')
    actual_hours = models.PositiveIntegerField(default=0, verbose_name='实际工时(小时)')
    
    # 状态和优先级
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=1, verbose_name='任务状态')
    priority = models.PositiveSmallIntegerField(choices=PRIORITY_CHOICES, default=2, verbose_name='优先级')
    progress = models.PositiveSmallIntegerField(default=0, verbose_name='完成进度(%)')
    
    # 创建信息
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_tasks', verbose_name='创建人')
    
    # 时间戳
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')

    class Meta:
        db_table = 'task'
        verbose_name = '任务'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return self.title
    
    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, '未知')
    
    @property
    def priority_display(self):
        return dict(self.PRIORITY_CHOICES).get(self.priority, '未知')
    
    @property
    def is_overdue(self):
        """是否已逾期"""
        if self.status in [3, 5]:  # 已完成或已取消
            return False
        return timezone.now().date() > self.end_date


class WorkHour(models.Model):
    """工时记录"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='work_hours', verbose_name='关联任务')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='工作人员')
    
    work_date = models.DateField(verbose_name='工作日期')
    hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='工作时长(小时)')
    description = models.TextField(blank=True, verbose_name='工作内容描述')
    
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='记录时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'work_hour'
        verbose_name = '工时记录'
        verbose_name_plural = verbose_name
        ordering = ['-work_date', '-create_time']

    def __str__(self):
        return f"{self.user.username} - {self.task.title} - {self.hours}小时"


class ProjectDocument(models.Model):
    """项目文档"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='documents', verbose_name='所属项目')
    title = models.CharField(max_length=255, verbose_name='文档标题')
    content = models.TextField(blank=True, verbose_name='文档内容')
    file_path = models.CharField(max_length=500, blank=True, verbose_name='文件路径')
    
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='创建人')
    
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')

    class Meta:
        db_table = 'project_document'
        verbose_name = '项目文档'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.project.name} - {self.title}"
