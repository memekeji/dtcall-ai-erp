from django.urls import path, include

app_name = 'system'

urlpatterns = [
    # 菜单管理路由 - 从adm应用迁移过来
    path('menu/', include('apps.system.urls.menu_urls')),
    
    # 系统配置路由
    path('config/', include('apps.system.urls.system_config_urls')),
    
    # 行政办公路由 - 从adm应用迁移过来
    path('admin_office/', include('apps.system.urls.admin_office_urls')),
]