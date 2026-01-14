from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
import json

User = get_user_model()

try:
    from apps.oa.models import MeetingRoom as OAMeetingRoom
except ImportError:
    OAMeetingRoom = None


class AssetCategory(models.Model):
    """资产分类"""
    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='分类代码')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name='上级分类')
    description = models.TextField(blank=True, verbose_name='分类描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '资产分类'
        verbose_name_plural = verbose_name
        db_table = 'system_asset_category'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class AssetBrand(models.Model):
    """资产品牌"""
    name = models.CharField(max_length=100, verbose_name='品牌名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='品牌代码')
    description = models.TextField(blank=True, verbose_name='品牌描述')
    logo = models.CharField(max_length=500, blank=True, verbose_name='品牌Logo')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '品牌管理'
        verbose_name_plural = verbose_name
        db_table = 'system_asset_brand'
        ordering = ['name']

    def __str__(self):
        return self.name


class SystemAttachment(models.Model):
    """系统附件"""
    name = models.CharField(max_length=200, verbose_name='文件名')
    original_name = models.CharField(max_length=200, verbose_name='原始文件名')
    file_path = models.CharField(max_length=500, verbose_name='文件路径')
    file_size = models.BigIntegerField(verbose_name='文件大小')
    file_type = models.CharField(max_length=50, verbose_name='文件类型')
    module = models.CharField(max_length=100, verbose_name='所属模块')
    object_id = models.CharField(max_length=50, blank=True, verbose_name='关联对象ID')
    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='上传者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')

    class Meta:
        verbose_name = '系统附件'
        verbose_name_plural = verbose_name
        db_table = 'system_attachment'
        ordering = ['-created_at']

    def __str__(self):
        return self.original_name


class SystemBackup(models.Model):
    """数据备份"""
    BACKUP_TYPES = (
        ('full', '完整备份'),
        ('incremental', '增量备份'),
        ('differential', '差异备份'),
    )

    name = models.CharField(max_length=200, verbose_name='备份名称')
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES, verbose_name='备份类型')
    file_path = models.CharField(max_length=500, verbose_name='备份文件路径')
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小')
    description = models.TextField(blank=True, verbose_name='备份描述')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='备份时间')

    class Meta:
        verbose_name = '数据备份'
        verbose_name_plural = verbose_name
        db_table = 'system_backup'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class BackupPolicy(models.Model):
    """自动备份策略"""
    # 执行周期选项
    INTERVAL_CHOICES = (
        ('daily', '每天'),
        ('weekly', '每周'),
        ('monthly', '每月'),
    )

    name = models.CharField(max_length=200, verbose_name='策略名称')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES, verbose_name='执行周期')
    # 每天执行的时间点
    hour = models.IntegerField(default=2, verbose_name='小时', help_text='0-23，每天执行的小时')
    minute = models.IntegerField(default=0, verbose_name='分钟', help_text='0-59，每天执行的分钟')
    # 每周执行的星期几（0-6，0表示周日）
    week_day = models.IntegerField(default=0, verbose_name='星期', help_text='0-6，每周执行的星期几，0表示周日')
    # 每月执行的日期（1-31）
    month_day = models.IntegerField(default=1, verbose_name='日期', help_text='1-31，每月执行的日期')
    # 保留最新备份份数
    keep_count = models.IntegerField(default=7, verbose_name='保留份数', help_text='保留最新备份的数量')
    # 备份类型（暂时只支持完整备份）
    backup_type = models.CharField(max_length=20, choices=SystemBackup.BACKUP_TYPES, default='full', verbose_name='备份类型')
    description = models.TextField(blank=True, verbose_name='策略描述')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '自动备份策略'
        verbose_name_plural = verbose_name
        db_table = 'system_backup_policy'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_interval_display()})"


