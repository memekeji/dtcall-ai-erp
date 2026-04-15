import logging
import json
from datetime import datetime
from .ai_client import AIClient, AIClientError
from .stt_service import transcribe_audio_file, STTError

logger = logging.getLogger(__name__)


class AIAnalysisTool:
    """AI分析工具基类"""

    def __init__(self, provider=None):
        """
        初始化AI分析工具
        :param provider: AI提供商，默认为None（使用数据库中的激活配置）
        """
        import sys
        # 检查是否在迁移过程中，避免访问尚未创建的数据库表
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            # 在迁移过程中，使用默认配置
            self.ai_client = AIClient(provider='openai')
            return

        # 优先使用数据库中的激活配置，但需要捕获数据库表不存在的异常
        try:
            from apps.ai.models import AIModelConfig
            active_configs = AIModelConfig.objects.filter(is_active=True)

            if active_configs.exists():
                # 使用第一个激活的配置
                active_config = active_configs.first()
                try:
                    # 尝试使用激活配置，如果失败则使用默认配置
                    self.ai_client = AIClient(model_config_id=active_config.id)
                except Exception as config_e:
                    logger.warning(f"无法使用激活的AI配置，使用默认配置: {config_e}")
                    self.ai_client = self._create_default_client()
            elif provider:
                # 如果没有激活配置但有指定提供商，使用指定提供商
                try:
                    self.ai_client = AIClient(provider=provider)
                except Exception as provider_e:
                    logger.warning(f"无法使用指定的AI提供商，使用默认配置: {provider_e}")
                    self.ai_client = self._create_default_client()
            else:
                # 默认使用openai提供商
                self.ai_client = self._create_default_client()
        except Exception as e:
            # 如果数据库表不存在或其他数据库错误，使用默认配置
            logger.warning(f"无法从数据库加载AI配置，使用默认配置: {e}")
            self.ai_client = self._create_default_client()

    def _create_default_client(self):
        """
        创建默认的AI客户端，带有友好的错误处理
        :return: AIClient实例或MockClient（如果初始化失败）
        """
        try:
            return AIClient(provider='openai')
        except Exception as e:
            logger.error(f"创建默认AI客户端失败: {str(e)}")
            # 返回一个Mock客户端，用于返回友好的错误信息

            class MockAIClient:
                """Mock AI客户端占位符"""
                provider = 'mock'
                is_available = False
                error_message = str(e)

                def chat_completion(self, *args, **kwargs):
                    raise AIClientError(f"AI客户端不可用: {self.error_message}")

                def text_completion(self, *args, **kwargs):
                    raise AIClientError(f"AI客户端不可用: {self.error_message}")

                def summarize_text(self, *args, **kwargs):
                    raise AIClientError(f"AI客户端不可用: {self.error_message}")

                def analyze_sentiment(self, *args, **kwargs):
                    raise AIClientError(f"AI客户端不可用: {self.error_message}")

                def generate_content(self, *args, **kwargs):
                    raise AIClientError(f"AI客户端不可用: {self.error_message}")

                def embedding(self, *args, **kwargs):
                    raise AIClientError(f"AI客户端不可用: {self.error_message}")

            return MockAIClient()

    def _prepare_prompt(self, context, task_type, **kwargs):
        """准备通用的提示词"""
        base_prompt = {
            "system": "你是一个专业的业务分析师，擅长分析各种业务数据。请严格按照要求进行分析。",
            "user": f"分析任务：{task_type}\n\n业务上下文：{context}\n\n请提供专业、准确的分析结果。"
        }

        # 添加额外的提示词参数
        if kwargs:
            additional_info = "\n\n" + \
                "\n".join([f"{k}：{v}" for k, v in kwargs.items()])
            base_prompt["user"] += additional_info

        return base_prompt

    def analyze(self, context, task_type, **kwargs):
        """
        通用分析方法
        :param context: 分析上下文数据
        :param task_type: 分析任务类型
        :param kwargs: 额外的参数
        :return: 分析结果和置信度
        """
        try:
            prompt = self._prepare_prompt(context, task_type, **kwargs)

            # 调用AI客户端进行分析
            ai_response = self.ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"]}
                ],
                max_tokens=1000,
                temperature=0.3
            )

            # 确保ai_response是字符串格式
            analysis_content = str(
                ai_response) if ai_response is not None else ""

            logger.debug(f"AI分析完成: provider={getattr(self.ai_client, 'provider', None)} len={len(analysis_content)}")

            result = {
                "analysis": analysis_content,
                "confidence": 0.9,  # 默认置信度，可根据实际情况调整
                "timestamp": datetime.now().isoformat(),
                "provider": self.ai_client.provider
            }

            return result
        except Exception as e:
            logger.error(f"AI分析失败: {str(e)}")
            # 即使失败也返回一个更友好的错误消息而不是"分析失败"
            return {
                "analysis": f"分析处理过程中遇到问题: {str(e)}",
                "confidence": 0,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


class CustomerAnalysisTool(AIAnalysisTool):
    """客户分析工具"""

    def classify_customer(self, customer_data):
        """
        智能客户分类
        :param customer_data: 客户数据
        :return: 分类结果
        """
        context = json.dumps(customer_data, ensure_ascii=False)
        task_type = "客户分类"

        # 添加特定的分类要求
        classification_rules = "Please classify from the following dimensions: customer value (high, medium, low), industry type, potential needs, customer maturity (new customer, old customer, loyal customer)"

        result = self.analyze(
            context,
            task_type,
            classification_rules=classification_rules)
        return result

    def generate_customer_profile(self, customer_data, follow_records):
        """
        生成客户画像
        :param customer_data: 客户基本数据
        :param follow_records: 跟进记录数据
        :return: 客户画像分析
        """
        context = f"客户基本信息：{json.dumps(customer_data, ensure_ascii=False)}\n\n跟进记录：{json.dumps(follow_records, ensure_ascii=False)}"
        task_type = "客户画像分析"

        profile_requirements = "Please generate detailed customer profile, including but not limited to: customer characteristics, preferences, pain points, cooperation potential, maintenance strategy suggestions, etc."

        result = self.analyze(
            context,
            task_type,
            profile_requirements=profile_requirements)
        return result


class ProjectAnalysisTool(AIAnalysisTool):
    """项目分析工具"""

    def predict_risk(self, project_data, task_data, work_hours):
        """
        项目风险预测
        :param project_data: 项目基本数据
        :param task_data: 任务数据
        :param work_hours: 工时记录数据
        :return: 风险预测结果
        """
        context = f"项目信息：{json.dumps(project_data, ensure_ascii=False)}\n\n任务信息：{json.dumps(task_data, ensure_ascii=False)}\n\n工时记录：{json.dumps(work_hours, ensure_ascii=False)}"
        task_type = "项目风险预测"

        risk_dimensions = "Please predict risks from the following dimensions: schedule risk, cost risk, quality risk, resource risk, external risk, and provide risk levels (high, medium, low) and response suggestions"

        result = self.analyze(
            context,
            task_type,
            risk_dimensions=risk_dimensions)
        return result

    def predict_project_risk(
            self,
            project_data,
            task_data,
            task_stats,
            total_hours):
        """
        项目风险预测（兼容AI视图调用）
        :param project_data: 项目基本数据
        :param task_data: 任务数据
        :param task_stats: 任务统计数据
        :param total_hours: 总工时
        :return: 风险预测结果
        """
        # 整合任务统计数据到项目数据中
        project_with_stats = project_data.copy()
        project_with_stats.update(task_stats)
        project_with_stats['total_hours'] = total_hours

        # 调用现有的风险预测方法
        return self.predict_risk(project_with_stats, task_data, {})

    def analyze_project_progress(self, project_data, tasks):
        """
        项目进度分析
        :param project_data: 项目基本数据
        :param tasks: 任务数据列表
        :return: 进度分析结果
        """
        context = f"项目信息：{json.dumps(project_data, ensure_ascii=False)}\n\n任务列表：{json.dumps(tasks, ensure_ascii=False)}"
        task_type = "项目进度分析"

        progress_requirements = "Please analyze whether the current project progress is normal, whether there is a delay risk, the completion status of critical path tasks, and provide acceleration suggestions"

        result = self.analyze(
            context,
            task_type,
            analysis_requirements=progress_requirements)
        return result


class MeetingAnalysisTool(AIAnalysisTool):
    """会议分析工具"""

    def _prepare_prompt(self, context, task_type, **kwargs):
        """
        重写会议纪要生成的提示词，确保严格基于实际语音内容
        """
        if task_type == "会议纪要生成":
            # 解析会议数据
            try:
                meeting_data = json.loads(context)

                # 提取关键信息
                meeting_content = meeting_data.get('meeting_content', '')
                transcription = meeting_data.get('transcription', '')

                # 构建严格的系统提示词
                system_prompt = """你是一个专业的会议纪要生成助手。请严格遵循以下规则：

1. **严格基于语音转文字内容**：只能使用提供的语音转文字内容生成会议纪要，严禁添加任何未在语音中提及的虚拟内容、推测信息或默认模板内容

2. **内容提取原则**：
   - 如果语音转文字内容为空或无效，直接返回"语音转文字内容为空，无法生成会议纪要"
   - 如果语音转文字内容简短，如实反映实际内容，不要补充或扩展
   - 只提取实际讨论的内容，不要添加默认的会议框架

3. **结构化要求**：
   - 会议主题：根据语音内容提取实际讨论的主题
   - 会议内容要点：如实总结语音中的讨论要点
   - 决议事项：只记录语音中明确提到的决议
   - 待跟进任务：只记录语音中明确提到的具体任务、负责人和截止时间

4. **真实性保证**：如果语音内容中没有明确提到某些信息（如具体时间、负责人、截止日期），请使用"待确认"或"待定"，严禁虚构

请严格遵守以上规则，确保会议纪要的真实性和准确性。"""

                # 构建用户提示词
                user_prompt = f"""请基于以下语音转文字内容生成会议纪要：

## 语音转文字内容：
{transcription if transcription else meeting_content}

## 会议基本信息：
- 会议主题：{meeting_data.get('meeting_title', '待确认')}
- 参会人员：{meeting_data.get('participants', '待确认')}

## 生成要求：
请严格按照语音转文字内容生成会议纪要，只记录实际讨论的内容。如果语音内容中没有明确提到的信息，请使用"待确认"或"待定"。"""

                return {
                    "system": system_prompt,
                    "user": user_prompt
                }

            except json.JSONDecodeError:
                # 如果JSON解析失败，使用通用提示词
                return super()._prepare_prompt(context, task_type, **kwargs)

        # 其他任务类型使用父类的提示词
        return super()._prepare_prompt(context, task_type, **kwargs)

    def generate_meeting_minutes(
            self,
            user,
            meeting_id,
            audio_file_path=None,
            transcript_content=None,
            started_at=None,
            completed_at=None):
        """
        生成会议纪要（优化版，确保严格基于语音内容）
        :param user: 用户对象
        :param meeting_id: 会议ID
        :param audio_file_path: 音频文件路径（可选）
        :param transcript_content: 语音转文字内容（可选）
        :param started_at: 开始时间
        :param completed_at: 完成时间
        :return: 会议纪要文本内容
        """
        import time
        start_time = time.time()
        logger.info(f"开始生成会议纪要（严格语音内容版），会议ID: {meeting_id}")

        try:
            # 获取会议数据 - 将导入移到方法内部以避免循环导入
            try:
                from apps.oa.models import MeetingRecord
                try:
                    meeting = MeetingRecord.objects.get(id=meeting_id)
                    meeting_data = {
                        'meeting_title': meeting.title,
                        'meeting_content': meeting.content or '',
                        'participants': [],  # 需要从会议记录中获取参会人员
                        'meeting_date': meeting.created_at.strftime('%Y-%m-%d') if meeting.created_at else '待确认'
                    }
                except MeetingRecord.DoesNotExist:
                    logger.error(f"会议记录不存在: {meeting_id}")
                    return "# 会议纪要\n\n## 系统提示\n会议记录不存在，无法生成会议纪要。"
            except ImportError as e:
                logger.warning(f"无法导入MeetingRecord模型: {str(e)}")
                # 使用默认会议数据
                meeting_data = {
                    'meeting_title': f'会议 #{meeting_id}',
                    'meeting_content': '',
                    'participants': [],
                    'meeting_date': '待确认'
                }

            # 快速处理音频文件（控制在10秒内）
            audio_start = time.time()
            if audio_file_path:
                meeting_data['audio_file_path'] = audio_file_path
            meeting_data_with_audio = self._process_audio_file(meeting_data)
            audio_time = time.time() - audio_start
            logger.info(f"音频处理耗时: {audio_time:.2f}秒")

            # 检查语音转文字内容是否有效
            transcription = transcript_content or meeting_data_with_audio.get(
                'transcription', '')
            meeting_content = meeting_data_with_audio.get(
                'meeting_content', '')

            # 如果语音转文字内容为空或无效，直接返回提示信息
            if not transcription or "语音转文字失败" in transcription or "音频文件不存在" in transcription:
                logger.warning("语音转文字内容无效，无法生成会议纪要")
                return "# 会议纪要\n\n## 系统提示\n语音转文字处理失败或音频文件无效，无法基于语音内容生成会议纪要。请检查音频文件或联系系统管理员。"

            # 调用AI分析服务生成会议纪要
            try:
                from apps.ai.services.ai_analysis_service import AIAnalysisService

                result = AIAnalysisService.generate_meeting_minutes(
                    user=user,
                    meeting_id=meeting_id,
                    transcript_content=transcription,
                    started_at=started_at,
                    completed_at=completed_at
                )

                if result['success']:
                    logger.info(
                        f"会议纪要生成成功，使用语音转文字内容: {result.get('used_transcript', False)}")
                    return result['minutes']
                else:
                    logger.error(f"AI会议纪要生成失败: {result.get('error', '未知错误')}")
                    # 失败时返回基于语音转文字内容的简单纪要
                    if transcription:
                        return f"# 会议纪要\n\n## 系统提示\nAI分析服务暂时不可用，以下是语音转文字内容：\n\n{transcription}"
                    else:
                        return "# 会议纪要\n\n## 系统提示\nAI分析服务暂时不可用，且语音转文字内容为空。"

            except Exception as ai_error:
                logger.error(f"调用AI分析服务失败: {str(ai_error)}")
                # AI调用失败时返回基于语音转文字内容的简单纪要
                if transcription:
                    return f"# 会议纪要\n\n## 系统提示\nAI分析服务暂时不可用，以下是语音转文字内容：\n\n{transcription}"
                else:
                    return "# 会议纪要\n\n## 系统提示\nAI分析服务暂时不可用，且语音转文字内容为空。"

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(
                f"生成会议纪要时发生错误（耗时{total_time:.2f}秒）: {str(e)}",
                exc_info=True)
            # 返回基于实际语音内容的错误处理
            return "# 会议纪要\n\n## 系统提示\n会议纪要生成过程中遇到技术问题。请检查语音转文字内容是否有效，或联系系统管理员。"

    def generate_meeting_summary(self, meeting_data):
        """
        生成会议纪要（兼容OA模块调用）
        :param meeting_data: 会议数据
        :return: 会议纪要
        """
        # 调用现有的会议纪要生成方法
        result = self.generate_meeting_minutes(meeting_data)
        return result

    def _process_audio_file(self, meeting_data):
        """
        处理会议数据中的音频文件（使用真正的语音转文字服务）
        :param meeting_data: 会议数据
        :return: 处理后的会议数据，确保包含会议内容
        """
        import time
        import os
        from django.conf import settings

        start_time = time.time()
        logger.info("开始处理会议音频文件（语音转文字版）")

        # 复制会议数据，避免修改原始数据
        processed_data = meeting_data.copy()

        # 确保有meeting_content字段，初始为空字符串
        if 'meeting_content' not in processed_data:
            processed_data['meeting_content'] = ''

        # 检查是否有音频文件路径
        audio_file_path = processed_data.pop('audio_file_path', None)

        try:
            # 检查音频文件是否存在
            if audio_file_path:
                full_audio_path = os.path.join(
                    settings.MEDIA_ROOT, audio_file_path)
                file_exists = os.path.exists(full_audio_path)
                logger.info(f"音频文件检查: {full_audio_path}, 存在状态: {file_exists}")

                if file_exists:
                    file_size = os.path.getsize(full_audio_path)
                    logger.info(f"音频文件大小: {file_size} bytes")

                    # 检查文件大小是否合理（最小10KB，最大100MB）
                    if file_size < 10 * 1024:  # 小于10KB
                        logger.warning(f"音频文件过小，可能无效: {file_size} bytes")
                        transcription_text = "# 会议录音转写内容\n\n## 系统提示\n音频文件过小，无法进行有效语音识别。系统将基于会议基本信息生成会议纪要。"
                    elif file_size > 100 * 1024 * 1024:  # 大于100MB
                        logger.warning(f"音频文件过大: {file_size} bytes")
                        transcription_text = "# 会议录音转写内容\n\n## 系统提示\n音频文件过大，超过处理限制。系统将基于会议基本信息生成会议纪要。"
                    else:
                        # 使用语音转文字服务进行实际转换
                        logger.info(f"开始语音转文字处理，文件大小: {file_size} bytes")

                        try:
                            # 使用STT服务进行语音转文字（自动选择服务类型）
                            transcription_result = transcribe_audio_file(
                                full_audio_path,
                                service_type='auto',  # 自动根据数据库配置选择服务
                                language='zh'  # 中文识别
                            )

                            logger.info("语音转文字处理完成")
                            transcription_text = f"# 会议录音转写内容\n\n{transcription_result}"

                        except STTError as e:
                            logger.error(f"语音转文字服务失败: {str(e)}")
                            transcription_text = f"# 会议录音转写内容\n\n## 系统提示\n语音转文字失败: {str(e)}。系统将基于会议基本信息生成会议纪要。"
                else:
                    transcription_text = "# 会议录音转写内容\n\n## 系统提示\n音频文件不存在，系统将基于会议基本信息生成会议纪要。"
            else:
                logger.warning("未提供音频文件路径")
                transcription_text = "# 会议录音转写内容\n\n## 系统提示\n未提供音频文件路径，系统将基于会议基本信息生成会议纪要。"

            # 将转写内容添加到会议内容中
            if processed_data['meeting_content']:
                processed_data['meeting_content'] += f"\n\n{transcription_text}"
            else:
                processed_data['meeting_content'] = transcription_text

            # 确保返回必要的字段
            processed_data['transcription'] = transcription_text

            elapsed_time = time.time() - start_time
            logger.info(f"音频文件处理完成（语音转文字版），耗时: {elapsed_time:.2f}秒")

        except Exception as e:
            logger.error(f"处理音频文件时发生异常: {str(e)}", exc_info=True)
            # 错误处理，使用简化模板
            transcription_text = f"# 会议录音转写内容\n\n## 系统提示\n处理异常: {str(e)}。系统将基于会议基本信息生成会议纪要。"

            if processed_data['meeting_content']:
                processed_data['meeting_content'] += f"\n\n{transcription_text}"
            else:
                processed_data['meeting_content'] = transcription_text

            processed_data['transcription'] = transcription_text

        # 最终确保会议内容不为空，但避免使用默认模板
        if not processed_data['meeting_content']:
            logger.critical("会议内容为空，使用真实错误提示")
            processed_data['meeting_content'] = "# 会议记录\n\n## 系统提示\n语音转文字处理失败，无法生成会议内容。请检查音频文件或重新上传。"

        total_time = time.time() - start_time
        logger.info(f"音频处理总耗时: {total_time:.2f}秒")

        return processed_data

    def extract_action_items(self, meeting_content):
        """
        从会议内容中提取行动项
        :param meeting_content: 会议内容文本或会议数据字典
        :return: 提取的行动项列表
        """
        # 支持两种参数格式
        if isinstance(meeting_content, dict):
            # 如果传入的是字典，从中提取会议内容
            context = meeting_content.get('meeting_content', '')
            if 'resolutions' in meeting_content and meeting_content['resolutions']:
                context += f"\n\n决议内容：{meeting_content['resolutions']}"
        else:
            # 如果传入的是字符串，直接使用
            context = meeting_content

        task_type = "行动项提取"

        extraction_rules = "请从会议内容中提取所有行动项，每个行动项包含：任务描述、负责人、截止时间"

        result = self.analyze(context, task_type, 提取规则=extraction_rules)

        # 确保返回的是提取结果文本
        if isinstance(result, dict):
            return result.get("analysis", [])
        return result

    def extract_resolutions(self, meeting_content):
        """
        从会议内容中提取会议决议
        :param meeting_content: 会议内容文本或会议数据字典
        :return: 提取的会议决议文本
        """
        # 支持两种参数格式
        if isinstance(meeting_content, dict):
            # 如果传入的是字典，从中提取会议内容
            context = meeting_content.get('meeting_content', '')
        else:
            # 如果传入的是字符串，直接使用
            context = meeting_content

        task_type = "会议决议提取"

        extraction_rules = "请从会议内容中提取所有会议决议，包括重要决策、达成的共识、需要执行的决定等"

        result = self.analyze(context, task_type, 提取规则=extraction_rules)

        # 确保返回的是提取结果文本
        if isinstance(result, dict):
            return result.get("analysis", "")
        return result


class ExpenseAnalysisTool(AIAnalysisTool):
    """报销分析工具"""

    def audit_expense(self, expense_data, rules=None):
        """
        智能报销审核
        :param expense_data: 报销数据
        :param rules: 审核规则（可选）
        :return: 审核结果和建议
        """
        context = json.dumps(expense_data, ensure_ascii=False)
        task_type = "报销审核"

        audit_requirements = "请审核报销单的合理性、合规性，并检查是否存在异常情况"
        if rules:
            audit_requirements += f"\n审核规则：{rules}"

        result = self.analyze(context, task_type, 审核要求=audit_requirements)
        return result

    def detect_abnormal_expense(self, expense_data, historical_data):
        """
        异常报销检测
        :param expense_data: 待检测的报销数据
        :param historical_data: 历史报销数据
        :return: 异常检测结果
        """
        context = f"当前报销：{json.dumps(expense_data, ensure_ascii=False)}\n\n历史报销：{json.dumps(historical_data, ensure_ascii=False)}"
        task_type = "异常报销检测"

        detection_rules = "请对比当前报销与历史报销数据，检测是否存在金额异常、频率异常、类型异常等情况"

        result = self.analyze(context, task_type, 检测规则=detection_rules)
        return result

    def analyze_expense(self, expense_data, user_comment='', user_id=None):
        """
        智能报销审核（兼容AI视图调用）
        :param expense_data: 报销数据
        :param user_comment: 用户评论
        :param user_id: 用户ID
        :return: 审核结果和建议
        """
        context = json.dumps(expense_data, ensure_ascii=False)
        task_type = "报销智能审核"

        audit_requirements = "请审核报销单的合理性、合规性，并检查是否存在异常情况"
        if user_comment:
            audit_requirements += f"\n用户评论：{user_comment}"

        result = self.analyze(context, task_type, 审核要求=audit_requirements)
        return result

    def detect_anomalies(self, expense_data, user_id=None):
        """
        异常报销检测（兼容AI视图调用）
        :param expense_data: 待检测的报销数据
        :param user_id: 用户ID
        :return: 异常检测结果
        """
        # 简单实现，这里可以添加更多历史数据获取逻辑
        context = f"当前报销：{json.dumps(expense_data, ensure_ascii=False)}"
        task_type = "异常报销智能检测"

        detection_rules = "请检测报销单是否存在金额异常、频率异常、类型异常等情况"

        result = self.analyze(context, task_type, 检测规则=detection_rules)
        return result


# 全局实例化常用的分析工具
default_customer_analysis_tool = CustomerAnalysisTool()
default_project_analysis_tool = ProjectAnalysisTool()
default_meeting_analysis_tool = MeetingAnalysisTool()
default_expense_analysis_tool = ExpenseAnalysisTool()


class ContractAnalysisTool(AIAnalysisTool):
    """合同AI分析工具"""
    
    def analyze_risk(self, contract_data):
        """合同风险分析"""
        prompt = f"""请对以下合同信息进行风险分析：
        合同名称: {contract_data.get('name', '')}
        合同金额: {contract_data.get('amount', '')}
        合同内容/条款: {contract_data.get('content', '')}
        
        请从以下维度进行分析并返回JSON格式：
        1. 法律风险评估 (高/中/低及原因)
        2. 财务风险评估 (高/中/低及原因)
        3. 关键条款缺失或异常
        4. 修改建议
        """
        return self._call_ai(prompt)
        
    def extract_key_terms(self, contract_content):
        """提取合同关键条款"""
        prompt = f"""请从以下合同内容中提取关键条款：
        {contract_content}
        
        请提取并返回JSON格式：
        1. 交付/履行期限
        2. 付款条件
        3. 违约责任
        4. 争议解决方式
        """
        return self._call_ai(prompt)

class ApprovalAnalysisTool(AIAnalysisTool):
    """审批AI分析工具"""
    
    def assess_approval(self, approval_data, history_data=None):
        """审批风险评估及建议"""
        prompt = f"""请对以下审批申请进行评估：
        申请类型: {approval_data.get('type', '')}
        申请内容: {approval_data.get('content', '')}
        申请金额/数量: {approval_data.get('amount', '')}
        历史相似申请: {history_data or '无'}
        
        请从以下维度进行分析并返回JSON格式：
        1. 合规性检查
        2. 异常风险提示
        3. 审批建议 (建议通过/建议拒绝/建议补充材料)
        4. 建议理由
        """
        return self._call_ai(prompt)

class InventoryAnalysisTool(AIAnalysisTool):
    """库存AI分析工具"""
    
    def forecast_demand(self, product_data, history_sales):
        """预测需求及库存建议"""
        prompt = f"""请基于以下产品及销售历史数据，预测未来需求并给出库存建议：
        产品信息: {product_data}
        历史销量: {history_sales}
        
        请返回JSON格式：
        1. 未来30天需求预测数量
        2. 建议安全库存量
        3. 补货建议 (需补货/暂不补货)
        4. 建议采购量
        """
        return self._call_ai(prompt)

class TaskAnalysisTool(AIAnalysisTool):
    """任务AI分析工具"""
    
    def estimate_task(self, task_data, assignee_data=None):
        """任务工时预估与分配建议"""
        prompt = f"""请对以下任务进行分析：
        任务名称: {task_data.get('name', '')}
        任务描述: {task_data.get('description', '')}
        相关人员信息: {assignee_data or '无'}
        
        请返回JSON格式：
        1. 预估所需工时(小时)
        2. 建议优先级 (高/中/低)
        3. 技能匹配度评估
        4. 潜在风险或难点
        """
        return self._call_ai(prompt)

# 实例化默认工具
default_contract_analysis_tool = ContractAnalysisTool()
default_approval_analysis_tool = ApprovalAnalysisTool()
default_inventory_analysis_tool = InventoryAnalysisTool()
default_task_analysis_tool = TaskAnalysisTool()
