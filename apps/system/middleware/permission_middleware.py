"""
权限控制中间件
用于拦截所有请求并检查用户是否有相应的权限
"""
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.urls import resolve
from django.contrib.auth import logout
from django.conf import settings
import logging

logger = logging.getLogger('django')

PERMISSION_CACHE_TIMEOUT = 5 * 60


class PermissionMiddleware:
    """
    权限控制中间件
    拦截所有请求，检查用户是否有相应的权限
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        path = request.path
        
        if self._should_skip_permission_check(path):
            return self.get_response(request)
        
        if not request.user.is_authenticated:
            if self._is_api_request(path):
                return HttpResponseForbidden("未登录或登录已过期")
            from django.urls import reverse
            return HttpResponseRedirect(reverse('user:login'))
        
        if hasattr(request.user, 'status') and request.user.status != 1:
            logout(request)
            return HttpResponseRedirect('/login/')
        
        if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
            return self.get_response(request)
        
        if not self._has_permission(request, path):
            logger.warning(f"用户 {request.user.username} 尝试访问无权限的URL: {path}")
            return HttpResponseForbidden("您没有权限访问该页面")
        
        return self.get_response(request)
    
    def _should_skip_permission_check(self, path):
        skip_urls = [
            '/login/', '/logout/', '/api/login/', '/api/logout/',
            '/user/login/', '/user/logout/', '/user/login-submit/',
            '/static/', '/media/', '/favicon.ico', '/captcha/',
            '/admin/', '/home/main/', '/home/dashboard/',
            '/get-new-captcha/',
        ]
        return any(path.startswith(url) for url in skip_urls)
    
    def _is_api_request(self, path):
        return path.startswith('/api/')
    
    def _has_permission(self, request, path):
        try:
            from apps.system.context_processors import get_permission_from_src
            from apps.user.models import Menu
            from django.core.cache import cache
            
            resolver_match = resolve(path)
            view_func = resolver_match.func
            
            permission_required = getattr(view_func, 'permission_required', None)
            
            if permission_required:
                if isinstance(permission_required, str):
                    return self._check_permission(request, permission_required)
                elif isinstance(permission_required, (list, tuple)):
                    return any(self._check_permission(request, perm) for perm in permission_required)
            
            perm_codename = get_permission_from_src(path)
            if perm_codename:
                return self._check_permission(request, perm_codename)
            
            cache_key = f'menu_path_{path}'
            menu = None
            
            try:
                menu = cache.get(cache_key)
                if menu is None:
                    menu = Menu.objects.filter(src=path, status=1).first()
                    if menu:
                        cache.set(cache_key, menu, PERMISSION_CACHE_TIMEOUT)
            except Exception:
                menu = Menu.objects.filter(src=path, status=1).first()
            
            if menu and menu.permission_required:
                return self._check_permission(request, menu.permission_required)
            
            app_label = resolver_match.app_name or resolver_match.view_name.split(':')[0]
            return request.user.has_module_perms(app_label)
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            return True
    
    def _check_permission(self, request, permission_required):
        if not permission_required:
            return True
        
        if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
            return True
        
        full_perm = permission_required
        if '.' not in full_perm:
            full_perm = f'user.{permission_required}'
        
        return request.user.has_perm(full_perm)
