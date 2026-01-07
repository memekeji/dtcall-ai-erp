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
                'provider': 'qwen',
                'model_type': 'chat',
                'api_key': '',  # 需要用户配置
                'base_url': 'https://dashscope.aliyuncs.com/api/v1',
                'default_params': {
                    'temperature': 0.7,
                    'max_tokens': 2000
                },
                'is_active': True
            },
            {
                'name': '豆包-标准版',
                'provider': 'doubao',
                'model_type': 'chat',
                'api_key': '',  # 需要用户配置
                'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
                'default_params': {
                    'temperature': 0.7,
                    'max_tokens': 2000
                },
                'is_active': True
            },
            {
                'name': '文心一言-Turbo',
                'provider': 'wenxin',
                'model_type': 'chat',
                'api_key': '',  # 需要用户配置
                'base_url': 'https://aip.baidubce.com/rpc/2.0/ai_custom/v1',
                'default_params': {
                    'temperature': 0.7,
                    'max_tokens': 2000
                },
                'is_active': True
            },
            {
                'name': 'DeepSeek-Chat',
                'provider': 'deepseek',
                'model_type': 'chat',
                'api_key': '',  # 需要用户配置
                'base_url': 'https://api.deepseek.com/v1',
                'default_params': {
                    'temperature': 0.7,
                    'max_tokens': 2000
                },
                'is_active': True
            },
            {
                'name': 'OpenAI-GPT-3.5-Turbo',
                'provider': 'openai',
                'model_type': 'chat',
                'api_key': '',  # 需要用户配置
                'base_url': 'https://api.openai.com/v1',
                'default_params': {
                    'temperature': 0.7,
                    'max_tokens': 2000
                },
                'is_active': True
            }
        ]
        
        created_count = 0
        for config_data in default_configs:
            config, created = AIModelConfig.objects.get_or_create(
                name=config_data['name'],
                defaults=config_data
            )
            if created:
                created_count += 1
                self.stdout.write(f"✓ 创建配置: {config.name}")
            else:
                self.stdout.write(f"- 配置已存在: {config.name}")
        
        self.stdout.write(f'\n创建完成: {created_count} 个新配置')
        self.stdout.write('\n注意: 默认配置的API密钥为空，请通过管理界面配置实际的API密钥')