class SystemTask(models.Model):
    """定时任务"""
    TASK_STATUS = (
        ('active', '启用'),
        ('inactive', '禁用'),
        ('running', '运行中'),
        ('error', '错误'),
    )

    name = models.CharField(max_length=200, verbose_name='任务名称')
    command = models.TextField(verbose_name='执行命令')
    cron_expression = models.CharField(max_length=100, verbose_name='Cron表达式')
    description = models.TextField(blank=True, verbose_name='任务描述')
    status = models.CharField(max_length=20, choices=TASK_STATUS, default='inactive', verbose_name='任务状态')
    last_run_time = models.DateTimeField(null=True, blank=True, verbose_name='最后执行时间')
    next_run_time = models.DateTimeField(null=True, blank=True, verbose_name='下次执行时间')
    run_count = models.IntegerField(default=0, verbose_name='执行次数')
    error_count = models.IntegerField(default=0, verbose_name='错误次数')
    last_error = models.TextField(blank=True, verbose_name='最后错误信息')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '定时任务'
        verbose_name_plural = verbose_name
        db_table = 'system_task'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


# 行政办公相关模型
class Asset(models.Model):
    """固定资产"""
    ASSET_STATUS = (
        ('normal', '正常'),
        ('repair', '维修中'),
        ('scrap', '报废'),
        ('lost', '丢失'),
    )
    
    asset_number = models.CharField(max_length=50, unique=True, verbose_name='资产编号')
    name = models.CharField(max_length=200, verbose_name='资产名称')
    category = models.ForeignKey('AssetCategory', on_delete=models.SET_NULL, null=True, verbose_name='资产分类')
    brand = models.ForeignKey('AssetBrand', on_delete=models.SET_NULL, null=True, verbose_name='品牌')
    model = models.CharField(max_length=100, blank=True, verbose_name='型号')
    specification = models.TextField(blank=True, verbose_name='规格参数')
    purchase_date = models.DateField(verbose_name='购买日期')
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='购买价格')
    supplier = models.CharField(max_length=200, blank=True, verbose_name='供应商')
    warranty_period = models.IntegerField(default=12, verbose_name='保修期(月)')
    location = models.CharField(max_length=200, blank=True, verbose_name='存放位置')
    responsible_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='责任人')
    department = models.ForeignKey('department.Department', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='使用部门')
    status = models.CharField(max_length=20, choices=ASSET_STATUS, default='normal', verbose_name='状态')
    description = models.TextField(blank=True, verbose_name='备注说明')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '固定资产'
        verbose_name_plural = verbose_name
        db_table = 'system_asset'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.asset_number} - {self.name}"


class AssetRepair(models.Model):
    """资产报修记录"""
    REPAIR_STATUS = (
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    )
    
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, null=True, verbose_name='资产')
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='reported_repairs', verbose_name='报修人')
    repair_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='handled_repairs', verbose_name='维修人')
    fault_description = models.TextField(verbose_name='故障描述')
    repair_description = models.TextField(blank=True, verbose_name='维修说明')
    repair_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='维修费用')
    status = models.CharField(max_length=20, choices=REPAIR_STATUS, default='pending', verbose_name='状态')
    report_time = models.DateTimeField(auto_now_add=True, verbose_name='报修时间')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='开始维修时间')
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    
    class Meta:
        verbose_name = '资产报修记录'
        verbose_name_plural = verbose_name
        db_table = 'system_asset_repair'
        ordering = ['-report_time']

    def __str__(self):
        return f"{self.asset.name} - {self.get_status_display()}"


class Vehicle(models.Model):
    """车辆信息"""
    VEHICLE_STATUS = (
        ('normal', '正常'),
        ('repair', '维修中'),
        ('scrap', '报废'),
    )
    
    license_plate = models.CharField(max_length=20, unique=True, verbose_name='车牌号')
    brand = models.CharField(max_length=50, verbose_name='品牌')
    model = models.CharField(max_length=50, verbose_name='型号')
    color = models.CharField(max_length=20, verbose_name='颜色')
    engine_number = models.CharField(max_length=50, verbose_name='发动机号')
    frame_number = models.CharField(max_length=50, verbose_name='车架号')
    purchase_date = models.DateField(verbose_name='购买日期')
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='购买价格')
    driver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='司机')
    status = models.CharField(max_length=20, choices=VEHICLE_STATUS, default='normal', verbose_name='状态')
    insurance_expire = models.DateField(null=True, blank=True, verbose_name='保险到期日')
    annual_inspection = models.DateField(null=True, blank=True, verbose_name='年检日期')
    description = models.TextField(blank=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '车辆信息'
        verbose_name_plural = verbose_name
        db_table = 'system_vehicle'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.license_plate} - {self.brand} {self.model}"


