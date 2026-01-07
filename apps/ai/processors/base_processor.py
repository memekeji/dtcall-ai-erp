"""
节点处理器基类
定义节点配置与执行逻辑的联动机制
"""

import abc
import json
from typing import Dict, Any, List, Optional
from django.core.exceptions import ValidationError


class BaseNodeProcessor(abc.ABC):
    """节点处理器基类"""
    
    def __init__(self, node_type_code: str):
        self.node_type_code = node_type_code
        self.config_schema = self._get_config_schema()
    
    @abc.abstractmethod
    def _get_config_schema(self) -> Dict[str, Any]:
        """获取节点配置模式"""
        pass
    
    @abc.abstractmethod
    def execute(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点逻辑"""
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """验证配置参数"""
        errors = []
        
        # 检查必填字段
        for field_name, field_schema in self.config_schema.items():
            if field_schema.get('required', False) and field_name not in config:
                errors.append(f"必填字段 '{field_name}' 缺失")
            
            # 检查字段类型
            if field_name in config:
                expected_type = field_schema.get('type')
                if expected_type and not self._validate_field_type(config[field_name], expected_type):
                    errors.append(f"字段 '{field_name}' 类型错误，期望 {expected_type}")
        
        # 检查未知字段
        for field_name in config:
            if field_name not in self.config_schema:
                errors.append(f"未知字段 '{field_name}'")
        
        return errors
    
    def _validate_field_type(self, value: Any, expected_type: str) -> bool:
        """验证字段类型"""
        type_mapping = {
            'string': str,
            'number': (int, float),
            'boolean': bool,
            'object': dict,
            'array': list
        }
        
        if expected_type in type_mapping:
            expected_type_class = type_mapping[expected_type]
            return isinstance(value, expected_type_class)
        
        return True
    
    def generate_form_config(self) -> Dict[str, Any]:
        """生成前端表单配置"""
        form_config = {
            'fields': [],
            'layout': 'vertical',
            'submitText': '保存配置',
            'resetText': '重置',
            'groups': [],
            'version': '1.0'
        }
        
        # 按功能分组配置字段
        groups = {
            'basic': {'name': '基本配置', 'fields': []},
            'input': {'name': '输入配置', 'fields': []},
            'advanced': {'name': '高级配置', 'fields': []}
        }
        
        for field_name, field_schema in self.config_schema.items():
            field_config = self._generate_field_config(field_name, field_schema)
            
            # 根据字段名或类型自动分组
            group_key = 'basic'
            if 'input' in field_name.lower() or 'config' in field_name.lower():
                group_key = 'input'
            elif 'advanced' in field_name.lower() or 'schedule' in field_name.lower() or 'event' in field_name.lower() or 'api' in field_name.lower():
                group_key = 'advanced'
            
            field_config['group'] = group_key
            groups[group_key]['fields'].append(field_config)
            form_config['fields'].append(field_config)
        
        # 添加分组信息
        for group_key, group_info in groups.items():
            if group_info['fields']:
                form_config['groups'].append({
                    'key': group_key,
                    'name': group_info['name'],
                    'fieldKeys': [field['name'] for field in group_info['fields']]
                })
        
        return form_config
    
    def _generate_field_config(self, field_name: str, field_schema: Dict[str, Any], parent_name: str = '') -> Dict[str, Any]:
        """生成单个字段的表单配置，支持递归处理嵌套对象"""
        field_type = field_schema.get('type', 'string')
        
        # 检查是否有options，如果有则为select类型
        if 'options' in field_schema:
            mapped_type = 'select'
        else:
            mapped_type = self._map_field_type(field_type)
        
        field_config = {
            'name': field_name,
            'label': field_schema.get('label', field_name),
            'type': mapped_type,
            'required': field_schema.get('required', False),
            'placeholder': field_schema.get('placeholder', ''),
            'help': field_schema.get('description', ''),
            'default': field_schema.get('default'),
            'visible': True,
            'disabled': field_schema.get('disabled', False),
            'readOnly': field_schema.get('readOnly', False),
            'order': field_schema.get('order', 0),
            'tooltip': field_schema.get('tooltip', ''),
            'validation': field_schema.get('validation', {}),
            'dependencies': field_schema.get('depends_on', {})
        }
        
        # 添加字段特定配置
        if 'options' in field_schema:
            field_config['options'] = field_schema['options']
        
        if 'min' in field_schema:
            field_config['min'] = field_schema['min']
            field_config['validation']['min'] = field_schema['min']
        
        if 'max' in field_schema:
            field_config['max'] = field_schema['max']
            field_config['validation']['max'] = field_schema['max']
        
        if 'pattern' in field_schema:
            field_config['validation']['pattern'] = field_schema['pattern']
        
        if 'multiline' in field_schema:
            field_config['multiline'] = field_schema['multiline']
            field_config['rows'] = field_schema.get('rows', 3)
        
        # 递归处理嵌套对象
        if field_type == 'object' and 'properties' in field_schema:
            field_config['properties'] = {}
            for prop_name, prop_schema in field_schema['properties'].items():
                field_config['properties'][prop_name] = self._generate_field_config(prop_name, prop_schema, field_name)
        
        # 处理数组类型
        if field_type == 'array' and 'items' in field_schema:
            field_config['items'] = field_schema['items']
            field_config['minItems'] = field_schema.get('minItems', 0)
            field_config['maxItems'] = field_schema.get('maxItems', 100)
        
        return field_config
    
    def _map_field_type(self, schema_type: str) -> str:
        """映射字段类型到前端表单类型"""
        mapping = {
            'string': 'text',
            'number': 'number',
            'boolean': 'checkbox',
            'object': 'object',
            'array': 'array'
        }
        return mapping.get(schema_type, 'text')
    
    def get_execution_dependencies(self) -> List[str]:
        """获取执行依赖的上下文变量"""
        dependencies = []
        
        for field_schema in self.config_schema.values():
            if 'depends_on' in field_schema:
                dependencies.extend(field_schema['depends_on'])
        
        return list(set(dependencies))


class NodeProcessorRegistry:
    """节点处理器注册表"""
    
    _processors = {}
    
    @classmethod
    def register(cls, node_type_code: str):
        """注册节点处理器装饰器"""
        def decorator(processor_class):
            cls._processors[node_type_code] = processor_class
            return processor_class
        return decorator
    
    @classmethod
    def get_processor(cls, node_type_code: str) -> Optional[BaseNodeProcessor]:
        """获取节点处理器实例"""
        if node_type_code in cls._processors:
            return cls._processors[node_type_code](node_type_code)
        return None
    
    @classmethod
    def get_all_processors(cls) -> Dict[str, BaseNodeProcessor]:
        """获取所有处理器实例"""
        return {code: cls.get_processor(code) for code in cls._processors}
    
    @classmethod
    def get_available_node_types(cls) -> List[Dict[str, Any]]:
        """获取可用的节点类型信息"""
        node_types = []
        
        for node_type_code, processor_class in cls._processors.items():
            processor = cls.get_processor(node_type_code)
            if processor:
                node_types.append({
                    'code': node_type_code,
                    'name': processor_class.get_display_name(),
                    'icon': processor_class.get_icon(),
                    'description': processor_class.get_description(),
                    'config_schema': processor.config_schema,
                    'form_config': processor.generate_form_config()
                })
        
        return node_types