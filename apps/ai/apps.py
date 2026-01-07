from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class AIConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ai'
    verbose_name = 'AI智能服务'
    
    def ready(self):
        """应用启动时执行"""
        # 只在主进程中执行，避免在迁移等操作时执行
        import sys
        # 检查是否在迁移过程中，避免访问未创建的数据库表
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return
        if 'runserver' in sys.argv or 'gunicorn' in sys.argv:
            self._validate_ai_configuration()
    
    def _validate_ai_configuration(self):
        """验证AI配置"""
        try:
            # 导入配置管理器
            from apps.ai.utils.ai_config_manager import validate_ai_configuration
            
            # 验证AI配置
            validation_results = validate_ai_configuration()
            
            # 统计有效配置
            valid_count = sum(1 for result in validation_results.values() if result['valid'])
            
            if valid_count > 0:
                logger.info(f"AI配置验证完成，{valid_count}个配置有效")
            else:
                logger.warning("没有有效的AI配置，AI功能将不可用")
                
        except Exception as e:
            logger.warning(f"AI配置验证失败: {e}")