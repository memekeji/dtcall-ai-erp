import logging

from django.core.cache import cache
from django.db import OperationalError, ProgrammingError, transaction

from apps.system.menu_config import system_menus
from apps.user.models import Menu, SystemModule

logger = logging.getLogger(__name__)


MODULE_CODE_MAP = {
    '工作台': 'dashboard',
    '系统管理': 'system',
    '人事管理': 'hr',
    '行政办公': 'oa',
    '个人办公': 'personal',
    '财务管理': 'finance',
    '客户管理': 'customer',
    '合同管理': 'contract',
    '项目管理': 'project',
    '生产管理': 'production',
    'AI智能中心': 'ai',
    '企业网盘': 'disk',
}

MODULE_ICON_MAP = {
    'dashboard': 'layui-icon-home',
    'system': 'layui-icon-set',
    'hr': 'layui-icon-user',
    'oa': 'layui-icon-template',
    'personal': 'layui-icon-username',
    'finance': 'layui-icon-rmb',
    'customer': 'layui-icon-group',
    'contract': 'layui-icon-file-b',
    'project': 'layui-icon-component',
    'production': 'layui-icon-engine',
    'ai': 'layui-icon-light',
    'disk': 'layui-icon-file',
}


def get_module_code(menu_data):
    title = menu_data.get('title', '')
    return MODULE_CODE_MAP.get(title, f"menu_{menu_data['id']}")


def get_top_menu_id(menu_data_by_id, menu_data):
    current = menu_data
    visited_ids = set()
    while current.get('pid_id'):
        parent_id = current.get('pid_id')
        if parent_id in visited_ids or parent_id not in menu_data_by_id:
            break
        visited_ids.add(parent_id)
        current = menu_data_by_id[parent_id]
    return current['id']


def build_module_defaults(menu_data):
    code = get_module_code(menu_data)
    title = menu_data['title']
    return {
        'name': title,
        'description': f'{title}相关功能模块',
        'icon': menu_data.get('icon') or MODULE_ICON_MAP.get(code, 'layui-icon-app'),
        'sort_order': menu_data.get('sort', 0),
        'is_active': menu_data.get('status', 1) == 1,
        'parent': None,
    }


def sync_menus_from_config(delete_extra=True, disabled_extra=True):
    with transaction.atomic():
        sorted_menus = sorted(system_menus.items(), key=lambda item: item[0])
        menu_data_by_id = {menu_data['id']: menu_data for _, menu_data in sorted_menus}
        top_menu_data = sorted(
            [menu_data for menu_data in menu_data_by_id.values() if not menu_data.get('pid_id')],
            key=lambda item: item.get('sort', 0),
        )
        modules_by_top_menu_id = {}
        module_created_count = 0
        module_updated_count = 0

        for menu_data in top_menu_data:
            module, created = SystemModule.objects.update_or_create(
                code=get_module_code(menu_data),
                defaults=build_module_defaults(menu_data),
            )
            modules_by_top_menu_id[menu_data['id']] = module
            if created:
                module_created_count += 1
            else:
                module_updated_count += 1

        config_menu_ids = set(menu_data_by_id)
        deleted_count = 0

        disabled_count = 0
        if delete_extra:
            extra_queryset = Menu.objects.exclude(id__in=config_menu_ids)
            if disabled_extra:
                deleted_count = extra_queryset.filter(status=0).delete()[0]
                disabled_count = extra_queryset.exclude(status=0).update(status=0)
            else:
                deleted_count = extra_queryset.delete()[0]

        existing_menus = {menu.id: menu for menu in Menu.objects.all()}
        created_count = 0
        updated_count = 0
        errors = []

        for _, menu_data in sorted_menus:
            menu_id = menu_data['id']
            try:
                top_menu_id = get_top_menu_id(menu_data_by_id, menu_data)
                module = modules_by_top_menu_id.get(top_menu_id)
                menu_defaults = {
                    'title': menu_data['title'],
                    'src': menu_data['src'],
                    'icon': menu_data.get('icon', ''),
                    'sort': menu_data['sort'],
                    'status': menu_data['status'],
                    'module': module,
                }
                menu, created = Menu.objects.update_or_create(
                    id=menu_id,
                    defaults=menu_defaults,
                )
                existing_menus[menu_id] = menu
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception:
                logger.exception('菜单同步失败: id=%s title=%s', menu_id, menu_data.get('title', ''))
                errors.append({
                    'id': menu_id,
                    'title': menu_data.get('title', 'Unknown'),
                    'message': '菜单保存失败',
                })

        parent_updated_count = 0
        for _, menu_data in sorted_menus:
            menu_id = menu_data['id']
            pid_id = menu_data.get('pid_id')
            try:
                menu = existing_menus.get(menu_id)
                parent = existing_menus.get(pid_id) if pid_id else None
                if menu and menu.pid_id != (parent.id if parent else None):
                    menu.pid = parent
                    menu.save(update_fields=['pid'])
                    parent_updated_count += 1
            except Exception:
                logger.exception('菜单父级关联同步失败: id=%s title=%s', menu_id, menu_data.get('title', ''))
                errors.append({
                    'id': menu_id,
                    'title': menu_data.get('title', 'Unknown'),
                    'message': '菜单父级关联失败',
                })

        cache.delete('user_menus')

    return {
        'deleted': deleted_count,
        'disabled_extra': disabled_count,
        'created': created_count,
        'updated': updated_count,
        'parent_updated': parent_updated_count,
        'module_created': module_created_count,
        'module_updated': module_updated_count,
        'total': len(sorted_menus),
        'errors': errors,
    }


def sync_menus_from_config_safely(delete_extra=True, disabled_extra=True):
    try:
        return sync_menus_from_config(delete_extra=delete_extra, disabled_extra=disabled_extra)
    except (OperationalError, ProgrammingError):
        logger.warning('系统菜单自动同步跳过，数据库表尚未就绪')
        return None
    except Exception:
        logger.exception('系统菜单自动同步失败')
        return None
