import logging
from typing import Dict, Any, Callable, List

logger = logging.getLogger(__name__)

class AIToolRegistry:
    """全站统一的业务工具注册中心 (Function Calling Registry)"""
    _tools: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(cls, name: str, description: str, parameters: dict):
        """
        工具注册装饰器
        :param name: 工具名称
        :param description: 工具描述
        :param parameters: 参数的 JSON Schema
        """
        def decorator(func: Callable):
            cls._tools[name] = {
                "name": name,
                "description": description,
                "parameters": parameters,
                "func": func
            }
            logger.debug(f"成功注册AI工具: {name}")
            return func
        return decorator

    @classmethod
    def get_tool(cls, name: str) -> Dict[str, Any]:
        return cls._tools.get(name)

    @classmethod
    def get_all_tools_schema(cls) -> List[Dict[str, Any]]:
        """获取所有工具的 OpenAI schema 格式"""
        schemas = []
        for name, tool in cls._tools.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
        return schemas

    @classmethod
    def execute_tool(cls, name: str, kwargs: dict) -> Any:
        """执行工具"""
        tool = cls.get_tool(name)
        if not tool:
            raise ValueError(f"未找到名为 {name} 的工具")
        
        try:
            logger.info(f"正在执行AI工具: {name}, 参数: {kwargs}")
            return tool["func"](**kwargs)
        except Exception as e:
            logger.error(f"执行工具 {name} 失败: {str(e)}")
            return f"执行失败: {str(e)}"

# 提供便捷访问
tool_registry = AIToolRegistry()
