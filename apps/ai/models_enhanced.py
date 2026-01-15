"""
AI工作流增强模型扩展
添加权限管理、审计日志等增强功能模型
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class WorkflowPermission(models.Model):
    """工作流权限配置"""
    
    ROLES = [
        ('admin', '管理员'),
        ('editor', '编辑者'),
        ('viewer', '查看者'),
        ('operator', '操作者'),
    ]
    
    workflow_id = models.UUIDField(verbose_name='工作流ID')
    user_id = models.IntegerField(verbose_name='用户ID')
    role = models.CharField(max_length=20, choices=ROLES, verbose_name='角色')
    granted_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name='授权人'
    )
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '工作流权限'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_permission'
        unique_together = ['workflow_id', 'user_id']
    
    def __str__(self):
        return f"工作流 {self.workflow_id} - 用户 {self.user_id} - {self.get_role_display()}"


class AIWorkflowAuditLog(models.Model):
    """AI工作流审计日志"""
    
    OPERATION_TYPES = [
        ('create', '创建'),
        ('update', '更新'),
        ('delete', '删除'),
        ('execute', '执行'),
        ('debug', '调试'),
        ('share', '分享'),
        ('export', '导出'),
        ('permission_change', '权限变更'),
        ('api_key_operation', 'API密钥操作'),
        ('login', '登录'),
        ('other', '其他'),
    ]
    
    RESOURCE_TYPES = [
        ('workflow', '工作流'),
        ('model_config', '模型配置'),
        ('knowledge_base', '知识库'),
        ('api_key', 'API密钥'),
        ('user', '用户'),
        ('system', '系统'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name='操作用户'
    )
    operation_type = models.CharField(max_length=50, choices=OPERATION_TYPES, verbose_name='操作类型')
    resource_type = models.CharField(max_length=50, choices=RESOURCE_TYPES, verbose_name='资源类型')
    resource_id = models.CharField(max_length=100, verbose_name='资源ID')
    details = models.JSONField(default=dict, verbose_name='详细信息')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = 'AI工作流审计日志'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_audit_log'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_operation_type_display()} - {self.resource_type} - {self.created_at}"


class WorkflowTemplate(models.Model):
    """工作流模板"""
    
    CATEGORIES = [
        ('customer_service', '客服场景'),
        ('document_processing', '文档处理'),
        ('data_analysis', '数据分析'),
        ('content_generation', '内容生成'),
        ('automation', '自动化流程'),
        ('other', '其他'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='模板名称')
    description = models.TextField(blank=True, verbose_name='模板描述')
    category = models.CharField(max_length=30, choices=CATEGORIES, verbose_name='分类')
    workflow_data = models.JSONField(verbose_name='工作流数据')
    thumbnail = models.URLField(blank=True, verbose_name='缩略图URL')
    is_public = models.BooleanField(default=False, verbose_name='是否公开')
    is_featured = models.BooleanField(default=False, verbose_name='是否推荐')
    usage_count = models.IntegerField(default=0, verbose_name='使用次数')
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '工作流模板'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_template'
    
    def __str__(self):
        return self.name


class WorkflowSchedule(models.Model):
    """工作流定时调度"""
    
    FREQUENCIES = [
        ('interval', '间隔执行'),
        ('cron', 'Cron表达式'),
        ('once', '单次执行'),
    ]
    
    STATUSES = [
        ('active', '活跃'),
        ('paused', '暂停'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    
    workflow = models.ForeignKey(
        AIWorkflow, 
        on_delete=models.CASCADE, 
        related_name='schedules',
        verbose_name='关联工作流'
    )
    name = models.CharField(max_length=100, verbose_name='调度名称')
    frequency_type = models.CharField(max_length=20, choices=FREQUENCIES, verbose_name='频率类型')
    cron_expression = models.CharField(max_length=100, blank=True, verbose_name='Cron表达式')
    interval_seconds = models.IntegerField(null=True, blank=True, verbose_name='间隔秒数')
    input_data = models.JSONField(default=dict, blank=True, verbose_name='输入数据')
    status = models.CharField(max_length=20, choices=STATUSES, default='active', verbose_name='状态')
    last_run_at = models.DateTimeField(null=True, blank=True, verbose_name='上次执行时间')
    next_run_at = models.DateTimeField(null=True, blank=True, verbose_name='下次执行时间')
    max_concurrent = models.IntegerField(default=1, verbose_name='最大并发数')
    timeout_seconds = models.IntegerField(default=300, verbose_name='超时时间')
    error_notification = models.BooleanField(default=True, verbose_name='错误通知')
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '工作流定时调度'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_schedule'
    
    def __str__(self):
        return f"{self.workflow.name} - {self.name}"


class WorkflowVersion(models.Model):
    """工作流版本管理"""
    
    workflow = models.ForeignKey(
        AIWorkflow, 
        on_delete=models.CASCADE, 
        related_name='versions',
        verbose_name='关联工作流'
    )
    version_number = models.CharField(max_length=20, verbose_name='版本号')
    workflow_data = models.JSONField(verbose_name='工作流数据')
    nodes = models.JSONField(verbose_name='节点数据')
    connections = models.JSONField(verbose_name='连接数据')
    change_summary = models.TextField(blank=True, verbose_name='变更摘要')
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '工作流版本'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_version'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.workflow.name} - v{self.version_number}"


class WorkflowWebhook(models.Model):
    """工作流Web钩子"""
    
    TRIGGER_TYPES = [
        ('workflow_started', '工作流开始'),
        ('workflow_completed', '工作流完成'),
        ('workflow_failed', '工作流失败'),
        ('node_completed', '节点完成'),
        ('condition_met', '条件满足'),
    ]
    
    STATUSES = [
        ('active', '活跃'),
        ('inactive', '不活跃'),
    ]
    
    workflow = models.ForeignKey(
        AIWorkflow, 
        on_delete=models.CASCADE, 
        related_name='webhooks',
        verbose_name='关联工作流'
    )
    name = models.CharField(max_length=100, verbose_name='名称')
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPES, verbose_name='触发类型')
    webhook_url = models.URLField(max_length=500, verbose_name='Webhook URL')
    secret_key = models.CharField(max_length=100, blank=True, verbose_name='密钥')
    headers = models.JSONField(default=dict, blank=True, verbose_name='请求头')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    status = models.CharField(max_length=20, choices=STATUSES, default='active', verbose_name='状态')
    last_triggered_at = models.DateTimeField(null=True, blank=True, verbose_name='上次触发时间')
    failure_count = models.IntegerField(default=0, verbose_name='失败次数')
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '工作流Webhook'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_webhook'
    
    def __str__(self):
        return f"{self.workflow.name} - {self.name}"
