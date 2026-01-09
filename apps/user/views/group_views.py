from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group, Permission
from django.db.models import Q, Count
from django.urls import reverse_lazy
from django.shortcuts import render
from django.core.exceptions import ObjectDoesNotExist

from apps.user.models.permission import GroupExtension, DepartmentGroup
from apps.department.models import Department
from apps.user.utils.permission_utils import PermissionManager

class GroupListAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """用户组列表API视图"""
    permission_required = 'auth.view_group'
    
    def get(self, request):
        """获取用户组列表"""
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        keyword = request.GET.get('keyword', '')
        status = request.GET.get('status', '')
        
        queryset = Group.objects.all()
        
        if keyword:
            queryset = queryset.filter(
                name__icontains=keyword
            )
        
        total = queryset.count()
        groups = queryset[(page-1)*limit:page*limit]
        
        data = []
        for group in groups:
            # 获取GroupExtension
            try:
                extension = group.extension
                description = extension.description
                status = 1 if extension.status else 0
                created_at = extension.created_at.strftime('%Y-%m-%d %H:%M:%S')
            except ObjectDoesNotExist:
                description = ''
                status = 1
                created_at = ''
            
            # 获取分配的部门
            departments = DepartmentGroup.objects.filter(group=group).select_related('department')
            department_names = [dept.department.name for dept in departments]
            
            data.append({
                'id': group.id,
                'title': group.name,  # 使用name作为title
                'name': group.name,
                'description': description,
                'status': status,
                'sort': 0,  # Django Group没有sort字段，默认0
                'create_time': created_at,
                'departments': department_names
            })
        
        return JsonResponse({
            'code': 200,
            'msg': 'success',
            'data': {
                'total': total,
                'items': data
            }
        })


class GroupDetailAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """用户组详情API视图"""
    permission_required = 'auth.view_group'
    
    def get(self, request, pk):
        """获取用户组详情"""
        try:
            group = Group.objects.get(id=pk)
            
            # 获取GroupExtension
            try:
                extension = group.extension
                description = extension.description
                status = 1 if extension.status else 0
                created_at = extension.created_at.strftime('%Y-%m-%d %H:%M:%S')
            except ObjectDoesNotExist:
                description = ''
                status = 1
                created_at = ''
            
            data = {
                'id': group.id,
                'title': group.name,
                'name': group.name,
                'description': description,
                'status': status,
                'sort': 0,
                'create_time': created_at
            }
            
            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': data
            })
        
        except Group.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': 'Group not found'
            })
    
    def delete(self, request, pk):
        """删除用户组"""
        try:
            group = Group.objects.get(id=pk)
            
            # 删除GroupExtension
            try:
                extension = group.extension
                extension.delete()
            except ObjectDoesNotExist:
                pass
            
            # 删除部门角色关联
            from apps.user.models.permission import DepartmentGroup
            DepartmentGroup.objects.filter(group=group).delete()
            
            # 删除角色
            group.delete()
            
            return JsonResponse({
                'code': 200,
                'msg': 'success'
            })
        except Group.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': 'Group not found'
            })
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'msg': f'删除失败: {str(e)}'
            })


class GroupListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """角色组列表视图"""
    model = Group
    template_name = 'permission/index.html'
    context_object_name = 'groups'
    paginate_by = 10
    permission_required = 'auth.view_group'

    def get_queryset(self):
        return Group.objects.all().order_by('-id')

class GroupDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """角色组详情视图"""
    model = Group
    template_name = 'permission/view.html'
    context_object_name = 'group'
    permission_required = 'auth.view_group'

class GroupCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """创建角色组视图"""
    model = Group
    template_name = 'permission/form.html'
    fields = ['name']
    success_url = reverse_lazy('user:group_list')
    permission_required = 'auth.add_group'
    
    def form_valid(self, form):
        """在创建Group后自动创建GroupExtension"""
        response = super().form_valid(form)
        # 自动创建GroupExtension
        GroupExtension.objects.get_or_create(group=self.object, defaults={'status': True})
        return response

