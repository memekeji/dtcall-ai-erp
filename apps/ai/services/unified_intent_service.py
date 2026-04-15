"""
统一意图识别服务
整合新旧意图识别系统，提供统一的接口
"""

import logging
from typing import Dict, Any
from django.contrib.auth.models import User
from apps.ai.services.ai_intent_classifier import ai_intent_classifier
from apps.ai.services.enhanced_intent_service import enhanced_intent_service
from apps.ai.services.intent_optimization_service import intent_optimization_service

logger = logging.getLogger(__name__)


class UnifiedIntentService:
    """
    统一意图识别服务
    兼容新旧系统，优先使用新的 AI 分类器
    """

    # 意图类型映射（新->旧）
    INTENT_MAPPING = {
        'DATA_QUERY': 'data_query',
        'DATA_CREATE': 'data_query',
        'DATA_UPDATE': 'data_query',
        'KNOWLEDGE_BASE': 'knowledge_base',
        'AI_CHAT': 'ai_chat',
    }

    def __init__(self):
        self.new_classifier = ai_intent_classifier
        self.enhanced_service = enhanced_intent_service
        self.optimization_service = intent_optimization_service

    def recognize_intent(self, user: User, query: str) -> Dict[str, Any]:
        """
        识别用户意图（兼容旧接口）

        Args:
            user: 当前用户
            query: 用户查询文本

        Returns:
            Dict[str, Any]: 意图识别结果（兼容旧格式）
        """
        try:
            result = self.new_classifier.classify_intent(user, query)

            old_format_result = self._convert_to_old_format(result)

            self.optimization_service.log_recognition(
                user=user,
                query=query,
                recognition_result=result,
                is_correct=True
            )

            logger.info(
                f"意图识别成功：query={query[:50]}, intent={result.get('intent')}, "
                f"confidence={result.get('confidence', 0):.2f}")

            return old_format_result

        except Exception as e:
            logger.error(f"意图识别失败：{str(e)}")
            return self._create_error_result(query)

    def _convert_to_old_format(
            self, new_result: Dict[str, Any]) -> Dict[str, Any]:
        """将新格式转换为旧格式（兼容现有代码）"""
        new_intent = new_result.get('intent', 'AI_CHAT')
        old_intent = self.INTENT_MAPPING.get(new_intent, 'ai_chat')

        return {
            'intent': old_intent,
            'confidence': new_result.get('confidence', 0.0),
            'entities': new_result.get('entities', {}),
            'requires_confirmation': new_result.get('requires_confirmation', False),
            'fallback_options': new_result.get('fallback_options', []),
            'action': new_result.get('action'),
            'data_type': new_result.get('data_type'),
            'time_range': new_result.get('time_range'),
            'status': new_result.get('status'),
            'customer_name': new_result.get('customer_name'),
        }

    def process_request(self, user: User, query: str) -> Dict[str, Any]:
        """
        处理用户请求（推荐使用）

        Args:
            user: 当前用户
            query: 用户查询文本

        Returns:
            Dict[str, Any]: 处理结果
        """
        return self.enhanced_service.process_user_request(user, query)

    def _create_error_result(self, query: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            'intent': 'ai_chat',
            'confidence': 0.5,
            'entities': {},
            'requires_confirmation': True,
            'fallback_options': [
                {'text': '查询项目数据', 'intent': 'data_query', 'action': 'select'},
                {'text': '调用知识库', 'intent': 'knowledge_base', 'action': 'select'},
                {'text': '纯 AI 对话', 'intent': 'ai_chat', 'action': 'select'},
                {'text': '重新描述需求', 'intent': None, 'action': 'retry'}
            ]
        }


unified_intent_service = UnifiedIntentService()
