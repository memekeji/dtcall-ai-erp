from django import template

register = template.Library()


@register.simple_tag
def get_menu_level(menu_items):
    return getattr(menu_items, 'level', 1)


def _check_permission_format(user, permission_code):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    full_perm = permission_code
    if '.' not in full_perm:
        full_perm = f'user.{permission_code}'

    return user.has_perm(full_perm)


@register.filter
def has_permission(user, permission_code):
    """
    检查用户是否拥有指定权限
    用法: {% if user|has_permission:"view_customer" %}
    """
    return _check_permission_format(user, permission_code)


@register.filter
def has_any_permission(user, *permissions):
    """
    检查用户是否拥有任一权限
    用法: {% if user|has_any_permission:"view_customer:add_customer" %}
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    for perm in permissions:
        if _check_permission_format(user, perm):
            return True
    return False


@register.filter
def has_all_permissions(user, *permissions):
    """
    检查用户是否拥有所有权限
    用法: {% if user|has_all_permissions:"view_customer:add_customer" %}
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    for perm in permissions:
        if not _check_permission_format(user, perm):
            return False
    return True


@register.simple_tag
def get_user_department(user):
    """
    获取用户所属部门
    """
    if user and hasattr(user, 'employee') and user.employee:
        return user.employee.department
    return None


@register.simple_tag
def can_access_data(user, data_owner_id, data_owner_field='created_by_id'):
    """
    检查用户是否可以访问指定数据（数据权限控制）
    返回 True 如果:
    - 用户是超级用户
    - 用户是数据所有者
    - 用户与数据所有者属于同一部门且有部门数据权限
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if hasattr(user, 'id') and str(user.id) == str(data_owner_id):
        return True
    return False
