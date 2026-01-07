from apps.user.models import Admin as User
from apps.department.models import Department

def get_admin(user_id):
    """获取用户信息"""
    user = User.objects.get(id=user_id)
    department = None
    if user.did:
        from apps.department.models import Department
        department = Department.objects.filter(id=user.did).first()
    return {
        'id': user.id,
        'name': user.name,
        'did': user.did,
        'department': department.name if department else ''
    }

def get_leader_departments(user_id):
    """获取用户管理的部门ID列表"""
    # 这里需要根据实际业务逻辑实现
    return []

def is_leader(user_id):
    """判断用户是否是部门领导"""
    # 这里需要根据实际业务逻辑实现
    return False

def is_auth(user_id, module, action):
    """判断用户是否有权限"""
    # 这里需要根据实际业务逻辑实现
    return True

def value_auth(module, action):
    """获取权限值"""
    # 这里需要根据实际业务逻辑实现
    return True
