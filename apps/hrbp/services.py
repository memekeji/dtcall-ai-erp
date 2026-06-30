"""
AI简历分析服务
"""
import os
import json
import logging
from datetime import datetime
from django.utils import timezone
from django.utils import timezone
from apps.ai.utils.ai_client import BaseAIClient
from apps.ai.models import AIModelConfig

logger = logging.getLogger(__name__)


class ResumeAnalysisService:
    """简历分析服务"""

    def __init__(self):
        self.ai_client = None
        self._init_ai_client()

    def _init_ai_client(self):
        """初始化AI客户端"""
        try:
            config = AIModelConfig.objects.filter(
                is_active=True,
                model_type='chat'
            ).first()
            
            if config:
                self.ai_client = BaseAIClient(
                    provider=config.provider,
                    base_url=config.api_base,
                    api_key=config.api_key,
                    model_config=config
                )
        except Exception as e:
            logger.error(f"初始化AI客户端失败: {str(e)}")

    def extract_text_from_file(self, file_path, file_type):
        """从文件中提取文本"""
        try:
            if file_type == 'pdf':
                return self._extract_from_pdf(file_path)
            elif file_type == 'word':
                return self._extract_from_word(file_path)
            elif file_type == 'image':
                return self._extract_from_image(file_path)
            else:
                return ""
        except Exception as e:
            logger.error(f"文件文本提取失败: {str(e)}")
            return ""

    def _extract_from_pdf(self, file_path):
        """从PDF提取文本"""
        try:
            import PyPDF2
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text()
            return text
        except ImportError:
            logger.warning("PyPDF2未安装，尝试使用基础方法")
            return self._extract_text_basic(file_path)
        except Exception as e:
            logger.error(f"PDF文本提取失败: {str(e)}")
            return ""

    def _extract_from_word(self, file_path):
        """从Word文档提取文本"""
        try:
            import docx
            doc = docx.Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text
        except ImportError:
            logger.warning("python-docx未安装，尝试使用基础方法")
            return self._extract_text_basic(file_path)
        except Exception as e:
            logger.error(f"Word文档文本提取失败: {str(e)}")
            return ""

    def _extract_from_image(self, file_path):
        """从图片提取文本（OCR）"""
        try:
            from PIL import Image
            import pytesseract
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            return text
        except ImportError:
            logger.warning("OCR库未安装，无法从图片提取文本")
            return "图片简历需要OCR功能支持"
        except Exception as e:
            logger.error(f"图片文本提取失败: {str(e)}")
            return ""

    def _extract_text_basic(self, file_path):
        """基础文本提取方法"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"基础文本提取失败: {str(e)}")
            return ""

    def analyze_resume(self, resume_text, job_position):
        """分析简历与岗位匹配度"""
        if not self.ai_client:
            raise Exception("AI客户端未初始化")

        prompt = self._build_analysis_prompt(resume_text, job_position)
        
        try:
            response = self._call_ai_api(prompt)
            analysis_result = self._parse_analysis_result(response)
            return analysis_result
        except Exception as e:
            logger.error(f"简历分析失败: {str(e)}")
            raise

    def _build_analysis_prompt(self, resume_text, job_position):
        """构建分析提示词"""
        prompt = f"""你是一位专业的HR招聘专家，请分析以下简历与岗位的匹配情况。

【岗位信息】
岗位名称：{job_position.title}
部门：{job_position.department.title}
岗位描述：{job_position.description}
任职要求：{job_position.requirements}
岗位职责：{job_position.responsibilities}
技能要求：{job_position.skills_required}
学历要求：{job_position.education_required}
工作年限：{job_position.experience_years or '不限'}年

【候选人简历】
{resume_text}

