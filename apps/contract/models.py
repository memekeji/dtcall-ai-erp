from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.contrib.auth import get_user_model

def get_user_model_lazy():
    """延迟获取用户模型，避免循环导入"""
    return get_user_model()


class ContractCategory(models.Model):
    """合同分类 - 从basedata迁移"""
    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='分类代码', blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name='上级分类')
    description = models.TextField(blank=True, verbose_name='分类描述')
    template_path = models.CharField(max_length=200, blank=True, verbose_name='合同模板路径')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '合同分类'
        verbose_name_plural = verbose_name
        db_table = 'basedata_contract_category'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.code:
            import re
            from django.utils.text import slugify
            
            base_code = slugify(self.name).replace('-', '_').upper()
            if len(base_code) > 45:
                base_code = base_code[:45]
            
            counter = 1
            temp_code = base_code
            
            while ContractCategory.objects.filter(code=temp_code).exclude(pk=self.pk).exists():
                suffix = f"_{counter}"
                if len(base_code) + len(suffix) > 50:
                    base_code = base_code[:50 - len(suffix)]
                temp_code = base_code + suffix
                counter += 1
            
            self.code = temp_code
        
        super().save(*args, **kwargs)


class ProductCategory(models.Model):
    """产品分类 - 从basedata迁移"""
    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='分类代码')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name='上级分类')
    description = models.TextField(blank=True, verbose_name='分类描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '产品分类'
        verbose_name_plural = verbose_name
        db_table = 'basedata_product_category'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class ServiceCategory(models.Model):
    """服务分类 - 从basedata迁移"""
    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='分类代码')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name='上级分类')
    description = models.TextField(blank=True, verbose_name='分类描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '服务分类'
        verbose_name_plural = verbose_name
        db_table = 'basedata_service_category'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Service(models.Model):
    """服务内容 - 从basedata迁移"""
    name = models.CharField(max_length=200, verbose_name='服务名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='服务代码')
    category = models.ForeignKey('ServiceCategory', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='服务分类')
    unit = models.CharField(max_length=20, blank=True, verbose_name='计量单位')
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='服务价格')
    duration = models.IntegerField(null=True, blank=True, verbose_name='服务周期(天)')
    description = models.TextField(blank=True, verbose_name='服务描述')
    requirements = models.TextField(blank=True, verbose_name='服务要求')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '服务内容'
        verbose_name_plural = verbose_name
        db_table = 'basedata_service'

    def __str__(self):
        return self.name


class Supplier(models.Model):
    """供应商列表 - 从basedata迁移"""
    name = models.CharField(max_length=200, verbose_name='供应商名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='供应商代码')
    contact_person = models.CharField(max_length=50, verbose_name='联系人')
    contact_phone = models.CharField(max_length=50, verbose_name='联系电话')
    contact_email = models.EmailField(blank=True, verbose_name='联系邮箱')
    address = models.CharField(max_length=500, blank=True, verbose_name='地址')
    tax_number = models.CharField(max_length=50, blank=True, verbose_name='税号')
    bank_account = models.CharField(max_length=100, blank=True, verbose_name='银行账号')
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='开户银行')
    credit_level = models.CharField(max_length=20, blank=True, verbose_name='信用等级')
    business_scope = models.TextField(blank=True, verbose_name='经营范围')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '供应商'
        verbose_name_plural = verbose_name
        db_table = 'basedata_supplier'

    def __str__(self):
        return self.name


class PurchaseCategory(models.Model):
    """采购品分类 - 从basedata迁移"""
    name = models.CharField(max_length=100, verbose_name='分类名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='分类代码')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name='上级分类')
    description = models.TextField(blank=True, verbose_name='分类描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '采购品分类'
        verbose_name_plural = verbose_name
        db_table = 'basedata_purchase_category'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class PurchaseItem(models.Model):
    """采购品列表 - 从basedata迁移"""
    name = models.CharField(max_length=200, verbose_name='采购品名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='采购品代码')
    category = models.ForeignKey(PurchaseCategory, on_delete=models.CASCADE, verbose_name='采购品分类')
    specification = models.CharField(max_length=500, blank=True, verbose_name='规格型号')
    unit = models.CharField(max_length=20, blank=True, verbose_name='计量单位')
    reference_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='参考价格')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='主要供应商')
    description = models.TextField(blank=True, verbose_name='采购品描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '采购品'
        verbose_name_plural = verbose_name
        db_table = 'basedata_purchase_item'

    def __str__(self):
        return self.name


class ContractCate(models.Model):
    title = models.CharField(max_length=100, verbose_name='合同类别名称', default='')
    status = models.SmallIntegerField(default=1, verbose_name='状态：-1删除 0禁用 1启用')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.BigIntegerField(verbose_name='删除时间', default=0, help_text='原表bigint NOT NULL DEFAULT 0')

    class Meta:
        db_table = 'mimu_contract_cate'
        verbose_name = '合同类别'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title

class Contract(models.Model):
    pid = models.IntegerField(default=0, verbose_name='父协议id')
    code = models.CharField(max_length=255, verbose_name='合同编号', default='')
    name = models.CharField(max_length=255, verbose_name='合同名称', default='')
    cate_id = models.IntegerField(default=0, verbose_name='分类id')
    types = models.SmallIntegerField(default=1, verbose_name='合同性质:1普通合同2商品合同3服务合同')
    subject_id = models.CharField(max_length=255, default='', verbose_name='签约主体')
    customer_id = models.IntegerField(default=0, verbose_name='关联客户ID')
    customer = models.CharField(max_length=255, default='', verbose_name='客户名称')
    contact_name = models.CharField(max_length=255, default='', verbose_name='客户代表')
    contact_mobile = models.CharField(max_length=255, default='', verbose_name='客户电话')
    contact_address = models.CharField(max_length=255, default='', verbose_name='客户地址')
    start_time = models.BigIntegerField(verbose_name='合同开始时间', default=0)
    end_time = models.BigIntegerField(verbose_name='合同结束时间', default=0)
    admin_id = models.IntegerField(default=0, verbose_name='创建人')
    prepared_uid = models.IntegerField(default=0, verbose_name='合同制定人')
    sign_uid = models.IntegerField(default=0, verbose_name='合同签订人')
    keeper_uid = models.IntegerField(default=0, verbose_name='合同保管人')
    share_ids = models.CharField(max_length=500, default='', verbose_name='共享人员ID')
    file_ids = models.CharField(max_length=500, default='', verbose_name='相关附件ID')
    sign_time = models.BigIntegerField(verbose_name='合同签订时间', default=0)
    did = models.IntegerField(default=0, verbose_name='合同所属部门')
    cost = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name='合同金额')
    content = models.TextField(default='', verbose_name='合同内容')
    is_tax = models.SmallIntegerField(default=0, verbose_name='是否含税：0未含税,1含税')
    tax = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name='税点')
    stop_uid = models.IntegerField(default=0, verbose_name='中止人')
    stop_time = models.BigIntegerField(verbose_name='中止时间', default=0)
    stop_remark = models.TextField(default='', verbose_name='中止备注信息')
    void_uid = models.IntegerField(default=0, verbose_name='作废人')
    void_time = models.BigIntegerField(verbose_name='作废时间', default=0)
    void_remark = models.TextField(default='', verbose_name='作废备注信息')
    archive_uid = models.IntegerField(default=0, verbose_name='归档人')
    archive_time = models.BigIntegerField(verbose_name='归档时间', default=0)
    remark = models.TextField(default='', verbose_name='备注信息')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.BigIntegerField(verbose_name='删除时间', default=0, help_text='原表bigint NOT NULL DEFAULT 0')
    check_status = models.SmallIntegerField(default=0, verbose_name='审核状态:0待审核,1审核中,2审核通过,3审核不通过,4撤销审核')
    check_flow_id = models.IntegerField(default=0, verbose_name='审核流程id')
    check_step_sort = models.IntegerField(default=0, verbose_name='当前审批步骤')
    check_uids = models.CharField(max_length=500, default='', verbose_name='当前审批人ID')
    check_last_uid = models.CharField(max_length=500, default='', verbose_name='上一审批人')
    check_history_uids = models.CharField(max_length=500, default='', verbose_name='历史审批人ID')
    check_copy_uids = models.CharField(max_length=500, default='', verbose_name='抄送人ID')
    check_time = models.BigIntegerField(default=0, verbose_name='审核通过时间')
    auto_generated = models.BooleanField(default=False, verbose_name='是否自动生成')

    class Meta:
        db_table = 'mimu_contract'
        verbose_name = '销售合同'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=100, verbose_name='产品名称', default='')
    code = models.CharField(max_length=50, verbose_name='产品编码', default='')
    cate = models.ForeignKey('ProductCate', on_delete=models.SET_NULL, null=True, verbose_name='产品分类')
    specs = models.CharField(max_length=100, blank=True, verbose_name='产品规格')
    unit = models.CharField(max_length=20, blank=True, verbose_name='单位')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='单价')
    remark = models.TextField(blank=True, verbose_name='备注')
    admin = models.ForeignKey('user.Admin', on_delete=models.SET_NULL, null=True, related_name='product_admin', verbose_name='管理员')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')

    class Meta:
        db_table = 'contract_product'
        verbose_name = '合同产品'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

