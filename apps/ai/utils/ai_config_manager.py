"""
AI模型配置管理器
统一管理所有AI模型的配置、验证和选择
"""

import os
import logging
from typing import Dict, List, Optional
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from apps.ai.models import AIModelConfig
from apps.common.cache_service import AICache

logger = logging.getLogger(__name__)


class AIConfigManager:
    """AI模型配置管理器"""
    
    def __init__(self):
        self._configs = {}
        self._active_config = None
        self._loaded = False
        
    
    def _load_configs(self):
        """加载所有AI模型配置"""
        if self._loaded:
            return
        
        cached_config = AICache.get_config()
        if cached_config is not None:
            self._configs = cached_config
            self._loaded = True
            logger.debug("从缓存加载AI配置")
            return
            
        # 从数据库加载配置
        try:
            db_configs = AIModelConfig.objects.filter(is_active=True)
            for config in db_configs:
                self._configs[config.id] = {
                    'id': config.id,
                    'name': config.name,
                    'provider': config.provider,
                    'model_type': config.model_type,
                    'base_url': config.api_base,
                    'api_base': config.api_base,
                    'model_name': config.model_name,
                    'max_tokens': config.max_tokens,
                    'temperature': config.temperature,
                    'top_p': config.top_p,
                    'is_active': config.is_active,
                    'is_default': config.is_default,
                    'created_at': config.created_at,
                    'updated_at': config.updated_at
                }
            AICache.set_config(self._configs)
            self._loaded = True
            logger.info(f"从数据库加载AI配置并缓存，共{len(self._configs)}个配置")
        except Exception as e:
            logger.warning(f"加载数据库AI配置失败: {e}")
        
        # 从settings.py加载默认配置
        self._load_settings_configs()
    
    def _load_settings_configs(self):
        """从settings.py加载默认配置"""
        # 不再从settings加载配置，仅使用数据库中的配置
        # 这里可以留空，或者根据需要从数据库加载配置
        pass
    
    def get_all_configs(self) -> Dict:
        """获取所有配置"""
        if not self._loaded:
            self._load_configs()
        return self._configs.copy()
    
    def get_config(self, config_id: str) -> Optional[Dict]:
        """获取指定配置"""
        if not self._loaded:
            self._load_configs()
        return self._configs.get(config_id)
    
    def get_config_by_provider(self, provider: str) -> Optional[Dict]:
        """根据提供商获取配置"""
        if not self._loaded:
            self._load_configs()
        for config in self._configs.values():
            if config.get('provider') == provider and config.get('is_active'):
                return config
        return None
    
    def set_active_config(self, config_id: str) -> bool:
        """设置活动配置"""
        if config_id in self._configs:
            self._active_config = config_id
            logger.info(f"设置活动AI配置: {config_id}")
            return True
        return False
    
    def get_active_config(self) -> Optional[Dict]:
        """获取活动配置"""
        if not self._loaded:
            self._load_configs()
            
        if self._active_config:
            return self._configs.get(self._active_config)
        
        # 如果没有设置活动配置，返回第一个可用的配置
        for config_id, config in self._configs.items():
            if config.get('is_active'):
                self._active_config = config_id
                return config
        
        return None
    
    def validate_config(self, config_id: str) -> Dict:
        """验证配置有效性"""
        config = self.get_config(config_id)
        if not config:
            return {'valid': False, 'error': '配置不存在'}
        
        errors = []
        
        # 检查必要字段
        if not config.get('api_key'):
            errors.append('API密钥未配置')
        
        if not config.get('provider'):
            errors.append('提供商未配置')
        
        # 检查基础URL（某些提供商可能需要）
        provider = config.get('provider')
        if provider not in ['local'] and not config.get('base_url'):
            errors.append('基础URL未配置')
        
        # 提供商特定验证
        if provider == 'wenxin':
            if not config.get('api_key') or not config.get('default_params', {}).get('secret_key'):
                errors.append('文心一言需要API Key和Secret Key')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'config': config
        }
    
    def validate_all_configs(self) -> Dict:
        """验证所有配置"""
        if not self._loaded:
            self._load_configs()
        results = {}
        for config_id in self._configs:
            results[config_id] = self.validate_config(config_id)
        return results
    
    def get_available_providers(self) -> List[str]:
        """获取可用的提供商列表"""
        if not self._loaded:
            self._load_configs()
        providers = set()
        for config in self._configs.values():
            if config.get('is_active'):
                providers.add(config.get('provider'))
        return list(providers)
    
    def get_provider_configs(self, provider: str) -> List[Dict]:
        """获取指定提供商的所有配置"""
        if not self._loaded:
            self._load_configs()
        return [
            config for config in self._configs.values() 
            if config.get('provider') == provider and config.get('is_active')
        ]
    
    def refresh_configs(self):
        """刷新配置"""
        self._configs.clear()
        self._active_config = None
        self._loaded = False
        self._load_configs()
    
    def get_recommended_config(self, use_case: str = 'general') -> Optional[Dict]:
        """根据使用场景获取推荐配置"""
        # 根据使用场景推荐不同的提供商
        recommendations = {
            'general': ['openai', 'qwen', 'deepseek'],
            'chinese': ['qwen', 'wenxin', 'doubao'],
            'creative': ['openai', 'deepseek'],
            'local': ['local']
        }
        
        preferred_providers = recommendations.get(use_case, ['openai', 'qwen'])
        
        for provider in preferred_providers:
            config = self.get_config_by_provider(provider)
            if config:
                return config
        
        # 如果没有找到推荐配置，返回第一个可用的
        return self.get_active_config()


