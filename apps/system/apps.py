import logging

from django.apps import AppConfig
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)


def sync_system_menus_after_migrate(sender, **kwargs):
    if sender.name != 'apps.system':
        return
    from apps.system.menu_sync import sync_menus_from_config_safely
    result = sync_menus_from_config_safely(delete_extra=True)
    if result and result.get('errors'):
        logger.error('系统菜单自动同步存在失败项: %s', result['errors'])


class SystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.system'
    verbose_name = '系统管理'

    def ready(self):
        post_migrate.connect(
            sync_system_menus_after_migrate,
            sender=self,
            dispatch_uid='apps.system.sync_system_menus_after_migrate',
        )
