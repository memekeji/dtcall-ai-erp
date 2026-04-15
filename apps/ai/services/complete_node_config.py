"""
工作流节点完整配置系统 - 参考Dify和扣子(Coze)最佳实践

提供40+种节点类型的完整配置和处理器实现：
1. 核心功能节点：触发、输入输出、对话历史
2. AI处理节点：生成、分类、提取、意图、情感
3. 流程控制节点：条件分支、循环、并行
4. 数据处理节点：转换、过滤、聚合、格式化
5. 外部集成节点：HTTP、数据库、消息队列
6. 文档媒体节点：文档、音频、图片、文本处理
7. 其他功能节点：代码执行、工具调用、定时任务
"""

import os
import django
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
django.setup()


logger = logging.getLogger(__name__)


# =============================================================================
# 节点配置Schema定义 - 完整的配置项设计
# =============================================================================

@dataclass
class NodeConfig:
    """节点配置定义"""
    name: str
    node_type: str
    description: str
    category: str
    config_fields: Dict[str, Dict] = field(default_factory=dict)
    input_schema: Dict = field(default_factory=dict)
    output_schema: Dict = field(default_factory=dict)
    error_handlers: Dict = field(default_factory=dict)
    examples: List[Dict] = field(default_factory=list)


@dataclass
class FieldConfig:
    """字段配置"""
    type: str  # string, number, boolean, array, object, select, text, code
    label: str
    description: str = ""
    required: bool = False
    default: Any = None
    placeholder: str = ""
    options: List[Dict] = field(default_factory=list)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    multiline: bool = False
    rows: int = 3
    language: str = "python"
    depends_on: Dict = field(default_factory=dict)
    validation: Dict = field(default_factory=dict)
    tooltip: str = ""
    properties: Dict = field(default_factory=dict)


# =============================================================================
# 完整节点配置定义 - 40+种节点类型
# =============================================================================

