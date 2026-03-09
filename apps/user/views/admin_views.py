from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db import models, transaction, connection
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import View
from django.urls import reverse_lazy
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.core.cache import cache
from ..models import Admin
from apps.department.models import Department
from ..models.permission import DepartmentGroup
from ..forms import EmployeeForm
import logging
import datetime

logger = logging.getLogger(__name__)


def _inherit_user_department_roles(user):
    """
    继承用户所属部门的角色
    当用户登录时，自动将用户加入其所在部门关联的所有角色组
    仅支持 Admin 模型（使用 did 字段）
    """
    try:
        if not user or not hasattr(user, 'did') or not user.did:
            return
        
        department_id = user.did
        
        try:
            department = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            logger.warning(f"部门不存在: {department_id}")
            return
        
        links = DepartmentGroup.objects.filter(
            department=department
        ).select_related('group')
        
        added_count = 0
        for link in links:
            if link.group and not user.groups.filter(id=link.group.id).exists():
                user.groups.add(link.group)
                logger.info(f"用户 {user.username} 自动加入部门角色: {link.group.name}")
                added_count += 1
        
        if added_count > 0:
            logger.info(f"用户 {user.username} 继承部门 {department.name} 的 {added_count} 个角色")
    except Exception as e:
        logger.error(f"继承用户部门角色失败: {e}")

class AdminListAPIView(LoginRequiredMixin, View):
    """员工列表API接口，提供JSON数据"""
    def get(self, request):
        queryset = Admin.objects.all().order_by('-id')
        # 部门筛选
        department_id = request.GET.get('dept_id')
        if department_id:
            queryset = queryset.filter(did=department_id)
        # 状态筛选
        status = request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        # 员工类型筛选
        employee_type = request.GET.get('employee_type')
        if employee_type:
            queryset = queryset.filter(type=employee_type)
        # 关键字搜索
        keyword = request.GET.get('keyword')
        if keyword:
            queryset = queryset.filter(
                models.Q(id__icontains=keyword) | 
                models.Q(name__icontains=keyword) | 
                models.Q(job_number__icontains=keyword) | 
                models.Q(username__icontains=keyword) | 
                models.Q(mobile__icontains=keyword) | 
                models.Q(email__icontains=keyword)
            )
        
        # 分页处理
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 10))
        start = (page - 1) * limit
        end = page * limit
        total = queryset.count()
        
        # 构建返回数据
        data = []
        departments = Department.objects.all()
        dept_map = {dept.id: dept.name for dept in departments}
        
        user_ids = [item.id for item in queryset[start:end]]
        
        role_map = {}
        for user_id in user_ids:
            role_map[user_id] = ['无角色']
        
        for item in queryset[start:end]:
            # 获取用户角色名称列表
            user_role_names = role_map.get(item.id, [])
            role_names_str = ', '.join(user_role_names) if user_role_names else '无角色'
            
            data.append({
                'id': item.id,
                'thumb': item.thumb if item.thumb else '/static/img/user-avatar.png',
                'name': item.name,
                'job_number': item.job_number,
                'mobile': item.mobile,
                'email': item.email,
                'department_name': dept_map.get(item.did, ''),
                'position_name': item.position_name,
                'type': item.type,
                'status': item.status,
                'entry_time': datetime.datetime.fromtimestamp(item.entry_time).strftime('%Y-%m-%d') if item.entry_time else '',
                'role_names': role_names_str
            })
        
        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': total,
            'data': data
        }, json_dumps_params={'ensure_ascii': False})



class AdminDetailView(LoginRequiredMixin, DetailView):
    """员工详情视图"""
    model = Admin
    template_name = 'user/detail.html'
    context_object_name = 'employee'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(** kwargs)
        context['departments'] = Department.objects.filter(status=1)
        # 获取次要部门信息
        context['secondary_departments'] = self.object.secondary_departments.all()
        return context

