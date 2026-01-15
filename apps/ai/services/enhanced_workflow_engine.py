"""
增强型工作流引擎
整合Dify和扣子平台的核心优势
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from apps.ai.models import (
    AIWorkflow, WorkflowNode, WorkflowConnection, 
    AIWorkflowExecution, NodeExecution, WorkflowVariable
)
from apps.ai.processors import get_processor_for_node_type
from apps.ai.services.ai_analysis_service import AIAnalysisService

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """执行模式"""
    SYNC = "sync"
    ASYNC = "async"
    PARALLEL = "parallel"


class NodeStatus(Enum):
    """节点执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class WorkflowStatus(Enum):
    """工作流执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class ExecutionContext:
    """执行上下文"""
    execution_id: str
    workflow_id: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    node_results: Dict[str, Any] = field(default_factory=dict)
    error_info: Optional[Dict[str, Any]] = None
    started_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeExecutionState:
    """节点执行状态"""
    node_id: str
    status: NodeStatus = NodeStatus.PENDING
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    execution_time: float = 0.0


class EnhancedWorkflowEngine:
    """增强型工作流引擎
    
    整合Dify和扣子的核心优势：
    1. 支持同步/异步/并行三种执行模式
    2. 完善的异常处理和重试机制
    3. 细粒度的超时控制
    4. 完整的执行链路追踪
    5. 性能监控和优化
    """
    
    def __init__(self, max_workers: int = 10, default_timeout: int = 300):
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.ai_service = AIAnalysisService()
        self._node_locks: Dict[str, asyncio.Lock] = {}
        self._execution_subscribers: Set[Callable] = set()
        
    def subscribe_execution(self, callback: Callable):
        """订阅执行事件"""
        self._execution_subscribers.add(callback)
        
    def unsubscribe_execution(self, callback: Callable):
        """取消订阅执行事件"""
        self._execution_subscribers.discard(callback)
        
    async def _notify_subscribers(self, event_type: str, data: Dict[str, Any]):
        """通知订阅者"""
        for callback in self._execution_subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, data)
                else:
                    callback(event_type, data)
            except Exception as e:
                logger.error(f"通知订阅者失败: {e}")
    
    @transaction.atomic
    def create_execution(self, workflow_id: str, user_id: int, input_data: Dict[str, Any]) -> AIWorkflowExecution:
        """创建执行实例"""
        workflow = AIWorkflow.objects.get(id=workflow_id)
        
        execution = AIWorkflowExecution.objects.create(
            workflow=workflow,
            created_by_id=user_id,
            input_data=input_data,
            status='pending'
        )
        
        logger.info(f"创建工作流执行: {execution.id}")
        return execution
    
    async def execute_workflow(
        self, 
        execution_id: str,
        execution_mode: ExecutionMode = ExecutionMode.SYNC,
        timeout: Optional[int] = None
    ) -> AIWorkflowExecution:
        """执行工作流
        
        Args:
            execution_id: 执行实例ID
            execution_mode: 执行模式
            timeout: 超时时间（秒）
        """
        execution = AIWorkflowExecution.objects.get(id=execution_id)
        workflow = execution.workflow
        
        if workflow.status != 'published':
            raise ValueError("只能执行已发布的工作流")
        
        timeout = timeout or self.default_timeout
        
        execution.status = 'running'
        execution.started_at = timezone.now()
        execution.save()
        
        try:
            context = ExecutionContext(
                execution_id=str(execution.id),
                workflow_id=str(workflow.id),
                input_data=execution.input_data or {}
            )
            
            await self._notify_subscribers('workflow_started', {
                'execution_id': str(execution.id),
                'workflow_id': str(workflow.id)
            })
            
            if execution_mode == ExecutionMode.SYNC:
                result = await self._execute_sync(context, workflow, timeout)
            elif execution_mode == ExecutionMode.ASYNC:
                result = await self._execute_async(context, workflow, timeout)
            elif execution_mode == ExecutionMode.PARALLEL:
                result = await self._execute_parallel(context, workflow, timeout)
            else:
                result = await self._execute_sync(context, workflow, timeout)
            
            execution.status = 'completed'
            execution.output_data = result.output_data
            execution.completed_at = timezone.now()
            
            await self._notify_subscribers('workflow_completed', {
                'execution_id': str(execution.id),
                'output_data': result.output_data
            })
            
        except asyncio.TimeoutError:
            execution.status = 'timeout'
            execution.error_message = f"工作流执行超时（{timeout}秒）"
            execution.completed_at = timezone.now()
            
            await self._notify_subscribers('workflow_timeout', {
                'execution_id': str(execution.id),
                'timeout': timeout
            })
            
        except Exception as e:
            logger.error(f"工作流执行失败: {e}", exc_info=True)
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.completed_at = timezone.now()
            
            await self._notify_subscribers('workflow_failed', {
                'execution_id': str(execution.id),
                'error': str(e)
            })
        
        execution.save()
        return execution
    
    async def _execute_sync(
        self, 
        context: ExecutionContext, 
        workflow: AIWorkflow,
        timeout: int
    ) -> ExecutionContext:
        """同步执行工作流"""
        nodes = {str(node.id): node for node in workflow.nodes.filter(is_active=True)}
        connections = list(workflow.connections.all())
        
        execution_graph = self._build_execution_graph(nodes, connections)
        
        start_node = self._find_start_node(nodes)
        if not start_node:
            raise ValueError("工作流中找不到开始节点")
        
        visited = set()
        async def execute_node_recursive(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)
            
            node = nodes.get(node_id)
            if not node:
                return
            
            await self._execute_node_with_retry(node, context, workflow, timeout)
            
            for target_id, condition in execution_graph.get(node_id, []):
                if self._evaluate_condition(condition, context):
                    await execute_node_recursive(target_id)
        
        await execute_node_recursive(str(start_node.id))
        
        context.output_data = context.variables.copy()
        return context
    
    async def _execute_async(self, context: ExecutionContext, workflow: AIWorkflow, timeout: int):
        """异步执行工作流"""
        nodes = {str(node.id): node for node in workflow.nodes.filter(is_active=True)}
        connections = list(workflow.connections.all())
        
        execution_graph = self._build_execution_graph(nodes, connections)
        start_node = self._find_start_node(nodes)
        
        if not start_node:
            raise ValueError("工作流中找不到开始节点")
        
        task_queue = [str(start_node.id)]
        visited = set()
        
        while task_queue:
            node_id = task_queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            
            node = nodes.get(node_id)
            if not node:
                continue
            
            await self._execute_node_with_retry(node, context, workflow, timeout)
            
            for target_id, condition in execution_graph.get(node_id, []):
                if self._evaluate_condition(condition, context):
                    task_queue.append(target_id)
        
        context.output_data = context.variables.copy()
        return context
    
    async def _execute_parallel(self, context: ExecutionContext, workflow: AIWorkflow, timeout: int):
        """并行执行工作流"""
        nodes = {str(node.id): node for node in workflow.nodes.filter(is_active=True)}
        connections = list(workflow.connections.all())
        
        execution_graph = self._build_execution_graph(nodes, connections)
        start_node = self._find_start_node(nodes)
        
        if not start_node:
            raise ValueError("工作流中找不到开始节点")
        
        level_map = self._build_node_levels(execution_graph, str(start_node.id))
        max_level = max(level_map.values()) if level_map else 0
        
        for level in range(max_level + 1):
            level_nodes = [nid for nid, lvl in level_map.items() if lvl == level]
            tasks = []
            
            for node_id in level_nodes:
                node = nodes.get(node_id)
                if node:
                    task = asyncio.create_task(
                        self._execute_node_with_retry(node, context, workflow, timeout)
                    )
                    tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks)
        
        context.output_data = context.variables.copy()
        return context
    
    async def _execute_node_with_retry(
        self,
        node: WorkflowNode,
        context: ExecutionContext,
        workflow: AIWorkflow,
        timeout: int,
        max_retries: int = 3
    ) -> NodeExecutionState:
        """执行节点（带重试机制）"""
        node_state = NodeExecutionState(node_id=str(node.id))
        
        await self._notify_subscribers('node_started', {
            'execution_id': context.execution_id,
            'node_id': str(node.id),
            'node_name': node.name
        })
        
        for attempt in range(max_retries):
            try:
                node_state.status = NodeStatus.RUNNING
                node_state.started_at = datetime.now()
                
                node_execution = NodeExecution.objects.create(
                    workflow_execution_id=context.execution_id,
                    node=node,
                    status='running',
                    input_data=context.variables.copy()
                )
                
                processor = get_processor_for_node_type(node.node_type)
                if processor:
                    result = await asyncio.wait_for(
                        processor.execute_async(node.config, context.variables),
                        timeout=timeout
                    )
                else:
                    result = await self._execute_node_legacy(node, context.variables)
                
                node_state.status = NodeStatus.COMPLETED
                node_state.output_data = result
                node_state.completed_at = datetime.now()
                node_state.execution_time = (node_state.completed_at - node_state.started_at).total_seconds()
                
                context.node_results[str(node.id)] = result
                context.variables.update(result)
                
                node_execution.status = 'completed'
                node_execution.output_data = result
                node_execution.completed_at = timezone.now()
                node_execution.execution_time = node_state.execution_time
                node_execution.save()
                
                await self._notify_subscribers('node_completed', {
                    'execution_id': context.execution_id,
                    'node_id': str(node.id),
                    'node_name': node.name,
                    'execution_time': node_state.execution_time
                })
                
                return node_state
                
            except asyncio.TimeoutError:
                node_state.retry_count = attempt + 1
                logger.warning(f"节点执行超时: {node.name}, 重试次数: {attempt + 1}")
                
                if attempt >= max_retries - 1:
                    node_state.status = NodeStatus.FAILED
                    node_state.error_message = f"节点执行超时（{timeout}秒）"
                    await self._handle_node_failure(node, context, node_state)
                    
            except Exception as e:
                node_state.retry_count = attempt + 1
                logger.error(f"节点执行失败: {node.name}, 错误: {e}, 重试次数: {attempt + 1}")
                
                if attempt >= max_retries - 1:
                    node_state.status = NodeStatus.FAILED
                    node_state.error_message = str(e)
                    await self._handle_node_failure(node, context, node_state)
                
                await asyncio.sleep(2 ** attempt)
        
        return node_state
    
    async def _handle_node_failure(
        self,
        node: WorkflowNode,
        context: ExecutionContext,
        node_state: NodeExecutionState
    ):
        """处理节点执行失败"""
        node_execution = NodeExecution.objects.filter(
            workflow_execution_id=context.execution_id,
            node=node
        ).order_by('-created_at').first()
        
        if node_execution:
            node_execution.status = 'failed'
            node_execution.error_message = node_state.error_message
            node_execution.completed_at = timezone.now()
            node_execution.save()
        
        await self._notify_subscribers('node_failed', {
            'execution_id': context.execution_id,
            'node_id': str(node.id),
            'node_name': node.name,
            'error': node_state.error_message
        })
    
    async def _execute_node_legacy(self, node: WorkflowNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """遗留节点执行逻辑"""
        node_type = node.node_type
        config = node.config
        output = {}
        
        if node_type == 'start':
            output = context.copy()
        elif node_type == 'end':
            output = context.copy()
        elif node_type == 'ai_model':
            model_name = config.get('model_name', 'gpt-3.5-turbo')
            prompt = config.get('prompt', '')
            for key, value in context.items():
                prompt = prompt.replace(f'{{{{{key}}}}}', str(value))
            result = self.ai_service.generate_content(prompt, model_name)
            output['ai_result'] = result
        elif node_type == 'condition':
            condition_type = config.get('condition_type', 'if_else')
            condition_variable = config.get('condition_variable')
            if condition_variable in context:
                output[f'{condition_variable}_result'] = context[condition_variable]
        elif node_type == 'api_call':
            output = await self._execute_api_call(config, context)
        elif node_type == 'data_input':
            output = self._execute_data_input(config, context)
        elif node_type == 'data_output':
            output = self._execute_data_output(config, context)
        
        return output
    
    async def _execute_api_call(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行API调用"""
        import aiohttp
        
        output = {}
        try:
            url = config.get('url', '')
            method = config.get('method', 'GET')
            headers = config.get('headers', {})
            body = config.get('body', '')
            
            for key, value in context.items():
                url = url.replace(f'{{{{{key}}}}}', str(value))
                if isinstance(body, str):
                    body = body.replace(f'{{{{{key}}}}}', str(value))
            
            timeout = aiohttp.ClientTimeout(total=config.get('timeout', 30))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method, url, headers=headers, data=body) as response:
                    output['status_code'] = response.status
                    output['response_time'] = response.elapsed.total_seconds()
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        output['response_body'] = await response.json()
                    else:
                        output['response_body'] = await response.text()
                    output['api_call_success'] = response.status < 400
                    
        except Exception as e:
            output['api_call_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_data_input(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据输入"""
        output = {}
        data_source = config.get('data_source', 'manual')
        input_data = config.get('input_data', '')
        
        if data_source == 'manual':
            output['input_data'] = input_data
        elif data_source == 'variable':
            var_name = config.get('variable_name', '')
            output['input_data'] = context.get(var_name)
        
        output['data_input_success'] = True
        return output
    
    def _execute_data_output(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据输出"""
        output = {}
        output_type = config.get('output_type', 'variable')
        output_variable = config.get('output_variable', '')
        
        if output_type == 'variable' and output_variable:
            output['output'] = context.get(output_variable)
        
        output['data_output_success'] = True
        return output
    
    def _build_execution_graph(self, nodes: Dict[str, WorkflowNode], connections: List[WorkflowConnection]) -> Dict[str, List[tuple]]:
        """构建执行图"""
        graph = {}
        for conn in connections:
            source_id = str(conn.source_node.id)
            target_id = str(conn.target_node.id)
            
            if source_id not in graph:
                graph[source_id] = []
            
            condition = conn.config.get('condition') if conn.config else None
            graph[source_id].append((target_id, condition))
        
        return graph
    
    def _build_node_levels(self, graph: Dict[str, List[tuple]], start_node: str) -> Dict[str, int]:
        """构建节点层级（用于并行执行）"""
        levels = {}
        queue = [(start_node, 0)]
        visited = {start_node}
        
        while queue:
            node_id, level = queue.pop(0)
            levels[node_id] = level
            
            for target_id, _ in graph.get(node_id, []):
                if target_id not in visited:
                    visited.add(target_id)
                    queue.append((target_id, level + 1))
        
        return levels
    
    def _find_start_node(self, nodes: Dict[str, WorkflowNode]) -> Optional[WorkflowNode]:
        """查找开始节点"""
        for node in nodes.values():
            if node.node_type == 'start' or node.node_type == 'data_input':
                return node
        return None
    
    def _evaluate_condition(self, condition: Optional[str], context: ExecutionContext) -> bool:
        """评估条件"""
        if not condition:
            return True
        
        try:
            local_vars = context.variables.copy()
            return eval(condition, {}, local_vars)
        except Exception as e:
            logger.warning(f"条件评估失败: {condition}, 错误: {e}")
            return True
    
    def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """获取执行状态"""
        execution = AIWorkflowExecution.objects.get(id=execution_id)
        node_executions = execution.node_executions.all()
        
        return {
            'execution_id': str(execution.id),
            'workflow_id': str(execution.workflow.id),
            'status': execution.status,
            'started_at': execution.started_at,
            'completed_at': execution.completed_at,
            'node_count': node_executions.count(),
            'completed_count': node_executions.filter(status='completed').count(),
            'failed_count': node_executions.filter(status='failed').count()
        }
    
    def cancel_execution(self, execution_id: str) -> bool:
        """取消执行"""
        try:
            execution = AIWorkflowExecution.objects.get(id=execution_id)
            if execution.status == 'running':
                execution.status = 'cancelled'
                execution.completed_at = timezone.now()
                execution.save()
                
                NodeExecution.objects.filter(
                    workflow_execution=execution,
                    status='running'
                ).update(status='cancelled', completed_at=timezone.now())
                
                logger.info(f"工作流执行已取消: {execution_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"取消执行失败: {e}")
            return False


class WorkflowDebugger:
    """工作流调试器"""
    
    def __init__(self, engine: EnhancedWorkflowEngine):
        self.engine = engine
        self.breakpoints: Dict[str, Set[str]] = {}
        self.execution_trace: List[Dict[str, Any]] = []
        
    def set_breakpoint(self, workflow_id: str, node_id: str):
        """设置断点"""
        if workflow_id not in self.breakpoints:
            self.breakpoints[workflow_id] = set()
        self.breakpoints[workflow_id].add(node_id)
        
    def remove_breakpoint(self, workflow_id: str, node_id: str):
        """移除断点"""
        if workflow_id in self.breakpoints:
            self.breakpoints[workflow_id].discard(node_id)
    
    def clear_breakpoints(self, workflow_id: str):
        """清除所有断点"""
        self.breakpoints.pop(workflow_id, None)
    
    def is_breakpoint(self, workflow_id: str, node_id: str) -> bool:
        """检查是否为断点"""
        return workflow_id in self.breakpoints and node_id in self.breakpoints[workflow_id]
    
    def record_trace(self, event: str, data: Dict[str, Any]):
        """记录执行轨迹"""
        self.execution_trace.append({
            'timestamp': datetime.now().isoformat(),
            'event': event,
            'data': data
        })
    
    def get_trace(self) -> List[Dict[str, Any]]:
        """获取执行轨迹"""
        return self.execution_trace.copy()
    
    def clear_trace(self):
        """清除执行轨迹"""
        self.execution_trace.clear()


class WorkflowPerformanceMonitor:
    """工作流性能监控器"""
    
    def __init__(self):
        self.metrics_cache = {}
        
    def record_execution_time(self, workflow_id: str, execution_time: float):
        """记录执行时间"""
        if workflow_id not in self.metrics_cache:
            self.metrics_cache[workflow_id] = {
                'execution_times': [],
                'node_times': {},
                'total_executions': 0
            }
        
        self.metrics_cache[workflow_id]['execution_times'].append(execution_time)
        self.metrics_cache[workflow_id]['total_executions'] += 1
        
        if len(self.metrics_cache[workflow_id]['execution_times']) > 100:
            self.metrics_cache[workflow_id]['execution_times'].pop(0)
    
    def record_node_time(self, workflow_id: str, node_id: str, execution_time: float):
        """记录节点执行时间"""
        if workflow_id not in self.metrics_cache:
            self.metrics_cache[workflow_id] = {
                'execution_times': [],
                'node_times': {},
                'total_executions': 0
            }
        
        if node_id not in self.metrics_cache[workflow_id]['node_times']:
            self.metrics_cache[workflow_id]['node_times'][node_id] = []
        
        self.metrics_cache[workflow_id]['node_times'][node_id].append(execution_time)
        
        if len(self.metrics_cache[workflow_id]['node_times'][node_id]) > 100:
            self.metrics_cache[workflow_id]['node_times'][node_id].pop(0)
    
    def get_average_execution_time(self, workflow_id: str) -> float:
        """获取平均执行时间"""
        if workflow_id in self.metrics_cache:
            times = self.metrics_cache[workflow_id]['execution_times']
            return sum(times) / len(times) if times else 0
        return 0
    
    def get_performance_report(self, workflow_id: str) -> Dict[str, Any]:
        """获取性能报告"""
        if workflow_id not in self.metrics_cache:
            return {}
        
        cache = self.metrics_cache[workflow_id]
        avg_time = self.get_average_execution_time(workflow_id)
        
        node_reports = {}
        for node_id, times in cache['node_times'].items():
            node_reports[node_id] = {
                'average_time': sum(times) / len(times) if times else 0,
                'max_time': max(times) if times else 0,
                'min_time': min(times) if times else 0,
                'execution_count': len(times)
            }
        
        return {
            'workflow_id': workflow_id,
            'total_executions': cache['total_executions'],
            'average_execution_time': avg_time,
            'node_metrics': node_reports
        }


workflow_engine = EnhancedWorkflowEngine()
workflow_debugger = WorkflowDebugger(workflow_engine)
performance_monitor = WorkflowPerformanceMonitor()
