from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class AIModelConfig(models.Model):
    """AI模型配置"""
    PROVIDERS = [
        ('openai', 'OpenAI'),
        ('azure', 'Azure OpenAI'),
        ('anthropic', 'Anthropic'),
        ('google', 'Google Gemini'),
        ('baidu', '百度文心一言'),
        ('alibaba', '阿里通义千问'),
        ('tencent', '腾讯混元'),
        ('deepseek', 'DeepSeek'),
        ('doubao', '字节跳动豆包'),
        ('local', '本地模型'),
    ]
    
    MODEL_TYPES = [
        ('chat', '对话模型'),
        ('text', '文本生成'),
        ('embedding', '嵌入模型'),
        ('image', '图像模型'),
        ('audio', '音频模型'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='模型名称')
    provider = models.CharField(max_length=50, choices=PROVIDERS, verbose_name='提供商')
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES, verbose_name='模型类型')
    model_name = models.CharField(max_length=100, default='', verbose_name='模型标识')
    api_key = models.CharField(max_length=200, blank=True, null=True, verbose_name='API密钥')
    api_base = models.URLField(max_length=200, blank=True, null=True, verbose_name='API基础URL')
    organization = models.CharField(max_length=100, blank=True, null=True, verbose_name='组织ID')
    project = models.CharField(max_length=100, blank=True, null=True, verbose_name='项目ID')
    max_tokens = models.IntegerField(default=2048, verbose_name='最大tokens')
    temperature = models.FloatField(default=0.7, verbose_name='温度', help_text='0-2，值越高越随机')
    top_p = models.FloatField(default=1.0, verbose_name='top_p', help_text='0-1，核采样参数')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    is_default = models.BooleanField(default=False, verbose_name='是否默认')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI模型配置'
        verbose_name_plural = verbose_name
        db_table = 'ai_model_config'
        unique_together = ['provider', 'model_name', 'model_type']
    
    def __str__(self):
        return f"{self.provider} - {self.model_name} ({self.get_model_type_display()})"


import uuid

