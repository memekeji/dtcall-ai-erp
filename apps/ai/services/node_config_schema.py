"""
工作流节点配置系统 - 完整的节点配置Schema和模块关联机制

提供：
1. 详细的节点配置Schema定义
2. 与项目现有模块的关联机制
3. 配置验证和默认值
4. 模块、服务、数据模型的引用支持
"""

from django.apps import apps
import os
import django
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
django.setup()


@dataclass
class FieldSchema:
    """字段Schema定义"""
    type: str
    required: bool = False
    label: str = ""
    description: str = ""
    default: Any = None
    placeholder: str = ""
    options: List[Dict] = field(default_factory=list)
    properties: Dict = field(default_factory=dict)
    depends_on: Dict = field(default_factory=dict)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    multiline: bool = False
    rows: int = 3


class NodeConfigSchema:
    """节点配置Schema管理器"""

    AVAILABLE_MODULES = {
        'customer': {'name': '客户管理', 'models': ['Customer', 'CustomerContact'], 'services': ['CustomerService']},
        'contract': {'name': '合同管理', 'models': ['Contract', 'ContractClause'], 'services': ['ContractService']},
        'finance': {'name': '财务管理', 'models': ['Invoice', 'Payment'], 'services': ['FinanceService']},
        'project': {'name': '项目管理', 'models': ['Project', 'ProjectTask'], 'services': ['ProjectService']},
        'approval': {'name': '审批流程', 'models': ['ApprovalFlow', 'ApprovalStep'], 'services': ['ApprovalService']},
        'message': {'name': '消息通知', 'models': ['Message', 'Notification'], 'services': ['MessageService']},
        'user': {'name': '用户管理', 'models': ['User', 'Employee', 'Department'], 'services': ['UserService']},
        'common': {'name': '公共模块', 'models': ['Attachment', 'Comment'], 'services': ['FileService']},
    }

    DATABASE_TABLES = {
        'customer_customer': '客户表',
        'contract_contract': '合同表',
        'finance_invoice': '发票表',
        'project_project': '项目表',
        'auth_user': '用户表',
    }

    @classmethod
    def get_data_input_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'input_type': FieldSchema(type='select', required=True, label='输入类型',
                                      default='json', options=[
                                          {'value': 'json', 'label': 'JSON数据'},
                                          {'value': 'form', 'label': '表单数据'},
                                          {'value': 'file', 'label': '文件上传'},
                                          {'value': 'database', 'label': '数据库查询'},
                                          {'value': 'api', 'label': 'API接口'},
                                          {'value': 'variable', 'label': '变量引用'},
                                          {'value': 'workflow_input',
                                              'label': '工作流输入'},
                                      ]),
            'output_variable': FieldSchema(type='string', required=True, label='输出变量名', default='input_data'),
            'required_fields': FieldSchema(type='array', required=False, label='必填字段', default=[]),
            'default_values': FieldSchema(type='object', required=False, label='默认值映射', default={}),

            'database_config': FieldSchema(type='object', required=False, label='数据库配置',
                                           depends_on={'input_type': 'database'}, properties={
                                               'table_name': FieldSchema(type='select', required=True, label='数据表',
                                                                         options=[{'value': k, 'label': v} for k, v in cls.DATABASE_TABLES.items()]),
                                               'fields': FieldSchema(type='array', required=False, label='查询字段', default=['*']),
                                               'conditions': FieldSchema(type='array', required=False, label='查询条件'),
                                               'order_by': FieldSchema(type='array', required=False, label='排序规则'),
                                               'limit': FieldSchema(type='number', required=False, label='返回数量', default=100),
                                           }),

            'api_config': FieldSchema(type='object', required=False, label='API配置',
                                      depends_on={'input_type': 'api'}, properties={
                                          'api_url': FieldSchema(type='string', required=True, label='API地址'),
                                          'method': FieldSchema(type='select', required=True, label='请求方法', default='GET',
                                                                options=[{'value': m, 'label': m} for m in ['GET', 'POST', 'PUT', 'DELETE']]),
                                          'headers': FieldSchema(type='object', required=False, label='请求头', default={}),
                                          'auth_type': FieldSchema(type='select', required=False, label='认证方式', default='none',
                                                                   options=[{'value': 'none', 'label': '无认证'}, {'value': 'bearer', 'label': 'Bearer Token'}]),
                                          'timeout': FieldSchema(type='number', required=False, label='超时时间', default=30),
                                      }),
        }

    @classmethod
    def get_data_output_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'output_type': FieldSchema(type='select', required=True, label='输出类型',
                                       default='json', options=[
                                           {'value': 'json', 'label': 'JSON响应'},
                                           {'value': 'file', 'label': '文件下载'},
                                           {'value': 'database', 'label': '数据库存储'},
                                           {'value': 'api', 'label': 'API回调'},
                                           {'value': 'webhook',
                                               'label': 'Webhook回调'},
                                       ]),
            'input_variable': FieldSchema(type='string', required=True, label='输入变量名', default='output_data'),

            'database_config': FieldSchema(type='object', required=False, label='数据库存储配置',
                                           depends_on={'output_type': 'database'}, properties={
                                               'table_name': FieldSchema(type='select', required=True, label='目标表'),
                                               'operation': FieldSchema(type='select', required=True, label='操作类型',
                                                                        options=[{'value': 'insert', 'label': '插入'}, {'value': 'update', 'label': '更新'}]),
                                               'field_mapping': FieldSchema(type='object', required=True, label='字段映射'),
                                           }),

            'file_config': FieldSchema(type='object', required=False, label='文件输出配置',
                                       depends_on={'output_type': 'file'}, properties={
                                           'file_type': FieldSchema(type='select', required=True, label='文件类型',
                                                                    options=[{'value': 'json', 'label': 'JSON'}, {'value': 'csv', 'label': 'CSV'}]),
                                           'file_name': FieldSchema(type='string', required=False, label='文件名模板', default='output'),
                                       }),
        }

    @classmethod
    def get_ai_generation_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'model_id': FieldSchema(type='select', required=True, label='AI模型', default='gpt-4',
                                    options=[{'value': 'gpt-4', 'label': 'GPT-4'}, {'value': 'gpt-3.5-turbo', 'label': 'GPT-3.5'},
                                             {'value': 'claude-3', 'label': 'Claude 3'}]),
            'prompt': FieldSchema(type='text', required=True, label='提示词', multiline=True, rows=8,
                                  placeholder='请根据以下信息生成内容：\n\n输入数据：${input_data}'),
            'prompt_type': FieldSchema(type='select', required=False, label='提示词类型', default='free',
                                       options=[{'value': 'free', 'label': '自由格式'}, {'value': 'structured', 'label': '结构化输出'}]),
            'temperature': FieldSchema(type='number', required=False, label='Temperature', default=0.7),
            'max_tokens': FieldSchema(type='number', required=False, label='最大输出token', default=2000),
            'input_variables': FieldSchema(type='array', required=False, label='输入变量', default=[]),
            'output_variable': FieldSchema(type='string', required=True, label='输出变量名', default='ai_output'),
            'error_handling': FieldSchema(type='select', required=False, label='错误处理', default='retry',
                                          options=[{'value': 'retry', 'label': '重试'}, {'value': 'fallback', 'label': '降级'}, {'value': 'error', 'label': '报错'}]),
        }

    @classmethod
    def get_ai_classification_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'model_id': FieldSchema(
                type='select', required=True, label='AI模型', default='gpt-4'), 'classification_type': FieldSchema(
                type='select', required=True, label='分类类型', default='single', options=[
                    {
                        'value': 'single', 'label': '单标签'}, {
                        'value': 'multi', 'label': '多标签'}, {
                            'value': 'binary', 'label': '二分类'}]), 'categories': FieldSchema(
                                type='array', required=True, label='分类选项', properties={
                                    'value': FieldSchema(
                                        type='string', required=True), 'label': FieldSchema(
                                            type='string', required=True)}), 'input_variable': FieldSchema(
                                                type='string', required=True, label='输入变量'), 'output_variable': FieldSchema(
                                                    type='string', required=True, label='输出变量', default='result'), 'temperature': FieldSchema(
                                                        type='number', required=False, label='Temperature', default=0.3), }

    @classmethod
    def get_ai_extraction_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'model_id': FieldSchema(type='select', required=True, label='AI模型', default='gpt-4'),
            'extraction_type': FieldSchema(type='select', required=True, label='提取类型',
                                           options=[{'value': 'schema', 'label': 'Schema定义'}, {'value': 'entity', 'label': '实体识别'}]),
            'extraction_schema': FieldSchema(type='text', required=True, label='提取Schema', multiline=True, rows=6,
                                             placeholder='{"type": "object", "properties": {"name": {"type": "string"}}}'),
            'input_variable': FieldSchema(type='string', required=True, label='输入变量'),
            'output_variable': FieldSchema(type='string', required=True, label='输出变量', default='extraction'),
            'temperature': FieldSchema(type='number', required=False, label='Temperature', default=0.1),
        }

    @classmethod
    def get_knowledge_retrieval_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'retrieval_type': FieldSchema(
                type='select', required=True, label='检索类型', default='vector', options=[
                    {
                        'value': 'vector', 'label': '向量检索'}, {
                        'value': 'keyword', 'label': '关键词检索'}, {
                        'value': 'hybrid', 'label': '混合检索'}]), 'knowledge_base': FieldSchema(
                            type='select', required=True, label='知识库', options=[
                                {
                                    'value': 'default', 'label': '默认知识库'}, {
                                        'value': 'product', 'label': '产品知识库'}, {
                                            'value': 'faq', 'label': 'FAQ知识库'}]), 'query_variable': FieldSchema(
                                                type='string', required=True, label='查询变量'), 'top_k': FieldSchema(
                                                    type='number', required=False, label='返回数量', default=5), 'similarity_threshold': FieldSchema(
                                                        type='number', required=False, label='相似度阈值', default=0.7), 'output_mode': FieldSchema(
                                                            type='select', required=False, label='输出模式', default='content', options=[
                                                                {
                                                                    'value': 'content', 'label': '内容'}, {
                                                                        'value': 'full', 'label': '完整信息'}]), }

    @classmethod
    def get_condition_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'condition_type': FieldSchema(
                type='select', required=True, label='条件类型', default='if_else', options=[
                    {
                        'value': 'if_else', 'label': 'IF-ELSE'}, {
                        'value': 'switch', 'label': 'SWITCH'}, {
                        'value': 'logic', 'label': '逻辑组合'}]), 'condition_variable': FieldSchema(
                            type='string', required=True, label='条件变量', placeholder='例如: data.sentiment'), 'expressions': FieldSchema(
                                type='array', required=False, label='条件表达式', properties={
                                    'operator': FieldSchema(
                                        type='select', required=True, label='运算符', options=[
                                            {
                                                'value': '==', 'label': '等于'}, {
                                                    'value': '>', 'label': '大于'}, {
                                                        'value': '<', 'label': '小于'}]), 'value': FieldSchema(
                                                            type='string', required=True, label='比较值'), 'output': FieldSchema(
                                                                type='string', required=True, label='输出标签'), }), 'default_output': FieldSchema(
                                                                    type='string', required=False, label='默认输出', default='default'), }

    @classmethod
    def get_notification_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'notification_type': FieldSchema(type='select', required=True, label='通知类型', default='email',
                                             options=[{'value': 'email', 'label': '邮件'}, {'value': 'sms', 'label': '短信'}, {'value': 'webhook', 'label': 'Webhook'},
                                                      {'value': 'in_app', 'label': '站内通知'}, {'value': 'ticket', 'label': '创建工单'}]),
            'title': FieldSchema(type='string', required=True, label='通知标题'),
            'priority': FieldSchema(type='select', required=False, label='优先级', default='medium',
                                    options=[{'value': 'low', 'label': '低'}, {'value': 'medium', 'label': '中'}, {'value': 'high', 'label': '高'}]),
            'trigger_type': FieldSchema(type='select', required=True, label='触发类型', default='always',
                                        options=[{'value': 'always', 'label': '始终'}, {'value': 'condition', 'label': '满足条件'}, {'value': 'on_error', 'label': '出错时'}]),
            'condition': FieldSchema(type='text', required=False, label='触发条件', depends_on={'trigger_type': 'condition'}),

            'email_config': FieldSchema(type='object', required=False, label='邮件配置',
                                        depends_on={'notification_type': 'email'}, properties={
                                            'recipients': FieldSchema(type='array', required=True, label='收件人',
                                                                      properties={'email': FieldSchema(type='string', required=True), 'name': FieldSchema(type='string, required=False')}),
                                            'content': FieldSchema(type='text', required=False, label='邮件内容', multiline=True, rows=6),
                                        }),

            'webhook_config': FieldSchema(type='object', required=False, label='Webhook配置',
                                          depends_on={'notification_type': 'webhook'}, properties={
                                              'url': FieldSchema(type='string', required=True, label='Webhook地址'),
                                              'method': FieldSchema(type='select', required=False, label='方法', default='POST'),
                                          }),

            'ticket_config': FieldSchema(type='object', required=False, label='工单配置',
                                         depends_on={'notification_type': 'ticket'}, properties={
                                             'title': FieldSchema(type='string', required=True, label='工单标题'),
                                             'description': FieldSchema(type='text', required=True, label='工单描述'),
                                             'severity': FieldSchema(type='select', required=False, label='严重程度', default='medium'),
                                         }),
        }

    @classmethod
    def get_database_query_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'table_name': FieldSchema(type='select', required=True, label='数据表',
                                      options=[{'value': k, 'label': v} for k, v in cls.DATABASE_TABLES.items()]),
            'query_type': FieldSchema(type='select', required=True, label='查询模式', default='wizard',
                                      options=[{'value': 'wizard', 'label': '向导模式'}, {'value': 'sql', 'label': 'SQL模式'}]),
            'fields': FieldSchema(type='array', required=False, label='查询字段', default=['*']),
            'conditions': FieldSchema(type='array', required=False, label='查询条件'),
            'order_by': FieldSchema(type='array', required=False, label='排序'),
            'limit': FieldSchema(type='number', required=False, label='限制', default=100),
            'sql_query': FieldSchema(type='text', required=False, label='SQL语句', multiline=True, rows=5,
                                     depends_on={'query_type': 'sql'}),
            'output_variable': FieldSchema(type='string', required=True, label='输出变量', default='result'),
            'timeout': FieldSchema(type='number', required=False, label='超时时间', default=30),
        }

    @classmethod
    def get_http_request_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'api_url': FieldSchema(type='string', required=True, label='API地址'),
            'method': FieldSchema(type='select', required=True, label='请求方法', default='GET',
                                  options=[{'value': m, 'label': m} for m in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']]),
            'headers': FieldSchema(type='object', required=False, label='请求头', default={}),
            'request_body': FieldSchema(type='text', required=False, label='请求体', multiline=True, rows=4),
            'auth_type': FieldSchema(type='select', required=False, label='认证方式', default='none',
                                     options=[{'value': 'none', 'label': '无'}, {'value': 'bearer', 'label': 'Bearer Token'}]),
            'timeout': FieldSchema(type='number', required=False, label='超时时间', default=30),
            'output_variable': FieldSchema(type='string', required=True, label='输出变量', default='response'),
        }

    @classmethod
    def get_text_processing_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'processing_type': FieldSchema(
                type='select', required=True, label='处理类型', options=[
                    {
                        'value': 'clean', 'label': '文本清洗'}, {
                        'value': 'transform', 'label': '文本转换'}, {
                        'value': 'extract', 'label': '信息提取'}, {
                            'value': 'translate', 'label': '翻译'}, {
                                'value': 'summarize', 'label': '摘要生成'}]), 'input_variable': FieldSchema(
                                    type='string', required=True, label='输入变量'), 'output_variable': FieldSchema(
                                        type='string', required=True, label='输出变量'), 'custom_config': FieldSchema(
                                            type='object', required=False, label='自定义配置', default={}), }

    @classmethod
    def get_data_aggregation_schema(cls) -> Dict[str, FieldSchema]:
        return {
            'group_by': FieldSchema(
                type='array', required=True, label='分组字段'), 'aggregations': FieldSchema(
                type='array', required=True, label='聚合操作', properties={
                    'field': FieldSchema(
                        type='string', required=True, label='字段'), 'function': FieldSchema(
                        type='select', required=True, label='聚合函数', options=[
                            {
                                'value': 'sum', 'label': '求和'}, {
                                    'value': 'avg', 'label': '平均'}, {
                                        'value': 'count', 'label': '计数'}, {
                                            'value': 'max', 'label': '最大'}]), 'alias': FieldSchema(
                                                type='string', required=False, label='别名'), }), 'input_variable': FieldSchema(
                                                    type='string', required=True, label='输入变量'), 'output_variable': FieldSchema(
                                                        type='string', required=True, label='输出变量'), }

    @classmethod
    def get_schema(cls, node_type: str) -> Dict[str, FieldSchema]:
        schemas = {
            'data_input': cls.get_data_input_schema(),
            'data_output': cls.get_data_output_schema(),
            'ai_generation': cls.get_ai_generation_schema(),
            'ai_classification': cls.get_ai_classification_schema(),
            'ai_extraction': cls.get_ai_extraction_schema(),
            'knowledge_retrieval': cls.get_knowledge_retrieval_schema(),
            'condition': cls.get_condition_schema(),
            'notification': cls.get_notification_schema(),
            'database_query': cls.get_database_query_schema(),
            'http_request': cls.get_http_request_schema(),
            'text_processing': cls.get_text_processing_schema(),
            'data_aggregation': cls.get_data_aggregation_schema(),
        }
        return schemas.get(node_type, {})


