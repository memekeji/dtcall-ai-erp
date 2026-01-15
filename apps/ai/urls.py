from django.urls import path
from django.shortcuts import redirect
from . import views
from .enhanced_views import (
    WorkflowEnhancedExecuteView,
    WorkflowDebugView,
    WorkflowMonitorView,
    WorkflowPermissionView,
    APIKeyManagementView,
    APIKeyRevokeView,
    ContentSecurityView,
    AuditLogView,
    ModelListView,
    PerformanceAnalysisView,
    WorkflowExecutionHistoryView
)

app_name = 'ai'

urlpatterns = [
    # AI模型配置
    path('model-config/list/', views.AIModelConfigListView.as_view(), name='model_config_list'),
    path('model-config/create/', views.AIModelConfigCreateView.as_view(), name='model_config_create'),
    path('model-config/create/', views.AIModelConfigCreateView.as_view(), name='ai_model_config_create'),
    path('model-config/update/<int:pk>/', views.AIModelConfigUpdateView.as_view(), name='model_config_update'),
    path('model-config/delete/<int:pk>/', views.AIModelConfigDeleteView.as_view(), name='ai_model_config_delete'),
    path('model-config/validate/<int:pk>/', views.AIModelConfigValidateView.as_view(), name='model_config_validate'),
    # 兼容旧的URL格式，重定向到新格式
    path('config/models/<int:pk>/validate/', lambda request, pk: redirect('ai:model_config_validate', pk=pk), name='model_config_validate_old'),
    path('model-config/detail/<int:pk>/', views.AIModelConfigDetailView.as_view(), name='ai_model_config_detail'),
    path('model-config/providers/', views.ListAvailableAIProvidersView.as_view(), name='list_available_providers'),
    
    # AI工作流
    path('workflow/list/', views.AIWorkflowListView.as_view(), name='workflow_list'),
    path('workflow/create/', views.AIWorkflowCreateView.as_view(), name='workflow_create'),
    path('workflow/update/<uuid:pk>/', views.AIWorkflowUpdateView.as_view(), name='workflow_update'),
    path('workflow/delete/<uuid:pk>/', views.AIWorkflowDeleteView.as_view(), name='workflow_delete'),
    path('workflow/detail/<uuid:pk>/', views.AIWorkflowDetailView.as_view(), name='workflow_detail'),
    path('workflow/designer/<uuid:pk>/', views.AIWorkflowDesignerView.as_view(), name='workflow_designer'),
    path('workflow/designer/v2/<uuid:pk>/', views.AIWorkflowDesignerV2View.as_view(), name='workflow_designer_v2'),
    path('workflow/execute/<uuid:pk>/', views.AIWorkflowExecuteView.as_view(), name='workflow_execute'),
    path('workflow/<uuid:pk>/run/', views.AIWorkflowExecuteView.as_view(), name='workflow_run'),
    path('workflow/<uuid:pk>/parameters/', views.AIWorkflowParametersView.as_view(), name='workflow_parameters'),
    path('workflow/<uuid:pk>/publish/', views.AIWorkflowPublishView.as_view(), name='workflow_publish'),
    
    # 增强工作流API
    path('workflow/<uuid:pk>/enhanced-execute/', WorkflowEnhancedExecuteView.as_view(), name='workflow_enhanced_execute'),
    path('workflow/<uuid:pk>/debug/', WorkflowDebugView.as_view(), name='workflow_debug'),
    path('workflow/<uuid:pk>/monitor/', WorkflowMonitorView.as_view(), name='workflow_monitor'),
    path('workflow/<uuid:pk>/permissions/', WorkflowPermissionView.as_view(), name='workflow_permissions'),
    path('workflow/<uuid:pk>/performance/', PerformanceAnalysisView.as_view(), name='workflow_performance'),
    path('workflow/<uuid:pk>/execution-history/', WorkflowExecutionHistoryView.as_view(), name='workflow_execution_history'),
    
    # API密钥管理
    path('api-keys/', APIKeyManagementView.as_view(), name='api_keys'),
    path('api-keys/<str:key_id>/revoke/', APIKeyRevokeView.as_view(), name='api_key_revoke'),
    
    # 内容安全
    path('content-security/', ContentSecurityView.as_view(), name='content_security'),
    
    # 审计日志
    path('audit-logs/', AuditLogView.as_view(), name='audit_logs'),
    
    # 模型管理
    path('models/list/', ModelListView.as_view(), name='model_list'),
    
    # AI聊天
    path('chat/', views.AIChatView.as_view(), name='chat'),
    path('chat/<int:pk>/', views.AIChatDetailView.as_view(), name='chat_detail'),
    path('chat/<int:pk>/delete/', views.AIChatDeleteView.as_view(), name='chat_delete'),
    path('chat/create/', views.AIChatCreateView.as_view(), name='chat_create'),
    path('chat/message/create/', views.AIChatMessageCreateView.as_view(), name='chat_message_create'),
    
    # AI知识库
    path('knowledge-base/list/', views.AIKnowledgeBaseListView.as_view(), name='knowledge_base_list'),
    path('knowledge-base/create/', views.AIKnowledgeBaseCreateView.as_view(), name='knowledge_base_create'),
    path('knowledge-base/update/<int:pk>/', views.AIKnowledgeBaseUpdateView.as_view(), name='knowledge_base_update'),
    path('knowledge-base/delete/<int:pk>/', views.AIKnowledgeBaseDeleteView.as_view(), name='knowledge_base_delete'),
    path('knowledge-base/detail/<int:pk>/', views.AIKnowledgeBaseDetailView.as_view(), name='knowledge_base_detail'),
    
    # AI知识条目
    path('knowledge-item/list/', views.AIKnowledgeItemListView.as_view(), name='knowledge_item_list'),
    path('knowledge-item/create/', views.AIKnowledgeItemCreateView.as_view(), name='knowledge_item_create'),
    path('knowledge-item/update/<int:pk>/', views.AIKnowledgeItemUpdateView.as_view(), name='knowledge_item_update'),
    path('knowledge-item/delete/<int:pk>/', views.AIKnowledgeItemDeleteView.as_view(), name='knowledge_item_delete'),
    path('knowledge-item/detail/<int:pk>/', views.AIKnowledgeItemDetailView.as_view(), name='knowledge_item_detail'),
    path('knowledge-item/search/', views.AIKnowledgeSearchView.as_view(), name='knowledge_search'),
    
    # AI销售策略
    path('sales-strategy/list/', views.AISalesStrategyListView.as_view(), name='sales_strategy_list'),
    path('sales-strategy/create/', views.AISalesStrategyCreateView.as_view(), name='sales_strategy_create'),
    path('sales-strategy/update/<int:pk>/', views.AISalesStrategyUpdateView.as_view(), name='sales_strategy_update'),
    path('sales-strategy/delete/<int:pk>/', views.AISalesStrategyDeleteView.as_view(), name='sales_strategy_delete'),
    
    # AI意图识别
    path('intent-recognition/list/', views.AIIntentRecognitionListView.as_view(), name='intent_recognition_list'),
    path('intent-recognition/create/', views.AIIntentRecognitionCreateView.as_view(), name='intent_recognition_create'),
    path('intent-recognition/update/<int:pk>/', views.AIIntentRecognitionUpdateView.as_view(), name='intent_recognition_update'),
    path('intent-recognition/delete/<int:pk>/', views.AIIntentRecognitionDeleteView.as_view(), name='intent_recognition_delete'),
    
    # AI情绪分析
    path('emotion-analysis/list/', views.AIEmotionAnalysisListView.as_view(), name='emotion_analysis_list'),
    path('emotion-analysis/create/', views.AIEmotionAnalysisCreateView.as_view(), name='emotion_analysis_create'),
    path('emotion-analysis/update/<int:pk>/', views.AIEmotionAnalysisUpdateView.as_view(), name='emotion_analysis_update'),
    path('emotion-analysis/delete/<int:pk>/', views.AIEmotionAnalysisDeleteView.as_view(), name='emotion_analysis_delete'),
    
    # AI合规规则
    path('compliance-rule/list/', views.AIComplianceRuleListView.as_view(), name='compliance_rule_list'),
    path('compliance-rule/create/', views.AIComplianceRuleCreateView.as_view(), name='compliance_rule_create'),
    path('compliance-rule/update/<int:pk>/', views.AIComplianceRuleUpdateView.as_view(), name='compliance_rule_update'),
    path('compliance-rule/delete/<int:pk>/', views.AIComplianceRuleDeleteView.as_view(), name='compliance_rule_delete'),
    
    # AI自动行动触发
    path('action-trigger/list/', views.AIActionTriggerListView.as_view(), name='action_trigger_list'),
    path('action-trigger/create/', views.AIActionTriggerCreateView.as_view(), name='action_trigger_create'),
    path('action-trigger/update/<int:pk>/', views.AIActionTriggerUpdateView.as_view(), name='action_trigger_update'),
    path('action-trigger/delete/<int:pk>/', views.AIActionTriggerDeleteView.as_view(), name='action_trigger_delete'),
    
    # AI操作日志
    path('log/list/', views.AILogListView.as_view(), name='log_list'),
    
    # AI任务管理
    path('tasks/', views.AIWorkflowExecutionListView.as_view(), name='ai_task_list'),
    path('tasks/<uuid:pk>/', views.AIWorkflowExecutionDetailView.as_view(), name='ai_task_detail'),
    
    # 文件解析
    path('parse-file-content/', views.ParseFileContentView.as_view(), name='parse_file_content'),
    # AI聊天流
    path('chat/stream/', views.AIChatStreamView.as_view(), name='chat_stream'),
]