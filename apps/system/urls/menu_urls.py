from django.urls import path
from django.shortcuts import redirect
from apps.system.views import menu_views

app_name = 'menu'

urlpatterns = [
    # 菜单管理页面路由
    path('', menu_views.MenuListView.as_view(), name='menu_list'),
    path('create/', menu_views.MenuCreateView.as_view(), name='menu_create'),
    path(
        'update/<int:pk>/',
        menu_views.MenuUpdateView.as_view(),
        name='menu_update'),
    path(
        'delete/<int:pk>/',
        menu_views.MenuDeleteView.as_view(),
        name='menu_delete'),

    # 菜单管理API路由
    path('sync/', menu_views.MenuSyncAPIView.as_view(), name='menu_sync'),
    path('order/', menu_views.MenuOrderAPIView.as_view(), name='menu_order'),

    # 获取权限组数据的API - 重定向到user应用
    path(
        'get_groups/',
        lambda request: redirect(
            '/user/group/all/',
            permanent=True),
        name='get_groups'),
]
