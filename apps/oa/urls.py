from django.urls import path
from . import views, ai_views

urlpatterns = [
    path(
        'meeting/datalist/',
        views.MeetingView.as_view(),
        name='meeting_datalist'),
    path(
        'meeting/list/',
        views.MeetingListView.as_view(),
        name='meeting_record_list'),
    path(
        'meeting/view/<int:pk>/',
        views.MeetingView.as_view(),
        name='meeting_view'),
    path(
        'meeting/delete/',
        views.MeetingView.as_view(),
        name='meeting_delete'),
    path(
        'meeting/apply/',
        views.MeetingApplyView.as_view(),
        name='meeting_apply'),
    path(
        'meeting/get_info/<int:pk>/',
        views.MeetingView.as_view(),
        name='meeting_get_info'),
    path(
        'meeting/update_summary/',
        views.MeetingView.as_view(),
        name='meeting_update_summary'),
    path(
        'meeting/minutes/',
        views.MeetingMinutesView.as_view(),
        name='meeting_minutes'),
    path('meeting/rooms/', views.get_meeting_rooms, name='meeting_rooms'),

    path('schedule/', views.ScheduleView.as_view(), name='oa_schedule'),
    path(
        'schedule/add/',
        views.ScheduleAddView.as_view(),
        name='oa_schedule_add'),
    path(
        'schedule/calendar/',
        views.ScheduleView.as_view(),
        name='oa_schedule_calendar'),
    path(
        'schedule/view/<int:id>/',
        views.ScheduleView.as_view(),
        name='oa_schedule_view'),
    path(
        'schedule/delete/<int:id>/',
        views.ScheduleView.as_view(),
        name='oa_schedule_delete'),
    path('message/list/', views.MessageView.datalist, name='message_list'),
    path(
        'message/view/<int:id>/',
        views.MessageDetailView.as_view(),
        name='message_view'),
    path('approval/list/', views.ApprovalView.datalist, name='approval_list'),
    path(
        'approval/submit/<int:id>/',
        views.ApprovalView.approve,
        name='approval_submit'),

    path(
        'ai/meeting-summary/<int:meeting_id>/',
        ai_views.ai_meeting_summary,
        name='ai_meeting_summary'),
    path(
        'ai/meeting-action-items/<int:meeting_id>/',
        ai_views.ai_meeting_action_items,
        name='ai_meeting_action_items'),

    path('upload/audio/', views.upload_audio, name='upload_audio'),
    path('meeting/save-audio/', views.save_audio, name='save_audio'),
    path(
        'meeting/create-temp/',
        views.create_temp_meeting,
        name='create_temp_meeting'),

    path('user/all/', views.get_all_users, name='all_users'),
]
