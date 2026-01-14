from django.urls import path
from apps.system.views.service_config_views import (
    ServiceConfigListView,
    ServiceConfigDetailView,
    ServiceConfigFormView,
    ServiceConfigUpdateView,
    ServiceConfigDeleteView,
    service_config_toggle,
    service_config_test,
    get_providers_by_category,
)

urlpatterns = [
    path('', ServiceConfigListView.as_view(), name='service_config_list'),
    path('add/', ServiceConfigFormView.as_view(), name='service_config_add'),
    path('<int:pk>/', ServiceConfigDetailView.as_view(), name='service_config_detail'),
    path('<int:pk>/edit/', ServiceConfigUpdateView.as_view(), name='service_config_edit'),
    path('<int:pk>/delete/', ServiceConfigDeleteView.as_view(), name='service_config_delete'),
    path('toggle/', service_config_toggle, name='service_config_toggle'),
    path('test/', service_config_test, name='service_config_test'),
    path('<int:pk>/test/', service_config_test, name='service_config_test_single'),
    path('providers/', get_providers_by_category, name='service_config_providers'),
]
