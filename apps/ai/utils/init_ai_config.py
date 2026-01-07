import os
import django
import logging

# 设置Django环境\os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
django.setup()

from apps.user.models import SystemConfiguration as SystemConfig
from apps.ai.models import AIModelConfig

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
            'key': 'ai_qwen_api_key',
            'value': '',
            'description': '阿里千问API密钥'
        },
        {
            'key': 'ai_qwen_base_url',
            'value': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'description': '阿里千问API基础URL'
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
            'value': 'https://api.doubao.com/v1',
            'description': '豆包API基础URL'
        },
        {
            'key': 'ai_local_base_url',
            'value': 'http://localhost:8000/v1',
            'description': '本地大模型API地址'
        },
        {
            'key': 'ai_request_timeout',
            'value': '60',
            'description': 'AI请求超时时间(秒)'
        },
        {
            'key': 'ai_max_retries',
            'value': '3',
            'description': 'AI请求最大重试次数'
        },
        {
            'key': 'ai_retry_delay',
            'value': '2',
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
            logger.info(f"创建配置项: {config_data['key']} - {config_data['description']}")
            created_count += 1
        else:
            # 更新现有配置
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
    """初始化AI模型配置"""
    models_to_create = [
        {
            'name': 'OpenAI GPT-3.5 Turbo',
            'model_type': 'chat',
            'default_params': {
                'model': 'gpt-3.5-turbo',
                'temperature': 0.7,
                'max_tokens': 4096
            },
            'is_active': True
        },
        {
            'name': 'OpenAI Embedding',
            'model_type': 'embedding',
            'default_params': {
                'model': 'text-embedding-ada-002'
            },
            'is_active': True
        },
        {
            'name': 'Qwen Turbo',
            'model_type': 'chat',
            'default_params': {
                'model': 'qwen-turbo',
                'temperature': 0.7,
                'max_tokens': 8192
            },
            'is_active': False
        },
        {
            'name': 'DeepSeek Chat',
            'model_type': 'chat',
            'default_params': {
                'model': 'deepseek-chat',
                'temperature': 0.7,
                'max_tokens': 4096
            },
            'is_active': False
        },
        {
            'name': 'Doubao Pro',
            'model_type': 'chat',
            'default_params': {
                'model': 'doubao-pro',
                'temperature': 0.7,
                'max_tokens': 4096
            },
            'is_active': False
        },
        {
            'name': '本地大模型',
            'model_type': 'chat',
            'default_params': {
                'model': 'local-model',
                'temperature': 0.7,
                'max_tokens': 4096
            },
            'is_active': False
        }
    ]

    created_count = 0
    for model_data in models_to_create:
        # 检查是否已存在同名同类型的模型配置
        existing_model = AIModelConfig.objects.filter(
            name=model_data['name'],
            model_type=model_data['model_type']
        ).first()

        if existing_model:
            # 更新现有模型配置
            updated = False
            if existing_model.default_params != model_data['default_params']:
                existing_model.default_params = model_data['default_params']
                updated = True
            if existing_model.is_active != model_data['is_active']:
                existing_model.is_active = model_data['is_active']
                updated = True
            if updated:
                existing_model.save()
                logger.info(f"更新模型配置: {model_data['name']}")
        else:
            # 创建新的模型配置
            AIModelConfig.objects.create(**model_data)
            logger.info(f"创建模型配置: {model_data['name']}")
            created_count += 1

    logger.info(f"AI模型配置初始化完成，共创建 {created_count} 个模型配置")


def main():
    """主函数"""
    logger.info("开始初始化AI配置...")
    init_ai_system_config()
    init_ai_model_config()
    logger.info("AI配置初始化完成！")


if __name__ == '__main__':
    main()