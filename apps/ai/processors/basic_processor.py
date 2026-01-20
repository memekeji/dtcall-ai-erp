"""
基础节点处理器
"""

from .base_processor import BaseNodeProcessor, NodeProcessorRegistry


@NodeProcessorRegistry.register('start')
class StartProcessor(BaseNodeProcessor):
    """开始节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "开始节点"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-play"
    
    @classmethod
    def get_description(cls):
        return "工作流开始节点"
    
    def _get_config_schema(self) -> dict:
        """获取开始节点的配置模式"""
        return {
            'trigger_type': {
                'type': 'string',
                'required': True,
                'label': '触发类型',
                'options': [
                    {'value': 'manual', 'label': '手动触发'},
                    {'value': 'schedule', 'label': '定时触发'},
                    {'value': 'event', 'label': '事件触发'},
                    {'value': 'api', 'label': 'API调用'}
                ],
                'description': '工作流触发方式'
            },
            'input_config': {
                'type': 'object',
                'required': True,
                'label': '输入配置',
                'properties': {
                    'input_type': {
                        'type': 'string',
                        'required': True,
                        'label': '输入类型',
                        'options': [
                            {'value': 'text', 'label': '文本输入'},
                            {'value': 'image', 'label': '图片上传'},
                            {'value': 'file', 'label': '文件上传'},
                            {'value': 'json', 'label': 'JSON数据'},
                            {'value': 'variable', 'label': '变量引用'}
                        ],
                        'description': '选择工作流启动时的输入方式'
                    },
                    'text_config': {
                        'type': 'object',
                        'required': False,
                        'label': '文本输入配置',
                        'properties': {
                            'placeholder': {
                                'type': 'string',
                                'required': False,
                                'label': '占位符',
                                'default': '请输入文本内容'
                            },
                            'multiline': {
                                'type': 'boolean',
                                'required': False,
                                'label': '多行输入',
                                'default': False
                            },
                            'max_length': {
                                'type': 'number',
                                'required': False,
                                'label': '最大长度',
                                'default': 1000
                            }
                        },
                        'depends_on': {'input_type': 'text'}
                    },
                    'image_config': {
                        'type': 'object',
                        'required': False,
                        'label': '图片上传配置',
                        'properties': {
                            'accept_types': {
                                'type': 'array',
                                'required': True,
                                'label': '接受的图片类型',
                                'items': {'type': 'string'},
                                'default': ['jpg', 'jpeg', 'png', 'gif', 'webp']
                            },
                            'max_size': {
                                'type': 'number',
                                'required': False,
                                'label': '最大文件大小(MB)',
                                'default': 10
                            },
                            'min_width': {
                                'type': 'number',
                                'required': False,
                                'label': '最小宽度',
                                'default': 0
                            },
                            'min_height': {
                                'type': 'number',
                                'required': False,
                                'label': '最小高度',
                                'default': 0
                            }
                        },
                        'depends_on': {'input_type': 'image'}
                    },
                    'file_config': {
                        'type': 'object',
                        'required': False,
                        'label': '文件上传配置',
                        'properties': {
                            'accept_types': {
                                'type': 'array',
                                'required': True,
                                'label': '接受的文件类型',
                                'items': {'type': 'string'},
                                'default': ['*']
                            },
                            'max_size': {
                                'type': 'number',
                                'required': False,
                                'label': '最大文件大小(MB)',
                                'default': 50
                            },
                            'multiple': {
                                'type': 'boolean',
                                'required': False,
                                'label': '允许多文件上传',
                                'default': False
                            }
                        },
                        'depends_on': {'input_type': 'file'}
                    },
                    'json_config': {
                        'type': 'object',
                        'required': False,
                        'label': 'JSON数据配置',
                        'properties': {
                            'schema': {
                                'type': 'string',
                                'required': False,
                                'label': 'JSON Schema',
                                'multiline': True,
                                'rows': 5,
                                'description': 'JSON数据的验证模式'
                            },
                            'default_value': {
                                'type': 'string',
                                'required': False,
                                'label': '默认值',
                                'multiline': True,
                                'rows': 5
                            }
                        },
                        'depends_on': {'input_type': 'json'}
                    },
                    'variable_config': {
                        'type': 'object',
                        'required': False,
                        'label': '变量引用配置',
                        'properties': {
                            'variable_name': {
                                'type': 'string',
                                'required': True,
                                'label': '变量名',
                                'description': '要引用的变量名称'
                            },
                            'default_value': {
                                'type': 'string',
                                'required': False,
                                'label': '默认值',
                                'multiline': True,
                                'rows': 3
                            }
                        },
                        'depends_on': {'input_type': 'variable'}
                    },
                    'output_variable': {
                        'type': 'string',
                        'required': True,
                        'label': '输出变量名',
                        'default': 'input_data',
                        'description': '存储输入数据的变量名'
                    }
                }
            },
            'schedule_config': {
                'type': 'object',
                'required': False,
                'label': '定时配置',
                'properties': {
                    'cron_expression': {
                        'type': 'string',
                        'required': True,
                        'label': 'Cron表达式',
                        'placeholder': '0 0 * * *',
                        'description': '定时执行的Cron表达式'
                    },
                    'timezone': {
                        'type': 'string',
                        'required': False,
                        'label': '时区',
                        'default': 'Asia/Shanghai'
                    }
                },
                'depends_on': {'trigger_type': 'schedule'}
            },
            'event_config': {
                'type': 'object',
                'required': False,
                'label': '事件配置',
                'properties': {
                    'event_type': {
                        'type': 'string',
                        'required': True,
                        'label': '事件类型'
                    },
                    'event_filter': {
                        'type': 'object',
                        'required': False,
                        'label': '事件过滤器',
                        'default': {}
                    }
                },
                'depends_on': {'trigger_type': 'event'}
            },
            'api_config': {
                'type': 'object',
                'required': False,
                'label': 'API配置',
                'properties': {
                    'api_path': {
                        'type': 'string',
                        'required': True,
                        'label': 'API路径'
                    },
                    'auth_required': {
                        'type': 'boolean',
                        'required': False,
                        'label': '需要认证',
                        'default': True
                    }
                },
                'depends_on': {'trigger_type': 'api'}
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行开始节点逻辑"""
        trigger_type = config.get('trigger_type', 'manual')
        input_config = config.get('input_config', {})
        input_type = input_config.get('input_type', 'text')
        output_var = input_config.get('output_variable', 'input_data')
        
        # 处理不同类型的输入
        input_data = {}
        if input_type == 'text':
            text_config = input_config.get('text_config', {})
            input_data = {
                'type': 'text',
                'value': text_config.get('default_value', ''),
                'placeholder': text_config.get('placeholder', '请输入文本内容'),
                'multiline': text_config.get('multiline', False),
                'max_length': text_config.get('max_length', 1000)
            }
        elif input_type == 'image':
            image_config = input_config.get('image_config', {})
            input_data = {
                'type': 'image',
                'accept_types': image_config.get('accept_types', ['jpg', 'jpeg', 'png', 'gif', 'webp']),
                'max_size': image_config.get('max_size', 10),
                'min_width': image_config.get('min_width', 0),
                'min_height': image_config.get('min_height', 0)
            }
        elif input_type == 'file':
            file_config = input_config.get('file_config', {})
            input_data = {
                'type': 'file',
                'accept_types': file_config.get('accept_types', ['*']),
                'max_size': file_config.get('max_size', 50),
                'multiple': file_config.get('multiple', False)
            }
        elif input_type == 'json':
            json_config = input_config.get('json_config', {})
            input_data = {
                'type': 'json',
                'schema': json_config.get('schema', ''),
                'default_value': json_config.get('default_value', '{}')
            }
        elif input_type == 'variable':
            var_config = input_config.get('variable_config', {})
            var_name = var_config.get('variable_name', '')
            default_value = var_config.get('default_value', '')
            input_data = {
                'type': 'variable',
                'variable_name': var_name,
                'default_value': default_value,
                'value': context.get(var_name, default_value)
            }
        
        # 将输入数据存储到上下文中
        context[output_var] = input_data
        
        return {
            'trigger_type': trigger_type,
            'input_type': input_type,
            'success': True,
            'message': f"工作流通过 {trigger_type} 方式启动，输入类型: {input_type}",
            'input_data': input_data,
            'output_variable': output_var
        }


