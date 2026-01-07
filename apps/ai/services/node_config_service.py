"""
节点配置服务 - 处理节点配置表单生成和验证
"""

import logging
from typing import Dict, List, Any, Optional
from apps.ai.processors import (
    get_processor_for_node_type, 
    generate_config_form, 
    validate_node_config,
    get_all_node_types
)
from apps.ai.models import WorkflowNodeType

logger = logging.getLogger(__name__)


class NodeConfigService:
    """节点配置服务类"""
    
    def __init__(self):
        self.processors_available = True
    
    def get_node_config_form(self, node_type_code: str, current_config: Dict = None) -> Dict:
        """
        获取节点配置表单
        
        Args:
            node_type_code: 节点类型代码
            current_config: 当前配置（用于编辑时预填充）
            
        Returns:
            dict: 配置表单定义
        """
        try:
            # 使用处理器系统生成配置表单
            form = generate_config_form(node_type_code, current_config)
            if form:
                return form
            
            # 如果处理器系统不可用，使用默认配置
            return self._get_default_config_form(node_type_code, current_config)
            
        except Exception as e:
            logger.error(f"获取节点配置表单失败: {str(e)}")
            return self._get_default_config_form(node_type_code, current_config)
    
    def validate_node_configuration(self, node_type_code: str, config: Dict) -> Dict:
        """
        验证节点配置
        
        Args:
            node_type_code: 节点类型代码
            config: 配置数据
            
        Returns:
            dict: 验证结果
        """
        try:
            # 使用处理器系统验证配置
            result = validate_node_config(node_type_code, config)
            if result:
                return result
            
            # 如果处理器系统不可用，使用默认验证
            return self._validate_default_config(node_type_code, config)
            
        except Exception as e:
            logger.error(f"验证节点配置失败: {str(e)}")
            return {
                'valid': False,
                'errors': [f'验证失败: {str(e)}']
            }
    
    def get_all_supported_node_types(self) -> List[Dict]:
        """
        获取所有支持的节点类型及其配置信息
        
        Returns:
            list: 节点类型列表
        """
        try:
            # 使用处理器系统获取节点类型
            node_types = get_all_node_types()
            if node_types:
                return node_types
            
            # 如果处理器系统不可用，从数据库获取
            return self._get_node_types_from_db()
            
        except Exception as e:
            logger.error(f"获取节点类型失败: {str(e)}")
            return self._get_node_types_from_db()
    
    def get_node_type_info(self, node_type_code: str) -> Optional[Dict]:
        """
        获取节点类型详细信息
        
        Args:
            node_type_code: 节点类型代码
            
        Returns:
            dict: 节点类型信息
        """
        try:
            processor = get_processor_for_node_type(node_type_code)
            if processor:
                return {
                    'code': node_type_code,
                    'name': processor.get_display_name(),
                    'description': processor.get_description(),
                    'category': processor.get_category(),
                    'config_form': processor.generate_config_form(),
                    'supported': True
                }
            
            # 从数据库获取
            return self._get_node_type_from_db(node_type_code)
            
        except Exception as e:
            logger.error(f"获取节点类型信息失败: {str(e)}")
            return self._get_node_type_from_db(node_type_code)
    
    def _get_default_config_form(self, node_type_code: str, current_config: Dict = None) -> Dict:
        """
        获取默认配置表单（回退方案）
        
        Args:
            node_type_code: 节点类型代码
            current_config: 当前配置
            
        Returns:
            dict: 默认配置表单
        """
        # 基本配置字段
        base_fields = {
            'name': {
                'type': 'text',
                'label': '节点名称',
                'required': True,
                'default': f'{node_type_code}节点'
            },
            'description': {
                'type': 'textarea',
                'label': '节点描述',
                'required': False,
                'default': ''
            }
        }
        
        # 根据节点类型添加特定字段
        type_specific_fields = self._get_type_specific_fields(node_type_code)
        
        return {
            'fields': {**base_fields, **type_specific_fields},
            'layout': self._get_form_layout(node_type_code)
        }
    
    def _get_type_specific_fields(self, node_type_code: str) -> Dict:
        """获取类型特定的配置字段"""
        fields = {}
        
        if node_type_code == 'ai_model':
            fields = {
                'model_name': {
                    'type': 'select',
                    'label': 'AI模型',
                    'required': True,
                    'options': [
                        {'value': 'gpt-3.5-turbo', 'label': 'GPT-3.5 Turbo'},
                        {'value': 'gpt-4', 'label': 'GPT-4'},
                        {'value': 'claude-3', 'label': 'Claude 3'}
                    ],
                    'default': 'gpt-3.5-turbo'
                },
                'prompt': {
                    'type': 'textarea',
                    'label': '提示词',
                    'required': True,
                    'default': ''
                }
            }
        elif node_type_code == 'condition':
            fields = {
                'condition_type': {
                    'type': 'select',
                    'label': '条件类型',
                    'required': True,
                    'options': [
                        {'value': 'if_else', 'label': '如果-否则'},
                        {'value': 'switch', 'label': '多条件分支'}
                    ],
                    'default': 'if_else'
                },
                'condition_variable': {
                    'type': 'text',
                    'label': '条件变量',
                    'required': True,
                    'default': ''
                }
            }
        elif node_type_code == 'api_call':
            fields = {
                'api_url': {
                    'type': 'text',
                    'label': 'API地址',
                    'required': True,
                    'default': ''
                },
                'method': {
                    'type': 'select',
                    'label': '请求方法',
                    'required': True,
                    'options': [
                        {'value': 'GET', 'label': 'GET'},
                        {'value': 'POST', 'label': 'POST'},
                        {'value': 'PUT', 'label': 'PUT'},
                        {'value': 'DELETE', 'label': 'DELETE'}
                    ],
                    'default': 'GET'
                }
            }
        
        return fields
    
    def _get_form_layout(self, node_type_code: str) -> List[Dict]:
        """获取表单布局"""
        base_layout = [
            {
                'type': 'section',
                'title': '基本信息',
                'fields': ['name', 'description']
            }
        ]
        
        if node_type_code == 'ai_model':
            base_layout.append({
                'type': 'section',
                'title': 'AI模型配置',
                'fields': ['model_name', 'prompt']
            })
        elif node_type_code == 'condition':
            base_layout.append({
                'type': 'section',
                'title': '条件配置',
                'fields': ['condition_type', 'condition_variable']
            })
        elif node_type_code == 'api_call':
            base_layout.append({
                'type': 'section',
                'title': 'API配置',
                'fields': ['api_url', 'method']
            })
        
        return base_layout
    
    def _validate_default_config(self, node_type_code: str, config: Dict) -> Dict:
        """默认配置验证"""
        errors = []
        
        # 基本验证
        if not config.get('name'):
            errors.append('节点名称不能为空')
        
        # 类型特定验证
        if node_type_code == 'ai_model':
            if not config.get('prompt'):
                errors.append('提示词不能为空')
        elif node_type_code == 'condition':
            if not config.get('condition_variable'):
                errors.append('条件变量不能为空')
        elif node_type_code == 'api_call':
            if not config.get('api_url'):
                errors.append('API地址不能为空')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _get_node_types_from_db(self) -> List[Dict]:
        """从数据库获取节点类型"""
        try:
            node_types = WorkflowNodeType.objects.all()
            return [
                {
                    'code': nt.code,
                    'name': nt.name,
                    'description': nt.description,
                    'category': nt.category,
                    'supported': True
                }
                for nt in node_types
            ]
        except Exception as e:
            logger.error(f"从数据库获取节点类型失败: {str(e)}")
            return []
    
    def _get_node_type_from_db(self, node_type_code: str) -> Optional[Dict]:
        """从数据库获取单个节点类型"""
        try:
            node_type = WorkflowNodeType.objects.get(code=node_type_code)
            return {
                'code': node_type.code,
                'name': node_type.name,
                'description': node_type.description,
                'category': node_type.category,
                'supported': True
            }
        except WorkflowNodeType.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"从数据库获取节点类型失败: {str(e)}")
            return None