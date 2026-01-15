"""
工作流权限管理与安全控制服务
提供企业级权限管理和安全防护能力
"""

import hashlib
import hmac
import logging
import secrets
import time
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, AuthenticationFailed

from apps.ai.models import AIWorkflow
from apps.user.models import Admin

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """权限级别"""
    NONE = 0
    VIEW = 1
    EDIT = 2
    EXECUTE = 3
    MANAGE = 4
    OWNER = 5


class SecurityEventType(Enum):
    """安全事件类型"""
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_API_KEY = "invalid_api_key"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    CONTENT_VIOLATION = "content_violation"
    DATA_LEAKAGE = "data_leakage"


@dataclass
class APIKey:
    """API密钥"""
    key_id: str
    key_hash: str
    user_id: int
    workflow_ids: List[str]
    permissions: List[str]
    rate_limit: int
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    is_active: bool = True


@dataclass
class SecurityEvent:
    """安全事件"""
    event_type: SecurityEventType
    timestamp: datetime
    user_id: Optional[int]
    ip_address: Optional[str]
    details: Dict[str, Any]
    severity: int


class WorkflowPermissionService:
    """工作流权限服务"""
    
    def __init__(self):
        self.permission_cache: Dict[str, Dict[str, PermissionLevel]] = {}
        self.cache_ttl = 300
        self.role_permissions: Dict[str, Set[str]] = {
            'admin': {'view', 'edit', 'execute', 'manage', 'delete', 'share'},
            'editor': {'view', 'edit', 'execute'},
            'viewer': {'view'},
            'operator': {'view', 'execute'}
        }
    
    def check_permission(
        self,
        user_id: int,
        workflow_id: str,
        permission: str
    ) -> bool:
        """检查用户权限"""
        cache_key = f"{user_id}_{workflow_id}"
        
        if cache_key in self.permission_cache:
            cached_perms = self.permission_cache[cache_key]
            if permission in cached_perms:
                return cached_perms[permission] >= PermissionLevel.EXECUTE.value
        
        workflow = AIWorkflow.objects.filter(id=workflow_id).first()
        if not workflow:
            return False
        
        has_permission = False
        
        if str(workflow.created_by_id) == str(user_id):
            has_permission = True
        else:
            from apps.ai.models import WorkflowPermission
            perms = WorkflowPermission.objects.filter(
                workflow_id=workflow_id,
                user_id=user_id,
                is_active=True
            ).first()
            
            if perms:
                role = perms.role or 'viewer'
                role_perms = self.role_permissions.get(role, set())
                has_permission = permission in role_perms
        
        self.permission_cache[cache_key] = {
            'view': PermissionLevel.VIEW.value,
            'edit': PermissionLevel.EDIT.value if has_permission else PermissionLevel.NONE.value,
            'execute': PermissionLevel.EXECUTE.value if has_permission else PermissionLevel.NONE.value,
            'manage': PermissionLevel.MANAGE.value if has_permission else PermissionLevel.NONE.value
        }
        
        return has_permission
    
    def grant_permission(
        self,
        workflow_id: str,
        user_id: int,
        role: str,
        granted_by: int
    ) -> bool:
        """授予权限"""
        if role not in self.role_permissions:
            logger.error(f"无效的角色: {role}")
            return False
        
        from apps.ai.models import WorkflowPermission
        
        with transaction.atomic():
            perm, created = WorkflowPermission.objects.update_or_create(
                workflow_id=workflow_id,
                user_id=user_id,
                defaults={
                    'role': role,
                    'granted_by_id': granted_by,
                    'is_active': True,
                    'created_at': timezone.now()
                }
            )
        
        self._invalidate_cache(workflow_id, user_id)
        
        logger.info(f"权限授予成功: 用户 {user_id} 获得角色 {role} 在工作流 {workflow_id}")
        return True
    
    def revoke_permission(self, workflow_id: str, user_id: int) -> bool:
        """撤销权限"""
        from apps.ai.models_enhanced import WorkflowPermission
        
        deleted = WorkflowPermission.objects.filter(
            workflow_id=workflow_id,
            user_id=user_id
        ).delete()
        
        if deleted[0] > 0:
            self._invalidate_cache(workflow_id, user_id)
            return True
        return False
    
    def get_user_permissions(self, user_id: int, workflow_id: str) -> Dict[str, bool]:
        """获取用户权限"""
        workflow = AIWorkflow.objects.filter(id=workflow_id).first()
        if not workflow:
            return {}
        
        is_owner = str(workflow.created_by_id) == str(user_id)
        
        from apps.ai.models_enhanced import WorkflowPermission
        perms = WorkflowPermission.objects.filter(
            workflow_id=workflow_id,
            user_id=user_id,
            is_active=True
        ).first()
        
        role = perms.role if perms else ('owner' if is_owner else None)
        role_perms = self.role_permissions.get(role, set()) if role else set()
        
        return {
            'view': True,
            'edit': is_owner or 'edit' in role_perms,
            'execute': is_owner or 'execute' in role_perms,
            'manage': is_owner or 'manage' in role_perms,
            'delete': is_owner,
            'share': is_owner or 'share' in role_perms,
            'is_owner': is_owner
        }
    
    def get_workflow_access_list(self, workflow_id: str) -> List[Dict[str, Any]]:
        """获取工作流访问列表"""
        from apps.ai.models_enhanced import WorkflowPermission
        
        workflow = AIWorkflow.objects.filter(id=workflow_id).first()
        if not workflow:
            return []
        
        access_list = []
        
        access_list.append({
            'user_id': workflow.created_by_id,
            'role': 'owner',
            'permissions': ['view', 'edit', 'execute', 'manage', 'delete', 'share'],
            'is_owner': True
        })
        
        perms = WorkflowPermission.objects.filter(
            workflow_id=workflow_id,
            is_active=True
        ).select_related('user')
        
        for perm in perms:
            role_perms = self.role_permissions.get(perm.role, set())
            access_list.append({
                'user_id': perm.user_id,
                'user_name': perm.user.name if perm.user else 'Unknown',
                'role': perm.role,
                'permissions': list(role_perms),
                'granted_by': perm.granted_by_id,
                'granted_at': perm.created_at.isoformat(),
                'is_owner': False
            })
        
        return access_list
    
    def _invalidate_cache(self, workflow_id: str, user_id: int):
        """使缓存失效"""
        cache_key = f"{user_id}_{workflow_id}"
        self.permission_cache.pop(cache_key, None)
    
    def clear_cache(self):
        """清除所有缓存"""
        self.permission_cache.clear()


