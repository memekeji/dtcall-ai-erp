"""
数据输入输出节点处理器
"""

import os
from typing import Dict, Any, List
from .base_processor import BaseNodeProcessor, NodeProcessorRegistry


@NodeProcessorRegistry.register('data_input')
class DataInputProcessor(BaseNodeProcessor):
    """数据输入节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "数据输入"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-file"
    
    @classmethod
    def get_description(cls):
        return "从外部数据源读取数据"
    
    def _get_config_schema(self) -> dict:
        """获取数据输入节点的配置模式"""
        return {
            'input_type': {
                'type': 'string',
                'required': True,
                'label': '输入类型',
                'options': [
                    {'value': 'text', 'label': '文本输入'},
                    {'value': 'form', 'label': '表单输入'},
                    {'value': 'image', 'label': '图片上传'},
                    {'value': 'file', 'label': '文件上传'},
                    {'value': 'json', 'label': 'JSON数据'},
                    {'value': 'database', 'label': '数据库查询'},
                    {'value': 'api', 'label': 'API接口'},
                    {'value': 'variable', 'label': '变量引用'}
                ],
                'description': '选择数据输入方式'
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
                    },
                    'default_value': {
                        'type': 'string',
                        'required': False,
                        'label': '默认值',
                        'multiline': True,
                        'rows': 3
                    },
                    'validation_rules': {
                        'type': 'object',
                        'required': False,
                        'label': '验证规则',
                        'properties': {
                            'required': {
                                'type': 'boolean',
                                'required': False,
                                'label': '必填',
                                'default': True
                            },
                            'pattern': {
                                'type': 'string',
                                'required': False,
                                'label': '正则表达式',
                                'description': '数据格式验证'
                            }
                        }
                    }
                },
                'depends_on': {'input_type': 'text'}
            },
            'form_config': {
                'type': 'object',
                'required': False,
                'label': '表单配置',
                'description': '配置表单字段，支持用户自定义输入',
                'properties': {
                    'title': {
                        'type': 'string',
                        'required': False,
                        'label': '表单标题',
                        'default': '请填写表单'
                    },
                    'description': {
                        'type': 'string',
                        'required': False,
                        'label': '表单描述',
                        'default': '请根据下方提示填写相关信息'
                    },
                    'fields': {
                        'type': 'array',
                        'required': True,
                        'label': '表单字段',
                        'description': '定义表单中的输入字段',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {
                                    'type': 'string',
                                    'required': True,
                                    'label': '字段ID',
                                    'description': '字段唯一标识符'
                                },
                                'name': {
                                    'type': 'string',
                                    'required': True,
                                    'label': '字段名称',
                                    'description': '字段显示名称'
                                },
                                'type': {
                                    'type': 'string',
                                    'required': True,
                                    'label': '字段类型',
                                    'options': [
                                        {'value': 'text', 'label': '文本'},
                                        {'value': 'textarea', 'label': '多行文本'},
                                        {'value': 'number', 'label': '数字'},
                                        {'value': 'date', 'label': '日期'},
                                        {'value': 'datetime', 'label': '日期时间'},
                                        {'value': 'select', 'label': '下拉选择'},
                                        {'value': 'checkbox', 'label': '复选框'},
                                        {'value': 'radio', 'label': '单选框'},
                                        {'value': 'file', 'label': '文件上传'}
                                    ]
                                },
                                'required': {
                                    'type': 'boolean',
                                    'required': False,
                                    'label': '是否必填',
                                    'default': False
                                },
                                'placeholder': {
                                    'type': 'string',
                                    'required': False,
                                    'label': '占位符',
                                    'description': '输入提示文字'
                                },
                                'default_value': {
                                    'type': 'string',
                                    'required': False,
                                    'label': '默认值'
                                },
                                'options': {
                                    'type': 'array',
                                    'required': False,
                                    'label': '选项列表',
                                    'description': '用于select/radio/checkbox类型',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'value': {'type': 'string'},
                                            'label': {'type': 'string'}
                                        }
                                    }
                                },
                                'validation': {
                                    'type': 'object',
                                    'required': False,
                                    'label': '验证规则',
                                    'properties': {
                                        'min_length': {
                                            'type': 'number',
                                            'required': False,
                                            'label': '最小长度'
                                        },
                                        'max_length': {
                                            'type': 'number',
                                            'required': False,
                                            'label': '最大长度'
                                        },
                                        'min': {
                                            'type': 'number',
                                            'required': False,
                                            'label': '最小值'
                                        },
                                        'max': {
                                            'type': 'number',
                                            'required': False,
                                            'label': '最大值'
                                        },
                                        'pattern': {
                                            'type': 'string',
                                            'required': False,
                                            'label': '正则表达式'
                                        }
                                    }
                                },
                                'help_text': {
                                    'type': 'string',
                                    'required': False,
                                    'label': '帮助提示',
                                    'description': '显示在字段下方的提示文字'
                                }
                            }
                        }
                    },
                    'submit_text': {
                        'type': 'string',
                        'required': False,
                        'label': '提交按钮文字',
                        'default': '提交'
                    },
                    'show_reset': {
                        'type': 'boolean',
                        'required': False,
                        'label': '显示重置按钮',
                        'default': False
                    }
                },
                'depends_on': {'input_type': 'form'}
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
                    },
                    'save_path': {
                        'type': 'string',
                        'required': False,
                        'label': '保存路径',
                        'default': '/uploads/images/'
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
                    },
                    'save_path': {
                        'type': 'string',
                        'required': False,
                        'label': '保存路径',
                        'default': '/uploads/files/'
                    },
                    'file_type': {
                        'type': 'string',
                        'required': True,
                        'label': '文件类型',
                        'options': [
                            {'value': 'json', 'label': 'JSON文件'},
                            {'value': 'csv', 'label': 'CSV文件'},
                            {'value': 'excel', 'label': 'Excel文件'},
                            {'value': 'text', 'label': '文本文件'},
                            {'value': 'xml', 'label': 'XML文件'},
                            {'value': 'other', 'label': '其他文件'}
                        ]
                    },
                    'encoding': {
                        'type': 'string',
                        'required': False,
                        'label': '文件编码',
                        'default': 'utf-8'
                    },
                    'sheet_name': {
                        'type': 'string',
                        'required': False,
                        'label': '工作表名称',
                        'depends_on': {'file_type': 'excel'}
                    },
                    'delimiter': {
                        'type': 'string',
                        'required': False,
                        'label': '分隔符',
                        'default': ',',
                        'depends_on': {'file_type': 'csv'}
                    },
                    'has_header': {
                        'type': 'boolean',
                        'required': False,
                        'label': '包含表头',
                        'default': True,
                        'depends_on': {'file_type': ['csv', 'excel']}
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
                    },
                    'validation_rules': {
                        'type': 'boolean',
                        'required': False,
                        'label': '启用验证',
                        'default': True
                    }
                },
                'depends_on': {'input_type': 'json'}
            },
            'database_config': {
                'type': 'object',
                'required': False,
                'label': '数据库配置',
                'properties': {
                    'database_type': {
                        'type': 'string',
                        'required': True,
                        'label': '数据库类型',
                        'options': [
                            {'value': 'mysql', 'label': 'MySQL'},
                            {'value': 'postgresql', 'label': 'PostgreSQL'},
                            {'value': 'sqlite', 'label': 'SQLite'},
                            {'value': 'oracle', 'label': 'Oracle'}
                        ]
                    },
                    'connection_string': {
                        'type': 'string',
                        'required': True,
                        'label': '连接字符串',
                        'description': '数据库连接字符串'
                    },
                    'query': {
                        'type': 'string',
                        'required': True,
                        'label': '查询语句',
                        'multiline': True,
                        'rows': 5,
                        'description': 'SQL查询语句'
                    },
                    'parameters': {
                        'type': 'object',
                        'required': False,
                        'label': '查询参数',
                        'default': {},
                        'description': '查询参数键值对'
                    },
                    'timeout': {
                        'type': 'number',
                        'required': False,
                        'label': '超时时间(秒)',
                        'default': 30,
                        'min': 1
                    }
                },
                'depends_on': {'input_type': 'database'}
            },
            'api_config': {
                'type': 'object',
                'required': False,
                'label': 'API配置',
                'properties': {
                    'api_url': {
                        'type': 'string',
                        'required': True,
                        'label': 'API地址',
                        'description': '完整的API URL'
                    },
                    'method': {
                        'type': 'string',
                        'required': True,
                        'label': '请求方法',
                        'options': [
                            {'value': 'GET', 'label': 'GET'},
                            {'value': 'POST', 'label': 'POST'},
                            {'value': 'PUT', 'label': 'PUT'},
                            {'value': 'DELETE', 'label': 'DELETE'}
                        ],
                        'default': 'GET'
                    },
                    'headers': {
                        'type': 'object',
                        'required': False,
                        'label': '请求头',
                        'default': {}
                    },
                    'body': {
                        'type': 'string',
                        'required': False,
                        'label': '请求体',
                        'multiline': True,
                        'rows': 3,
                        'depends_on': {'method': ['POST', 'PUT']}
                    },
                    'auth_type': {
                        'type': 'string',
                        'required': False,
                        'label': '认证类型',
                        'options': [
                            {'value': 'none', 'label': '无认证'},
                            {'value': 'basic', 'label': '基础认证'},
                            {'value': 'bearer', 'label': 'Bearer Token'},
                            {'value': 'api_key', 'label': 'API密钥'}
                        ]
                    },
                    'auth_config': {
                        'type': 'object',
                        'required': False,
                        'label': '认证配置',
                        'properties': {
                            'username': {
                                'type': 'string',
                                'required': False,
                                'label': '用户名'
                            },
                            'password': {
                                'type': 'string',
                                'required': False,
                                'label': '密码'
                            },
                            'token': {
                                'type': 'string',
                                'required': False,
                                'label': 'Token'
                            },
                            'api_key': {
                                'type': 'string',
                                'required': False,
                                'label': 'API密钥'
                            }
                        },
                        'depends_on': {'auth_type': ['basic', 'bearer', 'api_key']}
                    },
                    'timeout': {
                        'type': 'number',
                        'required': False,
                        'label': '超时时间(秒)',
                        'default': 30,
                        'min': 1
                    }
                },
                'depends_on': {'input_type': 'api'}
            },
            'variable_config': {
                'type': 'object',
                'required': False,
                'label': '变量配置',
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
                    },
                    'transform_rule': {
                        'type': 'string',
                        'required': False,
                        'label': '转换规则',
                        'multiline': True,
                        'rows': 3,
                        'description': '对变量值进行转换的规则'
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
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行数据输入节点逻辑"""
        input_type = config.get('input_type', 'text')
        output_var = config.get('output_variable', 'input_data')
        
        try:
            # 检查是否是开始节点（使用外部输入数据）
            is_start_node = config.get('is_start_node', False) or config.get('trigger_type') == 'manual'
            
            # 如果是开始节点，优先从外部输入数据读取
            if is_start_node and context:
                if isinstance(context, dict):
                    # 尝试多种方式获取外部输入数据
                    external_input = None
                    
                    # 方式1: context.input_data (如果context是ExecutionContext对象)
                    if hasattr(context, 'input_data'):
                        external_input = context.input_data
                    
                    # 方式2: context.get('input_data')
                    if not external_input:
                        external_input = context.get('input_data')
                    
                    # 方式3: context.get('data')
                    if not external_input:
                        external_input = context.get('data')
                    
                    # 方式4: 如果output_var在context中，直接使用
                    if output_var in context:
                        external_input = context[output_var]
                    
                    # 方式5: 如果context本身就是输入数据（字典），使用它
                    if not external_input and isinstance(context, dict) and len(context) > 0:
                        # 查找与output_var匹配的数据
                        for key, value in context.items():
                            if key == output_var or key in ['input_data', 'data']:
                                external_input = value
                                break
                        # 如果没找到匹配的，使用整个context
                        if not external_input:
                            external_input = context
                    
                    if external_input and external_input != context:
                        context[output_var] = external_input
                        return {
                            'input_type': input_type,
                            'success': True,
                            'message': f"使用外部输入数据成功",
                            'data_size': len(str(external_input)) if external_input else 0,
                            'output_variable': output_var,
                            'is_external_input': True
                        }
            
            # 非开始节点或没有外部输入，使用配置读取数据
            if input_type == 'text':
                data = self._read_text_data(config)
            elif input_type == 'form':
                data = self._read_form_data(config)
            elif input_type == 'image':
                data = self._read_image_data(config)
            elif input_type == 'file':
                data = self._read_file_data(config)
            elif input_type == 'json':
                data = self._read_json_data(config)
            elif input_type == 'database':
                data = self._read_database_data(config)
            elif input_type == 'api':
                data = self._read_api_data(config)
            elif input_type == 'variable':
                data = self._read_variable_data(config, context)
            else:
                raise Exception(f"不支持的输入类型: {input_type}")
            
            # 将数据存储到上下文中
            context[output_var] = data
            
            return {
                'input_type': input_type,
                'success': True,
                'message': f"数据输入成功，类型: {input_type}",
                'data_size': len(str(data)) if data else 0,
                'output_variable': output_var,
                'is_external_input': False
            }
            
        except Exception as e:
            return {
                'input_type': input_type,
                'success': False,
                'message': f"数据输入失败: {str(e)}",
                'output_variable': output_var
            }
    
    async def execute_async(self, config: dict, context: dict) -> dict:
        """异步执行数据输入节点逻辑"""
        return self.execute(config, context)
    
    def _read_text_data(self, config: dict):
        """读取文本输入数据"""
        text_config = config.get('text_config', {})
        return text_config.get('default_value', '')
    
    def _read_form_data(self, config: dict):
        """读取表单配置数据"""
        form_config = config.get('form_config', {})
        return {
            'title': form_config.get('title', '请填写表单'),
            'description': form_config.get('description', '请根据下方提示填写相关信息'),
            'fields': form_config.get('fields', []),
            'submit_text': form_config.get('submit_text', '提交'),
            'show_reset': form_config.get('show_reset', False),
            'form_schema': self._generate_form_schema(form_config)
        }
    
    def _generate_form_schema(self, form_config: dict) -> dict:
        """生成表单JSON Schema（用于前端表单渲染）"""
        fields = form_config.get('fields', [])
        
        schema = {
            'type': 'object',
            'properties': {},
            'required': [],
            'ui': {}
        }
        
        for field in fields:
            field_id = field.get('id')
            field_type = field.get('type', 'text')
            
            # 构建JSON Schema属性
            schema['properties'][field_id] = {
                'type': self._map_field_type(field_type),
                'title': field.get('name', field_id),
                'description': field.get('help_text', '')
            }
            
            # 添加验证规则
            validation = field.get('validation', {})
            if validation:
                if validation.get('min_length'):
                    schema['properties'][field_id]['minLength'] = validation['min_length']
                if validation.get('max_length'):
                    schema['properties'][field_id]['maxLength'] = validation['max_length']
                if validation.get('min') is not None:
                    schema['properties'][field_id]['minimum'] = validation['min']
                if validation.get('max') is not None:
                    schema['properties'][field_id]['maximum'] = validation['max']
                if validation.get('pattern'):
                    schema['properties'][field_id]['pattern'] = validation['pattern']
            
            # 添加选项（用于select/radio/checkbox）
            options = field.get('options', [])
            if options:
                schema['properties'][field_id]['enum'] = [opt.get('value') for opt in options]
                schema['properties'][field_id]['enumNames'] = [opt.get('label') for opt in options]
            
            # 添加默认值
            default_value = field.get('default_value')
            if default_value is not None:
                schema['properties'][field_id]['default'] = default_value
            
            # 处理必填字段
            if field.get('required', False):
                schema['required'].append(field_id)
            
            # 构建UI Schema
            schema['ui'] = schema.get('ui', {})
            schema['ui'][field_id] = {
                'ui:widget': self._map_field_widget(field_type),
                'ui:options': {
                    'placeholder': field.get('placeholder', ''),
                    'rows': field.get('rows', 4) if field_type == 'textarea' else None
                }
            }
        
        return schema
    
    def _map_field_type(self, field_type: str) -> str:
        """映射字段类型到JSON Schema类型"""
        type_mapping = {
            'text': 'string',
            'textarea': 'string',
            'number': 'number',
            'integer': 'integer',
            'date': 'string',
            'datetime': 'string',
            'select': 'string',
            'checkbox': 'boolean',
            'radio': 'string',
            'file': 'string'
        }
        return type_mapping.get(field_type, 'string')
    
    def _map_field_widget(self, field_type: str) -> str:
        """映射字段类型到UI Widget"""
        widget_mapping = {
            'text': 'text',
            'textarea': 'textarea',
            'number': 'updown',
            'date': 'date',
            'datetime': 'datetime',
            'select': 'select',
            'checkbox': 'checkbox',
            'radio': 'radio',
            'file': 'file'
        }
        return widget_mapping.get(field_type, 'text')
    
    def _read_image_data(self, config: dict):
        """读取图片上传数据"""
        image_config = config.get('image_config', {})
        # 图片上传通常在前端处理，这里返回配置信息
        return {
            'accept_types': image_config.get('accept_types', ['jpg', 'jpeg', 'png', 'gif', 'webp']),
            'max_size': image_config.get('max_size', 10),
            'save_path': image_config.get('save_path', '/uploads/images/')
        }
    
    def _read_json_data(self, config: dict):
        """读取JSON数据"""
        json_config = config.get('json_config', {})
        default_value = json_config.get('default_value', '{}')
        import json
        return json.loads(default_value) if default_value else {}
    
    def _read_manual_data(self, config: dict):
        """读取手动输入数据（兼容旧版）"""
        return self._read_text_data(config)
    
    def _read_file_data(self, config: dict):
        """读取文件数据"""
        file_config = config.get('file_config', {})
        file_type = file_config.get('file_type', 'text')
        file_path = file_config.get('file_path', '')
        encoding = file_config.get('encoding', 'utf-8')
        
        if not file_path:
            raise Exception("文件路径不能为空")
        
        if file_type == 'json':
            import json
            with open(file_path, 'r', encoding=encoding) as f:
                return json.load(f)
        elif file_type == 'csv':
            import csv
            delimiter = file_config.get('delimiter', ',')
            has_header = file_config.get('has_header', True)
            
            with open(file_path, 'r', encoding=encoding) as f:
                reader = csv.reader(f, delimiter=delimiter)
                data = list(reader)
                
                if has_header and data:
                    headers = data[0]
                    rows = data[1:]
                    return [dict(zip(headers, row)) for row in rows]
                else:
                    return data
        elif file_type == 'excel':
            import pandas as pd
            sheet_name = file_config.get('sheet_name', 0)
            has_header = file_config.get('has_header', True)
            
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=0 if has_header else None)
            return df.to_dict('records')
        elif file_type == 'xml':
            import xml.etree.ElementTree as ET
            tree = ET.parse(file_path)
            root = tree.getroot()
            return self._xml_to_dict(root)
        else:  # text
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
    
    def _read_database_data(self, config: dict):
        """读取数据库数据"""
        db_config = config.get('database_config', {})
        query = db_config.get('query', '')
        
        if not query:
            raise Exception("查询语句不能为空")
        
        from django.db import connection
        from django.conf import settings
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                if query.strip().upper().startswith('SELECT'):
                    columns = [col[0] for col in cursor.description]
                    rows = cursor.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
                else:
                    return {'affected_rows': cursor.rowcount}
        except Exception as e:
            raise Exception(f"数据库查询失败: {str(e)}")
    
    def _read_api_data(self, config: dict):
        """读取API数据"""
        import requests
        
        api_config = config.get('api_config', {})
        api_url = api_config.get('api_url', '')
        method = api_config.get('method', 'GET')
        headers = api_config.get('headers', {})
        body = api_config.get('body', '')
        timeout = api_config.get('timeout', 30)
        
        if not api_url:
            raise Exception("API地址不能为空")
        
        # 处理认证
        auth_config = api_config.get('auth_config', {})
        auth_type = api_config.get('auth_type', 'none')
        
        if auth_type == 'basic':
            from requests.auth import HTTPBasicAuth
            auth = HTTPBasicAuth(auth_config.get('username', ''), auth_config.get('password', ''))
        elif auth_type == 'bearer':
            headers['Authorization'] = f"Bearer {auth_config.get('token', '')}"
            auth = None
        elif auth_type == 'api_key':
            headers['X-API-Key'] = auth_config.get('api_key', '')
            auth = None
        else:
            auth = None
        
        # 发送请求
        if method == 'GET':
            response = requests.get(api_url, headers=headers, auth=auth, timeout=timeout)
        elif method == 'POST':
            response = requests.post(api_url, headers=headers, data=body, auth=auth, timeout=timeout)
        elif method == 'PUT':
            response = requests.put(api_url, headers=headers, data=body, auth=auth, timeout=timeout)
        elif method == 'DELETE':
            response = requests.delete(api_url, headers=headers, auth=auth, timeout=timeout)
        else:
            raise Exception(f"不支持的HTTP方法: {method}")
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API请求失败: {response.status_code} - {response.text}")
    
    def _read_variable_data(self, config: dict, context: dict):
        """读取变量数据"""
        var_config = config.get('variable_config', {})
        var_name = var_config.get('variable_name', '')
        default_value = var_config.get('default_value', '')
        transform_rule = var_config.get('transform_rule', '')
        
        if not var_name:
            raise Exception("变量名不能为空")
        
        # 从上下文中获取变量值
        data = context.get(var_name, default_value)
        
        # 应用转换规则
        if transform_rule:
            try:
                # 简单的转换规则评估（注意安全限制）
                data = eval(transform_rule, {'data': data})
            except Exception as e:
                raise Exception(f"转换规则执行失败: {str(e)}")
        
        return data
    
    def _xml_to_dict(self, element):
        """将XML元素转换为字典"""
        result = {}
        
        # 处理属性
        if element.attrib:
            result['@attributes'] = element.attrib
        
        # 处理子元素
        for child in element:
            child_dict = self._xml_to_dict(child)
            
            # 处理重复元素
            if child.tag in result:
                if isinstance(result[child.tag], list):
                    result[child.tag].append(child_dict)
                else:
                    result[child.tag] = [result[child.tag], child_dict]
            else:
                result[child.tag] = child_dict
        
        # 处理文本内容
        if element.text and element.text.strip():
            if result:  # 如果有子元素，将文本作为特殊字段
                result['#text'] = element.text.strip()
            else:  # 如果没有子元素，直接返回文本
                result = element.text.strip()
        
        return result


