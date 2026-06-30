"""
AI-HRBP视图
"""
import os
import json
import logging
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.db.models import Q, Count
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings

from apps.system.views.base import CustomLoginRequiredMixin
from .forms import JobPositionForm, ResumeSubmissionForm, CandidatePipelineForm, OnlineExamForm, ExamQuestionForm, QuestionBankGroupForm, ExamAutoGenerationRuleForm, OnboardingForm, RecruitmentConfigForm
from .models import JobPosition, ResumeSubmission, ResumeAnalysisReport, InterviewInvitation, CandidatePipeline, PipelineStageLog, OnlineExam, ExamQuestion, QuestionBankGroup, ExamAutoGenerationRule, CandidateExam, CandidateExamAnswer, OnboardingRecord, RecruitmentConfig, RecruitmentNotification
from .services import ResumeAnalysisService, RecruitmentPipelineService, NotificationService, ExamService, ExamAutoGenerationService

logger = logging.getLogger(__name__)


class JobPositionListView(CustomLoginRequiredMixin, ListView):
    """岗位列表视图"""
    model = JobPosition
    template_name = 'hrbp/position_list.html'
    context_object_name = 'positions'
    paginate_by = 20

    def get_queryset(self):
        try:
            queryset = JobPosition.objects.select_related('department', 'publisher').all()
            
            # 搜索过滤
            search = self.request.GET.get('search', '')
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search)
                )
            
            # 状态过滤
            status = self.request.GET.get('status', '')
            if status:
                queryset = queryset.filter(status=status)
            
            return queryset.order_by('-created_at')
        except Exception as e:
            logger.error(f"获取岗位列表失败: {str(e)}")
            return JobPosition.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = JobPosition.STATUS_CHOICES
        return context


class JobPositionCreateView(CustomLoginRequiredMixin, CreateView):
    """创建岗位"""
    model = JobPosition
    form_class = JobPositionForm
    template_name = 'hrbp/position_form.html'

    def form_valid(self, form):
        form.instance.publisher = self.request.user
        if form.instance.status == 'published':
            form.instance.published_at = timezone.now()
        response = super().form_valid(form)
        return JsonResponse({
            'success': True,
            'message': '岗位创建成功',
            'position_id': self.object.id
        })

    def form_invalid(self, form):
        return JsonResponse({
            'success': False,
            'message': '表单验证失败',
            'errors': form.errors
        }, status=400)


class JobPositionUpdateView(CustomLoginRequiredMixin, UpdateView):
    """更新岗位"""
    model = JobPosition
    form_class = JobPositionForm
    template_name = 'hrbp/position_form.html'

    def form_valid(self, form):
        if form.instance.status == 'published' and not form.instance.published_at:
            form.instance.published_at = timezone.now()
        response = super().form_valid(form)
        return JsonResponse({
            'success': True,
            'message': '岗位更新成功'
        })

    def form_invalid(self, form):
        return JsonResponse({
            'success': False,
            'message': '表单验证失败',
            'errors': form.errors
        }, status=400)


class JobPositionDetailView(CustomLoginRequiredMixin, DetailView):
    """岗位详情"""
    model = JobPosition
    template_name = 'hrbp/position_detail.html'
    context_object_name = 'position'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        position = self.object
        
        # 获取该岗位的简历统计
        context['resume_count'] = position.resume_submissions.count()
        context['pending_count'] = position.resume_submissions.filter(status='pending').count()
        context['completed_count'] = position.resume_submissions.filter(status='completed').count()
        
        return context


class ResumeSubmissionView(CustomLoginRequiredMixin, View):
    """简历提交视图"""
    
    def get(self, request, position_id):
        """显示简历上传页面"""
        position = get_object_or_404(JobPosition, id=position_id)
        return render(request, 'hrbp/resume_upload.html', {
            'position': position
        })
    
    def post(self, request, position_id):
        """处理简历上传"""
        position = get_object_or_404(JobPosition, id=position_id)
        
        try:
            files = request.FILES.getlist('resume_files')
            if not files:
                return JsonResponse({
                    'success': False,
                    'message': '请选择要上传的简历文件'
                }, status=400)
            
            submissions = []
            for file in files:
                # 验证文件类型
                file_ext = os.path.splitext(file.name)[1].lower()
                if file_ext == '.pdf':
                    file_type = 'pdf'
                elif file_ext in ['.doc', '.docx']:
                    file_type = 'word'
                elif file_ext in ['.jpg', '.jpeg', '.png']:
                    file_type = 'image'
                else:
                    continue
                
                # 保存文件
                upload_path = f'hrbp/resumes/{position.id}/{datetime.now().strftime("%Y%m%d")}'
                file_path = default_storage.save(
                    f'{upload_path}/{file.name}',
                    file
                )
                
                # 创建简历提交记录
                submission = ResumeSubmission.objects.create(
                    position=position,
                    file_type=file_type,
                    file_path=file_path,
                    file_name=file.name,
                    file_size=file.size,
                    submitter=request.user,
                    status='pending'
                )
                submissions.append(submission)
            
            # 启动异步分析（这里简化为同步）
            if len(submissions) == 1:
                # 单个简历立即分析
                self._analyze_single_resume(submissions[0])
                return JsonResponse({
                    'success': True,
                    'message': '简历上传成功，正在分析中...',
                    'redirect_url': f'/hrbp/resume/{submissions[0].id}/report/'
                })
            else:
                # 批量简历
                for submission in submissions:
                    self._analyze_single_resume(submission)
                return JsonResponse({
                    'success': True,
                    'message': f'成功上传{len(submissions)}份简历，正在批量分析...',
                    'redirect_url': f'/hrbp/position/{position.id}/resumes/'
                })
                
        except Exception as e:
            logger.error(f"简历上传失败: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'上传失败: {str(e)}'
            }, status=500)
    
    def _analyze_single_resume(self, submission):
        """分析单个简历 — 调用共用服务"""
        try:
            ResumeAnalysisService.complete_analysis(submission)
        except Exception as e:
            logger.error(f"简历分析失败: {str(e)}")
            submission.status = 'failed'
            submission.error_message = str(e)
            submission.save()
