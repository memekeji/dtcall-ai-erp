from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import ai_views

app_name = 'message'

router = DefaultRouter()
router.register(
    r'categories',
    views.MessageCategoryViewSet,
    basename='message-category')
router.register(r'messages', views.MessageViewSet, basename='message')
router.register(
    r'preferences',
    views.NotificationPreferenceViewSet,
    basename='notification-preference')
router.register(
    r'conversations',
    views.ConversationViewSet,
    basename='conversation')

urlpatterns = [
    path(
        'stats/',
        views.MessageStatsView.as_view(),
        name='message-stats'),
    path(
        'mark-read/',
        views.MessageMarkReadView.as_view(),
        name='message-mark-read'),
    path(
        'unread-count/',
        views.UnreadCountView.as_view(),
        name='unread-count'),
    path(
        'contacts/',
        views.ConversationContactView.as_view(),
        name='conversation-contacts'),
    path(
        'conversations/page/',
        views.conversation_center_page,
        name='conversation-center-page'),
    path(
        'page/',
        views.message_center_page,
        name='message-center-page'),
    path(
        'preference/',
        views.message_preference_page,
        name='message-preference-page'),
    path(
        'stats/page/',
        views.message_stats_page,
        name='message-stats-page'),
        
    # AI 功能
    path('ai/analyze/<int:message_id>/', ai_views.MessageAIAssistantView.as_view(), name='ai_analyze'),
    
    # 协作信息API (延迟导入避免循环依赖)
    path('collaboration/', views.user_collaboration_view, name='user-collaboration'),
    
    # 协同分享API
    path('share/content/', views.shareable_content_view, name='shareable-content'),
    
    # 卡片操作API
    path('card/action/', views.card_action_view, name='card-action'),
    
    path(
        'conversations/<int:conversation_id>/messages/<int:message_id>/recall/',
        views.MessageRecallView.as_view(),
        name='message-recall'),
    path(
        '',
        include(
            router.urls)),
]
