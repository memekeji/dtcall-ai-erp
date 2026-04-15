from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.user.models import Admin
from .models import (
    PersonalSchedule, WorkRecord, WorkReport,
    PersonalNote, PersonalTask, PersonalContact, MeetingMinutes
)

User = get_user_model()


class PersonalScheduleForm(forms.ModelForm):
    class Meta:
        model = PersonalSchedule
        fields = [
            'title', 'content', 'start_time', 'end_time', 'priority',
            'status', 'location', 'reminder_time', 'is_all_day', 'is_private'
        ]
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入日程标题'}),
            'content': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入日程内容',
                    'rows': 4}),
            'start_time': forms.DateTimeInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'datetime-local'}),
            'priority': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'status': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'location': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入地点'}),
            'reminder_time': forms.DateTimeInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'datetime-local'}),
            'is_all_day': forms.CheckboxInput(
                attrs={
                    'class': 'layui-checkbox',
                    'lay-skin': 'primary'}),
            'is_private': forms.CheckboxInput(
                attrs={
                    'class': 'layui-checkbox',
                    'lay-skin': 'primary'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if start_time and end_time and start_time > end_time:
            self.add_error('end_time', '结束时间必须晚于开始时间')

        return cleaned_data


class WorkRecordForm(forms.ModelForm):
    class Meta:
        model = WorkRecord
        fields = [
            'title', 'content', 'work_type', 'work_date', 'start_time',
            'end_time', 'duration', 'progress', 'difficulty', 'result',
            'problem', 'next_plan'
        ]
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入工作标题'}),
            'content': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入工作内容',
                    'rows': 4}),
            'work_type': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'work_date': forms.DateInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'date'}),
            'start_time': forms.TimeInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'time'}),
            'end_time': forms.TimeInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'time'}),
            'duration': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'step': '0.1',
                    'placeholder': '工作时长(小时)'}),
            'progress': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'min': '0',
                    'max': '100',
                    'placeholder': '完成进度(%)'}),
            'difficulty': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'min': '1',
                    'max': '5',
                    'placeholder': '难度系数(1-5)'}),
            'result': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入工作成果',
                    'rows': 3}),
            'problem': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入遇到的问题',
                    'rows': 3}),
            'next_plan': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入下步计划',
                    'rows': 3}),
        }


class WorkReportForm(forms.ModelForm):
    class Meta:
        model = WorkReport
        fields = [
            'title', 'report_type', 'report_date', 'summary',
            'completed_work', 'next_work', 'problems', 'suggestions'
        ]
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入汇报标题'}),
            'report_type': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'report_date': forms.DateInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'date'}),
            'summary': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入工作总结',
                    'rows': 4}),
            'completed_work': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入已完成工作',
                    'rows': 4}),
            'next_work': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入下期工作计划',
                    'rows': 4}),
            'problems': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入存在问题',
                    'rows': 3}),
            'suggestions': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入意见建议',
                    'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recipient_users'] = forms.ModelMultipleChoiceField(
            queryset=Admin.objects.filter(status=1).order_by('name'),
            widget=forms.CheckboxSelectMultiple,
            required=False,
            label='接收人'
        )


class PersonalNoteForm(forms.ModelForm):
    class Meta:
        model = PersonalNote
        fields = [
            'title',
            'content',
            'category',
            'tags',
            'is_important',
            'is_private']
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入笔记标题'}),
            'content': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入笔记内容',
                    'rows': 10}),
            'category': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'tags': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入标签，多个标签用逗号分隔'}),
        }


class PersonalTaskForm(forms.ModelForm):
    class Meta:
        model = PersonalTask
        fields = [
            'title', 'description', 'priority', 'status', 'due_date',
            'progress', 'estimated_hours', 'actual_hours'
        ]
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入任务标题'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入任务描述',
                    'rows': 4}),
            'priority': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'status': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'due_date': forms.DateTimeInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'datetime-local'}),
            'progress': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'min': '0',
                    'max': '100',
                    'placeholder': '完成进度(%)'}),
            'estimated_hours': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'step': '0.1',
                    'placeholder': '预估工时'}),
            'actual_hours': forms.NumberInput(
                attrs={
                    'class': 'layui-input',
                    'step': '0.1',
                    'placeholder': '实际工时'}),
        }


class PersonalContactForm(forms.ModelForm):
    class Meta:
        model = PersonalContact
        fields = [
            'name', 'company', 'position', 'phone', 'mobile',
            'email', 'address', 'notes', 'tags', 'is_important'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入姓名'}),
            'company': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入公司'}),
            'position': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入职位'}),
            'phone': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入电话'}),
            'mobile': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入手机'}),
            'email': forms.EmailInput(attrs={'class': 'layui-input', 'placeholder': '请输入邮箱'}),
            'address': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入地址', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'layui-textarea', 'placeholder': '请输入备注', 'rows': 3}),
            'tags': forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '请输入标签，多个标签用逗号分隔'}),
        }


class MeetingMinutesForm(forms.ModelForm):
    class Meta:
        model = MeetingMinutes
        fields = [
            'title',
            'meeting_type',
            'meeting_date',
            'location',
            'host',
            'attendees',
            'content',
            'decisions',
            'action_items',
            'attachments',
            'is_public']
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入会议主题'}),
            'meeting_type': forms.Select(
                attrs={
                    'class': 'layui-input'}),
            'meeting_date': forms.DateTimeInput(
                attrs={
                    'class': 'layui-input',
                    'type': 'datetime-local'}),
            'location': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入会议地点'}),
            'host': forms.TextInput(
                attrs={
                    'class': 'layui-input',
                    'placeholder': '请输入主持人'}),
            'attendees': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入参会人员，多个人员用逗号分隔',
                    'rows': 2}),
            'content': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入会议内容',
                    'rows': 5}),
            'decisions': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入会议决议',
                    'rows': 3}),
            'action_items': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入行动项',
                    'rows': 3}),
            'attachments': forms.Textarea(
                attrs={
                    'class': 'layui-textarea',
                    'placeholder': '请输入附件信息',
                    'rows': 2}),
            'is_public': forms.CheckboxInput(
                attrs={
                    'class': 'layui-checkbox',
                    'lay-skin': 'primary'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        meeting_date = cleaned_data.get('meeting_date')

        if meeting_date and meeting_date > timezone.now():
            self.add_error('meeting_date', '会议时间不能是未来时间')

        return cleaned_data