@NodeProcessorRegistry.register('end')
class EndProcessor(BaseNodeProcessor):
    """结束节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "结束节点"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-ok"
    
    @classmethod
    def get_description(cls):
        return "工作流结束节点"
    
    def _get_config_schema(self) -> dict:
        """获取结束节点的配置模式"""
        return {
            'result_type': {
                'type': 'string',
                'required': True,
                'label': '结果类型',
                'options': [
                    {'value': 'success', 'label': '成功'},
                    {'value': 'failure', 'label': '失败'},
                    {'value': 'warning', 'label': '警告'},
                    {'value': 'info', 'label': '信息'}
                ],
                'description': '工作流执行结果类型'
            },
            'output_data': {
                'type': 'object',
                'required': False,
                'label': '输出数据',
                'default': {},
                'description': '工作流最终输出数据'
            },
            'save_result': {
                'type': 'boolean',
                'required': False,
                'label': '保存结果',
                'default': True,
                'description': '是否保存执行结果'
            },
            'notify_on_complete': {
                'type': 'boolean',
                'required': False,
                'label': '完成时通知',
                'default': False,
                'description': '工作流完成时发送通知'
            },
            'notification_config': {
                'type': 'object',
                'required': False,
                'label': '通知配置',
                'properties': {
                    'recipients': {
                        'type': 'array',
                        'required': True,
                        'label': '接收人',
                        'items': {'type': 'string'}
                    },
                    'message_template': {
                        'type': 'string',
                        'required': True,
                        'label': '消息模板',
                        'multiline': True,
                        'rows': 3
                    }
                },
                'depends_on': {'notify_on_complete': True}
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行结束节点逻辑"""
        result_type = config.get('result_type', 'success')
        output_data = config.get('output_data', {})
        save_result = config.get('save_result', True)
        notify_on_complete = config.get('notify_on_complete', False)
        
        # 合并输出数据到结果中
        result_data = {**context, **output_data}
        
        result = {
            'result_type': result_type,
            'success': True,
            'message': f"工作流执行完成，结果类型: {result_type}",
            'output_data': result_data,
            'save_result': save_result,
            'notify_on_complete': notify_on_complete
        }
        
        return result


