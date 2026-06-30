"""
AI-HRBP数据模型
"""
from django.db import models
from django.contrib.auth import get_user_model
from apps.department.models import Department

User = get_user_model()


class JobPosition(models.Model):
    """岗位管理"""
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('published', '已发布'),
        ('closed', '已关闭'),
    )

    WORK_TYPE_CHOICES = (
        ('full_time', '全职'),
        ('part_time', '兼职'),
        ('internship', '实习'),
        ('contract', '合同工'),
    )

    title = models.CharField(max_length=200, verbose_name='岗位名称')
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        verbose_name='所属部门'
    )
    work_type = models.CharField(
        max_length=20,
        choices=WORK_TYPE_CHOICES,
        default='full_time',
        verbose_name='工作类型'
    )
    location = models.CharField(max_length=200, verbose_name='工作地点')
    salary_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='薪资范围（最低）'
    )
    salary_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='薪资范围（最高）'
    )
    headcount = models.IntegerField(default=1, verbose_name='招聘人数')
    description = models.TextField(verbose_name='岗位描述')
    requirements = models.TextField(verbose_name='任职要求')
    responsibilities = models.TextField(verbose_name='岗位职责')
    skills_required = models.TextField(blank=True, verbose_name='技能要求')
    education_required = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='学历要求'
    )
    experience_years = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='工作年限要求'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='状态'
    )
    publisher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='published_positions',
        verbose_name='发布人'
    )
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    deadline = models.DateField(null=True, blank=True, verbose_name='截止日期')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '岗位信息'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_job_position'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.department.title}"


class ResumeSubmission(models.Model):
    """简历提交记录"""
    STATUS_CHOICES = (
        ('pending', '待处理'),
        ('analyzing', '分析中'),
        ('completed', '已完成'),
        ('failed', '分析失败'),
    )

    FILE_TYPE_CHOICES = (
        ('pdf', 'PDF'),
        ('word', 'Word文档'),
        ('image', '图片'),
    )

    position = models.ForeignKey(
        JobPosition,
        on_delete=models.CASCADE,
        related_name='resume_submissions',
        verbose_name='应聘岗位'
    )
    candidate_name = models.CharField(max_length=100, blank=True, verbose_name='候选人姓名')
    candidate_phone = models.CharField(max_length=20, blank=True, verbose_name='联系电话')
    candidate_email = models.CharField(max_length=100, blank=True, verbose_name='电子邮箱')
    file_type = models.CharField(
        max_length=20,
        choices=FILE_TYPE_CHOICES,
        verbose_name='文件类型'
    )
    file_path = models.CharField(max_length=500, verbose_name='文件路径')
    file_name = models.CharField(max_length=255, verbose_name='文件名称')
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小(字节)')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='处理状态'
    )
    submitter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='submitted_resumes',
        verbose_name='提交人'
    )
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')
    analyzed_at = models.DateTimeField(null=True, blank=True, verbose_name='分析完成时间')
    error_message = models.TextField(blank=True, verbose_name='错误信息')

    class Meta:
        verbose_name = '简历提交'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_resume_submission'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.candidate_name or '未知'} - {self.position.title}"


class ResumeAnalysisReport(models.Model):
    """简历分析报告"""
    MATCH_LEVEL_CHOICES = (
        ('excellent', '优秀匹配'),
        ('good', '良好匹配'),
        ('fair', '一般匹配'),
        ('poor', '不匹配'),
    )

    resume = models.OneToOneField(
        ResumeSubmission,
        on_delete=models.CASCADE,
        related_name='analysis_report',
        verbose_name='简历'
    )
    match_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='匹配得分(0-100)'
    )
    match_level = models.CharField(
        max_length=20,
        choices=MATCH_LEVEL_CHOICES,
        verbose_name='匹配等级'
    )
    
    # 提取的简历信息
    extracted_name = models.CharField(max_length=100, blank=True, verbose_name='提取姓名')
    extracted_phone = models.CharField(max_length=20, blank=True, verbose_name='提取电话')
    extracted_email = models.CharField(max_length=100, blank=True, verbose_name='提取邮箱')
    extracted_education = models.CharField(max_length=50, blank=True, verbose_name='学历')
    extracted_experience_years = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='工作年限'
    )
    extracted_skills = models.TextField(blank=True, verbose_name='技能')
    extracted_work_experience = models.TextField(blank=True, verbose_name='工作经历')
    
    # AI分析结果
    strength_analysis = models.TextField(verbose_name='优势分析')
    weakness_analysis = models.TextField(verbose_name='不足分析')
    skill_match_detail = models.TextField(verbose_name='技能匹配详情')
    experience_match_detail = models.TextField(verbose_name='经验匹配详情')
    education_match_detail = models.TextField(verbose_name='学历匹配详情')
    comprehensive_evaluation = models.TextField(verbose_name='综合评价')
    recommendation = models.TextField(verbose_name='推荐意见')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='生成时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '简历分析报告'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_resume_analysis_report'
        ordering = ['-match_score']

    def __str__(self):
        return f"{self.resume.candidate_name} - 得分{self.match_score}"


