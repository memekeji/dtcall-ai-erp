from django.contrib import admin
from django.db import models
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


class ProcedureSetItemInline(admin.TabularInline):
    model = ProcedureSetItem
    extra = 1
    fields = ['procedure', 'sequence', 'estimated_time']
    verbose_name = '工序明细'
    verbose_name_plural = '工序明细'


class BOMItemInline(admin.TabularInline):
    model = BOMItem
    extra = 1
    fields = ['material_name', 'material_code', 'specification', 'unit', 
              'quantity', 'unit_cost', 'total_cost', 'supplier']
    verbose_name = '物料明细'
    verbose_name_plural = '物料明细'


class ProductionTaskInline(admin.TabularInline):
    model = ProductionTask
    extra = 0
    fields = ['name', 'code', 'procedure', 'equipment', 'quantity', 
              'completed_quantity', 'status', 'assignee']
    readonly_fields = ['completed_quantity']
    verbose_name = '生产任务'
    verbose_name_plural = '生产任务'


class QualityCheckInline(admin.TabularInline):
    model = QualityCheck
    extra = 0
    fields = ['check_time', 'checker', 'check_quantity', 'qualified_quantity',
              'defective_quantity', 'result']
    readonly_fields = ['check_time', 'qualified_quantity', 'defective_quantity']
    verbose_name = '质量检查'
    verbose_name_plural = '质量检查'


class DataCollectionInline(admin.TabularInline):
    model = DataCollection
    extra = 0
    fields = ['equipment', 'parameter_name', 'parameter_value', 'unit',
              'is_normal', 'collect_time']
    readonly_fields = ['parameter_value', 'collect_time']
    verbose_name = '数据采集'
    verbose_name_plural = '数据采集'


class DataMappingInline(admin.TabularInline):
    model = DataMapping
    extra = 1
    fields = ['name', 'source_path', 'field_type', 'transform_type',
              'is_required', 'sort', 'is_active']
    verbose_name = '数据映射'
    verbose_name_plural = '数据映射'


class MaterialRequestItemInline(admin.TabularInline):
    model = MaterialRequestItem
    extra = 1
    fields = ['material_name', 'material_code', 'specification', 'unit',
              'request_quantity', 'issued_quantity', 'unit_cost', 'amount']
    readonly_fields = ['issued_quantity', 'amount']
    verbose_name = '申请明细'
    verbose_name_plural = '申请明细'


class MaterialIssueItemInline(admin.TabularInline):
    model = MaterialIssueItem
    extra = 1
    fields = ['material_name', 'material_code', 'specification', 'unit',
              'issue_quantity', 'unit_cost', 'amount']
    readonly_fields = ['amount']
    verbose_name = '出库明细'
    verbose_name_plural = '出库明细'


class MaterialReturnItemInline(admin.TabularInline):
    model = MaterialReturnItem
    extra = 1
    fields = ['material_name', 'material_code', 'specification', 'unit',
              'return_quantity', 'unit_cost', 'amount']
    readonly_fields = ['amount']
    verbose_name = '退料明细'
    verbose_name_plural = '退料明细'


class ProcessRouteItemInline(admin.TabularInline):
    model = ProcessRouteItem
    extra = 1
    fields = ['procedure', 'sequence', 'estimated_time', 'workstation',
              'cycle_time']
    verbose_name = '工艺路线明细'
    verbose_name_plural = '工艺路线明细'


@admin.register(ProductionProcedure)
class ProductionProcedureAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'department', 'standard_time', 
                    'cost_per_hour', 'status', 'create_time']
    list_filter = ['department', 'status', 'create_time']
    search_fields = ['code', 'name', 'description']
    ordering = ['sort', '-create_time']
    fieldsets = [
        ('基本信息', {'fields': ['name', 'code', 'description']}),
        ('时间成本', {'fields': ['standard_time', 'cost_per_hour']}),
        ('组织信息', {'fields': ['department', 'sort']}),
        ('状态信息', {'fields': ['status']}),
    ]


