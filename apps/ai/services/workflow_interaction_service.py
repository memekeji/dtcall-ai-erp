"""
工作流交互服务
提供工作流执行过程中的用户交互管理
"""

import logging
from typing import Dict, Any, List, Optional
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.ai.models import (
    WorkflowNode, AIWorkflowExecution, NodeExecution
)
from apps.ai.models_workflow_interaction import (
    WorkflowInteraction,
    WorkflowCheckpoint
)

logger = logging.getLogger(__name__)


class WorkflowInteractionService:
    """工作流交互服务"""

    def __init__(self):
        self.pending_interactions = {}

    def create_interaction(
        self,
        workflow_execution: AIWorkflowExecution,
        node_execution: Optional[NodeExecution] = None,
        interaction_type: str = 'approval',
        title: str = '',
        description: str = '',
        input_schema: Optional[Dict] = None,
        requester: Any = None,
        handler: Any = None,
        timeout: int = 3600,
        priority: str = 'normal'
    ) -> WorkflowInteraction:
        """创建工作流交互"""
        try:
            interaction = WorkflowInteraction.objects.create(
                workflow_execution=workflow_execution,
                node_execution=node_execution,
                interaction_type=interaction_type,
                title=title,
                description=description,
                input_schema=input_schema or self._get_default_input_schema(
                    interaction_type),
                requester=requester,
                handler=handler,
                timeout=timeout,
                priority=priority,
                status='pending')

            logger.info(f"创建工作流交互成功: {interaction.id}")
            return interaction

        except Exception as e:
            logger.error(f"创建工作流交互失败: {e}")
            raise

    def _get_default_input_schema(self, interaction_type: str) -> Dict:
        """获取默认输入Schema"""
        schemas = {
            'approval': {
                'type': 'object',
                'properties': {
                    'approved': {
                        'type': 'boolean',
                        'label': '是否批准',
                        'default': True
                    },
                    'comment': {
                        'type': 'string',
                        'label': '审批意见',
                        'placeholder': '请输入审批意见...'
                    }
                },
                'required': ['approved']
            },
            'input': {
                'type': 'object',
                'properties': {},
                'required': []
            },
            'confirmation': {
                'type': 'object',
                'properties': {
                    'confirmed': {
                        'type': 'boolean',
                        'label': '确认操作',
                        'default': True
                    }
                },
                'required': ['confirmed']
            },
            'selection': {
                'type': 'object',
                'properties': {
                    'selected_option': {
                        'type': 'string',
                        'label': '选择选项'
                    }
                },
                'required': ['selected_option']
            },
            'review': {
                'type': 'object',
                'properties': {
                    'review_result': {
                        'type': 'string',
                        'label': '审核结果',
                        'enum': ['approved', 'rejected', 'needs_revision']
                    },
                    'review_comment': {
                        'type': 'string',
                        'label': '审核意见'
                    }
                },
                'required': ['review_result']
            },
            'feedback': {
                'type': 'object',
                'properties': {
                    'rating': {
                        'type': 'integer',
                        'label': '评分',
                        'minimum': 1,
                        'maximum': 5
                    },
                    'feedback_text': {
                        'type': 'string',
                        'label': '反馈内容'
                    }
                },
                'required': []
            }
        }
        return schemas.get(
            interaction_type, {
                'type': 'object', 'properties': {}})

    @transaction.atomic
    def complete_interaction(
        self,
        interaction_id: str,
        user: Any,
        input_data: Dict[str, Any],
        result: Optional[Dict] = None,
        comment: Optional[str] = None
    ) -> WorkflowInteraction:
        """完成工作流交互"""
        try:
            interaction = WorkflowInteraction.objects.select_for_update().get(id=interaction_id)

            if interaction.status == 'completed':
                raise ValidationError('该交互已经完成')

            if not interaction.can_complete(user):
                raise ValidationError('您没有权限处理此交互')

            if interaction.is_expired:
                interaction.status = 'timeout'
                interaction.save()
                raise ValidationError('该交互已超时')

            interaction.input_data = input_data
            interaction.result = result
            interaction.comment = comment
            interaction.handler = user
            interaction.status = 'completed'
            interaction.responded_at = timezone.now()
            interaction.save()

            logger.info(f"完成工作流交互成功: {interaction.id}")
            return interaction

        except WorkflowInteraction.DoesNotExist:
            raise ValidationError('交互不存在')
        except Exception as e:
            logger.error(f"完成工作流交互失败: {e}")
            raise

    def cancel_interaction(
        self,
        interaction_id: str,
        user: Any,
        reason: Optional[str] = None
    ) -> WorkflowInteraction:
        """取消工作流交互"""
        try:
            interaction = WorkflowInteraction.objects.get(id=interaction_id)

            if interaction.requester_id != user.id:
                raise ValidationError('您没有权限取消此交互')

            if interaction.status == 'completed':
                raise ValidationError('已完成的交互不能取消')

            interaction.status = 'cancelled'
            interaction.comment = reason
            interaction.save()

            return interaction

        except WorkflowInteraction.DoesNotExist:
            raise ValidationError('交互不存在')

    def get_pending_interactions(
        self,
        user: Optional[Any] = None,
        workflow_execution_id: Optional[str] = None
    ) -> List[WorkflowInteraction]:
        """获取待处理的交互"""
        queryset = WorkflowInteraction.objects.filter(
            status__in=['pending', 'in_progress']
        )

        if user:
            queryset = queryset.filter(
                models.Q(requester=user) | models.Q(handler=user)
            )

        if workflow_execution_id:
            queryset = queryset.filter(
                workflow_execution_id=workflow_execution_id)

        return list(queryset.order_by('-priority', '-created_at'))

    def get_interaction_status(self, interaction_id: str) -> Dict[str, Any]:
        """获取交互状态"""
        try:
            interaction = WorkflowInteraction.objects.get(id=interaction_id)

            return {
                'id': str(interaction.id),
                'type': interaction.interaction_type,
                'title': interaction.title,
                'status': interaction.status,
                'priority': interaction.priority,
                'requester': interaction.requester_id,
                'handler': interaction.handler_id,
                'input_schema': interaction.input_schema,
                'input_data': interaction.input_data,
                'result': interaction.result,
                'is_expired': interaction.is_expired,
                'created_at': interaction.created_at,
                'responded_at': interaction.responded_at
            }

        except WorkflowInteraction.DoesNotExist:
            return None

    def create_approval_interaction(
        self,
        workflow_execution: AIWorkflowExecution,
        node_execution: Optional[NodeExecution] = None,
        title: str = '',
        description: str = '',
        requester: Any = None,
        handler: Any = None,
        timeout: int = 3600
    ) -> WorkflowInteraction:
        """创建审批交互"""
        return self.create_interaction(
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            interaction_type='approval',
            title=title or '审批请求',
            description=description,
            input_schema=self._get_default_input_schema('approval'),
            requester=requester,
            handler=handler,
            timeout=timeout,
            priority='high'
        )

    def create_input_interaction(
        self,
        workflow_execution: AIWorkflowExecution,
        node_execution: Optional[NodeExecution] = None,
        title: str = '',
        description: str = '',
        input_schema: Optional[Dict] = None,
        requester: Any = None,
        handler: Any = None,
        timeout: int = 3600
    ) -> WorkflowInteraction:
        """创建表单输入交互"""
        return self.create_interaction(
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            interaction_type='input',
            title=title or '请输入信息',
            description=description,
            input_schema=input_schema or self._get_default_input_schema(
                'input'),
            requester=requester,
            handler=handler,
            timeout=timeout)

    def create_confirmation_interaction(
        self,
        workflow_execution: AIWorkflowExecution,
        node_execution: Optional[NodeExecution] = None,
        title: str = '',
        description: str = '',
        requester: Any = None,
        handler: Any = None,
        timeout: int = 3600
    ) -> WorkflowInteraction:
        """创建确认交互"""
        return self.create_interaction(
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            interaction_type='confirmation',
            title=title or '请确认操作',
            description=description,
            input_schema=self._get_default_input_schema('confirmation'),
            requester=requester,
            handler=handler,
            timeout=timeout
        )

    def create_selection_interaction(
        self,
        workflow_execution: AIWorkflowExecution,
        node_execution: Optional[NodeExecution] = None,
        title: str = '',
        options: Optional[List[Dict]] = None,
        requester: Any = None,
        handler: Any = None,
        timeout: int = 3600
    ) -> WorkflowInteraction:
        """创建选项选择交互"""
        input_schema = {
            'type': 'object',
            'properties': {
                'selected_option': {
                    'type': 'string',
                    'label': '选择选项',
                    'options': options or []
                }
            },
            'required': ['selected_option']
        }

        return self.create_interaction(
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            interaction_type='selection',
            title=title or '请选择',
            input_schema=input_schema,
            requester=requester,
            handler=handler,
            timeout=timeout
        )