class GroupUpdateViewCBV(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """更新角色组视图（CBV版本）"""
    model = Group
    template_name = 'permission/form.html'
    fields = ['name']
    success_url = reverse_lazy('user:group_list')
    permission_required = 'auth.change_group'

class GroupDeleteViewCBV(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """删除角色组视图（CBV版本）"""
    model = Group
    success_url = reverse_lazy('user:group_list')
    permission_required = 'auth.delete_group'
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        return JsonResponse({'code': 200, 'msg': 'success'})

class GroupUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """更新角色信息"""
    permission_required = 'auth.change_group'
    
    def post(self, request, pk):
        """更新角色信息"""
        try:
            group = Group.objects.get(id=pk)
            name = request.POST.get('name', '')
            description = request.POST.get('description', '')
            status = request.POST.get('status', '') == 'true'
            
            if not name:
                return JsonResponse({'code': 400, 'msg': '角色名称不能为空'})
            
            # 更新Group名称
            group.name = name
            group.save()
            
            # 更新或创建GroupExtension
            extension, created = GroupExtension.objects.get_or_create(group=group)
            extension.description = description
            extension.status = status
            extension.save()
            
            return JsonResponse({'code': 200, 'msg': '更新成功'})
        
        except Group.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '角色不存在'})

class GroupStatusToggleView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """切换角色状态"""
    permission_required = 'auth.change_group'
    
    def post(self, request, pk):
        """切换角色状态"""
        try:
            group = Group.objects.get(id=pk)
            
            # 获取或创建GroupExtension
            extension, created = GroupExtension.objects.get_or_create(group=group)
            extension.status = not extension.status
            extension.save()
            
            return JsonResponse({
                'code': 200, 
                'msg': '状态更新成功',
                'data': {'status': 1 if extension.status else 0}
            })
        
        except Group.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '角色不存在'})


class GetGroupsAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """获取所有权限组（auth.Group）数据的API视图"""
    permission_required = 'auth.view_group'
    def get(self, request, *args, **kwargs):
        # 获取所有的auth.Group数据
        groups = Group.objects.all().order_by('name')
        
        # 构建返回数据结构
        groups_list = []
        for group in groups:
            groups_list.append({
                'id': group.id,
                'name': group.name
            })
        
        # 返回JSON响应
        return JsonResponse({'status': 'success', 'data': groups_list}, json_dumps_params={'ensure_ascii': False})

class RoleManagementView(LoginRequiredMixin, View):
    """角色管理页面"""
    
    def get(self, request, department_id):
        """获取部门角色管理页面"""
        return render(request, 'permission/role_list.html', {
            'department_id': department_id
        })

class RoleListView(LoginRequiredMixin, ListView):
    """角色列表视图"""
    model = Group
    template_name = 'permission/role_list.html'
    context_object_name = 'roles'
    paginate_by = 20
    
    def get_queryset(self):
        """获取角色列表"""
        queryset = Group.objects.all().order_by('-id')
        # 添加搜索过滤
        name = self.request.GET.get('name', '')
        description = self.request.GET.get('description', '')
        
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """添加上下文数据"""
        context = super().get_context_data(**kwargs)
        
        # 获取分页信息
        if hasattr(self, 'paginator'):
            context['total_count'] = self.paginator.count
            context['limit'] = self.paginator.per_page
        else:
            # 如果没有分页器，使用默认值
            context['total_count'] = self.get_queryset().count()
            context['limit'] = self.paginate_by
        
        context['page'] = self.request.GET.get('page', 1)
        context['name'] = self.request.GET.get('name', '')
        context['description'] = self.request.GET.get('description', '')
        
        # 处理isInIframe参数
        context['isInIframe'] = self.request.GET.get('isInIframe', 'false').lower() == 'true'
        
        # 为每个角色添加扩展信息和部门信息
        roles = context['roles']
        for role in roles:
            try:
                extension = role.extension
                role.desc = extension.description
                role.status = 1 if extension.status else 0
                role.create_time = extension.created_at
            except ObjectDoesNotExist:
                role.desc = ''
                role.status = 1
                role.create_time = None
            
            # 获取分配的部门
            departments = DepartmentGroup.objects.filter(group=role).select_related('department')
            role.departments = [dept.department.name for dept in departments]
        
        return context