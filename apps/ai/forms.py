from django import forms
from .models import (
    AIModelConfig,
    AIWorkflow,
    WorkflowNode,
    WorkflowConnection,
    AIKnowledgeBase,
    AIKnowledgeItem,
    AISalesStrategy,
    AIIntentRecognition,
    AIEmotionAnalysis,
    AIComplianceRule,
    AIActionTrigger
)


class AIModelConfigForm(forms.ModelForm):
    """AI模型配置表单"""
    class Meta:
        model = AIModelConfig
        fields = [
            'name',
            'provider',
            'model_type',
            'model_name',
            'api_key',
            'api_base',
            'organization',
            'project',
            'max_tokens',
            'temperature',
            'top_p',
            'is_active',
            'is_default']
        widgets = {
            'api_key': forms.PasswordInput(render_value=True),
            'api_base': forms.URLInput(),
        }
        # 设置非必填字段
        required = {
            'name': True,
            'provider': True,
            'model_type': True,
            'model_name': True,
            'api_key': True,
            'api_base': True,
            'organization': False,
            'project': False,
            'max_tokens': True,
            'temperature': True,
            'top_p': True,
            'is_active': True,
            'is_default': False,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 设置默认值
        self.fields['max_tokens'].initial = 2048
        self.fields['temperature'].initial = 0.7
        self.fields['top_p'].initial = 1.0
        self.fields['is_active'].initial = True
        self.fields['is_default'].initial = False

        # 设置非必填字段
        self.fields['organization'].required = False
        self.fields['project'].required = False
        self.fields['is_default'].required = False

        # 添加layui样式
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'layui-input'})

        # 为不同类型的字段添加更合适的样式
        self.fields['max_tokens'].widget.attrs.update(
            {'type': 'number', 'min': '100', 'max': '8192'})
        self.fields['temperature'].widget.attrs.update(
            {'type': 'number', 'step': '0.1', 'min': '0', 'max': '2'})
        self.fields['top_p'].widget.attrs.update(
            {'type': 'number', 'step': '0.1', 'min': '0', 'max': '1'})


class AIWorkflowForm(forms.ModelForm):
    """AI工作流表单"""
    class Meta:
        model = AIWorkflow
        fields = ['name', 'description', 'status', 'is_public']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'layui-input'})
        self.fields['description'].widget.attrs.update(
            {'class': 'layui-textarea'})
        self.fields['is_public'].widget.attrs.update(
            {'lay-skin': 'switch', 'lay-text': '是|否'})


class WorkflowNodeForm(forms.ModelForm):
    """工作流节点表单"""
    class Meta:
        model = WorkflowNode
        fields = ['name', 'node_type', 'config', 'position_x', 'position_y']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'layui-input'})
        self.fields['config'].widget.attrs.update({'class': 'layui-textarea'})


class WorkflowConnectionForm(forms.ModelForm):
    """工作流连接表单"""
    class Meta:
        model = WorkflowConnection
        fields = [
            'source_node',
            'target_node',
            'source_handle',
            'target_handle',
            'config']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'layui-input'})
        self.fields['config'].widget.attrs.update({'class': 'layui-textarea'})


class AIKnowledgeBaseForm(forms.ModelForm):
    """AI知识库表单"""
    class Meta:
        model = AIKnowledgeBase
        fields = ['name', 'description', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'layui-input'})
        self.fields['description'].widget.attrs.update(
            {'class': 'layui-textarea'})


class AIKnowledgeItemForm(forms.ModelForm):
    """AI知识条目表单"""
    class Meta:
        model = AIKnowledgeItem
        fields = [
            'title',
            'content',
            'knowledge_type',
            'status',
            'knowledge_base',
            'tags',
            'file']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['tags', 'file']:
                self.fields[field].widget.attrs.update(
                    {'class': 'layui-input'})
        self.fields['content'].widget.attrs.update(
            {'class': 'layui-textarea', 'rows': 10})
        self.fields['tags'].widget = forms.TextInput(
            attrs={'class': 'layui-input', 'placeholder': '请输入标签，用逗号分隔'})
        self.fields['file'].widget.attrs.update(
            {'class': 'layui-upload-file', 'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt'})

    def clean_tags(self):
        tags = self.cleaned_data.get('tags', '')
        if tags:
            return [tag.strip() for tag in tags.split(',') if tag.strip()]
        return []


class AISalesStrategyForm(forms.ModelForm):
    """AI销售策略表单"""
    class Meta:
        model = AISalesStrategy
        fields = [
            'name',
            'strategy_type',
            'description',
            'config',
            'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'config':
                self.fields[field].widget.attrs.update(
                    {'class': 'layui-input'})
        self.fields['description'].widget.attrs.update(
            {'class': 'layui-textarea'})
        self.fields['config'].widget = forms.Textarea(
            attrs={
                'class': 'layui-textarea',
                'rows': 10,
                'placeholder': '请输入JSON格式的配置'})


class AIIntentRecognitionForm(forms.ModelForm):
    """AI意图识别表单"""
    class Meta:
        model = AIIntentRecognition
        fields = [
            'intent_type',
            'keywords',
            'examples',
            'description',
            'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['keywords', 'examples']:
                self.fields[field].widget.attrs.update(
                    {'class': 'layui-input'})
        self.fields['description'].widget.attrs.update(
            {'class': 'layui-textarea'})
        self.fields['keywords'].widget = forms.Textarea(
            attrs={
                'class': 'layui-textarea',
                'rows': 5,
                'placeholder': '请输入JSON格式的关键词列表，如：["询价", "价格", "多少钱"]'})
        self.fields['examples'].widget = forms.Textarea(
            attrs={
                'class': 'layui-textarea',
                'rows': 5,
                'placeholder': '请输入JSON格式的示例句子列表'})


class AIEmotionAnalysisForm(forms.ModelForm):
    """AI情绪分析表单"""
    class Meta:
        model = AIEmotionAnalysis
        fields = ['emotion_type', 'keywords', 'description', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'keywords':
                self.fields[field].widget.attrs.update(
                    {'class': 'layui-input'})
        self.fields['description'].widget.attrs.update(
            {'class': 'layui-textarea'})
        self.fields['keywords'].widget = forms.Textarea(
            attrs={'class': 'layui-textarea', 'rows': 5, 'placeholder': '请输入JSON格式的关键词列表'})


class AIComplianceRuleForm(forms.ModelForm):
    """AI合规规则表单"""
    class Meta:
        model = AIComplianceRule
        fields = [
            'rule_type',
            'content',
            'description',
            'severity',
            'action',
            'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'layui-input'})
        self.fields['content'].widget.attrs.update({'class': 'layui-textarea'})
        self.fields['description'].widget.attrs.update(
            {'class': 'layui-textarea'})


class AIActionTriggerForm(forms.ModelForm):
    """AI自动行动触发表单"""
    class Meta:
        model = AIActionTrigger
        fields = ['name', 'action_type', 'conditions', 'config', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['conditions', 'config']:
                self.fields[field].widget.attrs.update(
                    {'class': 'layui-input'})
        self.fields['conditions'].widget = forms.Textarea(
            attrs={'class': 'layui-textarea', 'rows': 5, 'placeholder': '请输入JSON格式的触发条件'})
        self.fields['config'].widget = forms.Textarea(
            attrs={
                'class': 'layui-textarea',
                'rows': 5,
                'placeholder': '请输入JSON格式的行动配置'})
