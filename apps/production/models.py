from django.db import models
from django.db.models import Sum
from django.conf import settings
from django.utils import timezone
from apps.department.models import Department
from apps.contract.models import Product


class StatusDisplayMixin:
    """状态显示混入类"""
    STATUS_CHOICES = None
    
    @property
    def status_display(self):
        if self.STATUS_CHOICES:
            return dict(self.STATUS_CHOICES).get(self.status, '未知')
        return '未知'


class RateCalculationMixin:
    """比率计算混入类"""
    
    @staticmethod
    def calculate_rate(numerator, denominator, default=0):
        """计算比率"""
        if denominator and float(denominator) != 0:
            return round((float(numerator) / float(denominator)) * 100, 2)
        return default
    
    @property
    def qualified_rate(self):
        """合格率 - 子类应重写"""
        raise NotImplementedError


class ProductionProcedure(models.Model):
    """基本工序"""
    name = models.CharField(max_length=100, verbose_name='工序名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='工序编码')
    description = models.TextField(blank=True, verbose_name='工序描述')
    standard_time = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='标准工时(小时)')
    cost_per_hour = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='每小时成本')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='所属部门')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='是否启用')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_procedures', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'production_procedure'
        verbose_name = '基本工序'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return f"{self.code} - {self.name}"


class ProcedureSet(models.Model):
    """工序集"""
    name = models.CharField(max_length=100, verbose_name='工序集名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='工序集编码')
    description = models.TextField(blank=True, verbose_name='工序集描述')
    procedures = models.ManyToManyField(ProductionProcedure, through='ProcedureSetItem', verbose_name='包含工序')
    total_time = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='总工时')
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总成本')
    status = models.BooleanField(default=True, verbose_name='是否启用')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_procedure_sets', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'production_procedure_set'
        verbose_name = '工序集'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.code} - {self.name}"


class ProcedureSetItem(models.Model):
    """工序集明细"""
    procedure_set = models.ForeignKey(ProcedureSet, on_delete=models.CASCADE, verbose_name='工序集')
    procedure = models.ForeignKey(ProductionProcedure, on_delete=models.CASCADE, verbose_name='工序')
    sequence = models.IntegerField(verbose_name='执行顺序')
    estimated_time = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='预估工时')
    
    class Meta:
        db_table = 'production_procedure_set_item'
        verbose_name = '工序集明细'
        verbose_name_plural = verbose_name
        ordering = ['sequence']
        unique_together = ['procedure_set', 'procedure']