class VehicleMaintenance(models.Model):
    """车辆维修记录"""
    MAINTENANCE_TYPE = (
        ('repair', '维修'),
        ('maintain', '保养'),
    )
    
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, verbose_name='车辆')
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPE, verbose_name='类型')
    maintenance_date = models.DateField(verbose_name='维修/保养日期')
    mileage = models.IntegerField(verbose_name='里程数(公里)')
    cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='费用')
    service_provider = models.CharField(max_length=200, verbose_name='服务商')
    description = models.TextField(verbose_name='维修/保养内容')
    next_maintenance = models.DateField(null=True, blank=True, verbose_name='下次保养日期')
    operator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='操作人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '车辆维修保养记录'
        verbose_name_plural = verbose_name
        db_table = 'system_vehicle_maintenance'
        ordering = ['-maintenance_date']

    def __str__(self):
        return f"{self.vehicle.license_plate} - {self.get_maintenance_type_display()}"


class VehicleFee(models.Model):
    """车辆费用记录"""
    FEE_TYPE_CHOICES = (
        ('fuel', '燃油费'),
        ('insurance', '保险费'),
        ('tax', '车船税'),
        ('parking', '停车费'),
        ('toll', '过路费'),
        ('fine', '罚款'),
        ('other', '其他'),
    )
    
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, verbose_name='车辆')
    fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES, verbose_name='费用类型')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='金额')
    fee_date = models.DateField(verbose_name='费用日期')
    description = models.TextField(blank=True, verbose_name='说明')
    operator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='操作人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '车辆费用记录'
        verbose_name_plural = verbose_name
        db_table = 'system_vehicle_fee'
        ordering = ['-fee_date']

    def __str__(self):
        return f"{self.vehicle.license_plate} - {self.get_fee_type_display()}"


class VehicleOil(models.Model):
    """车辆油耗记录"""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, verbose_name='车辆')
    oil_amount = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='加油量(升)')
    oil_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='加油费用')
    mileage = models.IntegerField(verbose_name='里程数(公里)')
    oil_date = models.DateField(verbose_name='加油日期')
    gas_station = models.CharField(max_length=200, verbose_name='加油站')
    operator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='操作人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '车辆油耗记录'
        verbose_name_plural = verbose_name
        db_table = 'system_vehicle_oil'
        ordering = ['-oil_date']

    def __str__(self):
        return f"{self.vehicle.license_plate} - {self.oil_date}"


class Notice(models.Model):
    """公告管理"""
    NOTICE_TYPE = (
        ('company', '公司公告'),
        ('system', '系统通知'),
        ('urgent', '紧急通知'),
    )
    
    title = models.CharField(max_length=200, verbose_name='公告标题')
    content = models.TextField(verbose_name='公告内容')
    notice_type = models.CharField(max_length=20, choices=NOTICE_TYPE, default='company', verbose_name='公告类型')
    is_top = models.BooleanField(default=False, verbose_name='是否置顶')
    is_published = models.BooleanField(default=False, verbose_name='是否发布')
    publish_time = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    expire_time = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')
    target_departments = models.ManyToManyField('department.Department', through='NoticeTargetDepartment', blank=True, verbose_name='目标部门')
    target_users = models.ManyToManyField(User, through='NoticeTargetUser', blank=True, verbose_name='目标用户')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authored_notices', verbose_name='发布人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '公告'
        verbose_name_plural = verbose_name
        db_table = 'system_notice'
        ordering = ['-is_top', '-publish_time']

    def __str__(self):
        return self.title