class AIWorkflow(models.Model):
    """AI工作流"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('published', '已发布'),
        ('archived', '已归档'),
    ]
    
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='ID')
    name = models.CharField(max_length=100, verbose_name='工作流名称')
    description = models.TextField(blank=True, null=True, verbose_name='工作流描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    is_public = models.BooleanField(default=False, verbose_name='是否公开')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_workflows', verbose_name='拥有者')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='created_workflows', verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI工作流'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow'
    
    def __str__(self):
        return self.name


class WorkflowNode(models.Model):
    """工作流节点 - 严格的预定义节点类型"""
    NODE_TYPES = [
        ('ai_model', 'AI模型'),
        ('ai_generation', 'AI生成'),
        ('ai_classification', 'AI分类'),
        ('ai_extraction', 'AI信息提取'),
        ('knowledge_retrieval', '知识检索'),
        ('intent_recognition', '意图识别'),
        ('sentiment_analysis', '情感分析'),
        ('data_input', '数据输入'),
        ('data_output', '数据输出'),
        ('condition', '条件判断'),
        ('switch', '多条件分支'),
        ('loop', '循环处理'),
        ('iterator', '迭代器'),
        ('parallel', '并行处理'),
        ('delay', '延迟'),
        ('wait', '等待'),
        ('webhook', 'Webhook'),
        ('api_call', 'API调用'),
        ('http_request', 'HTTP请求'),
        ('code_execution', '代码执行'),
        ('code_block', '代码块'),
        ('tool_call', '工具调用'),
        ('database_query', '数据库查询'),
        ('message_queue', '消息队列'),
        ('variable_aggregation', '变量聚合'),
        ('parameter_aggregator', '参数聚合'),
        ('variable_assign', '变量赋值'),
        ('data_transformation', '数据转换'),
        ('data_filter', '数据过滤'),
        ('data_aggregation', '数据聚合'),
        ('data_format', '数据格式化'),
        ('text_processing', '文本处理'),
        ('template', '模板渲染'),
        ('file_operation', '文件操作'),
        ('document_extractor', '文档提取'),
        ('image_processing', '图片处理'),
        ('audio_processing', '音频处理'),
        ('notification', '通知'),
        ('scheduled_task', '定时任务'),
        ('question_answer', '问答交互'),
        ('conversation_history', '对话历史'),
        ('workflow_trigger', '工作流触发'),
        ('start', '开始'),
        ('end', '结束'),
    ]
    
    # 有效的节点类型集合（用于快速验证）
    VALID_NODE_TYPES = set(dict(NODE_TYPES).keys())
    
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='ID')
    workflow = models.ForeignKey(AIWorkflow, on_delete=models.CASCADE, related_name='nodes', verbose_name='所属工作流')
    name = models.CharField(max_length=100, verbose_name='节点名称')
    node_type = models.CharField(max_length=50, choices=NODE_TYPES, verbose_name='节点类型')
    config = models.JSONField(verbose_name='节点配置')
    position_x = models.IntegerField(default=0, verbose_name='X坐标')
    position_y = models.IntegerField(default=0, verbose_name='Y坐标')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    
    class Meta:
        verbose_name = '工作流节点'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_node'
    
    def __str__(self):
        return f"{self.workflow.name} - {self.name}"


class WorkflowConnection(models.Model):
    """工作流连接"""
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='ID')
    workflow = models.ForeignKey(AIWorkflow, on_delete=models.CASCADE, related_name='connections', verbose_name='所属工作流')
    source_node = models.ForeignKey(WorkflowNode, on_delete=models.CASCADE, related_name='output_connections', verbose_name='源节点')
    target_node = models.ForeignKey(WorkflowNode, on_delete=models.CASCADE, related_name='input_connections', verbose_name='目标节点')
    source_handle = models.CharField(max_length=50, blank=True, null=True, verbose_name='源节点端口')
    target_handle = models.CharField(max_length=50, blank=True, null=True, verbose_name='目标节点端口')
    config = models.JSONField(blank=True, null=True, verbose_name='连接配置')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '工作流连接'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_connection'
    
    def __str__(self):
        return f"{self.source_node.name} → {self.target_node.name}"


class AIWorkflowExecution(models.Model):
    """工作流执行记录"""
    STATUS_CHOICES = [
        ('pending', '待执行'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('failed', '执行失败'),
        ('cancelled', '已取消'),
    ]
    
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='ID')
    workflow = models.ForeignKey(AIWorkflow, on_delete=models.CASCADE, verbose_name='工作流')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='执行状态')
    input_data = models.JSONField(blank=True, null=True, verbose_name='输入数据')
    output_data = models.JSONField(blank=True, null=True, verbose_name='输出数据')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='执行人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    started_at = models.DateTimeField(auto_now=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name='完成时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '工作流执行记录'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_execution'
    
    def __str__(self):
        return f"{self.workflow.name} - {self.get_status_display()}"


class AIChat(models.Model):
    """AI聊天记录"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    session_id = models.CharField(max_length=100, verbose_name='会话ID')
    title = models.CharField(max_length=200, blank=True, verbose_name='会话标题')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI聊天记录'
        verbose_name_plural = verbose_name
        db_table = 'ai_chat'
    
    def __str__(self):
        return f"{self.user.name} - {self.title or self.session_id[:8]}"


class AIChatMessage(models.Model):
    """AI聊天消息"""
    ROLES = [
        ('user', '用户'),
        ('assistant', '助手'),
        ('system', '系统'),
    ]
    
    chat = models.ForeignKey(AIChat, on_delete=models.CASCADE, related_name='messages', verbose_name='聊天会话')
    role = models.CharField(max_length=20, choices=ROLES, verbose_name='角色')
    content = models.TextField(verbose_name='消息内容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = 'AI聊天消息'
        verbose_name_plural = verbose_name
        db_table = 'ai_chat_message'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}"