class ResumeListView(CustomLoginRequiredMixin, ListView):
    """简历列表视图"""
    model = ResumeSubmission
    template_name = 'hrbp/resume_list.html'
    context_object_name = 'resumes'
    paginate_by = 20

    def get_queryset(self):
        position_id = self.kwargs.get('position_id')
        queryset = ResumeSubmission.objects.select_related(
            'position', 'submitter'
        ).filter(position_id=position_id)
        
        # 状态过滤
        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-submitted_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        position_id = self.kwargs.get('position_id')
        context['position'] = get_object_or_404(JobPosition, id=position_id)
        return context


class ResumeReportView(CustomLoginRequiredMixin, DetailView):
    """简历分析报告视图"""
    model = ResumeSubmission
    template_name = 'hrbp/resume_report.html'
    context_object_name = 'resume'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['report'] = self.object.analysis_report
        except ResumeAnalysisReport.DoesNotExist:
            context['report'] = None
        return context


class SendInterviewInvitationView(CustomLoginRequiredMixin, View):
    """发送面试邀请"""
    
    def post(self, request, report_id):
        """发送面试邀请"""
        try:
            report = get_object_or_404(ResumeAnalysisReport, id=report_id)
            
            data = json.loads(request.body)
            notification_type = data.get('notification_type')
            interview_type = data.get('interview_type')
            interview_time = data.get('interview_time')
            interview_location = data.get('interview_location', '')
            
            if not all([notification_type, interview_type]):
                return JsonResponse({
                    'success': False,
                    'message': '参数不完整'
                }, status=400)
            
            # 构建通知内容
            message_content = self._build_invitation_message(
                report,
                interview_type,
                interview_time,
                interview_location
            )
            
            # 创建邀请记录
            invitation = InterviewInvitation.objects.create(
                resume_report=report,
                notification_type=notification_type,
                interview_type=interview_type,
                interview_time=interview_time,
                interview_location=interview_location,
                message_content=message_content,
                sender=request.user,
                status='pending'
            )
            
            # 发送通知
            success = self._send_notification(invitation, report)
            
            if success:
                invitation.status = 'sent'
                invitation.sent_at = timezone.now()
                invitation.save()
                
                return JsonResponse({
                    'success': True,
                    'message': '面试邀请发送成功'
                })
            else:
                invitation.status = 'failed'
                invitation.error_message = '通知发送失败'
                invitation.save()
                
                return JsonResponse({
                    'success': False,
                    'message': '通知发送失败'
                }, status=500)
                
        except Exception as e:
            logger.error(f"发送面试邀请失败: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'发送失败: {str(e)}'
            }, status=500)
    
    def _build_invitation_message(self, report, interview_type, interview_time, interview_location):
        """构建邀请消息"""
        resume = report.resume
        position = resume.position
        
        message = f"""尊敬的{resume.candidate_name}，

您好！感谢您应聘我公司{position.title}岗位。

经过初步筛选，我们认为您的背景与岗位要求较为匹配，诚邀您参加面试。

面试信息：
- 岗位：{position.title}
- 部门：{position.department.title}
- 面试方式：{'线上面试' if interview_type == 'online' else '到公司面试'}
"""
        
        if interview_time:
            message += f"- 面试时间：{interview_time}\n"
        
        if interview_location:
            if interview_type == 'online':
                message += f"- 面试链接：{interview_location}\n"
            else:
                message += f"- 面试地点：{interview_location}\n"
        
        message += "\n请您提前做好准备，准时参加面试。如有任何问题，请及时与我们联系。\n\n祝好！"
        
        return message
    
    def _send_notification(self, invitation, report):
        """发送通知"""
        try:
            resume = report.resume
            
            # TODO: 集成实际的通知服务（邮件、短信、SIP）
            # 当前返回模拟成功，实际项目中需要对接相应服务
            
            if invitation.notification_type == 'email':
                # 发送邮件 - 需要配置邮件服务
                if resume.candidate_email:
                    logger.info(f"模拟发送邮件到: {resume.candidate_email}")
                    return True
            elif invitation.notification_type == 'sms':
                # 发送短信 - 需要配置短信服务
                if resume.candidate_phone:
                    logger.info(f"模拟发送短信到: {resume.candidate_phone}")
                    return True
            elif invitation.notification_type == 'sip':
                # SIP电话通知 - 需要配置SIP服务
                if resume.candidate_phone:
                    logger.info(f"模拟SIP呼叫: {resume.candidate_phone}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"通知发送失败: {str(e)}")
            return False


class BatchResumeReportView(CustomLoginRequiredMixin, ListView):
    """批量简历报告列表"""
    model = ResumeAnalysisReport
    template_name = 'hrbp/batch_report_list.html'
    context_object_name = 'reports'
    paginate_by = 20

    def get_queryset(self):
        position_id = self.kwargs.get('position_id')
        queryset = ResumeAnalysisReport.objects.select_related(
            'resume__position', 'resume__submitter'
        ).filter(resume__position_id=position_id)
        
        # 按匹配分数排序
        return queryset.order_by('-match_score')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        position_id = self.kwargs.get('position_id')
        context['position'] = get_object_or_404(JobPosition, id=position_id)
        return context


# ========== 招聘仪表盘 ==========

class RecruitmentDashboardView(CustomLoginRequiredMixin, View):
    """招聘全流程仪表盘"""

    def get(self, request):
        from .models import CandidatePipeline, RecruitmentConfig

        # 统计各阶段数量
        stage_stats = {}
        for stage_code, stage_name in CandidatePipeline.STAGE_CHOICES:
            count = CandidatePipeline.objects.filter(current_stage=stage_code, is_active=True).count()
            stage_stats[stage_code] = {
                'name': stage_name,
                'count': count,
            }

        # 总数统计
        total_candidates = CandidatePipeline.objects.filter(is_active=True).count()
        total_completed = CandidatePipeline.objects.filter(current_stage='completed').count()
        total_rejected = CandidatePipeline.objects.filter(current_stage='rejected').count()
        total_positions = JobPosition.objects.filter(status='published').count()

        # 待处理审批
        pending_review = CandidatePipeline.objects.filter(
            current_stage='hr_review', is_active=True
        ).count()

        # 今日数据
        today = timezone.now().date()
        today_new = CandidatePipeline.objects.filter(
            created_at__date=today
        ).count()

        # 流程配置
        configs = {c.stage: c.exec_mode for c in RecruitmentConfig.objects.filter(is_enabled=True)}

        return render(request, 'hrbp/dashboard.html', {
            'stage_stats': stage_stats,
            'total_candidates': total_candidates,
            'total_completed': total_completed,
            'total_rejected': total_rejected,
            'total_positions': total_positions,
            'pending_review': pending_review,
            'today_new': today_new,
            'configs': configs,
            'stage_choices': dict(CandidatePipeline.STAGE_CHOICES),
        })


# ========== 候选人筛选审批 ==========

class CandidateScreeningView(CustomLoginRequiredMixin, ListView):
    """候选人筛选列表 — HR审批页面"""
    model = CandidatePipeline
    template_name = 'hrbp/screening_list.html'
    context_object_name = 'pipelines'
    paginate_by = 20

    def get_queryset(self):
        from .models import CandidatePipeline
        queryset = CandidatePipeline.objects.select_related(
            'resume_submission', 'resume_submission__position',
            'resume_submission__position__department', 'hr_reviewer'
        ).prefetch_related('resume_submission__analysis_report')

        stage = self.request.GET.get('stage', '')
        if stage:
            queryset = queryset.filter(current_stage=stage)
        else:
            # 默认显示待审批阶段
            queryset = queryset.filter(current_stage__in=['hr_review', 'exam_review'])

        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(resume_submission__candidate_name__icontains=search) |
                Q(resume_submission__position__title__icontains=search)
            )

        position_id = self.request.GET.get('position_id', '')
        if position_id:
            queryset = queryset.filter(position_id=position_id)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stage_choices'] = CandidatePipeline.STAGE_CHOICES
        context['positions'] = JobPosition.objects.filter(status='published')
        return context


