from dataclasses import dataclass

from django.db.models import Q

from apps.system.middleware.data_permission_middleware import PermissionChecker


def build_csv_membership_q(field_name: str, value) -> Q:
    normalized = str(value or '').strip()
    if not normalized:
        return Q(pk__in=[])
    return (
        Q(**{field_name: normalized}) |
        Q(**{f'{field_name}__startswith': f'{normalized},'}) |
        Q(**{f'{field_name}__endswith': f',{normalized}'}) |
        Q(**{f'{field_name}__contains': f',{normalized},'})
    )


@dataclass(slots=True)
class PermissionCheckResult:
    allowed: bool
    reason: str


class AIPermissionGuard:
    OPERATION_TO_CHECKER = {
        'query': 'can_view',
        'list': 'can_view',
        'detail': 'can_view',
        'create': 'can_add',
        'update': 'can_change',
        'delete': 'can_delete',
        'approve': 'can_approve',
    }

    RESOURCE_PERMISSION_ALIASES = {
        'finance': 'reimbursement',
        'invoice_request': 'invoice',
    }

    def check_action_permission(
            self,
            user,
            action,
            permission_code: str,
            queryset=None,
            exact_permission: bool = False):
        if not getattr(user, 'is_authenticated', False):
            return PermissionCheckResult(allowed=False, reason='unauthenticated')

        checker_name = self.OPERATION_TO_CHECKER.get(action.operation, 'can_operate')
        checker = getattr(PermissionChecker, checker_name)
        permission_name = permission_code.split('.', 1)[-1] if '.' in permission_code else permission_code
        app_label = permission_code.split('.', 1)[0] if '.' in permission_code else 'user'
        resource_type = permission_name.split('_', 1)[-1] if '_' in permission_name else permission_name
        resource_type = self.RESOURCE_PERMISSION_ALIASES.get(resource_type, resource_type)

        if exact_permission or checker_name == 'can_operate':
            allowed = self._check_exact_permission(user, permission_code)
        elif app_label != 'user':
            allowed = self._check_exact_permission(user, permission_code)
        else:
            allowed = checker(user, resource_type)

        if not allowed:
            return PermissionCheckResult(allowed=False, reason='missing_permission')

        if queryset is not None and hasattr(queryset, 'exists') and not queryset.exists():
            return PermissionCheckResult(allowed=False, reason='out_of_scope')

        return PermissionCheckResult(allowed=True, reason='allowed')

    def _check_exact_permission(self, user, permission_code: str) -> bool:
        if not getattr(user, 'is_authenticated', False):
            return False
        if getattr(user, 'is_superuser', False):
            return True
        normalized_perm = PermissionChecker.normalize_permission(permission_code)
        return bool(getattr(user, 'has_perm', lambda code: False)(normalized_perm))