class ProcessRoute(models.Model):
    """工艺路线"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '执行中'),
        (4, '已完成'),
        (5, '已取消'),
    )
    
    name = models.CharField(max_length=100, verbose_name='工艺路线名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='工艺路线编码')
    description = models.TextField(blank=True, verbose_name='工艺路线描述')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='适用产品')
    procedures = models.ManyToManyField(ProductionProcedure, through='ProcessRouteItem', verbose_name='包含工序')
    total_time = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='总工时(小时)')
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总成本')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本号')
    effective_date = models.DateField(null=True, blank=True, verbose_name='生效日期')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='失效日期')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_process_routes', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'production_process_route'
        verbose_name = '工艺路线'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, '未知')


class ProcessRouteItem(models.Model):
    """工艺路线明细"""
    process_route = models.ForeignKey(ProcessRoute, on_delete=models.CASCADE, verbose_name='工艺路线')
    procedure = models.ForeignKey(ProductionProcedure, on_delete=models.CASCADE, verbose_name='工序')
    sequence = models.IntegerField(verbose_name='执行顺序')
    estimated_time = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='预估工时(小时)')
    workstation = models.CharField(max_length=100, blank=True, verbose_name='工位')
    work_instruction = models.TextField(blank=True, verbose_name='作业指导')
    quality_check_points = models.TextField(blank=True, verbose_name='质量检查点')
    cycle_time = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='节拍时间(秒)')
    
    class Meta:
        db_table = 'production_process_route_item'
        verbose_name = '工艺路线明细'
        verbose_name_plural = verbose_name
        ordering = ['sequence']
        unique_together = ['process_route', 'procedure']
    
    def __str__(self):
        return f"{self.process_route.code} - {self.procedure.name} (顺序:{self.sequence})"


class BOM(models.Model):
    """BOM物料清单"""
    name = models.CharField(max_length=100, verbose_name='BOM名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='BOM编码')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, verbose_name='关联产品')
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本号')
    description = models.TextField(blank=True, verbose_name='BOM描述')
    status = models.BooleanField(default=True, verbose_name='是否启用')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_boms', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'production_bom'
        verbose_name = 'BOM管理'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.code} - {self.name}"


class BOMItem(models.Model):
    """BOM物料明细"""
    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name='items', verbose_name='所属BOM')
    material_name = models.CharField(max_length=100, verbose_name='物料名称')
    material_code = models.CharField(max_length=50, verbose_name='物料编码')
    specification = models.CharField(max_length=100, blank=True, verbose_name='规格型号')
    unit = models.CharField(max_length=20, verbose_name='单位')
    quantity = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='用量')
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='单价')
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总价')
    supplier = models.CharField(max_length=100, blank=True, verbose_name='供应商')
    remark = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'production_bom_item'
        verbose_name = 'BOM物料明细'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.bom.code} - {self.material_name}"


class Equipment(models.Model, StatusDisplayMixin):
    """设备管理"""
    STATUS_CHOICES = (
        (1, '正常'),
        (2, '维修中'),
        (3, '停用'),
        (4, '报废'),
    )
    
    name = models.CharField(max_length=100, verbose_name='设备名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='设备编号')
    model = models.CharField(max_length=100, blank=True, verbose_name='设备型号')
    manufacturer = models.CharField(max_length=100, blank=True, verbose_name='制造商')
    purchase_date = models.DateField(null=True, blank=True, verbose_name='采购日期')
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='采购成本')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='所属部门')
    location = models.CharField(max_length=100, blank=True, verbose_name='设备位置')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='设备状态')
    responsible_person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='负责人')
    maintenance_cycle = models.IntegerField(default=30, verbose_name='维护周期(天)')
    last_maintenance = models.DateField(null=True, blank=True, verbose_name='上次维护日期')
    next_maintenance = models.DateField(null=True, blank=True, verbose_name='下次维护日期')
    description = models.TextField(blank=True, verbose_name='设备描述')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_equipment', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'production_equipment'
        verbose_name = '设备管理'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.code} - {self.name}"


class ProductionPlan(models.Model, StatusDisplayMixin):
    """生产计划"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '执行中'),
        (4, '已完成'),
        (5, '已取消'),
        (6, '已挂起'),
    )
    
    name = models.CharField(max_length=100, verbose_name='计划名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='计划编号')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, verbose_name='生产产品')
    bom = models.ForeignKey(BOM, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='使用BOM')
    procedure_set = models.ForeignKey(ProcedureSet, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='工序集')
    process_route = models.ForeignKey(ProcessRoute, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='工艺路线')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='计划数量')
    unit = models.CharField(max_length=20, verbose_name='单位')
    plan_start_date = models.DateField(verbose_name='计划开始日期')
    plan_end_date = models.DateField(verbose_name='计划结束日期')
    actual_start_date = models.DateField(null=True, blank=True, verbose_name='实际开始日期')
    actual_end_date = models.DateField(null=True, blank=True, verbose_name='实际结束日期')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='计划状态')
    priority = models.IntegerField(default=2, verbose_name='优先级')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='生产部门')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='负责人')
    description = models.TextField(blank=True, verbose_name='计划描述')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_plans', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    auto_complete = models.BooleanField(default=False, verbose_name='是否自动完工')
    complete_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=100.00, verbose_name='自动完工阈值(%)')

    class Meta:
        db_table = 'production_plan'
        verbose_name = '生产计划'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def completion_rate(self):
        """计划完成率"""
        total_completed = self.tasks.aggregate(total=Sum('completed_quantity'))['total'] or 0
        if self.quantity > 0:
            return round((total_completed / self.quantity) * 100, 2)
        return 0
    
    def check_auto_complete(self):
        """检查是否满足自动完工条件"""
        if self.auto_complete and self.status == 3:
            if self.completion_rate >= self.complete_threshold:
                self.status = 4
                self.actual_end_date = timezone.now().date()
                self.save()
                return True
        return False


