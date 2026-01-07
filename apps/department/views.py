from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.db.models import F
from django.utils import timezone
from .models import Department
from .forms import DepartmentForm
from django.core.serializers.json import DjangoJSONEncoder
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views import View
from apps.user.models import Admin
from apps.common.views_utils import generic_form_view

logger = logging.getLogger(__name__)

@method_decorator(login_required, name='dispatch')
class DepartmentListView(PermissionRequiredMixin, ListView):
    model = Department
    template_name = 'department/list.html'
    context_object_name = 'departments'
    paginate_by = 20  # 添加分页功能
    permission_required = 'department.view_department'

    def get_queryset(self):
        # 获取查询集并添加搜索功能
        queryset = Department.objects.all()
        # 检查是否有搜索参数
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        # 构建层级排序的部门列表
        def build_department_tree(parent_id=0, level=0):
            departments = []
            # 获取当前层级的部门，按sort和id排序
            current_departments = queryset.filter(pid=parent_id).order_by('sort', 'id')
            for dept in current_departments:
                # 设置部门层级
                dept.level = level
                departments.append(dept)
                # 递归获取子部门
                departments.extend(build_department_tree(dept.id, level + 1))
            return departments
        
        # 从顶级部门（pid=0）开始构建树形结构
        departments_with_level = build_department_tree()
        return departments_with_level

    def get_context_data(self,** kwargs):
        context = super().get_context_data(**kwargs)
        # 获取顶级部门并构建树形结构字典
        top_departments = Department.objects.filter(pid=0).order_by('sort')
        department_tree = self.build_hierarchy(top_departments)
        # 将部门树形数据序列化为JSON字符串
        context['department_tree_json'] = json.dumps(department_tree, cls=DjangoJSONEncoder)
        # 将搜索参数添加到上下文，用于在模板中显示
        context['search'] = self.request.GET.get('search', '')
        return context

    def build_hierarchy(self, departments):
        hierarchy = []
        for dept in departments:
            children = Department.objects.filter(pid=dept.id).order_by('sort')
            dept_dict = {
                'id': dept.id,
                'title': dept.name,  # 使用name字段代替title
                'children': self.build_hierarchy(children)
            }
            hierarchy.append(dept_dict)
        return hierarchy

@login_required
def department_create(request):
    """创建部门视图"""
    return generic_form_view(
        request,
        Department,
        DepartmentForm,
        'department/form.html',
        'department:department_list',
        None
    )

@login_required
def department_update(request, pk):
    """更新部门视图"""
    return generic_form_view(
        request,
        Department,
        DepartmentForm,
        'department/form.html',
        'department:department_list',
        pk
    )

@login_required
def department_detail(request, pk):
    """部门详情视图"""
    try:
        # 获取部门对象
        department = get_object_or_404(Department, id=pk)
        
        # 获取父部门信息
        parent_department = None
        if department.pid:
            parent_department = Department.objects.filter(id=department.pid).first()
        
        # 获取子部门列表
        children_departments = Department.objects.filter(pid=pk).order_by('sort', 'id')
        
        # 获取负责人信息
        manager_info = None
        if department.manager:
            manager_info = {
                'id': department.manager.id,
                'name': department.manager.name or department.manager.username,
                'mobile': department.manager.mobile or '未设置'
            }
        
        # 构建部门层级路径
        def get_department_path(dept_id):
            path = []
            current_id = dept_id
            while current_id:
                dept = Department.objects.filter(id=current_id).first()
                if dept:
                    path.insert(0, {'id': dept.id, 'name': dept.name})
                    current_id = dept.pid
                else:
                    break
            return path
        
        department_path = get_department_path(pk)
        
        context = {
            'department': department,
            'parent_department': parent_department,
            'children_departments': children_departments,
            'manager_info': manager_info,
            'department_path': department_path,
            'is_detail': True  # 标记为详情页面
        }
        
        return render(request, 'department/detail.html', context)
        
    except Exception as e:
        logger.error(f"获取部门详情失败: {str(e)}")
        return JsonResponse({'code': 1, 'msg': '获取部门详情失败'})

@login_required
def department_delete(request, department_id):
    """删除部门视图"""
    if request.method == 'POST':
        try:
            department = Department.objects.get(id=department_id)
            # 检查是否有子部门
            has_children = Department.objects.filter(pid=department_id).exists()
            if has_children:
                return JsonResponse({'code': 1, 'msg': '该部门下有子部门，无法删除'})
                
            department.delete()  # 使用硬删除
            return JsonResponse({'code': 0, 'msg': '删除成功'})
        except Department.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '部门不存在'}, status=404)
        except Exception as e:
            logger.error(f"删除部门失败: {str(e)}")
            return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})
    else:
        return JsonResponse({'code': 1, 'msg': '不支持的请求方法'}, status=405)


