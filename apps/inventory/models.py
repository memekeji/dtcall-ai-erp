from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.user.models import Admin
from apps.production.models import BOM, BOMItem


class Warehouse(models.Model):
    """仓库信息"""
    STATUS_CHOICES = (
        (1, '启用'),
        (0, '禁用'),
    )
    
    TYPE_CHOICES = (
        ('main', '主仓库'),
        ('branch', '分仓库'),
        ('virtual', '虚拟仓库'),
        ('production', '生产仓库'),
        ('quality', '质检仓库'),
    )
    
    name = models.CharField(max_length=100, verbose_name='仓库名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='仓库编码')
    warehouse_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='main', verbose_name='仓库类型')
    address = models.CharField(max_length=500, blank=True, verbose_name='仓库地址')
    manager = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='仓库管理员')
    phone = models.CharField(max_length=50, blank=True, verbose_name='联系电话')
    email = models.EmailField(blank=True, verbose_name='电子邮箱')
    capacity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='仓库容量')
    used_capacity = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已用容量')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    is_default = models.BooleanField(default=False, verbose_name='是否默认仓库')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'inventory_warehouse'
        verbose_name = '仓库管理'
        verbose_name_plural = verbose_name
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def usage_rate(self):
        if self.capacity > 0:
            return (self.used_capacity / self.capacity) * 100
        return 0


class WarehouseLocation(models.Model):
    """库位层级结构"""
    STATUS_CHOICES = (
        (1, '启用'),
        (0, '禁用'),
    )
    
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='locations', verbose_name='所属仓库')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name='上级库位')
    name = models.CharField(max_length=100, verbose_name='库位名称')
    code = models.CharField(max_length=50, verbose_name='库位编码')
    location_type = models.CharField(max_length=20, choices=[
        ('area', '区域'),
        ('shelf', '货架'),
        ('layer', '层'),
        ('bin', '货位'),
    ], default='area', verbose_name='库位类型')
    capacity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='容量')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    sort = models.IntegerField(default=0, verbose_name='排序')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'inventory_warehouse_location'
        verbose_name = '库位管理'
        verbose_name_plural = verbose_name
        unique_together = ['warehouse', 'code']
        ordering = ['warehouse', 'code']
    
    def __str__(self):
        return f"{self.warehouse.name} - {self.code} {self.name}"
    
    @property
    def full_path(self):
        paths = []
        current = self
        while current:
            paths.insert(0, current.name)
            current = current.parent
        return ' > '.join(paths)


class InventoryCategory(models.Model):
    """库存类别体系"""
    STATUS_CHOICES = (
        (1, '启用'),
        (0, '禁用'),
    )
    
    TYPE_CHOICES = (
        ('material', '原材料'),
        ('product', '产成品'),
        ('semi', '半成品'),
        ('pack', '包装物'),
        ('consumable', '消耗品'),
        ('other', '其他'),
    )
    
    name = models.CharField(max_length=100, verbose_name='类别名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='类别编码')
    category_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='material', verbose_name='类别类型')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name='上级类别')
    description = models.TextField(blank=True, verbose_name='类别描述')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    sort = models.IntegerField(default=0, verbose_name='排序')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'inventory_category'
        verbose_name = '库存类别'
        verbose_name_plural = verbose_name
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class InventoryItem(models.Model):
    """库存物料"""
    STATUS_CHOICES = (
        (1, '启用'),
        (0, '禁用'),
    )
    
    name = models.CharField(max_length=200, verbose_name='物料名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='物料编码')
    category = models.ForeignKey(InventoryCategory, on_delete=models.SET_NULL, null=True, verbose_name='物料类别')
    specification = models.CharField(max_length=200, blank=True, verbose_name='规格型号')
    unit = models.CharField(max_length=20, verbose_name='计量单位')
    weight = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='重量')
    length = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='长度')
    width = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='宽度')
    height = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='高度')
    volume = models.DecimalField(max_digits=15, decimal_places=6, default=0, verbose_name='体积')
    barcode = models.CharField(max_length=100, blank=True, verbose_name='条形码')
    qr_code = models.CharField(max_length=100, blank=True, verbose_name='二维码')
    standard_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='标准成本')
    average_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='平均成本')
    latest_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='最近成本')
    retail_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='零售价格')
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='批发价格')
    min_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='最低库存')
    max_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='最高库存')
    reorder_point = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='再订货点')
    safety_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='安全库存')
    shelf_life = models.IntegerField(default=0, verbose_name='保质期(天)')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    image = models.CharField(max_length=500, blank=True, verbose_name='物料图片')
    description = models.TextField(blank=True, verbose_name='物料描述')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'inventory_item'
        verbose_name = '库存物料'
        verbose_name_plural = verbose_name
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Inventory(models.Model):
    """库存记录"""
    STATUS_CHOICES = (
        ('normal', '正常'),
        ('locked', '锁定'),
        ('quarantine', '隔离'),
    )
    
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='inventories', verbose_name='物料')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='inventories', verbose_name='仓库')
    location = models.ForeignKey(WarehouseLocation, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='库位')
    batch_number = models.CharField(max_length=50, blank=True, verbose_name='批次号')
    quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='库存数量')
    locked_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='锁定数量')
    available_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='可用数量')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='单位成本')
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='总成本')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='normal', verbose_name='库存状态')
    production_date = models.DateField(null=True, blank=True, verbose_name='生产日期')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='过期日期')
    last_movement_date = models.DateTimeField(null=True, blank=True, verbose_name='最后变动日期')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'inventory_inventory'
        verbose_name = '库存记录'
        verbose_name_plural = verbose_name
        unique_together = ['item', 'warehouse', 'location', 'batch_number']
        indexes = [
            models.Index(fields=['item', 'warehouse']),
            models.Index(fields=['batch_number']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.item.code} - {self.warehouse.code} - {self.quantity}"
    
    def save(self, *args, **kwargs):
        self.available_quantity = self.quantity - self.locked_quantity
        self.total_cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)