class InterviewInvitation(models.Model):
    """面试邀请"""
    STATUS_CHOICES = (
        ('pending', '待发送'),
        ('sent', '已发送'),
        ('failed', '发送失败'),
    )

    NOTIFICATION_TYPE_CHOICES = (
        ('sip', 'SIP电话'),
        ('sms', '短信'),
        ('email', '邮件'),
    )

    INTERVIEW_TYPE_CHOICES = (
        ('online', '线上面试'),
        ('offline', '到公司面试'),
    )

    resume_report = models.ForeignKey(
        ResumeAnalysisReport,
        on_delete=models.CASCADE,
        related_name='interview_invitations',
        verbose_name='简历报告'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
        verbose_name='通知方式'
    )
    interview_type = models.CharField(
        max_length=20,
        choices=INTERVIEW_TYPE_CHOICES,
        verbose_name='面试类型'
    )
    interview_time = models.DateTimeField(null=True, blank=True, verbose_name='面试时间')
    interview_location = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='面试地点/在线链接'
    )
    message_content = models.TextField(verbose_name='通知内容')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='发送状态'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_invitations',
        verbose_name='发送人'
    )
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '面试邀请'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_interview_invitation'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.resume_report.resume.candidate_name} - {self.get_notification_type_display()}"

# ========== 招聘流程配置 ==========

class RecruitmentConfig(models.Model):
    """招聘流程全局配置 — 控制各阶段的执行模式"""
    EXEC_MODE_CHOICES = (
        ('ai', 'AI自动执行'),
        ('auto', '系统自动执行'),
        ('manual', '人工手动执行'),
    )

    stage = models.CharField(max_length=50, unique=True, verbose_name='流程阶段')
    stage_name = models.CharField(max_length=100, verbose_name='阶段名称')
    exec_mode = models.CharField(
        max_length=10, choices=EXEC_MODE_CHOICES, default='manual',
        verbose_name='执行模式'
    )
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')
    description = models.TextField(blank=True, verbose_name='阶段说明')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '招聘流程配置'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_recruitment_config'
        ordering = ['sort_order']

    def __str__(self):
        return f'{self.stage_name} [{self.get_exec_mode_display()}]'


# ========== 候选人流程追踪 ==========

class CandidatePipeline(models.Model):
    """候选人招聘流程状态"""
    STAGE_CHOICES = (
        ('resume_received', '简历已接收'),
        ('ai_matching', 'AI匹配评分'),
        ('hr_review', 'HR审批筛选'),
        ('contact_interview', '联系面试'),
        ('interview', '面试中'),
        ('interview_result', '面试结果评估'),
        ('online_exam', '在线考核'),
        ('exam_review', '考核审批'),
        ('offer', '发放Offer'),
        ('onboarding', '入职办理'),
        ('completed', '已完成'),
        ('rejected', '已淘汰'),
    )

    RESULT_CHOICES = (
        ('pending', '待处理'),
        ('passed', '通过'),
        ('rejected', '淘汰'),
        ('pending_decision', '待决策'),
    )

    resume_submission = models.OneToOneField(
        ResumeSubmission, on_delete=models.CASCADE,
        related_name='pipeline', verbose_name='简历'
    )
    position = models.ForeignKey(
        JobPosition, on_delete=models.CASCADE,
        related_name='candidate_pipelines', verbose_name='岗位'
    )
    current_stage = models.CharField(
        max_length=30, choices=STAGE_CHOICES,
        default='resume_received', verbose_name='当前阶段'
    )
    stage_result = models.CharField(
        max_length=20, choices=RESULT_CHOICES,
        default='pending', verbose_name='阶段结果'
    )
    hr_reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_pipelines', verbose_name='HR审批人'
    )
    hr_comment = models.TextField(blank=True, verbose_name='HR审批意见')
    hr_reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='HR审批时间')
    overall_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='综合评分'
    )
    is_active = models.BooleanField(default=True, verbose_name='是否活跃')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '候选人流程'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_candidate_pipeline'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['current_stage']),
            models.Index(fields=['is_active', 'current_stage']),
        ]

    def __str__(self):
        name = self.resume_submission.candidate_name or '候选人'
        return f'{name} - {self.get_current_stage_display()}'