class ApproveCandidateView(CustomLoginRequiredMixin, View):
    """HR审批通过候选人"""

    def post(self, request, pipeline_id):
        pipeline = get_object_or_404(CandidatePipeline, id=pipeline_id)
        comment = request.POST.get('comment', '')
        auto_notify = request.POST.get('auto_notify', 'true') == 'true'

        try:
            RecruitmentPipelineService.approve_candidate(pipeline, request.user, comment)

            if auto_notify and pipeline.current_stage == 'contact_interview':
                NotificationService.send_interview_invitation(pipeline, request.user)

            return JsonResponse({
                'success': True,
                'message': '审批通过，已推进到下一阶段',
                'current_stage': pipeline.get_current_stage_display(),
            })
        except Exception as e:
            logger.error(f'审批候选人失败: {str(e)}')
            return JsonResponse({
                'success': False,
                'message': f'操作失败: {str(e)}',
            }, status=500)


class RejectCandidateView(CustomLoginRequiredMixin, View):
    """HR淘汰候选人"""

    def post(self, request, pipeline_id):
        pipeline = get_object_or_404(CandidatePipeline, id=pipeline_id)
        comment = request.POST.get('comment', '')

        try:
            RecruitmentPipelineService.reject_candidate(pipeline, request.user, comment)
            return JsonResponse({
                'success': True,
                'message': '已淘汰该候选人',
            })
        except Exception as e:
            logger.error(f'淘汰候选人失败: {str(e)}')
            return JsonResponse({
                'success': False,
                'message': f'操作失败: {str(e)}',
            }, status=500)


