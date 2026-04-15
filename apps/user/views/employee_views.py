"""
统一员工管理视图
整合user应用和adm应用中的员工管理功能
"""

from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.db import transaction
from django.db.models import Q

# 导入自定义登录验证混入类
from apps.system.views.base import CustomLoginRequiredMixin

from apps.user.models.admin import Admin
from apps.department.models import Department
from apps.user.forms import EmployeeForm
from apps.user.forms.employee_forms import (
    RewardPunishmentForm, EmployeeCareForm, EmployeeContractForm
)

# 导入user应用中的统一数据模型
from apps.user.models import (
    EmployeeFile, EmployeeTransfer, EmployeeDimission,
    RewardPunishment, EmployeeCare, EmployeeContract
)


class EmployeeListView(CustomLoginRequiredMixin, ListView):
    """员工列表视图 - 整合AdminListAPIView功能"""
    model = Admin
    template_name = 'user/list.html'
    context_object_name = 'employees'
    paginate_by = 20

    def get_queryset(self):
        queryset = Admin.objects.prefetch_related('secondary_departments')

        # 搜索功能
        keyword = self.request.GET.get('keyword', '')
        if keyword:
            queryset = queryset.filter(
                Q(username__icontains=keyword) |
                Q(name__icontains=keyword) |
                Q(job_number__icontains=keyword) |
                Q(mobile__icontains=keyword)
            )

        # 部门筛选
        department_id = self.request.GET.get('department_id')
        if department_id:
            queryset = queryset.filter(did=department_id)

        # 状态筛选
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by('-create_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.all()
        context['search_keyword'] = self.request.GET.get('keyword', '')
        context['selected_department'] = self.request.GET.get(
            'department_id', '')
        context['selected_status'] = self.request.GET.get('status', '')

        # 生成部门树形数据
        import json
        department_tree_data = self._build_department_tree()
        context['department_tree'] = json.dumps(
            department_tree_data, ensure_ascii=False)

        return context

    def _build_department_tree(self):
        """构建部门树形结构数据，符合layui.tree组件格式"""
        departments = Department.objects.filter(
            status=1).order_by('sort', 'id')

        # 构建部门映射
        department_map = {}
        for dept in departments:
            department_map[dept.id] = {
                'id': dept.id,
                'title': dept.name,  # layui.tree直接使用title字段
                'pid': dept.pid,
                'children': []
            }

        # 构建树形结构
        tree = []
        for dept_data in department_map.values():
            if dept_data['pid'] == 0:
                # 根节点
                tree.append(dept_data)
            else:
                # 子节点，添加到父节点的children中
                parent_id = dept_data['pid']
                if parent_id in department_map:
                    department_map[parent_id]['children'].append(dept_data)

        return tree


class EmployeeDetailView(CustomLoginRequiredMixin, DetailView):
    """员工详情视图 - 整合AdminDetailView功能"""
    model = Admin
    template_name = 'user/detail.html'
    context_object_name = 'employee'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object

        # 获取员工档案信息
        try:
            context['employee_file'] = EmployeeFile.objects.get(
                employee=employee)
        except EmployeeFile.DoesNotExist:
            context['employee_file'] = None

        # 获取调动记录
        context['transfer_records'] = EmployeeTransfer.objects.filter(
            employee=employee
        ).order_by('-created_at')[:10]

        # 获取离职记录
        context['dimission_records'] = EmployeeDimission.objects.filter(
            employee=employee
        ).order_by('-created_at')[:10]

        # 获取奖惩记录
        context['reward_punishment_records'] = RewardPunishment.objects.filter(
            employee=employee
        ).order_by('-created_at')[:10]

        # 获取关怀记录
        context['care_records'] = EmployeeCare.objects.filter(
            employee=employee
        ).order_by('-care_date')[:10]

        # 获取合同信息
        context['contracts'] = EmployeeContract.objects.filter(
            employee=employee
        ).order_by('-created_at')[:10]

        return context


class EmployeeCreateView(CustomLoginRequiredMixin, CreateView):
    """员工创建视图 - 整合AdminCreateView功能"""
    model = Admin
    form_class = EmployeeForm
    template_name = 'user/form.html'

    def form_valid(self, form):
        with transaction.atomic():
            employee = form.save()

            return JsonResponse({
                'code': 0,
                'msg': '员工创建成功',
                'data': {'id': employee.id}
            })

    def form_invalid(self, form):
        return JsonResponse({
            'code': 1,
            'msg': '表单验证失败',
            'form_errors': form.errors
        })


class EmployeeUpdateView(CustomLoginRequiredMixin, UpdateView):
    """员工更新视图 - 整合AdminUpdateView功能"""
    model = Admin
    form_class = EmployeeForm
    template_name = 'user/form.html'

    def form_valid(self, form):
        with transaction.atomic():
            employee = form.save()

            return JsonResponse({
                'code': 0,
                'msg': '员工信息更新成功',
                'data': {'id': employee.id}
            })

    def form_invalid(self, form):
        return JsonResponse({
            'code': 1,
            'msg': '表单验证失败',
            'form_errors': form.errors
        })


class EmployeeDeleteView(CustomLoginRequiredMixin, View):
    """员工删除视图 - 整合AdminDeleteView功能"""

    def post(self, request):
        employee_ids = request.POST.getlist('ids[]')

        if not employee_ids:
            return JsonResponse({'code': 1, 'msg': '请选择要删除的员工'})

        try:
            # 使用Django的bulk_delete方法直接删除员工，避免级联删除问题
            # bulk_delete不会触发信号和级联删除，只会直接删除记录
            from django.db import connection
            with connection.cursor() as cursor:
                # 直接执行SQL删除，跳过Django的ORM级联删除机制
                # 1. 先删除中间表记录
                cursor.execute(
                    "DELETE FROM admin_secondary_departments WHERE admin_id IN %s", [
                        tuple(employee_ids)])

                # 2. 再删除员工记录
                cursor.execute(
                    "DELETE FROM mimu_admin WHERE id IN %s", [
                        tuple(employee_ids)])

                deleted_count = cursor.rowcount

            return JsonResponse({
                'code': 0,
                'msg': f'成功删除 {deleted_count} 名员工',
                'data': {'deleted_count': deleted_count}
            })

        except Exception as e:
            return JsonResponse({
                'code': 1,
                'msg': f'删除失败: {str(e)}'
            })


# 专项管理功能视图（从adm应用迁移）

class EmployeeFileView(CustomLoginRequiredMixin, DetailView):
    """员工档案视图"""
    model = Admin
    template_name = 'user/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object

        try:
            context['employee_file'] = EmployeeFile.objects.get(
                employee=employee)
        except EmployeeFile.DoesNotExist:
            context['employee_file'] = None

        return context


class EmployeeTransferListView(CustomLoginRequiredMixin, ListView):
    """员工调动记录列表"""
    model = EmployeeTransfer
    template_name = 'user/list.html'
    paginate_by = 20

    def get_queryset(self):
        queryset = EmployeeTransfer.objects.select_related(
            'employee', 'from_department', 'to_department'
        ).all()

        # 员工筛选
        employee_id = self.request.GET.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        # 状态筛选
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by('-created_at')


class EmployeeDimissionListView(CustomLoginRequiredMixin, ListView):
    """员工离职记录列表"""
    model = EmployeeDimission
    template_name = 'user/list.html'
    paginate_by = 20

    def get_queryset(self):
        queryset = EmployeeDimission.objects.select_related('employee').all()

        # 员工筛选
        employee_id = self.request.GET.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        # 状态筛选
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by('-created_at')


# API视图（保持与现有接口兼容）

class EmployeeListAPIView(CustomLoginRequiredMixin, View):
    """员工列表API - 保持与现有接口兼容"""

    def get(self, request):
        """获取员工列表"""
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        keyword = request.GET.get('keyword', '')
        department_id = request.GET.get('department_id', '')
        dept_id = request.GET.get('dept_id', '')  # 兼容模板中的参数名
        status = request.GET.get('status', '')

        # 部门筛选，兼容两种参数名
        department_filter_id = department_id or dept_id

        # 构建查询条件
        queryset = Admin.objects.all()

        if keyword:
            queryset = queryset.filter(
                Q(username__icontains=keyword) |
                Q(name__icontains=keyword) |
                Q(job_number__icontains=keyword) |
                Q(mobile__icontains=keyword)
            )

        if department_filter_id:
            queryset = queryset.filter(did=department_filter_id)

        if status:
            queryset = queryset.filter(status=status)

        # 获取部门名称映射，避免N+1查询
        department_ids = queryset.values_list('did', flat=True).distinct()
        department_map = {}
        for dept in Department.objects.filter(id__in=department_ids):
            department_map[dept.id] = dept.name

        total = queryset.count()
        employees = queryset[(page - 1) * limit:page * limit]

        data = []
        for emp in employees:
            data.append({
                'id': emp.id,
                'username': emp.username,
                'name': emp.name,
                'job_number': emp.job_number,
                'mobile': emp.mobile,
                'email': emp.email,
                'thumb': emp.thumb or '/static/img/user-avatar.png',
                'department_name': department_map.get(emp.did, ''),
                'position_name': emp.position_name or '',
                'type': emp.type or '普通员工',
                'status': emp.status,
                'entry_time': datetime.fromtimestamp(emp.entry_time).strftime('%Y-%m-%d') if emp.entry_time and emp.entry_time > 0 else '',
                'create_time': datetime.fromtimestamp(emp.create_time).strftime('%Y-%m-%d %H:%M:%S') if emp.create_time and emp.create_time > 0 else '',
                'last_login_time': datetime.fromtimestamp(emp.last_login_time).strftime('%Y-%m-%d %H:%M:%S') if emp.last_login_time and emp.last_login_time > 0 else ''
            })

        return JsonResponse({
            'code': 0,
            'msg': 'success',
            'count': total,
            'data': data
        })


# 专项管理功能视图

class RewardPunishmentListView(CustomLoginRequiredMixin, View):
    """奖惩记录列表视图"""

    def get(self, request):
        # 检查是否是Ajax请求数据
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        # 普通页面请求返回HTML模板
        return render(request, 'user/reward_punishment_list.html')

    def get_data_list(self, request):
        """返回奖惩记录列表的JSON格式"""
        try:
            # 获取查询参数
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 20))
            employee_id = request.GET.get('employee_id')
            rp_type = request.GET.get('type')

            # 构建查询条件
            queryset = RewardPunishment.objects.select_related(
                'employee').all()

            # 员工筛选
            if employee_id:
                queryset = queryset.filter(employee_id=employee_id)

            # 类型筛选
            if rp_type:
                queryset = queryset.filter(type=rp_type)

            # 分页
            total = queryset.count()
            start = (page - 1) * limit
            end = start + limit
            records = queryset.order_by('-created_at')[start:end]

            # 构建返回数据
            data_list = []
            for record in records:
                data_list.append({
                    'id': record.id,
                    'employee_name': record.employee.username if record.employee else '',
                    'type': record.type,
                    'type_display': record.get_type_display(),
                    'amount': str(record.amount),
                    'reason': record.reason,
                    'created_at': record.created_at.strftime('%Y-%m-%d %H:%M') if record.created_at else '',
                    'remark': record.remark or ''
                })

            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'count': total,
                'data': data_list
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({
                'code': 1,
                'msg': f'获取数据失败: {str(e)}',
                'count': 0,
                'data': []
            })


