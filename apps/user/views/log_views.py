from django.views.generic import ListView
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
import json
from apps.user.models import SystemOperationLog, SystemLog
from django.db.models import Q, Count

class LogListAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """日志列表API视图"""
    permission_required = 'user.view_systemoperationlog'
    
    def get(self, request):
        """获取日志列表"""
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        keyword = request.GET.get('keyword', '')
        action = request.GET.get('action', '')
        
        queryset = SystemOperationLog.objects.all()
        
        if keyword:
            queryset = queryset.filter(
                Q(user__username__icontains=keyword) |
                Q(ip_address__icontains=keyword) |
                Q(user_agent__icontains=keyword)
            )
        
        if action:
            queryset = queryset.filter(action=action)
        
        total = queryset.count()
        logs = queryset[(page-1)*limit:page*limit]
        
        data = []
        for log in logs:
            data.append({
                'id': log.id,
                'user': log.user.username if log.user else 'Unknown',
                'action': log.action,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'created_at': log.create_time.strftime('%Y-%m-%d %H:%M:%S') if log.create_time else '',
                'details': log.details
            })
        
        return JsonResponse({
            'code': 200,
            'msg': 'success',
            'data': {
                'total': total,
                'items': data
            }
        })


class LogDetailAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """日志详情API视图"""
    permission_required = 'user.view_systemoperationlog'
    
    def get(self, request, pk):
        """获取日志详情"""
        try:
            log = SystemOperationLog.objects.get(id=pk)
            data = {
                'id': log.id,
                'user': log.user.username if log.user else 'Unknown',
                'action': log.action,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'created_at': log.create_time.strftime('%Y-%m-%d %H:%M:%S') if log.create_time else '',
                'details': log.details
            }
            
            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': data
            })
        
        except SystemOperationLog.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': 'Log not found'
            })


class SystemOperationLogListView(LoginRequiredMixin, ListView):
    """系统操作日志列表视图"""
    model = SystemLog
    template_name = 'log/list.html'
    context_object_name = 'logs'
    paginate_by = 10
    ordering = ['-created_at']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 添加日志类型统计数据
        log_type_stats = SystemLog.objects.values('log_type').annotate(count=Count('id'))
        # 获取日志类型映射
        log_type_mapping = dict(SystemLog.LOG_TYPES)
        # 转换为图表所需格式
        chart_data = []
        for stat in log_type_stats:
            log_type = stat['log_type']
            chart_data.append({
                'name': log_type_mapping.get(log_type, log_type),
                'value': stat['count']
            })
        # 如果没有数据，添加默认数据以确保图表正常显示
        if not chart_data:
            for type_code, type_name in SystemLog.LOG_TYPES:
                chart_data.append({
                    'name': type_name,
                    'value': 0
                })
        # 添加日志类型选项用于过滤
        context['log_types'] = SystemLog.LOG_TYPES
        # 确保chart_data是有效的列表
        if not isinstance(chart_data, list):
            chart_data = []
        # 将chart_data转换为JSON字符串，确保模板中正确解析
        context['chart_data_json'] = json.dumps(chart_data, ensure_ascii=False)
        context['chart_data'] = chart_data
        # 添加搜索参数
        context['search'] = self.request.GET.get('search', '')
        context['log_type'] = self.request.GET.get('log_type', '')
        # 调试信息：输出图表数据
        print('Chart Data:', chart_data)
        print('Chart Data JSON:', context['chart_data_json'])
        return context
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # 添加搜索过滤
        search = self.request.GET.get('search', '')
        log_type = self.request.GET.get('log_type', '')
        
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(module__icontains=search) |
                Q(action__icontains=search)
            )
        
        if log_type:
            queryset = queryset.filter(log_type=log_type)
        
        return queryset