class StockTransaction(models.Model):
    """库存交易/变动记录"""
    TRANSACTION_TYPES = (
        ('stock_in', '入库'),
        ('stock_out', '出库'),
        ('transfer', '调拨'),
        ('adjustment', '调整'),
        ('check', '盘点'),
        ('lock', '锁定'),
        ('unlock', '解锁'),
        ('return', '退货'),
        ('scrap', '报废'),
    )
    
    TRANSACTION_TYPE_CHOICES = [
        ('stock_in', '入库'),
        ('stock_out', '出库'),
        ('transfer', '调拨'),
        ('adjustment', '调整'),
        ('check', '盘点'),
        ('lock', '锁定'),
        ('unlock', '解锁'),
        ('return', '退货'),
        ('scrap', '报废'),
    ]
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, verbose_name='交易类型')
    transaction_code = models.CharField(max_length=50, verbose_name='交易编号')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='transactions', verbose_name='物料')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='transactions', verbose_name='仓库')
    location = models.ForeignKey(WarehouseLocation, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='库位')
    batch_number = models.CharField(max_length=50, blank=True, verbose_name='批次号')
    quantity = models.DecimalField(max_digits=12, decimal_places=4, verbose_name='交易数量')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='单位成本')
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='总成本')
    before_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='变动前数量')
    after_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='变动后数量')
    reference_type = models.CharField(max_length=50, blank=True, verbose_name='关联单据类型')
    reference_id = models.BigIntegerField(default=0, verbose_name='关联单据ID')
    reference_code = models.CharField(max_length=50, blank=True, verbose_name='关联单据编号')
    operator = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, verbose_name='操作人')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        db_table = 'inventory_stock_transaction'
        verbose_name = '库存交易记录'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
        indexes = [
            models.Index(fields=['transaction_code']),
            models.Index(fields=['item', 'create_time']),
            models.Index(fields=['transaction_type', 'create_time']),
        ]
    
    def __str__(self):
        return f"{self.transaction_code} - {self.item.code} - {self.quantity}"


