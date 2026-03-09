from django.urls import path, include
from . import views, ai_views

app_name = 'project'

urlpatterns = [
    # API路由
    path('api/', include('apps.project.api_urls')),
    # 项目管理路由
    path('', views.ProjectListView.as_view(), name='project_list'),
    path('datalist/', views.ProjectListView.as_view(), name='project_datalist'),
    path('detail/<int:project_id>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('add/', views.ProjectAddView.as_view(), name='project_add'),
    path('edit/<int:project_id>/', views.ProjectEditView.as_view(), name='project_edit'),
    path('delete/<int:project_id>/', views.ProjectDeleteView.as_view(), name='project_delete'),
    
    # 项目分类管理路由
    path('category/', views.ProjectCategoryListView.as_view(), name='project_category_list'),
    path('category/datalist/', views.ProjectCategoryListView.as_view(), name='project_category_datalist'),
    path('category/add/', views.ProjectCategoryAddView.as_view(), name='project_category_add'),
    path('category/edit/<int:category_id>/', views.ProjectCategoryEditView.as_view(), name='project_category_edit'),
    path('category/delete/<int:category_id>/', views.ProjectCategoryDeleteView.as_view(), name='project_category_delete'),
    
    # 项目阶段管理路由
    path('stage/', views.project_stage_list, name='project_stage_list'),
    path('stage/add/', views.project_stage_form, name='project_stage_add'),
    path('stage/edit/<int:pk>/', views.project_stage_form, name='project_stage_edit'),
    
    # 工作类型管理路由
    path('worktype/', views.work_type_list, name='work_type_list'),
    path('worktype/add/', views.work_type_form, name='work_type_add'),
    path('worktype/edit/<int:pk>/', views.work_type_form, name='work_type_edit'),
    
    # 项目文档路由
    path('document/', views.ProjectDocumentListView.as_view(), name='project_document'),
    path('document/datalist/', views.ProjectDocumentListView.as_view(), name='project_document_datalist'),
    path('document/add/', views.ProjectDocumentAddView.as_view(), name='project_document_add'),
    path('document/edit/<int:doc_id>/', views.ProjectDocumentEditView.as_view(), name='project_document_edit'),
    path('document/delete/<int:doc_id>/', views.ProjectDocumentDeleteView.as_view(), name='project_document_delete'),
    path('document/detail/<int:doc_id>/', views.ProjectDocumentDetailView.as_view(), name='project_document_detail'),
    path('document/upload/', views.ProjectDocumentUploadView.as_view(), name='project_document_upload'),
    
    # adm前缀的项目文档路由（解决前端POST重定向问题）
    path('adm/project/document/', views.ProjectDocumentListView.as_view(), name='adm_project_document'),
    path('adm/project/document/datalist/', views.ProjectDocumentListView.as_view(), name='adm_project_document_datalist'),
    path('adm/project/document/add/', views.ProjectDocumentAddView.as_view(), name='adm_project_document_add'),
    path('adm/project/document/edit/<int:doc_id>/', views.ProjectDocumentEditView.as_view(), name='adm_project_document_edit'),
    path('adm/project/document/delete/<int:doc_id>/', views.ProjectDocumentDeleteView.as_view(), name='adm_project_document_delete'),
    path('adm/project/document/detail/<int:doc_id>/', views.ProjectDocumentDetailView.as_view(), name='adm_project_document_detail'),
    path('adm/project/document/upload/', views.ProjectDocumentUploadView.as_view(), name='adm_project_document_upload'),
    
    # AI分析功能 - 页面视图
    path('ai/progress-analysis/<int:project_id>/', ai_views.AIProgressAnalysisView.as_view(), name='ai_progress_analysis_page'),
    path('ai/risk-prediction/<int:project_id>/', ai_views.AIRiskPredictionView.as_view(), name='ai_risk_prediction_page'),
    
    # AI分析功能 - API接口
    path('api/ai/progress-analysis/<int:project_id>/', ai_views.ai_project_progress_analysis, name='ai_progress_analysis_api'),
    path('api/ai/risk-prediction/<int:project_id>/', ai_views.ai_project_risk_prediction, name='ai_risk_prediction_api'),
]