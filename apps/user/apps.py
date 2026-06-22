from django.apps import AppConfig
from django.db.models.signals import post_migrate


class UserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.user'
    verbose_name = '用户管理'

    def ready(self):
        post_migrate.connect(
            init_permission_basic_data_after_migrate,
            sender=self,
            dispatch_uid='apps.user.init_permission_basic_data_after_migrate',
        )


def init_permission_basic_data_after_migrate(sender, **kwargs):
    if sender.name != 'apps.user':
        return

    try:
        from django.core.management import call_command
        call_command('init_permissions', verbosity=0)
    except Exception as exc:
        print(f'初始化权限基础数据失败: {exc}')
