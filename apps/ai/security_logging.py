"""
安全日志配置

提供日志脱敏功能，保护敏感信息不被记录到日志中。
"""

import logging
import re
from typing import Any, Dict


class SensitiveDataFilter(logging.Filter):
    """敏感数据日志过滤器"""
    
    SENSITIVE_FIELDS = {
        'api_key', 'api_key', 'password', 'secret', 'token', 
        'access_key', 'private_key', 'credential', 'auth',
        'authorization', 'apikey', 'secret_key'
    }
    
    SENSITIVE_PATTERNS = [
        r'sk-[a-zA-Z0-9]{20,}',  # OpenAI API Key格式
        r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',  # JWT格式
        r'A[aA-Z0-9]{20,}',  # Azure格式
        r'AIza[0-9A-Za-z\-_]{35}',  # Google API Key格式
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """过滤敏感信息"""
        try:
            if isinstance(record.msg, str):
                record.msg = self._mask_sensitive_data(record.msg)
            
            if isinstance(record.args, tuple):
                new_args = []
                for arg in record.args:
                    if isinstance(arg, str):
                        new_args.append(self._mask_sensitive_data(arg))
                    elif isinstance(arg, dict):
                        new_args.append(self._mask_dict_values(arg))
                    else:
                        new_args.append(arg)
                record.args = tuple(new_args)
            
            if hasattr(record, 'request') and record.request:
                self._mask_request_data(record)
                
        except Exception:
            pass
        
        return True
    
    def _mask_sensitive_data(self, text: str) -> str:
        """脱敏文本中的敏感数据"""
        if not isinstance(text, str):
            return text
        
        # 脱敏敏感字段模式
        for field in self.SENSITIVE_FIELDS:
            patterns = [
                rf'({field}["\']?\s*[:=]\s*["\']?)([^"\'\s,}}]+)',
                rf'(" {field}":\s*")([^"]+)',
                rf"('{ field }':\s*')([^']+)",
            ]
            for pattern in patterns:
                text = re.sub(pattern, lambda m: m.group(1) + '***', text, flags=re.IGNORECASE)
        
        # 脱敏特定格式的敏感数据
        for pattern in self.SENSITIVE_PATTERNS:
            text = re.sub(pattern, '***MASKED***', text)
        
        return text
    
    def _mask_dict_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏字典中的敏感值"""
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in self.SENSITIVE_FIELDS):
                result[key] = '***MASKED***'
            elif isinstance(value, dict):
                result[key] = self._mask_dict_values(value)
            elif isinstance(value, str):
                result[key] = self._mask_sensitive_data(value)
            else:
                result[key] = value
        
        return result
    
    def _mask_request_data(self, record):
        """脱敏请求数据中的敏感信息"""
        try:
            if hasattr(record, 'getMessage'):
                msg = record.getMessage()
                if isinstance(msg, str):
                    masked = self._mask_sensitive_data(msg)
                    record.msg = masked
        except Exception:
            pass


def setup_security_logging():
    """配置安全日志"""
    # 创建敏感数据过滤器
    sensitive_filter = SensitiveDataFilter()
    
    # 添加到所有处理器
    for handler in logging.root.handlers:
        handler.addFilter(sensitive_filter)
    
    # 配置AI模块日志
    ai_logger = logging.getLogger('apps.ai')
    ai_logger.addFilter(sensitive_filter)
    
    return sensitive_filter


# 便捷函数：安全日志记录
def log_with_masking(logger: logging.Logger, level: int, message: str, 
                     extra: Dict[str, Any] = None, exc_info=None):
    """安全地记录日志，自动脱敏敏感信息"""
    extra = extra or {}
    
    # 确保敏感信息被脱敏
    masked_extra = {}
    sensitive_filter = SensitiveDataFilter()
    
    for key, value in extra.items():
        if isinstance(value, str):
            masked_extra[key] = sensitive_filter._mask_sensitive_data(value)
        elif isinstance(value, dict):
            masked_extra[key] = sensitive_filter._mask_dict_values(value)
        else:
            masked_extra[key] = value
    
    logger.log(level, message, extra=masked_extra, exc_info=exc_info)


# 在应用启动时自动配置
setup_security_logging()
