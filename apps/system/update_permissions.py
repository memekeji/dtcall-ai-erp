from __future__ import annotations


def can_view_update_center(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    has_perm = getattr(user, "has_perm", None)
    if not callable(has_perm):
        return False
    return any(
        has_perm(permission)
        for permission in (
            "user.change_config",
            "user.view_config",
        )
    )


def can_manage_update_center(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    has_perm = getattr(user, "has_perm", None)
    if not callable(has_perm):
        return False
    return has_perm("user.change_config")
