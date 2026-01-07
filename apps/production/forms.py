from django import forms
from django.core.exceptions import ValidationError
from .models import (
    ProductionProcedure, ProcedureSet, ProcedureSetItem, BOM, BOMItem,
    Equipment, ProductionPlan, ProductionTask, QualityCheck, 
    DataCollection, DataSource, DataCollectionRecord, SOP,
    DataMapping, ProductionDataPoint, DataCollectionTask,
    ProductionOrderChange, ProductionLineDayPlan,
    MaterialRequest, MaterialRequestItem, MaterialIssue, MaterialIssueItem,
    MaterialReturn, MaterialReturnItem, WorkCompletionReport,
    WorkCompletionRedFlush, ProductReceipt, OrderMaterialConfirmation,
    ResourceConsumption, ProcessRoute, ProcessRouteItem
)


class ProductionProcedureForm(forms.ModelForm):
    """基本工序表单"""
    class Meta:
        model = ProductionProcedure
        fields = ['name', 'code', 'description', 'standard_time', 'cost_per_hour', 
                  'department', 'sort', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'standard_time': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cost_per_hour': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'sort': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProcedureSetForm(forms.ModelForm):
    """工序集表单"""
    class Meta:
        model = ProcedureSet
        fields = ['name', 'code', 'description', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BOMForm(forms.ModelForm):
    """BOM表单"""
    class Meta:
        model = BOM
        fields = ['name', 'code', 'product', 'version', 'description', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'product': forms.Select(attrs={'class': 'form-control'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BOMItemForm(forms.ModelForm):
    """BOM物料明细表单"""
    class Meta:
        model = BOMItem
        fields = ['material_name', 'material_code', 'specification', 'unit', 
                  'quantity', 'unit_cost', 'total_cost', 'supplier', 'remark']
        widgets = {
            'material_name': forms.TextInput(attrs={'class': 'form-control'}),
            'material_code': forms.TextInput(attrs={'class': 'form-control'}),
            'specification': forms.TextInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'supplier': forms.TextInput(attrs={'class': 'form-control'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class BOMItemFormSet(forms.BaseInlineFormSet):
    """BOM物料明细内联表单集"""
    def clean(self):
        super().clean()
        total_cost = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                quantity = form.cleaned_data.get('quantity', 0)
                unit_cost = form.cleaned_data.get('unit_cost', 0)
                if quantity and unit_cost:
                    form.instance.total_cost = float(quantity) * float(unit_cost)
                    total_cost += form.instance.total_cost


class EquipmentForm(forms.ModelForm):
    """设备管理表单"""
    class Meta:
        model = Equipment
        fields = ['name', 'code', 'model', 'manufacturer', 'purchase_date', 
                  'purchase_cost', 'department', 'location', 'status', 
                  'responsible_person', 'maintenance_cycle', 'last_maintenance',
                  'next_maintenance', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'responsible_person': forms.Select(attrs={'class': 'form-control'}),
            'maintenance_cycle': forms.NumberInput(attrs={'class': 'form-control'}),
            'last_maintenance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'next_maintenance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ProductionPlanForm(forms.ModelForm):
    """生产计划表单"""
    class Meta:
        model = ProductionPlan
        fields = ['name', 'code', 'product', 'bom', 'procedure_set', 'process_route',
                  'quantity', 'unit', 'plan_start_date', 'plan_end_date',
                  'status', 'priority', 'department', 'manager', 'description',
                  'auto_complete', 'complete_threshold']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'product': forms.Select(attrs={'class': 'form-control'}),
            'bom': forms.Select(attrs={'class': 'form-control'}),
            'procedure_set': forms.Select(attrs={'class': 'form-control'}),
            'process_route': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'plan_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'plan_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'manager': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'auto_complete': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'complete_threshold': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class ProductionTaskForm(forms.ModelForm):
    """生产任务表单"""
    class Meta:
        model = ProductionTask
        fields = ['plan', 'name', 'code', 'procedure', 'equipment', 'quantity',
                  'plan_start_time', 'plan_end_time', 'status', 'assignee', 'description']
        widgets = {
            'plan': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'procedure': forms.Select(attrs={'class': 'form-control'}),
            'equipment': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'plan_start_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'plan_end_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'assignee': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class QualityCheckForm(forms.ModelForm):
    """质量检查表单"""
    class Meta:
        model = QualityCheck
        fields = ['task', 'check_time', 'checker', 'check_quantity', 
                  'qualified_quantity', 'defective_quantity', 'result',
                  'defect_description', 'improvement_suggestion']
        widgets = {
            'task': forms.Select(attrs={'class': 'form-control'}),
            'check_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'checker': forms.Select(attrs={'class': 'form-control'}),
            'check_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'qualified_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'defective_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'result': forms.Select(attrs={'class': 'form-control'}),
            'defect_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'improvement_suggestion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class DataCollectionForm(forms.ModelForm):
    """数据采集表单"""
    class Meta:
        model = DataCollection
        fields = ['task', 'equipment', 'parameter_name', 'parameter_value', 'unit',
                  'standard_min', 'standard_max', 'is_normal', 'collect_time', 'collector']
        widgets = {
            'task': forms.Select(attrs={'class': 'form-control'}),
            'equipment': forms.Select(attrs={'class': 'form-control'}),
            'parameter_name': forms.TextInput(attrs={'class': 'form-control'}),
            'parameter_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'standard_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'standard_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'is_normal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'collect_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'collector': forms.Select(attrs={'class': 'form-control'}),
        }


class DataSourceForm(forms.ModelForm):
    """数据源配置表单"""
    class Meta:
        model = DataSource
        fields = ['name', 'code', 'source_type', 'description', 'endpoint_url',
                  'host', 'port', 'auth_type', 'username', 'password', 'api_key',
                  'token', 'request_method', 'request_headers', 'request_params',
                  'request_body', 'timeout', 'retry_count', 'collection_interval',
                  'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'source_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'endpoint_url': forms.URLInput(attrs={'class': 'form-control'}),
            'host': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'auth_type': forms.Select(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'password': forms.PasswordInput(attrs={'class': 'form-control'}, render_value=True),
            'api_key': forms.TextInput(attrs={'class': 'form-control'}),
            'token': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'request_method': forms.Select(attrs={'class': 'form-control'}),
            'request_headers': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'request_params': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'request_body': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'timeout': forms.NumberInput(attrs={'class': 'form-control'}),
            'retry_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'collection_interval': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].required = False
        self.fields['api_key'].required = False
        self.fields['token'].required = False


class DataMappingForm(forms.ModelForm):
    """数据映射配置表单"""
    class Meta:
        model = DataMapping
        fields = ['data_source', 'name', 'source_path', 'field_type', 'transform_type',
                  'transform_params', 'is_required', 'min_value', 'max_value',
                  'regex_pattern', 'default_value', 'target_table', 'target_field',
                  'sort', 'is_active']
        widgets = {
            'data_source': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'source_path': forms.TextInput(attrs={'class': 'form-control'}),
            'field_type': forms.Select(attrs={'class': 'form-control'}),
            'transform_type': forms.Select(attrs={'class': 'form-control'}),
            'transform_params': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'min_value': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_value': forms.NumberInput(attrs={'class': 'form-control'}),
            'regex_pattern': forms.TextInput(attrs={'class': 'form-control'}),
            'default_value': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'target_table': forms.TextInput(attrs={'class': 'form-control'}),
            'target_field': forms.TextInput(attrs={'class': 'form-control'}),
            'sort': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DataCollectionRecordForm(forms.ModelForm):
    """数据采集记录表单"""
    class Meta:
        model = DataCollectionRecord
        fields = ['data_source', 'collection_time', 'status', 'raw_data',
                  'processed_data', 'record_count', 'success_count', 'error_count']
        widgets = {
            'data_source': forms.Select(attrs={'class': 'form-control'}),
            'collection_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'raw_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'processed_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'record_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'success_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'error_count': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class SOPForm(forms.ModelForm):
    """标准作业程序表单"""
    class Meta:
        model = SOP
        fields = ['name', 'code', 'procedure', 'version', 'content',
                  'safety_requirements', 'quality_standards', 'tools_required',
                  'file_path', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'procedure': forms.Select(attrs={'class': 'form-control'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'safety_requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'quality_standards': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tools_required': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'file_path': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProcessRouteForm(forms.ModelForm):
    """工艺路线表单"""
    class Meta:
        model = ProcessRoute
        fields = ['name', 'code', 'description', 'product', 'total_time', 
                  'total_cost', 'status', 'version', 'effective_date', 
                  'expiry_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'product': forms.Select(attrs={'class': 'form-control'}),
            'total_time': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'effective_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class ProcessRouteItemForm(forms.ModelForm):
    """工艺路线明细表单"""
    class Meta:
        model = ProcessRouteItem
        fields = ['procedure', 'sequence', 'estimated_time', 'workstation',
                  'work_instruction', 'quality_check_points', 'cycle_time']
        widgets = {
            'procedure': forms.Select(attrs={'class': 'form-control'}),
            'sequence': forms.NumberInput(attrs={'class': 'form-control'}),
            'estimated_time': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'workstation': forms.TextInput(attrs={'class': 'form-control'}),
            'work_instruction': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'quality_check_points': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cycle_time': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class ProcessRouteItemFormSet(forms.BaseInlineFormSet):
    """工艺路线明细内联表单集"""
    def clean(self):
        super().clean()
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                pass


class ProductionOrderChangeForm(forms.ModelForm):
    """生产订单变更单表单"""
    class Meta:
        model = ProductionOrderChange
        fields = ['production_plan', 'change_type', 'change_reason', 
                  'old_value', 'new_value', 'status']
        widgets = {
            'production_plan': forms.Select(attrs={'class': 'form-control'}),
            'change_type': forms.TextInput(attrs={'class': 'form-control'}),
            'change_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'old_value': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'new_value': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class ProductionLineDayPlanForm(forms.ModelForm):
    """生产线日计划表单"""
    class Meta:
        model = ProductionLineDayPlan
        fields = ['name', 'code', 'production_line', 'plan_date', 'production_plan',
                  'quantity', 'completed_quantity', 'status', 'manager', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'production_line': forms.TextInput(attrs={'class': 'form-control'}),
            'plan_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'production_plan': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'completed_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'manager': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class MaterialRequestForm(forms.ModelForm):
    """领料申请单表单"""
    class Meta:
        model = MaterialRequest
        fields = ['production_plan', 'production_task', 'code', 'request_date',
                  'requested_by', 'status', 'total_amount', 'description']
        widgets = {
            'production_plan': forms.Select(attrs={'class': 'form-control'}),
            'production_task': forms.Select(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'request_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'requested_by': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class MaterialRequestItemForm(forms.ModelForm):
    """领料申请明细表单"""
    class Meta:
        model = MaterialRequestItem
        fields = ['bom_item', 'material_name', 'material_code', 'specification',
                  'unit', 'request_quantity', 'issued_quantity', 'unit_cost',
                  'amount', 'remark']
        widgets = {
            'bom_item': forms.Select(attrs={'class': 'form-control'}),
            'material_name': forms.TextInput(attrs={'class': 'form-control'}),
            'material_code': forms.TextInput(attrs={'class': 'form-control'}),
            'specification': forms.TextInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'request_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'issued_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class MaterialIssueForm(forms.ModelForm):
    """材料出库单表单"""
    class Meta:
        model = MaterialIssue
        fields = ['code', 'material_request', 'production_plan', 'issue_date',
                  'issued_by', 'status', 'total_amount', 'description']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'material_request': forms.Select(attrs={'class': 'form-control'}),
            'production_plan': forms.Select(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'issued_by': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class MaterialIssueItemForm(forms.ModelForm):
    """材料出库明细表单"""
    class Meta:
        model = MaterialIssueItem
        fields = ['material_request_item', 'material_name', 'material_code',
                  'specification', 'unit', 'issue_quantity', 'unit_cost', 
                  'amount', 'remark']
        widgets = {
            'material_request_item': forms.Select(attrs={'class': 'form-control'}),
            'material_name': forms.TextInput(attrs={'class': 'form-control'}),
            'material_code': forms.TextInput(attrs={'class': 'form-control'}),
            'specification': forms.TextInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'issue_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class MaterialReturnForm(forms.ModelForm):
    """材料退料单表单"""
    class Meta:
        model = MaterialReturn
        fields = ['code', 'material_issue', 'production_plan', 'return_date',
                  'returned_by', 'status', 'total_amount', 'return_reason']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'material_issue': forms.Select(attrs={'class': 'form-control'}),
            'production_plan': forms.Select(attrs={'class': 'form-control'}),
            'return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'returned_by': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'return_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class MaterialReturnItemForm(forms.ModelForm):
    """材料退料明细表单"""
    class Meta:
        model = MaterialReturnItem
        fields = ['material_issue_item', 'material_name', 'material_code',
                  'specification', 'unit', 'return_quantity', 'unit_cost',
                  'amount', 'remark']
        widgets = {
            'material_issue_item': forms.Select(attrs={'class': 'form-control'}),
            'material_name': forms.TextInput(attrs={'class': 'form-control'}),
            'material_code': forms.TextInput(attrs={'class': 'form-control'}),
            'specification': forms.TextInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'return_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class WorkCompletionReportForm(forms.ModelForm):
    """完工申报表单"""
    class Meta:
        model = WorkCompletionReport
        fields = ['code', 'production_task', 'report_date', 'reported_quantity',
                  'qualified_quantity', 'defective_quantity', 'reported_by',
                  'status', 'work_hours', 'resource_consumption', 'remarks']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'production_task': forms.Select(attrs={'class': 'form-control'}),
            'report_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reported_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'qualified_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'defective_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reported_by': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'work_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'resource_consumption': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class WorkCompletionRedFlushForm(forms.ModelForm):
    """完工红冲表单"""
    class Meta:
        model = WorkCompletionRedFlush
        fields = ['code', 'completion_report', 'red_flush_date', 'red_flush_reason',
                  'red_flush_quantity', 'requested_by', 'status']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'completion_report': forms.Select(attrs={'class': 'form-control'}),
            'red_flush_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'red_flush_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'red_flush_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'requested_by': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class ProductReceiptForm(forms.ModelForm):
    """成品入库表单"""
    class Meta:
        model = ProductReceipt
        fields = ['code', 'completion_report', 'production_plan', 'receipt_date',
                  'receipt_quantity', 'storage_location', 'received_by',
                  'status', 'remarks']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'completion_report': forms.Select(attrs={'class': 'form-control'}),
            'production_plan': forms.Select(attrs={'class': 'form-control'}),
            'receipt_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'receipt_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'storage_location': forms.TextInput(attrs={'class': 'form-control'}),
            'received_by': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class OrderMaterialConfirmationForm(forms.ModelForm):
    """订单材料确认单表单"""
    class Meta:
        model = OrderMaterialConfirmation
        fields = ['production_plan', 'material_issue', 'confirmed_quantity',
                  'confirmed_by', 'confirm_time', 'remarks']
        widgets = {
            'production_plan': forms.Select(attrs={'class': 'form-control'}),
            'material_issue': forms.Select(attrs={'class': 'form-control'}),
            'confirmed_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'confirmed_by': forms.Select(attrs={'class': 'form-control'}),
            'confirm_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ResourceConsumptionForm(forms.ModelForm):
    """资源消耗记录表单"""
    class Meta:
        model = ResourceConsumption
        fields = ['production_task', 'resource_type', 'resource_name',
                  'consumed_quantity', 'unit', 'cost', 'consumption_time',
                  'recorded_by']
        widgets = {
            'production_task': forms.Select(attrs={'class': 'form-control'}),
            'resource_type': forms.TextInput(attrs={'class': 'form-control'}),
            'resource_name': forms.TextInput(attrs={'class': 'form-control'}),
            'consumed_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'consumption_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'recorded_by': forms.Select(attrs={'class': 'form-control'}),
        }


class DataCollectionTaskForm(forms.ModelForm):
    """数据采集任务表单"""
    class Meta:
        model = DataCollectionTask
        fields = ['name', 'task_type', 'cron_expression', 'interval_seconds',
                  'max_retries', 'timeout_seconds', 'status', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'task_type': forms.Select(attrs={'class': 'form-control'}),
            'cron_expression': forms.TextInput(attrs={'class': 'form-control'}),
            'interval_seconds': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_retries': forms.NumberInput(attrs={'class': 'form-control'}),
            'timeout_seconds': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProductionDataPointForm(forms.ModelForm):
    """生产数据点表单"""
    class Meta:
        model = ProductionDataPoint
        fields = ['equipment', 'data_source', 'collection', 'metric_name',
                  'metric_value', 'metric_unit', 'timestamp', 'collection_time',
                  'quality', 'confidence', 'task', 'procedure', 'tags', 'metadata']
        widgets = {
            'equipment': forms.Select(attrs={'class': 'form-control'}),
            'data_source': forms.Select(attrs={'class': 'form-control'}),
            'collection': forms.Select(attrs={'class': 'form-control'}),
            'metric_name': forms.TextInput(attrs={'class': 'form-control'}),
            'metric_value': forms.TextInput(attrs={'class': 'form-control'}),
            'metric_unit': forms.TextInput(attrs={'class': 'form-control'}),
            'timestamp': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'collection_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'quality': forms.TextInput(attrs={'class': 'form-control'}),
            'confidence': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'task': forms.Select(attrs={'class': 'form-control'}),
            'procedure': forms.Select(attrs={'class': 'form-control'}),
            'tags': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'metadata': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
