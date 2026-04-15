from django.urls import path
from . import views, dashboard_views

app_name = 'home'

urlpatterns = [
    path('main/', views.main, name='main'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # 各种数据大屏
    path(
        'dashboard/finance/',
        dashboard_views.finance_dashboard,
        name='finance_dashboard'),
    path(
        'dashboard/business/',
        dashboard_views.business_dashboard,
        name='business_dashboard'),
    path(
        'dashboard/production/',
        dashboard_views.production_dashboard,
        name='production_dashboard'),
]
