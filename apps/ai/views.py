import logging
import os
import uuid
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect, StreamingHttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.utils import timezone
import json

from .services.workflow_service import WorkflowService
from .services.business_feedback import record_business_ai_feedback
from .services.operation_service import operation_service
from .services.rollback_service import rollback_service
from .services.enterprise_agents import enterprise_agent_service

from .models import (
    AIModelConfig,
    AIWorkflow,
    AIWorkflowExecution,
    AIChat,
    AIChatMessage,
    AIOperation,
    AIKnowledgeBase,
    AIKnowledgeItem,
    AIKnowledgeVector,
    AISalesStrategy,
    AIIntentRecognition,
    AIEmotionAnalysis,
    AIComplianceRule,
    AIActionTrigger,
    AILog
)
from .forms import (
    AIModelConfigForm,
    AIWorkflowForm,
    AIKnowledgeBaseForm,
    AIKnowledgeItemForm,
    AISalesStrategyForm,
    AIIntentRecognitionForm,
    AIEmotionAnalysisForm,
    AIComplianceRuleForm,
    AIActionTriggerForm
)
from .utils.ai_client import AIClient, AIClientError
from .services.enhanced_intent_service import enhanced_intent_service
from apps.common.cache_service import CacheManager
from .services.complete_node_config import (
    get_node_config_schema,
    get_node_full_config,
    get_all_node_configs,
    get_nodes_by_category
)


def invalidate_ai_model_runtime_cache(model_id=None):
    CacheManager.invalidate_ai_related(model_id=model_id)
    try:
        from apps.ai.utils.ai_config_manager import get_ai_config_manager
        get_ai_config_manager().refresh_configs()
    except Exception as exc:
        logging.getLogger(__name__).warning(f"刷新AI配置缓存失败: {exc}")


def normalize_confirmable_operation_payload(payload):
    if not isinstance(payload, dict):
        return payload

    task = payload.get('task')
    if not isinstance(task, dict):
        return payload

    if task.get('execution_status') in {'executed', 'cancelled', 'rolled_back'}:
        return payload

    action = str(payload.get('action') or task.get('action') or '').lower()
    intent_type = str(payload.get('intent_type') or task.get('intent_type') or '')
    if action not in enhanced_intent_service.MUTATING_ACTIONS and intent_type not in {'DATA_CREATE', 'DATA_UPDATE', 'DATA_DELETE'}:
        return payload

    confirmation = dict(payload.get('confirmation') or {})
    operation_id = task.get('operation_id') or payload.get('operation_id')
    token = task.get('confirmation_token') or confirmation.get('token')
    if not operation_id or not token:
        return payload

    task_title = task.get('title') or '业务操作'
    notice_action = action or task.get('action') or 'create'
    safety_notice = enhanced_intent_service._get_business_safety_notice(notice_action)
    message_text = f'已识别到{task_title}意图。{safety_notice}'
    confirm_option = {
        'text': '确认并执行',
        'intent': task.get('intent_type') or intent_type or 'AI_CHAT',
        'action': 'confirm_operation',
        'operation_id': operation_id,
        'token': token,
        'enabled': True,
    }
    cancel_option = {
        'text': '取消操作',
        'intent': 'AI_CHAT',
        'action': 'cancel',
        'enabled': True,
    }

    normalized = dict(payload)
    task_payload = dict(task)
    task_payload.update({
        'operation_id': operation_id,
        'confirmation_token': token,
        'confirmation_message': message_text,
        'message': message_text,
        'safety_notice': safety_notice,
        'options': [confirm_option, cancel_option],
    })
    confirmation.update({
        'required': True,
        'token': token,
        'message': message_text,
    })
    normalized.update({
        'task': task_payload,
        'options': [confirm_option, cancel_option],
        'operation_id': operation_id,
        'requires_confirmation': True,
        'confirmation': confirmation,
        'message': message_text,
        'ai_message': message_text,
    })
    return normalized


# AI模型配置视图
class AIModelConfigListView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    model = AIModelConfig
    template_name = 'ai/model_config_list.html'
    context_object_name = 'model_configs'
    permission_required = 'ai.view_aimodelconfig'
    paginate_by = 10

    def get_queryset(self):
        return AIModelConfig.objects.order_by('-created_at')

    def get(self, request, *args, **kwargs):
        # 检查是否为AJAX请求
        # 只通过X-Requested-With头判断，避免accepts导致的问题
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # 处理AJAX请求，返回JSON数据
            queryset = self.get_queryset()
            paginator = Paginator(queryset, self.paginate_by)

            page = request.GET.get('page')
            objects = paginator.get_page(page)

            # 构造Layui表格需要的数据格式
            data = {
                "code": 0,
                "msg": "",
                "count": paginator.count,
                "data": [
                    {
                        "id": obj.id,
                        "name": obj.name,
                        "api_base": obj.base_url,
                        "model_names": obj.model_names or [],
                        "is_default": obj.is_default,
                        "is_active": obj.is_active,
                        "created_at": obj.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    } for obj in objects
                ]
            }

            return JsonResponse(data)
        else:
            # 处理HTML请求，返回完整页面
            return super().get(request, *args, **kwargs)


class AIModelConfigCreateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        CreateView):
    model = AIModelConfig
    form_class = AIModelConfigForm
    template_name = 'ai/model_config_form.html'
    permission_required = 'ai.add_aimodelconfig'
    success_url = reverse_lazy('ai:model_config_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        invalidate_ai_model_runtime_cache(self.object.id)
        messages.success(self.request, 'AI模型配置创建成功')
        return response


class AIModelConfigUpdateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        UpdateView):
    model = AIModelConfig
    form_class = AIModelConfigForm
    template_name = 'ai/model_config_form.html'
    permission_required = 'ai.change_aimodelconfig'
    success_url = reverse_lazy('ai:model_config_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        invalidate_ai_model_runtime_cache(self.object.id)
        messages.success(self.request, 'AI模型配置更新成功')
        return response


class AIModelConfigDeleteView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DeleteView):
    model = AIModelConfig
    template_name = 'ai/model_config_confirm_delete.html'
    permission_required = 'ai.delete_aimodelconfig'
    success_url = reverse_lazy('ai:model_config_list')

    def delete(self, request, *args, **kwargs):
        model_id = self.get_object().id
        response = super().delete(request, *args, **kwargs)
        invalidate_ai_model_runtime_cache(model_id)
        messages.success(self.request, 'AI模型配置删除成功')
        return response


class AIModelConfigDetailView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DetailView):
    model = AIModelConfig
    template_name = 'ai/model_config_detail.html'
    context_object_name = 'model_config'
    permission_required = 'ai.view_aimodelconfig'


class AIModelConfigValidateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DetailView):
    model = AIModelConfig
    permission_required = 'ai.view_aimodelconfig'

    def get(self, request, *args, **kwargs):
        return self.validate_connection()

    def post(self, request, *args, **kwargs):
        return self.validate_connection()

    def validate_connection(self):
        model_config = self.get_object()
        logger = logging.getLogger(__name__)
        display_base_url = self._get_base_url(model_config)
        try:
            logger.info(f"测试AI模型连接 - 模型ID: {model_config.id}")
            logger.info(
                f"模型配置 - 基础URL: {display_base_url}")
            logger.info(f"API密钥: {'***' if model_config.api_key else '未配置'}")

            client = AIClient(model_config_id=model_config.id)
            result = self._run_model_validation(client, model_config)
            display_result = self._format_validation_result(result)
            logger.info(f"AI模型连接成功 - 模型ID: {model_config.id}, 模型: {model_config.primary_model_name()}")
            return JsonResponse({
                'status': 'success',
                'message': '连接成功',
                'result': display_result,
                'details': {
                    'provider': model_config.provider,
                    'base_url': display_base_url,
                    'model_name': self._get_primary_model_name(model_config),
                    'model_names': self._get_model_names(model_config),
                }
            })
        except AIClientError as e:
            import traceback
            logger.error(f"AI模型连接失败 - 模型ID: {model_config.id}")
            logger.error(f"错误类型: {type(e).__name__}")
            logger.error(f"错误详情: {str(e)}")
            logger.error(f"完整错误堆栈: {traceback.format_exc()}")
            logger.error(
                f"模型配置 - 基础URL: {display_base_url}")

            error_payload = self._build_validation_error_payload(model_config, e)
            return JsonResponse(error_payload)
        except Exception as e:
            import traceback
            logger.error(f"AI模型连接失败 - 模型ID: {model_config.id}")
            logger.error(f"错误类型: {type(e).__name__}")
            logger.error(f"错误详情: {str(e)}")
            logger.error(f"完整错误堆栈: {traceback.format_exc()}")
            logger.error(
                f"模型配置 - 基础URL: {display_base_url}")
            error_payload = self._build_validation_error_payload(model_config, e)
            return JsonResponse(error_payload)

    def _get_base_url(self, model_config):
        return getattr(model_config, 'base_url', None) or getattr(model_config, 'api_base', '')

    def _run_model_validation(self, client, model_config):
        test_message = [{"role": "user", "content": "你好，这是一个连接测试。"}]
        return client.chat_completion(
            test_message,
            model=self._get_primary_model_name(model_config),
        )

    def _get_primary_model_name(self, model_config):
        if hasattr(model_config, 'primary_model_name'):
            return model_config.primary_model_name()
        names = getattr(model_config, 'model_names', None) or []
        return names[0] if names else getattr(model_config, 'model_name', 'gpt-4o-mini')

    def _get_model_names(self, model_config):
        names = getattr(model_config, 'model_names', None) or []
        return list(names) if isinstance(names, (list, tuple)) else []

    def _format_validation_result(self, result):
        if isinstance(result, (list, tuple)):
            return f"向量维度: {len(result)}"
        text = str(result or '')
        return text[:50] + '...' if len(text) > 50 else text

    def _build_validation_error_payload(self, model_config, error):
        error_type = type(error).__name__
        status_code = getattr(error, 'status_code', None)
        error_code = getattr(error, 'error_code', None)
        detail = getattr(error, 'detail', None) or str(error)
        message = self._build_validation_message(error_type, status_code, detail)
        return {
            'status': 'error',
            'message': message,
            'details': {
                'provider': model_config.provider,
                'base_url': self._get_base_url(model_config),
                'model_name': self._get_primary_model_name(model_config),
                'model_names': self._get_model_names(model_config),
                'error_type': error_type,
                'error_code': error_code,
                'status_code': status_code,
                'detail': detail[:500] if isinstance(detail, str) else str(detail),
                'suggestion': self._get_error_suggestion(
                    error_type,
                    model_config,
                    status_code=status_code,
                    error_code=error_code,
                    detail=detail,
                )
            }
        }

    def _is_model_channel_error(self, detail):
        detail_lower = str(detail or '').lower()
        return (
            'no available channel for model' in detail_lower
            or 'model_not_found' in detail_lower
            or 'model not found' in detail_lower
        )

    def _build_validation_message(self, error_type, status_code=None, detail=None):
        if self._is_model_channel_error(detail):
            return '连接失败：当前模型在所选渠道不可用'
        if status_code == 401:
            return '连接失败：API 密钥无效或已过期'
        if status_code == 403:
            return '连接失败：当前密钥无权访问该模型或接口'
        if status_code == 404:
            return '连接失败：API 地址或模型接口不存在'
        if status_code == 429:
            return '连接失败：请求过于频繁或额度已耗尽'
        if status_code == 500:
            return '连接失败：模型服务端返回 500 错误'
        if status_code == 502:
            return '连接失败：模型网关返回 502 错误'
        if status_code == 503:
            return '连接失败：模型服务暂时不可用（503）'
        if status_code == 504:
            return '连接失败：模型服务网关超时（504）'
        if error_type == 'AIClientError':
            return '连接失败，请检查模型配置或稍后重试'
        return '连接失败，请检查模型配置后重试'

    def _get_error_suggestion(self, error_type, model_config, status_code=None, error_code=None, detail=None):
        """根据错误类型提供修复建议"""
        if self._is_model_channel_error(detail):
            return (
                f'当前渠道未返回模型 {self._get_primary_model_name(model_config)} 的可用实例。'
                '请确认模型名称是否与服务商控制台完全一致、该模型是否已开通，'
                '或检查该服务商是否要求使用 /responses 等特定 OpenAI 兼容接口。'
            )
        if status_code == 401:
            return '请检查数据库中保存的 API 密钥是否正确、是否已过期，并确认该密钥属于当前服务地址'
        if status_code == 403:
            return '请确认当前密钥已开通目标模型权限，并检查服务商侧访问控制设置'
        if status_code == 404:
            return f'请检查 API 地址或兼容路径是否正确。当前配置地址：{self._get_base_url(model_config)}'
        if status_code == 429:
            return '请检查调用频率限制、账户余额或套餐额度'
        if status_code in {500, 502, 503, 504}:
            return '模型服务端暂时异常，建议稍后重试；若持续失败，请联系模型服务提供方检查网关和实例状态'
        if error_code == 'timeout':
            return '请求超时，请检查网络连通性、代理配置或服务响应速度'
        if error_code == 'connection_error':
            return f'无法连接到模型服务，请检查网络、DNS、代理或服务地址。当前配置地址：{self._get_base_url(model_config)}'
        suggestions = {
            'ConnectionError': '请检查网络连接是否正常，以及API地址是否正确',
            'TimeoutError': '请求超时，请检查网络连接或API地址是否正确',
            'HTTPError': f'HTTP请求失败，请检查API地址是否正确。当前配置的地址是: {self._get_base_url(model_config)}',
            'AIClientError': 'AI客户端错误，请检查API密钥和API地址是否正确',
            'KeyError': 'API响应格式错误，请检查API地址是否正确',
            'ValueError': '参数错误，请检查模型配置是否正确',
            'ImportError': '缺少依赖库，请安装相关依赖',
            'AttributeError': '代码错误，请联系开发人员',
            'TypeError': '类型错误，请检查API地址格式是否正确'}

        return suggestions.get(error_type, '请检查模型配置是否正确，特别是API地址和API密钥')


