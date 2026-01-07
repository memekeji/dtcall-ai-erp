from django.urls import path
from . import views

app_name = 'production'

urlpatterns = [
    # 基础信息模块
    path('baseinfo/', views.baseinfo_index, name='baseinfo_index'),
    path('procedure/', views.procedure_list, name='procedure_list'),
    path('procedure/add/', views.procedure_add, name='procedure_add'),
    path('procedure/edit/<int:pk>/', views.procedure_edit, name='procedure_edit'),
    path('procedure/delete/<int:pk>/', views.procedure_delete, name='procedure_delete'),
    
    path('procedureset/', views.procedureset_list, name='procedureset_list'),
    path('procedureset/add/', views.procedureset_add, name='procedureset_add'),
    path('procedureset/edit/<int:pk>/', views.procedureset_edit, name='procedureset_edit'),
    path('procedureset/delete/<int:pk>/', views.procedureset_delete, name='procedureset_delete'),
    
    path('bom/', views.bom_list, name='bom_list'),
    path('bom/add/', views.bom_add, name='bom_add'),
    path('bom/edit/<int:pk>/', views.bom_edit, name='bom_edit'),
    path('bom/delete/<int:pk>/', views.bom_delete, name='bom_delete'),
    path('bom/detail/<int:pk>/', views.bom_detail, name='bom_detail'),
    
    path('equipment/', views.equipment_list, name='equipment_list'),
    path('equipment/add/', views.equipment_add, name='equipment_add'),
    path('equipment/edit/<int:pk>/', views.equipment_edit, name='equipment_edit'),
    path('equipment/delete/<int:pk>/', views.equipment_delete, name='equipment_delete'),
    path('equipment/detail/<int:pk>/', views.equipment_detail, name='equipment_detail'),
    path('equipment/monitor/', views.equipment_monitor, name='equipment_monitor'),
    
    # 数据采集模块
    path('data/', views.data_collection_list, name='data_collection_list'),
    path('data/add/', views.data_collection_add, name='data_collection_add'),
    path('data/chart/<int:equipment_id>/', views.data_chart, name='data_chart'),
    
    # 数据源管理
    path('data/source/', views.data_source_list, name='data_source_list'),
    path('data/source/add/', views.data_source_add, name='data_source_add'),
    path('data/source/<int:pk>/', views.data_source_detail, name='data_source_detail'),
    path('data/source/<int:pk>/edit/', views.data_source_edit, name='data_source_edit'),
    path('data/source/<int:pk>/delete/', views.data_source_delete, name='data_source_delete'),
    path('data/source/<int:pk>/test/', views.data_source_test, name='data_source_test'),
    
    # 数据映射管理
    path('data/mapping/', views.data_mapping_list, name='data_mapping_list'),
    path('data/mapping/add/', views.data_mapping_add, name='data_mapping_add'),
    path('data/mapping/<int:pk>/edit/', views.data_mapping_edit, name='data_mapping_edit'),
    path('data/mapping/<int:pk>/delete/', views.data_mapping_delete, name='data_mapping_delete'),
    
    # 数据采集记录
    path('data/record/', views.data_collection_record_list, name='data_collection_record_list'),
    path('data/record/<int:pk>/', views.data_collection_record_detail, name='data_collection_record_detail'),
    
    # 生产数据点
    path('data/point/', views.data_point_list, name='data_point_list'),
    
    # 数据采集任务
    path('data/task/', views.data_collection_task_list, name='data_collection_task_list'),
    path('data/task/add/', views.data_collection_task_add, name='data_collection_task_add'),
    path('data/task/<int:pk>/edit/', views.data_collection_task_edit, name='data_collection_task_edit'),
    path('data/task/<int:pk>/delete/', views.data_collection_task_delete, name='data_collection_task_delete'),
    path('data/task/<int:pk>/trigger/', views.data_collection_task_trigger, name='data_collection_task_trigger'),
    
    # SOP管理模块
    path('sop/', views.sop_list, name='sop_list'),
    path('sop/add/', views.sop_add, name='sop_add'),
    path('sop/edit/<int:pk>/', views.sop_edit, name='sop_edit'),
    path('sop/delete/<int:pk>/', views.sop_delete, name='sop_delete'),
    path('sop/detail/<int:pk>/', views.sop_detail, name='sop_detail'),
    
    # 生产计划模块
    path('task/', views.production_task_index, name='production_task_index'),
    path('task/plan/', views.production_plan_list, name='production_plan_list'),
    path('task/plan/add/', views.production_plan_add, name='production_plan_add'),
    path('task/plan/edit/<int:pk>/', views.production_plan_edit, name='production_plan_edit'),
    path('task/plan/delete/<int:pk>/', views.production_plan_delete, name='production_plan_delete'),
    path('task/plan/detail/<int:pk>/', views.production_plan_detail, name='production_plan_detail'),
    
    # 生产任务模块
    path('task/execution/', views.production_task_list, name='production_task_list'),
    path('task/execution/add/', views.production_task_add, name='production_task_add'),
    path('task/execution/edit/<int:pk>/', views.production_task_edit, name='production_task_edit'),
    path('task/execution/delete/<int:pk>/', views.production_task_delete, name='production_task_delete'),
    path('task/execution/detail/<int:pk>/', views.production_task_detail, name='production_task_detail'),
    path('task/execution/start/<int:pk>/', views.production_task_start, name='production_task_start'),
    path('task/execution/complete/<int:pk>/', views.production_task_complete, name='production_task_complete'),
    path('task/execution/quality/<int:pk>/', views.production_task_quality, name='production_task_quality'),
    path('task/execution/suspend/<int:pk>/', views.production_task_suspend, name='production_task_suspend'),
    path('task/execution/resume/<int:pk>/', views.production_task_resume, name='production_task_resume'),
    
    # 质量管理模块
    path('quality/', views.quality_check_list, name='quality_check_list'),
    path('quality/add/', views.quality_check_add, name='quality_check_add'),
    path('quality/edit/<int:pk>/', views.quality_check_edit, name='quality_check_edit'),
    path('quality/delete/<int:pk>/', views.quality_check_delete, name='quality_check_delete'),
    path('quality/detail/<int:pk>/', views.quality_check_detail, name='quality_check_detail'),
    
    # 工艺路线模块
    path('process/', views.process_route_list, name='process_route_list'),
    path('process/add/', views.process_route_add, name='process_route_add'),
    path('process/edit/<int:pk>/', views.process_route_edit, name='process_route_edit'),
    path('process/delete/<int:pk>/', views.process_route_delete, name='process_route_delete'),
    path('process/detail/<int:pk>/', views.process_route_detail, name='process_route_detail'),
    path('process/copy/<int:pk>/', views.process_route_copy, name='process_route_copy'),
    
    # 资源调度模块
    path('technology/', views.resource_scheduling, name='resource_scheduling'),
    
    # 生产订单变更
    path('order/change/', views.production_order_change_list, name='production_order_change_list'),
    path('order/change/add/', views.production_order_change_add, name='production_order_change_add'),
    path('order/change/<int:pk>/edit/', views.production_order_change_edit, name='production_order_change_edit'),
    path('order/change/<int:pk>/approve/', views.production_order_change_approve, name='production_order_change_approve'),
    path('order/change/<int:pk>/execute/', views.production_order_change_execute, name='production_order_change_execute'),
    
    # 生产线日计划
    path('line/dayplan/', views.production_line_day_plan_list, name='production_line_day_plan_list'),
    path('line/dayplan/add/', views.production_line_day_plan_add, name='production_line_day_plan_add'),
    path('line/dayplan/<int:pk>/edit/', views.production_line_day_plan_edit, name='production_line_day_plan_edit'),
    path('line/dayplan/<int:pk>/delete/', views.production_line_day_plan_delete, name='production_line_day_plan_delete'),
    
    # 领料申请
    path('material/request/', views.material_request_list, name='material_request_list'),
    path('material/request/add/', views.material_request_add, name='material_request_add'),
    path('material/request/<int:pk>/edit/', views.material_request_edit, name='material_request_edit'),
    path('material/request/<int:pk>/approve/', views.material_request_approve, name='material_request_approve'),
    path('material/request/<int:pk>/cancel/', views.material_request_cancel, name='material_request_cancel'),
    
    # 材料出库
    path('material/issue/', views.material_issue_list, name='material_issue_list'),
    path('material/issue/add/', views.material_issue_add, name='material_issue_add'),
    path('material/issue/<int:pk>/edit/', views.material_issue_edit, name='material_issue_edit'),
    path('material/issue/<int:pk>/approve/', views.material_issue_approve, name='material_issue_approve'),
    path('material/issue/<int:pk>/cancel/', views.material_issue_cancel, name='material_issue_cancel'),
    
    # 退料管理
    path('material/return/', views.material_return_list, name='material_return_list'),
    path('material/return/add/', views.material_return_add, name='material_return_add'),
    path('material/return/<int:pk>/edit/', views.material_return_edit, name='material_return_edit'),
    path('material/return/<int:pk>/approve/', views.material_return_approve, name='material_return_approve'),
    path('material/return/<int:pk>/cancel/', views.material_return_cancel, name='material_return_cancel'),
    
    # 完工申报
    path('completion/report/', views.work_completion_report_list, name='work_completion_report_list'),
    path('completion/report/add/', views.work_completion_report_add, name='work_completion_report_add'),
    path('completion/report/<int:pk>/edit/', views.work_completion_report_edit, name='work_completion_report_edit'),
    path('completion/report/<int:pk>/approve/', views.work_completion_report_approve, name='work_completion_report_approve'),
    path('completion/report/<int:pk>/red-flush/', views.work_completion_report_red_flush, name='work_completion_report_red_flush'),
    
    # 完工红冲
    path('completion/red-flush/', views.work_completion_red_flush_list, name='work_completion_red_flush_list'),
    path('completion/red-flush/add/', views.work_completion_red_flush_add, name='work_completion_red_flush_add'),
    path('completion/red-flush/<int:pk>/approve/', views.work_completion_red_flush_approve, name='work_completion_red_flush_approve'),
    path('completion/red-flush/<int:pk>/execute/', views.work_completion_red_flush_execute, name='work_completion_red_flush_execute'),
    
    # 成品入库
    path('product/receipt/', views.product_receipt_list, name='product_receipt_list'),
    path('product/receipt/add/', views.product_receipt_add, name='product_receipt_add'),
    path('product/receipt/<int:pk>/edit/', views.product_receipt_edit, name='product_receipt_edit'),
    path('product/receipt/<int:pk>/approve/', views.product_receipt_approve, name='product_receipt_approve'),
    path('product/receipt/<int:pk>/cancel/', views.product_receipt_cancel, name='product_receipt_cancel'),
    
    # 材料确认
    path('order/confirmation/', views.order_material_confirmation_list, name='order_material_confirmation_list'),
    path('order/confirmation/add/', views.order_material_confirmation_add, name='order_material_confirmation_add'),
    
    # 资源消耗
    path('resource/consumption/', views.resource_consumption_list, name='resource_consumption_list'),
    path('resource/consumption/add/', views.resource_consumption_add, name='resource_consumption_add'),
    
    # 分析报告
    path('analysis/', views.performance_analysis, name='performance_analysis'),
    
    # 首页路由
    path('', views.baseinfo_index, name='production_index'),
]