class AIKnowledgeBase(models.Model):
    """AI知识库"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('published', '已发布'),
        ('archived', '已归档'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='知识库名称')
    description = models.TextField(blank=True, verbose_name='知识库描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    creator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI知识库'
        verbose_name_plural = verbose_name
        db_table = 'ai_knowledge_base'
    
    def __str__(self):
        return self.name


class AIKnowledgeItem(models.Model):
    """AI知识库条目"""
    KNOWLEDGE_TYPES = [
        ('document', '文档'),
        ('faq', '常见问题'),
        ('product', '产品信息'),
        ('policy', '政策法规'),
        ('sales', '销售话术'),
        ('other', '其他'),
    ]
    
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('published', '已发布'),
        ('archived', '已归档'),
    ]
    
    knowledge_base = models.ForeignKey(AIKnowledgeBase, on_delete=models.CASCADE, related_name='items', verbose_name='所属知识库')
    title = models.CharField(max_length=200, verbose_name='标题')
    content = models.TextField(verbose_name='内容')
    file = models.FileField(upload_to='knowledge_files/', blank=True, null=True, verbose_name='附件', help_text='支持上传PDF、Word、Excel、PPT、TXT等文件')
    file_type = models.CharField(max_length=50, blank=True, verbose_name='文件类型')
    file_size = models.IntegerField(blank=True, null=True, verbose_name='文件大小(字节)')
    knowledge_type = models.CharField(max_length=20, choices=KNOWLEDGE_TYPES, default='other', verbose_name='知识类型')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    creator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建人')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    tags = models.JSONField(blank=True, null=True, verbose_name='标签')
    metadata = models.JSONField(blank=True, null=True, verbose_name='元数据')
    
    class Meta:
        verbose_name = 'AI知识库条目'
        verbose_name_plural = verbose_name
        db_table = 'ai_knowledge_item'
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # 自动设置文件类型和大小
        if self.file:
            self.file_type = self.file.name.split('.')[-1].lower() if '.' in self.file.name else ''
            self.file_size = self.file.size
        
        # 保存知识条目
        super().save(*args, **kwargs)
        
        # 异步生成或更新向量
        from apps.ai.services.vector_generation_service import vector_generation_service
        vector_generation_service.generate_vector_for_knowledge_item(self.id)


class AIKnowledgeVector(models.Model):
    """AI知识库向量存储"""
    knowledge_item = models.OneToOneField(AIKnowledgeItem, on_delete=models.CASCADE, related_name='vector', verbose_name='关联知识条目')
    vector = models.BinaryField(verbose_name='向量数据')
    dimension = models.IntegerField(verbose_name='向量维度')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI知识库向量'
        verbose_name_plural = verbose_name
        db_table = 'ai_knowledge_vector'
    
    def __str__(self):
        return f"{self.knowledge_item.title} - 向量"


class AISalesStrategy(models.Model):
    """AI销售策略"""
    STRATEGY_TYPES = [
        ('spin', 'SPIN销售法'),
        ('fabe', 'FABE销售法'),
        ('solution', '解决方案销售'),
        ('challenger', '挑战者销售法'),
        ('other', '其他'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='策略名称')
    strategy_type = models.CharField(max_length=20, choices=STRATEGY_TYPES, verbose_name='策略类型')
    description = models.TextField(blank=True, verbose_name='策略描述')
    config = models.JSONField(verbose_name='策略配置')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI销售策略'
        verbose_name_plural = verbose_name
        db_table = 'ai_sales_strategy'
    
    def __str__(self):
        return f"{self.name} ({self.get_strategy_type_display()})"


class AIIntentRecognition(models.Model):
    """AI意图识别"""
    INTENT_TYPES = [
        ('inquiry', '询价'),
        ('comparison', '比价'),
        ('complaint', '投诉'),
        ('repurchase', '复购'),
        ('consultation', '咨询'),
        ('feedback', '反馈'),
        ('other', '其他'),
    ]
    
    intent_type = models.CharField(max_length=20, choices=INTENT_TYPES, verbose_name='意图类型')
    keywords = models.JSONField(verbose_name='关键词列表')
    examples = models.JSONField(verbose_name='示例句子')
    description = models.TextField(blank=True, verbose_name='意图描述')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI意图识别'
        verbose_name_plural = verbose_name
        db_table = 'ai_intent_recognition'
    
    def __str__(self):
        return self.get_intent_type_display()


class AIEmotionAnalysis(models.Model):
    """AI情绪分析"""
    EMOTION_TYPES = [
        ('positive', '积极'),
        ('neutral', '中性'),
        ('negative', '消极'),
        ('hesitant', '犹豫'),
        ('angry', '愤怒'),
        ('happy', '开心'),
        ('sad', '悲伤'),
        ('surprised', '惊讶'),
    ]
    
    emotion_type = models.CharField(max_length=20, choices=EMOTION_TYPES, verbose_name='情绪类型')
    keywords = models.JSONField(verbose_name='关键词列表')
    description = models.TextField(blank=True, verbose_name='情绪描述')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI情绪分析'
        verbose_name_plural = verbose_name
        db_table = 'ai_emotion_analysis'
    
    def __str__(self):
        return self.get_emotion_type_display()


class AIComplianceRule(models.Model):
    """AI合规规则"""
    RULE_TYPES = [
        ('sensitive_word', '敏感词'),
        ('forbidden_content', '禁止内容'),
        ('warning_content', '警告内容'),
        ('required_content', '必填内容'),
    ]
    
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES, verbose_name='规则类型')
    content = models.TextField(verbose_name='规则内容')
    description = models.TextField(blank=True, verbose_name='规则描述')
    severity = models.IntegerField(default=1, verbose_name='严重程度', help_text='1-5，5最严重')
    action = models.CharField(max_length=50, default='block', verbose_name='处理动作', help_text='block: 阻止, warn: 警告, log: 记录')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI合规规则'
        verbose_name_plural = verbose_name
        db_table = 'ai_compliance_rule'
    
    def __str__(self):
        return f"{self.get_rule_type_display()} - {self.content[:50]}"


class AIActionTrigger(models.Model):
    """AI自动行动触发"""
    ACTION_TYPES = [
        ('send_message', '发送消息'),
        ('create_task', '创建任务'),
        ('send_email', '发送邮件'),
        ('send_sms', '发送短信'),
        ('add_contact', '添加联系人'),
        ('share_document', '分享文档'),
        ('other', '其他'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='触发名称')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, verbose_name='行动类型')
    conditions = models.JSONField(verbose_name='触发条件')
    config = models.JSONField(verbose_name='行动配置')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI自动行动触发'
        verbose_name_plural = verbose_name
        db_table = 'ai_action_trigger'
    
    def __str__(self):
        return f"{self.name} ({self.get_action_type_display()})"


class AILog(models.Model):
    """AI操作日志"""
    LOG_TYPES = [
        ('model_call', '模型调用'),
        ('knowledge_access', '知识库访问'),
        ('workflow_execution', '工作流执行'),
        ('chat_interaction', '聊天交互'),
        ('compliance_check', '合规检查'),
        ('intent_recognition', '意图识别'),
        ('emotion_analysis', '情绪分析'),
        ('action_trigger', '行动触发'),
    ]
    
    log_type = models.CharField(max_length=20, choices=LOG_TYPES, verbose_name='日志类型')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='操作用户')
    content = models.JSONField(verbose_name='日志内容')
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name='IP地址')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = 'AI操作日志'
        verbose_name_plural = verbose_name
        db_table = 'ai_log'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_log_type_display()} - {self.created_at}"


class AIFeedback(models.Model):
    """AI效果反馈"""
    RATING_CHOICES = [
        (1, '非常不满意'),
        (2, '不满意'),
        (3, '一般'),
        (4, '满意'),
        (5, '非常满意'),
    ]
    
    TASK_TYPES = [
        ('chat_completion', '聊天完成'),
        ('text_generation', '文本生成'),
        ('knowledge_retrieval', '知识检索'),
        ('customer_analysis', '客户分析'),
        ('meeting_minutes', '会议纪要'),
        ('project_risk', '项目风险评估'),
        ('expense_audit', '报销单审核'),
        ('document_summary', '文档摘要'),
        ('other', '其他'),
    ]
    
    task_id = models.CharField(max_length=100, verbose_name='任务ID')
    task_type = models.CharField(max_length=30, choices=TASK_TYPES, default='other', verbose_name='任务类型')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='反馈用户')
    rating = models.IntegerField(choices=RATING_CHOICES, verbose_name='评分')
    comment = models.TextField(blank=True, verbose_name='反馈内容')
    ai_output = models.TextField(verbose_name='AI输出内容')
    input_content = models.TextField(verbose_name='输入内容')
    model_config_id = models.ForeignKey(AIModelConfig, on_delete=models.SET_NULL, null=True, verbose_name='使用的模型配置')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI效果反馈'
        verbose_name_plural = verbose_name
        db_table = 'ai_feedback'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_task_type_display()} - {self.rating}分"


class AIBatchTest(models.Model):
    """AI A/B测试"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('running', '运行中'),
        ('completed', '已完成'),
        ('paused', '已暂停'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='测试名称')
    description = models.TextField(blank=True, verbose_name='测试描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='测试状态')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建人')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    traffic_allocation = models.JSONField(verbose_name='流量分配', help_text='如：{"variant_a": 50, "variant_b": 50}')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI A/B测试'
        verbose_name_plural = verbose_name
        db_table = 'ai_ab_test'
    
    def __str__(self):
        return self.name


