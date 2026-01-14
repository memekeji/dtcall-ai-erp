import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from collections import deque
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.production.models import (
    Equipment, ProductionTask, DataCollection, ProductionDataPoint,
    QualityCheck, DataSource
)

logger = logging.getLogger(__name__)


class RealTimeDataManager:
    """
    实时数据管理器
    
    负责收集、缓存和分发实时生产数据
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.data_buffers = {}  # 设备数据缓冲区
        self.alert_rules = {}   # 告警规则
        self.active_alerts = []  # 活跃告警
        self.subscribers = {}   # 订阅者管理
        self.lock = threading.Lock()
        
        self._init_default_alert_rules()
    
    def _init_default_alert_rules(self):
        """初始化默认告警规则"""
        self.alert_rules = {
            'equipment_offline': {
                'name': '设备离线',
                'condition': lambda data: data.get('status') == 3,
                'severity': 'high',
                'message': '设备已离线',
                'cooldown': 300
            },
            'equipment_maintenance': {
                'name': '设备维修中',
                'condition': lambda data: data.get('status') == 2,
                'severity': 'medium',
                'message': '设备正在维修',
                'cooldown': 600
            },
            'temperature_high': {
                'name': '温度过高',
                'condition': lambda data: data.get('parameter_name') == 'temperature' and data.get('is_normal') == False,
                'severity': 'high',
                'message': '设备温度异常',
                'cooldown': 60
            },
            'production_slow': {
                'name': '生产进度滞后',
                'condition': lambda data: data.get('progress_rate', 100) < 50,
                'severity': 'medium',
                'message': '生产进度低于预期',
                'cooldown': 1800
            },
            'quality_issue': {
                'name': '质量问题',
                'condition': lambda data: data.get('result') == 2,
                'severity': 'high',
                'message': '检测到不合格品',
                'cooldown': 120
            }
        }
    
    def register_subscriber(self, subscriber_id: str, callback: Callable):
        """注册数据订阅者"""
        with self.lock:
            if subscriber_id not in self.subscribers:
                self.subscribers[subscriber_id] = []
            self.subscribers[subscriber_id].append(callback)
            logger.info(f"订阅者 {subscriber_id} 已注册")
    
    def unregister_subscriber(self, subscriber_id: str):
        """注销订阅者"""
        with self.lock:
            if subscriber_id in self.subscribers:
                del self.subscribers[subscriber_id]
                logger.info(f"订阅者 {subscriber_id} 已注销")
    
    def publish_data(self, data_type: str, data: Dict[str, Any]):
        """发布数据到所有订阅者"""
        with self.lock:
            callbacks = self.subscribers.get(data_type, [])
            for callback in callbacks:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"执行回调函数失败: {str(e)}")
    
    def buffer_equipment_data(self, equipment_id: int, data: Dict[str, Any]):
        """缓存设备实时数据"""
        with self.lock:
            if equipment_id not in self.data_buffers:
                self.data_buffers[equipment_id] = deque(maxlen=1000)
            
            data['timestamp'] = timezone.now().isoformat()
            self.data_buffers[equipment_id].append(data)
            
            self._check_alert_rules(equipment_id, data)
    
    def get_equipment_data(self, equipment_id: int, 
                          limit: int = 100) -> List[Dict[str, Any]]:
        """获取设备历史数据"""
        with self.lock:
            buffer = self.data_buffers.get(equipment_id, deque())
            return list(buffer)[-limit:]
    
    def _check_alert_rules(self, equipment_id: int, data: Dict[str, Any]):
        """检查告警规则"""
        for rule_id, rule in self.alert_rules.items():
            try:
                if rule['condition'](data):
                    self._trigger_alert(equipment_id, rule_id, rule, data)
            except Exception as e:
                logger.error(f"检查告警规则失败: {str(e)}")
    
    def _trigger_alert(self, equipment_id: int, rule_id: str, 
                      rule: Dict[str, Any], data: Dict[str, Any]):
        """触发告警"""
        alert = {
            'id': f"{equipment_id}_{rule_id}_{int(time.time())}",
            'equipment_id': equipment_id,
            'rule_id': rule_id,
            'name': rule['name'],
            'message': rule['message'],
            'severity': rule['severity'],
            'timestamp': timezone.now().isoformat(),
            'data': data,
            'acknowledged': False
        }
        
        with self.lock:
            for existing_alert in self.active_alerts:
                if (existing_alert['equipment_id'] == equipment_id and 
                    existing_alert['rule_id'] == rule_id):
                    cooldown = rule.get('cooldown', 300)
                    last_time = datetime.fromisoformat(existing_alert['timestamp'])
                    if (timezone.now() - last_time).total_seconds() < cooldown:
                        return
            
            self.active_alerts.append(alert)
        
        self.publish_data('alert', alert)
        logger.warning(f"触发告警: {rule['name']} - 设备 {equipment_id}")
    
    def acknowledge_alert(self, alert_id: str, user_id: int = None):
        """确认告警"""
        with self.lock:
            for alert in self.active_alerts:
                if alert['id'] == alert_id:
                    alert['acknowledged'] = True
                    alert['acknowledged_by'] = user_id
                    alert['acknowledged_time'] = timezone.now().isoformat()
                    break
    
    def get_active_alerts(self, equipment_id: int = None) -> List[Dict[str, Any]]:
        """获取活跃告警"""
        with self.lock:
            if equipment_id:
                return [a for a in self.active_alerts 
                       if a['equipment_id'] == equipment_id and not a['acknowledged']]
            return [a for a in self.active_alerts if not a['acknowledged']]
    
    def get_all_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取所有告警"""
        with self.lock:
            return self.active_alerts[-limit:]


