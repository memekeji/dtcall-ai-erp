from django.urls import path
from apps.system.views.storage_config_views import (
    StorageConfigListView,
    StorageConfigFormView,
    StorageConfigDeleteView,
    StorageConfigTestView,
    StorageConfigSetDefaultView,
    StorageConfigToggleStatusView,
    StorageConfigTestFormView,
)

urlpatterns = [
    path('', StorageConfigListView.as_view(), name='storage_config_list'),
    path('add/', StorageConfigFormView.as_view(), name='storage_config_add'),
    path(
        '<int:pk>/',
        StorageConfigFormView.as_view(),
        name='storage_config_edit'),
    path(
        '<int:pk>/delete/',
        StorageConfigDeleteView.as_view(),
        name='storage_config_delete'),
    path(
        '<int:pk>/test/',
        StorageConfigTestView.as_view(),
        name='storage_config_test'),
    path(
        'test/',
        StorageConfigTestFormView.as_view(),
        name='storage_config_test_form'),
    path(
        '<int:pk>/set_default/',
        StorageConfigSetDefaultView.as_view(),
        name='storage_config_set_default'),
    path('<int:pk>/toggle_status/',
         StorageConfigToggleStatusView.as_view(),
         name='storage_config_toggle_status'),
]
