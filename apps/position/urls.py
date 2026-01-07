from django.urls import path
from . import views

urlpatterns = [
    path('', views.PositionListView.as_view(), name='position_list'),
    path('add/', views.PositionCreateView.as_view(), name='position_add'),
    path('edit/<int:pk>/', views.PositionUpdateView.as_view(), name='position_edit'),
    path('delete/<int:pk>/', views.PositionDeleteView.as_view(), name='position_delete'),
    path('list-data/', views.position_list_data, name='position_list_data'),
    path('api/<int:pk>/', views.position_detail_api, name='position_detail_api'),
    path('disable/', views.position_disable, name='position_disable'),
    path('enable/', views.position_enable, name='position_enable'),
]