class ListAvailableAIProvidersView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    permission_required = 'ai.view_aimodelconfig'

    def get(self, request, *args, **kwargs):
        providers = AIModelConfig.PROVIDERS
        return JsonResponse(
            {'providers': [{'value': p[0], 'label': p[1]} for p in providers]})


# AI工作流视图
class AIWorkflowListView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    model = AIWorkflow
    template_name = 'ai/workflow_list.html'
    context_object_name = 'workflows'
    permission_required = 'ai.view_aiworkflow'
    paginate_by = 10

    def get_queryset(self):
        return AIWorkflow.objects.select_related(
            'owner', 'created_by').order_by('-created_at')

    def get(self, request, *args, **kwargs):
        # 检查是否为AJAX请求
        # 只通过X-Requested-With头判断，避免accepts导致的问题
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # 处理AJAX请求，返回JSON数据
            queryset = self.get_queryset()
            paginator = Paginator(queryset, self.paginate_by)

            page = request.GET.get('page')
            objects = paginator.get_page(page)

            # 构造Layui表格需要的数据格式
            data = {
                "code": 0,
                "msg": "",
                "count": paginator.count,
                "data": [
                    {
                        "id": obj.id,
                        "name": obj.name,
                        "status": obj.status,
                        "created_by__name": obj.created_by.name if obj.created_by and hasattr(
                            obj.created_by,
                            'name') else '',
                        "created_at": obj.created_at.strftime('%Y-%m-%d %H:%M:%S')} for obj in objects]}

            return JsonResponse(data)
        else:
            # 处理HTML请求，返回完整页面
            return super().get(request, *args, **kwargs)


class AIWorkflowCreateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        CreateView):
    model = AIWorkflow
    form_class = AIWorkflowForm
    template_name = 'ai/workflow_form.html'
    permission_required = 'ai.add_aiworkflow'
    success_url = reverse_lazy('ai:workflow_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'AI工作流创建成功')
        return response


class AIWorkflowUpdateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        UpdateView):
    model = AIWorkflow
    form_class = AIWorkflowForm
    template_name = 'ai/workflow_form.html'
    permission_required = 'ai.change_aiworkflow'
    success_url = reverse_lazy('ai:workflow_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'AI工作流更新成功')
        return response

    def post(self, request, *args, **kwargs):
        """处理AJAX请求保存工作流节点数据"""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                workflow = self.get_object()
                data = json.loads(request.body)

                nodes_data = data.get('nodes', [])
                connections_data = data.get('connections', [])

                service = WorkflowService()
                service.update_workflow_nodes(
                    workflow.id, nodes_data, connections_data)

                return JsonResponse({
                    'status': 'success',
                    'message': '工作流保存成功',
                    'node_count': len(nodes_data),
                    'connection_count': len(connections_data)
                })
            except json.JSONDecodeError:
                return JsonResponse({
                    'status': 'error',
                    'message': '无效的JSON数据'
                }, status=400)
            except Exception as e:
                logger.error(f'保存工作流失败: {e}', exc_info=True)
                return JsonResponse({
                    'status': 'error',
                    'message': '工作流保存失败，请稍后重试'
                }, status=500)

        return super().post(request, *args, **kwargs)


class AIWorkflowDeleteView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DeleteView):
    model = AIWorkflow
    permission_required = 'ai.delete_aiworkflow'

    def delete(self, request, *args, **kwargs):
        workflow = self.get_object()
        workflow_name = workflow.name

        try:
            workflow.delete()
            return JsonResponse({
                'success': True,
                'message': f'工作流 "{workflow_name}" 删除成功'
            })
        except Exception as e:
            logger.error(f'删除工作流失败: {str(e)}')
            return JsonResponse({
                'success': False,
                'message': '删除失败，请稍后重试'
            }, status=500)

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


class AIWorkflowDesignerView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DetailView):
    model = AIWorkflow
    template_name = 'ai/workflow_designer.html'
    permission_required = 'ai.change_aiworkflow'
    context_object_name = 'workflow'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nodes'] = self.object.nodes.all()
        context['connections'] = self.object.connections.all()
        return context


class AIWorkflowPublishView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        UpdateView):
    model = AIWorkflow
    fields = ['status']
    permission_required = 'ai.change_aiworkflow'

    def post(self, request, *args, **kwargs):
        workflow = self.get_object()

        if workflow.status == 'published':
            return JsonResponse({
                'status': 'error',
                'message': '工作流已经发布过了'
            })

        workflow.status = 'published'
        workflow.save()

        return JsonResponse({
            'status': 'success',
            'message': '发布成功'
        })


class AIWorkflowDetailView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DetailView):
    model = AIWorkflow
    template_name = 'ai/workflow_detail.html'
    permission_required = 'ai.view_aiworkflow'
    context_object_name = 'workflow'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nodes'] = self.object.nodes.all()
        context['connections'] = self.object.connections.all()
        return context


class AIWorkflowJsonDetailView(LoginRequiredMixin, DetailView):
    """工作流JSON详情API，用于工作流设计器数据加载"""
    model = AIWorkflow

    def get(self, request, *args, **kwargs):
        try:
            workflow = self.get_object()

            if not workflow.is_public:
                if not request.user.is_authenticated:
                    return JsonResponse({
                        'status': 'error',
                        'message': '请先登录'
                    }, status=401)

            nodes = workflow.nodes.all()
            connections = workflow.connections.all()

            def parse_config(config):
                if config is None:
                    return {}
                if isinstance(config, str):
                    try:
                        return json.loads(config)
                    except BaseException:
                        return {}
                return config if isinstance(config, dict) else {}

            nodes_data = []
            for node in nodes:
                node_data = {
                    'id': str(node.id),
                    'name': node.name,
                    'type': node.node_type or 'basic',
                    'x': int(node.position_x) if node.position_x else 100,
                    'y': int(node.position_y) if node.position_y else 200,
                    'config': parse_config(node.config)
                }
                nodes_data.append(node_data)

            connections_data = []
            for conn in connections:
                conn_data = {
                    'id': str(
                        conn.id),
                    'source': str(
                        conn.source_node_id) if conn.source_node_id else None,
                    'target': str(
                        conn.target_node_id) if conn.target_node_id else None,
                    'source_handle': conn.source_handle or 'output',
                    'target_handle': conn.target_handle or 'input',
                    'config': parse_config(
                        conn.config)}
                connections_data.append(conn_data)

            return JsonResponse({
                'status': 'success',
                'workflow': {
                    'id': str(workflow.id),
                    'name': workflow.name,
                    'description': workflow.description or '',
                    'status': workflow.status or 'draft',
                    'nodes': nodes_data,
                    'connections': connections_data
                }
            })
        except Exception as e:
            logger.error(f'获取工作流详情失败: {str(e)}')
            return JsonResponse({
                'status': 'error',
                'message': '获取工作流详情失败，请稍后重试'
            }, status=500)