class NoticeRead(models.Model):
    """公告阅读记录"""
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, verbose_name='公告')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    read_time = models.DateTimeField(auto_now_add=True, verbose_name='阅读时间')

    class Meta:
        verbose_name = '公告阅读记录'
        verbose_name_plural = verbose_name
        db_table = 'system_notice_read'
        unique_together = ['notice', 'user']

    def __str__(self):
        return f"{self.user.name} - {self.notice.title}"


class Seal(models.Model):
    """印章管理"""
    SEAL_TYPE = (
        ('company', '公司公章'),
        ('contract', '合同专用章'),
        ('finance', '财务专用章'),
        ('legal', '法人章'),
        ('other', '其他'),
    )
    
    name = models.CharField(max_length=100, verbose_name='印章名称')
    seal_type = models.CharField(max_length=20, choices=SEAL_TYPE, verbose_name='印章类型')
    keeper = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='保管人')
    location = models.CharField(max_length=200, blank=True, verbose_name='存放位置')
    description = models.TextField(blank=True, verbose_name='备注')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '印章'
        verbose_name_plural = verbose_name
        db_table = 'system_seal'
        ordering = ['name']

    def __str__(self):
        return self.name


class SealApplication(models.Model):
    """用章申请"""
    STATUS_CHOICES = (
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('used', '已用章'),
        ('cancelled', '已取消'),
    )
    
    seal = models.ForeignKey(Seal, on_delete=models.CASCADE, verbose_name='印章')
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='申请人')
    purpose = models.TextField(verbose_name='用章用途')
    document_title = models.CharField(max_length=200, verbose_name='文件标题')
    use_date = models.DateField(verbose_name='用章日期')
    copies = models.IntegerField(default=1, verbose_name='份数')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_seal_applications', verbose_name='审批人')
    approve_time = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    approve_comment = models.TextField(blank=True, verbose_name='审批意见')
    use_time = models.DateTimeField(null=True, blank=True, verbose_name='用章时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='申请时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '用章申请'
        verbose_name_plural = verbose_name
        db_table = 'system_seal_application'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.seal.name} - {self.document_title}"


class DocumentCategory(models.Model):
    """公文分类"""
    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=20, unique=True, verbose_name='分类编码')
    description = models.TextField(blank=True, verbose_name='分类描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '公文分类'
        verbose_name_plural = verbose_name
        db_table = 'system_document_category'
        ordering = ['code']
    
    def __str__(self):
        return self.name


class Document(models.Model):
    """公文"""
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('pending', '待审核'),
        ('reviewing', '审核中'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('published', '已发布'),
        ('archived', '已归档'),
    )
    
    URGENCY_CHOICES = (
        ('normal', '普通'),
        ('urgent', '紧急'),
        ('very_urgent', '特急'),
    )
    
    SECURITY_LEVEL = (
        ('public', '公开'),
        ('internal', '内部'),
        ('confidential', '机密'),
        ('secret', '秘密'),
    )
    
    title = models.CharField(max_length=200, verbose_name='公文标题')
    document_number = models.CharField(max_length=50, unique=True, verbose_name='公文编号')
    category = models.ForeignKey(DocumentCategory, on_delete=models.CASCADE, verbose_name='公文分类')
    content = models.TextField(verbose_name='公文内容')
    summary = models.TextField(blank=True, verbose_name='公文摘要')
    
    author = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='authored_documents', verbose_name='起草人')
    department = models.ForeignKey('department.Department', on_delete=models.CASCADE, null=True, blank=True, verbose_name='起草部门')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='normal', verbose_name='紧急程度')
    security_level = models.CharField(max_length=20, choices=SECURITY_LEVEL, default='internal', verbose_name='密级')
    
    # 审批相关
    current_reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewing_documents', verbose_name='当前审批人')
    review_deadline = models.DateTimeField(null=True, blank=True, verbose_name='审批截止时间')
    
    # 发布相关
    publish_time = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    effective_time = models.DateTimeField(null=True, blank=True, verbose_name='生效时间')
    expire_time = models.DateTimeField(null=True, blank=True, verbose_name='失效时间')
    
    # 接收范围
    target_departments = models.ManyToManyField('department.Department', through='DocumentTargetDepartment', blank=True, related_name='received_documents', verbose_name='接收部门')
    target_users = models.ManyToManyField(User, through='DocumentTargetUser', blank=True, related_name='received_documents', verbose_name='接收人员')
    
    # 附件
    attachments = models.TextField(blank=True, verbose_name='附件信息')
    
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '公文'
        verbose_name_plural = verbose_name
        db_table = 'system_document'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.document_number} - {self.title}"


