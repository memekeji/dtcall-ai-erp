"""
工作流调试与监控服务
提供完整的调试、监控和性能分析能力
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from django.db.models import Avg, Count, Max, Min
from django.utils import timezone

from apps.ai.models import (
    AIWorkflow, AIWorkflowExecution, NodeExecution, WorkflowNode
)
from apps.ai.services.enhanced_workflow_engine import (
    EnhancedWorkflowEngine, WorkflowDebugger, WorkflowPerformanceMonitor
)

logger = logging.getLogger(__name__)


workflow_engine = EnhancedWorkflowEngine()
workflow_debugger = WorkflowDebugger(workflow_engine)
performance_monitor = WorkflowPerformanceMonitor()


class DebugEventType(Enum):
    """调试事件类型"""
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_TIMEOUT = "workflow_timeout"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    BREAKPOINT_HIT = "breakpoint_hit"
    VARIABLE_CHANGED = "variable_changed"


@dataclass
class DebugEvent:
    """调试事件"""
    event_type: DebugEventType
    timestamp: datetime
    execution_id: str
    workflow_id: str
    node_id: Optional[str] = None
    node_name: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    traceback: Optional[str] = None


class WorkflowDebuggerService:
    """工作流调试服务"""
    
    def __init__(self):
        self.active_sessions: Dict[str, 'DebugSession'] = {}
        self.event_handlers: List[Callable] = []
        workflow_engine.subscribe_execution(self._handle_execution_event)
    
    def _handle_execution_event(self, event_type: str, data: Dict[str, Any]):
        """处理执行事件"""
        for handler in self.event_handlers:
            try:
                handler(event_type, data)
            except Exception as e:
                logger.error(f"调试事件处理失败: {e}")
    
    def create_debug_session(
        self, 
        workflow_id: str, 
        user_id: int,
        breakpoints: Optional[List[str]] = None
    ) -> 'DebugSession':
        """创建调试会话"""
        session_id = f"debug_{workflow_id}_{user_id}_{int(time.time())}"
        session = DebugSession(
            session_id=session_id,
            workflow_id=workflow_id,
            user_id=user_id,
            breakpoints=breakpoints or []
        )
        self.active_sessions[session_id] = session
        
        if breakpoints:
            for node_id in breakpoints:
                workflow_debugger.set_breakpoint(workflow_id, node_id)
        
        return session
    
    def end_debug_session(self, session_id: str):
        """结束调试会话"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            for node_id in session.breakpoints:
                workflow_debugger.remove_breakpoint(session.workflow_id, node_id)
            del self.active_sessions[session_id]
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取调试会话状态"""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        return {
            'session_id': session_id,
            'workflow_id': session.workflow_id,
            'status': session.status,
            'current_node': session.current_node_id,
            'variables': session.variables,
            'trace': session.get_trace(),
            'breakpoints': session.breakpoints
        }
    
    def execute_with_debug(
        self,
        workflow_id: str,
        user_id: int,
        input_data: Dict[str, Any],
        breakpoints: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """执行工作流并调试"""
        session = self.create_debug_session(workflow_id, user_id, breakpoints)
        
        try:
            execution = workflow_engine.create_execution(workflow_id, user_id, input_data)
            
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    workflow_engine.execute_workflow(str(execution.id))
                )
            finally:
                loop.close()
            
            return {
                'success': result.status == 'completed',
                'execution_id': str(result.id),
                'output_data': result.output_data,
                'error_message': result.error_message,
                'trace': session.get_trace()
            }
        finally:
            self.end_debug_session(session.session_id)
    
    def add_event_handler(self, handler: Callable):
        """添加事件处理器"""
        self.event_handlers.append(handler)
    
    def remove_event_handler(self, handler: Callable):
        """移除事件处理器"""
        if handler in self.event_handlers:
            self.event_handlers.remove(handler)


class DebugSession:
    """调试会话"""
    
    def __init__(
        self, 
        session_id: str, 
        workflow_id: str, 
        user_id: int,
        breakpoints: List[str]
    ):
        self.session_id = session_id
        self.workflow_id = workflow_id
        self.user_id = user_id
        self.breakpoints = set(breakpoints)
        self.status = 'created'
        self.current_node_id = None
        self.variables: Dict[str, Any] = {}
        self.execution_trace: List[DebugEvent] = []
        self.start_time = datetime.now()
    
    def record_event(self, event: DebugEvent):
        """记录调试事件"""
        self.execution_trace.append(event)
        
        if event.event_type == DebugEventType.NODE_STARTED:
            self.current_node_id = event.node_id
            self.status = 'running'
        
        if event.event_type == DebugEventType.NODE_COMPLETED:
            self.status = 'paused'
        
        if event.node_id and event.node_id in self.breakpoints:
            self.status = 'breakpoint'
    
    def set_variable(self, name: str, value: Any):
        """设置变量"""
        old_value = self.variables.get(name)
        self.variables[name] = value
        
        self.execution_trace.append(DebugEvent(
            event_type=DebugEventType.VARIABLE_CHANGED,
            timestamp=datetime.now(),
            execution_id='',
            workflow_id=self.workflow_id,
            data={
                'variable': name,
                'old_value': old_value,
                'new_value': value
            }
        ))
    
    def get_trace(self) -> List[Dict[str, Any]]:
        """获取执行轨迹"""
        return [
            {
                'event_type': e.event_type.value,
                'timestamp': e.timestamp.isoformat(),
                'node_id': e.node_id,
                'node_name': e.node_name,
                'data': e.data
            }
            for e in self.execution_trace
        ]
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        events_by_node = defaultdict(list)
        for event in self.execution_trace:
            if event.node_id:
                events_by_node[event.node_id].append(event)
        
        node_summary = {}
        for node_id, events in events_by_node.items():
            start_time = None
            end_time = None
            for event in events:
                if event.event_type == DebugEventType.NODE_STARTED:
                    start_time = event.timestamp
                if event.event_type == DebugEventType.NODE_COMPLETED:
                    end_time = event.timestamp
            
            node_summary[node_id] = {
                'execution_time': (end_time - start_time).total_seconds() if start_time and end_time else 0,
                'event_count': len(events)
            }
        
        return {
            'session_id': self.session_id,
            'workflow_id': self.workflow_id,
            'status': self.status,
            'duration': (datetime.now() - self.start_time).total_seconds(),
            'node_summary': node_summary,
            'total_events': len(self.execution_trace)
        }


class WorkflowMonitoringService:
    """工作流监控服务"""
    
    def __init__(self):
        self.metrics_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.alert_thresholds: Dict[str, float] = {}
        self.alert_callbacks: List[Callable] = []
    
    def set_alert_threshold(self, metric: str, threshold: float):
        """设置告警阈值"""
        self.alert_thresholds[metric] = threshold
    
    def record_execution_metric(
        self,
        workflow_id: str,
        execution_id: str,
        metrics: Dict[str, Any]
    ):
        """记录执行指标"""
        metric_data = {
            'execution_id': execution_id,
            'timestamp': timezone.now(),
            **metrics
        }
        self.metrics_history[workflow_id].append(metric_data)
        
        if len(self.metrics_history[workflow_id]) > 1000:
            self.metrics_history[workflow_id].pop(0)
        
        self._check_alerts(workflow_id, metrics)
    
    def _check_alerts(self, workflow_id: str, metrics: Dict[str, Any]):
        """检查告警"""
        for metric, threshold in self.alert_thresholds.items():
            if metric in metrics and metrics[metric] > threshold:
                for callback in self.alert_callbacks:
                    try:
                        callback(workflow_id, metric, metrics[metric], threshold)
                    except Exception as e:
                        logger.error(f"告警回调失败: {e}")
    
    def add_alert_callback(self, callback: Callable):
        """添加告警回调"""
        self.alert_callbacks.append(callback)
    
    def get_workflow_metrics(
        self, 
        workflow_id: str, 
        time_range: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """获取工作流指标"""
        history = self.metrics_history.get(workflow_id, [])
        
        if time_range:
            cutoff = datetime.now() - time_range
            history = [m for m in history if m['timestamp'] > cutoff]
        
        if not history:
            return {}
        
        execution_times = [m.get('execution_time', 0) for m in history]
        success_count = sum(1 for m in history if m.get('success', False))
        
        return {
            'total_executions': len(history),
            'successful_executions': success_count,
            'failed_executions': len(history) - success_count,
            'success_rate': success_count / len(history) if history else 0,
            'avg_execution_time': sum(execution_times) / len(execution_times) if execution_times else 0,
            'max_execution_time': max(execution_times) if execution_times else 0,
            'min_execution_time': min(execution_times) if execution_times else 0,
            'recent_metrics': history[-10:]
        }
    
    def get_node_metrics(
        self, 
        workflow_id: str, 
        node_id: str,
        time_range: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """获取节点指标"""
        history = self.metrics_history.get(workflow_id, [])
        
        if time_range:
            cutoff = datetime.now() - time_range
            history = [m for m in history if m['timestamp'] > cutoff]
        
        node_executions = [
            m for m in history 
            if 'node_metrics' in m and node_id in m.get('node_metrics', {})
        ]
        
        if not node_executions:
            return {}
        
        node_times = [
            m['node_metrics'].get(node_id, {}).get('execution_time', 0)
            for m in node_executions
        ]
        
        return {
            'total_executions': len(node_executions),
            'avg_execution_time': sum(node_times) / len(node_times) if node_times else 0,
            'max_execution_time': max(node_times) if node_times else 0,
            'min_execution_time': min(node_times) if node_times else 0
        }
    
    def get_execution_history(
        self,
        workflow_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取执行历史"""
        executions = AIWorkflowExecution.objects.filter(
            workflow_id=workflow_id
        ).order_by('-created_at')[offset:offset + limit]
        
        return [
            {
                'execution_id': str(e.id),
                'status': e.status,
                'created_at': e.created_at.isoformat(),
                'started_at': e.started_at.isoformat() if e.started_at else None,
                'completed_at': e.completed_at.isoformat() if e.completed_at else None,
                'duration': (e.completed_at - e.started_at).total_seconds() if e.started_at and e.completed_at else None,
                'input_data': e.input_data,
                'output_data': e.output_data,
                'error_message': e.error_message
            }
            for e in executions
        ]
    
    def get_workflow_health_status(self, workflow_id: str) -> Dict[str, Any]:
        """获取工作流健康状态"""
        recent_metrics = self.get_workflow_metrics(workflow_id, timedelta(hours=24))
        
        health_score = 100
        
        if recent_metrics.get('success_rate', 1) < 0.95:
            health_score -= 20
        if recent_metrics.get('avg_execution_time', 0) > 60:
            health_score -= 15
        if recent_metrics.get('failed_executions', 0) > 10:
            health_score -= 25
        
        health_status = 'healthy'
        if health_score < 60:
            health_status = 'critical'
        elif health_score < 80:
            health_status = 'warning'
        
        return {
            'workflow_id': workflow_id,
            'health_score': health_score,
            'health_status': health_status,
            'metrics': recent_metrics,
            'recommendations': self._generate_recommendations(recent_metrics)
        }
    
    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if metrics.get('success_rate', 1) < 0.95:
            recommendations.append("建议检查失败率较高节点的错误日志，优化异常处理逻辑")
        
        if metrics.get('avg_execution_time', 0) > 60:
            recommendations.append("建议评估慢节点的优化空间，考虑使用缓存或并行处理")
        
        if metrics.get('max_execution_time', 0) > 300:
            recommendations.append("检测到执行时间过长的节点，建议添加超时控制和重试机制")
        
        if not recommendations:
            recommendations.append("工作流运行良好，继续保持")
        
        return recommendations
    
    def export_metrics(
        self, 
        workflow_id: str, 
        format: str = 'json',
        time_range: Optional[timedelta] = None
    ) -> str:
        """导出指标数据"""
        metrics = self.get_workflow_metrics(workflow_id, time_range)
        
        if format == 'json':
            return json.dumps(metrics, ensure_ascii=False, indent=2)
        elif format == 'csv':
            lines = ['指标,值']
            for key, value in metrics.items():
                lines.append(f'{key},{value}')
            return '\n'.join(lines)
        
        return json.dumps(metrics)