class ProductCate(models.Model):
    title = models.CharField(max_length=50, verbose_name='分类名称', default='')
    pid = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='父级分类')
    status = models.SmallIntegerField(default=1, verbose_name='状态')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')

    class Meta:
        db_table = 'contract_product_cate'
        verbose_name = '合同产品分类'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title

class Services(models.Model):
    title = models.CharField(max_length=100, verbose_name='服务名称', default='')
    code = models.CharField(max_length=50, verbose_name='服务编码', default='')
    unit = models.CharField(max_length=20, blank=True, verbose_name='单位')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='单价')
    remark = models.TextField(blank=True, verbose_name='备注')
    admin = models.ForeignKey('user.Admin', on_delete=models.SET_NULL, null=True, related_name='services_admin', verbose_name='管理员')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')

    class Meta:
        db_table = 'contract_services'
        verbose_name = '合同服务'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

from django.conf import settings

class Purchase(models.Model):
    name = models.CharField(max_length=100, verbose_name='采购名称', default='')
    code = models.CharField(max_length=50, verbose_name='采购编号', default='')
    cate = models.ForeignKey(ContractCate, on_delete=models.SET_NULL, null=True, verbose_name='采购分类')
    types = models.SmallIntegerField(default=0, verbose_name='采购类型')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], verbose_name='采购金额')
    sign_time = models.DateField(verbose_name='签订日期')
    start_time = models.DateField(verbose_name='开始日期')
    end_time = models.DateField(verbose_name='结束日期')
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchase_admin', verbose_name='管理员')
    sign_uid = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchase_sign', verbose_name='签订人')
    prepared_uid = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchase_prepared', verbose_name='编制人')
    keeper_uid = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchase_keeper', verbose_name='保管人')
    share_ids = models.CharField(max_length=255, blank=True, verbose_name='共享人员ID')
    check_status = models.SmallIntegerField(default=0, verbose_name='审核状态')
    check_uids = models.CharField(max_length=255, blank=True, verbose_name='待审核人员ID')
    check_history_uids = models.CharField(max_length=255, blank=True, verbose_name='已审核人员ID')
    file_ids = models.CharField(max_length=255, blank=True, verbose_name='附件ID')
    remark = models.TextField(blank=True, verbose_name='备注')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    delete_time = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')
    archive_time = models.DateTimeField(null=True, blank=True, verbose_name='归档时间')
    stop_time = models.DateTimeField(null=True, blank=True, verbose_name='终止时间')
    void_time = models.DateTimeField(null=True, blank=True, verbose_name='作废时间')
    archive_uid = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchase_archive', verbose_name='归档人')
    stop_uid = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchase_stop', verbose_name='终止人')
    void_uid = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchase_void', verbose_name='作废人')

    class Meta:
        db_table = 'contract_purchase'
        verbose_name = '合同采购'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name