class PipelineStageLog(models.Model):
    """流程阶段操作日志"""
    ACTION_CHOICES = (
        ('enter', '进入阶段'),
        ('ai_process', 'AI处理'),
        ('auto_process', '自动处理'),
        ('manual_approve', '人工通过'),
        ('manual_reject', '人工淘汰'),
        ('auto_advance', '自动推进'),
        ('notification_sent', '已发送通知'),
        ('notification_failed', '通知失败'),
        ('exit', '离开阶段'),
    )

    pipeline = models.ForeignKey(
        CandidatePipeline, on_delete=models.CASCADE,
        related_name='stage_logs', verbose_name='流程'
    )
    stage = models.CharField(max_length=30, verbose_name='阶段')
    action = models.CharField(
        max_length=30, choices=ACTION_CHOICES, verbose_name='操作'
    )
    operator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pipeline_actions', verbose_name='操作人'
    )
    detail = models.TextField(blank=True, verbose_name='详情')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='附加数据')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')

    class Meta:
        verbose_name = '流程操作日志'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_pipeline_stage_log'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.pipeline} - {self.get_action_display()}'


# ========== 在线考核 ==========

class OnlineExam(models.Model):
    """在线考核/笔试题库"""
    TYPE_CHOICES = (
        ('technical', '技术考核'),
        ('personality', '性格测试'),
        ('comprehensive', '综合能力'),
        ('professional', '专业知识'),
        ('custom', '自定义'),
    )

    DIFFICULTY_CHOICES = (
        ('easy', '简单'),
        ('medium', '中等'),
        ('hard', '困难'),
    )

    title = models.CharField(max_length=200, verbose_name='考核名称')
    exam_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default='technical',
        verbose_name='考核类型'
    )
    difficulty = models.CharField(
        max_length=10, choices=DIFFICULTY_CHOICES, default='medium',
        verbose_name='难度'
    )
    description = models.TextField(blank=True, verbose_name='考核说明')
    duration_minutes = models.IntegerField(default=60, verbose_name='考试时长(分钟)')
    passing_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=60.00,
        verbose_name='及格分'
    )
    total_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=100.00,
        verbose_name='总分'
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_exams',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '在线考核'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_online_exam'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ExamQuestion(models.Model):
    """考核题目"""
    QUESTION_TYPE_CHOICES = (
        ('single', '单选题'),
        ('multiple', '多选题'),
        ('true_false', '判断题'),
        ('essay', '问答题'),
        ('code', '编程题'),
    )

    exam = models.ForeignKey(
        OnlineExam, on_delete=models.CASCADE,
        related_name='questions', verbose_name='所属考核'
    )
    question_type = models.CharField(
        max_length=20, choices=QUESTION_TYPE_CHOICES, verbose_name='题目类型'
    )
    content = models.TextField(verbose_name='题目内容')
    options = models.JSONField(
        default=list, blank=True,
        help_text='选择题选项列表，格式: [{"key": "A", "text": "选项内容"}]',
        verbose_name='选项'
    )
    correct_answer = models.TextField(
        blank=True,
        help_text='正确答案：单选填key，多选填key列表JSON，判断填true/false，问答填参考答案',
        verbose_name='正确答案'
    )
    score = models.DecimalField(
        max_digits=6, decimal_places=2, default=5.00,
        verbose_name='分值'
    )
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    bank_group = models.ForeignKey(
        'QuestionBankGroup', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='questions',
        verbose_name='所属题库分组'
    )
    tags = models.JSONField(
        default=list, blank=True,
        help_text='标签列表，如 ["Python", "Django", "中级"]',
        verbose_name='标签'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '考核题目'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_exam_question'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.exam.title} - 第{self.sort_order}题'


class CandidateExam(models.Model):
    """候选人考核记录"""
    STATUS_CHOICES = (
        ('assigned', '已分配'),
        ('in_progress', '考核中'),
        ('submitted', '已提交'),
        ('ai_graded', 'AI已评分'),
        ('hr_reviewed', 'HR已审批'),
        ('passed', '通过'),
        ('failed', '未通过'),
    )

    pipeline = models.ForeignKey(
        CandidatePipeline, on_delete=models.CASCADE,
        related_name='exams', verbose_name='候选人流程'
    )
    exam = models.ForeignKey(
        OnlineExam, on_delete=models.CASCADE,
        related_name='candidate_exams', verbose_name='考核'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='assigned',
        verbose_name='状态'
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name='提交时间')
    total_correct = models.IntegerField(null=True, blank=True, verbose_name='正确题数')
    total_questions = models.IntegerField(null=True, blank=True, verbose_name='总题数')
    ai_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='AI评分'
    )
    ai_feedback = models.TextField(blank=True, verbose_name='AI评语')
    hr_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='HR调整分'
    )
    hr_feedback = models.TextField(blank=True, verbose_name='HR评语')
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_exams', verbose_name='审批人'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    exam_link = models.CharField(max_length=500, blank=True, verbose_name='考核链接')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '候选人考核'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_candidate_exam'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.pipeline} - {self.exam.title}'


