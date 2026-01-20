"""
工作流调试服务

提供工作流调试能力，包括：
1. 断点管理 - 设置、查看、删除断点
2. 单步执行 - 支持单步进入、单步跳过、单步跳出
3. 变量观察 - 观察和修改变量值
4. 执行追踪 - 记录执行历史和状态变化
"""

import json
import uuid
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from django.utils import timezone


class DebugCommand(Enum):
    """调试命令类型"""
    STEP_INTO = "step_into"      # 单步进入
    STEP_OVER = "step_over"      # 单步跳过
    STEP_OUT = "step_out"        # 单步跳出
    CONTINUE = "continue"        # 继续执行
    PAUSE = "pause"              # 暂停执行
    STOP = "stop"                # 停止调试
    SET_BREAKPOINT = "set_breakpoint"    # 设置断点
    REMOVE_BREAKPOINT = "remove_breakpoint"  # 移除断点


class DebugEventType(Enum):
    """调试事件类型"""
    BREAKPOINT_HIT = "breakpoint_hit"
    STEP_COMPLETED = "step_completed"
    VARIABLE_CHANGED = "variable_changed"
    EXCEPTION_RAISED = "exception_raised"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_STARTED = "execution_started"


@dataclass
class Breakpoint:
    """断点定义"""
    id: str
    node_id: str
    node_name: str
    workflow_id: str
    condition: Optional[str] = None
    enabled: bool = True
    hit_count: int = 0
    created_at = field(default_factory=timezone.now)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'node_id': self.node_id,
            'node_name': self.node_name,
            'workflow_id': self.workflow_id,
            'condition': self.condition,
            'enabled': self.enabled,
            'hit_count': self.hit_count,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Breakpoint':
        bp = cls(
            id=data['id'],
            node_id=data['node_id'],
            node_name=data['node_name'],
            workflow_id=data['workflow_id'],
            condition=data.get('condition'),
            enabled=data.get('enabled', True),
            hit_count=data.get('hit_count', 0)
        )
        if 'created_at' in data:
            from dateutil.parser import parse
            bp.created_at = parse(data['created_at'])
        return bp


@dataclass
class DebugFrame:
    """调试帧 - 表示执行到某个节点时的状态"""
    execution_id: str
    node_id: str
    node_name: str
    node_type: str
    depth: int
    call_stack: List[Dict[str, Any]] = field(default_factory=list)
    local_variables: Dict[str, Any] = field(default_factory=dict)
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    status: str = "pending"
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'execution_id': self.execution_id,
            'node_id': self.node_id,
            'node_name': self.node_name,
            'node_type': self.node_type,
            'depth': self.depth,
            'call_stack': self.call_stack,
            'local_variables': self.local_variables,
            'input_data': self.input_data,
            'output_data': self.output_data,
            'status': self.status,
            'error_message': self.error_message
        }


@dataclass
class DebugSession:
    """调试会话"""
    id: str
    workflow_id: str
    execution_id: str
    user_id: Any
    breakpoints: Dict[str, Breakpoint] = field(default_factory=dict)
    current_frame: Optional[DebugFrame] = None
    execution_history: List[DebugFrame] = field(default_factory=list)
    watched_variables: Dict[str, List[str]] = field(default_factory=dict)
    status: str = "idle"  # idle, running, paused, stopped
    start_time = field(default_factory=timezone.now)
    total_steps: int = 0

    def add_breakpoint(self, breakpoint: Breakpoint):
        self.breakpoints[breakpoint.id] = breakpoint

    def remove_breakpoint(self, breakpoint_id: str):
        if breakpoint_id in self.breakpoints:
            del self.breakpoints[breakpoint_id]

    def get_breakpoints_for_node(self, node_id: str) -> List[Breakpoint]:
        return [bp for bp in self.breakpoints.values() 
                if bp.node_id == node_id and bp.enabled]

    def record_execution_step(self, frame: DebugFrame):
        self.execution_history.append(frame)
        self.total_steps += 1

    def add_watched_variable(self, var_name: str, watch_expression: str = None):
        if var_name not in self.watched_variables:
            self.watched_variables[var_name] = []
        if watch_expression:
            self.watched_variables[var_name].append(watch_expression)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'workflow_id': self.workflow_id,
            'execution_id': self.execution_id,
            'breakpoints': {k: v.to_dict() for k, v in self.breakpoints.items()},
            'current_frame': self.current_frame.to_dict() if self.current_frame else None,
            'execution_history': [f.to_dict() for f in self.execution_history],
            'watched_variables': self.watched_variables,
            'status': self.status,
            'start_time': self.start_time.isoformat(),
            'total_steps': self.total_steps
        }


