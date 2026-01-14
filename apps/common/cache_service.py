import logging
from django.core.cache import cache
from django.conf import settings
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger('django')

CACHE_KEY_PREFIX = 'dtcall'


class CacheService:
    @staticmethod
    def make_key(*args, **kwargs) -> str:
        key_parts = [CACHE_KEY_PREFIX]
        for arg in args:
            if isinstance(arg, (int, float, str, bool)):
                key_parts.append(str(arg))
            elif isinstance(arg, (list, tuple)):
                key_parts.append('_'.join(str(x) for x in arg))
            elif isinstance(arg, dict):
                items = sorted(arg.items())
                key_parts.append('_'.join(f'{k}-{v}' for k, v in items))
            else:
                key_parts.append(str(hash(arg)))
        return ':'.join(key_parts)

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        try:
            result = cache.get(key)
            return result if result is not None else default
        except Exception as e:
            logger.warning(f'缓存读取失败 [{key[:50]}...]: {e}')
            return default

    @staticmethod
    def set(key: str, value: Any, timeout: int = 300) -> bool:
        try:
            cache.set(key, value, timeout)
            logger.debug(f'缓存写入成功: {key[:50]}... (超时: {timeout}s)')
            return True
        except Exception as e:
            logger.warning(f'缓存写入失败 [{key[:50]}...]: {e}')
            return False

    @staticmethod
    def delete(key: str) -> bool:
        try:
            cache.delete(key)
            return True
        except Exception as e:
            logger.warning(f'缓存删除失败 [{key[:50]}...]: {e}')
            return False

    @staticmethod
    def delete_pattern(pattern: str) -> int:
        try:
            from django.core.cache import caches

            redis_backend = caches['default']
            if hasattr(redis_backend, 'delete_pattern'):
                return redis_backend.delete_pattern(f'{CACHE_KEY_PREFIX}:{pattern}')
            return 0
        except Exception as e:
            logger.warning(f'批量缓存删除失败 [{pattern[:50]}...]: {e}')
            return 0

    @staticmethod
    def incr(key: str, delta: int = 1) -> Optional[int]:
        try:
            return cache.incr(key, delta)
        except ValueError:
            logger.warning(f'缓存增值失败 (键不存在): {key[:50]}...')
            return None
        except Exception as e:
            logger.warning(f'缓存增值失败 [{key[:50]}...]: {e}')
            return None

    @staticmethod
    def decr(key: str, delta: int = 1) -> Optional[int]:
        try:
            return cache.decr(key, delta)
        except ValueError:
            logger.warning(f'缓存减值失败 (键不存在): {key[:50]}...')
            return None
        except Exception as e:
            logger.warning(f'缓存减值失败 [{key[:50]}...]: {e}')
            return None


def cached_method(timeout: int = 300, key_prefix: str = ''):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = CacheService.make_key(
                key_prefix or func.__module__,
                func.__name__,
                args,
                kwargs
            )
            cached_result = CacheService.get(cache_key)
            if cached_result is not None:
                return cached_result

            result = func(*args, **kwargs)
            if result is not None:
                CacheService.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


class UserCache:
    PERMISSION_TIMEOUT = 5 * 60

    @staticmethod
    def get_permissions_key(user_id: int) -> str:
        return f'{CACHE_KEY_PREFIX}:user:{user_id}:permissions'

    @classmethod
    def get_permissions(cls, user_id: int) -> Optional[set]:
        return CacheService.get(cls.get_permissions_key(user_id))

    @classmethod
    def set_permissions(cls, user_id: int, permissions: set) -> bool:
        return CacheService.set(
            cls.get_permissions_key(user_id),
            permissions,
            cls.PERMISSION_TIMEOUT
        )

    @classmethod
    def invalidate_permissions(cls, user_id: int) -> bool:
        return CacheService.delete(cls.get_permissions_key(user_id))


class SystemCache:
    CONFIG_TIMEOUT = 30 * 60
    DICT_TIMEOUT = 60 * 60

    @staticmethod
    def get_config_key() -> str:
        return f'{CACHE_KEY_PREFIX}:system:configs'

    @staticmethod
    def get_dict_key(dict_type: str) -> str:
        return f'{CACHE_KEY_PREFIX}:system:dict:{dict_type}'

    @classmethod
    def get_configs(cls):
        return CacheService.get(cls.get_config_key())

    @classmethod
    def set_configs(cls, configs: dict) -> bool:
        return CacheService.set(cls.get_config_key(), configs, cls.CONFIG_TIMEOUT)

    @classmethod
    def invalidate_configs(cls) -> bool:
        return CacheService.delete(cls.get_config_key())

    @classmethod
    def get_dict(cls, dict_type: str):
        return CacheService.get(cls.get_dict_key(dict_type))

    @classmethod
    def set_dict(cls, dict_type: str, data: list) -> bool:
        return CacheService.set(
            cls.get_dict_key(dict_type),
            data,
            cls.DICT_TIMEOUT
        )

    @classmethod
    def invalidate_dict(cls, dict_type: str) -> bool:
        return CacheService.delete(cls.get_dict_key(dict_type))


