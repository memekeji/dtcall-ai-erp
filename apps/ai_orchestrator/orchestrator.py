import logging
from django.dispatch import Signal, receiver

logger = logging.getLogger(__name__)

# 事件总线信号定义
marketing_event_signal = Signal()
user_behavior_signal = Signal()


class AIOperatorBus:
    """多智能体编排层 - 事件总线串联"""

    @classmethod
    def publish_user_behavior(cls, user_id, event_type, data):
        """发布用户行为事件"""
        logger.info(f"发布行为事件: {user_id}, {event_type}")
        user_behavior_signal.send(
            sender=cls,
            user_id=user_id,
            event_type=event_type,
            data=data)

    @classmethod
    def publish_marketing_decision(cls, user_id, content):
        """发布营销决策事件"""
        logger.info(f"发布营销决策: {user_id}")
        marketing_event_signal.send(
            sender=cls, user_id=user_id, content=content)


class BaseAgent:
    """Agent基类"""

    def execute(self, *args, **kwargs):
        raise NotImplementedError


class UserProfileAgent(BaseAgent):
    """用户画像Agent"""

    def execute(self, user_id):
        # 提取用户画像，复用现有表结构
        return {"user_id": user_id, "tags": ["活跃", "高价值"]}


class ContentGenerationAgent(BaseAgent):
    """内容生成Agent"""

    def execute(self, profile):
        # 根据画像生成内容
        return f"尊贵的客户，根据您的偏好为您推荐：特惠套餐！"


class MarketingDecisionAgent(BaseAgent):
    """营销决策Agent"""

    def execute(self, user_id, event_type):
        profile_agent = UserProfileAgent()
        profile = profile_agent.execute(user_id)

        content_agent = ContentGenerationAgent()
        content = content_agent.execute(profile)

        AIOperatorBus.publish_marketing_decision(user_id, content)


@receiver(user_behavior_signal)
def handle_user_behavior(sender, user_id, event_type, data, **kwargs):
    # 触发营销Agent
    agent = MarketingDecisionAgent()
    agent.execute(user_id, event_type)


@receiver(marketing_event_signal)
def handle_marketing_execution(sender, user_id, content, **kwargs):
    # 复用消息通道发送
    logger.info(f"执行自动营销: 给 {user_id} 发送 {content}")
