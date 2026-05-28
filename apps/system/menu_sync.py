import logging

from django.db import OperationalError, ProgrammingError, transaction

from apps.system.menu_config import system_menus
from apps.user.models import Menu, SystemModule

logger = logging.getLogger(__name__)


DEFAULT_MODULE_DATA = {
    'name': '系统管理',
    'description': '系统基础菜单默认所属模块',
    'icon': 'layui-icon-set',
    'sort_order': 1,
    'is_active': True,
    'parent': None,
}


def sync_menus_from_config(delete_extra=True, disabled_extra=True):
    with transaction.atomic():
        default_module, _ = SystemModule.objects.update_or_create(
            code='system',
            defaults=DEFAULT_MODULE_DATA,
        )
        sorted_menus = sorted(system_menus.items(), key=lambda item: item[0])
        config_menu_ids = {menu_data['id'] for _, menu_data in sorted_menus}
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
                menu_defaults = {
                    'title': menu_data['title'],
                    'src': menu_data['src'],
                    'icon': menu_data.get('icon', ''),
                    'sort': menu_data['sort'],
                    'status': menu_data['status'],
                    'module': default_module,
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

    return {
        'deleted': deleted_count,
        'disabled_extra': disabled_count,
        'created': created_count,
        'updated': updated_count,
        'parent_updated': parent_updated_count,
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
