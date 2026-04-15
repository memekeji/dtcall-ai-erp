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

urlpatterns = [
    path(
        '',
        include(
            router.urls)),
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
]
