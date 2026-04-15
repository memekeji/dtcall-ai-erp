import numpy as np
import logging
from apps.ai.models import AIKnowledgeItem, AIKnowledgeVector
from apps.ai.utils.ai_client import AIClient
from apps.ai.utils.ai_config_manager import get_ai_config_manager

logger = logging.getLogger(__name__)


class VectorGenerationService:
    """向量生成服务类"""

    def __init__(self):
        self.ai_client = AIClient.from_config(
            get_ai_config_manager().get_recommended_config())

    def generate_vector_for_knowledge_item(self, knowledge_item_id):
        """为单个知识条目生成向量"""
        knowledge_item = None
        try:
            # 获取知识条目
            knowledge_item = AIKnowledgeItem.objects.get(id=knowledge_item_id)

            # 只处理已发布的知识条目
            if knowledge_item.status != 'published':
                logger.info(
                    f"跳过未发布的知识条目 - ID: {knowledge_item_id}, 状态: {knowledge_item.status}")
                return False

            # 生成向量
            vector = self._generate_vector(knowledge_item)
            if not vector:
                logger.error(f"生成向量失败 - 知识条目ID: {knowledge_item_id}, 向量为空")
                return False

            # 存储向量
            self._save_vector(knowledge_item, vector)
            logger.info(
                f"成功生成向量 - 知识条目ID: {knowledge_item_id}, 标题: {knowledge_item.title}")
            return True
        except AIKnowledgeItem.DoesNotExist:
            logger.error(f"知识条目不存在 - ID: {knowledge_item_id}")
            return False
        except Exception as e:
            knowledge_item_id_log = knowledge_item.id if knowledge_item else knowledge_item_id
            logger.error(
                f"生成向量失败 - 知识条目ID: {knowledge_item_id_log}, 错误: {str(e)}")
            logger.error(f"异常类型: {type(e).__name__}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return False

    def batch_generate_vectors(self, knowledge_item_ids=None):
        """批量生成向量"""
        try:
            # 构建查询集
            queryset = AIKnowledgeItem.objects.filter(status='published')
            if knowledge_item_ids:
                queryset = queryset.filter(id__in=knowledge_item_ids)

            total = queryset.count()
            logger.info(f"开始批量生成向量 - 总数量: {total}")

            success_count = 0
            error_count = 0

            for item in queryset:
                if self.generate_vector_for_knowledge_item(item.id):
                    success_count += 1
                else:
                    error_count += 1

            logger.info(
                f"批量生成向量完成 - 成功: {success_count}, 失败: {error_count}, 总数量: {total}")
            return {
                'success_count': success_count,
                'error_count': error_count,
                'total_count': total
            }
        except Exception as e:
            logger.error(f"批量生成向量失败: {str(e)}")
            return {'error': str(e)}

    def update_all_vectors(self):
        """更新所有向量"""
        return self.batch_generate_vectors()

    def _generate_vector(self, knowledge_item):
        """生成向量"""
        try:
            # 组合标题和内容
            full_text = f"{knowledge_item.title}\n{knowledge_item.content}"
            logger.info(
                f"生成向量 - 知识条目ID: {knowledge_item.id}, 原始文本长度: {len(full_text)}")

            # 文本长度限制，避免超过API限制
            # 阿里千问API一般限制在100000字符以内
            max_text_length = 100000
            if len(full_text) > max_text_length:
                text = full_text[:max_text_length]
                logger.info(
                    f"文本过长，已截断 - 知识条目ID: {knowledge_item.id}, 截断后长度: {len(text)}")
            else:
                text = full_text

            # 生成向量
            return self.ai_client.embedding(text)
        except Exception as e:
            logger.error(f"生成向量失败 - 知识条目ID: {knowledge_item.id}, 错误: {str(e)}")
            logger.error(f"异常类型: {type(e).__name__}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return []

    def _save_vector(self, knowledge_item, vector):
        """存储向量"""
        # 将向量转换为二进制
        vector_bytes = np.array(vector).tobytes()
        dimension = len(vector)

        # 保存或更新向量
        AIKnowledgeVector.objects.update_or_create(
            knowledge_item=knowledge_item,
            defaults={
                'vector': vector_bytes,
                'dimension': dimension
            }
        )

    def get_vector_for_knowledge_item(self, knowledge_item_id):
        """获取知识条目的向量"""
        try:
            vector_record = AIKnowledgeVector.objects.get(
                knowledge_item_id=knowledge_item_id)
            return np.frombuffer(
                vector_record.vector,
                dtype=np.float32).tolist()
        except AIKnowledgeVector.DoesNotExist:
            # 如果向量不存在，尝试生成向量
            logger.info(f"向量不存在，尝试生成 - 知识条目ID: {knowledge_item_id}")
            self.generate_vector_for_knowledge_item(knowledge_item_id)
            # 再次尝试获取向量
            try:
                vector_record = AIKnowledgeVector.objects.get(
                    knowledge_item_id=knowledge_item_id)
                return np.frombuffer(
                    vector_record.vector,
                    dtype=np.float32).tolist()
            except AIKnowledgeVector.DoesNotExist:
                logger.error(f"无法获取或生成向量 - 知识条目ID: {knowledge_item_id}")
                return None
        except Exception as e:
            logger.error(f"获取向量失败 - 知识条目ID: {knowledge_item_id}, 错误: {str(e)}")
            return None


vector_generation_service = VectorGenerationService()
