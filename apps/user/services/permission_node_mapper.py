"""
权限节点映射服务
建立权限配置节点与后端权限检查机制之间的映射关系
"""
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from apps.user.config.permission_nodes import PERMISSION_NODES
import logging

logger = logging.getLogger('django')


class PermissionNodeMapper:
    """
    权限节点映射器
    管理权限配置节点与系统权限检查之间的映射关系
    """

    def __init__(self):
        self._permission_cache = None
        self._node_permission_map = None

    def _build_permission_cache(self):
        """构建权限缓存"""
        if self._permission_cache is None:
            self._permission_cache = {}
            ct = ContentType.objects.get(app_label='user', model='permission')
            for perm in Permission.objects.filter(content_type=ct):
                self._permission_cache[perm.codename] = perm
        return self._permission_cache

    def _build_node_permission_map(self):
        """构建节点到权限的映射"""
        if self._node_permission_map is None:
            self._node_permission_map = {}

            for module_key, module_config in PERMISSION_NODES.items():
                if 'permissions' in module_config:
                    for perm_config in module_config['permissions']:
                        codename = perm_config.get('codename')
                        if codename:
                            self._node_permission_map[codename] = f'user.{codename}'

                if 'children' in module_config:
                    for child_key, child_config in module_config['children'].items(
                    ):
                        self._node_permission_map[f'view_{child_key}'] = f'user.view_{child_key}'

                        if 'permissions' in child_config:
                            for perm_config in child_config['permissions']:
                                codename = perm_config.get('codename')
                                if codename:
                                    self._node_permission_map[codename] = f'user.{codename}'

                        if 'children' in child_config:
                            for sub_key, sub_config in child_config['children'].items(
                            ):
                                self._node_permission_map[f'view_{sub_key}'] = f'user.view_{sub_key}'

                                if 'permissions' in sub_config:
                                    for perm_config in sub_config['permissions']:
                                        codename = perm_config.get('codename')
                                        if codename:
                                            self._node_permission_map[codename] = f'user.{codename}'

        return self._node_permission_map

    def get_full_permission(self, node_codename):
        """
        获取权限节点的完整权限格式

        Args:
            node_codename: 权限节点codename，如 'view_customer'

        Returns:
            完整权限格式，如 'user.view_customer'
        """
        node_map = self._build_node_permission_map()
        return node_map.get(node_codename, f'user.{node_codename}')

    def get_node_codename(self, full_permission):
        """
        从完整权限格式获取节点codename

        Args:
            full_permission: 完整权限格式，如 'user.view_customer'

        Returns:
            节点codename，如 'view_customer'
        """
        node_map = self._build_node_permission_map()
        for node_codename, perm in node_map.items():
            if perm == full_permission:
                return node_codename
        return full_permission.split(
            '.')[-1] if '.' in full_permission else full_permission

    def check_permission(self, user, node_codename):
        """
        检查用户是否拥有指定权限节点的权限

        Args:
            user: 用户对象
            node_codename: 权限节点codename

        Returns:
            bool: 用户是否拥有权限
        """
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True

        full_permission = self.get_full_permission(node_codename)
        return user.has_perm(full_permission)

    def get_permission_ids_for_node(self, node_codename):
        """
        获取权限节点对应的权限ID列表

        Args:
            node_codename: 权限节点codename

        Returns:
            list: 权限ID列表
        """
        perm_cache = self._build_permission_cache()

        related_permissions = []
        base_name = node_codename
        if node_codename.startswith(('add_', 'change_', 'delete_', 'view_')):
            base_name = '_'.join(node_codename.split('_')[1:])

        for codename, perm in perm_cache.items():
            if (codename == node_codename or
                codename.startswith(f'{node_codename}_') or
                codename.endswith(f'_{base_name}') or
                    base_name in codename):
                related_permissions.append(perm.id)

        return related_permissions

    def get_view_permission_id(self, menu_code):
        """
        获取菜单查看权限ID

        Args:
            menu_code: 菜单代码，如 'department'

        Returns:
            int: 权限ID
        """
        perm_cache = self._build_permission_cache()
        view_codename = f'view_{menu_code}'

        if view_codename in perm_cache:
            return perm_cache[view_codename].id

        return None

    def get_all_permissions_for_menu(self, menu_code):
        """
        获取菜单关联的所有权限

        Args:
            menu_code: 菜单代码

        Returns:
            list: 权限对象列表
        """
        perm_cache = self._build_permission_cache()
        permissions = []

        view_codename = f'view_{menu_code}'
        for codename, perm in perm_cache.items():
            if (codename == view_codename or
                codename.startswith(f'{view_codename}_') or
                codename.startswith(f'add_{menu_code}') or
                codename.startswith(f'change_{menu_code}') or
                codename.startswith(f'delete_{menu_code}') or
                    codename.endswith(f'_{menu_code}')):
                permissions.append(perm)

        return permissions

    def normalize_permission_for_check(self, permission_code):
        """
        标准化权限代码用于后端检查

        Args:
            permission_code: 权限代码

        Returns:
            str: 标准化后的权限代码
        """
        if not permission_code:
            return None

        if '.' in permission_code:
            return permission_code

        return f'user.{permission_code}'


permission_node_mapper = PermissionNodeMapper()


def check_permission_by_node(user, node_codename):
    """
    检查用户是否拥有指定权限节点的权限（便捷函数）

    Args:
        user: 用户对象
        node_codename: 权限节点codename

    Returns:
        bool
    """
    return permission_node_mapper.check_permission(user, node_codename)


def get_permission_for_check(permission_code):
    """
    获取用于后端检查的权限代码（便捷函数）

    Args:
        permission_code: 权限代码

    Returns:
        str
    """
    return permission_node_mapper.normalize_permission_for_check(
        permission_code)
