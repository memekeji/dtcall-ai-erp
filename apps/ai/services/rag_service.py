from django.conf import settings
from apps.ai.models import AIKnowledgeItem, AIKnowledgeVector
from apps.ai.utils.ai_client import AIClient
from apps.ai.utils.ai_config_manager import get_ai_config_manager
import logging

logger = logging.getLogger(__name__)


class RAGService:
    """RAG服务类，实现完整的RAG流程"""
    
    def __init__(self):
        self.ai_client = AIClient.from_config(get_ai_config_manager().get_recommended_config())
        self.max_relevant_items = 5  # 最多返回的相关知识条目数量
        self.similarity_threshold = 0.5  # 相似度阈值，低于此值的条目将被过滤
    
    def generate_response(self, user, query, context_limit=None):
        """生成RAG回复"""
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
    
    def _generate_answer(self, query, context, user):
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