def get_all_node_configs() -> Dict[str, NodeConfig]:
    """获取所有节点配置"""

    configs = {}

    # ==========================================================================
    # 第一部分：核心功能节点
    # ==========================================================================

    # 1. 工作流触发节点 (Workflow Trigger)
    configs['workflow_trigger'] = NodeConfig(
        name="工作流触发",
        node_type="workflow_trigger",
        description="工作流的入口节点，定义了工作流的启动方式",
        category="核心功能",
        config_fields={
            'trigger_type': FieldConfig(
                type="select",
                label="触发类型",
                description="选择工作流的触发方式",
                required=True,
                default="manual",
                options=[
                    {"value": "manual", "label": "手动触发",
                        "description": "用户手动启动工作流"},
                    {"value": "webhook", "label": "Webhook触发",
                        "description": "通过HTTP请求触发"},
                    {"value": "schedule", "label": "定时触发",
                        "description": "按设定时间自动执行"},
                    {"value": "event", "label": "事件触发", "description": "响应系统事件"},
                    {"value": "api", "label": "API调用", "description": "通过API调用触发"},
                ]
            ),
            'webhook_path': FieldConfig(
                type="string",
                label="Webhook路径",
                description="Webhook触发的URL路径",
                required=False,
                default="",
                placeholder="/webhook/workflow_id",
                depends_on={"trigger_type": ["webhook"]}
            ),
            'webhook_method': FieldConfig(
                type="select",
                label="HTTP方法",
                description="接受的HTTP请求方法",
                required=False,
                default="POST",
                options=[
                    {"value": "GET", "label": "GET"},
                    {"value": "POST", "label": "POST"},
                    {"value": "PUT", "label": "PUT"},
                    {"value": "PATCH", "label": "PATCH"},
                ],
                depends_on={"trigger_type": ["webhook"]}
            ),
            'schedule_cron': FieldConfig(
                type="string",
                label="Cron表达式",
                description="定时任务的Cron表达式",
                required=False,
                placeholder="0 0 * * * (每天零点)",
                depends_on={"trigger_type": ["schedule"]}
            ),
            'schedule_interval': FieldConfig(
                type="number",
                label="执行间隔(分钟)",
                description="定时执行的间隔时间",
                required=False,
                min_value=1,
                max_value=1440,
                depends_on={"trigger_type": ["schedule"]}
            ),
            'input_parameters': FieldConfig(
                type="array",
                label="输入参数定义",
                description="工作流接收的输入参数",
                required=False,
                default=[],
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "type": {"type": "select", "label": "类型", "options": [
                        {"value": "string", "label": "字符串"},
                        {"value": "number", "label": "数字"},
                        {"value": "boolean", "label": "布尔值"},
                        {"value": "array", "label": "数组"},
                        {"value": "object", "label": "对象"},
                    ]},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "description": {"type": "string", "label": "说明"},
                }
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "triggered_at": {"type": "string", "description": "触发时间"},
                "input_data": {"type": "object", "description": "输入数据"},
                "execution_id": {"type": "string", "description": "执行ID"},
            }
        },
        examples=[
            {"trigger_type": "webhook", "webhook_path": "/api/webhook/customer"},
            {"trigger_type": "schedule", "schedule_interval": 60},
        ]
    )

    # 2. 对话历史节点 (Chat History)
    configs['chat_history'] = NodeConfig(
        name="对话历史",
        node_type="chat_history",
        description="管理对话上下文历史，支持存储和检索对话记录",
        category="核心功能",
        config_fields={
            'operation': FieldConfig(
                type="select",
                label="操作类型",
                description="对对话历史执行的操作",
                required=True,
                default="read",
                options=[
                    {"value": "read", "label": "读取历史", "description": "获取历史对话记录"},
                    {"value": "append", "label": "追加记录", "description": "添加新的对话记录"},
                    {"value": "clear", "label": "清空历史",
                        "description": "清空指定对话的历史"},
                    {"value": "search", "label": "搜索历史", "description": "搜索历史对话"},
                ]
            ),
            'conversation_id': FieldConfig(
                type="string",
                label="对话ID",
                description="对话会话的唯一标识",
                required=True,
                default="${conversation_id}",
                placeholder="对话会话ID"
            ),
            'max_messages': FieldConfig(
                type="number",
                label="最大消息数",
                description="获取的最大历史消息数量",
                required=False,
                default=20,
                min_value=1,
                max_value=100,
                depends_on={"operation": ["read"]}
            ),
            'include_system': FieldConfig(
                type="boolean",
                label="包含系统消息",
                description="是否包含系统设置的消息",
                required=False,
                default=True,
                depends_on={"operation": ["read"]}
            ),
            'message_content': FieldConfig(
                type="text",
                label="消息内容",
                description="要追加的消息内容",
                required=False,
                multiline=True,
                depends_on={"operation": ["append"]}
            ),
            'message_role': FieldConfig(
                type="select",
                label="消息角色",
                description="发送消息的角色",
                required=False,
                default="user",
                options=[
                    {"value": "user", "label": "用户"},
                    {"value": "assistant", "label": "AI助手"},
                    {"value": "system", "label": "系统"},
                ],
                depends_on={"operation": ["append"]}
            ),
            'search_query': FieldConfig(
                type="string",
                label="搜索关键词",
                description="搜索历史对话的关键词",
                required=False,
                depends_on={"operation": ["search"]}
            ),
            'search_limit': FieldConfig(
                type="number",
                label="搜索结果数",
                description="返回的最大搜索结果数",
                required=False,
                default=10,
                depends_on={"operation": ["search"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "conversation_id": {"type": "string"},
                "message": {"type": "string"},
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "messages": {"type": "array", "description": "消息列表"},
                "count": {"type": "number", "description": "消息数量"},
                "conversation_id": {"type": "string"},
            }
        },
        examples=[
            {"operation": "read", "max_messages": 10},
            {"operation": "append", "message_content": "用户输入"},
        ]
    )

    # 3. 数据输入节点 (Data Input)
    configs['data_input'] = NodeConfig(
        name="数据输入",
        node_type="data_input",
        description="工作流的数据入口，支持多种数据来源和格式",
        category="核心功能",
        config_fields={
            'input_type': FieldConfig(
                type="select",
                label="输入类型",
                description="选择数据输入的方式",
                required=True,
                default="json",
                options=[
                    {"value": "json", "label": "JSON数据",
                        "description": "接收JSON格式的输入数据"},
                    {"value": "form", "label": "表单数据", "description": "接收表单字段输入"},
                    {"value": "file", "label": "文件上传", "description": "接收文件上传"},
                    {"value": "database", "label": "数据库查询",
                        "description": "从数据库查询数据"},
                    {"value": "api", "label": "API接口",
                        "description": "调用外部API获取数据"},
                    {"value": "variable", "label": "变量引用",
                        "description": "引用上游节点的输出变量"},
                    {"value": "workflow_input", "label": "工作流输入",
                        "description": "接收工作流入口参数"},
                    {"value": "csv", "label": "CSV数据", "description": "解析CSV格式数据"},
                ]
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                description="存储输入数据的变量名",
                required=True,
                default="input_data",
                placeholder="变量名"
            ),
            'required_fields': FieldConfig(
                type="array",
                label="必填字段",
                description="指定哪些字段为必填项",
                required=False,
                default=[],
                placeholder="选择必填字段"
            ),
            'validation_enabled': FieldConfig(
                type="boolean",
                label="启用验证",
                description="是否启用输入数据验证",
                required=False,
                default=True
            ),
            # 数据库查询配置
            'database_config': FieldConfig(
                type="object",
                label="数据库查询配置",
                description="从数据库查询数据的配置",
                required=False,
                depends_on={"input_type": ["database"]},
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "fields": {"type": "array", "label": "查询字段", "default": ["*"]},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "limit": {"type": "number", "label": "限制", "default": 100},
                }
            ),
            # API配置
            'api_config': FieldConfig(
                type="object",
                label="API配置",
                description="调用外部API的配置",
                required=False,
                depends_on={"input_type": ["api"]},
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "method": {"type": "select", "label": "方法", "options": [
                        {"value": "GET"}, {"value": "POST"}, {"value": "PUT"}
                    ], "default": "GET"},
                    "\1": {"type": "\2", "label": "\3"},
                    "auth_type": {"type": "select", "label": "认证", "options": [
                        {"value": "none"}, {"value": "bearer"}, {"value": "basic"}
                    ], "default": "none"},
                }
            ),
            # CSV配置
            'csv_config': FieldConfig(
                type="object",
                label="CSV配置",
                description="CSV数据解析配置",
                required=False,
                depends_on={"input_type": ["csv"]},
                properties={
                    "\1": {"type": "\2", "label": "\3", "default": "\4"},
                    "has_header": {"type": "boolean", "label": "包含表头", "default": True},
                    "\1": {"type": "\2", "label": "\3", "default": "\4"},
                }
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "data": {"description": "输入数据"},
                "variables": {"type": "object", "description": "变量映射"},
                "metadata": {"type": "object", "description": "元数据"},
            }
        },
        examples=[
            {"input_type": "json", "output_variable": "user_data"},
            {"input_type": "database", "database_config": {
                "table_name": "users", "limit": 10}},
        ]
    )

    # 4. 数据输出节点 (Data Output)
    configs['data_output'] = NodeConfig(
        name="数据输出",
        node_type="data_output",
        description="工作流的结果输出，支持多种输出方式",
        category="核心功能",
        config_fields={
            'output_type': FieldConfig(
                type="select",
                label="输出类型",
                description="选择数据输出的方式",
                required=True,
                default="json",
                options=[
                    {"value": "json", "label": "JSON响应",
                        "description": "返回JSON格式数据"},
                    {"value": "file", "label": "文件下载", "description": "生成并下载文件"},
                    {"value": "database", "label": "数据库存储", "description": "保存到数据库"},
                    {"value": "api", "label": "API回调",
                        "description": "调用外部API发送数据"},
                    {"value": "webhook", "label": "Webhook回调",
                        "description": "触发Webhook"},
                    {"value": "variable", "label": "变量存储",
                        "description": "存储到工作流变量"},
                ]
            ),
            'input_variable': FieldConfig(
                type="string",
                label="输入变量名",
                description="要输出的数据变量名",
                required=True,
                default="output_data"
            ),
            'output_data': FieldConfig(
                type="object",
                label="输出数据映射",
                description="输出字段与输入变量的映射",
                required=False,
                default={}
            ),
            'save_result': FieldConfig(
                type="boolean",
                label="保存结果",
                description="是否保存执行结果到数据库",
                required=False,
                default=True
            ),
            'include_metadata': FieldConfig(
                type="boolean",
                label="包含元数据",
                description="是否在输出中包含执行元数据",
                required=False,
                default=True
            ),
            'status_field': FieldConfig(
                type="boolean",
                label="包含状态字段",
                description="是否包含success/status等状态字段",
                required=False,
                default=True
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "output_data": {"type": "object"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "data": {"description": "输出数据"},
                "message": {"type": "string"},
            }
        },
        examples=[
            {"output_type": "json", "input_variable": "result"},
            {"output_type": "file", "file_type": "csv"},
        ]
    )

    # 5. 延迟节点 (Delay)
    configs['delay'] = NodeConfig(
        name="延迟",
        node_type="delay",
        description="使工作流暂停指定时间后继续执行",
        category="流程控制",
        config_fields={
            'delay_type': FieldConfig(
                type="select",
                label="延迟类型",
                description="延迟时间的指定方式",
                required=True,
                default="fixed",
                options=[
                    {"value": "fixed", "label": "固定时间", "description": "固定延迟时间"},
                    {"value": "variable", "label": "变量时间",
                        "description": "从变量读取延迟时间"},
                    {"value": "random", "label": "随机时间",
                        "description": "指定时间范围内的随机延迟"},
                ]
            ),
            'duration': FieldConfig(
                type="number",
                label="延迟时间(秒)",
                description="延迟的秒数",
                required=False,
                default=5,
                min_value=0,
                max_value=86400,
                depends_on={"delay_type": ["fixed"]}
            ),
            'duration_variable': FieldConfig(
                type="string",
                label="时间变量名",
                description="包含延迟时间的变量名(秒)",
                required=False,
                placeholder="${delay_seconds}",
                depends_on={"delay_type": ["variable"]}
            ),
            'min_duration': FieldConfig(
                type="number",
                label="最小时间(秒)",
                description="随机延迟的最小值",
                required=False,
                default=1,
                depends_on={"delay_type": ["random"]}
            ),
            'max_duration': FieldConfig(
                type="number",
                label="最大时间(秒)",
                description="随机延迟的最大值",
                required=False,
                default=10,
                depends_on={"delay_type": ["random"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "delayed": {"type": "boolean"},
                "duration": {"type": "number"},
                "resumed_at": {"type": "string"},
            }
        },
        examples=[
            {"delay_type": "fixed", "duration": 10},
            {"delay_type": "variable", "duration_variable": "${wait_time}"},
        ]
    )

    # 6. 等待节点 (Wait)
    configs['wait'] = NodeConfig(
        name="等待",
        node_type="wait",
        description="等待特定条件满足后继续执行",
        category="流程控制",
        config_fields={
            'wait_type': FieldConfig(
                type="select",
                label="等待类型",
                description="等待的条件类型",
                required=True,
                default="condition",
                options=[
                    {"value": "condition", "label": "条件等待", "description": "等待条件满足"},
                    {"value": "webhook", "label": "等待Webhook",
                        "description": "等待外部回调"},
                    {"value": "time", "label": "等待时间", "description": "等待指定时间"},
                    {"value": "approval", "label": "等待审批", "description": "等待人工审批"},
                ]
            ),
            'condition': FieldConfig(
                type="text",
                label="等待条件",
                description="需要满足的条件(使用变量表达式)",
                required=False,
                multiline=True,
                placeholder="data.status == 'ready'",
                depends_on={"wait_type": ["condition"]}
            ),
            'timeout': FieldConfig(
                type="number",
                label="超时时间(秒)",
                description="等待超时时间",
                required=False,
                default=3600,
                min_value=60,
                max_value=86400
            ),
            'timeout_action': FieldConfig(
                type="select",
                label="超时处理",
                description="等待超时的处理方式",
                required=False,
                default="continue",
                options=[
                    {"value": "continue", "label": "继续执行",
                        "description": "超时后继续工作流"},
                    {"value": "fail", "label": "标记失败", "description": "超时后标记为失败"},
                    {"value": "retry", "label": "重试", "description": "超时后重新等待"},
                ]
            ),
            'webhook_path': FieldConfig(
                type="string",
                label="Webhook路径",
                description="接收回调的Webhook路径",
                required=False,
                placeholder="/webhook/wait_id",
                depends_on={"wait_type": ["webhook"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "completed": {"type": "boolean"},
                "condition_met": {"type": "boolean"},
                "wait_time": {"type": "number"},
            }
        },
        examples=[
            {"wait_type": "condition",
             "condition": "data.ready == true",
             "timeout": 300},
            {"wait_type": "webhook", "webhook_path": "/webhook/confirm"},
        ]
    )

    # 7. 定时任务节点 (Schedule)
    configs['schedule'] = NodeConfig(
        name="定时任务",
        node_type="schedule",
        description="按设定的时间计划执行工作流",
        category="核心功能",
        config_fields={
            'schedule_type': FieldConfig(
                type="select",
                label="定时类型",
                description="定时执行的类型",
                required=True,
                default="cron",
                options=[
                    {"value": "cron", "label": "Cron表达式",
                        "description": "使用Cron表达式定义时间"},
                    {"value": "interval", "label": "固定间隔",
                        "description": "按固定时间间隔执行"},
                    {"value": "specific", "label": "指定时间",
                        "description": "指定具体的执行时间"},
                ]
            ),
            'cron_expression': FieldConfig(
                type="string",
                label="Cron表达式",
                description="标准Cron格式: 分 时 日 月 周",
                required=False,
                default="0 0 * * *",
                placeholder="0 0 * * * (每天零点)",
                depends_on={"schedule_type": ["cron"]}
            ),
            'timezone': FieldConfig(
                type="select",
                label="时区",
                description="定时执行的时区",
                required=False,
                default="Asia/Shanghai",
                options=[
                    {"value": "Asia/Shanghai", "label": "北京时间(UTC+8)"},
                    {"value": "UTC", "label": "UTC时间"},
                    {"value": "America/New_York", "label": "纽约时间(UTC-5)"},
                    {"value": "Europe/London", "label": "伦敦时间(UTC+0)"},
                ]
            ),
            'interval_minutes': FieldConfig(
                type="number",
                label="执行间隔(分钟)",
                description="固定执行的间隔时间",
                required=False,
                default=60,
                min_value=1,
                max_value=10080,
                depends_on={"schedule_type": ["interval"]}
            ),
            'start_time': FieldConfig(
                type="datetime",
                label="开始时间",
                description="首次执行的开始时间",
                required=False,
                depends_on={"schedule_type": ["specific"]}
            ),
            'end_time': FieldConfig(
                type="datetime",
                label="结束时间",
                description="停止执行的时间(可选)",
                required=False,
                depends_on={"schedule_type": ["specific"]}
            ),
            'enabled': FieldConfig(
                type="boolean",
                label="是否启用",
                description="是否启用此定时任务",
                required=False,
                default=True
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "scheduled": {"type": "boolean"},
                "next_run": {"type": "string"},
                "schedule_config": {"type": "object"},
            }
        },
        examples=[
            {"schedule_type": "cron",
             "cron_expression": "0 9 * * *",
             "timezone": "Asia/Shanghai"},
            {"schedule_type": "interval", "interval_minutes": 30},
        ]
    )

    # ==========================================================================
    # 第二部分：AI处理节点
    # ==========================================================================

    # 8. AI生成节点 (AI Generation)
    configs['ai_generation'] = NodeConfig(
        name="AI生成",
        node_type="ai_generation",
        description="使用大语言模型生成内容，支持多种模型",
        category="AI处理",
        config_fields={
            'model_id': FieldConfig(
                type="select",
                label="AI模型",
                description="选择用于生成的AI模型",
                required=True,
                default="gpt-4",
                options=[
                    {"value": "gpt-4", "label": "GPT-4",
                        "description": "OpenAI GPT-4, 强大的推理能力"},
                    {"value": "gpt-4-turbo", "label": "GPT-4 Turbo",
                        "description": "GPT-4 Turbo, 更快的速度"},
                    {"value": "gpt-3.5-turbo",
                     "label": "GPT-3.5 Turbo",
                     "description": "性价比之选"},
                    {"value": "claude-3-opus", "label": "Claude 3 Opus",
                        "description": "Anthropic Claude 3 Opus"},
                    {"value": "claude-3-sonnet",
                     "label": "Claude 3 Sonnet",
                     "description": "Claude 3 Sonnet"},
                    {"value": "claude-3-haiku", "label": "Claude 3 Haiku",
                        "description": "Claude 3 Haiku, 快速响应"},
                    {"value": "ernie-4", "label": "文心一言4.0",
                        "description": "百度文心一言4.0"},
                    {"value": "qianwen-max", "label": "通义千问Max",
                        "description": "阿里通义千问Max"},
                ]
            ),
            'prompt': FieldConfig(
                type="text",
                label="提示词",
                description="AI生成使用的提示词模板，支持变量引用${var}",
                required=True,
                multiline=True,
                rows=10,
                placeholder="请根据以下信息生成内容：\n\n输入数据：${input_data}\n\n要求：..."
            ),
            'prompt_type': FieldConfig(
                type="select",
                label="提示词类型",
                description="提示词的格式类型",
                required=False,
                default="free",
                options=[
                    {"value": "free", "label": "自由格式", "description": "不限制输出格式"},
                    {"value": "structured", "label": "结构化输出",
                        "description": "按指定格式输出JSON"},
                    {"value": "conversation", "label": "对话模式",
                        "description": "模拟对话交互"},
                    {"value": "few_shot", "label": "Few-shot",
                        "description": "提供示例的生成"},
                ]
            ),
            'output_schema': FieldConfig(
                type="text",
                label="输出Schema",
                description="期望输出数据的JSON Schema",
                required=False,
                multiline=True,
                rows=6,
                placeholder='{"type": "object", "properties": {"answer": {"type": "string"}}}',
                depends_on={"prompt_type": ["structured"]}
            ),
            'temperature': FieldConfig(
                type="number",
                label="Temperature",
                description="控制输出的随机性，0-2之间，值越高越随机",
                required=False,
                default=0.7,
                min_value=0,
                max_value=2
            ),
            'max_tokens': FieldConfig(
                type="number",
                label="最大输出token",
                description="生成内容的最大长度",
                required=False,
                default=2000,
                min_value=100,
                max_value=32000
            ),
            'top_p': FieldConfig(
                type="number",
                label="Top P",
                description="核采样参数，0-1之间",
                required=False,
                default=1.0,
                min_value=0,
                max_value=1
            ),
            'frequency_penalty': FieldConfig(
                type="number",
                label="频率惩罚",
                description="降低重复token的权重，-2到2之间",
                required=False,
                default=0,
                min_value=-2,
                max_value=2
            ),
            'presence_penalty': FieldConfig(
                type="number",
                label="存在惩罚",
                description="降低已出现token的权重，-2到2之间",
                required=False,
                default=0,
                min_value=-2,
                max_value=2
            ),
            'stop_sequences': FieldConfig(
                type="array",
                label="停止序列",
                description="生成到这些序列时停止",
                required=False,
                default=[]
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                description="存储AI生成结果的变量名",
                required=True,
                default="ai_output"
            ),
            'input_variables': FieldConfig(
                type="array",
                label="输入变量列表",
                description="提示词中使用的变量列表",
                required=False,
                default=[],
                placeholder="在提示词中使用${变量名}引用"
            ),
            'system_prompt': FieldConfig(
                type="text",
                label="系统提示词",
                description="设置AI的角色和行为规则",
                required=False,
                multiline=True,
                rows=4,
                placeholder="你是一个专业的助手..."
            ),
            'stream_output': FieldConfig(
                type="boolean",
                label="流式输出",
                description="是否启用流式输出（实时返回生成内容）",
                required=False,
                default=False
            ),
            'error_handling': FieldConfig(
                type="select",
                label="错误处理",
                description="AI调用失败时的处理方式",
                required=False,
                default="retry",
                options=[
                    {"value": "retry", "label": "重试", "description": "自动重试指定次数"},
                    {"value": "fallback", "label": "降级", "description": "使用备用模型"},
                    {"value": "error", "label": "报错", "description": "直接抛出错误"},
                    {"value": "default", "label": "使用默认值",
                        "description": "使用预设的默认值"},
                ]
            ),
            'max_retries': FieldConfig(
                type="number",
                label="最大重试次数",
                description="失败时的最大重试次数",
                required=False,
                default=3,
                min_value=0,
                max_value=10
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "input_data": {"description": "输入数据"},
                "context": {"type": "object", "description": "上下文信息"},
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "生成的文本"},
                "usage": {"type": "object", "description": "Token使用统计"},
                "model": {"type": "string", "description": "使用的模型"},
            }
        },
        examples=[
            {
                "model_id": "gpt-4",
                "prompt": "请总结以下内容：\n\n${content}\n\n总结：",
                "temperature": 0.5,
                "output_variable": "summary"
            },
            {
                "model_id": "claude-3-sonnet",
                "prompt_type": "structured",
                "output_schema": '{"type": "object", "properties": {"sentiment": {"type": "string"}, "score": {"type": "number"}}}',
            }
        ]
    )

    # 9. AI分类节点 (AI Classification)
    configs['ai_classification'] = NodeConfig(
        name="AI分类",
        node_type="ai_classification",
        description="使用AI对输入内容进行分类，支持单标签、多标签和二分类",
        category="AI处理",
        config_fields={
            'model_id': FieldConfig(
                type="select",
                label="AI模型",
                description="选择用于分类的AI模型",
                required=False,
                default="gpt-4",
                options=[
                    {"value": "gpt-4", "label": "GPT-4"},
                    {"value": "gpt-3.5-turbo", "label": "GPT-3.5 Turbo"},
                    {"value": "claude-3-sonnet", "label": "Claude 3 Sonnet"},
                ]
            ),
            'classification_type': FieldConfig(
                type="select",
                label="分类类型",
                description="选择分类的类型",
                required=True,
                default="single",
                options=[
                    {"value": "single", "label": "单标签分类",
                        "description": "只返回一个最匹配的类别"},
                    {"value": "multi", "label": "多标签分类",
                        "description": "可以返回多个匹配的类别"},
                    {"value": "binary", "label": "二分类", "description": "是/否类型的分类"},
                ]
            ),
            'categories': FieldConfig(
                type="array",
                label="分类选项",
                description="所有可能的分类类别",
                required=True,
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                }
            ),
            'input_variable': FieldConfig(
                type="string",
                label="输入变量名",
                description="要分类的文本来源变量",
                required=True,
                default="input_text"
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                description="存储分类结果的变量名",
                required=True,
                default="classification_result"
            ),
            'temperature': FieldConfig(
                type="number",
                label="Temperature",
                description="控制分类的确定性，值越低越确定",
                required=False,
                default=0.3,
                min_value=0,
                max_value=1
            ),
            'return_scores': FieldConfig(
                type="boolean",
                label="返回分数",
                description="是否返回每个类别的置信度分数",
                required=False,
                default=True
            ),
            'allow_none': FieldConfig(
                type="boolean",
                label="允许无匹配",
                description="当没有合适类别时是否返回none",
                required=False,
                default=False
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "input_text": {"type": "string", "description": "待分类的文本"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "categories": {"type": "array", "description": "匹配的类别列表"},
                "scores": {"type": "object", "description": "各类别的置信度"},
                "predicted": {"type": "string", "description": "预测的类别"},
            }
        },
        examples=[
            {
                "classification_type": "single",
                "categories": [
                    {"value": "positive", "label": "正面"},
                    {"value": "negative", "label": "负面"},
                    {"value": "neutral", "label": "中性"}
                ],
                "input_variable": "review_text"
            }
        ]
    )

    # 10. AI信息提取节点 (AI Extraction)
    configs['ai_extraction'] = NodeConfig(
        name="AI信息提取",
        node_type="ai_extraction",
        description="使用AI从文本中提取结构化信息",
        category="AI处理",
        config_fields={
            'model_id': FieldConfig(
                type="select",
                label="AI模型",
                required=False,
                default="gpt-4",
                options=[
                    {"value": "gpt-4", "label": "GPT-4"},
                    {"value": "gpt-3.5-turbo", "label": "GPT-3.5 Turbo"},
                    {"value": "claude-3-sonnet", "label": "Claude 3 Sonnet"},
                ]
            ),
            'extraction_type': FieldConfig(
                type="select",
                label="提取类型",
                description="选择提取的方式",
                required=True,
                default="schema",
                options=[
                    {"value": "schema", "label": "Schema定义提取",
                        "description": "按定义的Schema提取"},
                    {"value": "entity", "label": "实体识别",
                        "description": "识别人名、地名等实体"},
                    {"value": "relation", "label": "关系抽取",
                        "description": "抽取实体间的关系"},
                    {"value": "freeform", "label": "自由提取",
                        "description": "自由形式的结构化提取"},
                ]
            ),
            'extraction_schema': FieldConfig(
                type="text",
                label="提取Schema",
                description="JSON格式的提取定义，指定要提取的字段和类型",
                required=True,
                multiline=True,
                rows=8,
                placeholder='''{
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "姓名"
        },
        "age": {
            "type": "number",
            "description": "年龄"
        },
        "email": {
            "type": "string",
            "description": "邮箱地址"
        }
    }
}'''
            ),
            'input_variable': FieldConfig(
                type="string",
                label="输入变量名",
                description="包含要提取内容的文本变量",
                required=True,
                default="input_text"
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                description="存储提取结果的变量名",
                required=True,
                default="extraction_result"
            ),
            'temperature': FieldConfig(
                type="number",
                label="Temperature",
                description="控制提取的精确度，值越低越精确",
                required=False,
                default=0.1,
                min_value=0,
                max_value=1
            ),
            'strict_mode': FieldConfig(
                type="boolean",
                label="严格模式",
                description="是否严格按照Schema格式输出",
                required=False,
                default=True
            ),
            'multiple': FieldConfig(
                type="boolean",
                label="提取多条",
                description="是否提取多条记录(如多个实体)",
                required=False,
                default=False
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "input_text": {"type": "string", "description": "待提取的文本"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "data": {"description": "提取的数据"},
                "fields": {"type": "array", "description": "提取的字段列表"},
                "confidence": {"type": "number", "description": "提取置信度"},
            }
        },
        examples=[
            {
                "extraction_type": "schema",
                "extraction_schema": '{"type": "object", "properties": {"name": {"type": "string"}, "phone": {"type": "string"}}}',
                "input_variable": "contract_text"
            }
        ]
    )

    # 11. 意图识别节点 (Intent Recognition)
    configs['intent_recognition'] = NodeConfig(
        name="意图识别",
        node_type="intent_recognition",
        description="识别用户输入的意图，适用于客服、对话等场景",
        category="AI处理",
        config_fields={
            'model': FieldConfig(
                type="select",
                label="识别模型",
                description="选择意图识别模型",
                required=True,
                default="general",
                options=[
                    {"value": "general", "label": "通用意图", "description": "通用的意图识别"},
                    {"value": "customer_service", "label": "客服意图",
                        "description": "客服场景专用意图"},
                    {"value": "e_commerce", "label": "电商意图",
                        "description": "电商场景专用意图"},
                    {"value": "faq", "label": "FAQ意图", "description": "问答匹配意图"},
                ]
            ),
            'intents': FieldConfig(
                type="array",
                label="意图定义",
                description="需要识别的意图列表",
                required=True,
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                }
            ),
            'input_variable': FieldConfig(
                type="string",
                label="输入变量名",
                description="用户输入文本的变量名",
                required=True,
                default="user_message"
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                description="存储识别结果的变量名",
                required=True,
                default="intent_result"
            ),
            'return_confidence': FieldConfig(
                type="boolean",
                label="返回置信度",
                description="是否返回意图识别的置信度",
                required=False,
                default=True
            ),
            'threshold': FieldConfig(
                type="number",
                label="置信度阈值",
                description="低于此阈值的意图将返回none",
                required=False,
                default=0.5,
                min_value=0,
                max_value=1
            ),
            'enable_fallback': FieldConfig(
                type="boolean",
                label="启用兜底意图",
                description="置信度低时是否返回兜底意图",
                required=False,
                default=True
            ),
            'fallback_intent': FieldConfig(
                type="string",
                label="兜底意图",
                description="置信度低时的默认意图",
                required=False,
                default="unknown"
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "user_message": {"type": "string", "description": "用户输入"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "intent": {"type": "string", "description": "识别出的意图"},
                "confidence": {"type": "number", "description": "置信度"},
                "all_scores": {"type": "object", "description": "所有意图的分数"},
            }
        },
        examples=[
            {
                "model": "customer_service",
                "intents": [
                    {"value": "query", "label": "查询",
                        "examples": ["查询订单", "订单状态"]},
                    {"value": "complaint", "label": "投诉",
                        "examples": ["我要投诉", "服务太差"]},
                    {"value": "suggestion", "label": "建议",
                        "examples": ["建议改进", "希望能"]},
                ]
            }
        ]
    )

    # 12. 情感分析节点 (Sentiment Analysis)
    configs['sentiment_analysis'] = NodeConfig(
        name="情感分析",
        node_type="sentiment_analysis",
        description="分析文本的情感倾向和情绪",
        category="AI处理",
        config_fields={
            'analysis_type': FieldConfig(
                type="select",
                label="分析类型",
                description="选择情感分析的类型",
                required=False,
                default="fine",
                options=[
                    {"value": "basic", "label": "基础情感",
                        "description": "正面/负面/中性三分类"},
                    {"value": "fine", "label": "细粒度情感",
                        "description": "更细粒度的情感分类"},
                    {"value": "batch", "label": "批量分析",
                        "description": "对批量文本进行分析"},
                    {"value": "emotion", "label": "情绪识别",
                        "description": "识别具体情绪如开心、愤怒等"},
                ]
            ),
            'input_variable': FieldConfig(
                type="string",
                label="输入变量名",
                description="待分析文本的变量名",
                required=True,
                default="input_text"
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                description="存储分析结果的变量名",
                required=True,
                default="sentiment_result"
            ),
            'return_scores': FieldConfig(
                type="boolean",
                label="返回分数",
                description="是否返回各情感的置信度分数",
                required=False,
                default=True
            ),
            'return_aspects': FieldConfig(
                type="boolean",
                label="方面情感",
                description="是否进行方面级情感分析",
                required=False,
                default=False
            ),
            'supported_languages': FieldConfig(
                type="select",
                label="支持语言",
                description="输入文本的语言",
                required=False,
                default="auto",
                options=[
                    {"value": "auto", "label": "自动检测"},
                    {"value": "zh", "label": "中文"},
                    {"value": "en", "label": "英文"},
                    {"value": "multilingual", "label": "多语言"},
                ]
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "input_text": {"type": "string", "description": "待分析文本"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "sentiment": {"type": "string", "description": "情感标签"},
                "score": {"type": "number", "description": "情感分数(-1到1)"},
                "scores": {"type": "object", "description": "各情感分数"},
                "emotion": {"type": "string", "description": "情绪(当analysis_type=emotion时)"},
            }
        },
        examples=[
            {
                "analysis_type": "fine",
                "input_variable": "customer_feedback"
            },
            {
                "analysis_type": "batch",
                "input_variable": "reviews_list"
            }
        ]
    )

    # ==========================================================================
    # 第三部分：流程控制节点
    # ==========================================================================

    # 13. 多条件分支节点 (Condition Branch)
    configs['condition'] = NodeConfig(
        name="多条件分支",
        node_type="condition",
        description="根据条件判断进行流程分支，支持多种条件类型",
        category="流程控制",
        config_fields={
            'condition_type': FieldConfig(
                type="select",
                label="条件类型",
                description="选择条件判断的类型",
                required=True,
                default="if_else",
                options=[
                    {"value": "if_else", "label": "IF-ELSE",
                        "description": "单条件二分支"},
                    {"value": "switch", "label": "SWITCH", "description": "多条件多分支"},
                    {"value": "logic", "label": "逻辑组合", "description": "组合多个条件"},
                    {"value": "expression", "label": "表达式",
                        "description": "使用自定义表达式"},
                ]
            ),
            'condition_variable': FieldConfig(
                type="string",
                label="条件变量",
                description="进行判断的变量路径，支持点分隔如 data.sentiment",
                required=True,
                default="data.value",
                placeholder="例如: data.status, result.score"
            ),
            # IF-ELSE配置
            'expressions': FieldConfig(
                type="array",
                label="条件表达式",
                description="定义条件分支的表达式列表",
                required=False,
                properties={
                    "operator": FieldConfig(
                        type="select",
                        label="运算符",
                        options=[
                            {"value": "=", "label": "等于"},
                            {"value": "!", "label": "不等于"},
                            {"value": ">", "label": "大于"},
                            {"value": ">", "label": "大于等于"},
                            {"value": "<", "label": "小于"},
                            {"value": "<", "label": "小于等于"},
                            {"value": "in", "label": "在列表中"},
                            {"value": "not_in", "label": "不在列表中"},
                            {"value": "contains", "label": "包含"},
                            {"value": "starts_with", "label": "开头是"},
                            {"value": "ends_with", "label": "结尾是"},
                            {"value": "regex", "label": "正则匹配"},
                            {"value": "is_empty", "label": "为空"},
                            {"value": "is_not_empty", "label": "不为空"},
                            {"value": "is_true", "label": "为真"},
                            {"value": "is_false", "label": "为假"},
                        ]
                    ),
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                },
                depends_on={"condition_type": ["if_else", "logic"]}
            ),
            # SWITCH配置
            'cases': FieldConfig(
                type="array",
                label="分支情况",
                description="SWITCH模式的各case分支",
                required=False,
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                },
                depends_on={"condition_type": ["switch"]}
            ),
            'default_output': FieldConfig(
                type="string",
                label="默认输出",
                description="无匹配条件时的默认输出标签",
                required=False,
                default="default"
            ),
            # 表达式配置
            'expression': FieldConfig(
                type="text",
                label="自定义表达式",
                description="使用Python语法的条件表达式",
                required=False,
                multiline=True,
                placeholder="data.value > 0 and data.status == 'valid'",
                depends_on={"condition_type": ["expression"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "matched": {"type": "boolean", "description": "是否匹配条件"},
                "output": {"type": "string", "description": "匹配的输出标签"},
                "condition": {"type": "string", "description": "实际使用的条件"},
            }
        },
        examples=[
            {
                "condition_type": "if_else",
                "condition_variable": "sentiment.score",
                "expressions": [
                    {"operator": ">", "value": "0.5", "output": "positive"},
                    {"operator": "<", "value": "-0.5", "output": "negative"},
                ]
            },
            {
                "condition_type": "switch",
                "condition_variable": "order.status",
                "cases": [
                    {"value": "pending", "output": "wait_payment"},
                    {"value": "paid", "output": "start_processing"},
                    {"value": "shipped", "output": "notify_customer"},
                ]
            }
        ]
    )

    # 14. 循环处理节点 (Loop)
    configs['loop'] = NodeConfig(
        name="循环处理",
        node_type="loop",
        description="对数组或范围内的数据进行循环处理",
        category="流程控制",
        config_fields={
            'loop_type': FieldConfig(
                type="select",
                label="循环类型",
                description="选择循环的类型",
                required=True,
                default="foreach",
                options=[
                    {"value": "foreach", "label": "遍历循环",
                        "description": "遍历数组的每个元素"},
                    {"value": "for", "label": "计次循环", "description": "按指定次数循环"},
                    {"value": "while", "label": "条件循环",
                        "description": "满足条件时持续循环"},
                    {"value": "do_while", "label": "直到循环",
                        "description": "先执行后判断条件"},
                ]
            ),
            # 遍历循环配置
            'iterable_variable': FieldConfig(
                type="string",
                label="迭代变量名",
                description="要遍历的数组变量",
                required=False,
                placeholder="${items}",
                depends_on={"loop_type": ["foreach"]}
            ),
            'item_variable': FieldConfig(
                type="string",
                label="项变量名",
                description="循环中每个元素的变量名",
                required=False,
                default="item"
            ),
            'index_variable': FieldConfig(
                type="string",
                label="索引变量名",
                description="当前索引的变量名(可选)",
                required=False,
                default="index"
            ),
            # 计次循环配置
            'start_index': FieldConfig(
                type="number",
                label="起始值",
                description="计次循环的起始值",
                required=False,
                default=0,
                depends_on={"loop_type": ["for"]}
            ),
            'end_index': FieldConfig(
                type="number",
                label="结束值",
                description="计次循环的结束值(不包含)",
                required=False,
                default=10,
                depends_on={"loop_type": ["for"]}
            ),
            'step': FieldConfig(
                type="number",
                label="步长",
                description="每次循环的增量",
                required=False,
                default=1,
                depends_on={"loop_type": ["for"]}
            ),
            # 条件循环配置
            'while_condition': FieldConfig(
                type="string",
                label="循环条件",
                description="继续循环的条件(表达式)",
                required=False,
                placeholder="count < 10",
                depends_on={"loop_type": ["while", "do_while"]}
            ),
            'do_while_condition': FieldConfig(
                type="string",
                label="退出条件",
                description="退出循环的条件(表达式)",
                required=False,
                placeholder="count >= 10",
                depends_on={"loop_type": ["do_while"]}
            ),
            'max_iterations': FieldConfig(
                type="number",
                label="最大迭代次数",
                description="防止无限循环的最大迭代次数",
                required=False,
                default=1000,
                min_value=1,
                max_value=100000
            ),
            'continue_on_error': FieldConfig(
                type="boolean",
                label="出错继续",
                description="单次迭代出错时是否继续下一次",
                required=False,
                default=False
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "items": {"type": "array", "description": "待遍历的数组"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "results": {"type": "array", "description": "每次迭代的结果"},
                "iterations": {"type": "number", "description": "迭代次数"},
                "completed": {"type": "boolean", "description": "是否完成"},
            }
        },
        examples=[
            {
                "loop_type": "foreach",
                "iterable_variable": "${orders}",
                "item_variable": "order"
            },
            {
                "loop_type": "for",
                "start_index": 0,
                "end_index": 100
            }
        ]
    )

    # 15. 迭代器节点 (Iterator)
    configs['iterator'] = NodeConfig(
        name="迭代器",
        node_type="iterator",
        description="对数据进行迭代处理，支持嵌套迭代",
        category="流程控制",
        config_fields={
            'source_variable': FieldConfig(
                type="string",
                label="源数据变量",
                description="要迭代的数据源变量",
                required=True,
                placeholder="${data_list}"
            ),
            'item_variable': FieldConfig(
                type="string",
                label="当前项变量",
                description="每次迭代当前项的变量名",
                required=True,
                default="item"
            ),
            'index_variable': FieldConfig(
                type="string",
                label="索引变量",
                description="当前索引的变量名",
                required=False,
                default="idx"
            ),
            'batch_size': FieldConfig(
                type="number",
                label="批次大小",
                description="每批处理的数据条数(0表示全部)",
                required=False,
                default=0,
                min_value=0
            ),
            'order': FieldConfig(
                type="select",
                label="处理顺序",
                description="数据处理的顺序",
                required=False,
                default="sequential",
                options=[
                    {"value": "sequential", "label": "顺序处理"},
                    {"value": "reverse", "label": "倒序处理"},
                    {"value": "shuffle", "label": "随机打乱"},
                ]
            ),
            'continue_on_error': FieldConfig(
                type="boolean",
                label="出错继续",
                description="某项处理出错时是否继续处理其他项",
                required=False,
                default=True
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "data_list": {"type": "array", "description": "数据列表"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "items": {"type": "array", "description": "处理后的数据"},
                "success_items": {"type": "array", "description": "成功的项"},
                "failed_items": {"type": "array", "description": "失败的项"},
                "total": {"type": "number", "description": "总数量"},
                "success_count": {"type": "number", "description": "成功数量"},
                "failed_count": {"type": "number", "description": "失败数量"},
            }
        },
        examples=[
            {
                "source_variable": "${user_list}",
                "item_variable": "user"
            }
        ]
    )

    # 16. 并行处理节点 (Parallel)
    configs['parallel'] = NodeConfig(
        name="并行处理",
        node_type="parallel",
        description="并行执行多个分支，提高处理效率",
        category="流程控制",
        config_fields={
            'execution_mode': FieldConfig(
                type="select",
                label="执行模式",
                description="并行执行的方式",
                required=True,
                default="all",
                options=[
                    {"value": "all", "label": "全部执行", "description": "所有分支都执行"},
                    {"value": "first_success", "label": "首个成功",
                        "description": "任意一个成功即返回"},
                    {"value": "all_success", "label": "全部成功",
                        "description": "所有都成功才返回"},
                    {"value": "race", "label": "竞速模式", "description": "返回最快完成的结果"},
                ]
            ),
            'branches': FieldConfig(
                type="array",
                label="并行分支",
                description="并行执行的分支列表",
                required=True,
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                }
            ),
            'timeout': FieldConfig(
                type="number",
                label="全局超时(秒)",
                description="所有分支的全局超时时间",
                required=False,
                default=300,
                min_value=1
            ),
            'continue_on_error': FieldConfig(
                type="boolean",
                label="部分失败继续",
                description="部分分支失败时是否继续等待其他分支",
                required=False,
                default=True
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "results": {"type": "object", "description": "各分支结果"},
                "completed": {"type": "array", "description": "完成的分支"},
                "failed": {"type": "array", "description": "失败的分支"},
                "execution_time": {"type": "number", "description": "执行时间(秒)"},
            }
        },
        examples=[
            {
                "execution_mode": "all",
                "branches": [
                    {"name": "发送邮件", "timeout": 30},
                    {"name": "发送短信", "timeout": 10},
                    {"name": "记录日志", "timeout": 5},
                ]
            }
        ]
    )

    # ==========================================================================
    # 第四部分：数据处理节点
    # ==========================================================================

    # 17. 变量聚合节点 (Variable Aggregation)
    configs['variable_aggregation'] = NodeConfig(
        name="变量聚合",
        node_type="variable_aggregation",
        description="将多个变量合并为一个复合变量",
        category="数据处理",
        config_fields={
            'aggregation_type': FieldConfig(
                type="select",
                label="聚合类型",
                description="选择聚合方式",
                required=True,
                default="object",
                options=[
                    {"value": "object", "label": "对象合并", "description": "合并为对象"},
                    {"value": "array", "label": "数组拼接", "description": "拼接为数组"},
                    {"value": "string", "label": "字符串拼接", "description": "拼接为字符串"},
                ]
            ),
            'source_variables': FieldConfig(
                type="array",
                label="源变量",
                description="要聚合的源变量列表",
                required=True,
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                }
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                description="存储聚合结果的变量名",
                required=True,
                default="aggregated"
            ),
            'string_separator': FieldConfig(
                type="string",
                label="字符串分隔符",
                description="字符串拼接时的分隔符",
                required=False,
                default=","
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "aggregated": {"description": "聚合后的数据"},
                "keys": {"type": "array", "description": "聚合的键列表"},
            }
        },
        examples=[
            {
                "aggregation_type": "object",
                "source_variables": [
                    {"variable": "${name}", "key": "name"},
                    {"variable": "${age}", "key": "age"},
                ]
            }
        ]
    )

    # 18. 参数聚合节点 (Parameter Aggregation)
    configs['parameter_aggregation'] = NodeConfig(
        name="参数聚合",
        node_type="parameter_aggregation",
        description="聚合函数参数，支持动态参数构建",
        category="数据处理",
        config_fields={
            'parameters': FieldConfig(
                type="array",
                label="参数列表",
                description="要聚合的参数",
                required=True,
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "type": {"type": "select", "label": "类型", "options": [
                        {"value": "string"}, {"value": "number"},
                        {"value": "boolean"}, {
                            "value": "array"}, {"value": "object"}
                    ]},
                }
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="params"
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "params": {"type": "object", "description": "聚合的参数对象"}
            }
        },
        examples=[
            {
                "parameters": [
                    {"name": "name", "value": "${user_name}", "type": "string"},
                    {"name": "age", "value": "${user_age}", "type": "number"},
                ]
            }
        ]
    )

    # 19. 变量赋值节点 (Variable Assignment)
    configs['variable_assignment'] = NodeConfig(
        name="变量赋值",
        node_type="variable_assignment",
        description="对变量进行赋值操作，支持条件赋值",
        category="数据处理",
        config_fields={
            'assignment_type': FieldConfig(
                type="select",
                label="赋值类型",
                description="选择赋值方式",
                required=True,
                default="direct",
                options=[
                    {"value": "direct", "label": "直接赋值", "description": "直接将值赋给变量"},
                    {"value": "conditional", "label": "条件赋值",
                        "description": "根据条件赋值"},
                    {"value": "computed", "label": "计算赋值", "description": "通过表达式计算"},
                    {"value": "copy", "label": "复制赋值", "description": "从另一个变量复制"},
                ]
            ),
            'variable_name': FieldConfig(
                type="string",
                label="变量名",
                description="要赋值的变量名",
                required=True,
                placeholder="new_variable"
            ),
            'variable_value': FieldConfig(
                type="string",
                label="变量值",
                description="要赋予的值或变量引用",
                required=True,
                placeholder="${source_value}"
            ),
            'value_type': FieldConfig(
                type="select",
                label="值类型",
                description="变量值的数据类型",
                required=False,
                default="auto",
                options=[
                    {"value": "auto", "label": "自动推断"},
                    {"value": "string", "label": "字符串"},
                    {"value": "number", "label": "数字"},
                    {"value": "boolean", "label": "布尔值"},
                    {"value": "array", "label": "数组"},
                    {"value": "object", "label": "对象"},
                ]
            ),
            # 条件赋值配置
            'conditions': FieldConfig(
                type="array",
                label="赋值条件",
                description="条件赋值的条件列表",
                required=False,
                depends_on={"assignment_type": ["conditional"]},
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                }
            ),
            'default_value': FieldConfig(
                type="string",
                label="默认值",
                description="无匹配条件时的默认值",
                required=False,
                depends_on={"assignment_type": ["conditional"]}
            ),
            # 计算赋值配置
            'expression': FieldConfig(
                type="text",
                label="计算表达式",
                description="用于计算的Python表达式",
                required=False,
                multiline=True,
                placeholder="a + b * 2",
                depends_on={"assignment_type": ["computed"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "assigned": {"type": "boolean"},
                "variable": {"type": "string", "description": "变量名"},
                "value": {"description": "赋值结果"},
            }
        },
        examples=[
            {
                "assignment_type": "direct",
                "variable_name": "result",
                "variable_value": "${calculation}"
            },
            {
                "assignment_type": "conditional",
                "variable_name": "status",
                "conditions": [
                    {"condition": "score >= 90", "value": "excellent"},
                    {"condition": "score >= 60", "value": "pass"},
                ],
                "default_value": "fail"
            }
        ]
    )

    # 20. 数据转换节点 (Data Transformation)
    configs['data_transformation'] = NodeConfig(
        name="数据转换",
        node_type="data_transformation",
        description="对数据进行各种转换操作",
        category="数据处理",
        config_fields={
            'transformation_type': FieldConfig(
                type="select",
                label="转换类型",
                description="选择转换操作",
                required=True,
                default="map",
                options=[
                    {"value": "map", "label": "数据映射", "description": "字段映射转换"},
                    {"value": "filter", "label": "数据过滤", "description": "按条件过滤数据"},
                    {"value": "sort", "label": "数据排序", "description": "对数据进行排序"},
                    {"value": "aggregate", "label": "数据聚合", "description": "分组统计"},
                    {"value": "flatten", "label": "扁平化", "description": "嵌套结构扁平化"},
                    {"value": "nest", "label": "嵌套化", "description": "扁平结构嵌套化"},
                    {"value": "pivot", "label": "数据透视", "description": "行列转换"},
                    {"value": "unpivot", "label": "逆透视", "description": "列转行"},
                    {"value": "deduplicate", "label": "去重", "description": "去除重复数据"},
                ]
            ),
            'input_variable': FieldConfig(
                type="string",
                label="输入变量名",
                description="源数据变量名",
                required=True,
                default="input_data"
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                description="结果存储变量名",
                required=True,
                default="output_data"
            ),
            # 映射配置
            'field_mapping': FieldConfig(
                type="object",
                label="字段映射",
                description="源字段到目标字段的映射",
                required=False,
                depends_on={"transformation_type": ["map"]},
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                }
            ),
            # 过滤配置
            'filter_condition': FieldConfig(
                type="string",
                label="过滤条件",
                description="数据过滤的条件表达式",
                required=False,
                placeholder="data.status == 'active'",
                depends_on={"transformation_type": ["filter"]}
            ),
            # 排序配置
            'sort_fields': FieldConfig(
                type="array",
                label="排序字段",
                description="排序的字段和方向",
                required=False,
                depends_on={"transformation_type": ["sort"]},
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "order": {"type": "select", "label": "方向", "options": [
                        {"value": "asc"}, {"value": "desc"}
                    ]},
                }
            ),
            # 分组配置
            'group_by': FieldConfig(
                type="array",
                label="分组字段",
                description="分组的字段列表",
                required=False,
                depends_on={"transformation_type": ["aggregate", "pivot"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "input_data": {"description": "输入数据"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "output_data": {"description": "转换后的数据"},
                "metadata": {"type": "object", "description": "转换元信息"},
            }
        },
        examples=[
            {
                "transformation_type": "map",
                "field_mapping": {
                    "source_field": "user_name",
                    "target_field": "name",
                    "transform": "uppercase"
                }
            },
            {
                "transformation_type": "filter",
                "filter_condition": "data.age >= 18"
            }
        ]
    )

    # 21. 数据过滤节点 (Data Filter)
    configs['data_filter'] = NodeConfig(
        name="数据过滤",
        node_type="data_filter",
        description="按条件过滤数据数组",
        category="数据处理",
        config_fields={
            'filter_type': FieldConfig(
                type="select",
                label="过滤类型",
                description="选择过滤方式",
                required=True,
                default="condition",
                options=[
                    {"value": "condition", "label": "条件过滤", "description": "按条件过滤"},
                    {"value": "range", "label": "范围过滤", "description": "按数值范围过滤"},
                    {"value": "unique", "label": "去重", "description": "去除重复项"},
                    {"value": "null", "label": "空值过滤", "description": "过滤空值"},
                    {"value": "regex", "label": "正则过滤", "description": "按正则表达式过滤"},
                ]
            ),
            'input_variable': FieldConfig(
                type="string",
                label="输入变量名",
                required=True,
                default="data"
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="filtered"
            ),
            'filter_condition': FieldConfig(
                type="string",
                label="过滤条件",
                description="过滤条件表达式",
                required=False,
                placeholder="item.status == 'active'",
                depends_on={"filter_type": ["condition", "regex"]}
            ),
            'range_min': FieldConfig(
                type="number",
                label="最小值",
                description="范围过滤的最小值",
                required=False,
                depends_on={"filter_type": ["range"]}
            ),
            'range_max': FieldConfig(
                type="number",
                label="最大值",
                description="范围过滤的最大值",
                required=False,
                depends_on={"filter_type": ["range"]}
            ),
            'unique_by': FieldConfig(
                type="string",
                label="去重字段",
                description="按此字段去重",
                required=False,
                depends_on={"filter_type": ["unique"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "data": {"type": "array", "description": "数据数组"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "filtered": {"type": "array", "description": "过滤后的数据"},
                "count": {"type": "number", "description": "过滤后数量"},
                "removed_count": {"type": "number", "description": "移除数量"},
            }
        },
        examples=[
            {
                "filter_type": "condition",
                "filter_condition": "item.age >= 18"
            }
        ]
    )

    # 22. 数据聚合节点 (Data Aggregation)
    configs['data_aggregation'] = NodeConfig(
        name="数据聚合",
        node_type="data_aggregation",
        description="对数据进行分组聚合统计",
        category="数据处理",
        config_fields={
            'input_variable': FieldConfig(
                type="string",
                label="输入变量名",
                required=True,
                default="data"
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="aggregated"
            ),
            'group_by': FieldConfig(
                type="array",
                label="分组字段",
                description="按这些字段进行分组",
                required=True,
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                }
            ),
            'aggregations': FieldConfig(
                type="array",
                label="聚合操作",
                required=True,
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "function": FieldConfig(
                        type="select",
                        label="聚合函数",
                        options=[
                            {"value": "sum", "label": "求和"},
                            {"value": "avg", "label": "平均值"},
                            {"value": "count", "label": "计数"},
                            {"value": "min", "label": "最小值"},
                            {"value": "max", "label": "最大值"},
                            {"value": "first", "label": "第一个"},
                            {"value": "last", "label": "最后一个"},
                            {"value": "concat", "label": "连接"},
                            {"value": "stddev", "label": "标准差"},
                        ]
                    ),
                    "\1": {"type": "\2", "label": "\3"},
                }
            ),
            'having': FieldConfig(
                type="string",
                label="过滤条件",
                description="对聚合结果进行过滤",
                required=False,
                placeholder="count > 10"
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "data": {"type": "array", "description": "数据数组"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "aggregated": {"type": "array", "description": "聚合结果"},
                "groups": {"type": "number", "description": "分组数量"},
            }
        },
        examples=[
            {
                "group_by": [{"field": "category"}],
                "aggregations": [
                    {"field": "amount", "function": "sum", "alias": "total"},
                    {"field": "id", "function": "count", "alias": "count"},
                ]
            }
        ]
    )

    # 23. 数据格式化节点 (Data Format)
    configs['data_format'] = NodeConfig(
        name="数据格式化",
        node_type="data_format",
        description="对数据进行格式化处理",
        category="数据处理",
        config_fields={
            'format_type': FieldConfig(
                type="select",
                label="格式化类型",
                description="选择格式化方式",
                required=True,
                default="datetime",
                options=[
                    {"value": "datetime", "label": "日期时间格式化",
                        "description": "日期时间格式化"},
                    {"value": "number", "label": "数字格式化", "description": "数字格式化"},
                    {"value": "currency", "label": "货币格式化", "description": "货币格式化"},
                    {"value": "percentage", "label": "百分比格式化",
                        "description": "百分比格式化"},
                    {"value": "json", "label": "JSON格式化", "description": "JSON格式化"},
                    {"value": "custom", "label": "自定义格式化", "description": "自定义格式模板"},
                ]
            ),
            'input_variable': FieldConfig(
                type="string",
                label="输入变量名",
                required=True,
                default="value"
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="formatted"
            ),
            'datetime_format': FieldConfig(
                type="string",
                label="日期时间格式",
                description="日期时间格式化模板",
                required=False,
                default="%Y-%m-%d %H:%M:%S",
                depends_on={"format_type": ["datetime"]}
            ),
            'number_format': FieldConfig(
                type="string",
                label="数字格式",
                description="数字格式化模板(如: 0.00)",
                required=False,
                default="0.00",
                depends_on={"format_type": ["number"]}
            ),
            'currency_code': FieldConfig(
                type="string",
                label="货币代码",
                description="货币代码如 CNY, USD",
                required=False,
                default="CNY",
                depends_on={"format_type": ["currency"]}
            ),
            'custom_template': FieldConfig(
                type="string",
                label="自定义模板",
                description="自定义格式化模板，支持${value}",
                required=False,
                placeholder="Value: ${value}",
                depends_on={"format_type": ["custom"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "value": {"description": "待格式化的值"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "formatted": {"type": "string", "description": "格式化后的值"},
                "original": {"description": "原始值"},
            }
        },
        examples=[
            {
                "format_type": "datetime",
                "datetime_format": "%Y年%m月%d日"
            },
            {
                "format_type": "currency",
                "currency_code": "USD"
            }
        ]
    )

    # 24. 文本处理节点 (Text Processing)
    configs['text_processing'] = NodeConfig(
        name="文本处理",
        node_type="text_processing",
        description="对文本进行各种处理操作",
        category="数据处理",
        config_fields={
            'processing_type': FieldConfig(
                type="select",
                label="处理类型",
                description="选择文本处理操作",
                required=True,
                default="clean",
                options=[
                    {"value": "clean", "label": "文本清洗",
                        "description": "去除多余空白、特殊字符"},
                    {"value": "transform", "label": "文本转换",
                        "description": "大小写、编码转换"},
                    {"value": "extract", "label": "信息提取",
                        "description": "提取特定格式内容"},
                    {"value": "split", "label": "文本分割", "description": "按分隔符分割"},
                    {"value": "join", "label": "文本合并", "description": "合并多个文本"},
                    {"value": "replace", "label": "文本替换", "description": "查找替换文本"},
                    {"value": "case", "label": "大小写转换", "description": "大小写转换"},
                    {"value": "translate", "label": "翻译", "description": "文本翻译"},
                    {"value": "summarize", "label": "摘要生成", "description": "生成文本摘要"},
                ]
            ),
            'input_variable': FieldConfig(
                type="string",
                label="输入变量名",
                required=True,
                default="input_text"
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="output_text"
            ),
            'delimiter': FieldConfig(
                type="string",
                label="分隔符",
                description="分割或合并的分隔符",
                required=False,
                default=",",
                depends_on={"processing_type": ["split", "join"]}
            ),
            'find_text': FieldConfig(
                type="string",
                label="查找文本",
                description="要查找的文本",
                required=False,
                depends_on={"processing_type": ["replace"]}
            ),
            'replace_text': FieldConfig(
                type="string",
                label="替换文本",
                description="替换为的文本",
                required=False,
                depends_on={"processing_type": ["replace"]}
            ),
            'case_type': FieldConfig(
                type="select",
                label="大小写类型",
                description="大小写转换类型",
                required=False,
                default="lower",
                options=[
                    {"value": "lower", "label": "小写"},
                    {"value": "upper", "label": "大写"},
                    {"value": "title", "label": "首字母大写"},
                    {"value": "capitalize", "label": "每个单词首字母大写"},
                ],
                depends_on={"processing_type": ["case"]}
            ),
            'target_language': FieldConfig(
                type="select",
                label="目标语言",
                description="翻译的目标语言",
                required=False,
                default="en",
                options=[
                    {"value": "en", "label": "英语"},
                    {"value": "zh", "label": "中文"},
                    {"value": "ja", "label": "日语"},
                    {"value": "ko", "label": "韩语"},
                    {"value": "fr", "label": "法语"},
                    {"value": "de", "label": "德语"},
                ],
                depends_on={"processing_type": ["translate"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "input_text": {"type": "string", "description": "输入文本"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "output_text": {"type": "string", "description": "处理后的文本"}
            }
        },
        examples=[
            {
                "processing_type": "clean",
                "input_variable": "raw_text"
            },
            {
                "processing_type": "replace",
                "find_text": "旧内容",
                "replace_text": "新内容"
            }
        ]
    )

    # 25. 模板渲染节点 (Template Rendering)
    configs['template'] = NodeConfig(
        name="模板渲染",
        node_type="template",
        description="使用模板引擎渲染文本",
        category="数据处理",
        config_fields={
            'template_engine': FieldConfig(
                type="select",
                label="模板引擎",
                description="使用的模板引擎",
                required=False,
                default="jinja2",
                options=[
                    {"value": "jinja2", "label": "Jinja2",
                        "description": "Python常用的模板引擎"},
                    {"value": "mustache", "label": "Mustache",
                        "description": "无逻辑模板引擎"},
                    {"value": "custom", "label": "自定义", "description": "自定义格式"},
                ]
            ),
            'template_text': FieldConfig(
                type="text",
                label="模板内容",
                description="模板文本，支持变量引用",
                required=True,
                multiline=True,
                rows=10,
                placeholder="Hello, {{ name }}! Your score is {{ score }}."
            ),
            'input_variables': FieldConfig(
                type="object",
                label="输入变量",
                description="模板中使用的变量值",
                required=False,
                default={}
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="rendered"
            ),
            'escape_html': FieldConfig(
                type="boolean",
                label="HTML转义",
                description="是否对输出进行HTML转义",
                required=False,
                default=True
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "rendered": {"type": "string", "description": "渲染后的文本"},
                "template": {"type": "string", "description": "使用的模板"},
            }
        },
        examples=[
            {
                "template_engine": "jinja2",
                "template_text": "用户{{ name }}的订单{{ order_id }}已{{ status }}",
                "input_variables": {
                    "name": "张三",
                    "order_id": "ORD001",
                    "status": "完成"
                }
            }
        ]
    )

    # ==========================================================================
    # 第五部分：外部集成节点
    # ==========================================================================

    # 26. HTTP请求节点 (HTTP Request)
    configs['http_request'] = NodeConfig(
        name="HTTP请求",
        node_type="http_request",
        description="发送HTTP请求调用外部API",
        category="外部集成",
        config_fields={
            'api_url': FieldConfig(
                type="string",
                label="API地址",
                description="请求的目标API地址",
                required=True,
                placeholder="https://api.example.com/endpoint"
            ),
            'method': FieldConfig(
                type="select",
                label="请求方法",
                description="HTTP请求方法",
                required=True,
                default="GET",
                options=[
                    {"value": "GET", "label": "GET"},
                    {"value": "POST", "label": "POST"},
                    {"value": "PUT", "label": "PUT"},
                    {"value": "PATCH", "label": "PATCH"},
                    {"value": "DELETE", "label": "DELETE"},
                ]
            ),
            'headers': FieldConfig(
                type="object",
                label="请求头",
                description="HTTP请求头",
                required=False,
                default={}
            ),
            'request_body': FieldConfig(
                type="text",
                label="请求体",
                description="POST/PUT/PATCH请求的请求体",
                required=False,
                multiline=True,
                rows=6,
                depends_on={"method": ["POST", "PUT", "PATCH"]}
            ),
            'content_type': FieldConfig(
                type="select",
                label="内容类型",
                description="请求体的Content-Type",
                required=False,
                default="application/json",
                options=[
                    {"value": "application/json", "label": "JSON"},
                    {"value": "application/x-www-form-urlencoded", "label": "表单"},
                    {"value": "multipart/form-data",
                        "label": "multipart/form-data"},
                    {"value": "text/plain", "label": "纯文本"},
                    {"value": "text/xml", "label": "XML"},
                ]
            ),
            'auth_type': FieldConfig(
                type="select",
                label="认证方式",
                description="API认证方式",
                required=False,
                default="none",
                options=[
                    {"value": "none", "label": "无认证"},
                    {"value": "bearer", "label": "Bearer Token"},
                    {"value": "basic", "label": "基础认证"},
                    {"value": "api_key", "label": "API Key"},
                    {"value": "oauth2", "label": "OAuth 2.0"},
                ]
            ),
            'auth_config': FieldConfig(
                type="object",
                label="认证配置",
                description="认证相关信息",
                required=False,
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3", "default": "\4"},
                }
            ),
            'timeout': FieldConfig(
                type="number",
                label="超时时间(秒)",
                description="请求超时时间",
                required=False,
                default=30,
                min_value=1,
                max_value=300
            ),
            'retry_count': FieldConfig(
                type="number",
                label="重试次数",
                description="请求失败时的重试次数",
                required=False,
                default=3,
                min_value=0,
                max_value=10
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                description="存储响应结果的变量名",
                required=True,
                default="http_response"
            ),
            'response_format': FieldConfig(
                type="select",
                label="响应格式",
                description="期望的响应数据格式",
                required=False,
                default="json",
                options=[
                    {"value": "json", "label": "JSON"},
                    {"value": "xml", "label": "XML"},
                    {"value": "text", "label": "纯文本"},
                    {"value": "binary", "label": "二进制"},
                ]
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "status_code": {"type": "number", "description": "HTTP状态码"},
                "headers": {"type": "object", "description": "响应头"},
                "body": {"description": "响应体"},
                "ok": {"type": "boolean", "description": "是否成功"},
                "elapsed": {"type": "number", "description": "响应时间(秒)"},
            }
        },
        examples=[
            {
                "api_url": "https://api.example.com/users",
                "method": "GET",
                "auth_type": "bearer",
                "auth_config": {"token": "${token}"}
            },
            {
                "api_url": "https://api.example.com/orders",
                "method": "POST",
                "request_body": "{\"user_id\": \"${user_id}\", \"items\": ${items}}"
            }
        ]
    )

    # 27. Webhook节点
    configs['webhook'] = NodeConfig(
        name="Webhook",
        node_type="webhook",
        description="发送Webhook回调",
        category="外部集成",
        config_fields={
            'webhook_url': FieldConfig(
                type="string",
                label="Webhook URL",
                description="接收回调的目标URL",
                required=True,
                placeholder="https://example.com/webhook"
            ),
            'method': FieldConfig(
                type="select",
                label="请求方法",
                description="Webhook请求方法",
                required=False,
                default="POST",
                options=[
                    {"value": "POST", "label": "POST"},
                    {"value": "PUT", "label": "PUT"},
                ]
            ),
            'payload': FieldConfig(
                type="text",
                label="负载内容",
                description="要发送的数据负载",
                required=False,
                multiline=True,
                rows=6,
                default="{}"
            ),
            'headers': FieldConfig(
                type="object",
                label="请求头",
                description="额外的请求头",
                required=False,
                default={}
            ),
            'timeout': FieldConfig(
                type="number",
                label="超时时间(秒)",
                required=False,
                default=10
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="webhook_result"
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "sent": {"type": "boolean", "description": "是否发送成功"},
                "status_code": {"type": "number"},
                "response": {"description": "响应内容"},
            }
        },
        examples=[
            {
                "webhook_url": "https://hooks.example.com/notify",
                "payload": "{\"event\": \"task_completed\", \"data\": ${task_data}}"
            }
        ]
    )

    # 28. 数据库查询节点 (Database Query)
    configs['database_query'] = NodeConfig(
        name="数据库查询",
        node_type="database_query",
        description="执行数据库查询操作",
        category="外部集成",
        config_fields={
            'connection_type': FieldConfig(
                type="select",
                label="连接方式",
                description="数据库连接方式",
                required=True,
                default="project",
                options=[
                    {"value": "project", "label": "使用项目数据库"},
                    {"value": "custom", "label": "自定义连接"},
                ]
            ),
            'connection_string': FieldConfig(
                type="string",
                label="连接字符串",
                description="自定义数据库连接字符串",
                required=False,
                placeholder="mysql://user:pass@host:port/dbname",
                depends_on={"connection_type": ["custom"]}
            ),
            'query_type': FieldConfig(
                type="select",
                label="查询模式",
                description="查询方式",
                required=True,
                default="wizard",
                options=[
                    {"value": "wizard", "label": "向导模式"},
                    {"value": "sql", "label": "SQL模式"},
                ]
            ),
            'table_name': FieldConfig(
                type="string",
                label="数据表",
                description="要查询的数据表名",
                required=False,
                depends_on={"query_type": ["wizard"]}
            ),
            'wizard_config': FieldConfig(
                type="object",
                label="向导配置",
                description="向导模式下的查询配置",
                required=False,
                properties={
                    "fields": {"type": "array", "label": "查询字段", "default": ["*"]},
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                    "limit": {"type": "number", "label": "限制", "default": 100},
                    "\1": {"type": "\2", "label": "\3"},
                }
            ),
            'sql_query': FieldConfig(
                type="text",
                label="SQL语句",
                description="完整的SQL查询语句",
                required=False,
                multiline=True,
                rows=6,
                placeholder="SELECT * FROM table WHERE condition",
                depends_on={"query_type": ["sql"]}
            ),
            'parameters': FieldConfig(
                type="object",
                label="查询参数",
                description="SQL参数化查询的参数",
                required=False,
                default={}
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="query_result"
            ),
            'timeout': FieldConfig(
                type="number",
                label="超时时间(秒)",
                required=False,
                default=30
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "data": {"type": "array", "description": "查询结果"},
                "count": {"type": "number", "description": "结果数量"},
                "fields": {"type": "array", "description": "字段列表"},
            }
        },
        examples=[
            {
                "query_type": "wizard",
                "table_name": "users",
                "wizard_config": {
                    "fields": ["id", "name", "email"],
                    "limit": 10
                }
            },
            {
                "query_type": "sql",
                "sql_query": "SELECT * FROM orders WHERE user_id = :user_id",
                "parameters": {"user_id": "${user_id}"}
            }
        ]
    )

    # 29. 消息队列节点 (Message Queue)
    configs['message_queue'] = NodeConfig(
        name="消息队列",
        node_type="message_queue",
        description="发送消息到消息队列",
        category="外部集成",
        config_fields={
            'queue_type': FieldConfig(
                type="select",
                label="队列类型",
                description="使用的消息队列类型",
                required=True,
                default="rabbitmq",
                options=[
                    {"value": "rabbitmq", "label": "RabbitMQ"},
                    {"value": "kafka", "label": "Kafka"},
                    {"value": "redis", "label": "Redis队列"},
                    {"value": "activemq", "label": "ActiveMQ"},
                ]
            ),
            'queue_name': FieldConfig(
                type="string",
                label="队列名称",
                description="消息队列名称",
                required=True,
                placeholder="task_queue"
            ),
            'message': FieldConfig(
                type="text",
                label="消息内容",
                description="要发送的消息内容",
                required=True,
                multiline=True,
                rows=4,
                default="{}"
            ),
            'priority': FieldConfig(
                type="select",
                label="消息优先级",
                description="消息的优先级",
                required=False,
                default="normal",
                options=[
                    {"value": "low", "label": "低"},
                    {"value": "normal", "label": "普通"},
                    {"value": "high", "label": "高"},
                ]
            ),
            'delay': FieldConfig(
                type="number",
                label="延迟时间(秒)",
                description="消息延迟发送时间",
                required=False,
                default=0
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="queue_result"
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "sent": {"type": "boolean"},
                "message_id": {"type": "string"},
                "queue": {"type": "string"},
            }
        },
        examples=[
            {
                "queue_type": "redis",
                "queue_name": "notifications",
                "message": "{\"type\": \"alert\", \"data\": ${alert_data}}"
            }
        ]
    )

    # ==========================================================================
    # 第六部分：文档和媒体处理节点
    # ==========================================================================

    # 30. 文档提取节点 (Document Extractor)
    configs['document_extractor'] = NodeConfig(
        name="文档提取",
        node_type="document_extractor",
        description="从各种文档格式中提取文本内容",
        category="文档处理",
        config_fields={
            'document_type': FieldConfig(
                type="select",
                label="文档类型",
                description="文档的类型",
                required=False,
                default="auto",
                options=[
                    {"value": "auto", "label": "自动识别"},
                    {"value": "pdf", "label": "PDF"},
                    {"value": "doc", "label": "Word (DOC/DOCX)"},
                    {"value": "txt", "label": "纯文本"},
                    {"value": "excel", "label": "Excel"},
                    {"value": "ppt", "label": "PowerPoint"},
                    {"value": "html", "label": "HTML"},
                    {"value": "markdown", "label": "Markdown"},
                ]
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="document_content"
            ),
            'extract_images': FieldConfig(
                type="boolean",
                label="提取图片文字",
                description="是否提取图片中的文字(OCR)",
                required=False,
                default=False
            ),
            'max_pages': FieldConfig(
                type="number",
                label="最大页数",
                description="处理的最大页数",
                required=False,
                default=100,
                min_value=1
            ),
            'encoding': FieldConfig(
                type="string",
                label="文件编码",
                description="文本文件的编码",
                required=False,
                default="utf-8"
            ),
            'include_metadata': FieldConfig(
                type="boolean",
                label="包含元数据",
                description="是否包含文档元数据",
                required=False,
                default=True
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "file": {"description": "文件内容或路径"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "提取的文本内容"},
                "metadata": {"type": "object", "description": "文档元数据"},
                "pages": {"type": "number", "description": "页数"},
            }
        },
        examples=[
            {
                "document_type": "pdf",
                "extract_images": True
            }
        ]
    )

    # 31. 文件操作节点 (File Operation)
    configs['file_operation'] = NodeConfig(
        name="文件操作",
        node_type="file_operation",
        description="对文件进行各种操作",
        category="文档处理",
        config_fields={
            'operation_type': FieldConfig(
                type="select",
                label="操作类型",
                description="文件操作类型",
                required=True,
                default="read",
                options=[
                    {"value": "read", "label": "读取文件"},
                    {"value": "write", "label": "写入文件"},
                    {"value": "append", "label": "追加内容"},
                    {"value": "delete", "label": "删除文件"},
                    {"value": "copy", "label": "复制文件"},
                    {"value": "move", "label": "移动文件"},
                    {"value": "exists", "label": "检查存在"},
                    {"value": "list", "label": "列出文件"},
                ]
            ),
            'file_path': FieldConfig(
                type="string",
                label="文件路径",
                description="操作的目标文件路径",
                required=True,
                placeholder="/path/to/file.txt"
            ),
            'content': FieldConfig(
                type="text",
                label="文件内容",
                description="写入/追加的内容",
                required=False,
                multiline=True,
                depends_on={"operation_type": ["write", "append"]}
            ),
            'target_path': FieldConfig(
                type="string",
                label="目标路径",
                description="复制/移动的目标路径",
                required=False,
                depends_on={"operation_type": ["copy", "move"]}
            ),
            'encoding': FieldConfig(
                type="string",
                label="文件编码",
                description="文件的编码格式",
                required=False,
                default="utf-8"
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="file_result"
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "content": {"type": "string", "description": "读取的内容"},
                "file_path": {"type": "string", "description": "文件路径"},
            }
        },
        examples=[
            {
                "operation_type": "read",
                "file_path": "/data/input.txt"
            },
            {
                "operation_type": "write",
                "file_path": "/data/output.txt",
                "content": "${result_text}"
            }
        ]
    )

    # 32. 图片处理节点 (Image Processing)
    configs['image_processing'] = NodeConfig(
        name="图片处理",
        node_type="image_processing",
        description="对图片进行分析和处理",
        category="文档处理",
        config_fields={
            'operation': FieldConfig(
                type="select",
                label="操作类型",
                description="图片处理操作",
                required=True,
                default="analyze",
                options=[
                    {"value": "analyze", "label": "图像分析", "description": "分析图片内容"},
                    {"value": "ocr", "label": "文字识别", "description": "提取图片中的文字"},
                    {"value": "classify", "label": "图像分类", "description": "识别图片类别"},
                    {"value": "detect", "label": "目标检测", "description": "检测图片中的目标"},
                    {"value": "describe", "label": "图片描述", "description": "生成图片描述"},
                ]
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="image_result"
            ),
            'return_details': FieldConfig(
                type="boolean",
                label="返回详情",
                description="是否返回详细信息",
                required=False,
                default=True
            ),
            'language': FieldConfig(
                type="select",
                label="OCR语言",
                description="OCR识别的语言",
                required=False,
                default="zh+en",
                options=[
                    {"value": "zh", "label": "中文"},
                    {"value": "en", "label": "英文"},
                    {"value": "zh+en", "label": "中英混合"},
                ],
                depends_on={"operation": ["ocr"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "image": {"description": "图片数据或路径"}
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"description": "处理结果"},
                "confidence": {"type": "number", "description": "置信度"},
            }
        },
        examples=[
            {
                "operation": "ocr",
                "language": "zh+en"
            }
        ]
    )

    # 33. 音频处理节点 (Audio Processing)
    configs['audio_processing'] = NodeConfig(
        name="音频处理",
        node_type="audio_processing",
        description="处理音频相关任务",
        category="文档处理",
        config_fields={
            'operation': FieldConfig(
                type="select",
                label="操作类型",
                description="音频处理操作",
                required=True,
                default="transcribe",
                options=[
                    {"value": "transcribe", "label": "语音转文字",
                        "description": "语音识别转文字"},
                    {"value": "translate", "label": "语音翻译",
                        "description": "语音翻译成其他语言"},
                    {"value": "tts", "label": "文字转语音", "description": "文本转语音合成"},
                    {"value": "analyze", "label": "音频分析", "description": "分析音频特征"},
                ]
            ),
            'language': FieldConfig(
                type="string",
                label="语言",
                description="语音识别的语言",
                required=False,
                default="zh-CN"
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="audio_result"
            ),
            'enable_srt': FieldConfig(
                type="boolean",
                label="生成字幕",
                description="是否生成SRT字幕文件",
                required=False,
                default=False
            ),
            'voice': FieldConfig(
                type="string",
                label="语音类型",
                description="TTS的语音类型",
                required=False,
                default="default",
                depends_on={"operation": ["tts"]}
            ),
            'speed': FieldConfig(
                type="number",
                label="语速",
                description="TTS的语速(0.5-2.0)",
                required=False,
                default=1.0,
                min_value=0.5,
                max_value=2.0,
                depends_on={"operation": ["tts"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {
                "audio": {"description": "音频数据或路径"},
                "text": {"type": "string", "description": "TTS的输入文本"},
            }
        },
        output_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "识别的文字"},
                "language": {"type": "string", "description": "检测的语言"},
                "duration": {"type": "number", "description": "音频时长(秒)"},
            }
        },
        examples=[
            {
                "operation": "transcribe",
                "language": "zh-CN"
            }
        ]
    )

    # ==========================================================================
    # 第七部分：其他功能节点
    # ==========================================================================

    # 34. 代码块执行节点 (Code Execution)
    configs['code_execution'] = NodeConfig(
        name="代码执行",
        node_type="code_execution",
        description="执行Python代码块",
        category="其他功能",
        config_fields={
            'code': FieldConfig(
                type="code",
                label="代码",
                description="要执行的Python代码",
                required=True,
                language="python",
                multiline=True,
                rows=15,
                placeholder="# 输入变量: input_data\n# 输出变量: result\n\nresult = {\n    'processed': True,\n    'data': input_data\n}"
            ),
            'input_variables': FieldConfig(
                type="array",
                label="输入变量",
                description="代码中可以使用的输入变量",
                required=False,
                default=[]
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                description="代码执行结果存储的变量名",
                required=True,
                default="result"
            ),
            'timeout': FieldConfig(
                type="number",
                label="超时时间(秒)",
                description="代码执行超时时间",
                required=False,
                default=30,
                min_value=1,
                max_value=300
            ),
            'error_handling': FieldConfig(
                type="select",
                label="错误处理",
                description="代码执行出错时的处理",
                required=False,
                default="error",
                options=[
                    {"value": "error", "label": "报错", "description": "直接抛出错误"},
                    {"value": "continue", "label": "继续",
                        "description": "继续执行并返回错误信息"},
                    {"value": "default", "label": "使用默认值", "description": "使用默认输出"},
                ]
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"description": "代码执行结果"},
                "success": {"type": "boolean"},
                "error": {"type": "string"},
            }
        },
        examples=[
            {
                "code": "# 数据处理示例\ndata = input_data['items']\ntotal = sum(item['price'] for item in data)\nresult = {'total': total, 'count': len(data)}",
                "input_variables": ["input_data"]
            }
        ]
    )

    # 35. 代码块节点 (Code Block)
    configs['code_block'] = NodeConfig(
        name="代码块",
        node_type="code_block",
        description="用于组织代码片段的容器节点",
        category="其他功能",
        config_fields={
            'language': FieldConfig(
                type="select",
                label="代码语言",
                description="代码的语言类型",
                required=False,
                default="python",
                options=[
                    {"value": "python", "label": "Python"},
                    {"value": "javascript", "label": "JavaScript"},
                    {"value": "bash", "label": "Bash"},
                    {"value": "sql", "label": "SQL"},
                ]
            ),
            'code': FieldConfig(
                type="text",
                label="代码内容",
                description="代码块内容",
                required=False,
                multiline=True,
                rows=10
            ),
            'description': FieldConfig(
                type="string",
                label="描述",
                description="代码块的功能描述",
                required=False
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {}
        },
        examples=[
            {"description": "数据预处理", "language": "python"}
        ]
    )

    # 36. 工具调用节点 (Tool Calling)
    configs['tool_calling'] = NodeConfig(
        name="工具调用",
        node_type="tool_calling",
        description="调用外部工具或API",
        category="其他功能",
        config_fields={
            'tool_name': FieldConfig(
                type="string",
                label="工具名称",
                description="要调用的工具名称",
                required=True,
                placeholder="search_weather"
            ),
            'tool_type': FieldConfig(
                type="select",
                label="工具类型",
                description="工具的类型",
                required=True,
                default="function",
                options=[
                    {"value": "function", "label": "函数工具"},
                    {"value": "api", "label": "API工具"},
                    {"value": "plugin", "label": "插件工具"},
                ]
            ),
            'parameters': FieldConfig(
                type="object",
                label="工具参数",
                description="调用工具的参数",
                required=False,
                default={}
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="tool_result"
            ),
            'timeout': FieldConfig(
                type="number",
                label="超时时间(秒)",
                required=False,
                default=60
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"description": "工具执行结果"},
                "success": {"type": "boolean"},
                "error": {"type": "string"},
            }
        },
        examples=[
            {
                "tool_name": "search_weather",
                "parameters": {"city": "${city}"}
            }
        ]
    )

    # 37. 通知节点 (Notification)
    configs['notification'] = NodeConfig(
        name="通知",
        node_type="notification",
        description="发送各类通知消息",
        category="其他功能",
        config_fields={
            'notification_type': FieldConfig(
                type="select",
                label="通知类型",
                description="选择通知发送方式",
                required=True,
                default="email",
                options=[
                    {"value": "email", "label": "邮件通知"},
                    {"value": "sms", "label": "短信通知"},
                    {"value": "webhook", "label": "Webhook回调"},
                    {"value": "in_app", "label": "站内通知"},
                    {"value": "dingtalk", "label": "钉钉通知"},
                    {"value": "wechat", "label": "企业微信"},
                    {"value": "ticket", "label": "创建工单"},
                    {"value": "log", "label": "记录日志"},
                ]
            ),
            'title': FieldConfig(
                type="string",
                label="通知标题",
                description="通知的标题",
                required=True,
                placeholder="工作流通知"
            ),
            'message': FieldConfig(
                type="text",
                label="通知内容",
                description="通知的消息内容",
                required=True,
                multiline=True,
                rows=6
            ),
            'priority': FieldConfig(
                type="select",
                label="优先级",
                description="通知优先级",
                required=False,
                default="medium",
                options=[
                    {"value": "low", "label": "低"},
                    {"value": "medium", "label": "中"},
                    {"value": "high", "label": "高"},
                    {"value": "urgent", "label": "紧急"},
                ]
            ),
            'trigger_type': FieldConfig(
                type="select",
                label="触发类型",
                description="什么情况下发送通知",
                required=False,
                default="always",
                options=[
                    {"value": "always", "label": "始终发送"},
                    {"value": "condition", "label": "满足条件时"},
                    {"value": "on_error", "label": "出错时"},
                    {"value": "on_success", "label": "成功时"},
                ]
            ),
            'condition': FieldConfig(
                type="string",
                label="触发条件",
                description="发送通知的条件表达式",
                required=False,
                placeholder="data.status == 'failed'",
                depends_on={"trigger_type": ["condition"]}
            ),
            # 邮件配置
            'recipients': FieldConfig(
                type="array",
                label="收件人",
                description="通知接收者列表",
                required=False,
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "\1": {"type": "\2", "label": "\3"},
                },
                depends_on={"notification_type": ["email", "in_app"]}
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "sent": {"type": "boolean"},
                "sent_at": {"type": "string"},
                "recipient_count": {"type": "number"},
            }
        },
        examples=[
            {
                "notification_type": "email",
                "title": "工作流执行完成",
                "message": "工作流${workflow_name}已执行完成，结果：${result}",
                "priority": "medium"
            }
        ]
    )

    # 38. 问答交互节点 (QA Interaction)
    configs['qa_interaction'] = NodeConfig(
        name="问答交互",
        node_type="qa_interaction",
        description="与用户进行问答交互",
        category="其他功能",
        config_fields={
            'question': FieldConfig(
                type="string",
                label="问题",
                description="向用户展示的问题",
                required=True,
                placeholder="请确认您的选择："
            ),
            'question_type': FieldConfig(
                type="select",
                label="问题类型",
                description="问题的类型",
                required=True,
                default="text",
                options=[
                    {"value": "text", "label": "文本输入"},
                    {"value": "choice", "label": "单选"},
                    {"value": "multi_choice", "label": "多选"},
                    {"value": "confirm", "label": "确认/取消"},
                ]
            ),
            'options': FieldConfig(
                type="array",
                label="选项",
                description="选择题的选项",
                required=False,
                properties={
                    "\1": {"type": "\2", "label": "\3"},
                    "label": {"type": "string", "label": "选项标签"},
                },
                depends_on={"question_type": ["choice", "multi_choice"]}
            ),
            'default_value': FieldConfig(
                type="string",
                label="默认值",
                description="用户未回答时的默认值",
                required=False
            ),
            'timeout': FieldConfig(
                type="number",
                label="等待时间(秒)",
                description="等待用户回答的超时时间",
                required=False,
                default=300
            ),
            'output_variable': FieldConfig(
                type="string",
                label="输出变量名",
                required=True,
                default="answer"
            ),
        },
        input_schema={
            "type": "object",
            "properties": {}
        },
        output_schema={
            "type": "object",
            "properties": {
                "answer": {"description": "用户的回答"},
                "answered": {"type": "boolean", "description": "是否已回答"},
                "answered_at": {"type": "string", "description": "回答时间"},
            }
        },
        examples=[
            {
                "question": "请选择处理方式：",
                "question_type": "choice",
                "options": [
                    {"value": "approve", "label": "批准"},
                    {"value": "reject", "label": "拒绝"},
                    {"value": "pending", "label": "待定"},
                ]
            }
        ]
    )

    return configs


def get_node_config(node_type: str) -> Optional[NodeConfig]:
    """获取指定节点类型的配置"""
    configs = get_all_node_configs()
    return configs.get(node_type)


def validate_node_config(node_type: str, config: Dict) -> tuple:
    """
    验证节点配置
    返回: (is_valid, errors, validated_config)
    """
    node_config = get_node_config(node_type)
    if not node_config:
        return False, [f"未知节点类型: {node_type}"], config

    errors = []
    validated = config.copy()

    # 检查必填字段
    for field_name, field_config in node_config.config_fields.items():
        if field_config.required and not config.get(field_name):
            # 检查是否有默认值
            if field_config.default is None:
                errors.append(f"字段 '{field_config.label}' 是必填的")

    return len(errors) == 0, errors, validated


def get_node_input_schema(node_type: str) -> Dict:
    """获取节点的输入Schema"""
    node_config = get_node_config(node_type)
    if node_config:
        return node_config.input_schema
    return {"type": "object", "properties": {}}


def get_node_output_schema(node_type: str) -> Dict:
    """获取节点的输出Schema"""
    node_config = get_node_config(node_type)
    if node_config:
        return node_config.output_schema
    return {"type": "object", "properties": {}}


def get_node_config_schema(node_type: str) -> Dict:
    """
    获取节点的完整配置Schema，用于前端动态表单生成
    返回前端可直接使用的配置字段定义
    """
    node_config = get_node_config(node_type)
    if not node_config:
        return {}

    schema = {}

    for field_name, field_config in node_config.config_fields.items():
        field_schema = {
            "type": field_config.type,
            "label": field_config.label,
            "description": field_config.description,
            "required": field_config.required,
        }

        # 添加默认值
        if field_config.default is not None:
            field_schema["default"] = field_config.default

        # 添加placeholder
        if field_config.placeholder:
            field_schema["placeholder"] = field_config.placeholder

        # 添加选项（针对select类型）
        if field_config.type == "select" and field_config.options:
            field_schema["options"] = field_config.options

        # 添加数值范围限制
        if field_config.min_value is not None:
            field_schema["min_value"] = field_config.min_value
        if field_config.max_value is not None:
            field_schema["max_value"] = field_config.max_value

        # 添加长度限制
        if field_config.min_length is not None:
            field_schema["min_length"] = field_config.min_length
        if field_config.max_length is not None:
            field_schema["max_length"] = field_config.max_length

        # 添加多行文本设置
        if field_config.multiline:
            field_schema["multiline"] = True
            field_schema["rows"] = field_config.rows

        # 添加代码语言设置
        if field_config.language:
            field_schema["language"] = field_config.language

        # 添加依赖关系
        if field_config.depends_on:
            field_schema["depends_on"] = field_config.depends_on

        # 添加验证规则
        if field_config.validation:
            field_schema["validation"] = field_config.validation

        # 添加tooltip
        if field_config.tooltip:
            field_schema["tooltip"] = field_config.tooltip

        # 添加属性定义（针对array类型）
        if field_config.properties:
            field_schema["properties"] = field_config.properties

        schema[field_name] = field_schema

    return schema


def get_node_full_config(node_type: str) -> Dict:
    """
    获取节点的完整配置信息，包括所有配置字段、输入输出Schema
    """
    node_config = get_node_config(node_type)
    if not node_config:
        return {}

    return {
        "name": node_config.name,
        "node_type": node_config.node_type,
        "description": node_config.description,
        "category": node_config.category,
        "config_fields": get_node_config_schema(node_type),
        "input_schema": node_config.input_schema,
        "output_schema": node_config.output_schema,
        "examples": node_config.examples,
    }


def get_nodes_by_category() -> Dict[str, List[NodeConfig]]:
    """按分类获取所有节点"""
    configs = get_all_node_configs()
    categories = {}
    for node_type, config in configs.items():
        cat = config.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(config)
    return categories


# 导出常用函数
__all__ = [
    'get_all_node_configs',
    'get_node_config',
    'validate_node_config',
    'get_node_input_schema',
    'get_node_output_schema',
    'get_node_config_schema',
    'get_node_full_config',
    'get_nodes_by_category',
    'NodeConfig',
    'FieldConfig',
]
