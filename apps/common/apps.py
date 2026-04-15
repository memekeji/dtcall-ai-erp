from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'
    verbose_name = '通用模块'

    def ready(self):
        # 导入信号处理器以确保它们被注册
        pass