@admin.register(ProcedureSet)
class ProcedureSetAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'total_time', 'total_cost', 
                    'status', 'create_time']
    list_filter = ['status', 'create_time']
    search_fields = ['code', 'name', 'description']
    inlines = [ProcedureSetItemInline]


@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'product', 'version', 'status', 'create_time']
    list_filter = ['product', 'status', 'create_time']
    search_fields = ['code', 'name', 'description']
    inlines = [BOMItemInline]


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'model', 'department', 'location', 
                    'status', 'next_maintenance', 'create_time']
    list_filter = ['department', 'status', 'create_time']
    search_fields = ['code', 'name', 'model', 'manufacturer']
    fieldsets = [
        ('基本信息', {'fields': ['name', 'code', 'model', 'manufacturer']}),
        ('采购信息', {'fields': ['purchase_date', 'purchase_cost']}),
        ('组织信息', {'fields': ['department', 'location']}),
        ('状态信息', {'fields': ['status', 'responsible_person']}),
        ('维护信息', {'fields': ['maintenance_cycle', 'last_maintenance', 
                                  'next_maintenance']}),
        ('描述信息', {'fields': ['description']}),
    ]


@admin.register(ProductionPlan)
class ProductionPlanAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'product', 'quantity', 'unit',
                    'plan_start_date', 'plan_end_date', 'status',
                    'completion_rate', 'create_time']
    list_filter = ['product', 'status', 'plan_start_date', 'create_time']
    search_fields = ['code', 'name', 'description']
    inlines = [ProductionTaskInline]
    fieldsets = [
        ('基本信息', {'fields': ['name', 'code', 'product']}),
        ('工艺信息', {'fields': ['bom', 'procedure_set', 'process_route']}),
        ('计划信息', {'fields': ['quantity', 'unit', 'plan_start_date', 
                                  'plan_end_date']}),
        ('状态信息', {'fields': ['status', 'priority', 'department', 'manager']}),
        ('描述信息', {'fields': ['description']}),
        ('自动完工', {'fields': ['auto_complete', 'complete_threshold']}),
    ]
    readonly_fields = ['completion_rate']


@admin.register(ProductionTask)
class ProductionTaskAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'plan', 'procedure', 'equipment',
                    'quantity', 'completed_quantity', 'qualified_quantity',
                    'status', 'assignee', 'create_time']
    list_filter = ['procedure', 'equipment', 'status', 'create_time']
    search_fields = ['code', 'name', 'description']
    inlines = [QualityCheckInline, DataCollectionInline]
    fieldsets = [
        ('基本信息', {'fields': ['plan', 'name', 'code']}),
        ('执行信息', {'fields': ['procedure', 'equipment']}),
        ('数量信息', {'fields': ['quantity', 'completed_quantity', 
                                  'qualified_quantity', 'defective_quantity']}),
        ('时间信息', {'fields': ['plan_start_time', 'plan_end_time',
                                  'actual_start_time', 'actual_end_time']}),
        ('状态信息', {'fields': ['status', 'assignee', 'description']}),
        ('挂起信息', {'fields': ['suspended_by', 'suspended_time', 
                                  'suspend_reason']}),
    ]
    readonly_fields = ['completed_quantity', 'qualified_quantity', 
                       'defective_quantity']


@admin.register(QualityCheck)
class QualityCheckAdmin(admin.ModelAdmin):
    list_display = ['task', 'check_time', 'checker', 'check_quantity',
                    'qualified_quantity', 'defective_quantity', 'result']
    list_filter = ['result', 'check_time']
    search_fields = ['task__name', 'defect_description']
    fieldsets = [
        ('任务信息', {'fields': ['task']}),
        ('检查信息', {'fields': ['check_time', 'checker']}),
        ('数量信息', {'fields': ['check_quantity', 'qualified_quantity',
                                  'defective_quantity']}),
        ('结果信息', {'fields': ['result']}),
        ('描述信息', {'fields': ['defect_description', 'improvement_suggestion']}),
    ]
    readonly_fields = ['check_time', 'qualified_quantity', 'defective_quantity']