class DocumentReview(models.Model):
    """公文审批记录"""
    REVIEW_RESULT = (
        ('pending', '待审批'),
        ('approved', '通过'),
        ('rejected', '拒绝'),
        ('returned', '退回修改'),
    )
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, verbose_name='公文')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='审批人')
    review_order = models.IntegerField(verbose_name='审批顺序')
    result = models.CharField(max_length=20, choices=REVIEW_RESULT, default='pending', verbose_name='审批结果')
    comment = models.TextField(blank=True, verbose_name='审批意见')
    review_time = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '公文审批记录'
        verbose_name_plural = verbose_name
        db_table = 'system_document_review'
        ordering = ['review_order']
        unique_together = ['document', 'reviewer']
    
    def __str__(self):
        return f"{self.document.title} - {self.reviewer.name}"


class DocumentRead(models.Model):
    """公文阅读记录"""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, verbose_name='公文')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='阅读人')
    read_time = models.DateTimeField(auto_now_add=True, verbose_name='阅读时间')
    
    class Meta:
        verbose_name = '公文阅读记录'
        verbose_name_plural = verbose_name
        db_table = 'system_document_read'
        unique_together = ['document', 'user']
    
    def __str__(self):
        return f"{self.user.name} - {self.document.title}"


class NoticeTargetDepartment(models.Model):
    """公告目标部门中间表"""
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, verbose_name='公告')
    department = models.ForeignKey('department.Department', on_delete=models.CASCADE, verbose_name='目标部门')
    
    class Meta:
        verbose_name = '公告目标部门'
        verbose_name_plural = verbose_name
        db_table = 'system_notice_target_departments'
        unique_together = ['notice', 'department']
    
    def __str__(self):
        return f"{self.department.name} - {self.notice.title}"


class NoticeTargetUser(models.Model):
    """公告目标用户中间表"""
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, verbose_name='公告')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='目标用户')
    
    class Meta:
        verbose_name = '公告目标用户'
        verbose_name_plural = verbose_name
        db_table = 'system_notice_target_users'
        unique_together = ['notice', 'user']
    
    def __str__(self):
        return f"{self.user.name} - {self.notice.title}"


class DocumentTargetDepartment(models.Model):
    """公文目标部门中间表"""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, verbose_name='公文')
    department = models.ForeignKey('department.Department', on_delete=models.CASCADE, verbose_name='目标部门')
    
    class Meta:
        verbose_name = '公文目标部门'
        verbose_name_plural = verbose_name
        db_table = 'system_document_target_departments'
        unique_together = ['document', 'department']
    
    def __str__(self):
        return f"{self.department.name} - {self.document.title}"


class DocumentTargetUser(models.Model):
    """公文目标用户中间表"""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, verbose_name='公文')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='目标用户')
    
    class Meta:
        verbose_name = '公文目标用户'
        verbose_name_plural = verbose_name
        db_table = 'system_document_target_users'
        unique_together = ['document', 'user']
    
    def __str__(self):
        return f"{self.user.name} - {self.document.title}"


class MeetingReservation(models.Model):
    """会议室预订"""
    STATUS_CHOICES = (
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('cancelled', '已取消'),
    )
    
    if OAMeetingRoom:
        meeting_room = models.ForeignKey(OAMeetingRoom, on_delete=models.CASCADE, verbose_name='会议室')
    else:
        meeting_room_id = models.IntegerField(verbose_name='会议室ID')
        @property
        def meeting_room(self):
            return None
    
    title = models.CharField(max_length=200, verbose_name='会议主题')
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='system_meeting_reservations', verbose_name='组织者')
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='结束时间')
    attendees = models.ManyToManyField(User, blank=True, related_name='system_meeting_attendees', verbose_name='参会人员')
    description = models.TextField(blank=True, verbose_name='会议描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '会议室预订'
        verbose_name_plural = verbose_name
        db_table = 'system_meeting_reservation'
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.meeting_room.name if self.meeting_room else '未知'} - {self.title}"