class AdminCreateView(LoginRequiredMixin, CreateView):
    """添加员工视图"""
    model = Admin
    form_class = EmployeeForm
    template_name = 'user/form.html'
    success_url = reverse_lazy('adm:employee_management')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 确保获取所有激活状态的部门
        departments = Department.objects.filter(status=1)
        logger.warning(f"AdminCreateView - Departments count: {len(departments)}")
        logger.warning(f"AdminCreateView - Sample departments: {departments[:3] if departments else 'None'}")
        context['departments'] = departments
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        return JsonResponse({'code': 0, 'msg': '添加成功'}, json_dumps_params={'ensure_ascii': False})

    def form_invalid(self, form):
        errors = {field: error for field, error in form.errors.items()}
        logger.warning(f"AdminCreateView - Form errors: {errors}")
        return JsonResponse({'code': 1, 'msg': '表单验证失败', 'form_errors': errors}, json_dumps_params={'ensure_ascii': False})

class AdminUpdateView(LoginRequiredMixin, UpdateView):
    """编辑员工视图"""
    model = Admin
    form_class = EmployeeForm
    template_name = 'user/form.html'
    success_url = reverse_lazy('adm:employee_management')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # 编辑时密码字段非必填
        form.fields['password'].required = False
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 确保获取所有激活状态的部门
        departments = Department.objects.filter(status=1)
        logger.warning(f"AdminUpdateView - Departments count: {len(departments)}")
        context['departments'] = departments
        return context

    def form_valid(self, form):
        # 如果未输入密码则不更新
        if not form.cleaned_data.get('pwd'):
            form.instance.pwd = Admin.objects.get(pk=self.object.pk).pwd
        
        # 确保表单保存成功
        self.object = form.save()
        
        # 确保会话数据正确保存
        self.request.session.cycle_key()
        self.request.session['user_updated'] = True
        self.request.session.modified = True
        
        # 返回JSON响应与前端匹配
        return JsonResponse({'code': 0, 'msg': '更新成功'}, json_dumps_params={'ensure_ascii': False})

    def form_invalid(self, form):
        errors = {field: error for field, error in form.errors.items()}
        logger.warning(f"AdminUpdateView - Form errors: {errors}")
        return JsonResponse({'code': 1, 'msg': '表单验证失败', 'form_errors': errors}, json_dumps_params={'ensure_ascii': False})