class AIWorkflowExecuteView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DetailView):
    model = AIWorkflow
    permission_required = 'ai.change_aiworkflow'

    def post(self, request, *args, **kwargs):
        import json

        workflow = self.get_object()

        try:
            # 尝试从JSON body获取输入数据
            if request.content_type == 'application/json':
                try:
                    body_data = json.loads(request.body)
                    input_data = body_data.get('input_data', {})
                except json.JSONDecodeError:
                    input_data = {}
            else:
                input_data = request.POST.dict()

            service = WorkflowService()
            execution = service.execute_workflow(
                workflow_id=str(workflow.id),
                user=request.user,
                input_data=input_data
            )
            return JsonResponse({
                'status': 'success',
                'execution_id': str(execution.id),
                'message': '工作流执行已启动'
            })
        except Exception as e:
            logger.error(f'执行工作流失败: {str(e)}')
            return JsonResponse({
                'status': 'error',
                'message': '工作流执行失败，请稍后重试'
            }, status=400)


class AIWorkflowParametersView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DetailView):
    model = AIWorkflow
    permission_required = 'ai.change_aiworkflow'

    def get(self, request, *args, **kwargs):
        workflow = self.get_object()

        try:
            # 从WorkflowVariable获取定义的参数
            pass

            variables = workflow.variables.all()
            parameters = []

            for var in variables:
                parameters.append({
                    'name': var.name,
                    'data_type': var.data_type,
                    'default_value': var.default_value,
                    'description': var.description,
                    'is_required': var.is_required
                })

            # 如果没有定义变量，返回空数组
            return JsonResponse({
                'status': 'success',
                'parameters': parameters,
                'workflow_name': workflow.name
            })

        except Exception as e:
            logger.error(f'获取工作流参数失败: {str(e)}')
            return JsonResponse({
                'status': 'error',
                'message': '获取工作流参数失败，请稍后重试'
            }, status=400)


# AI聊天视图
class AIChatView(LoginRequiredMixin, ListView):
    model = AIChat
    template_name = 'ai/chat.html'

    def get_queryset(self):
        return AIChat.objects.select_related('user').filter(
            user=self.request.user).order_by('-updated_at')

    def get(self, request, *args, **kwargs):
        referrer = request.META.get('HTTP_REFERER')
        if referrer:
            request.session['ai_last_referrer'] = referrer
        # 处理JSON请求，返回聊天会话列表
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            queryset = self.get_queryset()
            chats = [
                {
                    'id': chat.id,
                    'title': chat.title,
                    'created_at': chat.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_at': chat.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                } for chat in queryset
            ]
            return JsonResponse(chats, safe=False)
        return super().get(request, *args, **kwargs)


class AIChatDetailView(
        LoginRequiredMixin,
        DetailView):
    model = AIChat
    template_name = 'ai/chat_detail.html'
    context_object_name = 'chat'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages'] = self.object.messages.order_by('created_at')
        return context

    def get(self, request, *args, **kwargs):
        # 处理JSON请求，返回聊天会话数据
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            chat = self.get_object()
            messages = chat.messages.order_by('created_at')

            return JsonResponse({
                'id': chat.id,
                'title': chat.title,
                'messages': [
                    self._serialize_message(msg) for msg in messages
                ]
            })
        return super().get(request, *args, **kwargs)

    def _serialize_message(self, message):
        payload = self._hydrate_pending_operation_payload(
            message,
            getattr(message, 'runtime_payload', None),
        )
        data = {
            'id': message.id,
            'role': message.role,
            'content': message.content,
            'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        if isinstance(payload, dict):
            task = payload.get('task')
            options = payload.get('options')
            if isinstance(task, dict):
                data['task'] = task
                if message.role == 'assistant' and task.get('message'):
                    data['content'] = task.get('message')
            if isinstance(options, list):
                data['options'] = options
            if isinstance(payload.get('recognition_meta'), dict):
                data['recognition_meta'] = payload.get('recognition_meta')
            if isinstance(payload.get('mcp_context'), dict):
                data['mcp_context'] = payload.get('mcp_context')
        return data

    def _hydrate_pending_operation_payload(self, message, payload):
        if not isinstance(payload, dict):
            return payload

        task = payload.get('task')
        action = str(
            (payload.get('action') or (task.get('action') if isinstance(task, dict) else '') or '')
        ).lower()
        intent_type = str(payload.get('intent_type') or (task.get('intent_type') if isinstance(task, dict) else '') or '')
        if action not in enhanced_intent_service.MUTATING_ACTIONS and intent_type not in {'DATA_CREATE', 'DATA_UPDATE', 'DATA_DELETE'}:
            return payload

        normalized_payload = normalize_confirmable_operation_payload(payload)
        normalized_task = normalized_payload.get('task') if isinstance(normalized_payload, dict) else None
        if isinstance(normalized_task, dict) and normalized_task.get('operation_id') and normalized_task.get('confirmation_token'):
            return normalized_payload

        pending_operation = self._get_pending_operation_for_message(message)
        if not pending_operation:
            return payload

        hydrated = dict(payload)
        task_payload = dict(task or {})
        task_title = task_payload.get('title') or '业务操作'
        safety_notice = enhanced_intent_service._get_business_safety_notice(action or task_payload.get('action') or 'create')
        message_text = f'已识别到{task_title}意图。{safety_notice}'
        confirm_option = {
            'text': '确认并执行',
            'intent': task_payload.get('intent_type') or intent_type or 'AI_CHAT',
            'action': 'confirm_operation',
            'operation_id': pending_operation.id,
            'token': pending_operation.confirmation_token,
            'enabled': True,
        }
        cancel_option = {
            'text': '取消操作',
            'intent': 'AI_CHAT',
            'action': 'cancel',
            'enabled': True,
        }

        task_payload.update({
            'operation_id': pending_operation.id,
            'confirmation_token': pending_operation.confirmation_token,
            'confirmation_message': message_text,
            'message': message_text,
            'safety_notice': safety_notice,
            'options': [confirm_option, cancel_option],
        })
        hydrated['task'] = task_payload
        hydrated['options'] = [confirm_option, cancel_option]
        hydrated['operation_id'] = pending_operation.id
        hydrated['requires_confirmation'] = True
        confirmation = dict(hydrated.get('confirmation') or {})
        confirmation.update({
            'required': True,
            'token': pending_operation.confirmation_token,
            'message': message_text,
        })
        hydrated['confirmation'] = confirmation
        return normalize_confirmable_operation_payload(hydrated)

    def _get_pending_operation_for_message(self, message):
        user = getattr(getattr(self, 'request', None), 'user', None)
        filters = {
            'ai_message_id': getattr(message, 'id', None),
            'status': 'preview',
        }
        user_id = getattr(user, 'id', None)
        if user_id:
            filters['user_id'] = user_id
        return AIOperation.objects.filter(**filters).order_by('-created_at').first()


class AIChatDeleteView(
        LoginRequiredMixin,
        DeleteView):
    model = AIChat
    success_url = reverse_lazy('ai:chat')

    def delete(self, request, *args, **kwargs):
        chat = self.get_object()
        chat.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': '聊天会话已删除'})
        return super().delete(request, *args, **kwargs)


class AIChatCreateView(
        LoginRequiredMixin,
        CreateView):
    model = AIChat
    fields = ['title']

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.session_id = f"chat_{self.request.user.id}_{timezone.now().timestamp()}"
        chat = form.save()
        return JsonResponse(
            {'status': 'success', 'chat_id': chat.id, 'chat_title': chat.title})


class AIChatMessageCreateView(
        LoginRequiredMixin,
        CreateView):
    model = AIChatMessage
    fields = ['content']

    def form_valid(self, form):
        chat_id = self.request.POST.get('chat_id')
        chat = get_object_or_404(AIChat, id=chat_id, user=self.request.user)
        message_content = form.cleaned_data['content']

        try:
            payload = AIChatStreamView()._build_intent_response_payload(
                self.request.user, chat.id, message_content, self.request)
            payload['status'] = 'success' if payload.get('success') else 'error'
            payload.setdefault('ai_message', payload.get('message', '抱歉，我无法处理您的请求'))
            payload.setdefault('user_message', message_content)
            payload.setdefault('intent', payload.get('intent_type') or payload.get('intent'))
            payload.setdefault('confidence', payload.get('confidence', 0))
            return JsonResponse(payload)
        except Exception as e:
            logger.error(f'AI生成失败: {str(e)}')
            return JsonResponse(
                {'status': 'error', 'message': 'AI生成失败，请稍后重试'})


# AI知识库视图
class AIKnowledgeBaseListView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    model = AIKnowledgeBase
    template_name = 'ai/knowledge_base_list.html'
    context_object_name = 'knowledge_bases'
    permission_required = 'ai.view_aiknowledgebase'
    paginate_by = 10

    def get_queryset(self):
        return AIKnowledgeBase.objects.select_related(
            'creator').order_by('-created_at')

    def get(self, request, *args, **kwargs):
        # 检查是否为AJAX请求
        # 只通过X-Requested-With头判断，避免accepts导致的问题
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # 处理AJAX请求，返回JSON数据
            queryset = self.get_queryset()
            paginator = Paginator(queryset, self.paginate_by)

            page = request.GET.get('page')
            objects = paginator.get_page(page)

            # 构造Layui表格需要的数据格式
            data = {
                "code": 0,
                "msg": "",
                "count": paginator.count,
                "data": [
                    {
                        "id": obj.id,
                        "name": obj.name,
                        "description": obj.description,
                        "status": obj.status,
                        "creator__name": obj.creator.name if obj.creator and hasattr(
                            obj.creator,
                            'name') else '',
                        "created_at": obj.created_at.strftime('%Y-%m-%d %H:%M:%S')} for obj in objects]}

            return JsonResponse(data)
        else:
            # 处理HTML请求，返回完整页面
            return super().get(request, *args, **kwargs)


class AIKnowledgeBaseCreateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        CreateView):
    model = AIKnowledgeBase
    form_class = AIKnowledgeBaseForm
    template_name = 'ai/knowledge_base_form.html'
    permission_required = 'ai.add_aiknowledgebase'
    success_url = reverse_lazy('ai:knowledge_base_list')

    def form_valid(self, form):
        form.instance.creator = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'AI知识库创建成功')
        return response


class AIKnowledgeBaseUpdateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        UpdateView):
    model = AIKnowledgeBase
    form_class = AIKnowledgeBaseForm
    template_name = 'ai/knowledge_base_form.html'
    permission_required = 'ai.change_aiknowledgebase'
    success_url = reverse_lazy('ai:knowledge_base_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'AI知识库更新成功')
        return response


class AIKnowledgeBaseDeleteView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DeleteView):
    model = AIKnowledgeBase
    template_name = 'ai/knowledge_base_confirm_delete.html'
    permission_required = 'ai.delete_aiknowledgebase'
    success_url = reverse_lazy('ai:knowledge_base_list')

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, 'AI知识库删除成功')
        return response


