"""
基于 AI 的意图分类器
使用机器学习模型进行意图识别，替代传统的关键词匹配方式
"""

import logging
import json
import re
from typing import Dict, Any, List
from django.contrib.auth.models import User
from django.core.cache import cache
from apps.ai.utils.ai_client import AIClient
from apps.ai.models import AIIntentRecognition

logger = logging.getLogger(__name__)


class AIIntentClassifier:
    """
    AI 意图分类器
    基于大语言模型的意图识别，支持多类别意图分类和实体提取
    """

    INTENT_CATEGORIES = {
        'DATA_QUERY': {
            'name': '数据查询',
            'description': '查询业务数据，包括客户、订单、合同、项目、发票、员工、部门、财务、生产等数据的查询、统计、列表展示',
            'examples': [
                '我有多少客户',
                '查询本月的订单总额',
                '列出所有进行中的项目',
                '统计上个月成交的客户数量',
                '查看张三的客户信息',
                '显示最近的订单列表',
                '合同金额总和是多少',
                '有哪些在职员工',
                '生产计划的完成情况如何',
            ]
        },
        'DATA_CREATE': {
            'name': '数据创建',
            'description': '创建新的数据记录，包括添加客户、订单、合同、项目、发票、跟进记录等',
            'examples': [
                '添加一个新客户',
                '帮我创建订单',
                '新增一条跟进记录',
                '创建合同记录',
                '添加项目信息',
            ]
        },
        'DATA_UPDATE': {
            'name': '数据修改',
            'description': '修改现有的数据记录，包括更新客户信息、订单状态、合同内容等',
            'examples': [
                '更新客户电话',
                '修改订单金额',
                '更改合同状态',
                '更新项目进度',
            ]
        },
        'KNOWLEDGE_BASE': {
            'name': '知识库查询',
            'description': '查询知识库内容、文档、帮助指南、教程、常见问题解答等',
            'examples': [
                '如何使用这个功能',
                '查询操作手册',
                '查看帮助文档',
                '有什么教程可以学习',
                '常见问题怎么解决',
            ]
        },
        'AI_CHAT': {
            'name': 'AI 对话',
            'description': '纯 AI 对话，包括问候、闲聊、讨论等非业务相关对话',
            'examples': [
                '你好',
                '早上好',
                '今天天气不错',
                '给我讲个笑话',
                '随便聊聊',
            ]
        }
    }

    CONFIDENCE_THRESHOLDS = {
        'HIGH': 0.85,
        'MEDIUM': 0.65,
        'LOW': 0.40
    }

    def __init__(self):
        self.ai_client = None
        self._training_data_cache = None

    def _ensure_ai_client(self):
        """确保 AI 客户端已初始化"""
        if self.ai_client is None:
            try:
                from apps.ai.utils.ai_config_manager import get_ai_config_manager
                config_manager = get_ai_config_manager()
                config = config_manager.get_recommended_config()
                if config:
                    self.ai_client = AIClient.from_config(config)
                else:
                    logger.warning("没有找到有效的 AI 配置，AI 功能将不可用")
                    self.ai_client = None
            except Exception as e:
                logger.error(f"初始化 AI 客户端失败：{str(e)}")
                self.ai_client = None

    def _get_training_data(self) -> List[Dict[str, Any]]:
        """获取训练数据，包括数据库配置和内置示例"""
        cache_key = 'ai_intent_training_data'
        training_data = cache.get(cache_key)

        if training_data is None:
            training_data = []

            try:
                for intent in AIIntentRecognition.objects.filter(
                        is_active=True):
                    training_data.append({
                        'intent_type': intent.intent_type,
                        'keywords': intent.keywords if isinstance(intent.keywords, list) else [intent.keywords],
                        'examples': intent.examples if isinstance(intent.examples, list) else [intent.examples],
                        'description': intent.description
                    })
            except Exception as e:
                logger.error(f"加载数据库意图配置失败：{str(e)}")

            for intent_type, intent_info in self.INTENT_CATEGORIES.items():
                training_data.append({
                    'intent_type': intent_type,
                    'keywords': [],
                    'examples': intent_info['examples'],
                    'description': intent_info['description']
                })

            cache.set(cache_key, training_data, 300)

        return training_data

    def classify_intent(self, user: User, query: str) -> Dict[str, Any]:
        """
        分类用户意图

        Args:
            user: 当前用户
            query: 用户查询文本

        Returns:
            Dict[str, Any]: 意图分类结果
        """
        try:
            query = query.strip()
            if not query:
                return self._create_empty_result()

            self._ensure_ai_client()

            if self.ai_client is None:
                return self._rule_based_fallback(query)

            ai_result = self._ai_classify_intent(query)

            # 如果 AI 不可用（返回 None），使用规则匹配
            if ai_result is None:
                return self._rule_based_fallback(query)

            if ai_result['confidence'] < self.CONFIDENCE_THRESHOLDS['LOW']:
                rule_result = self._rule_based_fallback(query)
                if rule_result['confidence'] > ai_result['confidence']:
                    ai_result = rule_result

            result = self._enhance_result(ai_result, query)

            logger.info(
                f"意图分类结果：intent={result['intent']}, confidence={result['confidence']}")
            return result

        except Exception as e:
            logger.error(f"意图分类失败：{str(e)}")
            # 发生异常时使用规则匹配降级
            return self._rule_based_fallback(query)

    def _ai_classify_intent(self, query: str) -> Dict[str, Any]:
        """使用 AI 模型进行意图分类"""
        try:
            self._get_training_data()

            intent_categories_str = "\n".join([
                f"- {cat_id}: {info['name']} - {info['description']}"
                for cat_id, info in self.INTENT_CATEGORIES.items()
            ])

            prompt = f"""请分析用户查询的意图，将其分类到以下类别之一：

{intent_categories_str}

请按照以下 JSON 格式返回分析结果：
{{
    "intent": "意图类别 ID",
    "confidence": 0.0-1.0 之间的置信度，
    "entities": {{
        "entity_type": "entity_value"
    }},
    "action": "query/create/update/delete 等操作类型",
    "data_type": "customer/order/contract/project 等数据类型",
    "time_range": "时间范围如 this_month/last_month 等",
    "status": "状态筛选条件",
    "customer_name": "客户名称（如果有）",
    "reasoning": "简要说明分类理由"
}}

用户查询：{query}

请确保返回有效的 JSON 格式，不要包含其他内容。"""

            messages = [
                {'role': 'system',
                 'content': '你是一个专业的意图分类器，能够准确识别用户的查询意图。请返回严格的 JSON 格式。'},
                {'role': 'user', 'content': prompt}
            ]

            response = self.ai_client.chat_completion(messages)

            result = self._parse_ai_response(response, query)

            if not self._validate_intent(result['intent']):
                result['intent'] = 'AI_CHAT'
                result['confidence'] = 0.5

            return result

        except Exception as e:
            logger.error(f"AI 意图分类失败：{str(e)}")
            # 返回 None 表示 AI 不可用，将使用规则匹配
            return None

    def _parse_ai_response(self, response: str, query: str) -> Dict[str, Any]:
        """解析 AI 响应"""
        try:
            response = response.strip()

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group()

            result = json.loads(response)

            return {
                'intent': result.get('intent', 'AI_CHAT').upper(),
                'confidence': float(result.get('confidence', 0.5)),
                'entities': result.get('entities', {}),
                'action': result.get('action'),
                'data_type': result.get('data_type'),
                'time_range': result.get('time_range'),
                'status': result.get('status'),
                'customer_name': result.get('customer_name'),
                'reasoning': result.get('reasoning', '')
            }
        except Exception as e:
            logger.warning(f"解析 AI 响应失败：{str(e)}")
            return self._extract_intent_from_text(response, query)

    def _extract_intent_from_text(
            self, response: str, query: str) -> Dict[str, Any]:
        """从文本响应中提取意图"""
        intent = 'AI_CHAT'
        confidence = 0.5

        if 'data_query' in response.lower() or '查询' in response:
            intent = 'DATA_QUERY'
            confidence = 0.7
        elif 'knowledge' in response.lower() or '知识库' in response:
            intent = 'KNOWLEDGE_BASE'
            confidence = 0.7
        elif 'chat' in response.lower() or '对话' in response:
            intent = 'AI_CHAT'
            confidence = 0.6

        return {
            'intent': intent,
            'confidence': confidence,
            'entities': {},
            'action': None,
            'data_type': None,
            'time_range': None,
            'status': None,
            'customer_name': None,
            'reasoning': '从文本响应中提取'
        }

    def _rule_based_fallback(self, query: str) -> Dict[str, Any]:
        """基于规则的降级处理 - 使用简单字符串匹配而非正则"""
        query_lower = query.lower()

        # 1. 优先检查问候语（最高优先级）
        greetings = [
            '你好',
            '您好',
            'hi',
            'hello',
            '早上好',
            '下午好',
            '晚上好',
            '早上好呀',
            '下午好呀',
            '晚上好呀']
        if any(greeting in query_lower for greeting in greetings):
            return {
                'intent': 'AI_CHAT',
                'confidence': 0.95,
                'entities': {},
                'action': 'chat',
                'data_type': None,
                'time_range': None,
                'status': None,
                'customer_name': None,
                'reasoning': '问候语匹配'
            }

        # 2. 检查聊天意图
        chat_keywords = [
            '聊天',
            '谈谈',
            '讨论',
            '说说',
            '想',
            '交流',
            '闲聊',
            '随便聊',
            '聊聊',
            '在吗',
            '有人吗']
        if any(keyword in query_lower for keyword in chat_keywords):
            return {
                'intent': 'AI_CHAT',
                'confidence': 0.85,
                'entities': {},
                'action': 'chat',
                'data_type': None,
                'time_range': None,
                'status': None,
                'customer_name': None,
                'reasoning': '聊天意图匹配'
            }

        # 3. 检查知识库意图
        knowledge_keywords = [
            '知识库',
            '知识',
            '文档',
            '帮助',
            '指南',
            '手册',
            '教程',
            '如何',
            '怎样',
            '怎么',
            '步骤',
            '方法']
        if any(keyword in query_lower for keyword in knowledge_keywords):
            return {
                'intent': 'KNOWLEDGE_BASE',
                'confidence': 0.85,
                'entities': {},
                'action': 'query',
                'data_type': None,
                'time_range': None,
                'status': None,
                'customer_name': None,
                'reasoning': '知识库意图匹配'
            }

        # 4. 检查创建意图
        create_keywords = ['添加', '新增', '创建', '增加', '建立', '开个', '办个']
        if any(keyword in query_lower for keyword in create_keywords):
            return {
                'intent': 'DATA_CREATE',
                'confidence': 0.85,
                'entities': {},
                'action': 'create',
                'data_type': None,
                'time_range': None,
                'status': None,
                'customer_name': None,
                'reasoning': '创建意图匹配'
            }

        # 5. 检查修改意图
        update_keywords = ['更新', '修改', '更改', '变更', '调整', '编辑', '改一下', '换一个']
        if any(keyword in query_lower for keyword in update_keywords):
            return {
                'intent': 'DATA_UPDATE',
                'confidence': 0.85,
                'entities': {},
                'action': 'update',
                'data_type': None,
                'time_range': None,
                'status': None,
                'customer_name': None,
                'reasoning': '修改意图匹配'
            }

        # 6. 检查查询意图（业务关键词）
        query_keywords = ['查询', '统计', '数量', '列表', '总数', '进度',
                          '多少', '有多少', '汇总', '数据', '报表', '记录', '看看', '显示']
        if any(keyword in query_lower for keyword in query_keywords):
            return {
                'intent': 'DATA_QUERY',
                'confidence': 0.80,
                'entities': {},
                'action': 'query',
                'data_type': None,
                'time_range': None,
                'status': None,
                'customer_name': None,
                'reasoning': '查询意图匹配'
            }

        # 7. 检查业务实体（隐含查询意图）
        business_keywords = [
            '客户',
            '订单',
            '合同',
            '项目',
            '发票',
            '员工',
            '部门',
            '财务',
            '生产',
            '销售',
            '采购',
            '库存',
            '产品',
            '供应商']
        if any(keyword in query_lower for keyword in business_keywords):
            return {
                'intent': 'DATA_QUERY',
                'confidence': 0.75,
                'entities': {},
                'action': 'query',
                'data_type': None,
                'time_range': None,
                'status': None,
                'customer_name': None,
                'reasoning': '业务实体匹配'
            }

        # 8. 检查时间词（隐含查询意图）
        time_keywords = [
            '本月',
            '上月',
            '今年',
            '去年',
            '本周',
            '上周',
            '最近',
            '当前',
            '这个月',
            '上个月']
        if any(keyword in query_lower for keyword in time_keywords):
            return {
                'intent': 'DATA_QUERY',
                'confidence': 0.70,
                'entities': {},
                'action': 'query',
                'data_type': None,
                'time_range': None,
                'status': None,
                'customer_name': None,
                'reasoning': '时间词匹配'
            }

        # 9. 默认：无法识别的意图，返回 AI_CHAT 但置信度较低
        return {
            'intent': 'AI_CHAT',
            'confidence': 0.60,
            'entities': {},
            'action': 'chat',
            'data_type': None,
            'time_range': None,
            'status': None,
            'customer_name': None,
            'reasoning': '无匹配规则，默认对话'
        }

    def _validate_intent(self, intent: str) -> bool:
        """验证意图是否有效"""
        return intent in self.INTENT_CATEGORIES.keys()

    def _enhance_result(
            self, result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """增强结果，提取更多实体信息"""
        query_lower = query.lower()

        if not result.get('customer_name'):
            customer_patterns = [
                r'客户 [：:]\s*([\u4e00-\u9fa5\w]+)',
                r'客户名称 [：:]\s*([\u4e00-\u9fa5\w]+)',
                r'帮我.*客户 ([\u4e00-\u9fa5]+)',
            ]
            for pattern in customer_patterns:
                match = re.search(pattern, query)
                if match:
                    result['customer_name'] = match.group(1)
                    break

        if not result.get('data_type'):
            if '客户' in query_lower:
                result['data_type'] = 'customer'
            elif '订单' in query_lower:
                result['data_type'] = 'order'
            elif '合同' in query_lower:
                result['data_type'] = 'contract'
            elif '项目' in query_lower:
                result['data_type'] = 'project'
            elif '发票' in query_lower:
                result['data_type'] = 'invoice'

        if not result.get('time_range'):
            if any(word in query_lower for word in ['本月', '这个月']):
                result['time_range'] = 'this_month'
            elif any(word in query_lower for word in ['上月', '上个月', '上个月']):
                result['time_range'] = 'last_month'
            elif any(word in query_lower for word in ['今年', '这一年']):
                result['time_range'] = 'this_year'

        if not result.get('status'):
            if '成交' in query_lower or '签约' in query_lower:
                result['status'] = 'deal'
            elif '潜在' in query_lower:
                result['status'] = 'potential'
            elif '进行中' in query_lower:
                result['status'] = 'in_progress'
            elif '已完成' in query_lower:
                result['status'] = 'completed'

        result['requires_confirmation'] = result['confidence'] < self.CONFIDENCE_THRESHOLDS['HIGH']

        result['fallback_options'] = []
        if result['confidence'] < self.CONFIDENCE_THRESHOLDS['MEDIUM']:
            result['fallback_options'] = [
                {'text': '查询项目数据', 'intent': 'DATA_QUERY', 'action': 'select'},
                {'text': '调用知识库', 'intent': 'KNOWLEDGE_BASE', 'action': 'select'},
                {'text': '纯 AI 对话', 'intent': 'AI_CHAT', 'action': 'select'},
            ]

        return result

    def _create_empty_result(self) -> Dict[str, Any]:
        """创建空结果"""
        return {
            'intent': None,
            'confidence': 0.0,
            'entities': {},
            'action': None,
            'data_type': None,
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'fallback_options': [],
            'reasoning': '空查询'
        }

    def _create_error_result(self, query: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            'intent': 'AI_CHAT',
            'confidence': 0.5,
            'entities': {},
            'action': 'chat',
            'data_type': None,
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': True,
            'fallback_options': [
                {'text': '查询项目数据', 'intent': 'DATA_QUERY', 'action': 'select'},
                {'text': '调用知识库', 'intent': 'KNOWLEDGE_BASE', 'action': 'select'},
                {'text': '纯 AI 对话', 'intent': 'AI_CHAT', 'action': 'select'},
            ],
            'reasoning': '分类错误，使用默认值'
        }

    def get_intent_description(self, intent: str) -> str:
        """获取意图描述"""
        if intent in self.INTENT_CATEGORIES:
            return self.INTENT_CATEGORIES[intent]['name']
        return '未知意图'


ai_intent_classifier = AIIntentClassifier()