class ModuleAssociationService:
    """模块关联服务 - 建立工作流节点与项目模块的关联"""

    @classmethod
    def get_available_modules(cls) -> Dict:
        return NodeConfigSchema.AVAILABLE_MODULES

    @classmethod
    def get_module_models(cls, module_name: str) -> List[Dict]:
        module = NodeConfigSchema.AVAILABLE_MODULES.get(module_name)
        if not module:
            return []

        models = []
        for model_name in module.get('models', []):
            try:
                model = apps.get_model(module_name, model_name)
                fields = [{'name': f.name, 'type': f.get_internal_type()}
                          for f in model._meta.fields]
                models.append({'name': model_name,
                               'verbose_name': model._meta.verbose_name,
                               'fields': fields})
            except BaseException:
                pass
        return models

    @classmethod
    def get_module_services(cls, module_name: str) -> List[Dict]:
        module = NodeConfigSchema.AVAILABLE_MODULES.get(module_name)
        if not module:
            return []
        return [{'name': s} for s in module.get('services', [])]

    @classmethod
    def generate_model_query_config(
            cls,
            module_name: str,
            model_name: str) -> Dict:
        return {
            'connection_type': 'project',
            'table_name': f'{module_name}_{model_name.lower()}',
            'query_type': 'wizard',
            'wizard_config': {'fields': ['*'], 'conditions': [], 'limit': 100}
        }


def get_full_config_schema(node_type: str) -> Dict[str, FieldSchema]:
    return NodeConfigSchema.get_schema(node_type)
