from django.views import View
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group
from apps.user.models_new import DepartmentGroup
from apps.department.models import Department


class DepartmentRoleManagementView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """部门角色管理视图"""
    permission_required = 'department.change_department'
    
    def get(self, request, department_id):
        """获取部门角色管理页面"""
        try:
            # 获取部门信息
            department = Department.objects.get(id=department_id)
            
            # 获取所有角色
            roles = Group.objects.all()
            
            # 获取部门已分配的角色
            department_roles = DepartmentGroup.objects.filter(department=department)
            department_role_ids = [dg.group.id for dg in department_roles]
            
            # 获取部门员工数
            from apps.user.models import Admin
            staff_count = Admin.objects.filter(did=department_id, status=1).count()
            
            # 获取部门员工角色列表
            staff_list = Admin.objects.filter(did=department_id, status=1)
            user_roles = []
            for staff in staff_list:
                staff_roles = staff.groups.all()
                user_roles.append({
                    'user': staff,
                    'roles': staff_roles
                })
            
            return render(request, 'permission/department_role.html', {
                'department': department,
                'roles': roles,  # 与模板变量名匹配
                'department_role_ids': department_role_ids,
                'isInIframe': True,
                'staff_count': staff_count,  # 传递正确的部门员工数
                'user_roles': user_roles  # 传递部门员工角色列表
            })
        except Department.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '部门不存在'})
    
    def post(self, request, department_id):
        """更新部门角色分配"""
        try:
            # 获取部门信息
            department = Department.objects.get(id=department_id)
            
            # 获取选中的角色ID列表
            selected_role_ids = request.POST.getlist('department_role_ids[]', [])
            selected_role_ids = [int(rid) for rid in selected_role_ids if rid.isdigit()]
            
            # 删除该部门的所有现有角色分配
            DepartmentGroup.objects.filter(department=department).delete()
            
            # 添加新的角色分配
            for role_id in selected_role_ids:
                try:
                    role = Group.objects.get(id=role_id)
                    DepartmentGroup.objects.create(department=department, group=role)
                except Group.DoesNotExist:
                    continue
            
            return JsonResponse({'code': 200, 'msg': '部门角色分配成功'})
        except Department.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '部门不存在'})


class DepartmentRoleListAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """获取部门角色列表API"""
    permission_required = 'department.view_department'
    
    def get(self, request, department_id):
        """获取部门已分配的角色列表"""
        try:
            # 获取部门信息
            department = Department.objects.get(id=department_id)
            
            # 获取部门已分配的角色
            department_roles = DepartmentGroup.objects.filter(department=department).select_related('group')
            
            # 构建角色列表数据
            roles_data = []
            for dg in department_roles:
                roles_data.append({
                    'id': dg.group.id,
                    'name': dg.group.name,
                    'description': dg.group.extension.description if hasattr(dg.group, 'extension') else ''
                })
            
            return JsonResponse({'code': 200, 'msg': '获取成功', 'data': roles_data})
        except Department.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '部门不存在'})