from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import os
import json


class StorageProvider:
    LOCAL = 'local'
    ALIYUN = 'aliyun'
    TENCENT = 'tencent'
    HUAWEI = 'huawei'
    BAIDU = 'baidu'
    QINIU = 'qiniu'
    AWS = 'aws'
    FEINIU_NAS = 'feiniu_nas'
    QUNHUI_NAS = 'qunhui_nas'
    WEBDAV = 'webdav'

    CHOICES = (
        (LOCAL, '本地存储'),
        (ALIYUN, '阿里云OSS'),
        (TENCENT, '腾讯云COS'),
        (HUAWEI, '华为云OBS'),
        (BAIDU, '百度云BOS'),
        (QINIU, '七牛云KODO'),
        (AWS, 'AWS S3'),
        (FEINIU_NAS, '飞牛NAS'),
        (QUNHUI_NAS, '群晖NAS'),
        (WEBDAV, 'WebDAV'),
    )


class StorageConfiguration(models.Model):
    """存储配置"""
    STORAGE_TYPES = (
        (StorageProvider.LOCAL, '本地存储'),
        (StorageProvider.ALIYUN, '阿里云OSS'),
        (StorageProvider.TENCENT, '腾讯云COS'),
        (StorageProvider.HUAWEI, '华为云OBS'),
        (StorageProvider.BAIDU, '百度云BOS'),
        (StorageProvider.QINIU, '七牛云KODO'),
        (StorageProvider.AWS, 'AWS S3'),
        (StorageProvider.FEINIU_NAS, '飞牛NAS'),
        (StorageProvider.QUNHUI_NAS, '群晖NAS'),
        (StorageProvider.WEBDAV, 'WebDAV'),
    )

    STATUS_CHOICES = (
        ('active', '启用'),
        ('inactive', '禁用'),
        ('testing', '测试中'),
        ('error', '错误'),
    )

    name = models.CharField(max_length=100, verbose_name='配置名称')
    storage_type = models.CharField(max_length=50, choices=STORAGE_TYPES, verbose_name='存储类型')
    is_default = models.BooleanField(default=False, verbose_name='是否默认')
    sync_to_local = models.BooleanField(default=False, verbose_name='同步到本地')

    access_key = models.CharField(max_length=200, blank=True, verbose_name='AccessKey')
    secret_key = models.CharField(max_length=200, blank=True, verbose_name='SecretKey')
    bucket_name = models.CharField(max_length=100, blank=True, verbose_name='存储桶名称')
    endpoint = models.CharField(max_length=200, blank=True, verbose_name='Endpoint地址')
    region = models.CharField(max_length=100, blank=True, verbose_name='区域')
    domain = models.CharField(max_length=200, blank=True, verbose_name='访问域名')
    base_path = models.CharField(max_length=200, blank=True, verbose_name='基础路径')

    nas_host = models.CharField(max_length=200, blank=True, verbose_name='NAS主机地址')
    nas_port = models.IntegerField(default=0, verbose_name='NAS端口')
    nas_share_path = models.CharField(max_length=200, blank=True, verbose_name='共享路径')
    webdav_url = models.CharField(max_length=500, blank=True, verbose_name='WebDAV地址')
    webdav_username = models.CharField(max_length=100, blank=True, verbose_name='WebDAV用户名')
    webdav_password = models.CharField(max_length=100, blank=True, verbose_name='WebDAV密码')

    local_path = models.CharField(max_length=500, blank=True, verbose_name='本地存储路径')
    max_file_size = models.BigIntegerField(default=0, verbose_name='最大文件大小(字节)')
    allowed_extensions = models.TextField(blank=True, verbose_name='允许的文件扩展名')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive', verbose_name='状态')
    last_test_time = models.DateTimeField(null=True, blank=True, verbose_name='最后测试时间')
    last_error = models.TextField(blank=True, verbose_name='最后错误信息')

    description = models.TextField(blank=True, verbose_name='描述')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '存储配置'
        verbose_name_plural = verbose_name
        db_table = 'system_storage_config'
        ordering = ['-is_default', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_storage_type_display()})"

    def save(self, *args, **kwargs):
        if self.is_default:
            StorageConfiguration.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class ServiceCategory:
    SMS = 'sms'
    STT = 'stt'
    TTS = 'tts'
    OCR = 'ocr'
    AI = 'ai'

    CHOICES = (
        (SMS, '短信服务'),
        (STT, '语音转文本'),
        (TTS, '文本转语音'),
        (OCR, 'OCR识别'),
        (AI, 'AI智能服务'),
    )

    ICONS = {
        SMS: 'layui-icon-cellphone',
        STT: 'layui-icon-audio',
        TTS: 'layui-icon-speaker',
        OCR: 'layui-icon-picture',
        AI: 'layui-icon-engine',
    }


