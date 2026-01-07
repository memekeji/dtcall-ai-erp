"""
API调用节点处理器
"""

import requests
import json
from .base_processor import BaseNodeProcessor, NodeProcessorRegistry


@NodeProcessorRegistry.register('api_call')
class APICallProcessor(BaseNodeProcessor):
    """API调用节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "API调用节点"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-link"
    
    @classmethod
    def get_description(cls):
        return "调用外部API接口"
    
    def _get_config_schema(self) -> dict:
        """获取API调用节点的配置模式"""
        return {
            'url': {
                'type': 'string',
                'required': True,
                'label': 'API地址',
                'placeholder': 'https://api.example.com/endpoint',
                'description': '要调用的API完整URL地址'
            },
            'method': {
                'type': 'string',
                'required': True,
                'label': '请求方法',
                'default': 'GET',
                'options': [
                    {'value': 'GET', 'label': 'GET'},
                    {'value': 'POST', 'label': 'POST'},
                    {'value': 'PUT', 'label': 'PUT'},
                    {'value': 'DELETE', 'label': 'DELETE'},
                    {'value': 'PATCH', 'label': 'PATCH'}
                ],
                'description': 'HTTP请求方法'
            },
            'headers': {
                'type': 'object',
                'required': False,
                'label': '请求头',
                'default': {},
                'description': 'HTTP请求头信息，JSON格式'
            },
            'params': {
                'type': 'object',
                'required': False,
                'label': '查询参数',
                'default': {},
                'description': 'URL查询参数，GET请求使用'
            },
            'body': {
                'type': 'object',
                'required': False,
                'label': '请求体',
                'default': {},
                'description': '请求体数据，POST/PUT请求使用'
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': '超时时间',
                'default': 30,
                'min': 1,
                'max': 300,
                'description': '请求超时时间（秒）'
            },
            'retry_count': {
                'type': 'number',
                'required': False,
                'label': '重试次数',
                'default': 3,
                'min': 0,
                'max': 10,
                'description': '请求失败时的重试次数'
            },
            'response_format': {
                'type': 'string',
                'required': False,
                'label': '响应格式',
                'default': 'json',
                'options': [
                    {'value': 'json', 'label': 'JSON'},
                    {'value': 'text', 'label': '文本'},
                    {'value': 'xml', 'label': 'XML'},
                    {'value': 'binary', 'label': '二进制'}
                ],
                'description': '期望的响应数据格式'
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行API调用节点逻辑"""
        url = config.get('url', '')
        method = config.get('method', 'GET').upper()
        headers = config.get('headers', {})
        params = config.get('params', {})
        body = config.get('body', {})
        timeout = config.get('timeout', 30)
        retry_count = config.get('retry_count', 3)
        response_format = config.get('response_format', 'json')
        
        # 替换URL和参数中的变量
        url = self._replace_variables(url, context)
        headers = self._replace_variables_in_dict(headers, context)
        params = self._replace_variables_in_dict(params, context)
        body = self._replace_variables_in_dict(body, context)
        
        # 准备请求参数
        request_kwargs = {
            'timeout': timeout,
            'headers': headers
        }
        
        if method == 'GET':
            request_kwargs['params'] = params
        else:
            if body:
                request_kwargs['json'] = body
        
        # 执行API调用（支持重试）
        response_data = None
        status_code = None
        error_message = None
        
        for attempt in range(retry_count + 1):
            try:
                response = requests.request(method, url, **request_kwargs)
                status_code = response.status_code
                
                if response.status_code == 200:
                    # 根据响应格式处理数据
                    if response_format == 'json':
                        response_data = response.json()
                    elif response_format == 'text':
                        response_data = response.text
                    elif response_format == 'xml':
                        response_data = response.text
                    else:
                        response_data = response.content
                    break
                else:
                    error_message = f"HTTP {response.status_code}: {response.text}"
                    
            except requests.exceptions.Timeout:
                error_message = "请求超时"
            except requests.exceptions.ConnectionError:
                error_message = "连接错误"
            except requests.exceptions.RequestException as e:
                error_message = f"请求异常: {str(e)}"
            except Exception as e:
                error_message = f"未知错误: {str(e)}"
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < retry_count and error_message:
                import time
                time.sleep(1)  # 简单的重试间隔
        
        return {
            'success': response_data is not None,
            'status_code': status_code,
            'response_data': response_data,
            'error_message': error_message,
            'url_used': url,
            'method_used': method
        }
    
    def _replace_variables(self, text: str, context: dict) -> str:
        """替换文本中的变量占位符"""
        if not isinstance(text, str):
            return text
        
        for key, value in context.items():
            placeholder = f'{{{{{key}}}}}'
            text = text.replace(placeholder, str(value))
        
        return text
    
    def _replace_variables_in_dict(self, data: dict, context: dict) -> dict:
        """替换字典中的变量占位符"""
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self._replace_variables(value, context)
            elif isinstance(value, dict):
                result[key] = self._replace_variables_in_dict(value, context)
            elif isinstance(value, list):
                result[key] = [self._replace_variables_in_dict(item, context) if isinstance(item, dict) 
                              else self._replace_variables(item, context) if isinstance(item, str) 
                              else item for item in value]
            else:
                result[key] = value
        
        return result


