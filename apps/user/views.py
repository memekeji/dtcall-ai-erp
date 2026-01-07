from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q

from .models import (
    Department, 
    Position,
    AdminLog,
    Admin,
    SystemOperationLog
)
from .forms import EmployeeForm
import logging
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.models import AnonymousUser
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .decorators import ajax_error_handler

def logout_view(request):
    import logging
    logger = logging.getLogger(__name__)
    logger.info('登出视图开始处理请求')
    logger.info(f'请求方法: {request.method}')
    
    try:
        # 手动清除会话
        request.session.flush()
        if hasattr(request, 'user'):
            from django.contrib.auth.models import AnonymousUser
            request.user = AnonymousUser()
        logger.info('手动清除会话成功')
        
        # 重定向到登录页面
        from django.shortcuts import redirect
        return redirect('/user/login/')
        
    except Exception as e:
        logger.error(f'登出处理异常: {str(e)}', exc_info=True)
        return JsonResponse({'code': 1, 'msg': f'服务器错误: {str(e)}'}, status=500)





class DepartmentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """部门创建视图"""
    model = Department
    template_name = 'department/form.html'
    fields = ['title', 'pid', 'sort', 'status', 'desc']
    success_url = reverse_lazy('user:department_list')
    permission_required = 'user.add_department'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'status_list': [
                {'value': 0, 'name': '禁用'},
                {'value': 1, 'name': '正常'}
            ],
            'parent_departments': Department.objects.filter(
                pid=0, 
                status=1
            ).order_by('sort')
        })
        return context
    
    @ajax_error_handler
    def post(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            try:
                # 获取表单数据
                title = request.POST.get('title')
                pid = request.POST.get('pid', 0)
                sort = request.POST.get('sort', 0)
                status = request.POST.get('status')
                desc = request.POST.get('desc')
                
                # 验证必填字段
                if not title:
                    return JsonResponse({
                        'code': 1,
                        'msg': '请填写部门名称',
                        'errors': {'title': ['部门名称为必填项']}
                    })
                
                # 验证名称唯一性
                if Department.objects.filter(name=title).exists():
                    return JsonResponse({
                        'code': 1,
                        'msg': '部门名称已存在',
                        'errors': {'title': ['该部门名称已被使用']}
                    })
                
                # 创建新部门
                department = Department.objects.create(
                    name=title,
                    pid=int(pid) if pid else 0,
                    sort=int(sort) if sort else 0,
                    status=int(status) if status else 1,
                    desc=desc
                )
                
                # 记录操作日志
                SystemOperationLog.objects.create(
                    operator_id=request.user.id,
                    operator_name=request.user.username,
                    operation_title=f'创建部门 - {title}',
                    operation_content='创建部门操作',
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                return JsonResponse({
                    'code': 0,
                    'msg': '创建成功',
                    'data': {'redirect_url': reverse_lazy('user:department_list')}
                })
            except Exception as e:
                return JsonResponse({
                    'code': 1,
                    'msg': f'创建失败：{str(e)}',
                    'errors': {'__all__': ['创建失败，请稍后重试']}
                })
        return super().post(request, *args, **kwargs)

class DepartmentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """部门更新视图"""
    model = Department
    template_name = 'department/form.html'
    fields = ['title', 'pid', 'sort', 'status', 'desc']
    success_url = reverse_lazy('user:department_list')
    permission_required = 'user.change_department'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'status_list': [
                {'value': 0, 'name': '禁用'},
                {'value': 1, 'name': '正常'}
            ],
            'parent_departments': Department.objects.filter(
                pid=0, 
                status=1
            ).exclude(id=self.object.id).order_by('sort')
        })
        return context
    
    @ajax_error_handler
    def post(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            try:
                department = self.get_object()
                
                # 获取表单数据
                title = request.POST.get('title')
                pid = request.POST.get('pid', 0)
                sort = request.POST.get('sort', 0)
                status = request.POST.get('status')
                desc = request.POST.get('desc')
                
                # 验证必填字段
                if not title:
                    return JsonResponse({
                        'code': 1,
                        'msg': '请填写部门名称',
                        'errors': {'title': ['部门名称为必填项']}
                    })
                
                # 验证名称唯一性
                if Department.objects.filter(name=title).exclude(id=department.id).exists():
                    return JsonResponse({
                        'code': 1,
                        'msg': '部门名称已存在',
                        'errors': {'title': ['该部门名称已被使用']}
                    })
                
                # 防止循环引用
                if int(pid) == department.id:
                    return JsonResponse({
                        'code': 1,
                        'msg': '不能选择自己作为父级部门',
                        'errors': {'pid': ['不能选择自己作为父级部门']}
                    })
                
                # 更新部门信息
                department.name = title
                department.pid = int(pid) if pid else 0
                department.sort = int(sort) if sort else 0
                department.status = int(status) if status else 1
                department.desc = desc
                department.save()
                
                # 记录操作日志
                SystemOperationLog.objects.create(
                    operator_id=request.user.id,
                    operator_name=request.user.username,
                    operation_title=f'更新部门 - {title}',
                    operation_content='更新部门操作',
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                return JsonResponse({
                    'code': 0,
                    'msg': '更新成功',
                    'data': {'redirect_url': reverse_lazy('user:department_list')}
                })
            except Exception as e:
                return JsonResponse({
                    'code': 1,
                    'msg': f'更新失败：{str(e)}',
                    'errors': {'__all__': ['更新失败，请稍后重试']}
                })
        return super().post(request, *args, **kwargs)

class DepartmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """部门删除视图"""
    model = Department
    success_url = reverse_lazy('user:department_list')
    permission_required = 'user.delete_department'
    
    @ajax_error_handler
    def delete(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            try:
                department = self.get_object()
                
                # 检查是否有子部门
                if Department.objects.filter(pid=department.id).exists():
                    return JsonResponse({
                        'code': 1,
                        'msg': '该部门下存在子部门，无法删除'
                    })
                
                # 检查是否有管理员关联此部门
                if department.admin_set.exists():
                    return JsonResponse({
                        'code': 1,
                        'msg': '该部门下存在管理员，无法删除'
                    })
                
                title = department.name
                
                # 记录操作日志
                SystemOperationLog.objects.create(
                    operator_id=request.user.id,
                    operator_name=request.user.username,
                    operation_title=f'删除部门 - {title}',
                    operation_content='删除部门操作',
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                # 执行删除操作
                department.delete()
                
                return JsonResponse({
                    'code': 0,
                    'msg': '删除成功'
                })
            except Exception as e:
                return JsonResponse({
                    'code': 1,
                    'msg': f'删除失败：{str(e)}'
                })
        return super().delete(request, *args, **kwargs)














class AdminListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """管理员列表视图"""
    model = Admin
    template_name = 'user/list.html'
    context_object_name = 'admins'
    paginate_by = 15
    permission_required = 'user.view_admin'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # 搜索条件
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(mobile__icontains=search)
            )
        
        # 状态过滤
        status = self.request.GET.get('status')
        if status and status.isdigit():
            queryset = queryset.filter(status=int(status))
            
        # 部门过滤
        did = self.request.GET.get('did')
        if did and did.isdigit():
            queryset = queryset.filter(did=int(did))
            
        # 排序
        sort_field = self.request.GET.get('sort')
        if sort_field and sort_field.lstrip('-') in ['username', 'name', 'create_time']:
            queryset = queryset.order_by(sort_field)
        else:
            queryset = queryset.order_by('-id')
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'status_list': [
                {'value': -1, 'name': '待入职'},
                {'value': 0, 'name': '禁用'},
                {'value': 1, 'name': '正常'},
                {'value': 2, 'name': '离职'}
            ],
            'departments': Department.objects.filter(status=1).order_by('sort'),
            'search': self.request.GET.get('search', ''),
            'current_status': self.request.GET.get('status', ''),
            'current_did': self.request.GET.get('did', ''),
            'current_sort': self.request.GET.get('sort', '-id')
        })
        return context
    
    @ajax_error_handler
    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            queryset = self.get_queryset()
            data = []
            for admin in queryset:
                department = Department.objects.filter(id=admin.did).first()
                data.append({
                    'id': admin.id,
                    'username': admin.username,
                    'name': admin.name,
                    'email': admin.email,
                    'mobile': admin.mobile,
                    'did': admin.did,
                    'department_name': department.name if department else '',
                    'position_name': admin.position_name,
                    'status': admin.status,
                    'status_text': dict([(x['value'], x['name']) for x in self.get_context_data()['status_list']]).get(admin.status, '未知'),
                    'last_login_time': admin.last_login_time,
                    'create_time': admin.create_time
                })
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'data': data,
                'total': queryset.count(),
                'page': self.request.GET.get('page', 1),
                'limit': self.paginate_by
            })
        return super().get(request, *args, **kwargs)


class AdminCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """员工创建视图"""
    model = Admin
    template_name = 'user/form.html'
    form_class = EmployeeForm
    success_url = reverse_lazy('user:admin_list')
    permission_required = 'user.add_admin'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'status_list': [
                {'value': -1, 'name': '待入职'},
                {'value': 0, 'name': '禁用'},
                {'value': 1, 'name': '正常'},
                {'value': 2, 'name': '离职'}
            ],
            'departments': Department.objects.filter(status=1).order_by('sort'),
            'positions': Position.objects.filter(status=1).order_by('sort')
        })
        return context
    
    @ajax_error_handler
    def post(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            try:
                # 使用EmployeeForm处理表单数据
                form = EmployeeForm(request.POST)
                if form.is_valid():
                    # 保存员工信息
                    employee = form.save(commit=False)
                    employee.save()
                    
                    # 记录操作日志
                    AdminLog.objects.create(
                        admin_id=request.user.id,
                        username=request.user.username,
                        title=f'创建员工 - {employee.name}',
                        content='创建员工操作',
                        ip=request.META.get('REMOTE_ADDR', ''),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )
                    
                    return JsonResponse({
                        'code': 0,
                        'msg': '创建成功',
                        'data': {'redirect_url': reverse_lazy('user:admin_list')}
                    })
                else:
                    # 表单验证失败
                    return JsonResponse({
                        'code': 1,
                        'msg': '表单验证失败',
                        'errors': form.errors
                    })
            except Exception as e:
                return JsonResponse({
                    'code': 1,
                    'msg': f'创建失败：{str(e)}',
                    'errors': {'__all__': ['创建失败，请稍后重试']}
                })
        return super().post(request, *args, **kwargs)


class AdminUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """员工更新视图"""
    model = Admin
    template_name = 'user/form.html'
    form_class = EmployeeForm
    success_url = reverse_lazy('user:admin_list')
    permission_required = 'user.change_admin'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'status_list': [
                {'value': -1, 'name': '待入职'},
                {'value': 0, 'name': '禁用'},
                {'value': 1, 'name': '正常'},
                {'value': 2, 'name': '离职'}
            ],
            'departments': Department.objects.filter(status=1).order_by('sort'),
            'positions': Position.objects.filter(status=1).order_by('sort')
        })
        return context
    
    @ajax_error_handler
    def post(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            try:
                employee = self.get_object()
                
                # 使用EmployeeForm处理表单数据
                form = EmployeeForm(request.POST, instance=employee)
                if form.is_valid():
                    # 保存员工信息
                    employee = form.save()
                    
                    # 记录操作日志
                    AdminLog.objects.create(
                        admin_id=request.user.id,
                        username=request.user.username,
                        title=f'更新员工 - {employee.name}',
                        content='更新员工操作',
                        ip=request.META.get('REMOTE_ADDR', ''),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )
                    
                    return JsonResponse({
                        'code': 0,
                        'msg': '更新成功',
                        'data': {'redirect_url': reverse_lazy('user:admin_list')}
                    })
                else:
                    # 表单验证失败
                    return JsonResponse({
                        'code': 1,
                        'msg': '表单验证失败',
                        'errors': form.errors
                    })
            except Exception as e:
                return JsonResponse({
                    'code': 1,
                    'msg': f'更新失败：{str(e)}',
                    'errors': {'__all__': ['更新失败，请稍后重试']}
                })
        return super().get(request, *args, **kwargs)





class AdminLogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """管理员操作日志列表视图"""
    model = AdminLog
    template_name = 'user/list.html'
    context_object_name = 'logs'
    paginate_by = 15
    ordering = ['-create_time']
    permission_required = 'user.view_adminlog'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # 搜索条件
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(ip__icontains=search) |
                Q(admin__username__icontains=search) |
                Q(admin__name__icontains=search)
            )
        
        # 管理员过滤
        admin_id = self.request.GET.get('admin_id')
        if admin_id and admin_id.isdigit():
            queryset = queryset.filter(admin_id=int(admin_id))
            
        # 操作类型过滤
        action = self.request.GET.get('action')
        if action:
            queryset = queryset.filter(action=action)
            
        # 时间范围过滤
        start_time = self.request.GET.get('start_time')
        end_time = self.request.GET.get('end_time')
        if start_time:
            queryset = queryset.filter(create_time__gte=start_time)
        if end_time:
            queryset = queryset.filter(create_time__lte=end_time)
            
        # 排序
        sort_field = self.request.GET.get('sort')
        if sort_field and sort_field.lstrip('-') in ['create_time', 'admin__username', 'action']:
            queryset = queryset.order_by(sort_field)
        else:
            queryset = queryset.order_by('-create_time')
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'admins': Admin.objects.filter(status=1).order_by('username'),
            'action_list': [
                {'value': 'login', 'name': '登录'},
                {'value': 'logout', 'name': '登出'},
                {'value': 'add', 'name': '新增'},
                {'value': 'edit', 'name': '编辑'},
                {'value': 'delete', 'name': '删除'},
                {'value': 'view', 'name': '查看'},
                {'value': 'import', 'name': '导入'},
                {'value': 'export', 'name': '导出'}
            ],
            'search': self.request.GET.get('search', ''),
            'current_admin': self.request.GET.get('admin_id', ''),
            'current_action': self.request.GET.get('action', ''),
            'current_sort': self.request.GET.get('sort', '-create_time'),
            'start_time': self.request.GET.get('start_time', ''),
            'end_time': self.request.GET.get('end_time', '')
        })
        return context
    
    @ajax_error_handler
    def get(self, request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            queryset = self.get_queryset()
            data = []
            for log in queryset:
                data.append({
                    'id': log.id,
                    'admin_id': log.admin_id,
                    'admin_name': log.admin.name if log.admin else '',
                    'admin_username': log.admin.username if log.admin else '',
                    'action': log.action,
                    'action_text': dict([(x['value'], x['name']) for x in self.get_context_data()['action_list']]).get(log.action, '未知'),
                    'title': log.title,
                    'ip': log.ip,
                    'create_time': log.create_time.strftime('%Y-%m-%d %H:%M:%S')
                })
            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'data': data,
                'total': queryset.count(),
                'page': self.request.GET.get('page', 1),
                'limit': self.paginate_by
            })
        return super().get(request, *args, **kwargs)