class AIBatchTestVariant(models.Model):
    """AI A/B测试变体"""
    ab_test = models.ForeignKey(AIBatchTest, on_delete=models.CASCADE, related_name='variants', verbose_name='所属测试')
    name = models.CharField(max_length=50, verbose_name='变体名称', help_text='如：variant_a, variant_b')
    description = models.TextField(blank=True, verbose_name='变体描述')
    model_config = models.ForeignKey(AIModelConfig, on_delete=models.SET_NULL, null=True, verbose_name='使用的模型配置')
    config_params = models.JSONField(verbose_name='配置参数', help_text='额外的配置参数')
    is_control = models.BooleanField(default=False, verbose_name='是否为对照组')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI A/B测试变体'
        verbose_name_plural = verbose_name
        db_table = 'ai_ab_test_variant'
        unique_together = ['ab_test', 'name']
    
    def __str__(self):
        return f"{self.ab_test.name} - {self.name}"


class AIBatchTestResult(models.Model):
    """AI A/B测试结果"""
    ab_test = models.ForeignKey(AIBatchTest, on_delete=models.CASCADE, related_name='results', verbose_name='所属测试')
    variant = models.ForeignKey(AIBatchTestVariant, on_delete=models.SET_NULL, null=True, verbose_name='变体')
    test_count = models.IntegerField(default=0, verbose_name='测试次数')
    positive_feedback_count = models.IntegerField(default=0, verbose_name='正面反馈次数')
    negative_feedback_count = models.IntegerField(default=0, verbose_name='负面反馈次数')
    average_rating = models.FloatField(default=0, verbose_name='平均评分')
    conversion_rate = models.FloatField(default=0, verbose_name='转化率')
    cost_per_result = models.FloatField(default=0, verbose_name='每次结果成本')
    metrics = models.JSONField(verbose_name='其他指标', help_text='如：响应时间、准确率等')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'AI A/B测试结果'
        verbose_name_plural = verbose_name
        db_table = 'ai_ab_test_result'
    
    def __str__(self):
        return f"{self.ab_test.name} - {self.variant.name if self.variant else '整体'}结果"


