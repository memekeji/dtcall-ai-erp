"""
增强的意图识别服务
整合 AI 意图分类器、数据权限控制和自动化数据处理功能
"""

import logging
from typing import Dict, Any, List, Optional
from django.contrib.auth.models import User
from django.core.cache import cache
from apps.ai.services.ai_intent_classifier import ai_intent_classifier
from apps.ai.services.query_service import query_service
from apps.system.middleware.data_permission_middleware import PermissionChecker

logger = logging.getLogger(__name__)


class EnhancedIntentService:
    """
    增强的意图识别服务
    提供完整的意图识别、权限验证和数据处理能力
    """
    
    def __init__(self):
        self.classifier = ai_intent_classifier
        self.query_service = query_service
    
    def process_user_request(self, user: User, query: str) -> Dict[str, Any]:
        """
        处理用户请求的完整流程
        
        Args:
            user: 当前用户
            query: 用户查询文本
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            intent_result = self.classifier.classify_intent(user, query)
            
            if not intent_result.get('intent'):
                return self._create_error_response('无法识别您的意图，请重新描述您的需求')
            
            permission_result = self._check_data_permission(user, intent_result)
            if not permission_result['has_permission']:
                return self._create_permission_denied_response(intent_result, permission_result)
            
            if intent_result['confidence'] < 0.65:
                return self._create_confirmation_response(intent_result, query)
            
            execution_result = self._execute_intent(user, intent_result, query)
            
            return execution_result
            
        except Exception as e:
            logger.error(f"处理用户请求失败：{str(e)}")
            return self._create_error_response(f'处理请求时发生错误：{str(e)}')
    
    def _check_data_permission(self, user: User, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查用户数据权限
        
        Args:
            user: 当前用户
            intent_result: 意图识别结果
            
        Returns:
            Dict[str, Any]: 权限检查结果
        """
        if user.is_superuser:
            return {
                'has_permission': True,
                'message': '超级管理员权限',
                'data_scope': 'all'
            }
        
        intent_type = intent_result.get('intent')
        data_type = intent_result.get('data_type')
        action = intent_result.get('action')
        
        if intent_type == 'AI_CHAT':
            return {
                'has_permission': True,
                'message': '对话无需权限',
                'data_scope': 'chat'
            }
        
        if intent_type == 'KNOWLEDGE_BASE':
            return {
                'has_permission': True,
                'message': '知识库查询权限',
                'data_scope': 'knowledge'
            }
        
        if not data_type:
            return {
                'has_permission': True,
                'message': '通用查询权限',
                'data_scope': 'general'
            }
        
        permission_map = {
            'customer': 'customer.view_customer',
            'order': 'customer.view_customerorder',
            'contract': 'contract.view_contract',
            'project': 'project.view_project',
            'invoice': 'customer.view_customerinvoice',
            'employee': 'user.view_employeefile',
            'department': 'user.view_department',
            'finance': 'finance.view_finance',
            'production': 'production.view_production',
        }
        
        required_permission = permission_map.get(data_type)
        
        if not required_permission:
            return {
                'has_permission': True,
                'message': f'{data_type} 类型无需特殊权限',
                'data_scope': 'general'
            }
        
        has_perm = user.has_perm(required_permission)
        
        if not has_perm:
            return {
                'has_permission': False,
                'message': f'您没有权限访问{data_type}数据',
                'required_permission': required_permission,
                'data_scope': 'none'
            }
        
        data_scope = self._get_user_data_scope(user, data_type)
        
        return {
            'has_permission': True,
            'message': '权限验证通过',
            'data_scope': data_scope,
            'action': action
        }
    
    def _get_user_data_scope(self, user: User, data_type: str) -> str:
        """
        获取用户的数据范围
        
        Args:
            user: 当前用户
            data_type: 数据类型
            
        Returns:
            str: 数据范围描述
        """
        try:
            data_scope = PermissionChecker.get_user_data_scope(user)
            return data_scope.get('scope', 'self')
        except Exception as e:
            logger.error(f"获取数据范围失败：{str(e)}")
            return 'self'
    
    def _execute_intent(self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        执行意图处理
        
        Args:
            user: 当前用户
            intent_result: 意图识别结果
            query: 原始查询
            
        Returns:
            Dict[str, Any]: 执行结果
        """
        intent_type = intent_result.get('intent')
        action = intent_result.get('action')
        data_type = intent_result.get('data_type')
        
        if intent_type == 'AI_CHAT':
            return self._handle_ai_chat(user, query)
        
        if intent_type == 'KNOWLEDGE_BASE':
            return self._handle_knowledge_base(user, query)
        
        if intent_type in ['DATA_QUERY', 'DATA_CREATE', 'DATA_UPDATE']:
            if action == 'create':
                return self._handle_data_create(user, intent_result, query)
            elif action == 'update':
                return self._handle_data_update(user, intent_result, query)
            else:
                return self._handle_data_query(user, intent_result, query)
        
        return self._handle_data_query(user, intent_result, query)
    
    def _handle_data_query(self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        处理数据查询
        
        Args:
            user: 当前用户
            intent_result: 意图识别结果
            query: 原始查询
            
        Returns:
            Dict[str, Any]: 查询结果
        """
        try:
            result = self.query_service.process_query(user, query)
            
            result['intent_type'] = intent_result.get('intent')
            result['confidence'] = intent_result.get('confidence')
            result['entities'] = intent_result.get('entities')
            
            return result
            
        except Exception as e:
            logger.error(f"数据查询失败：{str(e)}")
            return self._create_error_response(f'查询失败：{str(e)}')
    
    def _handle_data_create(self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        处理数据创建
        
        Args:
            user: 当前用户
            intent_result: 意图识别结果
            query: 原始查询
            
        Returns:
            Dict[str, Any]: 创建结果
        """
        data_type = intent_result.get('data_type')
        customer_name = intent_result.get('customer_name')
        
        if not data_type:
            return self._create_error_response('无法确定要创建的数据类型')
        
        if data_type == 'order' and customer_name:
            return self.query_service.handle_add_order({'customer_name': customer_name}, user)
        
        if data_type == 'followup' and customer_name:
            return self.query_service.handle_add_followup({'customer_name': customer_name}, user)
        
        return self._create_error_response(f'暂不支持创建{data_type}数据，请通过界面操作')
    
    def _handle_data_update(self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        处理数据修改
        
        Args:
            user: 当前用户
            intent_result: 意图识别结果
            query: 原始查询
            
        Returns:
            Dict[str, Any]: 修改结果
        """
        return self._create_error_response('数据修改功能暂不支持，请通过界面操作')
    
    def _handle_knowledge_base(self, user: User, query: str) -> Dict[str, Any]:
        """
        处理知识库查询
        
        Args:
            user: 当前用户
            query: 原始查询
            
        Returns:
            Dict[str, Any]: 查询结果
        """
        return {
            'success': True,
            'message': '知识库功能正在开发中',
            'intent_type': 'KNOWLEDGE_BASE',
            'result': '知识库查询功能即将上线，敬请期待'
        }
    
    def _handle_ai_chat(self, user: User, query: str) -> Dict[str, Any]:
        """
        处理 AI 对话
        
        Args:
            user: 当前用户
            query: 原始查询
            
        Returns:
            Dict[str, Any]: 对话结果
        """
        try:
            from apps.ai.services.ai_intent_classifier import ai_intent_classifier
            
            ai_client = ai_intent_classifier.ai_client
            if ai_client is None:
                return self._create_fallback_response(query)
            
            messages = [
                {'role': 'system', 'content': '你是一个友好的智能助手，能够与用户进行自然对话。'},
                {'role': 'user', 'content': query}
            ]
            
            response = ai_client.chat_completion(messages)
            
            # 如果返回空响应，使用降级
            if not response or not response.strip():
                logger.warning("AI 返回空响应，使用降级响应")
                return self._create_fallback_response(query)
            
            return {
                'success': True,
                'message': response,
                'intent_type': 'AI_CHAT',
                'result': response,
                'confidence': 1.0
            }
        except Exception as e:
            logger.error(f"AI 对话失败：{str(e)}")
            # AI 调用失败，使用降级响应
            return self._create_fallback_response(query)
    
    def _create_fallback_response(self, query: str) -> Dict[str, Any]:
        """创建降级响应（AI 不可用时）"""
        query_lower = query.lower()
        
        # 根据用户输入提供智能响应
        if any(greeting in query_lower for greeting in ['你好', '您好', 'hi', 'hello', '早', '好']):
            response = '您好！👋 我是您的智能助手，很高兴为您服务！我可以帮您查询和管理业务数据，比如：\n• 客户管理：查询客户数量、客户列表、客户详情\n• 订单管理：查看订单总额、订单列表、订单统计\n• 合同管理：查询合同信息、合同总额\n• 项目管理：查看项目进度、项目列表\n\n请问有什么可以帮您？'
        elif any(question_word in query_lower for question_word in ['多少', '几个', '数量', '统计', '总额', '汇总']):
            response = '您好！我可以帮您查询各类业务数据。\n\n您可以这样问我：\n• "我有多少客户？"\n• "查询订单列表"\n• "查看合同总额"\n• "统计本月成交客户"\n• "有哪些正在进行的项目"\n\n请告诉我您想查询什么？'
        elif any(action_word in query_lower for action_word in ['添加', '新增', '创建', '修改', '更新', '删除']):
            response = '您好！我可以帮您操作业务数据。\n\n您可以这样告诉我：\n• "添加一个新客户"\n• "创建订单"\n• "修改客户电话"\n• "更新项目进度"\n\n请告诉我您的具体需求？'
        elif any(keyword in query_lower for keyword in ['帮助', '帮助文档', '教程', '怎么', '如何', '怎样']):
            response = '您好！我很乐意为您提供帮助！\n\n我可以帮您：\n• 查询业务数据（客户、订单、合同、项目等）\n• 创建和修改业务记录\n• 统计和分析业务数据\n\n您想了解什么呢？'
        else:
            response = '您好！👋 我是您的智能助手，很高兴为您服务！\n\n我可以帮您：\n• 查询客户、订单、合同、项目等业务数据\n• 创建和修改业务记录\n• 统计和分析业务数据\n\n请问有什么可以帮您？'
        
        return {
            'success': True,
            'message': response,
            'intent_type': 'AI_CHAT',
            'result': response,
            'confidence': 1.0
        }
    
    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            'success': False,
            'message': message,
            'intent_type': None,
            'confidence': 0.0
        }
    
    def _create_permission_denied_response(self, intent_result: Dict[str, Any], permission_result: Dict[str, Any]) -> Dict[str, Any]:
        """创建权限拒绝响应"""
        return {
            'success': False,
            'message': permission_result.get('message', '您没有权限执行此操作'),
            'intent_type': intent_result.get('intent'),
            'confidence': intent_result.get('confidence'),
            'requires_permission': permission_result.get('required_permission'),
            'suggestion': '请联系管理员获取相应权限'
        }
    
    def _create_confirmation_response(self, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """创建确认响应"""
        intent_type = intent_result.get('intent')
        confidence = intent_result.get('confidence', 0)
        
        options = intent_result.get('fallback_options', [])
        if not options:
            options = [
                {'text': '查询项目数据', 'intent': 'DATA_QUERY', 'action': 'select'},
                {'text': '调用知识库', 'intent': 'KNOWLEDGE_BASE', 'action': 'select'},
                {'text': '纯 AI 对话', 'intent': 'AI_CHAT', 'action': 'select'},
            ]
        
        return {
            'success': True,
            'requires_confirmation': True,
            'message': f'我不太确定您的意图（置信度：{confidence:.0%}），请选择：',
            'intent_type': intent_type,
            'confidence': confidence,
            'options': options,
            'original_query': query
        }


enhanced_intent_service = EnhancedIntentService()
