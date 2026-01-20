"""
Complete Node Processors for DTCall Workflow Designer
Comprehensive node types comparable to Dify and Coze platforms
Reference implementation based on Dify and Coze platform standards
"""

import json
import re
import ast
import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
import hashlib
import uuid

from apps.ai.processors.base_processor import BaseNodeProcessor, NodeProcessorRegistry
from apps.ai.services.ai_analysis_service import AIAnalysisService
from apps.ai.services.rag_service import RAGService
from apps.ai.services.intent_recognition_service import IntentRecognitionService

logger = logging.getLogger(__name__)


@NodeProcessorRegistry.register('workflow_trigger')
class WorkflowTriggerProcessor(BaseNodeProcessor):
    """工作流触发器处理器 - 支持多种触发方式"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'trigger_type': {
                'type': 'select',
                'required': True,
                'label': '触发类型',
                'options': [
                    {'value': 'manual', 'label': '手动触发', 'description': '用户手动启动工作流'},
                    {'value': 'webhook', 'label': 'Webhook触发', 'description': '通过HTTP请求触发'},
                    {'value': 'schedule', 'label': '定时触发', 'description': '按设定时间自动执行'},
                    {'value': 'event', 'label': '事件触发', 'description': '响应系统事件'},
                    {'value': 'api', 'label': 'API调用', 'description': '通过API调用触发'},
                ],
                'default': 'manual'
            },
            'webhook_path': {
                'type': 'string',
                'required': False,
                'label': 'Webhook路径',
                'placeholder': '/webhook/workflow_id',
                'depends_on': {'trigger_type': ['webhook']}
            },
            'schedule_cron': {
                'type': 'string',
                'required': False,
                'label': 'Cron表达式',
                'placeholder': '0 * * * *',
                'depends_on': {'trigger_type': ['schedule']},
                'description': '标准Cron格式: 分 时 日 月 周'
            },
            'event_type': {
                'type': 'string',
                'required': False,
                'label': '事件类型',
                'placeholder': 'task.completed',
                'depends_on': {'trigger_type': ['event']}
            },
            'input_parameters': {
                'type': 'array',
                'required': False,
                'label': '输入参数定义',
                'items': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string', 'label': '参数名'},
                        'type': {'type': 'string', 'label': '类型'},
                        'required': {'type': 'boolean', 'label': '必填'},
                        'default': {'type': 'string', 'label': '默认值'}
                    }
                }
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': '输出变量名',
                'default': 'trigger_data'
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        trigger_type = config.get('trigger_type', 'manual')
        output_var = config.get('output_variable', 'trigger_data')

        result = {
            'trigger_type': trigger_type,
            'triggered_at': datetime.now().isoformat(),
            'triggered_by': context.get('user_id', 'system'),
            'status': 'completed'
        }

        if trigger_type == 'manual':
            result['message'] = '手动触发执行'
        elif trigger_type == 'webhook':
            webhook_path = config.get('webhook_path', '')
            result['webhook_path'] = webhook_path
            result['message'] = f'Webhook触发: {webhook_path}'
        elif trigger_type == 'schedule':
            cron = config.get('schedule_cron', '')
            result['schedule_cron'] = cron
            result['message'] = f'定时任务触发: {cron}'
        elif trigger_type == 'event':
            event_type = config.get('event_type', '')
            result['event_type'] = event_type
            result['message'] = f'事件触发: {event_type}'
        elif trigger_type == 'api':
            result['message'] = 'API调用触发'

        return {output_var: result, 'status': 'completed'}


@NodeProcessorRegistry.register('chat_history')
class ConversationHistoryProcessor(BaseNodeProcessor):
    """对话历史处理器 - 管理会话上下文"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'session_id': {
                'type': 'string',
                'required': True,
                'label': '会话ID变量',
                'placeholder': '输入会话ID变量名'
            },
            'max_messages': {
                'type': 'number',
                'required': False,
                'label': '最大消息数',
                'default': 10,
                'min': 1,
                'max': 100
            },
            'include_system': {
                'type': 'boolean',
                'required': False,
                'label': '包含系统消息',
                'default': True
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': '输出变量名',
                'default': 'history'
            },
            'direction': {
                'type': 'select',
                'required': False,
                'label': '消息顺序',
                'options': [
                    {'value': 'newest_first', 'label': '最新在前'},
                    {'value': 'oldest_first', 'label': '最旧在前'}
                ],
                'default': 'newest_first'
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        session_id = config.get('session_id', '')
        max_messages = config.get('max_messages', 10)
        include_system = config.get('include_system', True)
        output_var = config.get('output_variable', 'history')
        direction = config.get('direction', 'newest_first')

        session_key = f'chat_history_{session_id}'
        history = context.get(session_key, [])

        if not isinstance(history, list):
            history = []

        filtered_history = []
        for msg in history:
            if include_system or msg.get('role') != 'system':
                filtered_history.append(msg)

        if direction == 'newest_first':
            filtered_history = filtered_history[-max_messages:]
        else:
            filtered_history = filtered_history[:max_messages]

        return {
            output_var: filtered_history,
            'message_count': len(filtered_history),
            'status': 'completed'
        }


@NodeProcessorRegistry.register('wait')
class WaitProcessor(BaseNodeProcessor):
    """等待处理器 - 暂停执行指定时间"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'wait_type': {
                'type': 'select',
                'required': True,
                'label': '等待类型',
                'options': [
                    {'value': 'seconds', 'label': '秒'},
                    {'value': 'minutes', 'label': '分钟'},
                    {'value': 'hours', 'label': '小时'},
                    {'value': 'until', 'label': '直到指定时间'}
                ],
                'default': 'seconds'
            },
            'duration': {
                'type': 'number',
                'required': True,
                'label': '等待时长',
                'default': 5,
                'min': 1
            },
            'until_time': {
                'type': 'string',
                'required': False,
                'label': '目标时间',
                'placeholder': 'YYYY-MM-DD HH:MM:SS',
                'depends_on': {'wait_type': ['until']}
            },
            'output_variable': {
                'type': 'string',
                'required': False,
                'label': '输出变量名',
                'default': 'wait_completed'
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        wait_type = config.get('wait_type', 'seconds')
        duration = config.get('duration', 5)
        output_var = config.get('output_variable', 'wait_completed')

        wait_seconds = 0
        if wait_type == 'seconds':
            wait_seconds = duration
        elif wait_type == 'minutes':
            wait_seconds = duration * 60
        elif wait_type == 'hours':
            wait_seconds = duration * 3600
        elif wait_type == 'until':
            until_str = config.get('until_time', '')
            try:
                until_dt = datetime.strptime(until_str, '%Y-%m-%d %H:%M:%S')
                wait_seconds = max(0, (until_dt - datetime.now()).total_seconds())
            except:
                wait_seconds = 0

        if wait_seconds > 0 and wait_seconds < 3600:
            await asyncio.sleep(wait_seconds)

        return {
            output_var: True,
            'wait_seconds': wait_seconds,
            'completed_at': datetime.now().isoformat(),
            'status': 'completed'
        }


@NodeProcessorRegistry.register('schedule')
class ScheduledTaskProcessor(BaseNodeProcessor):
    """定时任务处理器 - 调度定时执行"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'cron_expression': {
                'type': 'string',
                'required': True,
                'label': 'Cron表达式',
                'placeholder': '0 * * * *',
                'description': '标准Cron格式: 分 时 日 月 周'
            },
            'timezone': {
                'type': 'string',
                'required': False,
                'label': '时区',
                'default': 'Asia/Shanghai'
            },
            'start_date': {
                'type': 'string',
                'required': False,
                'label': '开始日期',
                'placeholder': 'YYYY-MM-DD'
            },
            'end_date': {
                'type': 'string',
                'required': False,
                'label': '结束日期',
                'placeholder': 'YYYY-MM-DD'
            },
            'output_variable': {
                'type': 'string',
                'required': False,
                'label': '输出变量名',
                'default': 'schedule_config'
            },
            'enabled': {
                'type': 'boolean',
                'required': False,
                'label': '是否启用',
                'default': True
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        cron = config.get('cron_expression', '')
        timezone = config.get('timezone', 'Asia/Shanghai')
        start_date = config.get('start_date', '')
        end_date = config.get('end_date', '')
        enabled = config.get('enabled', True)
        output_var = config.get('output_variable', 'schedule_config')

        return {
            output_var: {
                'cron_expression': cron,
                'timezone': timezone,
                'start_date': start_date,
                'end_date': end_date,
                'enabled': enabled,
                'status': 'configured'
            },
            'status': 'completed'
        }


@NodeProcessorRegistry.register('iterator')
class IteratorProcessor(BaseNodeProcessor):
    """迭代器处理器 - 遍历集合并处理每个元素"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'iterable_variable': {
                'type': 'string',
                'required': True,
                'label': '可迭代变量',
                'placeholder': '输入数组或列表变量名'
            },
            'item_variable': {
                'type': 'string',
                'required': True,
                'label': '元素变量名',
                'default': 'item'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': '输出变量名',
                'default': 'results'
            },
            'parallel': {
                'type': 'boolean',
                'required': False,
                'label': '并行处理',
                'default': False
            },
            'max_concurrent': {
                'type': 'number',
                'required': False,
                'label': '最大并发数',
                'default': 5,
                'depends_on': {'parallel': [True]}
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        iterable_var = config.get('iterable_variable', '')
        item_var = config.get('item_variable', 'item')
        output_var = config.get('output_variable', 'results')
        parallel = config.get('parallel', False)
        max_concurrent = config.get('max_concurrent', 5)

        iterable = context.get(iterable_var, [])
        if not isinstance(iterable, (list, tuple, dict)):
            iterable = []

        results = []
        index = 0

        if parallel and len(iterable) > 1:
            semaphore = asyncio.Semaphore(max_concurrent)

            async def process_item(item, idx):
                async with semaphore:
                    item_context = context.copy()
                    if isinstance(iterable, dict):
                        item_context[item_var] = {'key': item, 'value': iterable[item]}
                    else:
                        item_context[item_var] = item
                    item_context['index'] = idx
                    return {'index': idx, 'item': item, 'result': item_context}

            tasks = [process_item(item, idx) for idx, item in enumerate(iterable)]
            results = await asyncio.gather(*tasks)
        else:
            for idx, item in enumerate(iterable):
                item_context = context.copy()
                if isinstance(iterable, dict):
                    item_context[item_var] = {'key': item, 'value': iterable[item]}
                else:
                    item_context[item_var] = item
                item_context['index'] = idx
                results.append({'index': idx, 'item': item, 'result': item_context})

        return {
            output_var: results,
            'total_count': len(results),
            'status': 'completed'
        }


@NodeProcessorRegistry.register('parameter_aggregation')
class ParameterAggregatorProcessor(BaseNodeProcessor):
    """参数聚合处理器 - 收集多个参数"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'parameters': {
                'type': 'array',
                'required': True,
                'label': '参数列表',
                'items': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string', 'label': '参数名'},
                        'source_type': {
                            'type': 'select',
                            'options': [
                                {'value': 'variable', 'label': '变量'},
                                {'value': 'fixed', 'label': '固定值'},
                                {'value': 'context', 'label': '上下文'}
                            ]
                        },
                        'source_value': {'type': 'string', 'label': '源值'},
                        'required': {'type': 'boolean', 'label': '必填'}
                    }
                }
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': '输出变量名',
                'default': 'aggregated_params'
            },
            'merge_strategy': {
                'type': 'select',
                'required': False,
                'label': '合并策略',
                'options': [
                    {'value': 'object', 'label': '对象合并'},
                    {'value': 'array', 'label': '数组拼接'},
                    {'value': 'override', 'label': '覆盖'}
                ],
                'default': 'object'
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        parameters = config.get('parameters', [])
        output_var = config.get('output_variable', 'aggregated_params')
        merge_strategy = config.get('merge_strategy', 'object')

        result = {}
        errors = []

        for param in parameters:
            name = param.get('name', '')
            source_type = param.get('source_type', 'variable')
            source_value = param.get('source_value', '')
            required = param.get('required', False)

            value = None
            if source_type == 'variable':
                value = context.get(source_value)
            elif source_type == 'fixed':
                value = source_value
            elif source_type == 'context':
                value = context.get(source_value)

            if required and value is None:
                errors.append(f"必填参数 '{name}' 缺失")
                continue

            if merge_strategy == 'object':
                result[name] = value
            elif merge_strategy == 'array':
                if 'array_items' not in result:
                    result['array_items'] = []
                result['array_items'].append({'name': name, 'value': value})

        if errors:
            return {output_var: result, 'errors': errors, 'status': 'failed'}

        return {
            output_var: result,
            'param_count': len(parameters),
            'status': 'completed'
        }


@NodeProcessorRegistry.register('variable_assignment')
class VariableAssignProcessor(BaseNodeProcessor):
    """变量赋值处理器 - 设置变量值"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'assignments': {
                'type': 'array',
                'required': True,
                'label': '赋值列表',
                'items': {
                    'type': 'object',
                    'properties': {
                        'variable_name': {'type': 'string', 'label': '变量名'},
                        'value_type': {
                            'type': 'select',
                            'options': [
                                {'value': 'variable', 'label': '变量'},
                                {'value': 'fixed', 'label': '固定值'},
                                {'value': 'expression', 'label': '表达式'},
                                {'value': 'context', 'label': '上下文'}
                            ]
                        },
                        'source_value': {'type': 'string', 'label': '源值'},
                        'expression': {'type': 'string', 'label': '表达式'}
                    }
                }
            },
            'output_variable': {
                'type': 'string',
                'required': False,
                'label': '输出变量名',
                'default': 'assignment_result'
            },
            'scope': {
                'type': 'select',
                'required': False,
                'label': '作用域',
                'options': [
                    {'value': 'local', 'label': '局部'},
                    {'value': 'global', 'label': '全局'},
                    {'value': 'workflow', 'label': '工作流'}
                ],
                'default': 'local'
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        assignments = config.get('assignments', [])
        output_var = config.get('output_variable', 'assignment_result')
        scope = config.get('scope', 'local')

        result = {'assignments': [], 'scope': scope}

        for assignment in assignments:
            var_name = assignment.get('variable_name', '')
            value_type = assignment.get('value_type', 'fixed')
            source_value = assignment.get('source_value', '')
            expression = assignment.get('expression', '')

            value = None
            if value_type == 'variable':
                value = context.get(source_value)
            elif value_type == 'fixed':
                value = source_value
            elif value_type == 'expression':
                try:
                    value = eval(expression, {'context': context, 'datetime': datetime})
                except:
                    value = None
            elif value_type == 'context':
                value = context.get(source_value)

            context[var_name] = value
            result['assignments'].append({
                'variable': var_name,
                'value': value,
                'type': value_type
            })

        return {
            output_var: result,
            'context': context,
            'status': 'completed'
        }


@NodeProcessorRegistry.register('template')
class TemplateProcessor(BaseNodeProcessor):
    """模板渲染处理器 - 使用模板引擎渲染内容"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'template_content': {
                'type': 'text',
                'required': True,
                'label': '模板内容',
                'multiline': True,
                'rows': 6,
                'placeholder': 'Hello {{name}}, welcome to {{place}}!'
            },
            'template_format': {
                'type': 'select',
                'required': False,
                'label': '模板格式',
                'options': [
                    {'value': 'jinja2', 'label': 'Jinja2'},
                    {'value': 'simple', 'label': '简单变量'},
                    {'value': 'python', 'label': 'Python格式化'}
                ],
                'default': 'jinja2'
            },
            'variables': {
                'type': 'object',
                'required': False,
                'label': '变量映射',
                'description': '将上下文变量映射到模板变量'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': '输出变量名',
                'default': 'rendered_content'
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        template = config.get('template_content', '')
        template_format = config.get('template_format', 'jinja2')
        var_mapping = config.get('variables', {})
        output_var = config.get('output_variable', 'rendered_content')

        render_context = {}
        for key, value in var_mapping.items():
            render_context[key] = context.get(value, '')

        rendered = template
        errors = []

        try:
            if template_format == 'jinja2':
                try:
                    from jinja2 import Template as Jinja2Template
                    jinja_template = Jinja2Template(template)
                    rendered = jinja_template.render(**render_context)
                except ImportError:
                    for key, value in render_context.items():
                        rendered = rendered.replace('{{' + key + '}}', str(value))
                        rendered = rendered.replace('{{ ' + key + ' }}', str(value))
            elif template_format == 'python':
                rendered = template.format(**render_context)
            else:
                for key, value in render_context.items():
                    rendered = rendered.replace('{{' + key + '}}', str(value))
                    rendered = rendered.replace('{{ ' + key + ' }}', str(value))
        except Exception as e:
            errors.append(str(e))
            rendered = template

        return {
            output_var: rendered,
            'template': template,
            'variables_used': list(render_context.keys()),
            'errors': errors,
            'status': 'completed' if not errors else 'partial'
        }


@NodeProcessorRegistry.register('code_block')
class CodeBlockProcessor(BaseNodeProcessor):
    """代码块处理器 - 执行自定义代码"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'code': {
                'type': 'text',
                'required': True,
                'label': '代码',
                'multiline': True,
                'rows': 10,
                'placeholder': 'def main(input_data, context):\n    # your code here\n    return {"result": input_data}'
            },
            'language': {
                'type': 'select',
                'required': True,
                'label': '语言',
                'options': [
                    {'value': 'python', 'label': 'Python'},
                    {'value': 'javascript', 'label': 'JavaScript'}
                ],
                'default': 'python'
            },
            'input_variables': {
                'type': 'array',
                'required': False,
                'label': '输入变量',
                'items': {'type': 'string'}
            },
            'output_variables': {
                'type': 'array',
                'required': False,
                'label': '输出变量',
                'items': {'type': 'string'}
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': '超时(秒)',
                'default': 30,
                'min': 1,
                'max': 300
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        code = config.get('code', '')
        language = config.get('language', 'python')
        input_vars = config.get('input_variables', [])
        output_vars = config.get('output_variables', ['result'])
        timeout = config.get('timeout', 30)

        input_data = {}
        for var in input_vars:
            input_data[var] = context.get(var)

        result = {'output': {}, 'status': 'completed'}

        try:
            if language == 'python':
                local_context = {'input_data': input_data, 'context': context}
                exec(code, {'__builtins__': __builtins__}, local_context)
                if 'main' in local_context:
                    output = local_context['main'](input_data, context)
                    for var in output_vars:
                        result['output'][var] = output.get(var)
                else:
                    for var in output_vars:
                        if var in local_context:
                            result['output'][var] = local_context[var]
            else:
                result['output']['javascript_not_implemented'] = True
        except Exception as e:
            result['output']['error'] = str(e)
            result['status'] = 'failed'

        return result


@NodeProcessorRegistry.register('tool_calling')
class ToolCallProcessor(BaseNodeProcessor):
    """工具调用处理器 - 调用预定义工具"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'tool_name': {
                'type': 'select',
                'required': True,
                'label': '工具名称',
                'options': [
                    {'value': 'calculator', 'label': '计算器'},
                    {'value': 'date_time', 'label': '日期时间'},
                    {'value': 'url_encoder', 'label': 'URL编码'},
                    {'value': 'hash', 'label': '哈希计算'},
                    {'value': 'random', 'label': '随机数'},
                    {'value': 'json_parser', 'label': 'JSON解析'},
                    {'value': 'text_splitter', 'label': '文本分割'}
                ]
            },
            'parameters': {
                'type': 'object',
                'required': False,
                'label': '工具参数',
                'description': '根据选择的工具动态显示参数'
            },
            'input_data': {
                'type': 'object',
                'required': False,
                'label': '输入数据',
                'description': '传递给工具的输入数据'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': '输出变量名',
                'default': 'tool_result'
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = config.get('tool_name', '')
        params = config.get('parameters', {})
        input_data = config.get('input_data', {})
        output_var = config.get('output_variable', 'tool_result')

        result = {}
        errors = []

        try:
            if tool_name == 'calculator':
                expression = params.get('expression', '0')
                result = {'result': eval(expression)}

            elif tool_name == 'date_time':
                format_str = params.get('format', '%Y-%m-%d %H:%M:%S')
                result = {'datetime': datetime.now().strftime(format_str)}

            elif tool_name == 'url_encoder':
                text = params.get('text', '')
                result = {'encoded': quote(text), 'decoded': text}

            elif tool_name == 'hash':
                text = params.get('text', '')
                algorithm = params.get('algorithm', 'md5')
                if algorithm == 'md5':
                    result = {'hash': hashlib.md5(text.encode()).hexdigest()}
                elif algorithm == 'sha256':
                    result = {'hash': hashlib.sha256(text.encode()).hexdigest()}

            elif tool_name == 'random':
                min_val = int(params.get('min', 0))
                max_val = int(params.get('max', 100))
                result = {'random': uuid.uuid4().int % (max_val - min_val + 1) + min_val}

            elif tool_name == 'json_parser':
                json_str = params.get('json_string', '{}')
                result = {'parsed': json.loads(json_str)}

            elif tool_name == 'text_splitter':
                text = params.get('text', '')
                separator = params.get('separator', '\n')
                max_length = int(params.get('max_length', 100))
                chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
                result = {'chunks': chunks, 'count': len(chunks)}

        except Exception as e:
            errors.append(f"工具执行失败: {str(e)}")
            result = {}

        return {
            output_var: result,
            'tool': tool_name,
            'errors': errors,
            'status': 'completed' if not errors else 'failed'
        }


@NodeProcessorRegistry.register('switch')
class SwitchProcessor(BaseNodeProcessor):
    """多条件分支处理器 - 多条件判断"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'condition_variable': {
                'type': 'string',
                'required': True,
                'label': '条件变量',
                'placeholder': '输入要判断的变量名'
            },
            'condition_type': {
                'type': 'select',
                'required': False,
                'label': '条件类型',
                'options': [
                    {'value': 'value_match', 'label': '值匹配'},
                    {'value': 'regex', 'label': '正则表达式'},
                    {'value': 'range', 'label': '范围判断'},
                    {'value': 'expression', 'label': '表达式'}
                ],
                'default': 'value_match'
            },
            'cases': {
                'type': 'array',
                'required': True,
                'label': '分支配置',
                'items': {
                    'type': 'object',
                    'properties': {
                        'value': {'type': 'string', 'label': '匹配值'},
                        'condition': {'type': 'string', 'label': '条件表达式'},
                        'output_key': {'type': 'string', 'label': '输出键'}
                    }
                }
            },
            'default_case': {
                'type': 'object',
                'required': False,
                'label': '默认分支',
                'properties': {
                    'output_key': {'type': 'string', 'label': '输出键'}
                }
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': '输出变量名',
                'default': 'switch_result'
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        var_name = config.get('condition_variable', '')
        condition_type = config.get('condition_type', 'value_match')
        cases = config.get('cases', [])
        default_case = config.get('default_case', {})
        output_var = config.get('output_variable', 'switch_result')

        value = context.get(var_name)
        matched_case = None

        for case in cases:
            case_value = case.get('value', '')
            condition = case.get('condition', '')

            if condition_type == 'value_match':
                if str(value) == str(case_value):
                    matched_case = case
                    break
            elif condition_type == 'regex':
                if re.match(case_value, str(value)):
                    matched_case = case
                    break
            elif condition_type == 'expression':
                expr_context = {var_name: value, 'context': context}
                try:
                    if eval(condition, expr_context):
                        matched_case = case
                        break
                except:
                    pass

        result = {
            'matched': matched_case is not None,
            'value': value,
            'condition_type': condition_type
        }

        if matched_case:
            result['output_key'] = matched_case.get('output_key', '')
        elif default_case:
            result['output_key'] = default_case.get('output_key', '')

        return {
            output_var: result,
            'status': 'completed'
        }


@NodeProcessorRegistry.register('webhook')
class WebhookProcessor(BaseNodeProcessor):
    """Webhook处理器 - 接收和发送Webhook请求"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'webhook_type': {
                'type': 'select',
                'required': True,
                'label': 'Webhook类型',
                'options': [
                    {'value': 'receive', 'label': '接收Webhook'},
                    {'value': 'send', 'label': '发送Webhook'}
                ],
                'default': 'send'
            },
            'webhook_url': {
                'type': 'string',
                'required': False,
                'label': 'Webhook URL',
                'placeholder': 'https://example.com/webhook',
                'depends_on': {'webhook_type': ['send']}
            },
            'method': {
                'type': 'select',
                'required': False,
                'label': '请求方法',
                'options': [
                    {'value': 'POST', 'label': 'POST'},
                    {'value': 'GET', 'label': 'GET'},
                    {'value': 'PUT', 'label': 'PUT'}
                ],
                'default': 'POST',
                'depends_on': {'webhook_type': ['send']}
            },
            'headers': {
                'type': 'object',
                'required': False,
                'label': '请求头'
            },
            'payload': {
                'type': 'object',
                'required': False,
                'label': '请求载荷',
                'depends_on': {'webhook_type': ['send']}
            },
            'response_variable': {
                'type': 'string',
                'required': False,
                'label': '响应变量名',
                'default': 'webhook_response'
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        webhook_type = config.get('webhook_type', 'send')
        output_var = config.get('response_variable', 'webhook_response')

        result = {'webhook_type': webhook_type, 'status': 'completed'}

        if webhook_type == 'send':
            url = config.get('webhook_url', '')
            method = config.get('method', 'POST')
            headers = config.get('headers', {})
            payload = config.get('payload', {})

            if not url:
                return {output_var: {'error': 'URL required'}, 'status': 'failed'}

            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(method, url, json=payload, headers=headers) as resp:
                        result['status_code'] = resp.status
                        result['response'] = await resp.text()
            except Exception as e:
                result['error'] = str(e)
                result['status'] = 'failed'
        else:
            result['message'] = 'Webhook接收配置已设置'

        return {output_var: result}


@NodeProcessorRegistry.register('qa_interaction')
class QAInteractionProcessor(BaseNodeProcessor):
    """问答交互处理器 - 用户输入问答"""

    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)

    def _get_config_schema(self) -> Dict[str, Any]:
        return {
            'question': {
                'type': 'string',
                'required': True,
                'label': '问题',
                'placeholder': '请输入要询问的问题'
            },
            'question_type': {
                'type': 'select',
                'required': False,
                'label': '问题类型',
                'options': [
                    {'value': 'text', 'label': '文本输入'},
                    {'value': 'choice', 'label': '选择题'},
                    {'value': 'confirm', 'label': '确认/取消'}
                ],
                'default': 'text'
            },
            'options': {
                'type': 'array',
                'required': False,
                'label': '选项列表',
                'depends_on': {'question_type': ['choice']},
                'items': {'type': 'string'}
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': '超时(秒)',
                'default': 300
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': '输出变量名',
                'default': 'user_answer'
            }
        }

    async def execute_async(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        question = config.get('question', '')
        question_type = config.get('question_type', 'text')
        options = config.get('options', [])
        timeout = config.get('timeout', 300)
        output_var = config.get('output_variable', 'user_answer')

        result = {
            'question': question,
            'question_type': question_type,
            'options': options if question_type == 'choice' else [],
            'status': 'pending_user_input'
        }

        return {
            output_var: result,
            'waiting_for_input': True,
            'status': 'waiting'
        }
