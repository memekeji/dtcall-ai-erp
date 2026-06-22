"""
操作日志自动记录中间件
自动记录已登录用户的所有业务操作到 SystemLog 表中
"""
import json
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone


SKIP_URL_PREFIXES = [
    '/static/',
    '/media/',
    '/admin/',
    '/captcha/',
    '/get-new-captcha/',
    '/favicon.ico',
    '/setup/database/',
    '/message/unread-count/',
    '/api/token/',
]

SKIP_URL_SUFFIXES = [
    '/datalist/',
]

SKIP_URL_KEYWORDS = [
    'datalist',
    'unread-count',
]

METHOD_LOG_TYPE_MAP = {
    'GET': 'view',
    'POST': 'create',
    'PUT': 'update',
    'PATCH': 'update',
    'DELETE': 'delete',
}

URL_MODULE_MAP = {
    '/user/': '用户管理',
    '/system/': '系统管理',
    '/project/': '项目管理',
    '/task/': '任务管理',
    '/contract/': '合同管理',
    '/customer/': '客户管理',
    '/finance/': '财务管理',
    '/production/': '生产管理',
    '/approval/': '审批流程',
    '/message/': '消息通知',
    '/disk/': '云盘管理',
    '/oa/': 'OA办公',
    '/personal/': '个人办公',
    '/position/': '职位管理',
    '/department/': '部门管理',
    '/inventory/': '库存管理',
    '/ai/': 'AI智能',
    '/home/': '首页',
    '/enterprise/': '企业管理',
    '/common/': '公共服务',
    '/reimbursement/': '报销管理',
    '/basedata/': '基础数据',
    '/adm/': '系统管理',
}


def get_module_from_url(url_path):
    for prefix, module_name in URL_MODULE_MAP.items():
        if url_path.startswith(prefix):
            return module_name
    return '其他模块'


def should_skip_logging(url_path):
    for prefix in SKIP_URL_PREFIXES:
        if url_path.startswith(prefix):
            return True
    for suffix in SKIP_URL_SUFFIXES:
        if url_path.endswith(suffix):
            return True
    for keyword in SKIP_URL_KEYWORDS:
        if keyword in url_path:
            return True
    return False


def get_action_description(request):
    method = request.method
    path = request.path
    if path in ('/user/login/', '/user/login_submit/'):
        return '用户登录'
    if path == '/logout/':
        return '用户退出'
    method_descriptions = {
        'GET': f'查看页面: {path}',
        'POST': f'提交数据: {path}',
        'PUT': f'更新数据: {path}',
        'PATCH': f'部分更新: {path}',
        'DELETE': f'删除数据: {path}',
    }
    return method_descriptions.get(method, f'{method}请求: {path}')


class OperationLogMiddleware(MiddlewareMixin):

    def process_response(self, request, response):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return response

        url_path = request.path

        if should_skip_logging(url_path):
            return response

        if response.status_code < 200 or response.status_code >= 400:
            return response

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if request.method == 'GET':
                return response

        try:
            from apps.user.models import SystemLog

            method = request.method
            log_type = METHOD_LOG_TYPE_MAP.get(method, 'other')
            module = get_module_from_url(url_path)
            action = get_action_description(request)
            ip_address = self._get_client_ip(request)
            user_agent = request.headers.get('User-Agent', '')[:500]

            SystemLog.objects.create(
                user=request.user,
                log_type=log_type,
                module=module,
                action=action,
                content='',
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception:
            pass

        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.headers.get('X-Forwarded-For', '')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.headers.get('X-Real-IP', '')
        if not ip:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        if ip == '::1':
            ip = '127.0.0.1'
        return ip
