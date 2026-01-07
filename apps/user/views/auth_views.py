from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
import logging
from captcha.models import CaptchaStore
from apps.user.models import SystemLog


def login_view(request):
    """登录页面视图"""
    # 登录用户自动重定向到仪表盘
    if request.user.is_authenticated:
        from django.conf import settings
        return redirect(settings.LOGIN_REDIRECT_URL)
    captcha_key = CaptchaStore.generate_key()
    return render(request, 'login.html', {'captcha_key': captcha_key})

def login_submit(request):
    """登录提交处理（支持AJAX）"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"登录请求: method={request.method}, is_ajax={request.headers.get('X-Requested-With') == 'XMLHttpRequest'}")
    logger.info(f"POST数据: {request.POST}")
    logger.info(f"CSRF验证: csrf_token={request.POST.get('csrfmiddlewaretoken')}, csrf_cookie={request.COOKIES.get('csrftoken')}")
    
    if request.method == 'POST':
        # 验证码验证
        captcha_key = request.POST.get('captcha_key')
        captcha_value = request.POST.get('captcha', '').strip().lower()
        logger.info(f"验证码验证: key={captcha_key}, value={captcha_value}")
        
        try:
            captcha = CaptchaStore.objects.get(hashkey=captcha_key, expiration__gt=timezone.now())
            logger.info(f"验证码查询: found={captcha is not None}, response={captcha.response}")
            if captcha.response != captcha_value:
                logger.info(f"验证码错误: expected={captcha.response}, got={captcha_value}")
                return JsonResponse({'code': 1, 'msg': '验证码错误'})
        except CaptchaStore.DoesNotExist:
            logger.info(f"验证码不存在或已过期")
            return JsonResponse({'code': 1, 'msg': '验证码已过期，请刷新'})

        # 用户认证
        username = request.POST.get('username')
        password = request.POST.get('password')
        logger.info(f"用户认证: username={username}, password_length={len(password) if password else 0}")
        
        user = authenticate(request, username=username, password=password)
        logger.info(f"认证结果: user={user}")
        
        if user:
            logger.info(f"用户登录前: is_authenticated={user.is_authenticated}, is_active={user.is_active}, employee_status={user.employee_status}")
            auth_login(request, user)
            logger.info(f"用户登录后: session_key={request.session.session_key}, auth_user_id={request.session.get('_auth_user_id')}")
            
            # 记录登录日志到SystemLog
            try:
                ip = request.META.get('REMOTE_ADDR', '')
                SystemLog.objects.create(
                    user=user,
                    log_type='login',
                    module='用户管理',
                    action='用户登录',
                    content=f'用户 {user.username} 登录系统',
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
                    created_at=timezone.now()
                )
                logger.info(f"登录日志记录成功")
            except Exception as e:
                logger.error(f'记录登录日志到SystemLog失败: {str(e)}')
            
            from django.conf import settings
            # 获取next参数，用于登录后重定向
            next_url = request.POST.get('next', settings.LOGIN_REDIRECT_URL)
            logger.info(f"登录成功，重定向到: {next_url}")
            return JsonResponse({'code': 0, 'msg': '登录成功', 'data': {'redirect_url': next_url}})
        else:
            logger.info(f"登录失败: 用户名或密码错误")
            return JsonResponse({'code': 1, 'msg': '用户名或密码错误'})
    return JsonResponse({'code': 1, 'msg': '无效的请求方法'})

def logout_view(request):
    """登出视图"""
    import logging
    logger = logging.getLogger('apps.user.views')
    
    # 获取当前用户并记录登出日志
    user = getattr(request, 'user', None)
    if user and not user.is_anonymous:
        try:
            ip = request.META.get('REMOTE_ADDR', '')
            SystemLog.objects.create(
                user=user,
                log_type='logout',
                module='用户管理',
                action='用户登出',
                content=f'用户 {user.username} 登出系统',
                ip_address=ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
                created_at=timezone.now()
            )
        except Exception as e:
            logger.error(f'记录登出日志到SystemLog失败: {str(e)}')
    
    # 执行登出操作
    auth_logout(request)
    
    # 重定向到登录页面，携带next参数回到首页
    next_url = request.GET.get('next', '/')
    # 使用reverse_lazy来获取带命名空间的登录URL
    from django.urls import reverse_lazy
    redirect_url = f'{reverse_lazy("user:login")}?next={next_url}'
    
    logger.critical(f'Final logout response - Redirecting to: {redirect_url}')
    return redirect(redirect_url)