@login_required
def department_list_api(request):
    """部门列表API接口"""
    # 获取所有部门并按照层级和排序正确排序
    departments = Department.objects.all().order_by('level', 'sort')
    
    # 创建部门ID到部门对象的映射，用于快速查找父部门
    dept_map = {}
    for dept in departments:
        dept_map[dept.id] = dept
    
    # 计算部门层级
    def calculate_level(dept_id, level=1):
        """递归计算部门层级"""
        dept = dept_map.get(dept_id)
        if not dept or not dept.pid:
            return level
        return calculate_level(dept.pid, level + 1)
    
    data = []
    for dept in departments:
        # 获取父部门名称
        parent_name = ''
        if dept.pid:
            parent_dept = dept_map.get(dept.pid)
            if parent_dept:
                parent_name = parent_dept.name
        
        # 获取负责人名称和电话
        leader_name = ''
        leader_phone = ''
        if dept.manager:
            # 增强健壮性，确保正确显示中文名称
            # 先检查name字段是否有值且不为空字符串
            if hasattr(dept.manager, 'name') and dept.manager.name and dept.manager.name.strip():
                leader_name = dept.manager.name.strip()
            # 如果name为空，再尝试使用username
            elif hasattr(dept.manager, 'username'):
                leader_name = dept.manager.username
            # 获取负责人电话
            if hasattr(dept.manager, 'mobile'):
                leader_phone = dept.manager.mobile or ''
        
        # 计算层级
        level = calculate_level(dept.id)
        
        # 获取部门已分配的角色（使用DepartmentGroup模型）
        from apps.user.models_new import DepartmentGroup
        from django.contrib.auth.models import Group
        
        # 获取部门已分配的角色
        department_group_roles = DepartmentGroup.objects.filter(department=dept)
        # 获取角色名称列表
        role_names = [dg.group.name for dg in department_group_roles]
        
        data.append({
            'id': dept.id,
            'name': dept.name,  # 使用name字段
            'parent_id': dept.pid,  # 确保返回parent_id字段，用于前端构建树形结构
            'parent_name': parent_name,
            'leader_name': leader_name,
            'leader_phone': leader_phone,  # 添加负责人电话
            'sort': dept.sort,
            'status': dept.status,
            'code': dept.code or '',
            'phone': dept.phone or '',
            'is_active': dept.is_active,
            'level': level,
            'roles': role_names,  # 添加部门已分配角色名称列表
            'role_count': len(role_names)  # 添加角色数量
        })
    return JsonResponse({'code': 0, 'data': data})


@login_required
def department_tree_api(request):
    """部门树API接口，用于获取部门层级结构"""
    # 获取所有部门
    departments = Department.objects.all()
    
    # 构建部门树
    def build_tree(parent_id=0):
        """递归构建部门树"""
        tree = []
        # 获取当前父部门下的子部门，按sort和id排序
        current_departments = departments.filter(pid=parent_id).order_by('sort', 'id')
        for dept in current_departments:
            # 递归获取子部门
            children = build_tree(dept.id)
            # 构建部门树节点
            tree_node = {
                'id': dept.id,
                'title': dept.name,
                'name': dept.name,
                'children': children
            }
            tree.append(tree_node)
        return tree
    
    # 从根部门开始构建树
    department_tree = build_tree()
    
    return JsonResponse({'code': 0, 'data': department_tree})


@login_required
def department_employees_api(request, department_id):
    """根据部门ID获取员工列表API"""
    try:
        # 获取指定部门的所有员工
        from apps.user.models import Admin
        employees = Admin.objects.filter(did=department_id, status=1)
        
        # 构建员工列表
        employee_list = []
        for emp in employees:
            employee_list.append({
                'id': emp.id,
                'name': emp.name or emp.username,
                'username': emp.username,
                'mobile': emp.mobile or '',
                'position_name': emp.position_name or '',
                'job_number': emp.job_number or ''
            })
        
        return JsonResponse({'code': 0, 'data': employee_list})
    except Exception as e:
        logger.error(f"获取部门员工列表失败: {str(e)}")
        return JsonResponse({'code': 1, 'msg': '获取员工列表失败'})

# AJAX视图：生成部门代码
@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class DepartmentCodeGenerateView(PermissionRequiredMixin, View):
    """部门编号生成"""
    permission_required = 'department.change_department'
    def post(self, request):
        try:
            data = json.loads(request.body)
            department_name = data.get('name', '').strip()
            parent_id = data.get('pid', 0)
            
            if not department_name:
                return JsonResponse({'code': 1, 'msg': '部门名称不能为空'})
            
            # 创建临时的Department实例用于代码生成
            from .models import Department
            temp_department = Department()
            temp_department.name = department_name
            temp_department.pid = int(parent_id) if parent_id else 0
            
            # 调用表单中的代码生成逻辑
            from .forms import DepartmentForm
            form = DepartmentForm()
            
            # 生成部门代码
            code = form._generate_department_code(temp_department)
            
            return JsonResponse({'code': 0, 'msg': 'success', 'data': {'code': code}})
            
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': str(e)})

