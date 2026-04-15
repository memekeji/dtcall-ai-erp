"""
工作流异常处理服务
提供完整的异常分类、处理和恢复机制
"""

import logging
import traceback
import asyncio
from typing import Dict, Any, List, Optional, Type, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from django.utils import timezone

from apps.ai.models import (
    AIWorkflow, WorkflowNode, AILog
)

logger = logging.getLogger(__name__)


class ExceptionSeverity(Enum):
    """异常严重程度"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ExceptionCategory(Enum):
    """异常分类"""
    WORKFLOW = "workflow"
    NODE = "node"
    DATA = "data"
    SYSTEM = "system"
    SECURITY = "security"
    NETWORK = "network"


class RecoveryStrategy(Enum):
    """恢复策略"""
    RETRY = "retry"
    SKIP = "skip"
    FALLBACK = "fallback"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"
    STOP = "stop"


@dataclass
class ExceptionInfo:
    """异常信息"""
    exception_type: str
    message: str
    category: ExceptionCategory
    severity: ExceptionSeverity
    timestamp: datetime
    node_id: Optional[str] = None
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    recovery_attempts: int = 0
    last_recovery_attempt: Optional[datetime] = None


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    retryable_exceptions: List[Type[Exception]] = field(default_factory=list)
    non_retryable_exceptions: List[Type[Exception]] = field(
        default_factory=list)


@dataclass
class CircuitBreakerState:
    """熔断器状态"""
    state: str = "closed"
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    success_count: int = 0
    half_open_successes: int = 0


class WorkflowException(Exception):
    """工作流基础异常"""

    def __init__(self, message: str, context: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.timestamp = timezone.now()


class WorkflowNotFoundError(WorkflowException):
    """工作流不存在异常"""


class WorkflowValidationError(WorkflowException):
    """工作流验证异常"""


class WorkflowExecutionError(WorkflowException):
    """工作流执行异常"""


class NodeException(WorkflowException):
    """节点异常"""

    def __init__(self, message: str, node_id: str = None,
                 context: Dict[str, Any] = None):
        super().__init__(message, context)
        self.node_id = node_id


class NodeNotFoundError(NodeException):
    """节点不存在异常"""


class NodeConfigError(NodeException):
    """节点配置异常"""


class NodeExecutionError(NodeException):
    """节点执行异常"""


class NodeTimeoutError(NodeException):
    """节点超时异常"""


class DataException(WorkflowException):
    """数据处理异常"""


class DataValidationError(DataException):
    """数据验证异常"""


class DataTransformationError(DataException):
    """数据转换异常"""


class DataNotFoundError(DataException):
    """数据未找到异常"""


class SystemException(WorkflowException):
    """系统级异常"""


class DatabaseError(SystemException):
    """数据库异常"""


class NetworkError(SystemException):
    """网络异常"""


class ResourceExhaustedError(SystemException):
    """资源耗尽异常"""


class CircuitBreaker:
    """熔断器"""

    _instances: Dict[str, 'CircuitBreaker'] = {}
    _lock = asyncio.Lock()

    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_time: int = 300, half_open_requests: int = 3):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.half_open_requests = half_open_requests
        self.state = CircuitBreakerState()

    @classmethod
    async def get_instance(cls, name: str, **kwargs) -> 'CircuitBreaker':
        """获取熔断器实例"""
        if name not in cls._instances:
            async with cls._lock:
                if name not in cls._instances:
                    cls._instances[name] = CircuitBreaker(name, **kwargs)
        return cls._instances[name]

    async def call(self, func: Callable, *args, **kwargs):
        """执行函数调用（带熔断保护）"""
        if not self._can_execute():
            raise CircuitBreakerOpenError(
                f"熔断器 '{self.name}' 已打开，拒绝执行"
            )

        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _can_execute(self) -> bool:
        """检查是否可以执行"""
        if self.state.state == "closed":
            return True

        if self.state.state == "open":
            if self._should_attempt_reset():
                self.state.state = "half_open"
                return True
            return False

        if self.state.state == "half_open":
            return self.state.half_open_successes < self.half_open_requests

        return False

    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置"""
        if self.state.last_failure_time is None:
            return True

        return (
            timezone.now() -
            self.state.last_failure_time).total_seconds() >= self.recovery_time

    def _on_success(self) -> None:
        """处理成功"""
        if self.state.state == "half_open":
            self.state.half_open_successes += 1
            self.state.success_count += 1

            if self.state.half_open_successes >= self.half_open_requests:
                self.state.state = "closed"
                self.state.failure_count = 0
                logger.info(f"熔断器 '{self.name}' 已关闭")
        else:
            self.state.success_count += 1

    def _on_failure(self) -> None:
        """处理失败"""
        self.state.failure_count += 1
        self.state.last_failure_time = timezone.now()

        if self.state.state == "half_open":
            self.state.state = "open"
            self.state.half_open_successes = 0
            logger.warning(f"熔断器 '{self.name}' 在半开状态失败，已重新打开")
        elif self.state.failure_count >= self.failure_threshold:
            self.state.state = "open"
            logger.warning(
                f"熔断器 '{self.name}' 因失败次数超过阈值已打开，"
                f"failure_count={self.state.failure_count}"
            )


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""