class WorkflowVariable(models.Model):
    """工作流变量"""
    DATA_TYPES = [
        ('string', '字符串'),
        ('number', '数字'),
        ('boolean', '布尔值'),
        ('object', '对象'),
        ('array', '数组'),
    ]
    
    workflow = models.ForeignKey(AIWorkflow, on_delete=models.CASCADE, related_name='variables', verbose_name='所属工作流')
    name = models.CharField(max_length=100, verbose_name='变量名称')
    data_type = models.CharField(max_length=20, choices=DATA_TYPES, default='string', verbose_name='数据类型')
    default_value = models.JSONField(blank=True, null=True, verbose_name='默认值')
    description = models.TextField(blank=True, verbose_name='变量描述')
    is_required = models.BooleanField(default=False, verbose_name='是否必填')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '工作流变量'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_variable'
    
    def __str__(self):
        return f"{self.workflow.name} - {self.name}"


class WorkflowNodeType(models.Model):
    """工作流节点类型"""
    NODE_CATEGORIES = [
        ('basic', '基础节点'),
        ('ai', 'AI节点'),
        ('data', '数据节点'),
        ('logic', '逻辑节点'),
        ('integration', '集成节点'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name='类型代码')
    name = models.CharField(max_length=100, verbose_name='类型名称')
    description = models.TextField(blank=True, verbose_name='类型描述')
    category = models.CharField(max_length=20, choices=NODE_CATEGORIES, default='basic', verbose_name='分类')
    icon = models.CharField(max_length=50, blank=True, verbose_name='图标类名')
    config_schema = models.JSONField(verbose_name='配置模式', help_text='JSON格式的配置模式定义')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '工作流节点类型'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_node_type'
    
    def __str__(self):
        return self.name


class NodeExecution(models.Model):
    """节点执行记录"""
    STATUS_CHOICES = [
        ('pending', '待执行'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('failed', '执行失败'),
        ('skipped', '已跳过'),
    ]
    
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='ID')
    workflow_execution = models.ForeignKey(AIWorkflowExecution, on_delete=models.CASCADE, related_name='node_executions', verbose_name='所属执行')
    node = models.ForeignKey(WorkflowNode, on_delete=models.SET_NULL, null=True, verbose_name='节点')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='执行状态')
    input_data = models.JSONField(blank=True, null=True, verbose_name='输入数据')
    output_data = models.JSONField(blank=True, null=True, verbose_name='输出数据')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name='完成时间')
    execution_time = models.FloatField(default=0, verbose_name='执行时间(秒)')
    
    class Meta:
        verbose_name = '节点执行记录'
        verbose_name_plural = verbose_name
        db_table = 'ai_node_execution'
    
    def __str__(self):
        node_name = self.node.name if self.node else '未知节点'
        return f"{node_name} - {self.get_status_display()}"


