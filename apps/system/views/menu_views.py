from apps.system.menu_config import system_menus
from apps.user.models import Menu
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponseRedirect
from django.db.models import Prefetch
from django.db import transaction
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
        except Exception as e:
            logger.error(f"菜单删除操作发生错误: {str(e)}")
            from django.contrib import messages
            messages.error(request, f'删除失败: {str(e)}')
            return HttpResponseRedirect(reverse_lazy('system:menu:menu_list'))


class MenuSyncAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """菜单同步API视图，将menu_config.py中的菜单配置导入数据库"""
    permission_required = 'user.change_menu'

    def post(self, request, *args, **kwargs):
        """执行菜单同步：先清空数据库，再从menu_config.py导入"""
        try:
            result = self._sync_menus_from_config()
            return JsonResponse({
                'status': 'success',
                'message': '菜单同步成功',
                'data': result
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'菜单同步失败: {str(e)}'
            }, status=500)

    def _sync_menus_from_config(self):
        """从menu_config.py同步菜单到数据库（先清空再导入）"""
        with transaction.atomic():
            existing_menus = {menu.id: menu for menu in Menu.objects.all()}

            sorted_menus = sorted(system_menus.items(), key=lambda x: x[0])

            deleted_count = 0
            created_count = 0
            updated_count = 0
            errors = []

            existing_menu_ids = set(existing_menus.keys())
            config_menu_ids = {menu_data['id']
                               for menu_key, menu_data in sorted_menus}

            menus_to_delete = existing_menu_ids - config_menu_ids
            if menus_to_delete:
                deleted_count = Menu.objects.filter(
                    id__in=menus_to_delete).delete()[0]

            for menu_key, menu_data in sorted_menus:
                menu_id = menu_data['id']

                try:
                    menu_defaults = {
                        'title': menu_data['title'],
                        'src': menu_data['src'],
                        'sort': menu_data['sort'],
                        'status': menu_data['status'],
                    }

                    pid_id = menu_data.get('pid_id')
                    if pid_id and pid_id in existing_menus:
                        menu_defaults['pid'] = existing_menus[pid_id]
                    elif pid_id and pid_id == 0:
                        menu_defaults['pid'] = None

                    menu, created = Menu.objects.update_or_create(
                        id=menu_id,
                        defaults=menu_defaults
                    )

                    existing_menus[menu_id] = menu

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                except Exception as e:
                    errors.append({
                        'id': menu_id,
                        'title': menu_data.get('title', 'Unknown'),
                        'error': str(e)
                    })

            for menu_key, menu_data in sorted_menus:
                menu_id = menu_data['id']
                pid_id = menu_data.get('pid_id')

                try:
                    if pid_id and pid_id != 0:
                        menu = existing_menus.get(menu_id)
                        parent = existing_menus.get(pid_id)

                        if menu and parent and (
                                not menu.pid or menu.pid_id != parent.id):
                            menu.pid = parent
                            menu.save(update_fields=['pid'])
                except Exception as e:
                    errors.append({
                        'id': menu_id,
                        'title': menu_data.get('title', 'Unknown'),
                        'error': f'父菜单关联失败: {e}'
                    })

        return {
            'deleted': deleted_count,
            'created': created_count,
            'updated': updated_count,
            'total': len(sorted_menus),
            'errors': errors
        }

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
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