class ExceptionClassifier:
    """异常分类器"""

    _exception_hierarchy = {
        WorkflowException: {
            'category': ExceptionCategory.WORKFLOW,
            'subclasses': {
                WorkflowNotFoundError: ExceptionCategory.WORKFLOW,
                WorkflowValidationError: ExceptionCategory.WORKFLOW,
                WorkflowExecutionError: ExceptionCategory.WORKFLOW,
                NodeException: {
                    'category': ExceptionCategory.NODE,
                    'subclasses': {
                        NodeNotFoundError: ExceptionCategory.NODE,
                        NodeConfigError: ExceptionCategory.NODE,
                        NodeExecutionError: ExceptionCategory.NODE,
                        NodeTimeoutError: ExceptionCategory.NODE
                    }
                },
                DataException: {
                    'category': ExceptionCategory.DATA,
                    'subclasses': {
                        DataValidationError: ExceptionCategory.DATA,
                        DataTransformationError: ExceptionCategory.DATA,
                        DataNotFoundError: ExceptionCategory.DATA
                    }
                },
                SystemException: {
                    'category': ExceptionCategory.SYSTEM,
                    'subclasses': {
                        DatabaseError: ExceptionCategory.SYSTEM,
                        NetworkError: ExceptionCategory.SYSTEM,
                        ResourceExhaustedError: ExceptionCategory.SYSTEM
                    }
                }
            }
        }
    }

    _severity_mapping = {
        WorkflowNotFoundError: ExceptionSeverity.HIGH,
        WorkflowValidationError: ExceptionSeverity.MEDIUM,
        WorkflowExecutionError: ExceptionSeverity.HIGH,
        NodeNotFoundError: ExceptionSeverity.CRITICAL,
        NodeConfigError: ExceptionSeverity.MEDIUM,
        NodeExecutionError: ExceptionSeverity.HIGH,
        NodeTimeoutError: ExceptionSeverity.MEDIUM,
        DataValidationError: ExceptionSeverity.LOW,
        DataTransformationError: ExceptionSeverity.MEDIUM,
        DataNotFoundError: ExceptionSeverity.LOW,
        DatabaseError: ExceptionSeverity.CRITICAL,
        NetworkError: ExceptionSeverity.HIGH,
        ResourceExhaustedError: ExceptionSeverity.CRITICAL
    }

    @classmethod
    def classify(cls, exception: Exception) -> tuple:
        """分类异常"""
        exception_type = type(exception)

        # 查找分类
        category = cls._find_category(exception_type, cls._exception_hierarchy)

        # 查找严重程度
        severity = cls._severity_mapping.get(
            exception_type, ExceptionSeverity.MEDIUM)

        # 检查是否包含在异常链中
        current = exception
        while current is not None:
            current_type = type(current)
            if current_type in cls._severity_mapping:
                severity = cls._severity_mapping[current_type]
                break
            current = current.__cause__ if hasattr(
                current, '__cause__') else None

        return category, severity

    @classmethod
    def _find_category(
            cls,
            exception_type: Type[Exception],
            hierarchy: Dict,
            current_category: ExceptionCategory = None) -> ExceptionCategory:
        """递归查找异常分类"""
        for exc_class, mapping in hierarchy.items():
            if issubclass(exception_type, exc_class):
                if isinstance(mapping, dict):
                    if 'category' in mapping:
                        return mapping['category']
                    if 'subclasses' in mapping:
                        return cls._find_category(
                            exception_type,
                            mapping['subclasses'],
                            current_category or mapping.get(
                                'category',
                                ExceptionCategory.SYSTEM))
                else:
                    return mapping

        return current_category or ExceptionCategory.SYSTEM


