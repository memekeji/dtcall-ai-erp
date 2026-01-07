# 原项目dtcall/utils.py核心工具函数
from django.conf import settings

def get_site_config():
    """获取站点配置（与原项目逻辑一致）"""
    return getattr(settings, 'SITE_CONFIG', {})

#实现验证码加法方法
def captcha_challenge():
    import random
    num1 = random.randint(1, 9)
    num2 = random.randint(1, 9)
    return f'{num1} + {num2}', str(num1 + num2)


from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

def get_system_config(section, key):
    # 缓存键
    cache_key = f'system_config_{section}_{key}'
    
    # 尝试从缓存获取
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    try:
        from apps.user.models import SystemConfiguration
        
        # 默认配置
        default_web_config = {
            'logo': 'static/img/logo.png',
            'small_logo': 'static/img/syslogo_small.png',
            'web_title': 'DTCALL管理系统',
            'keywords': '企业管理,OA系统,项目管理',
            'description': '高效的企业管理解决方案',
            'admin_title': '后台管理'
        }
        
        # 如果请求完整的web配置
        if section == 'web' and key == 'web_config':
            # 从数据库获取所有web相关配置
            db_configs = SystemConfiguration.objects.filter(is_active=True)
            
            # 构建完整的web配置，先使用默认值
            web_config = default_web_config.copy()
            
            # 用数据库值覆盖默认值
            for config in db_configs:
                if config.key in web_config:
                    web_config[config.key] = config.value
            
            # 缓存30分钟
            cache.set(cache_key, web_config, 30 * 60)
            return web_config
        
        # 如果请求单个配置项
        if section == 'web' and key in default_web_config:
            # 先从数据库查找
            try:
                config = SystemConfiguration.objects.get(key=key, is_active=True)
                result = config.value
            except SystemConfiguration.DoesNotExist:
                # 数据库中没有，使用默认值
                result = default_web_config[key]
            
            # 缓存30分钟
            cache.set(cache_key, result, 30 * 60)
            return result
        
        # 其他情况，尝试从数据库直接查找
        try:
            config = SystemConfiguration.objects.get(key=key, is_active=True)
            result = config.value
        except SystemConfiguration.DoesNotExist:
            result = ''
        
        # 缓存30分钟
        cache.set(cache_key, result, 30 * 60)
        return result
    except Exception as e:
        logger.error(f"获取系统配置失败: {str(e)}")
        
        # 发生错误时，返回默认值
        if section == 'web' and key == 'web_config':
            cache.set(cache_key, default_web_config, 30 * 60)
            return default_web_config
        if section == 'web' and key in default_web_config:
            result = default_web_config[key]
            cache.set(cache_key, result, 30 * 60)
            return result
        
        return ''


class PermissionsPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 先获取响应
        response = self.get_response(request)
        
        # 允许unload事件以解决LayUI的权限策略错误
        # 同时设置Content-Security-Policy以确保兼容性
        response["Permissions-Policy"] = "unload=*"
        
        # 检查是否已有Content-Security-Policy头
        if "Content-Security-Policy" not in response:
            # 添加常用CDN域名到白名单以解决大量文件使用CDN引用的问题
            response["Content-Security-Policy"] = "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://code.jquery.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; img-src 'self' data: https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; connect-src 'self';"
        
        return response