class ProductionTask(models.Model, StatusDisplayMixin, RateCalculationMixin):
    """生产任务"""
    STATUS_CHOICES = (
        (1, '待开始'),
        (2, '进行中'),
        (3, '已完成'),
        (4, '已暂停'),
        (5, '已取消'),
        (6, '已挂起'),
    )
    
    plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE, related_name='tasks', verbose_name='所属计划')
    name = models.CharField(max_length=100, verbose_name='任务名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='任务编号')
    procedure = models.ForeignKey(ProductionProcedure, on_delete=models.CASCADE, verbose_name='执行工序')
    equipment = models.ForeignKey(Equipment, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='使用设备')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='任务数量')
    completed_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='完成数量')
    qualified_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='合格数量')
    defective_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='不合格数量')
    plan_start_time = models.DateTimeField(verbose_name='计划开始时间')
    plan_end_time = models.DateTimeField(verbose_name='计划结束时间')
    actual_start_time = models.DateTimeField(null=True, blank=True, verbose_name='实际开始时间')
    actual_end_time = models.DateTimeField(null=True, blank=True, verbose_name='实际结束时间')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='任务状态')
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='执行人')
    description = models.TextField(blank=True, verbose_name='任务描述')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_production_tasks', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    suspended_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='suspended_tasks', verbose_name='挂起人')
    suspended_time = models.DateTimeField(null=True, blank=True, verbose_name='挂起时间')
    suspend_reason = models.TextField(blank=True, verbose_name='挂起原因')

    class Meta:
        db_table = 'production_task'
        verbose_name = '生产任务'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def completion_rate(self):
        """完成率"""
        return self.calculate_rate(self.completed_quantity, self.quantity)
    
    @property
    def qualified_rate(self):
        """合格率"""
        return self.calculate_rate(self.qualified_quantity, self.completed_quantity)
    
    def update_task_status(self):
        """更新任务状态，同时检查并更新关联的生产计划状态"""
        if self.completed_quantity >= self.quantity:
            self.status = 3
            if not self.actual_end_time:
                self.actual_end_time = timezone.now()
        
        self.save()
        
        self.plan.check_auto_complete()


class QualityCheck(models.Model):
    """质量检查"""
    STATUS_CHOICES = (
        (1, '合格'),
        (2, '不合格'),
        (3, '待检'),
    )
    
    task = models.ForeignKey(ProductionTask, on_delete=models.CASCADE, related_name='quality_checks', verbose_name='关联任务')
    check_time = models.DateTimeField(default=timezone.now, verbose_name='检查时间')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_quality_checks', verbose_name='检查员')
    check_quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='检查数量')
    qualified_quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='合格数量')
    defective_quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='不合格数量')
    result = models.IntegerField(choices=STATUS_CHOICES, default=3, verbose_name='检查结果')
    defect_description = models.TextField(blank=True, verbose_name='缺陷描述')
    improvement_suggestion = models.TextField(blank=True, verbose_name='改进建议')
    
    class Meta:
        db_table = 'production_quality_check'
        verbose_name = '质量检查'
        verbose_name_plural = verbose_name
        ordering = ['-check_time']

    def __str__(self):
        return f"{self.task.name} - {self.check_time.strftime('%Y-%m-%d %H:%M')}"

    @property
    def result_display(self):
        return dict(self.STATUS_CHOICES).get(self.result, '未知')

    @property
    def qualified_rate(self):
        """合格率"""
        return RateCalculationMixin.calculate_rate(self.qualified_quantity, self.check_quantity)


