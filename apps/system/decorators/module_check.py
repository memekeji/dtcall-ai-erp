from django.shortcuts import redirect
from django.http import JsonResponse
from django.contrib import messages
from apps.user.models import SystemModule


def get_module_from_request(request):
    """
    从请求URL中获取对应的模块
    规则：
    - URL格式：/app/module/...
    - 例如：/system/config/ -> module code: 'system'
    - 例如：/customer/list/ -> module code: 'customer'
    """
    path = request.path
    if not path or not path.startswith('/'):
        return None

    parts = path.strip('/').split('/')
    if len(parts) < 1:
        return None

    app = parts[0]

    # 查找对应的模块
    try:
        # 首先尝试完全匹配code（不考虑is_active，后面统一检查）
        module = SystemModule.objects.filter(code=app).first()
        if module:
            return module

        # 尝试匹配name
        module = SystemModule.objects.filter(name__icontains=app).first()
        if module:
            return module

        # 处理子路径
        if len(parts) >= 2:
            sub_module = parts[1]
            full_code = f"{app}_{sub_module}" or f"{app}.{sub_module}"
            module = SystemModule.objects.filter(code=full_code).first()
            if module:
                return module

            # 尝试匹配name包含子模块
            from django.db.models import Q
            module = SystemModule.objects.filter(
                Q(name__icontains=app) | Q(name__icontains=sub_module)
            ).first()
            if module:
                return module
    except Exception:
        pass

    return None


def module_active_required():
    """
    模块启用状态检查装饰器
    检查请求对应的模块是否处于启用状态
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            # 获取请求对应的模块
            module = get_module_from_request(request)

            # 如果找不到模块，允许访问（可能是系统核心模块）
            if not module:
                return view_func(request, *args, **kwargs)

            # 检查模块是否启用
            if not module.is_active:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    # AJAX请求返回JSON响应
                    return JsonResponse({
                        'code': 403,
                        'msg': f'模块"{module.name}"已禁用，无法访问'
                    })
                else:
                    # 普通请求显示错误信息
                    messages.error(request, f'模块"{module.name}"已禁用，无法访问')
                    return redirect('system:dashboard')

            # 模块启用，继续执行视图
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


class ModuleActiveCheckMixin:
    """
    模块启用状态检查混入类
    用于基于类的视图
    """

    def dispatch(self, request, *args, **kwargs):
        # 获取请求对应的模块
        module = get_module_from_request(request)

        # 如果找不到模块，允许访问（可能是系统核心模块）
        if not module:
            return super().dispatch(request, *args, **kwargs)

        # 检查模块是否启用
        if not module.is_active:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # AJAX请求返回JSON响应
                return JsonResponse({
                    'code': 403,
                    'msg': f'模块"{module.name}"已禁用，无法访问'
                })
            else:
                # 普通请求显示错误信息
                messages.error(request, f'模块"{module.name}"已禁用，无法访问')
                return redirect('system:dashboard')

        # 模块启用，继续执行视图
        return super().dispatch(request, *args, **kwargs)