class AIKnowledgeBaseDetailView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DetailView):
    model = AIKnowledgeBase
    template_name = 'ai/knowledge_base_detail.html'
    permission_required = 'ai.view_aiknowledgebase'
    context_object_name = 'knowledge_base'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['knowledge_items'] = self.object.items.select_related('creator').order_by('-created_at')
        return context


# AI知识条目视图
class AIKnowledgeItemListView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    model = AIKnowledgeItem
    template_name = 'ai/knowledge_item_list.html'
    context_object_name = 'knowledge_items'
    permission_required = 'ai.view_aiknowledgeitem'
    paginate_by = 10

    def get_queryset(self):
        queryset = AIKnowledgeItem.objects.select_related('knowledge_base', 'creator').order_by('-created_at')
        knowledge_base_id = self.request.GET.get('knowledge_base')
        if knowledge_base_id:
            return queryset.filter(knowledge_base_id=knowledge_base_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['knowledge_bases'] = AIKnowledgeBase.objects.filter(
            status='published')
        return context

    def get(self, request, *args, **kwargs):
        # 检查是否为AJAX请求
        # 只通过X-Requested-With头判断，避免accepts导致的问题
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # 处理AJAX请求，返回JSON数据
            queryset = self.get_queryset()
            paginator = Paginator(queryset, self.paginate_by)

            page = request.GET.get('page')
            objects = paginator.get_page(page)

            # 构造Layui表格需要的数据格式
            data = {"code": 0,
                    "msg": "",
                    "count": paginator.count,
                    "data": [{"id": obj.id,
                              "title": obj.title,
                              "knowledge_type": obj.knowledge_type,
                              "status": obj.status,
                              "knowledge_base__name": obj.knowledge_base.name if obj.knowledge_base and hasattr(obj.knowledge_base,
                                                                                                                'name') else '',
                              "creator__name": obj.creator.name if obj.creator and hasattr(obj.creator,
                                                                                           'name') else '',
                              "created_at": obj.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                              "has_file": True if obj.file else False,
                              "file_name": obj.file.name.split('/')[-1] if obj.file else '',
                              "file_type": obj.file_type if obj.file_type else ''} for obj in objects]}

            return JsonResponse(data)
        else:
            # 处理HTML请求，返回完整页面
            return super().get(request, *args, **kwargs)


class AIKnowledgeItemCreateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        CreateView):
    model = AIKnowledgeItem
    form_class = AIKnowledgeItemForm
    template_name = 'ai/knowledge_item_form.html'
    permission_required = 'ai.add_aiknowledgeitem'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 添加所有知识库到上下文
        context['knowledge_bases'] = AIKnowledgeBase.objects.all()
        return context

    def form_valid(self, form):
        try:
            # 获取表单数据
            form.instance.creator = self.request.user

            # 保存知识库条目
            knowledge_item = form.save()

            # 生成向量
            from apps.ai.services.vector_generation_service import vector_generation_service
            vector_generation_success = vector_generation_service.generate_vector_for_knowledge_item(
                knowledge_item.id)

            # 检查向量是否生成成功
            if not vector_generation_success:
                # 向量化失败，删除已保存的知识库条目
                knowledge_item.delete()
                # 返回错误信息
                if self.request.headers.get(
                        'X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse(
                        {'status': 'error', 'message': '向量化失败，请检查内容并重试'})
                else:
                    messages.error(self.request, '向量化失败，请检查内容并重试')
                    return redirect('ai:knowledge_item_list')

            # 检查是否是AJAX请求
            if self.request.headers.get(
                    'X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'success', 'message': '知识条目创建成功'})
            else:
                messages.success(self.request, '知识条目创建成功')
                return redirect('ai:knowledge_item_list')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"创建知识库条目失败: {str(e)}")

            error_msg = "操作失败，请稍后重试"
            if self.request.headers.get(
                    'X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': error_msg})
            else:
                messages.error(self.request, error_msg)
                return self.form_invalid(form)


class AIKnowledgeItemUpdateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        UpdateView):
    model = AIKnowledgeItem
    form_class = AIKnowledgeItemForm
    template_name = 'ai/knowledge_item_form.html'
    permission_required = 'ai.change_aiknowledgeitem'
    success_url = reverse_lazy('ai:knowledge_item_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 添加所有知识库到上下文
        context['knowledge_bases'] = AIKnowledgeBase.objects.all()
        return context

    def form_valid(self, form):
        try:
            # 保存知识库条目更新
            knowledge_item = form.save()

            # 生成向量
            from apps.ai.services.vector_generation_service import vector_generation_service
            vector_generation_success = vector_generation_service.generate_vector_for_knowledge_item(
                knowledge_item.id)

            # 检查向量是否生成成功
            if not vector_generation_success:
                # 向量化失败，返回错误信息
                if self.request.headers.get(
                        'X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse(
                        {'status': 'error', 'message': '向量化失败，知识条目已更新但向量未更新'})
                else:
                    messages.error(self.request, '向量化失败，知识条目已更新但向量未更新')
                    return redirect('ai:knowledge_item_list')

            # 检查是否是AJAX请求
            if self.request.headers.get(
                    'X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(
                    {'status': 'success', 'message': '知识条目更新成功'})
            else:
                messages.success(self.request, '知识条目更新成功')
                return redirect('ai:knowledge_item_list')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"更新知识库条目失败: {str(e)}")

            error_msg = "操作失败，请稍后重试"
            if self.request.headers.get(
                    'X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': error_msg})
            else:
                messages.error(self.request, error_msg)
                return self.form_invalid(form)


class AIKnowledgeItemDeleteView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DeleteView):
    model = AIKnowledgeItem
    template_name = 'ai/knowledge_item_confirm_delete.html'
    permission_required = 'ai.delete_aiknowledgeitem'
    success_url = reverse_lazy('ai:knowledge_item_list')

    def delete(self, request, *args, **kwargs):
        # 执行删除操作
        super().delete(request, *args, **kwargs)
        messages.success(self.request, '知识条目删除成功')

        # 检查是否是AJAX请求
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # 返回JSON响应
            return JsonResponse({'status': 'success', 'message': '知识条目删除成功'})
        else:
            # 返回重定向响应
            return HttpResponseRedirect(self.success_url)

    def post(self, request, *args, **kwargs):
        # 处理POST请求，调用delete方法
        return self.delete(request, *args, **kwargs)


class AIKnowledgeItemDetailView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DetailView):
    model = AIKnowledgeItem
    template_name = 'ai/knowledge_item_detail.html'
    permission_required = 'ai.view_aiknowledgeitem'
    context_object_name = 'knowledge_item'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 获取知识条目的向量信息
        knowledge_item = self.get_object()
        try:
            vector_record = AIKnowledgeVector.objects.get(
                knowledge_item=knowledge_item)
            context['vector_info'] = {
                'exists': True,
                'dimension': vector_record.dimension,
                'created_at': vector_record.created_at,
                'updated_at': vector_record.updated_at,
                'vector_size': len(
                    vector_record.vector) if vector_record.vector else 0}
        except AIKnowledgeVector.DoesNotExist:
            context['vector_info'] = {
                'exists': False
            }

        return context


class AIKnowledgeSearchView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    model = AIKnowledgeItem
    template_name = 'ai/knowledge_search.html'
    permission_required = 'ai.view_aiknowledgeitem'

    def get_queryset(self):
        query = self.request.GET.get('q', '')
        if not query:
            return AIKnowledgeItem.objects.none()

        return AIKnowledgeItem.objects.select_related('knowledge_base', 'creator').filter(
            content__icontains=query,
            status='published'
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context


# AI销售策略视图
class AISalesStrategyListView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    model = AISalesStrategy
    template_name = 'ai/sales_strategy_list.html'
    context_object_name = 'sales_strategies'
    permission_required = 'ai.view_aisalesstrategy'
    paginate_by = 10

    def get_queryset(self):
        return AISalesStrategy.objects.order_by('-created_at')


class AISalesStrategyCreateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        CreateView):
    model = AISalesStrategy
    form_class = AISalesStrategyForm
    template_name = 'ai/sales_strategy_form.html'
    permission_required = 'ai.add_aisalesstrategy'
    success_url = reverse_lazy('ai:sales_strategy_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '销售策略创建成功')
        return response


class AISalesStrategyUpdateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        UpdateView):
    model = AISalesStrategy
    form_class = AISalesStrategyForm
    template_name = 'ai/sales_strategy_form.html'
    permission_required = 'ai.change_aisalesstrategy'
    success_url = reverse_lazy('ai:sales_strategy_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '销售策略更新成功')
        return response


class AISalesStrategyDeleteView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DeleteView):
    model = AISalesStrategy
    template_name = 'ai/sales_strategy_confirm_delete.html'
    permission_required = 'ai.delete_aisalesstrategy'
    success_url = reverse_lazy('ai:sales_strategy_list')

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, '销售策略删除成功')
        return response


# AI意图识别视图
class AIIntentRecognitionListView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    model = AIIntentRecognition
    template_name = 'ai/intent_recognition_list.html'
    context_object_name = 'intent_recognitions'
    permission_required = 'ai.view_aiintentrecognition'
    paginate_by = 10

    def get_queryset(self):
        return AIIntentRecognition.objects.order_by('-created_at')


class AIIntentRecognitionCreateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        CreateView):
    model = AIIntentRecognition
    form_class = AIIntentRecognitionForm
    template_name = 'ai/intent_recognition_form.html'
    permission_required = 'ai.add_aiintentrecognition'
    success_url = reverse_lazy('ai:intent_recognition_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '意图识别规则创建成功')
        return response


class AIIntentRecognitionUpdateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        UpdateView):
    model = AIIntentRecognition
    form_class = AIIntentRecognitionForm
    template_name = 'ai/intent_recognition_form.html'
    permission_required = 'ai.change_aiintentrecognition'
    success_url = reverse_lazy('ai:intent_recognition_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '意图识别规则更新成功')
        return response


class AIIntentRecognitionDeleteView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DeleteView):
    model = AIIntentRecognition
    template_name = 'ai/intent_recognition_confirm_delete.html'
    permission_required = 'ai.delete_aiintentrecognition'
    success_url = reverse_lazy('ai:intent_recognition_list')

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, '意图识别规则删除成功')
        return response


# AI情绪分析视图
class AIEmotionAnalysisListView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    model = AIEmotionAnalysis
    template_name = 'ai/emotion_analysis_list.html'
    context_object_name = 'emotion_analyses'
    permission_required = 'ai.view_aiemotionanalysis'
    paginate_by = 10

    def get_queryset(self):
        return AIEmotionAnalysis.objects.order_by('-created_at')


class AIEmotionAnalysisCreateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        CreateView):
    model = AIEmotionAnalysis
    form_class = AIEmotionAnalysisForm
    template_name = 'ai/emotion_analysis_form.html'
    permission_required = 'ai.add_aiemotionanalysis'
    success_url = reverse_lazy('ai:emotion_analysis_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '情绪分析规则创建成功')
        return response


class AIEmotionAnalysisUpdateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        UpdateView):
    model = AIEmotionAnalysis
    form_class = AIEmotionAnalysisForm
    template_name = 'ai/emotion_analysis_form.html'
    permission_required = 'ai.change_aiemotionanalysis'
    success_url = reverse_lazy('ai:emotion_analysis_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '情绪分析规则更新成功')
        return response


class AIEmotionAnalysisDeleteView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DeleteView):
    model = AIEmotionAnalysis
    template_name = 'ai/emotion_analysis_confirm_delete.html'
    permission_required = 'ai.delete_aiemotionanalysis'
    success_url = reverse_lazy('ai:emotion_analysis_list')

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, '情绪分析规则删除成功')
        return response


# AI合规规则视图
class AIComplianceRuleListView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    model = AIComplianceRule
    template_name = 'ai/compliance_rule_list.html'
    context_object_name = 'compliance_rules'
    permission_required = 'ai.view_aicompliancerule'
    paginate_by = 10

    def get_queryset(self):
        return AIComplianceRule.objects.order_by('-created_at')


class AIComplianceRuleCreateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        CreateView):
    model = AIComplianceRule
    form_class = AIComplianceRuleForm
    template_name = 'ai/compliance_rule_form.html'
    permission_required = 'ai.add_aicompliancerule'
    success_url = reverse_lazy('ai:compliance_rule_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '合规规则创建成功')
        return response


class AIComplianceRuleUpdateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        UpdateView):
    model = AIComplianceRule
    form_class = AIComplianceRuleForm
    template_name = 'ai/compliance_rule_form.html'
    permission_required = 'ai.change_aicompliancerule'
    success_url = reverse_lazy('ai:compliance_rule_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '合规规则更新成功')
        return response


class AIComplianceRuleDeleteView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DeleteView):
    model = AIComplianceRule
    template_name = 'ai/compliance_rule_confirm_delete.html'
    permission_required = 'ai.delete_aicompliancerule'
    success_url = reverse_lazy('ai:compliance_rule_list')

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, '合规规则删除成功')
        return response


# AI自动行动触发视图
class AIActionTriggerListView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    model = AIActionTrigger
    template_name = 'ai/action_trigger_list.html'
    context_object_name = 'action_triggers'
    permission_required = 'ai.view_aiactiontrigger'
    paginate_by = 10

    def get_queryset(self):
        return AIActionTrigger.objects.order_by('-created_at')


class AIActionTriggerCreateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        CreateView):
    model = AIActionTrigger
    form_class = AIActionTriggerForm
    template_name = 'ai/action_trigger_form.html'
    permission_required = 'ai.add_aiactiontrigger'
    success_url = reverse_lazy('ai:action_trigger_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '自动行动触发创建成功')
        return response


class AIActionTriggerUpdateView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        UpdateView):
    model = AIActionTrigger
    form_class = AIActionTriggerForm
    template_name = 'ai/action_trigger_form.html'
    permission_required = 'ai.change_aiactiontrigger'
    success_url = reverse_lazy('ai:action_trigger_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '自动行动触发更新成功')
        return response


class AIActionTriggerDeleteView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DeleteView):
    model = AIActionTrigger
    template_name = 'ai/action_trigger_confirm_delete.html'
    permission_required = 'ai.delete_aiactiontrigger'
    success_url = reverse_lazy('ai:action_trigger_list')

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, '自动行动触发删除成功')
        return response


# AI仪表盘视图
class AIDashboardView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        TemplateView):
    template_name = 'ai/dashboard.html'
    permission_required = 'ai.view_aidashboard'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 添加仪表盘数据
        context['total_knowledge_bases'] = AIKnowledgeBase.objects.count()
        context['total_knowledge_items'] = AIKnowledgeItem.objects.count()
        context['total_sales_strategies'] = AISalesStrategy.objects.count()
        context['total_workflows'] = AIWorkflow.objects.count()
        context['total_model_configs'] = AIModelConfig.objects.count()
        return context


# AI操作日志视图
class AILogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = AILog
    template_name = 'ai/log_list.html'
    context_object_name = 'logs'
    permission_required = 'ai.view_ailog'
    paginate_by = 20

    def get_queryset(self):
        return AILog.objects.select_related('user').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['log_types'] = AILog.LOG_TYPES
        return context


class BusinessAIFeedbackAPIView(LoginRequiredMixin, View):
    """Record user feedback for normalized business AI results."""

    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body or '{}')
        except ValueError:
            return JsonResponse({'code': 400, 'msg': '无效的JSON格式'}, status=400)

        try:
            feedback = record_business_ai_feedback(request, payload)
        except ValueError as exc:
            return JsonResponse({'code': 400, 'msg': str(exc)}, status=400)
        except Exception as exc:
            logger.error(f"AI反馈记录失败: {str(exc)}", exc_info=True)
            return JsonResponse({'code': 500, 'msg': '反馈记录失败，请稍后重试'}, status=500)

        return JsonResponse({
            'code': 0,
            'msg': '反馈已记录',
            'data': {
                'feedback_id': feedback.id,
                'task_type': feedback.task_type,
            },
        })


class LocalSTTAPIView(LoginRequiredMixin, View):
    """服务端语音识别接口，不直接调用浏览器/Google语音识别"""

    def post(self, request, *args, **kwargs):
        audio_file = request.FILES.get('audio')
        if not audio_file:
            return JsonResponse({'status': 'error', 'message': '未收到语音文件'}, status=400)

        suffix = os.path.splitext(audio_file.name or '')[1] or '.webm'
        try:
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_path = temp_file.name
                for chunk in audio_file.chunks():
                    temp_file.write(chunk)

            from apps.ai.utils.stt_service import STTError, transcribe_audio_file

            text = transcribe_audio_file(temp_path, service_type='auto')
            if not text.strip():
                return JsonResponse({'status': 'error', 'message': '未识别到语音内容'}, status=422)
            return JsonResponse({'status': 'success', 'text': text.strip()})
        except STTError as exc:
            return JsonResponse({'status': 'error', 'message': str(exc)}, status=503)
        except Exception as exc:
            logger.error(f'服务端语音识别失败: {str(exc)}')
            return JsonResponse({'status': 'error', 'message': '服务端语音识别失败，请检查语音转文字服务配置'}, status=500)
        finally:
            if 'temp_path' in locals():
                try:
                    os.remove(temp_path)
                except OSError:
                    pass


# 文件解析视图
class ParseFileContentView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        CreateView):
    """文件内容解析视图"""
    permission_required = 'ai.add_aiknowledgeitem'

    def post(self, request, *args, **kwargs):
        """处理文件上传和解析"""
        try:
            if 'file' not in request.FILES:
                return JsonResponse({'status': 'error', 'message': '未找到上传的文件'})

            uploaded_file = request.FILES['file']
            file_name = uploaded_file.name
            file_extension = file_name.split('.')[-1].lower()

            # 读取文件内容
            file_content = uploaded_file.read()

            # 根据文件类型选择解析方法
            parsed_content = ''

            if file_extension == 'txt':
                # 解析TXT文件
                parsed_content = file_content.decode('utf-8', errors='ignore')
            elif file_extension in ['doc', 'docx']:
                # 解析Word文件
                try:
                    from docx import Document
                    from io import BytesIO

                    doc = Document(BytesIO(file_content))
                    for para in doc.paragraphs:
                        parsed_content += para.text + '\n'
                except Exception as e:
                    logger.error(f'Word文件解析失败: {str(e)}')
                    return JsonResponse(
                        {'status': 'error', 'message': 'Word文件解析失败，请检查文件内容后重试'})
            elif file_extension in ['pdf']:
                # 解析PDF文件
                try:
                    import PyPDF2
                    from io import BytesIO

                    pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
                    for page in pdf_reader.pages:
                        parsed_content += page.extract_text() + '\n'
                except Exception as e:
                    logger.error(f'PDF文件解析失败: {str(e)}')
                    return JsonResponse(
                        {'status': 'error', 'message': 'PDF文件解析失败，请检查文件内容后重试'})
            elif file_extension in ['xls', 'xlsx']:
                # 解析Excel文件
                try:
                    import openpyxl
                    from io import BytesIO

                    workbook = openpyxl.load_workbook(BytesIO(file_content))
                    for sheet_name in workbook.sheetnames:
                        sheet = workbook[sheet_name]
                        parsed_content += f'=== {sheet_name} ===\n'
                        for row in sheet.iter_rows(values_only=True):
                            # 过滤掉空行
                            if any(
                                    cell is not None and cell != '' for cell in row):
                                row_content = '\t'.join(
                                    [str(cell) if cell is not None else '' for cell in row])
                                parsed_content += row_content + '\n'
                except Exception as e:
                    logger.error(f'Excel文件解析失败: {str(e)}')
                    return JsonResponse(
                        {'status': 'error', 'message': 'Excel文件解析失败，请检查文件内容后重试'})
            elif file_extension in ['ppt', 'pptx']:
                # 解析PPT文件
                try:
                    from pptx import Presentation
                    from io import BytesIO

                    presentation = Presentation(BytesIO(file_content))
                    for i, slide in enumerate(presentation.slides, 1):
                        parsed_content += f'=== 幻灯片 {i} ===\n'
                        for shape in slide.shapes:
                            if hasattr(shape, 'text'):
                                parsed_content += shape.text + '\n'
                except Exception as e:
                    logger.error(f'PPT文件解析失败: {str(e)}')
                    return JsonResponse(
                        {'status': 'error', 'message': 'PPT文件解析失败，请检查文件内容后重试'})
            else:
                return JsonResponse(
                    {'status': 'error', 'message': f'不支持的文件类型: {file_extension}'})

            # 返回解析结果
            return JsonResponse({
                'status': 'success',
                'content': parsed_content,
                'file_name': file_name,
                'file_extension': file_extension
            })
        except Exception as e:
            logger.error(f'文件解析失败: {str(e)}')
            return JsonResponse(
                {'status': 'error', 'message': '文件解析失败，请检查文件后重试'})


# AI流式聊天视图

logger = logging.getLogger(__name__)