请从以下维度进行详细分析，并以JSON格式返回结果：
{{
    "extracted_info": {{
        "name": "候选人姓名",
        "phone": "联系电话",
        "email": "电子邮箱",
        "education": "学历",
        "experience_years": 工作年限（数字）,
        "skills": "技能列表",
        "work_experience": "工作经历摘要"
    }},
    "match_score": 匹配得分（0-100），
    "match_level": "匹配等级（excellent/good/fair/poor）",
    "strength_analysis": "优势分析（列举3-5点）",
    "weakness_analysis": "不足分析（列举3-5点）",
    "skill_match_detail": "技能匹配详细分析",
    "experience_match_detail": "工作经验匹配详细分析",
    "education_match_detail": "学历匹配详细分析",
    "comprehensive_evaluation": "综合评价",
    "recommendation": "推荐意见（建议是否邀约面试及理由）"
}}

请确保返回有效的JSON格式。"""
        return prompt

    def _call_ai_api(self, prompt):
        """调用AI API"""
        try:
            url = self.ai_client._join_url('/chat/completions')
            headers = {
                'Authorization': f'Bearer {self.ai_client.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': self.ai_client.model_name,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.7,
                'max_tokens': 2000
            }
            
            import requests
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"AI API调用失败: {str(e)}")
            raise

    def _parse_analysis_result(self, response_text):
        """解析AI分析结果"""
        try:
            # 尝试提取JSON部分
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                result = json.loads(json_text)
                return result
            else:
                raise ValueError("无法从响应中提取JSON数据")
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            # 返回默认结果
            return self._get_default_analysis_result()
        except Exception as e:
            logger.error(f"分析结果解析失败: {str(e)}")
            return self._get_default_analysis_result()

    def _get_default_analysis_result(self):
        """获取默认分析结果"""
        return {
            "extracted_info": {
                "name": "",
                "phone": "",
                "email": "",
                "education": "",
                "experience_years": 0,
                "skills": "",
                "work_experience": ""
            },
            "match_score": 50.0,
            "match_level": "fair",
            "strength_analysis": "AI分析暂时不可用",
            "weakness_analysis": "AI分析暂时不可用",
            "skill_match_detail": "AI分析暂时不可用",
            "experience_match_detail": "AI分析暂时不可用",
            "education_match_detail": "AI分析暂时不可用",
            "comprehensive_evaluation": "AI分析暂时不可用，请人工审核",
            "recommendation": "建议进行人工审核"
        }

    def batch_analyze_resumes(self, resume_submissions):
        """批量分析简历"""
        results = []
        for submission in resume_submissions:
            try:
                resume_text = self.extract_text_from_file(
                    submission.file_path,
                    submission.file_type
                )
                analysis = self.analyze_resume(resume_text, submission.position)
                results.append({
                    'submission': submission,
                    'analysis': analysis,
                    'success': True
                })
            except Exception as e:
                results.append({
                    'submission': submission,
                    'error': str(e),
                    'success': False
                })
        return results

    @classmethod
    def complete_analysis(cls, submission):
        import os as _os
        from django.conf import settings as _settings
        from django.utils import timezone as _timezone
        from .models import ResumeAnalysisReport as _Report

        submission.status = 'analyzing'
        submission.save(update_fields=['status'])

        service = cls()
        full = _os.path.join(_settings.MEDIA_ROOT, submission.file_path)
        text = service.extract_text_from_file(full, submission.file_type)
        analysis = service.analyze_resume(text, submission.position)
        extracted = analysis.get('extracted_info', {})

        submission.candidate_name = submission.candidate_name or extracted.get('name', '')
        submission.candidate_phone = submission.candidate_phone or extracted.get('phone', '')
        submission.candidate_email = submission.candidate_email or extracted.get('email', '')
        submission.status = 'completed'
        submission.analyzed_at = _timezone.now()
        submission.save(update_fields=['candidate_name','candidate_phone','candidate_email','status','analyzed_at'])

        defaults = {
            'match_score': analysis.get('match_score',50),
            'match_level': analysis.get('match_level','fair'),
            'extracted_name': extracted.get('name',''),
            'extracted_phone': extracted.get('phone',''),
            'extracted_email': extracted.get('email',''),
            'extracted_education': extracted.get('education',''),
            'extracted_experience_years': extracted.get('experience_years',0),
            'extracted_skills': extracted.get('skills',''),
            'extracted_work_experience': extracted.get('work_experience',''),
            'strength_analysis': analysis.get('strength_analysis',''),
            'weakness_analysis': analysis.get('weakness_analysis',''),
            'skill_match_detail': analysis.get('skill_match_detail',''),
            'experience_match_detail': analysis.get('experience_match_detail',''),
            'education_match_detail': analysis.get('education_match_detail',''),
            'comprehensive_evaluation': analysis.get('comprehensive_evaluation',''),
            'recommendation': analysis.get('recommendation',''),
        }
        report, created = _Report.objects.get_or_create(resume=submission, defaults=defaults)
        if not created:
            for k,v in defaults.items():
                setattr(report, k, v)
            report.save()
        return report


# ========== 招聘流程编排服务 ==========

class RecruitmentPipelineService:
    """招聘全流程编排服务 — 支持AI/自动/手动三种执行模式"""

    STAGE_ORDER = [
        'resume_received', 'ai_matching', 'hr_review',
        'contact_interview', 'interview', 'interview_result',
        'online_exam', 'exam_review', 'offer', 'onboarding',
        'completed'
    ]

    @classmethod
    def get_stage_config(cls, stage):
        """获取阶段的执行模式配置"""
        try:
            from .models import RecruitmentConfig
            config = RecruitmentConfig.objects.filter(stage=stage, is_enabled=True).first()
            return config.exec_mode if config else 'manual'
        except Exception:
            return 'manual'

    @classmethod
    def get_or_create_pipeline(cls, resume_submission):
        """为简历创建或获取流程记录"""
        from .models import CandidatePipeline
        pipeline, created = CandidatePipeline.objects.get_or_create(
            resume_submission=resume_submission,
            defaults={
                'position': resume_submission.position,
                'current_stage': 'resume_received',
            }
        )
        if created:
            cls._log(pipeline, 'resume_received', 'enter', None,
                     f'简历已接收，候选人: {resume_submission.candidate_name or "未知"}')
        return pipeline

    @classmethod
    def advance_stage(cls, pipeline, operator=None, auto_advance=False):
        """推进到下一阶段，根据配置决定执行方式"""
        from .models import PipelineStageLog

        current_idx = cls.STAGE_ORDER.index(pipeline.current_stage) if pipeline.current_stage in cls.STAGE_ORDER else -1
        if current_idx < 0 or current_idx >= len(cls.STAGE_ORDER) - 1:
            return None

        next_stage = cls.STAGE_ORDER[current_idx + 1]
        exec_mode = cls.get_stage_config(next_stage)

        # 记录离开当前阶段
        cls._log(pipeline, pipeline.current_stage, 'exit', operator,
                 f'离开阶段 -> {dict(CandidatePipeline.STAGE_CHOICES).get(next_stage, next_stage)}')

        # 更新阶段
        pipeline.current_stage = next_stage
        pipeline.stage_result = 'pending'
        pipeline.save(update_fields=['current_stage', 'stage_result', 'updated_at'])

        # 记录进入新阶段
        cls._log(pipeline, next_stage, 'enter', operator,
                 f'进入阶段 [{exec_mode}模式]: {dict(CandidatePipeline.STAGE_CHOICES).get(next_stage, next_stage)}')

        # 根据执行模式自动处理
        if exec_mode == 'auto':
            cls._handle_auto_stage(pipeline, operator)
        elif exec_mode == 'ai':
            cls._handle_ai_stage(pipeline, operator)
        # manual模式等待人工操作

        return next_stage

    @classmethod
    def _handle_auto_stage(cls, pipeline, operator):
        """自动模式处理各阶段"""
        from .models import PipelineStageLog

        stage = pipeline.current_stage
        cls._log(pipeline, stage, 'auto_process', operator, '系统自动处理该阶段')

        try:
            if stage == 'ai_matching':
                from .services import ResumeAnalysisService
                report = ResumeAnalysisService.complete_analysis(pipeline.resume_submission)
                cls._log(pipeline, stage, 'auto_advance', operator, f'AI匹配完成，得分: {report.match_score}')
                cls.advance_stage(pipeline, operator, auto_advance=True)
                # AI自动评分主观题
                cls._ai_grade_exam_essays(pipeline, operator)

        except Exception as e:
            logger.error(f'AI处理阶段 {stage} 失败: {str(e)}')

    @classmethod
    def _ai_grade_exam_essays(cls, pipeline, operator):
        """AI评分主观题"""
        from .models import CandidateExam
        try:
            candidate_exam = CandidateExam.objects.filter(
                pipeline=pipeline, status__in=['submitted', 'assigned']
            ).order_by('-created_at').first()
            if candidate_exam:
                ExamService.ai_grade_exam(candidate_exam, operator)
        except Exception as e:
            logger.error(f'AI评分主观题失败: {str(e)}')

    @classmethod
    def approve_candidate(cls, pipeline, reviewer, comment=''):
        """HR审批通过候选人"""
        pipeline.hr_reviewer = reviewer
        pipeline.hr_comment = comment
        pipeline.hr_reviewed_at = timezone.now()
        pipeline.stage_result = 'passed'
        pipeline.save()

        cls._log(pipeline, pipeline.current_stage, 'manual_approve', reviewer,
                 f'HR审批通过。意见: {comment}' if comment else 'HR审批通过')

        # 推进到下一阶段
        cls.advance_stage(pipeline, reviewer)
        return True

    @classmethod
    def reject_candidate(cls, pipeline, reviewer, comment=''):
        """HR淘汰候选人"""
        pipeline.hr_reviewer = reviewer
        pipeline.hr_comment = comment
        pipeline.hr_reviewed_at = timezone.now()
        pipeline.current_stage = 'rejected'
        pipeline.stage_result = 'rejected'
        pipeline.is_active = False
        pipeline.save()

        cls._log(pipeline, pipeline.current_stage, 'manual_reject', reviewer,
                 f'HR淘汰。意见: {comment}' if comment else 'HR淘汰候选人')

        # 是否自动发送淘汰通知
        exec_mode = cls.get_stage_config('rejection_notice')
        if exec_mode in ('ai', 'auto'):
            NotificationService.send_rejection_notification(pipeline, reviewer)

        return True

    @classmethod
    def _log(cls, pipeline, stage, action, operator, detail='', metadata=None):
        """记录流程日志"""
        from .models import PipelineStageLog
        PipelineStageLog.objects.create(
            pipeline=pipeline,
            stage=stage,
            action=action,
            operator=operator,
            detail=detail,
            metadata=metadata or {},
        )


# ========== 通知服务（集成短信/邮件/电话） ==========

class NotificationService:
    """招聘通知服务 — 对接项目消息系统发送短信/邮件/电话"""

    @classmethod
    def _send_message_to_system(cls, user_ids, title, content, related_obj_type='hrbp_pipeline',
                                related_obj_id=None):
        """通过项目消息系统发送站内通知"""
        try:
            from apps.message.services import MessageService

            MessageService.send_broadcast_notification(
                title=title,
                content=content,
                target_user_ids=list(user_ids) if user_ids else [],
                category_code='system',
                priority=2,
                related_object_type=related_obj_type,
                related_object_id=related_obj_id,
            )
            return True
        except Exception as e:
            logger.error(f'发送站内消息失败: {str(e)}')
            return False

    @classmethod
    def _create_notification_record(cls, pipeline, notify_type, scene, recipient,
                                     contact_info, title, content, sender=None):
        """创建通知记录"""
        from .models import RecruitmentNotification
        return RecruitmentNotification.objects.create(
            pipeline=pipeline,
            notify_type=notify_type,
            scene=scene,
            recipient=recipient,
            contact_info=contact_info,
            title=title,
            content=content,
            sender=sender,
            status='sent',
            sent_at=timezone.now(),
        )

    @classmethod
    def _get_candidate_contact(cls, pipeline):
        """获取候选人联系方式"""
        submission = pipeline.resume_submission
        return {
            'name': submission.candidate_name or '候选人',
            'phone': submission.candidate_phone,
            'email': submission.candidate_email,
        }

    @classmethod
    def send_interview_invitation(cls, pipeline, sender=None):
        """发送面试邀请 — 短信+邮件+电话（根据可用性）"""
        contact = cls._get_candidate_contact(pipeline)
        if not contact['phone'] and not contact['email']:
            logger.warning(f'候选人 {contact["name"]} 无联系方式，跳过通知')
            return False

        position = pipeline.position
        title = f'面试邀请 - {position.title}'

        content = f'''尊敬的{contact['name']}：

您好！感谢您应聘我公司"{position.title}"岗位。

经过筛选，我们认为您的背景与岗位要求较为匹配，诚邀您参加面试。

请登录系统查看面试详情或等待HR进一步联系。

如有任何问题，请及时与我们联系。祝好！'''

        sent_any = False

        # 短信通知
        if contact['phone']:
            try:
                cls._create_notification_record(
                    pipeline, 'sms', 'interview_invite',
                    contact['name'], contact['phone'], title, content, sender
                )
                cls._send_sms(contact['phone'], content)
                sent_any = True
                RecruitmentPipelineService._log(
                    pipeline, pipeline.current_stage, 'notification_sent',
                    sender, f'短信已发送至 {contact["phone"]}'
                )
            except Exception as e:
                logger.error(f'短信发送失败: {str(e)}')

        # 邮件通知
        if contact['email']:
            try:
                cls._create_notification_record(
                    pipeline, 'email', 'interview_invite',
                    contact['name'], contact['email'], title, content, sender
                )
                cls._send_email(contact['email'], title, content)
                sent_any = True
                RecruitmentPipelineService._log(
                    pipeline, pipeline.current_stage, 'notification_sent',
                    sender, f'邮件已发送至 {contact["email"]}'
                )
            except Exception as e:
                logger.error(f'邮件发送失败: {str(e)}')

        # 电话通知（如果配置了SIP）
        if contact['phone']:
            try:
                cls._create_notification_record(
                    pipeline, 'phone', 'interview_invite',
                    contact['name'], contact['phone'], title,
                    f'AI语音通知：{contact["name"]}，您有面试邀请，请查收短信或邮件。', sender
                )
                sent_any = True
            except Exception as e:
                logger.error(f'电话通知失败: {str(e)}')

        return sent_any

    @classmethod
    def send_exam_invitation(cls, pipeline, exam_link='', sender=None):
        """发送考核邀请"""
        contact = cls._get_candidate_contact(pipeline)
        title = f'在线考核邀请 - {pipeline.position.title}'
        content = f'''尊敬的{contact['name']}：

您好！请参加"{pipeline.position.title}"岗位的在线考核。

考核链接：{exam_link or '请联系HR获取考核链接'}

祝您考核顺利！'''

        cls._send_to_candidate(pipeline, contact, 'exam_invite', title, content, sender)

    @classmethod
    def send_offer_notification(cls, pipeline, sender=None):
        """发送Offer通知"""
        contact = cls._get_candidate_contact(pipeline)
        title = f'录用通知 - {pipeline.position.title}'
        content = f'''尊敬的{contact['name']}：

恭喜您通过"{pipeline.position.title}"岗位的全部考核！

我们很高兴向您发出录用通知，请登录系统查看Offer详情。

期待您的加入！'''

        cls._send_to_candidate(pipeline, contact, 'offer_notice', title, content, sender)

    @classmethod
    def send_onboarding_notification(cls, pipeline, sender=None):
        """发送入职通知"""
        contact = cls._get_candidate_contact(pipeline)
        title = f'入职通知 - {pipeline.position.title}'
        content = f'''尊敬的{contact['name']}：

欢迎加入我们！请按照入职指引准备相关材料。

如有疑问请随时联系HR。期待与您共事！'''

        cls._send_to_candidate(pipeline, contact, 'onboarding_notice', title, content, sender)

    @classmethod
    def send_rejection_notification(cls, pipeline, sender=None):
        """发送淘汰通知"""
        contact = cls._get_candidate_contact(pipeline)
        title = f'应聘结果通知 - {pipeline.position.title}'
        content = f'''尊敬的{contact['name']}：

感谢您应聘"{pipeline.position.title}"岗位。

经过综合评估，很遗憾本次未能匹配成功。您的简历将保留在我们的储备库中，如有合适机会将优先与您联系。

祝您早日找到理想工作！'''

        cls._send_to_candidate(pipeline, contact, 'rejection_notice', title, content, sender)

    @classmethod
    def _send_to_candidate(cls, pipeline, contact, scene, title, content, sender):
        """向候选人发送通知（短信+邮件）"""
        sent_any = False
        if contact['phone']:
            try:
                cls._create_notification_record(pipeline, 'sms', scene,
                                                 contact['name'], contact['phone'],
                                                 title, content, sender)
                cls._send_sms(contact['phone'], content)
                sent_any = True
            except Exception as e:
                logger.error(f'短信发送失败 [{scene}]: {str(e)}')

        if contact['email']:
            try:
                cls._create_notification_record(pipeline, 'email', scene,
                                                 contact['name'], contact['email'],
                                                 title, content, sender)
                cls._send_email(contact['email'], title, content)
                sent_any = True
            except Exception as e:
                logger.error(f'邮件发送失败 [{scene}]: {str(e)}')

        return sent_any

    @classmethod
    def _send_sms(cls, phone, content):
        """发送短信 — 对接项目短信服务"""
        # 取内容前200字作为短信内容
        sms_content = content[:200]
        try:
            from apps.message.services import MessageService
            # 通过消息系统发送短信通知
            logger.info(f'[HRBP短信] 发送至 {phone}: {sms_content[:50]}...')
            # TODO: 对接实际短信网关 (阿里云/腾讯云短信服务)
            # 当前通过系统通知记录
            MessageService.send_broadcast_notification(
                title='招聘短信通知',
                content=f'[SMS -> {phone}] {sms_content}',
                category_code='system',
                priority=3,
            )
            return True
        except Exception as e:
            logger.error(f'短信服务调用失败: {str(e)}')
            raise

    @classmethod
    def _send_email(cls, email, subject, content):
        """发送邮件 — 对接项目邮件服务"""
        try:
            from django.core.mail import send_mail
            from django.conf import settings

            send_mail(
                subject=subject,
                message=content,
                from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else None,
                recipient_list=[email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f'邮件服务调用失败: {str(e)}')
            raise


# ========== 在线考核服务 ==========

class ExamService:
    """在线考核服务"""

    @classmethod
    def auto_assign_exam(cls, pipeline, operator=None):
        """自动为候选人分配在线考核"""
        from .models import OnlineExam, CandidateExam

        # 匹配岗位相关的考核
        position = pipeline.position
        exams = OnlineExam.objects.filter(is_active=True).order_by('-created_at')

        if not exams.exists():
            RecruitmentPipelineService._log(
                pipeline, 'online_exam', 'notification_failed',
                operator, '没有可用的在线考核'
            )
            return None

        # 选择第一个匹配类型的考核（可扩展匹配逻辑）
        exam = exams.first()
        candidate_exam = CandidateExam.objects.create(
            pipeline=pipeline,
            exam=exam,
            status='assigned',
        )

        RecruitmentPipelineService._log(
            pipeline, 'online_exam', 'auto_process',
            operator, f'已分配考核: {exam.title}'
        )

        # 生成考核链接
        import uuid
        candidate_exam.exam_link = f'/hrbp/exam/{candidate_exam.id}/take/?token={uuid.uuid4().hex[:16]}'
        candidate_exam.save(update_fields=['exam_link'])

        # 自动发送考核通知
        NotificationService.send_exam_invitation(
            pipeline, exam_link=candidate_exam.exam_link, sender=operator
        )

        return candidate_exam

    @classmethod
    def ai_grade_exam(cls, candidate_exam, operator=None):
        """AI自动评分考核"""
        from .models import CandidateExamAnswer

        answers = CandidateExamAnswer.objects.filter(
            candidate_exam=candidate_exam
        ).select_related('question')

        total_correct = 0
        total_questions = answers.count()
        total_score = 0

        for answer in answers:
            question = answer.question
            # 客观题自动判分
            if question.question_type in ('single', 'true_false'):
                if answer.answer.strip().upper() == question.correct_answer.strip().upper():
                    answer.is_correct = True
                    answer.ai_score = question.score
                    total_correct += 1
                    total_score += float(question.score)
                else:
                    answer.is_correct = False
                    answer.ai_score = 0
                answer.save(update_fields=['is_correct', 'ai_score'])

            elif question.question_type == 'multiple':
                correct_parts = set(part.strip() for part in question.correct_answer.split(',') if part.strip())
                answer_parts = set(part.strip() for part in answer.answer.split(',') if part.strip())
                if correct_parts == answer_parts:
                    answer.is_correct = True
                    answer.ai_score = question.score
                    total_correct += 1
                    total_score += float(question.score)
                else:
                    answer.is_correct = False
                    answer.ai_score = 0
                answer.save(update_fields=['is_correct', 'ai_score'])

            elif question.question_type in ('essay', 'code'):
                # 主观题尝试AI评分
                try:
                    score, comment = cls._ai_score_essay(
                        question.content, answer.answer, question.correct_answer
                    )
                    answer.ai_score = score
                    answer.ai_comment = comment
                    total_score += float(score)
                except Exception as e:
                    logger.error(f'AI评分主观题失败: {str(e)}')
                    answer.ai_score = question.score * 0.6
                    answer.ai_comment = 'AI自动评分（仅供参考）'
                    total_score += float(answer.ai_score)
                answer.is_correct = None
                answer.save(update_fields=['is_correct', 'ai_score', 'ai_comment'])

        candidate_exam.total_correct = total_correct
        candidate_exam.total_questions = total_questions
        candidate_exam.ai_score = total_score
        candidate_exam.ai_feedback = f'自动评分完成：正确 {total_correct}/{total_questions} 题，总分 {total_score}'
        candidate_exam.status = 'ai_graded'
        candidate_exam.save()

        RecruitmentPipelineService._log(
            candidate_exam.pipeline, 'online_exam', 'ai_process',
            operator, f'AI评分完成: {total_score}分 ({total_correct}/{total_questions})'
        )

        return candidate_exam

    @classmethod
    def _ai_score_essay(cls, question, answer, reference):
        """使用AI对主观题评分"""
        try:
            from apps.ai.utils.ai_client import BaseAIClient
            from apps.ai.models import AIModelConfig

            config = AIModelConfig.objects.filter(is_active=True, model_type='chat').first()
            if not config:
                return (60, 'AI评分服务不可用')

            ai_client = BaseAIClient(
                provider=config.provider,
                base_url=config.api_base,
                api_key=config.api_key,
                model_config=config,
            )

            url = ai_client._join_url('/chat/completions')
            headers = {
                'Authorization': f'Bearer {ai_client.api_key}',
                'Content-Type': 'application/json'
            }
            prompt = f'''请对以下主观题作答进行评分（满分100分），返回JSON格式: {{"score": 数字, "comment": "评语"}}

【题目】{question}
【参考答案】{reference}
【考生答案】{answer}'''

            data = {
                'model': ai_client.model_name,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 300,
            }

            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            text = result['choices'][0]['message']['content']

            import json, re
            json_match = re.search(r'\{[^}]+\}', text)
            if json_match:
                parsed = json.loads(json_match.group())
                return (parsed.get('score', 60), parsed.get('comment', 'AI评分'))
            return (60, 'AI评分（默认）')
        except Exception:
            return (60, 'AI评分（默认，仅供参考）')



class ExamAutoGenerationService:
    """自动组卷服务 — 按岗位/职能+难度+标签+题库分组综合抽题"""

    @classmethod
    def get_available_questions(cls, bank_group_ids=None, position_id=None,
                                 function_tags=None, difficulty=None, tags=None,
                                 question_types=None):
        """获取符合条件的题库题目"""
        from .models import ExamQuestion

        qs = ExamQuestion.objects.filter(bank_group__isnull=False, bank_group__is_active=True)

        if bank_group_ids:
            if isinstance(bank_group_ids, (list, tuple)):
                qs = qs.filter(bank_group_id__in=bank_group_ids)
            else:
                qs = qs.filter(bank_group_id=bank_group_ids)

        if position_id:
            qs = qs.filter(bank_group__position_id=position_id)

        if function_tags and isinstance(function_tags, list):
            qs = qs.filter(bank_group__function_tags__contains=function_tags)

        if difficulty:
            qs = qs.filter(bank_group__difficulty=difficulty)

        if tags and isinstance(tags, list):
            for tag in tags:
                qs = qs.filter(bank_group__tags__contains=[tag])

        if question_types and isinstance(question_types, list):
            qs = qs.filter(question_type__in=question_types)

        return qs.distinct()

    @classmethod
    def generate_exam_from_rule(cls, rule, exam_title=None, creator=None):
        """根据规则自动生成考核试卷"""
        from .models import OnlineExam, ExamQuestion

        bank_group_ids = list(rule.bank_groups.values_list('id', flat=True))
        question_pool = cls.get_available_questions(
            bank_group_ids=bank_group_ids,
            position_id=rule.position_filter_id,
            question_types=list(rule.question_type_distribution.keys()) if rule.question_type_distribution else None,
        )

        # 按难度分布抽题
        selected_questions = []
        difficulty_dist = rule.difficulty_distribution or {}
        type_dist = rule.question_type_distribution or {}

        # 按难度分组
        for difficulty, percent in difficulty_dist.items():
            count = max(1, int(rule.total_questions * percent / 100))
            diff_qs = question_pool.filter(bank_group__difficulty=difficulty).order_by('?')[:count]
            selected_questions.extend(list(diff_qs))

        # 补充未满足的题型分布
        for qtype, count in type_dist.items():
            already = sum(1 for q in selected_questions if q.question_type == qtype)
            needed = count - already
            if needed > 0:
                extra = question_pool.filter(question_type=qtype).exclude(
                    id__in=[q.id for q in selected_questions]
                ).order_by('?')[:needed]
                selected_questions.extend(list(extra))

        # 如果有标签要求，过滤
        tag_reqs = rule.tag_requirements or {}
        required_tags = tag_reqs.get('required', [])
        if required_tags:
            weighted = []
            for q in selected_questions:
                if q.tags and any(t in q.tags for t in required_tags):
                    weighted.append(q)
            # 优先使用带标签的题目
            remaining = [q for q in selected_questions if q not in weighted]
            selected_questions = weighted + remaining

        # 截取到题目总数
        selected_questions = selected_questions[:rule.total_questions]

        # 创建考核
        title = exam_title or f'{rule.name} - 自动组卷 {timezone.now().strftime("%Y%m%d%H%M")}'
        exam = OnlineExam.objects.create(
            title=title,
            exam_type='custom',
            difficulty='medium',
            description=rule.description or f'由规则"{rule.name}"自动生成',
            duration_minutes=60,
            total_score=rule.total_score,
            passing_score=float(rule.total_score) * 0.6,
            creator=creator,
        )

        # 创建题目副本并关联到考核
        for idx, q in enumerate(selected_questions, 1):
            ExamQuestion.objects.create(
                exam=exam,
                question_type=q.question_type,
                content=q.content,
                options=q.options,
                correct_answer=q.correct_answer,
                score=q.score,
                sort_order=idx,
                bank_group=q.bank_group,
                tags=q.tags,
            )

        return exam, len(selected_questions)

    @classmethod
    def preview_generation(cls, rule):
        """预览组卷结果（不创建考核）"""
        bank_group_ids = list(rule.bank_groups.values_list('id', flat=True))
        question_pool = cls.get_available_questions(
            bank_group_ids=bank_group_ids,
            position_id=rule.position_filter_id,
        )

        result = {
            'total_available': question_pool.count(),
            'by_difficulty': {},
            'by_type': {},
            'by_group': {},
        }

        for q in question_pool:
            diff = q.bank_group.get_difficulty_display() if q.bank_group else '未知'
            result['by_difficulty'][diff] = result['by_difficulty'].get(diff, 0) + 1

            qtype = q.get_question_type_display()
            result['by_type'][qtype] = result['by_type'].get(qtype, 0) + 1

            if q.bank_group:
                result['by_group'][q.bank_group.name] = result['by_group'].get(q.bank_group.name, 0) + 1

        return result