class StockIn(models.Model):
    """入库单"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '已入库'),
        (4, '已取消'),
    )
    
    IN_TYPE_CHOICES = (
        ('purchase', '采购入库'),
        ('production', '生产入库'),
        ('return', '退货入库'),
        ('transfer', '调拨入库'),
        ('other', '其他入库'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name='入库单号')
    stock_in_type = models.CharField(max_length=20, choices=IN_TYPE_CHOICES, verbose_name='入库类型')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name='入库仓库')
    supplier = models.ForeignKey('contract.Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='供应商')
    purchase_order = models.ForeignKey('PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='采购订单')
    production_plan = models.ForeignKey('production.ProductionPlan', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='生产计划')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='总金额')
    total_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总数量')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    checker = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_stockins', verbose_name='审核人')
    check_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    stocker = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, related_name='stocked_stockins', verbose_name='入库人')
    stock_time = models.DateTimeField(null=True, blank=True, verbose_name='入库时间')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'inventory_stock_in'
        verbose_name = '入库单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.get_stock_in_type_display()}"


class StockInItem(models.Model):
    """入库单明细"""
    stock_in = models.ForeignKey(StockIn, on_delete=models.CASCADE, related_name='items', verbose_name='入库单')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, verbose_name='物料')
    location = models.ForeignKey(WarehouseLocation, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='库位')
    batch_number = models.CharField(max_length=50, blank=True, verbose_name='批次号')
    quantity = models.DecimalField(max_digits=12, decimal_places=4, verbose_name='入库数量')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='单位成本')
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='金额')
    production_date = models.DateField(null=True, blank=True, verbose_name='生产日期')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='过期日期')
    remark = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'inventory_stock_in_item'
        verbose_name = '入库单明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.stock_in.code} - {self.item.code} - {self.quantity}"


class StockOut(models.Model):
    """出库单"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '已出库'),
        (4, '已取消'),
    )
    
    OUT_TYPE_CHOICES = (
        ('sale', '销售出库'),
        ('production', '生产领料'),
        ('transfer', '调拨出库'),
        ('scrap', '报废出库'),
        ('other', '其他出库'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name='出库单号')
    stock_out_type = models.CharField(max_length=20, choices=OUT_TYPE_CHOICES, verbose_name='出库类型')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name='出库仓库')
    customer = models.ForeignKey('customer.Customer', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='客户')
    sales_order = models.ForeignKey('SalesOrder', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='销售订单')
    production_task = models.ForeignKey('production.ProductionTask', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='生产任务')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='总金额')
    total_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总数量')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    checker = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_stockouts', verbose_name='审核人')
    check_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    stocker = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, related_name='stocked_stockouts', verbose_name='出库人')
    stock_time = models.DateTimeField(null=True, blank=True, verbose_name='出库时间')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'inventory_stock_out'
        verbose_name = '出库单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.get_stock_out_type_display()}"


class StockOutItem(models.Model):
    """出库单明细"""
    stock_out = models.ForeignKey(StockOut, on_delete=models.CASCADE, related_name='items', verbose_name='出库单')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, verbose_name='物料')
    location = models.ForeignKey(WarehouseLocation, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='库位')
    batch_number = models.CharField(max_length=50, blank=True, verbose_name='批次号')
    quantity = models.DecimalField(max_digits=12, decimal_places=4, verbose_name='出库数量')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='单位成本')
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='金额')
    remark = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'inventory_stock_out_item'
        verbose_name = '出库单明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.stock_out.code} - {self.item.code} - {self.quantity}"


