from django.urls import path
from apps.system.views.system_config_views import (
    SystemConfigListView,
    SystemConfigEditView,
    SystemConfigDeleteView,
    SystemConfigAPIView,
    SystemConfigView
)

app_name = 'system_config'

urlpatterns = [
    # 系统配置页面路由
    path('config/', SystemConfigView.as_view(), name='system_config'),  # 兼容旧版本路由
    path('config/list/', SystemConfigListView.as_view(), name='system_config_list'),
    path('config/edit/', SystemConfigEditView.as_view(), name='system_config_edit'),
    path('config/delete/<int:pk>/', SystemConfigDeleteView.as_view(), name='system_config_delete'),
    
    # 系统配置API路由
    path('api/config/', SystemConfigAPIView.as_view(), name='system_config_api'),
]