# AJAX视图：根据部门获取负责人列表
@method_decorator(login_required, name='dispatch')
@method_decorator(csrf_exempt, name='dispatch')
class DepartmentManagersView(PermissionRequiredMixin, View):
    """获取部门负责人列表"""
    permission_required = 'department.view_department'
    
    def get(self, request):
        department_id = request.GET.get('pid')  # 前端发送的是pid参数
        
        # 导入正确的Admin模型
        from apps.user.models import Admin
        
        # 如果department_id为空或0，显示所有用户
        if not department_id or department_id == '0':
            managers = Admin.objects.filter(status=1)  # 状态为1表示正常员工
        else:
            try:
                # 显示该部门内的用户
                managers = Admin.objects.filter(did=department_id, status=1)
            except Exception as e:
                return JsonResponse({'code': 1, 'msg': str(e)})
        
        manager_list = [
            {'id': manager.id, 'name': manager.name or manager.username}  # 优先显示姓名，如果没有则显示用户名
            for manager in managers
        ]
        
        return JsonResponse({'code': 0, 'msg': 'success', 'data': manager_list})

# AJAX视图：获取负责人联系电话
@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class ManagerPhoneView(PermissionRequiredMixin, View):
    """获取负责人联系电话"""
    permission_required = 'department.view_department'
    
    def get(self, request):
        manager_id = request.GET.get('manager_id')
        
        if not manager_id:
            return JsonResponse({'code': 1, 'msg': '负责人ID不能为空'})
        
        # 导入正确的Admin模型
        from apps.user.models import Admin
        
        try:
            manager = Admin.objects.get(id=manager_id)
            phone = manager.mobile or ''  # Admin模型只有mobile字段
            
            return JsonResponse({'code': 0, 'msg': 'success', 'data': phone})
            
        except Admin.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '负责人不存在'})
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': str(e)})

# 树形选择器页面
@method_decorator(login_required, name='dispatch')
class ManagerSelectView(PermissionRequiredMixin, View):
    """部门负责人树形选择器"""
    permission_required = 'department.view_department'
    
    def get(self, request):
        # 获取所有部门数据
        departments = Department.objects.all().order_by('sort', 'id')
        
        # 构建部门树形结构
        def build_department_tree(parent_id=0):
            tree = []
            current_departments = departments.filter(pid=parent_id).order_by('sort', 'id')
            for dept in current_departments:
                children = build_department_tree(dept.id)
                tree_item = {
                    'id': dept.id,
                    'title': dept.name,
                    'children': children
                }
                tree.append(tree_item)
            return tree
        
        department_tree = build_department_tree()
        
        # 获取所有用户数据
        from apps.user.models import Admin
        users = Admin.objects.filter(status=1).values('id', 'username', 'name', 'mobile', 'did')
        
        # 获取部门名称映射
        dept_names = {dept.id: dept.name for dept in departments}
        
        # 构建用户数据
        user_list = []
        for user in users:
            user_list.append({
                'id': user['id'],
                'name': user['name'] or user['username'],
                'employee_id': user['username'],
                'department_id': user['did'] or 0,
                'department_name': dept_names.get(user['did'], '未分配部门'),
                'phone': user['mobile'] or ''
            })
        
        context = {
            'departments': json.dumps(department_tree, cls=DjangoJSONEncoder),
            'users': json.dumps(user_list, cls=DjangoJSONEncoder)
        }
        
        return render(request, 'adm/department/manager_select.html', context)


"""
部门角色关联管理视图
"""
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.decorators import login_required
from django.db import transaction
import json
import logging


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class DepartmentChangeStatusView(PermissionRequiredMixin, View):
    """修改部门状态（启用/禁用）"""
    permission_required = 'department.change_department'
    
    def post(self, request, department_id):
        """修改部门状态"""
        try:
            # 获取状态参数
            status = request.POST.get('status', None)
            if status is None:
                return JsonResponse({'code': 1, 'msg': '状态参数不能为空'})
            
            # 转换状态为整数
            try:
                status = int(status)
                if status not in [0, 1]:
                    return JsonResponse({'code': 1, 'msg': '状态值只能是0或1'})
            except ValueError:
                return JsonResponse({'code': 1, 'msg': '状态值必须是数字'})
            
            # 获取部门对象
            department = get_object_or_404(Department, id=department_id)
            
            # 同时更新status和is_active字段，确保数据一致性
            department.status = status
            department.is_active = (status == 1)
            department.save()
            
            return JsonResponse({'code': 0, 'msg': '操作成功'})
            
        except Exception as e:
            logger.error(f"修改部门状态失败: {str(e)}")
            return JsonResponse({'code': 1, 'msg': '操作失败'})


