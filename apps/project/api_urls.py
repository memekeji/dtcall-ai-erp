from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    ProjectViewSet, ProjectStepViewSet, TaskViewSet,
    WorkHourViewSet, ProjectDocumentViewSet, ProjectCategoryViewSet,
    ProjectStageViewSet, WorkTypeViewSet, CommentViewSet
)

# 创建路由器
router = DefaultRouter()

# 注册视图集
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'project-steps', ProjectStepViewSet, basename='project-step')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'work-hours', WorkHourViewSet, basename='work-hour')
router.register(
    r'project-documents',
    ProjectDocumentViewSet,
    basename='project-document')
router.register(
    r'project-categories',
    ProjectCategoryViewSet,
    basename='project-category')
router.register(
    r'project-stages',
    ProjectStageViewSet,
    basename='project-stage')
router.register(r'work-types', WorkTypeViewSet, basename='work-type')
router.register(r'comments', CommentViewSet, basename='comment')

# 定义URL模式
urlpatterns = [
    # 包含路由器生成的URL
    path('', include(router.urls)),
]
