"""
AI模型节点处理器
"""

from .base_processor import BaseNodeProcessor, NodeProcessorRegistry


@NodeProcessorRegistry.register('ai_model')
class AIModelProcessor(BaseNodeProcessor):
    """AI模型节点处理器"""
    
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
        model_options = []
        for config_id, config in available_configs.items():
            if config.get('is_active'):
                provider = config.get('provider', 'unknown')
                name = config.get('name', config_id)
                model_options.append({'value': f"{provider}:{name}", 'label': f"{provider}:{name}"})
        
        # 如果没有可用配置，添加默认选项
        if not model_options:
            model_options = [
                {'value': 'openai:GPT-3.5 Turbo', 'label': 'openai:GPT-3.5 Turbo'},
                {'value': 'openai:GPT-4', 'label': 'openai:GPT-4'},
                {'value': 'qwen:千问', 'label': 'qwen:千问'},
                {'value': 'wenxin:文心一言', 'label': 'wenxin:文心一言'},
                {'value': 'deepseek:DeepSeek', 'label': 'deepseek:DeepSeek'},
                {'value': 'doubao:豆包', 'label': 'doubao:豆包'}
            ]
        
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
        from apps.ai.utils.ai_client import AIClient
        
        # 获取配置参数
        model_config_str = config.get('model_config', '')
        prompt_template = config.get('prompt_template', '')
        temperature = config.get('temperature', 0.7)
        max_tokens = config.get('max_tokens', 1000)
        system_prompt = config.get('system_prompt', '')
        
        # 解析模型配置
        config_manager = get_ai_config_manager()
        ai_config = None
        
        if ':' in model_config_str:
            # 格式为 provider:name
            provider, name = model_config_str.split(':', 1)
            ai_config = config_manager.get_config_by_provider(provider)
        else:
            # 尝试直接使用配置ID
            ai_config = config_manager.get_config(model_config_str)
        
        if not ai_config:
            # 如果没有找到配置，使用默认配置
            ai_config = config_manager.get_active_config()
        
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
            # 使用BaseAIClient而非AIClient，支持直接传递配置参数
            from apps.ai.utils.ai_client import BaseAIClient
            
            ai_client = BaseAIClient(
                provider=ai_config.get('provider'),
                base_url=ai_config.get('api_base'),
                api_key=ai_config.get('api_key'),
                model_config=ai_config
            )
            
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
            return {
                'ai_result': None,
                'model_used': ai_config.get('name', 'unknown'),
                'provider': ai_config.get('provider'),
                'config_id': ai_config.get('id'),
                'prompt_length': len(prompt),
                'response_length': 0,
                'error': str(e)
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
        model_options = []
        for config_id, config in available_configs.items():
            if config.get('is_active'):
                provider = config.get('provider', 'unknown')
                name = config.get('name', config_id)
                model_options.append({'value': f"{provider}:{name}", 'label': f"{provider}:{name}"})
        
        # 如果没有可用配置，添加默认选项
        if not model_options:
            model_options = [
                {'value': 'openai:GPT-3.5 Turbo', 'label': 'openai:GPT-3.5 Turbo'},
                {'value': 'openai:GPT-4', 'label': 'openai:GPT-4'},
                {'value': 'qwen:千问', 'label': 'qwen:千问'},
                {'value': 'wenxin:文心一言', 'label': 'wenxin:文心一言'},
                {'value': 'deepseek:DeepSeek', 'label': 'deepseek:DeepSeek'},
                {'value': 'doubao:豆包', 'label': 'doubao:豆包'}
            ]
        
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
        model_options = []
        for config_id, config in available_configs.items():
            if config.get('is_active'):
                provider = config.get('provider', 'unknown')
                name = config.get('name', config_id)
                model_options.append({'value': f"{provider}:{name}", 'label': f"{provider}:{name}"})
        
        # 如果没有可用配置，添加默认选项
        if not model_options:
            model_options = [
                {'value': 'openai:GPT-3.5 Turbo', 'label': 'openai:GPT-3.5 Turbo'},
                {'value': 'openai:GPT-4', 'label': 'openai:GPT-4'},
                {'value': 'qwen:千问', 'label': 'qwen:千问'},
                {'value': 'wenxin:文心一言', 'label': 'wenxin:文心一言'},
                {'value': 'deepseek:DeepSeek', 'label': 'deepseek:DeepSeek'},
                {'value': 'doubao:豆包', 'label': 'doubao:豆包'}
            ]
        
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
        model_options = []
        for config_id, config in available_configs.items():
            if config.get('is_active'):
                provider = config.get('provider', 'unknown')
                name = config.get('name', config_id)
                model_options.append({'value': f"{provider}:{name}", 'label': f"{provider}:{name}"})
        
        # 如果没有可用配置，添加默认选项
        if not model_options:
            model_options = [
                {'value': 'openai:GPT-3.5 Turbo', 'label': 'openai:GPT-3.5 Turbo'},
                {'value': 'openai:GPT-4', 'label': 'openai:GPT-4'},
                {'value': 'qwen:千问', 'label': 'qwen:千问'},
                {'value': 'wenxin:文心一言', 'label': 'wenxin:文心一言'},
                {'value': 'deepseek:DeepSeek', 'label': 'deepseek:DeepSeek'},
                {'value': 'doubao:豆包', 'label': 'doubao:豆包'}
            ]
        
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