class EquipmentMonitorService:
    """
    设备监控服务
    
    提供设备状态监控、实时数据采集、异常告警等功能
    """
    
    def __init__(self):
        self.data_manager = RealTimeDataManager()
        self.logger = logging.getLogger(__name__)
    
    def get_equipment_status(self, equipment_id: int) -> Dict[str, Any]:
        """获取设备实时状态"""
        equipment = Equipment.objects.select_related('department', 'responsible_person').get(id=equipment_id)
        
        current_task = ProductionTask.objects.filter(
            equipment=equipment,
            status=2
        ).select_related('plan', 'assignee').first()
        
        latest_data = self._get_latest_equipment_data(equipment_id)
        
        alerts = self.data_manager.get_active_alerts(equipment_id)
        
        status_info = {
            'equipment': {
                'id': equipment.id,
                'name': equipment.name,
                'code': equipment.code,
                'model': equipment.model,
                'status': equipment.status,
                'status_display': equipment.status_display,
                'location': equipment.location,
                'department': equipment.department.name if equipment.department else None,
                'responsible_person': equipment.responsible_person.username if equipment.responsible_person else None
            },
            'current_task': None,
            'latest_data': latest_data,
            'alerts': alerts,
            'monitoring_status': 'active' if equipment.status == 1 else 'inactive'
        }
        
        if current_task:
            status_info['current_task'] = {
                'id': current_task.id,
                'name': current_task.name,
                'code': current_task.code,
                'progress': current_task.completion_rate,
                'assignee': current_task.assignee.username if current_task.assignee else None,
                'start_time': current_task.actual_start_time.isoformat() if current_task.actual_start_time else None
            }
        
        return status_info
    
    def get_all_equipment_status(self) -> List[Dict[str, Any]]:
        """获取所有设备状态"""
        equipment_list = Equipment.objects.select_related(
            'department', 'responsible_person'
        ).all()
        
        status_list = []
        for equipment in equipment_list:
            status = self.get_equipment_status(equipment.id)
            status_list.append(status)
        
        return status_list
    
    def _get_latest_equipment_data(self, equipment_id: int) -> Optional[Dict[str, Any]]:
        """获取设备最新采集数据"""
        latest = ProductionDataPoint.objects.filter(
            equipment_id=equipment_id
        ).order_by('-timestamp').first()
        
        if latest:
            return {
                'metric_name': latest.metric_name,
                'metric_value': latest.metric_value,
                'metric_unit': latest.metric_unit,
                'timestamp': latest.timestamp.isoformat(),
                'quality': latest.quality
            }
        
        collection = DataCollection.objects.filter(
            equipment_id=equipment_id
        ).order_by('-collect_time').first()
        
        if collection:
            return {
                'parameter_name': collection.parameter_name,
                'parameter_value': float(collection.parameter_value),
                'unit': collection.unit,
                'timestamp': collection.collect_time.isoformat(),
                'is_normal': collection.is_normal
            }
        
        return None
    
    def get_equipment_data_history(self, equipment_id: int,
                                   start_time: datetime = None,
                                   end_time: datetime = None,
                                   metric_name: str = None,
                                   limit: int = 500) -> List[Dict[str, Any]]:
        """获取设备历史数据"""
        if not start_time:
            start_time = timezone.now() - timedelta(hours=24)
        if not end_time:
            end_time = timezone.now()
        
        query = Q(equipment_id=equipment_id)
        query &= Q(timestamp__gte=start_time)
        query &= Q(timestamp__lte=end_time)
        
        if metric_name:
            query &= Q(metric_name=metric_name)
        
        data_points = ProductionDataPoint.objects.filter(
            query
        ).order_by('-timestamp')[:limit]
        
        return [{
            'timestamp': dp.timestamp.isoformat(),
            'metric_name': dp.metric_name,
            'metric_value': dp.metric_value,
            'metric_unit': dp.metric_unit,
            'quality': dp.quality
        } for dp in data_points]
    
    def calculate_equipment_oee(self, equipment_id: int,
                               start_date: datetime = None,
                               end_date: datetime = None) -> Dict[str, Any]:
        """计算设备OEE（Overall Equipment Effectiveness）"""
        if not start_date:
            start_date = timezone.now().date()
        if not end_date:
            end_date = start_date
        
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        
        equipment = Equipment.objects.get(id=equipment_id)
        
        days = (end_date - start_date).days + 1
        total_available_hours = days * 24
        
        tasks = ProductionTask.objects.filter(
            equipment_id=equipment_id,
            status__in=[1, 2, 3],
            plan_start_time__date__gte=start_date,
            plan_start_time__date__lte=end_date
        )
        
        planned_production_time = tasks.aggregate(
            total=Sum(F('plan_end_time') - F('plan_start_time'))
        )['total'] or timedelta(0)
        
        planned_production_hours = planned_production_time.total_seconds() / 3600
        
        running_time = timedelta(0)
        for task in tasks.filter(status=2):
            if task.actual_start_time:
                end = task.actual_end_time or timezone.now()
                running_time += (end - task.actual_start_time)
        
        actual_production_hours = running_time.total_seconds() / 3600
        
        good_units = tasks.aggregate(
            total=Sum('qualified_quantity')
        )['total'] or 0
        
        total_units = tasks.aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        availability = (planned_production_hours / total_available_hours * 100) if total_available_hours > 0 else 0
        performance = (actual_production_hours / planned_production_hours * 100) if planned_production_hours > 0 else 0
        quality = (good_units / total_units * 100) if total_units > 0 else 0
        
        oee = availability * performance * quality / 10000
        
        return {
            'equipment_id': equipment_id,
            'equipment_name': equipment.name,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days
            },
            'oee': round(oee, 2),
            'availability': round(availability, 2),
            'performance': round(performance, 2),
            'quality': round(quality, 2),
            'planned_production_hours': round(planned_production_hours, 2),
            'actual_production_hours': round(actual_production_hours, 2),
            'total_units': float(total_units),
            'good_units': float(good_units),
            'defect_units': float(total_units - good_units)
        }
    
    def get_production_progress(self, plan_id: int = None,
                               task_id: int = None) -> Dict[str, Any]:
        """获取生产进度"""
        query = Q()
        
        if plan_id:
            query &= Q(plan_id=plan_id)
        if task_id:
            query &= Q(id=task_id)
        
        if not query:
            return {'error': '请指定计划或任务'}
        
        tasks = ProductionTask.objects.filter(query)
        
        total_quantity = tasks.aggregate(total=Sum('quantity'))['total'] or 0
        completed_quantity = tasks.aggregate(total=Sum('completed_quantity'))['total'] or 0
        qualified_quantity = tasks.aggregate(total=Sum('qualified_quantity'))['total'] or 0
        
        status_counts = {
            'pending': tasks.filter(status=1).count(),
            'running': tasks.filter(status=2).count(),
            'completed': tasks.filter(status=3).count(),
            'suspended': tasks.filter(status=4).count()
        }
        
        progress_rate = (completed_quantity / total_quantity * 100) if total_quantity > 0 else 0
        quality_rate = (qualified_quantity / completed_quantity * 100) if completed_quantity > 0 else 0
        
        return {
            'plan_id': plan_id,
            'task_id': task_id,
            'total_tasks': tasks.count(),
            'total_quantity': float(total_quantity),
            'completed_quantity': float(completed_quantity),
            'qualified_quantity': float(qualified_quantity),
            'progress_rate': round(progress_rate, 2),
            'quality_rate': round(quality_rate, 2),
            'status_counts': status_counts
        }


