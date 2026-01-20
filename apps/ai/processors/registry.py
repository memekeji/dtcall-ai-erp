"""
统一处理器注册表

此模块提供统一的处理器注册和管理机制，解决重复类定义问题。

设计原则：
1. 每个节点类型只保留一个处理器类
2. 处理器按功能模块分组
3. 提供清晰的继承关系

处理器模块分布：
- basic_processor.py: 基础节点（start、end等）
- ai_model_processor.py: AI模型节点
- condition_processor.py: 条件判断节点
- data_processor.py: 数据处理节点
- api_processor.py: API调用节点
- file_processor.py: 文件操作节点
- notification_processor.py: 通知节点
- enhanced_processors.py: 增强功能节点
- complete_nodes.py: 完整功能节点
- complete_node_processors.py: 完整功能节点（增强版）

注意：后加载的模块会覆盖先注册的同名节点类型
"""

from .base_processor import BaseNodeProcessor, NodeProcessorRegistry

__all__ = ['BaseNodeProcessor', 'NodeProcessorRegistry']
