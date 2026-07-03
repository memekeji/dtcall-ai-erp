from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from django.utils import timezone

from apps.ai.services.business_result import normalize_business_ai_result
from apps.ai.utils.analysis_tools import default_project_analysis_tool

from .models import Comment, Project, ProjectRiskAnalysis, Task, WorkHour


RISK_LEVEL_ORDER = {
    'unknown': 0,
    'low': 1,
    'medium': 2,
    'high': 3,
}

RISK_LEVEL_DISPLAY = {
    'high': '高风险',
    'medium': '中风险',
    'low': '低风险',
    'unknown': '待评估',
}

ACTION_DISPLAY = {
    'manual_review': '人工重点复核',
    'approve': '可直接推进',
    'request_more_info': '补充关键数据',
    'reject': '暂停推进',
}


def get_risk_level_display(level: str) -> str:
    return RISK_LEVEL_DISPLAY.get(level or 'unknown', '待评估')


def get_action_display(action: str) -> str:
    return ACTION_DISPLAY.get(action or 'manual_review', '人工重点复核')


def serialize_risk_analysis(analysis: ProjectRiskAnalysis | None) -> dict | None:
    if analysis is None:
        return None

    payload = dict(analysis.analysis_payload or {})
    payload.update({
        'analysis_id': analysis.id,
        'project_id': analysis.project_id,
        'project_name': analysis.project.name,
        'risk_level': analysis.risk_level,
        'risk_level_display': analysis.risk_level_display,
        'risk_score': analysis.risk_score,
        'warning_count': analysis.warning_count,
        'summary': analysis.summary,
        'key_risks': analysis.key_risks or [],
        'suggestions': analysis.suggestions or [],
        'recommended_action': analysis.recommended_action,
        'recommended_action_display': get_action_display(analysis.recommended_action),
        'confidence': float(analysis.confidence or 0),
        'metrics': analysis.metrics or {},
        'trigger_source': analysis.trigger_source,
        'trigger_source_display': analysis.get_trigger_source_display(),
        'analyzed_at': analysis.analyzed_at.strftime('%Y-%m-%d %H:%M'),
    })
    return payload


