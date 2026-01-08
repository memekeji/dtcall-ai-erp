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
]
