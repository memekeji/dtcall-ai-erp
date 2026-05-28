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

    INTENT_MAPPING = {
        'DATA_QUERY': 'data_query',
        'DATA_CREATE': 'data_create',
        'DATA_UPDATE': 'data_update',
        'DATA_DELETE': 'data_delete',
        'KNOWLEDGE_BASE': 'knowledge_base',
        'AI_CHAT': 'ai_chat',
        'UI_ACTION': 'ui_action',
    }

    INTENT_TYPES = {
        'data_query': '数据查询',
        'data_create': '数据创建',
        'data_update': '数据修改',
        'data_delete': '数据删除',
        'knowledge_base': '知识库',
        'ai_chat': 'AI对话',
        'ui_action': '界面操作',
    }

    UNSAFE_INTENTS = {'DATA_CREATE', 'DATA_UPDATE', 'DATA_DELETE'}

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
        new_intent = new_result.get('intent', 'AI_CHAT')
        old_intent = self.INTENT_MAPPING.get(new_intent, 'ai_chat')

        is_unsafe = new_intent in self.UNSAFE_INTENTS or new_result.get('action') in {'create', 'update', 'delete'}

        return {
            'intent': old_intent,
            'intent_type': old_intent,
            'raw_intent': new_intent,
            'confidence': new_result.get('confidence', 0.0),
            'entities': new_result.get('entities', {}),
            'requires_confirmation': True if is_unsafe else new_result.get('requires_confirmation', False),
            'fallback_options': new_result.get('fallback_options', []),
            'action': new_result.get('action'),
            'data_type': new_result.get('data_type'),
            'time_range': new_result.get('time_range'),
            'status': new_result.get('status'),
            'customer_name': new_result.get('customer_name'),
            'source': new_result.get('source'),
            'ai_available': new_result.get('ai_available', False),
            'model_provider': new_result.get('model_provider'),
            'model_name': new_result.get('model_name'),
            'reasoning': new_result.get('reasoning', ''),
            'safe_to_execute': not is_unsafe,
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
        return {
            'intent': 'ai_chat',
            'intent_type': 'ai_chat',
            'raw_intent': 'AI_CHAT',
            'confidence': 0.0,
            'entities': {},
            'requires_confirmation': True,
            'fallback_options': [
                {'text': '按普通对话继续', 'intent': 'ai_chat', 'action': 'select'},
                {'text': '请补充要查询的数据范围', 'intent': 'data_query', 'action': 'select'},
                {'text': '重新描述需求', 'intent': None, 'action': 'retry'}
            ],
            'action': 'chat',
            'data_type': None,
            'time_range': None,
            'status': None,
            'customer_name': None,
            'source': 'error',
            'ai_available': False,
            'model_provider': None,
            'model_name': None,
            'reasoning': '意图识别服务异常',
            'safe_to_execute': False,
        }


unified_intent_service = UnifiedIntentService()
