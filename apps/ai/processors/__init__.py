"""
节点处理器包初始化文件
"""

import os
import importlib
import logging
from .base_processor import NodeProcessorRegistry

# 配置日志
logger = logging.getLogger(__name__)


def register_all_processors():
    """注册所有节点处理器"""
    # 导入所有处理器模块，确保它们被注册
    processor_modules = [
        'ai_model_processor',
        'condition_processor', 
        'api_processor',
        'file_processor',
        'notification_processor',
        'basic_processor',
        'data_processor'
    ]
    
    for module_name in processor_modules:
        try:
            module = importlib.import_module(f'.{module_name}', __package__)
            logger.info(f"成功注册处理器模块: {module_name}")
        except ImportError as e:
            logger.error(f"导入处理器模块失败 {module_name}: {e}")
    
    return NodeProcessorRegistry.get_all_processors()


def get_processor_for_node_type(node_type: str):
    """根据节点类型获取对应的处理器"""
    return NodeProcessorRegistry.get_processor(node_type)


def get_all_node_types():
    """获取所有支持的节点类型"""
    return NodeProcessorRegistry.get_available_node_types()


def generate_config_form(node_type: str, current_config: dict = None) -> dict:
    """为指定节点类型生成配置表单"""
    processor = get_processor_for_node_type(node_type)
    if processor:
        return processor.generate_form_config()
    return {}


def validate_node_config(node_type: str, config: dict) -> dict:
    """验证节点配置"""
    processor = get_processor_for_node_type(node_type)
    if processor:
        return processor.validate_config(config)
    return {'valid': False, 'errors': ['不支持的节点类型']}


# 自动注册所有处理器
_all_processors = register_all_processors()