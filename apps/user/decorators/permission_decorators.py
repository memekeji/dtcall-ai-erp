"""
权限装饰器模块
提供多种权限检查装饰器用于视图函数
"""

from functools import wraps
from django.http import JsonResponse, HttpResponseForbidden
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger('django')

DATA_PERMISSION_CACHE_TIMEOUT = 5 * 60
PERMISSION_CACHE_TIMEOUT = 5 * 60
MENU_CACHE_TIMEOUT = 10 * 60


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
            return any(request.user.has_perm(self._normalize_permission(perm))
                       for perm in perm_required)

        return request.user.has_perm(self._normalize_permission(perm_required))

    @staticmethod
    def _normalize_permission(permission_code):
        """标准化权限代码"""
        if not permission_code:
            return None
        if '.' in permission_code:
            return permission_code
        return f'user.{permission_code}'

    def dispatch(self, request, *args, **kwargs):
        if not self.has_permission(request):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'code': 403,
                    'msg': '您没有权限执行此操作'
                })
            raise PermissionDenied('您没有权限执行此操作')
        return super().dispatch(request, *args, **kwargs)


def _normalize_permission(permission_code):
    """标准化权限代码"""
    if not permission_code:
        return None
    if '.' in permission_code:
        return permission_code
    return f'user.{permission_code}'


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

            normalized_perm = _normalize_permission(permission)

            if isinstance(permission, (list, tuple)):
                has_all = all(
                    request.user.has_perm(
                        _normalize_permission(perm)) for perm in permission)
                if not has_all:
                    logger.warning(
                        f"用户 {request.user.username} 缺少权限: {permission}"
                    )
                    if request.headers.get(
                            'X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'code': 403,
                            'msg': '您没有权限执行此操作'
                        }, status=403)
                    raise PermissionDenied('您没有权限执行此操作')
            else:
                if not request.user.has_perm(normalized_perm):
                    logger.warning(
                        f"用户 {request.user.username} 缺少权限: {permission}"
                    )
                    if request.headers.get(
                            'X-Requested-With') == 'XMLHttpRequest':
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

            has_any = any(
                request.user.has_perm(
                    _normalize_permission(perm)) for perm in permissions)
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
            if not user_department or not hasattr(
                    user_department, department_field):
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

    return request.user.has_perm(_normalize_permission(permission_code))


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


def filter_queryset_by_permissions(
        user, queryset, permission_code, field_name='created_by'):
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

    if check_permission(request=user, permission_code=permission_code):
        return queryset

    return queryset.filter(**{field_name: user})


def data_isolation(model=None):
    """
    数据隔离装饰器
    确保用户只能访问自己有权限的数据

    参数：
    - model: 模型类，用于确定数据过滤的字段
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated and getattr(
                    request.user, 'is_superuser', False):
                return view_func(request, *args, **kwargs)

            auth_did = getattr(request.user, 'auth_did', 0)
            auth_dids = getattr(request.user, 'auth_dids', '')
            son_dids = getattr(request.user, 'son_dids', '')

            auth_dids_list = list(
                map(int, auth_dids.split(','))) if auth_dids else []
            son_dids_list = list(
                map(int, son_dids.split(','))) if son_dids else []

            all_visible_dids = auth_dids_list + son_dids_list
            all_visible_dids = list(set(all_visible_dids))

            if not all_visible_dids and auth_did != 0:
                return HttpResponseForbidden("您没有权限访问该数据")

            request.user_data_permissions = {
                'auth_did': auth_did,
                'auth_dids': auth_dids_list,
                'son_dids': son_dids_list,
                'all_visible_dids': all_visible_dids
            }

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def button_permission_required(button_code):
    """
    按钮权限检查装饰器
    用于检查用户是否有使用特定按钮的权限

    参数：
    - button_code: 按钮代码，用于标识特定的按钮权限
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated and getattr(
                    request.user, 'is_superuser', False):
                return view_func(request, *args, **kwargs)

            button_perm = f"user.button_{button_code}"
            if not request.user.has_perm(button_perm):
                logger.warning(
                    f"用户 {request.user.username} 尝试使用无权限的按钮: {button_code}")
                return HttpResponseForbidden("您没有权限使用此功能")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