class StockTransfer(models.Model):
    """调拨单"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '调拨中'),
        (4, '已完成'),
        (5, '已取消'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name='调拨单号')
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='transfer_out', verbose_name='调出仓库')
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='transfer_in', verbose_name='调入仓库')
    total_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总数量')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='总金额')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
   requester = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, related_name='requested_transfers', verbose_name='申请人')
    request_time = models.DateTimeField(auto_now_add=True, verbose_name='申请时间')
    checker = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_transfers', verbose_name='审核人')
    check_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    executor = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, related_name='executed_transfers', verbose_name='执行人')
    execute_time = models.DateTimeField(null=True, blank=True, verbose_name='执行时间')
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'inventory_stock_transfer'
        verbose_name = '调拨单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.from_warehouse.name} → {self.to_warehouse.name}"


class StockTransferItem(models.Model):
    """调拨单明细"""
    stock_transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name='items', verbose_name='调拨单')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, verbose_name='物料')
    from_location = models.ForeignKey(WarehouseLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_from', verbose_name='调出库位')
    to_location = models.ForeignKey(WarehouseLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_to', verbose_name='调入库位')
    batch_number = models.CharField(max_length=50, blank=True, verbose_name='批次号')
    quantity = models.DecimalField(max_digits=12, decimal_places=4, verbose_name='调拨数量')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='单位成本')
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='金额')
    transferred_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='已调拨数量')
    remark = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'inventory_stock_transfer_item'
        verbose_name = '调拨单明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.stock_transfer.code} - {self.item.code} - {self.quantity}"


class StockCheck(models.Model):
    """盘点单"""
    STATUS_CHOICES = (
        (1, '待盘点'),
        (2, '盘点中'),
        (3, '已完成'),
        (4, '已取消'),
    )
    
    CHECK_TYPE_CHOICES = (
        ('partial', '部分盘点'),
        ('full', '全仓盘点'),
        ('cycle', '循环盘点'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name='盘点单号')
    check_type = models.CharField(max_length=20, choices=CHECK_TYPE_CHOICES, default='partial', verbose_name='盘点类型')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name='盘点仓库')
    category = models.ForeignKey(InventoryCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='盘点类别')
    total_items = models.IntegerField(default=0, verbose_name='盘点项数')
    checked_items = models.IntegerField(default=0, verbose_name='已盘点项数')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    profit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='盘盈金额')
    loss_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='盘亏金额')
    checker = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, related_name='checked_stockchecks', verbose_name='盘点人')
    check_time = models.DateTimeField(null=True, blank=True, verbose_name='盘点时间')
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'inventory_stock_check'
        verbose_name = '盘点单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.warehouse.name}"


class StockCheckItem(models.Model):
    """盘点单明细"""
    STATUS_CHOICES = (
        (1, '待盘点'),
        (2, '已盘点'),
        (3, '差异'),
        (4, '盘盈'),
        (5, '盘亏'),
    )
    
    stock_check = models.ForeignKey(StockCheck, on_delete=models.CASCADE, related_name='items', verbose_name='盘点单')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, verbose_name='物料')
    location = models.ForeignKey(WarehouseLocation, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='库位')
    batch_number = models.CharField(max_length=50, blank=True, verbose_name='批次号')
    system_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='系统数量')
    actual_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='实盘数量')
    difference = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='差异数量')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='单位成本')
    difference_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='差异金额')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='盘点状态')
    checker = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, verbose_name='盘点人')
    check_time = models.DateTimeField(null=True, blank=True, verbose_name='盘点时间')
    remark = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'inventory_stock_check_item'
        verbose_name = '盘点单明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.stock_check.code} - {self.item.code}"


class PurchaseOrder(models.Model):
    """采购订单"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '执行中'),
        (4, '已完成'),
        (5, '已取消'),
        (6, '已中止'),
    )
    
    ORDER_TYPE_CHOICES = (
        ('standard', '标准采购'),
        ('contract', '合同采购'),
        ('urgent', '紧急采购'),
        ('blanket', '框架协议'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name='采购单号')
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='standard', verbose_name='订单类型')
    supplier = models.ForeignKey('contract.Supplier', on_delete=models.CASCADE, verbose_name='供应商')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='收货仓库')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='订单金额')
    total_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='订单数量')
    received_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已收货金额')
    received_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='已收货数量')
    order_date = models.DateField(verbose_name='订单日期')
    expected_date = models.DateField(null=True, blank=True, verbose_name='期望到货日期')
    actual_date = models.DateField(null=True, blank=True, verbose_name='实际到货日期')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    checker = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_purchase_orders', verbose_name='审核人')
    check_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    creator = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, related_name='created_purchase_orders', verbose_name='创建人')
    contact_person = models.CharField(max_length=50, blank=True, verbose_name='联系人')
    contact_phone = models.CharField(max_length=50, blank=True, verbose_name='联系电话')
    delivery_address = models.CharField(max_length=500, blank=True, verbose_name='交货地址')
    payment_terms = models.CharField(max_length=100, blank=True, verbose_name='付款条件')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'inventory_purchase_order'
        verbose_name = '采购订单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.supplier.name}"


class PurchaseOrderItem(models.Model):
    """采购订单明细"""
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items', verbose_name='采购订单')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, verbose_name='物料')
    quantity = models.DecimalField(max_digits=12, decimal_places=4, verbose_name='采购数量')
    unit_price = models.DecimalField(max_digits=12, decimal_places=4, verbose_name='单价')
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='金额')
    received_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='已收货数量')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='实际成本')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='税率')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='税额')
    expected_date = models.DateField(null=True, blank=True, verbose_name='期望到货日期')
    actual_date = models.DateField(null=True, blank=True, verbose_name='实际到货日期')
    remark = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'inventory_purchase_order_item'
        verbose_name = '采购订单明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.purchase_order.code} - {self.item.code} - {self.quantity}"


class PurchasePriceHistory(models.Model):
    """采购价格历史"""
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='price_histories', verbose_name='物料')
    supplier = models.ForeignKey('contract.Supplier', on_delete=models.CASCADE, verbose_name='供应商')
    unit_price = models.DecimalField(max_digits=12, decimal_places=4, verbose_name='单价')
    min_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='最小订购量')
    effective_date = models.DateField(verbose_name='生效日期')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='失效日期')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    creator = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, verbose_name='创建人')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        db_table = 'inventory_purchase_price_history'
        verbose_name = '采购价格历史'
        verbose_name_plural = verbose_name
        ordering = ['-effective_date']
    
    def __str__(self):
        return f"{self.item.code} - {self.supplier.name} - {self.unit_price}"


