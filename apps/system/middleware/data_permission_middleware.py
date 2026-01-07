"""
数据权限控制中间件
确保用户只能访问授权的数据范围
"""
import re
from django.http import HttpResponseForbidden
from django.conf import settings
from apps.user.models import Admin


class DataPermissionMiddleware:
    """
    数据权限中间件
    控制用户只能访问其权限范围内的数据
    """
    
    EXEMPT_URLS = [
        r'^/api/auth/',
        r'^/api/user/login/',
        r'^/api/user/logout/',
        r'^/api/user/password/',
        r'^/home/',
        r'^/api/common/',
        r'^/media/',
        r'^/static/',
    ]
    
    EXEMPT_VIEWS = [
        'home',
        'login', 
        'logout',
        'password_reset',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = [re.compile(url) for url in self.EXEMPT_URLS]
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        在视图执行前检查数据权限
        """
        if self._is_exempt(request.path):
            return None
        
        user = request.user
        
        if not user or not user.is_authenticated:
            return None
        
        if user.is_superuser:
            return None
        
        employee = getattr(user, 'employee', None)
        
        if not employee:
            return None
        
        return None
    
    def _is_exempt(self, path):
        """检查路径是否豁免数据权限检查"""
        from django.urls import resolve
        try:
            match = resolve(path)
            view_name = match.func.__name__
            if view_name in self.EXEMPT_VIEWS:
                return True
        except:
            pass
        
        for url_pattern in self.exempt_urls:
            if url_pattern.match(path):
                return True
        return False


class DataScopeFilter:
    """
    数据范围过滤器
    用于在QuerySet中过滤用户有权访问的数据
    """
    
    SCOPE_CHOICES = {
        'all': '全部数据',
        'department': '本部门数据',
        'self': '仅本人数据',
        'self_and_department': '本人及本部门数据',
    }
    
    @classmethod
    def filter_queryset(cls, user, queryset, scope_field='created_by_id', department_field='department_id'):
        """
        根据用户权限过滤QuerySet
        
        Args:
            user: 当前用户
            queryset: 原始QuerySet
            scope_field: 创建者ID字段名
            department_field: 部门ID字段名
            
        Returns:
            过滤后的QuerySet
        """
        if not user or not user.is_authenticated:
            return queryset.none()
        
        if user.is_superuser:
            return queryset
        
        employee = getattr(user, 'employee', None)
        
        if not employee:
            return queryset.none()
        
        if employee.is_admin:
            return queryset
        
        employee_dept_id = getattr(employee, 'department_id', None)
        
        if not employee_dept_id:
            return queryset.filter(**{scope_field: user.id})
        
        from django.db.models import Q
        return queryset.filter(
            Q(**{scope_field: user.id}) | 
            Q(**{department_field: employee_dept_id})
        ).distinct()
    
    @classmethod
    def get_user_data_scope(cls, user):
        """
        获取用户的数据权限范围
        
        Returns:
            dict: {
                'scope': 权限范围代码,
                'scope_name': 权限范围名称,
                'department_id': 部门ID,
                'can_view_all': 是否可以查看全部数据,
                'can_view_department': 是否可以查看部门数据,
                'can_view_self': 是否只能查看本人数据,
            }
        """
        if not user or not user.is_authenticated:
            return {
                'scope': 'none',
                'scope_name': '无权限',
                'department_id': None,
                'can_view_all': False,
                'can_view_department': False,
                'can_view_self': False,
            }
        
        if user.is_superuser:
            return {
                'scope': 'all',
                'scope_name': '全部数据',
                'department_id': None,
                'can_view_all': True,
                'can_view_department': True,
                'can_view_self': True,
            }
        
        employee = getattr(user, 'employee', None)
        
        if not employee:
            return {
                'scope': 'self',
                'scope_name': '仅本人数据',
                'department_id': None,
                'can_view_all': False,
                'can_view_department': False,
                'can_view_self': True,
            }
        
        if employee.is_admin:
            return {
                'scope': 'all',
                'scope_name': '全部数据',
                'department_id': employee.department_id,
                'can_view_all': True,
                'can_view_department': True,
                'can_view_self': True,
            }
        
        return {
            'scope': 'self_and_department',
            'scope_name': '本人及本部门数据',
            'department_id': employee.department_id,
            'can_view_all': False,
            'can_view_department': True,
            'can_view_self': True,
        }
    
    @classmethod
    def filter_by_data_owner(cls, user, queryset, owner_field='created_by'):
        """
        过滤：只返回用户有权查看的数据所有者创建的数据
        
        Args:
            user: 当前用户
            queryset: 原始QuerySet
            owner_field: 数据所有者字段名
            
        Returns:
            过滤后的QuerySet
        """
        if not user or not user.is_authenticated:
            return queryset.none()
        
        if user.is_superuser:
            return queryset
        
        employee = getattr(user, 'employee', None)
        
        if not employee:
            return queryset.filter(**{owner_field: user.id})
        
        employee_dept_id = getattr(employee, 'department_id', None)
        
        if not employee_dept_id:
            return queryset.filter(**{owner_field: user.id})
        
        from django.db.models import Q
        return queryset.filter(
            Q(**{owner_field: user.id}) | 
            Q(**{f'{owner_field}__department_id': employee_dept_id})
        ).distinct()


class PermissionChecker:
    """
    权限检查器
    提供细粒度的权限检查功能
    """
    
    @staticmethod
    def can_view(user, resource_type):
        """
        检查用户是否可以查看指定类型的资源
        
        Args:
            user: 用户对象
            resource_type: 资源类型（如 'customer', 'contract', 'project'）
            
        Returns:
            bool: 是否有查看权限
        """
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_perm(f'user.view_{resource_type}')
    
    @staticmethod
    def can_add(user, resource_type):
        """
        检查用户是否可以创建指定类型的资源
        """
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_perm(f'user.add_{resource_type}')
    
    @staticmethod
    def can_change(user, resource_type):
        """
        检查用户是否可以修改指定类型的资源
        """
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_perm(f'user.change_{resource_type}')
    
    @staticmethod
    def can_delete(user, resource_type):
        """
        检查用户是否可以删除指定类型的资源
        """
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_perm(f'user.delete_{resource_type}')
    
    @staticmethod
    def can_approve(user, resource_type):
        """
        检查用户是否可以审批指定类型的资源
        """
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_perm(f'user.approve_{resource_type}')
    
    @staticmethod
    def can_export(user, resource_type):
        """
        检查用户是否可以导出指定类型的资源
        """
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_perm(f'user.export_{resource_type}')
    
    @staticmethod
    def can_import(user, resource_type):
        """
        检查用户是否可以导入指定类型的资源
        """
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_perm(f'user.import_{resource_type}')
    
    @staticmethod
    def can_operate(user, operation_code):
        """
        检查用户是否拥有指定操作权限
        
        Args:
            user: 用户对象
            operation_code: 操作代码（如 'view_customer', 'approve_contract'）
            
        Returns:
            bool: 是否有权限
        """
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_perm(f'user.{operation_code}')
    
    @staticmethod
    def can_access_menu(user, menu_code):
        """
        检查用户是否可以访问指定菜单
        
        Args:
            user: 用户对象
            menu_code: 菜单代码
        """
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.has_perm(f'user.view_{menu_code}')
