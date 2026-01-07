from django.urls import path, include
from django.shortcuts import redirect
from .views import admin_views, department_views, menu_views, log_views, group_views
from .views.group_permission_view import GroupPermissionView, MenuPermissionsAPIView
from .views.department_role_views import DepartmentRoleManagementView, DepartmentRoleListAPIView
from .views.employee_views import (
    EmployeeListView, EmployeeDetailView, EmployeeCreateView, EmployeeUpdateView, EmployeeDeleteView,
    EmployeeListAPIView, EmployeeFileView, EmployeeTransferListView, EmployeeDimissionListView,
    RewardPunishmentListView, RewardPunishmentCreateView, RewardPunishmentUpdateView, RewardPunishmentDeleteView,
    EmployeeCareListView, EmployeeCareCreateView, EmployeeCareUpdateView, EmployeeCareDeleteView,
    EmployeeContractListView, EmployeeContractDetailView, EmployeeContractCreateView,
    EmployeeContractUpdateView, EmployeeContractDeleteView
)
from .views.admin_views import ResetPasswordView, ChangeStatusView
from .views.employee_views import EmployeeCenterView, EmployeeCenterUpdateView

app_name = 'user'

urlpatterns = [
    # 菜单管理
    path('menu/', menu_views.MenuListAPIView.as_view(), name='menu_list'),
    path('menu/<int:pk>/', menu_views.MenuDetailAPIView.as_view(), name='menu_detail'),
    path('menu/<int:menu_id>/permissions/', MenuPermissionsAPIView.as_view(), name='menu_permissions'),
    
    # 验证码
    path('captcha/', include('captcha.urls')),
    
    # 统一员工管理路由
    path('employee/', EmployeeListView.as_view(), name='employee_list'),
    path('employee/detail/<int:pk>/', EmployeeDetailView.as_view(), name='employee_detail'),
    path('employee/create/', EmployeeCreateView.as_view(), name='employee_create'),
    path('employee/update/<int:pk>/', EmployeeUpdateView.as_view(), name='employee_update'),
    path('employee/delete/', EmployeeDeleteView.as_view(), name='employee_delete'),
    
    # 员工专项管理
    path('employee/<int:pk>/file/', EmployeeFileView.as_view(), name='employee_file'),
    path('employee/transfer/', EmployeeTransferListView.as_view(), name='employee_transfer_list'),
    path('employee/dimission/', EmployeeDimissionListView.as_view(), name='employee_dimission_list'),
    
    # 奖惩管理
    path('reward-punishment/', RewardPunishmentListView.as_view(), name='reward_punishment_list'),
    path('reward-punishment/add/', RewardPunishmentCreateView.as_view(), name='reward_punishment_add'),
    path('reward-punishment/<int:pk>/edit/', RewardPunishmentUpdateView.as_view(), name='reward_punishment_edit'),
    path('reward-punishment/<int:pk>/delete/', RewardPunishmentDeleteView.as_view(), name='reward_punishment_delete'),
    
    # 员工关怀管理
    path('employee-care/', EmployeeCareListView.as_view(), name='employee_care_list'),
    path('employee-care/add/', EmployeeCareCreateView.as_view(), name='employee_care_add'),
    path('employee-care/<int:pk>/edit/', EmployeeCareUpdateView.as_view(), name='employee_care_edit'),
    path('employee-care/<int:pk>/delete/', EmployeeCareDeleteView.as_view(), name='employee_care_delete'),
    
    # 员工合同管理
    path('employee-contract/', EmployeeContractListView.as_view(), name='employee_contract_list'),
    path('employee-contract/add/', EmployeeContractCreateView.as_view(), name='employee_contract_add'),
    path('employee-contract/<int:pk>/', EmployeeContractDetailView.as_view(), name='employee_contract_detail'),
    path('employee-contract/<int:pk>/edit/', EmployeeContractUpdateView.as_view(), name='employee_contract_edit'),
    path('employee-contract/<int:pk>/delete/', EmployeeContractDeleteView.as_view(), name='employee_contract_delete'),
    
    # 保持向后兼容的API路由
    path('admin/list/', EmployeeListAPIView.as_view(), name='admin_list'),
    path('admin/detail/<int:pk>/', EmployeeDetailView.as_view(), name='admin_detail'),
    path('admin/create/', EmployeeCreateView.as_view(), name='admin_create'),
    path('admin/update/<int:pk>/', EmployeeUpdateView.as_view(), name='admin_update'),
    path('admin/delete/', EmployeeDeleteView.as_view(), name='admin_delete'),
    
    # 部门管理
    path('department/', department_views.DepartmentListView.as_view(), name='department_list'),
    path('department/<int:pk>/', department_views.DepartmentDetailAPIView.as_view(), name='department_detail'),
    # 部门角色管理
    path('department/<int:department_id>/roles/', DepartmentRoleManagementView.as_view(), name='department_role_management'),
    path('department/<int:department_id>/roles/list/', DepartmentRoleListAPIView.as_view(), name='department_role_list'),
    
    # 角色管理
    path('group/', group_views.RoleListView.as_view(), name='group_list'),
    path('group/api/', group_views.GroupListAPIView.as_view(), name='group_list_api'),
    path('group/<int:pk>/', group_views.GroupDetailAPIView.as_view(), name='group_detail'),
    path('group/<int:pk>/update/', group_views.GroupUpdateView.as_view(), name='group_update'),
    path('group/<int:pk>/toggle-status/', group_views.GroupStatusToggleView.as_view(), name='group_toggle_status'),
    path('group/<int:pk>/permission/', GroupPermissionView.as_view(), name='group_permission'),
    # 获取所有角色（权限组）数据
    path('group/all/', group_views.GetGroupsAPIView.as_view(), name='get_all_groups'),
    
    # 日志管理
    path('log/', log_views.LogListAPIView.as_view(), name='log_list'),
    path('log/<int:pk>/', log_views.LogDetailAPIView.as_view(), name='log_detail'),
    
    # 重定向到员工管理首页
    path('admin/index/', lambda request: redirect('/user/employee/')),
    
    # 保留原有登录相关路由
    path('login/', admin_views.login_view, name='login'),
    path('login-submit/', admin_views.login_submit, name='login-submit'),
    path('logout/', admin_views.logout_view, name='logout'),
    
    # 个人中心路由
    path('center/', EmployeeCenterView.as_view(), name='employee_center'),
    path('center/update/', EmployeeCenterUpdateView.as_view(), name='employee_center_update'),
    
    # 密码重置和状态变更API
    path('employee/<int:pk>/reset-password/', ResetPasswordView.as_view(), name='employee_reset_password'),
    path('employee/<int:pk>/change-status/', ChangeStatusView.as_view(), name='employee_change_status'),
]