class CandidateExamAnswer(models.Model):
    """候选人答题记录"""
    candidate_exam = models.ForeignKey(
        CandidateExam, on_delete=models.CASCADE,
        related_name='answers', verbose_name='考核记录'
    )
    question = models.ForeignKey(
        ExamQuestion, on_delete=models.CASCADE,
        related_name='candidate_answers', verbose_name='题目'
    )
    answer = models.TextField(blank=True, verbose_name='考生答案')
    is_correct = models.BooleanField(null=True, blank=True, verbose_name='是否自动判对')
    ai_score = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='AI给分'
    )
    ai_comment = models.TextField(blank=True, verbose_name='AI点评')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作答时间')

    class Meta:
        verbose_name = '答题记录'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_exam_answer'
        unique_together = [('candidate_exam', 'question')]

    def __str__(self):
        return f'{self.candidate_exam} - 第{self.question.sort_order}题'


# ========== 入职管理 ==========

class OnboardingRecord(models.Model):
    """入职记录"""
    STATUS_CHOICES = (
        ('pending', '待入职'),
        ('in_progress', '办理中'),
        ('completed', '已入职'),
        ('cancelled', '已取消'),
    )

    pipeline = models.OneToOneField(
        CandidatePipeline, on_delete=models.CASCADE,
        related_name='onboarding', verbose_name='候选人流程'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        verbose_name='状态'
    )
    expected_date = models.DateField(
        null=True, blank=True, verbose_name='预计入职日期'
    )
    actual_date = models.DateField(
        null=True, blank=True, verbose_name='实际入职日期'
    )
    offer_letter = models.CharField(
        max_length=500, blank=True, verbose_name='Offer文件路径'
    )
    salary_offered = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Offer薪资'
    )
    remarks = models.TextField(blank=True, verbose_name='备注')
    handler = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='handled_onboardings', verbose_name='经办人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '入职记录'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_onboarding_record'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.pipeline} - 入职'


# ========== 通知记录 ==========