class WorkflowDataAccessConfig(models.Model):
    """工作流数据访问配置"""
    ACCESS_TYPES = [
        ('database', '数据库'),
        ('api', 'API接口'),
        ('file', '文件'),
        ('memory', '内存数据'),
    ]
    
    OPERATIONS = [
        ('read', '读取'),
        ('write', '写入'),
        ('delete', '删除'),
    ]
    
    workflow = models.ForeignKey(AIWorkflow, on_delete=models.CASCADE, related_name='data_access_configs', verbose_name='所属工作流')
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPES, verbose_name='访问类型')
    resource_name = models.CharField(max_length=100, verbose_name='资源名称')
    resource_identifier = models.CharField(max_length=200, verbose_name='资源标识符')
    operations = models.JSONField(verbose_name='允许的操作', help_text='如：["read", "write"]')
    filters = models.JSONField(blank=True, null=True, verbose_name='过滤条件')
    description = models.TextField(blank=True, verbose_name='配置描述')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '工作流数据访问配置'
        verbose_name_plural = verbose_name
        db_table = 'ai_workflow_data_access'
    
    def __str__(self):
        return f"{self.workflow.name} - {self.resource_name}"


class AITask(models.Model):
    """AI任务记录"""
    TASK_TYPES = [
        ('customer_analysis', '客户智能分析'),
        ('meeting_minutes', '会议纪要生成'),
        ('project_risk', '项目风险评估'),
        ('expense_audit', '费用审计'),
        ('document_summary', '文档摘要'),
        ('workflow_execution', '工作流执行'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '待执行'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('failed', '执行失败'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    task_type = models.CharField(max_length=50, choices=TASK_TYPES, verbose_name='任务类型')
    task_params = models.JSONField(verbose_name='任务参数')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    result = models.JSONField(blank=True, null=True, verbose_name='执行结果')
    error_message = models.TextField(blank=True, null=True, verbose_name='错误信息')
    started_at = models.DateTimeField(blank=True, null=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name='完成时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = 'AI任务记录'
        verbose_name_plural = verbose_name
        db_table = 'ai_task'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user} - {self.get_task_type_display()} - {self.get_status_display()}"