class BatchApproveView(CustomLoginRequiredMixin, View):
    """批量审批"""

    def post(self, request):
        pipeline_ids = request.POST.getlist('pipeline_ids', [])
        if not pipeline_ids:
            return JsonResponse({'success': False, 'message': '请选择候选人'}, status=400)

        comment = request.POST.get('comment', '')
        success_count = 0
        fail_count = 0

        for pid in pipeline_ids:
            try:
                pipeline = CandidatePipeline.objects.get(id=pid)
                RecruitmentPipelineService.approve_candidate(pipeline, request.user, comment)
                success_count += 1
            except Exception as e:
                logger.error(f'批量审批失败 pipeline_id={pid}: {str(e)}')
                fail_count += 1

        return JsonResponse({
            'success': True,
            'message': f'批量审批完成：通过 {success_count} 人' + (f'，失败 {fail_count} 人' if fail_count else ''),
        })


# ========== 流程详情页 ==========

class PipelineDetailView(CustomLoginRequiredMixin, DetailView):
    """候选人流程详情"""
    model = CandidatePipeline
    template_name = 'hrbp/pipeline_detail.html'
    context_object_name = 'pipeline'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pipeline = self.object

        context['resume'] = pipeline.resume_submission
        try:
            context['report'] = pipeline.resume_submission.analysis_report
        except ResumeAnalysisReport.DoesNotExist:
            context['report'] = None

        context['stage_logs'] = pipeline.stage_logs.select_related('operator').order_by('-created_at')
        context['notifications'] = pipeline.notifications.order_by('-created_at')
        context['exams'] = pipeline.exams.select_related('exam', 'reviewer').order_by('-created_at')

        try:
            context['onboarding'] = pipeline.onboarding
        except:
            context['onboarding'] = None

        context['stage_choices'] = dict(CandidatePipeline.STAGE_CHOICES)

        return context


class ManualAdvanceStageView(CustomLoginRequiredMixin, View):
    """手动推进阶段"""

    def post(self, request, pipeline_id):
        pipeline = get_object_or_404(CandidatePipeline, id=pipeline_id)
        target_stage = request.POST.get('target_stage', '')

        try:
            if target_stage and target_stage in dict(CandidatePipeline.STAGE_CHOICES):
                RecruitmentPipelineService._log(
                    pipeline, pipeline.current_stage, 'exit',
                    request.user, f'手动跳转到: {dict(CandidatePipeline.STAGE_CHOICES).get(target_stage)}'
                )
                pipeline.current_stage = target_stage
                pipeline.stage_result = 'pending'
                pipeline.save(update_fields=['current_stage', 'stage_result', 'updated_at'])
                RecruitmentPipelineService._log(
                    pipeline, target_stage, 'enter',
                    request.user, f'手动进入阶段: {dict(CandidatePipeline.STAGE_CHOICES).get(target_stage)}'
                )
            else:
                RecruitmentPipelineService.advance_stage(pipeline, request.user)

            return JsonResponse({
                'success': True,
                'message': f'已推进到: {pipeline.get_current_stage_display()}',
                'current_stage': pipeline.get_current_stage_display(),
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'操作失败: {str(e)}',
            }, status=500)


# ========== 面试管理 ==========

class InterviewManagementView(CustomLoginRequiredMixin, ListView):
    """面试管理列表"""
    model = CandidatePipeline
    template_name = 'hrbp/interview_list.html'
    context_object_name = 'pipelines'
    paginate_by = 20

    def get_queryset(self):
        return CandidatePipeline.objects.filter(
            current_stage__in=['contact_interview', 'interview', 'interview_result'],
            is_active=True,
        ).select_related(
            'resume_submission', 'resume_submission__position',
        ).order_by('-updated_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invitations'] = InterviewInvitation.objects.filter(
            resume_report__resume__pipeline__is_active=True
        ).select_related('resume_report__resume__pipeline').order_by('-created_at')
        return context


