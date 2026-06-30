from django.http import HttpResponseRedirect, JsonResponse

from apps.system.database_setup import (
    SETUP_PATH,
    get_database_state,
    has_initial_admin,
    is_setup_path,
)


class DatabaseSetupMiddleware:
    """Redirect requests to the database setup page when the database is not ready."""

    EXEMPT_PREFIXES = (
        SETUP_PATH,
        '/static/',
        '/media/',
        '/favicon.ico',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if self._is_exempt(path):
            return self.get_response(request)

        state = get_database_state()
        if state.needs_setup or not has_initial_admin():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'code': 503,
                    'msg': '系统尚未完成初始化，请先完成数据库和管理员配置',
                    'data': {'redirect_url': SETUP_PATH},
                }, status=503)
            return HttpResponseRedirect(SETUP_PATH)

        return self.get_response(request)

    def _is_exempt(self, path):
        if is_setup_path(path):
            return True
        return any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES)