class RewardPunishmentCreateView(CustomLoginRequiredMixin, CreateView):
    """奖惩记录创建视图"""
    model = RewardPunishment
    form_class = RewardPunishmentForm
    template_name = 'user/reward_punishment_form.html'

    def form_valid(self, form):
        reward_punishment = form.save()
        return JsonResponse({
            'code': 0,
            'msg': '奖惩记录创建成功',
            'data': {'id': reward_punishment.id}
        })

    def form_invalid(self, form):
        return JsonResponse({
            'code': 1,
            'msg': '表单验证失败',
            'errors': form.errors
        })


class RewardPunishmentUpdateView(CustomLoginRequiredMixin, UpdateView):
    """奖惩记录更新视图"""
    model = RewardPunishment
    form_class = RewardPunishmentForm
    template_name = 'user/reward_punishment_form.html'

    def form_valid(self, form):
        reward_punishment = form.save()
        return JsonResponse({
            'code': 0,
            'msg': '修改成功',
            'data': {'id': reward_punishment.id}
        })

    def form_invalid(self, form):
        return JsonResponse({
            'code': 1,
            'msg': '修改失败，请检查表单',
            'errors': form.errors
        })


class EmployeeCareListView(CustomLoginRequiredMixin, View):
    """员工关怀记录列表视图"""

    def get(self, request):
        # 检查是否是Ajax请求数据
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        # 普通页面请求返回HTML模板
        return render(request, 'user/employee_care_list.html')

    def get_data_list(self, request):
        """返回员工关怀记录列表的JSON格式"""
        try:
            # 获取查询参数
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 20))
            employee_name = request.GET.get('employee_name')
            care_type = request.GET.get('care_type')
            care_date = request.GET.get('care_date')
            month = request.GET.get('month')

            # 构建查询条件
            queryset = EmployeeCare.objects.select_related('employee').all()

            # 员工姓名筛选
            if employee_name:
                queryset = queryset.filter(
                    employee__username__icontains=employee_name)

            # 关怀类型筛选
            if care_type:
                queryset = queryset.filter(care_type=care_type)

            # 关怀日期筛选
            if care_date:
                queryset = queryset.filter(care_date=care_date)

            # 月份筛选（用于本月生日员工和本月入职纪念）
            if month:
                # 如果是生日关怀，需要查询员工档案中的生日月份
                if care_type == 'birthday':
                    # 获取本月生日的员工ID列表
                    from django.db.models import Q
                    from apps.user.models import EmployeeFile

                    # 获取本月生日的员工ID
                    birthday_employee_ids = EmployeeFile.objects.filter(
                        birth_date__month=month
                    ).values_list('employee_id', flat=True)

                    # 筛选关怀记录
                    queryset = queryset.filter(
                        Q(care_type='birthday') &
                        Q(employee_id__in=birthday_employee_ids)
                    )
                # 如果是入职纪念，需要查询员工档案中的入职日期月份
                elif care_type == 'anniversary':
                    # 获取本月入职的员工ID列表
                    from apps.user.models import EmployeeFile

                    # 获取本月入职的员工ID
                    anniversary_employee_ids = EmployeeFile.objects.filter(
                        entry_date__month=month
                    ).values_list('employee_id', flat=True)

                    # 筛选关怀记录
                    queryset = queryset.filter(
                        Q(care_type='anniversary') &
                        Q(employee_id__in=anniversary_employee_ids)
                    )

            # 分页
            total = queryset.count()
            start = (page - 1) * limit
            end = start + limit
            records = queryset.order_by('-created_at')[start:end]

            # 构建返回数据
            data_list = []
            for record in records:
                data_list.append({
                    'id': record.id,
                    'employee_name': record.employee.username if record.employee else '',
                    'care_type': record.care_type,
                    'care_type_display': record.get_care_type_display(),
                    'title': record.title,
                    'content': record.content,
                    'care_date': record.care_date.strftime('%Y-%m-%d') if record.care_date else '',
                    'amount': str(record.amount) if record.amount else '',
                    'executor_name': record.executor.username if record.executor else '',
                    'created_at': record.created_at.strftime('%Y-%m-%d %H:%M') if record.created_at else '',
                    'remarks': record.remarks or ''
                })

            return JsonResponse({
                'code': 0,
                'msg': 'success',
                'count': total,
                'data': data_list
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({
                'code': 1,
                'msg': f'获取数据失败: {str(e)}',
                'count': 0,
                'data': []
            })


class EmployeeCareCreateView(CustomLoginRequiredMixin, CreateView):
    """员工关怀记录创建视图"""
    model = EmployeeCare
    form_class = EmployeeCareForm
    template_name = 'user/employee_care_form.html'

    def form_valid(self, form):
        # 设置执行人为当前用户
        form.instance.executor = self.request.user
        form.save()
        return JsonResponse({
            'success': True,
            'message': '员工关怀记录创建成功'
        })

    def form_invalid(self, form):
        return JsonResponse({
            'success': False,
            'message': '表单验证失败',
            'errors': form.errors
        })


class EmployeeCareUpdateView(CustomLoginRequiredMixin, UpdateView):
    """员工关怀记录更新视图"""
    model = EmployeeCare
    form_class = EmployeeCareForm
    template_name = 'user/employee_care_form.html'

    def form_valid(self, form):
        employee_care = form.save()
        return JsonResponse({
            'code': 0,
            'msg': '员工关怀记录更新成功',
            'data': {'id': employee_care.id}
        })

    def form_invalid(self, form):
        return JsonResponse({
            'code': 1,
            'msg': '表单验证失败',
            'errors': form.errors
        })


class EmployeeContractListView(CustomLoginRequiredMixin, ListView):
    """员工合同列表视图"""
    model = EmployeeContract
    template_name = 'user/list.html'
    paginate_by = 20

    def get_queryset(self):
        queryset = EmployeeContract.objects.select_related('employee').all()

        # 员工筛选
        employee_id = self.request.GET.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        # 合同状态筛选
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by('-created_at')


class EmployeeContractDetailView(CustomLoginRequiredMixin, DetailView):
    """员工合同详情视图"""
    model = EmployeeContract
    template_name = 'user/detail.html'
    context_object_name = 'contract'


class EmployeeContractCreateView(CustomLoginRequiredMixin, CreateView):
    """员工合同创建视图"""
    model = EmployeeContract
    form_class = EmployeeContractForm
    template_name = 'user/form.html'

    def form_valid(self, form):
        employee_contract = form.save()
        return JsonResponse({
            'code': 0,
            'msg': '员工合同创建成功',
            'data': {'id': employee_contract.id}
        })

    def form_invalid(self, form):
        return JsonResponse({
            'code': 1,
            'msg': '表单验证失败',
            'errors': form.errors
        })


class EmployeeContractUpdateView(CustomLoginRequiredMixin, UpdateView):
    """员工合同更新视图"""
    model = EmployeeContract
    form_class = EmployeeContractForm
    template_name = 'user/form.html'

    def form_valid(self, form):
        employee_contract = form.save()
        return JsonResponse({
            'code': 0,
            'msg': '员工合同更新成功',
            'data': {'id': employee_contract.id}
        })

    def form_invalid(self, form):
        return JsonResponse({
            'code': 1,
            'msg': '表单验证失败',
            'errors': form.errors
        })


class RewardPunishmentDeleteView(CustomLoginRequiredMixin, View):
    """奖罚记录删除视图"""

    def post(self, request, pk):
        try:
            reward_punishment = RewardPunishment.objects.get(pk=pk)
            reward_punishment.delete()
            return JsonResponse({
                'code': 0,
                'msg': '奖罚记录删除成功'
            })
        except RewardPunishment.DoesNotExist:
            return JsonResponse({
                'code': 1,
                'msg': '奖罚记录不存在'
            })


class EmployeeCareDeleteView(CustomLoginRequiredMixin, View):
    """员工关怀记录删除视图"""

    def post(self, request, pk):
        try:
            employee_care = EmployeeCare.objects.get(pk=pk)
            employee_care.delete()
            return JsonResponse({
                'code': 0,
                'msg': '员工关怀记录删除成功'
            })
        except EmployeeCare.DoesNotExist:
            return JsonResponse({
                'code': 1,
                'msg': '员工关怀记录不存在'
            })


class EmployeeContractDeleteView(CustomLoginRequiredMixin, View):
    """员工合同删除视图"""

    def post(self, request, pk):
        try:
            contract = EmployeeContract.objects.get(pk=pk)
            contract.delete()
            return JsonResponse({
                'code': 0,
                'msg': '员工合同删除成功'
            })
        except EmployeeContract.DoesNotExist:
            return JsonResponse({
                'code': 1,
                'msg': '合同不存在'
            })


class EmployeeCenterView(CustomLoginRequiredMixin, DetailView):
    """员工个人中心视图"""
    model = Admin
    template_name = 'user/center.html'
    context_object_name = 'employee'

    def get_object(self):
        # 获取当前登录用户
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object

        # 获取员工档案信息
        try:
            context['employee_file'] = EmployeeFile.objects.get(
                employee=employee)
        except EmployeeFile.DoesNotExist:
            context['employee_file'] = None

        # 获取员工合同信息
        context['contracts'] = EmployeeContract.objects.filter(
            employee=employee
        ).order_by('-created_at')[:5]

        # 获取奖惩记录
        context['reward_punishment_records'] = RewardPunishment.objects.filter(
            employee=employee
        ).order_by('-created_at')[:5]

        return context


class EmployeeCenterUpdateView(CustomLoginRequiredMixin, UpdateView):
    """员工个人中心更新视图"""
    model = Admin
    form_class = EmployeeForm
    template_name = 'user/center_form.html'

    def get_object(self):
        # 获取当前登录用户
        return self.request.user

    def form_valid(self, form):
        with transaction.atomic():
            # 使用form.save()直接保存，因为表单的save方法已经处理了密码和次要部门
            employee = form.save()

            return JsonResponse({
                'code': 0,
                'msg': '个人信息更新成功',
                'data': {'id': employee.id}
            })

    def form_invalid(self, form):
        return JsonResponse({
            'code': 1,
            'msg': '表单验证失败',
            'form_errors': form.errors
        })


# 工具函数

def get_employee_statistics():
    """获取员工统计信息"""
    total_employees = Admin.objects.filter(is_superuser=False).count()
    active_employees = Admin.objects.filter(
        status=1, is_superuser=False).count()
    inactive_employees = Admin.objects.filter(
        status=0, is_superuser=False).count()
    dimission_employees = Admin.objects.filter(
        status=2, is_superuser=False).count()

    return {
        'total': total_employees,
        'active': active_employees,
        'inactive': inactive_employees,
        'dimission': dimission_employees
    }
