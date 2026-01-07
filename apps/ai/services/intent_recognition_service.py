"""
意图识别服务
负责识别用户对话意图，包括项目数据查询意图、知识库调用意图、纯AI对话意图
"""

import logging
from typing import Dict, Any, Tuple, Optional
from django.contrib.auth.models import User
from apps.ai.utils.ai_client import AIClient
from apps.ai.models import AIIntentRecognition

logger = logging.getLogger(__name__)


class IntentRecognitionService:
    """
    意图识别服务类
    基于NLP的用户意图分类模型，识别三类核心意图
    """
    
    # 核心意图类型
    INTENT_TYPES = {
        'DATA_QUERY': 'data_query',  # 项目数据查询意图
        'KNOWLEDGE_BASE': 'knowledge_base',  # 知识库调用意图
        'AI_CHAT': 'ai_chat'  # 纯AI对话意图
    }
    
    # 置信度阈值配置
    CONFIDENCE_THRESHOLDS = {
        'HIGH': 0.85,  # 高置信度，直接执行
        'MEDIUM': 0.65,  # 中等置信度，提示确认
        'LOW': 0.40,  # 低置信度，提供意图引导
        'FAIL': 0.40  # 识别失败阈值
    }
    
    def __init__(self):
        self.ai_client = None
        self.intent_patterns = self._load_intent_patterns()
    
    def _load_intent_patterns(self) -> Dict[str, Any]:
        """
        加载意图识别规则
        """
        try:
            # 从数据库加载意图识别规则
            patterns = {}
            for intent in AIIntentRecognition.objects.filter(is_active=True):
                intent_type = intent.intent_type
                if intent_type not in patterns:
                    patterns[intent_type] = []
                patterns[intent_type].append({
                    'keywords': intent.keywords.split(','),
                    'confidence': intent.confidence,
                    'description': intent.description
                })
            return patterns
        except Exception as e:
            logger.error(f"加载意图识别规则失败: {str(e)}")
            return {
                self.INTENT_TYPES['DATA_QUERY']: [
                    {'keywords': ['查询', '统计', '数量', '列表', '总数', '进度', '多少', '有多少', '统计', '汇总', '数据', '报表', '记录'], 'confidence': 0.85, 'description': '数据查询意图'},
                    {'keywords': ['客户', '订单', '合同', '项目', '发票', '员工', '部门', '财务', '生产', '销售', '采购', '库存'], 'confidence': 0.8, 'description': '业务数据查询'},
                    {'keywords': ['本月', '上月', '今年', '去年', '本周', '上周', '最近'], 'confidence': 0.75, 'description': '时间范围查询意图'}
                ],
                self.INTENT_TYPES['KNOWLEDGE_BASE']: [
                    {'keywords': ['知识库', '知识', '文档', '资料', '帮助', '指南', '手册', '教程', '说明', '文档'], 'confidence': 0.85, 'description': '知识库查询意图'},
                    {'keywords': ['如何', '怎样', '教程', '步骤', '方法', '怎么做', '怎么操作', '使用方法'], 'confidence': 0.8, 'description': '知识获取意图'},
                    {'keywords': ['常见问题', 'FAQ', '问题解答', '故障', '错误', '解决方法'], 'confidence': 0.75, 'description': '问题解决意图'}
                ],
                self.INTENT_TYPES['AI_CHAT']: [
                    {'keywords': ['你好', '您好', 'hi', 'hello', '早上好', '下午好', '晚上好', '欢迎', '感谢', '谢谢', '再见'], 'confidence': 0.95, 'description': '问候意图'},
                    {'keywords': ['聊天', '谈谈', '讨论', '说说', '想', '交流', '闲聊', '随便聊', '聊聊'], 'confidence': 0.85, 'description': '聊天意图'},
                    {'keywords': ['天气', '新闻', '时间', '日期', '节日', '笑话', '故事', '推荐'], 'confidence': 0.8, 'description': '生活聊天意图'}
                ]
            }
    
    def _ensure_ai_client(self):
        """
        确保AI客户端已初始化
        """
        if self.ai_client is None:
            try:
                from apps.ai.utils.ai_config_manager import get_ai_config_manager
                config_manager = get_ai_config_manager()
                # 使用get_recommended_config代替get_default_config，因为get_default_config方法不存在
                config = config_manager.get_recommended_config()
                if config:
                    self.ai_client = AIClient.from_config(config)
                else:
                    logger.warning("没有找到有效的AI配置，AI功能将不可用")
                    self.ai_client = None
            except Exception as e:
                logger.error(f"初始化AI客户端失败: {str(e)}")
                self.ai_client = None
    
    def recognize_intent(self, user: User, query: str) -> Dict[str, Any]:
        """
        识别用户意图
        
        Args:
            user: 当前用户
            query: 用户查询文本
            
        Returns:
            Dict[str, Any]: 意图识别结果
                - intent: 意图类型
                - confidence: 置信度
                - entities: 识别到的实体
                - requires_confirmation: 是否需要确认
                - fallback_options: 降级处理选项
        """
        try:
            # 1. 初始化结果
            result = {
                'intent': None,
                'confidence': 0.0,
                'entities': {},
                'requires_confirmation': False,
                'fallback_options': []
            }
            
            query_lower = query.lower().strip()
            if not query_lower:
                return result
            
            # 2. 基于规则的初步意图识别
            rule_based_result = self._rule_based_intent_recognition(query_lower)
            
            # 3. 基于AI的意图分类和置信度评估（容错处理）
            ai_based_result = {
                'intent': None,
                'confidence': 0.0,
                'entities': {}
            }
            try:
                ai_based_result = self._ai_based_intent_recognition(query_lower)
            except Exception as ai_e:
                logger.warning(f"基于AI的意图识别失败，仅使用规则识别: {str(ai_e)}")
            
            # 4. 融合两种识别结果
            final_result = self._fuse_recognition_results(rule_based_result, ai_based_result, query_lower)
            
            # 5. 应用置信度阈值，确定处理方式
            result = self._apply_confidence_threshold(final_result, query_lower)
            
            # 6. 增强结果，确保即使置信度低，也能返回有意义的意图
            if result['intent'] is None:
                # 尝试从规则识别结果中获取意图
                if rule_based_result['intent']:
                    result['intent'] = rule_based_result['intent']
                    result['confidence'] = rule_based_result['confidence']
                    result['requires_confirmation'] = True
                else:
                    # 如果规则识别也失败，默认使用AI聊天意图
                    result['intent'] = self.INTENT_TYPES['AI_CHAT']
                    result['confidence'] = 0.5
                    result['requires_confirmation'] = True
            
            logger.info(f"意图识别结果: {result}")
            return result
            
        except Exception as e:
            logger.error(f"意图识别失败: {str(e)}")
            # 出错时返回默认的AI聊天意图
            return {
                'intent': self.INTENT_TYPES['AI_CHAT'],
                'confidence': 0.5,
                'entities': {},
                'requires_confirmation': True,
                'fallback_options': [
                    {
                        'text': '您是想要进行纯AI对话吗？',
                        'intent': self.INTENT_TYPES['AI_CHAT'],
                        'action': 'confirm'
                    },
                    {
                        'text': '我不太确定您的需求，请选择以下选项',
                        'intent': None,
                        'action': 'select'
                    }
                ]
            }
    
    def _rule_based_intent_recognition(self, query: str) -> Dict[str, Any]:
        """
        基于规则的意图识别
        """
        scores = {
            self.INTENT_TYPES['DATA_QUERY']: 0.0,
            self.INTENT_TYPES['KNOWLEDGE_BASE']: 0.0,
            self.INTENT_TYPES['AI_CHAT']: 0.0
        }
        
        entities = {}
        
        # 特定查询模式匹配，优先处理
        # 数据查询模式
        data_query_patterns = [
            # 列表查询模式
            r'.*列出.*客户',
            r'.*客户.*列表',
            r'.*展示.*客户',
            r'.*查看.*客户.*列表',
            r'.*列出.*订单',
            r'.*订单.*列表',
            r'.*展示.*订单',
            r'.*查看.*订单.*列表',
            r'.*列出.*合同',
            r'.*合同.*列表',
            r'.*展示.*合同',
            r'.*查看.*合同.*列表',
            r'.*列出.*项目',
            r'.*项目.*列表',
            r'.*展示.*项目',
            r'.*查看.*项目.*列表',
            r'.*列出.*发票',
            r'.*发票.*列表',
            r'.*展示.*发票',
            r'.*查看.*发票.*列表',
            
            # 数量查询模式
            r'.*有几个.*客户',
            r'.*客户.*数量',
            r'.*客户.*有多少',
            r'.*我有多少.*客户',
            r'.*我有几个.*客户',
            r'.*有多少.*客户',
            r'.*查询.*客户.*数量',
            r'.*统计.*客户',
            r'.*有多少.*订单',
            r'.*订单.*数量',
            r'.*项目.*数量',
            r'.*查询.*订单',
            r'.*统计.*订单',
            r'.*查询.*项目',
            r'.*统计.*项目',
            
            # 客户深度查询模式
            r'.*查询.*客户.*订单',
            r'.*客户.*订单.*信息',
            r'.*客户.*跟进记录',
            r'.*客户.*合同.*详情',
            r'.*客户.*发票.*状态',
            r'.*客户.*付款.*情况',
            r'.*客户.*订单.*历史',
            
            # 按客户名称查询
            r'.*查询.*客户.*[\u4e00-\u9fa5]+',
            r'.*[\u4e00-\u9fa5]+.*客户.*信息',
            r'.*[\u4e00-\u9fa5]+.*订单',
            r'.*[\u4e00-\u9fa5]+.*合同',
            r'.*[\u4e00-\u9fa5]+.*发票',
            r'.*[\u4e00-\u9fa5]+.*跟进记录'
        ]
        
        # 数据添加模式
        data_add_patterns = [
            # 订单添加
            r'.*添加.*订单',
            r'.*帮我添加.*订单',
            r'.*新增.*订单',
            r'.*创建.*订单',
            r'.*增加.*订单',
            
            # 跟进记录添加
            r'.*添加.*跟进记录',
            r'.*帮我添加.*跟进记录',
            r'.*新增.*跟进记录',
            r'.*创建.*跟进记录',
            r'.*增加.*跟进记录',
            r'.*添加.*客户.*跟进记录',
            r'.*帮我添加.*客户.*跟进记录',
            r'.*新增.*客户.*跟进记录',
            r'.*创建.*客户.*跟进记录',
            r'.*增加.*客户.*跟进记录'
        ]
        
        import re
        # 检查数据添加模式
        for pattern in data_add_patterns:
            if re.search(pattern, query):
                scores[self.INTENT_TYPES['DATA_QUERY']] += 1.0
                entities['action'] = 'add'
                
                # 提取操作类型
                if any(keyword in query for keyword in ['订单', 'order']):
                    entities['action_type'] = 'order'
                elif any(keyword in query for keyword in ['跟进记录', 'followup']):
                    entities['action_type'] = 'followup'
                
                # 提取客户名称 - 改进版，避免将整个查询识别为客户名称
                customer_name_pattern = r'[\u4e00-\u9fa5]{2,}'  # 至少2个中文字符
                customer_name_matches = re.findall(customer_name_pattern, query)
                if customer_name_matches:
                    # 尝试找到最可能是客户名称的匹配项
                    exclude_words = ['客户', '订单', '合同', '项目', '发票', '查询', '列出', '展示', '查看', '数量', '有多少', '几个', '统计', '关联', '所有', '的', '添加', '帮我', '新增', '创建', '增加', '跟进记录', '我', '有', '几', '个', '多少', '我有', '有几', '几个', '多少个', '我有几个', '我有多少', '有多少']
                    for match in customer_name_matches:
                        if match not in exclude_words and len(match) > 1:  # 客户名称至少2个字符
                            # 只提取真正的客户名称，避免提取查询中的其他词语
                            entities['customer_name'] = match
                            break
                
                break
            
        # 如果已经匹配到添加模式，不再检查查询模式
        if entities.get('action') != 'add':
            for pattern in data_query_patterns:
                match = re.search(pattern, query)
                if match:
                    scores[self.INTENT_TYPES['DATA_QUERY']] += 2.0  # 增加数据查询的权重
                    
                    # 提取实体信息
                    if any(keyword in query for keyword in ['客户', 'customer']):
                        entities['entity_type'] = '客户'
                        entities['customer_count'] = '客户数量'
                    elif any(keyword in query for keyword in ['订单', 'order']):
                        entities['entity_type'] = '订单'
                    elif any(keyword in query for keyword in ['合同', 'contract']):
                        entities['entity_type'] = '合同'
                    elif any(keyword in query for keyword in ['项目', 'project']):
                        entities['entity_type'] = '项目'
                    elif any(keyword in query for keyword in ['发票', 'invoice']):
                        entities['entity_type'] = '发票'
                    
                    # 提取客户名称 - 改进版，避免将整个查询识别为客户名称
                    customer_name_pattern = r'[\u4e00-\u9fa5]{2,}'  # 至少2个中文字符
                    customer_name_matches = re.findall(customer_name_pattern, query)
                    if customer_name_matches:
                        # 尝试找到最可能是客户名称的匹配项
                        exclude_words = ['客户', '订单', '合同', '项目', '发票', '查询', '列出', '展示', '查看', '数量', '有多少', '几个', '统计', '关联', '所有', '的', '我', '有', '几', '个', '多少', '我有', '有几', '几个', '多少个', '我有几个', '我有多少', '有多少']
                        for match in customer_name_matches:
                            if match not in exclude_words and len(match) > 1:  # 客户名称至少2个字符
                                # 只提取真正的客户名称，避免提取查询中的其他词语
                                # 检查是否是查询类词语
                                if any(query_word in match for query_word in ['查询', '列出', '展示', '查看', '统计', '关联', '所有']):
                                    continue
                                # 检查是否是数量类词语
                                if any(count_word in match for count_word in ['数量', '有多少', '几个', '多少']):
                                    continue
                                entities['customer_name'] = match
                                break
                    
                    break
        

        
        # 遍历所有意图模式
        for intent_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                keywords = pattern['keywords']
                confidence = pattern['confidence']
                
                # 检查关键词匹配
                if any(keyword in query for keyword in keywords):
                    scores[intent_type] += confidence
        
        # 归一化分数
        total_score = sum(scores.values())
        if total_score > 0:
            for intent_type in scores:
                scores[intent_type] = scores[intent_type] / total_score
        
        # 确定最高分数的意图
        max_score = max(scores.values())
        if max_score > 0:
            # 按优先级排序，数据查询优先于AI聊天
            if scores[self.INTENT_TYPES['DATA_QUERY']] > 0:
                intent = self.INTENT_TYPES['DATA_QUERY']
            elif scores[self.INTENT_TYPES['KNOWLEDGE_BASE']] > 0:
                intent = self.INTENT_TYPES['KNOWLEDGE_BASE']
            else:
                intent = self.INTENT_TYPES['AI_CHAT']
        else:
            intent = None
        
        return {
            'intent': intent,
            'confidence': max_score,
            'entities': entities
        }
    
    def _ai_based_intent_recognition(self, query: str) -> Dict[str, Any]:
        """
        基于AI的意图识别
        """
        self._ensure_ai_client()
        
        if self.ai_client is None:
            return {
                'intent': None,
                'confidence': 0.0,
                'entities': {}
            }
        
        try:
            # 构建意图分类提示
            prompt = f"""请分析以下用户查询的意图，将其分类为三类之一：
1. data_query：项目数据查询意图，例如查询客户数量、订单总额、项目进度等业务数据
2. knowledge_base：知识库调用意图，例如查询知识库内容、文档、帮助指南等
3. ai_chat：纯AI对话意图，例如问候、闲聊、讨论等非业务相关对话

请按照以下JSON格式返回结果，包含意图类型、置信度（0-1之间的小数）和识别到的实体：
{{
  "intent": "意图类型",
  "confidence": 置信度,
  "entities": {{"实体类型": "实体值"}}
}}

用户查询：{query}"""
            
            messages = [
                {'role': 'system', 'content': '你是一个专业的意图分类器，能够准确识别用户的对话意图。'}, 
                {'role': 'user', 'content': prompt}
            ]
            
            response = self.ai_client.chat_completion(messages)
            import json
            result = json.loads(response)
            
            # 验证结果格式
            if not isinstance(result, dict) or 'intent' not in result:
                raise ValueError("Invalid AI response format")
            
            return result
        except Exception as e:
            logger.error(f"AI意图识别失败: {str(e)}")
            return {
                'intent': None,
                'confidence': 0.0,
                'entities': {}
            }
    
    def _fuse_recognition_results(self, rule_result: Dict[str, Any], ai_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        融合规则识别和AI识别结果
        """
        # 规则识别权重和AI识别权重
        RULE_WEIGHT = 0.7  # 提高规则识别权重
        AI_WEIGHT = 0.3  # 降低AI识别权重
        
        # 对于明确的数量查询，强制使用规则识别结果
        if any(pattern in query for pattern in ['我有几个客户', '我有多少客户', '客户数量', '有多少客户']):
            # 确保规则识别结果有置信度
            if rule_result['confidence'] < 0.5:
                rule_result['confidence'] = 0.85
            return rule_result
        
        # 如果AI识别结果有效，则融合结果
        if ai_result['intent'] and ai_result['confidence'] > 0:
            # 融合置信度
            confidence = (rule_result['confidence'] * RULE_WEIGHT) + (ai_result['confidence'] * AI_WEIGHT)
            
            # 确定最终意图（优先使用规则结果，特别是数据查询意图）
            if rule_result['confidence'] > 0 and (rule_result['confidence'] > ai_result['confidence'] or rule_result['intent'] == self.INTENT_TYPES['DATA_QUERY']):
                intent = rule_result['intent']
            else:
                intent = ai_result['intent']
            
            # 融合实体
            entities = {**rule_result['entities'], **ai_result['entities']}
        else:
            # 使用规则识别结果
            intent = rule_result['intent']
            confidence = rule_result['confidence']
            entities = rule_result['entities']
        
        return {
            'intent': intent,
            'confidence': round(confidence, 2),
            'entities': entities
        }
    
    def _apply_confidence_threshold(self, result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        应用置信度阈值，确定处理方式
        """
        confidence = result['confidence']
        intent = result['intent']
        
        # 高置信度：直接执行
        if confidence >= self.CONFIDENCE_THRESHOLDS['HIGH']:
            return {
                'intent': intent,
                'confidence': confidence,
                'entities': result['entities'],
                'requires_confirmation': False,
                'fallback_options': []
            }
        
        # 中等置信度：提示确认
        elif confidence >= self.CONFIDENCE_THRESHOLDS['MEDIUM']:
            return {
                'intent': intent,
                'confidence': confidence,
                'entities': result['entities'],
                'requires_confirmation': True,
                'fallback_options': [
                    {
                        'text': f'您是想要查询{self._get_intent_description(intent)}吗？',
                        'intent': intent,
                        'action': 'confirm'
                    },
                    {
                        'text': '我不太确定您的需求，请选择以下选项',
                        'intent': None,
                        'action': 'select'
                    }
                ]
            }
        
        # 低置信度：提供意图引导
        else:
            return self._handle_recognition_failure(query)
    
    def _handle_recognition_failure(self, query: str) -> Dict[str, Any]:
        """
        意图识别失败的降级处理
        """
        return {
            'intent': None,
            'confidence': 0.0,
            'entities': {},
            'requires_confirmation': False,
            'fallback_options': [
                {
                    'text': '查询项目数据',
                    'intent': self.INTENT_TYPES['DATA_QUERY'],
                    'action': 'select'
                },
                {
                    'text': '调用知识库',
                    'intent': self.INTENT_TYPES['KNOWLEDGE_BASE'],
                    'action': 'select'
                },
                {
                    'text': '纯AI对话',
                    'intent': self.INTENT_TYPES['AI_CHAT'],
                    'action': 'select'
                },
                {
                    'text': '重新描述需求',
                    'intent': None,
                    'action': 'retry'
                }
            ]
        }
    
    def _get_intent_description(self, intent: str) -> str:
        """
        获取意图描述
        """
        descriptions = {
            self.INTENT_TYPES['DATA_QUERY']: '项目数据',
            self.INTENT_TYPES['KNOWLEDGE_BASE']: '知识库内容',
            self.INTENT_TYPES['AI_CHAT']: '纯AI对话'
        }
        return descriptions.get(intent, '未知意图')
    
    def get_intent_specific_handler(self, intent: str):
        """
        获取意图特定处理器
        """
        from apps.ai.services.query_service import query_service
        
        handlers = {
            self.INTENT_TYPES['DATA_QUERY']: query_service.process_query,
            self.INTENT_TYPES['KNOWLEDGE_BASE']: self._handle_knowledge_base,
            self.INTENT_TYPES['AI_CHAT']: self._handle_ai_chat
        }
        
        return handlers.get(intent)    
    
    def _handle_knowledge_base(self, user: User, query: str) -> Dict[str, Any]:
        """
        处理知识库调用意图
        由于knowledge_service模块不存在，暂时使用默认处理方式
        """
        return {
            'success': True,
            'result': '知识库功能正在开发中，暂时无法提供服务。请稍后再试。'
        }
    
    def _handle_ai_chat(self, user: User, query: str) -> Dict[str, Any]:
        """
        处理纯AI对话意图，包含会话记忆功能
        遵循多级识别机制：仅当项目内意图和知识库匹配均失败时才使用
        """
        self._ensure_ai_client()
        
        if self.ai_client is None:
            return {
                'success': False,
                'message': 'AI服务暂时不可用，请稍后再试'
            }
        
        try:
            from apps.ai.models import AIChat, AIChatMessage
            
            # 获取当前用户的最新聊天会话
            latest_chat = AIChat.objects.filter(user=user).order_by('-updated_at').first()
            
            # 构建完整的对话上下文，包括历史消息
            messages = [
                {'role': 'system', 'content': '你是一个友好的智能助手，能够与用户进行自然对话。请注意：如果用户询问的是关于系统或业务的问题，而你无法提供准确答案，请明确告知用户你无法回答，而不要编造信息。'}
            ]
            
            # 如果有历史会话，添加最近10条消息作为上下文
            if latest_chat:
                history_messages = AIChatMessage.objects.filter(chat=latest_chat).order_by('-created_at')[:10]
                # 反转消息顺序，确保时间顺序正确
                history_messages = reversed(list(history_messages))
                
                for msg in history_messages:
                    messages.append({
                        'role': msg.role,
                        'content': msg.content
                    })
            
            # 添加当前用户消息
            messages.append({'role': 'user', 'content': query})
            
            logger.info(f"AI对话上下文: {messages}")
            
            response = self.ai_client.chat_completion(messages)
            
            return {
                'success': True,
                'result': response
            }
        except Exception as e:
            logger.error(f"AI对话处理失败: {str(e)}")
            return {
                'success': False,
                'message': 'AI对话处理失败，请稍后再试'
            }


# 创建全局实例
intent_recognition_service = IntentRecognitionService()