class WebSocketNotificationService:
    """
    WebSocket通知服务
    
    负责通过WebSocket推送实时数据
    """
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def broadcast_to_group(self, group_name: str, event_type: str, data: Dict[str, Any]):
        """向指定组广播消息"""
        try:
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    'type': event_type,
                    'data': data
                }
            )
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"WebSocket广播失败: {str(e)}")
    
    def broadcast_equipment_update(self, equipment_id: int, status_data: Dict[str, Any]):
        """广播设备状态更新"""
        self.broadcast_to_group(
            f'equipment_{equipment_id}',
            'equipment_update',
            {
                'equipment_id': equipment_id,
                'data': status_data,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        self.broadcast_to_group(
            'all_equipment',
            'equipment_update',
            {
                'equipment_id': equipment_id,
                'data': status_data,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    def broadcast_alert(self, alert: Dict[str, Any]):
        """广播告警信息"""
        self.broadcast_to_group(
            'alerts',
            'alert_notification',
            alert
        )
    
    def broadcast_production_update(self, plan_id: int, progress_data: Dict[str, Any]):
        """广播生产进度更新"""
        self.broadcast_to_group(
            f'production_{plan_id}',
            'production_update',
            {
                'plan_id': plan_id,
                'data': progress_data,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    def broadcast_task_update(self, task_id: int, task_data: Dict[str, Any]):
        """广播任务状态更新"""
        self.broadcast_to_group(
            f'task_{task_id}',
            'task_update',
            {
                'task_id': task_id,
                'data': task_data,
                'timestamp': timezone.now().isoformat()
            }
        )


class AlertRuleService:
    """
    告警规则服务
    
    管理自定义告警规则
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def create_alert_rule(self, name: str, condition: Dict[str, Any],
                         severity: str, message: str,
                         notification_channels: List[str] = None) -> Dict[str, Any]:
        """创建告警规则"""
        rule = {
            'id': f"custom_{int(time.time())}",
            'name': name,
            'condition': condition,
            'severity': severity,
            'message': message,
            'notification_channels': notification_channels or ['web'],
            'enabled': True,
            'created_at': timezone.now().isoformat()
        }
        
        data_manager = RealTimeDataManager()
        data_manager.alert_rules[rule['id']] = rule
        
        return rule
    
    def update_alert_rule(self, rule_id: str, updates: Dict[str, Any]) -> bool:
        """更新告警规则"""
        data_manager = RealTimeDataManager()
        
        if rule_id in data_manager.alert_rules:
            data_manager.alert_rules[rule_id].update(updates)
            return True
        return False
    
    def delete_alert_rule(self, rule_id: str) -> bool:
        """删除告警规则"""
        data_manager = RealTimeDataManager()
        
        if rule_id in data_manager.alert_rules:
            del data_manager.alert_rules[rule_id]
            return True
        return False
    
    def get_all_rules(self) -> List[Dict[str, Any]]:
        """获取所有告警规则"""
        data_manager = RealTimeDataManager()
        return list(data_manager.alert_rules.values())
    
    def acknowledge_alert(self, alert_id: str, user_id: int = None) -> bool:
        """确认告警"""
        data_manager = RealTimeDataManager()
        data_manager.acknowledge_alert(alert_id, user_id)
        return True
