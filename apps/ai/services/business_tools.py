import json
from apps.ai.utils.tool_registry import tool_registry

@tool_registry.register(
    name="get_current_time",
    description="获取系统当前时间，用于回答与时间相关的问题",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    }
)
def get_current_time():
    from datetime import datetime
    return f"当前系统时间是: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

@tool_registry.register(
    name="analyze_project_risk",
    description="分析指定项目的风险情况",
    parameters={
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "项目ID"
            }
        },
        "required": ["project_id"]
    }
)
def analyze_project_risk(project_id: str):
    try:
        from apps.project.models import Project, Task
        project = Project.objects.get(id=project_id)
        
        project_data = {
            "name": project.name,
            "status": project.status,
            "start_date": str(project.start_date),
            "end_date": str(project.end_date)
        }
        
        tasks = Task.objects.filter(project=project)
        task_data = [
            {"name": t.name, "status": t.status, "progress": t.progress}
            for t in tasks[:10]
        ]
        
        from apps.ai.utils.analysis_tools import ProjectAnalysisTool
        tool = ProjectAnalysisTool()
        result = tool.predict_risk(project_data, task_data, [])
        return result.get('analysis', '分析失败')
    except Exception as e:
        return f"获取项目信息失败: {str(e)}"

@tool_registry.register(
    name="fill_frontend_form",
    description="当用户明确要求填写表单、输入数据、自动填表时，调用此工具将数据发送到前端页面进行智能填充",
    parameters={
        "type": "object",
        "properties": {
            "form_data": {
                "type": "object",
                "description": "要填充的表单数据键值对，键为输入框的字段名、中文名或placeholder，值为要填入的内容"
            }
        },
        "required": ["form_data"]
    }
)
def fill_frontend_form(form_data: dict):
    """
    返回特殊的标记字符串，前端Chat页面接收到后解析并通过postMessage通知父页面SDK执行
    """
    payload = json.dumps({"action": "fill_form", "data": form_data}, ensure_ascii=False)
    # AI 可能会将这个字符串直接返回给用户，或者作为工具结果被模型二次总结。
    # 我们将其设计为一个易于被前端正则捕获的结构
    return f"我已经为您生成了表单数据，正在自动填充：\n```ui_action\n{payload}\n```"
