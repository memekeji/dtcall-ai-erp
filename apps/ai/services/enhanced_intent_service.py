"""
增强的意图识别服务
整合 AI 意图分类器、数据权限控制和自动化数据处理功能
"""

import logging
from typing import Dict, Any
from django.contrib.auth.models import User
from apps.ai.models import AIChat, AIChatMessage
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
        'approval': {
            'name': '审批',
            'module': '审批管理',
            'list_url': '/approval/my/',
            'create_url': '/approval/apply/',
            'edit_url_template': '/approval/{id}/process/',
            'permission_base': 'approval',
            'available': False,
            'unavailable_reason': '审批模块当前未配置统一权限节点，已阻止从 AI 直接进入写操作',
        },
        'approval_flow': {
            'name': '审批流程',
            'module': '审批管理',
            'list_url': '/approval/approvalflow/',
            'create_url': '/approval/approvalflow/add/',
            'edit_url_template': '/approval/approvalflow/{id}/edit/',
            'permission_base': 'approval_flow',
            'available': False,
            'unavailable_reason': '审批流程模块当前未配置统一权限节点，已阻止从 AI 直接进入写操作',
        },
        'approval_task': {
            'name': '待办审批',
            'module': '审批管理',
            'list_url': '/approval/pending/',
            'create_url': None,
            'edit_url_template': '/approval/{id}/process/',
            'permission_base': 'approval',
            'available': False,
            'unavailable_reason': '审批任务模块当前未配置统一权限节点，已阻止从 AI 直接进入写操作',
        },
        'task': {
            'name': '任务',
            'module': '任务管理',
            'list_url': '/task/',
            'create_url': '/task/add/',
            'edit_url_template': '/task/edit/{id}/',
            'permission_base': 'task',
        },
        'workhour': {
            'name': '工时',
            'module': '任务管理',
            'list_url': '/task/workhour/',
            'create_url': '/task/workhour/add/',
            'edit_url_template': '/task/workhour/edit/{id}/',
            'permission_base': 'workhour',
        },
        'message': {
            'name': '站内消息',
            'module': '消息中心',
            'list_url': '/message/page/',
            'create_url': None,
            'edit_url_template': None,
            'permission_base': 'message',
        },
        'notice': {
            'name': '通知公告',
            'module': '办公管理',
            'list_url': '/system/admin_office/notice/',
            'create_url': '/system/admin_office/notice/create/',
            'edit_url_template': '/system/admin_office/notice/{id}/update/',
            'permission_base': 'notice',
        },
        'meeting': {
            'name': '会议',
            'module': '办公管理',
            'list_url': '/oa/meeting/list/',
            'create_url': '/oa/meeting/apply/',
            'edit_url_template': '/oa/meeting/view/{id}/',
            'permission_base': 'meeting_record',
        },
        'schedule': {
            'name': '工作日程',
            'module': '个人办公',
            'list_url': '/oa/schedule/',
            'create_url': '/oa/schedule/add/',
            'edit_url_template': '/oa/schedule/view/{id}/',
            'permission_base': 'work_calendar',
        },
        'document': {
            'name': '文档',
            'module': '公文管理',
            'list_url': '/oa/document/view/',
            'create_url': '/oa/document/draft/add/',
            'edit_url_template': None,
            'permission_base': 'document',
            'available': False,
            'unavailable_reason': '文档模块存在多个业务入口，请先在业务页面选择具体文档类型',
        },
        'disk': {
            'name': '网盘文件',
            'module': '企业网盘',
            'list_url': '/disk/',
            'create_url': '/disk/upload/',
            'edit_url_template': '/disk/preview/{id}/',
            'permission_base': 'disk_file',
        },
        'disk_folder': {
            'name': '网盘文件夹',
            'module': '企业网盘',
            'list_url': '/disk/',
            'create_url': None,
            'edit_url_template': None,
            'permission_base': 'disk_folder',
        },
        'disk_share': {
            'name': '网盘分享',
            'module': '企业网盘',
            'list_url': '/disk/share/',
            'create_url': None,
            'edit_url_template': None,
            'permission_base': 'share',
            'available': False,
            'unavailable_reason': '网盘分享需要先定位具体文件或文件夹，已阻止直接写操作',
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

    def process_user_request(self, user: User, query: str, chat_id: int | None = None) -> Dict[str, Any]:
        """处理用户请求"""
        try:
            conversation_context = self._build_conversation_context(user, chat_id)
            intent_result = self.classifier.classify_intent(user, query)
            intent_result = self._apply_follow_up_context(intent_result, query, conversation_context)

            if not intent_result.get('intent'):
                return self._create_error_response('无法识别您的意图，请重新描述您的需求')

            if intent_result.get('source') != 'ai' and intent_result.get('intent') != 'UI_ACTION':
                return self._create_confirmation_response(intent_result, query, user)

            if self._is_mutating_intent(intent_result):
                return self._create_confirmation_response(intent_result, query, user)

            permission_result = self._check_data_permission(
                user, intent_result)
            if not permission_result['has_permission']:
                return self._create_permission_denied_response(
                    intent_result, permission_result)

            if intent_result['confidence'] < 0.65 or intent_result.get('requires_confirmation'):
                return self._create_confirmation_response(intent_result, query, user)

            execution_result = self._execute_intent(user, intent_result, query, conversation_context)

            return execution_result

        except Exception as e:
            logger.error(f"处理用户请求失败：{str(e)}")
            return self._create_error_response('处理请求时发生错误，请稍后重试')

    def _apply_follow_up_context(
            self,
            intent_result: Dict[str, Any],
            query: str,
            conversation_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        conversation_context = conversation_context or {}
        previous_query = conversation_context.get('previous_query') or {}
        query_lower = (query or '').lower()
        if not previous_query:
            return intent_result

        previous_specific_intent = previous_query.get('specific_intent')
        is_short_follow_up = len((query or '').strip()) <= 20
        mentions_time_range = any(keyword in query_lower for keyword in ['本月', '这个月', '上月', '上个月', '今天', '昨天', '昨日'])
        mentions_count = any(keyword in query_lower for keyword in ['数量', '多少', '几个', '有几个', '总数'])
        mentions_in_progress = any(keyword in query_lower for keyword in ['进行中', '在进行'])
        mentions_detail = any(keyword in query_lower for keyword in ['明细', '列表', '看一下', '看下', '展开'])
        previous_entities = dict(previous_query.get('entities') or {})
        if previous_query.get('status') and 'status' not in previous_entities:
            previous_entities['status'] = previous_query.get('status')
        if previous_query.get('time_range') and 'time_range' not in previous_entities:
            previous_entities['time_range'] = previous_query.get('time_range')

        if (
            previous_specific_intent in {'order_total', 'order_total_this_month', 'order_total_last_month'} and
            is_short_follow_up and mentions_time_range and
            intent_result.get('intent') == 'AI_CHAT'
        ):
            patched = dict(intent_result)
            patched['intent'] = 'DATA_QUERY'
            patched['action'] = 'summary'
            patched['data_type'] = 'order'
            patched['confidence'] = max(float(patched.get('confidence', 0.0) or 0.0), 0.82)
            patched['requires_confirmation'] = False
            patched['reasoning'] = '承接上一轮订单金额查询的时间范围追问'
            entities = dict(patched.get('entities') or {})
            if any(keyword in query_lower for keyword in ['本月', '这个月']):
                patched['time_range'] = 'this_month'
                entities['time_range'] = 'this_month'
            elif any(keyword in query_lower for keyword in ['上月', '上个月']):
                patched['time_range'] = 'last_month'
                entities['time_range'] = 'last_month'
            elif '今天' in query_lower:
                patched['time_range'] = 'today'
                entities['time_range'] = 'today'
            elif any(keyword in query_lower for keyword in ['昨天', '昨日']):
                patched['time_range'] = 'yesterday'
                entities['time_range'] = 'yesterday'
            patched['entities'] = entities
            return patched

        if intent_result.get('intent') == 'AI_CHAT' and is_short_follow_up:
            if previous_specific_intent in {'approval_task_list', 'approval_task_count'} and mentions_count:
                patched = dict(intent_result)
                patched['intent'] = 'DATA_QUERY'
                patched['action'] = 'count'
                patched['data_type'] = 'approval_task'
                patched['confidence'] = max(float(patched.get('confidence', 0.0) or 0.0), 0.82)
                patched['requires_confirmation'] = False
                patched['reasoning'] = '承接上一轮待审批查询的数量追问'
                patched['entities'] = previous_entities
                return patched

            if previous_specific_intent in {'project_list', 'project_count', 'project_list_in_progress', 'project_count_in_progress'}:
                patched = dict(intent_result)
                if mentions_count or mentions_in_progress:
                    patched['intent'] = 'DATA_QUERY'
                    patched['data_type'] = 'project'
                    patched['action'] = 'count' if mentions_count else 'list'
                    patched['confidence'] = max(float(patched.get('confidence', 0.0) or 0.0), 0.8)
                    patched['requires_confirmation'] = False
                    patched['reasoning'] = '承接上一轮项目查询的状态/数量追问'
                    entities = dict(previous_entities)
                    if previous_specific_intent in {'project_list_in_progress', 'project_count_in_progress'} or mentions_in_progress:
                        entities['status'] = '进行中'
                    patched['entities'] = entities
                    return patched

            if mentions_detail:
                detail_data_type = None
                if previous_specific_intent:
                    if previous_specific_intent.startswith('supplier'):
                        detail_data_type = 'supplier'
                    elif previous_specific_intent.startswith('product'):
                        detail_data_type = 'product'
                    elif previous_specific_intent.startswith('inventory'):
                        detail_data_type = 'inventory'
                    elif previous_specific_intent.startswith('followup'):
                        detail_data_type = 'followup'
                    elif previous_specific_intent.startswith('approval_task'):
                        detail_data_type = 'approval_task'
                    elif previous_specific_intent.startswith('approval'):
                        detail_data_type = 'approval'
                    elif previous_specific_intent.startswith('disk_share'):
                        detail_data_type = 'disk_share'
                    elif previous_specific_intent.startswith('disk'):
                        detail_data_type = 'disk'
                if detail_data_type:
                    patched = dict(intent_result)
                    patched['intent'] = 'DATA_QUERY'
                    patched['data_type'] = detail_data_type
                    patched['action'] = 'list'
                    patched['confidence'] = max(float(patched.get('confidence', 0.0) or 0.0), 0.8)
                    patched['requires_confirmation'] = False
                    patched['reasoning'] = '承接上一轮统计结果的明细追问'
                    patched['entities'] = previous_entities
                    return patched

        return intent_result

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
            'approval': 'approval.view_approval',
            'approval_flow': 'approval.view_approvalflow',
            'approval_task': 'approval.view_approval',
            'task': 'task.view_task',
            'workhour': 'task.view_workhour',
            'message': 'message.view_message',
            'notice': 'user.view_notice',
            'contact': 'customer.view_customer',
            'document': 'system.view_document',
            'payment': 'finance.view_payment',
            'meeting': 'oa.view_meetingrecord',
            'schedule': '__authenticated__',
            'disk': 'disk.view_disk_file',
            'disk_folder': 'disk.view_disk_folder',
            'disk_share': 'disk.view_share',
        }

        required_permission = permission_map.get(data_type)

        if not required_permission:
            return {
                'has_permission': False,
                'required_permission': 'mapped_business_permission',
                'message': f'{data_type} 类型暂未配置 AI 查询权限映射',
                'data_scope': 'forbidden'
            }

        if required_permission == '__authenticated__':
            has_permission = bool(getattr(user, 'is_authenticated', False))
        else:
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
            self, user: User, intent_result: Dict[str, Any], query: str, conversation_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
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
                return self._create_confirmation_response(intent_result, query, user)
            return self._handle_data_query(user, intent_result, query, conversation_context)

        return self._handle_data_query(user, intent_result, query, conversation_context)

    def _handle_data_query(
            self, user: User, intent_result: Dict[str, Any], query: str, conversation_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """处理数据查询"""
        try:
            result = self.query_service.process_query(
                user,
                query,
                intent_result,
                context=conversation_context,
            )

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

    def _build_conversation_context(self, user: User, chat_id: int | None) -> Dict[str, Any]:
        if not chat_id:
            return {}
        try:
            chat = AIChat.objects.get(id=chat_id, user=user)
        except AIChat.DoesNotExist:
            return {}

        previous_user_message = (
            AIChatMessage.objects.filter(chat=chat, role='user')
            .order_by('-created_at')
            .first()
        )
        previous_assistant_message = (
            AIChatMessage.objects.filter(chat=chat, role='assistant')
            .exclude(runtime_payload={})
            .order_by('-created_at')
            .first()
        )

        return {
            'previous_user_message': previous_user_message.content if previous_user_message else '',
            'previous_query': previous_assistant_message.runtime_payload if previous_assistant_message else {},
        }

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
        return self._create_confirmation_response(intent_result, query, user)

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
        return self._create_confirmation_response(intent_result, query, user)

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

            ai_intent_classifier._ensure_ai_client(force_refresh=True)
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
        ai_configured = ai_intent_classifier.ai_config is not None
        failure_reason = 'AI 模型服务暂时不可用，请稍后重试。' if ai_configured else '当前未配置可用的 AI 模型，请先完成模型配置。'
        response = (
            'AI 模型服务暂时不可用，我可以继续提供基础帮助。请稍后重试。'
            if ai_configured else
            '当前未配置可用的 AI 模型，我可以继续提供基础帮助。请配置 AI 模型后获得更准确的意图识别和自然语言理解能力。'
        )

        return {
            'success': True,
            'message': response,
            'intent_type': 'AI_CHAT',
            'result': response,
            'confidence': 0.35,
            'source': 'safe_fallback',
            'ai_available': False,
            'ai_configured': ai_configured,
            'failure_reason': failure_reason,
            'model_provider': ai_intent_classifier.ai_config.get('provider') if ai_intent_classifier.ai_config else None,
            'model_name': ai_intent_classifier.ai_config.get('model_name') if ai_intent_classifier.ai_config else None,
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
            self, intent_result: Dict[str, Any], query: str, user: User = None) -> Dict[str, Any]:
        """创建确认响应"""
        intent_type = intent_result.get('intent')
        confidence = intent_result.get('confidence', 0)
        business_task = None

        if self._is_mutating_intent(intent_result):
            business_task = self._build_business_handoff(
                user, intent_result, query) if user else self._build_unknown_business_handoff(intent_result, query)
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
                if intent_result.get('ai_configured'):
                    message = 'AI 模型服务暂时不可用，当前已按安全降级规则识别您的意图。您可以继续补充说明，或稍后再试。'
                else:
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
            'ai_available': intent_result.get('ai_available', False),
            'ai_configured': intent_result.get('ai_configured', False),
            'failure_reason': intent_result.get('failure_reason'),
            'model_provider': intent_result.get('model_provider'),
            'model_name': intent_result.get('model_name'),
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
            self, user: User, intent_result: Dict[str, Any], query: str) -> Dict[str, Any]:
        data_type = intent_result.get('data_type')
        if not data_type:
            return self._build_unknown_business_handoff(intent_result, query)

        if data_type not in self.BUSINESS_HANDOFF_CONFIG:
            return self._build_unknown_business_handoff(intent_result, query)

        config = self.BUSINESS_HANDOFF_CONFIG.get(data_type)
        if not config:
            return self._build_unknown_business_handoff(intent_result, query)

        action = self._normalize_business_action(intent_result)
        title = self._build_business_title(action, config['name'])
        target_url, disabled_reason = self._resolve_business_target_url(config, action, intent_result)
        permission = self._build_business_permission(config.get('permission_base'), action)
        entities = intent_result.get('entities') or {}
        permission_exists = self._business_permission_exists(permission)
        user_has_permission = self._user_has_business_permission(user, permission)
        disabled_reason = self._merge_disabled_reason(disabled_reason, None if permission_exists else '当前业务操作权限节点未配置，已阻止直接打开')
        disabled_reason = self._merge_disabled_reason(disabled_reason, None if user_has_permission else '您当前没有该业务操作权限')
        enabled = bool(target_url and not disabled_reason and config.get('available', True))
        safety_notice = self._get_business_safety_notice(action)
        if action in {'update', 'delete'} and target_url == config.get('list_url'):
            safety_notice = f'{safety_notice} 请先在列表中定位具体记录后再继续操作。'
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
            'permission_exists': permission_exists,
            'has_business_permission': user_has_permission,
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
            if config.get('list_url'):
                return config.get('list_url'), None
            return None, '未配置业务列表页面入口'

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

    def _business_permission_exists(self, permission: Dict[str, Any]) -> bool:
        if not permission:
            return False
        codename = permission.get('codename')
        if not codename:
            return False
        try:
            node_map = permission_node_mapper._build_node_permission_map()
            return codename in node_map
        except Exception:
            return False

    def _user_has_business_permission(self, user: User, permission: Dict[str, Any]) -> bool:
        if not permission:
            return False
        if not self._business_permission_exists(permission):
            return False
        if getattr(user, 'is_superuser', False):
            return True
        full_code = permission.get('full_code')
        codename = permission.get('codename')
        try:
            return bool(
                (full_code and user.has_perm(full_code)) or
                (codename and user.has_perm(codename))
            )
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
            option_text = f"打开{task.get('title')}"
            if task.get('action') in {'update', 'delete'} and task.get('target_url') == task.get('list_url'):
                option_text = f"打开{config.get('name')}列表并定位记录"
            options.append({
                'text': option_text,
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
