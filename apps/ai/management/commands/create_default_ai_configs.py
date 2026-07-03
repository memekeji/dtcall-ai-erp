"""
创建默认AI配置的管理命令
"""
from django.core.management.base import BaseCommand
from apps.ai.models import AIModelConfig


class Command(BaseCommand):
    help = '创建默认的AI模型配置'

    def handle(self, *args, **options):
        """执行命令"""
        self.stdout.write('开始创建默认AI配置...')

        # 检查是否已存在配置
        existing_configs = AIModelConfig.objects.all()
        if existing_configs.exists():
            self.stdout.write(f'发现 {existing_configs.count()} 个现有配置，跳过创建默认配置')
            return

        # 创建默认配置
        default_configs = [
            {
                'name': '千问-Turbo',
                'model_names': ['qwen-turbo'],
                'api_key': '',
                'api_base': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                'is_default': False,
                'is_active': True
            },
            {
                'name': '豆包-标准版',
                'model_names': ['doubao-seed-1-6-250615'],
                'api_key': '',
                'api_base': 'https://ark.cn-beijing.volces.com/api/v3',
                'is_default': False,
                'is_active': True
            },
            {
                'name': '文心一言-Turbo',
                'model_names': ['ernie-4.0-turbo-8k'],
                'api_key': '',
                'api_base': 'https://aip.baidubce.com/rpc/2.0/ai_custom/v1',
                'is_default': False,
                'is_active': True
            },
            {
                'name': 'DeepSeek-Chat',
                'model_names': ['deepseek-chat'],
                'api_key': '',
                'api_base': 'https://api.deepseek.com/v1',
                'is_default': False,
                'is_active': True
            },
            {
                'name': 'OpenAI-GPT-4o-Mini',
                'model_names': ['gpt-4o-mini'],
                'api_key': '',
                'api_base': 'https://api.openai.com/v1',
                'is_default': True,
                'is_active': True
            }
        ]

        created_count = 0
        for config_data in default_configs:
            config, created = AIModelConfig.objects.get_or_create(name=config_data['name'], defaults=config_data)
            if created:
                created_count += 1
                self.stdout.write(f"✓ 创建配置: {config.name}")
            else:
                self.stdout.write(f"- 配置已存在: {config.name}")

        self.stdout.write(f'\n创建完成: {created_count} 个新配置')
        self.stdout.write('\n注意: 默认配置的API密钥为空，请通过管理界面配置实际的API密钥')