@admin.register(DataCollection)
class DataCollectionAdmin(admin.ModelAdmin):
    list_display = ['task', 'equipment', 'parameter_name', 'parameter_value',
                    'unit', 'is_normal', 'collect_time']
    list_filter = ['equipment', 'is_normal', 'collect_time']
    search_fields = ['parameter_name']


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'source_type', 'host', 'port',
                    'collection_interval', 'is_active', 'last_collection_time']
    list_filter = ['source_type', 'is_active', 'create_time']
    search_fields = ['name', 'code', 'description']
    inlines = [DataMappingInline]
    fieldsets = [
        ('基本信息', {'fields': ['name', 'code', 'source_type', 'description']}),
        ('连接信息', {'fields': ['endpoint_url', 'host', 'port']}),
        ('认证信息', {'fields': ['auth_type', 'username', 'password', 
                                  'api_key', 'token']}),
        ('请求配置', {'fields': ['request_method', 'request_headers',
                                  'request_params', 'request_body']}),
        ('高级配置', {'fields': ['timeout', 'retry_count', 'collection_interval']}),
        ('状态信息', {'fields': ['is_active']}),
    ]


@admin.register(DataMapping)
class DataMappingAdmin(admin.ModelAdmin):
    list_display = ['data_source', 'name', 'source_path', 'field_type',
                    'transform_type', 'is_required', 'sort', 'is_active']
    list_filter = ['data_source', 'field_type', 'transform_type', 'is_active']
    search_fields = ['name', 'source_path']


@admin.register(DataCollectionRecord)
class DataCollectionRecordAdmin(admin.ModelAdmin):
    list_display = ['data_source', 'collection_time', 'status', 
                    'record_count', 'success_count', 'error_count', 'duration']
    list_filter = ['data_source', 'status', 'collection_time']
    search_fields = ['error_message']
    fieldsets = [
        ('基本信息', {'fields': ['data_source', 'collection_time', 'status']}),
        ('数据信息', {'fields': ['raw_data', 'raw_response', 'processed_data']}),
        ('统计信息', {'fields': ['record_count', 'success_count', 'error_count']}),
        ('错误信息', {'fields': ['error_message', 'error_details']}),
        ('时间信息', {'fields': ['start_time', 'end_time', 'duration']}),
    ]


@admin.register(SOP)
class SOPAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'procedure', 'version', 'status', 'create_time']
    list_filter = ['procedure', 'status', 'create_time']
    search_fields = ['code', 'name', 'content']
    fieldsets = [
        ('基本信息', {'fields': ['name', 'code', 'procedure', 'version']}),
        ('内容信息', {'fields': ['content', 'safety_requirements', 
                                  'quality_standards', 'tools_required']}),
        ('文件信息', {'fields': ['file_path']}),
        ('状态信息', {'fields': ['status']}),
    ]


@admin.register(ProcessRoute)
class ProcessRouteAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'product', 'version', 'total_time',
                    'total_cost', 'status', 'effective_date', 'create_time']
    list_filter = ['product', 'status', 'create_time']
    search_fields = ['code', 'name', 'description']
    inlines = [ProcessRouteItemInline]
    fieldsets = [
        ('基本信息', {'fields': ['name', 'code', 'description', 'product']}),
        ('成本信息', {'fields': ['total_time', 'total_cost']}),
        ('状态信息', {'fields': ['status', 'version']}),
        ('有效期', {'fields': ['effective_date', 'expiry_date']}),
    ]


@admin.register(ProductionOrderChange)
class ProductionOrderChangeAdmin(admin.ModelAdmin):
    list_display = ['production_plan', 'change_type', 'change_reason',
                    'status', 'creator', 'create_time']
    list_filter = ['status', 'create_time']
    search_fields = ['change_type', 'change_reason']
    fieldsets = [
        ('基本信息', {'fields': ['production_plan', 'change_type', 'change_reason']}),
        ('变更内容', {'fields': ['old_value', 'new_value']}),
        ('状态信息', {'fields': ['status']}),
        ('审核信息', {'fields': ['approved_by', 'approved_time', 'executed_time']}),
    ]