class RecruitmentNotification(models.Model):
    """招聘通知记录（集成短信/邮件/电话）"""
    NOTIFY_TYPE_CHOICES = (
        ('sms', '短信'),
        ('email', '邮件'),
        ('phone', '电话'),
    )

    STATUS_CHOICES = (
        ('pending', '待发送'),
        ('sent', '已发送'),
        ('failed', '发送失败'),
        ('delivered', '已送达'),
    )

    SCENE_CHOICES = (
        ('interview_invite', '面试邀请'),
        ('exam_invite', '考核邀请'),
        ('offer_notice', 'Offer通知'),
        ('onboarding_notice', '入职通知'),
        ('rejection_notice', '淘汰通知'),
        ('custom', '自定义'),
    )

    pipeline = models.ForeignKey(
        CandidatePipeline, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='候选人流程'
    )
    notify_type = models.CharField(
        max_length=10, choices=NOTIFY_TYPE_CHOICES, verbose_name='通知方式'
    )
    scene = models.CharField(
        max_length=30, choices=SCENE_CHOICES, verbose_name='通知场景'
    )
    recipient = models.CharField(max_length=200, verbose_name='接收人')
    contact_info = models.CharField(max_length=200, verbose_name='联系方式')
    title = models.CharField(max_length=200, blank=True, verbose_name='标题')
    content = models.TextField(verbose_name='通知内容')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        verbose_name='发送状态'
    )
    sender = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_recruitment_notifications', verbose_name='发送人'
    )
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    external_id = models.CharField(
        max_length=200, blank=True, verbose_name='外部服务ID'
    )
    retry_count = models.IntegerField(default=0, verbose_name='重试次数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = '招聘通知'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_recruitment_notification'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_scene_display()} - {self.get_notify_type_display()} -> {self.recipient}'



class QuestionBankGroup(models.Model):
    """题库分组"""
    DIFFICULTY_CHOICES = (
        ('easy', '简单'),
        ('medium', '中等'),
        ('hard', '困难'),
    )

    name = models.CharField(max_length=200, verbose_name='分组名称')
    position = models.ForeignKey(
        'JobPosition', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='question_bank_groups',
        verbose_name='关联岗位'
    )
    function_tags = models.JSONField(
        default=list, blank=True,
        help_text='职能标签',
        verbose_name='职能标签'
    )
    difficulty = models.CharField(
        max_length=10, choices=DIFFICULTY_CHOICES, default='medium',
        verbose_name='难度等级'
    )
    tags = models.JSONField(
        default=list, blank=True,
        help_text='通用标签',
        verbose_name='标签'
    )
    description = models.TextField(blank=True, verbose_name='分组说明')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_question_bank_groups',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '题库分组'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_question_bank_group'
        ordering = ['-created_at']

    def __str__(self):
        parts = [self.name]
        if self.position:
            parts.append(self.position.title)
        parts.append(self.get_difficulty_display())
        return ' - '.join(parts)

    @property
    def question_count(self):
        return self.questions.count()


class ExamAutoGenerationRule(models.Model):
    """自动组卷规则"""
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('active', '启用'),
        ('archived', '归档'),
    )

    name = models.CharField(max_length=200, verbose_name='规则名称')
    description = models.TextField(blank=True, verbose_name='规则说明')
    bank_groups = models.ManyToManyField(
        QuestionBankGroup, blank=True, related_name='generation_rules',
        verbose_name='题库分组'
    )
    total_questions = models.IntegerField(default=20, verbose_name='题目总数')
    total_score = models.DecimalField(
        max_digits=6, decimal_places=2, default=100.00,
        verbose_name='总分'
    )
    difficulty_distribution = models.JSONField(
        default=dict, blank=True,
        help_text='难度分布百分比',
        verbose_name='难度分布'
    )
    question_type_distribution = models.JSONField(
        default=dict, blank=True,
        help_text='题型数量分布',
        verbose_name='题型分布'
    )
    tag_requirements = models.JSONField(
        default=dict, blank=True,
        help_text='标签要求',
        verbose_name='标签要求'
    )
    position_filter = models.ForeignKey(
        'JobPosition', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='exam_generation_rules',
        verbose_name='岗位筛选'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft',
        verbose_name='状态'
    )
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_exam_rules',
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '自动组卷规则'
        verbose_name_plural = verbose_name
        db_table = 'hrbp_exam_auto_generation_rule'
        ordering = ['-created_at']

    def __str__(self):
        return self.name
