from apps.system.menu_sync import sync_menus_from_config
from apps.user.models import Menu
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseRedirect
from django.db.models import Prefetch
from django.contrib.sessions.exceptions import SessionInterrupted
import logging

logger = logging.getLogger(__name__)


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
            form.fields['pid'].queryset = Menu.objects.exclude(
                id=self.object.id).order_by('sort')
        else:
            form.fields['pid'].queryset = Menu.objects.order_by('sort')
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        from apps.user.models.menu import clear_menu_cache_data
        clear_menu_cache_data()
        return response


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
        if hasattr(self, 'object') and self.object:
            form.fields['pid'].queryset = Menu.objects.exclude(
                id=self.object.id).order_by('sort')
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        from apps.user.models.menu import clear_menu_cache_data
        clear_menu_cache_data()
        return response


class MenuDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Menu
    template_name = 'menu/menu_confirm_delete.html'
    permission_required = 'user.delete_menu'

    def get_success_url(self):
        return reverse_lazy('system:menu:menu_list') + '?refresh=1'

    def post(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
            self.object.delete()
            from apps.user.models.menu import clear_menu_cache_data
            clear_menu_cache_data()
            return HttpResponseRedirect(self.get_success_url())
        except SessionInterrupted:
            logger.warning("会话在删除菜单操作中被中断，用户可能已登出或会话已过期")
            from django.contrib.auth import logout
            logout(request)
            return HttpResponseRedirect('/user/login/?next=' + request.path)
        except Exception:
            logger.exception("菜单删除操作发生错误")
            from django.contrib import messages
            messages.error(request, '删除失败，请稍后重试')
            return HttpResponseRedirect(reverse_lazy('system:menu:menu_list'))


class MenuSyncAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'user.change_menu'

    def post(self, request, *args, **kwargs):
        try:
            result = sync_menus_from_config(delete_extra=True)
            if result['errors']:
                return JsonResponse({
                    'status': 'error',
                    'message': '菜单同步失败，请检查服务端日志',
                    'data': result
                }, status=500)
            return JsonResponse({
                'status': 'success',
                'message': '菜单同步成功',
                'data': result
            })
        except Exception:
            logger.exception('菜单同步操作发生错误')
            return JsonResponse({
                'status': 'error',
                'message': '菜单同步失败，请稍后重试'
            }, status=500)

    def get(self, request, *args, **kwargs):
        """获取同步状态信息"""
        return JsonResponse({
            'status': 'success',
            'message': '使用POST方法执行菜单同步',
            'data': {
                'method': 'post_required',
                'description': '此API需要使用POST方法执行菜单同步'
            }
        })


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
                    menu.sort = index + 1
                    menu.save()
                except Menu.DoesNotExist:
                    continue

            from apps.user.models.menu import clear_menu_cache_data
            clear_menu_cache_data()

            return JsonResponse({'status': 'success', 'message': '菜单排序更新成功'})
        except Exception:
            logger.exception('菜单排序更新失败')
            return JsonResponse({'status': 'error', 'message': '菜单排序更新失败，请稍后重试'}, status=500)