@admin.register(ProductionLineDayPlan)
class ProductionLineDayPlanAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'production_line', 'plan_date',
                    'production_plan', 'quantity', 'completed_quantity',
                    'status', 'create_time']
    list_filter = ['production_line', 'status', 'plan_date']
    search_fields = ['code', 'name', 'description']
    fieldsets = [
        ('基本信息', {'fields': ['name', 'code', 'production_line', 'plan_date']}),
        ('计划信息', {'fields': ['production_plan', 'quantity']}),
        ('完成信息', {'fields': ['completed_quantity', 'status']}),
        ('描述信息', {'fields': ['description']}),
    ]
    readonly_fields = ['completed_quantity']


@admin.register(MaterialRequest)
class MaterialRequestAdmin(admin.ModelAdmin):
    list_display = ['code', 'production_plan', 'request_date', 'requested_by',
                    'status', 'total_amount', 'create_time']
    list_filter = ['status', 'request_date']
    search_fields = ['code', 'description']
    inlines = [MaterialRequestItemInline]
    fieldsets = [
        ('基本信息', {'fields': ['production_plan', 'production_task', 
                                  'code', 'request_date']}),
        ('状态信息', {'fields': ['requested_by', 'status']}),
        ('金额信息', {'fields': ['total_amount']}),
        ('描述信息', {'fields': ['description']}),
    ]
    readonly_fields = ['total_amount']


@admin.register(MaterialIssue)
class MaterialIssueAdmin(admin.ModelAdmin):
    list_display = ['code', 'material_request', 'production_plan', 'issue_date',
                    'issued_by', 'status', 'total_amount', 'create_time']
    list_filter = ['status', 'issue_date']
    search_fields = ['code', 'description']
    inlines = [MaterialIssueItemInline]
    fieldsets = [
        ('基本信息', {'fields': ['code', 'material_request', 'production_plan',
                                  'issue_date']}),
        ('状态信息', {'fields': ['issued_by', 'status']}),
        ('金额信息', {'fields': ['total_amount']}),
        ('描述信息', {'fields': ['description']}),
    ]
    readonly_fields = ['total_amount']


@admin.register(MaterialReturn)
class MaterialReturnAdmin(admin.ModelAdmin):
    list_display = ['code', 'material_issue', 'production_plan', 'return_date',
                    'returned_by', 'status', 'total_amount', 'create_time']
    list_filter = ['status', 'return_date']
    search_fields = ['return_reason']
    inlines = [MaterialReturnItemInline]
    fieldsets = [
        ('基本信息', {'fields': ['code', 'material_issue', 'production_plan',
                                  'return_date']}),
        ('状态信息', {'fields': ['returned_by', 'status']}),
        ('金额信息', {'fields': ['total_amount']}),
        ('退料原因', {'fields': ['return_reason']}),
    ]
    readonly_fields = ['total_amount']


@admin.register(WorkCompletionReport)
class WorkCompletionReportAdmin(admin.ModelAdmin):
    list_display = ['code', 'production_task', 'report_date', 'reported_by',
                    'status', 'reported_quantity', 'qualified_quantity', 
                    'create_time']
    list_filter = ['status', 'report_date']
    search_fields = ['code', 'remarks']
    fieldsets = [
        ('基本信息', {'fields': ['code', 'production_task', 'report_date']}),
        ('数量信息', {'fields': ['reported_quantity', 'qualified_quantity',
                                  'defective_quantity']}),
        ('状态信息', {'fields': ['reported_by', 'status']}),
        ('工时信息', {'fields': ['work_hours']}),
        ('资源消耗', {'fields': ['resource_consumption']}),
        ('备注信息', {'fields': ['remarks']}),
    ]
    readonly_fields = ['reported_quantity', 'qualified_quantity', 
                       'defective_quantity']


