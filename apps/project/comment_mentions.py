from django.contrib.auth import get_user_model

from .models import Project

User = get_user_model()


def get_project_comment_candidate_users(project: Project):
    """Return deduplicated users allowed in project comment mentions."""
    task_queryset = project.tasks.filter(delete_time__isnull=True)
    user_ids = set()

    if project.manager_id:
        user_ids.add(project.manager_id)

    user_ids.update(project.members.values_list('id', flat=True))
    user_ids.update(
        task_queryset.exclude(assignee_id__isnull=True).values_list(
            'assignee_id',
            flat=True,
        )
    )
    user_ids.update(
        user_id for user_id in task_queryset.values_list('participants__id', flat=True)
        if user_id
    )

    if not user_ids:
        return User.objects.none()

    return User.objects.filter(id__in=user_ids).order_by('id')
