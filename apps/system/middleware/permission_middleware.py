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
        login_urls = ['/login/', '/logout/', '/api/login/', '/api/logout/', '/user/login/', '/user/logout/', '/user/login-submit/']
        if any(path.startswith(url) for url in login_urls):
            return True
        
        static_urls = ['/static/', '/media/', '/favicon.ico', '/captcha/']
        if any(path.startswith(url) for url in static_urls):
            return True
        
        if path.startswith('/admin/'):
            return True
        
        home_urls = ['/home/main/', '/home/dashboard/']
        if any(path.startswith(url) for url in home_urls):
            return True
        
        if path.startswith('/get-new-captcha/'):
            return True
        
        return False
    
    def _is_api_request(self, path):
        return path.startswith('/api/')
    
    def _has_permission(self, request, path):
        try:
            resolver_match = resolve(path)
            view_func = resolver_match.func
            
            permission_required = getattr(view_func, 'permission_required', None)
            
            if permission_required:
                if isinstance(permission_required, str):
                    return self._check_permission(request, permission_required)
                elif isinstance(permission_required, (list, tuple)):
                    return any(self._check_permission(request, perm) for perm in permission_required)
            
            from apps.user.models import Menu
            from django.core.cache import cache
            
            cache_key = f'menu_path_{path}'
            
            menu = cache.get(cache_key)
            if menu is None:
                menu = Menu.objects.filter(src=path, status=1).first()
                cache.set(cache_key, menu, 60 * 60)
            
            if menu:
                if menu.permission_required:
                    return self._check_permission(request, menu.permission_required)
                if menu.view_permission_id:
                    return self._check_menu_view_permission(request, menu.view_permission_id)
                return True
            
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
    
    def _check_menu_view_permission(self, request, view_permission_id):
        from django.contrib.auth.models import Permission
        
        try:
            view_perm = Permission.objects.filter(id=view_permission_id).first()
            if view_perm:
                full_perm = f'{view_perm.content_type.app_label}.{view_perm.codename}'
                return request.user.has_perm(full_perm)
        except Exception as e:
            logger.error(f"检查菜单查看权限失败: {e}")
        return True