class WorkflowDebugger:
    """工作流调试器"""
    
    _sessions: Dict[str, DebugSession] = {}
    _event_callbacks: Dict[str, List[Callable]] = {}
    
    @classmethod
    def create_session(cls, workflow_id: str, execution_id: str, user_id: Any) -> DebugSession:
        """创建新的调试会话"""
        session_id = str(uuid.uuid4())
        session = DebugSession(
            id=session_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            user_id=user_id
        )
        cls._sessions[session_id] = session
        return session
    
    @classmethod
    def get_session(cls, session_id: str) -> Optional[DebugSession]:
        """获取调试会话"""
        return cls._sessions.get(session_id)
    
    @classmethod
    def end_session(cls, session_id: str):
        """结束调试会话"""
        if session_id in cls._sessions:
            del cls._sessions[session_id]
    
    @classmethod
    def add_breakpoint(cls, session_id: str, node_id: str, node_name: str, 
                       workflow_id: str, condition: str = None) -> Breakpoint:
        """添加断点"""
        session = cls.get_session(session_id)
        if not session:
            raise ValueError(f"调试会话不存在: {session_id}")
        
        breakpoint_id = str(uuid.uuid4())
        breakpoint = Breakpoint(
            id=breakpoint_id,
            node_id=node_id,
            node_name=node_name,
            workflow_id=workflow_id,
            condition=condition
        )
        session.add_breakpoint(breakpoint)
        return breakpoint
    
    @classmethod
    def remove_breakpoint(cls, session_id: str, breakpoint_id: str):
        """移除断点"""
        session = cls.get_session(session_id)
        if session:
            session.remove_breakpoint(breakpoint_id)
    
    @classmethod
    def check_breakpoint(cls, session_id: str, node_id: str, context: Dict[str, Any]) -> bool:
        """检查是否命中断点"""
        session = cls.get_session(session_id)
        if not session:
            return False
        
        breakpoints = session.get_breakpoints_for_node(node_id)
        for bp in breakpoints:
            if bp.condition:
                try:
                    # 评估断点条件
                    result = cls._evaluate_condition(bp.condition, context)
                    if result:
                        bp.hit_count += 1
                        return True
                except Exception:
                    pass
            else:
                bp.hit_count += 1
                return True
        
        return False
    
    @classmethod
    def _evaluate_condition(cls, condition: str, context: Dict[str, Any]) -> bool:
        """评估条件表达式"""
        if not condition:
            return True
        
        try:
            # 安全地替换变量
            eval_context = {}
            for key, value in context.items():
                eval_context[key] = value
            
            # 简单的条件评估
            return bool(eval(condition, {"__builtins__": {}}, eval_context))
        except Exception:
            return False
    
    @classmethod
    def create_frame(cls, execution_id: str, node_id: str, node_name: str, 
                     node_type: str, depth: int, context: Dict[str, Any]) -> DebugFrame:
        """创建调试帧"""
        return DebugFrame(
            execution_id=execution_id,
            node_id=node_id,
            node_name=node_name,
            node_type=node_type,
            depth=depth,
            local_variables=context.copy(),
            input_data=context.copy()
        )
    
    @classmethod
    def register_event_callback(cls, event_type: DebugEventType, callback: Callable):
        """注册调试事件回调"""
        if event_type not in cls._event_callbacks:
            cls._event_callbacks[event_type] = []
        cls._event_callbacks[event_type].append(callback)
    
    @classmethod
    def trigger_event(cls, event_type: DebugEventType, session_id: str, data: Any):
        """触发调试事件"""
        if event_type in cls._event_callbacks:
            for callback in cls._event_callbacks[event_type]:
                try:
                    callback(session_id, data)
                except Exception as e:
                    print(f"调试事件回调错误: {e}")
    
    @classmethod
    def get_session_list(cls, workflow_id: str = None) -> List[DebugSession]:
        """获取调试会话列表"""
        sessions = list(cls._sessions.values())
        if workflow_id:
            sessions = [s for s in sessions if s.workflow_id == workflow_id]
        return sessions


