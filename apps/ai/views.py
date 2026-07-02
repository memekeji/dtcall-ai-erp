import logging
import os
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.utils import timezone
import json

from .services.workflow_service import WorkflowService
from .services.business_feedback import record_business_ai_feedback
from .services.operation_service import operation_service

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
                        "provider": obj.provider,
                        "model_type": obj.model_type,
                        "api_key": "***",  # 脱敏处理，不返回实际API密钥
                        "api_base": obj.api_base,
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
        try:
            logger.info(f"测试AI模型连接 - 模型ID: {model_config.id}")
            logger.info(
                f"模型配置 - 提供商: {model_config.provider}, 基础URL: {model_config.api_base}, 模型名称: {model_config.model_name}, 模型类型: {model_config.model_type}")
            logger.info(f"API密钥: {'***' if model_config.api_key else '未配置'}")

            client = AIClient(model_config_id=model_config.id)
            result = self._run_model_validation(client, model_config)
            display_result = self._format_validation_result(result)
            logger.info(f"AI模型连接成功 - 模型ID: {model_config.id}, 模型类型: {model_config.model_type}")
            return JsonResponse({
                'status': 'success',
                'message': '连接成功',
                'result': display_result,
                'details': {
                    'provider': model_config.provider,
                    'base_url': model_config.api_base,
                    'model_name': model_config.model_name,
                    'model_type': model_config.model_type
                }
            })
        except AIClientError as e:
            import traceback
            logger.error(f"AI模型连接失败 - 模型ID: {model_config.id}")
            logger.error(f"错误类型: {type(e).__name__}")
            logger.error(f"错误详情: {str(e)}")
            logger.error(f"完整错误堆栈: {traceback.format_exc()}")
            logger.error(
                f"模型配置 - 提供商: {model_config.provider}, 基础URL: {model_config.api_base}, 模型名称: {model_config.model_name}, 模型类型: {model_config.model_type}")

            error_payload = self._build_validation_error_payload(model_config, e)
            return JsonResponse(error_payload)
        except Exception as e:
            import traceback
            logger.error(f"AI模型连接失败 - 模型ID: {model_config.id}")
            logger.error(f"错误类型: {type(e).__name__}")
            logger.error(f"错误详情: {str(e)}")
            logger.error(f"完整错误堆栈: {traceback.format_exc()}")
            logger.error(
                f"模型配置 - 提供商: {model_config.provider}, 基础URL: {model_config.api_base}, 模型名称: {model_config.model_name}, 模型类型: {model_config.model_type}")
            error_payload = self._build_validation_error_payload(model_config, e)
            return JsonResponse(error_payload)

    def _run_model_validation(self, client, model_config):
        if model_config.model_type == 'embedding':
            return client.embedding('这是一个嵌入模型连接测试。', model=model_config.model_name)
        if model_config.model_type in ['chat', 'text']:
            test_message = [{"role": "user", "content": "你好，这是一个连接测试。"}]
            if model_config.model_type == 'text':
                return client.text_completion('你好，这是一个连接测试。', model=model_config.model_name)
            return client.chat_completion(test_message, model=model_config.model_name)
        raise AIClientError(f"当前暂不支持验证{model_config.get_model_type_display()}接口")

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
        message = self._build_validation_message(error_type, status_code)
        return {
            'status': 'error',
            'message': message,
            'details': {
                'provider': model_config.provider,
                'base_url': model_config.api_base,
                'model_name': model_config.model_name,
                'model_type': model_config.model_type,
                'error_type': error_type,
                'error_code': error_code,
                'status_code': status_code,
                'detail': detail[:500] if isinstance(detail, str) else str(detail),
                'suggestion': self._get_error_suggestion(error_type, model_config, status_code=status_code, error_code=error_code)
            }
        }

    def _build_validation_message(self, error_type, status_code=None):
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

    def _get_error_suggestion(self, error_type, model_config, status_code=None, error_code=None):
        """根据错误类型提供修复建议"""
        if status_code == 401:
            return '请检查数据库中保存的 API 密钥是否正确、是否已过期，并确认该密钥属于当前服务地址'
        if status_code == 403:
            return '请确认当前密钥已开通目标模型权限，并检查服务商侧访问控制设置'
        if status_code == 404:
            return f'请检查 API 地址或兼容路径是否正确。当前配置地址：{model_config.api_base}'
        if status_code == 429:
            return '请检查调用频率限制、账户余额或套餐额度'
        if status_code in {500, 502, 503, 504}:
            return '模型服务端暂时异常，建议稍后重试；若持续失败，请联系模型服务提供方检查网关和实例状态'
        if error_code == 'timeout':
            return '请求超时，请检查网络连通性、代理配置或服务响应速度'
        if error_code == 'connection_error':
            return f'无法连接到模型服务，请检查网络、DNS、代理或服务地址。当前配置地址：{model_config.api_base}'
        suggestions = {
            'ConnectionError': '请检查网络连接是否正常，以及API地址是否正确',
            'TimeoutError': '请求超时，请检查网络连接或API地址是否正确',
            'HTTPError': f'HTTP请求失败，请检查API地址是否正确。当前配置的地址是: {model_config.api_base}',
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
        payload = getattr(message, 'runtime_payload', None)
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
            if isinstance(options, list):
                data['options'] = options
        return data


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

            # 1. 调用意图识别服务（使用新的 AI 分类器）
            if request.headers.get('Accept') == 'application/json' or data.get('response_format') == 'json':
                return JsonResponse(self._build_intent_response_payload(
                    request.user, data.get('chat_id'), message, request))

            from apps.ai.services.intent_recognition_service import intent_recognition_service
            referrer = request.session.get('ai_last_referrer')
            intent_input = f"当前页面URL: {referrer}\n用户请求: {message}" if referrer else message
            intent_result = intent_recognition_service.process_request(
                request.user, intent_input, chat_id=data.get('chat_id'))

            # 2. 获取意图
            intent_result.get('intent_type', 'ai_chat')

            # 3. 处理响应
            ai_response = self.get_response_text(intent_result)

            try:
                chat, user_message, ai_message = self.save_chat_record(
                    request.user,
                    data.get('chat_id'),
                    message,
                    ai_response,
                )
                if ai_message:
                    ai_message.runtime_payload = dict(intent_result)
                    ai_message.save(update_fields=['runtime_payload'])
            except Exception as e:
                logger.error(f'保存聊天记录失败: {str(e)}')

            # 6. 返回流式响应
            response = HttpResponse(
                self.generate_streaming_response(ai_response),
                content_type='text/event-stream')
            response['Cache-Control'] = 'no-cache'
            return response

        except Exception as e:
            logger.error(f'流式聊天请求失败: {str(e)}')
            error_message = '抱歉，我暂时无法回答您的问题，请稍后再试。'
            return HttpResponse(
                self.generate_streaming_response(error_message),
                content_type='text/event-stream')

    def _build_intent_response_payload(self, user, chat_id, message, request=None):
        from apps.ai.services.intent_recognition_service import intent_recognition_service
        from apps.ai.services.confirmation_service import confirmation_service
        request_obj = request or getattr(self, 'request', None)
        referrer = request_obj.session.get('ai_last_referrer') if request_obj else None
        intent_input = f"当前页面URL: {referrer}\n用户请求: {message}" if referrer else message
        intent_result = intent_recognition_service.process_request(
            user,
            intent_input,
            chat_id=chat_id,
        )
        ai_response = self.get_response_text(intent_result)
        chat, user_message, ai_message = self.save_chat_record(
            user, chat_id, message, ai_response)
        payload = dict(intent_result)
        payload['ai_message'] = ai_response
        payload['user_message'] = message
        payload.update(confirmation_service.build_confirmation_payload(payload))
        operation = None
        if payload.get('confirmation', {}).get('required'):
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
        options = payload.get('options') or (task.get('options') if isinstance(task, dict) else [])
        if chat:
            payload['chat_id'] = chat.id
        if user_message:
            payload['user_message_id'] = user_message.id
        if ai_message:
            payload['ai_message_id'] = ai_message.id
            ai_message.runtime_payload = {
                'task': task,
                'options': options,
                'intent_type': payload.get('intent_type'),
                'confidence': payload.get('confidence'),
                'requires_confirmation': payload.get('requires_confirmation'),
                'action_plan': payload.get('action_plan'),
                'confirmation': payload.get('confirmation'),
                'operation_id': payload.get('operation_id'),
            }
            ai_message.save(update_fields=['runtime_payload'])
        return payload

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
                chat, created = AIChat.objects.get_or_create(
                    user=user, defaults={
                        'title': f'聊天 {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'})

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

    def generate_streaming_response(self, response_text):
        """生成流式响应"""
        # 模拟流式输出，逐字符发送
        for char in response_text:
            yield char
            import time
            time.sleep(0.01)  # 添加小延迟，模拟真实的流式输出


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

        result = operation_service.confirm_operation(
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
                'provider': config['provider'],
                'model_name': config['model_name']
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
                     'label': f"{config.name} ({config.provider})",
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
        
        # 获取所有可用的智能体数据
        context['agents'] = self.get_agents_data()
        
        return context
    
    def get_agents_data(self):
        """获取智能体数据，包括工作流、模型配置等"""
        agents = []
        
        # 预定义的企业智能体（演示卡片）
        predefined_agents = [
            {
                'id': 'agent_smart_production',
                'name': '智能排产助手',
                'type': 'enterprise',
                'type_display': '企业智能体',
                'description': '基于AI算法的智能生产排程系统，自动优化生产计划，提高产能利用率',
                'icon': 'layui-icon-chart',
                'status': 'active',
                'creator': '系统',
                'created_at': '2024-01-15 10:00',
                'tags': ['生产管理', '智能排程', '优化算法'],
                'color': 'purple'
            },
            {
                'id': 'agent_customer_service',
                'name': '智能客服',
                'type': 'enterprise',
                'type_display': '企业智能体',
                'description': '7×24小时在线智能客服系统，支持多轮对话、意图识别、知识库问答',
                'icon': 'layui-icon-dialogue',
                'status': 'active',
                'creator': '系统',
                'created_at': '2024-01-20 14:30',
                'tags': ['客户服务', '自然语言', '智能问答'],
                'color': 'purple'
            },
            {
                'id': 'agent_contract_review',
                'name': '合同智能审核',
                'type': 'enterprise',
                'type_display': '企业智能体',
                'description': '自动审核合同条款，识别风险点，提供合规性建议和修改意见',
                'icon': 'layui-icon-file-b',
                'status': 'active',
                'creator': '系统',
                'created_at': '2024-02-05 09:15',
                'tags': ['合同管理', '风险识别', '智能审核'],
                'color': 'purple'
            },
            {
                'id': 'agent_financial_analysis',
                'name': '财务智能分析',
                'type': 'enterprise',
                'type_display': '企业智能体',
                'description': '自动分析财务数据，生成财务报表，预测资金流向和经营风险',
                'icon': 'layui-icon-chart-screen',
                'status': 'active',
                'creator': '系统',
                'created_at': '2024-02-10 16:00',
                'tags': ['财务分析', '数据洞察', '风险预警'],
                'color': 'purple'
            },
            {
                'id': 'agent_hr_assistant',
                'name': '人事智能助手',
                'type': 'enterprise',
                'type_display': '企业智能体',
                'description': '智能简历筛选、面试评估、员工培训推荐，提升HR工作效率',
                'icon': 'layui-icon-user',
                'status': 'active',
                'creator': '系统',
                'created_at': '2024-02-15 11:20',
                'tags': ['人事管理', '智能招聘', '员工培训'],
                'color': 'purple'
            },
            {
                'id': 'agent_sales_forecast',
                'name': '销售预测分析',
                'type': 'enterprise',
                'type_display': '企业智能体',
                'description': '基于历史数据和市场趋势，智能预测销售业绩，辅助决策',
                'icon': 'layui-icon-dollar',
                'status': 'active',
                'creator': '系统',
                'created_at': '2024-02-20 13:45',
                'tags': ['销售管理', '预测分析', '数据挖掘'],
                'color': 'purple'
            },
            {
                'id': 'agent_inventory_optimization',
                'name': '库存优化智能体',
                'type': 'enterprise',
                'type_display': '企业智能体',
                'description': '智能分析库存数据，优化库存水平，降低库存成本和缺货风险',
                'icon': 'layui-icon-component',
                'status': 'active',
                'creator': '系统',
                'created_at': '2024-02-25 10:30',
                'tags': ['库存管理', '智能优化', '成本控制'],
                'color': 'purple'
            },
            {
                'id': 'agent_quality_inspection',
                'name': '质检智能助手',
                'type': 'enterprise',
                'type_display': '企业智能体',
                'description': '自动化质量检测，识别产品缺陷，生成质检报告和改进建议',
                'icon': 'layui-icon-star',
                'status': 'active',
                'creator': '系统',
                'created_at': '2024-03-01 15:00',
                'tags': ['质量管理', '缺陷检测', '智能报告'],
                'color': 'purple'
            }
        ]
        
        # 添加预定义智能体
        agents.extend(predefined_agents)
        
        # 1. 工作流类智能体
        workflows = AIWorkflow.objects.filter(
            status='published'
        ).select_related('owner').order_by('-created_at')[:20]
        
        for workflow in workflows:
            agents.append({
                'id': str(workflow.id),
                'name': workflow.name,
                'type': 'workflow',
                'type_display': '工作流智能体',
                'description': workflow.description or '智能工作流处理',
                'icon': 'layui-icon-engine',
                'status': 'active',
                'creator': workflow.owner.username if workflow.owner else '系统',
                'created_at': workflow.created_at.strftime('%Y-%m-%d %H:%M'),
                'tags': ['工作流', '自动化'],
                'color': 'blue'
            })
        
        # 2. AI模型类智能体
        model_configs = AIModelConfig.objects.filter(
            is_active=True
        ).order_by('-created_at')[:10]
        
        for config in model_configs:
            agents.append({
                'id': str(config.id),
                'name': config.name,
                'type': 'model',
                'type_display': 'AI模型',
                'description': f"{config.get_provider_display()}提供的{config.get_model_type_display()}模型",
                'icon': 'layui-icon-light',
                'status': 'active',
                'creator': '系统',
                'created_at': config.created_at.strftime('%Y-%m-%d %H:%M'),
                'tags': [config.get_provider_display(), config.get_model_type_display()],
                'color': 'green'
            })
        
        # 3. 知识库类智能体
        knowledge_bases = AIKnowledgeBase.objects.filter(
            status='published'
        ).select_related('creator').order_by('-created_at')[:10]
        
        for kb in knowledge_bases:
            agents.append({
                'id': str(kb.id),
                'name': kb.name,
                'type': 'knowledge',
                'type_display': '知识库智能体',
                'description': kb.description or '智能知识检索与问答',
                'icon': 'layui-icon-read',
                'status': 'active',
                'creator': kb.creator.username if kb.creator else '系统',
                'created_at': kb.created_at.strftime('%Y-%m-%d %H:%M'),
                'tags': ['知识库', '问答'],
                'color': 'orange'
            })
        
        return agents
