"""
自定义认证后端
用于处理Admin模型的权限检查
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Group
from apps.user.models.permission import DepartmentGroup, GroupExtension
from apps.user.models import Admin
from apps.department.models import Department
from django.core.cache import cache
import logging

logger = logging.getLogger('django')

AUTH_CACHE_TIMEOUT = 5 * 60


class AdminAuthBackend(ModelBackend):
    """
    自定义认证后端，处理Admin模型的权限检查
    支持部门角色权限继承
    """

    def _get_user_department_groups(self, user_obj):
        """
        获取用户所属部门的角色
        仅获取用户直接所属部门的角色，不继承上级部门的权限
        """
        if not user_obj or not user_obj.is_authenticated:
            return set()

        if not hasattr(user_obj, 'did') or not user_obj.did:
            return set()

        cache_key = f'user_dept_groups_{user_obj.id}_{user_obj.did}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            department = Department.objects.filter(id=user_obj.did).first()

            if department and department.status == 1:
                department_groups = DepartmentGroup.objects.filter(
                    department=department)
                department_group_ids = {
                    dg.group.id for dg in department_groups}
                cache.set(cache_key, department_group_ids, AUTH_CACHE_TIMEOUT)
                return department_group_ids
        except Exception as e:
            logger.error(f"获取用户部门角色失败: {e}")

        cache.set(cache_key, set(), AUTH_CACHE_TIMEOUT)
        return set()

    def _get_all_user_groups(self, user_obj):
        """
        获取用户的所有角色（包括个人角色和部门角色）
        """
        if not user_obj or not user_obj.is_authenticated:
            return set()

        cache_key = f'user_all_groups_{user_obj.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        user_groups = set()
        if hasattr(user_obj, 'groups'):
            user_groups = {group.id for group in user_obj.groups.all()}

        department_groups = self._get_user_department_groups(user_obj)

        all_groups = user_groups | department_groups

        cache.set(cache_key, all_groups, AUTH_CACHE_TIMEOUT)
        return all_groups

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        认证用户，返回Admin实例
        统一使用pwd字段进行密码验证
        """
        try:
            user = Admin.objects.get(username=username)

            if user.status != 1:
                return None

            if not user.is_active:
                user.is_active = True
                user.save()

            from django.contrib.auth.hashers import check_password
            # 统一使用pwd字段进行密码验证
            if check_password(password, user.pwd):
                user.backend = 'apps.user.auth_backend.AdminAuthBackend'
                return user
        except Admin.DoesNotExist:
            return None
        return None

    def get_user(self, user_id):
        """
        根据user_id获取用户实例
        """
        try:
            user = Admin.objects.get(pk=user_id)

            if user.status != 1:
                return None

            if not user.is_active:
                user.is_active = True
                user.save()

            user.backend = 'apps.user.auth_backend.AdminAuthBackend'
            return user
        except Admin.DoesNotExist:
            return None
        except Exception:
            return None

    def has_perm(self, user_obj, perm, obj=None):
        """
        检查用户是否有权限
        """
        if not user_obj:
            return False

        is_active = getattr(user_obj, 'status', 0) == 1

        if not is_active:
            return False

        if getattr(user_obj, 'is_superuser', False):
            return True

        if '.' not in perm:
            return False

        all_permissions = self.get_all_permissions(user_obj, obj)

        if '*' in all_permissions:
            return True

        return perm in all_permissions

    def has_module_perms(self, user_obj, app_label):
        """
        检查用户是否有权限访问整个应用
        """
        if not user_obj:
            return False

        is_active = getattr(user_obj, 'status', 0) == 1

        if not is_active:
            return False

        if getattr(user_obj, 'is_superuser', False):
            return True

        all_permissions = self.get_all_permissions(user_obj)

        if '*' in all_permissions:
            return True

        for perm in all_permissions:
            if perm.startswith(f'{app_label}.'):
                return True

        return False

    def get_group_permissions(self, user_obj, obj=None):
        """
        获取用户组权限（包括部门角色权限）
        """
        if not user_obj:
            return set()

        is_active = getattr(user_obj, 'status', 0) == 1

        if not is_active:
            return set()

        if getattr(user_obj, 'is_superuser', False):
            return set(['*'])

        cache_key = f'user_group_perms_{user_obj.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        all_group_ids = self._get_all_user_groups(user_obj)

        permissions = set()

        groups = Group.objects.filter(id__in=all_group_ids)

        for group in groups:
            try:
                try:
                    group_extension = GroupExtension.objects.filter(
                        group=group).first()
                    if group_extension is not None and not group_extension.status:
                        continue
                except Exception:
                    pass

                for perm in group.permissions.all():
                    perm_str = f"{perm.content_type.app_label}.{perm.codename}"
                    permissions.add(perm_str)
            except Exception as e:
                logger.error(f"获取角色权限失败 (group_id={group.id}): {e}")
                continue

        cache.set(cache_key, permissions, AUTH_CACHE_TIMEOUT)
        return permissions

    def get_user_permissions(self, user_obj, obj=None):
        """
        获取用户个人权限
        """
        if not user_obj:
            return set()

        is_active = getattr(user_obj, 'status', 0) == 1

        if not is_active:
            return set()

        if getattr(user_obj, 'is_superuser', False):
            return set(['*'])

        cache_key = f'user_perms_{user_obj.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        permissions = set()
        if hasattr(user_obj, 'user_permissions'):
            for perm in user_obj.user_permissions.all():
                perm_str = f"{perm.content_type.app_label}.{perm.codename}"
                permissions.add(perm_str)

        cache.set(cache_key, permissions, AUTH_CACHE_TIMEOUT)
        return permissions

    def get_all_permissions(self, user_obj, obj=None):
        """
        获取用户所有权限（包括个人权限、角色权限和部门角色权限）
        """
        if not user_obj:
            return set()

        is_active = getattr(user_obj, 'status', 0) == 1

        if not is_active:
            return set()

        if getattr(user_obj, 'is_superuser', False):
            return set(['*'])

        cache_key = f'user_all_perms_{user_obj.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        user_permissions = self.get_user_permissions(user_obj, obj)
        group_permissions = self.get_group_permissions(user_obj, obj)

        all_permissions = user_permissions | group_permissions

        cache.set(cache_key, all_permissions, AUTH_CACHE_TIMEOUT)
        return all_permissions
