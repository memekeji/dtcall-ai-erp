from django.views.generic import ListView
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
import json
from apps.user.models import SystemOperationLog, SystemLog
from apps.user.utils.log_sanitizer import sanitize_log_record
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
        logs = queryset[(page - 1) * limit:page * limit]

        data = []
        for log in logs:
            record = {
                'id': log.id,
                'user': log.user.username if log.user else 'Unknown',
                'action': log.action,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'created_at': log.create_time.strftime('%Y-%m-%d %H:%M:%S') if log.create_time else '',
                'details': log.details
            }
            data.append(sanitize_log_record(record))

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
            record = {
                'id': log.id,
                'user': log.user.username if log.user else 'Unknown',
                'action': log.action,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'created_at': log.create_time.strftime('%Y-%m-%d %H:%M:%S') if log.create_time else '',
                'details': log.details
            }

            sanitized_record = sanitize_log_record(record)

            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': sanitized_record
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
        log_type_stats = SystemLog.objects.values(
            'log_type').annotate(count=Count('id'))
        log_type_mapping = dict(SystemLog.LOG_TYPES)
        chart_data = []
        for stat in log_type_stats:
            log_type = stat['log_type']
            chart_data.append({
                'name': log_type_mapping.get(log_type, log_type),
                'value': stat['count']
            })
        if not chart_data:
            for type_code, type_name in SystemLog.LOG_TYPES:
                chart_data.append({
                    'name': type_name,
                    'value': 0
                })
        context['log_types'] = SystemLog.LOG_TYPES
        if not isinstance(chart_data, list):
            chart_data = []
        context['chart_data_json'] = json.dumps(chart_data, ensure_ascii=False)
        context['chart_data'] = chart_data
        context['search'] = self.request.GET.get('search', '')
        context['log_type'] = self.request.GET.get('log_type', '')
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
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

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 20))
            search = request.GET.get('search', '')
            log_type = request.GET.get('log_type', '')

            queryset = SystemLog.objects.all()

            if search:
                queryset = queryset.filter(
                    Q(user__username__icontains=search) |
                    Q(module__icontains=search) |
                    Q(action__icontains=search)
                )

            if log_type:
                queryset = queryset.filter(log_type=log_type)

            total = queryset.count()
            logs = queryset[(page - 1) * limit:page * limit]

            data = []
            for log in logs:
                record = {
                    'id': log.id,
                    'user': log.user.username if log.user else 'Unknown',
                    'log_type': log.log_type,
                    'module': log.module,
                    'action': log.action,
                    'content': log.content,
                    'ip_address': log.ip_address,
                    'user_agent': log.user_agent,
                    'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else '',
                }
                data.append(sanitize_log_record(record))

            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': {
                    'total': total,
                    'items': data
                }
            })

        return super().get(request, *args, **kwargs)
