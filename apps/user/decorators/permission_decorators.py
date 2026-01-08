"""
权限装饰器模块
提供多种权限检查装饰器用于视图函数
"""

from functools import wraps
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger('django')


class PermissionRequiredMixin:
    """
    类视图权限检查Mixin
    使用方式:
        class MyView(PermissionRequiredMixin, View):
            permission_required = 'user.view_notice'
            # 或者多个权限
            # permission_required = ['user.view_notice', 'user.add_notice']
    """
    
    permission_required = None
    
    def get_permission_required(self):
        """获取权限要求，可以被子类重写"""
        return self.permission_required
    
    def has_permission(self, request):
        """检查用户是否有权限"""
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        perm_required = self.get_permission_required()
        if not perm_required:
            return True
        
        if isinstance(perm_required, (list, tuple)):
            return any(request.user.has_perm(perm) for perm in perm_required)
        
        return request.user.has_perm(perm_required)
    
    def dispatch(self, request, *args, **kwargs):
        if not self.has_permission(request):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'code': 403,
                    'msg': '您没有权限执行此操作'
                })
            raise PermissionDenied('您没有权限执行此操作')
        return super().dispatch(request, *args, **kwargs)


def permission_required(permission, login_url=None):
    """
    函数视图权限检查装饰器
    使用方式:
        @permission_required('user.view_notice')
        def my_view(request):
            ...
    
    支持多个权限（用户需要拥有所有权限）:
        @permission_required(['user.view_notice', 'user.add_notice'])
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if login_url:
                    from django.shortcuts import redirect
                    return redirect(login_url)
                return JsonResponse({
                    'code': 401,
                    'msg': '请先登录'
                }, status=401)
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if isinstance(permission, (list, tuple)):
                has_all = all(request.user.has_perm(perm) for perm in permission)
                if not has_all:
                    logger.warning(
                        f"用户 {request.user.username} 缺少权限: {permission}"
                    )
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'code': 403,
                            'msg': '您没有权限执行此操作'
                        }, status=403)
                    raise PermissionDenied('您没有权限执行此操作')
            else:
                if not request.user.has_perm(permission):
                    logger.warning(
                        f"用户 {request.user.username} 缺少权限: {permission}"
                    )
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'code': 403,
                            'msg': '您没有权限执行此操作'
                        }, status=403)
                    raise PermissionDenied('您没有权限执行此操作')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def permission_required_any(*permissions):
    """
    函数视图权限检查装饰器（用户拥有任一权限即可）
    使用方式:
        @permission_required_any('user.view_notice', 'user.add_notice')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({
                    'code': 401,
                    'msg': '请先登录'
                }, status=401)
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            has_any = any(request.user.has_perm(perm) for perm in permissions)
            if not has_any:
                logger.warning(
                    f"用户 {request.user.username} 缺少以下任一权限: {permissions}"
                )
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'code': 403,
                        'msg': '您没有权限执行此操作'
                    }, status=403)
                raise PermissionDenied('您没有权限执行此操作')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def staff_required(view_func):
    """
    装饰器：检查用户是否为员工（is_staff）
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'code': 401,
                'msg': '请先登录'
            }, status=401)
        
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({
                'code': 403,
                'msg': '仅员工可访问此功能'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    return wrapper


def department_required(department_field='department'):
    """
    装饰器：检查用户是否属于指定部门
    使用方式:
        @department_required('department')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({
                    'code': 401,
                    'msg': '请先登录'
                }, status=401)
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            user_department = getattr(request.user, 'employee', None)
            if not user_department or not hasattr(user_department, department_field):
                return JsonResponse({
                    'code': 403,
                    'msg': '您不属于任何部门'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def check_permission(request, permission_code):
    """
    检查用户是否拥有指定权限的便捷函数
    
    Args:
        request: HTTP请求对象
        permission_code: 权限代码（如 'view_notice' 或 'user.view_notice'）
    
    Returns:
        bool: 用户是否拥有权限
    """
    if not request.user.is_authenticated:
        return False
    
    if request.user.is_superuser:
        return True
    
    full_perm = permission_code
    if '.' not in full_perm:
        full_perm = f'user.{permission_code}'
    
    return request.user.has_perm(full_perm)


def get_user_permissions(user):
    """
    获取用户所有权限的便捷函数
    
    Args:
        user: 用户对象
    
    Returns:
        set: 权限codename集合
    """
    if not user or not user.is_authenticated:
        return set()
    
    if user.is_superuser:
        from apps.user.config.permission_nodes import get_all_permission_codenames
        return set(get_all_permission_codenames())
    
    permissions = set()
    for perm in user.user_permissions.all():
        permissions.add(perm.codename)
    
    for group in user.groups.all():
        for perm in group.permissions.all():
            permissions.add(perm.codename)
    
    return permissions


def filter_queryset_by_permissions(user, queryset, permission_code, field_name='created_by'):
    """
    根据用户权限过滤Queryset
    
    Args:
        user: 用户对象
        queryset: 待过滤的Queryset
        permission_code: 权限代码
        field_name: 用于检查的字段名
    
    Returns:
        Queryset: 过滤后的Queryset
    """
    if not user or not user.is_authenticated:
        return queryset.none()
    
    if user.is_superuser:
        return queryset
    
    if check_permission(user, permission_code):
        return queryset
    
    return queryset.filter(**{field_name: user})
