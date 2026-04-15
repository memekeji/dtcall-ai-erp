"""
意图识别优化服务
负责记录意图识别日志、分析效果、持续优化模型
"""

import logging
from typing import Dict, Any, List, Optional
from django.contrib.auth.models import User
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from apps.ai.models import AIIntentRecognition, AIIntentRecognitionLog

logger = logging.getLogger(__name__)


class IntentOptimizationService:
    """
    意图识别优化服务
    提供日志记录、效果分析、模型优化等功能
    """

    def __init__(self):
        pass

    def log_recognition(self,
                        user: User,
                        query: str,
                        recognition_result: Dict[str,
                                                 Any],
                        actual_intent: Optional[str] = None,
                        user_feedback: str = '',
                        is_correct: bool = True) -> AIIntentRecognitionLog:
        """
        记录意图识别日志

        Args:
            user: 当前用户
            query: 用户查询文本
            recognition_result: 意图识别结果
            actual_intent: 实际意图（用户确认后）
            user_feedback: 用户反馈
            is_correct: 是否正确

        Returns:
            AIIntentRecognitionLog: 创建的日志记录
        """
        try:
            log_entry = AIIntentRecognitionLog.objects.create(
                user=user if hasattr(user, 'id') else None,
                query_text=query,
                recognized_intent=recognition_result.get('intent', 'UNKNOWN'),
                confidence=recognition_result.get('confidence', 0.0),
                actual_intent=actual_intent or recognition_result.get(
                    'intent', 'UNKNOWN'),
                entities=recognition_result.get('entities', {}),
                action_taken=recognition_result.get('action', 'unknown'),
                result=self._determine_result(recognition_result, is_correct),
                user_feedback=user_feedback,
                is_correct=is_correct
            )

            logger.info(
                f"记录意图识别日志：query={query[:50]}, intent={log_entry.recognized_intent}, "
                f"confidence={log_entry.confidence:.2f}, correct={is_correct}")

            if not is_correct:
                self._trigger_optimization(log_entry)

            return log_entry

        except Exception as e:
            logger.error(f"记录意图识别日志失败：{str(e)}")
            return None

    def _determine_result(
            self, recognition_result: Dict[str, Any], is_correct: bool) -> str:
        """确定识别结果状态"""
        confidence = recognition_result.get('confidence', 0.0)

        if not is_correct:
            return 'failure'
        elif confidence < 0.65:
            return 'uncertain'
        elif confidence >= 0.85:
            return 'confirmed'
        else:
            return 'success'

    def _trigger_optimization(self, log_entry: AIIntentRecognitionLog):
        """触发优化流程"""
        try:
            intent_type = log_entry.recognized_intent

            incorrect_count = AIIntentRecognitionLog.objects.filter(
                recognized_intent=intent_type,
                is_correct=False,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()

            if incorrect_count >= 5:
                logger.warning(
                    f"意图 {intent_type} 在过去 7 天内有{incorrect_count}次识别错误，触发优化流程")
                self._optimize_intent_config(intent_type)

        except Exception as e:
            logger.error(f"触发优化流程失败：{str(e)}")

    def _optimize_intent_config(self, intent_type: str):
        """优化意图配置"""
        try:
            intent_config = AIIntentRecognition.objects.filter(
                intent_type=intent_type,
                is_active=True
            ).first()

            if not intent_config:
                logger.warning(f"未找到意图配置：{intent_type}")
                return

            incorrect_logs = AIIntentRecognitionLog.objects.filter(
                recognized_intent=intent_type,
                is_correct=False,
                used_for_training=False
            ).order_by('-created_at')[:20]

            if incorrect_logs.count() < 3:
                logger.info(f"意图 {intent_type} 错误样本不足，暂不优化")
                return

            new_examples = []
            for log in incorrect_logs:
                if log.actual_intent == intent_type:
                    new_examples.append(log.query_text)

            if new_examples:
                current_examples = intent_config.examples if isinstance(
                    intent_config.examples, list) else []
                current_examples.extend(new_examples[:10])
                intent_config.examples = current_examples[:50]
                intent_config.save()

                for log in incorrect_logs:
                    log.used_for_training = True
                    log.save()

                logger.info(
                    f"优化意图配置成功：{intent_type}, 新增{len(new_examples)}个示例")

        except Exception as e:
            logger.error(f"优化意图配置失败：{str(e)}")

    def get_accuracy_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        获取准确率统计

        Args:
            days: 统计天数

        Returns:
            Dict[str, Any]: 统计数据
        """
        try:
            start_date = timezone.now() - timedelta(days=days)

            logs = AIIntentRecognitionLog.objects.filter(
                created_at__gte=start_date)

            total_count = logs.count()
            correct_count = logs.filter(is_correct=True).count()
            accuracy_rate = (
                correct_count /
                total_count *
                100) if total_count > 0 else 0.0

            intent_stats = logs.values('recognized_intent').annotate(
                total=Count('id'),
                correct=Count('id', filter=Q(is_correct=True)),
                avg_confidence=Avg('confidence')
            )

            intent_accuracy = []
            for stat in intent_stats:
                intent_accuracy.append({
                    'intent_type': stat['recognized_intent'],
                    'total': stat['total'],
                    'correct': stat['correct'],
                    'accuracy_rate': (stat['correct'] / stat['total'] * 100) if stat['total'] > 0 else 0.0,
                    'avg_confidence': float(stat['avg_confidence']) if stat['avg_confidence'] else 0.0
                })

            return {
                'total_count': total_count,
                'correct_count': correct_count,
                'accuracy_rate': round(accuracy_rate, 2),
                'intent_accuracy': intent_accuracy,
                'period_days': days
            }

        except Exception as e:
            logger.error(f"获取准确率统计失败：{str(e)}")
            return {
                'total_count': 0,
                'correct_count': 0,
                'accuracy_rate': 0.0,
                'intent_accuracy': [],
                'period_days': days
            }

    def get_low_confidence_queries(
            self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取低置信度查询列表

        Args:
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 低置信度查询列表
        """
        try:
            low_conf_logs = AIIntentRecognitionLog.objects.filter(
                confidence__lt=0.65
            ).order_by('-created_at')[:limit]

            return [
                {
                    'id': log.id,
                    'query_text': log.query_text,
                    'recognized_intent': log.recognized_intent,
                    'confidence': log.confidence,
                    'actual_intent': log.actual_intent,
                    'is_correct': log.is_correct,
                    'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'user': log.user.username if log.user else 'Anonymous'
                }
                for log in low_conf_logs
            ]

        except Exception as e:
            logger.error(f"获取低置信度查询失败：{str(e)}")
            return []

    def get_training_samples(self, intent_type: Optional[str] = None,
                             limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取训练样本

        Args:
            intent_type: 意图类型
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 训练样本列表
        """
        try:
            query = AIIntentRecognitionLog.objects.filter(
                is_correct=True,
                used_for_training=False
            )

            if intent_type:
                query = query.filter(actual_intent=intent_type)

            logs = query.order_by('-confidence', '-created_at')[:limit]

            return [
                {
                    'query_text': log.query_text,
                    'intent_type': log.actual_intent,
                    'confidence': log.confidence,
                    'entities': log.entities,
                    'action': log.action_taken
                }
                for log in logs
            ]

        except Exception as e:
            logger.error(f"获取训练样本失败：{str(e)}")
            return []

    def mark_as_training_used(self, log_ids: List[int]):
        """
        标记日志已用于训练

        Args:
            log_ids: 日志 ID 列表
        """
        try:
            AIIntentRecognitionLog.objects.filter(id__in=log_ids).update(
                used_for_training=True
            )
            logger.info(f"标记{len(log_ids)}条日志已用于训练")
        except Exception as e:
            logger.error(f"标记训练样本失败：{str(e)}")

    def retrain_intent_model(
            self, intent_type: Optional[str] = None) -> Dict[str, Any]:
        """
        重新训练意图模型

        Args:
            intent_type: 意图类型，None 表示训练所有意图

        Returns:
            Dict[str, Any]: 训练结果
        """
        try:
            training_samples = self.get_training_samples(
                intent_type, limit=500)

            if not training_samples:
                return {
                    'success': False,
                    'message': '没有可用的训练样本',
                    'samples_count': 0
                }

            intent_config = AIIntentRecognition.objects.filter(
                intent_type=intent_type,
                is_active=True
            ).first() if intent_type else None

            if intent_type and not intent_config:
                return {
                    'success': False,
                    'message': f'未找到意图配置：{intent_type}',
                    'samples_count': len(training_samples)
                }

            new_examples = [sample['query_text']
                            for sample in training_samples]

            if intent_config:
                current_examples = intent_config.examples if isinstance(
                    intent_config.examples, list) else []
                current_examples.extend(new_examples)
                intent_config.examples = list(set(current_examples))[:100]
                intent_config.training_count += len(new_examples)

                recent_accuracy = self.get_accuracy_statistics(days=7)
                intent_accuracy = next(
                    (item for item in recent_accuracy['intent_accuracy']
                     if item['intent_type'] == intent_type),
                    None
                )
                if intent_accuracy:
                    intent_config.accuracy_rate = intent_accuracy['accuracy_rate'] / 100.0

                intent_config.save()

                log_ids = [sample['id'] for sample in training_samples]
                self.mark_as_training_used(log_ids)

                logger.info(
                    f"重新训练意图模型成功：{intent_type}, 使用{len(new_examples)}个样本")

                return {
                    'success': True,
                    'message': f'训练完成，使用{len(new_examples)}个样本',
                    'samples_count': len(new_examples),
                    'intent_type': intent_type
                }
            else:
                for sample in training_samples:
                    sample_intent = sample['intent_type']
                    if sample_intent:
                        sample_intent_config = AIIntentRecognition.objects.filter(
                            intent_type=sample_intent, is_active=True).first()
                        if sample_intent_config:
                            current_examples = sample_intent_config.examples if isinstance(
                                sample_intent_config.examples, list) else []
                            current_examples.append(sample['query_text'])
                            sample_intent_config.examples = list(
                                set(current_examples))[:100]
                            sample_intent_config.training_count += 1
                            sample_intent_config.save()

                log_ids = [sample['id'] for sample in training_samples]
                self.mark_as_training_used(log_ids)

                logger.info(f"重新训练所有意图模型成功，使用{len(training_samples)}个样本")

                return {
                    'success': True,
                    'message': f'训练完成，使用{len(training_samples)}个样本',
                    'samples_count': len(training_samples),
                    'intent_type': 'all'
                }

        except Exception as e:
            logger.error(f"重新训练意图模型失败：{str(e)}")
            return {
                'success': False,
                'message': f'训练失败：{str(e)}',
                'samples_count': 0
            }


intent_optimization_service = IntentOptimizationService()