class APIKeyManagementService:
    """API密钥管理服务"""
    
    def __init__(self):
        self.api_keys: Dict[str, APIKey] = {}
        self.key_usage: Dict[str, List[datetime]] = {}
        self.rate_limit_window = 60
    
    def create_api_key(
        self,
        user_id: int,
        workflow_ids: List[str],
        permissions: List[str],
        rate_limit: int = 100,
        expires_in_days: Optional[int] = None
    ) -> Dict[str, str]:
        """创建API密钥"""
        key_id = secrets.token_hex(8)
        key_value = f"dk_{secrets.token_hex(24)}"
        key_hash = self._hash_key(key_value)
        
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)
        
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            user_id=user_id,
            workflow_ids=workflow_ids,
            permissions=permissions,
            rate_limit=rate_limit,
            created_at=datetime.now(),
            expires_at=expires_at,
            last_used_at=None,
            is_active=True
        )
        
        self.api_keys[key_id] = api_key
        self.key_usage[key_id] = []
        
        logger.info(f"API密钥创建成功: {key_id}")
        
        return {
            'key_id': key_id,
            'key_value': key_value,
            'expires_at': expires_at.isoformat() if expires_at else None
        }
    
    def validate_api_key(self, key_value: str) -> Optional[APIKey]:
        """验证API密钥"""
        key_hash = self._hash_key(key_value)
        
        for key_id, api_key in self.api_keys.items():
            if api_key.key_hash == key_hash:
                if not api_key.is_active:
                    logger.warning(f"API密钥已禁用: {key_id}")
                    return None
                
                if api_key.expires_at and api_key.expires_at < datetime.now():
                    logger.warning(f"API密钥已过期: {key_id}")
                    return None
                
                api_key.last_used_at = datetime.now()
                return api_key
        
        return None
    
    def check_rate_limit(self, key_id: str) -> bool:
        """检查速率限制"""
        if key_id not in self.api_keys:
            return False
        
        api_key = self.api_keys[key_id]
        now = datetime.now()
        
        window_start = now - timedelta(seconds=self.rate_limit_window)
        
        if key_id not in self.key_usage:
            self.key_usage[key_id] = []
        
        self.key_usage[key_id] = [
            t for t in self.key_usage[key_id] if t > window_start
        ]
        
        if len(self.key_usage[key_id]) >= api_key.rate_limit:
            logger.warning(f"API密钥速率超限: {key_id}")
            return False
        
        self.key_usage[key_id].append(now)
        return True
    
    def revoke_api_key(self, key_id: str) -> bool:
        """撤销API密钥"""
        if key_id in self.api_keys:
            self.api_keys[key_id].is_active = False
            logger.info(f"API密钥已撤销: {key_id}")
            return True
        return False
    
    def get_key_info(self, key_id: str) -> Optional[Dict[str, Any]]:
        """获取密钥信息"""
        if key_id not in self.api_keys:
            return None
        
        api_key = self.api_keys[key_id]
        return {
            'key_id': api_key.key_id,
            'user_id': api_key.user_id,
            'workflow_ids': api_key.workflow_ids,
            'permissions': api_key.permissions,
            'rate_limit': api_key.rate_limit,
            'created_at': api_key.created_at.isoformat(),
            'expires_at': api_key.expires_at.isoformat() if api_key.expires_at else None,
            'last_used_at': api_key.last_used_at.isoformat() if api_key.last_used_at else None,
            'is_active': api_key.is_active
        }
    
    def _hash_key(self, key: str) -> str:
        """哈希密钥"""
        return hashlib.sha256(key.encode()).hexdigest()


