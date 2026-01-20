import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
from django.db.models import Sum, Avg, Count, F, Q, Max, Min
from django.utils import timezone
from django.db.models.functions import TruncDate, TruncHour, TruncWeek, TruncMonth
from apps.production.models import (
    ProductionPlan, ProductionTask, Equipment, ProductionProcedure,
    QualityCheck, DataCollection, ResourceConsumption, BOM, BOMItem,
    MaterialRequest, MaterialIssue, ProductReceipt, WorkCompletionReport
)
from apps.user.models import Admin
from apps.department.models import Department

logger = logging.getLogger(__name__)


class ProductionStatisticsService:
    """
    生产统计分析服务
    
    提供全面的生产数据统计分析功能，包括：
    - 生产进度统计
    - 质量指标统计
    - 设备效率统计
    - 人员效率统计
    - 成本分析统计
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_production_summary(self, start_date: datetime = None,
                              end_date: datetime = None,
                              department_id: int = None) -> Dict[str, Any]:
        """获取生产综合统计概览"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        
        query = Q(plan_start_date__gte=start_date, plan_start_date__lte=end_date)
        if department_id:
            query &= Q(department_id=department_id)
        
        plans = ProductionPlan.objects.filter(query)
        
        total_plans = plans.count()
        completed_plans = plans.filter(status=4).count()
        active_plans = plans.filter(status=3).count()
        cancelled_plans = plans.filter(status=5).count()
        
        total_tasks = 0
        completed_tasks = 0
        total_quantity = 0
        completed_quantity = 0
        qualified_quantity = 0
        
        tasks_query = Q()
        for plan in plans:
            tasks_query |= Q(plan_id=plan.id)
        
        if plans.exists():
            tasks = ProductionTask.objects.filter(tasks_query)
            
            total_tasks = tasks.count()
            completed_tasks = tasks.filter(status=3).count()
            
            agg = tasks.aggregate(
                total=Sum('quantity'),
                completed=Sum('completed_quantity'),
                qualified=Sum('qualified_quantity')
            )
            total_quantity = agg['total'] or 0
            completed_quantity = agg['completed'] or 0
            qualified_quantity = agg['qualified'] or 0
        
        plan_completion_rate = (completed_plans / total_plans * 100) if total_plans > 0 else 0
        task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        production_completion_rate = (completed_quantity / total_quantity * 100) if total_quantity > 0 else 0
        quality_rate = (qualified_quantity / completed_quantity * 100) if completed_quantity > 0 else 0
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'plans': {
                'total': total_plans,
                'completed': completed_plans,
                'active': active_plans,
                'cancelled': cancelled_plans,
                'completion_rate': round(plan_completion_rate, 2)
            },
            'tasks': {
                'total': total_tasks,
                'completed': completed_tasks,
                'completion_rate': round(task_completion_rate, 2)
            },
            'production': {
                'total_quantity': float(total_quantity),
                'completed_quantity': float(completed_quantity),
                'qualified_quantity': float(qualified_quantity),
                'completion_rate': round(production_completion_rate, 2),
                'quality_rate': round(quality_rate, 2)
            }
        }
    
    def get_production_trend(self, start_date: datetime = None,
                            end_date: datetime = None,
                            granularity: str = 'day') -> List[Dict[str, Any]]:
        """获取生产趋势数据"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        
        if granularity == 'hour':
            trunc_func = TruncHour
        elif granularity == 'week':
            trunc_func = TruncWeek
        elif granularity == 'month':
            trunc_func = TruncMonth
        else:
            trunc_func = TruncDate
        
        tasks = ProductionTask.objects.filter(
            status=3,
            actual_end_time__date__gte=start_date,
            actual_end_time__date__lte=end_date
        ).annotate(
            period=trunc_func('actual_end_time')
        ).values('period').annotate(
            completed_count=Count('id'),
            completed_quantity=Sum('completed_quantity'),
            qualified_quantity=Sum('qualified_quantity')
        ).order_by('period')
        
        trend_data = []
        current_date = start_date
        while current_date <= end_date:
            period_data = {
                'date': current_date.isoformat(),
                'completed_count': 0,
                'completed_quantity': 0,
                'qualified_quantity': 0,
                'quality_rate': 0
            }
            
            for task in tasks:
                task_date = task['period'].date() if hasattr(task['period'], 'date') else task['period']
                if task_date == current_date:
                    period_data['completed_count'] = task['completed_count']
                    period_data['completed_quantity'] = float(task['completed_quantity'] or 0)
                    period_data['qualified_quantity'] = float(task['qualified_quantity'] or 0)
                    if period_data['completed_quantity'] > 0:
                        period_data['quality_rate'] = round(
                            period_data['qualified_quantity'] / period_data['completed_quantity'] * 100, 2
                        )
                    break
            
            trend_data.append(period_data)
            current_date += timedelta(days=1)
        
        return trend_data
    
    def get_quality_statistics(self, start_date: datetime = None,
                              end_date: datetime = None) -> Dict[str, Any]:
        """获取质量统计指标"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        
        checks = QualityCheck.objects.filter(
            check_time__date__gte=start_date,
            check_time__date__lte=end_date
        )
        
        total_checks = checks.count()
        qualified_checks = checks.filter(result=1).count()
        unqualified_checks = checks.filter(result=2).count()
        pending_checks = checks.filter(result=3).count()
        
        agg = checks.aggregate(
            total_checked=Sum('check_quantity'),
            total_qualified=Sum('qualified_quantity'),
            total_unqualified=Sum('defective_quantity')
        )
        
        total_checked = agg['total_checked'] or 0
        total_qualified = agg['total_qualified'] or 0
        total_unqualified = agg['total_unqualified'] or 0
        
        overall_quality_rate = (total_qualified / total_checked * 100) if total_checked > 0 else 0
        first_pass_rate = self._calculate_first_pass_rate(checks)
        
        defect_distribution = self._get_defect_distribution(checks)
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': {
                'total_checks': total_checks,
                'qualified_checks': qualified_checks,
                'unqualified_checks': unqualified_checks,
                'pending_checks': pending_checks,
                'overall_quality_rate': round(overall_quality_rate, 2),
                'first_pass_rate': round(first_pass_rate, 2),
                'total_checked_quantity': float(total_checked),
                'qualified_quantity': float(total_qualified),
                'unqualified_quantity': float(total_unqualified),
                'defect_rate': round(100 - overall_quality_rate, 2)
            },
            'defect_distribution': defect_distribution
        }
    
    def _calculate_first_pass_rate(self, checks) -> float:
        """计算一次通过率"""
        first_pass = checks.filter(result=1).count()
        total = checks.count()
        return (first_pass / total * 100) if total > 0 else 0
    
    def _get_defect_distribution(self, checks) -> List[Dict[str, Any]]:
        """获取缺陷分布"""
        defect_data = checks.filter(
            result=2,
            defect_description__isnull=False
        ).exclude(defect_description='')
        
        defect_counts = defaultdict(int)
        for check in defect_data:
            defects = check.defect_description.split(';')
            for defect in defects:
                defect = defect.strip()
                if defect:
                    defect_counts[defect] += 1
        
        distribution = [
            {'defect': defect, 'count': count}
            for defect, count in sorted(defect_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return distribution[:10]
    
    def get_equipment_efficiency(self, start_date: datetime = None,
                                end_date: datetime = None) -> List[Dict[str, Any]]:
        """获取设备效率统计"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        
        equipment_list = Equipment.objects.all()
        efficiency_data = []
        
        for equipment in equipment_list:
            tasks = ProductionTask.objects.filter(
                equipment=equipment,
                status__in=[1, 2, 3],
                plan_start_time__date__gte=start_date,
                plan_start_time__date__lte=end_date
            )
            
            total_tasks = tasks.count()
            completed_tasks = tasks.filter(status=3).count()
            
            task_hours = 0
            for task in tasks:
                if task.plan_end_time and task.plan_start_time:
                    duration = (task.plan_end_time - task.plan_start_time).total_seconds() / 3600
                    task_hours += duration
            
            utilization_rate = min(task_hours / 160 * 100, 100) if total_tasks > 0 else 0
            
            oee_data = self._calculate_oee_for_equipment(equipment, start_date, end_date)
            
            efficiency_data.append({
                'equipment_id': equipment.id,
                'equipment_name': equipment.name,
                'equipment_code': equipment.code,
                'status': equipment.status,
                'status_display': equipment.status_display,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'task_hours': round(task_hours, 2),
                'utilization_rate': round(utilization_rate, 2),
                'oee': oee_data.get('oee', 0),
                'availability': oee_data.get('availability', 0),
                'performance': oee_data.get('performance', 0),
                'quality': oee_data.get('quality', 0)
            })
        
        return efficiency_data
    
    def _calculate_oee_for_equipment(self, equipment: Equipment,
                                     start_date, end_date) -> Dict[str, float]:
        """计算单台设备的OEE"""
        days = (end_date - start_date).days + 1
        total_available_hours = days * 24
        
        tasks = ProductionTask.objects.filter(
            equipment=equipment,
            status__in=[1, 2, 3],
            plan_start_time__date__gte=start_date,
            plan_start_time__date__lte=end_date
        )
        
        planned_hours = 0
        for task in tasks:
            if task.plan_end_time and task.plan_start_time:
                planned_hours += (task.plan_end_time - task.plan_start_time).total_seconds() / 3600
        
        running_hours = 0
        for task in tasks.filter(status=2):
            if task.actual_start_time:
                end = task.actual_end_time or timezone.now()
                running_hours += (end - task.actual_start_time).total_seconds() / 3600
        
        good_units = float(tasks.aggregate(total=Sum('qualified_quantity'))['total'] or 0)
        total_units = float(tasks.aggregate(total=Sum('quantity'))['total'] or 0)
        
        availability = (planned_hours / total_available_hours * 100) if total_available_hours > 0 else 0
        performance = (running_hours / planned_hours * 100) if planned_hours > 0 else 0
        quality = (good_units / total_units * 100) if total_units > 0 else 0
        oee = availability * performance * quality / 10000
        
        return {
            'oee': round(oee, 2),
            'availability': round(availability, 2),
            'performance': round(performance, 2),
            'quality': round(quality, 2)
        }
    
    def get_labor_efficiency(self, start_date: datetime = None,
                            end_date: datetime = None) -> List[Dict[str, Any]]:
        """获取人员效率统计"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        
        tasks = ProductionTask.objects.filter(
            status=3,
            actual_end_time__date__gte=start_date,
            actual_end_time__date__lte=end_date
        ).select_related('assignee', 'procedure')
        
        user_stats = defaultdict(lambda: {
            'completed_tasks': 0,
            'completed_quantity': 0,
            'qualified_quantity': 0,
            'total_hours': 0,
            'procedures': set()
        })
        
        for task in tasks:
            if task.assignee:
                stats = user_stats[task.assignee.id]
                stats['completed_tasks'] += 1
                stats['completed_quantity'] += float(task.completed_quantity or 0)
                stats['qualified_quantity'] += float(task.qualified_quantity or 0)
                if task.actual_end_time and task.actual_start_time:
                    hours = (task.actual_end_time - task.actual_start_time).total_seconds() / 3600
                    stats['total_hours'] += hours
                if task.procedure:
                    stats['procedures'].add(task.procedure.name)
        
        efficiency_data = []
        for user_id, stats in user_stats.items():
            user = Admin.objects.filter(id=user_id).first()
            if user:
                avg_output = stats['completed_quantity'] / stats['total_hours'] if stats['total_hours'] > 0 else 0
                quality_rate = (stats['qualified_quantity'] / stats['completed_quantity'] * 100) if stats['completed_quantity'] > 0 else 0
                
                efficiency_data.append({
                    'user_id': user_id,
                    'user_name': user.username,
                    'department': user.department.name if user.department else None,
                    'completed_tasks': stats['completed_tasks'],
                    'completed_quantity': stats['completed_quantity'],
                    'qualified_quantity': stats['qualified_quantity'],
                    'total_hours': round(stats['total_hours'], 2),
                    'avg_output_per_hour': round(avg_output, 2),
                    'quality_rate': round(quality_rate, 2),
                    'procedures': list(stats['procedures'])
                })
        
        efficiency_data.sort(key=lambda x: x['avg_output_per_hour'], reverse=True)
        
        return efficiency_data
    
    def get_cost_analysis(self, start_date: datetime = None,
                         end_date: datetime = None) -> Dict[str, Any]:
        """获取成本分析"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        
        material_costs = self._get_material_costs(start_date, end_date)
        labor_costs = self._get_labor_costs(start_date, end_date)
        overhead_costs = self._get_overhead_costs(start_date, end_date)
        
        total_cost = material_costs['total'] + labor_costs['total'] + overhead_costs['total']
        
        completed_units = ProductionTask.objects.filter(
            status=3,
            actual_end_time__date__gte=start_date,
            actual_end_time__date__lte=end_date
        ).aggregate(total=Sum('qualified_quantity'))['total'] or 0
        
        unit_cost = total_cost / completed_units if completed_units > 0 else 0
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'material_cost': material_costs,
            'labor_cost': labor_costs,
            'overhead_cost': overhead_costs,
            'total_cost': round(total_cost, 2),
            'completed_units': float(completed_units),
            'unit_cost': round(unit_cost, 2),
            'cost_breakdown': {
                'material': round(material_costs['total'] / total_cost * 100, 2) if total_cost > 0 else 0,
                'labor': round(labor_costs['total'] / total_cost * 100, 2) if total_cost > 0 else 0,
                'overhead': round(overhead_costs['total'] / total_cost * 100, 2) if total_cost > 0 else 0
            }
        }
    
    def _get_material_costs(self, start_date, end_date) -> Dict[str, Any]:
        """获取材料成本"""
        issues = MaterialIssue.objects.filter(
            status=2,
            issue_date__gte=start_date,
            issue_date__lte=end_date
        )
        
        total = issues.aggregate(total=Sum('total_amount'))['total'] or 0
        
        return {
            'total': float(total),
            'count': issues.count()
        }
    
    def _get_labor_costs(self, start_date, end_date) -> Dict[str, Any]:
        """获取人工成本"""
        tasks = ProductionTask.objects.filter(
            status=3,
            actual_end_time__date__gte=start_date,
            actual_end_time__date__lte=end_date
        )
        
        total_hours = 0
        for task in tasks:
            if task.actual_start_time and task.actual_end_time:
                total_hours += (task.actual_end_time - task.actual_start_time).total_seconds() / 3600
        
        hourly_rate = 50  # 假设平均时薪50元
        total = total_hours * hourly_rate
        
        return {
            'total': round(total, 2),
            'total_hours': round(total_hours, 2),
            'hourly_rate': hourly_rate
        }
    
    def _get_overhead_costs(self, start_date, end_date) -> Dict[str, Any]:
        """获取制造费用"""
        consumptions = ResourceConsumption.objects.filter(
            consumption_time__date__gte=start_date,
            consumption_time__date__lte=end_date
        )
        
        total = consumptions.aggregate(total=Sum('cost'))['total'] or 0
        
        return {
            'total': float(total),
            'count': consumptions.count()
        }
    
    def get_on_time_delivery_rate(self, start_date: datetime = None,
                                  end_date: datetime = None) -> Dict[str, Any]:
        """获取准时交货率"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        
        completed_plans = ProductionPlan.objects.filter(
            status=4,
            actual_end_date__gte=start_date,
            actual_end_date__lte=end_date
        )
        
        total = completed_plans.count()
        on_time = 0
        
        for plan in completed_plans:
            if plan.actual_end_date and plan.plan_end_date:
                if plan.actual_end_date <= plan.plan_end_date:
                    on_time += 1
        
        on_time_rate = (on_time / total * 100) if total > 0 else 0
        
        delay_days = []
        for plan in completed_plans:
            if plan.actual_end_date and plan.plan_end_date:
                delay = (plan.actual_end_date - plan.plan_end_date).days
                if delay > 0:
                    delay_days.append(delay)
        
        avg_delay = sum(delay_days) / len(delay_days) if delay_days else 0
        max_delay = max(delay_days) if delay_days else 0
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_completed': total,
            'on_time_count': on_time,
            'on_time_rate': round(on_time_rate, 2),
            'delayed_count': total - on_time,
            'average_delay_days': round(avg_delay, 2),
            'max_delay_days': max_delay
        }
    
    def generate_comprehensive_report(self, start_date: datetime = None,
                                     end_date: datetime = None) -> Dict[str, Any]:
        """生成综合分析报告"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        return {
            'report_date': timezone.now().isoformat(),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'production_summary': self.get_production_summary(start_date, end_date),
            'quality_statistics': self.get_quality_statistics(start_date, end_date),
            'equipment_efficiency': self.get_equipment_efficiency(start_date, end_date),
            'labor_efficiency': self.get_labor_efficiency(start_date, end_date),
            'cost_analysis': self.get_cost_analysis(start_date, end_date),
            'on_time_delivery': self.get_on_time_delivery_rate(start_date, end_date),
            'production_trend': self.get_production_trend(start_date, end_date)
        }
