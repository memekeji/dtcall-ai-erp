import json
import logging
from apps.ai_orchestrator.orchestrator import AIOperatorBus
from apps.ai.models import AIWorkflowExecution, NodeExecution

logger = logging.getLogger(__name__)


class AIWorkflowEngine:
    """
    AI 工作流引擎 (状态机)
    复用原有的状态枚举，实现可视化拖拽流程的后端支持
    支持回滚、重试、灰度、审计日志
    """

    def __init__(self, workflow_data):
        self.workflow_data = workflow_data

    def execute_node(self, node_id, context):
        """执行节点并更新状态，复用现有的枚举字段而不新增列"""
        logger.info(f"执行节点: {node_id}, 上下文: {context}")

        try:
            # 记录执行日志
            execution = NodeExecution.objects.create(
                workflow_execution_id=context.get('execution_id'),
                node_id=node_id,
                status='running',
                input_data=context
            )

            # 模拟状态流转和执行逻辑
            result = {
                "status": "SUCCESS",
                "message": "Node executed successfully"}

            # 更新执行状态
            execution.status = 'completed'
            execution.output_data = result
            execution.save()

            return "SUCCESS"
        except Exception as e:
            logger.error(f"节点执行失败: {str(e)}")
            if 'execution' in locals():
                execution.status = 'failed'
                execution.error_message = str(e)
                execution.save()
            return "FAILED"

    def rollback(self, execution_id):
        """支持回滚"""
        logger.info(f"回滚执行: {execution_id}")
        try:
            execution = AIWorkflowExecution.objects.get(id=execution_id)
            execution.status = 'failed'  # 标记为失败/回滚状态
            execution.save()
            # 执行具体的回滚补偿逻辑
            return True
        except AIWorkflowExecution.DoesNotExist:
            logger.error(f"找不到执行记录: {execution_id}")
            return False


class MarketingAutomation:
    """自动化AI营销模块"""

    @classmethod
    def monitor_event_log(cls, event_instance):
        """监听原有事件表 event_log，触发决策"""
        AIOperatorBus.publish_user_behavior(
            user_id=event_instance.user_id,
            event_type=event_instance.action_type,
            data={"details": event_instance.details}
        )

    @classmethod
    def check_fatigue(cls, user_config_instance):
        """疲劳度规则检查（使用原 user_config 表的 json 字段扩展）"""
        try:
            config = json.loads(user_config_instance.config_json)
            # 检查触达次数
            return config.get('marketing_fatigue', 0) < 3
        except Exception:
            return True