class DataCollection(models.Model):
    """数据采集"""
    task = models.ForeignKey(ProductionTask, on_delete=models.CASCADE, related_name='data_collections', verbose_name='关联任务')
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, verbose_name='采集设备')
    parameter_name = models.CharField(max_length=50, verbose_name='参数名称')
    parameter_value = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='参数值')
    unit = models.CharField(max_length=20, verbose_name='单位')
    standard_min = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, verbose_name='标准下限')
    standard_max = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, verbose_name='标准上限')
    is_normal = models.BooleanField(default=True, verbose_name='是否正常')
    collect_time = models.DateTimeField(default=timezone.now, verbose_name='采集时间')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_data_collections', verbose_name='采集人')
    
    class Meta:
        db_table = 'production_data_collection'
        verbose_name = '数据采集'
        verbose_name_plural = verbose_name
        ordering = ['-collect_time']

    def __str__(self):
        return f"{self.equipment.name} - {self.parameter_name}: {self.parameter_value}"


class SOP(models.Model):
    """标准作业程序"""
    name = models.CharField(max_length=100, verbose_name='SOP名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='SOP编号')
    procedure = models.ForeignKey(ProductionProcedure, on_delete=models.CASCADE, verbose_name='关联工序')
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本号')
    content = models.TextField(verbose_name='SOP内容')
    safety_requirements = models.TextField(blank=True, verbose_name='安全要求')
    quality_standards = models.TextField(blank=True, verbose_name='质量标准')
    tools_required = models.TextField(blank=True, verbose_name='所需工具')
    file_path = models.CharField(max_length=500, blank=True, verbose_name='附件路径')
    status = models.BooleanField(default=True, verbose_name='是否启用')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_sops', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'production_sop'
        verbose_name = 'SOP管理'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.code} - {self.name}"


class DataSource(models.Model):
    """数据源配置"""
    SOURCE_TYPES = (
        ('api', 'API接口'),
        ('iot', 'IoT设备'),
        ('database', '数据库'),
        ('file', '文件导入'),
        ('mqtt', 'MQTT消息'),
        ('modbus', 'Modbus协议'),
        ('opcua', 'OPC UA'),
        ('custom', '自定义协议'),
    )
    
    AUTH_TYPES = (
        ('none', '无认证'),
        ('basic', 'Basic认证'),
        ('bearer', 'Bearer Token'),
        ('api_key', 'API Key'),
        ('oauth2', 'OAuth2'),
        ('custom', '自定义认证'),
    )
    
    name = models.CharField(max_length=100, verbose_name='数据源名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='数据源编码')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES, verbose_name='数据源类型')
    description = models.TextField(blank=True, verbose_name='描述')
    endpoint_url = models.URLField(blank=True, verbose_name='接口地址')
    host = models.CharField(max_length=255, blank=True, verbose_name='主机地址')
    port = models.IntegerField(null=True, blank=True, verbose_name='端口')
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPES, default='none', verbose_name='认证类型')
    username = models.CharField(max_length=100, blank=True, verbose_name='用户名')
    password = models.CharField(max_length=255, blank=True, verbose_name='密码')
    api_key = models.CharField(max_length=255, blank=True, verbose_name='API密钥')
    token = models.TextField(blank=True, verbose_name='访问令牌')
    request_method = models.CharField(max_length=10, default='GET', verbose_name='请求方法')
    request_headers = models.JSONField(default=dict, blank=True, verbose_name='请求头')
    request_params = models.JSONField(default=dict, blank=True, verbose_name='请求参数')
    request_body = models.TextField(blank=True, verbose_name='请求体')
    timeout = models.IntegerField(default=30, verbose_name='超时时间(秒)')
    retry_count = models.IntegerField(default=3, verbose_name='重试次数')
    collection_interval = models.IntegerField(default=60, verbose_name='采集间隔(秒)')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    last_collection_time = models.DateTimeField(null=True, blank=True, verbose_name='最后采集时间')
    last_success_time = models.DateTimeField(null=True, blank=True, verbose_name='最后成功时间')
    error_count = models.IntegerField(default=0, verbose_name='错误次数')
    last_error = models.TextField(blank=True, verbose_name='最后错误信息')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_data_sources', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'production_data_source'
        verbose_name = '数据源'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"


