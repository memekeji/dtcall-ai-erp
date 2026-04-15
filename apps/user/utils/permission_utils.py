"""
权限管理工具模块
提供统一的权限处理、分组和显示逻辑
"""
from django.contrib.auth.models import Permission
from typing import Dict, List, Any


class PermissionManager:
    """权限管理器，提供权限分组和处理功能"""

    MENU_ORDER = [
        '工作台', '系统管理', '人事管理', '行政办公', '个人办公', '审批流程', '消息管理', '任务管理', '财务管理',
        '客户管理', '合同管理', '项目管理', '生产管理', 'AI智能中心', '企业网盘', '其他权限'
    ]

    @classmethod
    def get_permission_data(
            cls, permissions: List[Permission]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """获取分组后的权限数据"""
        permission_data = {menu: {} for menu in cls.MENU_ORDER}

        unique_permissions = {perm.id: perm for perm in permissions}
        used_display_names = {}

        for perm_id, perm in unique_permissions.items():
            app_label = perm.content_type.app_label
            model = perm.content_type.model

            model_display_name = model.capitalize()
            menu_group = cls._get_menu_group(app_label, model)
            action = cls._get_action_type(perm.name)
            display_name = cls._get_unique_display_name(
                action, model_display_name, perm_id, used_display_names)

            perm_copy = {
                'id': perm_id,
                'name': display_name,
                'codename': perm.codename,
                'content_type_id': perm.content_type_id,
                'app_label': app_label,
                'model': model
            }

            if model_display_name not in permission_data[menu_group]:
                permission_data[menu_group][model_display_name] = []

            permission_data[menu_group][model_display_name].append(perm_copy)

        return cls._sort_permission_data(permission_data)

    @classmethod
    def _get_menu_group(cls, app_label: str, model: str) -> str:
        """获取权限所属的菜单分组"""
        if app_label in ['contenttypes', 'auth', 'sessions', 'sites']:
            return '系统管理'

        group_mapping = {
            'system': '系统管理',
            'user': '系统管理',
            'department': '人事管理',
            'position': '人事管理',
            'employee': '人事管理',
            'personal': '个人办公',
            'finance': '财务管理',
            'customer': '客户管理',
            'contract': '合同管理',
            'project': '项目管理',
            'production': '生产管理',
            'ai': 'AI智能中心',
            'disk': '企业网盘',
            'approval': '审批流程',
            'oa': '行政办公',
            'message': '消息管理',
            'task': '任务管理',
        }

        if app_label in group_mapping:
            return group_mapping[app_label]

        return '其他权限'

    @classmethod
    def _get_action_type(cls, perm_name: str) -> str:
        """获取权限的操作类型"""
        if 'add' in perm_name.lower() or 'create' in perm_name.lower():
            return '添加'
        elif 'change' in perm_name.lower() or 'update' in perm_name.lower():
            return '修改'
        elif 'delete' in perm_name.lower() or 'remove' in perm_name.lower():
            return '删除'
        elif 'view' in perm_name.lower() or 'can view' in perm_name.lower():
            return '查看'
        else:
            return '操作'

    @classmethod
    def _get_unique_display_name(cls, action: str, model_display_name: str,
                                 perm_id: int, used_display_names: Dict[str, int]) -> str:
        """获取唯一的显示名称"""
        base_display_name = f"{action} {model_display_name}"
        display_name = base_display_name

        counter = 1
        while display_name in used_display_names:
            display_name = f"{base_display_name} ({perm_id})"
            counter += 1

        used_display_names[display_name] = perm_id
        return display_name

    @classmethod
    def _sort_permission_data(
            cls, permission_data: Dict[str, Dict[str, List[Dict[str, Any]]]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """按预设的菜单顺序排序权限数据"""
        sorted_permission_data = {}

        for menu in cls.MENU_ORDER:
            if menu in permission_data and permission_data[menu]:
                sorted_permission_data[menu] = permission_data[menu]

        return sorted_permission_data