class PerformanceOptimizationService:
    """性能优化服务"""
    
    def __init__(self):
        self.execution_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 300
    
    def analyze_bottleneck(self, workflow_id: str) -> Dict[str, Any]:
        """分析性能瓶颈"""
        metrics = performance_monitor.get_performance_report(workflow_id)
        
        node_metrics = metrics.get('node_metrics', {})
        bottleneck_node = None
        max_time = 0
        
        for node_id, node_metric in node_metrics.items():
            avg_time = node_metric.get('average_time', 0)
            if avg_time > max_time:
                max_time = avg_time
                bottleneck_node = node_id
        
        return {
            'workflow_id': workflow_id,
            'bottleneck_node': bottleneck_node,
            'bottleneck_time': max_time,
            'total_executions': metrics.get('total_executions', 0),
            'avg_execution_time': metrics.get('average_execution_time', 0),
            'node_metrics': node_metrics,
            'suggestions': self._generate_optimization_suggestions(node_metrics)
        }
    
    def _generate_optimization_suggestions(self, node_metrics: Dict[str, Any]) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        sorted_nodes = sorted(
            node_metrics.items(), 
            key=lambda x: x[1].get('average_time', 0), 
            reverse=True
        )
        
        for node_id, metric in sorted_nodes[:3]:
            avg_time = metric.get('average_time', 0)
            exec_count = metric.get('execution_count', 0)
            
            if avg_time > 10:
                suggestions.append(
                    f"节点 {node_id} 平均执行时间较长（{avg_time:.2f}秒），"
                    f"建议优化其内部逻辑或增加缓存"
                )
            
            if avg_time > 5 and exec_count > 10:
                suggestions.append(
                    f"节点 {node_id} 执行频繁且耗时，考虑使用并行处理或预计算"
                )
        
        return suggestions
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        valid_cache = {
            k: v for k, v in self.execution_cache.items()
            if (datetime.now() - v.get('cached_at', datetime.now())).total_seconds() < self.cache_ttl
        }
        
        return {
            'total_entries': len(self.execution_cache),
            'valid_entries': len(valid_cache),
            'hit_rate': self._calculate_hit_rate()
        }
    
    def _calculate_hit_rate(self) -> float:
        """计算缓存命中率"""
        hits = sum(1 for v in self.execution_cache.values() if v.get('hit', False))
        total = len(self.execution_cache)
        return hits / total if total > 0 else 0


debugger_service = WorkflowDebuggerService()
monitoring_service = WorkflowMonitoringService()
optimization_service = PerformanceOptimizationService()