class ExceptionHandler:
    """异常处理器"""

    def __init__(self):
        self.retry_config = RetryConfig()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.notification_callbacks: List[Callable] = []

    def register_notification_callback(self, callback: Callable):
        """注册通知回调"""
        self.notification_callbacks.append(callback)

    def handle_exception(self, exception: Exception,
                         context: Dict[str, Any] = None) -> ExceptionInfo:
        """
        处理异常

        处理流程：
        1. 异常分类
        2. 日志记录
        3. 通知触发
        4. 恢复策略选择
        5. 上下文更新
        """
        # Step 1: 异常分类
        category, severity = ExceptionClassifier.classify(exception)

        # Step 2: 构建异常信息
        exception_info = ExceptionInfo(
            exception_type=type(exception).__name__,
            message=str(exception),
            category=category,
            severity=severity,
            timestamp=timezone.now(),
            context_data=context or {},
            stack_trace=traceback.format_exc()
        )

        # Step 3: 记录日志
        self._log_exception(exception_info)

        # Step 4: 触发通知
        self._send_notifications(exception_info)

        # Step 5: 记录到数据库
        self._save_to_database(exception_info)

        return exception_info

    def _log_exception(self, exception_info: ExceptionInfo):
        """记录异常日志"""
        log_level = {
            ExceptionSeverity.LOW: logging.WARNING,
            ExceptionSeverity.MEDIUM: logging.ERROR,
            ExceptionSeverity.HIGH: logging.ERROR,
            ExceptionSeverity.CRITICAL: logging.CRITICAL
        }

        logger.log(
            log_level[exception_info.severity],
            f"异常发生 - "
            f"类型: {exception_info.exception_type}, "
            f"分类: {exception_info.category.value}, "
            f"严重程度: {exception_info.severity.name}, "
            f"消息: {exception_info.message}",
            exc_info=True
        )

    def _send_notifications(self, exception_info: ExceptionInfo):
        """发送通知"""
        for callback in self.notification_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(exception_info))
                else:
                    callback(exception_info)
            except Exception as e:
                logger.error(f"发送异常通知失败: {e}")

    def _save_to_database(self, exception_info: ExceptionInfo):
        """保存到数据库"""
        try:
            AILog.objects.create(
                log_type='workflow_execution',
                content={
                    'exception_type': exception_info.exception_type,
                    'category': exception_info.category.value,
                    'severity': exception_info.severity.name,
                    'message': exception_info.message,
                    'context': exception_info.context_data,
                    'stack_trace': exception_info.stack_trace
                }
            )
        except Exception as e:
            logger.error(f"保存异常日志到数据库失败: {e}")

    def should_retry(self, exception_info: ExceptionInfo) -> bool:
        """判断是否应该重试"""
        exception_type = exception_info.exception_type

        # 检查是否在可重试列表中
        for exc_class in self.retry_config.retryable_exceptions:
            if exception_type == exc_class.__name__:
                return True

        # 检查是否在不重试列表中
        for exc_class in self.retry_config.non_retryable_exceptions:
            if exception_type == exc_class.__name__:
                return False

        # 根据异常类型判断
        if exception_info.category in [
                ExceptionCategory.NETWORK,
                ExceptionCategory.SYSTEM]:
            return exception_info.severity not in [ExceptionSeverity.CRITICAL]

        return False

    def get_retry_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        delay = self.retry_config.initial_delay * (
            self.retry_config.backoff_factor ** attempt
        )
        return min(delay, self.retry_config.max_delay)

    async def execute_with_retry(self, func: Callable,
                                 exception_info: ExceptionInfo,
                                 *args, **kwargs):
        """执行带重试的函数"""
        if not self.should_retry(exception_info):
            raise exception_info

        last_exception = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                last_exception = e
                exception_info.recovery_attempts = attempt + 1
                exception_info.last_recovery_attempt = timezone.now()

                logger.warning(
                    f"第 {attempt + 1} 次重试失败: {e}"
                )

                if attempt < self.retry_config.max_retries:
                    delay = self.get_retry_delay(attempt)
                    await asyncio.sleep(delay)

        raise last_exception

    def get_recovery_strategy(
            self,
            exception_info: ExceptionInfo) -> RecoveryStrategy:
        """获取恢复策略"""
        # 根据异常类型和严重程度选择恢复策略
        if exception_info.category == ExceptionCategory.SECURITY:
            return RecoveryStrategy.STOP

        if exception_info.category == ExceptionCategory.SYSTEM:
            if exception_info.severity == ExceptionSeverity.CRITICAL:
                return RecoveryStrategy.ROLLBACK
            return RecoveryStrategy.FALLBACK

        if exception_info.category == ExceptionCategory.NODE:
            if exception_info.severity == ExceptionSeverity.CRITICAL:
                return RecoveryStrategy.STOP
            return RecoveryStrategy.RETRY

        if exception_info.category == ExceptionCategory.DATA:
            return RecoveryStrategy.SKIP

        return RecoveryStrategy.RETRY