class ServiceProvider:
    ALIYUN = 'aliyun'
    TENCENT = 'tencent'
    HUAWEI = 'huawei'
    BAIDU = 'baidu'
    QINIU = 'qiniu'
    AWS = 'aws'
    AZURE = 'azure'
    ANTHROPIC = 'anthropic'
    OPENAI = 'openai'
    ZHIPU = 'zhipu'

    SMS_PROVIDERS = (
        (ALIYUN, '阿里云'),
        (TENCENT, '腾讯云'),
        (HUAWEI, '华为云'),
        (BAIDU, '百度云'),
    )

    STT_PROVIDERS = (
        (ALIYUN, '阿里云'),
        (TENCENT, '腾讯云'),
        (BAIDU, '百度云'),
        (AZURE, 'Azure'),
    )

    TTS_PROVIDERS = (
        (ALIYUN, '阿里云'),
        (TENCENT, '腾讯云'),
        (BAIDU, '百度云'),
        (AZURE, 'Azure'),
    )

    OCR_PROVIDERS = (
        (ALIYUN, '阿里云'),
        (TENCENT, '腾讯云'),
        (BAIDU, '百度云'),
    )

    AI_PROVIDERS = (
        (OPENAI, 'OpenAI'),
        (AZURE, 'Azure OpenAI'),
        (ANTHROPIC, 'Anthropic'),
        (BAIDU, '百度文心'),
        (ALIYUN, '阿里通义千问'),
        (TENCENT, '腾讯混元'),
        (ZHIPU, '智谱AI'),
    )


