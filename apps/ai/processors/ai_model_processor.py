"""
AI模型节点处理器
"""

import logging

from .base_processor import BaseNodeProcessor, NodeProcessorRegistry

logger = logging.getLogger(__name__)


@NodeProcessorRegistry.register('ai_model')
class AIModelProcessor(BaseNodeProcessor):
    """AI模型节点处理器"""

    @staticmethod
    def _build_model_options(available_configs):
        model_options = []
        for config_id, config in available_configs.items():
            if not config.get('is_active'):
                continue
            label = config.get('name', str(config_id))
            primary_model = config.get('model_name') or (
                (config.get('model_names') or [''])[0]
            )
            provider = config.get('provider_display') or config.get('provider')
            summary = primary_model or provider or '未命名模型'
            model_options.append({
                'value': str(config_id),
                'label': f"{label} ({summary})"
            })

        if model_options:
            return model_options

        return [
            {'value': '', 'label': '暂无可用模型配置'}
        ]

    @staticmethod
    def _resolve_ai_config(config_manager, model_config_value):
        if model_config_value:
            ai_config = config_manager.get_config(model_config_value)
            if ai_config:
                return ai_config

        if ':' in (model_config_value or ''):
            provider, _ = model_config_value.split(':', 1)
            ai_config = config_manager.get_config_by_provider(provider)
            if ai_config:
                return ai_config

        return config_manager.get_active_config()

    @classmethod
    def get_display_name(cls):
        return "AI模型节点"

    @classmethod
    def get_icon(cls):
        return "layui-icon-engine"

    @classmethod
    def get_description(cls):
        return "调用AI模型进行文本生成、分类等任务"

    def _get_config_schema(self) -> dict:
        """获取AI模型节点的配置模式"""
        from apps.ai.utils.ai_config_manager import get_ai_config_manager

        # 从配置管理器获取可用的模型列表
        config_manager = get_ai_config_manager()
        available_configs = config_manager.get_all_configs()

        # 生成模型选项列表
        model_options = self._build_model_options(available_configs)

        return {
            'model_config': {
                'type': 'string',
                'required': True,
                'label': 'AI模型配置',
                'placeholder': '选择AI模型配置',
                'description': '要使用的AI模型配置',
                'options': model_options
            },
            'prompt_template': {
                'type': 'string',
                'required': True,
                'label': '提示词模板',
                'placeholder': '请输入提示词模板，可使用 {{变量名}} 引用上下文变量',
                'description': 'AI模型的提示词模板，支持变量替换'
            },
            'temperature': {
                'type': 'number',
                'required': False,
                'label': '温度参数',
                'default': 0.7,
                'min': 0.0,
                'max': 2.0,
                'description': '控制生成结果的随机性，值越大越随机'
            },
            'max_tokens': {
                'type': 'number',
                'required': False,
                'label': '最大输出长度',
                'default': 1000,
                'min': 1,
                'max': 4000,
                'description': '限制AI生成的最大token数量'
            },
            'system_prompt': {
                'type': 'string',
                'required': False,
                'label': '系统提示',
                'placeholder': '系统角色设定',
                'description': '系统级别的角色设定提示'
            }
        }

    def execute(self, config: dict, context: dict) -> dict:
        """执行AI模型节点逻辑"""
        from apps.ai.utils.ai_config_manager import get_ai_config_manager

        # 获取配置参数
        model_config_str = config.get('model_config', '')
        prompt_template = config.get('prompt_template', '')
        temperature = config.get('temperature', 0.7)
        max_tokens = config.get('max_tokens', 1000)
        system_prompt = config.get('system_prompt', '')

        # 解析模型配置
        config_manager = get_ai_config_manager()
        ai_config = self._resolve_ai_config(config_manager, model_config_str)

        if not ai_config:
            return {
                'ai_result': None,
                'model_used': 'unknown',
                'prompt_length': 0,
                'response_length': 0,
                'error': '没有可用的AI配置'
            }

        # 替换提示词中的变量
        prompt = prompt_template
        for key, value in context.items():
            placeholder = f'{{{{{key}}}}}'
            prompt = prompt.replace(placeholder, str(value))

        # 调用AI服务
        try:
            from apps.ai.utils.ai_client import AIClient

            ai_client = AIClient.from_config(ai_config)

            result = ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )

            return {
                'ai_result': result,
                'model_used': ai_config.get('name', 'unknown'),
                'provider': ai_config.get('provider'),
                'config_id': ai_config.get('id'),
                'prompt_length': len(prompt),
                'response_length': len(result) if result else 0
            }

        except Exception as e:
            logger.error(f"AI模型调用失败: {str(e)}")
            return {
                'ai_result': None,
                'model_used': ai_config.get('name', 'unknown'),
                'provider': ai_config.get('provider'),
                'config_id': ai_config.get('id'),
                'prompt_length': len(prompt),
                'response_length': 0,
                'error': 'AI模型调用失败，请检查模型配置后重试'
            }


