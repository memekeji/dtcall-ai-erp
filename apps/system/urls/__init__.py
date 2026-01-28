from django.urls import path, include
from apps.system import views

app_name = 'system'

urlpatterns = [
    path('config/', views.config_list, name='config_list'),
    path('config/toggle/', views.config_toggle, name='config_toggle'),
    path('config/update/', views.config_update, name='config_update'),
    path('config/upload-logo/', views.config_upload_logo, name='config_upload_logo'),
    path('config/storage/toggle/', views.storage_config_toggle, name='storage_config_toggle'),
    path('config/storage/set_default/', views.storage_config_set_default, name='storage_config_set_default'),
    path('config/storage/delete/', views.storage_config_delete, name='storage_config_delete'),
    path('config/add/', views.config_form, name='config_add'),
    path('config/<int:pk>/edit/', views.config_form, name='config_edit'),
    
    # 功能模块
    path('module/', views.module_list, name='module_list'),
    path('module/add/', views.module_form, name='module_add'),
    path('module/<int:pk>/edit/', views.module_form, name='module_edit'),
    
    
    
    # 操作日志
    path('log/', views.log_list, name='log_list'),
    
    # 附件管理
    path('attachment/', views.attachment_list, name='attachment_list'),
    # 禁用尾随斜杠重定向，允许精确匹配文件路径
    path('attachment/<path:file_path>', views.attachment_download, name='attachment_download'),
    
    # 数据备份
    path('backup/', views.backup_list, name='backup_list'),
    path('backup/add/', views.backup_form, name='backup_add'),
    path('backup/<int:pk>/edit/', views.backup_form, name='backup_edit'),
    path('backup/<int:pk>/delete/', views.delete_backup, name='backup_delete'),
    path('backup/<int:pk>/download/', views.download_backup, name='download_backup'),
    path('backup/batch-delete/', views.batch_delete_backups, name='backup_batch_delete'),
    
    # 自动备份策略
    path('backup/policy/', views.backup_policy_list, name='backup_policy_list'),
    path('backup/policy/add/', views.backup_policy_form, name='backup_policy_add'),
    path('backup/policy/<int:pk>/edit/', views.backup_policy_form, name='backup_policy_edit'),
    path('backup/policy/<int:pk>/delete/', views.delete_backup_policy, name='backup_policy_delete'),
    path('backup/policy/<int:pk>/toggle/', views.backup_policy_toggle, name='backup_policy_toggle'),
    
    # 数据还原
    path('restore/', views.restore_list, name='restore_list'),
    path('restore/<int:pk>/', views.restore_backup, name='restore_backup'),
    
    # 定时任务
    path('task/', views.task_list, name='task_list'),
    path('task/add/', views.task_form, name='task_add'),
    path('task/<int:pk>/edit/', views.task_form, name='task_edit'),
    path('task/<int:pk>/toggle/', views.task_toggle, name='task_toggle'),
    # 菜单管理
    path('menu/', include('apps.system.urls.menu_urls')),
    # 行政办公
    path('admin_office/', include('apps.system.urls.admin_office_urls')),
    # 人事管理 - 部门页面
    path('department/', views.department_page, name='department_page'),
    
    # 存储配置
    path('storage/', include('apps.system.urls.storage_config_urls')),
    
    # 服务配置
    path('config/service/', include('apps.system.urls.service_config_urls')),
]