"""
权限装饰器模块
提供多种权限检查装饰器和工具函数
"""

from .permission_decorators import (
    PermissionRequiredMixin,
    permission_required,
    permission_required_any,
    staff_required,
    department_required,
    check_permission,
    get_user_permissions,
    filter_queryset_by_permissions,
    data_isolation,
    button_permission_required,
    _normalize_permission,
    DATA_PERMISSION_CACHE_TIMEOUT,
    PERMISSION_CACHE_TIMEOUT,
    MENU_CACHE_TIMEOUT,
)

__all__ = [
    'PermissionRequiredMixin',
    'permission_required',
    'permission_required_any',
    'staff_required',
    'department_required',
    'check_permission',
    'get_user_permissions',
    'filter_queryset_by_permissions',
    'data_isolation',
    'button_permission_required',
    '_normalize_permission',
    'DATA_PERMISSION_CACHE_TIMEOUT',
    'PERMISSION_CACHE_TIMEOUT',
    'MENU_CACHE_TIMEOUT',
]
