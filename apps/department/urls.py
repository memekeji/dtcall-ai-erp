from django.urls import path
from . import views

urlpatterns = [
    path('add/', views.department_create, name='department_add'),
    path(
        '<int:pk>/update/',
        views.department_update,
        name='department_update'),
    path(
        '<int:pk>/detail/',
        views.department_detail,
        name='department_detail'),
    path(
        '<int:department_id>/delete/',
        views.department_delete,
        name='department_delete'),

    # API接口
    path(
        'department-list-api/',
        views.department_list_api,
        name='department_list_api'),
    path(
        'department-tree-api/',
        views.department_tree_api,
        name='department_tree_api'),
    path(
        '<int:department_id>/employees/',
        views.department_employees_api,
        name='department_employees_api'),
    path(
        'generate_code/',
        views.DepartmentCodeGenerateView.as_view(),
        name='generate_code'),
    path(
        'get_managers/',
        views.DepartmentManagersView.as_view(),
        name='get_managers'),
    path(
        'manager-phone/',
        views.ManagerPhoneView.as_view(),
        name='manager_phone'),
    path(
        'manager-select/',
        views.ManagerSelectView.as_view(),
        name='manager_select'),

    # 部门状态管理
    path('<int:department_id>/change_status/',
         views.DepartmentChangeStatusView.as_view(),
         name='department_change_status'),

    # 列表页放在最后，避免与其他路径冲突
    path('', views.DepartmentListView.as_view(), name='department_list'),
]