class SendInvitationView(CustomLoginRequiredMixin, View):
    """发送面试/考核/Offer/入职通知"""

    def post(self, request, pipeline_id):
        pipeline = get_object_or_404(CandidatePipeline, id=pipeline_id)
        notify_type = request.POST.get('notify_type', 'all')  # all, sms, email, phone
        scene = request.POST.get('scene', 'interview_invite')

        try:
            success = False
            if scene == 'interview_invite':
                success = NotificationService.send_interview_invitation(pipeline, request.user)
            elif scene == 'exam_invite':
                exam_link = request.POST.get('exam_link', '')
                success = NotificationService.send_exam_invitation(pipeline, exam_link, request.user)
            elif scene == 'offer_notice':
                success = NotificationService.send_offer_notification(pipeline, request.user)
            elif scene == 'onboarding_notice':
                success = NotificationService.send_onboarding_notification(pipeline, request.user)

            if success:
                RecruitmentPipelineService._log(
                    pipeline, pipeline.current_stage, 'notification_sent',
                    request.user, f'已发送{scene}通知'
                )

            return JsonResponse({
                'success': success,
                'message': '通知发送成功' if success else '通知发送失败，请检查候选人联系方式',
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'发送失败: {str(e)}',
            }, status=500)


# ========== 在线考核管理 ==========

class ExamListView(CustomLoginRequiredMixin, ListView):
    """考核列表"""
    model = OnlineExam
    template_name = 'hrbp/exam_list.html'
    context_object_name = 'exams'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '')
        if search:
            qs = qs.filter(title__icontains=search)
        return qs.order_by('-created_at')


class ExamCreateView(CustomLoginRequiredMixin, View):
    """创建考核"""

    def get(self, request):
        form = OnlineExamForm()
        return render(request, 'hrbp/exam_create_drawer.html', {'form': form, 'is_create': True})

    def post(self, request):
        form = OnlineExamForm(request.POST)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.creator = request.user
            exam.save()
            return JsonResponse({'success': True, 'message': '考核创建成功', 'exam_id': exam.id})
        return JsonResponse({'success': False, 'message': '表单验证失败', 'errors': form.errors}, status=400)


class ExamEditView(CustomLoginRequiredMixin, View):
    """编辑考核"""

    def get(self, request, exam_id):
        exam = get_object_or_404(OnlineExam, id=exam_id)
        form = OnlineExamForm(instance=exam)
        return render(request, 'hrbp/exam_form.html', {'form': form, 'exam': exam, 'is_create': False})

    def post(self, request, exam_id):
        exam = get_object_or_404(OnlineExam, id=exam_id)
        form = OnlineExamForm(request.POST, instance=exam)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': '考核更新成功'})
        return JsonResponse({'success': False, 'message': '表单验证失败', 'errors': form.errors}, status=400)


class ExamDetailView(CustomLoginRequiredMixin, DetailView):
    """考核详情 — 含题目管理"""
    model = OnlineExam
    template_name = 'hrbp/exam_detail.html'
    context_object_name = 'exam'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['questions'] = self.object.questions.order_by('sort_order', 'id')
        context['question_types'] = dict(ExamQuestion.QUESTION_TYPE_CHOICES)
        return context


class ExamCandidateResultsView(CustomLoginRequiredMixin, ListView):
    """考核候选人结果列表"""
    model = CandidateExam
    template_name = 'hrbp/exam_results.html'
    context_object_name = 'results'
    paginate_by = 20

    def get_queryset(self):
        exam_id = self.kwargs.get('exam_id')
        qs = CandidateExam.objects.filter(exam_id=exam_id).select_related(
            'pipeline', 'pipeline__resume_submission', 'reviewer'
        ).order_by('-created_at')

        status = self.request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exam'] = get_object_or_404(OnlineExam, id=self.kwargs.get('exam_id'))
        context['status_choices'] = CandidateExam.STATUS_CHOICES
        return context


class ReviewExamResultView(CustomLoginRequiredMixin, View):
    """HR审批考核结果"""

    def get(self, request, candidate_exam_id):
        candidate_exam = get_object_or_404(
            CandidateExam.objects.select_related('pipeline', 'exam', 'pipeline__resume_submission'),
            id=candidate_exam_id
        )
        answers = candidate_exam.answers.select_related('question').order_by('question__sort_order')
        return render(request, 'hrbp/exam_review.html', {
            'candidate_exam': candidate_exam,
            'answers': answers,
        })

    def post(self, request, candidate_exam_id):
        candidate_exam = get_object_or_404(CandidateExam, id=candidate_exam_id)
        action = request.POST.get('action', '')  # pass, fail, adjust

        try:
            hr_score = request.POST.get('hr_score', '')
            hr_feedback = request.POST.get('hr_feedback', '')

            if hr_score:
                candidate_exam.hr_score = hr_score
            candidate_exam.hr_feedback = hr_feedback
            candidate_exam.reviewer = request.user
            candidate_exam.reviewed_at = timezone.now()

            if action == 'pass':
                candidate_exam.status = 'passed'
                candidate_exam.save()
                # 推进候选人流程
                pipeline = candidate_exam.pipeline
                RecruitmentPipelineService._log(
                    pipeline, 'exam_review', 'manual_approve',
                    request.user, f'考核通过。{hr_feedback}' if hr_feedback else '考核通过'
                )
                RecruitmentPipelineService.advance_stage(pipeline, request.user)
                msg = '考核审批通过，已推进到下一阶段'
            elif action == 'fail':
                candidate_exam.status = 'failed'
                candidate_exam.save()
                RecruitmentPipelineService._log(
                    candidate_exam.pipeline, 'exam_review', 'manual_reject',
                    request.user, f'考核不通过。{hr_feedback}' if hr_feedback else '考核不通过'
                )
                msg = '考核标记为不通过'
            else:
                candidate_exam.status = 'hr_reviewed'
                candidate_exam.save()
                msg = '考核结果已保存'

            return JsonResponse({'success': True, 'message': msg})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'操作失败: {str(e)}'}, status=500)


