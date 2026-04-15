"""
增强型工作流配置服务
重构后的工作流核心配置和执行管理
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.ai.models import (
    AIWorkflow, WorkflowNode, WorkflowConnection,
    AIWorkflowExecution, NodeExecution
)

logger = logging.getLogger(__name__)


class NodeLayer(Enum):
    """节点层级枚举"""
    CORE_CONTROL = 1
    DATA_IO = 2
    AI_CAPABILITY = 3
    LOGIC_CONTROL = 4
    DATA_PROCESSING = 5
    INTEGRATION = 6


class ExecutionMode(Enum):
    """执行模式"""
    SYNC = "sync"
    ASYNC = "async"
    PARALLEL = "parallel"


class NodeStatus(Enum):
    """节点执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class NodeLayerMapping:
    """节点层级映射配置"""
    layer: NodeLayer
    layer_name: str
    node_types: List[str]
    can_call_layers: List[int]
    description: str


@dataclass
class ExecutionContext:
    """执行上下文"""
    execution_id: str
    workflow_id: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    node_results: Dict[str, Any] = field(default_factory=dict)
    error_info: Optional[Dict[str, Any]] = None
    started_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    current_node_id: Optional[str] = None
    branch_variables: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataFlowRule:
    """数据流转规则"""
    source_type: str
    target_type: str
    allowed_transformations: List[str]
    required_mapping: bool
    validation_schema: Dict[str, Any]


class NodeHierarchyManager:
    """节点层级管理器"""

    _layer_mappings: Dict[str, NodeLayerMapping] = {}

    @classmethod
    def initialize(cls):
        """初始化节点层级映射"""
        cls._layer_mappings = {
            'core_control': NodeLayerMapping(
                layer=NodeLayer.CORE_CONTROL,
                layer_name='核心控制层',
                node_types=['start', 'end', 'workflow_trigger'],
                can_call_layers=[NodeLayer.DATA_IO.value],
                description='负责工作流的整体控制和流程编排'
            ),
            'data_io': NodeLayerMapping(
                layer=NodeLayer.DATA_IO,
                layer_name='数据IO层',
                node_types=['data_input', 'data_output', 'database_query',
                            'file_operation', 'document_extractor'],
                can_call_layers=[NodeLayer.AI_CAPABILITY.value],
                description='负责数据的输入输出和数据源连接管理'
            ),
            'ai_capability': NodeLayerMapping(
                layer=NodeLayer.AI_CAPABILITY,
                layer_name='AI能力层',
                node_types=['ai_model', 'ai_generation', 'ai_classification',
                            'ai_extraction', 'knowledge_retrieval', 'intent_recognition',
                            'sentiment_analysis', 'question_answer', 'conversation_history'],
                can_call_layers=[
                    NodeLayer.LOGIC_CONTROL.value,
                    NodeLayer.DATA_PROCESSING.value],
                description='封装各种AI能力，为工作流提供智能支持'
            ),
            'logic_control': NodeLayerMapping(
                layer=NodeLayer.LOGIC_CONTROL,
                layer_name='逻辑控制层',
                node_types=['condition', 'switch', 'loop', 'iterator',
                            'parallel', 'delay', 'wait'],
                can_call_layers=[
                    NodeLayer.AI_CAPABILITY.value,
                    NodeLayer.DATA_PROCESSING.value],
                description='实现复杂的流程控制逻辑'
            ),
            'data_processing': NodeLayerMapping(
                layer=NodeLayer.DATA_PROCESSING,
                layer_name='数据处理层',
                node_types=['data_transformation', 'data_filter', 'data_aggregation',
                            'data_format', 'text_processing', 'template',
                            'variable_aggregation', 'parameter_aggregator', 'variable_assign'],
                can_call_layers=[
                    NodeLayer.DATA_IO.value,
                    NodeLayer.INTEGRATION.value],
                description='对数据进行转换、过滤、聚合等处理操作'
            ),
            'integration': NodeLayerMapping(
                layer=NodeLayer.INTEGRATION,
                layer_name='集成服务层',
                node_types=['api_call', 'http_request', 'webhook', 'code_execution',
                            'code_block', 'tool_call', 'message_queue', 'notification'],
                can_call_layers=[NodeLayer.CORE_CONTROL.value],
                description='提供与外部系统和服务集成的能力'
            )
        }

    @classmethod
    def get_node_layer(cls, node_type: str) -> Optional[NodeLayer]:
        """获取节点类型对应的层级"""
        if not cls._layer_mappings:
            cls.initialize()

        for layer_mapping in cls._layer_mappings.values():
            if node_type in layer_mapping.node_types:
                return layer_mapping.layer
        return None

    @classmethod
    def get_allowed_callers(cls, node_type: str) -> List[int]:
        """获取可以调用该节点类型的层级列表"""
        if not cls._layer_mappings:
            cls.initialize()

        for mapping in cls._layer_mappings.values():
            if node_type in mapping.node_types:
                return mapping.can_call_layers
        return []

    @classmethod
    def validate_node_hierarchy(cls, workflow: AIWorkflow) -> List[str]:
        """验证工作流的节点层级结构是否合法"""
        errors = []
        nodes = list(workflow.nodes.filter(is_active=True))

        for node in nodes:
            source_connections = node.output_connections.all()

            for conn in source_connections:
                caller_layer = cls.get_node_layer(conn.source_node.node_type)
                callee_layer = cls.get_node_layer(node.node_type)

                if caller_layer and callee_layer:
                    if callee_layer.value not in cls.get_allowed_callers(
                            conn.source_node.node_type):
                        errors.append(
                            f"节点 '{conn.source_node.name}' (层级{caller_layer.value}) "
                            f"不能直接调用节点 '{node.name}' (层级{callee_layer.value})")

        return errors


