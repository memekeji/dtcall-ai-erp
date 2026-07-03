import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView

from apps.ai.services.business_result import build_business_ai_result

from .models import Project, ProjectRiskAnalysis, Task, WorkHour
from .risk_analysis import (
    get_action_display,
    get_risk_level_display,
    default_project_analysis_tool,
    serialize_risk_analysis,
)

logger = logging.getLogger(__name__)


def _get_accessible_projects(user):
    queryset = Project.objects.filter(delete_time__isnull=True).select_related(
        'manager',
        'creator',
        'department',
        'category',
    )
    if user.is_superuser:
        return queryset

    permission_q = (
        Q(creator=user) |
        Q(manager=user) |
        Q(members=user)
    )
    if hasattr(user, 'did') and user.did:
        permission_q |= Q(department_id=user.did)
    return queryset.filter(permission_q).distinct()


def has_permission(user, project):
    if user.is_superuser:
        return True

    user_has_dept_permission = False
    if project.department and hasattr(user, 'did') and user.did:
        user_has_dept_permission = project.department.id == user.did

    return (
        project.creator == user or
        project.manager == user or
        user in project.members.all() or
        user_has_dept_permission
    )


def _build_risk_analysis_rows(projects):
    project_ids = list(projects.values_list('id', flat=True))
    if not project_ids:
        return []

    latest_analysis_subquery = ProjectRiskAnalysis.objects.filter(
        project=OuterRef('pk')
    ).order_by('-analyzed_at', '-id').values('id')[:1]

    projects = list(projects.annotate(latest_analysis_id=Subquery(latest_analysis_subquery)))
    latest_ids = [project.latest_analysis_id for project in projects if project.latest_analysis_id]
    analyses = ProjectRiskAnalysis.objects.filter(id__in=latest_ids).select_related('project')
    analysis_map = {analysis.id: analysis for analysis in analyses}

    rows = []
    for project in projects:
        analysis = analysis_map.get(project.latest_analysis_id)
        row = {
            'project': project,
            'analysis': analysis,
            'project_id': project.id,
            'project_name': project.name,
            'project_code': project.code,
            'manager_name': project.manager.name if project.manager else '',
            'status_display': project.status_display,
            'progress': int(project.progress or 0),
            'end_date': project.end_date,
            'risk_level': analysis.risk_level if analysis else 'unknown',
            'risk_level_display': analysis.risk_level_display if analysis else '待分析',
            'risk_score': analysis.risk_score if analysis else None,
            'warning_count': analysis.warning_count if analysis else 0,
            'summary': analysis.summary if analysis else '尚未生成风险分析结果',
            'recommended_action_display': get_action_display(analysis.recommended_action) if analysis else '等待分析',
            'analyzed_at': analysis.analyzed_at if analysis else None,
            'detail_url': f'/project/ai/risk-prediction/detail/{analysis.id}/' if analysis else '',
        }
        rows.append(row)
    return rows


@login_required
def ai_project_risk_prediction(request, project_id):
    try:
        try:
            project = Project.objects.get(id=project_id, delete_time__isnull=True)
        except Project.DoesNotExist as exc:
            raise Http404('项目不存在') from exc
        if not has_permission(request.user, project):
            return JsonResponse({'code': 403, 'msg': '没有权限查看此项目'}, status=403)

        task_queryset = Task.objects.filter(project=project, delete_time__isnull=True)
        work_hour_queryset = WorkHour.objects.filter(project=project, delete_time__isnull=True)

        task_data = [
            {
                'id': task.id,
                'title': getattr(task, 'title', ''),
                'status': getattr(task, 'status', ''),
                'priority': getattr(task, 'priority', ''),
                'progress': getattr(task, 'progress', 0),
                'assignee_id': getattr(task, 'assignee_id', None),
                'start_date': getattr(task, 'start_date', None),
                'end_date': getattr(task, 'end_date', None),
            }
            for task in task_queryset
        ]
        task_stats = task_queryset.aggregate(
            total_tasks=Count('id'),
            completed_tasks=Count('id', filter=Q(status='completed')),
            in_progress_tasks=Count('id', filter=Q(status='in_progress')),
            pending_tasks=Count('id', filter=Q(status='pending')),
        )
        total_hours = work_hour_queryset.aggregate(total=Sum('hours'))

        project_data = {
            'id': project.id,
            'name': project.name,
            'code': getattr(project, 'code', ''),
            'status': getattr(project, 'status', ''),
            'progress': getattr(project, 'progress', 0),
            'start_date': getattr(project, 'start_date', None),
            'end_date': getattr(project, 'end_date', None),
            'manager_id': getattr(project, 'manager_id', None),
            'department_id': getattr(project, 'department_id', None),
        }

        raw_result = default_project_analysis_tool.predict_project_risk(
            project_data=project_data,
            task_data=task_data,
            task_stats=task_stats,
            total_hours=total_hours,
        )
        payload = build_business_ai_result(
            raw_result,
            scenario='project_risk_prediction',
            source_refs=[{'type': 'project', 'id': project.id}],
            request=request,
            raw_input={
                'project': project_data,
                'tasks': task_data,
                'task_stats': task_stats,
                'total_hours': total_hours,
            },
        )
        logger.info('项目风险预测完成: project=%s', project_id)
        return JsonResponse({
            'code': 0,
            'msg': '风险预测成功',
            'data': payload,
        })
    except Exception as exc:
        logger.exception('项目风险预测失败: project=%s', project_id)
        return JsonResponse({'code': 500, 'msg': f'风险预测失败: {exc}'}, status=500)


@login_required
def ai_project_progress_analysis(request, project_id):
    """兼容旧入口：进度分析已下线，统一跳转到风险分析。"""
    return ai_project_risk_prediction(request, project_id)


class AIRiskPredictionView(LoginRequiredMixin, TemplateView):
    template_name = 'project/ai_risk_prediction.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        projects = _get_accessible_projects(self.request.user).order_by('-create_time')
        rows = _build_risk_analysis_rows(projects)
        selected_project_id = self.kwargs.get('project_id') or self.request.GET.get('project_id') or ''

        level_counts = {'high': 0, 'medium': 0, 'low': 0, 'unknown': 0}
        for row in rows:
            level_counts[row['risk_level']] = level_counts.get(row['risk_level'], 0) + 1

        context.update({
            'projects': projects,
            'rows': rows,
            'selected_project_id': str(selected_project_id) if selected_project_id else '',
            'stats': {
                'total': len(rows),
                'high': level_counts.get('high', 0),
                'medium': level_counts.get('medium', 0),
                'low': level_counts.get('low', 0),
                'unknown': level_counts.get('unknown', 0),
            },
        })
        return context


class AIRiskPredictionDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'project/ai_risk_prediction_detail.html'

    def get(self, request, *args, **kwargs):
        analysis = get_object_or_404(
            ProjectRiskAnalysis.objects.select_related('project', 'project__manager', 'triggered_by'),
            id=kwargs['analysis_id'],
            project__delete_time__isnull=True,
        )
        if not has_permission(self.request.user, analysis.project):
            return JsonResponse({'code': 403, 'msg': '没有权限查看此项目'}, status=403)

        payload = serialize_risk_analysis(analysis)
        context = {
            'analysis': analysis,
            'project': analysis.project,
            'analysis_payload': payload,
            'risk_level_display': get_risk_level_display(analysis.risk_level),
        }
        return render(request, self.template_name, context)
