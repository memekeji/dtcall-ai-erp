from django.urls import path
from . import views

app_name = 'approval'

urlpatterns = [
    path('approval_type/', views.approval_type_list, name='approval_type_list'),
    path('approval_type/add/', views.approval_type_form, name='approval_type_add'),
    path('approval_type/<int:pk>/edit/', views.approval_type_form, name='approval_type_edit'),
    
    path('approvalflow/', views.approval_flow_list, name='approval_flow_list'),
    path('approvalflow/add/', views.approval_flow_form, name='approval_flow_add'),
    path('approvalflow/<int:pk>/edit/', views.approval_flow_form, name='approval_flow_edit'),
    path('approvalflow/<int:pk>/steps/', views.approval_flow_steps, name='approval_flow_steps'),
    path('approvalflow/<int:flow_pk>/step/add/', views.approval_step_form, name='approval_step_add'),
    path('approvalflow/<int:flow_pk>/step/<int:pk>/edit/', views.approval_step_form, name='approval_step_edit'),
    path('approvalflow/<int:flow_pk>/step/<int:pk>/delete/', views.approval_step_delete, name='approval_step_delete'),
    path('approvalflow/<int:pk>/preview/', views.approval_flow_preview, name='approval_flow_preview'),
    path('approvalflow/<int:pk>/batch-create-steps/', views.batch_create_steps, name='batch_create_steps'),
    
    path('delete/<str:model_name>/<int:pk>/', views.delete_item, name='delete_item'),
]
