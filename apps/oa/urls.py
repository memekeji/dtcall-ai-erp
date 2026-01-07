from django.urls import path
from . import views, ai_views

urlpatterns = [
    # 会议相关
    path('meeting/datalist/', views.MeetingView.as_view(), name='meeting_list'),
    path('meeting/list/', views.MeetingListView.as_view(), name='meeting_record_list'),
    path('meeting/view/<int:pk>/', views.MeetingView.as_view(), name='meeting_view'),
    path('meeting/apply/', views.MeetingApplyView.as_view(), name='meeting_apply'),
    path('meeting/save/', views.MeetingApplyView.as_view(), name='meeting_save'),
    path('meeting/minutes/', views.MeetingMinutesView.as_view(), name='meeting_minutes'),
    path('meeting/get_info/<int:pk>/', views.MeetingView.as_view(), name='meeting_get_info'),
    path('meeting/update_summary/', views.MeetingView.as_view(), name='meeting_update_summary'),
    # 新增会议室列表API
    path('meeting/rooms/', views.get_meeting_rooms, name='meeting_rooms'),
    
    # 日程相关路由
    path('schedule/', views.ScheduleView.as_view(), name='oa_schedule'),
    path('schedule/add/', views.ScheduleAddView.as_view(), name='oa_schedule_add'),
    path('schedule/calendar/', views.ScheduleView.as_view(), name='oa_schedule_calendar'),
    path('schedule/view/<int:id>/', views.ScheduleView.as_view(), name='oa_schedule_view'),
    path('schedule/delete/<int:id>/', views.ScheduleView.as_view(), name='oa_schedule_delete'),
    # 消息相关路由
    path('message/list/', views.MessageView.datalist, name='message_list'),
    path('message/view/<int:id>/', views.MessageDetailView.as_view(), name='message_view'),
    # 审批相关路由
    path('approval/list/', views.ApprovalView.datalist, name='approval_list'),
    path('approval/submit/<int:id>/', views.ApprovalView.approve, name='approval_submit'),
    
    # AI相关接口
    path('ai/meeting-summary/<int:meeting_id>/', ai_views.ai_meeting_summary, name='ai_meeting_summary'),
    path('ai/meeting-action-items/<int:meeting_id>/', ai_views.ai_meeting_action_items, name='ai_meeting_action_items'),
    
    # 文件上传相关
    path('upload/audio/', views.upload_audio, name='upload_audio'),
    path('meeting/save-audio/', views.save_audio, name='save_audio'),
    path('meeting/create-temp/', views.create_temp_meeting, name='create_temp_meeting'),
    

    
    # 用户相关
    path('user/all/', views.get_all_users, name='all_users'),
]