@NodeProcessorRegistry.register('data_input')
class DataInputProcessor(BaseNodeProcessor):
    """数据输入节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "数据输入节点"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-import"
    
    @classmethod
    def get_description(cls):
        return "从外部数据源获取数据"
    
    def _get_config_schema(self) -> dict:
        """获取数据输入节点的配置模式"""
        return {
            'data_source': {
                'type': 'string',
                'required': True,
                'label': '数据源',
                'options': [
                    {'value': 'file', 'label': '文件'},
                    {'value': 'database', 'label': '数据库'},
                    {'value': 'api', 'label': 'API接口'},
                    {'value': 'manual', 'label': '手动输入'}
                ],
                'description': '选择数据来源类型'
            },
            'file_path': {
                'type': 'string',
                'required': False,
                'label': '文件路径',
                'description': '数据文件路径（当数据源为文件时）',
                'depends_on': {'data_source': 'file'}
            },
            'database_connection': {
                'type': 'string',
                'required': False,
                'label': '数据库连接',
                'description': '数据库连接配置（当数据源为数据库时）',
                'depends_on': {'data_source': 'database'}
            },
            'api_endpoint': {
                'type': 'string',
                'required': False,
                'label': 'API端点',
                'description': 'API接口地址（当数据源为API时）',
                'depends_on': {'data_source': 'api'}
            },
            'input_data': {
                'type': 'object',
                'required': False,
                'label': '输入数据',
                'description': '手动输入的数据（当数据源为手动输入时）',
                'depends_on': {'data_source': 'manual'}
            },
            'data_format': {
                'type': 'string',
                'required': False,
                'label': '数据格式',
                'default': 'json',
                'options': [
                    {'value': 'json', 'label': 'JSON'},
                    {'value': 'csv', 'label': 'CSV'},
                    {'value': 'xml', 'label': 'XML'},
                    {'value': 'text', 'label': '文本'}
                ],
                'description': '输入数据的格式'
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行数据输入节点逻辑"""
        data_source = config.get('data_source', 'manual')
        data_format = config.get('data_format', 'json')
        
        input_data = {}
        
        if data_source == 'manual':
            input_data = config.get('input_data', {})
        elif data_source == 'file':
            input_data = self._read_from_file(config, context)
        elif data_source == 'api':
            # 使用API调用处理器获取数据
            api_config = {
                'url': config.get('api_endpoint', ''),
                'method': 'GET',
                'response_format': data_format
            }
            api_processor = APICallProcessor('api_call')
            api_result = api_processor.execute(api_config, context)
            
            if api_result['success']:
                input_data = api_result['response_data']
            else:
                raise Exception(f"API调用失败: {api_result['error_message']}")
        
        return {
            'input_data': input_data,
            'data_source': data_source,
            'data_format': data_format
        }
    
    def _read_from_file(self, config: dict, context: dict) -> dict:
        """从文件读取数据"""
        file_path = config.get('file_path', '')
        data_format = config.get('data_format', 'json')
        
        if not file_path:
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                if data_format == 'json':
                    return json.loads(content)
                elif data_format == 'csv':
                    import csv
                    from io import StringIO
                    csv_reader = csv.DictReader(StringIO(content))
                    return list(csv_reader)
                else:
                    return {'content': content}
                    
        except Exception as e:
            raise Exception(f"文件读取失败: {str(e)}")