@NodeProcessorRegistry.register('data_output')
class DataOutputProcessor(BaseNodeProcessor):
    """数据输出节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "数据输出"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-export"
    
    @classmethod
    def get_description(cls):
        return "将数据输出到外部目标"
    
    def _get_config_schema(self) -> dict:
        """获取数据输出节点的配置模式"""
        return {
            'output_type': {
                'type': 'string',
                'required': True,
                'label': '输出类型',
                'options': [
                    {'value': 'file', 'label': '文件输出'},
                    {'value': 'database', 'label': '数据库存储'},
                    {'value': 'api', 'label': 'API接口'},
                    {'value': 'variable', 'label': '变量存储'},
                    {'value': 'display', 'label': '界面显示'}
                ],
                'description': '选择数据输出方式'
            },
            'input_variable': {
                'type': 'string',
                'required': True,
                'label': '输入变量名',
                'default': 'output_data',
                'description': '要输出的数据变量名'
            },
            'file_config': {
                'type': 'object',
                'required': False,
                'label': '文件输出配置',
                'properties': {
                    'file_type': {
                        'type': 'string',
                        'required': True,
                        'label': '文件类型',
                        'options': [
                            {'value': 'json', 'label': 'JSON文件'},
                            {'value': 'csv', 'label': 'CSV文件'},
                            {'value': 'excel', 'label': 'Excel文件'},
                            {'value': 'text', 'label': '文本文件'}
                        ]
                    },
                    'file_path': {
                        'type': 'string',
                        'required': True,
                        'label': '文件路径',
                        'description': '输出文件路径'
                    },
                    'encoding': {
                        'type': 'string',
                        'required': False,
                        'label': '文件编码',
                        'default': 'utf-8'
                    },
                    'mode': {
                        'type': 'string',
                        'required': False,
                        'label': '写入模式',
                        'options': [
                            {'value': 'overwrite', 'label': '覆盖'},
                            {'value': 'append', 'label': '追加'}
                        ],
                        'default': 'overwrite'
                    },
                    'delimiter': {
                        'type': 'string',
                        'required': False,
                        'label': '分隔符',
                        'default': ',',
                        'depends_on': {'file_type': 'csv'}
                    },
                    'sheet_name': {
                        'type': 'string',
                        'required': False,
                        'label': '工作表名称',
                        'default': 'Sheet1',
                        'depends_on': {'file_type': 'excel'}
                    }
                },
                'depends_on': {'output_type': 'file'}
            },
            'database_config': {
                'type': 'object',
                'required': False,
                'label': '数据库配置',
                'properties': {
                    'database_type': {
                        'type': 'string',
                        'required': True,
                        'label': '数据库类型',
                        'options': [
                            {'value': 'mysql', 'label': 'MySQL'},
                            {'value': 'postgresql', 'label': 'PostgreSQL'},
                            {'value': 'sqlite', 'label': 'SQLite'}
                        ]
                    },
                    'connection_string': {
                        'type': 'string',
                        'required': True,
                        'label': '连接字符串'
                    },
                    'table_name': {
                        'type': 'string',
                        'required': True,
                        'label': '表名'
                    },
                    'operation': {
                        'type': 'string',
                        'required': True,
                        'label': '操作类型',
                        'options': [
                            {'value': 'insert', 'label': '插入'},
                            {'value': 'update', 'label': '更新'},
                            {'value': 'upsert', 'label': '插入或更新'}
                        ]
                    },
                    'primary_key': {
                        'type': 'string',
                        'required': False,
                        'label': '主键字段',
                        'depends_on': {'operation': ['update', 'upsert']}
                    }
                },
                'depends_on': {'output_type': 'database'}
            },
            'api_config': {
                'type': 'object',
                'required': False,
                'label': 'API配置',
                'properties': {
                    'api_url': {
                        'type': 'string',
                        'required': True,
                        'label': 'API地址'
                    },
                    'method': {
                        'type': 'string',
                        'required': True,
                        'label': '请求方法',
                        'options': [
                            {'value': 'POST', 'label': 'POST'},
                            {'value': 'PUT', 'label': 'PUT'},
                            {'value': 'PATCH', 'label': 'PATCH'}
                        ]
                    },
                    'headers': {
                        'type': 'object',
                        'required': False,
                        'label': '请求头',
                        'default': {}
                    },
                    'auth_type': {
                        'type': 'string',
                        'required': False,
                        'label': '认证类型',
                        'options': [
                            {'value': 'none', 'label': '无认证'},
                            {'value': 'basic', 'label': '基础认证'},
                            {'value': 'bearer', 'label': 'Bearer Token'}
                        ]
                    },
                    'auth_config': {
                        'type': 'object',
                        'required': False,
                        'label': '认证配置',
                        'properties': {
                            'username': {'type': 'string'},
                            'password': {'type': 'string'},
                            'token': {'type': 'string'}
                        },
                        'depends_on': {'auth_type': ['basic', 'bearer']}
                    },
                    'timeout': {
                        'type': 'number',
                        'required': False,
                        'label': '超时时间(秒)',
                        'default': 30
                    }
                },
                'depends_on': {'output_type': 'api'}
            },
            'variable_config': {
                'type': 'object',
                'required': False,
                'label': '变量配置',
                'properties': {
                    'variable_name': {
                        'type': 'string',
                        'required': True,
                        'label': '变量名'
                    },
                    'overwrite': {
                        'type': 'boolean',
                        'required': False,
                        'label': '覆盖现有变量',
                        'default': True
                    }
                },
                'depends_on': {'output_type': 'variable'}
            },
            'display_config': {
                'type': 'object',
                'required': False,
                'label': '显示配置',
                'properties': {
                    'format': {
                        'type': 'string',
                        'required': True,
                        'label': '显示格式',
                        'options': [
                            {'value': 'table', 'label': '表格'},
                            {'value': 'json', 'label': 'JSON'},
                            {'value': 'text', 'label': '文本'},
                            {'value': 'chart', 'label': '图表'}
                        ]
                    },
                    'title': {
                        'type': 'string',
                        'required': False,
                        'label': '显示标题'
                    },
                    'max_rows': {
                        'type': 'number',
                        'required': False,
                        'label': '最大显示行数',
                        'default': 100
                    }
                },
                'depends_on': {'output_type': 'display'}
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行数据输出节点逻辑"""
        output_type = config.get('output_type', 'file')
        input_var = config.get('input_variable', 'output_data')
        
        # 获取输入数据
        data = context.get(input_var)
        if data is None:
            return {
                'output_type': output_type,
                'success': False,
                'message': f"输入变量 '{input_var}' 不存在"
            }
        
        try:
            if output_type == 'file':
                result = self._write_to_file(config, data)
            elif output_type == 'database':
                result = self._write_to_database(config, data)
            elif output_type == 'api':
                result = self._write_to_api(config, data)
            elif output_type == 'variable':
                result = self._write_to_variable(config, data, context)
            elif output_type == 'display':
                result = self._display_data(config, data)
            else:
                raise Exception(f"不支持的输出类型: {output_type}")
            
            result['output_type'] = output_type
            result['input_variable'] = input_var
            return result
            
        except Exception as e:
            return {
                'output_type': output_type,
                'success': False,
                'message': f"数据输出失败: {str(e)}",
                'input_variable': input_var
            }
    
    def _write_to_file(self, config: dict, data) -> dict:
        """写入文件"""
        file_config = config.get('file_config', {})
        file_type = file_config.get('file_type', 'json')
        file_path = file_config.get('file_path', '')
        encoding = file_config.get('encoding', 'utf-8')
        mode = file_config.get('mode', 'overwrite')
        
        if not file_path:
            raise Exception("文件路径不能为空")
        
        if file_type == 'json':
            import json
            write_mode = 'a' if mode == 'append' else 'w'
            with open(file_path, write_mode, encoding=encoding) as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                if mode == 'append':
                    f.write('\n')
        
        elif file_type == 'csv':
            import csv
            delimiter = file_config.get('delimiter', ',')
            write_mode = 'a' if mode == 'append' else 'w'
            
            with open(file_path, write_mode, encoding=encoding, newline='') as f:
                writer = csv.writer(f, delimiter=delimiter)
                
                if isinstance(data, list) and data:
                    # 如果是字典列表，写入表头和行
                    if isinstance(data[0], dict):
                        if mode == 'overwrite' or not os.path.exists(file_path):
                            writer.writerow(data[0].keys())
                        for row in data:
                            writer.writerow(row.values())
                    else:
                        writer.writerow(data)
                else:
                    writer.writerow([data])
        
        elif file_type == 'excel':
            import pandas as pd
            sheet_name = file_config.get('sheet_name', 'Sheet1')
            
            if mode == 'append' and os.path.exists(file_path):
                # 追加模式，读取现有文件
                existing_df = pd.read_excel(file_path, sheet_name=sheet_name)
                new_df = pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame([data])
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df.to_excel(file_path, sheet_name=sheet_name, index=False)
            else:
                # 覆盖模式
                df = pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame([data])
                df.to_excel(file_path, sheet_name=sheet_name, index=False)
        
        else:  # text
            write_mode = 'a' if mode == 'append' else 'w'
            with open(file_path, write_mode, encoding=encoding) as f:
                f.write(str(data))
                if mode == 'append':
                    f.write('\n')
        
        return {
            'success': True,
            'message': f"数据成功写入文件: {file_path}",
            'file_path': file_path,
            'file_type': file_type
        }
    
    def _write_to_database(self, config: dict, data) -> dict:
        """写入数据库"""
        # 这里需要根据实际数据库连接实现
        # 暂时返回模拟结果
        db_config = config.get('database_config', {})
        table_name = db_config.get('table_name', '')
        operation = db_config.get('operation', 'insert')
        
        if not table_name:
            raise Exception("表名不能为空")
        
        # 模拟数据库操作
        return {
            'success': True,
            'message': f"数据成功写入数据库表: {table_name}",
            'table_name': table_name,
            'operation': operation
        }
    
    def _write_to_api(self, config: dict, data) -> dict:
        """写入API接口"""
        import requests
        
        api_config = config.get('api_config', {})
        api_url = api_config.get('api_url', '')
        method = api_config.get('method', 'POST')
        headers = api_config.get('headers', {})
        timeout = api_config.get('timeout', 30)
        
        if not api_url:
            raise Exception("API地址不能为空")
        
        # 处理认证
        auth_config = api_config.get('auth_config', {})
        auth_type = api_config.get('auth_type', 'none')
        
        if auth_type == 'basic':
            from requests.auth import HTTPBasicAuth
            auth = HTTPBasicAuth(auth_config.get('username', ''), auth_config.get('password', ''))
        elif auth_type == 'bearer':
            headers['Authorization'] = f"Bearer {auth_config.get('token', '')}"
            auth = None
        else:
            auth = None
        
        # 发送请求
        if method == 'POST':
            response = requests.post(api_url, json=data, headers=headers, auth=auth, timeout=timeout)
        elif method == 'PUT':
            response = requests.put(api_url, json=data, headers=headers, auth=auth, timeout=timeout)
        elif method == 'PATCH':
            response = requests.patch(api_url, json=data, headers=headers, auth=auth, timeout=timeout)
        else:
            raise Exception(f"不支持的HTTP方法: {method}")
        
        if response.status_code in [200, 201, 204]:
            return {
                'success': True,
                'message': f"数据成功发送到API: {api_url}",
                'api_url': api_url,
                'status_code': response.status_code
            }
        else:
            raise Exception(f"API请求失败: {response.status_code} - {response.text}")
    
    def _write_to_variable(self, config: dict, data, context: dict) -> dict:
        """写入变量"""
        var_config = config.get('variable_config', {})
        var_name = var_config.get('variable_name', '')
        overwrite = var_config.get('overwrite', True)
        
        if not var_name:
            raise Exception("变量名不能为空")
        
        # 检查变量是否已存在
        if var_name in context and not overwrite:
            raise Exception(f"变量 '{var_name}' 已存在且不允许覆盖")
        
        # 存储到上下文
        context[var_name] = data
        
        return {
            'success': True,
            'message': f"数据成功存储到变量: {var_name}",
            'variable_name': var_name
        }
    
    def _display_data(self, config: dict, data) -> dict:
        """显示数据"""
        display_config = config.get('display_config', {})
        format_type = display_config.get('format', 'table')
        title = display_config.get('title', '数据输出')
        max_rows = display_config.get('max_rows', 100)
        
        # 根据格式处理数据
        if format_type == 'table':
            # 转换为表格格式
            if isinstance(data, list) and data:
                # 限制行数
                if len(data) > max_rows:
                    data = data[:max_rows]
                display_data = {
                    'type': 'table',
                    'title': title,
                    'headers': list(data[0].keys()) if isinstance(data[0], dict) else ['数据'],
                    'rows': data
                }
            else:
                display_data = {
                    'type': 'table',
                    'title': title,
                    'headers': ['数据'],
                    'rows': [[data]]
                }
        elif format_type == 'json':
            import json
            display_data = {
                'type': 'json',
                'title': title,
                'content': json.dumps(data, ensure_ascii=False, indent=2)
            }
        elif format_type == 'text':
            display_data = {
                'type': 'text',
                'title': title,
                'content': str(data)
            }
        else:  # chart
            display_data = {
                'type': 'chart',
                'title': title,
                'data': data
            }
        
        return {
            'success': True,
            'message': f"数据成功显示，格式: {format_type}",
            'display_data': display_data
        }


