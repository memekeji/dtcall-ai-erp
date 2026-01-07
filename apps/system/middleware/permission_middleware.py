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
        # 跳过登录页面和静态资源的权限检查
        path = request.path
        
        # 跳过不需要权限检查的URL
        if self._should_skip_permission_check(path):
            return self.get_response(request)
        
        # 检查用户是否已登录
        if not request.user.is_authenticated:
            # 对于API请求，返回401未授权
            if self._is_api_request(path):
                return HttpResponseForbidden("未登录或登录已过期")
            # 对于页面请求，重定向到登录页面
            from django.urls import reverse
            return HttpResponseRedirect(reverse('user:login'))
        
        # 检查用户状态
        if hasattr(request.user, 'status') and request.user.status != 1:
            # 用户状态不正常，强制登出
            logout(request)
            return HttpResponseRedirect('/login/')
        
        # 超级用户拥有所有权限
        if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
            return self.get_response(request)
        
        # 检查用户是否有访问该URL的权限
        if not self._has_permission(request, path):
            logger.warning(f"用户 {request.user.username} 尝试访问无权限的URL: {path}")
            return HttpResponseForbidden("您没有权限访问该页面")
        
        return self.get_response(request)
    
    def _should_skip_permission_check(self, path):
        """
        判断是否应该跳过权限检查
        """
        # 跳过登录相关URL
        login_urls = ['/login/', '/logout/', '/api/login/', '/api/logout/', '/user/login/', '/user/logout/', '/user/login-submit/']
        if any(path.startswith(url) for url in login_urls):
            return True
        
        # 跳过静态资源
        static_urls = ['/static/', '/media/', '/favicon.ico', '/captcha/']
        if any(path.startswith(url) for url in static_urls):
            return True
        
        # 跳过管理后台URL
        if path.startswith('/admin/'):
            return True
        
        # 跳过主页和仪表盘，允许已登录用户访问
        home_urls = ['/home/main/', '/home/dashboard/']
        if any(path.startswith(url) for url in home_urls):
            return True
        
        # 跳过获取新验证码的URL
        if path.startswith('/get-new-captcha/'):
            return True
        
        return False
    
    def _is_api_request(self, path):
        """
        判断是否是API请求
        """
        return path.startswith('/api/')
    
    def _has_permission(self, request, path):
        """
        检查用户是否有访问该URL的权限
        """
        try:
            # 首先检查视图函数的权限要求
            resolver_match = resolve(path)
            view_func = resolver_match.func
            
            # 获取视图函数的权限要求
            permission_required = getattr(view_func, 'permission_required', None)
            
            # 如果视图指定了权限要求，检查用户是否有该权限
            if permission_required:
                if isinstance(permission_required, str):
                    return request.user.has_perm(permission_required)
                elif isinstance(permission_required, (list, tuple)):
                    return any(request.user.has_perm(perm) for perm in permission_required)
            
            # 如果视图没有指定权限要求，检查该URL对应的菜单是否有权限
            from apps.user.models import Menu
            from django.core.cache import cache
            
            # 构建缓存键
            cache_key = f'menu_path_{path}'
            
            # 尝试从缓存获取菜单
            menu = cache.get(cache_key)
            if menu is None:
                # 查找与当前URL匹配的菜单
                menu = Menu.objects.filter(src=path, status=1).first()
                # 缓存1小时
                cache.set(cache_key, menu, 60 * 60)
            
            if menu:
                # 检查用户是否有访问该菜单的权限
                return request.user.has_perm(menu.permission_required) if menu.permission_required else True
            
            # 如果没有找到匹配的菜单，检查用户是否有该应用的任何权限
            # 获取应用标签
            app_label = resolver_match.app_name or resolver_match.view_name.split(':')[0]
            
            # 检查用户是否有该应用的任何权限
            return request.user.has_module_perms(app_label)
        except Exception as e:
            logger.error(f"权限检查失败: {e}")
            # 发生错误时，默认允许访问，避免影响正常使用
            return True