class SalesOrder(models.Model):
    """销售订单"""
    STATUS_CHOICES = (
        (1, '待审核'),
        (2, '已审核'),
        (3, '已发货'),
        (4, '已完成'),
        (5, '已取消'),
        (6, '已退货'),
    )
    
    ORDER_TYPE_CHOICES = (
        ('standard', '标准销售'),
        ('contract', '合同销售'),
        ('urgent', '紧急订单'),
        ('blanket', '框架协议'),
    )
    
    code = models.CharField(max_length=50, unique=True, verbose_name='销售单号')
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='standard', verbose_name='订单类型')
    customer = models.ForeignKey('customer.Customer', on_delete=models.CASCADE, verbose_name='客户')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='发货仓库')
    contract = models.ForeignKey('contract.Contract', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='销售合同')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='订单金额')
    total_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='订单数量')
    shipped_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已发货金额')
    shipped_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='已发货数量')
    order_date = models.DateField(verbose_name='订单日期')
    expected_date = models.DateField(null=True, blank=True, verbose_name='期望发货日期')
    actual_date = models.DateField(null=True, blank=True, verbose_name='实际发货日期')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    checker = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_sales_orders', verbose_name='审核人')
    check_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    creator = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, related_name='created_sales_orders', verbose_name='创建人')
    contact_person = models.CharField(max_length=50, blank=True, verbose_name='联系人')
    contact_phone = models.CharField(max_length=50, blank=True, verbose_name='联系电话')
    shipping_address = models.CharField(max_length=500, blank=True, verbose_name='收货地址')
    payment_terms = models.CharField(max_length=100, blank=True, verbose_name='付款条件')
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='折扣金额')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='税额')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'inventory_sales_order'
        verbose_name = '销售订单'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.code} - {self.customer.name}"


class SalesOrderItem(models.Model):
    """销售订单明细"""
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items', verbose_name='销售订单')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, verbose_name='物料')
    quantity = models.DecimalField(max_digits=12, decimal_places=4, verbose_name='销售数量')
    unit_price = models.DecimalField(max_digits=12, decimal_places=4, verbose_name='单价')
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='金额')
    shipped_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='已发货数量')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='成本单价')
    cost_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='成本金额')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='税率')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='税额')
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='折扣率')
    expected_date = models.DateField(null=True, blank=True, verbose_name='期望发货日期')
    actual_date = models.DateField(null=True, blank=True, verbose_name='实际发货日期')
    remark = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'inventory_sales_order_item'
        verbose_name = '销售订单明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.sales_order.code} - {self.item.code} - {self.quantity}"


class InventoryAlert(models.Model):
    """库存预警"""
    ALERT_TYPE_CHOICES = (
        ('low_stock', '低库存预警'),
        ('over_stock', '超库存预警'),
        ('expiring', '过期预警'),
        ('slow_moving', '呆滞料预警'),
        ('reorder', '再订货预警'),
    )
    
    STATUS_CHOICES = (
        (1, '未处理'),
        (2, '已处理'),
        (3, '已忽略'),
    )
    
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='alerts', verbose_name='物料')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='alerts', verbose_name='仓库')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES, verbose_name='预警类型')
    current_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='当前数量')
    threshold_value = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name='阈值')
    message = models.TextField(verbose_name='预警信息')
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name='状态')
    handler = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='处理人')
    handle_time = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    handle_remark = models.TextField(blank=True, verbose_name='处理备注')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        db_table = 'inventory_alert'
        verbose_name = '库存预警'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.item.code} - {self.get_alert_type_display()}"


class InventoryReport(models.Model):
    """库存报表"""
    REPORT_TYPE_CHOICES = (
        ('summary', '库存汇总报表'),
        ('transaction', '库存变动明细报表'),
        ('turnover', '库存周转报表'),
        ('valuation', '库存价值报表'),
        ('age', '库龄分析报表'),
        ('movement', '出入库统计报表'),
    )
    
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, verbose_name='报表类型')
    report_name = models.CharField(max_length=100, verbose_name='报表名称')
    report_params = models.JSONField(default=dict, verbose_name='报表参数')
    report_data = models.JSONField(default=dict, verbose_name='报表数据')
    file_path = models.CharField(max_length=500, blank=True, verbose_name='文件路径')
    creator = models.ForeignKey(Admin, on_delete=models.SET_NULL, null=True, verbose_name='创建人')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        db_table = 'inventory_report'
        verbose_name = '库存报表'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.report_name} - {self.create_time}"
