"""
工作流交互API视图
提供工作流执行过程中的用户交互接口
"""

import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.generic import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction

from apps.ai.models import AIWorkflowExecution, NodeExecution
from apps.ai.models_workflow_interaction import (
    WorkflowInteraction,
    WorkflowInteractionTemplate,
    WorkflowCheckpoint
)
from apps.ai.services.workflow_interaction_service import (
    workflow_interaction_service,
    workflow_interaction_engine
)

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowInteractionListView(LoginRequiredMixin, View):
    """工作流交互列表API"""

    def get(self, request):
        """获取交互列表"""
        try:
            status = request.GET.get('status')
            interaction_type = request.GET.get('type')
            workflow_execution_id = request.GET.get('execution_id')

            queryset = WorkflowInteraction.objects.all()

            if status:
                queryset = queryset.filter(status=status)

            if interaction_type:
                queryset = queryset.filter(interaction_type=interaction_type)

            if workflow_execution_id:
                queryset = queryset.filter(
                    workflow_execution_id=workflow_execution_id)

            interactions = []
            for interaction in queryset.order_by('-created_at')[:100]:
                interactions.append({
                    'id': str(interaction.id),
                    'type': interaction.interaction_type,
                    'title': interaction.title,
                    'status': interaction.status,
                    'priority': interaction.priority,
                    'requester_id': interaction.requester_id,
                    'handler_id': interaction.handler_id,
                    'created_at': interaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'is_expired': interaction.is_expired
                })

            return JsonResponse({
                'success': True,
                'data': interactions,
                'total': len(interactions)
            })

        except Exception as e:
            logger.error(f'获取交互列表失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowInteractionDetailView(LoginRequiredMixin, View):
    """工作流交互详情API"""

    def get(self, request, interaction_id):
        """获取交互详情"""
        try:
            interaction = workflow_interaction_service.get_interaction_status(
                interaction_id)

            if not interaction:
                return JsonResponse({
                    'success': False,
                    'error': '交互不存在'
                }, status=404)

            return JsonResponse({
                'success': True,
                'data': interaction
            })

        except Exception as e:
            logger.error(f'获取交互详情失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowInteractionCompleteView(LoginRequiredMixin, View):
    """完成工作流交互API"""

    @transaction.atomic
    def post(self, request, interaction_id):
        """完成交互"""
        try:
            data = json.loads(request.body)
            input_data = data.get('input_data', {})
            result = data.get('result')
            comment = data.get('comment')

            completed_interaction = workflow_interaction_service.complete_interaction(
                interaction_id=interaction_id,
                user=request.user,
                input_data=input_data,
                result=result,
                comment=comment
            )

            waiting = workflow_interaction_engine.get_waiting_interaction(
                interaction_id)
            if waiting:
                context = waiting['context']
                context['interaction_result'] = completed_interaction.result
                context['interaction_input'] = completed_interaction.input_data

            return JsonResponse({
                'success': True,
                'message': '交互已完成',
                'data': {
                    'interaction_id': str(completed_interaction.id),
                    'status': completed_interaction.status,
                    'result': completed_interaction.result,
                    'responded_at': completed_interaction.responded_at.strftime('%Y-%m-%d %H:%M:%S')
                }
            })

        except Exception as e:
            logger.error(f'完成交互失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowInteractionCancelView(LoginRequiredMixin, View):
    """取消工作流交互API"""

    def post(self, request, interaction_id):
        """取消交互"""
        try:
            data = json.loads(request.body)
            reason = data.get('reason')

            interaction = workflow_interaction_service.cancel_interaction(
                interaction_id=interaction_id,
                user=request.user,
                reason=reason
            )

            return JsonResponse({
                'success': True,
                'message': '交互已取消',
                'data': {
                    'interaction_id': str(interaction.id),
                    'status': interaction.status
                }
            })

        except Exception as e:
            logger.error(f'取消交互失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


@method_decorator(csrf_exempt, name='dispatch')
class PendingInteractionListView(LoginRequiredMixin, View):
    """待处理交互列表API"""

    def get(self, request):
        """获取当前用户的待处理交互"""
        try:
            workflow_execution_id = request.GET.get('execution_id')

            interactions = workflow_interaction_service.get_pending_interactions(
                user=request.user, workflow_execution_id=workflow_execution_id)

            result = []
            for interaction in interactions:
                waiting = workflow_interaction_engine.get_waiting_interaction(
                    str(interaction.id))
                result.append({
                    'id': str(interaction.id),
                    'type': interaction.interaction_type,
                    'title': interaction.title,
                    'description': interaction.description,
                    'status': interaction.status,
                    'priority': interaction.priority,
                    'input_schema': interaction.input_schema,
                    'workflow_execution_id': str(interaction.workflow_execution_id),
                    'created_at': interaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'is_expired': interaction.is_expired,
                    'timeout': interaction.timeout
                })

            return JsonResponse({
                'success': True,
                'data': result,
                'total': len(result)
            })

        except Exception as e:
            logger.error(f'获取待处理交互失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class InteractionFormSchemaView(LoginRequiredMixin, View):
    """获取交互表单Schema"""

    def get(self, request, interaction_id):
        """获取交互表单Schema"""
        try:
            interaction = WorkflowInteraction.objects.get(id=interaction_id)

            schema = interaction.input_schema or {}

            form_config = {
                'title': interaction.title,
                'description': interaction.description,
                'type': interaction.interaction_type,
                'schema': schema,
                'timeout': interaction.timeout,
                'is_expired': interaction.is_expired
            }

            return JsonResponse({
                'success': True,
                'data': form_config
            })

        except WorkflowInteraction.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '交互不存在'
            }, status=404)
        except Exception as e:
            logger.error(f'获取交互表单Schema失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class InteractionTemplateListView(LoginRequiredMixin, View):
    """交互模板列表API"""

    def get(self, request):
        """获取交互模板列表"""
        try:
            templates = WorkflowInteractionTemplate.objects.filter(
                is_active=True)

            result = []
            for template in templates:
                result.append({
                    'id': str(template.id),
                    'name': template.name,
                    'description': template.description,
                    'type': template.interaction_type,
                    'input_schema': template.input_schema,
                    'default_title': template.default_title,
                    'default_timeout': template.default_timeout
                })

            return JsonResponse({
                'success': True,
                'data': result
            })

        except Exception as e:
            logger.error(f'获取交互模板列表失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class CreateInteractionFromTemplateView(LoginRequiredMixin, View):
    """从模板创建交互"""

    def post(self, request):
        """从模板创建交互"""
        try:
            data = json.loads(request.body)
            template_id = data.get('template_id')
            workflow_execution_id = data.get('workflow_execution_id')
            node_execution_id = data.get('node_execution_id')
            custom_title = data.get('title')
            custom_description = data.get('description')

            template = WorkflowInteractionTemplate.objects.get(id=template_id)

            workflow_execution = AIWorkflowExecution.objects.get(
                id=workflow_execution_id)

            node_execution = None
            if node_execution_id:
                try:
                    node_execution = NodeExecution.objects.get(
                        id=node_execution_id)
                except NodeExecution.DoesNotExist:
                    pass

            interaction = template.apply(
                workflow_execution=workflow_execution,
                node_execution=node_execution,
                title=custom_title,
                description=custom_description,
                requester=request.user
            )

            return JsonResponse({
                'success': True,
                'message': '创建成功',
                'data': {
                    'interaction_id': str(interaction.id),
                    'title': interaction.title,
                    'input_schema': interaction.input_schema
                }
            })

        except WorkflowInteractionTemplate.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '模板不存在'
            }, status=404)
        except Exception as e:
            logger.error(f'从模板创建交互失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowCheckpointListView(LoginRequiredMixin, View):
    """工作流检查点列表API"""

    def get(self, request, execution_id):
        """获取执行检查点列表"""
        try:
            checkpoints = WorkflowCheckpoint.objects.filter(
                workflow_execution_id=execution_id
            ).order_by('-created_at')

            result = []
            for checkpoint in checkpoints:
                result.append({
                    'id': str(checkpoint.id),
                    'type': checkpoint.checkpoint_type,
                    'name': checkpoint.name,
                    'description': checkpoint.description,
                    'created_at': checkpoint.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })

            return JsonResponse({
                'success': True,
                'data': result
            })

        except Exception as e:
            logger.error(f'获取检查点列表失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    def post(self, request, execution_id):
        """创建检查点"""
        try:
            data = json.loads(request.body)
            checkpoint_type = data.get('type', 'manual')
            name = data.get('name', '')
            data.get('description', '')

            workflow_execution = AIWorkflowExecution.objects.get(
                id=execution_id)

            checkpoint = workflow_interaction_engine.create_checkpoint(
                workflow_execution=workflow_execution,
                context={},
                node_states={},
                checkpoint_type=checkpoint_type,
                name=name
            )

            return JsonResponse({
                'success': True,
                'message': '检查点创建成功',
                'data': {
                    'checkpoint_id': str(checkpoint.id)
                }
            })

        except AIWorkflowExecution.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '执行记录不存在'
            }, status=404)
        except Exception as e:
            logger.error(f'创建检查点失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowCheckpointRestoreView(LoginRequiredMixin, View):
    """恢复工作流检查点API"""

    def post(self, request, checkpoint_id):
        """从检查点恢复"""
        try:
            data = workflow_interaction_engine.restore_from_checkpoint(
                checkpoint_id)

            if not data:
                return JsonResponse({
                    'success': False,
                    'error': '检查点不存在'
                }, status=404)

            return JsonResponse({
                'success': True,
                'data': data
            })

        except Exception as e:
            logger.error(f'恢复检查点失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class InteractionNotificationsView(LoginRequiredMixin, View):
    """交互通知API - SSE实时推送"""

    def get(self, request):
        """SSE长连接，实时推送交互通知"""
        def event_stream():
            import time

            time.time()

            while True:
                try:
                    pending = workflow_interaction_service.get_pending_interactions(
                        user=request.user)

                    if pending:
                        yield f"data: {json.dumps({'type': 'new_interaction', 'count': len(pending)})}\n\n"

                    time.sleep(5)

                except GeneratorExit:
                    break
                except Exception as e:
                    logger.error(f'SSE错误: {e}')
                    break

        response = HttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'

        return response


@method_decorator(csrf_exempt, name='dispatch')
class WorkflowExecutionInteractionsView(LoginRequiredMixin, View):
    """获取工作流执行的所有交互"""

    def get(self, request, execution_id):
        """获取执行的交互列表"""
        try:
            interactions = WorkflowInteraction.objects.filter(
                workflow_execution_id=execution_id
            ).order_by('-created_at')

            result = []
            for interaction in interactions:
                result.append({
                    'id': str(interaction.id),
                    'type': interaction.interaction_type,
                    'title': interaction.title,
                    'status': interaction.status,
                    'priority': interaction.priority,
                    'input_data': interaction.input_data,
                    'result': interaction.result,
                    'comment': interaction.comment,
                    'requester_id': interaction.requester_id,
                    'handler_id': interaction.handler_id,
                    'created_at': interaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'responded_at': interaction.responded_at.strftime('%Y-%m-%d %H:%M:%S') if interaction.responded_at else None
                })

            return JsonResponse({
                'success': True,
                'data': result,
                'total': len(result)
            })

        except Exception as e:
            logger.error(f'获取执行交互列表失败: {e}')
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