class DataMapping(models.Model):
    """数据映射配置"""
    FIELD_TYPES = (
        ('string', '字符串'),
        ('integer', '整数'),
        ('float', '浮点数'),
        ('boolean', '布尔值'),
        ('datetime', '日期时间'),
        ('json', 'JSON对象'),
        ('array', '数组'),
    )
    
    TRANSFORM_TYPES = (
        ('none', '无转换'),
        ('multiply', '乘法运算'),
        ('divide', '除法运算'),
        ('add', '加法运算'),
        ('subtract', '减法运算'),
        ('round', '四舍五入'),
        ('format', '格式化'),
        ('regex', '正则提取'),
        ('custom', '自定义函数'),
    )
    
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='mappings', verbose_name='数据源')
    name = models.CharField(max_length=100, verbose_name='字段名称')
    source_path = models.CharField(max_length=500, verbose_name='源数据路径')
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, verbose_name='字段类型')
    transform_type = models.CharField(max_length=20, choices=TRANSFORM_TYPES, default='none', verbose_name='转换类型')
    transform_params = models.JSONField(default=dict, blank=True, verbose_name='转换参数')
    is_required = models.BooleanField(default=False, verbose_name='是否必填')
    min_value = models.FloatField(null=True, blank=True, verbose_name='最小值')
    max_value = models.FloatField(null=True, blank=True, verbose_name='最大值')
    regex_pattern = models.CharField(max_length=500, blank=True, verbose_name='正则表达式')
    default_value = models.TextField(blank=True, verbose_name='默认值')
    target_table = models.CharField(max_length=100, blank=True, verbose_name='目标表')
    target_field = models.CharField(max_length=100, blank=True, verbose_name='目标字段')
    sort = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'production_data_mapping'
        verbose_name = '数据映射'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']
    
    def __str__(self):
        return f"{self.data_source.name} - {self.name}"


class DataCollectionRecord(models.Model):
    """数据采集记录"""
    STATUS_CHOICES = (
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('success', '成功'),
        ('failed', '失败'),
        ('partial', '部分成功'),
    )
    
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='collections', verbose_name='数据源')
    collection_time = models.DateTimeField(default=timezone.now, verbose_name='采集时间')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    raw_data = models.JSONField(default=dict, verbose_name='原始数据')
    raw_response = models.TextField(blank=True, verbose_name='原始响应')
    processed_data = models.JSONField(default=dict, blank=True, verbose_name='处理后数据')
    record_count = models.IntegerField(default=0, verbose_name='记录数量')
    success_count = models.IntegerField(default=0, verbose_name='成功数量')
    error_count = models.IntegerField(default=0, verbose_name='错误数量')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    error_details = models.JSONField(default=list, blank=True, verbose_name='错误详情')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    duration = models.FloatField(null=True, blank=True, verbose_name='处理时长(秒)')
    
    class Meta:
        db_table = 'production_data_collection_record'
        verbose_name = '数据采集记录'
        verbose_name_plural = verbose_name
        ordering = ['-collection_time']
    
    def __str__(self):
        return f"{self.data_source.name} - {self.collection_time.strftime('%Y-%m-%d %H:%M:%S')}"


class ProductionDataPoint(models.Model):
    """生产数据点"""
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='data_points', verbose_name='设备')
    data_source = models.ForeignKey(DataSource, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='数据源')
    collection = models.ForeignKey(DataCollection, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='采集记录')
    metric_name = models.CharField(max_length=100, verbose_name='指标名称')
    metric_value = models.TextField(verbose_name='指标值')
    metric_unit = models.CharField(max_length=50, blank=True, verbose_name='单位')
    timestamp = models.DateTimeField(verbose_name='数据时间戳')
    collection_time = models.DateTimeField(default=timezone.now, verbose_name='采集时间')
    quality = models.CharField(max_length=20, default='good', verbose_name='数据质量')
    confidence = models.FloatField(default=1.0, verbose_name='置信度')
    task = models.ForeignKey(ProductionTask, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='生产任务')
    procedure = models.ForeignKey(ProductionProcedure, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='工序')
    tags = models.JSONField(default=dict, blank=True, verbose_name='标签')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='元数据')
    
    class Meta:
        db_table = 'production_data_point'
        verbose_name = '生产数据点'
        verbose_name_plural = verbose_name
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['equipment', 'timestamp']),
            models.Index(fields=['metric_name', 'timestamp']),
            models.Index(fields=['collection_time']),
        ]
    
    def __str__(self):
        return f"{self.equipment.name} - {self.metric_name}: {self.metric_value}"


