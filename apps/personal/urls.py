from django.urls import path
from . import views

app_name = 'personal'

urlpatterns = [
    # 个人办公首页
    path('', views.dashboard, name='dashboard'),

    # 日程安排
    path('schedule/', views.schedule_list, name='schedule_list'),
    path('schedule/add/', views.schedule_form, name='schedule_add'),
    path('schedule/<int:pk>/edit/', views.schedule_form, name='schedule_edit'),
    path(
        'schedule/<int:pk>/delete/',
        views.schedule_delete,
        name='schedule_delete'),
    path('calendar/', views.schedule_calendar, name='schedule_calendar'),

    # 工作记录
    path('record/', views.work_record_list, name='work_record_list'),
    path('record/add/', views.work_record_form, name='work_record_add'),
    path(
        'record/<int:pk>/edit/',
        views.work_record_form,
        name='work_record_edit'),
    path(
        'record/<int:pk>/delete/',
        views.work_record_delete,
        name='work_record_delete'),
    path('workcalendar/', views.work_calendar, name='work_calendar'),

    # 工作汇报
    path('report/', views.work_report_list, name='work_report_list'),
    path('report/add/', views.work_report_form, name='work_report_add'),
    path(
        'report/<int:pk>/edit/',
        views.work_report_form,
        name='work_report_edit'),
    path(
        'report/<int:pk>/delete/',
        views.work_report_delete,
        name='work_report_delete'),
    path(
        'report/<int:pk>/view/',
        views.work_report_detail,
        name='work_report_detail'),

    # 个人笔记
    path('note/', views.note_list, name='note_list'),
    path('note/add/', views.note_form, name='note_add'),
    path('note/<int:pk>/edit/', views.note_form, name='note_edit'),
    path('note/<int:pk>/delete/', views.note_delete, name='note_delete'),

    # 个人任务
    path('task/', views.task_list, name='task_list'),
    path('task/add/', views.task_form, name='task_add'),
    path('task/<int:pk>/edit/', views.task_form, name='task_edit'),
    path('task/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path(
        'task/<int:pk>/toggle/',
        views.task_toggle_status,
        name='task_toggle_status'),

    # 个人通讯录
    path('contact/', views.contact_list, name='contact_list'),
    path('contact/add/', views.contact_form, name='contact_add'),
    path('contact/<int:pk>/edit/', views.contact_form, name='contact_edit'),
    path(
        'contact/<int:pk>/delete/',
        views.contact_delete,
        name='contact_delete'),

    # 公告通知
    path('notice/', views.notice_list, name='notice_list'),

    # 公司新闻（只读）
    path('news/', views.news_list, name='news_list'),

    # 会议纪要
    path('minutes/', views.minutes_list, name='minutes_list'),
    path('minutes/add/', views.minutes_form, name='minutes_add'),
    path('minutes/<int:pk>/edit/', views.minutes_form, name='minutes_edit'),
    path(
        'minutes/<int:pk>/delete/',
        views.minutes_delete,
        name='minutes_delete'),
    path(
        'minutes/<int:pk>/view/',
        views.minutes_detail,
        name='minutes_detail'),
    path(
        'minutes/download/<int:pk>/',
        views.generate_minutes_word,
        name='minutes_download'),
    path(
        'minutes/preview/<int:pk>/',
        views.generate_minutes_preview,
        name='minutes_preview'),
]
