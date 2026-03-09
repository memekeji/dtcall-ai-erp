"""
意图识别服务（已重构）
使用新的 AI 意图分类器替代旧的关键词匹配方式
"""

import logging
from typing import Dict, Any
from django.contrib.auth.models import User
from apps.ai.services.ai_intent_classifier import ai_intent_classifier
from apps.ai.services.enhanced_intent_service import enhanced_intent_service
from apps.ai.services.intent_optimization_service import intent_optimization_service

logger = logging.getLogger(__name__)


# 向后兼容的常量定义
INTENT_TYPES = {
    'DATA_QUERY': 'data_query',
    'DATA_CREATE': 'data_create',
    'DATA_UPDATE': 'data_update',
    'KNOWLEDGE_BASE': 'knowledge_base',
    'AI_CHAT': 'ai_chat'
}

CONFIDENCE_THRESHOLDS = {
    'HIGH': 0.85,
    'MEDIUM': 0.65,
    'LOW': 0.40,
    'FAIL': 0.40
}


class IntentRecognitionService:
    """
    意图识别服务类（重构版）
    基于 AI 大模型的意图识别，支持智能降级
    """
    
    def __init__(self):
        self.classifier = ai_intent_classifier
        self.enhanced_service = enhanced_intent_service
        self.optimization_service = intent_optimization_service
    
    def recognize_intent(self, user: User, query: str) -> Dict[str, Any]:
        """
        识别用户意图（兼容旧接口）
        
        Args:
            user: 当前用户
            query: 用户查询文本
            
        Returns:
            Dict[str, Any]: 意图识别结果
        """
        try:
            result = self.classifier.classify_intent(user, query)
            
            old_format = {
                'intent': self._convert_intent(result.get('intent', 'AI_CHAT')),
                'confidence': result.get('confidence', 0.0),
                'entities': result.get('entities', {}),
                'requires_confirmation': result.get('requires_confirmation', False),
                'fallback_options': result.get('fallback_options', []),
                'action': result.get('action'),
                'data_type': result.get('data_type'),
                'time_range': result.get('time_range'),
                'status': result.get('status'),
                'customer_name': result.get('customer_name'),
            }
            
            self.optimization_service.log_recognition(
                user=user,
                query=query,
                recognition_result=result,
                is_correct=True
            )
            
            logger.info(f"意图识别成功：query={query[:50]}, intent={result.get('intent')}, "
                       f"confidence={result.get('confidence', 0):.2f}")
            
            return old_format
            
        except Exception as e:
            logger.error(f"意图识别失败：{str(e)}")
            return self._create_error_result(query)
    
    def _convert_intent(self, new_intent: str) -> str:
        """将新意图类型转换为旧格式"""
        mapping = {
            'DATA_QUERY': 'data_query',
            'DATA_CREATE': 'data_create',
            'DATA_UPDATE': 'data_update',
            'KNOWLEDGE_BASE': 'knowledge_base',
            'AI_CHAT': 'ai_chat'
        }
        return mapping.get(new_intent, 'ai_chat')
    
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
    
    def _handle_ai_chat(self, user: User, message: str) -> Dict[str, Any]:
        """
        处理 AI 对话（兼容旧接口）
        使用增强服务处理
        """
        return self.enhanced_service._handle_ai_chat(user, message)
    
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


intent_recognition_service = IntentRecognitionService()
