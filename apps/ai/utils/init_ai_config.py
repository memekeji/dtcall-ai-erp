from apps.ai.models import AIModelConfig
from apps.user.models import SystemConfiguration as SystemConfig
import os
import django
import logging

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
    """初始化AI模型配置"""
    models_to_create = [
        {
            'name': 'OpenAI GPT-4o Mini',
            'provider': 'openai',
            'model_type': 'chat',
            'api_key': '',
            'api_base': 'https://api.openai.com/v1',
            'model_name': 'gpt-4o-mini',
            'is_active': True,
            'is_default': False,
            'max_tokens': 2000,
            'temperature': 0.7,
            'top_p': 1.0,
        },
        {
            'name': 'OpenAI Embedding',
            'provider': 'openai',
            'model_type': 'embedding',
            'api_key': '',
            'api_base': 'https://api.openai.com/v1',
            'model_name': 'text-embedding-3-small',
            'is_active': True,
            'is_default': False,
            'max_tokens': 2048,
            'temperature': 0.7,
            'top_p': 1.0,
        },
        {
            'name': '通义千问 Turbo',
            'provider': 'alibaba',
            'model_type': 'chat',
            'api_key': '',
            'api_base': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'model_name': 'qwen-turbo',
            'is_active': False,
            'is_default': False,
            'max_tokens': 2000,
            'temperature': 0.7,
            'top_p': 1.0,
        },
        {
            'name': 'DeepSeek Chat',
            'provider': 'deepseek',
            'model_type': 'chat',
            'api_key': '',
            'api_base': 'https://api.deepseek.com/v1',
            'model_name': 'deepseek-chat',
            'is_active': False,
            'is_default': False,
            'max_tokens': 2000,
            'temperature': 0.7,
            'top_p': 1.0,
        },
        {
            'name': '豆包 Seed',
            'provider': 'doubao',
            'model_type': 'chat',
            'api_key': '',
            'api_base': 'https://ark.cn-beijing.volces.com/api/v3',
            'model_name': 'doubao-seed-1-6-250615',
            'is_active': False,
            'is_default': False,
            'max_tokens': 2000,
            'temperature': 0.7,
            'top_p': 1.0,
        },
        {
            'name': '本地大模型',
            'provider': 'local',
            'model_type': 'chat',
            'api_key': '',
            'api_base': 'http://localhost:8001',
            'model_name': 'local-model',
            'is_active': False,
            'is_default': False,
            'max_tokens': 2000,
            'temperature': 0.7,
            'top_p': 1.0,
        }
    ]

    created_count = 0
    for model_data in models_to_create:
        existing_model = AIModelConfig.objects.filter(
            name=model_data['name'],
            provider=model_data['provider'],
            model_name=model_data['model_name'],
            model_type=model_data['model_type']
        ).first()

        if existing_model:
            updated = False
            for field, value in model_data.items():
                if getattr(existing_model, field) != value:
                    setattr(existing_model, field, value)
                    updated = True
            if updated:
                existing_model.save()
                logger.info(f"更新模型配置: {model_data['name']}")
        else:
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
