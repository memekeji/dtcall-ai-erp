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
    """循环节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "循环节点"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-refresh"
    
    @classmethod
    def get_description(cls):
        return "循环执行子节点"
    
    def _get_config_schema(self) -> dict:
        """获取循环节点的配置模式"""
        return {
            'loop_type': {
                'type': 'string',
                'required': True,
                'label': '循环类型',
                'options': [
                    {'value': 'for_loop', 'label': 'For循环'},
                    {'value': 'while_loop', 'label': 'While循环'},
                    {'value': 'foreach', 'label': '遍历循环'}
                ],
                'description': '选择循环执行方式'
            },
            'for_loop_config': {
                'type': 'object',
                'required': False,
                'label': 'For循环配置',
                'properties': {
                    'start_value': {
                        'type': 'number',
                        'required': True,
                        'label': '起始值',
                        'default': 0
                    },
                    'end_value': {
                        'type': 'number',
                        'required': True,
                        'label': '结束值',
                        'default': 10
                    },
                    'step_value': {
                        'type': 'number',
                        'required': False,
                        'label': '步长',
                        'default': 1
                    },
                    'loop_variable': {
                        'type': 'string',
                        'required': True,
                        'label': '循环变量名',
                        'default': 'i'
                    }
                },
                'depends_on': {'loop_type': 'for_loop'}
            },
            'while_loop_config': {
                'type': 'object',
                'required': False,
                'label': 'While循环配置',
                'properties': {
                    'condition': {
                        'type': 'string',
                        'required': True,
                        'label': '循环条件',
                        'multiline': True,
                        'rows': 3,
                        'description': '循环继续执行的条件表达式'
                    },
                    'max_iterations': {
                        'type': 'number',
                        'required': False,
                        'label': '最大迭代次数',
                        'default': 100,
                        'min': 1,
                        'max': 10000
                    }
                },
                'depends_on': {'loop_type': 'while_loop'}
            },
            'foreach_config': {
                'type': 'object',
                'required': False,
                'label': '遍历循环配置',
                'properties': {
                    'collection': {
                        'type': 'string',
                        'required': True,
                        'label': '遍历集合',
                        'description': '要遍历的数据集合变量名'
                    },
                    'item_variable': {
                        'type': 'string',
                        'required': True,
                        'label': '元素变量名',
                        'default': 'item'
                    },
                    'index_variable': {
                        'type': 'string',
                        'required': False,
                        'label': '索引变量名',
                        'default': 'index'
                    }
                },
                'depends_on': {'loop_type': 'foreach'}
            },
            'break_condition': {
                'type': 'string',
                'required': False,
                'label': '中断条件',
                'multiline': True,
                'rows': 3,
                'description': '提前终止循环的条件表达式'
            },
            'continue_condition': {
                'type': 'string',
                'required': False,
                'label': '继续条件',
                'multiline': True,
                'rows': 3,
                'description': '跳过当前迭代的条件表达式'
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行循环节点逻辑"""
        loop_type = config.get('loop_type', 'for_loop')
        
        result = {
            'loop_type': loop_type,
            'success': True,
            'iterations': 0,
            'results': [],
            'message': ''
        }
        
        try:
            if loop_type == 'for_loop':
                self._execute_for_loop(config, context, result)
            elif loop_type == 'while_loop':
                self._execute_while_loop(config, context, result)
            elif loop_type == 'foreach':
                self._execute_foreach_loop(config, context, result)
            else:
                result['success'] = False
                result['message'] = f"不支持的循环类型: {loop_type}"
                
        except Exception as e:
            result['success'] = False
            result['message'] = f"循环执行失败: {str(e)}"
        
        return result
    
    def _execute_for_loop(self, config: dict, context: dict, result: dict):
        """执行For循环"""
        for_config = config.get('for_loop_config', {})
        start = for_config.get('start_value', 0)
        end = for_config.get('end_value', 10)
        step = for_config.get('step_value', 1)
        loop_var = for_config.get('loop_variable', 'i')
        
        break_condition = config.get('break_condition', '')
        continue_condition = config.get('continue_condition', '')
        
        for i in range(start, end, step):
            # 设置循环变量
            loop_context = context.copy()
            loop_context[loop_var] = i
            
            # 检查中断条件
            if break_condition and self._evaluate_condition(break_condition, loop_context):
                result['message'] = f"循环在第 {result['iterations'] + 1} 次迭代时中断"
                break
            
            # 检查继续条件
            if continue_condition and self._evaluate_condition(continue_condition, loop_context):
                continue
            
            # 执行子节点（这里需要集成子节点执行逻辑）
            # 暂时记录迭代信息
            result['iterations'] += 1
            result['results'].append({
                'iteration': result['iterations'],
                'loop_variable': i,
                'context': loop_context
            })
        
        result['message'] = f"For循环完成，共执行 {result['iterations']} 次迭代"
    
    def _execute_while_loop(self, config: dict, context: dict, result: dict):
        """执行While循环"""
        while_config = config.get('while_loop_config', {})
        condition = while_config.get('condition', '')
        max_iterations = while_config.get('max_iterations', 100)
        
        break_condition = config.get('break_condition', '')
        continue_condition = config.get('continue_condition', '')
        
        iteration = 0
        while self._evaluate_condition(condition, context) and iteration < max_iterations:
            iteration += 1
            
            # 检查中断条件
            if break_condition and self._evaluate_condition(break_condition, context):
                result['message'] = f"循环在第 {iteration} 次迭代时中断"
                break
            
            # 检查继续条件
            if continue_condition and self._evaluate_condition(continue_condition, context):
                continue
            
            # 执行子节点
            result['iterations'] += 1
            result['results'].append({
                'iteration': iteration,
                'context': context.copy()
            })
        
        result['message'] = f"While循环完成，共执行 {result['iterations']} 次迭代"
    
    def _execute_foreach_loop(self, config: dict, context: dict, result: dict):
        """执行遍历循环"""
        foreach_config = config.get('foreach_config', {})
        collection_name = foreach_config.get('collection', '')
        item_var = foreach_config.get('item_variable', 'item')
        index_var = foreach_config.get('index_variable', 'index')
        
        break_condition = config.get('break_condition', '')
        continue_condition = config.get('continue_condition', '')
        
        # 获取要遍历的集合
        collection = context.get(collection_name, [])
        if not isinstance(collection, (list, tuple, dict)):
            raise Exception(f"无法遍历的数据类型: {type(collection)}")
        
        if isinstance(collection, dict):
            items = collection.items()
        else:
            items = enumerate(collection)
        
        for index, item in items:
            # 设置循环变量
            loop_context = context.copy()
            loop_context[item_var] = item
            loop_context[index_var] = index
            
            # 检查中断条件
            if break_condition and self._evaluate_condition(break_condition, loop_context):
                result['message'] = f"循环在第 {result['iterations'] + 1} 次迭代时中断"
                break
            
            # 检查继续条件
            if continue_condition and self._evaluate_condition(continue_condition, loop_context):
                continue
            
            # 执行子节点
            result['iterations'] += 1
            result['results'].append({
                'iteration': result['iterations'],
                'index': index,
                'item': item,
                'context': loop_context
            })
        
        result['message'] = f"遍历循环完成，共执行 {result['iterations']} 次迭代"
    
    def _evaluate_condition(self, condition: str, context: dict) -> bool:
        """评估条件表达式"""
        if not condition:
            return True
        
        try:
            # 替换变量
            condition = self._replace_variables(condition, context)
            
            # 简单的条件评估（注意安全限制）
            return bool(eval(condition))
        except:
            return False
    
    def _replace_variables(self, condition: str, context: dict) -> str:
        """替换条件表达式中的变量"""
        for key, value in context.items():
            placeholder = f'{{{{{key}}}}}'
            condition = condition.replace(placeholder, str(value))
        return condition