# 全局配置管理器实例（延迟实例化）
_ai_config_manager = None


def get_ai_config_manager() -> AIConfigManager:
    """获取AI配置管理器实例"""
    global _ai_config_manager
    if _ai_config_manager is None:
        _ai_config_manager = AIConfigManager()
    return _ai_config_manager


def validate_ai_configuration():
    """验证AI配置（项目启动时调用）"""
    # 检查是否在迁移过程中，避免数据库访问
    import sys
    if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
        logger.info("跳过AI配置验证（迁移过程中）")
        return {}
    
    # 在迁移过程中直接返回空结果，避免任何数据库访问
    if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
        return {}
    
    manager = get_ai_config_manager()
    validation_results = manager.validate_all_configs()
    
    valid_configs = 0
    for config_id, result in validation_results.items():
        if result['valid']:
            valid_configs += 1
        else:
            logger.warning(f"AI配置验证失败 [{config_id}]: {', '.join(result['errors'])}")
    
    if valid_configs == 0:
        logger.error("没有有效的AI配置，AI功能将不可用")
    else:
        logger.info(f"AI配置验证完成，{valid_configs}个配置有效")
    
    return validation_results


def get_ai_client_config(config_id: str = None) -> Dict:
    """获取AI客户端配置"""
    manager = get_ai_config_manager()
    
    if config_id:
        config = manager.get_config(config_id)
    else:
        config = manager.get_active_config()
    
    if not config:
        raise ImproperlyConfigured("没有可用的AI配置")
    
    # 验证配置
    validation = manager.validate_config(config['id'])
    if not validation['valid']:
        raise ImproperlyConfigured(f"AI配置无效: {', '.join(validation['errors'])}")
    
    return config


def validate_model_config(model_config):
    """验证模型配置对象"""
    from apps.ai.models import AIModelConfig
    
    if not isinstance(model_config, AIModelConfig):
        return {'success': False, 'error': '无效的模型配置对象'}
    
    errors = []
    
    # 检查必要字段
    if not model_config.name:
        errors.append('模型名称不能为空')
    
    if not model_config.provider:
        errors.append('提供商不能为空')
    
    if not model_config.api_key:
        errors.append('API密钥不能为空')
    
    # 检查基础URL（某些提供商可能需要）
    provider = model_config.provider
    if provider not in ['local'] and not model_config.api_base:
        errors.append('基础URL不能为空')
    
    # 提供商特定验证
    if provider == 'wenxin':
        # 检查文心一言的Secret Key
        # 文心一言的Secret Key现在存储在api_key中，或者需要单独配置
        pass
    
    # 检查模型类型
    if not model_config.model_type:
        errors.append('模型类型不能为空')
    
    if len(errors) > 0:
        return {
            'success': False, 
            'error': '配置验证失败',
            'details': '; '.join(errors)
        }
    
    # 如果基本验证通过，尝试连接测试
    try:
        # 导入AI客户端进行连接测试
        from apps.ai.utils.ai_client import AIClient
        
        # 创建AI客户端实例，使用模型配置ID
        client = AIClient(model_config_id=model_config.id)
    
        # 发送简单的测试消息
        test_message = "你好，这是一个连接测试。"
        response = client.chat_completion([{"role": "user", "content": test_message}])
        
        # 检查响应是否有效
        if response and isinstance(response, str) and len(response.strip()) > 0:
            return {
                'success': True,
                'details': f'配置验证成功 - 模型响应正常: {response}'
            }
        else:
            return {
                'success': False,
                'error': '连接测试失败',
                'details': f'模型响应为空或无效: {response}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': '连接测试异常',
            'details': f'连接测试过程中发生错误: {str(e)}'
        }