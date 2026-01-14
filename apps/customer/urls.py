from django.urls import path, include
from . import views, ai_views

app_name = 'customer'
urlpatterns = [
    # 客户管理路由
    path('', views.CustomerListView.as_view(), name='customer_list'),
    path('simple/', views.CustomerListSimpleView.as_view(), name='customer_list_simple'),
    path('list/data/', views.CustomerListDataView.as_view(), name='customer_list_data'),
    path('create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('edit/<int:pk>/', views.CustomerUpdateView.as_view(), name='customer_edit'),
    path('detail/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('detail-api/<int:pk>/', views.CustomerDetailApiView.as_view(), name='customer_detail_api'),
    path('delete/<int:pk>/', views.CustomerDeleteView.as_view(), name='customer_delete'),
    path('batch/import/', views.CustomerBatchImportView.as_view(), name='customer_batch_import'),
    path('batch/delete/', views.CustomerBatchDeleteView.as_view(), name='customer_batch_delete'),
    path('download/template/', views.download_template, name='download_template'),
    path('upload/import/file/', views.upload_import_file, name='upload_import_file'),
    path('process/import/', views.process_import, name='process_import'),
    path('import/progress/', views.import_progress, name='import_progress'),
    
    # 客户字段管理路由
    path('field/', views.customer_field_page, name='customer_field_page'),
    path('field/list/', views.customer_field_list, name='customer_field_list'),
    path('field/list/data/', views.customer_field_list_data, name='customer_field_list_data'),
    path('field/form/', views.customer_field_form, name='customer_field_form'),
    path('field/form/<int:pk>/', views.customer_field_form, name='customer_field_form_edit'),
    path('field/delete/<int:pk>/', views.customer_field_delete, name='customer_field_delete'),
    path('field/toggle/<int:pk>/', views.customer_field_toggle, name='customer_field_toggle'),
    
    # 客户来源管理路由
    path('source/list/', views.customer_source_list, name='customer_source_list'),
    path('source/list/data/', views.customer_source_list_data, name='customer_source_list_data'),
    path('source/form/', views.customer_source_form, name='customer_source_form'),
    path('source/form/<int:pk>/', views.customer_source_form, name='customer_source_form_edit'),
    path('source/delete/<int:pk>/', views.customer_source_delete, name='customer_source_delete'),
    path('source/toggle/<int:pk>/', views.customer_source_toggle, name='customer_source_toggle'),
    
    # 客户等级管理路由
    path('grade/list/', views.customer_grade_list, name='customer_grade_list'),
    path('grade/list/data/', views.customer_grade_list_data, name='customer_grade_list_data'),
    path('grade/form/', views.customer_grade_form, name='customer_grade_form'),
    path('grade/form/<int:pk>/', views.customer_grade_form, name='customer_grade_form_edit'),
    path('grade/delete/<int:pk>/', views.customer_grade_delete, name='customer_grade_delete'),
    path('grade/toggle/<int:pk>/', views.customer_grade_toggle, name='customer_grade_toggle'),
    
    # 客户意向管理路由
    path('intent/list/', views.customer_intent_list, name='customer_intent_list'),
    path('intent/list/data/', views.customer_intent_list_data, name='customer_intent_list_data'),
    path('intent/form/', views.customer_intent_form, name='customer_intent_form'),
    path('intent/form/<int:pk>/', views.customer_intent_form, name='customer_intent_form_edit'),
    path('intent/delete/<int:pk>/', views.customer_intent_delete, name='customer_intent_delete'),
    path('intent/toggle/<int:pk>/', views.customer_intent_toggle, name='customer_intent_toggle'),
    path('intent/update-sort/<int:pk>/', views.customer_intent_update_sort, name='customer_intent_update_sort'),
    path('intent/batch-update-sort/', views.customer_intent_batch_update_sort, name='customer_intent_batch_update_sort'),
    
    # 跟进字段管理路由
    path('follow/field/list/', views.follow_field_list, name='follow_field_list'),
    path('follow/field/list/data/', views.follow_field_list_data, name='follow_field_list_data'),
    path('follow/field/form/', views.follow_field_form, name='follow_field_form'),
    path('follow/field/form/<int:pk>/', views.follow_field_form, name='follow_field_form_edit'),
    path('follow/field/add/', views.follow_field_form, name='follow_field_add'),
    path('follow/field/sync/', views.follow_field_sync, name='follow_field_sync'),
    path('follow/field/toggle/<int:pk>/', views.follow_field_toggle, name='follow_field_toggle'),
    path('follow/field/delete/<int:pk>/', views.follow_field_delete, name='follow_field_delete'),
    
    # 订单字段管理路由
    path('order/field/list/', views.order_field_list, name='order_field_list'),
    path('order/field/list/data/', views.order_field_list_data, name='order_field_list_data'),
    path('order/field/form/', views.order_field_form, name='order_field_form'),
    path('order/field/form/<int:pk>/', views.order_field_form, name='order_field_form_edit'),
    path('order/field/toggle/<int:pk>/', views.order_field_toggle, name='order_field_toggle'),
    path('order/field/delete/<int:pk>/', views.order_field_delete, name='order_field_delete'),
    path('order/field/sync/', views.order_field_sync, name='order_field_sync'),
    
    # 公海客户管理
    path('public/list/', views.PublicCustomerListView.as_view(), name='public_customer_list'),
    path('public/list/data/', views.PublicCustomerListDataView.as_view(), name='public_customer_list_data'),
    path('public/ai-robot/', views.AIRobotView.as_view(), name='ai_robot'),
    path('public/ai-robot/data/', views.AIRobotDataView.as_view(), name='ai_robot_data'),
    
    # 爬虫任务管理
    path('spider_task/', views.SpiderTaskListView.as_view(), name='spider_task_list'),
    path('spider_task/data/', views.SpiderTaskListDataView.as_view(), name='spider_task_list_data'),
    path('spider_task/create/', views.SpiderTaskCreateView.as_view(), name='spider_task_create'),
    path('spider_task/<int:pk>/edit/', views.SpiderTaskUpdateView.as_view(), name='spider_task_edit'),
    path('spider_task/<int:pk>/delete/', views.SpiderTaskDeleteView.as_view(), name='spider_task_delete'),
    path('spider_task/<int:pk>/action/', views.SpiderTaskActionView.as_view(), name='spider_task_action'),
    path('spider_task/batch/delete/', views.SpiderTaskBatchDeleteView.as_view(), name='spider_task_batch_delete'),
    
    # 废弃客户管理
    path('abandoned/list/', views.AbandonedCustomerListView.as_view(), name='abandoned_customer_list'),
    path('abandoned/list/data/', views.AbandonedCustomerListDataView.as_view(), name='abandoned_customer_list_data'),
    
    # 客户订单管理
    path('orders/', views.CustomerOrderListView.as_view(), name='customer_order_list'),
    path('orders/data/', views.CustomerOrderListDataView.as_view(), name='customer_order_list_data'),
    path('orders/create/', views.CustomerOrderCreateView.as_view(), name='customer_order_create'),
    path('orders/<int:pk>/edit/', views.CustomerOrderUpdateView.as_view(), name='customer_order_edit'),
    path('orders/<int:pk>/detail/', views.CustomerOrderDetailView.as_view(), name='customer_order_detail'),
    path('orders/<int:pk>/delete/', views.CustomerOrderDeleteView.as_view(), name='customer_order_delete'),
    path('orders/<int:pk>/payment/', views.CustomerOrderPaymentView.as_view(), name='customer_order_payment'),
    path('orders/batch/delete/', views.CustomerOrderBatchDeleteView.as_view(), name='customer_order_batch_delete'),
    
    # 机会线索管理
    path('opportunity/', views.OpportunityListView.as_view(), name='opportunity_list'),
    path('opportunity/data/', views.OpportunityListDataView.as_view(), name='opportunity_list_data'),
    
    # 跟进记录管理
    path('followup/', views.FollowRecordListView.as_view(), name='follow_record_list'),
    path('followup/data/', views.FollowRecordListDataView.as_view(), name='follow_record_list_data'),
    path('followup/create/', views.FollowRecordCreateView.as_view(), name='follow_record_create'),
    path('followup/<int:pk>/edit/', views.FollowRecordUpdateView.as_view(), name='follow_record_edit'),
    
    # 合同管理
    path('contract/create/', views.ContractAddView.as_view(), name='customer_contract_create'),
    path('contract/check_number/', views.ContractNumberCheckView.as_view(), name='contract_number_check'),
    path('contract/generate_number/', views.ContractNumberGenerateView.as_view(), name='contract_number_generate'),
    path('contract/list/<int:customer_id>/', views.CustomerContractListView.as_view(), name='customer_contract_list'),
    
    # 拨号记录管理
    path('callrecord/', views.CallRecordListView.as_view(), name='call_record_list'),
    path('callrecord/data/', views.CallRecordListDataView.as_view(), name='call_record_list_data'),
    path('sip/call/', views.sip_call, name='sip_call'),
    path('call/status/update/', views.update_call_status, name='update_call_status'),
    
    # AI分析功能
    path('ai/classify/<int:customer_id>/', ai_views.ai_customer_classification, name='ai_customer_classification'),
    path('ai/profile/<int:customer_id>/', ai_views.ai_customer_profile, name='ai_customer_profile'),
    
    # 客户选择功能（用于其他模块选择客户）
    path('select/', views.CustomerSelectView.as_view(), name='customer_select'),
    
    # 客户协同功能
    path('get_shared_employees/<int:customer_id>/', views.get_shared_employees, name='get_shared_employees'),
    path('set_customer_share/<int:customer_id>/', views.set_customer_share, name='set_customer_share'),
    
    # 公海客户认领
    path('public/claim/<int:customer_id>/', views.claim_public_customer, name='claim_public_customer'),
    
    # 客户移入废弃列表
    path('discard/<int:customer_id>/', views.discard_customer, name='discard_customer'),
    
    # 废弃客户恢复
    path('restore/<int:customer_id>/', views.restore_customer, name='restore_customer'),
    
    # 废弃客户清理
    path('clean_abandoned/', views.clean_abandoned_customers, name='clean_abandoned_customers'),
    
    # 自动将长期未跟进客户移入公海
    path('auto_move_to_public/', views.auto_move_to_public_pool, name='auto_move_to_public_pool'),
]

# 员工列表URL，用于客户共享选择
from django.urls import path
urlpatterns += [
    path('employee_list/', views.get_employee_list, name='employee_list'),
]