@NodeProcessorRegistry.register('ai_generation')
class AIGenerationProcessor(AIModelProcessor):
    """AI生成节点处理器"""

    @classmethod
    def get_display_name(cls):
        return "AI生成节点"

    @classmethod
    def get_icon(cls):
        return "layui-icon-fonts-code"

    @classmethod
    def get_description(cls):
        return "使用AI模型生成文本内容"

    def _get_config_schema(self) -> dict:
        """获取AI生成节点的配置模式"""
        from apps.ai.utils.ai_config_manager import get_ai_config_manager

        # 从配置管理器获取可用的模型列表
        config_manager = get_ai_config_manager()
        available_configs = config_manager.get_all_configs()

        # 生成模型选项列表
        model_options = self._build_model_options(available_configs)

        return {
            'model_config': {
                'type': 'string',
                'required': True,
                'label': 'AI模型配置',
                'placeholder': '选择AI模型配置',
                'description': '要使用的AI模型配置',
                'options': model_options
            },
            'prompt_template': {
                'type': 'string',
                'required': True,
                'label': '提示词模板',
                'placeholder': '请输入提示词模板，可使用 {{变量名}} 引用上下文变量',
                'description': 'AI模型的提示词模板，支持变量替换'
            },
            'temperature': {
                'type': 'number',
                'required': False,
                'label': '温度参数',
                'default': 0.7,
                'min': 0.0,
                'max': 2.0,
                'description': '控制生成结果的随机性，值越大越随机'
            },
            'max_tokens': {
                'type': 'number',
                'required': False,
                'label': '最大输出长度',
                'default': 1000,
                'min': 1,
                'max': 4000,
                'description': '限制AI生成的最大token数量'
            },
            'system_prompt': {
                'type': 'string',
                'required': False,
                'label': '系统提示',
                'placeholder': '系统角色设定',
                'description': '系统级别的角色设定提示'
            },
            'output_format': {
                'type': 'string',
                'required': False,
                'label': '输出格式',
                'default': 'text',
                'options': [
                    {'value': 'text', 'label': '纯文本'},
                    {'value': 'json', 'label': 'JSON格式'},
                    {'value': 'markdown', 'label': 'Markdown'},
                    {'value': 'html', 'label': 'HTML'}
                ],
                'description': '指定生成内容的格式'
            },
            'creativity_level': {
                'type': 'string',
                'required': False,
                'label': '创意程度',
                'default': 'balanced',
                'options': [
                    {'value': 'conservative', 'label': '保守'},
                    {'value': 'balanced', 'label': '平衡'},
                    {'value': 'creative', 'label': '创意'}
                ],
                'description': '控制生成内容的创意程度'
            }
        }


