from django.conf import settings
from apps.ai.models import AIKnowledgeItem, AIKnowledgeVector
from apps.ai.utils.ai_client import AIClient
from apps.ai.utils.ai_config_manager import get_ai_config_manager
import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class EnhancedRAGService:
    """增强版RAG服务，支持混合检索、查询改写和重排序"""
    
    def __init__(self):
        self.ai_client = AIClient.from_config(get_ai_config_manager().get_recommended_config())
        self.max_relevant_items = 10  # 最多返回的相关知识条目数量
        self.similarity_threshold = 0.3  # 相似度阈值
        self.hybrid_weight = 0.6  # 语义检索权重，关键词检索权重为 1-hybrid_weight
        self.rerank_top_k = 5  # 重排序后返回的结果数量
    
    def generate_response(self, user, query, context_limit=None, use_enhanced=True):
        """生成RAG回复（增强版）"""
        if use_enhanced:
            return self._enhanced_generate_response(user, query, context_limit)
        else:
            return self._basic_generate_response(user, query, context_limit)
    
    def _basic_generate_response(self, user, query, context_limit=None):
        """基础RAG回复"""
        query_vector = self._generate_vector(query)
        relevant_items = self._retrieve_relevant_items(query_vector, user)
        
        if not relevant_items:
            return "抱歉，我在知识库中没有找到与您的问题相关的信息。"
        
        context = self._build_context(relevant_items, context_limit)
        return self._generate_answer(query, context, user)
    
    def _enhanced_generate_response(self, user, query, context_limit=None):
        """增强版RAG回复"""
        try:
            # 1. 查询改写
            rewritten_query = self._rewrite_query(query)
            
            # 2. 混合检索（语义 + 关键词）
            retrieved_items = self._hybrid_retrieve(rewritten_query, user)
            
            if not retrieved_items:
                # 如果增强检索没有结果，回退到基础检索
                return self._basic_generate_response(user, query, context_limit)
            
            # 3. 重排序
            reranked_items = self._rerank(query, retrieved_items)
            
            # 4. 构建上下文
            context = self._build_context(reranked_items, context_limit)
            
            # 5. 生成回复
            response = self._generate_answer(rewritten_query, context, user, use_rewritten=True)
            
            return response
        except Exception as e:
            logger.error(f"增强RAG回复失败: {str(e)}")
            # 回退到基础实现
            return self._basic_generate_response(user, query, context_limit)
    
    def _rewrite_query(self, query: str) -> str:
        """使用AI改写查询，提高检索质量"""
        try:
            prompt = f"""请将以下用户查询改写为更适合知识库检索的形式。

原始查询：{query}

要求：
1. 提取查询的核心意图
2. 补充相关关键词和同义词
3. 去除口语化表达，使其更加规范化
4. 保持查询的原始含义

改写后的查询："""
            
            messages = [
                {"role": "system", "content": "你是一个专业的知识库检索助手，擅长改写查询以提高检索准确率。"},
                {"role": "user", "content": prompt}
            ]
            
            rewritten_query = self.ai_client.chat_completion(messages=messages)
            
            # 清理改写结果
            rewritten_query = rewritten_query.strip()
            if not rewritten_query:
                return query
            
            return rewritten_query
        except Exception as e:
            logger.warning(f"查询改写失败，使用原查询: {str(e)}")
            return query
    
    def _hybrid_retrieve(self, query: str, user) -> List:
        """混合检索 - 结合语义检索和关键词检索"""
        try:
            # 1. 语义检索
            query_vector = self._generate_vector(query)
            semantic_results = self._semantic_retrieve(query_vector, user)
            
            # 2. 关键词检索
            keyword_results = self._keyword_retrieve(query, user)
            
            # 3. 融合结果
            return self._merge_results(semantic_results, keyword_results)
        except Exception as e:
            logger.error(f"混合检索失败: {str(e)}")
            return []
    
    def _semantic_retrieve(self, query_vector, user, top_k=None):
        """语义检索"""
        try:
            if top_k is None:
                top_k = self.max_relevant_items * 2
            
            knowledge_items = AIKnowledgeItem.objects.filter(status='published')
            if not knowledge_items.exists():
                return []
            
            knowledge_vectors = {}
            for vector_record in AIKnowledgeVector.objects.filter(knowledge_item__in=knowledge_items):
                knowledge_vectors[vector_record.knowledge_item.id] = {
                    'vector': vector_record.vector,
                    'dimension': vector_record.dimension
                }
            
            results = []
            for item in knowledge_items:
                if item.id in knowledge_vectors:
                    vector_data = knowledge_vectors[item.id]
                    item_vector = self._vector_from_bytes(vector_data['vector'], vector_data['dimension'])
                else:
                    from apps.ai.services.vector_generation_service import vector_generation_service
                    item_vector = vector_generation_service.get_vector_for_knowledge_item(item.id)
                
                if item_vector:
                    similarity = self._calculate_cosine_similarity(query_vector, item_vector)
                    if similarity >= self.similarity_threshold:
                        results.append((item, similarity))
            
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
        except Exception as e:
            logger.error(f"语义检索失败: {str(e)}")
            return []
    
    def _keyword_retrieve(self, query: str, user, top_k=None):
        """关键词检索"""
        try:
            if top_k is None:
                top_k = self.max_relevant_items * 2
            
            knowledge_items = AIKnowledgeItem.objects.filter(status='published')
            if not knowledge_items.exists():
                return []
            
            # 提取查询关键词
            keywords = self._extract_keywords(query)
            
            results = []
            for item in knowledge_items:
                # 计算关键词匹配分数
                score = self._calculate_keyword_score(item, keywords)
                if score > 0:
                    results.append((item, score))
            
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
        except Exception as e:
            logger.error(f"关键词检索失败: {str(e)}")
            return []
    
    def _extract_keywords(self, query: str) -> List[str]:
        """提取查询关键词"""
        # 简单的关键词提取
        stopwords = {'的', '了', '是', '在', '和', '与', '或', '等', '有', '没有', '如何', '怎么', '什么', '请问'}
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 1]
        return keywords
    
    def _calculate_keyword_score(self, item: AIKnowledgeItem, keywords: List[str]) -> float:
        """计算关键词匹配分数"""
        if not keywords:
            return 0.0
        
        # 计算标题和内容中的关键词匹配
        title_lower = item.title.lower() if item.title else ''
        content_lower = item.content.lower() if item.content else ''
        
        title_words = set(re.findall(r'\b\w+\b', title_lower))
        content_words = set(re.findall(r'\b\w+\b', content_lower))
        
        title_matches = sum(1 for kw in keywords if kw in title_words)
        content_matches = sum(1 for kw in keywords if kw in content_words)
        
        # 标题匹配权重更高
        score = (title_matches * 2 + content_matches) / (len(keywords) * 3)
        return min(score, 1.0)
    
    def _merge_results(self, semantic_results: List, keyword_results: List) -> List:
        """融合语义检索和关键词检索的结果"""
        merged = {}
        
        # 添加语义检索结果
        for item, score in semantic_results:
            item_id = str(item.id)
            if item_id not in merged:
                merged[item_id] = {'item': item, 'semantic_score': score, 'keyword_score': 0}
            else:
                merged[item_id]['semantic_score'] = score
        
        # 添加关键词检索结果
        for item, score in keyword_results:
            item_id = str(item.id)
            if item_id not in merged:
                merged[item_id] = {'item': item, 'semantic_score': 0, 'keyword_score': score}
            else:
                merged[item_id]['keyword_score'] = score
        
        # 计算综合分数
        final_results = []
        for item_id, data in merged.items():
            semantic_score = data['semantic_score']
            keyword_score = data['keyword_score']
            
            # 归一化分数
            max_semantic = max(s['semantic_score'] for s in semantic_results) if semantic_results else 1
            max_keyword = max(s['keyword_score'] for s in keyword_results) if keyword_results else 1
            
            normalized_semantic = semantic_score / max_semantic if max_semantic > 0 else 0
            normalized_keyword = keyword_score / max_keyword if max_keyword > 0 else 0
            
            # 混合权重
            hybrid_score = self.hybrid_weight * normalized_semantic + (1 - self.hybrid_weight) * normalized_keyword
            
            final_results.append((data['item'], hybrid_score))
        
        # 按综合分数排序
        final_results.sort(key=lambda x: x[1], reverse=True)
        return final_results
    
    def _rerank(self, query: str, items: List) -> List:
        """对检索结果进行重排序"""
        try:
            if not items:
                return []
            
            # 使用AI进行重排序
            item_texts = []
            for item, score in items:
                text = f"标题：{item.title}\n内容：{item.content[:500]}"
                item_texts.append(text)
            
            # 构建重排序提示
            items_context = "\n---\n".join([
                f"[{i+1}] {text}" for i, text in enumerate(item_texts)
            ])
            
            prompt = f"""给定用户查询和多个文档片段，请对文档片段进行相关性排序。

用户查询：{query}

文档片段：
{items_context}

要求：
1. 根据与查询的相关性对文档片段进行排序
2. 只返回排序后的序号列表，用逗号分隔
3. 最相关的排在前面

排序结果："""
            
            messages = [
                {"role": "system", "content": "你是一个专业的文档相关性评估专家。"},
                {"role": "user", "content": prompt}
            ]
            
            rerank_result = self.ai_client.chat_completion(messages=messages)
            
            # 解析重排序结果
            ranking = self._parse_ranking(rerank_result, len(items))
            
            # 根据重排序结果重新排序
            reranked = []
            for idx in ranking:
                if 0 <= idx < len(items):
                    reranked.append(items[idx])
            
            # 保留不在重排序结果中的项目（按原分数排序）
            seen_indices = set(ranking)
            for idx, item in enumerate(items):
                if idx not in seen_indices:
                    reranked.append(item)
            
            return [item for item, score in reranked[:self.rerank_top_k]]
        except Exception as e:
            logger.warning(f"重排序失败，使用原排序: {str(e)}")
            return [item for item, score in items[:self.rerank_top_k]]
    
    def _parse_ranking(self, ranking_text: str, num_items: int) -> List[int]:
        """解析重排序结果"""
        try:
            # 尝试提取数字列表
            numbers = re.findall(r'\d+', ranking_text)
            if numbers:
                # 转换为0-based索引
                return [int(n) - 1 for n in numbers if 0 < int(n) <= num_items]
            return list(range(num_items))
        except Exception:
            return list(range(num_items))