# ========== 入职管理 ==========

class OnboardingListView(CustomLoginRequiredMixin, ListView):
    """入职管理列表"""
    model = OnboardingRecord
    template_name = 'hrbp/onboarding_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        qs = OnboardingRecord.objects.select_related(
            'pipeline', 'pipeline__resume_submission',
            'pipeline__resume_submission__position', 'handler',
        ).order_by('-created_at')

        status = self.request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = OnboardingRecord.STATUS_CHOICES
        return context


class OnboardingManageView(CustomLoginRequiredMixin, View):
    """入职办理"""

    def get(self, request, pipeline_id):
        pipeline = get_object_or_404(
            CandidatePipeline.objects.select_related('resume_submission'),
            id=pipeline_id
        )
        try:
            onboarding = pipeline.onboarding
        except:
            onboarding = None

        form = OnboardingForm(instance=onboarding)
        return render(request, 'hrbp/onboarding_form.html', {
            'pipeline': pipeline,
            'onboarding': onboarding,
            'form': form,
        })

    def post(self, request, pipeline_id):
        pipeline = get_object_or_404(CandidatePipeline, id=pipeline_id)

        try:
            onboarding, created = OnboardingRecord.objects.get_or_create(
                pipeline=pipeline,
                defaults={'handler': request.user},
            )

            form = OnboardingForm(request.POST, instance=onboarding)
            if form.is_valid():
                onboarding = form.save(commit=False)
                onboarding.handler = request.user
                onboarding.save()

                if request.POST.get('send_notice') == 'on':
                    NotificationService.send_onboarding_notification(pipeline, request.user)

                # 更新流程状态
                if request.POST.get('mark_completed') == 'on':
                    onboarding.status = 'completed'
                    onboarding.actual_date = timezone.now().date()
                    onboarding.save()
                    pipeline.current_stage = 'completed'
                    pipeline.is_active = False
                    pipeline.save()
                    RecruitmentPipelineService._log(
                        pipeline, 'onboarding', 'exit',
                        request.user, '入职办理完成'
                    )

                return JsonResponse({'success': True, 'message': '入职信息保存成功'})
            return JsonResponse({'success': False, 'message': '表单验证失败', 'errors': form.errors}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'操作失败: {str(e)}'}, status=500)


# ========== 流程配置 ==========

class PipelineConfigView(CustomLoginRequiredMixin, View):
    """招聘流程阶段配置"""

    def get(self, request):
        from .models import RecruitmentConfig

        # 确保所有阶段都有配置记录
        for stage_code, stage_name in CandidatePipeline.STAGE_CHOICES:
            RecruitmentConfig.objects.get_or_create(
                stage=stage_code,
                defaults={
                    'stage_name': stage_name,
                    'exec_mode': 'manual',
                    'sort_order': RecruitmentPipelineService.STAGE_ORDER.index(stage_code)
                        if stage_code in RecruitmentPipelineService.STAGE_ORDER else 99,
                }
            )

        configs = RecruitmentConfig.objects.all().order_by('sort_order')
        return render(request, 'hrbp/config.html', {
            'configs': configs,
            'exec_modes': dict(RecruitmentConfig.EXEC_MODE_CHOICES),
            'stage_choices': dict(CandidatePipeline.STAGE_CHOICES),
        })