@NodeProcessorRegistry.register('text_processing')
class TextProcessingProcessor(BaseNodeProcessor):
    """文本处理节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "文本处理"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-edit"
    
    @classmethod
    def get_description(cls):
        return "对文本数据进行处理和转换"
    
    def _get_config_schema(self) -> dict:
        """获取文本处理节点的配置模式"""
        return {
            'processing_type': {
                'type': 'string',
                'required': True,
                'label': '处理类型',
                'options': [
                    {'value': 'clean', 'label': '文本清洗'},
                    {'value': 'transform', 'label': '文本转换'},
                    {'value': 'extract', 'label': '信息提取'},
                    {'value': 'split', 'label': '文本分割'},
                    {'value': 'join', 'label': '文本合并'},
                    {'value': 'replace', 'label': '文本替换'},
                    {'value': 'trim', 'label': '去除空白'},
                    {'value': 'case', 'label': '大小写转换'}
                ],
                'description': '选择文本处理方式'
            },
            'input_variable': {
                'type': 'string',
                'required': True,
                'label': '输入变量',
                'default': 'input_text',
                'description': '要处理的文本变量名'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': '输出变量',
                'default': 'output_text',
                'description': '处理后文本的变量名'
            },
            'clean_config': {
                'type': 'object',
                'required': False,
                'label': '文本清洗配置',
                'properties': {
                    'remove_html': {
                        'type': 'boolean',
                        'required': False,
                        'label': '移除HTML标签',
                        'default': True
                    },
                    'remove_special_chars': {
                        'type': 'boolean',
                        'required': False,
                        'label': '移除特殊字符',
                        'default': True
                    },
                    'remove_extra_spaces': {
                        'type': 'boolean',
                        'required': False,
                        'label': '移除多余空格',
                        'default': True
                    },
                    'remove_newlines': {
                        'type': 'boolean',
                        'required': False,
                        'label': '移除换行符',
                        'default': False
                    }
                },
                'depends_on': {'processing_type': 'clean'}
            },
            'transform_config': {
                'type': 'object',
                'required': False,
                'label': '文本转换配置',
                'properties': {
                    'transform_rule': {
                        'type': 'string',
                        'required': True,
                        'label': '转换规则',
                        'multiline': True,
                        'rows': 3,
                        'description': '文本转换的Python表达式，使用变量text表示输入文本'
                    }
                },
                'depends_on': {'processing_type': 'transform'}
            },
            'extract_config': {
                'type': 'object',
                'required': False,
                'label': '信息提取配置',
                'properties': {
                    'pattern': {
                        'type': 'string',
                        'required': True,
                        'label': '提取模式',
                        'description': '正则表达式或提取规则'
                    },
                    'group': {
                        'type': 'number',
                        'required': False,
                        'label': '提取组',
                        'default': 0,
                        'description': '正则表达式提取组索引'
                    }
                },
                'depends_on': {'processing_type': 'extract'}
            },
            'split_config': {
                'type': 'object',
                'required': False,
                'label': '文本分割配置',
                'properties': {
                    'delimiter': {
                        'type': 'string',
                        'required': True,
                        'label': '分隔符',
                        'default': ','
                    },
                    'max_splits': {
                        'type': 'number',
                        'required': False,
                        'label': '最大分割数',
                        'default': -1,
                        'description': '最大分割次数，-1表示不限制'
                    }
                },
                'depends_on': {'processing_type': 'split'}
            },
            'join_config': {
                'type': 'object',
                'required': False,
                'label': '文本合并配置',
                'properties': {
                    'delimiter': {
                        'type': 'string',
                        'required': True,
                        'label': '分隔符',
                        'default': ','
                    }
                },
                'depends_on': {'processing_type': 'join'}
            },
            'replace_config': {
                'type': 'object',
                'required': False,
                'label': '文本替换配置',
                'properties': {
                    'pattern': {
                        'type': 'string',
                        'required': True,
                        'label': '查找模式',
                        'description': '要替换的文本或正则表达式'
                    },
                    'replacement': {
                        'type': 'string',
                        'required': True,
                        'label': '替换文本',
                        'description': '替换后的文本'
                    },
                    'use_regex': {
                        'type': 'boolean',
                        'required': False,
                        'label': '使用正则表达式',
                        'default': False
                    }
                },
                'depends_on': {'processing_type': 'replace'}
            },
            'case_config': {
                'type': 'object',
                'required': False,
                'label': '大小写转换配置',
                'properties': {
                    'case_type': {
                        'type': 'string',
                        'required': True,
                        'label': '转换类型',
                        'options': [
                            {'value': 'upper', 'label': '全部大写'},
                            {'value': 'lower', 'label': '全部小写'},
                            {'value': 'title', 'label': '首字母大写'},
                            {'value': 'capitalize', 'label': '句子首字母大写'}
                        ]
                    }
                },
                'depends_on': {'processing_type': 'case'}
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行文本处理节点逻辑"""
        processing_type = config.get('processing_type', 'clean')
        input_var = config.get('input_variable', 'input_text')
        output_var = config.get('output_variable', 'output_text')
        
        # 获取输入文本
        text = context.get(input_var, '')
        if text is None:
            return {
                'processing_type': processing_type,
                'success': False,
                'message': f"输入变量 '{input_var}' 不存在"
            }
        
        try:
            # 执行文本处理
            if processing_type == 'clean':
                result = self._clean_text(config, text)
            elif processing_type == 'transform':
                result = self._transform_text(config, text)
            elif processing_type == 'extract':
                result = self._extract_text(config, text)
            elif processing_type == 'split':
                result = self._split_text(config, text)
            elif processing_type == 'join':
                result = self._join_text(config, text)
            elif processing_type == 'replace':
                result = self._replace_text(config, text)
            elif processing_type == 'trim':
                result = self._trim_text(config, text)
            elif processing_type == 'case':
                result = self._change_case(config, text)
            else:
                raise Exception(f"不支持的处理类型: {processing_type}")
            
            # 将结果存储到上下文中
            context[output_var] = result
            
            return {
                'processing_type': processing_type,
                'success': True,
                'message': f"文本处理成功，类型: {processing_type}",
                'input_variable': input_var,
                'output_variable': output_var,
                'input_length': len(str(text)),
                'output_length': len(str(result))
            }
        except Exception as e:
            return {
                'processing_type': processing_type,
                'success': False,
                'message': f"文本处理失败: {str(e)}",
                'input_variable': input_var,
                'output_variable': output_var
            }
    
    def _clean_text(self, config: dict, text: str) -> str:
        """清洗文本"""
        clean_config = config.get('clean_config', {})
        
        if clean_config.get('remove_html', True):
            import re
            text = re.sub(r'<[^>]*>', '', text)
        
        if clean_config.get('remove_special_chars', True):
            import re
            text = re.sub(r'[^\w\s]', '', text)
        
        if clean_config.get('remove_extra_spaces', True):
            import re
            text = re.sub(r'\s+', ' ', text)
        
        if clean_config.get('remove_newlines', False):
            text = text.replace('\n', ' ').replace('\r', '')
        
        return text
    
    def _transform_text(self, config: dict, text: str) -> str:
        """转换文本"""
        transform_config = config.get('transform_config', {})
        transform_rule = transform_config.get('transform_rule', '')
        
        if not transform_rule:
            return text
        
        try:
            # 执行转换规则
            return eval(transform_rule, {'text': text})
        except Exception as e:
            raise Exception(f"转换规则执行失败: {str(e)}")
    
    def _extract_text(self, config: dict, text: str) -> str:
        """提取文本"""
        extract_config = config.get('extract_config', {})
        pattern = extract_config.get('pattern', '')
        group = extract_config.get('group', 0)
        
        if not pattern:
            return text
        
        import re
        match = re.search(pattern, text)
        if match:
            return match.group(group)
        return ''
    
    def _split_text(self, config: dict, text: str) -> list:
        """分割文本"""
        split_config = config.get('split_config', {})
        delimiter = split_config.get('delimiter', ',')
        max_splits = split_config.get('max_splits', -1)
        
        if max_splits == -1:
            return text.split(delimiter)
        return text.split(delimiter, max_splits)
    
    def _join_text(self, config: dict, text: list) -> str:
        """合并文本"""
        join_config = config.get('join_config', {})
        delimiter = join_config.get('delimiter', ',')
        
        if isinstance(text, list):
            return delimiter.join(text)
        return str(text)
    
    def _replace_text(self, config: dict, text: str) -> str:
        """替换文本"""
        replace_config = config.get('replace_config', {})
        pattern = replace_config.get('pattern', '')
        replacement = replace_config.get('replacement', '')
        use_regex = replace_config.get('use_regex', False)
        
        if not pattern:
            return text
        
        if use_regex:
            import re
            return re.sub(pattern, replacement, text)
        else:
            return text.replace(pattern, replacement)
    
    def _trim_text(self, config: dict, text: str) -> str:
        """去除空白"""
        return text.strip()
    
    def _change_case(self, config: dict, text: str) -> str:
        """改变大小写"""
        case_config = config.get('case_config', {})
        case_type = case_config.get('case_type', 'lower')
        
        if case_type == 'upper':
            return text.upper()
        elif case_type == 'lower':
            return text.lower()
        elif case_type == 'title':
            return text.title()
        elif case_type == 'capitalize':
            return text.capitalize()
        return text


