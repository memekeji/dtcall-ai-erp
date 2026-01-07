from django.apps import AppConfig


class DiskConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.disk'
    verbose_name = '知识网盘'