class DataCollectionTask(models.Model):
    """数据采集任务"""
    TASK_TYPES = (
        ('scheduled', '定时任务'),
        ('manual', '手动触发'),
        ('event', '事件触发'),
        ('continuous', '连续采集'),
    )
    
    STATUS_CHOICES = (
        ('pending', '待执行'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('failed', '执行失败'),
        ('cancelled', '已取消'),
    )
    
    name = models.CharField(max_length=100, verbose_name='任务名称')
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, verbose_name='任务类型')
    data_sources = models.ManyToManyField(DataSource, verbose_name='数据源')
    cron_expression = models.CharField(max_length=100, blank=True, verbose_name='Cron表达式')
    interval_seconds = models.IntegerField(null=True, blank=True, verbose_name='间隔秒数')
    max_retries = models.IntegerField(default=3, verbose_name='最大重试次数')
    timeout_seconds = models.IntegerField(default=300, verbose_name='超时时间(秒)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    last_run_time = models.DateTimeField(null=True, blank=True, verbose_name='最后执行时间')
    next_run_time = models.DateTimeField(null=True, blank=True, verbose_name='下次执行时间')
    total_runs = models.IntegerField(default=0, verbose_name='总执行次数')
    success_runs = models.IntegerField(default=0, verbose_name='成功次数')
    failed_runs = models.IntegerField(default=0, verbose_name='失败次数')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_data_collection_tasks', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'production_data_collection_task'
        verbose_name = '数据采集任务'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.name} ({self.get_task_type_display()})"


class ProductionOrderChange(models.Model):
    """生产订单变更单"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '已执行'),
        (4, '已拒绝'),
    )
    
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE, related_name='changes', verbose_name='生产计划')
    change_type = models.CharField(max_length=50, verbose_name='变更类型')
    change_reason = models.TextField(verbose_name='变更原因')
    old_value = models.JSONField(default=dict, verbose_name='变更前值')
    new_value = models.JSONField(default=dict, verbose_name='变更后值')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_order_changes', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='approved_order_changes', verbose_name='审核人')
    approved_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    executed_time = models.DateTimeField(null=True, blank=True, verbose_name='执行时间')
    
    class Meta:
        db_table = 'production_order_change'
        verbose_name = '生产订单变更单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.production_plan.code} - {self.change_type}"


class ProductionLineDayPlan(models.Model):
    """生产线日计划"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '执行中'),
        (4, '已完成'),
        (5, '已取消'),
    )
    
    name = models.CharField(max_length=100, verbose_name='日计划名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='日计划编号')
    production_line = models.CharField(max_length=50, verbose_name='生产线')
    plan_date = models.DateField(verbose_name='计划日期')
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE, related_name='day_plans', verbose_name='关联生产计划')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='计划数量')
    completed_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='完成数量')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='managed_day_plans', verbose_name='负责人')
    description = models.TextField(blank=True, verbose_name='计划描述')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_day_plans', verbose_name='创建人')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'production_line_day_plan'
        verbose_name = '生产线日计划'
        verbose_name_plural = verbose_name
        ordering = ['-plan_date', '-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.plan_date}"


class MaterialRequest(models.Model):
    """领料申请单"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '已领料'),
        (4, '已拒绝'),
        (5, '已取消'),
    )
    
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE, related_name='material_requests', verbose_name='生产计划')
    production_task = models.ForeignKey(ProductionTask, on_delete=models.SET_NULL, null=True, blank=True, related_name='material_requests', verbose_name='生产任务')
    code = models.CharField(max_length=50, unique=True, verbose_name='申请单号')
    request_date = models.DateField(default=timezone.now, verbose_name='申请日期')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_material_requests', verbose_name='申请人')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='approved_material_requests', verbose_name='审核人')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总金额')
    description = models.TextField(blank=True, verbose_name='申请说明')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'production_material_request'
        verbose_name = '领料申请单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.request_date}"


class MaterialRequestItem(models.Model):
    """领料申请明细"""
    material_request = models.ForeignKey(MaterialRequest, on_delete=models.CASCADE, related_name='items', verbose_name='领料申请单')
    bom_item = models.ForeignKey(BOMItem, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='BOM物料明细')
    material_name = models.CharField(max_length=100, verbose_name='物料名称')
    material_code = models.CharField(max_length=50, verbose_name='物料编码')
    specification = models.CharField(max_length=100, blank=True, verbose_name='规格型号')
    unit = models.CharField(max_length=20, verbose_name='单位')
    request_quantity = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='申请数量')
    issued_quantity = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='已发数量')
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='单价')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='金额')
    remark = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'production_material_request_item'
        verbose_name = '领料申请明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.material_request.code} - {self.material_name}"


class MaterialIssue(models.Model):
    """材料出库单（生产领料）"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '已出库'),
        (4, '已取消'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name='出库单号')
    material_request = models.ForeignKey(MaterialRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='material_issues', verbose_name='领料申请单')
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE, related_name='material_issues', verbose_name='生产计划')
    issue_date = models.DateField(default=timezone.now, verbose_name='出库日期')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_material_issues', verbose_name='出库人')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='approved_material_issues', verbose_name='审核人')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总金额')
    description = models.TextField(blank=True, verbose_name='出库说明')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'production_material_issue'
        verbose_name = '材料出库单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.issue_date}"


