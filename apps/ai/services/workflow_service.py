from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
import json
import logging
import requests
from apps.ai.models import (
    AIWorkflow, WorkflowNode, WorkflowConnection
)
from apps.ai.services.ai_analysis_service import AIAnalysisService
from apps.ai.processors import get_processor_for_node_type, validate_node_config, get_all_node_types, generate_config_form

logger = logging.getLogger(__name__)

class WorkflowService:
    """工作流服务类，提供工作流相关的业务逻辑处理"""
    
    def __init__(self):
        self.ai_service = AIAnalysisService()
    
    @transaction.atomic
    def create_workflow(self, name=None, description='', owner=None, workflow_data=None):
        """
        创建新的工作流
        
        Args:
            name: 工作流名称
            description: 工作流描述
            owner: 创建用户
            workflow_data: 工作流数据字典（用于兼容旧的调用方式）
            
        Returns:
            AIWorkflow: 创建的工作流实例
        """
        # 兼容旧的调用方式
        if workflow_data is not None and owner is None:
            owner = workflow_data.get('user')
            name = workflow_data.get('name')
            description = workflow_data.get('description', '')
        try:
            # 验证数据
            if not name:
                raise ValidationError('工作流名称不能为空')
            
            # 创建工作流
            workflow = AIWorkflow.objects.create(
                name=name,
                description=description,
                owner=owner,
                is_public=(workflow_data.get('is_public', False) if workflow_data else False),
                created_at=timezone.now(),
                updated_at=timezone.now()
            )
            
            # 添加协作者（如果有）
            if workflow_data and 'collaborators' in workflow_data:
                collaborators = workflow_data.get('collaborators', [])
                if collaborators:
                    workflow.collaborators.add(*collaborators)
            
            # 创建默认变量（如果有）
            if workflow_data and 'variables' in workflow_data:
                variables = workflow_data.get('variables', [])
                for var_data in variables:
                    WorkflowVariable.objects.create(
                        workflow=workflow,
                        name=var_data['name'],
                        data_type=var_data['data_type'],
                        default_value=var_data.get('default_value'),
                        description=var_data.get('description', ''),
                        is_required=var_data.get('is_required', False)
                    )
            
            # 创建默认节点（开始节点和结束节点）
            start_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_type='data_input',
                name='开始',
                position_x=100,
                position_y=200,
                config={
                    'trigger_type': 'manual',
                    'input_config': {
                        'input_type': 'json',
                        'output_variable': 'input_data'
                    }
                }
            )
            
            end_node = WorkflowNode.objects.create(
                workflow=workflow,
                node_type='data_output',
                name='结束',
                position_x=500,
                position_y=200,
                config={
                    'result_type': 'success',
                    'output_data': {},
                    'save_result': True
                }
            )
            
            # 创建默认连接
            WorkflowConnection.objects.create(
                workflow=workflow,
                source_node=start_node,
                target_node=end_node
            )
            
            logger.info(f'创建工作流成功: {workflow.name}, ID: {workflow.id}')
            return workflow
            
        except Exception as e:
            logger.error(f'创建工作流失败: {str(e)}')
            raise
    
    @transaction.atomic
    def update_workflow(self, workflow_id, workflow_data):
        """
        更新工作流信息
        
        Args:
            workflow_id: 工作流ID
            workflow_data: 更新的工作流数据
            
        Returns:
            AIWorkflow: 更新后的工作流实例
        """
        try:
            workflow = AIWorkflow.objects.get(id=workflow_id)
            
            # 更新基本信息
            if 'name' in workflow_data:
                workflow.name = workflow_data['name']
            if 'description' in workflow_data:
                workflow.description = workflow_data['description']
            if 'status' in workflow_data:
                workflow.status = workflow_data['status']
            if 'is_public' in workflow_data:
                workflow.is_public = workflow_data['is_public']
                
            workflow.save()
            
            # 更新协作者
            if 'collaborators' in workflow_data:
                workflow.collaborators.clear()
                workflow.collaborators.add(*workflow_data['collaborators'])
            
            logger.info(f'更新工作流成功: {workflow.name}, ID: {workflow.id}')
            return workflow
            
        except AIWorkflow.DoesNotExist:
            logger.error(f'工作流不存在: {workflow_id}')
            raise ValidationError('工作流不存在')
        except Exception as e:
            logger.error(f'更新工作流失败: {str(e)}')
            raise
    
    @transaction.atomic
    def update_workflow_nodes(self, workflow_id, nodes_data, connections_data):
        """
        更新工作流节点和连接
        
        Args:
            workflow_id: 工作流ID
            nodes_data: 节点数据列表
            connections_data: 连接数据列表
            
        Returns:
            AIWorkflow: 更新后的工作流实例
        """
        try:
            workflow = AIWorkflow.objects.get(id=workflow_id)
            
            # 获取现有的节点和连接
            existing_node_ids = set(WorkflowNode.objects.filter(workflow=workflow).values_list('id', flat=True))
            node_ids_to_keep = set()
            
            # 更新或创建节点
            for node_data in nodes_data:
                node_id = node_data.get('id')
                
                if node_id and str(node_id) in map(str, existing_node_ids):
                    # 更新现有节点
                    node = WorkflowNode.objects.get(id=node_id)
                    node.name = node_data.get('name', node.name)
                    node.description = node_data.get('description', node.description)
                    node.position_x = node_data.get('position_x', node.position_x)
                    node.position_y = node_data.get('position_y', node.position_y)
                    node.config = node_data.get('config', node.config)
                    node.is_active = node_data.get('is_active', node.is_active)
                    node.save()
                    node_ids_to_keep.add(str(node.id))
                else:
                    # 创建新节点
                    node_type_code = node_data['node_type']
                    node = WorkflowNode.objects.create(
                        workflow=workflow,
                        node_type=node_type_code,
                        name=node_data.get('name', f'节点 {node_type_code}'),
                        description=node_data.get('description', ''),
                        position_x=node_data.get('position_x', 0),
                        position_y=node_data.get('position_y', 0),
                        config=node_data.get('config', {})
                    )
                    
                    node_ids_to_keep.add(str(node.id))
            
            # 删除不存在的节点
            nodes_to_delete = list(existing_node_ids - set(map(lambda x: uuid.UUID(x), node_ids_to_keep)))
            if nodes_to_delete:
                WorkflowNode.objects.filter(id__in=nodes_to_delete).delete()
            
            # 删除所有现有连接
            WorkflowConnection.objects.filter(workflow=workflow).delete()
            
            # 创建新连接
            for conn_data in connections_data:
                source_node = WorkflowNode.objects.get(id=conn_data['source_node_id'])
                target_node = WorkflowNode.objects.get(id=conn_data['target_node_id'])
                
                WorkflowConnection.objects.create(
                    workflow=workflow,
                    source_node=source_node,
                    target_node=target_node,
                    source_handle=conn_data.get('source_handle'),
                    target_handle=conn_data.get('target_handle'),
                    condition=conn_data.get('condition')
                )
            
            logger.info(f'更新工作流节点和连接成功: {workflow.name}, ID: {workflow.id}')
            return workflow
            
        except AIWorkflow.DoesNotExist:
            logger.error(f'工作流不存在: {workflow_id}')
            raise ValidationError('工作流不存在')
        except Exception as e:
            logger.error(f'更新工作流节点失败: {str(e)}')
            raise
    
    def get_workflow(self, workflow_id):
        """
        获取工作流详情
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            dict: 工作流详情字典
        """
        try:
            workflow = AIWorkflow.objects.get(id=workflow_id)
            
            # 获取所有相关数据
            nodes = list(workflow.nodes.all().values(
                'id', 'node_type_id', 'node_type__name', 'name', 'description',
                'position_x', 'position_y', 'config', 'is_active'
            ))
            
            connections = list(workflow.connections.all().values(
                'id', 'source_node_id', 'target_node_id', 'source_handle',
                'target_handle', 'condition'
            ))
            
            variables = list(workflow.variables.all().values(
                'id', 'name', 'data_type', 'default_value', 'description', 'is_required'
            ))
            
            data_access_configs = list(workflow.data_access_configs.all().values(
                'id', 'access_type', 'resource_name', 'resource_identifier',
                'operations', 'filters'
            ))
            
            return {
                'id': str(workflow.id),
                'name': workflow.name,
                'description': workflow.description,
                'owner': workflow.owner.id,
                'status': workflow.status,
                'is_public': workflow.is_public,
                'collaborators': list(workflow.collaborators.values_list('id', flat=True)),
                'nodes': nodes,
                'connections': connections,
                'variables': variables,
                'data_access_configs': data_access_configs,
                'created_at': workflow.created_at,
                'updated_at': workflow.updated_at
            }
            
        except AIWorkflow.DoesNotExist:
            logger.error(f'工作流不存在: {workflow_id}')
            raise ValidationError('工作流不存在')
        except Exception as e:
            logger.error(f'获取工作流失败: {str(e)}')
            raise
    
    @transaction.atomic
    def execute_workflow(self, workflow_id, user, input_data=None):
        """
        执行工作流
        
        Args:
            workflow_id: 工作流ID
            user: 执行用户
            input_data: 输入数据
            
        Returns:
            WorkflowExecution: 执行实例
        """
        try:
            workflow = AIWorkflow.objects.get(id=workflow_id)
            
            # 验证工作流状态
            if workflow.status != 'published':
                raise ValidationError('只能执行已发布的工作流')
            
            # 创建执行实例
            execution = WorkflowExecution.objects.create(
                workflow=workflow,
                created_by=user,
                input_data=input_data or {}
            )
            
            # 启动执行
            execution.status = 'running'
            execution.started_at = timezone.now()
            execution.save()
            
            # 异步执行工作流
            self._execute_workflow_async(execution.id)
            
            return execution
            
        except AIWorkflow.DoesNotExist:
            logger.error(f'工作流不存在: {workflow_id}')
            raise ValidationError('工作流不存在')
        except Exception as e:
            logger.error(f'执行工作流失败: {str(e)}')
            # 更新执行状态为失败
            if 'execution' in locals():
                execution.status = 'failed'
                execution.error_message = str(e)
                execution.completed_at = timezone.now()
                execution.save()
            raise
    
    def _execute_workflow_async(self, execution_id):
        """
        异步执行工作流逻辑
        
        Args:
            execution_id: 执行实例ID
        """
        try:
            execution = WorkflowExecution.objects.select_related('workflow').get(id=execution_id)
            workflow = execution.workflow
            
            # 获取所有节点和连接
            nodes = {str(node.id): node for node in workflow.nodes.all()}
            connections = list(workflow.connections.all())
            
            # 构建执行图
            execution_graph = self._build_execution_graph(nodes, connections)
            
            # 查找开始节点
            start_node = next((node for node in nodes.values() if node.node_type.code == 'start'), None)
            if not start_node:
                raise ValueError('工作流中找不到开始节点')
            
            # 初始化执行上下文
            context = execution.input_data.copy()
            
            # 递归执行节点
            self._execute_node(start_node, execution, execution_graph, context, nodes)
            
            # 更新执行状态为完成
            execution.status = 'completed'
            execution.output_data = context
            execution.completed_at = timezone.now()
            execution.save()
            
        except Exception as e:
            logger.error(f'异步执行工作流失败: {str(e)}')
            execution = WorkflowExecution.objects.get(id=execution_id)
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.completed_at = timezone.now()
            execution.save()
    
    def _execute_node(self, node, execution, execution_graph, context, nodes):
        """
        执行单个节点
        
        Args:
            node: 要执行的节点
            execution: 执行实例
            execution_graph: 执行图
            context: 执行上下文
            nodes: 所有节点的字典
        """
        # 创建节点执行记录
        node_execution = NodeExecution.objects.create(
            workflow_execution=execution,
            node=node,
            input_data=context.copy()
        )
        
        # 执行节点逻辑
        self._execute_node_logic(node, node_execution, context)
    
    def get_processor_for_node_type(self, node_type_code):
        """
        获取指定节点类型的处理器
        
        Args:
            node_type_code: 节点类型代码
            
        Returns:
            BaseNodeProcessor: 节点处理器实例
        """
        return get_processor_for_node_type(node_type_code)
    
    def validate_node_configuration(self, node_type_code, config_data):
        """
        验证节点配置数据
        
        Args:
            node_type_code: 节点类型代码
            config_data: 配置数据
            
        Returns:
            tuple: (是否有效, 错误消息)
        """
        return validate_node_config(node_type_code, config_data)
    
    def get_all_supported_node_types(self):
        """
        获取所有支持的节点类型
        
        Returns:
            list: 节点类型列表
        """
        return get_all_node_types()
    
    def generate_node_config_form(self, node_type_code):
        """
        生成节点配置表单
        
        Args:
            node_type_code: 节点类型代码
            
        Returns:
            dict: 配置表单定义
        """
        return generate_config_form(node_type_code)
    
    def _execute_node_logic(self, node, context):
        """
        根据节点类型执行对应的逻辑
        
        Args:
            node: 节点实例
            context: 执行上下文
            
        Returns:
            dict: 执行结果
        """
        node_type = node.node_type.code
        config = node.config
        
        # 使用新的处理器系统
        processor = get_processor_for_node_type(node_type)
        if processor:
            try:
                # 验证配置
                validation_result = validate_node_config(node_type, config)
                if not validation_result.get('valid', False):
                    logger.warning(f"节点配置验证失败: {validation_result.get('errors', [])}")
                
                # 执行节点逻辑
                return processor.execute(config, context)
            except Exception as e:
                logger.error(f"节点处理器执行失败: {str(e)}")
                return {
                    'success': False,
                    'error': str(e),
                    'node_type': node_type
                }
        else:
            # 回退到旧的执行逻辑
            logger.warning(f"未找到节点类型 {node_type} 的处理器，使用旧逻辑")
            return self._execute_node_logic_legacy(node, context)
    
    def _execute_node_logic_legacy(self, node, context):
        """
        旧的节点执行逻辑（回退方案）
        
        Args:
            node: 节点实例
            context: 执行上下文
            
        Returns:
            dict: 执行结果
        """
        node_type = node.node_type.code
        config = node.config
        output = {}
        
        if node_type == 'start':
            # 开始节点，直接返回上下文
            output = context.copy()
            
        elif node_type == 'end':
            # 结束节点，返回上下文
            output = context.copy()
            
        elif node_type == 'ai_model':
            # AI模型节点
            model_name = config.get('model_name', 'gpt-3.5-turbo')
            prompt = config.get('prompt', '')
            
            # 替换提示中的变量
            for key, value in context.items():
                prompt = prompt.replace(f'{{{{{key}}}}}', str(value))
            
            # 调用AI服务
            result = self.ai_service.generate_content(prompt, model_name)
            output['ai_result'] = result
            
        elif node_type == 'condition':
            # 条件节点
            condition_type = config.get('condition_type', 'if_else')
            condition_variable = config.get('condition_variable')
            
            if condition_variable in context:
                output[f'{condition_variable}_result'] = context[condition_variable]
            
        elif node_type == 'api_call':
            # API调用节点
            output = self._execute_api_call(config, context)
            
        elif node_type == 'data_input':
            # 数据输入节点
            output = self._execute_data_input(config, context)
            
        elif node_type == 'data_output':
            # 数据输出节点
            output = self._execute_data_output(config, context)
                
        elif node_type == 'database_query':
            # 数据库查询节点
            output = self._execute_database_query(config, context)
            
        elif node_type == 'file_operation':
            # 文件操作节点
            output = self._execute_file_operation(config, context)
            
        elif node_type == 'data_transformation':
            # 数据转换节点
            output = self._execute_data_transformation(config, context)
            
        elif node_type == 'text_processing':
            # 文本处理节点
            output = self._execute_text_processing(config, context)
            
        elif node_type == 'wait':
            # 等待节点
            output = self._execute_wait(config, context)
            
        elif node_type == 'parallel':
            # 并行处理节点
            output = self._execute_parallel(config, context)
            
        elif node_type == 'loop':
            # 循环节点
            output = self._execute_loop(config, context)
            
        elif node_type == 'multi_condition':
            # 多条件分支节点
            output = self._execute_multi_condition(config, context)
            
        elif node_type == 'ai_generation':
            # AI生成节点
            output = self._execute_ai_generation(config, context)
            
        elif node_type == 'ai_classification':
            # AI分类节点
            output = self._execute_ai_classification(config, context)
            
        elif node_type == 'ai_extraction':
            # AI信息提取节点
            output = self._execute_ai_extraction(config, context)
                
        return output
    
    def _build_execution_graph(self, nodes, connections):
        """
        构建执行图
        
        Args:
            nodes: 节点字典
            connections: 连接列表
            
        Returns:
            dict: 执行图，键为节点ID，值为(目标节点ID, 条件)列表
        """
        graph = {}
        
        for conn in connections:
            source_id = str(conn.source_node.id)
            target_id = str(conn.target_node.id)
            
            if source_id not in graph:
                graph[source_id] = []
                
            graph[source_id].append((target_id, conn.condition))
            
        return graph
    
    def _execute_database_query(self, config, context):
        """
        执行数据库查询节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 查询结果
        """
        output = {}
        
        try:
            # 获取配置参数
            database_type = config.get('database_type', 'mysql')
            connection_name = config.get('connection_name', 'default')
            query_type = config.get('query_type', 'select')
            sql_query = config.get('sql_query', '')
            
            # 替换SQL中的变量
            for key, value in context.items():
                sql_query = sql_query.replace(f'{{{{{key}}}}}', str(value))
            
            # 根据数据库类型执行查询
            if database_type == 'mysql':
                # 使用Django ORM或原生SQL执行查询
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(sql_query)
                    if query_type.lower() == 'select':
                        columns = [col[0] for col in cursor.description]
                        rows = cursor.fetchall()
                        output['query_result'] = [dict(zip(columns, row)) for row in rows]
                    else:
                        output['affected_rows'] = cursor.rowcount
            
            # 添加查询统计信息
            output['query_success'] = True
            output['query_type'] = query_type
            
        except Exception as e:
            logger.error(f'数据库查询失败: {str(e)}')
            output['query_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_file_operation(self, config, context):
        """
        执行文件操作节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 操作结果
        """
        output = {}
        
        try:
            # 获取配置参数
            operation_type = config.get('operation_type', 'read')
            file_path = config.get('file_path', '')
            target_path = config.get('target_path', '')
            file_content = config.get('file_content', '')
            encoding = config.get('encoding', 'utf-8')
            
            # 替换路径中的变量
            for key, value in context.items():
                file_path = file_path.replace(f'{{{{{key}}}}}', str(value))
                target_path = target_path.replace(f'{{{{{key}}}}}', str(value))
                file_content = file_content.replace(f'{{{{{key}}}}}', str(value))
            
            # 根据操作类型执行文件操作
            if operation_type == 'read':
                # 读取文件
                with open(file_path, 'r', encoding=encoding) as f:
                    output['file_content'] = f.read()
                    output['file_size'] = len(output['file_content'])
                    
            elif operation_type == 'write':
                # 写入文件
                with open(file_path, 'w', encoding=encoding) as f:
                    f.write(file_content)
                output['write_success'] = True
                output['file_path'] = file_path
                
            elif operation_type == 'append':
                # 追加内容到文件
                with open(file_path, 'a', encoding=encoding) as f:
                    f.write(file_content)
                output['append_success'] = True
                output['file_path'] = file_path
                
            elif operation_type == 'copy':
                # 复制文件
                import shutil
                shutil.copy2(file_path, target_path)
                output['copy_success'] = True
                output['source_path'] = file_path
                output['target_path'] = target_path
                
            elif operation_type == 'move':
                # 移动文件
                import shutil
                shutil.move(file_path, target_path)
                output['move_success'] = True
                output['source_path'] = file_path
                output['target_path'] = target_path
                
            elif operation_type == 'delete':
                # 删除文件
                import os
                if os.path.exists(file_path):
                    os.remove(file_path)
                    output['delete_success'] = True
                else:
                    output['delete_success'] = False
                    output['error_message'] = '文件不存在'
                
            elif operation_type == 'upload':
                # 文件上传（需要结合前端实现）
                output['upload_success'] = True
                output['uploaded_file'] = file_path
                
            elif operation_type == 'download':
                # 文件下载（需要结合前端实现）
                output['download_success'] = True
                output['download_path'] = file_path
                
            elif operation_type == 'list':
                # 列出目录内容
                import os
                if os.path.isdir(file_path):
                    files = os.listdir(file_path)
                    output['file_list'] = files
                    output['file_count'] = len(files)
                else:
                    output['error_message'] = '路径不是目录'
            
            # 添加操作统计信息
            output['operation_type'] = operation_type
            output['operation_success'] = True
            
        except Exception as e:
            logger.error(f'文件操作失败: {str(e)}')
            output['operation_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_api_call(self, config, context):
        """
        执行API调用节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: API调用结果
        """
        output = {}
        
        try:
            # 获取配置参数
            url = config.get('url', '')
            method = config.get('method', 'GET')
            headers = config.get('headers', {})
            body = config.get('body', '')
            params = config.get('params', {})
            timeout = config.get('timeout', 30)
            auth_type = config.get('auth_type', 'none')
            auth_config = config.get('auth_config', {})
            
            # 替换URL、body、params中的变量
            for key, value in context.items():
                url = url.replace(f'{{{{{key}}}}}', str(value))
                
                # 处理body中的变量（仅当body是字符串时）
                if isinstance(body, str):
                    body = body.replace(f'{{{{{key}}}}}', str(value))
                
                # 处理params中的变量
                if isinstance(params, dict):
                    for param_key, param_value in params.items():
                        if isinstance(param_value, str):
                            params[param_key] = param_value.replace(f'{{{{{key}}}}}', str(value))
            
            # 处理认证配置
            auth = None
            if auth_type == 'basic':
                username = auth_config.get('username', '')
                password = auth_config.get('password', '')
                auth = (username, password)
            elif auth_type == 'bearer':
                token = auth_config.get('token', '')
                headers['Authorization'] = f'Bearer {token}'
            elif auth_type == 'api_key':
                api_key = auth_config.get('api_key', '')
                key_location = auth_config.get('key_location', 'header')
                key_name = auth_config.get('key_name', 'X-API-Key')
                
                if key_location == 'header':
                    headers[key_name] = api_key
                elif key_location == 'query':
                    params[key_name] = api_key
            
            # 准备请求参数
            request_kwargs = {
                'headers': headers,
                'timeout': timeout
            }
            
            if params:
                request_kwargs['params'] = params
            
            if auth:
                request_kwargs['auth'] = auth
            
            # 根据方法类型执行请求
            if method.upper() == 'GET':
                response = requests.get(url, **request_kwargs)
            elif method.upper() == 'POST':
                request_kwargs['data'] = body
                response = requests.post(url, **request_kwargs)
            elif method.upper() == 'PUT':
                request_kwargs['data'] = body
                response = requests.put(url, **request_kwargs)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, **request_kwargs)
            elif method.upper() == 'PATCH':
                request_kwargs['data'] = body
                response = requests.patch(url, **request_kwargs)
            else:
                request_kwargs['data'] = body
                response = requests.request(method, url, **request_kwargs)
            
            # 处理响应
            output['status_code'] = response.status_code
            output['response_headers'] = dict(response.headers)
            output['response_time'] = response.elapsed.total_seconds()
            
            # 尝试解析响应体
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                try:
                    output['response_body'] = response.json()
                except:
                    output['response_body'] = response.text
            elif 'application/xml' in content_type or 'text/xml' in content_type:
                output['response_body'] = response.text
            else:
                output['response_body'] = response.text
            
            # 判断请求是否成功
            output['api_call_success'] = response.status_code < 400
            
            # 添加详细的响应信息
            output['request_url'] = url
            output['request_method'] = method
            output['request_headers'] = headers
            
            if response.status_code >= 400:
                output['error_message'] = f'HTTP错误: {response.status_code}'
            
        except requests.exceptions.Timeout:
            logger.error('API调用超时')
            output['api_call_success'] = False
            output['error_message'] = '请求超时'
        except requests.exceptions.ConnectionError:
            logger.error('API连接错误')
            output['api_call_success'] = False
            output['error_message'] = '连接错误'
        except Exception as e:
            logger.error(f'API调用失败: {str(e)}')
            output['api_call_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_data_transformation(self, config, context):
        """
        执行数据转换节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 转换结果
        """
        output = {}
        
        try:
            # 获取配置参数
            transformation_type = config.get('transformation_type', 'json_to_csv')
            input_data = config.get('input_data', '')
            
            # 从上下文中获取输入数据
            if not input_data and 'input' in context:
                input_data = context['input']
            
            # 根据转换类型执行转换
            if transformation_type == 'json_to_csv':
                # JSON转CSV
                import json
                import csv
                from io import StringIO
                
                if isinstance(input_data, str):
                    data = json.loads(input_data)
                else:
                    data = input_data
                
                if isinstance(data, list) and len(data) > 0:
                    # 获取所有字段
                    fieldnames = set()
                    for item in data:
                        if isinstance(item, dict):
                            fieldnames.update(item.keys())
                    
                    # 转换为CSV
                    output_csv = StringIO()
                    writer = csv.DictWriter(output_csv, fieldnames=sorted(fieldnames))
                    writer.writeheader()
                    for item in data:
                        writer.writerow(item)
                    
                    output['csv_content'] = output_csv.getvalue()
                    output['row_count'] = len(data)
                    
            elif transformation_type == 'csv_to_json':
                # CSV转JSON
                import csv
                import json
                from io import StringIO
                
                if isinstance(input_data, str):
                    csv_data = StringIO(input_data)
                    reader = csv.DictReader(csv_data)
                    data = list(reader)
                    output['json_data'] = json.dumps(data, ensure_ascii=False)
                    output['row_count'] = len(data)
                    
            elif transformation_type == 'xml_to_json':
                # XML转JSON
                import xml.etree.ElementTree as ET
                import json
                
                def xml_to_dict(element):
                    result = {}
                    for child in element:
                        if len(child) == 0:
                            result[child.tag] = child.text
                        else:
                            result[child.tag] = xml_to_dict(child)
                    return result
                
                root = ET.fromstring(input_data)
                json_data = xml_to_dict(root)
                output['json_data'] = json.dumps(json_data, ensure_ascii=False)
                
            elif transformation_type == 'json_to_xml':
                # JSON转XML
                import json
                import xml.etree.ElementTree as ET
                
                def dict_to_xml(tag, d):
                    elem = ET.Element(tag)
                    for key, val in d.items():
                        child = ET.Element(key)
                        child.text = str(val)
                        elem.append(child)
                    return elem
                
                if isinstance(input_data, str):
                    data = json.loads(input_data)
                else:
                    data = input_data
                    
                root = dict_to_xml('root', data)
                output['xml_content'] = ET.tostring(root, encoding='unicode')
                
            elif transformation_type == 'yaml_to_json':
                # YAML转JSON
                import yaml
                import json
                
                data = yaml.safe_load(input_data)
                output['json_data'] = json.dumps(data, ensure_ascii=False)
                
            elif transformation_type == 'json_to_yaml':
                # JSON转YAML
                import json
                import yaml
                
                if isinstance(input_data, str):
                    data = json.loads(input_data)
                else:
                    data = input_data
                    
                output['yaml_content'] = yaml.dump(data, allow_unicode=True)
                
            elif transformation_type == 'data_filter':
                # 数据过滤
                import json
                
                if isinstance(input_data, str):
                    data = json.loads(input_data)
                else:
                    data = input_data
                    
                filter_condition = config.get('filter_condition', '')
                
                if isinstance(data, list):
                    filtered_data = []
                    for item in data:
                        try:
                            if eval(filter_condition, {}, item):
                                filtered_data.append(item)
                        except:
                            continue
                    output['filtered_data'] = filtered_data
                    output['original_count'] = len(data)
                    output['filtered_count'] = len(filtered_data)
                    
            elif transformation_type == 'data_sort':
                # 数据排序
                import json
                
                if isinstance(input_data, str):
                    data = json.loads(input_data)
                else:
                    data = input_data
                    
                sort_key = config.get('sort_key', '')
                sort_order = config.get('sort_order', 'asc')
                
                if isinstance(data, list) and sort_key:
                    reverse = sort_order.lower() == 'desc'
                    sorted_data = sorted(data, key=lambda x: x.get(sort_key, ''), reverse=reverse)
                    output['sorted_data'] = sorted_data
                    
            elif transformation_type == 'data_aggregate':
                # 数据聚合
                import json
                
                if isinstance(input_data, str):
                    data = json.loads(input_data)
                else:
                    data = input_data
                    
                group_by = config.get('group_by', '')
                aggregate_field = config.get('aggregate_field', '')
                aggregate_type = config.get('aggregate_type', 'count')
                
                if isinstance(data, list) and group_by:
                    grouped_data = {}
                    for item in data:
                        group_key = item.get(group_by, '')
                        if group_key not in grouped_data:
                            grouped_data[group_key] = []
                        grouped_data[group_key].append(item)
                    
                    aggregated_data = {}
                    for key, group in grouped_data.items():
                        if aggregate_type == 'count':
                            aggregated_data[key] = len(group)
                        elif aggregate_type == 'sum' and aggregate_field:
                            aggregated_data[key] = sum(float(item.get(aggregate_field, 0)) for item in group)
                        elif aggregate_type == 'avg' and aggregate_field:
                            values = [float(item.get(aggregate_field, 0)) for item in group]
                            aggregated_data[key] = sum(values) / len(values) if values else 0
                        elif aggregate_type == 'max' and aggregate_field:
                            aggregated_data[key] = max(float(item.get(aggregate_field, 0)) for item in group)
                        elif aggregate_type == 'min' and aggregate_field:
                            aggregated_data[key] = min(float(item.get(aggregate_field, 0)) for item in group)
                    
                    output['aggregated_data'] = aggregated_data
            
            output['transformation_success'] = True
            
        except Exception as e:
            logger.error(f'数据转换失败: {str(e)}')
            output['transformation_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_text_processing(self, config, context):
        """
        执行文本处理节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 处理结果
        """
        output = {}
        
        try:
            # 获取配置参数
            operation = config.get('operation', 'trim')
            input_text = config.get('input_text', '')
            
            # 从上下文中获取输入文本
            if not input_text and 'text' in context:
                input_text = context['text']
            
            # 根据操作类型执行文本处理
            if operation == 'trim':
                output['processed_text'] = input_text.strip()
            elif operation == 'lowercase':
                output['processed_text'] = input_text.lower()
            elif operation == 'uppercase':
                output['processed_text'] = input_text.upper()
            elif operation == 'replace':
                old_str = config.get('old_string', '')
                new_str = config.get('new_string', '')
                output['processed_text'] = input_text.replace(old_str, new_str)
            elif operation == 'split':
                separator = config.get('separator', ',')
                output['split_result'] = input_text.split(separator)
            elif operation == 'join':
                separator = config.get('separator', ',')
                if isinstance(input_text, list):
                    output['joined_text'] = separator.join(input_text)
                else:
                    output['joined_text'] = input_text
            
            output['text_processing_success'] = True
            
        except Exception as e:
            logger.error(f'文本处理失败: {str(e)}')
            output['text_processing_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_data_input(self, config, context):
        """
        执行数据输入节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 输入结果
        """
        output = {}
        
        try:
            # 获取配置参数
            data_source = config.get('data_source', 'manual')
            input_data = config.get('input_data', '')
            
            # 根据数据源类型获取数据
            if data_source == 'manual':
                # 手动输入数据
                output['input_data'] = input_data
                
            elif data_source == 'file':
                # 从文件读取数据
                file_path = config.get('file_path', '')
                encoding = config.get('encoding', 'utf-8')
                
                # 替换路径中的变量
                for key, value in context.items():
                    file_path = file_path.replace(f'{{{{{key}}}}}', str(value))
                
                with open(file_path, 'r', encoding=encoding) as f:
                    output['file_content'] = f.read()
                    
            elif data_source == 'api':
                # 从API获取数据
                url = config.get('api_url', '')
                method = config.get('api_method', 'GET')
                
                # 替换URL中的变量
                for key, value in context.items():
                    url = url.replace(f'{{{{{key}}}}}', str(value))
                
                import requests
                response = requests.request(method, url)
                output['api_response'] = response.text
            
            output['data_input_success'] = True
            
        except Exception as e:
            logger.error(f'数据输入失败: {str(e)}')
            output['data_input_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_data_output(self, config, context):
        """
        执行数据输出节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 输出结果
        """
        output = {}
        
        try:
            # 获取配置参数
            output_type = config.get('output_type', 'variable')
            output_variable = config.get('output_variable', '')
            
            if output_type == 'variable' and output_variable:
                # 输出到变量
                if output_variable in context:
                    output['output'] = context[output_variable]
                else:
                    output['output'] = None
                    
            elif output_type == 'file':
                # 输出到文件
                file_path = config.get('file_path', '')
                content = config.get('content', '')
                encoding = config.get('encoding', 'utf-8')
                file_mode = config.get('file_mode', 'w')  # w: 覆盖, a: 追加
                
                # 替换路径和内容中的变量
                for key, value in context.items():
                    file_path = file_path.replace(f'{{{{{key}}}}}', str(value))
                    content = content.replace(f'{{{{{key}}}}}', str(value))
                
                # 确保目录存在
                import os
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, file_mode, encoding=encoding) as f:
                    f.write(content)
                    
                output['file_output_success'] = True
                output['file_path'] = file_path
                output['file_size'] = len(content)
                
            elif output_type == 'api':
                # 输出到API
                url = config.get('api_url', '')
                method = config.get('api_method', 'POST')
                data = config.get('api_data', '')
                headers = config.get('headers', {})
                
                # 替换URL、数据和请求头中的变量
                for key, value in context.items():
                    url = url.replace(f'{{{{{key}}}}}', str(value))
                    data = data.replace(f'{{{{{key}}}}}', str(value))
                    headers = {k: v.replace(f'{{{{{key}}}}}', str(value)) for k, v in headers.items()}
                
                import requests
                import json
                
                # 处理JSON数据
                if headers.get('Content-Type') == 'application/json' and isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except:
                        pass
                
                response = requests.request(method, url, data=data, headers=headers, timeout=30)
                output['api_response'] = response.text
                output['api_status_code'] = response.status_code
                output['api_response_time'] = response.elapsed.total_seconds()
                
            elif output_type == 'database':
                # 输出到数据库
                db_type = config.get('db_type', 'mysql')
                table_name = config.get('table_name', '')
                data_to_insert = config.get('data', '')
                
                # 替换变量
                for key, value in context.items():
                    table_name = table_name.replace(f'{{{{{key}}}}}', str(value))
                    data_to_insert = data_to_insert.replace(f'{{{{{key}}}}}', str(value))
                
                import json
                
                if isinstance(data_to_insert, str):
                    try:
                        data_to_insert = json.loads(data_to_insert)
                    except:
                        pass
                
                # 这里需要根据数据库类型实现具体的插入逻辑
                # 目前先返回配置信息
                output['database_output'] = {
                    'db_type': db_type,
                    'table_name': table_name,
                    'data': data_to_insert
                }
                
            elif output_type == 'email':
                # 输出到邮件
                smtp_server = config.get('smtp_server', '')
                smtp_port = config.get('smtp_port', 587)
                username = config.get('username', '')
                password = config.get('password', '')
                to_email = config.get('to_email', '')
                subject = config.get('subject', '')
                body = config.get('body', '')
                
                # 替换变量
                for key, value in context.items():
                    to_email = to_email.replace(f'{{{{{key}}}}}', str(value))
                    subject = subject.replace(f'{{{{{key}}}}}', str(value))
                    body = body.replace(f'{{{{{key}}}}}', str(value))
                
                # 这里需要实现邮件发送逻辑
                # 目前先返回配置信息
                output['email_output'] = {
                    'to_email': to_email,
                    'subject': subject,
                    'body_preview': body[:100] + '...' if len(body) > 100 else body
                }
                
            elif output_type == 'notification':
                # 输出到通知
                notification_type = config.get('notification_type', 'webhook')
                webhook_url = config.get('webhook_url', '')
                message = config.get('message', '')
                
                # 替换变量
                for key, value in context.items():
                    webhook_url = webhook_url.replace(f'{{{{{key}}}}}', str(value))
                    message = message.replace(f'{{{{{key}}}}}', str(value))
                
                if notification_type == 'webhook':
                    import requests
                    response = requests.post(webhook_url, json={'message': message})
                    output['notification_response'] = response.text
                    output['notification_status'] = response.status_code
                
            elif output_type == 'log':
                # 输出到日志
                log_level = config.get('log_level', 'INFO')
                log_message = config.get('log_message', '')
                
                # 替换变量
                for key, value in context.items():
                    log_message = log_message.replace(f'{{{{{key}}}}}', str(value))
                
                # 记录日志
                if log_level == 'DEBUG':
                    logger.debug(log_message)
                elif log_level == 'INFO':
                    logger.info(log_message)
                elif log_level == 'WARNING':
                    logger.warning(log_message)
                elif log_level == 'ERROR':
                    logger.error(log_message)
                elif log_level == 'CRITICAL':
                    logger.critical(log_message)
                
                output['log_output'] = log_message
            
            output['data_output_success'] = True
            
        except Exception as e:
            logger.error(f'数据输出失败: {str(e)}')
            output['data_output_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_wait(self, config, context):
        """
        执行等待节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 等待结果
        """
        output = {}
        
        try:
            # 获取配置参数
            wait_type = config.get('wait_type', 'time')
            wait_duration = config.get('wait_duration', 0)
            
            if wait_type == 'time':
                # 时间等待
                import time
                time.sleep(wait_duration)
                output['wait_duration'] = wait_duration
                
            elif wait_type == 'condition':
                # 条件等待
                condition = config.get('condition', '')
                max_wait = config.get('max_wait', 60)
                
                import time
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    try:
                        should_continue = eval(condition, {}, context)
                        if should_continue:
                            break
                    except:
                        pass
                    time.sleep(1)
                
                output['condition_met'] = True
                output['actual_wait'] = time.time() - start_time
            
            output['wait_success'] = True
            
        except Exception as e:
            logger.error(f'等待节点执行失败: {str(e)}')
            output['wait_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_parallel(self, config, context):
        """
        执行并行处理节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 并行处理结果
        """
        output = {}
        
        try:
            # 获取配置参数
            parallel_tasks = config.get('parallel_tasks', [])
            max_workers = config.get('max_workers', 5)
            timeout = config.get('timeout', 300)
            
            # 导入并发处理库
            import concurrent.futures
            import time
            
            # 定义任务执行函数
            def execute_task(task_config, task_context):
                """执行单个并行任务"""
                try:
                    # 这里需要根据任务配置执行具体的节点逻辑
                    # 目前先模拟任务执行
                    task_type = task_config.get('type', 'api_call')
                    task_name = task_config.get('name', f'task_{int(time.time())}')
                    
                    # 模拟任务执行时间
                    execution_time = task_config.get('execution_time', 1)
                    time.sleep(execution_time)
                    
                    # 模拟任务结果
                    result = {
                        'task_name': task_name,
                        'task_type': task_type,
                        'status': 'completed',
                        'result': f'{task_type}_result_{int(time.time())}',
                        'execution_time': execution_time
                    }
                    
                    return result
                    
                except Exception as e:
                    return {
                        'task_name': task_config.get('name', 'unknown'),
                        'task_type': task_config.get('type', 'unknown'),
                        'status': 'failed',
                        'error': str(e),
                        'execution_time': 0
                    }
            
            # 使用线程池执行并行任务
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_task = {
                    executor.submit(execute_task, task, context.copy()): task 
                    for task in parallel_tasks
                }
                
                # 收集任务结果
                completed_tasks = []
                failed_tasks = []
                
                for future in concurrent.futures.as_completed(future_to_task, timeout=timeout):
                    task_config = future_to_task[future]
                    try:
                        task_result = future.result()
                        if task_result['status'] == 'completed':
                            completed_tasks.append(task_result)
                        else:
                            failed_tasks.append(task_result)
                    except concurrent.futures.TimeoutError:
                        failed_tasks.append({
                            'task_name': task_config.get('name', 'unknown'),
                            'task_type': task_config.get('type', 'unknown'),
                            'status': 'timeout',
                            'error': 'Task execution timeout',
                            'execution_time': timeout
                        })
                    except Exception as e:
                        failed_tasks.append({
                            'task_name': task_config.get('name', 'unknown'),
                            'task_type': task_config.get('type', 'unknown'),
                            'status': 'failed',
                            'error': str(e),
                            'execution_time': 0
                        })
            
            # 构建输出结果
            output['parallel_tasks'] = {
                'total_tasks': len(parallel_tasks),
                'completed_tasks': len(completed_tasks),
                'failed_tasks': len(failed_tasks),
                'completed': completed_tasks,
                'failed': failed_tasks
            }
            output['parallel_success'] = len(failed_tasks) == 0
            output['max_workers'] = max_workers
            output['timeout'] = timeout
            
        except Exception as e:
            logger.error(f'并行处理节点执行失败: {str(e)}')
            output['parallel_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_loop(self, config, context):
        """
        执行循环节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 循环结果
        """
        output = {}
        
        try:
            # 获取配置参数
            loop_type = config.get('loop_type', 'for')
            loop_variable = config.get('loop_variable', 'i')
            loop_condition = config.get('loop_condition', '')
            max_iterations = config.get('max_iterations', 10)
            
            if loop_type == 'for':
                # For循环
                start = config.get('start', 0)
                end = config.get('end', 10)
                step = config.get('step', 1)
                
                loop_results = []
                for i in range(start, end, step):
                    context[loop_variable] = i
                    loop_results.append(context.copy())
                    
                output['loop_results'] = loop_results
                output['iterations'] = len(loop_results)
                
            elif loop_type == 'while':
                # While循环
                loop_results = []
                iteration = 0
                
                while iteration < max_iterations:
                    try:
                        # 评估循环条件
                        should_continue = eval(loop_condition, {}, context)
                        if not should_continue:
                            break
                            
                        # 执行循环体逻辑
                        context[loop_variable] = iteration
                        loop_results.append(context.copy())
                        iteration += 1
                        
                    except Exception as e:
                        logger.warning(f'循环条件评估失败: {str(e)}')
                        break
                
                output['loop_results'] = loop_results
                output['iterations'] = len(loop_results)
                
            elif loop_type == 'foreach':
                # Foreach循环
                items = config.get('items', [])
                item_variable = config.get('item_variable', 'item')
                
                loop_results = []
                for index, item in enumerate(items):
                    context[item_variable] = item
                    context[f'{item_variable}_index'] = index
                    loop_results.append(context.copy())
                    
                output['loop_results'] = loop_results
                output['iterations'] = len(loop_results)
                
            output['loop_success'] = True
            output['loop_type'] = loop_type
            output['loop_variable'] = loop_variable
            
        except Exception as e:
            logger.error(f'循环节点执行失败: {str(e)}')
            output['loop_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_multi_condition(self, config, context):
        """
        执行多条件分支节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 条件分支结果
        """
        output = {}
        
        try:
            # 获取配置参数
            conditions = config.get('conditions', [])
            default_branch = config.get('default_branch', '')
            evaluation_mode = config.get('evaluation_mode', 'first_match')  # first_match, all_matches
            
            matched_branches = []
            condition_results = []
            
            for condition in conditions:
                condition_expression = condition.get('expression', '')
                branch_name = condition.get('branch', '')
                condition_description = condition.get('description', '')
                
                if condition_expression:
                    try:
                        # 替换表达式中的变量
                        for key, value in context.items():
                            if isinstance(value, (str, int, float, bool)):
                                condition_expression = condition_expression.replace(f'{{{{{key}}}}}', str(value))
                        
                        # 评估条件
                        condition_result = eval(condition_expression, {}, context)
                        condition_results.append({
                            'branch': branch_name,
                            'expression': condition_expression,
                            'description': condition_description,
                            'result': condition_result
                        })
                        
                        if condition_result:
                            matched_branches.append(branch_name)
                            
                            # 如果是first_match模式，找到第一个匹配就停止
                            if evaluation_mode == 'first_match':
                                break
                                
                    except Exception as e:
                        condition_results.append({
                            'branch': branch_name,
                            'expression': condition_expression,
                            'description': condition_description,
                            'result': False,
                            'error': str(e)
                        })
                        continue
            
            # 处理匹配结果
            if evaluation_mode == 'first_match':
                matched_branch = matched_branches[0] if matched_branches else None
            else:
                matched_branch = matched_branches if matched_branches else None
            
            # 如果没有匹配且设置了默认分支
            if not matched_branch and default_branch:
                matched_branch = default_branch
                output['used_default_branch'] = True
            
            output['matched_branch'] = matched_branch
            output['matched_branches'] = matched_branches
            output['condition_results'] = condition_results
            output['evaluation_mode'] = evaluation_mode
            output['total_conditions'] = len(conditions)
            output['matched_conditions'] = len(matched_branches)
            output['multi_condition_success'] = True
            
        except Exception as e:
            logger.error(f'多条件分支节点执行失败: {str(e)}')
            output['multi_condition_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_multi_condition(self, config, context):
        """
        执行多条件分支节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: 条件分支结果
        """
        output = {}
        
        try:
            # 获取配置参数
            conditions = config.get('conditions', [])
            default_branch = config.get('default_branch', '')
            evaluation_mode = config.get('evaluation_mode', 'first_match')  # first_match, all_matches
            
            matched_branches = []
            condition_results = []
            
            for condition in conditions:
                condition_expression = condition.get('expression', '')
                branch_name = condition.get('branch', '')
                condition_description = condition.get('description', '')
                
                if condition_expression:
                    try:
                        # 替换表达式中的变量
                        for key, value in context.items():
                            if isinstance(value, (str, int, float, bool)):
                                condition_expression = condition_expression.replace(f'{{{{{key}}}}}', str(value))
                        
                        # 评估条件
                        condition_result = eval(condition_expression, {}, context)
                        condition_results.append({
                            'branch': branch_name,
                            'expression': condition_expression,
                            'description': condition_description,
                            'result': condition_result
                        })
                        
                        if condition_result:
                            matched_branches.append(branch_name)
                            
                            # 如果是first_match模式，找到第一个匹配就停止
                            if evaluation_mode == 'first_match':
                                break
                                
                    except Exception as e:
                        condition_results.append({
                            'branch': branch_name,
                            'expression': condition_expression,
                            'description': condition_description,
                            'result': False,
                            'error': str(e)
                        })
                        continue
            
            # 处理匹配结果
            if evaluation_mode == 'first_match':
                matched_branch = matched_branches[0] if matched_branches else None
            else:
                matched_branch = matched_branches if matched_branches else None
            
            # 如果没有匹配且设置了默认分支
            if not matched_branch and default_branch:
                matched_branch = default_branch
                output['used_default_branch'] = True
            
            output['matched_branch'] = matched_branch
            output['matched_branches'] = matched_branches
            output['condition_results'] = condition_results
            output['evaluation_mode'] = evaluation_mode
            output['total_conditions'] = len(conditions)
            output['matched_conditions'] = len(matched_branches)
            output['multi_condition_success'] = True
            
        except Exception as e:
            logger.error(f'多条件分支节点执行失败: {str(e)}')
            output['multi_condition_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_ai_generation(self, config, context):
        """
        执行AI生成节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: AI生成结果
        """
        output = {}
        
        try:
            # 获取配置参数
            model_name = config.get('model_name', 'gpt-3.5-turbo')
            prompt_template = config.get('prompt_template', '')
            temperature = config.get('temperature', 0.7)
            max_tokens = config.get('max_tokens', 1000)
            top_p = config.get('top_p', 1.0)
            frequency_penalty = config.get('frequency_penalty', 0.0)
            presence_penalty = config.get('presence_penalty', 0.0)
            stop_sequences = config.get('stop_sequences', [])
            
            # 替换提示模板中的变量
            for key, value in context.items():
                prompt_template = prompt_template.replace(f'{{{{{key}}}}}', str(value))
            
            # 构建系统提示
            system_prompt = config.get('system_prompt', '')
            
            # 调用AI服务
            result = self.ai_service.generate_content(
                prompt_template, 
                model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                stop_sequences=stop_sequences,
                system_prompt=system_prompt
            )
            
            output['generated_content'] = result
            output['ai_generation_success'] = True
            output['model_used'] = model_name
            output['tokens_used'] = len(result.split())  # 简单估算
            
        except Exception as e:
            logger.error(f'AI生成节点执行失败: {str(e)}')
            output['ai_generation_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_ai_classification(self, config, context):
        """
        执行AI分类节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: AI分类结果
        """
        output = {}
        
        try:
            # 获取配置参数
            model_name = config.get('model_name', 'gpt-3.5-turbo')
            classification_type = config.get('classification_type', 'binary')
            input_text = config.get('input_text', '')
            categories = config.get('categories', [])
            confidence_threshold = config.get('confidence_threshold', 0.5)
            multi_label = config.get('multi_label', False)
            
            # 从上下文中获取输入文本
            if not input_text and 'text' in context:
                input_text = context['text']
            
            # 构建分类提示
            if multi_label:
                prompt = f"请对以下文本进行多标签分类，可用类别：{', '.join(categories)}。文本：{input_text}。请返回JSON格式结果，包含类别和置信度。"
            else:
                prompt = f"请对以下文本进行分类，分类类型为{classification_type}，可用类别：{', '.join(categories)}。文本：{input_text}。请返回JSON格式结果，包含类别和置信度。"
            
            # 调用AI服务
            result = self.ai_service.generate_content(prompt, model_name)
            
            # 解析分类结果
            try:
                import json
                classification_data = json.loads(result)
                output['classification_result'] = classification_data
                output['predicted_class'] = classification_data.get('class', '')
                output['confidence'] = classification_data.get('confidence', 0.0)
                
                # 检查置信度阈值
                if output['confidence'] >= confidence_threshold:
                    output['classification_success'] = True
                else:
                    output['classification_success'] = False
                    output['low_confidence'] = True
                    
            except:
                # 如果无法解析JSON，使用原始结果
                output['classification_result'] = result
                output['classification_success'] = True
            
            output['ai_classification_success'] = True
            output['model_used'] = model_name
            
        except Exception as e:
            logger.error(f'AI分类节点执行失败: {str(e)}')
            output['ai_classification_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def _execute_ai_extraction(self, config, context):
        """
        执行AI信息提取节点逻辑
        
        Args:
            config: 节点配置
            context: 执行上下文
            
        Returns:
            dict: AI信息提取结果
        """
        output = {}
        
        try:
            # 获取配置参数
            model_name = config.get('model_name', 'gpt-3.5-turbo')
            extraction_type = config.get('extraction_type', 'entities')
            input_text = config.get('input_text', '')
            target_entities = config.get('target_entities', [])
            output_format = config.get('output_format', 'json')
            include_context = config.get('include_context', False)
            
            # 从上下文中获取输入文本
            if not input_text and 'text' in context:
                input_text = context['text']
            
            # 构建信息提取提示
            if extraction_type == 'entities':
                prompt = f"请从以下文本中提取命名实体，目标实体类型：{', '.join(target_entities)}。文本：{input_text}。请返回{output_format.upper()}格式结果。"
            elif extraction_type == 'keywords':
                prompt = f"请从以下文本中提取关键词，最多提取{len(target_entities) if target_entities else 10}个关键词。文本：{input_text}。请返回{output_format.upper()}格式结果。"
            elif extraction_type == 'sentiment':
                prompt = f"请分析以下文本的情感倾向（正面/负面/中性）。文本：{input_text}。请返回{output_format.upper()}格式结果，包含情感类型和置信度。"
            elif extraction_type == 'summary':
                prompt = f"请对以下文本进行摘要，摘要长度控制在{target_entities[0] if target_entities else '100'}字以内。文本：{input_text}。请返回{output_format.upper()}格式结果。"
            else:
                prompt = f"请从以下文本中提取{extraction_type}信息，目标：{', '.join(target_entities)}。文本：{input_text}。请返回{output_format.upper()}格式结果。"
            
            # 调用AI服务
            result = self.ai_service.generate_content(prompt, model_name)
            
            # 解析提取结果
            try:
                import json
                extraction_data = json.loads(result)
                output['extraction_result'] = extraction_data
                
                # 根据提取类型设置特定字段
                if extraction_type == 'sentiment':
                    output['sentiment'] = extraction_data.get('sentiment', '')
                    output['confidence'] = extraction_data.get('confidence', 0.0)
                elif extraction_type == 'keywords':
                    output['keywords'] = extraction_data.get('keywords', [])
                elif extraction_type == 'entities':
                    output['entities'] = extraction_data.get('entities', {})
                elif extraction_type == 'summary':
                    output['summary'] = extraction_data.get('summary', '')
                    
            except:
                # 如果无法解析JSON，使用原始结果
                output['extraction_result'] = result
            
            output['ai_extraction_success'] = True
            output['model_used'] = model_name
            output['extraction_type'] = extraction_type
            
            # 如果包含上下文，添加相关信息
            if include_context:
                output['input_text'] = input_text
                output['target_entities'] = target_entities
            
        except Exception as e:
            logger.error(f'AI信息提取节点执行失败: {str(e)}')
            output['ai_extraction_success'] = False
            output['error_message'] = str(e)
        
        return output
    
    def get_workflow_executions(self, workflow_id, **filters):
        """
        获取工作流执行历史
        
        Args:
            workflow_id: 工作流ID
            filters: 过滤条件
            
        Returns:
            QuerySet: 执行实例查询集
        """
        return WorkflowExecution.objects.filter(workflow_id=workflow_id, **filters).order_by('-created_at')
    
    def get_execution_details(self, execution_id):
        """
        获取执行详情
        
        Args:
            execution_id: 执行实例ID
            
        Returns:
            dict: 执行详情
        """
        try:
            execution = WorkflowExecution.objects.get(id=execution_id)
            
            # 获取节点执行记录
            node_executions = list(execution.node_executions.all().values(
                'id', 'node_id', 'node__name', 'status', 'input_data', 
                'output_data', 'error_message', 'started_at', 'completed_at'
            ))
            
            return {
                'id': str(execution.id),
                'workflow_id': str(execution.workflow.id),
                'workflow_name': execution.workflow.name,
                'user_id': execution.created_by.id,
                'input_data': execution.input_data,
                'output_data': execution.output_data,
                'status': execution.status,
                'error_message': execution.error_message,
                'created_at': execution.created_at,
                'started_at': execution.started_at,
                'completed_at': execution.completed_at,
                'node_executions': node_executions
            }
            
        except WorkflowExecution.DoesNotExist:
            logger.error(f'执行实例不存在: {execution_id}')
            raise ValidationError('执行实例不存在')
        except Exception as e:
            logger.error(f'获取执行详情失败: {str(e)}')
            raise

    @transaction.atomic
    def save_workflow_design(self, workflow_id, nodes_data, connections_data):
        """
        保存工作流设计（节点和连接）
        
        Args:
            workflow_id: 工作流ID
            nodes_data: 节点数据列表
            connections_data: 连接数据列表
            
        Returns:
            AIWorkflow: 更新后的工作流实例
        """
        try:
            workflow = AIWorkflow.objects.get(id=workflow_id)
            
            # 更新工作流节点和连接
            workflow = self.update_workflow_nodes(workflow_id, nodes_data, connections_data)
            
            # 更新工作流更新时间
            workflow.updated_at = timezone.now()
            workflow.save()
            
            logger.info(f'保存工作流设计成功: {workflow.name}, ID: {workflow.id}')
            return workflow
            
        except AIWorkflow.DoesNotExist:
            logger.error(f'工作流不存在: {workflow_id}')
            raise ValidationError('工作流不存在')
        except Exception as e:
            logger.error(f'保存工作流设计失败: {str(e)}')
            raise

    def test_node(self, node_type, node_config, input_data, user):
        """
        测试单个节点功能
        
        Args:
            node_type: 节点类型代码
            node_config: 节点配置
            input_data: 输入数据
            user: 测试用户
            
        Returns:
            dict: 测试结果
        """
        try:
            # 创建模拟上下文
            context = input_data.copy()
            context['user'] = user
            
            # 根据节点类型执行相应的逻辑
            if node_type == 'data_input':
                result = self._execute_data_input(node_config, context)
            elif node_type == 'data_output':
                result = self._execute_data_output(node_config, context)
            elif node_type == 'data_filter':
                result = self._execute_data_filter(node_config, context)
            elif node_type == 'data_sort':
                result = self._execute_data_sort(node_config, context)
            elif node_type == 'data_aggregate':
                result = self._execute_data_aggregate(node_config, context)
            elif node_type == 'data_transformation':
                result = self._execute_data_transformation(node_config, context)
            elif node_type == 'text_processing':
                result = self._execute_text_processing(node_config, context)
            elif node_type == 'api_call':
                result = self._execute_api_call(node_config, context)
            elif node_type == 'database_query':
                result = self._execute_database_query(node_config, context)
            elif node_type == 'file_operation':
                result = self._execute_file_operation(node_config, context)
            elif node_type == 'wait':
                result = self._execute_wait(node_config, context)
            elif node_type == 'parallel':
                result = self._execute_parallel(node_config, context)
            elif node_type == 'loop':
                result = self._execute_loop(node_config, context)
            elif node_type == 'multi_condition':
                result = self._execute_multi_condition(node_config, context)
            elif node_type == 'ai_generation':
                result = self._execute_ai_generation(node_config, context)
            elif node_type == 'ai_classification':
                result = self._execute_ai_classification(node_config, context)
            elif node_type == 'ai_extraction':
                result = self._execute_ai_extraction(node_config, context)
            else:
                raise ValidationError(f'不支持的节点类型: {node_type}')
            
            return {
                'success': True,
                'node_type': node_type,
                'input_data': input_data,
                'output_data': result,
                'tested_at': timezone.now()
            }
            
        except Exception as e:
            logger.error(f'节点测试失败: {str(e)}')
            return {
                'success': False,
                'node_type': node_type,
                'input_data': input_data,
                'error_message': str(e),
                'tested_at': timezone.now()
            }

    def get_available_node_types(self):
        """
        获取可用的节点类型列表
        
        Returns:
            list: 节点类型列表
        """
        try:
            node_types = WorkflowNodeType.objects.filter(is_active=True).values(
                'id', 'code', 'name', 'description', 'node_type', 'icon', 
                'config_schema'
            )
            
            return list(node_types)
            
        except Exception as e:
            logger.error(f'获取节点类型失败: {str(e)}')
            return []

# 添加时区导入
from django.utils import timezone
from django.core.exceptions import PermissionDenied
import uuid