class RAGService:
    """RAG服务类，实现完整的RAG流程"""
    
    def __init__(self):
        self.ai_client = AIClient.from_config(get_ai_config_manager().get_recommended_config())
        self.max_relevant_items = 5  # 最多返回的相关知识条目数量
        self.similarity_threshold = 0.5  # 相似度阈值，低于此值的条目将被过滤
        self.enhanced_service = EnhancedRAGService()
    
    def generate_response(self, user, query, context_limit=None, use_enhanced=True):
        """生成RAG回复"""
        if use_enhanced:
            return self.enhanced_service.generate_response(user, query, context_limit)
        
        try:
            # 1. 生成查询向量
            query_vector = self._generate_vector(query)
            
            # 2. 向量检索
            relevant_items = self._retrieve_relevant_items(query_vector, user)
            
            if not relevant_items:
                # 如果没有找到相关知识，给予明确提示
                return "抱歉，我在知识库中没有找到与您的问题相关的信息。"
            
            # 3. 构建上下文
            context = self._build_context(relevant_items, context_limit)
            
            # 4. 生成回复
            response = self._generate_answer(query, context, user)
            
            return response
        except Exception as e:
            logger.error(f"生成RAG回复失败: {str(e)}")
            # 处理异常，给予明确提示
            return "抱歉，知识库查询服务暂时不可用，请稍后再试。"
    
    def _generate_vector(self, text):
        """生成文本向量"""
        try:
            return self.ai_client.embedding(text)
        except Exception as e:
            logger.error(f"生成向量失败: {str(e)}")
            return []
    
    def _retrieve_relevant_items(self, query_vector, user):
        """检索相关知识条目"""
        try:
            # 获取所有已发布的知识条目
            knowledge_items = AIKnowledgeItem.objects.filter(status='published')
            
            # 如果没有知识条目，直接返回空列表
            if not knowledge_items.exists():
                return []
            
            # 预加载向量，避免重复查询
            knowledge_vectors = {}
            for vector_record in AIKnowledgeVector.objects.filter(knowledge_item__in=knowledge_items):
                knowledge_vectors[vector_record.knowledge_item.id] = {
                    'vector': vector_record.vector,
                    'dimension': vector_record.dimension
                }
            
            # 计算每个知识条目与查询向量的相似度
            relevant_items = []
            for item in knowledge_items:
                if item.id in knowledge_vectors:
                    # 从预加载的向量中获取
                    vector_data = knowledge_vectors[item.id]
                    item_vector = self._vector_from_bytes(vector_data['vector'], vector_data['dimension'])
                else:
                    # 生成缺失的向量
                    from apps.ai.services.vector_generation_service import vector_generation_service
                    item_vector = vector_generation_service.get_vector_for_knowledge_item(item.id)
                
                if item_vector:
                    # 计算余弦相似度
                    similarity = self._calculate_cosine_similarity(query_vector, item_vector)
                    # 只保留相似度高于阈值的条目
                    if similarity >= self.similarity_threshold:
                        relevant_items.append((item, similarity))
            
            # 按相似度降序排序
            relevant_items.sort(key=lambda x: x[1], reverse=True)
            
            # 返回相似度最高的前N个知识条目
            return [item for item, similarity in relevant_items[:self.max_relevant_items]]
        except Exception as e:
            logger.error(f"检索相关知识失败: {str(e)}")
            return []
    
    def _vector_from_bytes(self, vector_bytes, dimension):
        """从二进制数据转换为向量列表"""
        try:
            import numpy as np
            return np.frombuffer(vector_bytes, dtype=np.float32).tolist()
        except Exception as e:
            logger.error(f"向量转换失败: {str(e)}")
            return None
    
    def _calculate_cosine_similarity(self, vector1, vector2):
        """计算余弦相似度"""
        try:
            import numpy as np
            
            # 将向量转换为numpy数组
            vec1 = np.array(vector1)
            vec2 = np.array(vector2)
            
            # 计算点积
            dot_product = np.dot(vec1, vec2)
            
            # 计算模长
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            # 计算余弦相似度
            if norm1 * norm2 == 0:
                return 0.0
            return dot_product / (norm1 * norm2)
        except Exception as e:
            logger.error(f"计算余弦相似度失败: {str(e)}")
            return 0.0
    
    def _build_context(self, relevant_items, context_limit=None):
        """构建上下文"""
        context = ""
        
        for item in relevant_items:
            # 添加知识条目标题和内容
            item_context = f"\n### {item.title}\n{item.content}"
            
            # 如果设置了上下文长度限制，确保不超过限制
            if context_limit and (len(context) + len(item_context)) > context_limit:
                break
            
            context += item_context
        
        return context
    
    def _generate_answer(self, query, context, user, use_rewritten=False):
        """生成最终回复"""
        # 构建带有上下文的提示模板
        prompt_template = """你是一个专业的AI助手，根据提供的上下文回答用户问题。

上下文：
{context}

用户问题：{query}

要求：
1. 基于提供的上下文回答问题，不要添加无关信息
2. 如果上下文不包含相关信息，直接回答不知道
3. 保持回答简洁、准确
4. 回答语言与用户问题保持一致
5. 如果需要引用上下文内容，请确保准确无误
"""
        
        messages = [
            {"role": "system", "content": "你是一个专业的AI助手，能够根据提供的上下文准确回答用户的问题。"},
            {"role": "user", "content": prompt_template.format(context=context, query=query)}
        ]
        
        try:
            return self.ai_client.chat_completion(messages=messages)
        except Exception as e:
            logger.error(f"生成AI回复失败: {str(e)}")
            return "抱歉，我暂时无法回答您的问题，请稍后再试。"
    
    def batch_generate_vectors(self, knowledge_item_ids=None):
        """批量生成向量"""
        from apps.ai.services.vector_generation_service import vector_generation_service
        return vector_generation_service.batch_generate_vectors(knowledge_item_ids)
    
    def optimize_vectors(self, quality_threshold=0.7):
        """优化低质量向量"""
        from apps.ai.services.vector_quality_service import vector_quality_service
        return vector_quality_service.optimize_vectors(quality_threshold)


rag_service = RAGService()
