from django.views.generic import ListView, DetailView
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from apps.department.models import Department
from django.db.models import Q


class DepartmentListAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """部门列表API视图"""
    permission_required = 'department.view_department'

    def get(self, request):
        """获取部门列表"""
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        keyword = request.GET.get('keyword', '')
        status = request.GET.get('status', '')

        queryset = Department.objects.all()

        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword) |
                Q(code__icontains=keyword)
            )

        if status:
            queryset = queryset.filter(status=(status == 'enabled'))

        total = queryset.count()
        departments = queryset[(page - 1) * limit:page * limit]

        data = []
        for dept in departments:
            data.append({
                'id': dept.id,
                'title': dept.name,
                'code': dept.code,
                'pid': dept.pid,
                'status': dept.status,
                'sort': dept.sort,
                'create_time': dept.create_time.strftime('%Y-%m-%d %H:%M:%S') if dept.create_time else '-',
                'update_time': dept.update_time.strftime('%Y-%m-%d %H:%M:%S') if dept.update_time else '-'
            })

        return JsonResponse({
            'code': 200,
            'msg': 'success',
            'data': {
                'total': total,
                'items': data
            }
        })


class DepartmentDetailAPIView(
        LoginRequiredMixin, PermissionRequiredMixin, View):
    """部门详情API视图"""
    permission_required = 'department.view_department'

    def get(self, request, pk):
        """获取部门详情"""
        try:
            dept = Department.objects.get(id=pk)
            data = {
                'id': dept.id,
                'title': dept.name,  # 使用name字段作为title
                'code': dept.code,
                'pid': dept.pid,
                'status': dept.status,
                'sort': dept.sort,
                'create_time': dept.create_time.strftime('%Y-%m-%d %H:%M:%S') if dept.create_time else '-',
                'update_time': dept.update_time.strftime('%Y-%m-%d %H:%M:%S') if dept.update_time else '-'
            }

            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': data
            })

        except Department.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': 'Department not found'
            })


class DepartmentListView(LoginRequiredMixin, ListView):
    """部门列表视图"""
    model = Department
    template_name = 'department/list.html'
    context_object_name = 'departments'
    paginate_by = 10

    def get_queryset(self):
        """获取按层级结构排序的部门列表"""
        # 获取所有部门
        departments = Department.objects.select_related('manager').all()

        # 构建部门树形结构
        def build_department_tree(departments_list, parent_id=0, level=0):
            """递归构建部门树"""
            result = []

            # 获取当前层级的部门
            current_level_deps = [
                dept for dept in departments_list if dept.pid == parent_id]

            # 按排序字段排序
            current_level_deps.sort(key=lambda x: x.sort)

            for dept in current_level_deps:
                # 设置部门层级
                dept.level = level
                result.append(dept)

                # 递归获取子部门
                children = build_department_tree(
                    departments_list, dept.id, level + 1)
                result.extend(children)

            return result

        # 构建完整的部门树
        department_tree = build_department_tree(list(departments))

        return department_tree


class DepartmentDetailView(LoginRequiredMixin, DetailView):
    """部门详情视图"""
    model = Department
    template_name = 'user/detail.html'
    context_object_name = 'department'
