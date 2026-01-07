import logging
from apps.user.models import SystemConfiguration as SystemConfig, Menu, SystemModule
from django.contrib.auth import get_user_model
from django.core.cache import cache

logger = logging.getLogger('django')

User = get_user_model()

def system_config(request):
    """系统配置上下文处理器，使配置在所有模板中可用"""
    # 使用缓存存储系统配置，减少数据库查询
    cache_key = 'system_configs'
    configs = cache.get(cache_key)
    
    if configs is None:
        config_items = SystemConfig.objects.filter(is_active=True)
        configs = {item.key: item for item in config_items}
        # 缓存30分钟
        cache.set(cache_key, configs, 30 * 60)
    
    return {'configs': configs}

def get_menus(request):
    # 获取当前用户
    user = request.user
    
    # 未登录用户返回空菜单列表
    if not user.is_authenticated:
        return {'menus': []}
    
    # 构建缓存键，包含用户ID和权限版本号
    # 这里使用用户ID作为缓存键的一部分，确保不同用户看到不同的菜单
    cache_key = f'menus_user_{user.id}'
    
    # 尝试从缓存获取菜单
    cached_menus = cache.get(cache_key)
    if cached_menus is not None:
        return {'menus': cached_menus}

    # 先获取所有状态正常的菜单，使用select_related优化外键查询
    all_menus = Menu.objects.filter(status=1).select_related('module').order_by('sort')

    # 过滤出可用的菜单
    available_menus = []
    for menu in all_menus:
        # 检查菜单是否可用
        if menu.is_available():
            available_menus.append(menu)

    # 超级管理员显示所有菜单
    if hasattr(user, 'is_superuser') and user.is_superuser:
        logger.debug(f"用户 {user.username} 是超级管理员，显示所有菜单")
        # 缓存结果
        cache.set(cache_key, available_menus, 10 * 60)  # 缓存10分钟
        return {'menus': available_menus}

    # 获取用户的所有权限
    user_permissions = set()
    if hasattr(user, 'get_all_permissions'):
        user_permissions = user.get_all_permissions()
    elif hasattr(user, 'permissions'):
        user_permissions = {f"{perm.content_type.app_label}.{perm.codename}" for perm in user.permissions.all()}

    # 构建菜单树结构，建立父子关系
    menu_dict = {menu.id: menu for menu in available_menus}
    menu_tree = {}
    
    # 先构建完整的菜单树
    for menu in available_menus:
        if menu.pid_id:
            parent = menu_dict.get(menu.pid_id)
            if parent:
                if not hasattr(parent, 'children'):
                    parent.children = []
                parent.children.append(menu)
        else:
            menu_tree[menu.id] = menu

    # 检查用户是否有权限访问菜单或其子菜单
    def has_menu_access(menu):
        # 如果用户有对应的权限，则有权限
        if menu.permission_required in user_permissions:
            return True
        # 检查子菜单是否有权限访问
        if hasattr(menu, 'children'):
            for submenu in menu.children:
                if has_menu_access(submenu):
                    return True
        # 如果菜单没有设置权限要求，检查用户是否有该应用的任何权限
        # 获取应用标签（从permission_required或src中提取）
        app_label = ''
        if menu.permission_required:
            app_label = menu.permission_required.split('.')[0]
        elif menu.src:
            # 从URL中提取应用标签
            url_parts = menu.src.strip('/').split('/')
            if url_parts:
                app_label = url_parts[0]
        
        # 如果能提取到应用标签，检查用户是否有该应用的任何权限
        if app_label:
            # 检查用户是否有该应用的任何权限
            for perm in user_permissions:
                if perm.startswith(f'{app_label}.'):
                    return True
                    
        return False

    # 过滤用户有权访问的菜单
    authorized_menus = []
    for menu_id, menu in menu_tree.items():
        if has_menu_access(menu):
            authorized_menus.append(menu)

    logger.debug(f"用户 {user.username} 有 {len(user_permissions)} 个权限，显示 {len(authorized_menus)} 个一级菜单")
    
    # 缓存结果
    cache.set(cache_key, authorized_menus, 10 * 60)  # 缓存10分钟
    
    return {'menus': authorized_menus}