class ProjectRiskAnalysisService:
    """项目风险分析服务"""

    def analyze_project(
        self,
        project: Project,
        *,
        trigger_source: str = 'manual',
        triggered_by=None,
    ) -> ProjectRiskAnalysis:
        snapshot = self._build_project_snapshot(project)
        deterministic_result = self._build_deterministic_result(project, snapshot)
        ai_enhancement = self._build_ai_enhancement(project, snapshot, deterministic_result)
        merged_payload = self._merge_results(deterministic_result, ai_enhancement)
        normalized_payload = normalize_business_ai_result(
            merged_payload,
            scenario='project_risk_prediction',
            source_refs=[{'type': 'project', 'id': project.id}],
        )

        risk_level = normalized_payload.get('risk_level') or deterministic_result['risk_level']
        risk_score = merged_payload.get('risk_score', deterministic_result['risk_score'])
        warning_count = len(normalized_payload.get('risk_points') or [])

        return ProjectRiskAnalysis.objects.create(
            project=project,
            risk_level=risk_level,
            risk_score=max(0, min(100, int(risk_score or 0))),
            warning_count=max(0, min(99, int(warning_count or 0))),
            summary=normalized_payload.get('summary', ''),
            key_risks=normalized_payload.get('risk_points') or [],
            suggestions=normalized_payload.get('suggestions') or [],
            recommended_action=normalized_payload.get('recommended_action') or 'manual_review',
            confidence=Decimal(str(normalized_payload.get('confidence') or 0)).quantize(Decimal('0.0001')),
            metrics=snapshot,
            analysis_payload=normalized_payload,
            trigger_source=trigger_source,
            triggered_by=triggered_by,
        )

    def analyze_all_projects(self, *, trigger_source: str = 'scheduled', triggered_by=None) -> list[ProjectRiskAnalysis]:
        analyses = []
        projects = Project.objects.filter(delete_time__isnull=True).select_related('manager', 'creator', 'department')
        for project in projects:
            analyses.append(
                self.analyze_project(
                    project,
                    trigger_source=trigger_source,
                    triggered_by=triggered_by,
                )
            )
        return analyses

    def _build_project_snapshot(self, project: Project) -> dict:
        today = timezone.now().date()
        tasks = list(
            Task.objects.filter(project=project, delete_time__isnull=True)
            .select_related('assignee')
            .prefetch_related('participants')
        )
        purchases = project.purchases.filter(delete_time__isnull=True)
        documents_count = project.documents.filter(delete_time__isnull=True).count()
        project_content_type = ContentType.objects.get_for_model(Project)
        comments_queryset = Comment.objects.filter(
            content_type=project_content_type,
            object_id=project.id,
            delete_time__isnull=True,
        )
        recent_comment_count = comments_queryset.filter(
            create_time__gte=timezone.now() - timedelta(days=7)
        ).count()

        total_tasks = len(tasks)
        completed_tasks = sum(1 for task in tasks if task.status == 3)
        in_progress_tasks = sum(1 for task in tasks if task.status == 2)
        pending_tasks = sum(1 for task in tasks if task.status == 1)
        delayed_tasks = sum(1 for task in tasks if task.status == 4)
        cancelled_tasks = sum(1 for task in tasks if task.status == 5)
        overdue_tasks = [
            task for task in tasks
            if task.end_date and task.status not in (3, 5) and task.end_date < today
        ]
        unassigned_tasks = [task for task in tasks if task.assignee_id is None]
        high_priority_tasks = [task for task in tasks if task.priority >= 3]
        not_started_high_priority = [
            task for task in high_priority_tasks
            if task.status == 1 and task.progress == 0
        ]
        stale_tasks = [
            task for task in tasks
            if task.status in (1, 2)
            and task.progress == 0
            and task.start_date
            and task.start_date < today
        ]
        tasks_missing_schedule = [
            task for task in tasks
            if not task.start_date or not task.end_date
        ]

        estimated_hours = sum(int(task.estimated_hours or 0) for task in tasks)
        actual_task_hours = sum(int(task.actual_hours or 0) for task in tasks)
        logged_hours = WorkHour.objects.filter(task__project=project).aggregate(total=Sum('hours'))['total'] or Decimal('0')

        budget = Decimal(str(project.budget or 0))
        actual_cost = Decimal(str(project.actual_cost or 0))
        purchase_cost = purchases.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        committed_cost = actual_cost + purchase_cost

        member_ids = set(project.members.values_list('id', flat=True))
        if project.manager_id:
            member_ids.add(project.manager_id)
        active_owner_ids = {
            task.assignee_id for task in tasks if task.assignee_id
        }
        for task in tasks:
            active_owner_ids.update(task.participants.values_list('id', flat=True))

        expected_progress = self._calculate_expected_progress(project, today)
        progress_gap = max(0, expected_progress - int(project.progress or 0))
        overdue_days = 0
        if project.end_date and today > project.end_date and project.status not in (3, 4):
            overdue_days = (today - project.end_date).days

        return {
            'project': {
                'id': project.id,
                'name': project.name,
                'code': project.code,
                'status': project.status,
                'status_display': project.status_display,
                'priority': project.priority,
                'priority_display': project.priority_display,
                'progress': int(project.progress or 0),
                'start_date': project.start_date.isoformat() if project.start_date else '',
                'end_date': project.end_date.isoformat() if project.end_date else '',
                'budget': float(budget),
                'actual_cost': float(actual_cost),
                'purchase_cost': float(purchase_cost),
                'committed_cost': float(committed_cost),
                'days_remaining': project.days_remaining,
                'is_overdue': project.is_overdue,
                'overdue_days': overdue_days,
                'manager_name': project.manager.name if project.manager else '',
                'member_count': len(member_ids),
                'description_length': len(project.description or ''),
            },
            'schedule': {
                'expected_progress': expected_progress,
                'progress_gap': progress_gap,
                'overdue_task_count': len(overdue_tasks),
                'delayed_task_count': delayed_tasks,
                'stale_task_count': len(stale_tasks),
                'tasks_missing_schedule_count': len(tasks_missing_schedule),
            },
            'tasks': {
                'total': total_tasks,
                'completed': completed_tasks,
                'in_progress': in_progress_tasks,
                'pending': pending_tasks,
                'delayed': delayed_tasks,
                'cancelled': cancelled_tasks,
                'overdue': len(overdue_tasks),
                'unassigned': len(unassigned_tasks),
                'high_priority': len(high_priority_tasks),
                'high_priority_not_started': len(not_started_high_priority),
            },
            'hours': {
                'estimated_hours': estimated_hours,
                'actual_task_hours': actual_task_hours,
                'logged_hours': float(logged_hours),
                'hours_overrun': max(0, actual_task_hours - estimated_hours),
            },
            'cost': {
                'budget': float(budget),
                'actual_cost': float(actual_cost),
                'purchase_cost': float(purchase_cost),
                'committed_cost': float(committed_cost),
                'budget_usage_ratio': self._safe_ratio(actual_cost, budget),
                'committed_budget_ratio': self._safe_ratio(committed_cost, budget),
            },
            'collaboration': {
                'team_member_count': len(member_ids),
                'active_owner_count': len(active_owner_ids),
                'documents_count': documents_count,
                'comment_count': comments_queryset.count(),
                'recent_comment_count': recent_comment_count,
            },
        }

    def _build_deterministic_result(self, project: Project, snapshot: dict) -> dict:
        project_metrics = snapshot['project']
        schedule = snapshot['schedule']
        tasks = snapshot['tasks']
        hours = snapshot['hours']
        cost = snapshot['cost']
        collaboration = snapshot['collaboration']

        issues = []
        dimension_scores = {
            'schedule': 0,
            'cost': 0,
            'delivery': 0,
            'collaboration': 0,
        }

        if not project.start_date or not project.end_date:
            dimension_scores['schedule'] += 18
            issues.append('项目起止日期不完整，整体排期基线不足。')
        if project_metrics['is_overdue']:
            dimension_scores['schedule'] += min(40, 20 + project_metrics['overdue_days'] * 3)
            issues.append(f"项目整体已逾期 {project_metrics['overdue_days']} 天。")
        if schedule['progress_gap'] >= 20:
            dimension_scores['schedule'] += 24
            issues.append(f"项目当前进度落后计划 {schedule['progress_gap']} 个百分点。")
        elif schedule['progress_gap'] >= 10:
            dimension_scores['schedule'] += 14
            issues.append(f"项目进度落后计划 {schedule['progress_gap']} 个百分点，需要追赶。")
        if schedule['overdue_task_count'] > 0:
            dimension_scores['schedule'] += min(24, schedule['overdue_task_count'] * 8)
            issues.append(f"存在 {schedule['overdue_task_count']} 个逾期任务。")
        if schedule['delayed_task_count'] > 0:
            dimension_scores['schedule'] += min(16, schedule['delayed_task_count'] * 6)
            issues.append(f"存在 {schedule['delayed_task_count']} 个延期状态任务。")
        if schedule['stale_task_count'] > 0:
            dimension_scores['schedule'] += min(14, schedule['stale_task_count'] * 5)
            issues.append(f"有 {schedule['stale_task_count']} 个任务已到开始时间但仍无进展。")

        if cost['budget'] <= 0:
            dimension_scores['cost'] += 20
            issues.append('项目未设置有效预算，成本管控边界不清晰。')
        if cost['budget_usage_ratio'] >= 0.9:
            dimension_scores['cost'] += 18
            issues.append('实际成本已接近预算上限。')
        if cost['committed_budget_ratio'] >= 1.1:
            dimension_scores['cost'] += 26
            issues.append('实际成本叠加采购承诺后已明显超预算。')
        elif cost['committed_budget_ratio'] >= 0.95:
            dimension_scores['cost'] += 14
            issues.append('采购承诺叠加已用成本后，预算余量不足。')
        if hours['estimated_hours'] and hours['actual_task_hours'] > hours['estimated_hours'] * 1.2:
            dimension_scores['cost'] += 12
            issues.append('任务实际工时明显高于预估，可能继续推高实施成本。')

        if tasks['total'] == 0:
            dimension_scores['delivery'] += 22
            issues.append('项目尚未拆解任务，交付路径不可见。')
        if tasks['high_priority_not_started'] > 0:
            dimension_scores['delivery'] += min(18, tasks['high_priority_not_started'] * 8)
            issues.append(f"有 {tasks['high_priority_not_started']} 个高优先级任务仍未启动。")
        if tasks['unassigned'] > 0:
            dimension_scores['delivery'] += min(18, tasks['unassigned'] * 8)
            issues.append(f"有 {tasks['unassigned']} 个任务尚未明确负责人。")
        if tasks['pending'] and tasks['total'] and tasks['pending'] / tasks['total'] >= 0.5:
            dimension_scores['delivery'] += 10
            issues.append('待开始任务占比偏高，后续排期存在集中拥堵风险。')
        if schedule['tasks_missing_schedule_count'] > 0:
            dimension_scores['delivery'] += min(12, schedule['tasks_missing_schedule_count'] * 4)
            issues.append(f"有 {schedule['tasks_missing_schedule_count']} 个任务缺少完整排期。")

        if collaboration['team_member_count'] == 0:
            dimension_scores['collaboration'] += 20
            issues.append('项目团队成员为空，协作资源尚未落实。')
        if collaboration['documents_count'] == 0:
            dimension_scores['collaboration'] += 10
            issues.append('项目暂无文档沉淀，交付与复盘依据不足。')
        if collaboration['recent_comment_count'] == 0 and project.status == 2:
            dimension_scores['collaboration'] += 8
            issues.append('近期缺少项目沟通痕迹，需确认跟踪机制是否有效。')
        if project_metrics['member_count'] > 0 and collaboration['active_owner_count'] == 0 and tasks['total'] > 0:
            dimension_scores['collaboration'] += 12
            issues.append('任务参与责任人覆盖不足，项目推进存在协同断层。')

        for key in dimension_scores:
            dimension_scores[key] = max(0, min(100, int(dimension_scores[key])))

        weighted_score = round(
            dimension_scores['schedule'] * 0.35 +
            dimension_scores['cost'] * 0.25 +
            dimension_scores['delivery'] * 0.25 +
            dimension_scores['collaboration'] * 0.15
        )

        if weighted_score >= 70:
            risk_level = 'high'
        elif weighted_score >= 40:
            risk_level = 'medium'
        else:
            risk_level = 'low'

        summary_parts = []
        if risk_level == 'high':
            summary_parts.append('项目当前处于高风险区间，需要管理层尽快介入。')
        elif risk_level == 'medium':
            summary_parts.append('项目存在可感知风险，建议按周跟踪关键指标。')
        else:
            summary_parts.append('项目整体风险可控，但仍需保持例行巡检。')

        if schedule['progress_gap'] > 0:
            summary_parts.append(f"当前进度较计划滞后 {schedule['progress_gap']} 个百分点。")
        if tasks['overdue'] > 0:
            summary_parts.append(f"逾期任务 {tasks['overdue']} 个。")
        if cost['committed_budget_ratio'] >= 0.95:
            summary_parts.append('预算余量偏紧。')

        suggestions = self._build_suggestions(project, snapshot, risk_level)

        return {
            'summary': ''.join(summary_parts),
            'risk_level': risk_level,
            'risk_level_display': get_risk_level_display(risk_level),
            'risk_score': weighted_score,
            'warning_count': len(issues),
            'risk_points': issues[:8],
            'suggestions': suggestions,
            'recommended_action': 'manual_review' if risk_level != 'low' else 'approve',
            'confidence': 0.82,
            'dimension_scores': dimension_scores,
            'snapshot': snapshot,
        }

    def _build_ai_enhancement(self, project: Project, snapshot: dict, deterministic_result: dict) -> dict:
        prompt = (
            "你是企业项目治理专家。请基于给定的项目风险指标，补充一份中文 JSON 结果。"
            "只能输出 JSON，不要输出 Markdown。JSON 字段必须包含："
            "summary, risk_level, risk_points, suggestions, recommended_action, confidence。"
            "summary 需要给出管理层可直接阅读的结论；risk_points 和 suggestions 各给 3-6 条。"
            f"\n项目基础信息：{snapshot['project']}"
            f"\n排期指标：{snapshot['schedule']}"
            f"\n任务指标：{snapshot['tasks']}"
            f"\n工时指标：{snapshot['hours']}"
            f"\n成本指标：{snapshot['cost']}"
            f"\n协同指标：{snapshot['collaboration']}"
            f"\n系统初判结果：{deterministic_result}"
        )
        result = default_project_analysis_tool._call_ai(prompt, max_tokens=900, temperature=0.2)
        return result if isinstance(result, dict) else {}

    def _merge_results(self, deterministic_result: dict, ai_enhancement: dict) -> dict:
        if not ai_enhancement:
            return deterministic_result

        merged = dict(deterministic_result)
        ai_level = str(ai_enhancement.get('risk_level') or '').lower()
        base_level = deterministic_result.get('risk_level', 'unknown')
        if RISK_LEVEL_ORDER.get(ai_level, 0) > RISK_LEVEL_ORDER.get(base_level, 0):
            merged['risk_level'] = ai_level
            merged['risk_level_display'] = get_risk_level_display(ai_level)

        merged['summary'] = ai_enhancement.get('summary') or deterministic_result.get('summary', '')
        merged['risk_points'] = self._merge_list_values(
            ai_enhancement.get('risk_points'),
            deterministic_result.get('risk_points'),
        )
        merged['suggestions'] = self._merge_list_values(
            ai_enhancement.get('suggestions'),
            deterministic_result.get('suggestions'),
        )
        merged['recommended_action'] = ai_enhancement.get('recommended_action') or deterministic_result.get('recommended_action')
        merged['confidence'] = ai_enhancement.get('confidence') or deterministic_result.get('confidence', 0)
        return merged

    def _build_suggestions(self, project: Project, snapshot: dict, risk_level: str) -> list[str]:
        schedule = snapshot['schedule']
        tasks = snapshot['tasks']
        cost = snapshot['cost']
        collaboration = snapshot['collaboration']

        suggestions = []
        if schedule['progress_gap'] >= 10 or schedule['overdue_task_count'] > 0:
            suggestions.append('围绕关键路径任务建立周度纠偏机制，逐项消化逾期与滞后任务。')
        if cost['committed_budget_ratio'] >= 0.95:
            suggestions.append('复核采购与外部支出优先级，先保障关键交付所需预算。')
        if tasks['unassigned'] > 0 or tasks['high_priority_not_started'] > 0:
            suggestions.append('补齐高优任务负责人和启动时间，避免关键工作继续悬空。')
        if collaboration['documents_count'] == 0:
            suggestions.append('尽快沉淀实施方案、会议纪要和验收依据，减少执行偏差。')
        if risk_level == 'high':
            suggestions.append('建议项目经理在 24 小时内提交专项风险处置计划，并同步管理层。')
        elif risk_level == 'low':
            suggestions.append('保持每日例行跟踪，重点关注预算与里程碑是否出现异常波动。')

        return suggestions[:6]

    def _calculate_expected_progress(self, project: Project, today) -> int:
        if not project.start_date or not project.end_date:
            return int(project.progress or 0)
        if today <= project.start_date:
            return 0
        total_days = (project.end_date - project.start_date).days + 1
        if total_days <= 0:
            return int(project.progress or 0)
        elapsed = min(today, project.end_date) - project.start_date
        expected = round(((elapsed.days + 1) / total_days) * 100)
        return max(0, min(100, expected))

    def _safe_ratio(self, numerator: Decimal, denominator: Decimal) -> float:
        if not denominator:
            return 0.0
        return round(float(numerator / denominator), 4)

    def _merge_list_values(self, preferred, fallback) -> list[str]:
        values = []
        for source in (preferred, fallback):
            if isinstance(source, list):
                values.extend(str(item).strip() for item in source if str(item).strip())
            elif source:
                values.append(str(source).strip())
        deduped = []
        for value in values:
            if value and value not in deduped:
                deduped.append(value)
        return deduped[:8]


project_risk_analysis_service = ProjectRiskAnalysisService()
