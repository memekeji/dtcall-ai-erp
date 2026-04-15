import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
from django.db.models import Avg, Q
from django.utils import timezone
from apps.production.models import (
    ProductionPlan, ProductionTask, Equipment, ProductionProcedure
)

logger = logging.getLogger(__name__)


class SchedulingConstraint:
    """排程约束定义"""

    def __init__(self):
        self.constraints = {
            'equipment_capacity': True,      # 设备产能约束
            'labor_capacity': True,          # 人员产能约束
            'material_availability': True,   # 物料齐套约束
            'delivery_date': True,           # 交期约束
            'process_sequence': True,        # 工艺顺序约束
            'setup_time': True,              # 换产时间约束
            'maintenance_window': False,     # 维护窗口约束
        }

    def enable_constraint(self, constraint_name: str, enabled: bool = True):
        if constraint_name in self.constraints:
            self.constraints[constraint_name] = enabled

    def is_enabled(self, constraint_name: str) -> bool:
        return self.constraints.get(constraint_name, False)


class SchedulingResult:
    """排程结果"""

    def __init__(self):
        self.scheduled_tasks = []
        self.unscheduled_tasks = []
        self.resource_load = defaultdict(list)
        self.start_time = None
        self.end_time = None
        self.execution_time = 0
        self.constraints_violated = []
        self.optimization_score = 0
        self.message = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'scheduled_tasks': [task.to_dict() for task in self.scheduled_tasks],
            'unscheduled_tasks': [task.to_dict() for task in self.unscheduled_tasks],
            'resource_load': dict(self.resource_load),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'execution_time': self.execution_time,
            'constraints_violated': self.constraints_violated,
            'optimization_score': self.optimization_score,
            'message': self.message
        }


class ScheduledTask:
    """已排程任务"""

    def __init__(self, task: ProductionTask, scheduled_start: datetime, scheduled_end: datetime,
                 equipment: Equipment = None, priority: int = 1):
        self.original_task = task
        self.scheduled_start = scheduled_start
        self.scheduled_end = scheduled_end
        self.equipment = equipment
        self.priority = priority
        self.dependencies = []
        self.constraints = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.original_task.id,
            'task_name': self.original_task.name,
            'task_code': self.original_task.code,
            'scheduled_start': self.scheduled_start.isoformat(),
            'scheduled_end': self.scheduled_end.isoformat(),
            'duration': (self.scheduled_end - self.scheduled_start).total_seconds() / 3600,
            'equipment_id': self.equipment.id if self.equipment else None,
            'equipment_name': self.equipment.name if self.equipment else None,
            'priority': self.priority,
            'quantity': float(self.original_task.quantity),
            'status': self.original_task.status
        }


