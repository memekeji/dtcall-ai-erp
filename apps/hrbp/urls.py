"""
AI-HRBP URL配置
"""
from django.urls import path
from . import views

app_name = 'hrbp'

urlpatterns = [
    # 仪表盘
    path('dashboard/', views.RecruitmentDashboardView.as_view(), name='dashboard'),

    # 岗位管理
    path('positions/', views.JobPositionListView.as_view(), name='position_list'),
    path('position/create/', views.JobPositionCreateView.as_view(), name='position_create'),
    path('position/<int:pk>/', views.JobPositionDetailView.as_view(), name='position_detail'),
    path('position/<int:pk>/update/', views.JobPositionUpdateView.as_view(), name='position_update'),

    # 简历管理
    path('position/<int:position_id>/upload/', views.ResumeSubmissionView.as_view(), name='resume_upload'),
    path('position/<int:position_id>/resumes/', views.ResumeListView.as_view(), name='resume_list'),
    path('resume/<int:pk>/report/', views.ResumeReportView.as_view(), name='resume_report'),

    # 批量报告
    path('position/<int:position_id>/batch-reports/', views.BatchResumeReportView.as_view(), name='batch_report_list'),

    # 面试邀请（旧接口）
    path('report/<int:report_id>/invite/', views.SendInterviewInvitationView.as_view(), name='send_invitation'),

    # ========== 新流程接口 ==========

    # 候选人筛选审批
    path('screening/', views.CandidateScreeningView.as_view(), name='screening_list'),
    path('screening/<int:pipeline_id>/approve/', views.ApproveCandidateView.as_view(), name='approve_candidate'),
    path('screening/<int:pipeline_id>/reject/', views.RejectCandidateView.as_view(), name='reject_candidate'),
    path('screening/batch-approve/', views.BatchApproveView.as_view(), name='batch_approve'),

    # 候选人流程详情
    path('pipeline/<int:pk>/', views.PipelineDetailView.as_view(), name='pipeline_detail'),
    path('pipeline/<int:pipeline_id>/advance/', views.ManualAdvanceStageView.as_view(), name='advance_stage'),

    # 通知发送
    path('pipeline/<int:pipeline_id>/send-notification/', views.SendInvitationView.as_view(), name='send_notification'),

    # 面试管理
    path('interviews/', views.InterviewManagementView.as_view(), name='interview_list'),

    # 在线考核管理
    path('exams/', views.ExamListView.as_view(), name='exam_list'),
    path('exam/create/', views.ExamCreateView.as_view(), name='exam_create'),
    path('exam/<int:exam_id>/edit/', views.ExamEditView.as_view(), name='exam_edit'),
    path('exam/<int:pk>/', views.ExamDetailView.as_view(), name='exam_detail'),

    # 考核结果
    path('exam/<int:exam_id>/results/', views.ExamCandidateResultsView.as_view(), name='exam_results'),
    path('exam-result/<int:candidate_exam_id>/review/', views.ReviewExamResultView.as_view(), name='exam_review'),

    # 入职管理
    path('onboarding/', views.OnboardingListView.as_view(), name='onboarding_list'),
    path('onboarding/<int:pipeline_id>/manage/', views.OnboardingManageView.as_view(), name='onboarding_manage'),

    # 题目管理 CRUD
    path('exam/question/create/', views.CreateQuestionView.as_view(), name='question_create'),
    path('exam/question/<int:question_id>/update/', views.UpdateQuestionView.as_view(), name='question_update'),
    path('exam/question/<int:question_id>/delete/', views.DeleteQuestionView.as_view(), name='question_delete'),

    # 流程配置
    path('config/', views.PipelineConfigView.as_view(), name='config'),
    path('config/update/', views.UpdatePipelineConfigView.as_view(), name='config_update'),
    path('api/config/', views.GetStageConfigView.as_view(), name='api_config'),

    # 考核创建右侧抽屉
    path('exam/create-drawer/', views.ExamCreateView.as_view(), name='exam_create_drawer'),
    # 题库分组管理
    path('question-banks/', views.QuestionBankGroupListView.as_view(), name='question_bank_list'),
    path('question-bank/create/', views.QuestionBankGroupCreateView.as_view(), name='question_bank_create'),
    path('question-bank/<int:group_id>/edit/', views.QuestionBankGroupEditView.as_view(), name='question_bank_edit'),
    path('question-bank/<int:group_id>/delete/', views.QuestionBankGroupDeleteView.as_view(), name='question_bank_delete'),
    path('question-bank/<int:pk>/', views.QuestionBankGroupDetailView.as_view(), name='question_bank_detail'),
    path('question-bank/<int:group_id>/add-question/', views.QuestionBankAddQuestionView.as_view(), name='question_bank_add_question'),
    # 自动组卷规则
    path('auto-rules/', views.AutoGenerationRuleListView.as_view(), name='auto_rule_list'),
    path('auto-rule/create/', views.AutoGenerationRuleCreateView.as_view(), name='auto_rule_create'),
    path('auto-rule/<int:rule_id>/edit/', views.AutoGenerationRuleEditView.as_view(), name='auto_rule_edit'),
    # 自动组卷操作
    path('auto-generate/<int:rule_id>/preview/', views.AutoGenerateExamPreviewView.as_view(), name='auto_generate_preview'),
    path('auto-generate/<int:rule_id>/execute/', views.AutoGenerateExamView.as_view(), name='auto_generate_execute'),
]