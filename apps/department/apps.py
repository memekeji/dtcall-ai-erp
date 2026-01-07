from django.apps import AppConfig

class DepartmentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.department'
    verbose_name = '部门管理'
    
    def ready(self):
        # 信号处理器已移除，自定义权限系统已替换为Django内置权限系统
        pass
