from django.urls import path
from . import views

app_name = 'enterprise'

urlpatterns = [
    path('enterprise_list/', views.enterprise_list, name='enterprise_list'),
    path('enterprise_add/<int:id>/', views.enterprise_add, name='enterprise_edit'),
    path('enterprise_add/', views.enterprise_add, name='enterprise_add'),
]