class NodeExceptionHandler:
    """节点级异常处理器"""

    def __init__(self):
        self.global_handler = ExceptionHandler()
        self.fallback_handlers: Dict[str, Callable] = {}

    def register_fallback_handler(self, node_type: str, handler: Callable):
        """注册回退处理器"""
        self.fallback_handlers[node_type] = handler

    async def execute_node(self, node: WorkflowNode,
                           context: Dict[str, Any],
                           node_func: Callable) -> Dict[str, Any]:
        """执行节点（带异常处理）"""
        try:
            # 执行节点逻辑
            if asyncio.iscoroutinefunction(node_func):
                result = await node_func()
            else:
                result = node_func()

            return {
                'status': 'completed',
                'result': result,
                'error': None
            }

        except Exception as e:
            # 获取异常信息
            exception_info = self.global_handler.handle_exception(
                e,
                {
                    'node_id': str(node.id),
                    'node_type': node.node_type,
                    'node_name': node.name,
                    **context
                }
            )

            # 获取恢复策略
            strategy = self.global_handler.get_recovery_strategy(
                exception_info)

            # 根据恢复策略处理
            if strategy == RecoveryStrategy.RETRY:
                return await self._handle_retry(node, context, node_func)

            elif strategy == RecoveryStrategy.SKIP:
                return self._handle_skip(node, context, exception_info)

            elif strategy == RecoveryStrategy.FALLBACK:
                return self._handle_fallback(node, context, exception_info)

            elif strategy == RecoveryStrategy.STOP:
                raise

            else:
                return {
                    'status': 'failed',
                    'result': None,
                    'error': str(e),
                    'strategy': strategy.value
                }

    async def _handle_retry(self, node: WorkflowNode,
                            context: Dict[str, Any],
                            node_func: Callable) -> Dict[str, Any]:
        """处理重试"""
        node_func_placeholder = node_func

        async def wrapped_func():
            if asyncio.iscoroutinefunction(node_func):
                return await node_func()
            return node_func()

        try:
            await self.global_handler.execute_with_retry(
                wrapped_func,
                ExceptionInfo(
                    exception_type=type(node_func_placeholder).__name__,
                    message="Node execution failed",
                    category=ExceptionCategory.NODE,
                    severity=ExceptionSeverity.MEDIUM,
                    timestamp=timezone.now()
                )
            )

            return {
                'status': 'completed',
                'result': None,
                'error': None
            }

        except Exception as e:
            return {
                'status': 'failed',
                'result': None,
                'error': str(e),
                'strategy': 'retry_exhausted'
            }

    def _handle_skip(self, node: WorkflowNode,
                     context: Dict[str, Any],
                     exception_info: ExceptionInfo) -> Dict[str, Any]:
        """处理跳过"""
        logger.warning(
            f"节点 '{node.name}' 执行失败，已跳过: {exception_info.message}"
        )

        return {
            'status': 'skipped',
            'result': None,
            'error': exception_info.message,
            'strategy': 'skip'
        }

    def _handle_fallback(self, node: WorkflowNode,
                         context: Dict[str, Any],
                         exception_info: ExceptionInfo) -> Dict[str, Any]:
        """处理回退"""
        fallback_func = self.fallback_handlers.get(node.node_type)

        if fallback_func:
            try:
                result = fallback_func(context)
                return {
                    'status': 'fallback',
                    'result': result,
                    'error': None,
                    'strategy': 'fallback'
                }
            except Exception as e:
                logger.error(f"回退处理失败: {e}")

        # 默认回退值
        default_fallback = node.config.get(
            'error_handling', {}).get('fallback_value')

        return {
            'status': 'fallback',
            'result': default_fallback,
            'error': exception_info.message,
            'strategy': 'default_fallback'
        }


