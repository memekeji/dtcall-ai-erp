"""
AI配置验证管理命令
在项目启动时验证AI配置的有效性
"""

from django.core.management.base import BaseCommand
from apps.ai.utils.ai_config_manager import validate_ai_configuration


class Command(BaseCommand):
    help = '验证AI配置的有效性'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='尝试自动修复配置问题',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细验证信息',
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        fix = options['fix']

        self.stdout.write('开始验证AI配置...')

        # 验证AI配置
        validation_results = validate_ai_configuration()

        # 统计结果
        valid_count = 0
        invalid_count = 0

        for config_id, result in validation_results.items():
            if result['valid']:
                valid_count += 1
                if verbose:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ {config_id}: 配置有效")
                    )
            else:
                invalid_count += 1
                self.stdout.write(
                    self.style.ERROR(f"✗ {config_id}: 配置无效 - {', '.join(result['errors'])}"))

        # 输出总结
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(f"验证完成: {valid_count} 个有效配置, {invalid_count} 个无效配置")

        if valid_count == 0:
            self.stdout.write(
                self.style.ERROR("警告: 没有有效的AI配置，AI功能将不可用")
            )

            if fix:
                self.stdout.write("尝试创建默认配置...")
                self._create_default_configs()

        if invalid_count > 0 and fix:
            self.stdout.write("尝试修复无效配置...")
            self._fix_invalid_configs(validation_results)

    def _create_default_configs(self):
        """创建默认配置"""
        try:
            from apps.ai.models import AIModelConfig

            default_configs = [
                {
                    'name': '默认OpenAI配置',
                    'provider': 'openai',
                    'model_type': 'chat',
                    'model_name': 'gpt-4o-mini',
                    'api_key': '',
                    'api_base': 'https://api.openai.com/v1',
                    'temperature': 0.7,
                    'max_tokens': 2000,
                    'top_p': 1.0,
                    'is_active': True
                },
                {
                    'name': '默认千问配置',
                    'provider': 'alibaba',
                    'model_type': 'chat',
                    'model_name': 'qwen-turbo',
                    'api_key': '',
                    'api_base': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                    'temperature': 0.7,
                    'max_tokens': 2000,
                    'top_p': 1.0,
                    'is_active': True
                },
                {
                    'name': '默认文心一言配置',
                    'provider': 'baidu',
                    'model_type': 'chat',
                    'model_name': 'eb-instant',
                    'api_key': '',
                    'api_base': 'https://aip.baidubce.com/rpc/2.0/ai_custom/v1',
                    'temperature': 0.7,
                    'max_tokens': 2000,
                    'top_p': 1.0,
                    'is_active': True
                },
                {
                    'name': '默认DeepSeek配置',
                    'provider': 'deepseek',
                    'model_type': 'chat',
                    'model_name': 'deepseek-chat',
                    'api_key': '',
                    'api_base': 'https://api.deepseek.com/v1',
                    'temperature': 0.7,
                    'max_tokens': 2000,
                    'top_p': 1.0,
                    'is_active': True
                },
                {
                    'name': '默认豆包配置',
                    'provider': 'doubao',
                    'model_type': 'chat',
                    'model_name': 'doubao-seed-1-6-250615',
                    'api_key': '',
                    'api_base': 'https://ark.cn-beijing.volces.com/api/v3',
                    'temperature': 0.7,
                    'max_tokens': 2000,
                    'top_p': 1.0,
                    'is_active': True
                }
            ]

            for config_data in default_configs:
                config, created = AIModelConfig.objects.get_or_create(
                    name=config_data['name'],
                    defaults=config_data)
                if created:
                    self.stdout.write(f"✓ 创建{config.name}")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"创建默认配置失败: {e}")
            )

    def _fix_invalid_configs(self, validation_results):
        """尝试修复无效配置"""
        try:
            from apps.ai.models import AIModelConfig

            for config_id, result in validation_results.items():
                if not result['valid']:
                    # 只处理数据库中的配置
                    if config_id.startswith('settings_'):
                        self.stdout.write(f"跳过settings配置: {config_id}")
                        continue

                    try:
                        config = AIModelConfig.objects.get(id=config_id)

                        # 根据错误类型尝试修复
                        errors = result['errors']

                        if 'API密钥未配置' in errors:
                            self.stdout.write(
                                f"警告: {config_id} 缺少API密钥，需要手动配置")

                        if '基础URL未配置' in errors:
                            provider_aliases = {
                                'qwen': 'alibaba',
                                'wenxin': 'baidu'
                            }
                            provider = provider_aliases.get(config.provider, config.provider)
                            default_urls = {
                                'openai': 'https://api.openai.com/v1',
                                'alibaba': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                                'baidu': 'https://aip.baidubce.com/rpc/2.0/ai_custom/v1',
                                'deepseek': 'https://api.deepseek.com/v1',
                                'doubao': 'https://ark.cn-beijing.volces.com/api/v3',
                                'anthropic': 'https://api.anthropic.com/v1',
                                'google': 'https://generativelanguage.googleapis.com/v1beta',
                                'tencent': 'https://api.hunyuan.cloud.tencent.com/v1'
                            }

                            if provider in default_urls:
                                config.provider = provider
                                config.api_base = default_urls[provider]
                                config.save(update_fields=['provider', 'api_base', 'updated_at'])
                                self.stdout.write(f"✓ 为 {config_id} 设置默认基础URL")

                        # 标记为不活跃
                        if len(errors) > 1:
                            config.is_active = False
                            config.save()
                            self.stdout.write(f"✓ 禁用无效配置: {config_id}")

                    except AIModelConfig.DoesNotExist:
                        self.stdout.write(f"配置不存在: {config_id}")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"修复配置失败: {e}")
            )
