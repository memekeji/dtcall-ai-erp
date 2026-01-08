"""
自定义认证后端
用于处理Admin模型的权限检查
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Group, Permission
from apps.user.models_new import DepartmentGroup, GroupExtension
from apps.user.models import Admin
from apps.department.models import Department


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
        
        department = None
        
        try:
            # 处理Admin模型（旧版用户模型）
            if hasattr(user_obj, 'did') and user_obj.did:
                department = Department.objects.filter(id=user_obj.did).first()
            # 处理UserNew模型（新版用户模型）
            elif hasattr(user_obj, 'department') and user_obj.department:
                department = user_obj.department
            
            if department:
                # 只获取启用且未被软删除的部门
                # Department模型的is_deleted是计算属性，status=1表示启用
                if department.status == 1:
                    # 仅获取用户直接所属部门的角色，不继承上级部门的权限
                    department_groups = DepartmentGroup.objects.filter(department=department)
                    department_group_ids = {dg.group.id for dg in department_groups}
                    return department_group_ids
        except Exception as e:
            # 记录异常，但继续执行
            import logging
            logging.error(f"获取用户部门角色失败: {e}")
        
        return set()
    
    def _get_all_user_groups(self, user_obj):
        """
        获取用户的所有角色（包括个人角色和部门角色）
        """
        if not user_obj or not user_obj.is_authenticated:
            return set()
        
        # 获取用户直接分配的角色
        user_groups = set()
        if hasattr(user_obj, 'groups'):
            user_groups = {group.id for group in user_obj.groups.all()}
        
        # 获取部门角色
        department_groups = self._get_user_department_groups(user_obj)
        
        # 合并用户角色和部门角色
        all_groups = user_groups | department_groups
        
        return all_groups
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        认证用户，返回Admin实例
        """
        try:
            # 通过用户名获取用户
            user = Admin.objects.get(username=username)
            
            # 检查用户状态
            if user.status != 1:
                return None
            
            # 确保is_active为True
            if not user.is_active:
                user.is_active = True
                user.save()
            
            # 使用Django内置的密码验证方法
            from django.contrib.auth.hashers import check_password
            if check_password(password, user.pwd):
                # 设置用户的backend属性，以便auth_login()函数能够正确登录用户
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
            # 从Admin表中获取用户
            user = Admin.objects.get(pk=user_id)
            
            # 检查用户状态
            if user.status != 1:
                return None
            
            # 确保is_active为True
            if not user.is_active:
                user.is_active = True
                user.save()
            
            # 设置用户的backend属性，确保权限检查使用正确的后端
            user.backend = 'apps.user.auth_backend.AdminAuthBackend'
            return user
        except Admin.DoesNotExist:
            return None
        except Exception:
            return None
    
    def has_perm(self, user_obj, perm, obj=None):
        """
        检查用户是否有权限
        超级用户自动拥有所有权限
        """
        if not user_obj:
            return False
        
        # 检查用户是否处于活跃状态
        is_active = False
        if hasattr(user_obj, 'status'):
            is_active = (user_obj.status == 1)  # Admin模型的活跃状态是status=1
        
        if not is_active:
            return False
        
        # 超级用户拥有所有权限，无需检查权限是否存在
        if hasattr(user_obj, 'is_superuser') and user_obj.is_superuser:
            return True
        
        # 非超级用户，检查权限格式
        if '.' not in perm:
            return False
        
        # 获取用户所有权限
        all_permissions = self.get_all_permissions(user_obj, obj)
        
        # 如果权限集合包含通配符'*'，表示拥有所有权限
        if '*' in all_permissions:
            return True
        
        # 严格检查完整权限字符串是否匹配
        return perm in all_permissions
    
    def has_module_perms(self, user_obj, app_label):
        """
        检查用户是否有权限访问整个应用
        注意：此方法仅用于检查用户是否有权访问应用的管理界面，
        具体的功能权限仍需通过has_perm方法单独检查
        """
        if not user_obj:
            return False
        
        # 检查用户是否处于活跃状态
        is_active = False
        if hasattr(user_obj, 'status'):
            is_active = (user_obj.status == 1)  # Admin模型的活跃状态是status=1
        
        if not is_active:
            return False
        
        # 超级用户拥有所有权限
        if hasattr(user_obj, 'is_superuser') and user_obj.is_superuser:
            return True
        
        # 获取用户所有权限
        all_permissions = self.get_all_permissions(user_obj)
        
        # 如果权限集合包含通配符'*'，表示拥有所有权限
        if '*' in all_permissions:
            return True
        
        # 检查用户是否拥有该应用的任何权限
        for perm in all_permissions:
            if perm.startswith(f'{app_label}.'):
                return True
        
        # 如果没有该应用的任何权限，则返回False
        return False
    
    def get_group_permissions(self, user_obj, obj=None):
        """
        获取用户组权限（包括部门角色权限）
        返回完整的权限字符串，如：{'user.add_user', 'user.change_user'}
        """
        if not user_obj:
            return set()
        
        # 检查用户是否处于活跃状态
        is_active = False
        if hasattr(user_obj, 'status'):
            is_active = (user_obj.status == 1)  # Admin模型的活跃状态是status=1
        
        if not is_active:
            return set()
        
        # 超级用户拥有所有权限
        if hasattr(user_obj, 'is_superuser') and user_obj.is_superuser:
            return set(['*'])
        
        # 获取用户的所有角色（包括个人角色和部门角色）
        all_group_ids = self._get_all_user_groups(user_obj)
        
        # 获取所有角色的权限
        permissions = set()
        
        # 批量获取所有Group对象，减少数据库查询
        groups = Group.objects.filter(id__in=all_group_ids)
        
        for group in groups:
            try:
                # 检查角色是否启用
                # 如果GroupExtension不存在，默认为启用状态
                group_extension = GroupExtension.objects.filter(group=group).first()
                if group_extension is not None and not group_extension.status:
                    continue
                
                # 直接获取权限字符串，避免后续转换
                for perm in group.permissions.all():
                    perm_str = f"{perm.content_type.app_label}.{perm.codename}"
                    permissions.add(perm_str)
            except Exception as e:
                # 记录异常，但继续执行
                import logging
                logging.error(f"获取角色权限失败 (group_id={group.id}): {e}")
                continue
        
        return permissions
    
    def get_user_permissions(self, user_obj, obj=None):
        """
        获取用户个人权限
        返回完整的权限字符串，如：{'user.add_user', 'user.change_user'}
        """
        if not user_obj:
            return set()
        
        # 检查用户是否处于活跃状态
        is_active = False
        if hasattr(user_obj, 'status'):
            is_active = (user_obj.status == 1)  # Admin模型的活跃状态是status=1
        
        if not is_active:
            return set()
        
        # 超级用户拥有所有权限
        if hasattr(user_obj, 'is_superuser') and user_obj.is_superuser:
            # 为超级用户返回一个特殊的权限标识符，代表所有权限
            return set(['*'])
        
        # 直接获取用户个人权限字符串
        permissions = set()
        if hasattr(user_obj, 'user_permissions'):
            for perm in user_obj.user_permissions.all():
                perm_str = f"{perm.content_type.app_label}.{perm.codename}"
                permissions.add(perm_str)
        return permissions
    
    def get_all_permissions(self, user_obj, obj=None):
        """
        获取用户所有权限（包括个人权限、角色权限和部门角色权限）
        返回完整的权限字符串，如：{'user.add_user', 'user.change_user'}
        """
        if not user_obj:
            return set()
        
        # 检查用户是否处于活跃状态
        is_active = False
        if hasattr(user_obj, 'status'):
            is_active = (user_obj.status == 1)  # Admin模型的活跃状态是status=1
        
        if not is_active:
            return set()
        
        # 超级用户拥有所有权限
        if hasattr(user_obj, 'is_superuser') and user_obj.is_superuser:
            return set(['*'])
        
        # 获取用户个人权限
        user_permissions = self.get_user_permissions(user_obj, obj)
        
        # 获取用户组权限（包括部门角色权限）
        group_permissions = self.get_group_permissions(user_obj, obj)
        
        # 合并个人权限和组权限
        all_permissions = user_permissions | group_permissions
        
        return all_permissions