class WorkflowExceptionHandler:
    """工作流级异常处理器"""

    def __init__(self):
        self.node_handler = NodeExceptionHandler()
        self.global_handler = ExceptionHandler()

    async def execute_workflow_with_error_handling(
        self,
        workflow_id: str,
        execution_context: Dict[str, Any],
        execute_node_func: Callable
    ) -> Dict[str, Any]:
        """
        执行工作流（带异常处理）

        异常处理策略：
        1. 节点级异常：尝试重试 -> 跳过/回退 -> 继续执行
        2. 工作流级异常：记录错误 -> 停止执行 -> 标记失败
        3. 系统级异常：熔断保护 -> 回退策略 -> 告警通知
        """
        execution_result = {
            'status': 'running',
            'workflow_id': workflow_id,
            'node_results': {},
            'error_info': None,
            'completed_at': None
        }

        try:
            # 获取工作流节点列表
            workflow = AIWorkflow.objects.get(id=workflow_id)
            nodes = list(
                workflow.nodes.filter(
                    is_active=True).order_by(
                    'position_x',
                    'position_y'))

            for node in nodes:
                try:
                    # 执行节点
                    node_result = await self.node_handler.execute_node(
                        node,
                        execution_context,
                        lambda n=node: execute_node_func(n, execution_context)
                    )

                    execution_result['node_results'][str(
                        node.id)] = node_result

                    # 更新执行上下文
                    if node_result.get('status') == 'completed':
                        execution_context.update(node_result.get('result', {}))

                    # 处理节点失败
                    if node_result.get('status') == 'failed':
                        if not node.config.get(
                                'error_handling', {}).get(
                                'continue_on_error', False):
                            raise WorkflowExecutionError(
                                f"节点 '{node.name}' 执行失败，停止工作流执行"
                            )

                except Exception as e:
                    exception_info = self.global_handler.handle_exception(
                        e,
                        {
                            'workflow_id': workflow_id,
                            'node_id': str(node.id),
                            'node_name': node.name
                        }
                    )

                    execution_result['error_info'] = {
                        'exception_type': exception_info.exception_type,
                        'message': exception_info.message,
                        'severity': exception_info.severity.name
                    }

                    if node.config.get(
                            'error_handling', {}).get(
                            'continue_on_error', False):
                        continue
                    else:
                        execution_result['status'] = 'failed'
                        break

            # 工作流完成
            execution_result['status'] = 'completed'
            execution_result['completed_at'] = timezone.now()

        except WorkflowExecutionError as e:
            execution_result['status'] = 'failed'
            execution_result['error_info'] = {
                'exception_type': 'WorkflowExecutionError',
                'message': str(e)
            }
            execution_result['completed_at'] = timezone.now()

        except Exception as e:
            exception_info = self.global_handler.handle_exception(e, {
                'workflow_id': workflow_id
            })

            execution_result['status'] = 'failed'
            execution_result['error_info'] = {
                'exception_type': exception_info.exception_type,
                'message': exception_info.message,
                'severity': exception_info.severity.name
            }
            execution_result['completed_at'] = timezone.now()

        return execution_result


# 初始化全局异常处理器
exception_handler = ExceptionHandler()
workflow_exception_handler = WorkflowExceptionHandler()