@NodeProcessorRegistry.register('ai_classification')
class AIClassificationProcessor(AIModelProcessor):
    """AI分类节点处理器"""

    @classmethod
    def get_display_name(cls):
        return "AI分类节点"

    @classmethod
    def get_icon(cls):
        return "layui-icon-read"

    @classmethod
    def get_description(cls):
        return "使用AI模型对文本进行分类"

    def _get_config_schema(self) -> dict:
        """获取AI分类节点的配置模式"""
        from apps.ai.utils.ai_config_manager import get_ai_config_manager

        # 从配置管理器获取可用的模型列表
        config_manager = get_ai_config_manager()
        available_configs = config_manager.get_all_configs()

        # 生成模型选项列表
        model_options = self._build_model_options(available_configs)

        return {
            'model_config': {
                'type': 'string',
                'required': True,
                'label': 'AI模型配置',
                'placeholder': '选择AI模型配置',
                'description': '要使用的AI模型配置',
                'options': model_options
            },
            'prompt_template': {
                'type': 'string',
                'required': True,
                'label': '提示词模板',
                'placeholder': '请输入分类提示词模板，可使用 {{变量名}} 引用上下文变量',
                'description': 'AI模型的分类提示词模板，支持变量替换'
            },
            'temperature': {
                'type': 'number',
                'required': False,
                'label': '温度参数',
                'default': 0.1,
                'min': 0.0,
                'max': 1.0,
                'description': '控制生成结果的随机性，分类任务建议使用较低值'
            },
            'max_tokens': {
                'type': 'number',
                'required': False,
                'label': '最大输出长度',
                'default': 100,
                'min': 1,
                'max': 500,
                'description': '限制AI生成的最大token数量，分类任务通常不需要太长'
            },
            'system_prompt': {
                'type': 'string',
                'required': False,
                'label': '系统提示',
                'placeholder': '系统角色设定',
                'description': '系统级别的角色设定提示'
            },
            'classification_labels': {
                'type': 'string',
                'required': True,
                'label': '分类标签',
                'placeholder': '请输入分类标签，用逗号分隔',
                'description': '指定分类的可能标签，如：正面,负面,中性'
            },
            'output_format': {
                'type': 'string',
                'required': False,
                'label': '输出格式',
                'default': 'text',
                'options': [
                    {'value': 'text', 'label': '纯文本'},
                    {'value': 'json', 'label': 'JSON格式'}
                ],
                'description': '指定分类结果的格式'
            }
        }


@NodeProcessorRegistry.register('ai_extraction')
class AIExtractionProcessor(AIModelProcessor):
    """AI信息提取节点处理器"""

    @classmethod
    def get_display_name(cls):
        return "AI信息提取节点"

    @classmethod
    def get_icon(cls):
        return "layui-icon-search"

    @classmethod
    def get_description(cls):
        return "使用AI模型从文本中提取结构化信息"

    def _get_config_schema(self) -> dict:
        """获取AI信息提取节点的配置模式"""
        from apps.ai.utils.ai_config_manager import get_ai_config_manager

        # 从配置管理器获取可用的模型列表
        config_manager = get_ai_config_manager()
        available_configs = config_manager.get_all_configs()

        # 生成模型选项列表
        model_options = self._build_model_options(available_configs)

        return {
            'model_config': {
                'type': 'string',
                'required': True,
                'label': 'AI模型配置',
                'placeholder': '选择AI模型配置',
                'description': '要使用的AI模型配置',
                'options': model_options
            },
            'prompt_template': {
                'type': 'string',
                'required': True,
                'label': '提示词模板',
                'placeholder': '请输入信息提取提示词模板，可使用 {{变量名}} 引用上下文变量',
                'description': 'AI模型的信息提取提示词模板，支持变量替换'
            },
            'temperature': {
                'type': 'number',
                'required': False,
                'label': '温度参数',
                'default': 0.1,
                'min': 0.0,
                'max': 1.0,
                'description': '控制生成结果的随机性，信息提取任务建议使用较低值'
            },
            'max_tokens': {
                'type': 'number',
                'required': False,
                'label': '最大输出长度',
                'default': 500,
                'min': 1,
                'max': 2000,
                'description': '限制AI生成的最大token数量'
            },
            'system_prompt': {
                'type': 'string',
                'required': False,
                'label': '系统提示',
                'placeholder': '系统角色设定',
                'description': '系统级别的角色设定提示'
            },
            'extraction_schema': {
                'type': 'string',
                'required': True,
                'label': '提取 schema',
                'placeholder': '请输入提取的结构化 schema，如：{\"姓名\": \"string\", \"年龄\": \"number\"}',
                'description': '指定要提取的结构化信息 schema，使用 JSON 格式',
                'multiline': True,
                'rows': 5
            },
            'output_format': {
                'type': 'string',
                'required': False,
                'label': '输出格式',
                'default': 'json',
                'options': [
                    {'value': 'json', 'label': 'JSON格式'},
                    {'value': 'text', 'label': '纯文本'}
                ],
                'description': '指定提取结果的格式'
            }
        }
