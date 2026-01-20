"""
统一的节点处理器模块

此模块整合了所有重复的处理器类，确保只有一个实现版本。
处理器的加载顺序由 apps/ai/processors/__init__.py 控制。

已整合的处理器：
1. DataInputProcessor -> 统一使用 data_processor.py 版本
2. CodeExecutionProcessor -> 统一使用 enhanced_processors.py 版本
3. LoopProcessor -> 统一使用 enhanced_processors.py 版本（增强版）
4. IteratorProcessor -> 保留 complete_node_processors.py 版本
5. VariableAssignProcessor -> 保留 complete_node_processors.py 版本
6. ParameterAggregatorProcessor -> 保留 complete_node_processors.py 版本
7. TemplateProcessor -> 保留 complete_node_processors.py 版本
8. ToolCallProcessor -> 保留 complete_node_processors.py 版本
9. ScheduledTaskProcessor -> 保留 complete_node_processors.py 版本
10. WorkflowTriggerProcessor -> 保留 complete_node_processors.py 版本
11. ConversationHistoryProcessor -> 保留 complete_node_processors.py 版本

注意事项：
- 不要在此文件中添加新的处理器类
- 新处理器应添加到对应的功能模块中
- 保持处理器模块职责单一
"""