class AICache:
    CONFIG_TIMEOUT = 15 * 60
    KNOWLEDGE_TIMEOUT = 60 * 60

    @staticmethod
    def get_config_key() -> str:
        return f'{CACHE_KEY_PREFIX}:ai:config'

    @staticmethod
    def get_knowledge_key(kb_id: int) -> str:
        return f'{CACHE_KEY_PREFIX}:ai:knowledge:{kb_id}'

    @staticmethod
    def get_model_key(model_id: int) -> str:
        return f'{CACHE_KEY_PREFIX}:ai:model:{model_id}'

    @classmethod
    def get_config(cls):
        return CacheService.get(cls.get_config_key())

    @classmethod
    def set_config(cls, config: dict) -> bool:
        return CacheService.set(cls.get_config_key(), config, cls.CONFIG_TIMEOUT)

    @classmethod
    def invalidate_config(cls) -> bool:
        return CacheService.delete(cls.get_config_key())

    @classmethod
    def get_knowledge(cls, kb_id: int):
        return CacheService.get(cls.get_knowledge_key(kb_id))

    @classmethod
    def set_knowledge(cls, kb_id: int, data: dict) -> bool:
        return CacheService.set(
            cls.get_knowledge_key(kb_id),
            data,
            cls.KNOWLEDGE_TIMEOUT
        )

    @classmethod
    def invalidate_knowledge(cls, kb_id: int) -> bool:
        return CacheService.delete(cls.get_knowledge_key(kb_id))

    @classmethod
    def get_model(cls, model_id: int):
        return CacheService.get(cls.get_model_key(model_id))

    @classmethod
    def set_model(cls, model_id: int, data: dict) -> bool:
        return CacheService.set(
            cls.get_model_key(model_id),
            data,
            cls.CONFIG_TIMEOUT
        )

    @classmethod
    def invalidate_model(cls, model_id: int) -> bool:
        return CacheService.delete(cls.get_model_key(model_id))


class MessageCache:
    COUNT_TIMEOUT = 2 * 60

    @staticmethod
    def get_unread_key(user_id: int) -> str:
        return f'{CACHE_KEY_PREFIX}:message:unread:{user_id}'

    @classmethod
    def get_unread_count(cls, user_id: int) -> int:
        count = CacheService.get(cls.get_unread_key(user_id))
        return count if count is not None else 0

    @classmethod
    def set_unread_count(cls, user_id: int, count: int) -> bool:
        return CacheService.set(
            cls.get_unread_key(user_id),
            count,
            cls.COUNT_TIMEOUT
        )

    @classmethod
    def incr_unread_count(cls, user_id: int, delta: int = 1) -> Optional[int]:
        key = cls.get_unread_key(user_id)
        current = cls.get_unread_count(user_id)
        if current is not None:
            return CacheService.incr(key, delta)
        CacheService.set(key, delta, cls.COUNT_TIMEOUT)
        return delta

    @classmethod
    def invalidate_unread_count(cls, user_id: int) -> bool:
        return CacheService.delete(cls.get_unread_key(user_id))


class CacheManager:
    @staticmethod
    def invalidate_user_related(user_id: int) -> None:
        UserCache.invalidate_permissions(user_id)
        MessageCache.invalidate_unread_count(user_id)
        logger.info(f'用户相关缓存已失效: user_id={user_id}')

    @staticmethod
    def invalidate_system_config() -> None:
        SystemCache.invalidate_configs()
        AICache.invalidate_config()
        logger.info('系统配置缓存已失效')

    @staticmethod
    def invalidate_ai_related(kb_id: int = None, model_id: int = None) -> None:
        if kb_id:
            AICache.invalidate_knowledge(kb_id)
        if model_id:
            AICache.invalidate_model(model_id)
        AICache.invalidate_config()
        logger.info(f'AI相关缓存已失效: kb_id={kb_id}, model_id={model_id}')
