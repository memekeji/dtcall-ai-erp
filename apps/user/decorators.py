"""
权限装饰器
用于实现数据隔离和权限控制
"""
from functools import wraps
from django.http import HttpResponseForbidden
import logging

logger = logging.getLogger('django')


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
            if request.user.is_authenticated and getattr(request.user, 'is_superuser', False):
                return view_func(request, *args, **kwargs)
            
            auth_did = getattr(request.user, 'auth_did', 0)
            auth_dids = getattr(request.user, 'auth_dids', '')
            son_dids = getattr(request.user, 'son_dids', '')
            
            auth_dids_list = list(map(int, auth_dids.split(','))) if auth_dids else []
            son_dids_list = list(map(int, son_dids.split(','))) if son_dids else []
            
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


def permission_required(perms):
    """
    权限检查装饰器
    用于检查用户是否有指定的权限
    
    参数：
    - perms: 字符串或列表，指定需要的权限
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated and getattr(request.user, 'is_superuser', False):
                return view_func(request, *args, **kwargs)
            
            if not request.user.is_authenticated:
                from django.contrib.auth.decorators import login_required
                return login_required(view_func)(request, *args, **kwargs)
            
            has_perm = False
            if isinstance(perms, str):
                has_perm = request.user.has_perm(perms)
            elif isinstance(perms, (list, tuple)):
                has_perm = any(request.user.has_perm(perm) for perm in perms)
            
            if not has_perm:
                logger.warning(f"用户 {request.user.username} 尝试访问无权限的功能: {perms}")
                return HttpResponseForbidden("您没有权限执行此操作")
            
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
            if request.user.is_authenticated and getattr(request.user, 'is_superuser', False):
                return view_func(request, *args, **kwargs)
            
            button_perm = f"user.button_{button_code}"
            if not request.user.has_perm(button_perm):
                logger.warning(f"用户 {request.user.username} 尝试使用无权限的按钮: {button_code}")
                return HttpResponseForbidden("您没有权限使用此功能")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