@admin.register(WorkCompletionRedFlush)
class WorkCompletionRedFlushAdmin(admin.ModelAdmin):
    list_display = ['code', 'completion_report', 'red_flush_date',
                    'requested_by', 'status', 'red_flush_quantity', 
                    'create_time']
    list_filter = ['status', 'red_flush_date']
    search_fields = ['red_flush_reason']
    fieldsets = [
        ('基本信息', {'fields': ['code', 'completion_report', 'red_flush_date']}),
        ('红冲信息', {'fields': ['red_flush_reason', 'red_flush_quantity']}),
        ('状态信息', {'fields': ['requested_by', 'status']}),
        ('审核信息', {'fields': ['approved_by', 'approved_time', 'executed_time']}),
    ]
    readonly_fields = ['red_flush_quantity']


@admin.register(ProductReceipt)
class ProductReceiptAdmin(admin.ModelAdmin):
    list_display = ['code', 'production_plan', 'receipt_date', 'received_by',
                    'status', 'receipt_quantity', 'storage_location', 
                    'create_time']
    list_filter = ['status', 'receipt_date']
    search_fields = ['code', 'remarks']
    fieldsets = [
        ('基本信息', {'fields': ['code', 'completion_report', 'production_plan',
                                  'receipt_date']}),
        ('入库信息', {'fields': ['receipt_quantity', 'storage_location']}),
        ('状态信息', {'fields': ['received_by', 'status']}),
        ('备注信息', {'fields': ['remarks']}),
    ]
    readonly_fields = ['receipt_quantity']


@admin.register(OrderMaterialConfirmation)
class OrderMaterialConfirmationAdmin(admin.ModelAdmin):
    list_display = ['production_plan', 'material_issue', 'confirmed_quantity',
                    'confirmed_by', 'confirm_time']
    list_filter = ['confirm_time']
    search_fields = ['remarks']
    fieldsets = [
        ('确认信息', {'fields': ['production_plan', 'material_issue',
                                  'confirmed_quantity']}),
        ('审核信息', {'fields': ['confirmed_by', 'confirm_time']}),
        ('备注信息', {'fields': ['remarks']}),
    ]
    readonly_fields = ['confirmed_quantity', 'confirm_time']


@admin.register(ResourceConsumption)
class ResourceConsumptionAdmin(admin.ModelAdmin):
    list_display = ['production_task', 'resource_type', 'resource_name',
                    'consumed_quantity', 'unit', 'cost', 'consumption_time']
    list_filter = ['resource_type', 'consumption_time']
    search_fields = ['resource_name']
    fieldsets = [
        ('基本信息', {'fields': ['production_task', 'resource_type', 
                                  'resource_name']}),
        ('消耗信息', {'fields': ['consumed_quantity', 'unit', 'cost']}),
        ('时间信息', {'fields': ['consumption_time']}),
    ]
    readonly_fields = ['consumption_time']


@admin.register(ProductionDataPoint)
class ProductionDataPointAdmin(admin.ModelAdmin):
    list_display = ['equipment', 'metric_name', 'metric_value', 'metric_unit',
                    'timestamp', 'quality', 'confidence']
    list_filter = ['equipment', 'metric_name', 'timestamp']
    search_fields = ['metric_name', 'tags']
    fieldsets = [
        ('基本信息', {'fields': ['equipment', 'metric_name', 'metric_value',
                                  'metric_unit']}),
        ('时间信息', {'fields': ['timestamp', 'collection_time']}),
        ('质量信息', {'fields': ['quality', 'confidence']}),
        ('关联信息', {'fields': ['data_source', 'collection', 'task', 'procedure']}),
        ('附加信息', {'fields': ['tags', 'metadata']}),
    ]


@admin.register(DataCollectionTask)
class DataCollectionTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'task_type', 'status', 'cron_expression',
                    'interval_seconds', 'is_active', 'last_run_time',
                    'next_run_time']
    list_filter = ['task_type', 'status', 'is_active', 'create_time']
    search_fields = ['name']
    fieldsets = [
        ('基本信息', {'fields': ['name', 'task_type']}),
        ('调度配置', {'fields': ['cron_expression', 'interval_seconds']}),
        ('执行配置', {'fields': ['max_retries', 'timeout_seconds']}),
        ('状态信息', {'fields': ['status', 'is_active']}),
        ('执行统计', {'fields': ['last_run_time', 'next_run_time', 'total_runs',
                                  'success_runs', 'failed_runs']}),
    ]