class UpdatePipelineConfigView(CustomLoginRequiredMixin, View):
    """更新阶段配置"""
    def post(self, request):
        stage = request.POST.get('stage', '')
        exec_mode = request.POST.get('exec_mode', 'manual')
        is_enabled = request.POST.get('is_enabled', 'true') == 'true'

        try:
            config = RecruitmentConfig.objects.get(stage=stage)
            config.exec_mode = exec_mode
            config.is_enabled = is_enabled
            config.save()
            return JsonResponse({'success': True, 'message': '配置更新成功'})
        except RecruitmentConfig.DoesNotExist:
            return JsonResponse({'success': False, 'message': '配置不存在'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ========== API: 获取阶段配置 ==========

class GetStageConfigView(CustomLoginRequiredMixin, View):
    """获取阶段执行模式（供前端AJAX）"""

    def get(self, request):
        from .models import RecruitmentConfig
        configs = {c.stage: {
            'exec_mode': c.exec_mode,
            'exec_mode_display': c.get_exec_mode_display(),
            'is_enabled': c.is_enabled,
        } for c in RecruitmentConfig.objects.filter(is_enabled=True)}
        return JsonResponse({'success': True, 'configs': configs})


# ========== 题目管理 CRUD ==========

class CreateQuestionView(CustomLoginRequiredMixin, View):
    """添加题目"""

    def post(self, request):
        try:
            exam_id = request.POST.get('exam_id')
            exam = get_object_or_404(OnlineExam, id=exam_id)

            question = ExamQuestion.objects.create(
                exam=exam,
                question_type=request.POST.get('question_type', 'single'),
                content=request.POST.get('content', ''),
                correct_answer=request.POST.get('correct_answer', ''),
                score=request.POST.get('score', 5),
                sort_order=request.POST.get('sort_order', 0),
            )
            return JsonResponse({'success': True, 'message': '题目添加成功', 'id': question.id})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class UpdateQuestionView(CustomLoginRequiredMixin, View):
    """更新题目"""

    def post(self, request, question_id):
        try:
            question = get_object_or_404(ExamQuestion, id=question_id)
            question.question_type = request.POST.get('question_type', question.question_type)
            question.content = request.POST.get('content', question.content)
            question.correct_answer = request.POST.get('correct_answer', question.correct_answer)
            question.score = request.POST.get('score', question.score)
            question.sort_order = request.POST.get('sort_order', question.sort_order)
            question.save()
            return JsonResponse({'success': True, 'message': '题目更新成功'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class DeleteQuestionView(CustomLoginRequiredMixin, View):
    """删除题目"""
    def post(self, request, question_id):
        try:
            question = get_object_or_404(ExamQuestion, id=question_id)
            exam_id = question.exam_id
            question.delete()
            return JsonResponse({'success': True, 'message': '题目已删除'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============================================================
# 题库分组管理
# ============================================================

class QuestionBankGroupListView(CustomLoginRequiredMixin, ListView):
    """题库分组列表"""
    model = QuestionBankGroup
    template_name = 'hrbp/question_bank_list.html'
    context_object_name = 'groups'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('position', 'creator')
        search = self.request.GET.get('search', '')
        if search:
            qs = qs.filter(name__icontains=search)
        difficulty = self.request.GET.get('difficulty', '')
        if difficulty:
            qs = qs.filter(difficulty=difficulty)
        position_id = self.request.GET.get('position_id', '')
        if position_id:
            qs = qs.filter(position_id=position_id)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['positions'] = JobPosition.objects.filter(status='published')
        return context


class QuestionBankGroupCreateView(CustomLoginRequiredMixin, View):
    """创建题库分组"""

    def get(self, request):
        form = QuestionBankGroupForm()
        return render(request, 'hrbp/question_bank_form.html', {'form': form, 'is_create': True})

    def post(self, request):
        form = QuestionBankGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            # Parse function_tags and tags from comma-separated strings
            ftags = request.POST.get('function_tags', '')
            group.function_tags = [t.strip() for t in ftags.split(',') if t.strip()]
            gtags = request.POST.get('tags', '')
            group.tags = [t.strip() for t in gtags.split(',') if t.strip()]
            group.creator = request.user
            group.save()
            form.save_m2m()
            return JsonResponse({'success': True, 'message': '题库分组创建成功', 'group_id': group.id})
        return JsonResponse({'success': False, 'message': '表单验证失败', 'errors': form.errors}, status=400)


class QuestionBankGroupEditView(CustomLoginRequiredMixin, View):
    """编辑题库分组"""

    def get(self, request, group_id):
        group = get_object_or_404(QuestionBankGroup, id=group_id)
        initial = {
            'function_tags': ', '.join(group.function_tags) if group.function_tags else '',
            'tags': ', '.join(group.tags) if group.tags else '',
        }
        form = QuestionBankGroupForm(instance=group, initial=initial)
        return render(request, 'hrbp/question_bank_form.html', {'form': form, 'group': group, 'is_create': False})

    def post(self, request, group_id):
        group = get_object_or_404(QuestionBankGroup, id=group_id)
        form = QuestionBankGroupForm(request.POST, instance=group)
        if form.is_valid():
            group = form.save(commit=False)
            ftags = request.POST.get('function_tags', '')
            group.function_tags = [t.strip() for t in ftags.split(',') if t.strip()]
            gtags = request.POST.get('tags', '')
            group.tags = [t.strip() for t in gtags.split(',') if t.strip()]
            group.save()
            return JsonResponse({'success': True, 'message': '题库分组更新成功'})
        return JsonResponse({'success': False, 'message': '表单验证失败', 'errors': form.errors}, status=400)


class QuestionBankGroupDeleteView(CustomLoginRequiredMixin, View):
    """删除题库分组"""

    def post(self, request, group_id):
        try:
            group = get_object_or_404(QuestionBankGroup, id=group_id)
            group.delete()
            return JsonResponse({'success': True, 'message': '题库分组已删除'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class QuestionBankGroupDetailView(CustomLoginRequiredMixin, DetailView):
    """题库分组详情 — 含题目列表"""
    model = QuestionBankGroup
    template_name = 'hrbp/question_bank_detail.html'
    context_object_name = 'group'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['questions'] = self.object.questions.order_by('sort_order', 'id')
        context['question_types'] = dict(ExamQuestion.QUESTION_TYPE_CHOICES)
        return context


# ============================================================
# 自动组卷规则管理
# ============================================================

class AutoGenerationRuleListView(CustomLoginRequiredMixin, ListView):
    """自动组卷规则列表"""
    model = ExamAutoGenerationRule
    template_name = 'hrbp/auto_rule_list.html'
    context_object_name = 'rules'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().select_related('position_filter', 'creator').order_by('-created_at')


class AutoGenerationRuleCreateView(CustomLoginRequiredMixin, View):
    """创建组卷规则"""

    def get(self, request):
        form = ExamAutoGenerationRuleForm()
        groups = QuestionBankGroup.objects.filter(is_active=True)
        return render(request, 'hrbp/auto_rule_form.html', {
            'form': form, 'is_create': True,
            'bank_groups': groups,
        })

    def post(self, request):
        form = ExamAutoGenerationRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            # Parse JSON fields
            rule.difficulty_distribution = json.loads(request.POST.get('difficulty_distribution', '{}'))
            rule.question_type_distribution = json.loads(request.POST.get('question_type_distribution', '{}'))
            rule.tag_requirements = json.loads(request.POST.get('tag_requirements', '{}'))
            rule.creator = request.user
            rule.save()
            form.save_m2m()
            return JsonResponse({'success': True, 'message': '组卷规则创建成功', 'rule_id': rule.id})
        return JsonResponse({'success': False, 'message': '表单验证失败', 'errors': form.errors}, status=400)


class AutoGenerationRuleEditView(CustomLoginRequiredMixin, View):
    """编辑组卷规则"""

    def get(self, request, rule_id):
        rule = get_object_or_404(ExamAutoGenerationRule, id=rule_id)
        form = ExamAutoGenerationRuleForm(instance=rule)
        groups = QuestionBankGroup.objects.filter(is_active=True)
        return render(request, 'hrbp/auto_rule_form.html', {
            'form': form, 'rule': rule, 'is_create': False,
            'bank_groups': groups,
        })

    def post(self, request, rule_id):
        rule = get_object_or_404(ExamAutoGenerationRule, id=rule_id)
        form = ExamAutoGenerationRuleForm(request.POST, instance=rule)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.difficulty_distribution = json.loads(request.POST.get('difficulty_distribution', '{}'))
            rule.question_type_distribution = json.loads(request.POST.get('question_type_distribution', '{}'))
            rule.tag_requirements = json.loads(request.POST.get('tag_requirements', '{}'))
            rule.save()
            form.save_m2m()
            return JsonResponse({'success': True, 'message': '组卷规则更新成功'})
        return JsonResponse({'success': False, 'message': '表单验证失败', 'errors': form.errors}, status=400)


# ============================================================
# 自动组卷操作
# ============================================================

class AutoGenerateExamPreviewView(CustomLoginRequiredMixin, View):
    """预览自动组卷结果"""

    def get(self, request, rule_id):
        rule = get_object_or_404(ExamAutoGenerationRule, id=rule_id)
        try:
            preview = ExamAutoGenerationService.preview_generation(rule)
            return JsonResponse({'success': True, 'preview': preview})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class AutoGenerateExamView(CustomLoginRequiredMixin, View):
    """执行自动组卷"""

    def post(self, request, rule_id):
        rule = get_object_or_404(ExamAutoGenerationRule, id=rule_id)
        try:
            exam_title = request.POST.get('title', '')
            exam, question_count = ExamAutoGenerationService.generate_exam_from_rule(
                rule, exam_title=exam_title, creator=request.user
            )
            return JsonResponse({
                'success': True,
                'message': f'自动组卷成功，共{question_count}道题目',
                'exam_id': exam.id,
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ============================================================
# 题目管理增强 — 支持题库分组
# ============================================================

class QuestionBankAddQuestionView(CustomLoginRequiredMixin, View):
    """向题库分组添加题目"""

    def get(self, request, group_id):
        group = get_object_or_404(QuestionBankGroup, id=group_id)
        form = ExamQuestionForm(initial={'bank_group': group})
        return render(request, 'hrbp/question_form.html', {'form': form, 'group': group, 'is_create': True})

    def post(self, request, group_id):
        group = get_object_or_404(QuestionBankGroup, id=group_id)
        form = ExamQuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            tags_str = request.POST.get('tags', '')
            question.tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            # 题库分组题目可以不关联具体考核
            question.bank_group = group
            question.save()
            return JsonResponse({'success': True, 'message': '题目添加成功', 'question_id': question.id})
        return JsonResponse({'success': False, 'message': '表单验证失败', 'errors': form.errors}, status=400)