@NodeProcessorRegistry.register('wait')
class WaitProcessor(BaseNodeProcessor):
    """等待节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "等待节点"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-time"
    
    @classmethod
    def get_description(cls):
        return "等待指定时间后继续执行"
    
    def _get_config_schema(self) -> dict:
        """获取等待节点的配置模式"""
        return {
            'wait_type': {
                'type': 'string',
                'required': True,
                'label': '等待类型',
                'options': [
                    {'value': 'fixed', 'label': '固定时间'},
                    {'value': 'dynamic', 'label': '动态时间'}
                ],
                'description': '等待时间的类型'
            },
            'wait_time': {
                'type': 'number',
                'required': True,
                'label': '等待时间',
                'default': 1,
                'min': 0.1,
                'max': 3600,
                'description': '等待的固定时间，单位：秒'
            },
            'time_unit': {
                'type': 'string',
                'required': False,
                'label': '时间单位',
                'options': [
                    {'value': 'seconds', 'label': '秒'},
                    {'value': 'minutes', 'label': '分钟'},
                    {'value': 'hours', 'label': '小时'}
                ],
                'default': 'seconds',
                'description': '等待时间的单位'
            },
            'dynamic_time_expression': {
                'type': 'string',
                'required': False,
                'label': '动态时间表达式',
                'placeholder': '例如：{{delay}} * 1000',
                'description': '动态计算等待时间的表达式，支持变量替换',
                'depends_on': {'wait_type': 'dynamic'}
            },
            'wait_message': {
                'type': 'string',
                'required': False,
                'label': '等待消息',
                'placeholder': '等待中...',
                'description': '等待过程中显示的消息'
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行等待节点逻辑"""
        wait_type = config.get('wait_type', 'fixed')
        wait_time = config.get('wait_time', 1)
        time_unit = config.get('time_unit', 'seconds')
        wait_message = config.get('wait_message', '等待中...')
        
        # 转换时间单位
        time_conversion = {
            'seconds': 1,
            'minutes': 60,
            'hours': 3600
        }
        
        total_seconds = wait_time * time_conversion.get(time_unit, 1)
        
        # 处理动态时间
        if wait_type == 'dynamic':
            dynamic_expression = config.get('dynamic_time_expression', '')
            if dynamic_expression:
                # 替换变量
                for key, value in context.items():
                    placeholder = f'{{{{{key}}}}}'
                    dynamic_expression = dynamic_expression.replace(placeholder, str(value))
                
                try:
                    # 计算动态时间（单位：毫秒）
                    dynamic_ms = eval(dynamic_expression)
                    total_seconds = dynamic_ms / 1000
                except:
                    # 计算失败，使用默认值
                    pass
        
        # 这里应该实现实际的等待逻辑，但在当前架构下，我们只返回配置信息
        # 实际的等待会在工作流执行引擎中处理
        
        return {
            'wait_type': wait_type,
            'wait_time': wait_time,
            'time_unit': time_unit,
            'total_seconds': total_seconds,
            'wait_message': wait_message,
            'success': True,
            'message': f"等待 {total_seconds} 秒后继续执行"
        }


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