class ServiceConfiguration(models.Model):
    """服务配置"""
    CATEGORY_CHOICES = (
        (ServiceCategory.SMS, '短信服务'),
        (ServiceCategory.STT, '语音转文本'),
        (ServiceCategory.TTS, '文本转语音'),
        (ServiceCategory.OCR, 'OCR识别'),
        (ServiceCategory.AI, 'AI智能服务'),
    )

    STATUS_CHOICES = (
        ('active', '启用'),
        ('inactive', '禁用'),
        ('testing', '测试中'),
        ('error', '错误'),
    )

    name = models.CharField(max_length=100, verbose_name='配置名称')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='服务类别')
    provider = models.CharField(max_length=50, verbose_name='服务商')
    
    api_key = models.CharField(max_length=500, blank=True, verbose_name='API密钥')
    api_secret = models.CharField(max_length=500, blank=True, verbose_name='API密钥Secret')
    base_url = models.CharField(max_length=500, blank=True, verbose_name='接口地址')
    
    template_id = models.CharField(max_length=100, blank=True, verbose_name='模板ID')
    sign_name = models.CharField(max_length=100, blank=True, verbose_name='签名名称')
    
    request_rate_limit = models.IntegerField(default=0, verbose_name='请求频率限制(次/秒)')
    max_audio_size = models.BigIntegerField(default=0, verbose_name='最大音频大小(字节)')
    supported_formats = models.CharField(max_length=200, blank=True, verbose_name='支持格式')
    
    extra_config = models.TextField(blank=True, verbose_name='额外配置(JSON格式)')

    is_enabled = models.BooleanField(default=False, verbose_name='是否启用')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive', verbose_name='状态')
    last_test_time = models.DateTimeField(null=True, blank=True, verbose_name='最后测试时间')
    last_error = models.TextField(blank=True, verbose_name='最后错误信息')

    description = models.TextField(blank=True, verbose_name='描述')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '服务配置'
        verbose_name_plural = verbose_name
        db_table = 'system_service_config'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def get_provider_display(self):
        provider_value = self.provider
        if self.category == ServiceCategory.SMS:
            providers = ServiceProvider.SMS_PROVIDERS
        elif self.category == ServiceCategory.STT:
            providers = ServiceProvider.STT_PROVIDERS
        elif self.category == ServiceCategory.TTS:
            providers = ServiceProvider.TTS_PROVIDERS
        elif self.category == ServiceCategory.OCR:
            providers = ServiceProvider.OCR_PROVIDERS
        elif self.category == ServiceCategory.AI:
            providers = ServiceProvider.AI_PROVIDERS
        else:
            return provider_value

        for value, text in providers:
            if value == provider_value:
                return text
        return provider_value

    def get_icon(self):
        return ServiceCategory.ICONS.get(self.category, 'layui-icon技术服务')

    def get_api_key_masked(self):
        api_key = self.api_key
        if len(api_key) <= 4:
            return '****'
        return '*' * (len(api_key) - 4) + api_key[-4:]

    def to_dict(self):
        import json
        extra_config = {}
        if self.extra_config:
            try:
                extra_config = json.loads(self.extra_config)
            except json.JSONDecodeError:
                pass

        return {
            'pk': self.pk,
            'name': self.name,
            'category': self.category,
            'category_display': self.get_category_display(),
            'provider': self.provider,
            'provider_display': self.get_provider_display(),
            'api_key_masked': self.get_api_key_masked(),
            'base_url': self.base_url,
            'template_id': self.template_id,
            'sign_name': self.sign_name,
            'description': self.description,
            'is_enabled': self.is_enabled,
            'status': self.status,
            'icon': self.get_icon(),
            'test_available': self.status == 'active',
            'extra_config': extra_config,
        }


@receiver(post_save, sender=MeetingReservation)
def create_meeting_record(sender, instance, created, **kwargs):
    if instance.status == 'approved' and not hasattr(instance, 'meeting_record'):
        audio_file_path = ''
        meeting_type = 'regular'
        temp_data_file = os.path.join(settings.MEDIA_ROOT, 'temp_reservation_data', f'{instance.id}.json')
        if os.path.exists(temp_data_file):
            try:
                with open(temp_data_file, 'r', encoding='utf-8') as f:
                    temp_data = json.load(f)
                    audio_file_path = temp_data.get('audio_file_path', '')
                    meeting_type = temp_data.get('meeting_type', 'regular')
            except Exception:
                pass
        from apps.oa.models import MeetingRecord
        meeting_record = MeetingRecord.objects.create(
            title=instance.title,
            meeting_type=meeting_type,
            meeting_date=instance.start_time,
            meeting_end_time=instance.end_time,
            duration=int((instance.end_time - instance.start_time).total_seconds() / 60),
            location=instance.meeting_room.location,
            host=instance.organizer,
            recorder=instance.organizer,
            department=instance.organizer.did if hasattr(instance.organizer, 'did') and instance.organizer.did else None,
            content=instance.description,
            status='scheduled'
        )
        for attendee in instance.attendees.all():
            meeting_record.participants.add(attendee)
        if audio_file_path:
            if meeting_record.attachments:
                meeting_record.attachments += f",{audio_file_path}"
            else:
                meeting_record.attachments = audio_file_path
            meeting_record.save()
        instance.meeting_record = meeting_record
        instance.save()
        if os.path.exists(temp_data_file):
            try:
                os.remove(temp_data_file)
            except Exception:
                pass
