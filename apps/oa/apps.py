from django.apps import AppConfig

class OaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.oa'
    verbose_name = 'OA办公'
    
    def ready(self):
        # 导入models_new.py中的模型，确保Django能够正确识别
        # 注意：这里只导入模块，不直接注册模型，避免循环导入问题
        pass