class MaterialIssueItem(models.Model):
    """材料出库明细"""
    material_issue = models.ForeignKey(MaterialIssue, on_delete=models.CASCADE, related_name='items', verbose_name='材料出库单')
    material_request_item = models.ForeignKey(MaterialRequestItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='material_issue_items', verbose_name='领料申请明细')
    material_name = models.CharField(max_length=100, verbose_name='物料名称')
    material_code = models.CharField(max_length=50, verbose_name='物料编码')
    specification = models.CharField(max_length=100, blank=True, verbose_name='规格型号')
    unit = models.CharField(max_length=20, verbose_name='单位')
    issue_quantity = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='出库数量')
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='单价')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='金额')
    remark = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'production_material_issue_item'
        verbose_name = '材料出库明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.material_issue.code} - {self.material_name}"


class MaterialReturn(models.Model):
    """材料入库单（退料）"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '已入库'),
        (4, '已取消'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name='退料单号')
    material_issue = models.ForeignKey(MaterialIssue, on_delete=models.SET_NULL, null=True, blank=True, related_name='material_returns', verbose_name='材料出库单')
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE, related_name='material_returns', verbose_name='生产计划')
    return_date = models.DateField(default=timezone.now, verbose_name='退料日期')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_material_returns', verbose_name='退料人')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='approved_material_returns', verbose_name='审核人')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总金额')
    return_reason = models.TextField(verbose_name='退料原因')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'production_material_return'
        verbose_name = '材料退料单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.return_date}"


class MaterialReturnItem(models.Model):
    """材料退料明细"""
    material_return = models.ForeignKey(MaterialReturn, on_delete=models.CASCADE, related_name='items', verbose_name='材料退库单')
    material_issue_item = models.ForeignKey(MaterialIssueItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='material_return_items', verbose_name='材料出库明细')
    material_name = models.CharField(max_length=100, verbose_name='物料名称')
    material_code = models.CharField(max_length=50, verbose_name='物料编码')
    specification = models.CharField(max_length=100, blank=True, verbose_name='规格型号')
    unit = models.CharField(max_length=20, verbose_name='单位')
    return_quantity = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='退料数量')
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='单价')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='金额')
    remark = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'production_material_return_item'
        verbose_name = '材料退料明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.material_return.code} - {self.material_name}"


class WorkCompletionReport(models.Model):
    """完工申报"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '已红冲'),
        (4, '已取消'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name='完工申报单号')
    production_task = models.ForeignKey(ProductionTask, on_delete=models.CASCADE, related_name='completion_reports', verbose_name='生产任务')
    report_date = models.DateField(default=timezone.now, verbose_name='申报日期')
    reported_quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='申报数量')
    qualified_quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='合格数量')
    defective_quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='不合格数量')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_completion_reports', verbose_name='申报人')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='approved_completion_reports', verbose_name='审核人')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    work_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='实际工时')
    resource_consumption = models.JSONField(default=dict, blank=True, verbose_name='资源消耗')
    remarks = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    approved_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    
    class Meta:
        db_table = 'production_work_completion_report'
        verbose_name = '完工申报'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.production_task.name}"


