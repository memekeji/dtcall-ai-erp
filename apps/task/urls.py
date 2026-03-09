from django.urls import path
from . import views

app_name = 'task'

urlpatterns = [
    # 任务管理路由
    path('', views.TaskListView.as_view(), name='task_list'),
    path('datalist/', views.TaskListView.as_view(), name='task_datalist'),
    path('add/', views.TaskAddView.as_view(), name='task_add'),
    path('edit/<int:task_id>/', views.TaskEditView.as_view(), name='task_edit'),
    path('delete/<int:task_id>/', views.TaskDeleteView.as_view(), name='task_delete'),
    path('detail/<int:task_id>/', views.TaskDetailView.as_view(), name='task_detail'),
    
    # 工时管理路由
    path('workhour/', views.WorkHourListView.as_view(), name='workhour_list'),
    path('workhour/datalist/', views.WorkHourListView.as_view(), name='workhour_datalist'),
    path('workhour/add/', views.WorkHourAddView.as_view(), name='workhour_add'),
    path('workhour/edit/<int:workhour_id>/', views.WorkHourEditView.as_view(), name='workhour_edit'),
    path('workhour/delete/<int:workhour_id>/', views.WorkHourDeleteView.as_view(), name='workhour_delete'),
    
    # adm前缀路由（兼容旧菜单）
    path('adm/workhour/', views.WorkHourListView.as_view(), name='workhour_list_adm'),
    path('adm/workhour/datalist/', views.WorkHourListView.as_view(), name='workhour_datalist_adm'),
    path('adm/workhour/add/', views.WorkHourAddView.as_view(), name='workhour_add_adm'),
    path('adm/workhour/edit/<int:workhour_id>/', views.WorkHourEditView.as_view(), name='workhour_edit_adm'),
    path('adm/workhour/delete/<int:workhour_id>/', views.WorkHourDeleteView.as_view(), name='workhour_delete_adm'),
    
    # 工时统计路由
    path('workhour/stats/', views.WorkHourStatsView.as_view(), name='workhour_stats'),
    path('adm/workhour/stats/', views.WorkHourStatsView.as_view(), name='workhour_stats_adm'),
]