class WorkflowInteractionEngine:
    """工作流交互引擎 - 在工作流执行过程中处理用户交互"""

    def __init__(self):
        self.interaction_service = WorkflowInteractionService()
        self.waiting_for_interaction = {}

    async def wait_for_approval(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        workflow_execution: AIWorkflowExecution,
        node_execution: NodeExecution,
        timeout: int = 3600
    ) -> Dict[str, Any]:
        """等待用户审批"""
        config = node.config or {}
        title = config.get('approval_title', f'请审批: {node.name}')
        description = config.get('approval_description', '')
        approver_id = config.get('approver_id')

        from django.contrib.auth import get_user_model
        User = get_user_model()

        approver = None
        if approver_id:
            try:
                approver = User.objects.get(id=approver_id)
            except User.DoesNotExist:
                pass

        interaction = self.interaction_service.create_approval_interaction(
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            title=title,
            description=description,
            requester=context.get('user'),
            handler=approver,
            timeout=timeout
        )

        self.waiting_for_interaction[str(interaction.id)] = {
            'interaction': interaction,
            'context': context,
            'node': node
        }

        return {
            'waiting_interaction_id': str(interaction.id),
            'status': 'waiting_for_approval'
        }

    async def wait_for_input(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        workflow_execution: AIWorkflowExecution,
        node_execution: NodeExecution,
        input_schema: Optional[Dict] = None,
        timeout: int = 3600
    ) -> Dict[str, Any]:
        """等待用户输入"""
        config = node.config or {}
        title = config.get('input_title', f'请输入: {node.name}')
        description = config.get('input_description', '')

        schema = input_schema or config.get('input_schema', {})

        interaction = self.interaction_service.create_input_interaction(
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            title=title,
            description=description,
            input_schema=schema,
            requester=context.get('user'),
            timeout=timeout
        )

        self.waiting_for_interaction[str(interaction.id)] = {
            'interaction': interaction,
            'context': context,
            'node': node
        }

        return {
            'waiting_interaction_id': str(interaction.id),
            'status': 'waiting_for_input',
            'input_schema': interaction.input_schema
        }

    async def wait_for_confirmation(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        workflow_execution: AIWorkflowExecution,
        node_execution: NodeExecution,
        message: str = '',
        timeout: int = 3600
    ) -> Dict[str, Any]:
        """等待用户确认"""
        interaction = self.interaction_service.create_confirmation_interaction(
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            title=message or f'请确认: {node.name}',
            requester=context.get('user'),
            timeout=timeout
        )

        self.waiting_for_interaction[str(interaction.id)] = {
            'interaction': interaction,
            'context': context,
            'node': node
        }

        return {
            'waiting_interaction_id': str(interaction.id),
            'status': 'waiting_for_confirmation'
        }

    async def wait_for_selection(
        self,
        node: WorkflowNode,
        context: Dict[str, Any],
        workflow_execution: AIWorkflowExecution,
        node_execution: NodeExecution,
        options: List[Dict],
        title: str = '',
        timeout: int = 3600
    ) -> Dict[str, Any]:
        """等待用户选择"""
        interaction = self.interaction_service.create_selection_interaction(
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            title=title or f'请选择: {node.name}',
            options=options,
            requester=context.get('user'),
            timeout=timeout
        )

        self.waiting_for_interaction[str(interaction.id)] = {
            'interaction': interaction,
            'context': context,
            'node': node
        }

        return {
            'waiting_interaction_id': str(interaction.id),
            'status': 'waiting_for_selection',
            'options': options
        }

    def get_waiting_interaction(self, interaction_id: str) -> Optional[Dict]:
        """获取等待中的交互"""
        return self.waiting_for_interaction.get(interaction_id)

    def process_interaction_response(
        self,
        interaction_id: str,
        user: Any,
        response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理交互响应"""
        waiting = self.waiting_for_interaction.get(interaction_id)
        if not waiting:
            return {'success': False, 'error': '交互不存在或已过期'}

        waiting['interaction']

        try:
            completed_interaction = self.interaction_service.complete_interaction(
                interaction_id=interaction_id,
                user=user,
                input_data=response_data
            )

            del self.waiting_for_interaction[interaction_id]

            return {
                'success': True,
                'interaction': completed_interaction,
                'result': completed_interaction.result
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def create_checkpoint(
        self,
        workflow_execution: AIWorkflowExecution,
        context: Dict[str, Any],
        node_states: Dict[str, Any],
        checkpoint_type: str = 'manual',
        name: str = ''
    ) -> WorkflowCheckpoint:
        """创建检查点"""
        checkpoint = WorkflowCheckpoint.objects.create(
            workflow_execution=workflow_execution,
            checkpoint_type=checkpoint_type,
            name=name or f'检查点 {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}',
            context_data=context,
            node_states=node_states
        )

        logger.info(f"创建工作流检查点: {checkpoint.id}")
        return checkpoint

    def restore_from_checkpoint(
        self,
        checkpoint_id: str
    ) -> Optional[Dict[str, Any]]:
        """从检查点恢复"""
        try:
            checkpoint = WorkflowCheckpoint.objects.get(id=checkpoint_id)
            return checkpoint.restore()
        except WorkflowCheckpoint.DoesNotExist:
            return None


class NodeInteractionHandler:
    """节点交互处理器 - 处理特定节点类型的交互需求"""

    @staticmethod
    async def handle_approval_node(
        node: WorkflowNode,
        context: Dict[str, Any],
        workflow_execution: AIWorkflowExecution,
        node_execution: NodeExecution,
        engine: WorkflowInteractionEngine
    ) -> Dict[str, Any]:
        """处理审批节点"""
        config = node.config or {}

        if not config.get('require_approval', False):
            return {'approved': True, 'skipped': True}

        timeout = config.get('approval_timeout', 3600)

        result = await engine.wait_for_approval(
            node=node,
            context=context,
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            timeout=timeout
        )

        return result

    @staticmethod
    async def handle_input_node(
        node: WorkflowNode,
        context: Dict[str, Any],
        workflow_execution: AIWorkflowExecution,
        node_execution: NodeExecution,
        engine: WorkflowInteractionEngine
    ) -> Dict[str, Any]:
        """处理输入节点"""
        config = node.config or {}
        input_schema = config.get('input_schema', {})
        timeout = config.get('input_timeout', 3600)

        result = await engine.wait_for_input(
            node=node,
            context=context,
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            input_schema=input_schema,
            timeout=timeout
        )

        return result

    @staticmethod
    async def handle_confirmation_node(
        node: WorkflowNode,
        context: Dict[str, Any],
        workflow_execution: AIWorkflowExecution,
        node_execution: NodeExecution,
        engine: WorkflowInteractionEngine
    ) -> Dict[str, Any]:
        """处理确认节点"""
        config = node.config or {}
        message = config.get('confirmation_message', f'请确认执行: {node.name}')
        timeout = config.get('confirmation_timeout', 3600)

        result = await engine.wait_for_confirmation(
            node=node,
            context=context,
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            message=message,
            timeout=timeout
        )

        return result

    @staticmethod
    async def handle_selection_node(
        node: WorkflowNode,
        context: Dict[str, Any],
        workflow_execution: AIWorkflowExecution,
        node_execution: NodeExecution,
        engine: WorkflowInteractionEngine
    ) -> Dict[str, Any]:
        """处理选择节点"""
        config = node.config or {}
        options = config.get('selection_options', [])
        title = config.get('selection_title', f'请选择: {node.name}')
        timeout = config.get('selection_timeout', 3600)

        result = await engine.wait_for_selection(
            node=node,
            context=context,
            workflow_execution=workflow_execution,
            node_execution=node_execution,
            options=options,
            title=title,
            timeout=timeout
        )

        return result


workflow_interaction_service = WorkflowInteractionService()
workflow_interaction_engine = WorkflowInteractionEngine()