class WorkCompletionRedFlush(models.Model):
    """完工红冲"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '已执行'),
        (4, '已取消'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name='红冲单号')
    completion_report = models.ForeignKey(WorkCompletionReport, on_delete=models.CASCADE, related_name='red_flushes', verbose_name='完工申报单')
    red_flush_date = models.DateField(default=timezone.now, verbose_name='红冲日期')
    red_flush_reason = models.TextField(verbose_name='红冲原因')
    red_flush_quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='红冲数量')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_red_flushes', verbose_name='申请人')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='approved_red_flushes', verbose_name='审核人')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    approved_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    executed_time = models.DateTimeField(null=True, blank=True, verbose_name='执行时间')
    
    class Meta:
        db_table = 'production_work_completion_red_flush'
        verbose_name = '完工红冲'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.completion_report.code}"


class ProductReceipt(models.Model):
    """成品入库"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '已入库'),
        (4, '已取消'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name='成品入库单号')
    completion_report = models.ForeignKey(WorkCompletionReport, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_receipts', verbose_name='完工申报单')
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE, related_name='product_receipts', verbose_name='生产计划')
    receipt_date = models.DateField(default=timezone.now, verbose_name='入库日期')
    receipt_quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='入库数量')
    storage_location = models.CharField(max_length=100, verbose_name='存储位置')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_product_receipts', verbose_name='入库人')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='approved_product_receipts', verbose_name='审核人')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    remarks = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'production_product_receipt'
        verbose_name = '成品入库单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.receipt_date}"


class OrderMaterialConfirmation(models.Model):
    """订单材料确认单"""
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE, related_name='material_confirmations', verbose_name='生产计划')
    material_issue = models.ForeignKey(MaterialIssue, on_delete=models.CASCADE, related_name='confirmations', verbose_name='材料出库单')
    confirmed_quantity = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='确认数量')
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='确认人')
    confirm_time = models.DateTimeField(default=timezone.now, verbose_name='确认时间')
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'production_order_material_confirmation'
        verbose_name = '订单材料确认单'
        verbose_name_plural = verbose_name
        unique_together = ['production_plan', 'material_issue']
    
    def __str__(self):
        return f"{self.production_plan.code} - {self.material_issue.code}"


class ResourceConsumption(models.Model):
    """资源消耗记录"""
    production_task = models.ForeignKey(ProductionTask, on_delete=models.CASCADE, related_name='resource_consumptions', verbose_name='生产任务')
    resource_type = models.CharField(max_length=50, verbose_name='资源类型')
    resource_name = models.CharField(max_length=100, verbose_name='资源名称')
    consumed_quantity = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='消耗数量')
    unit = models.CharField(max_length=20, verbose_name='单位')
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='成本')
    consumption_time = models.DateTimeField(default=timezone.now, verbose_name='消耗时间')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_resource_consumptions', verbose_name='记录人')
    
    class Meta:
        db_table = 'production_resource_consumption'
        verbose_name = '资源消耗记录'
        verbose_name_plural = verbose_name
        ordering = ['-consumption_time']
    
    def __str__(self):
        return f"{self.production_task.name} - {self.resource_name}"