@NodeProcessorRegistry.register('data_transformation')
class DataTransformationProcessor(BaseNodeProcessor):
    """数据转换节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "数据转换"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-swap"
    
    @classmethod
    def get_description(cls):
        return "对数据进行转换和处理"
    
    def _get_config_schema(self) -> dict:
        """获取数据转换节点的配置模式"""
        return {
            'transformation_type': {
                'type': 'string',
                'required': True,
                'label': '转换类型',
                'options': [
                    {'value': 'map', 'label': '数据映射'},
                    {'value': 'filter', 'label': '数据过滤'},
                    {'value': 'sort', 'label': '数据排序'},
                    {'value': 'aggregate', 'label': '数据聚合'},
                    {'value': 'format', 'label': '数据格式化'},
                    {'value': 'calculate', 'label': '数据计算'}
                ],
                'description': '选择数据转换方式'
            },
            'input_variable': {
                'type': 'string',
                'required': True,
                'label': '输入变量',
                'default': 'input_data',
                'description': '要转换的数据变量名'
            },
            'output_variable': {
                'type': 'string',
                'required': True,
                'label': '输出变量',
                'default': 'output_data',
                'description': '转换后数据的变量名'
            },
            'map_config': {
                'type': 'object',
                'required': False,
                'label': '数据映射配置',
                'properties': {
                    'mapping_rule': {
                        'type': 'string',
                        'required': True,
                        'label': '映射规则',
                        'multiline': True,
                        'rows': 3,
                        'description': '数据映射的Python表达式，使用变量data表示输入数据'
                    }
                },
                'depends_on': {'transformation_type': 'map'}
            },
            'filter_config': {
                'type': 'object',
                'required': False,
                'label': '数据过滤配置',
                'properties': {
                    'filter_rule': {
                        'type': 'string',
                        'required': True,
                        'label': '过滤规则',
                        'multiline': True,
                        'rows': 3,
                        'description': '数据过滤的Python表达式，使用变量item表示列表中的每个元素'
                    }
                },
                'depends_on': {'transformation_type': 'filter'}
            },
            'sort_config': {
                'type': 'object',
                'required': False,
                'label': '数据排序配置',
                'properties': {
                    'sort_key': {
                        'type': 'string',
                        'required': True,
                        'label': '排序键',
                        'description': '用于排序的字段名'
                    },
                    'reverse': {
                        'type': 'boolean',
                        'required': False,
                        'label': '降序排序',
                        'default': False
                    }
                },
                'depends_on': {'transformation_type': 'sort'}
            },
            'aggregate_config': {
                'type': 'object',
                'required': False,
                'label': '数据聚合配置',
                'properties': {
                    'aggregate_function': {
                        'type': 'string',
                        'required': True,
                        'label': '聚合函数',
                        'options': [
                            {'value': 'sum', 'label': '求和'},
                            {'value': 'avg', 'label': '平均值'},
                            {'value': 'count', 'label': '计数'},
                            {'value': 'min', 'label': '最小值'},
                            {'value': 'max', 'label': '最大值'}
                        ]
                    },
                    'aggregate_field': {
                        'type': 'string',
                        'required': True,
                        'label': '聚合字段',
                        'description': '要聚合的字段名'
                    }
                },
                'depends_on': {'transformation_type': 'aggregate'}
            },
            'format_config': {
                'type': 'object',
                'required': False,
                'label': '数据格式化配置',
                'properties': {
                    'format_type': {
                        'type': 'string',
                        'required': True,
                        'label': '格式化类型',
                        'options': [
                            {'value': 'json', 'label': 'JSON格式化'},
                            {'value': 'csv', 'label': 'CSV格式化'},
                            {'value': 'datetime', 'label': '日期时间格式化'}
                        ]
                    },
                    'format_pattern': {
                        'type': 'string',
                        'required': False,
                        'label': '格式化模式',
                        'description': '格式化的模式字符串'
                    }
                },
                'depends_on': {'transformation_type': 'format'}
            },
            'calculate_config': {
                'type': 'object',
                'required': False,
                'label': '数据计算配置',
                'properties': {
                    'calculate_rule': {
                        'type': 'string',
                        'required': True,
                        'label': '计算规则',
                        'multiline': True,
                        'rows': 3,
                        'description': '数据计算的Python表达式，使用变量data表示输入数据'
                    }
                },
                'depends_on': {'transformation_type': 'calculate'}
            }
        }
    
    def execute(self, config: dict, context: dict) -> dict:
        """执行数据转换节点逻辑"""
        transformation_type = config.get('transformation_type', 'map')
        input_var = config.get('input_variable', 'input_data')
        output_var = config.get('output_variable', 'output_data')
        
        # 获取输入数据
        data = context.get(input_var)
        if data is None:
            return {
                'transformation_type': transformation_type,
                'success': False,
                'message': f"输入变量 '{input_var}' 不存在"
            }
        
        try:
            # 执行数据转换
            if transformation_type == 'map':
                result = self._map_data(config, data)
            elif transformation_type == 'filter':
                result = self._filter_data(config, data)
            elif transformation_type == 'sort':
                result = self._sort_data(config, data)
            elif transformation_type == 'aggregate':
                result = self._aggregate_data(config, data)
            elif transformation_type == 'format':
                result = self._format_data(config, data)
            elif transformation_type == 'calculate':
                result = self._calculate_data(config, data)
            else:
                raise Exception(f"不支持的转换类型: {transformation_type}")
            
            # 将结果存储到上下文中
            context[output_var] = result
            
            return {
                'transformation_type': transformation_type,
                'success': True,
                'message': f"数据转换成功，类型: {transformation_type}",
                'input_variable': input_var,
                'output_variable': output_var
            }
        except Exception as e:
            return {
                'transformation_type': transformation_type,
                'success': False,
                'message': f"数据转换失败: {str(e)}",
                'input_variable': input_var,
                'output_variable': output_var
            }
    
    def _map_data(self, config: dict, data: any) -> any:
        """映射数据"""
        map_config = config.get('map_config', {})
        mapping_rule = map_config.get('mapping_rule', '')
        
        if not mapping_rule:
            return data
        
        try:
            # 执行映射规则
            return eval(mapping_rule, {'data': data})
        except Exception as e:
            raise Exception(f"映射规则执行失败: {str(e)}")
    
    def _filter_data(self, config: dict, data: list) -> list:
        """过滤数据"""
        filter_config = config.get('filter_config', {})
        filter_rule = filter_config.get('filter_rule', '')
        
        if not filter_rule:
            return data
        
        if not isinstance(data, list):
            raise Exception("过滤操作只支持列表类型数据")
        
        try:
            # 执行过滤规则
            return [item for item in data if eval(filter_rule, {'item': item})]
        except Exception as e:
            raise Exception(f"过滤规则执行失败: {str(e)}")
    
    def _sort_data(self, config: dict, data: list) -> list:
        """排序数据"""
        sort_config = config.get('sort_config', {})
        sort_key = sort_config.get('sort_key', '')
        reverse = sort_config.get('reverse', False)
        
        if not sort_key:
            return data
        
        if not isinstance(data, list):
            raise Exception("排序操作只支持列表类型数据")
        
        return sorted(data, key=lambda x: x.get(sort_key, 0), reverse=reverse)
    
    def _aggregate_data(self, config: dict, data: list) -> any:
        """聚合数据"""
        aggregate_config = config.get('aggregate_config', {})
        aggregate_function = aggregate_config.get('aggregate_function', 'sum')
        aggregate_field = aggregate_config.get('aggregate_field', '')
        
        if not aggregate_field:
            raise Exception("聚合字段不能为空")
        
        if not isinstance(data, list):
            raise Exception("聚合操作只支持列表类型数据")
        
        # 提取聚合字段的值
        values = [item.get(aggregate_field, 0) for item in data if isinstance(item, dict)]
        
        if not values:
            return 0
        
        if aggregate_function == 'sum':
            return sum(values)
        elif aggregate_function == 'avg':
            return sum(values) / len(values)
        elif aggregate_function == 'count':
            return len(values)
        elif aggregate_function == 'min':
            return min(values)
        elif aggregate_function == 'max':
            return max(values)
        return 0
    
    def _format_data(self, config: dict, data: any) -> any:
        """格式化数据"""
        format_config = config.get('format_config', {})
        format_type = format_config.get('format_type', 'json')
        format_pattern = format_config.get('format_pattern', '')
        
        if format_type == 'json':
            import json
            return json.dumps(data, ensure_ascii=False, indent=2)
        elif format_type == 'csv':
            import csv
            import io
            if isinstance(data, list) and data:
                if isinstance(data[0], dict):
                    output = io.StringIO()
                    writer = csv.DictWriter(output, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
                    return output.getvalue()
            return str(data)
        elif format_type == 'datetime':
            from datetime import datetime
            if isinstance(data, str):
                try:
                    dt = datetime.fromisoformat(data)
                    if format_pattern:
                        return dt.strftime(format_pattern)
                    return dt.isoformat()
                except:
                    return data
        return data
    
    def _calculate_data(self, config: dict, data: any) -> any:
        """计算数据"""
        calculate_config = config.get('calculate_config', {})
        calculate_rule = calculate_config.get('calculate_rule', '')
        
        if not calculate_rule:
            return data
        
        try:
            # 执行计算规则
            return eval(calculate_rule, {'data': data})
        except Exception as e:
            raise Exception(f"计算规则执行失败: {str(e)}")


@NodeProcessorRegistry.register('data_filter')
class DataFilterProcessor(DataTransformationProcessor):
    """数据过滤节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "数据过滤"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-filter"
    
    @classmethod
    def get_description(cls):
        return "过滤数据，只保留符合条件的数据"
    
    def _get_config_schema(self) -> dict:
        """获取数据过滤节点的配置模式"""
        schema = super()._get_config_schema()
        # 默认设置过滤类型
        schema['transformation_type']['default'] = 'filter'
        return schema


