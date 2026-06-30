"""
AI-HRBP表单
"""
from django import forms
from .models import JobPosition, ResumeSubmission, CandidatePipeline, OnlineExam, ExamQuestion, QuestionBankGroup, ExamAutoGenerationRule, OnboardingRecord, RecruitmentConfig


class JobPositionForm(forms.ModelForm):
    """岗位表单"""
    
    class Meta:
        model = JobPosition
        fields = [
            'title', 'department', 'work_type', 'location',
            'salary_min', 'salary_max', 'headcount',
            'description', 'requirements', 'responsibilities',
            'skills_required', 'education_required', 'experience_years',
            'status', 'deadline'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'layui-input',
                'placeholder': '请输入岗位名称'
            }),
            'department': forms.Select(attrs={
                'class': 'layui-input',
                'lay-search': ''
            }),
            'work_type': forms.Select(attrs={
                'class': 'layui-input'
            }),
            'location': forms.TextInput(attrs={
                'class': 'layui-input',
                'placeholder': '请输入工作地点'
            }),
            'salary_min': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': '最低薪资'
            }),
            'salary_max': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': '最高薪资'
            }),
            'headcount': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': '招聘人数'
            }),
            'description': forms.Textarea(attrs={
                'class': 'layui-textarea',
                'placeholder': '请输入岗位描述',
                'rows': 4
            }),
            'requirements': forms.Textarea(attrs={
                'class': 'layui-textarea',
                'placeholder': '请输入任职要求',
                'rows': 4
            }),
            'responsibilities': forms.Textarea(attrs={
                'class': 'layui-textarea',
                'placeholder': '请输入岗位职责',
                'rows': 4
            }),
            'skills_required': forms.Textarea(attrs={
                'class': 'layui-textarea',
                'placeholder': '请输入技能要求（每行一项）',
                'rows': 3
            }),
            'education_required': forms.TextInput(attrs={
                'class': 'layui-input',
                'placeholder': '如：本科及以上'
            }),
            'experience_years': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': '工作年限（年）'
            }),
            'status': forms.Select(attrs={
                'class': 'layui-input'
            }),
            'deadline': forms.DateInput(attrs={
                'class': 'layui-input',
                'placeholder': '截止日期',
                'type': 'date'
            }),
        }


class ResumeSubmissionForm(forms.ModelForm):
    """简历提交表单"""
    
    class Meta:
        model = ResumeSubmission
        fields = ['position']
        widgets = {
            'position': forms.Select(attrs={
                'class': 'layui-input',
                'lay-search': ''
            }),
        }


class CandidatePipelineForm(forms.ModelForm):
    """候选人流程表单 — 用于HR审批"""

    class Meta:
        model = CandidatePipeline
        fields = ['hr_comment']
        widgets = {
            'hr_comment': forms.Textarea(attrs={
                'class': 'layui-textarea',
                'placeholder': '请输入审批意见',
                'rows': 4,
            }),
        }


class OnlineExamForm(forms.ModelForm):
    """在线考核表单"""

    class Meta:
        model = OnlineExam
        fields = [
            'title', 'exam_type', 'difficulty', 'description',
            'duration_minutes', 'passing_score', 'total_score', 'is_active',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'layui-input',
                'placeholder': '请输入考核名称',
            }),
            'exam_type': forms.Select(attrs={'class': 'layui-input'}),
            'difficulty': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={
                'class': 'layui-textarea',
                'placeholder': '请输入考核说明',
                'rows': 3,
            }),
            'duration_minutes': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': '分钟',
            }),
            'passing_score': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': '及格分数线',
            }),
            'total_score': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': '总分',
            }),
        }


class ExamQuestionForm(forms.ModelForm):
    """考核题目表单"""

    class Meta:
        model = ExamQuestion
        fields = ['question_type', 'content', 'options', 'correct_answer', 'score', 'sort_order', 'bank_group', 'tags']
        widgets = {
            'question_type': forms.Select(attrs={'class': 'layui-input'}),
            'content': forms.Textarea(attrs={
                'class': 'layui-textarea',
                'placeholder': '请输入题目内容',
                'rows': 3,
            }),
            'correct_answer': forms.TextInput(attrs={
                'class': 'layui-input',
                'placeholder': '正确答案',
            }),
            'score': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': '分值',
            }),
            'sort_order': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': '排序号',
            }),
            'bank_group': forms.Select(attrs={'class': 'layui-input', 'lay-search': ''}),
            'tags': forms.TextInput(attrs={
                'class': 'layui-input',
                'placeholder': '标签，逗号分隔',
            }),
        }


class OnboardingForm(forms.ModelForm):
    """入职记录表单"""

    class Meta:
        model = OnboardingRecord
        fields = ['expected_date', 'actual_date', 'salary_offered', 'remarks']
        widgets = {
            'expected_date': forms.DateInput(attrs={
                'class': 'layui-input',
                'type': 'date',
            }),
            'actual_date': forms.DateInput(attrs={
                'class': 'layui-input',
                'type': 'date',
            }),
            'salary_offered': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': 'Offer薪资',
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'layui-textarea',
                'rows': 3,
                'placeholder': '备注信息',
            }),
        }


class RecruitmentConfigForm(forms.ModelForm):
    """招聘流程配置表单"""

    class Meta:
        model = RecruitmentConfig
        fields = ['exec_mode', 'is_enabled', 'description']
        widgets = {
            'exec_mode': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={
                'class': 'layui-textarea',
                'rows': 2,
                'placeholder': '阶段说明',
            }),
        }



class QuestionBankGroupForm(forms.ModelForm):
    """题库分组表单"""

    class Meta:
        model = QuestionBankGroup
        fields = ['name', 'position', 'function_tags', 'difficulty', 'tags', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'layui-input',
                'placeholder': '请输入分组名称',
            }),
            'position': forms.Select(attrs={
                'class': 'layui-input',
                'lay-search': '',
            }),
            'function_tags': forms.TextInput(attrs={
                'class': 'layui-input',
                'placeholder': '职能标签，逗号分隔，如：后端开发,系统架构',
            }),
            'difficulty': forms.Select(attrs={'class': 'layui-input'}),
            'tags': forms.TextInput(attrs={
                'class': 'layui-input',
                'placeholder': '通用标签，逗号分隔，如：Python,微服务',
            }),
            'description': forms.Textarea(attrs={
                'class': 'layui-textarea',
                'placeholder': '分组说明',
                'rows': 3,
            }),
        }


class ExamAutoGenerationRuleForm(forms.ModelForm):
    """自动组卷规则表单"""

    class Meta:
        model = ExamAutoGenerationRule
        fields = [
            'name', 'description', 'bank_groups', 'total_questions', 'total_score',
            'difficulty_distribution', 'question_type_distribution',
            'tag_requirements', 'position_filter', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'layui-input',
                'placeholder': '请输入规则名称',
            }),
            'description': forms.Textarea(attrs={
                'class': 'layui-textarea',
                'placeholder': '规则说明',
                'rows': 2,
            }),
            'bank_groups': forms.SelectMultiple(attrs={
                'class': 'layui-input',
                'lay-search': '',
            }),
            'total_questions': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': '题目总数',
            }),
            'total_score': forms.NumberInput(attrs={
                'class': 'layui-input',
                'placeholder': '总分',
            }),
            'position_filter': forms.Select(attrs={
                'class': 'layui-input',
                'lay-search': '',
            }),
            'status': forms.Select(attrs={'class': 'layui-input'}),
        }
