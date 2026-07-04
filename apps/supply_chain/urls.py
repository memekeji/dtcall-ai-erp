from django.urls import path

from . import views


app_name = 'supply_chain'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
]