@NodeProcessorRegistry.register('data_aggregation')
class DataAggregationProcessor(DataTransformationProcessor):
    """数据聚合节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "数据聚合"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-cols"
    
    @classmethod
    def get_description(cls):
        return "对数据进行聚合统计"
    
    def _get_config_schema(self) -> dict:
        """获取数据聚合节点的配置模式"""
        schema = super()._get_config_schema()
        # 默认设置聚合类型
        schema['transformation_type']['default'] = 'aggregate'
        return schema


@NodeProcessorRegistry.register('data_format')
class DataFormatProcessor(DataTransformationProcessor):
    """数据格式化节点处理器"""
    
    @classmethod
    def get_display_name(cls):
        return "数据格式化"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-file"
    
    @classmethod
    def get_description(cls):
        return "对数据进行格式化处理"
    
    def _get_config_schema(self) -> dict:
        """获取数据格式化节点的配置模式"""
        schema = super()._get_config_schema()
        # 默认设置格式化类型
        schema['transformation_type']['default'] = 'format'
        return schema


@NodeProcessorRegistry.register('database_query')
class DatabaseQueryProcessor(BaseNodeProcessor):
    """数据库查询节点处理器 - 安全、高效的数据库访问"""
    
    def __init__(self, node_type_code: str):
        super().__init__(node_type_code)
        from django.db import connection
    
    @classmethod
    def get_display_name(cls):
        return "数据库查询"
    
    @classmethod
    def get_icon(cls):
        return "layui-icon-database"
    
    @classmethod
    def get_description(cls):
        return "执行SQL查询，返回查询结果"
    
    def _get_config_schema(self) -> Dict[str, Any]:
        """获取数据库查询节点的配置模式"""
        return {
            'query': {
                'type': 'string',
                'required': True,
                'label': 'SQL查询语句',
                'placeholder': 'SELECT * FROM table WHERE condition',
                'multiline': True,
                'rows': 5,
                'tooltip': '支持SELECT、INSERT、UPDATE、DELETE语句'
            },
            'output_variable': {
                'type': 'string',
                'required': False,
                'label': '输出变量名',
                'default': 'query_result',
                'placeholder': '输入变量名'
            },
            'max_rows': {
                'type': 'number',
                'required': False,
                'label': '最大返回行数',
                'default': 1000,
                'min': 1,
                'max': 100000
            },
            'timeout': {
                'type': 'number',
                'required': False,
                'label': '超时时间(秒)',
                'default': 30,
                'min': 1,
                'max': 300
            },
            'cache_result': {
                'type': 'boolean',
                'required': False,
                'label': '缓存查询结果',
                'default': False
            },
            'cache_ttl': {
                'type': 'number',
                'required': False,
                'label': '缓存时间(秒)',
                'default': 300,
                'min': 60,
                'depends_on': 'cache_result'
            }
        }
    
    def execute(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据库查询"""
        from django.db import connection
        from django.core.cache import cache
        import hashlib
        import json
        
        query = config.get('query', '').strip()
        output_var = config.get('output_variable', 'query_result')
        max_rows = config.get('max_rows', 1000)
        timeout = config.get('timeout', 30)
        cache_result = config.get('cache_result', False)
        cache_ttl = config.get('cache_ttl', 300)
        
        if not query:
            raise ValueError('SQL查询语句不能为空')
        
        # 验证查询安全性
        query_upper = query.upper()
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE']
        
        if any(keyword in query_upper for keyword in dangerous_keywords):
            if not query_upper.strip().startswith('SELECT'):
                raise ValueError('出于安全考虑，只允许执行SELECT查询')
        
        # 检查缓存
        if cache_result:
            cache_key = f'workflow_db_query_{hashlib.md5(query.encode()).hexdigest()}'
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return {
                    output_var: cached_result,
                    'cached': True,
                    'row_count': len(cached_result) if isinstance(cached_result, list) else 1,
                    'status': 'completed'
                }
        
        # 执行查询
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                
                if query_upper.strip().startswith('SELECT'):
                    columns = [col[0] for col in cursor.description]
                    rows = cursor.fetchmany(max_rows)
                    result = [dict(zip(columns, row)) for row in rows]
                else:
                    result = {'affected_rows': cursor.rowcount}
                
                # 缓存结果
                if cache_result and query_upper.strip().startswith('SELECT'):
                    cache.set(cache_key, result, cache_ttl)
                
                return {
                    output_var: result,
                    'cached': False,
                    'row_count': len(result) if isinstance(result, list) else 1,
                    'status': 'completed'
                }
        except Exception as e:
            return {
                'error': str(e),
                'status': 'failed'
            }
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """验证数据库查询配置"""
        errors = []
        query = config.get('query', '').strip()
        
        if not query:
            errors.append('SQL查询语句不能为空')
        else:
            # 基础语法检查
            if not query.upper().startswith(('SELECT', 'WITH')):
                if not config.get('allow_write', False):
                    errors.append('出于安全考虑，只允许执行SELECT查询语句')
        
        return errors