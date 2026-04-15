from django.urls import path
from . import views
from .ai_views import ai_approval_assessment


app_name = 'approval'

urlpatterns = [
    # AI 路由
    path('api/ai/assessment/<int:approval_id>/', ai_approval_assessment, name='ai_approval_assessment'),

    path(
        'approval_type/',
        views.approval_type_list,
        name='approval_type_list'),
    path(
        'approval_type/add/',
        views.approval_type_form,
        name='approval_type_add'),
    path(
        'approval_type/<int:pk>/edit/',
        views.approval_type_form,
        name='approval_type_edit'),

    path('approvalflow/', views.approval_flow_list, name='approval_flow_list'),
    path(
        'approvalflow/add/',
        views.approval_flow_form,
        name='approval_flow_add'),
    path(
        'approvalflow/<int:pk>/edit/',
        views.approval_flow_form,
        name='approval_flow_edit'),
    path(
        'approvalflow/<int:pk>/steps/',
        views.approval_flow_steps,
        name='approval_flow_steps'),
    path(
        'approvalflow/<int:flow_pk>/step/add/',
        views.approval_step_form,
        name='approval_step_add'),
    path('approvalflow/<int:flow_pk>/step/<int:pk>/edit/',
         views.approval_step_form, name='approval_step_edit'),
    path('approvalflow/<int:flow_pk>/step/<int:pk>/delete/',
         views.approval_step_delete, name='approval_step_delete'),
    path(
        'approvalflow/<int:pk>/preview/',
        views.approval_flow_preview,
        name='approval_flow_preview'),
    path('approvalflow/<int:pk>/batch-create-steps/',
         views.batch_create_steps, name='batch_create_steps'),
    path(
        'approvalflow/<int:pk>/initiator/',
        views.get_initiator_config,
        name='get_initiator_config'),
    path(
        'approvalflow/<int:pk>/update-initiator/',
        views.update_initiator_config,
        name='update_initiator_config'),
    path(
        'approvalflow/<int:pk>/start-config/',
        views.get_start_config,
        name='get_start_config'),
    path('approvalflow/<int:pk>/update-start-config/',
         views.update_start_config, name='update_start_config'),

    path('my/', views.my_approval_list, name='my_approval_list'),
    path('pending/', views.pending_list, name='pending_list'),
    path(
        'pending/api/',
        views.get_pending_approvals,
        name='get_pending_approvals'),
    path('<int:pk>/', views.approval_detail, name='approval_detail'),
    path('<int:pk>/process/', views.process_approval, name='process_approval'),
    path(
        'api/<int:pk>/action/',
        views.approval_action,
        name='approval_action'),
    path('apply/', views.apply_approval, name='apply_approval'),
    path(
        'apply/<int:flow_id>/',
        views.create_approval,
        name='create_approval'),
    path(
        'api/available-flows/',
        views.get_available_flows,
        name='get_available_flows'),

    path('delete/<str:model_name>/<int:pk>/',
         views.delete_item, name='delete_item'),
]
