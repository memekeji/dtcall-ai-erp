"""
自定义会话中间件
处理会话相关的异常，提供友好的错误处理和用户体验
"""
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware as DjangoSessionMiddleware
from django.contrib.sessions.exceptions import SessionInterrupted
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.contrib.auth import logout
from django.urls import reverse
import logging

logger = logging.getLogger('django')


class SessionMiddleware(DjangoSessionMiddleware):
    """
    自定义会话中间件
    继承自 Django 的 SessionMiddleware，在保存会话时捕获异常并优雅处理
    """

    def process_response(self, request, response):
        try:
            return super().process_response(request, response)
        except SessionInterrupted:
            return self._handle_session_interrupted(request, response)
        except Exception as e:
            if 'session' in str(e).lower() or 'SessionInterrupted' in str(type(e).__name__):
                return self._handle_session_interrupted(request, response)
            raise

    def _handle_session_interrupted(self, request, response):
        """
        处理会话中断异常
        当会话在请求处理过程中被删除时（如用户登出或会话过期）
        """
        logger.warning(
            f"会话中断: 用户可能在并发请求中登出。路径: {request.path}, "
            f"用户: {getattr(request.user, 'username', 'Anonymous')}, "
            f"方法: {request.method}"
        )

        is_ajax = request.META.get('HTTP_X_REQUESTED_WITH', '') == 'XMLHttpRequest'
        login_url = reverse('user:login') + f'?next={request.path}'

        if is_ajax:
            return JsonResponse({
                'code': 401,
                'msg': '登录已过期，请重新登录',
                'data': {
                    'redirect_url': login_url
                }
            }, status=401)

        referer = request.META.get('HTTP_REFERER', '')
        host = request.META.get('HTTP_HOST', '')
        is_iframe = bool(referer and host in referer)

        if is_iframe:
            logout(request)
            return HttpResponse(
                f'<script>window.top.location.href = "{login_url}";</script>'
            )

        if hasattr(request, 'session'):
            try:
                request.session.flush()
            except Exception:
                pass

        logout(request)
        return HttpResponseRedirect(login_url)
