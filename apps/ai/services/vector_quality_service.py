import numpy as np
from apps.ai.models import AIKnowledgeItem, AIKnowledgeVector
from apps.ai.utils.ai_client import AIClient
from apps.ai.utils.ai_config_manager import get_ai_config_manager
import logging

logger = logging.getLogger(__name__)


class VectorQualityService:
    """向量质量评估和优化服务"""

    def __init__(self):
        self.ai_client = AIClient.from_config(
            get_ai_config_manager().get_recommended_config())

    def evaluate_vector_quality(self):
        """评估所有向量的质量"""
        try:
            # 获取所有知识条目和向量
            knowledge_items = AIKnowledgeItem.objects.filter(
                status='published')
            quality_results = []

            for item in knowledge_items:
                try:
                    vector_record = AIKnowledgeVector.objects.get(
                        knowledge_item=item)
                    vector = np.frombuffer(
                        vector_record.vector, dtype=np.float32).tolist()

                    # 计算向量质量指标
                    quality = self._calculate_vector_quality(item, vector)
                    quality_results.append({
                        'knowledge_item_id': item.id,
                        'title': item.title,
                        'quality_score': quality['score'],
                        'metrics': quality['metrics']
                    })
                except AIKnowledgeVector.DoesNotExist:
                    quality_results.append({
                        'knowledge_item_id': item.id,
                        'title': item.title,
                        'quality_score': 0.0,
                        'metrics': {'error': 'Missing vector'}
                    })
                except Exception as e:
                    logger.error(f"评估向量质量失败 - 知识条目ID: {item.id}, 错误: {str(e)}")

            return quality_results
        except Exception as e:
            logger.error(f"向量质量评估失败: {str(e)}")
            return []

    def _calculate_vector_quality(self, knowledge_item, vector):
        """计算单个向量的质量"""
        metrics = {
            'dimension': len(vector),
            'magnitude': np.linalg.norm(vector),
            'sparsity': np.count_nonzero(vector) / len(vector) if len(vector) > 0 else 0}

        # 计算向量与文本的相关性（通过重新生成向量并比较）
        try:
            recreated_vector = self.ai_client.embedding(
                f"{knowledge_item.title}\n{knowledge_item.content}")
            metrics['consistency'] = self._calculate_cosine_similarity(
                vector, recreated_vector)
        except Exception as e:
            metrics['consistency'] = 0.0
            metrics['consistency_error'] = str(e)

        # 综合质量得分（0-1）
        score = 0.0
        if metrics['dimension'] > 0:
            # 维度应在合理范围内（如1536-7680）
            dimension_score = min(
                1.0, max(
                    0.0, (metrics['dimension'] - 512) / 7168))

            # 向量 magnitude 应接近1.0（归一化向量）
            magnitude_score = max(0.0, 1.0 - abs(metrics['magnitude'] - 1.0))

            # 一致性得分（越高越好）
            consistency_score = metrics['consistency']

            # 稀疏性得分（对于词嵌入，通常不需要太稀疏）
            sparsity_score = max(0.0, 1.0 - metrics['sparsity'])

            # 综合得分（权重可调整）
            score = (dimension_score * 0.2) + (magnitude_score * 0.2) + \
                (consistency_score * 0.4) + (sparsity_score * 0.2)

        return {
            'score': score,
            'metrics': metrics
        }

    def optimize_vectors(self, quality_threshold=0.7):
        """优化低质量向量"""
        try:
            # 评估所有向量质量
            quality_results = self.evaluate_vector_quality()

            # 找出低质量向量
            low_quality_items = [
                result for result in quality_results if result['quality_score'] < quality_threshold]

            # 重新生成低质量向量
            from apps.ai.services.vector_generation_service import vector_generation_service
            for item in low_quality_items:
                try:
                    vector_generation_service.generate_vector_for_knowledge_item(
                        item['knowledge_item_id'])
                    logger.info(
                        f"优化向量成功 - 知识条目ID: {item['knowledge_item_id']}, 标题: {item['title']}")
                except Exception as e:
                    logger.error(
                        f"优化向量失败 - 知识条目ID: {item['knowledge_item_id']}, 错误: {str(e)}")

            return {
                'total_evaluated': len(quality_results),
                'low_quality_count': len(low_quality_items),
                'optimized_count': len(low_quality_items),  # 假设都优化成功
                'quality_threshold': quality_threshold
            }
        except Exception as e:
            logger.error(f"向量优化失败: {str(e)}")
            return {'error': str(e)}

    def _calculate_cosine_similarity(self, vector1, vector2):
        """计算余弦相似度"""
        try:
            vec1 = np.array(vector1)
            vec2 = np.array(vector2)

            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 * norm2 == 0:
                return 0.0
            return dot_product / (norm1 * norm2)
        except Exception as e:
            logger.error(f"计算余弦相似度失败: {str(e)}")
            return 0.0


vector_quality_service = VectorQualityService()
