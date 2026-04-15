"""
行政办公表单模块
包含公告管理、会议室管理、印章管理、公文管理、资产管理、车辆管理等表单类
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.system.models import (
    Notice, MeetingReservation, Seal, SealApplication,
    Document, DocumentCategory, Asset, AssetRepair, Vehicle,
    VehicleMaintenance, VehicleFee, VehicleOil
)
from apps.oa.models import MeetingRoom


class NoticeForm(forms.ModelForm):
    """公告表单"""
    target_departments = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'layui-checkbox'}),
        label='目标部门'
    )
    target_users = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'layui-checkbox'}),
        label='目标用户'
    )

    class Meta:
        model = Notice
        fields = [
            'title',
            'content',
            'notice_type',
            'is_top',
            'is_published',
            'target_departments',
            'target_users',
            'expire_time']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入公告标题'}),
            'content': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入公告内容', 'rows': 10}),
            'is_published': forms.CheckboxInput(attrs={'class': 'layui-checkbox'}),
            'notice_type': forms.Select(attrs={'class': 'layui-select'}),
            'is_top': forms.CheckboxInput(attrs={'class': 'layui-checkbox'}),
            'expire_time': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
        }
        labels = {
            'title': '公告标题',
            'content': '公告内容',
            'notice_type': '公告类型',
            'is_top': '置顶',
            'is_published': '是否发布',
            'expire_time': '过期时间',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.department.models import Department
        from apps.user.models import Admin
        self.fields['target_departments'].queryset = Department.objects.filter(
            is_active=True)
        self.fields['target_users'].queryset = Admin.objects.filter(status=1)

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if len(title) < 5:
            raise ValidationError('公告标题长度不能少于5个字符')
        return title


class MeetingRoomForm(forms.ModelForm):
    """会议室表单"""
    class Meta:
        model = MeetingRoom
        fields = ['name', 'code', 'location', 'capacity', 'has_projector',
                  'has_whiteboard', 'has_tv', 'has_phone', 'has_wifi',
                  'equipment_list', 'description', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入会议室名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入会议室编号'}),
            'capacity': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入容纳人数'}),
            'equipment_list': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入设备清单', 'rows': 3}),
            'location': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入位置信息'}),
            'status': forms.Select(attrs={'class': 'layui-select'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入描述信息', 'rows': 5}),
        }
        labels = {
            'name': '会议室名称',
            'code': '会议室编号',
            'capacity': '容纳人数',
            'equipment_list': '设备清单',
            'location': '位置信息',
            'status': '状态',
            'description': '描述信息',
        }

    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity')
        if capacity <= 0:
            raise ValidationError('容纳人数必须大于0')
        return capacity


class MeetingReservationForm(forms.ModelForm):
    """会议室预订表单"""
    class Meta:
        model = MeetingReservation
        fields = [
            'meeting_room',
            'title',
            'start_time',
            'end_time',
            'description']
        widgets = {
            'meeting_room': forms.Select(attrs={'class': 'layui-select'}),
            'title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入会议主题'}),
            'start_time': forms.DateTimeInput(attrs={'class': 'layui-input', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': 'layui-input', 'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入会议描述', 'rows': 5}),
        }
        labels = {
            'meeting_room': '会议室',
            'title': '会议主题',
            'start_time': '开始时间',
            'end_time': '结束时间',
            'description': '会议描述',
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if start_time and end_time:
            if start_time >= end_time:
                raise ValidationError('结束时间必须晚于开始时间')

            if start_time < timezone.now():
                raise ValidationError('开始时间不能早于当前时间')

        return cleaned_data


class SealForm(forms.ModelForm):
    """印章表单"""
    class Meta:
        model = Seal
        fields = ['name', 'seal_type', 'keeper', 'location', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入印章名称'}),
            'seal_type': forms.Select(attrs={'class': 'layui-select'}),
            'keeper': forms.Select(attrs={'class': 'layui-select'}),
            'location': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入存放位置'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入描述信息', 'rows': 5}),
        }
        labels = {
            'name': '印章名称',
            'seal_type': '印章类型',
            'keeper': '保管人',
            'location': '存放位置',
            'description': '描述信息',
        }


class SealApplicationForm(forms.ModelForm):
    """印章申请表单"""
    class Meta:
        model = SealApplication
        fields = ['seal', 'purpose', 'document_title', 'use_date', 'copies']
        widgets = {
            'seal': forms.Select(attrs={'class': 'layui-select'}),
            'purpose': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入用章用途', 'rows': 5}),
            'document_title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入文件标题'}),
            'use_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'copies': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入份数'}),
        }
        labels = {
            'seal': '印章',
            'purpose': '用章用途',
            'document_title': '文件标题',
            'use_date': '用章日期',
            'copies': '份数',
        }

    def clean_purpose(self):
        purpose = self.cleaned_data.get('purpose')
        if len(purpose) < 10:
            raise ValidationError('用章用途描述不能少于10个字符')
        return purpose


class DocumentForm(forms.ModelForm):
    """公文表单"""
    class Meta:
        model = Document
        fields = ['title', 'category', 'content', 'urgency', 'attachments']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入公文标题'}),
            'category': forms.Select(attrs={'class': 'layui-select'}),
            'content': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入公文内容', 'rows': 15}),
            'urgency': forms.Select(attrs={'class': 'layui-select'}),
            'attachments': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入附件信息', 'rows': 5}),
        }
        labels = {
            'title': '公文标题',
            'category': '公文分类',
            'content': '公文内容',
            'urgency': '紧急程度',
            'attachments': '附件信息',
        }

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if len(title) < 5:
            raise ValidationError('公文标题长度不能少于5个字符')
        return title


class DocumentCategoryForm(forms.ModelForm):
    """公文分类表单"""
    class Meta:
        model = DocumentCategory
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入分类名称'}),
            'code': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入分类代码'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入描述信息', 'rows': 5}),
        }
        labels = {
            'name': '分类名称',
            'code': '分类代码',
            'description': '描述信息',
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if not code.isalnum():
            raise ValidationError('分类代码只能包含字母和数字')
        return code


class AssetForm(forms.ModelForm):
    """资产表单"""
    class Meta:
        model = Asset
        fields = ['asset_number', 'name', 'category', 'brand', 'model', 'purchase_date',
                  'purchase_price', 'status', 'location', 'responsible_person', 'department', 'description']
        widgets = {
            'asset_number': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入资产编号'}),
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入资产名称'}),
            'category': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入资产类别'}),
            'brand': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入品牌'}),
            'model': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入型号'}),
            'purchase_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入购买价格'}),
            'status': forms.Select(attrs={'class': 'layui-select'}),
            'location': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入存放位置'}),
            'responsible_person': forms.Select(attrs={'class': 'layui-select'}),
            'department': forms.Select(attrs={'class': 'layui-select'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入描述信息', 'rows': 5}),
        }
        labels = {
            'asset_number': '资产编号',
            'name': '资产名称',
            'category': '资产类别',
            'brand': '品牌',
            'model': '型号',
            'purchase_date': '购买日期',
            'purchase_price': '购买价格',
            'status': '状态',
            'location': '存放位置',
            'responsible_person': '责任人',
            'department': '所属部门',
            'description': '描述信息',
        }

    def clean_purchase_price(self):
        price = self.cleaned_data.get('purchase_price')
        if price and price < 0:
            raise ValidationError('购买价格不能为负数')
        return price


class AssetRepairForm(forms.ModelForm):
    """资产维修表单"""
    class Meta:
        model = AssetRepair
        fields = [
            'asset',
            'fault_description',
            'repair_description',
            'repair_cost']
        widgets = {
            'asset': forms.Select(attrs={'class': 'layui-select'}),
            'fault_description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入故障描述', 'rows': 5}),
            'repair_description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入维修说明', 'rows': 5}),
            'repair_cost': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入维修费用'}),
        }
        labels = {
            'asset': '资产',
            'fault_description': '故障描述',
            'repair_description': '维修说明',
            'repair_cost': '维修费用',
        }

    def clean_repair_cost(self):
        cost = self.cleaned_data.get('repair_cost')
        if cost and cost < 0:
            raise ValidationError('维修费用不能为负数')
        return cost


class VehicleForm(forms.ModelForm):
    """车辆表单"""
    class Meta:
        model = Vehicle
        fields = ['license_plate', 'brand', 'model', 'color', 'purchase_date',
                  'purchase_price', 'status', 'driver', 'description']
        widgets = {
            'license_plate': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入车牌号'}),
            'brand': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入品牌'}),
            'model': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入型号'}),
            'color': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入颜色'}),
            'purchase_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入购买价格'}),
            'status': forms.Select(attrs={'class': 'layui-select'}),
            'driver': forms.Select(attrs={'class': 'layui-select'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入描述信息', 'rows': 5}),
        }
        labels = {
            'license_plate': '车牌号',
            'brand': '品牌',
            'model': '型号',
            'color': '颜色',
            'purchase_date': '购买日期',
            'purchase_price': '购买价格',
            'status': '状态',
            'driver': '驾驶员',
            'description': '描述信息',
        }

    def clean_license_plate(self):
        license_plate = self.cleaned_data.get('license_plate')
        # 简单的车牌号验证
        if len(license_plate) < 5:
            raise ValidationError('车牌号格式不正确')
        return license_plate


class VehicleMaintenanceForm(forms.ModelForm):
    """车辆维护表单"""
    class Meta:
        model = VehicleMaintenance
        fields = ['vehicle', 'maintenance_type', 'maintenance_date', 'mileage', 'cost',
                  'service_provider', 'description', 'next_maintenance']
        widgets = {
            'vehicle': forms.Select(attrs={'class': 'layui-select'}),
            'maintenance_type': forms.Select(attrs={'class': 'layui-select'}),
            'maintenance_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'mileage': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入里程数(公里)'}),
            'cost': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入费用'}),
            'service_provider': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入服务商'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入维修/保养内容', 'rows': 5}),
            'next_maintenance': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
        }
        labels = {
            'vehicle': '车辆',
            'maintenance_type': '类型',
            'maintenance_date': '维修/保养日期',
            'mileage': '里程数(公里)',
            'cost': '费用',
            'service_provider': '服务商',
            'description': '维修/保养内容',
            'next_maintenance': '下次保养日期',
        }

    def clean(self):
        cleaned_data = super().clean()
        maintenance_date = cleaned_data.get('maintenance_date')
        next_maintenance = cleaned_data.get('next_maintenance')

        if maintenance_date and next_maintenance:
            if next_maintenance <= maintenance_date:
                raise ValidationError('下次保养日期必须晚于本次维护日期')

        return cleaned_data


class VehicleFeeForm(forms.ModelForm):
    """车辆费用表单"""
    class Meta:
        model = VehicleFee
        fields = ['vehicle', 'fee_type', 'amount', 'fee_date', 'description']
        widgets = {
            'vehicle': forms.Select(attrs={'class': 'layui-select'}),
            'fee_type': forms.Select(attrs={'class': 'layui-select'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入金额'}),
            'fee_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入说明', 'rows': 5}),
        }
        labels = {
            'vehicle': '车辆',
            'fee_type': '费用类型',
            'amount': '金额',
            'fee_date': '费用日期',
            'description': '说明',
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount < 0:
            raise ValidationError('金额不能为负数')
        return amount


class VehicleOilForm(forms.ModelForm):
    """车辆加油表单"""
    class Meta:
        model = VehicleOil
        fields = [
            'vehicle',
            'oil_date',
            'oil_amount',
            'oil_cost',
            'mileage',
            'gas_station']
        widgets = {
            'vehicle': forms.Select(attrs={'class': 'layui-select'}),
            'oil_date': forms.DateInput(attrs={'class': 'layui-input', 'type': 'date'}),
            'oil_amount': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入加油量(L)'}),
            'oil_cost': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入加油费用'}),
            'mileage': forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '请输入里程数(公里)'}),
            'gas_station': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入加油站'}),
        }
        labels = {
            'vehicle': '车辆',
            'oil_date': '加油日期',
            'oil_amount': '加油量(L)',
            'oil_cost': '加油费用',
            'mileage': '里程数(公里)',
            'gas_station': '加油站',
        }

    def clean_oil_amount(self):
        amount = self.cleaned_data.get('oil_amount')
        if amount and amount <= 0:
            raise ValidationError('加油量必须大于0')
        return amount

    def clean_oil_cost(self):
        cost = self.cleaned_data.get('oil_cost')
        if cost and cost < 0:
            raise ValidationError('加油费用不能为负数')
        return cost

    def clean_mileage(self):
        mileage = self.cleaned_data.get('mileage')
        if mileage and mileage < 0:
            raise ValidationError('里程数不能为负数')
        return mileage