class DebugExecutionService:
    """调试执行服务"""
    
    def __init__(self):
        self.debugger = WorkflowDebugger
    
    def start_debug_execution(self, workflow_id: str, execution_id: str, 
                              user_id: Any, breakpoints: List[Dict] = None) -> DebugSession:
        """开始调试执行"""
        session = self.debugger.create_session(workflow_id, execution_id, user_id)
        
        if breakpoints:
            for bp_data in breakpoints:
                self.debugger.add_breakpoint(
                    session.id,
                    bp_data['node_id'],
                    bp_data.get('node_name', ''),
                    workflow_id,
                    bp_data.get('condition')
                )
        
        return session
    
    def step_into(self, session_id: str, node_id: str, node_name: str, 
                  node_type: str, depth: int, context: Dict[str, Any]) -> DebugFrame:
        """单步进入"""
        session = self.debugger.get_session(session_id)
        if not session:
            raise ValueError(f"调试会话不存在: {session_id}")
        
        frame = self.debugger.create_frame(
            session.execution_id, node_id, node_name, node_type, depth, context
        )
        session.current_frame = frame
        session.record_execution_step(frame)
        
        self.debugger.trigger_event(DebugEventType.STEP_COMPLETED, session_id, frame.to_dict())
        return frame
    
    def step_over(self, session_id: str, node_id: str, node_name: str, 
                  context: Dict[str, Any]) -> DebugFrame:
        """单步跳过 - 停留在同一深度"""
        return self.step_into(session_id, node_id, node_name, 'step_over', 0, context)
    
    def continue_execution(self, session_id: str) -> str:
        """继续执行直到下一个断点"""
        session = self.debugger.get_session(session_id)
        if not session:
            raise ValueError(f"调试会话不存在: {session_id}")
        
        session.status = "running"
        return "continued"
    
    def pause_execution(self, session_id: str) -> DebugFrame:
        """暂停执行"""
        session = self.debugger.get_session(session_id)
        if not session:
            raise ValueError(f"调试会话不存在: {session_id}")
        
        session.status = "paused"
        return session.current_frame
    
    def stop_execution(self, session_id: str):
        """停止调试"""
        session = self.debugger.get_session(session_id)
        if not session:
            raise ValueError(f"调试会话不存在: {session_id}")
        
        session.status = "stopped"
        self.debugger.end_session(session_id)
    
    def update_variables(self, session_id: str, variables: Dict[str, Any]) -> DebugFrame:
        """修改变量值"""
        session = self.debugger.get_session(session_id)
        if not session:
            raise ValueError(f"调试会话不存在: {session_id}")
        
        if session.current_frame:
            old_values = session.current_frame.local_variables.copy()
            session.current_frame.local_variables.update(variables)
            
            self.debugger.trigger_event(
                DebugEventType.VARIABLE_CHANGED,
                session_id,
                {'old_values': old_values, 'new_values': variables}
            )
            return session.current_frame
        
        return None
    
    def get_watched_values(self, session_id: str) -> Dict[str, Any]:
        """获取被监视变量的当前值"""
        session = self.debugger.get_session(session_id)
        if not session:
            raise ValueError(f"调试会话不存在: {session_id}")
        
        result = {}
        if session.current_frame:
            for var_name in session.watched_variables:
                if var_name in session.current_frame.local_variables:
                    result[var_name] = session.current_frame.local_variables[var_name]
        return result
    
    def get_execution_history(self, session_id: str) -> List[Dict]:
        """获取执行历史"""
        session = self.debugger.get_session(session_id)
        if not session:
            raise ValueError(f"调试会话不存在: {session_id}")
        
        return [frame.to_dict() for frame in session.execution_history]
    
    def export_debug_trace(self, session_id: str) -> Dict:
        """导出调试追踪结果"""
        session = self.debugger.get_session(session_id)
        if not session:
            raise ValueError(f"调试会话不存在: {session_id}")
        
        return {
            'session_id': session.id,
            'workflow_id': session.workflow_id,
            'execution_id': session.execution_id,
            'status': session.status,
            'total_steps': session.total_steps,
            'execution_history': self.get_execution_history(session_id),
            'breakpoints_hit': [
                bp.to_dict() for bp in session.breakpoints.values() 
                if bp.hit_count > 0
            ],
            'duration': (timezone.now() - session.start_time).total_seconds()
        }


# 便捷函数
def create_debug_session(workflow_id: str, execution_id: str, user_id: Any) -> DebugSession:
    return WorkflowDebugger.create_session(workflow_id, execution_id, user_id)

def add_breakpoint(session_id: str, node_id: str, node_name: str, 
                   workflow_id: str, condition: str = None) -> Breakpoint:
    return WorkflowDebugger.add_breakpoint(session_id, node_id, node_name, workflow_id, condition)

def check_breakpoint(session_id: str, node_id: str, context: Dict[str, Any]) -> bool:
    return WorkflowDebugger.check_breakpoint(session_id, node_id, context)
