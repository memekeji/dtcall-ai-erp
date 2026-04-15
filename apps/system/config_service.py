from apps.user.models import SystemConfiguration


class ConfigService:
    """系统配置服务，用于集中管理和读取系统配置"""

    def __init__(self):
        self._config_cache = {}
        self._loaded = False

    def _load_configs(self):
        """加载所有系统配置到缓存"""
        try:
            configs = SystemConfiguration.objects.filter(is_active=True)
            self._config_cache = {
                config.key: config.value for config in configs}
            self._loaded = True
        except Exception:
            # 捕获数据库连接异常，避免在项目初始化时崩溃
            self._config_cache = {}
            self._loaded = False

    def get_config(self, key, default=None):
        """获取配置值"""
        # 如果还没有加载或缓存中没有，尝试加载
        if not self._loaded or key not in self._config_cache:
            self._load_configs()
        return self._config_cache.get(key, default)

    def get_bool_config(self, key, default=False):
        """获取布尔类型配置值"""
        value = self.get_config(key, str(default))
        return value.lower() in ('true', '1', 'yes', 'on')

    def get_int_config(self, key, default=0):
        """获取整数类型配置值"""
        value = self.get_config(key, str(default))
        try:
            return int(value)
        except ValueError:
            return default

    def get_float_config(self, key, default=0.0):
        """获取浮点数类型配置值"""
        value = self.get_config(key, str(default))
        try:
            return float(value)
        except ValueError:
            return default

    def refresh_configs(self):
        """刷新配置缓存"""
        self._load_configs()

    def __getitem__(self, key):
        """支持字典式访问"""
        return self.get_config(key)

    def __contains__(self, key):
        """支持in操作符"""
        if not self._loaded:
            self._load_configs()
        return key in self._config_cache


# 创建全局配置服务实例 - 不会立即访问数据库
config_service = ConfigService()
