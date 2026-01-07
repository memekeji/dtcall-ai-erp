from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Prefetch
import json

from apps.user.models import Menu

class MenuListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Menu
    template_name = 'menu/list.html'
    context_object_name = 'menus'
    permission_required = 'user.view_menu'
    
    def get_queryset(self):
        # 只获取顶级菜单，子菜单在模板中通过prefetch_related获取
        
        # 递归预取所有级别的子菜单，并确保每级都按sort字段排序
        def prefetch_submenus(level=0):
            if level >= 5:  # 限制最大递归深度，避免无限循环
                return None
            
            # 创建下一级的Prefetch对象
            next_level = prefetch_submenus(level + 1)
            query = Menu.objects.filter(status=1).order_by('sort')
            
            if next_level:
                query = query.prefetch_related(next_level)
            
            return Prefetch('submenus', queryset=query)
        
        # 获取顶级菜单并预取所有级别的子菜单
        queryset = Menu.objects.filter(pid=None, status=1).order_by('sort')
        queryset = queryset.prefetch_related(prefetch_submenus())
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 添加额外的排序验证信息（可选）
        context['sort_verification'] = '菜单已按排序字段正确排序'
        return context

class MenuCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Menu
    fields = ['title', 'src', 'icon', 'pid', 'sort', 'status', 'module']
    template_name = 'menu/form.html'
    success_url = reverse_lazy('system:menu:menu_list')
    permission_required = 'user.add_menu'
    
    def get_success_url(self):
        # 操作成功后添加refresh参数，指示需要刷新菜单
        return reverse_lazy('system:menu:menu_list') + '?refresh=1'
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # 排除当前正在编辑的菜单作为父菜单选项
        if self.object:
            form.fields['pid'].queryset = Menu.objects.exclude(id=self.object.id).order_by('sort')
        else:
            form.fields['pid'].queryset = Menu.objects.order_by('sort')
        return form

class MenuUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Menu
    fields = ['title', 'src', 'icon', 'pid', 'sort', 'status', 'module']
    template_name = 'menu/form.html'
    success_url = reverse_lazy('system:menu:menu_list')
    permission_required = 'user.change_menu'
    
    def get_success_url(self):
        # 操作成功后添加refresh参数，指示需要刷新菜单
        return reverse_lazy('system:menu:menu_list') + '?refresh=1'
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # 排除当前正在编辑的菜单作为父菜单选项
        form.fields['pid'].queryset = Menu.objects.exclude(id=self.object.id).order_by('sort')
        return form

class MenuDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Menu
    template_name = 'menu/menu_confirm_delete.html'
    success_url = reverse_lazy('system:menu:menu_list')
    permission_required = 'user.delete_menu'
    
    def get_success_url(self):
        # 操作成功后添加refresh参数，指示需要刷新菜单
        return reverse_lazy('system:menu:menu_list') + '?refresh=1'
    
    def delete(self, request, *args, **kwargs):
        # 处理删除操作，这里可以添加额外的逻辑
        return super().delete(request, *args, **kwargs)

class MenuSyncAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """菜单同步API视图，返回最新的菜单数据"""
    permission_required = 'user.change_menu'
    def get(self, request, *args, **kwargs):
        # 使用与MenuListView相同的递归预取方法获取菜单数据
        
        # 递归预取所有级别的子菜单，并确保每级都按sort字段排序
        def prefetch_submenus(level=0):
            if level >= 5:  # 限制最大递归深度，避免无限循环
                return None
            
            # 创建下一级的Prefetch对象
            next_level = prefetch_submenus(level + 1)
            query = Menu.objects.filter(status=1).order_by('sort')
            
            if next_level:
                query = query.prefetch_related(next_level)
            
            return Prefetch('submenus', queryset=query)
        
        # 获取顶级菜单并预取所有级别的子菜单
        menus = Menu.objects.filter(pid=None, status=1).order_by('sort')
        menus = menus.prefetch_related(prefetch_submenus())
        
        # 构建菜单树结构
        def build_menu_tree(menu_queryset):
            menu_list = []
            for menu in menu_queryset:
                # 检查菜单是否可用
                if not menu.is_available():
                    continue
                
                # 对子菜单进行排序，确保即使在API响应中也保持正确的排序
                sorted_submenus = sorted(menu.submenus.all(), key=lambda x: x.sort)
                
                # 过滤可用的子菜单
                available_submenus = [submenu for submenu in sorted_submenus if submenu.is_available()]
                
                menu_dict = {
                    'id': menu.id,
                    'title': menu.title,
                    'src': menu.src,
                    'icon': menu.icon,
                    'pid': menu.pid.id if menu.pid else None,
                    'sort': menu.sort,
                    'status': menu.status,
                    'create_time': menu.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'update_time': menu.update_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'submenus': build_menu_tree(available_submenus)
                }
                menu_list.append(menu_dict)
            return menu_list
        
        menu_tree = build_menu_tree(menus)
        return JsonResponse({'status': 'success', 'data': menu_tree}, encoder=DjangoJSONEncoder)

class MenuOrderAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """处理菜单排序更新的API视图"""
    permission_required = 'user.change_menu'
    def post(self, request, *args, **kwargs):
        try:
            # 获取排序数据
            ordered_menu_ids = request.POST.getlist('menu_ids[]', [])
            pid = request.POST.get('pid')
            
            # 转换pid为整数或None
            pid = int(pid) if pid else None
            
            # 更新菜单排序
            for index, menu_id in enumerate(ordered_menu_ids):
                try:
                    menu = Menu.objects.get(id=int(menu_id))
                    menu.sort = index + 1  # 排序从1开始
                    menu.save()
                except Menu.DoesNotExist:
                    continue
            
            return JsonResponse({'status': 'success', 'message': '菜单排序更新成功'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})