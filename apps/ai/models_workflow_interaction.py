"""
工作流交互模型
提供工作流执行过程中的用户交互机制
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class WorkflowInteraction(models.Model):
    """工作流交互记录 - 跟踪工作流执行中的用户交互"""
    
    INTERACTION_TYPES = [
        ('approval', '审批确认'),
        ('input', '表单输入'),
        ('confirmation', '确认操作'),
        ('selection', '选项选择'),
        ('review', '审核确认'),
        ('feedback', '反馈输入'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('in_progress', '处理中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
        ('timeout', '超时'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', '低'),
        ('normal', '普通'),
        ('high', '高'),
        ('urgent', '紧急'),
    ]
    
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)
    workflow_execution = models.ForeignKey(
        'AIWorkflowExecution', 
        on_delete=models.CASCADE, 
        related_name='interactions',
        verbose_name='工作流执行'
    )
    node_execution = models.ForeignKey(
        'NodeExecution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interactions',
        verbose_name='节点执行'
    )
    interaction_type = models.CharField(
        max_length=20, 
        choices=INTERACTION_TYPES, 
        default='approval',
        verbose_name='交互类型'
    )
    title = models.CharField(max_length=200, verbose_name='交互标题')
    description = models.TextField(blank=True, null=True, verbose_name='交互描述')
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        verbose_name='状态'
    )
    priority = models.CharField(
        max_length=20, 
        choices=PRIORITY_CHOICES, 
        default='normal',
        verbose_name='优先级'
    )
    requester = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='requested_interactions',
        verbose_name='请求者'
    )
    handler = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='handled_interactions',
        verbose_name='处理人'
    )
    input_schema = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name='输入Schema',
        help_text='定义需要用户输入的字段和类型'
    )
    input_data = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name='用户输入数据'
    )
    output_data = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name='输出数据'
    )
    result = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name='处理结果'
    )
    comment = models.TextField(blank=True, null=True, verbose_name='处理备注')
    timeout = models.IntegerField(
        default=3600,
        verbose_name='超时时间(秒)',
        help_text='0表示不超时'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    responded_at = models.DateTimeField(blank=True, null=True, verbose_name='响应时间')
    
    class Meta:
        verbose_name = '工作流交互'
        verbose_name_plural = '工作流交互'
        db_table = 'ai_workflow_interaction'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    @property
    def is_expired(self):
        """检查是否超时"""
        if self.timeout == 0:
            return False
        return (timezone.now() - self.created_at).total_seconds() > self.timeout
    
    @property
    def is_pending(self):
        """是否待处理"""
        return self.status in ['pending', 'in_progress']
    
    def can_complete(self, user):
        """检查用户是否有权限处理"""
        if self.requester_id and user.id == self.requester_id:
            return True
        if self.handler_id and user.id == self.handler_id:
            return True
        return False


class WorkflowInteractionTemplate(models.Model):
    """工作流交互模板 - 预定义的交互配置"""
    
    INTERACTION_TYPES = [
        ('approval', '审批确认'),
        ('input', '表单输入'),
        ('confirmation', '确认操作'),
        ('selection', '选项选择'),
        ('review', '审核确认'),
    ]
    
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)
    name = models.CharField(max_length=100, verbose_name='模板名称')
    description = models.TextField(blank=True, null=True, verbose_name='模板描述')
    interaction_type = models.CharField(
        max_length=20, 
        choices=INTERACTION_TYPES,
        verbose_name='交互类型'
    )
    input_schema = models.JSONField(verbose_name='输入Schema')
    default_title = models.CharField(max_length=200, verbose_name='默认标题')
    default_description = models.TextField(blank=True, null=True, verbose_name='默认描述')
    default_timeout = models.IntegerField(default=3600, verbose_name='默认超时时间(秒)')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '工作流交互模板'
        verbose_name_plural = '工作流交互模板'
        db_table = 'ai_workflow_interaction_template'
    
    def __str__(self):
        return self.name
    
    def apply(self, **kwargs):
        """应用模板创建交互"""
        return WorkflowInteraction.objects.create(
            interaction_type=self.interaction_type,
            title=kwargs.get('title', self.default_title),
            description=kwargs.get('description', self.default_description),
            input_schema=self.input_schema,
            timeout=kwargs.get('timeout', self.default_timeout),
            requester=kwargs.get('requester'),
            handler=kwargs.get('handler'),
            **kwargs
        )


class NodeInputForm(models.Model):
    """节点输入表单 - 定义节点需要的用户输入"""
    
    FIELD_TYPES = [
        ('text', '文本输入'),
        ('textarea', '多行文本'),
        ('number', '数字输入'),
        ('select', '下拉选择'),
        ('multiselect', '多选'),
        ('radio', '单选'),
        ('checkbox', '复选框'),
        ('date', '日期选择'),
        ('datetime', '日期时间选择'),
        ('file', '文件上传'),
        ('richtext', '富文本'),
        ('table', '表格输入'),
    ]
    
    VALIDATION_TYPES = [
        ('required', '必填'),
        ('optional', '可选'),
        ('email', '邮箱格式'),
        ('phone', '手机号格式'),
        ('number', '数字'),
        ('integer', '整数'),
        ('regex', '正则表达式'),
    ]
    
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)
    node = models.ForeignKey(
        'WorkflowNode',
        on_delete=models.CASCADE,
        related_name='input_forms',
        verbose_name='所属节点'
    )
    field_name = models.CharField(max_length=100, verbose_name='字段名称')
    field_label = models.CharField(max_length=200, verbose_name='字段标签')
    field_type = models.CharField(
        max_length=20, 
        choices=FIELD_TYPES,
        default='text',
        verbose_name='字段类型'
    )
    field_value = models.JSONField(
        blank=True, 
        null=True, 
        verbose_name='字段值',
        help_text='用于select、radio等选项类型的选项值'
    )
    placeholder = models.CharField(max_length=200, blank=True, null=True, verbose_name='占位符')
    help_text = models.TextField(blank=True, null=True, verbose_name='帮助文本')
    default_value = models.JSONField(blank=True, null=True, verbose_name='默认值')
    validation_type = models.CharField(
        max_length=20,
        choices=VALIDATION_TYPES,
        default='optional',
        verbose_name='验证类型'
    )
    validation_rules = models.JSONField(
        blank=True, 
        null=True,
        verbose_name='验证规则'
    )
    order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '节点输入表单'
        verbose_name_plural = '节点输入表单'
        db_table = 'ai_node_input_form'
        ordering = ['order']
    
    def __str__(self):
        return f"{self.node.name} - {self.field_label}"
    
    def to_form_schema(self):
        """转换为表单Schema"""
        schema = {
            'name': self.field_name,
            'label': self.field_label,
            'type': self.field_type,
            'placeholder': self.placeholder or '',
            'helpText': self.help_text or '',
            'default': self.default_value,
            'validation': {
                'type': self.validation_type,
                'rules': self.validation_rules or {}
            }
        }
        
        if self.field_value:
            schema['options'] = self.field_value
        
        return schema


class WorkflowCheckpoint(models.Model):
    """工作流检查点 - 支持工作流执行过程中的断点和恢复"""
    
    CHECKPOINT_TYPES = [
        ('manual', '手动保存'),
        ('auto', '自动保存'),
        ('node', '节点检查点'),
        ('error', '错误恢复点'),
    ]
    
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)
    workflow_execution = models.ForeignKey(
        'AIWorkflowExecution',
        on_delete=models.CASCADE,
        related_name='checkpoints',
        verbose_name='工作流执行'
    )
    checkpoint_type = models.CharField(
        max_length=20,
        choices=CHECKPOINT_TYPES,
        default='manual',
        verbose_name='检查点类型'
    )
    name = models.CharField(max_length=100, verbose_name='检查点名称')
    context_data = models.JSONField(verbose_name='上下文数据')
    node_states = models.JSONField(verbose_name='节点状态')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '工作流检查点'
        verbose_name_plural = '工作流检查点'
        db_table = 'ai_workflow_checkpoint'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.workflow_execution.id} - {self.name}"
    
    def restore(self):
        """恢复检查点数据"""
        return {
            'context_data': self.context_data,
            'node_states': self.node_states
        }