@NodeProcessorRegistry.register('loop')
class LoopProcessor(BaseNodeProcessor):
    """循环节点处理器 - 使用 enhanced_processors 中的增强版本"""
    
    @classmethod
    def get_display_name(cls):
        return "循环处理"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-refresh"
    
    @classmethod
    def get_description(cls):
        return "循环执行子节点，支持For/While/Foreach循环"
    
    def _get_config_schema(self) -> dict:
        """获取循环节点的配置模式"""
        from .enhanced_processors import LoopProcessor as EnhancedLoopProcessor
        return EnhancedLoopProcessor(node_type_code='loop')._get_config_schema()
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行循环节点逻辑"""
        from .enhanced_processors import LoopProcessor as EnhancedLoopProcessor
        processor = EnhancedLoopProcessor('loop')
        return processor.execute(config, context)


# WaitProcessor已迁移到complete_node_processors.py
# 提供更完整的异步实现，包括动态等待时间支持
# 保留此注释以保持代码可追溯性

@NodeProcessorRegistry.register('parallel')
class ParallelProcessor(BaseNodeProcessor):
    """并行处理节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "并行处理节点"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-layer"
    
    @classmethod
    def get_description(cls):
        return "并行执行多个子节点"
    
    def _get_config_schema(self) -> dict:
        """获取并行处理节点的配置模式"""
        return {
            'parallel_type': {
                'type': 'string',
                'required': True,
                'label': '并行类型',
                'options': [
                    {'value': 'all', 'label': '等待所有完成'},
                    {'value': 'any', 'label': '等待任意完成'},
                    {'value': 'race', 'label': '竞速模式'}
                ],
                'description': '并行执行的策略'
            },
            'max_parallel': {
                'type': 'number',
                'required': False,
                'label': '最大并行数',
                'default': 5,
                'min': 1,
                'max': 20,
                'description': '最大并行执行的子节点数量'
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': '超时时间',
                'default': 300,
                'min': 1,
                'max': 3600,
                'description': '并行执行的超时时间，单位：秒'
            },
            'error_handling': {
                'type': 'string',
                'required': False,
                'label': '错误处理',
                'options': [
                    {'value': 'fail_fast', 'label': '快速失败'},
                    {'value': 'continue', 'label': '继续执行'},
                    {'value': 'ignore', 'label': '忽略错误'}
                ],
                'default': 'fail_fast',
                'description': '并行执行中遇到错误的处理方式'
            },
            'join_strategy': {
                'type': 'string',
                'required': False,
                'label': '结果合并策略',
                'options': [
                    {'value': 'merge', 'label': '合并结果'},
                    {'value': 'keep_first', 'label': '保留第一个'},
                    {'value': 'keep_all', 'label': '保留所有'},
                    {'value': 'custom', 'label': '自定义合并'}
                ],
                'default': 'merge',
                'description': '并行执行结果的合并策略'
            },
            'custom_join_expression': {
                'type': 'string',
                'required': False,
                'label': '自定义合并表达式',
                'placeholder': '例如：{"results": $results}',
                'description': '自定义合并结果的表达式，支持变量 $results 表示所有并行结果',
                'multiline': True,
                'rows': 3,
                'depends_on': {'join_strategy': 'custom'}
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行并行处理节点逻辑"""
        parallel_type = config.get('parallel_type', 'all')
        max_parallel = config.get('max_parallel', 5)
        timeout = config.get('timeout', 300)
        error_handling = config.get('error_handling', 'fail_fast')
        join_strategy = config.get('join_strategy', 'merge')
        
        return {
            'parallel_type': parallel_type,
            'max_parallel': max_parallel,
            'timeout': timeout,
            'error_handling': error_handling,
            'join_strategy': join_strategy,
            'success': True,
            'message': f"并行执行 {max_parallel} 个子节点，策略：{parallel_type}",
            'context': context
        }