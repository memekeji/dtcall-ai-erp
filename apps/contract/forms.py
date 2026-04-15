from django import forms
from django.contrib.auth import get_user_model
from .models import (
    Contract,
    Product,
    ProductCate,
    ContractCategory,
    ProductCategory,
    ServiceCategory,
    Service,
    Supplier,
    PurchaseCategory,
    PurchaseItem)

User = get_user_model()


class ContractCategoryForm(forms.ModelForm):
    class Meta:
        model = ContractCategory
        fields = [
            'name',
            'code',
            'parent',
            'description',
            'template_path',
            'sort_order',
            'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入分类名称'}),
            'code': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '自动生成，可修改'}),
            'parent': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入分类描述',
                    'rows': 3}),
            'template_path': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '合同模板路径'}),
            'sort_order': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '排序号'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = ContractCategory.objects.all()
        self.fields['parent'].empty_label = "无上级分类"


class ProductCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = [
            'name',
            'code',
            'parent',
            'description',
            'sort_order',
            'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入分类名称'}),
            'code': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '自动生成，可修改'}),
            'parent': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入分类描述',
                    'rows': 3}),
            'sort_order': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '排序号'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = ProductCategory.objects.all()
        self.fields['parent'].empty_label = "无上级分类"


class ServiceCategoryForm(forms.ModelForm):
    class Meta:
        model = ServiceCategory
        fields = [
            'name',
            'code',
            'parent',
            'description',
            'sort_order',
            'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入分类名称'}),
            'code': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '自动生成，可修改'}),
            'parent': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入分类描述',
                    'rows': 3}),
            'sort_order': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '排序号'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = ServiceCategory.objects.all()
        self.fields['parent'].empty_label = "无上级分类"


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            'name',
            'code',
            'category',
            'unit',
            'price',
            'duration',
            'description',
            'requirements',
            'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入服务名称'}),
            'code': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '自动生成，可修改'}),
            'category': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'unit': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '计量单位'}),
            'price': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'step': '0.01',
                    'placeholder': '服务价格'}),
            'duration': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '服务周期(天)'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入服务描述',
                    'rows': 3}),
            'requirements': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入服务要求',
                    'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ServiceCategory.objects.all()
        self.fields['category'].empty_label = "请选择服务分类"


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            'name',
            'code',
            'contact_person',
            'contact_phone',
            'contact_email',
            'address',
            'tax_number',
            'bank_account',
            'bank_name',
            'credit_level',
            'business_scope',
            'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入供应商名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '自动生成，可修改'}),
            'contact_person': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入联系人'}),
            'contact_phone': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入联系电话'}),
            'contact_email': forms.EmailInput(attrs={'class': 'layui-input', 'placeholder': '请输入联系邮箱'}),
            'address': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入地址'}),
            'tax_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入税号'}),
            'bank_account': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入银行账号'}),
            'bank_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入开户银行'}),
            'credit_level': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '信用等级'}),
            'business_scope': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入经营范围', 'rows': 3}),
        }


class PurchaseCategoryForm(forms.ModelForm):
    class Meta:
        model = PurchaseCategory
        fields = [
            'name',
            'code',
            'parent',
            'description',
            'sort_order',
            'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入分类名称'}),
            'code': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '自动生成，可修改'}),
            'parent': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入分类描述',
                    'rows': 3}),
            'sort_order': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '排序号'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = PurchaseCategory.objects.all()
        self.fields['parent'].empty_label = "无上级分类"


class PurchaseItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = [
            'name',
            'code',
            'category',
            'specification',
            'unit',
            'reference_price',
            'supplier',
            'description',
            'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入采购品名称'}),
            'code': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '自动生成，可修改'}),
            'category': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'specification': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入规格型号'}),
            'unit': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '计量单位'}),
            'reference_price': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'step': '0.01',
                    'placeholder': '参考价格'}),
            'supplier': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入采购品描述',
                    'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = PurchaseCategory.objects.all()
        self.fields['category'].empty_label = "请选择采购分类"
        self.fields['supplier'].queryset = Supplier.objects.filter(
            is_active=True)
        self.fields['supplier'].empty_label = "请选择供应商"


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = [
            'code',
            'name',
            'cate_id',
            'types',
            'subject_id',
            'customer_id',
            'customer',
            'contact_name',
            'contact_mobile',
            'contact_address',
            'start_time',
            'end_time',
            'admin_id',
            'prepared_uid',
            'sign_uid',
            'keeper_uid',
            'share_ids',
            'file_ids',
            'sign_time',
            'did',
            'cost',
            'content',
            'is_tax',
            'tax',
            'stop_uid',
            'stop_time',
            'stop_remark',
            'void_uid',
            'void_time',
            'void_remark',
            'archive_uid',
            'archive_time',
            'remark',
            'check_status',
            'check_flow_id',
            'check_step_sort',
            'check_uids',
            'check_last_uid',
            'check_history_uids',
            'check_copy_uids',
            'check_time']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入合同编号'}),
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入合同名称'}),
            'cate_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '分类ID'}),
            'types': forms.Select(attrs={'class': 'layui-input'}),
            'subject_id': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '签约主体'}),
            'customer_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '客户ID'}),
            'customer': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '客户名称'}),
            'contact_name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '客户代表'}),
            'contact_mobile': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '客户电话'}),
            'contact_address': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '客户地址'}),
            'start_time': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '开始时间'}),
            'end_time': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '结束时间'}),
            'admin_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '创建人ID'}),
            'prepared_uid': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '制定人ID'}),
            'sign_uid': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '签订人ID'}),
            'keeper_uid': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '保管人ID'}),
            'share_ids': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '共享人员ID'}),
            'file_ids': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '附件ID'}),
            'sign_time': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '签订时间'}),
            'did': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '部门ID'}),
            'cost': forms.NumberInput(attrs={'class': 'layui-input', 'step': '0.01', 'placeholder': '合同金额'}),
            'content': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '合同内容', 'rows': 6}),
            'is_tax': forms.Select(attrs={'class': 'layui-input'}),
            'tax': forms.NumberInput(attrs={'class': 'layui-input', 'step': '0.01', 'placeholder': '税点'}),
            'stop_uid': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '中止人ID'}),
            'stop_time': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '中止时间'}),
            'stop_remark': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '中止备注', 'rows': 3}),
            'void_uid': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '作废人ID'}),
            'void_time': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '作废时间'}),
            'void_remark': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '作废备注', 'rows': 3}),
            'archive_uid': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '归档人ID'}),
            'archive_time': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '归档时间'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '备注信息', 'rows': 3}),
            'check_status': forms.Select(attrs={'class': 'layui-input'}),
            'check_flow_id': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '审核流程ID'}),
            'check_step_sort': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '当前审批步骤'}),
            'check_uids': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '当前审批人ID'}),
            'check_last_uid': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '上一审批人'}),
            'check_history_uids': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '历史审批人ID'}),
            'check_copy_uids': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '抄送人ID'}),
            'check_time': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '审核通过时间'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'code', 'cate', 'specs', 'unit',
            'price', 'remark'
        ]
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入产品名称'}),
            'code': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入产品编码'}),
            'cate': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'specs': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '产品规格'}),
            'unit': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '计量单位'}),
            'price': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'step': '0.01',
                    'placeholder': '销售价格'}),
            'remark': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '产品描述',
                    'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cate'].queryset = ProductCate.objects.filter(
            status=1).order_by('title')


class LegacyProductCateForm(forms.ModelForm):
    class Meta:
        model = ProductCate
        fields = ['title', 'pid', 'status']
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入分类名称'}),
            'pid': forms.Select(
                attrs={
                    'class': 'layui-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pid'].queryset = ProductCate.objects.filter(
            pid__isnull=True, status=1)
        self.fields['pid'].empty_label = "无父分类"