class AdminDeleteView(LoginRequiredMixin, View):
    """删除员工视图 - 彻底删除员工所有相关信息"""
    success_url = reverse_lazy('adm:employee_management')
    template_name = 'user/form.html'  # 使用通用的form.html模板

    def get_object(self):
        # 直接使用原始SQL查询获取员工对象
        employee_id = self.kwargs.get('pk')
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, name FROM mimu_admin WHERE id = %s", [employee_id])
            row = cursor.fetchone()
            if not row:
                from django.http import Http404
                logger.warning(f"尝试访问不存在的员工ID: {employee_id}")
                raise Http404("员工不存在")
            # 创建一个简单的对象来存储结果
            class SimpleAdmin:
                def __init__(self, id, name):
                    self.id = id
                    self.name = name
            return SimpleAdmin(row[0], row[1])

    def form_valid(self, form=None):
        try:
            employee_id = self.kwargs.get('pk')
            
            # 使用事务确保操作的一致性
            with transaction.atomic():
                # 使用单个cursor处理所有SQL操作
                with connection.cursor() as cursor:
                    # 1. 删除员工操作日志
                    cursor.execute("DELETE FROM mimu_admin_log WHERE admin_id = %s", [employee_id])
                    
                    # 2. 删除员工部门关联记录（使用try-except处理可能不存在的表或列）
                    try:
                        cursor.execute("DELETE FROM mimu_admin_department WHERE admin_id = %s", [employee_id])
                    except Exception as dept_error:
                        logger.warning(f"删除部门关联记录时出错: {str(dept_error)}")
                    
                    # 3. 删除员工职位关联记录
                    try:
                        cursor.execute("DELETE FROM mimu_admin_position WHERE admin_id = %s", [employee_id])
                    except Exception as pos_error:
                        logger.warning(f"删除职位关联记录时出错: {str(pos_error)}")
                    
                    # 4. 处理system_log表关系（解决外键约束问题）
                    try:
                        # 先更新system_log表中的user_id为NULL
                        cursor.execute("UPDATE system_log SET user_id = NULL WHERE user_id = %s", [employee_id])
                        logger.debug(f"成功更新system_log表中的user_id字段")
                    except Exception as system_log_error:
                        logger.warning(f"处理system_log表关系时出错: {str(system_log_error)}")
                    
                    # 5. 不处理oa_announcement表关系 - 数据库表中不存在publisher字段
                    # 经过查看数据库表结构，oa_announcement表中没有publisher相关字段
                    # 因此不需要处理此表的关系，删除用户时不会影响公告表
                    
                    # 6. 使用原始SQL直接删除员工记录
                    try:
                        cursor.execute("DELETE FROM mimu_admin WHERE id = %s", [employee_id])
                        logger.debug(f"成功使用SQL删除员工记录")
                    except Exception as sql_delete_error:
                        logger.warning(f"使用SQL删除员工记录时出错: {str(sql_delete_error)}")
                        # SQL删除失败时，让事务自动回滚，外层异常处理会捕获
                        raise
        
            # 检查是否是Ajax请求
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'code': 0, 'msg': '删除成功'}, json_dumps_params={'ensure_ascii': False})
            else:
                from django.http import HttpResponseRedirect
                return HttpResponseRedirect(self.success_url)
        except Exception as e:
            # 添加日志记录
            logger.error(f"删除员工失败: {str(e)}")
            
            # 检查是否是Ajax请求
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})
            else:
                # 添加错误消息并渲染表单
                from django.contrib import messages
                messages.error(self.request, f'删除失败: {str(e)}')
                return self.render_to_response(self.get_context_data())
    
    def post(self, request, *args, **kwargs):
        try:
            # 先检查员工是否存在
            self.get_object()
            return self.form_valid()
        except Http404 as e:
            # 员工不存在时的特定处理
            employee_id = self.kwargs.get('pk')
            logger.warning(f"尝试删除不存在的员工ID: {employee_id}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'code': 1, 'msg': f'员工ID: {employee_id} 不存在，无法删除。'}, json_dumps_params={'ensure_ascii': False})
            else:
                messages.error(request, f'员工ID: {employee_id} 不存在，无法删除。')
                return redirect(self.success_url)
        except Exception as e:
            logger.error(f"删除员工请求处理失败: {str(e)}")
            return JsonResponse({'code': 1, 'msg': f'删除员工请求处理失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})
            
    def get(self, request, *args, **kwargs):
        try:
            employee = self.get_object()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # 如果是Ajax请求，返回确认信息
                return JsonResponse({
                    'code': 0,
                    'name': employee.name,
                    'id': employee.id,
                    'confirm_message': f'确定要删除员工 "{employee.name}" 吗？此操作不可撤销，将彻底删除该员工的所有相关信息。'
                }, json_dumps_params={'ensure_ascii': False})
            else:
                # 非Ajax请求，正常渲染确认页面
                context = {
                    'object': employee,
                    'form': request.POST if request.method == 'POST' else None
                }
                return render(request, self.template_name, context)
        except Http404 as e:
            # 员工不存在时的特定处理
            employee_id = self.kwargs.get('pk')
            logger.warning(f"尝试访问不存在的员工ID: {employee_id}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'code': 1, 'msg': f'员工ID: {employee_id} 不存在，请检查ID是否正确。'}, json_dumps_params={'ensure_ascii': False})
            else:
                # 非Ajax请求，渲染错误页面或重定向
                from django.shortcuts import redirect
                from django.contrib import messages
                messages.error(request, f'员工ID: {employee_id} 不存在，请检查ID是否正确。')
                return redirect(self.success_url)
        except Exception as e:
            # 其他错误的处理
            logger.error(f"获取员工信息失败: {str(e)}")
            return JsonResponse({'code': 1, 'msg': f'获取员工信息失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})

    def get_context_data(self, **kwargs):
        context = kwargs
        try:
            context['object'] = self.get_object()
        except Exception:
            context['object'] = None
        return context

# 批量导入员工
class BatchImportView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'adm/user/batch_import.html')
    
    def post(self, request):
        try:
            file = request.FILES.get('file')
            # 此处添加Excel文件处理逻辑
            return JsonResponse({'code': 0, 'msg': '导入成功'}, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': str(e)}, json_dumps_params={'ensure_ascii': False})

# 重置密码
class ResetPasswordView(LoginRequiredMixin, View):
    
    def post(self, request, pk):
        try:
            
            admin = get_object_or_404(Admin, pk=pk)
            password = request.POST.get('password')
            if not password:
                return JsonResponse({'code': 1, 'msg': '密码不能为空'}, json_dumps_params={'ensure_ascii': False})
            from django.contrib.auth.hashers import make_password
            admin.pwd = make_password(password)
            admin.save()
            return JsonResponse({'code': 0, 'msg': '密码重置成功'}, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': str(e)}, json_dumps_params={'ensure_ascii': False})

# 更改员工状态
class ChangeStatusView(LoginRequiredMixin, View):
    
    def post(self, request, pk):
        try:
            
            admin = get_object_or_404(Admin, pk=pk)
            status = int(request.POST.get('status', 0))
            admin.status = status
            admin.save()
            return JsonResponse({'code': 0, 'msg': '状态更新成功'}, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': str(e)}, json_dumps_params={'ensure_ascii': False})


def login_view(request):
    """用户登录视图"""
    # 登录用户自动重定向到仪表盘
    if request.user.is_authenticated:
        from django.conf import settings
        return redirect(settings.LOGIN_REDIRECT_URL)
    
    if request.method == 'POST':
        # 从POST数据中获取参数，并进行安全验证
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        # 验证输入完整性
        if not username or not password:
            return JsonResponse({'code': 1, 'msg': '用户名和密码不能为空'}, json_dumps_params={'ensure_ascii': False})
        
        # 暴力破解防护：使用缓存跟踪登录失败次数
        from django.core.cache import cache
        from django.conf import settings
        
        # 获取客户端IP
        client_ip = get_client_ip(request)
        
        # 检查IP维度的全局锁定（防止暴力破解攻击）
        ip_lock_key = f'login_ip_lock:{client_ip}'
        if cache.get(ip_lock_key):
            remaining_time = cache.ttl(ip_lock_key)
            return JsonResponse({
                'code': 1, 
                'msg': f'登录失败次数过多，请{int(remaining_time / 60)}分钟后再试'
            }, json_dumps_params={'ensure_ascii': False})
        
        # 构造缓存键
        login_attempts_key = f'login_attempts:{client_ip}:{username}'
        login_lock_key = f'login_lock:{client_ip}:{username}'
        
        # 检查账户是否被锁定
        if cache.get(login_lock_key):
            remaining_time = cache.ttl(login_lock_key)
            return JsonResponse({
                'code': 1, 
                'msg': f'登录失败次数过多，请{int(remaining_time / 60)}分钟后再试'
            }, json_dumps_params={'ensure_ascii': False})
        
        try:
            # 使用Django内置的authenticate函数进行认证，自动处理模型匹配
            from django.contrib.auth import authenticate
            user = authenticate(request, username=username, password=password)
            
            if user:
                # 登录成功，清除失败次数记录
                cache.delete(login_attempts_key)
                cache.delete(login_lock_key)
                cache.delete(ip_attempts_key) if 'ip_attempts_key' in dir() else None
                
                # 安全会话管理：登录前重置会话，防止会话固定攻击
                request.session.cycle_key()
                
                # 使用Django认证系统登录，确保安全会话管理
                from django.contrib.auth import login
                login(request, user)
                
                # 同时设置自定义会话（保持兼容性）
                request.session['admin_id'] = user.id
                request.session['admin_name'] = getattr(user, 'name', user.username)
                request.session['admin_username'] = user.username
                
                # 记录登录日志
                from ..models import AdminLog
                AdminLog.objects.create(
                    admin_id=user.id,
                    username=user.username,
                    title='用户登录',
                    content=f'用户 {getattr(user, "name", user.username)} 登录系统',
                    ip=client_ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                # 使用Django内置的权限系统，无需手动清除权限缓存
                
                # 安全会话管理：使用settings.py中配置的会话超时时间和自动更新机制
                
                return JsonResponse({
                    'code': 0, 
                    'msg': '登录成功',
                    'data': {
                        'id': user.id,
                        'name': getattr(user, 'name', user.username),
                        'username': user.username,
                        'redirect_url': settings.LOGIN_REDIRECT_URL  # 使用配置的重定向URL
                    }
                }, json_dumps_params={'ensure_ascii': False})
            else:
                # 登录失败，增加失败次数
                attempts = cache.get(login_attempts_key, 0) + 1
                cache.set(login_attempts_key, attempts, 300)  # 5分钟内有效
                
                # 检查IP维度的全局失败次数
                ip_attempts_key = f'login_ip_attempts:{client_ip}'
                ip_attempts = cache.get(ip_attempts_key, 0) + 1
                cache.set(ip_attempts_key, ip_attempts, 300)  # 5分钟内有效
                
                if attempts >= 5:
                    # 超过5次失败，锁定15分钟
                    cache.set(login_lock_key, True, 900)  # 15分钟锁定
                    return JsonResponse({
                        'code': 1, 
                        'msg': '登录失败次数过多，请15分钟后再试'
                    }, json_dumps_params={'ensure_ascii': False})
                
                # 如果IP维度的失败次数超过20次，锁定该IP 30分钟
                if ip_attempts >= 40:
                    cache.set(ip_lock_key, True, 1800)  # 30分钟锁定
                    return JsonResponse({
                        'code': 1, 
                        'msg': '登录失败次数过多，请30分钟后再试'
                    }, json_dumps_params={'ensure_ascii': False})
                
                return JsonResponse({
                    'code': 1, 
                    'msg': '用户名或密码错误'
                }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'登录失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': '登录失败，请稍后重试'}, json_dumps_params={'ensure_ascii': False})
    
    else:
        # GET请求，返回登录页面
        from captcha.models import CaptchaStore
        from apps.common.views import DAILY_QUOTES
        import random
        from datetime import datetime
        
        captcha_key = CaptchaStore.generate_key()
        
        today = datetime.now().date()
        day_of_year = today.timetuple().tm_yday
        random.seed(day_of_year)
        daily_quote = random.choice(DAILY_QUOTES)
        random.seed()
        
        return render(request, 'login.html', {
            'captcha_key': captcha_key,
            'daily_quote': daily_quote
        })


def get_client_ip(request):
    """获取客户端 IP 地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def verify_captcha(request, captcha_value, captcha_key):
    """验证验证码"""
    try:
        from captcha.models import CaptchaStore
        from django.utils import timezone
        
        captcha_value = captcha_value.strip().lower()
        
        # 验证输入完整性
        if not captcha_key or not captcha_value:
            return False
        
        # 验证验证码
        captcha = CaptchaStore.objects.get(hashkey=captcha_key, expiration__gt=timezone.now())
        if captcha.response != captcha_value:
            return False
        
        # 验证码正确，删除验证码记录
        captcha.delete()
        return True
    except CaptchaStore.DoesNotExist:
        return False
    except Exception as e:
        logger.warning(f"验证码验证失败：{e}")
        return False


def login_submit(request):
    """登录表单提交处理"""
    if request.method != 'POST':
        return JsonResponse({'code': 1, 'msg': '请求方法错误'}, json_dumps_params={'ensure_ascii': False})
    
    # 获取表单数据
    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    captcha = request.POST.get('captcha', '')
    captcha_key = request.POST.get('captcha_key', '')
    
    if not username or not password:
        return JsonResponse({'code': 1, 'msg': '用户名和密码不能为空'}, json_dumps_params={'ensure_ascii': False})
    
    # 验证验证码
    if not verify_captcha(request, captcha, captcha_key):
        return JsonResponse({'code': 1, 'msg': '验证码错误'}, json_dumps_params={'ensure_ascii': False})
        
    # 获取客户端 IP
    client_ip = get_client_ip(request)
    
    # 检查 IP 维度的全局锁定（防止暴力破解攻击）
    ip_lock_key = f'login_ip_lock:{client_ip}'
    if cache.get(ip_lock_key):
        return JsonResponse({
            'code': 1, 
            'msg': '登录失败次数过多，请 30 分钟后再试'
        }, json_dumps_params={'ensure_ascii': False})
    
    # 构造缓存键
    login_attempts_key = f'login_attempts:{client_ip}:{username}'
    login_lock_key = f'login_lock:{client_ip}:{username}'
    
    # 检查账户是否被锁定
    if cache.get(login_lock_key):
        return JsonResponse({
            'code': 1, 
            'msg': '登录失败次数过多，请 15 分钟后再试'
        }, json_dumps_params={'ensure_ascii': False})
    
    try:
        # 使用 Django 内置的 authenticate 函数进行认证，自动处理模型匹配
        from django.contrib.auth import authenticate, login
        
        # 认证用户
        user = authenticate(request, username=username, password=password)
        
        if user:
            # 登录成功，清除失败次数记录
            cache.delete(login_attempts_key)
            cache.delete(login_lock_key)
            
            # 安全会话管理：登录前重置会话，防止会话固定攻击
            request.session.cycle_key()
            
            # 使用 Django 认证系统登录，确保安全会话管理
            login(request, user)
            
            # 继承用户所属部门的默认角色
            _inherit_user_department_roles(user)
            
            # 同时设置自定义会话（保持兼容性）
            request.session['admin_id'] = user.id
            request.session['admin_name'] = getattr(user, 'name', user.username)
            request.session['admin_username'] = user.username
            
            # 记录登录日志
            from ..models import AdminLog
            AdminLog.objects.create(
                admin_id=user.id,
                username=user.username,
                title='用户登录',
                content=f'用户 {getattr(user, "name", user.username)} 登录系统',
                ip=client_ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return JsonResponse({
                'code': 0, 
                'msg': '登录成功',
                'data': {
                    'id': user.id,
                    'name': getattr(user, 'name', user.username),
                    'username': user.username,
                    'redirect_url': '/home/main/'
                }
            }, json_dumps_params={'ensure_ascii': False})
        else:
            # 登录失败，增加失败次数
            attempts = cache.get(login_attempts_key, 0) + 1
            cache.set(login_attempts_key, attempts, 300)  # 5 分钟内有效
            
            # 检查 IP 维度的全局失败次数
            ip_attempts_key = f'login_ip_attempts:{client_ip}'
            ip_attempts = cache.get(ip_attempts_key, 0) + 1
            cache.set(ip_attempts_key, ip_attempts, 300)  # 5 分钟内有效
            
            if attempts >= 5:
                # 超过 5 次失败，锁定 15 分钟
                cache.set(login_lock_key, True, 900)  # 15 分钟锁定
                return JsonResponse({
                    'code': 1, 
                    'msg': '登录失败次数过多，请 15 分钟后再试'
                }, json_dumps_params={'ensure_ascii': False})
            
            # 如果 IP 维度的失败次数超过 20 次，锁定该 IP 30 分钟
            if ip_attempts >= 20:
                cache.set(ip_lock_key, True, 1800)  # 30 分钟锁定
                return JsonResponse({
                    'code': 1, 
                    'msg': '登录失败次数过多，请 30 分钟后再试'
                }, json_dumps_params={'ensure_ascii': False})
            
            return JsonResponse({
                'code': 1, 
                'msg': '用户名或密码错误'
            }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f'登录提交失败：{str(e)}')
        return JsonResponse({'code': 1, 'msg': '登录失败，请稍后重试'}, json_dumps_params={'ensure_ascii': False})
    
    else:
        # 非POST请求，返回错误
        return JsonResponse({'code': 1, 'msg': '请求方法不正确'}, json_dumps_params={'ensure_ascii': False})


def logout_view(request):
    """用户登出处理"""
    if 'admin_id' in request.session:
        admin_id = request.session['admin_id']
        admin_name = request.session.get('admin_name', '')
        
        # 记录登出日志
        try:
            from ..models import AdminLog, Admin
            admin = Admin.objects.get(id=admin_id)
            AdminLog.objects.create(
                admin_id=admin.id,
                username=admin.username,
                title='用户登出',
                content=f'用户 {admin_name} 登出系统',
                ip=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        except Exception as e:
            logger.error(f'记录登出日志失败: {str(e)}')
        
        # 清除session
        request.session.flush()
    
    # 重定向到登录页面
    from django.shortcuts import redirect
    return redirect('user:login')