class SchedulingOptimizerService:
    """
    智能排程优化服务

    支持多种排程策略：
    1. 最短作业优先 (SJF)
    2. 最早交期优先 (EDD)
    3. 优先级调度
    4. 混合策略（综合考虑交期、优先级、设备利用率）
    """

    def __init__(self):
        self.constraints = SchedulingConstraint()
        self.logger = logging.getLogger(__name__)

    def optimize_schedule(self, plans: List[ProductionPlan] = None,
                          start_date: datetime = None,
                          end_date: datetime = None,
                          strategy: str = 'hybrid') -> SchedulingResult:
        """
        执行智能排程优化

        Args:
            plans: 待排程的生产计划列表
            start_date: 排程开始日期
            end_date: 排程结束日期
            strategy: 排程策略 ('sjf', 'edd', 'priority', 'hybrid')

        Returns:
            SchedulingResult: 排程结果
        """
        start_time = datetime.now()
        result = SchedulingResult()

        try:
            self.logger.info(f"开始执行智能排程优化，策略: {strategy}")

            if not start_date:
                start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if not end_date:
                end_date = start_date + timedelta(days=30)

            result.start_time = start_date
            result.end_time = end_date

            tasks = self._get_pending_tasks(plans, start_date, end_date)
            if not tasks:
                result.message = "暂无待排程的任务"
                result.execution_time = (
                    datetime.now() - start_time).total_seconds()
                return result

            equipment_list = self._get_available_equipment()
            resources = self._get_available_resources()

            if strategy == 'sjf':
                scheduled = self._schedule_sjf(
                    tasks, equipment_list, resources, start_date, end_date)
            elif strategy == 'edd':
                scheduled = self._schedule_edd(
                    tasks, equipment_list, resources, start_date, end_date)
            elif strategy == 'priority':
                scheduled = self._schedule_priority(
                    tasks, equipment_list, resources, start_date, end_date)
            else:
                scheduled = self._schedule_hybrid(
                    tasks, equipment_list, resources, start_date, end_date)

            result.scheduled_tasks = scheduled

            for task in scheduled:
                if task.equipment:
                    result.resource_load[task.equipment.id].append(task)

            result.optimization_score = self._calculate_optimization_score(
                scheduled)
            result.message = f"排程完成，成功排程 {len(scheduled)} 个任务"

            self.logger.info(f"排程优化完成，耗时: {result.execution_time:.2f}秒")

        except Exception as e:
            self.logger.error(f"排程优化失败: {str(e)}")
            result.message = f"排程优化失败: {str(e)}"

        result.execution_time = (datetime.now() - start_time).total_seconds()
        return result

    def _get_pending_tasks(self, plans: List[ProductionPlan] = None,
                           start_date: datetime = None,
                           end_date: datetime = None) -> List[ProductionTask]:
        """获取待排程的任务列表"""
        query = Q(status__in=[1])  # 待开始状态

        if plans:
            plan_ids = [p.id for p in plans]
            query &= Q(plan_id__in=plan_ids)

        if start_date:
            query &= Q(plan_start_time__gte=start_date)
        if end_date:
            query &= Q(plan_start_time__lte=end_date)

        tasks = ProductionTask.objects.filter(query).select_related(
            'plan', 'procedure', 'equipment', 'assignee'
        ).order_by('plan_start_time')

        return list(tasks)

    def _get_available_equipment(self) -> List[Equipment]:
        """获取可用设备列表"""
        return list(Equipment.objects.filter(
            status__in=[1]  # 正常状态
        ).select_related('department'))

    def _get_available_resources(self) -> Dict[str, Any]:
        """获取可用资源信息"""
        resources = {
            'equipment_capacity': {},  # 设备产能
            'labor_capacity': {},      # 人员产能
            'work_centers': {},        # 工作中心
        }

        equipment_list = Equipment.objects.filter(status=1)
        for eq in equipment_list:
            resources['equipment_capacity'][eq.id] = {
                'name': eq.name,
                'daily_capacity': 8,  # 默认日产能8小时
                'efficiency': 0.85,   # 默认效率85%
                'available': True
            }

        return resources

    def _schedule_sjf(self, tasks: List[ProductionTask],
                      equipment_list: List[Equipment],
                      resources: Dict[str, Any],
                      start_date: datetime,
                      end_date: datetime) -> List[ScheduledTask]:
        """最短作业优先排程策略"""
        scheduled = []
        task_queue = sorted(tasks, key=lambda t: t.quantity)
        current_time = start_date

        for task in task_queue:
            if current_time >= end_date:
                break

            equipment = self._find_best_equipment(
                task, equipment_list, current_time)
            if not equipment:
                continue

            duration = self._estimate_duration(task, equipment)
            scheduled_end = current_time + timedelta(hours=float(duration))

            if scheduled_end <= end_date:
                scheduled.append(
                    ScheduledTask(
                        task,
                        current_time,
                        scheduled_end,
                        equipment))
                current_time = scheduled_end

        return scheduled

    def _schedule_edd(self, tasks: List[ProductionTask],
                      equipment_list: List[Equipment],
                      resources: Dict[str, Any],
                      start_date: datetime,
                      end_date: datetime) -> List[ScheduledTask]:
        """最早交期优先排程策略"""
        scheduled = []
        task_queue = sorted(tasks, key=lambda t: t.plan_end_date)
        current_time = start_date

        for task in task_queue:
            if current_time >= end_date:
                break

            equipment = self._find_best_equipment(
                task, equipment_list, current_time)
            if not equipment:
                continue

            duration = self._estimate_duration(task, equipment)
            scheduled_end = current_time + timedelta(hours=float(duration))

            if scheduled_end <= end_date:
                scheduled.append(
                    ScheduledTask(
                        task,
                        current_time,
                        scheduled_end,
                        equipment))
                current_time = scheduled_end

        return scheduled

    def _schedule_priority(self, tasks: List[ProductionTask],
                           equipment_list: List[Equipment],
                           resources: Dict[str, Any],
                           start_date: datetime,
                           end_date: datetime) -> List[ScheduledTask]:
        """优先级调度策略"""
        scheduled = []
        task_queue = sorted(
            tasks,
            key=lambda t: (
                t.plan.priority if t.plan else 2,
                t.plan_end_date))
        current_time = start_date

        for task in task_queue:
            if current_time >= end_date:
                break

            equipment = self._find_best_equipment(
                task, equipment_list, current_time)
            if not equipment:
                continue

            duration = self._estimate_duration(task, equipment)
            scheduled_end = current_time + timedelta(hours=float(duration))

            if scheduled_end <= end_date:
                scheduled.append(
                    ScheduledTask(
                        task,
                        current_time,
                        scheduled_end,
                        equipment))
                current_time = scheduled_end

        return scheduled

    def _schedule_hybrid(self, tasks: List[ProductionTask],
                         equipment_list: List[Equipment],
                         resources: Dict[str, Any],
                         start_date: datetime,
                         end_date: datetime) -> List[ScheduledTask]:
        """混合策略排程（综合考虑交期、优先级、设备利用率）"""
        scheduled = []
        current_time = start_date

        remaining_tasks = tasks.copy()

        while remaining_tasks and current_time < end_date:
            best_task = None
            best_equipment = None
            best_score = -float('inf')

            for task in remaining_tasks:
                equipment = self._find_best_equipment(
                    task, equipment_list, current_time)
                if not equipment:
                    continue

                score = self._calculate_task_score(
                    task, equipment, current_time)

                if score > best_score:
                    best_score = score
                    best_task = task
                    best_equipment = equipment

            if best_task and best_equipment:
                duration = self._estimate_duration(best_task, best_equipment)
                scheduled_end = current_time + timedelta(hours=float(duration))

                if scheduled_end <= end_date:
                    scheduled.append(
                        ScheduledTask(
                            best_task,
                            current_time,
                            scheduled_end,
                            best_equipment))
                    remaining_tasks.remove(best_task)
                    current_time = scheduled_end
                else:
                    break
            else:
                break

        return scheduled

    def _find_best_equipment(self, task: ProductionTask,
                             equipment_list: List[Equipment],
                             scheduled_time: datetime) -> Optional[Equipment]:
        """查找最适合任务的设备"""
        candidates = []

        for equipment in equipment_list:
            if equipment.status != 1:  # 设备状态必须正常
                continue

            if task.equipment and task.equipment.id != equipment.id:
                continue

            if self._check_equipment_available(equipment, scheduled_time):
                load_score = self._calculate_equipment_load_score(
                    equipment, scheduled_time)
                candidates.append((equipment, load_score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    def _check_equipment_available(self, equipment: Equipment,
                                   start_time: datetime) -> bool:
        """检查设备在指定时间是否可用"""
        overlapping = ProductionTask.objects.filter(
            equipment=equipment,
            status__in=[2],  # 进行中
            plan_start_time__lte=start_time,
            plan_end_time__gte=start_time
        ).exists()

        return not overlapping

    def _calculate_equipment_load_score(self, equipment: Equipment,
                                        current_time: datetime) -> float:
        """计算设备负载评分（负载越低评分越高）"""
        day_start = current_time.replace(
            hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        task_count = ProductionTask.objects.filter(
            equipment=equipment,
            status__in=[1, 2],
            plan_start_time__gte=day_start,
            plan_start_time__lt=day_end
        ).count()

        return 1.0 / (task_count + 1)

    def _estimate_duration(self, task: ProductionTask,
                           equipment: Equipment) -> float:
        """估算任务执行时长（小时）"""
        base_time = float(
            task.procedure.standard_time) if task.procedure else 1.0

        quantity_factor = float(task.quantity) / 100  # 每100件需要一个基础工时

        duration = base_time * quantity_factor

        return max(duration, 0.5)  # 至少0.5小时

    def _calculate_task_score(self, task: ProductionTask,
                              equipment: Equipment,
                              current_time: datetime) -> float:
        """计算任务调度评分"""
        score = 0

        if task.plan:
            priority_score = (5 - task.plan.priority) * 10  # 优先级越高分数越高
            score += priority_score

            days_to_due = (task.plan.plan_end_date - current_time.date()).days
            if days_to_due < 0:
                score += 50  # 逾期任务
            elif days_to_due <= 3:
                score += 30  # 临近交期
            elif days_to_due <= 7:
                score += 20
            else:
                score += 10

        load_score = self._calculate_equipment_load_score(
            equipment, current_time)
        score += load_score * 100

        return score

    def _calculate_optimization_score(
            self, scheduled: List[ScheduledTask]) -> float:
        """计算排程优化评分"""
        if not scheduled:
            return 0

        total_tasks = len(scheduled)

        score = 100

        due_date_violations = 0
        for task in scheduled:
            if task.original_task.plan and task.scheduled_end.date(
            ) > task.original_task.plan.plan_end_date:
                due_date_violations += 1

        if total_tasks > 0:
            due_date_penalty = (due_date_violations / total_tasks) * 30
            score -= due_date_penalty

        if total_tasks < 10:
            scale_penalty = (10 - total_tasks) * 2
            score -= scale_penalty

        return max(0, min(100, score))

    def calculate_bottleneck_analysis(self, start_date: datetime,
                                      end_date: datetime) -> Dict[str, Any]:
        """分析瓶颈工序"""
        bottleneck_analysis = {
            'bottleneck_equipment': [],
            'bottleneck_procedures': [],
            'suggestions': []
        }

        equipment_usage = defaultdict(list)

        tasks = ProductionTask.objects.filter(
            status__in=[1, 2, 3],
            plan_start_time__gte=start_date,
            plan_start_time__lte=end_date
        ).select_related('equipment', 'procedure')

        for task in tasks:
            if task.equipment:
                equipment_usage[task.equipment.id].append(task)

        equipment_load = []
        for eq_id, tasks_list in equipment_usage.items():
            eq = Equipment.objects.filter(id=eq_id).first()
            if eq:
                total_hours = sum(
                    self._estimate_duration(task, eq)
                    for task in tasks_list
                )
                equipment_load.append({
                    'equipment_id': eq_id,
                    'equipment_name': eq.name,
                    'task_count': len(tasks_list),
                    'total_hours': total_hours,
                    # 假设月工作160小时
                    'utilization_rate': min(total_hours / 160, 1.0)
                })

        equipment_load.sort(key=lambda x: x['utilization_rate'], reverse=True)

        for load in equipment_load[:3]:
            if load['utilization_rate'] > 0.8:
                bottleneck_analysis['bottleneck_equipment'].append(load)

        procedure_usage = defaultdict(list)
        for task in tasks:
            if task.procedure:
                procedure_usage[task.procedure.id].append(task)

        procedure_load = []
        for proc_id, tasks_list in procedure_usage.items():
            proc = ProductionProcedure.objects.filter(id=proc_id).first()
            if proc:
                procedure_load.append({
                    'procedure_id': proc_id,
                    'procedure_name': proc.name,
                    'task_count': len(tasks_list)
                })

        procedure_load.sort(key=lambda x: x['task_count'], reverse=True)
        bottleneck_analysis['bottleneck_procedures'] = procedure_load[:5]

        if bottleneck_analysis['bottleneck_equipment']:
            bottleneck_analysis['suggestions'].append(
                f"发现 {len(bottleneck_analysis['bottleneck_equipment'])} 台设备负载过高，建议增加设备或调整排程"
            )

        return bottleneck_analysis

    def simulate_schedule(self, plan: ProductionPlan,
                          target_date: datetime = None) -> Dict[str, Any]:
        """模拟单个计划的排程结果"""
        if not target_date:
            target_date = plan.plan_start_date

        tasks = list(plan.tasks.filter(status=1))

        simulation = {
            'plan': {
                'id': plan.id,
                'name': plan.name,
                'code': plan.code
            },
            'simulation_date': target_date.isoformat(),
            'tasks': [],
            'total_estimated_time': 0,
            'estimated_completion_date': None,
            'feasibility': True,
            'issues': []
        }

        if not tasks:
            simulation['issues'].append("该计划暂无待执行的任务")
            simulation['feasibility'] = False
            return simulation

        current_date = target_date
        total_hours = 0

        for task in tasks:
            duration = self._estimate_duration(
                task, task.equipment or Equipment.objects.filter(
                    status=1).first())
            end_date = current_date + timedelta(hours=duration)

            simulation['tasks'].append({
                'task_id': task.id,
                'task_name': task.name,
                'start_date': current_date.isoformat(),
                'end_date': end_date.isoformat(),
                'duration_hours': duration,
                'equipment': task.equipment.name if task.equipment else '待分配'
            })

            total_hours += duration
            current_date = end_date

        simulation['total_estimated_time'] = total_hours
        simulation['estimated_completion_date'] = current_date.isoformat()

        if plan.plan_end_date and current_date.date() > plan.plan_end_date:
            simulation['feasibility'] = False
            simulation['issues'].append(
                f"预计完成时间 {current_date.date()} 晚于计划交期 {plan.plan_end_date}"
            )

        return simulation


class GanttChartService:
    """甘特图服务"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def generate_gantt_data(self, scheduled_tasks: List[ScheduledTask],
                            start_date: datetime = None,
                            end_date: datetime = None) -> Dict[str, Any]:
        """生成甘特图数据"""
        if not start_date:
            start_date = min(task.scheduled_start for task in scheduled_tasks)
        if not end_date:
            end_date = max(task.scheduled_end for task in scheduled_tasks)

        tasks_data = []
        resources = set()

        for task in scheduled_tasks:
            task_info = {
                'id': task.original_task.id,
                'name': task.original_task.name,
                'code': task.original_task.code,
                'start': task.scheduled_start.isoformat(),
                'end': task.scheduled_end.isoformat(),
                'progress': task.original_task.completion_rate if hasattr(task.original_task, 'completion_rate') else 0,
                'dependencies': [dep.original_task.id for dep in task.dependencies],
                'custom_class': self._get_task_status_class(task),
                'equipment': task.equipment.name if task.equipment else '未分配'
            }
            tasks_data.append(task_info)

            if task.equipment:
                resources.add(task.equipment.name)

        return {
            'tasks': tasks_data,
            'resources': list(resources),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'total_tasks': len(scheduled_tasks)
        }

    def _get_task_status_class(self, task: ScheduledTask) -> str:
        """根据任务状态获取甘特图样式类"""
        status = task.original_task.status
        if status == 1:
            return 'task-pending'
        elif status == 2:
            return 'task-running'
        elif status == 3:
            return 'task-completed'
        else:
            return 'task-cancelled'


class DeliveryPredictionService:
    """交期达成率预测服务"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def predict_delivery_rate(self, plan: ProductionPlan) -> Dict[str, Any]:
        """预测计划交期达成率"""
        tasks = plan.tasks.filter(status__in=[1, 2, 3])

        if not tasks.exists():
            return {
                'plan_id': plan.id,
                'predicted_rate': 0,
                'confidence': 0,
                'factors': [],
                'recommendations': []
            }

        historical_data = self._get_historical_delivery_data()

        completed_tasks = tasks.filter(status=3)
        in_progress_tasks = tasks.filter(status=2)
        pending_tasks = tasks.filter(status=1)

        completed_rate = 0
        if completed_tasks.exists():
            avg_completion = completed_tasks.aggregate(
                avg_rate=Avg('completed_quantity') / Avg('quantity')
            )['avg_rate'] or 0
            completed_rate = float(avg_completion) * 100

        progress_factor = float(in_progress_tasks.count()
                                ) / float(tasks.count()) * 30

        time_factor = self._calculate_time_factor(plan)

        predicted_rate = completed_rate + progress_factor + time_factor

        predicted_rate = min(100, max(0, predicted_rate))

        confidence = self._calculate_confidence(plan, tasks, historical_data)

        factors = [
            {'name': '已完成进度',
             'value': f'{completed_rate:.1f}%',
             'impact': 'positive'},
            {'name': '进行中任务', 'value': f'{in_progress_tasks.count()}个',
             'impact': 'neutral'},
            {'name': '时间因素', 'value': f'{time_factor:.1f}%',
                'impact': 'positive' if time_factor > 0 else 'negative'}
        ]

        recommendations = []
        if predicted_rate < 70:
            recommendations.append("建议增加资源投入，加快生产进度")
        if time_factor < 0:
            recommendations.append("当前进度落后于计划，建议调整排程")
        if in_progress_tasks.count() > tasks.count() / 2:
            recommendations.append("进行中任务过多，建议优先完成现有任务")

        return {
            'plan_id': plan.id,
            'plan_name': plan.name,
            'predicted_rate': round(predicted_rate, 1),
            'confidence': round(confidence, 1),
            'factors': factors,
            'recommendations': recommendations
        }

    def _get_historical_delivery_data(self) -> Dict[str, Any]:
        """获取历史交期达成数据"""
        completed_plans = ProductionPlan.objects.filter(status=4)  # 已完成

        total_plans = completed_plans.count()
        on_time_plans = 0

        for plan in completed_plans:
            if plan.actual_end_date and plan.plan_end_date:
                if plan.actual_end_date <= plan.plan_end_date:
                    on_time_plans += 1

        return {
            'total_completed': total_plans,
            'on_time_count': on_time_plans,
            'on_time_rate': (on_time_plans / total_plans * 100) if total_plans > 0 else 0
        }

    def _calculate_time_factor(self, plan: ProductionPlan) -> float:
        """计算时间因素得分"""
        if not plan.plan_start_date:
            return 0

        today = timezone.now().date()
        total_days = (
            plan.plan_end_date -
            plan.plan_start_date).days if plan.plan_end_date else 1
        elapsed_days = (today - plan.plan_start_date).days

        if elapsed_days < 0:
            return 20  # 尚未开始

        if elapsed_days > total_days:
            return -20  # 已逾期

        expected_progress = (elapsed_days / total_days) * 100

        actual_progress = plan.completion_rate if hasattr(
            plan, 'completion_rate') else 0

        return expected_progress - actual_progress

    def _calculate_confidence(self, plan: ProductionPlan,
                              tasks,
                              historical_data: Dict[str, Any]) -> float:
        """计算预测置信度"""
        base_confidence = 70

        if historical_data['total_completed'] < 10:
            base_confidence -= 20
        elif historical_data['total_completed'] < 50:
            base_confidence -= 10

        on_time_rate = historical_data.get('on_time_rate', 50)
        confidence_adjustment = (on_time_rate - 50) / 5
        base_confidence += confidence_adjustment

        task_count = tasks.count()
        if task_count < 5:
            base_confidence -= 10
        elif task_count > 50:
            base_confidence -= 5

        return max(30, min(95, base_confidence))
