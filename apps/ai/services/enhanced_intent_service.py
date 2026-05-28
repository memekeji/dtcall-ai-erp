"""
增强的意图识别服务
整合 AI 意图分类器、数据权限控制和自动化数据处理功能
"""

import logging
from typing import Dict, Any
from django.contrib.auth.models import User
from apps.ai.services.ai_intent_classifier import ai_intent_classifier
from apps.ai.services.query_service import query_service
from apps.user.services.permission_node_mapper import permission_node_mapper
from apps.system.middleware.data_permission_middleware import PermissionChecker

logger = logging.getLogger(__name__)


class EnhancedIntentService:
    """增强的意图处理服务"""

    MUTATING_ACTIONS = {'create', 'update', 'delete'}
    MUTATING_INTENTS = {'DATA_CREATE', 'DATA_UPDATE', 'DATA_DELETE'}

    BUSINESS_HANDOFF_CONFIG = {
        'customer': {
            'name': '客户',
            'module': '客户管理',
            'list_url': '/customer/',
            'create_url': '/customer/create/',
            'edit_url_template': '/customer/edit/{id}/',
            'permission_base': 'customer',
        },
        'order': {
            'name': '客户订单',
            'module': '客户管理',
            'list_url': '/customer/orders/',
            'create_url': '/customer/orders/create/',
            'edit_url_template': '/customer/orders/{id}/edit/',
            'permission_base': 'customer_order',
        },
        'contract': {
            'name': '合同',
            'module': '合同管理',
            'list_url': '/contract/sales/',
            'create_url': '/contract/create/',
            'edit_url_template': '/contract/sales/update/{id}/',
            'permission_base': 'contract',
        },
        'project': {
            'name': '项目',
            'module': '项目管理',
            'list_url': '/project/',
            'create_url': '/project/add/',
            'edit_url_template': '/project/edit/{id}/',
            'permission_base': 'project',
        },
        'invoice': {
            'name': '发票',
            'module': '财务管理',
            'list_url': '/finance/invoice/',
            'create_url': '/finance/invoice/add/',
            'edit_url_template': '/finance/invoice/edit/{id}/',
            'permission_base': 'invoice',
        },
        'employee': {
            'name': '员工',
            'module': '人事管理',
            'list_url': '/user/employee/',
            'create_url': '/user/employee/create/',
            'edit_url_template': '/user/employee/update/{id}/',
            'permission_base': 'employee',
        },
        'department': {
            'name': '部门',
            'module': '组织管理',
            'list_url': '/system/department/',
            'create_url': '/system/department/add/',
            'edit_url_template': '/system/department/{id}/update/',
            'permission_base': 'department',
        },
        'finance': {
            'name': '费用报销',
            'module': '财务管理',
            'list_url': '/finance/expense/',
            'create_url': '/finance/expense/add/',
            'edit_url_template': None,
            'permission_base': 'reimbursement',
        },
        'production': {
            'name': '生产计划',
            'module': '生产管理',
            'list_url': '/production/task/plan/',
            'create_url': '/production/task/plan/add/',
            'edit_url_template': '/production/task/plan/edit/{id}/',
            'permission_base': 'production_plan',
        },
        'followup': {
            'name': '跟进记录',
            'module': '客户管理',
            'list_url': '/customer/followup/',
            'create_url': '/customer/followup/create/',
            'edit_url_template': '/customer/followup/{id}/edit/',
            'permission_base': 'follow_record',
        },
        'supplier': {
            'name': '供应商',
            'module': '合同管理',
            'list_url': '/contract/supplier/',
            'create_url': '/contract/supplier/add/',
            'edit_url_template': '/contract/supplier/edit/{id}/',
            'permission_base': 'supplier',
        },
        'product': {
            'name': '产品',
            'module': '合同管理',
            'list_url': '/contract/product/',
            'create_url': '/contract/product/add/',
            'edit_url_template': '/contract/product/edit/{id}/',
            'permission_base': 'product',
        },
        'inventory': {
            'name': '库存物料',
            'module': '库存管理',
            'list_url': '/inventory/inventory/',
            'create_url': '/inventory/item/add/',
            'edit_url_template': '/inventory/item/{id}/',
            'permission_base': 'inventory',
            'available': False,
            'unavailable_reason': '库存模块当前未接入系统根路由，请先完成模块接入后再进入业务页面操作',
        },
    }

    def __init__(self):
        self.classifier = ai_intent_classifier
        self.query_service = query_service
        self.permission_checker = PermissionChecker()

    @property
    def intelligent_assistant(self):
        """获取智能助手实例（已禁用直接业务执行）"""
        return None

    def _get_intelligent_assistant(self, user):
        """阻止通过智能助手绕过意图识别和权限确认"""
        logger.warning("直接智能助手业务执行已被安全策略禁用")
        return None

    def process_user_request(self, user: User, query: str) -> Dict[str, Any]:
        """处理用户请求"""
        try:
            intent_result = self.classifier.classify_intent(user, query)

            if not intent_result.get('intent'):
                return self._create_error_response('无法识别您的意图，请重新描述您的需求')

            if intent_result.get('source') != 'ai' and intent_result.get('intent') != 'UI_ACTION':
                return self._create_confirmation_response(intent_result, query)

            if self._is_mutating_intent(intent_result):
                return self._create_confirmation_response(intent_result, query)

            permission_result = self._check_data_permission(
                user, intent_result)
            if not permission_result['has_permission']:
                return self._create_permission_denied_response(
                    intent_result, permission_result)

            if intent_result['confidence'] < 0.65 or intent_result.get('requires_confirmation'):
                return self._create_confirmation_response(intent_result, query)

            execution_result = self._execute_intent(user, intent_result, query)

            return execution_result

        except Exception as e:
            logger.error(f"处理用户请求失败：{str(e)}")
            return self._create_error_response('处理请求时发生错误，请稍后重试')

    def _check_data_permission(
            self, user: User, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查用户数据权限

        Args:
            user: 当前用户
            intent_result: 意图识别结果

        Returns:
            Dict[str, Any]: 权限检查结果
        """
        if user.is_superuser:
            return {
                'has_permission': True,
                'message': '超级管理员权限',
                'data_scope': 'all'
            }

        intent_type = intent_result.get('intent')
        data_type = intent_result.get('data_type')
        action = intent_result.get('action')

        if intent_type == 'AI_CHAT':
            return {
                'has_permission': True,
                'message': '对话无需权限',
                'data_scope': 'chat'
            }

        if intent_type == 'KNOWLEDGE_BASE':
            return {
                'has_permission': True,
                'message': '知识库查询权限',
                'data_scope': 'knowledge'
            }

        if intent_result.get('intent') == 'UI_ACTION':
            return {'has_permission': True}

        if intent_result.get('action') in {'create', 'update', 'delete'} or intent_result.get('intent') in {'DATA_CREATE', 'DATA_UPDATE', 'DATA_DELETE'}:
            return {
                'has_permission': False,
                'required_permission': 'explicit_confirmation',
                'message': '数据新增、修改、删除需要在业务页面中确认后执行'
            }

        if not data_type:
            return {
                'has_permission': True,
                'message': '通用查询权限',
                'data_scope': 'general'
            }

        permission_map = {
            'customer': 'customer.view_customer',
            'order': 'customer.view_customerorder',
            'contract': 'contract.view_contract',
            'project': 'project.view_project',
            'invoice': 'customer.view_customerinvoice',
            'employee': 'user.view_employeefile',
            'department': 'department.view_department',
            'finance': 'finance.view_expense',
            'production': 'production.view_productionplan',
            'supplier': 'contract.view_supplier',
            'product': 'contract.view_product',
            'inventory': 'inventory.view_inventory',
            'followup': 'customer.view_followrecord',
        }

        required_permission = permission_map.get(data_type)

        if not required_permission:
            return {
                'has_permission': False,
                'required_permission': 'mapped_business_permission',
                'message': f'{data_type} 类型暂未配置 AI 查询权限映射',
                'data_scope': 'forbidden'
            }

        has_permission = user.has_perm(required_permission)

        if not has_permission:
            return {
                'has_permission': False,
                'message': f'您没有权限访问{data_type}数据',
                'required_permission': required_permission,
                'data_scope': 'none'
            }

        data_scope = self._get_user_data_scope(user, data_type)

        return {
            'has_permission': True,
            'message': '权限验证通过',
            'data_scope': data_scope,
            'action': action
        }

    def _get_user_data_scope(self, user: User, data_type: str) -> str:
        """
        获取用户的数据范围

        Args:
            user: 当前用户
            data_type: 数据类型

        Returns:
            str: 数据范围描述
        """
        try:
            data_scope = PermissionChecker.get_user_data_scope(user)
            return data_scope.get('scope', 'self')
        except Exception as e:
            logger.error(f"获取数据范围失败：{str(e)}")
            return 'self'

    def _execute_intent(
            self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        执行意图处理

        Args:
            user: 当前用户
            intent_result: 意图识别结果
            query: 原始查询

        Returns:
            Dict[str, Any]: 执行结果
        """
        intent_type = intent_result.get('intent')
        action = intent_result.get('action')
        intent_result.get('data_type')

        if intent_type == 'UI_ACTION':
            return {
                'success': True,
                'intent_type': intent_type,
                'result': '已识别为安全界面操作',
                'ui_action': intent_result.get('action'),
                'confidence': intent_result.get('confidence', 0.0),
                'requires_client_action': True
            }

        if intent_type == 'AI_CHAT':
            return self._handle_ai_chat(user, query)

        if intent_type == 'KNOWLEDGE_BASE':
            return self._handle_knowledge_base(user, query)

        if intent_type in ['DATA_QUERY', 'DATA_CREATE', 'DATA_UPDATE', 'DATA_DELETE']:
            if self._is_mutating_intent(intent_result):
                return self._create_confirmation_response(intent_result, query)
            return self._handle_data_query(user, intent_result, query)

        return self._handle_data_query(user, intent_result, query)

    def _handle_data_query(
            self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """处理数据查询"""
        try:
            result = self.query_service.process_query(user, query, intent_result)

            if result.get('success'):
                return {
                    'success': True,
                    'intent_type': 'DATA_QUERY',
                    'result': result['result'],
                    'data': result.get('data'),
                    'confidence': intent_result.get('confidence', 0.0),
                    'specific_intent': result.get('specific_intent')
                }
            else:
                return self._create_error_response(result.get('message', '查询失败'))

        except Exception as e:
            logger.error(f"数据查询处理失败：{str(e)}")
            return self._create_error_response('数据查询失败，请稍后重试')

    def _handle_data_create(
            self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        处理数据创建

        Args:
            user: 当前用户
            intent_result: 意图识别结果
            query: 原始查询

        Returns:
            Dict[str, Any]: 创建结果
        """
        return self._create_confirmation_response(intent_result, query)

    def _handle_data_update(
            self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        处理数据修改

        Args:
            user: 当前用户
            intent_result: 意图识别结果
            query: 原始查询

        Returns:
            Dict[str, Any]: 修改结果
        """
        return self._create_confirmation_response(intent_result, query)

    def _handle_knowledge_base(self, user: User, query: str) -> Dict[str, Any]:
        """
        处理知识库查询

        Args:
            user: 当前用户
            query: 原始查询

        Returns:
            Dict[str, Any]: 查询结果
        """
        return {
            'success': True,
            'message': '知识库功能正在开发中',
            'intent_type': 'KNOWLEDGE_BASE',
            'result': '知识库查询功能即将上线，敬请期待'
        }

    def _handle_ai_chat(self, user: User, query: str) -> Dict[str, Any]:
        """处理 AI 对话"""
        try:
            from apps.ai.services.ai_intent_classifier import ai_intent_classifier

            ai_client = ai_intent_classifier.ai_client
            if ai_client is None:
                return self._create_fallback_response(query)

            messages = [
                {'role': 'system', 'content': '你是友好的企业级智能助手。只进行安全的自然语言回答，不直接执行业务数据新增、修改、删除，不调用工具。'},
                {'role': 'user', 'content': query}
            ]

            response = ai_client.chat_completion(messages)
            response_text = response.get('content', '') if isinstance(response, dict) else str(response)

            if not response_text or not response_text.strip():
                logger.warning("AI 返回空响应，使用降级响应")
                return self._create_fallback_response(query)

            return {
                'success': True,
                'message': response_text,
                'intent_type': 'AI_CHAT',
                'result': response_text,
                'confidence': 1.0
            }
        except Exception as e:
            logger.error(f"AI 对话失败：{str(e)}")
            return self._create_fallback_response(query)

    def _create_fallback_response(self, query: str) -> Dict[str, Any]:
        """创建降级响应（AI 不可用时）"""
        response = '当前未配置可用的 AI 模型，我可以继续提供基础帮助。请配置 AI 模型后获得更准确的意图识别和自然语言理解能力。'

        return {
            'success': True,
            'message': response,
            'intent_type': 'AI_CHAT',
            'result': response,
            'confidence': 0.35,
            'source': 'safe_fallback'
        }

    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            'success': False,
            'message': message,
            'intent_type': None,
            'confidence': 0.0
        }

    def _create_permission_denied_response(
            self, intent_result: Dict[str, Any], permission_result: Dict[str, Any]) -> Dict[str, Any]:
        """创建权限拒绝响应"""
        return {
            'success': False,
            'message': permission_result.get(
                'message',
                '您没有权限执行此操作'),
            'intent_type': intent_result.get('intent'),
            'confidence': intent_result.get('confidence'),
            'requires_permission': permission_result.get('required_permission'),
            'suggestion': '请联系管理员获取相应权限'}

    def _create_confirmation_response(
            self, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """创建确认响应"""
        intent_type = intent_result.get('intent')
        confidence = intent_result.get('confidence', 0)
        business_task = None

        if self._is_mutating_intent(intent_result):
            business_task = self._build_business_handoff(intent_result, query)
            if business_task:
                options = business_task.get('options', [])
                message = business_task.get('message')
            else:
                options = [
                    {'text': '打开相关业务列表', 'intent': intent_type, 'action': 'open_business_page'},
                    {'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel'},
                ]
                message = '已识别到数据新增、修改或删除意图。为保护业务数据安全，请在对应业务页面核对并确认后执行。'
        else:
            options = intent_result.get('fallback_options', [])
            if not options:
                options = [
                    {'text': '按普通 AI 对话处理', 'intent': 'AI_CHAT', 'action': 'chat'},
                    {'text': '补充数据查询条件', 'intent': 'DATA_QUERY', 'action': 'query'},
                    {'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel'},
                ]

            if intent_result.get('source') != 'ai':
                message = '当前未配置可用的 AI 模型，无法进行高置信度意图识别。请补充说明或先配置 AI 模型。'
            else:
                message = f'我不太确定您的意图（置信度：{confidence:.0%}），请选择：'

        response = {
            'success': True,
            'requires_confirmation': True,
            'message': message,
            'intent_type': intent_type,
            'confidence': confidence,
            'options': options,
            'original_query': query,
            'source': intent_result.get('source'),
            'action': intent_result.get('action'),
            'data_type': intent_result.get('data_type'),
            'entities': intent_result.get('entities') or {},
        }
        if business_task:
            response['task'] = business_task
            response['requires_client_action'] = True
        return response

    def _is_mutating_intent(self, intent_result: Dict[str, Any]) -> bool:
        return (
            intent_result.get('action') in self.MUTATING_ACTIONS or
            intent_result.get('intent') in self.MUTATING_INTENTS
        )

    def _build_business_handoff(
            self, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        data_type = intent_result.get('data_type')
        if not data_type:
            return self._build_unknown_business_handoff(intent_result, query)

        config = self.BUSINESS_HANDOFF_CONFIG.get(data_type)
        if not config:
            return self._build_unknown_business_handoff(intent_result, query)

        action = self._normalize_business_action(intent_result)
        title = self._build_business_title(action, config['name'])
        target_url, disabled_reason = self._resolve_business_target_url(config, action, intent_result)
        permission = self._build_business_permission(config.get('permission_base'), action)
        entities = intent_result.get('entities') or {}
        permission_exists = self._has_business_permission(permission)
        disabled_reason = self._merge_disabled_reason(disabled_reason, None if permission_exists else '当前业务操作权限节点未配置，已阻止直接打开')
        enabled = bool(target_url and not disabled_reason and config.get('available', True))
        safety_notice = self._get_business_safety_notice(action)
        message = f'已识别到{title}意图。{safety_notice}'
        if disabled_reason:
            message = f'已识别到{title}意图，但{disabled_reason}。'

        task = {
            'type': 'business_handoff',
            'intent_type': intent_result.get('intent'),
            'action': action,
            'data_type': data_type,
            'module': config.get('module'),
            'title': title,
            'target_url': target_url,
            'list_url': config.get('list_url'),
            'open_mode': 'tab',
            'requires_user_confirmation': True,
            'safety_notice': safety_notice,
            'message': message,
            'prefill': self._sanitize_prefill(entities),
            'permission_required': permission,
            'has_business_permission': permission_exists,
            'enabled': enabled,
            'disabled_reason': disabled_reason,
            'confidence': intent_result.get('confidence', 0),
            'options': [],
        }
        task['options'] = self._build_business_options(task, config)
        return task

    def _build_unknown_business_handoff(
            self, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        action = self._normalize_business_action(intent_result)
        title = self._build_business_title(action, '业务数据')
        message = f'已识别到{title}意图，但暂时无法确定具体业务模块。请补充说明客户、项目、合同、订单等业务类型后再继续。'
        task = {
            'type': 'business_handoff',
            'intent_type': intent_result.get('intent'),
            'action': action,
            'data_type': intent_result.get('data_type'),
            'module': None,
            'title': title,
            'target_url': None,
            'list_url': None,
            'open_mode': 'tab',
            'requires_user_confirmation': True,
            'safety_notice': 'AI 不会直接新增、修改或删除业务数据。',
            'message': message,
            'prefill': {},
            'permission_required': None,
            'has_business_permission': False,
            'enabled': False,
            'disabled_reason': '无法确定具体业务模块',
            'confidence': intent_result.get('confidence', 0),
            'options': [],
        }
        task['options'] = [
            {'text': '补充业务类型', 'intent': 'DATA_QUERY', 'action': 'clarify', 'enabled': True},
            {'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel', 'enabled': True},
        ]
        return task

    def _normalize_business_action(self, intent_result: Dict[str, Any]) -> str:
        action = intent_result.get('action')
        intent_type = intent_result.get('intent')
        if action in self.MUTATING_ACTIONS:
            return action
        if intent_type == 'DATA_CREATE':
            return 'create'
        if intent_type == 'DATA_UPDATE':
            return 'update'
        if intent_type == 'DATA_DELETE':
            return 'delete'
        return 'query'

    def _build_business_title(self, action: str, business_name: str) -> str:
        action_names = {
            'create': '新增',
            'update': '修改',
            'delete': '删除',
            'query': '查看',
        }
        return f"{action_names.get(action, '处理')}{business_name}"

    def _get_business_safety_notice(self, action: str) -> str:
        if action == 'delete':
            return 'AI 不会直接删除业务数据，只会打开对应业务页面或列表，请您核对记录后在页面内按系统流程确认。'
        if action == 'update':
            return 'AI 不会直接修改业务数据，只会打开对应业务页面，请您核对记录和字段后再保存。'
        return 'AI 只负责识别和带您进入业务页面，不会直接新增业务数据，请在页面内核对后再保存。'

    def _resolve_business_target_url(
            self, config: Dict[str, Any], action: str, intent_result: Dict[str, Any]):
        if not config.get('available', True):
            return None, config.get('unavailable_reason') or '该业务模块当前不可用'

        if action == 'create':
            return config.get('create_url'), None if config.get('create_url') else '未配置新增页面入口'

        if action in {'update', 'delete'}:
            record_id = self._extract_record_id(intent_result)
            template = config.get('edit_url_template')
            if action == 'update' and record_id and template:
                return template.format(id=record_id), None
            if action == 'delete' and record_id and template:
                return template.format(id=record_id), None
            return config.get('list_url'), '请先在列表中定位具体记录后再继续操作'

        return config.get('list_url'), None if config.get('list_url') else '未配置业务页面入口'

    def _extract_record_id(self, intent_result: Dict[str, Any]):
        entities = intent_result.get('entities') or {}
        for key in ('id', 'pk', 'record_id', 'object_id'):
            value = entities.get(key) or intent_result.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return value
        return None

    def _build_business_permission(self, permission_base: str, action: str):
        if not permission_base:
            return None
        permission_actions = {
            'create': 'add',
            'update': 'change',
            'delete': 'delete',
            'query': 'view',
        }
        permission_action = permission_actions.get(action, 'view')
        codename = f'{permission_action}_{permission_base}'
        return {
            'app_label': 'user',
            'codename': codename,
            'full_code': f'user.{codename}',
            'action': permission_action,
            'name': self._get_permission_display_name(codename),
        }

    def _has_business_permission(self, permission: Dict[str, Any]) -> bool:
        if not permission:
            return False
        codename = permission.get('codename')
        if not codename:
            return False
        try:
            return permission_node_mapper.get_full_permission(codename) is not None
        except Exception:
            return False

    def _get_permission_display_name(self, codename: str) -> str:
        try:
            permission = permission_node_mapper.get_full_permission(codename)
            if permission:
                return permission
        except Exception:
            pass
        return codename

    def _merge_disabled_reason(self, current_reason, new_reason):
        if current_reason and new_reason:
            return f'{current_reason}；{new_reason}'
        return current_reason or new_reason

    def _sanitize_prefill(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(entities, dict):
            return {}
        sanitized = {}
        for key, value in entities.items():
            if key in {'password', 'token', 'secret', 'api_key', 'csrfmiddlewaretoken'}:
                continue
            if value is None or isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [item for item in value if isinstance(item, (str, int, float, bool))][:10]
        return sanitized

    def _build_business_options(
            self, task: Dict[str, Any], config: Dict[str, Any]) -> list:
        options = []
        if task.get('target_url'):
            options.append({
                'text': f"打开{task.get('title')}",
                'intent': task.get('intent_type'),
                'action': 'open_business_page',
                'target_url': task.get('target_url'),
                'open_mode': task.get('open_mode'),
                'title': task.get('title'),
                'enabled': task.get('enabled', True),
                'disabled_reason': task.get('disabled_reason'),
            })
        if config.get('list_url') and config.get('list_url') != task.get('target_url'):
            options.append({
                'text': f"打开{config.get('name')}列表",
                'intent': 'DATA_QUERY',
                'action': 'open_business_page',
                'target_url': config.get('list_url'),
                'open_mode': task.get('open_mode'),
                'title': f"{config.get('name')}列表",
                'enabled': config.get('available', True),
                'disabled_reason': config.get('unavailable_reason'),
            })
        options.append({'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel', 'enabled': True})
        return options



enhanced_intent_service = EnhancedIntentService()
