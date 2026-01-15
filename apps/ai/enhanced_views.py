"""
AI工作流增强API视图
提供增强的工作流管理、调试、监控和权限控制接口
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from django.views import View
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from apps.ai.models import (
    AIWorkflow, AIWorkflowExecution, WorkflowNode, 
    WorkflowConnection, NodeExecution
)
from apps.ai.services.enhanced_workflow_engine import (
    workflow_engine, ExecutionMode
)
from apps.ai.services.workflow_debug_monitor import (
    debugger_service, monitoring_service, optimization_service
)
from apps.ai.services.workflow_permission_security import (
    permission_service, api_key_service, content_security_service, audit_log_service
)
from apps.ai.services.enhanced_model_service import model_service

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowEnhancedExecuteView(View):
    """增强型工作流执行API"""
    
    def post(self, request, pk):
        """执行工作流（支持同步/异步/并行模式）"""
        try:
            workflow = AIWorkflow.objects.get(id=pk)
            
            if workflow.status != 'published':
                return JsonResponse({
                    'status': 'error',
                    'message': '只能执行已发布的工作流'
                }, status=400)
            
            execution_mode = request.POST.get('mode', 'sync')
            timeout = int(request.POST.get('timeout', 300))
            
            try:
                input_data = json.loads(request.body) if request.content_type == 'application/json' else {}
            except:
                input_data = {}
            
            execution = workflow_engine.create_execution(
                str(workflow.id),
                request.user.id,
                input_data
            )
            
            mode = ExecutionMode.SYNC
            if execution_mode == 'async':
                mode = ExecutionMode.ASYNC
            elif execution_mode == 'parallel':
                mode = ExecutionMode.PARALLEL
            
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    workflow_engine.execute_workflow(str(execution.id), mode, timeout)
                )
            finally:
                loop.close()
            
            audit_log_service.log_operation(
                user_id=request.user.id,
                operation_type='workflow_execute',
                resource_type='workflow',
                resource_id=str(workflow.id),
                details={
                    'execution_id': str(result.id),
                    'mode': execution_mode,
                    'status': result.status
                },
                ip_address=self._get_client_ip(request)
            )
            
            return JsonResponse({
                'status': 'success',
                'execution_id': str(result.id),
                'output_data': result.output_data,
                'error_message': result.error_message,
                'execution_time': (result.completed_at - result.started_at).total_seconds() if result.started_at and result.completed_at else None
            })
            
        except AIWorkflow.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '工作流不存在'}, status=404)
        except Exception as e:
            logger.error(f"工作流执行失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    def _get_client_ip(self, request):
        """获取客户端IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowDebugView(View):
    """工作流调试API"""
    
    def post(self, request, pk):
        """启动调试会话"""
        try:
            workflow = AIWorkflow.objects.get(id=pk)
            
            try:
                input_data = json.loads(request.body) if request.content_type == 'application/json' else {}
            except:
                input_data = {}
            
            breakpoints = request.POST.getlist('breakpoints', [])
            
            result = debugger_service.execute_with_debug(
                str(workflow.id),
                request.user.id,
                input_data,
                breakpoints
            )
            
            return JsonResponse({
                'status': 'success',
                'result': result
            })
            
        except AIWorkflow.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '工作流不存在'}, status=404)
        except Exception as e:
            logger.error(f"调试失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    def get(self, request, pk):
        """获取调试会话状态"""
        session_id = request.GET.get('session_id')
        
        if not session_id:
            return JsonResponse({'status': 'error', 'message': '缺少session_id'}, status=400)
        
        status = debugger_service.get_session_status(session_id)
        
        if not status:
            return JsonResponse({'status': 'error', 'message': '调试会话不存在'}, status=404)
        
        return JsonResponse({
            'status': 'success',
            'session_status': status
        })


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowMonitorView(View):
    """工作流监控API"""
    
    def get(self, request, pk):
        """获取工作流监控数据"""
        try:
            time_range = request.GET.get('time_range', '24h')
            
            if time_range == '1h':
                delta = timedelta(hours=1)
            elif time_range == '24h':
                delta = timedelta(hours=24)
            elif time_range == '7d':
                delta = timedelta(days=7)
            else:
                delta = timedelta(hours=24)
            
            metrics = monitoring_service.get_workflow_metrics(str(pk), delta)
            health = monitoring_service.get_workflow_health_status(str(pk))
            
            return JsonResponse({
                'status': 'success',
                'metrics': metrics,
                'health': health
            })
            
        except Exception as e:
            logger.error(f"获取监控数据失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    def post(self, request, pk):
        """设置告警阈值"""
        try:
            data = json.loads(request.body)
            metric = data.get('metric')
            threshold = data.get('threshold')
            
            if not metric or threshold is None:
                return JsonResponse({'status': 'error', 'message': '参数不完整'}, status=400)
            
            monitoring_service.set_alert_threshold(metric, threshold)
            
            audit_log_service.log_operation(
                user_id=request.user.id,
                operation_type='set_alert_threshold',
                resource_type='workflow',
                resource_id=str(pk),
                details={'metric': metric, 'threshold': threshold}
            )
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"设置告警阈值失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowPermissionView(View):
    """工作流权限管理API"""
    
    def get(self, request, pk):
        """获取权限信息"""
        try:
            access_list = permission_service.get_workflow_access_list(str(pk))
            user_perms = permission_service.get_user_permissions(
                request.user.id, str(pk)
            )
            
            return JsonResponse({
                'status': 'success',
                'access_list': access_list,
                'user_permissions': user_perms
            })
            
        except Exception as e:
            logger.error(f"获取权限信息失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    def post(self, request, pk):
        """授予权限"""
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            role = data.get('role')
            
            if not user_id or not role:
                return JsonResponse({'status': 'error', 'message': '参数不完整'}, status=400)
            
            success = permission_service.grant_permission(
                str(pk),
                int(user_id),
                role,
                request.user.id
            )
            
            if success:
                audit_log_service.log_operation(
                    user_id=request.user.id,
                    operation_type='grant_permission',
                    resource_type='workflow',
                    resource_id=str(pk),
                    details={'target_user': user_id, 'role': role}
                )
            
            return JsonResponse({'status': 'success' if success else 'error'})
            
        except Exception as e:
            logger.error(f"授予权限失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    def delete(self, request, pk):
        """撤销权限"""
        try:
            user_id = request.GET.get('user_id')
            
            if not user_id:
                return JsonResponse({'status': 'error', 'message': '缺少user_id'}, status=400)
            
            success = permission_service.revoke_permission(str(pk), int(user_id))
            
            if success:
                audit_log_service.log_operation(
                    user_id=request.user.id,
                    operation_type='revoke_permission',
                    resource_type='workflow',
                    resource_id=str(pk),
                    details={'target_user': user_id}
                )
            
            return JsonResponse({'status': 'success' if success else 'error'})
            
        except Exception as e:
            logger.error(f"撤销权限失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class APIKeyManagementView(View):
    """API密钥管理API"""
    
    def get(self, request):
        """获取API密钥列表"""
        try:
            keys = []
            for key_id in api_key_service.api_keys:
                info = api_key_service.get_key_info(key_id)
                if info and info['user_id'] == request.user.id:
                    keys.append(info)
            
            return JsonResponse({
                'status': 'success',
                'api_keys': keys
            })
            
        except Exception as e:
            logger.error(f"获取API密钥列表失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    def post(self, request):
        """创建API密钥"""
        try:
            data = json.loads(request.body)
            workflow_ids = data.get('workflow_ids', [])
            permissions = data.get('permissions', [])
            rate_limit = data.get('rate_limit', 100)
            expires_in_days = data.get('expires_in_days')
            
            result = api_key_service.create_api_key(
                user_id=request.user.id,
                workflow_ids=workflow_ids,
                permissions=permissions,
                rate_limit=rate_limit,
                expires_in_days=expires_in_days
            )
            
            audit_log_service.log_operation(
                user_id=request.user.id,
                operation_type='create_api_key',
                resource_type='api_key',
                resource_id=result['key_id']
            )
            
            return JsonResponse({
                'status': 'success',
                'key_id': result['key_id'],
                'key_value': result['key_value'],
                'expires_at': result['expires_at']
            })
            
        except Exception as e:
            logger.error(f"创建API密钥失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class APIKeyRevokeView(View):
    """撤销API密钥"""
    
    def post(self, request, key_id):
        """撤销API密钥"""
        try:
            success = api_key_service.revoke_api_key(key_id)
            
            if success:
                audit_log_service.log_operation(
                    user_id=request.user.id,
                    operation_type='revoke_api_key',
                    resource_type='api_key',
                    resource_id=key_id
                )
            
            return JsonResponse({'status': 'success' if success else 'error'})
            
        except Exception as e:
            logger.error(f"撤销API密钥失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class ContentSecurityView(View):
    """内容安全检查API"""
    
    def post(self, request):
        """检查内容安全性"""
        try:
            data = json.loads(request.body)
            content = data.get('content', '')
            
            result = content_security_service.check_content(content)
            
            return JsonResponse({
                'status': 'success',
                'check_result': result
            })
            
        except Exception as e:
            logger.error(f"内容安全检查失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class AuditLogView(View):
    """审计日志API"""
    
    def get(self, request):
        """查询审计日志"""
        try:
            resource_type = request.GET.get('resource_type')
            resource_id = request.GET.get('resource_id')
            start_time_str = request.GET.get('start_time')
            end_time_str = request.GET.get('end_time')
            limit = int(request.GET.get('limit', 100))
            
            start_time = None
            end_time = None
            if start_time_str:
                start_time = datetime.fromisoformat(start_time_str)
            if end_time_str:
                end_time = datetime.fromisoformat(end_time_str)
            
            logs = audit_log_service.query_logs(
                user_id=request.user.id if not request.user.is_superuser else None,
                resource_type=resource_type,
                resource_id=resource_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
            
            return JsonResponse({
                'status': 'success',
                'logs': logs
            })
            
        except Exception as e:
            logger.error(f"查询审计日志失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class ModelListView(View):
    """模型列表API"""
    
    def get(self, request):
        """获取可用模型列表"""
        try:
            models = model_service.get_available_models()
            
            return JsonResponse({
                'status': 'success',
                'models': models
            })
            
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class PerformanceAnalysisView(View):
    """性能分析API"""
    
    def get(self, request, pk):
        """获取性能分析结果"""
        try:
            analysis = optimization_service.analyze_bottleneck(str(pk))
            
            cache_stats = optimization_service.get_cache_stats()
            
            return JsonResponse({
                'status': 'success',
                'analysis': analysis,
                'cache_stats': cache_stats
            })
            
        except Exception as e:
            logger.error(f"性能分析失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowExecutionHistoryView(View):
    """工作流执行历史API"""
    
    def get(self, request, pk):
        """获取执行历史"""
        try:
            limit = int(request.GET.get('limit', 50))
            offset = int(request.GET.get('offset', 0))
            
            history = monitoring_service.get_execution_history(
                str(pk),
                limit=limit,
                offset=offset
            )
            
            return JsonResponse({
                'status': 'success',
                'history': history
            })
            
        except Exception as e:
            logger.error(f"获取执行历史失败: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
