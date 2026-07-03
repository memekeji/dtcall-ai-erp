import os
import django
import logging

from apps.ai.models import AIModelConfig
from apps.user.models import SystemConfiguration as SystemConfig

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
django.setup()


# 配置日志
logger = logging.getLogger(__name__)


def init_ai_system_config():
    """初始化AI相关的系统配置"""
    configs_to_create = [
        {
            'key': 'ai_enabled',
            'value': 'true',
            'description': '是否启用AI功能'
        },
        {
            'key': 'ai_default_provider',
            'value': 'openai',
            'description': '默认AI服务提供商'
        },
        {
            'key': 'ai_openai_api_key',
            'value': '',
            'description': 'OpenAI API密钥'
        },
        {
            'key': 'ai_openai_base_url',
            'value': 'https://api.openai.com/v1',
            'description': 'OpenAI API基础URL'
        },
        {
            'key': 'ai_alibaba_api_key',
            'value': '',
            'description': '阿里通义千问API密钥'
        },
        {
            'key': 'ai_alibaba_base_url',
            'value': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'description': '阿里通义千问API基础URL'
        },
        {
            'key': 'ai_deepseek_api_key',
            'value': '',
            'description': 'DeepSeek API密钥'
        },
        {
            'key': 'ai_deepseek_base_url',
            'value': 'https://api.deepseek.com/v1',
            'description': 'DeepSeek API基础URL'
        },
        {
            'key': 'ai_doubao_api_key',
            'value': '',
            'description': '豆包API密钥'
        },
        {
            'key': 'ai_doubao_base_url',
            'value': 'https://ark.cn-beijing.volces.com/api/v3',
            'description': '豆包API基础URL'
        },
        {
            'key': 'ai_local_base_url',
            'value': 'http://localhost:8001',
            'description': '本地大模型API地址'
        },
        {
            'key': 'ai_request_timeout',
            'value': '30',
            'description': 'AI请求超时时间(秒)'
        },
        {
            'key': 'ai_max_retries',
            'value': '1',
            'description': 'AI请求最大重试次数'
        },
        {
            'key': 'ai_retry_delay',
            'value': '1',
            'description': 'AI请求重试间隔(秒)'
        },
        {
            'key': 'ai_chat_history_days',
            'value': '30',
            'description': 'AI聊天历史保留天数'
        }
    ]

    created_count = 0
    for config_data in configs_to_create:
        config, created = SystemConfig.objects.get_or_create(
            key=config_data['key'],
            defaults={
                'value': config_data['value'],
                'description': config_data['description'],
                'status': True
            }
        )
        if created:
            logger.info(
                f"创建配置项: {config_data['key']} - {config_data['description']}")
            created_count += 1
        else:
            updated = False
            if config.value != config_data['value']:
                config.value = config_data['value']
                updated = True
            if config.description != config_data['description']:
                config.description = config_data['description']
                updated = True
            if not config.status:
                config.status = True
                updated = True
            if updated:
                config.save()
                logger.info(f"更新配置项: {config_data['key']}")

    logger.info(f"AI系统配置初始化完成，共创建 {created_count} 个配置项")


def init_ai_model_config():
    """初始化默认AI模型配置（简化版）。"""
    default_configs = [
        {
            'name': '默认OpenAI配置',
            'api_base': 'https://api.openai.com/v1',
            'api_key': '',
            'model_names': ['gpt-4o-mini'],
            'is_default': True,
            'is_active': True,
        },
        {
            'name': '默认DeepSeek配置',
            'api_base': 'https://api.deepseek.com/v1',
            'api_key': '',
            'model_names': ['deepseek-chat'],
            'is_default': False,
            'is_active': True,
        },
        {
            'name': '默认千问配置',
            'api_base': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'api_key': '',
            'model_names': ['qwen-turbo'],
            'is_default': False,
            'is_active': True,
        },
    ]

    created_count = 0
    for config_data in default_configs:
        _, created = AIModelConfig.objects.get_or_create(
            name=config_data['name'],
            defaults=config_data
        )
        if created:
            created_count += 1
            logger.info(f"创建AI模型配置: {config_data['name']}")

    logger.info(f"AI模型配置初始化完成，共创建 {created_count} 个配置项")


def main():
    """主函数"""
    logger.info("开始初始化AI配置...")
    init_ai_system_config()
    init_ai_model_config()
    logger.info("AI配置初始化完成！")


if __name__ == '__main__':
    main()