class AIIntentRecognizeAPIView(LoginRequiredMixin, View):
    """AI 意图识别接口"""

    def post(self, request, *args, **kwargs):
        import json

        try:
            if request.POST:
                data = request.POST
            else:
                try:
                    data = json.loads(request.body or '{}')
                except json.JSONDecodeError:
                    return JsonResponse({'status': 'error', 'message': '无效的JSON格式'}, status=400)

            message = (data.get('message') or data.get('query') or '').strip()
            if not message:
                return JsonResponse({'status': 'error', 'message': '消息不能为空'}, status=400)
            if len(message) > 2000:
                return JsonResponse({'status': 'error', 'message': '消息过长，请精简后重试'}, status=400)

            from apps.ai.services.intent_recognition_service import intent_recognition_service
            result = intent_recognition_service.recognize_intent(request.user, message)
            return JsonResponse({'status': 'success', 'result': result})

        except Exception as e:
            logger.error(f'AI意图识别接口失败: {str(e)}')
            return JsonResponse({'status': 'error', 'message': 'AI意图识别暂时不可用，请稍后重试'}, status=500)


class AIChatStreamView(LoginRequiredMixin, CreateView):
    """AI流式聊天视图"""
    # 移除PermissionRequiredMixin，允许所有登录用户访问AI聊天功能
    # 权限检查通过RBAC中间件进行，而不是通过PermissionRequiredMixin

    def post(self, request, *args, **kwargs):
        """处理流式聊天请求"""
        import json

        try:
            # 获取请求数据
            if request.POST:
                # 表单数据
                data = request.POST
            else:
                # JSON数据
                try:
                    data = json.loads(request.body)
                except json.JSONDecodeError:
                    return JsonResponse(
                        {'status': 'error', 'message': '无效的JSON格式'})

            message = data.get('message', '')

            if not message:
                return JsonResponse({'status': 'error', 'message': '消息不能为空'})

            if request.headers.get('Accept') == 'application/json' or data.get('response_format') == 'json':
                return JsonResponse(self._build_intent_response_payload(
                    request.user, data.get('chat_id'), message, request))

            if request.headers.get('Accept') == 'text/event-stream' or data.get('stream') in {True, 'true', '1', 1}:
                response = StreamingHttpResponse(
                    self._stream_chat_events(
                        user=request.user,
                        chat_id=data.get('chat_id'),
                        message=message,
                        request=request,
                    ),
                    content_type='text/event-stream; charset=utf-8',
                )
                response['Cache-Control'] = 'no-cache'
                response['X-Accel-Buffering'] = 'no'
                return response

            response = StreamingHttpResponse(
                self._stream_chat_events(
                    user=request.user,
                    chat_id=data.get('chat_id'),
                    message=message,
                    request=request,
                ),
                content_type='text/event-stream; charset=utf-8',
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response

        except Exception as e:
            logger.error(f'流式聊天请求失败: {str(e)}')
            error_message = '抱歉，我暂时无法回答您的问题，请稍后再试。'
            return StreamingHttpResponse(
                self.generate_streaming_response({
                    'success': False,
                    'status': 'error',
                    'message': error_message,
                    'ai_message': error_message,
                    'options': [],
                }),
                content_type='text/event-stream; charset=utf-8',
            )

    def _stream_chat_events(self, user, chat_id, message, request=None):
        yield self._serialize_stream_event('thinking', {'message': '正在思考....'})
        try:
            follow_up_payload = self._build_pending_operation_follow_up_payload(user, chat_id, message)
            if follow_up_payload:
                for chunk in self._chunk_stream_text(follow_up_payload.get('ai_message') or follow_up_payload.get('message')):
                    yield self._serialize_stream_event('chunk', {'content': chunk})
                yield self._serialize_stream_event('done', follow_up_payload)
                return

            request_obj = request or getattr(self, 'request', None)
            referrer = request_obj.session.get('ai_last_referrer') if request_obj else None
            page_context = None
            if request_obj and hasattr(request_obj, 'POST'):
                raw_page_context = request_obj.POST.get('page_context')
                if raw_page_context:
                    try:
                        page_context = json.loads(raw_page_context)
                    except (TypeError, ValueError):
                        page_context = None
            if request_obj and hasattr(request_obj, 'session'):
                if page_context:
                    request_obj.session['ai_page_context'] = page_context
                elif request_obj.session.get('ai_page_context'):
                    page_context = request_obj.session.get('ai_page_context')
            intent_input = f"当前页面URL: {referrer}\n用户请求: {message}" if referrer else message
            stream_iter = enhanced_intent_service.stream_user_request(
                user,
                intent_input,
                chat_id=chat_id,
                context={'page_context': page_context} if page_context else None,
            )
            assistant_text = []
            final_payload = None
            for item in stream_iter:
                if not isinstance(item, dict):
                    continue
                event_type = item.get('type')
                if event_type == 'chunk':
                    chunk = item.get('content') or ''
                    if chunk:
                        assistant_text.append(chunk)
                        yield self._serialize_stream_event('chunk', {'content': chunk})
                elif event_type == 'done':
                    final_payload = dict(item.get('payload') or {})
                elif event_type == 'error':
                    final_payload = dict(item.get('payload') or {})
                    break

            if final_payload is None:
                final_payload = {
                    'success': True,
                    'status': 'success',
                    'message': ''.join(assistant_text),
                    'ai_message': ''.join(assistant_text),
                    'options': [],
                }
            if not final_payload.get('status'):
                final_payload['status'] = 'success' if final_payload.get('success', True) else 'error'
            if not final_payload.get('ai_message'):
                final_payload['ai_message'] = self.get_response_text(final_payload)
            if not final_payload.get('message'):
                final_payload['message'] = final_payload.get('ai_message') or self.get_response_text(final_payload)
            final_payload.setdefault('user_message', message)
            final_payload.setdefault('intent', final_payload.get('intent_type') or final_payload.get('intent'))
            final_payload.setdefault('confidence', final_payload.get('confidence', 0))
            final_payload = self._enrich_intent_payload(
                user=user,
                chat_id=chat_id,
                message=message,
                payload=final_payload,
            )
            if not assistant_text and final_payload.get('ai_message'):
                for chunk in self._chunk_stream_text(final_payload.get('ai_message')):
                    yield self._serialize_stream_event('chunk', {'content': chunk})
            yield self._serialize_stream_event('done', final_payload)
        except Exception as e:
            logger.error(f'流式聊天请求失败: {str(e)}')
            error_payload = {
                'success': False,
                'status': 'error',
                'message': '抱歉，我暂时无法回答您的问题，请稍后再试。',
                'ai_message': '抱歉，我暂时无法回答您的问题，请稍后再试。',
                'options': [],
            }
            yield self._serialize_stream_event('error', error_payload)

    def _build_intent_response_payload(self, user, chat_id, message, request=None):
        from apps.ai.services.intent_recognition_service import intent_recognition_service

        follow_up_payload = self._build_pending_operation_follow_up_payload(user, chat_id, message)
        if follow_up_payload:
            return follow_up_payload

        request_obj = request or getattr(self, 'request', None)
        referrer = request_obj.session.get('ai_last_referrer') if request_obj else None
        page_context = None
        if request_obj and hasattr(request_obj, 'POST'):
            raw_page_context = request_obj.POST.get('page_context')
            if raw_page_context:
                try:
                    page_context = json.loads(raw_page_context)
                except (TypeError, ValueError):
                    page_context = None
        if request_obj and hasattr(request_obj, 'session'):
            if page_context:
                request_obj.session['ai_page_context'] = page_context
            elif request_obj.session.get('ai_page_context'):
                page_context = request_obj.session.get('ai_page_context')
        intent_input = f"当前页面URL: {referrer}\n用户请求: {message}" if referrer else message
        intent_result = intent_recognition_service.process_request(
            user,
            intent_input,
            chat_id=chat_id,
            context={'page_context': page_context} if page_context else None,
        )
        return self._enrich_intent_payload(
            user=user,
            chat_id=chat_id,
            message=message,
            payload=intent_result,
        )

    def _enrich_intent_payload(self, user, chat_id, message, payload):
        from apps.ai.services.confirmation_service import confirmation_service
        from apps.ai.services.enhanced_intent_service import enhanced_intent_service

        payload = dict(payload or {})
        payload = enhanced_intent_service._decorate_response_with_recognition_meta(payload, payload)
        payload.setdefault('original_query', message)
        payload.setdefault('query', message)

        ai_response = payload.get('ai_message') or self.get_response_text(payload)
        chat = None
        user_message = None
        ai_message = None
        if not payload.get('ai_message_id'):
            chat, user_message, ai_message = self.save_chat_record(
                user, chat_id, message, ai_response)

        payload['ai_message'] = ai_response
        payload['user_message'] = message
        payload.update(confirmation_service.build_confirmation_payload(payload, user=user))

        operation = None
        if payload.get('confirmation', {}).get('required') and not payload.get('operation_id'):
            operation = self._create_operation_preview(
                user=user,
                chat=chat,
                user_message=user_message,
                ai_message=ai_message,
                payload=payload,
            )
            if operation:
                payload['operation_id'] = operation.id
                payload['confirmation']['token'] = operation.confirmation_token
                task = payload.get('task')
                if isinstance(task, dict):
                    task['operation_id'] = operation.id
                    task['confirmation_token'] = operation.confirmation_token
                    task['confirmation_message'] = payload.get('confirmation', {}).get('message', '')
                    task_options = list(task.get('options') or [])
                    confirm_option = {
                        'text': '确认并执行',
                        'intent': payload.get('intent_type'),
                        'action': 'confirm_operation',
                        'operation_id': operation.id,
                        'token': operation.confirmation_token,
                        'enabled': True,
                    }
                    task['options'] = [confirm_option] + [
                        option for option in task_options
                        if not (
                            isinstance(option, dict)
                            and option.get('action') in {'confirm_operation', 'open_business_page'}
                        )
                    ]
                    payload['options'] = task['options']

        payload = normalize_confirmable_operation_payload(payload)
        task = payload.get('task')
        options = payload.get('options') or (task.get('options') if isinstance(task, dict) else [])
        if chat:
            payload['chat_id'] = chat.id
        if user_message:
            payload['user_message_id'] = user_message.id
            if hasattr(user_message, 'created_at') and user_message.created_at:
                payload['user_message_created_at'] = user_message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        if ai_message:
            payload['ai_message_id'] = ai_message.id
            if hasattr(ai_message, 'created_at') and ai_message.created_at:
                payload['ai_message_created_at'] = ai_message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ai_message.runtime_payload = {
                'task': task,
                'options': options,
                'intent_type': payload.get('intent_type'),
                'confidence': payload.get('confidence'),
                'requires_confirmation': payload.get('requires_confirmation'),
                'action_plan': payload.get('action_plan'),
                'confirmation': payload.get('confirmation'),
                'operation_id': payload.get('operation_id'),
                'specific_intent': payload.get('specific_intent'),
                'action': payload.get('action'),
                'data_type': payload.get('data_type'),
                'entities': payload.get('entities') or {},
                'status': payload.get('status'),
                'time_range': payload.get('time_range'),
                'source': payload.get('source'),
                'ai_available': payload.get('ai_available'),
                'ai_configured': payload.get('ai_configured'),
                'failure_reason': payload.get('failure_reason'),
                'model_provider': payload.get('model_provider'),
                'model_name': payload.get('model_name'),
                'recognition_meta': payload.get('recognition_meta'),
                'mcp_context': payload.get('mcp_context'),
            }
            update_fields = ['runtime_payload']
            if payload.get('ai_message') and getattr(ai_message, 'content', None) != payload.get('ai_message'):
                ai_message.content = payload.get('ai_message')
                update_fields.append('content')
            ai_message.save(update_fields=update_fields)
        return payload

    def _build_pending_operation_follow_up_payload(self, user, chat_id, message):
        command = operation_service.match_pending_operation_command(message)
        if not command:
            return None

        if command == 'rollback':
            operation = operation_service.get_latest_executed_operation(user, chat_id=chat_id)
            if not operation:
                return None
            result = rollback_service.rollback_operation(operation.id, user)
            return self._build_operation_result_payload(user, chat_id, message, operation, result, 'rolled_back')

        operation = operation_service.get_latest_preview_operation(user, chat_id=chat_id)
        if not operation:
            return None

        if command == 'confirm':
            result = operation_service.confirm_operation(
                operation_id=operation.id,
                token=operation.confirmation_token,
                user=user,
            )
            return self._build_operation_result_payload(user, chat_id, message, operation, result, 'confirmed')

        if command == 'cancel':
            result = operation_service.cancel_operation(
                operation_id=operation.id,
                token=operation.confirmation_token,
                user=user,
            )
            return self._build_operation_result_payload(user, chat_id, message, operation, result, 'cancelled')

        return None

    def _build_operation_result_payload(self, user, chat_id, message, operation, result, command):
        success = bool(result.get('success'))
        default_messages = {
            'confirmed': '已执行完成，支持按本次操作单独回退。',
            'cancelled': '已取消上一步待确认操作，本次不会写入任何数据。',
            'rolled_back': '已回退本次操作。',
        }
        default_message = default_messages.get(command, '操作已处理。')
        ai_response = result.get('message') or default_message
        chat, user_message, ai_message = self.save_chat_record(user, chat_id, message, ai_response)
        task = self._build_operation_result_task(operation, result, command, success)
        payload = {
            'success': success,
            'status': 'success' if success else 'error',
            'message': ai_response,
            'ai_message': ai_response,
            'user_message': message,
            'intent': self._get_operation_result_intent(command),
            'intent_type': self._get_operation_result_intent(command),
            'confidence': 1.0,
            'operation_id': getattr(operation, 'id', None),
            'operation_result': result,
            'task': task,
            'options': task.get('options', []) if isinstance(task, dict) else [],
        }
        if chat:
            payload['chat_id'] = chat.id
        if user_message:
            payload['user_message_id'] = user_message.id
        if ai_message:
            payload['ai_message_id'] = ai_message.id
            ai_message.runtime_payload = {
                'task': payload.get('task'),
                'options': payload.get('options'),
                'intent_type': payload.get('intent_type'),
                'confidence': payload.get('confidence'),
                'operation_id': payload.get('operation_id'),
                'operation_result': payload.get('operation_result'),
                'status': payload.get('status'),
            }
            ai_message.save(update_fields=['runtime_payload'])
        return payload

    def _get_operation_result_intent(self, command):
        if command == 'confirmed':
            return 'AI_OPERATION_CONFIRM'
        if command == 'cancelled':
            return 'AI_OPERATION_CANCEL'
        if command == 'rolled_back':
            return 'AI_OPERATION_ROLLBACK'
        return 'AI_OPERATION'

    def _build_operation_result_task(self, operation, result, command, success):
        previous_task = {}
        ai_message = getattr(operation, 'ai_message', None)
        runtime_payload = getattr(ai_message, 'runtime_payload', None)
        if isinstance(runtime_payload, dict) and isinstance(runtime_payload.get('task'), dict):
            previous_task = dict(runtime_payload.get('task'))

        task = {
            'type': 'business_handoff',
            'title': previous_task.get('title') or '业务操作',
            'module': previous_task.get('module') or getattr(operation, 'resource_type', '') or '业务模块',
            'data_type': previous_task.get('data_type') or getattr(operation, 'resource_type', ''),
            'action': previous_task.get('action') or getattr(operation, 'operation_type', ''),
            'operation_id': getattr(operation, 'id', None),
            'execution_status': self._get_operation_execution_status(command, success),
            'operation_result': result,
            'message': result.get('message') or '',
            'options': [],
        }
        if command == 'confirmed' and success:
            task['can_rollback'] = True
            task['safety_notice'] = '本次操作已执行完成，支持按单条记录回退。'
            task['options'] = [{
                'text': '回退本次操作',
                'intent': 'AI_OPERATION_ROLLBACK',
                'action': 'rollback_operation',
                'operation_id': getattr(operation, 'id', None),
                'enabled': True,
            }]
        elif command == 'cancelled' and success:
            task['can_rollback'] = False
            task['safety_notice'] = '本次操作已取消，未写入业务数据。'
        elif command == 'rolled_back' and success:
            task['can_rollback'] = False
            task['safety_notice'] = '本次操作已按单条记录完成物理回退。'
        return task

    def _get_operation_execution_status(self, command, success):
        if not success:
            return 'failed'
        if command == 'confirmed':
            return 'executed'
        if command == 'cancelled':
            return 'cancelled'
        if command == 'rolled_back':
            return 'rolled_back'
        return 'success'

    def _create_operation_preview(self, user, chat, user_message, ai_message, payload):
        from apps.ai.services.operation_service import operation_service

        return operation_service.create_preview_operation(
            user=user,
            chat=chat,
            user_message=user_message,
            ai_message=ai_message,
            payload=payload,
        )

    def save_chat_record(self, user, chat_id, message, ai_response):
        try:
            chat = None

            if chat_id:
                try:
                    chat = AIChat.objects.get(id=chat_id, user=user)
                except AIChat.DoesNotExist:
                    chat = None

            if not chat:
                chat = AIChat.objects.create(
                    user=user,
                    session_id=uuid.uuid4().hex,
                    title=f'聊天 {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}',
                )

            user_message = AIChatMessage.objects.create(
                chat=chat,
                role='user',
                content=message
            )

            ai_message = AIChatMessage.objects.create(
                chat=chat,
                role='assistant',
                content=ai_response
            )
            return chat, user_message, ai_message
        except Exception as e:
            logger.error(f'保存聊天记录失败: {str(e)}')
            return None, None, None

    def get_response_text(self, intent_result):
        if intent_result.get('success'):
            ai_response = intent_result.get(
                'result', intent_result.get('message', ''))
            if intent_result.get('requires_confirmation'):
                ai_response = intent_result.get('message', '请选择您要执行的操作：')
            return ai_response

        if intent_result.get('requires_confirmation'):
            return intent_result.get('message', '我不太确定您的意图，请选择：')
        if intent_result.get('requires_permission'):
            return f"{intent_result.get('message', '您没有权限执行此操作')}。{intent_result.get('suggestion', '请联系管理员获取相应权限')}"
        return intent_result.get('message', '抱歉，我无法处理您的请求')

    def generate_streaming_response(self, response_text, include_thinking=True):
        """生成流式响应"""
        payload = response_text if isinstance(response_text, dict) else {
            'success': True,
            'status': 'success',
            'message': str(response_text or ''),
            'ai_message': str(response_text or ''),
            'options': [],
        }

        if payload.get('status') == 'error':
            yield self._serialize_stream_event('error', payload)
            return

        if include_thinking:
            yield self._serialize_stream_event('thinking', {
                'message': payload.get('thinking_message') or '正在思考....'
            })

        assistant_text = payload.get('ai_message') or payload.get('message') or ''
        for chunk in self._chunk_stream_text(assistant_text):
            yield self._serialize_stream_event('chunk', {'content': chunk})

        yield self._serialize_stream_event('done', payload)

    def _serialize_stream_event(self, event_name, payload):
        return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _chunk_stream_text(self, text, chunk_size=12):
        normalized = str(text or '')
        if not normalized:
            return []
        return [
            normalized[index:index + chunk_size]
            for index in range(0, len(normalized), chunk_size)
        ]


class AIConfirmOperationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '无效的JSON格式'}, status=400)

        operation_id = data.get('operation_id')
        token = data.get('token', '')
        if not operation_id or not token:
            return JsonResponse({'success': False, 'message': '缺少必要参数'}, status=400)

        try:
            result = operation_service.confirm_operation(
                operation_id=operation_id,
                token=token,
                user=request.user,
            )
        except Exception:
            logger.exception('AI确认操作执行失败')
            return JsonResponse({
                'success': False,
                'message': '操作执行失败，请检查字段后重试或联系管理员',
            }, status=500)
        status = 200 if result.get('success') else 400
        return JsonResponse(result, status=status)


class AICancelOperationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '无效的JSON格式'}, status=400)

        operation_id = data.get('operation_id')
        token = data.get('token', '')
        if not operation_id or not token:
            return JsonResponse({'success': False, 'message': '缺少必要参数'}, status=400)

        result = operation_service.cancel_operation(
            operation_id=operation_id,
            token=token,
            user=request.user,
        )
        status = 200 if result.get('success') else 400
        return JsonResponse(result, status=status)


# AI工作流执行记录视图
class AIWorkflowExecutionListView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        ListView):
    """AI工作流执行记录列表视图"""
    model = AIWorkflowExecution
    template_name = 'ai/workflow_execution_list.html'
    permission_required = 'ai.view_aiworkflowexecution'
    context_object_name = 'executions'
    paginate_by = 10

    def get_queryset(self):
        """获取工作流执行记录，按开始时间倒序排列"""
        queryset = AIWorkflowExecution.objects.select_related(
            'workflow', 'created_by'
        ).prefetch_related('node_executions').order_by('-started_at')

        # 添加入口参数过滤
        workflow_id = self.request.GET.get('workflow_id')
        status = self.request.GET.get('status')

        if workflow_id:
            queryset = queryset.filter(workflow_id=workflow_id)
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        """添加额外的上下文数据"""
        context = super().get_context_data(**kwargs)
        # 使用缓存避免重复查询
        from django.core.cache import cache

        stats_cache_key = 'workflow_execution_stats'
        stats = cache.get(stats_cache_key)

        if stats is None:
            stats = {
                'total_executions': AIWorkflowExecution.objects.count(),
                'running_executions': AIWorkflowExecution.objects.filter(
                    status='running').count(),
                'completed_executions': AIWorkflowExecution.objects.filter(
                    status='completed').count(),
                'failed_executions': AIWorkflowExecution.objects.filter(
                    status='failed').count(),
            }
            cache.set(stats_cache_key, stats, 300)  # 缓存5分钟

        context.update({
            'total_executions': stats['total_executions'],
            'running_executions': stats['running_executions'],
            'completed_executions': stats['completed_executions'],
            'failed_executions': stats['failed_executions'],
        })
        return context