class DataFlowManager:
    """数据流转管理器"""

    _data_flow_rules: Dict[str, DataFlowRule] = {}

    @classmethod
    def initialize(cls):
        """初始化数据流转规则"""
        cls._data_flow_rules = {
            ('data_input', 'ai_model'): DataFlowRule(
                source_type='data_input',
                target_type='ai_model',
                allowed_transformations=[
                    'passthrough', 'field_mapping', 'type_cast'],
                required_mapping=True,
                validation_schema={
                    'required_fields': ['text', 'context'],
                    'data_types': {'text': str, 'context': dict}
                }
            ),
            ('ai_model', 'data_output'): DataFlowRule(
                source_type='ai_model',
                target_type='data_output',
                allowed_transformations=[
                    'passthrough', 'field_mapping', 'filter'],
                required_mapping=False,
                validation_schema={
                    'required_fields': ['result'],
                    'data_types': {'result': str}
                }
            ),
            ('condition', 'ai_model'): DataFlowRule(
                source_type='condition',
                target_type='ai_model',
                allowed_transformations=['passthrough', 'branch_selection'],
                required_mapping=False,
                validation_schema={}
            ),
            ('data_processing', 'data_output'): DataFlowRule(
                source_type='data_processing',
                target_type='data_output',
                allowed_transformations=['passthrough', 'format_transform'],
                required_mapping=True,
                validation_schema={
                    'required_fields': ['processed_data'],
                    'data_types': {'processed_data': (dict, list)}
                }
            )
        }

    @classmethod
    def get_flow_rule(
            cls,
            source_type: str,
            target_type: str) -> Optional[DataFlowRule]:
        """获取数据流转规则"""
        if not cls._data_flow_rules:
            cls.initialize()

        key = (source_type, target_type)
        return cls._data_flow_rules.get(key)

    @classmethod
    def validate_data_flow(cls,
                           source_node: WorkflowNode,
                           target_node: WorkflowNode,
                           data: Dict[str,
                                      Any]) -> tuple:
        """
        验证数据流转是否合法

        Returns:
            (is_valid: bool, errors: List[str], transformed_data: Dict)
        """
        flow_rule = cls.get_flow_rule(
            source_node.node_type, target_node.node_type)

        if not flow_rule:
            return True, [], data

        errors = []
        transformed_data = data.copy()

        # 验证必需字段
        for field_name in flow_rule.validation_schema.get(
                'required_fields', []):
            if field_name not in transformed_data:
                errors.append(
                    f"从 '{source_node.name}' 传递到 '{target_node.name}' "
                    f"缺少必需字段: {field_name}"
                )

        # 验证数据类型
        for field_name, expected_type in flow_rule.validation_schema.get(
                'data_types', {}).items():
            if field_name in transformed_data:
                if not isinstance(transformed_data[field_name], expected_type):
                    errors.append(
                        f"字段 '{field_name}' 类型错误，期望 {expected_type}"
                    )
                    try:
                        transformed_data[field_name] = expected_type(
                            transformed_data[field_name]
                        )
                    except (ValueError, TypeError):
                        pass

        return len(errors) == 0, errors, transformed_data

    @classmethod
    def transform_data(cls,
                       data: Dict[str,
                                  Any],
                       transformation: str,
                       mapping_config: Dict[str,
                                            str] = None) -> Dict[str,
                                                                 Any]:
        """根据转换规则转换数据"""
        if transformation == 'passthrough':
            return data.copy()

        if transformation == 'field_mapping' and mapping_config:
            return cls._apply_field_mapping(data, mapping_config)

        if transformation == 'type_cast':
            return cls._apply_type_casting(data)

        return data

    @classmethod
    def _apply_field_mapping(cls, data: Dict[str, Any],
                             mapping: Dict[str, str]) -> Dict[str, Any]:
        """应用字段映射"""
        result = {}
        for source, target in mapping.items():
            if source in data:
                result[target] = data[source]
        return result

    @classmethod
    def _apply_type_casting(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """应用类型转换"""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    if value.lower() in ('true', 'false'):
                        result[key] = value.lower() == 'true'
                    else:
                        result[key] = float(value)
                        if result[key].is_integer():
                            result[key] = int(result[key])
                except (ValueError, AttributeError):
                    result[key] = value
            else:
                result[key] = value
        return result


class ParameterValidator:
    """参数验证器"""

    _validation_rules = {
        'required': {
            'validator': lambda v: v is not None and v != '',
            'error_message': '参数 {param_name} 为必填项'
        },
        'string': {
            'validator': lambda v: isinstance(v, str),
            'error_message': '参数 {param_name} 必须为字符串类型'
        },
        'number': {
            'validator': lambda v: isinstance(v, (int, float)),
            'error_message': '参数 {param_name} 必须为数字类型'
        },
        'boolean': {
            'validator': lambda v: isinstance(v, bool),
            'error_message': '参数 {param_name} 必须为布尔类型'
        },
        'dict': {
            'validator': lambda v: isinstance(v, dict),
            'error_message': '参数 {param_name} 必须为字典类型'
        },
        'list': {
            'validator': lambda v: isinstance(v, list),
            'error_message': '参数 {param_name} 必须为列表类型'
        },
        'min_length': {
            'validator': lambda v, p: len(v) >= p['min'],
            'error_message': '参数 {param_name} 长度必须大于等于 {min}'
        },
        'max_length': {
            'validator': lambda v, p: len(v) <= p['max'],
            'error_message': '参数 {param_name} 长度必须小于等于 {max}'
        },
        'min_value': {
            'validator': lambda v, p: v >= p['min'],
            'error_message': '参数 {param_name} 值必须大于等于 {min}'
        },
        'max_value': {
            'validator': lambda v, p: v <= p['max'],
            'error_message': '参数 {param_name} 值必须小于等于 {max}'
        },
        'pattern': {
            'validator': lambda v, p: bool(p['pattern'].match(str(v))),
            'error_message': '参数 {param_name} 格式不匹配'
        }
    }

    @classmethod
    def validate_parameters(cls, params: Dict[str, Any],
                            schema: Dict[str, Any]) -> tuple:
        """
        验证参数是否符合Schema定义

        Returns:
            (is_valid: bool, errors: List[str])
        """
        errors = []

        for field_name, field_schema in schema.items():
            value = params.get(field_name)

            # 必填验证
            if field_schema.get('required', False):
                rule = cls._validation_rules['required']
                if not rule['validator'](value):
                    errors.append(
                        rule['error_message'].format(param_name=field_name)
                    )
                    continue

            # 如果值为空且不是必填，跳过其他验证
            if value is None or value == '':
                continue

            # 类型验证
            expected_type = field_schema.get('type')
            if expected_type:
                type_validator = cls._validation_rules.get(expected_type)
                if type_validator and not type_validator['validator'](value):
                    errors.append(
                        type_validator['error_message'].format(
                            param_name=field_name))
                    continue

            # 范围验证
            if isinstance(value, (str, list)):
                if 'min_length' in field_schema:
                    rule = cls._validation_rules['min_length']
                    if not rule['validator'](value, field_schema):
                        errors.append(
                            rule['error_message'].format(
                                param_name=field_name,
                                min=field_schema['min_length']
                            )
                        )

                if 'max_length' in field_schema:
                    rule = cls._validation_rules['max_length']
                    if not rule['validator'](value, field_schema):
                        errors.append(
                            rule['error_message'].format(
                                param_name=field_name,
                                max=field_schema['max_length']
                            )
                        )

            if isinstance(value, (int, float)):
                if 'min_value' in field_schema:
                    rule = cls._validation_rules['min_value']
                    if not rule['validator'](value, field_schema):
                        errors.append(
                            rule['error_message'].format(
                                param_name=field_name,
                                min=field_schema['min_value']
                            )
                        )

                if 'max_value' in field_schema:
                    rule = cls._validation_rules['max_value']
                    if not rule['validator'](value, field_schema):
                        errors.append(
                            rule['error_message'].format(
                                param_name=field_name,
                                max=field_schema['max_value']
                            )
                        )

            # 正则验证
            if 'pattern' in field_schema:
                import re
                rule = cls._validation_rules['pattern']
                pattern = {'pattern': re.compile(field_schema['pattern'])}
                if not rule['validator'](value, pattern):
                    errors.append(
                        rule['error_message'].format(param_name=field_name)
                    )

        return len(errors) == 0, errors


class WorkflowExecutionService:
    """工作流执行服务"""

    def __init__(self):
        self.node_hierarchy = NodeHierarchyManager()
        self.data_flow = DataFlowManager()
        self.parameter_validator = ParameterValidator()
        self.node_hierarchy.initialize()
        self.data_flow.initialize()

    @transaction.atomic
    def create_execution(self, workflow_id: str, user_id: int,
                         input_data: Dict[str, Any]) -> AIWorkflowExecution:
        """创建工作流执行实例"""
        workflow = AIWorkflow.objects.get(id=workflow_id)

        # 验证工作流状态
        if workflow.status != 'published':
            raise ValidationError("只能执行已发布的工作流")

        # 验证节点层级结构
        hierarchy_errors = self.node_hierarchy.validate_node_hierarchy(
            workflow)
        if hierarchy_errors:
            raise ValidationError(
                f"工作流节点层级结构不合法: {'; '.join(hierarchy_errors)}"
            )

        execution = AIWorkflowExecution.objects.create(
            workflow=workflow,
            created_by_id=user_id,
            input_data=input_data,
            status='pending'
        )

        logger.info(f"创建工作流执行: {execution.id}, 工作流: {workflow.name}")
        return execution

    def prepare_execution_context(
            self, execution: AIWorkflowExecution) -> ExecutionContext:
        """准备执行上下文"""
        workflow = execution.workflow

        # 初始化变量
        variables = {}
        for var in workflow.variables.all():
            variables[var.name] = var.default_value

        # 添加输入数据
        input_data = execution.input_data or {}
        variables['input_data'] = input_data

        return ExecutionContext(
            execution_id=str(execution.id),
            workflow_id=str(workflow.id),
            input_data=input_data,
            variables=variables,
            metadata={
                'user_id': execution.created_by_id,
                'started_at': timezone.now(),
                'execution_mode': ExecutionMode.SYNC.value
            }
        )

    def execute_node(self, node: WorkflowNode,
                     context: ExecutionContext) -> Dict[str, Any]:
        """执行单个节点（带完整错误处理）"""
        from apps.ai.processors import get_processor_for_node_type

        context.current_node_id = str(node.id)

        try:
            # Step 1: 获取处理器
            processor = get_processor_for_node_type(node.node_type)
            if not processor:
                raise ValueError(f"不支持的节点类型: {node.node_type}")

            # Step 2: 提取输入参数
            input_params = self._extract_input_parameters(node, context)

            # Step 3: 验证输入参数
            input_schema = node.config.get('input_schema', {})
            is_valid, errors = self.parameter_validator.validate_parameters(
                input_params, input_schema
            )
            if not is_valid:
                raise ValidationError(f"输入参数验证失败: {'; '.join(errors)}")

            # Step 4: 执行节点逻辑
            result = processor.execute(node.config, context.variables)

            # Step 5: 验证输出结果
            output_schema = node.config.get('output_schema', {})
            if output_schema:
                is_valid, errors = self.parameter_validator.validate_parameters(
                    result, output_schema)
                if not is_valid:
                    logger.warning(
                        f"节点 '{node.name}' 输出参数验证失败: {'; '.join(errors)}"
                    )

            # Step 6: 更新上下文
            self._update_context_with_result(node, result, context)

            # Step 7: 记录执行结果
            self._record_node_execution(
                node, context, result, 'completed', None)

            return result

        except ValidationError as e:
            logger.warning(f"节点 '{node.name}' 验证失败: {e}")
            self._record_node_execution(
                node, context, {}, 'skipped', str(e)
            )
            return {'status': 'skipped', 'error': str(e)}

        except Exception as e:
            logger.error(f"节点 '{node.name}' 执行失败: {e}", exc_info=True)
            self._record_node_execution(
                node, context, {}, 'failed', str(e)
            )
            raise

    def _extract_input_parameters(self, node: WorkflowNode,
                                  context: ExecutionContext) -> Dict[str, Any]:
        """提取节点输入参数"""
        input_params = {}
        input_mapping = node.config.get('input_mapping', {})

        for param_name, source in input_mapping.items():
            # 解析变量引用
            if isinstance(source, str) and source.startswith(
                    '{{') and source.endswith('}}'):
                var_name = source[2:-2]
                value = self._get_nested_value(context.variables, var_name)
            else:
                value = context.variables.get(source)

            input_params[param_name] = value

        return input_params

    def _get_nested_value(self, data: Dict[str, Any],
                          path: str) -> Any:
        """获取嵌套值"""
        keys = path.split('.')
        value = data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                index = int(key)
                value = value[index] if index < len(value) else None
            else:
                return None

        return value

    def _update_context_with_result(self, node: WorkflowNode,
                                    result: Dict[str, Any],
                                    context: ExecutionContext) -> None:
        """更新上下文中的结果"""
        output_mapping = node.config.get('output_mapping', {})

        for source_field, target in output_mapping.items():
            value = self._get_nested_value(result, source_field)

            # 解析目标位置
            if isinstance(target, str) and target.startswith('${'):
                namespace_var = target[2:-1]
                if '.' in namespace_var:
                    namespace, var_name = namespace_var.split('.', 1)
                    if namespace == 'global':
                        context.variables[var_name] = value
                    elif namespace == 'branch':
                        context.branch_variables[var_name] = value
            else:
                context.variables[target] = value

        # 记录节点结果
        context.node_results[str(node.id)] = result

    def _record_node_execution(self, node: WorkflowNode,
                               context: ExecutionContext,
                               result: Dict[str, Any],
                               status: str,
                               error_message: Optional[str]) -> None:
        """记录节点执行历史"""
        NodeExecution.objects.create(
            workflow_execution_id=context.execution_id,
            node=node,
            status=status,
            input_data=context.variables.copy(),
            output_data=result,
            error_message=error_message,
            completed_at=timezone.now()
        )

    def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """获取执行状态"""
        execution = AIWorkflowExecution.objects.get(id=execution_id)
        node_executions = execution.node_executions.all()

        return {
            'execution_id': str(
                execution.id),
            'workflow_id': str(
                execution.workflow.id),
            'status': execution.status,
            'started_at': execution.started_at,
            'completed_at': execution.completed_at,
            'node_count': node_executions.count(),
            'completed_count': node_executions.filter(
                status='completed').count(),
            'failed_count': node_executions.filter(
                    status='failed').count(),
            'skipped_count': node_executions.filter(
                        status='skipped').count()}


class WorkflowRefactoringService:
    """工作流重构服务"""

    def __init__(self):
        self.execution_service = WorkflowExecutionService()
        self.node_hierarchy = NodeHierarchyManager()
        self.data_flow = DataFlowManager()
        self.node_hierarchy.initialize()
        self.data_flow.initialize()

    @transaction.atomic
    def refactor_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        重构工作流

        重构内容：
        1. 验证并优化节点层级结构
        2. 标准化节点配置
        3. 完善数据流转规则
        4. 添加异常处理配置
        """
        workflow = AIWorkflow.objects.get(id=workflow_id)
        nodes = workflow.nodes.filter(is_active=True)

        refactoring_report = {
            'workflow_id': str(workflow.id),
            'workflow_name': workflow.name,
            'changes': [],
            'warnings': [],
            'errors': []
        }

        # Step 1: 分析当前工作流结构
        self._analyze_workflow_structure(workflow)

        # Step 2: 验证节点层级
        hierarchy_errors = self.node_hierarchy.validate_node_hierarchy(
            workflow)
        if hierarchy_errors:
            refactoring_report['errors'].extend(hierarchy_errors)

        # Step 3: 优化节点配置
        for node in nodes:
            changes = self._optimize_node_config(node)
            if changes:
                refactoring_report['changes'].extend(changes)

        # Step 4: 优化连接配置
        connections = workflow.connections.all()
        for conn in connections:
            changes = self._optimize_connection_config(conn)
            if changes:
                refactoring_report['changes'].extend(changes)

        # Step 5: 添加缺失的配置
        self._add_missing_configs(workflow, refactoring_report)

        logger.info(
            f"工作流重构完成: {workflow.name}, "
            f"变更数量: {len(refactoring_report['changes'])}, "
            f"警告数量: {len(refactoring_report['warnings'])}, "
            f"错误数量: {len(refactoring_report['errors'])}"
        )

        return refactoring_report

    def _analyze_workflow_structure(
            self, workflow: AIWorkflow) -> Dict[str, Any]:
        """分析工作流结构"""
        nodes = list(workflow.nodes.filter(is_active=True))
        connections = list(workflow.connections.all())

        return {
            'node_count': len(nodes),
            'connection_count': len(connections),
            'node_types': [n.node_type for n in nodes],
            'layers': {
                NodeLayer.CORE_CONTROL.name: 0,
                NodeLayer.DATA_IO.name: 0,
                NodeLayer.AI_CAPABILITY.name: 0,
                NodeLayer.LOGIC_CONTROL.name: 0,
                NodeLayer.DATA_PROCESSING.name: 0,
                NodeLayer.INTEGRATION.name: 0
            }
        }

    def _optimize_node_config(
            self, node: WorkflowNode) -> List[Dict[str, Any]]:
        """优化节点配置"""
        changes = []
        current_config = node.config.copy()
        optimized_config = current_config.copy()

        # 确保有输入输出配置
        if 'input_mapping' not in optimized_config:
            optimized_config['input_mapping'] = {}
            changes.append({
                'node_name': node.name,
                'change_type': 'add_config',
                'detail': '添加 input_mapping 配置'
            })

        if 'output_mapping' not in optimized_config:
            optimized_config['output_mapping'] = {}
            changes.append({
                'node_name': node.name,
                'change_type': 'add_config',
                'detail': '添加 output_mapping 配置'
            })

        # 确保有错误处理配置
        if 'error_handling' not in optimized_config:
            optimized_config['error_handling'] = {
                'continue_on_error': False,
                'fallback_value': None
            }
            changes.append({
                'node_name': node.name,
                'change_type': 'add_config',
                'detail': '添加 error_handling 配置'
            })

        # 确保有执行配置
        if 'execution_config' not in optimized_config:
            optimized_config['execution_config'] = {
                'timeout': 30,
                'retry_count': 0,
                'priority': 'normal'
            }
            changes.append({
                'node_name': node.name,
                'change_type': 'add_config',
                'detail': '添加 execution_config 配置'
            })

        # 更新配置
        if optimized_config != current_config:
            node.config = optimized_config
            node.save()

        return changes

    def _optimize_connection_config(
            self, conn: WorkflowConnection) -> List[Dict[str, Any]]:
        """优化连接配置"""
        changes = []
        current_config = conn.config or {}

        # 确保连接有必要的配置
        if 'condition' not in current_config:
            current_config['condition'] = None
            changes.append({
                'connection': f"{conn.source_node.name} -> {conn.target_node.name}",
                'change_type': 'add_config',
                'detail': '添加连接条件配置'
            })

        # 更新配置
        if current_config != conn.config:
            conn.config = current_config
            conn.save()

        return changes

    def _add_missing_configs(self, workflow: AIWorkflow,
                             report: Dict[str, Any]) -> None:
        """添加缺失的配置"""
        # 检查是否有开始和结束节点
        nodes = workflow.nodes.filter(is_active=True)
        has_start = any(n.node_type == 'start' for n in nodes)
        has_end = any(n.node_type == 'end' for n in nodes)

        if not has_start:
            report['warnings'].append({
                'type': 'missing_node',
                'detail': '工作流缺少开始节点'
            })

        if not has_end:
            report['warnings'].append({
                'type': 'missing_node',
                'detail': '工作流缺少结束节点'
            })

        # 检查变量配置
        for node in nodes:
            if node.node_type in ['ai_model', 'ai_generation']:
                if 'output_variable' not in node.config:
                    node.config['output_variable'] = f'{node.name}_result'
                    node.save()
                    report['changes'].append({
                        'node_name': node.name,
                        'change_type': 'fix_config',
                        'detail': '添加缺失的 output_variable 配置'
                    })


# 初始化服务
workflow_refactoring_service = WorkflowRefactoringService()
