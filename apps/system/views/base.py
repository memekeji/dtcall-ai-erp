from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Prefetch
from django.shortcuts import redirect
from django.http import JsonResponse, HttpResponse
from apps.user.models import Menu
from apps.system.decorators.module_check import ModuleActiveCheckMixin


class CustomLoginRequiredMixin(LoginRequiredMixin):
    """自定义登录验证混入类，同时支持Django认证系统和自定义会话机制"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def dispatch(self, request, *args, **kwargs):
        # 检查Django认证系统
        if not request.user.is_authenticated:
            # 对于API请求，返回JSON响应
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'code': 1, 'msg': '请先登录'}, json_dumps_params={'ensure_ascii': False})
            
            # 构建登录URL
            login_redirect_url = f'{self.login_url}?{self.redirect_field_name}={request.get_full_path()}'
            
            # 强制在顶层窗口重定向，无论请求来自何处
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>登录重定向</title>
                <script>
                    // 在顶层窗口重定向到登录页面
                    window.top.location.href = '{login_redirect_url}';
                </script>
            </head>
            <body>
                <p>正在重定向到登录页面...</p>
            </body>
            </html>
            """
            return HttpResponse(html)
        return super().dispatch(request, *args, **kwargs)


class BaseAdminView(CustomLoginRequiredMixin, PermissionRequiredMixin, ModuleActiveCheckMixin):
    """系统管理视图基类"""
    permission_required = None  # 由子类设置具体权限
    raise_exception = True  # 权限不足时直接抛出异常，不重定向到登录页
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 获取所有有效顶级菜单并预取子菜单
        all_top_menus = Menu.objects.filter(pid=None, status=1).order_by('sort').prefetch_related(
            Prefetch(
                'submenus',
                queryset=Menu.objects.filter(status=1).order_by('sort')
            )
        )
        
        # 过滤出可用的菜单（考虑模块启用状态）
        available_menus = []
        for menu in all_top_menus:
            if menu.is_available():
                # 过滤子菜单
                menu.submenus_list = [submenu for submenu in menu.submenus.all() if submenu.is_available()]
                available_menus.append(menu)
        
        context['menus'] = available_menus
        
        # 加载仪表盘数据（可以根据需要添加更多数据）
        context['dashboard_data'] = {
            'project_count': 0,  # 暂时设置为0，后续可以根据需要添加
            'contract_count': 0,  # 暂时设置为0，后续可以根据需要添加
            'invoice_count': 0   # 暂时设置为0，后续可以根据需要添加
        }
        
        return context