class AIWorkflowExecutionDetailView(
        LoginRequiredMixin,
        PermissionRequiredMixin,
        DetailView):
    """AI工作流执行记录详情视图"""
    model = AIWorkflowExecution
    template_name = 'ai/workflow_execution_detail.html'
    permission_required = 'ai.view_aiworkflowexecution'
    context_object_name = 'execution'


# ============================================================================
# 节点配置Schema API视图
# ============================================================================

class NodeConfigSchemaView(View):
    """
    获取节点配置Schema的API视图
    支持获取单个节点配置或所有节点配置列表
    """

    def get(self, request, node_type=None):
        """处理GET请求"""
        if node_type:
            # 获取单个节点的配置Schema
            config = get_node_full_config(node_type)
            if not config:
                return JsonResponse({
                    'success': False,
                    'error': f'未找到节点类型: {node_type}'
                }, status=404)
            return JsonResponse({
                'success': True,
                'data': config
            })
        else:
            # 获取所有节点配置列表
            all_nodes = get_all_node_configs()
            nodes_list = []
            for node_type_key, config in all_nodes.items():
                nodes_list.append({
                    'node_type': node_type_key,
                    'name': config.name,
                    'description': config.description,
                    'category': config.category,
                })
            return JsonResponse({
                'success': True,
                'data': {
                    'nodes': nodes_list,
                    'categories': list(get_nodes_by_category().keys())
                }
            })


class NodeConfigFieldsView(View):
    """
    获取节点配置字段详情（用于前端动态表单生成）
    """

    def get(self, request, node_type):
        """获取指定节点的配置字段详情"""
        schema = get_node_config_schema(node_type)

        # 如果未找到配置，尝试从处理器注册表获取
        if not schema:
            from .processors import get_processor_for_node_type
            processor = get_processor_for_node_type(node_type)
            if processor and hasattr(processor, 'config_schema'):
                schema = processor.config_schema

            # 如果还是没有找到配置，返回空对象而不是404
            if not schema:
                return JsonResponse({
                    'success': False,
                    'error': f'未找到节点类型: {node_type}'
                }, status=404)

        return JsonResponse({
            'success': True,
            'data': schema
        })


class NodeInputSchemaView(View):
    """获取节点输入Schema"""

    def get(self, request, node_type):
        """获取指定节点的输入Schema"""
        from .services.complete_node_config import get_node_input_schema
        schema = get_node_input_schema(node_type)
        return JsonResponse({
            'success': True,
            'data': schema
        })


class NodeOutputSchemaView(View):
    """获取节点输出Schema"""

    def get(self, request, node_type):
        """获取指定节点的输出Schema"""
        from .services.complete_node_config import get_node_output_schema
        schema = get_node_output_schema(node_type)
        return JsonResponse({
            'success': True,
            'data': schema
        })


class KnowledgeBaseListAPIView(View):
    """知识库列表API - 获取可用的知识库"""

    def get(self, request):
        """获取知识库列表"""
        try:
            from .models import AIKnowledgeBase
            knowledge_bases = AIKnowledgeBase.objects.filter(
                status='published'
            ).values('id', 'name', 'description')

            kb_list = []
            for kb in knowledge_bases:
                kb_list.append({
                    'id': str(kb['id']),
                    'title': kb['name'],
                    'description': kb['description'] or '',
                    'knowledge_type': 'generic'
                })

            return JsonResponse({
                'success': True,
                'data': kb_list,
                'total': len(kb_list)
            })

        except Exception as e:
            logger.error(f'获取知识库列表失败: {e}', exc_info=True)
            return JsonResponse({
                'success': False,
                'error': '获取知识库列表失败，请稍后重试'
            }, status=500)


class ModelConfigListAPIView(View):
    """模型配置列表API - 获取可用的AI模型配置"""

    def get(self, request):
        """获取模型配置列表"""
        try:
            model_configs = AIModelConfig.get_active_runtime_configs()

            model_list = [{
                'id': str(config['id']),
                'name': config['name'],
                'api_base': config.get('api_base', ''),
                'model_names': config.get('model_names', []),
                'is_default': config.get('is_default', False),
            } for config in model_configs]

            return JsonResponse({
                'success': True,
                'data': model_list,
                'total': len(model_list)
            })

        except Exception as e:
            logger.error(f'获取模型配置列表失败: {e}', exc_info=True)
            return JsonResponse({
                'success': False,
                'error': '获取模型配置列表失败，请稍后重试'
            }, status=500)


class WorkflowModuleListAPIView(View):
    """工作流模块列表API - 获取可用的工作流"""

    def get(self, request):
        """获取工作流列表"""
        try:
            workflows = AIWorkflow.objects.filter(
                is_active=True
            ).values('id', 'name', 'description', 'category')

            wf_list = []
            for wf in workflows:
                wf_list.append({
                    'id': str(wf['id']),
                    'name': wf['name'],
                    'description': wf['description'] or '',
                    'category': wf['category'] or '未分类'
                })

            return JsonResponse({
                'success': True,
                'data': wf_list,
                'total': len(wf_list)
            })

        except Exception as e:
            logger.error(f'获取工作流列表失败: {e}', exc_info=True)
            return JsonResponse({
                'success': False,
                'error': '获取工作流列表失败，请稍后重试'
            }, status=500)


class ProjectMCPCapabilityAPIView(LoginRequiredMixin, View):
    """项目 MCP 能力目录 API。"""

    def get(self, request):
        from apps.ai.services.project_mcp_service import project_mcp_service

        query = request.GET.get('q', '')
        capabilities = project_mcp_service.get_capability_catalog()
        matched_capabilities = project_mcp_service.match_capabilities(
            query,
            {'intent': 'DATA_QUERY'} if query else {},
        ) if query else []
        return JsonResponse({
            'success': True,
            'protocol': 'project-mcp',
            'total': len(capabilities),
            'capabilities': capabilities,
            'matched_capabilities': matched_capabilities,
        })


class NodeDynamicOptionsView(View):
    """节点动态选项API - 根据节点类型获取动态下拉选项"""

    def get(self, request, node_type):
        """获取指定节点的动态选项"""
        try:
            from .models import AIKnowledgeBase, AIModelConfig, AIWorkflow
            options = {}

            if node_type in [
                'ai_generation',
                'ai_model',
                'ai_classification',
                'ai_extraction',
                'intent_recognition',
                    'sentiment_analysis']:
                model_configs = AIModelConfig.objects.filter(is_active=True)
                options['model_id'] = [
                    {'value': str(config.id),
                     'label': f"{config.name} ({config.primary_model_name()})",
                     'provider': config.provider}
                    for config in model_configs
                ]

            elif node_type in ['knowledge_retrieval', 'ai_knowledge_retrieval']:
                knowledge_bases = AIKnowledgeBase.objects.filter(
                    status='published')
                options['knowledge_base_id'] = [
                    {'value': str(kb.id), 'label': kb.name, 'knowledge_type': getattr(
                        kb, 'knowledge_type', 'generic')}
                    for kb in knowledge_bases
                ]

            elif node_type == 'workflow_trigger':
                workflows = AIWorkflow.objects.filter(is_active=True)
                options['workflow_id'] = [
                    {'value': str(wf.id), 'label': wf.name,
                     'category': getattr(wf, 'category', '未分类')}
                    for wf in workflows
                ]

            elif node_type in ['http_request', 'api_call']:
                options['method'] = [
                    {'value': 'GET', 'label': 'GET'},
                    {'value': 'POST', 'label': 'POST'},
                    {'value': 'PUT', 'label': 'PUT'},
                    {'value': 'DELETE', 'label': 'DELETE'},
                    {'value': 'PATCH', 'label': 'PATCH'}
                ]
                options['content_type'] = [
                    {'value': 'application/json', 'label': 'JSON'},
                    {'value': 'application/x-www-form-urlencoded',
                        'label': 'Form URL Encoded'},
                    {'value': 'multipart/form-data', 'label': 'Multipart Form'},
                    {'value': 'text/plain', 'label': 'Plain Text'}
                ]

            return JsonResponse({
                'success': True,
                'node_type': node_type,
                'options': options
            })

        except Exception as e:
            logger.error(f'获取节点动态选项失败: {e}', exc_info=True)
            return JsonResponse({
                'success': False,
                'error': '获取节点动态选项失败，请稍后重试'
            }, status=500)


class AgentCenterView(LoginRequiredMixin, TemplateView):
    """智能体中心视图"""
    template_name = 'ai/agent_center.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['center_payload'] = enterprise_agent_service.get_center_payload(self.request.user)
        return context


class AgentCenterDataView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({
            'success': True,
            'data': enterprise_agent_service.get_center_payload(request.user),
        })


class AgentCenterDetailView(LoginRequiredMixin, View):
    def get(self, request, agent_id, *args, **kwargs):
        try:
            data = enterprise_agent_service.get_agent_detail(agent_id, request.user)
            return JsonResponse({'success': True, 'data': data})
        except KeyError as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=404)


class AgentCenterExecuteView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '无效的JSON格式'}, status=400)

        try:
            result = enterprise_agent_service.execute(
                user=request.user,
                agent_id=data.get('agent_id', ''),
                action_id=data.get('action_id', ''),
                params=data.get('params') or {},
            )
        except KeyError as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=404)
        except Exception as exc:
            logger.exception('企业智能体执行失败')
            return JsonResponse({'success': False, 'message': str(exc)}, status=500)

        status = 200 if result.get('success') else 400
        return JsonResponse({'success': bool(result.get('success')), 'data': result}, status=status)


class AgentCenterRollbackView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '无效的JSON格式'}, status=400)

        operation_id = data.get('operation_id')
        if not operation_id:
            return JsonResponse({'success': False, 'message': '缺少 operation_id'}, status=400)

        result = rollback_service.rollback_operation(operation_id, request.user)
        status = 200 if result.get('success') else 400
        return JsonResponse({'success': bool(result.get('success')), 'data': result}, status=status)
