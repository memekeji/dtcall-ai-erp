from django.http import HttpResponseRedirect, JsonResponse

from apps.system.database_setup import get_database_state, is_setup_path, SETUP_PATH


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
        if state.needs_setup:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'code': 503,
                    'msg': '数据库未配置或不可用，请先完成数据库配置',
                    'data': {'redirect_url': SETUP_PATH},
                }, status=503)
            return HttpResponseRedirect(SETUP_PATH)

        return self.get_response(request)

    def _is_exempt(self, path):
        if is_setup_path(path):
            return True
        return any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES)
