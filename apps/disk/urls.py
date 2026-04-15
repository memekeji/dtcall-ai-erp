from django.urls import path
from . import views
from . import ai_views

app_name = 'disk'

urlpatterns = [
    # 新版网盘功能
    path('', views.DiskIndexView.as_view(), name='index'),
    path('personal/', views.PersonalDiskView.as_view(), name='personal'),
    path('share/', views.SharedDiskView.as_view(), name='shared'),
    path('recycle/', views.RecycleBinView.as_view(), name='recycle'),
    path('starred/', views.StarredFilesView.as_view(), name='starred'),

    # 文件操作
    path('upload/', views.FileUploadView.as_view(), name='file_upload'),
    path(
        'download/<int:file_id>/',
        views.FileDownloadView.as_view(),
        name='file_download'),
    path(
        'file/delete/<int:file_id>/',
        views.FileDeleteView.as_view(),
        name='file_delete'),
    path(
        'file/restore/<int:file_id>/',
        views.FileRestoreView.as_view(),
        name='file_restore'),
    path(
        'file/rename/<int:file_id>/',
        views.FileRenameView.as_view(),
        name='file_rename'),

    # 文件夹操作
    path(
        'folder/create/',
        views.FolderCreateView.as_view(),
        name='folder_create'),
    path(
        'folder/delete/<int:folder_id>/',
        views.FolderDeleteView.as_view(),
        name='folder_delete'),
    path(
        'folder/restore/<int:folder_id>/',
        views.FolderRestoreView.as_view(),
        name='folder_restore'),
    path(
        'folder/rename/<int:folder_id>/',
        views.FolderRenameView.as_view(),
        name='folder_rename'),
    path(
        'folder/move/<int:folder_id>/',
        views.FolderMoveView.as_view(),
        name='folder_move'),

    # 回收站操作
    path(
        'recycle/clear/',
        views.RecycleBinClearView.as_view(),
        name='recycle_clear'),

    # 搜索功能
    path('search/', views.FileSearchView.as_view(), name='file_search'),

    # 分享功能
    path(
        'share/create/',
        views.FileShareCreateView.as_view(),
        name='share_create'),
    path(
        'share/view/<str:share_code>/',
        views.FileShareView.as_view(),
        name='share_view'),
    path(
        'share/download/',
        views.ShareDownloadView.as_view(),
        name='share_download'),
    path(
        'share/folder/',
        views.ShareFolderView.as_view(),
        name='share_folder'),

    # 收藏功能
    path(
        'file/star/<int:file_id>/',
        views.FileStarToggleView.as_view(),
        name='file_star_toggle'),

    # 权限管理
    path(
        'permission/',
        views.PermissionManageView.as_view(),
        name='permission_manage'),
    path(
        'permission/user/',
        views.UserPermissionView.as_view(),
        name='user_permission'),
    path(
        'permission/user/add/',
        views.UserPermissionAddView.as_view(),
        name='user_permission_add'),
    path(
        'permission/user/remove/',
        views.UserPermissionRemoveView.as_view(),
        name='user_permission_remove'),
    path(
        'permission/user/list/',
        views.UserPermissionListView.as_view(),
        name='user_permission_list'),
    path('permission/user/list/existing/',
         views.ExistingPermissionUsersView.as_view(),
         name='existing_permission_users'),
    path(
        'permission/dept/',
        views.DeptPermissionView.as_view(),
        name='dept_permission'),
    path(
        'permission/dept/add/',
        views.DeptPermissionAddView.as_view(),
        name='dept_permission_add'),
    path(
        'permission/dept/remove/',
        views.DeptPermissionRemoveView.as_view(),
        name='dept_permission_remove'),
    path('permission/dept/list/existing/',
         views.ExistingPermissionDepartmentsView.as_view(),
         name='existing_permission_departments'),
    path(
        'permission/save/',
        views.PermissionSaveView.as_view(),
        name='permission_save'),

    # 文件预览功能
    path('preview/', views.PreviewView.as_view(), name='preview'),
    path(
        'file/preview/<int:file_id>/',
        views.FilePreviewView.as_view(),
        name='file_preview'),
    path(
        'share/preview/<int:file_id>/',
        views.SharePreviewView.as_view(),
        name='share_preview'),
    path(
        'image/thumbnail/<int:file_id>/',
        views.ImageThumbnailView.as_view(),
        name='image_thumbnail'),

    # 兼容原有功能
    path('disk_list/', views.disk_list, name='disk_list'),
    path('disk_add/', views.disk_add, name='disk_add'),
    path('disk_edit/<int:id>/', views.disk_edit, name='disk_edit'),
    path('disk_delete/<int:id>/', views.disk_delete, name='disk_delete'),       

    # AI 增强功能
    path('ai/analyze/<int:file_id>/', ai_views.FileAIAssistantView.as_view(), name='ai_analyze'),
]