class ContentSecurityService:
    """内容安全服务"""
    
    def __init__(self):
        self.sensitive_words: Set[str] = set()
        self.forbidden_patterns: List[str] = []
        self.warning_patterns: List[str] = []
    
    def load_sensitive_words(self, words: List[str]):
        """加载敏感词"""
        self.sensitive_words.update(w.lower() for w in words)
    
    def add_forbidden_pattern(self, pattern: str):
        """添加禁止模式"""
        self.forbidden_patterns.append(pattern)
    
    def add_warning_pattern(self, pattern: str):
        """添加警告模式"""
        self.warning_patterns.append(pattern)
    
    def check_content(self, content: str) -> Dict[str, Any]:
        """检查内容安全性"""
        result = {
            'is_safe': True,
            'violations': [],
            'warnings': [],
            'suggestions': []
        }
        
        content_lower = content.lower()
        
        for word in self.sensitive_words:
            if word in content_lower:
                result['is_safe'] = False
                result['violations'].append({
                    'type': 'sensitive_word',
                    'matched': word,
                    'severity': 'high'
                })
        
        import re
        for pattern in self.forbidden_patterns:
            if re.search(pattern, content):
                result['is_safe'] = False
                result['violations'].append({
                    'type': 'forbidden_pattern',
                    'matched': pattern,
                    'severity': 'high'
                })
        
        for pattern in self.warning_patterns:
            matches = re.findall(pattern, content)
            if matches:
                result['warnings'].append({
                    'type': 'warning_pattern',
                    'matched': pattern,
                    'count': len(matches)
                })
        
        return result
    
    def sanitize_content(self, content: str) -> str:
        """内容脱敏"""
        sanitized = content
        
        for word in self.sensitive_words:
            sanitized = re.sub(
                word, 
                '*' * len(word), 
                sanitized, 
                flags=re.IGNORECASE
            )
        
        return sanitized


class AuditLogService:
    """审计日志服务"""
    
    def __init__(self):
        self.log_buffer: List[Dict[str, Any]] = []
        self.batch_size = 100
        self.flush_interval = 60
    
    def log_operation(
        self,
        user_id: Optional[int],
        operation_type: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        """记录操作日志"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'user_id': user_id,
            'operation_type': operation_type,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'details': details or {},
            'ip_address': ip_address
        }
        
        self.log_buffer.append(log_entry)
        
        if len(self.log_buffer) >= self.batch_size:
            self.flush_logs()
    
    def flush_logs(self):
        """刷新日志到数据库"""
        from apps.ai.models import AIWorkflowAuditLog
        
        if not self.log_buffer:
            return
        
        logs_to_create = []
        for entry in self.log_buffer:
            logs_to_create.append(AIWorkflowAuditLog(
                user_id=entry['user_id'],
                operation_type=entry['operation_type'],
                resource_type=entry['resource_type'],
                resource_id=entry['resource_id'],
                details=entry['details'],
                ip_address=entry['ip_address']
            ))
        
        try:
            AIWorkflowAuditLog.objects.bulk_create(logs_to_create)
            self.log_buffer.clear()
        except Exception as e:
            logger.error(f"审计日志写入失败: {e}")
    
    def query_logs(
        self,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """查询审计日志"""
        from apps.ai.models import AIWorkflowAuditLog
        
        query = Q()
        
        if user_id:
            query &= Q(user_id=user_id)
        if resource_type:
            query &= Q(resource_type=resource_type)
        if resource_id:
            query &= Q(resource_id=resource_id)
        if start_time:
            query &= Q(created_at__gte=start_time)
        if end_time:
            query &= Q(created_at__lte=end_time)
        
        logs = AIWorkflowAuditLog.objects.filter(query).order_by('-created_at')[:limit]
        
        return [
            {
                'id': log.id,
                'user_id': log.user_id,
                'operation_type': log.operation_type,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'details': log.details,
                'ip_address': log.ip_address,
                'created_at': log.created_at.isoformat()
            }
            for log in logs
        ]


permission_service = WorkflowPermissionService()
api_key_service = APIKeyManagementService()
content_security_service = ContentSecurityService()
audit_log_service = AuditLogService()
