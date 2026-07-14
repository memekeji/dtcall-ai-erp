import ast
import json
import re
from datetime import date, timedelta
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from django.apps import apps
from django.utils import timezone
from django.test import RequestFactory, SimpleTestCase, TestCase


class AIModelRegistryTests(SimpleTestCase):
    def test_enhanced_workflow_models_are_registered(self):
        expected_models = {
            'WorkflowPermission',
            'AIWorkflowAuditLog',
            'WorkflowTemplate',
            'WorkflowSchedule',
            'WorkflowVersion',
            'WorkflowWebhook',
        }

        registered_models = {model.__name__ for model in apps.get_app_config('ai').get_models()}

        self.assertTrue(
            expected_models.issubset(registered_models),
            f"Missing AI enhanced models: {sorted(expected_models - registered_models)}",
        )

    def test_ai_operation_models_are_registered(self):
        expected_models = {
            'AIOperation',
            'AIOperationChangeSet',
            'AIOperationConfirmation',
            'AIOperationRollback',
        }

        registered_models = {model.__name__ for model in apps.get_app_config('ai').get_models()}

        self.assertTrue(
            expected_models.issubset(registered_models),
            f"Missing AI operation models: {sorted(expected_models - registered_models)}",
        )


class AIServiceSourceQualityTests(SimpleTestCase):
    def test_project_classes_do_not_define_duplicate_methods(self):
        apps_root = Path(__file__).parents[1]

        for source_path in apps_root.rglob('*.py'):
            tree = ast.parse(source_path.read_text(encoding='utf-8-sig'))
            for class_node in (
                node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
            ):
                method_names = [
                    node.name
                    for node in class_node.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                duplicates = sorted({name for name in method_names if method_names.count(name) > 1})

                with self.subTest(source_path=source_path, class_name=class_node.name):
                    self.assertEqual(duplicates, [])

    def test_django_settings_do_not_define_ai_model_credentials(self):
        settings_source = (Path(__file__).parents[2] / 'dtcall' / 'settings.py').read_text(encoding='utf-8')

        self.assertNotIn('OPENAI_API_KEY', settings_source)
        self.assertNotIn('OPENAI_BASE_URL', settings_source)

    def test_menu_icon_loader_does_not_request_title_based_missing_files(self):
        home_source = (Path(__file__).parents[2] / 'static' / 'js' / 'home.js').read_text(encoding='utf-8')
        template_source = (Path(__file__).parents[2] / 'templates' / 'home' / 'base.html').read_text(encoding='utf-8')

        self.assertIn('[fallbackIcon, defaultIconUrl]', home_source)
        self.assertNotIn('directPng, directSvg, fallbackIcon', home_source)
        self.assertIn('[fallbackIcon, defaultIconUrl]', template_source)
        self.assertNotIn('const rawSrc = img.getAttribute', template_source)

        icon_root = Path(__file__).parents[2] / 'static' / 'img' / 'icon'
        mapped_icons = set(re.findall(r"icon:\s*'([^']+)'", template_source))
        self.assertTrue(mapped_icons)
        self.assertEqual(
            sorted(icon for icon in mapped_icons if not (icon_root / icon).is_file()),
            [],
        )

    def test_font_awesome_consumers_load_existing_font_override(self):
        project_root = Path(__file__).parents[2]
        override_source = (project_root / 'static' / 'css' / 'dtcall-ui.css').read_text(encoding='utf-8')
        consumers = [
            project_root / 'templates' / 'home' / 'dashboard.html',
            project_root / 'templates' / 'home' / 'business_dashboard.html',
            project_root / 'templates' / 'home' / 'finance_dashboard.html',
            project_root / 'templates' / 'home' / 'production_dashboard.html',
            project_root / 'templates' / 'position' / 'new_list.html',
            project_root / 'templates' / 'position' / 'new_form.html',
        ]

        self.assertIn('../font/font-awesome/fontawesome-webfont.woff2', override_source)
        for template_path in consumers:
            with self.subTest(template=template_path):
                source = template_path.read_text(encoding='utf-8')
                self.assertIn('css/font-awesome.min.css', source)
                self.assertIn('css/dtcall-ui.css', source)


class AILegacyWritePathCompatibilityTests(SimpleTestCase):
    def test_legacy_data_assistant_returns_unified_confirmation_plan(self):
        from apps.ai.services.intelligent_assistant import IntelligentDataAssistant

        assistant = IntelligentDataAssistant(user=SimpleNamespace(id=7, is_authenticated=True))
        parsed_intent = {
            'operation': 'CREATE',
            'target': '客户',
            'data': {'name': '统一入口客户'},
        }

        with patch.object(assistant, '_ai_parse_intent', return_value=parsed_intent):
            result = assistant.process('新增客户统一入口客户')

        self.assertTrue(result['requires_confirmation'])
        self.assertEqual(result['action_plan']['resource'], 'customer')
        self.assertEqual(result['action_plan']['operation'], 'create')
        self.assertEqual(result['action_plan']['changes']['name'], '统一入口客户')
        self.assertNotIn('对应业务页面', result['message'])

    def test_legacy_data_assistant_updates_and_deletes_through_confirmation_plan(self):
        from apps.ai.services.intelligent_assistant import IntelligentDataAssistant

        assistant = IntelligentDataAssistant(user=SimpleNamespace(id=7, is_authenticated=True))
        cases = [
            ({'operation': 'UPDATE', 'target': '客户', 'object_ids': [12], 'data': {'name': '新名称'}}, 'update'),
            ({'operation': 'DELETE', 'target': '客户', 'object_ids': [12], 'data': {}}, 'delete'),
        ]

        for parsed_intent, operation in cases:
            with self.subTest(operation=operation), patch.object(
                assistant,
                '_ai_parse_intent',
                return_value=parsed_intent,
            ):
                result = assistant.process('执行操作')

            self.assertTrue(result['requires_confirmation'])
            self.assertEqual(result['action_plan']['resource'], 'customer')
            self.assertEqual(result['action_plan']['operation'], operation)


class AIRollbackUnsupportedChangeTests(SimpleTestCase):
    def test_unsupported_rollback_change_returns_structured_error(self):
        from apps.ai.services.rollback_service import rollback_service

        change_set = SimpleNamespace(
            app_label='customer',
            model_name='Customer',
            object_pk='12',
            change_type='unsupported',
            before_snapshot={},
            after_snapshot={},
            rollback_metadata={},
        )
        model = SimpleNamespace()

        with patch('apps.ai.services.rollback_service.apps.get_model', return_value=model):
            result = rollback_service._apply_change_set(change_set)

        self.assertFalse(result['success'])
        self.assertEqual(result['object_pk'], '12')
        self.assertEqual(result['error_code'], 'unsupported_change_type')

    def test_unsupported_change_does_not_mark_operation_as_rolled_back(self):
        from apps.ai.services.rollback_service import rollback_service

        user = SimpleNamespace(id=7, is_authenticated=True)
        change_set = SimpleNamespace(
            sequence=1,
            app_label='customer',
            model_name='Customer',
            object_pk='12',
            change_type='unsupported',
            before_snapshot={},
            after_snapshot={},
            rollback_metadata={},
        )
        operation = SimpleNamespace(
            id=901,
            status='executed',
            rollback_status='',
            change_sets=SimpleNamespace(all=lambda: [change_set]),
            save=MagicMock(),
        )
        rollback_record = SimpleNamespace(
            id=902,
            status='pending',
            error_message='',
            completed_at=None,
            save=MagicMock(),
        )

        with patch('apps.ai.services.rollback_service.AIOperation.objects.get', return_value=operation), \
                patch('apps.ai.services.rollback_service.AIOperationRollback.objects.create', return_value=rollback_record), \
                patch('apps.ai.services.rollback_service.apps.get_model', return_value=SimpleNamespace()), \
                patch('apps.ai.services.rollback_service.transaction.atomic'):
            result = rollback_service.rollback_operation(operation_id=901, user=user)

        self.assertFalse(result['success'])
        self.assertEqual(operation.status, 'executed')
        operation.save.assert_not_called()
        self.assertEqual(rollback_record.status, 'failed')


class AIExecutionContractTests(SimpleTestCase):
    def test_action_request_normalizes_defaults(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
        except ModuleNotFoundError:
            self.fail('apps.ai.services.action_contracts.AIActionRequest is missing')

        request = AIActionRequest(
            resource='customer',
            operation='update',
            changes={'name': '新客户名称'},
        )

        self.assertEqual(request.resource, 'customer')
        self.assertEqual(request.operation, 'update')
        self.assertEqual(request.object_ids, [])
        self.assertEqual(request.filters, {})
        self.assertEqual(request.context, {})
        self.assertEqual(request.changes, {'name': '新客户名称'})

    def test_module_registry_rejects_unknown_resource(self):
        try:
            from apps.ai.services.action_gateway import AIActionGateway
        except ModuleNotFoundError:
            self.fail('apps.ai.services.action_gateway.AIActionGateway is missing')

        gateway = AIActionGateway()

        with self.assertRaisesMessage(KeyError, 'No AI module adapter registered for resource: unknown'):
            gateway.get_adapter('unknown')


class AIPermissionGuardTests(SimpleTestCase):
    def test_guard_denies_when_permission_checker_fails(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.permission_guard import AIPermissionGuard
        except ModuleNotFoundError as exc:
            self.fail(f'Missing AI permission guard dependency: {exc}')

        user = SimpleNamespace(is_authenticated=True, is_superuser=False, has_perm=lambda perm: False)
        action = AIActionRequest(resource='customer', operation='update', object_ids=[1])

        result = AIPermissionGuard().check_action_permission(
            user,
            action,
            permission_code='customer.change_customer',
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, 'missing_permission')

    def test_guard_allows_when_checker_passes_without_queryset(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.permission_guard import AIPermissionGuard
        except ModuleNotFoundError as exc:
            self.fail(f'Missing AI permission guard dependency: {exc}')

        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm == 'customer.view_customer',
        )
        action = AIActionRequest(resource='customer', operation='query')

        result = AIPermissionGuard().check_action_permission(
            user,
            action,
            permission_code='customer.view_customer',
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, 'allowed')

    def test_guard_uses_exact_permission_for_non_user_app_codes(self):
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.permission_guard import AIPermissionGuard

        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm == 'system.change_document',
        )
        action = AIActionRequest(resource='document', operation='update', object_ids=[1])

        result = AIPermissionGuard().check_action_permission(
            user,
            action,
            permission_code='system.change_document',
        )

        self.assertTrue(result.allowed)


class AIQueryServicePermissionMappingTests(SimpleTestCase):
    def test_specialized_query_intents_inherit_exact_resource_permissions(self):
        from apps.ai.services.query_service import QueryService

        intent_permissions = {
            'contract_count_effective': 'contract.view_contract',
            'contract_count_expired': 'contract.view_contract',
            'contract_total': 'contract.view_contract',
            'customer_count_deal': 'customer.view_customer',
            'customer_count_potential': 'customer.view_customer',
            'customer_deal_last_month': 'customer.view_customer',
            'customer_deal_this_month': 'customer.view_customer',
            'customer_detail': 'customer.view_customer',
            'customer_list_deal': 'customer.view_customer',
            'customer_list_potential': 'customer.view_customer',
            'employee_count_active': 'user.view_employeefile',
            'employee_count_inactive': 'user.view_employeefile',
            'invoice_count_issued': 'customer.view_customerinvoice',
            'invoice_count_unissued': 'customer.view_customerinvoice',
            'order_count_completed': 'customer.view_customerorder',
            'order_count_in_progress': 'customer.view_customerorder',
            'order_total': 'customer.view_customerorder',
            'order_total_last_month': 'customer.view_customerorder',
            'order_total_this_month': 'customer.view_customerorder',
            'project_count_completed': 'project.view_project',
            'project_count_in_progress': 'project.view_project',
            'project_count_paused': 'project.view_project',
            'project_list_completed': 'project.view_project',
            'project_list_in_progress': 'project.view_project',
            'project_progress': 'project.view_project',
        }
        service = QueryService()

        for intent, expected_permission in intent_permissions.items():
            with self.subTest(intent=intent):
                allowed_user = SimpleNamespace(
                    username='allowed-query-user',
                    is_authenticated=True,
                    is_superuser=False,
                    has_perm=lambda permission, expected=expected_permission: permission == expected,
                )
                denied_user = SimpleNamespace(
                    username='denied-query-user',
                    is_authenticated=True,
                    is_superuser=False,
                    has_perm=lambda permission: False,
                )

                self.assertTrue(service.check_permission(allowed_user, intent))
                self.assertFalse(service.check_permission(denied_user, intent))

    def test_ai_center_query_permissions_follow_menu_permissions(self):
        from apps.ai.services.query_service import QueryService

        allowed_permissions = {
            'user.view_model_config',
            'user.view_knowledge_base',
            'user.view_ai_task',
            'user.view_ai_workflow',
        }
        user = SimpleNamespace(
            username='ai-center-query-user',
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in allowed_permissions,
        )
        service = QueryService()

        self.assertTrue(service.check_permission(user, 'ai_model_config_list'))
        self.assertTrue(service.check_permission(user, 'ai_knowledge_base_list'))
        self.assertTrue(service.check_permission(user, 'ai_task_list'))
        self.assertTrue(service.check_permission(user, 'ai_workflow_list'))

    def test_supply_chain_query_permissions_follow_menu_permissions(self):
        from apps.ai.services.query_service import QueryService

        allowed_permissions = {
            'user.view_supply_chain_forecast',
            'user.view_supply_chain_outsource',
            'user.view_supply_chain_pr_review',
            'user.view_supply_chain_price_review',
            'user.view_supply_chain_sample',
        }
        user = SimpleNamespace(
            username='supply-chain-query-user',
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in allowed_permissions,
        )
        service = QueryService()

        self.assertTrue(service.check_permission(user, 'supply_chain_forecast_list'))
        self.assertTrue(service.check_permission(user, 'supply_chain_outsource_list'))
        self.assertTrue(service.check_permission(user, 'supply_chain_pr_review_list'))
        self.assertTrue(service.check_permission(user, 'supply_chain_price_review_list'))
        self.assertTrue(service.check_permission(user, 'supply_chain_sample_list'))

    def test_advanced_finance_query_permissions_follow_model_permissions(self):
        from apps.ai.services.query_service import QueryService

        allowed_permissions = {
            'finance.view_financeaccount',
            'finance.view_financebudget',
            'finance.view_accountsreceivable',
            'finance.view_accountspayable',
            'finance.view_banktransaction',
        }
        user = SimpleNamespace(
            username='finance-query-user',
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in allowed_permissions,
        )
        service = QueryService()

        self.assertTrue(service.check_permission(user, 'finance_account_list'))
        self.assertTrue(service.check_permission(user, 'finance_budget_list'))
        self.assertTrue(service.check_permission(user, 'finance_receivable_list'))
        self.assertTrue(service.check_permission(user, 'finance_payable_list'))
        self.assertTrue(service.check_permission(user, 'finance_bank_transaction_list'))

    def test_admin_office_query_permissions_follow_menu_nodes(self):
        from apps.ai.services.query_service import QueryService

        allowed_permissions = {
            'user.view_asset',
            'user.view_asset_repair',
            'user.view_document_category',
            'user.view_vehicle_info',
            'user.view_vehicle_maintenance',
            'user.view_vehicle_fee',
            'user.view_vehicle_oil',
            'user.view_meeting_room',
            'user.view_meeting_minutes',
            'user.view_seal_management',
            'user.view_seal_application',
        }
        user = SimpleNamespace(
            username='office-query-user',
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in allowed_permissions,
        )
        service = QueryService()

        self.assertTrue(service.check_permission(user, 'asset_list'))
        self.assertTrue(service.check_permission(user, 'asset_category_list'))
        self.assertTrue(service.check_permission(user, 'asset_brand_list'))
        self.assertTrue(service.check_permission(user, 'asset_repair_list'))
        self.assertTrue(service.check_permission(user, 'document_category_list'))
        self.assertTrue(service.check_permission(user, 'vehicle_list'))
        self.assertTrue(service.check_permission(user, 'vehicle_maintenance_list'))
        self.assertTrue(service.check_permission(user, 'vehicle_fee_list'))
        self.assertTrue(service.check_permission(user, 'vehicle_oil_list'))
        self.assertTrue(service.check_permission(user, 'meeting_room_list'))
        self.assertTrue(service.check_permission(user, 'meeting_minutes_list'))
        self.assertTrue(service.check_permission(user, 'meeting_reservation_list'))
        self.assertTrue(service.check_permission(user, 'seal_list'))
        self.assertTrue(service.check_permission(user, 'seal_application_list'))

    def test_hr_and_production_detail_query_permissions_follow_menu_nodes(self):
        from apps.ai.services.query_service import QueryService

        allowed_permissions = {
            'user.view_reward_punishment',
            'user.view_employee_care',
            'user.view_procedureset',
            'user.view_bom',
            'user.view_process',
            'user.view_quality_check',
            'user.view_datacollection',
        }
        user = SimpleNamespace(
            username='hr-production-detail-query-user',
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in allowed_permissions,
        )
        service = QueryService()

        self.assertTrue(service.check_permission(user, 'reward_punishment_list'))
        self.assertTrue(service.check_permission(user, 'employee_care_list'))
        self.assertTrue(service.check_permission(user, 'procedureset_list'))
        self.assertTrue(service.check_permission(user, 'bom_list'))
        self.assertTrue(service.check_permission(user, 'process_list'))
        self.assertTrue(service.check_permission(user, 'quality_check_list'))
        self.assertTrue(service.check_permission(user, 'datacollection_list'))

    def test_approval_detail_query_permissions_follow_model_nodes(self):
        from apps.ai.services.query_service import QueryService

        allowed_permissions = {
            'approval.view_approvaltype',
            'approval.view_approvalstep',
            'approval.view_approvalrecord',
            'approval.view_approvalflowedge',
        }
        user = SimpleNamespace(
            username='approval-detail-query-user',
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in allowed_permissions,
        )
        service = QueryService()

        self.assertTrue(service.check_permission(user, 'approval_type_list'))
        self.assertTrue(service.check_permission(user, 'approval_step_list'))
        self.assertTrue(service.check_permission(user, 'approval_record_list'))
        self.assertTrue(service.check_permission(user, 'approval_flow_edge_list'))


class AIRollbackServiceTests(SimpleTestCase):
    def test_rollback_plan_reverses_change_set_order(self):
        try:
            from apps.ai.services.rollback_service import build_rollback_plan
        except ModuleNotFoundError:
            self.fail('apps.ai.services.rollback_service.build_rollback_plan is missing')

        change_set = [
            SimpleNamespace(sequence=1, change_type='create', object_pk='1'),
            SimpleNamespace(sequence=2, change_type='update', object_pk='2'),
            SimpleNamespace(sequence=3, change_type='delete', object_pk='3'),
        ]

        rollback_plan = build_rollback_plan(change_set)

        self.assertEqual([item.object_pk for item in rollback_plan], ['3', '2', '1'])

    def test_rollback_step_uses_inverse_change_type(self):
        try:
            from apps.ai.services.rollback_service import RollbackStep, inverse_change_type
        except ModuleNotFoundError as exc:
            self.fail(f'Missing rollback dependency: {exc}')

        self.assertEqual(inverse_change_type('create'), 'delete')
        self.assertEqual(inverse_change_type('update'), 'restore')
        self.assertEqual(inverse_change_type('delete'), 'recreate')

        step = RollbackStep(
            sequence=3,
            app_label='customer',
            model_name='Customer',
            object_pk='8',
            forward_change_type='delete',
            rollback_change_type=inverse_change_type('delete'),
            before_snapshot={'id': 8, 'name': 'A'},
            after_snapshot=None,
        )

        self.assertEqual(asdict(step)['rollback_change_type'], 'recreate')

    def test_apply_customer_update_rollback_restores_before_snapshot(self):
        try:
            from apps.ai.services.rollback_service import rollback_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.rollback_service.rollback_service is missing')

        customer = SimpleNamespace(
            id=12,
            name='新名称',
            address='新地址',
            save=MagicMock(),
        )
        change_set = SimpleNamespace(
            sequence=1,
            app_label='customer',
            model_name='Customer',
            object_pk='12',
            change_type='update',
            before_snapshot={'name': '旧名称', 'address': '旧地址'},
            after_snapshot={'name': '新名称', 'address': '新地址'},
            changed_fields=['name', 'address'],
            is_rollback_supported=True,
        )
        operation = SimpleNamespace(
            id=77,
            status='executed',
            change_sets=SimpleNamespace(all=lambda: [change_set]),
            save=MagicMock(),
        )

        with patch('apps.ai.services.rollback_service.AIOperation.objects.get', return_value=operation), \
                patch('apps.ai.services.rollback_service.AIOperationRollback.objects.create'), \
                patch('apps.ai.services.rollback_service.build_rollback_plan', return_value=[change_set]), \
                patch('apps.ai.services.rollback_service.apps.get_model') as get_model, \
                patch('apps.ai.services.rollback_service.transaction.atomic'):
            get_model.return_value = MagicMock(objects=MagicMock(get=MagicMock(return_value=customer)))

            result = rollback_service.rollback_operation(operation_id=77, user=SimpleNamespace(id=7))

        self.assertTrue(result['success'])
        self.assertEqual(customer.name, '旧名称')
        self.assertEqual(customer.address, '旧地址')
        self.assertEqual(operation.status, 'rolled_back')
        customer.save.assert_called_once()
        operation.save.assert_called_once()

    def test_apply_customer_create_rollback_deletes_created_record(self):
        try:
            from apps.ai.services.rollback_service import rollback_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.rollback_service.rollback_service is missing')

        customer = SimpleNamespace(
            id=15,
            delete=MagicMock(),
        )
        change_set = SimpleNamespace(
            sequence=1,
            app_label='customer',
            model_name='Customer',
            object_pk='15',
            change_type='create',
            before_snapshot=None,
            after_snapshot={'id': 15, 'name': '新客户'},
            changed_fields=['name'],
            is_rollback_supported=True,
        )
        operation = SimpleNamespace(
            id=78,
            status='executed',
            change_sets=SimpleNamespace(all=lambda: [change_set]),
            save=MagicMock(),
        )

        with patch('apps.ai.services.rollback_service.AIOperation.objects.get', return_value=operation), \
                patch('apps.ai.services.rollback_service.AIOperationRollback.objects.create'), \
                patch('apps.ai.services.rollback_service.build_rollback_plan', return_value=[change_set]), \
                patch('apps.ai.services.rollback_service.apps.get_model') as get_model, \
                patch('apps.ai.services.rollback_service.transaction.atomic'):
            get_model.return_value = MagicMock(objects=MagicMock(get=MagicMock(return_value=customer)))

            result = rollback_service.rollback_operation(operation_id=78, user=SimpleNamespace(id=7))

        self.assertTrue(result['success'])
        customer.delete.assert_called_once()
        self.assertEqual(operation.status, 'rolled_back')

    def test_apply_soft_delete_create_rollback_prefers_hard_delete(self):
        try:
            from apps.ai.services.rollback_service import rollback_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.rollback_service.rollback_service is missing')

        record = SimpleNamespace(
            id=25,
            delete=MagicMock(),
            hard_delete=MagicMock(),
        )
        change_set = SimpleNamespace(
            sequence=1,
            app_label='oa',
            model_name='MeetingRecord',
            object_pk='25',
            change_type='create',
            before_snapshot=None,
            after_snapshot={'id': 25, 'title': '项目例会'},
            changed_fields=['title'],
            is_rollback_supported=True,
        )
        operation = SimpleNamespace(
            id=780,
            status='executed',
            change_sets=SimpleNamespace(all=lambda: [change_set]),
            save=MagicMock(),
        )

        with patch('apps.ai.services.rollback_service.AIOperation.objects.get', return_value=operation), \
                patch('apps.ai.services.rollback_service.AIOperationRollback.objects.create'), \
                patch('apps.ai.services.rollback_service.build_rollback_plan', return_value=[change_set]), \
                patch('apps.ai.services.rollback_service.apps.get_model') as get_model, \
                patch('apps.ai.services.rollback_service.transaction.atomic'):
            get_model.return_value = MagicMock(objects=MagicMock(get=MagicMock(return_value=record)))

            result = rollback_service.rollback_operation(operation_id=780, user=SimpleNamespace(id=7))

        self.assertTrue(result['success'])
        record.hard_delete.assert_called_once()
        record.delete.assert_not_called()

    def test_apply_customer_delete_rollback_restores_soft_deleted_record(self):
        try:
            from apps.ai.services.rollback_service import rollback_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.rollback_service.rollback_service is missing')

        customer = SimpleNamespace(
            id=16,
            delete_time=123456,
            belong_uid=0,
            belong_did=0,
            share_ids='',
            save=MagicMock(),
        )
        change_set = SimpleNamespace(
            sequence=1,
            app_label='customer',
            model_name='Customer',
            object_pk='16',
            change_type='delete',
            before_snapshot={'delete_time': 0, 'belong_uid': 7, 'belong_did': 3, 'share_ids': '7,8'},
            after_snapshot={'delete_time': 123456, 'belong_uid': 0, 'belong_did': 0, 'share_ids': ''},
            changed_fields=['delete_time', 'belong_uid', 'belong_did', 'share_ids'],
            is_rollback_supported=True,
        )
        operation = SimpleNamespace(
            id=79,
            status='executed',
            change_sets=SimpleNamespace(all=lambda: [change_set]),
            save=MagicMock(),
        )

        with patch('apps.ai.services.rollback_service.AIOperation.objects.get', return_value=operation), \
                patch('apps.ai.services.rollback_service.AIOperationRollback.objects.create'), \
                patch('apps.ai.services.rollback_service.build_rollback_plan', return_value=[change_set]), \
                patch('apps.ai.services.rollback_service.apps.get_model') as get_model, \
                patch('apps.ai.services.rollback_service.transaction.atomic'):
            get_model.return_value = MagicMock(objects=MagicMock(get=MagicMock(return_value=customer)))

            result = rollback_service.rollback_operation(operation_id=79, user=SimpleNamespace(id=7))

        self.assertTrue(result['success'])
        self.assertEqual(customer.delete_time, 0)
        self.assertEqual(customer.belong_uid, 7)
        self.assertEqual(customer.belong_did, 3)
        self.assertEqual(customer.share_ids, '7,8')

    def test_rollback_operation_scopes_to_request_user(self):
        from apps.ai.services.rollback_service import rollback_service

        user = SimpleNamespace(id=7, is_authenticated=True)
        operation = SimpleNamespace(
            id=77,
            status='executed',
            change_sets=SimpleNamespace(all=lambda: []),
            save=MagicMock(),
        )
        rollback_record = SimpleNamespace(
            id=1,
            status='pending',
            result_summary={},
            error_message='',
            completed_at=None,
            save=MagicMock(),
        )

        with patch('apps.ai.services.rollback_service.AIOperation.objects.get', return_value=operation) as get_operation, \
                patch('apps.ai.services.rollback_service.AIOperationRollback.objects.create', return_value=rollback_record), \
                patch('apps.ai.services.rollback_service.transaction.atomic'):
            result = rollback_service.rollback_operation(operation_id=77, user=user)

        self.assertTrue(result['success'])
        get_operation.assert_called_once_with(id=77, user=user)

    def test_rollback_operation_rejects_an_operation_that_was_already_rolled_back(self):
        from apps.ai.services.rollback_service import rollback_service

        user = SimpleNamespace(id=7, is_authenticated=True)
        operation = SimpleNamespace(
            id=77,
            status='rolled_back',
            rollback_status='completed',
            change_sets=SimpleNamespace(all=lambda: []),
            save=MagicMock(),
        )
        rollback_record = SimpleNamespace(
            id=2,
            status='pending',
            result_summary={},
            completed_at=None,
            save=MagicMock(),
        )

        with patch('apps.ai.services.rollback_service.AIOperation.objects.get', return_value=operation), \
                patch(
                    'apps.ai.services.rollback_service.AIOperationRollback.objects.create',
                    return_value=rollback_record,
                ) as create_rollback, \
                patch('apps.ai.services.rollback_service.transaction.atomic'):
            result = rollback_service.rollback_operation(operation_id=77, user=user)

        self.assertFalse(result['success'])
        self.assertIn('已回退', result['message'])
        create_rollback.assert_not_called()


class AIChatExecutionPayloadTests(SimpleTestCase):
    def test_chat_payload_includes_action_plan_for_confirmable_write(self):
        from apps.ai.views import AIChatStreamView

        user = SimpleNamespace(is_authenticated=True, id=9)
        request = SimpleNamespace(session={})

        intent_result = {
            'success': True,
            'intent_type': 'data_update',
            'message': '准备更新客户名称，请确认后执行。',
            'result': '',
            'confidence': 0.92,
            'requires_confirmation': True,
            'action': 'update',
            'data_type': 'customer',
            'entities': {'object_ids': [12], 'changes': {'name': '上海壹号客户'}},
        }

        with patch('apps.ai.services.intent_recognition_service.intent_recognition_service.process_request', return_value=intent_result), \
                patch('apps.ai.services.operation_service.AIOperation.objects.create', return_value=SimpleNamespace(id=55, confirmation_token='token-55')), \
                patch('apps.ai.services.operation_service.AIOperationConfirmation.objects.create'), \
                patch.object(
                    AIChatStreamView,
                    'save_chat_record',
                    return_value=(SimpleNamespace(id=1), SimpleNamespace(id=2), SimpleNamespace(id=3, runtime_payload={}, save=lambda **kwargs: None)),
                ):
            payload = AIChatStreamView()._build_intent_response_payload(
                user,
                chat_id=None,
                message='把客户12改成上海壹号客户',
                request=request,
            )

        self.assertEqual(payload['ai_message'], '准备更新客户名称，请确认后执行。')
        self.assertTrue(payload['requires_confirmation'])
        self.assertEqual(payload['action_plan']['resource'], 'customer')
        self.assertEqual(payload['action_plan']['operation'], 'update')
        self.assertEqual(payload['action_plan']['object_ids'], [12])
        self.assertEqual(payload['action_plan']['changes'], {'name': '上海壹号客户'})
        self.assertTrue(payload['confirmation']['required'])
        self.assertEqual(payload['confirmation']['message'], '准备更新客户名称，请确认后执行。')

    def test_chat_payload_persists_preview_operation_for_confirmable_write(self):
        from apps.ai.views import AIChatStreamView

        user = SimpleNamespace(is_authenticated=True, id=9)
        request = SimpleNamespace(session={})

        intent_result = {
            'success': True,
            'intent_type': 'data_update',
            'message': '准备更新客户名称，请确认后执行。',
            'result': '',
            'confidence': 0.92,
            'requires_confirmation': True,
            'action': 'update',
            'data_type': 'customer',
            'entities': {'object_ids': [12], 'changes': {'name': '上海壹号客户'}},
        }

        operation_record = SimpleNamespace(id=88, confirmation_token='token-88')

        with patch('apps.ai.services.intent_recognition_service.intent_recognition_service.process_request', return_value=intent_result), \
                patch.object(
                    AIChatStreamView,
                    'save_chat_record',
                    return_value=(SimpleNamespace(id=1), SimpleNamespace(id=2), SimpleNamespace(id=3, runtime_payload={}, save=lambda **kwargs: None)),
                ), \
                patch(
                    'apps.ai.views.AIChatStreamView._create_operation_preview',
                    return_value=operation_record,
                ) as create_preview:
            payload = AIChatStreamView()._build_intent_response_payload(
                user,
                chat_id=None,
                message='把客户12改成上海壹号客户',
                request=request,
            )

        create_preview.assert_called_once()
        self.assertEqual(payload['operation_id'], 88)
        self.assertEqual(payload['confirmation']['token'], 'token-88')

    def test_chat_payload_persists_recognition_metadata_for_history_rendering(self):
        from apps.ai.views import AIChatStreamView

        user = SimpleNamespace(is_authenticated=True, id=9)
        request = SimpleNamespace(session={})
        ai_message = SimpleNamespace(
            id=3,
            runtime_payload={},
            created_at=None,
            save=MagicMock(),
        )

        intent_result = {
            'success': True,
            'intent_type': 'DATA_QUERY',
            'message': '已按安全降级规则识别为待审批查询。',
            'result': '已按安全降级规则识别为待审批查询。',
            'confidence': 0.58,
            'requires_confirmation': True,
            'action': 'list',
            'data_type': 'approval_task',
            'entities': {},
            'source': 'safe_fallback',
            'ai_available': False,
            'ai_configured': True,
            'failure_reason': 'AI 模型暂时不可用',
            'model_provider': 'openai',
            'model_name': 'gpt-5.4',
        }

        with patch('apps.ai.services.intent_recognition_service.intent_recognition_service.process_request', return_value=intent_result), \
                patch.object(
                    AIChatStreamView,
                    'save_chat_record',
                    return_value=(SimpleNamespace(id=1), SimpleNamespace(id=2), ai_message),
                ), \
                patch.object(
                    AIChatStreamView,
                    '_create_operation_preview',
                    return_value=None,
                ):
            payload = AIChatStreamView()._build_intent_response_payload(
                user,
                chat_id=None,
                message='看一下我的待审批流程',
                request=request,
            )

        self.assertEqual(payload['recognition_meta']['source'], 'safe_fallback')
        self.assertEqual(payload['recognition_meta']['source_label'], '规则降级')
        self.assertEqual(payload['recognition_meta']['status_label'], '模型不可用')
        self.assertEqual(ai_message.runtime_payload['recognition_meta']['source'], 'safe_fallback')
        self.assertEqual(ai_message.runtime_payload['recognition_meta']['failure_reason'], 'AI 模型暂时不可用')

    def test_chat_payload_confirms_latest_preview_operation_from_natural_language(self):
        from apps.ai.views import AIChatStreamView

        user = SimpleNamespace(is_authenticated=True, id=9)
        request = SimpleNamespace(session={})
        ai_message = SimpleNamespace(
            id=13,
            runtime_payload={},
            created_at=None,
            save=MagicMock(),
        )
        pending_operation = SimpleNamespace(
            id=401,
            confirmation_token='token-401',
            resource_type='approval',
            operation_type='create',
            ai_message=SimpleNamespace(
                runtime_payload={
                    'task': {
                        'type': 'business_handoff',
                        'title': '请假申请',
                        'module': '审批管理',
                        'data_type': 'approval',
                        'action': 'create',
                    }
                }
            ),
        )

        with patch('apps.ai.views.operation_service.match_pending_operation_command', return_value='confirm'), \
                patch('apps.ai.views.operation_service.get_latest_preview_operation', return_value=pending_operation), \
                patch(
                    'apps.ai.views.operation_service.confirm_operation',
                    return_value={
                        'success': True,
                        'message': '请假申请已创建',
                        'operation_id': 401,
                        'gateway_result': {
                            'change_set': [{'object_pk': '88'}],
                        },
                    },
                ) as confirm_operation, \
                patch('apps.ai.services.intent_recognition_service.intent_recognition_service.process_request') as process_request, \
                patch.object(
                    AIChatStreamView,
                    'save_chat_record',
                    return_value=(SimpleNamespace(id=1), SimpleNamespace(id=2), ai_message),
                ):
            payload = AIChatStreamView()._build_intent_response_payload(
                user,
                chat_id=3,
                message='确认',
                request=request,
            )

        process_request.assert_not_called()
        confirm_operation.assert_called_once_with(
            operation_id=401,
            token='token-401',
            user=user,
        )
        self.assertTrue(payload['success'])
        self.assertEqual(payload['task']['operation_id'], 401)
        self.assertTrue(payload['task']['can_rollback'])
        self.assertEqual(payload['options'][0]['action'], 'rollback_operation')

    def test_chat_payload_cancels_latest_preview_operation_from_natural_language(self):
        from apps.ai.views import AIChatStreamView

        user = SimpleNamespace(is_authenticated=True, id=9)
        request = SimpleNamespace(session={})
        ai_message = SimpleNamespace(
            id=14,
            runtime_payload={},
            created_at=None,
            save=MagicMock(),
        )
        pending_operation = SimpleNamespace(
            id=402,
            confirmation_token='token-402',
            resource_type='approval',
            operation_type='create',
            ai_message=SimpleNamespace(runtime_payload={}),
        )

        with patch('apps.ai.views.operation_service.match_pending_operation_command', return_value='cancel'), \
                patch('apps.ai.views.operation_service.get_latest_preview_operation', return_value=pending_operation), \
                patch(
                    'apps.ai.views.operation_service.cancel_operation',
                    return_value={
                        'success': True,
                        'message': '已取消上一步待确认操作，本次不会写入任何数据。',
                        'operation_id': 402,
                    },
                ) as cancel_operation, \
                patch('apps.ai.services.intent_recognition_service.intent_recognition_service.process_request') as process_request, \
                patch.object(
                    AIChatStreamView,
                    'save_chat_record',
                    return_value=(SimpleNamespace(id=1), SimpleNamespace(id=2), ai_message),
                ):
            payload = AIChatStreamView()._build_intent_response_payload(
                user,
                chat_id=3,
                message='不要了',
                request=request,
            )

        process_request.assert_not_called()
        cancel_operation.assert_called_once_with(
            operation_id=402,
            token='token-402',
            user=user,
        )
        self.assertTrue(payload['success'])
        self.assertEqual(payload['message'], '已取消上一步待确认操作，本次不会写入任何数据。')
        self.assertEqual(payload.get('options'), [])

    def test_chat_payload_rolls_back_latest_executed_operation_from_natural_language(self):
        from apps.ai.views import AIChatStreamView

        user = SimpleNamespace(is_authenticated=True, id=9)
        request = SimpleNamespace(session={})
        ai_message = SimpleNamespace(
            id=15,
            runtime_payload={},
            created_at=None,
            save=MagicMock(),
        )
        executed_operation = SimpleNamespace(
            id=403,
            resource_type='approval',
            operation_type='create',
            ai_message=SimpleNamespace(
                runtime_payload={
                    'task': {
                        'type': 'business_handoff',
                        'title': '请假申请',
                        'module': '审批管理',
                        'data_type': 'approval',
                        'action': 'create',
                    }
                }
            ),
        )

        with patch('apps.ai.views.operation_service.match_pending_operation_command', return_value='rollback'), \
                patch('apps.ai.views.operation_service.get_latest_executed_operation', return_value=executed_operation), \
                patch(
                    'apps.ai.views.rollback_service.rollback_operation',
                    return_value={
                        'success': True,
                        'message': '已回退本次操作',
                        'operation_id': 403,
                    },
                ) as rollback_operation, \
                patch('apps.ai.services.intent_recognition_service.intent_recognition_service.process_request') as process_request, \
                patch.object(
                    AIChatStreamView,
                    'save_chat_record',
                    return_value=(SimpleNamespace(id=1), SimpleNamespace(id=2), ai_message),
                ):
            payload = AIChatStreamView()._build_intent_response_payload(
                user,
                chat_id=3,
                message='回退刚才的操作',
                request=request,
            )

        process_request.assert_not_called()
        rollback_operation.assert_called_once_with(403, user)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['task']['execution_status'], 'rolled_back')
        self.assertEqual(payload.get('options'), [])


class AIChatStreamingResponseTests(SimpleTestCase):
    def test_openai_client_stream_chat_completion_yields_delta_chunks(self):
        from apps.ai.utils.ai_client import OpenAIClient

        client = OpenAIClient(
            base_url='https://api.openai.com/v1',
            api_key='sk-test',
            model_config={'chat': 'gpt-5.5'},
        )
        client._ensure_client = MagicMock(return_value=True)
        client.client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=MagicMock(return_value=[
                        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='你'))]),
                        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='好'))]),
                        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]),
                    ])
                )
            )
        )

        chunks = list(client.stream_chat_completion([
            {'role': 'user', 'content': '你好'}
        ]))

        self.assertEqual(chunks, ['你', '好'])

    def test_stream_user_request_does_not_reclassify_non_ai_requests(self):
        from apps.ai.services.enhanced_intent_service import enhanced_intent_service

        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            pk=7,
            has_perm=lambda perm: True,
        )
        intent_result = {
            'intent': 'DATA_QUERY',
            'confidence': 0.92,
            'action': 'list',
            'data_type': 'customer',
            'entities': {},
            'requires_confirmation': False,
            'source': 'ai',
            'ai_available': True,
            'ai_configured': True,
            'model_provider': 'openai',
            'model_name': 'gpt-5.5',
        }

        with patch.object(
            enhanced_intent_service.classifier,
            'classify_intent',
            return_value=intent_result,
        ) as classify_intent, \
                patch.object(
                    enhanced_intent_service.query_service,
                    'process_query',
                    return_value={'success': True, 'result': 'ok', 'specific_intent': 'customer_list'},
                ):
            events = list(enhanced_intent_service.stream_user_request(user, '查一下客户', chat_id=None))

        self.assertEqual(classify_intent.call_count, 1)
        self.assertEqual(events[-1]['type'], 'done')

    def test_stream_user_request_keeps_successful_ai_chat_when_model_stream_succeeds(self):
        from apps.ai.services.enhanced_intent_service import enhanced_intent_service
        from apps.ai.services.ai_intent_classifier import ai_intent_classifier

        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=True,
            pk=7,
            has_perm=lambda perm: True,
        )
        intent_result = {
            'intent': 'AI_CHAT',
            'confidence': 0.96,
            'source': 'ai',
            'ai_available': True,
            'ai_configured': True,
            'model_provider': 'openai',
            'model_name': 'gpt-5.5',
        }
        ai_client = SimpleNamespace(
            stream_chat_completion=MagicMock(return_value=iter(['上游', '成功']))
        )

        with patch.object(
            enhanced_intent_service.classifier,
            'classify_intent',
            return_value=intent_result,
        ), patch.object(
            ai_intent_classifier,
            '_ensure_ai_client',
        ), patch.object(
            ai_intent_classifier,
            'ai_config',
            {'provider': 'openai', 'model_name': 'gpt-5.5'},
        ), patch.object(
            ai_intent_classifier,
            'ai_client',
            ai_client,
        ):
            events = list(enhanced_intent_service.stream_user_request(user, '帮我解释一下当前页面', chat_id=None))

        self.assertEqual([event['type'] for event in events], ['chunk', 'chunk', 'done'])
        self.assertEqual(''.join(event.get('content', '') for event in events), '上游成功')
        payload = events[-1]['payload']
        self.assertEqual(payload['source'], 'ai')
        self.assertTrue(payload['ai_available'])
        self.assertNotEqual(payload.get('source'), 'safe_fallback')
        self.assertEqual(payload['message'], '上游成功')

    def test_generate_streaming_response_emits_thinking_chunk_and_done_events(self):
        from apps.ai.views import AIChatStreamView

        view = AIChatStreamView()
        payload = {
            'success': True,
            'ai_message': '你好，世界',
            'message': '你好，世界',
            'chat_id': 3,
            'options': [],
        }

        stream_text = ''.join(view.generate_streaming_response(payload))

        self.assertIn('event: thinking', stream_text)
        self.assertIn('正在思考....', stream_text)
        self.assertIn('event: chunk', stream_text)
        self.assertIn('event: done', stream_text)
        self.assertIn('"chat_id": 3', stream_text)

    def test_stream_view_returns_streaming_http_response(self):
        from apps.ai.views import AIChatStreamView
        from django.http import StreamingHttpResponse

        factory = RequestFactory()
        request = factory.post('/ai/chat/stream/', data={'chat_id': 5, 'message': '你好'})
        request.user = SimpleNamespace(is_authenticated=True, id=7)
        request.session = {}

        with patch.object(
            AIChatStreamView,
            '_stream_chat_events',
            return_value=iter([
                'event: thinking\ndata: {"message": "正在思考...."}\n\n',
                'event: done\ndata: {"success": true, "chat_id": 5}\n\n',
            ]),
        ):
            response = AIChatStreamView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, StreamingHttpResponse)
        stream_text = ''.join(
            chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
            for chunk in response.streaming_content
        )
        self.assertIn('event: done', stream_text)

    def test_stream_view_streams_ai_chat_chunks(self):
        from apps.ai.views import AIChatStreamView
        from django.http import StreamingHttpResponse

        factory = RequestFactory()
        request = factory.post('/ai/chat/stream/', data={'chat_id': 5, 'message': '你好'})
        request.user = SimpleNamespace(is_authenticated=True, id=7)
        request.session = {}

        with patch.object(
            AIChatStreamView,
            '_stream_chat_events',
            return_value=iter([
                'event: thinking\ndata: {"message": "正在思考...."}\n\n',
                'event: chunk\ndata: {"content": "你"}\n\n',
                'event: chunk\ndata: {"content": "好"}\n\n',
                'event: done\ndata: {"success": true, "ai_message": "你好", "status": "success"}\n\n',
            ]),
        ):
            response = AIChatStreamView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, StreamingHttpResponse)
        stream_text = ''.join(
            chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
            for chunk in response.streaming_content
        )
        self.assertIn('event: chunk', stream_text)
        self.assertIn('你', stream_text)
        self.assertIn('event: done', stream_text)
        self.assertIn('"ai_message": "你好"', stream_text)

    def test_stream_chat_events_uses_query_result_as_ai_message(self):
        from apps.ai.views import AIChatStreamView

        factory = RequestFactory()
        request = factory.post('/ai/chat/stream/', data={'message': '我有几个客户'})
        request.user = SimpleNamespace(is_authenticated=True, id=7)
        request.session = {}
        ai_message = SimpleNamespace(
            id=41,
            content='您有21个客户。',
            runtime_payload={},
            created_at=None,
            save=MagicMock(),
        )
        stream_payload = {
            'success': True,
            'intent_type': 'DATA_QUERY',
            'result': '您有21个客户。',
            'confidence': 0.95,
            'specific_intent': 'customer_count',
            'source': 'ai',
            'ai_available': True,
            'ai_configured': True,
        }

        with patch(
            'apps.ai.views.enhanced_intent_service.stream_user_request',
            return_value=iter([{'type': 'done', 'payload': stream_payload}]),
        ), patch.object(
            AIChatStreamView,
            'save_chat_record',
            return_value=(SimpleNamespace(id=5), SimpleNamespace(id=21, created_at=None), ai_message),
        ):
            events = list(AIChatStreamView()._stream_chat_events(
                user=request.user,
                chat_id=None,
                message='我有几个客户',
                request=request,
            ))

        stream_text = ''.join(events)
        done_event = next(item for item in events if 'event: done' in item)
        payload = json.loads(done_event.split('data: ', 1)[1].strip())

        self.assertIn('您有21个客户。', stream_text)
        self.assertNotIn('抱歉，我无法处理您的请求', stream_text)
        self.assertEqual(payload['ai_message'], '您有21个客户。')
        self.assertEqual(payload['message'], '您有21个客户。')

    def test_stream_chat_events_upgrade_confirmable_write_to_confirm_operation(self):
        from apps.ai.views import AIChatStreamView

        factory = RequestFactory()
        request = factory.post('/ai/chat/stream/', data={'chat_id': 5, 'message': '帮我请个假，我要去结婚'})
        request.user = SimpleNamespace(is_authenticated=True, id=7)
        request.session = {}

        ai_message = SimpleNamespace(
            id=31,
            runtime_payload={},
            created_at=None,
            save=MagicMock(),
        )
        operation_record = SimpleNamespace(id=123, confirmation_token='token-123')
        stream_payload = {
            'success': True,
            'requires_confirmation': True,
            'message': '已识别到新增审批意图。AI 会在您确认后直接执行新增，并保留本次操作的单条回退记录。',
            'ai_message': '已识别到新增审批意图。AI 会在您确认后直接执行新增，并保留本次操作的单条回退记录。',
            'intent_type': 'DATA_CREATE',
            'confidence': 0.78,
            'source': 'ai',
            'action': 'create',
            'data_type': 'approval',
            'entities': {
                'type': 'leave_request',
                'reason': '结婚',
            },
            'task': {
                'type': 'business_handoff',
                'intent_type': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'approval',
                'module': '审批管理',
                'title': '新增审批',
                'target_url': '/approval/apply/',
                'list_url': '/approval/my/',
                'open_mode': 'tab',
                'requires_user_confirmation': True,
                'safety_notice': 'AI 会在您确认后直接执行新增，并保留本次操作的单条回退记录。',
                'message': '已识别到新增审批意图。AI 会在您确认后直接执行新增，并保留本次操作的单条回退记录。',
                'prefill': {
                    'type': 'leave_request',
                    'reason': '结婚',
                },
                'options': [
                    {
                        'text': '确认并执行',
                        'intent': 'DATA_CREATE',
                        'action': 'confirm_operation',
                    },
                    {
                        'text': '打开新增审批',
                        'intent': 'DATA_CREATE',
                        'action': 'open_business_page',
                        'target_url': '/approval/apply/',
                    },
                    {
                        'text': '打开审批列表',
                        'intent': 'DATA_QUERY',
                        'action': 'open_business_page',
                        'target_url': '/approval/my/',
                    },
                    {
                        'text': '取消操作',
                        'intent': 'AI_CHAT',
                        'action': 'cancel',
                        'enabled': True,
                    },
                ],
            },
            'options': [
                {
                    'text': '打开新增审批',
                    'intent': 'DATA_CREATE',
                    'action': 'open_business_page',
                    'target_url': '/approval/apply/',
                },
                {
                    'text': '打开审批列表',
                    'intent': 'DATA_QUERY',
                    'action': 'open_business_page',
                    'target_url': '/approval/my/',
                },
                {
                    'text': '取消操作',
                    'intent': 'AI_CHAT',
                    'action': 'cancel',
                    'enabled': True,
                },
            ],
        }

        with patch(
            'apps.ai.views.enhanced_intent_service.stream_user_request',
            return_value=iter([{'type': 'done', 'payload': stream_payload}]),
        ), patch(
            'apps.ai.services.confirmation_service.confirmation_service.build_confirmation_payload',
            return_value={
                'action_plan': {
                    'resource': 'approval',
                    'operation': 'create',
                    'object_ids': [],
                    'changes': {
                        'flow_id': 8,
                        'title': '请假申请（结婚）',
                        'content': '请假事由：结婚',
                    },
                    'filters': {},
                    'context': {'approval_request_type': 'leave_request'},
                },
                'confirmation': {
                    'required': True,
                    'message': '已识别到新增审批意图。AI 会在您确认后直接执行新增，并保留本次操作的单条回退记录。',
                },
            },
        ), patch.object(
            AIChatStreamView,
            'save_chat_record',
            return_value=(SimpleNamespace(id=5), SimpleNamespace(id=21), ai_message),
        ) as save_chat_record, patch.object(
            AIChatStreamView,
            '_create_operation_preview',
            return_value=operation_record,
        ) as create_preview:
            events = list(AIChatStreamView()._stream_chat_events(
                user=request.user,
                chat_id=5,
                message='帮我请个假，我要去结婚',
                request=request,
            ))

        done_event = next(item for item in events if 'event: done' in item)
        payload = json.loads(done_event.split('data: ', 1)[1].strip())

        save_chat_record.assert_called_once()
        create_preview.assert_called_once()
        self.assertEqual(payload['options'][0]['action'], 'confirm_operation')
        self.assertEqual(payload['task']['options'][0]['action'], 'confirm_operation')
        self.assertEqual(payload['operation_id'], 123)
        self.assertEqual(payload['confirmation']['token'], 'token-123')
        self.assertEqual(
            sum(1 for option in payload['task']['options'] if option['action'] == 'confirm_operation'),
            1,
        )
        self.assertEqual(payload['task']['options'][0]['token'], 'token-123')

    def test_stream_chat_events_shortcut_confirm_uses_pending_operation_follow_up(self):
        from apps.ai.views import AIChatStreamView

        factory = RequestFactory()
        request = factory.post('/ai/chat/stream/', data={'chat_id': 5, 'message': '确认'})
        request.user = SimpleNamespace(is_authenticated=True, id=7)
        request.session = {}

        with patch.object(
            AIChatStreamView,
            '_build_pending_operation_follow_up_payload',
            create=True,
            return_value={
                'success': True,
                'status': 'success',
                'message': '已执行完成',
                'ai_message': '已执行完成',
                'options': [],
            },
        ) as build_follow_up, patch(
            'apps.ai.views.enhanced_intent_service.stream_user_request',
        ) as stream_user_request:
            events = list(AIChatStreamView()._stream_chat_events(
                user=request.user,
                chat_id=5,
                message='确认',
                request=request,
            ))

        build_follow_up.assert_called_once()
        stream_user_request.assert_not_called()
        self.assertTrue(any('event: done' in item for item in events))


class AIChatRecordPersistenceTests(TestCase):
    def test_save_chat_record_creates_new_chat_when_user_has_multiple_existing_chats(self):
        from django.contrib.auth import get_user_model
        from apps.ai.models import AIChat, AIChatMessage
        from apps.ai.views import AIChatStreamView

        user_model = get_user_model()
        user = user_model.objects.create_user(username='ai-chat-record-user')
        AIChat.objects.create(user=user, session_id='existing-session-1', title='已有会话1')
        AIChat.objects.create(user=user, session_id='existing-session-2', title='已有会话2')

        chat, user_message, ai_message = AIChatStreamView().save_chat_record(
            user,
            chat_id=None,
            message='你好',
            ai_response='你好，我在',
        )

        self.assertIsNotNone(chat)
        self.assertIsNotNone(user_message)
        self.assertIsNotNone(ai_message)
        self.assertEqual(AIChat.objects.filter(user=user).count(), 3)
        self.assertNotIn(chat.session_id, {'existing-session-1', 'existing-session-2'})
        self.assertEqual(
            list(AIChatMessage.objects.filter(chat=chat).values_list('role', 'content')),
            [('user', '你好'), ('assistant', '你好，我在')],
        )


class AIChatHistorySerializationTests(SimpleTestCase):
    def test_serialize_message_hydrates_legacy_pending_operation(self):
        from apps.ai.views import AIChatDetailView

        view = AIChatDetailView()
        view.request = SimpleNamespace(user=SimpleNamespace(id=9, is_authenticated=True))
        message = SimpleNamespace(
            id=3,
            role='assistant',
            content='已识别到新增审批意图。AI 只负责识别和带您进入业务页面，不会直接新增业务数据，请在页面内核对后再保存。',
            created_at=timezone.now(),
            runtime_payload={
                'intent_type': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'approval',
                'confirmation': {'required': True},
                'task': {
                    'type': 'business_handoff',
                    'intent_type': 'DATA_CREATE',
                    'action': 'create',
                    'data_type': 'approval',
                    'module': '审批管理',
                    'title': '新增审批',
                    'target_url': '/approval/apply/',
                    'list_url': '/approval/my/',
                    'open_mode': 'tab',
                    'requires_user_confirmation': True,
                    'safety_notice': 'AI 只负责识别和带您进入业务页面，不会直接新增业务数据，请在页面内核对后再保存。',
                    'message': '已识别到新增审批意图。AI 只负责识别和带您进入业务页面，不会直接新增业务数据，请在页面内核对后再保存。',
                    'options': [
                        {'text': '打开新增审批', 'intent': 'DATA_CREATE', 'action': 'open_business_page', 'target_url': '/approval/apply/'},
                        {'text': '打开审批列表', 'intent': 'DATA_QUERY', 'action': 'open_business_page', 'target_url': '/approval/my/'},
                        {'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel'},
                    ],
                },
                'options': [
                    {'text': '打开新增审批', 'intent': 'DATA_CREATE', 'action': 'open_business_page', 'target_url': '/approval/apply/'},
                    {'text': '打开审批列表', 'intent': 'DATA_QUERY', 'action': 'open_business_page', 'target_url': '/approval/my/'},
                    {'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel'},
                ],
            },
        )
        operation = SimpleNamespace(id=301, confirmation_token='token-301')

        with patch('apps.ai.views.AIOperation.objects.filter') as operation_filter:
            operation_filter.return_value.order_by.return_value.first.return_value = operation
            data = view._serialize_message(message)

        self.assertIn('确认后直接执行', data['content'])
        self.assertEqual(data['task']['operation_id'], 301)
        self.assertEqual(data['task']['confirmation_token'], 'token-301')
        self.assertEqual(data['task']['options'][0]['action'], 'confirm_operation')
        self.assertEqual(data['options'][0]['action'], 'confirm_operation')

    def test_serialize_message_normalizes_top_level_pending_operation(self):
        from apps.ai.views import AIChatDetailView

        view = AIChatDetailView()
        view.request = SimpleNamespace(user=SimpleNamespace(id=9, is_authenticated=True))
        message = SimpleNamespace(
            id=4,
            role='assistant',
            content='已识别到新增审批意图。AI 只负责识别和带您进入业务页面，不会直接新增业务数据，请在页面内核对后再保存。',
            created_at=timezone.now(),
            runtime_payload={
                'intent_type': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'approval',
                'operation_id': 302,
                'confirmation': {'required': True, 'token': 'token-302'},
                'task': {
                    'type': 'business_handoff',
                    'intent_type': 'DATA_CREATE',
                    'action': 'create',
                    'data_type': 'approval',
                    'module': '审批管理',
                    'title': '新增审批',
                    'target_url': '/approval/apply/',
                    'requires_user_confirmation': True,
                    'safety_notice': 'AI 只负责识别和带您进入业务页面，不会直接新增业务数据，请在页面内核对后再保存。',
                    'message': '已识别到新增审批意图。AI 只负责识别和带您进入业务页面，不会直接新增业务数据，请在页面内核对后再保存。',
                    'options': [
                        {'text': '打开新增审批', 'intent': 'DATA_CREATE', 'action': 'open_business_page', 'target_url': '/approval/apply/'},
                        {'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel'},
                    ],
                },
                'options': [
                    {'text': '打开新增审批', 'intent': 'DATA_CREATE', 'action': 'open_business_page', 'target_url': '/approval/apply/'},
                    {'text': '取消操作', 'intent': 'AI_CHAT', 'action': 'cancel'},
                ],
            },
        )

        data = view._serialize_message(message)

        self.assertIn('确认后直接执行', data['content'])
        self.assertNotIn('不会直接新增业务数据', data['content'])
        self.assertEqual(data['task']['operation_id'], 302)
        self.assertEqual(data['task']['confirmation_token'], 'token-302')
        self.assertEqual(data['task']['options'][0]['action'], 'confirm_operation')
        self.assertEqual(data['task']['options'][0]['token'], 'token-302')
        self.assertEqual(data['options'][0]['action'], 'confirm_operation')


class AIOperationPreviewServiceTests(SimpleTestCase):
    def test_create_preview_operation_persists_operation_and_confirmation(self):
        try:
            from apps.ai.services.operation_service import operation_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.operation_service.operation_service is missing')

        user = SimpleNamespace(id=7, is_authenticated=True)
        payload = {
            'action_plan': {
                'resource': 'customer',
                'operation': 'update',
                'object_ids': [12],
                'changes': {'name': '上海壹号客户'},
                'filters': {},
                'context': {},
            },
            'confirmation': {
                'required': True,
                'message': '准备更新客户名称，请确认后执行。',
            },
        }

        operation = SimpleNamespace(id=101, confirmation_token='token-101')

        with patch('apps.ai.services.operation_service.AIOperation.objects.create', return_value=operation) as create_operation, \
                patch('apps.ai.services.operation_service.AIOperationConfirmation.objects.create') as create_confirmation:
            created = operation_service.create_preview_operation(
                user=user,
                chat=None,
                user_message=None,
                ai_message=None,
                payload=payload,
            )

        self.assertEqual(created.id, 101)
        create_operation.assert_called_once()
        create_confirmation.assert_called_once()
        self.assertEqual(create_confirmation.call_args.kwargs['operation'], operation)
        self.assertEqual(create_confirmation.call_args.kwargs['token'], create_operation.call_args.kwargs['confirmation_token'])


class AIConfirmationServiceTests(SimpleTestCase):
    def test_build_action_request_uses_entity_name_for_customer_create(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'customer',
            'entities': {
                'name': 'AI回归客户',
            },
        })

        self.assertEqual(request.resource, 'customer')
        self.assertEqual(request.operation, 'create')
        self.assertEqual(request.changes['name'], 'AI回归客户')

    def test_build_action_request_normalizes_customer_name_alias(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'customer',
            'entities': {
                'customer_name': 'AI全链路客户',
            },
        })

        self.assertEqual(request.changes['name'], 'AI全链路客户')
        self.assertNotIn('customer_name', request.changes)

    def test_build_action_request_uses_entity_title_for_personal_task_create(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'personal_task',
            'entities': {
                'title': 'AI回归任务',
            },
        })

        self.assertEqual(request.resource, 'personal_task')
        self.assertEqual(request.operation, 'create')
        self.assertEqual(request.changes['title'], 'AI回归任务')

    def test_build_action_request_uses_due_date_content_for_personal_task_create(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'personal_task',
            'original_query': '帮我新增一个个人任务，明天下午3点跟进客户',
            'entities': {
                'content': '跟进客户',
                'due_date': '明天下午3点',
            },
        })

        self.assertEqual(request.changes['title'], '跟进客户')
        self.assertIn('due_date', request.changes)

    def test_build_action_request_normalizes_model_personal_task_aliases(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'personal_task',
            'original_query': '帮我新增一个个人任务，明天下午3点跟进客户925236',
            'entities': {
                'task_content': '跟进客户925236',
                'due_date': '明天下午3点',
            },
        })

        self.assertEqual(request.changes['title'], '跟进客户925236')
        self.assertRegex(request.changes['due_date'], r'^\d{4}-\d{2}-\d{2} 15:00:00$')
        self.assertNotIn('task_content', request.changes)

    def test_build_action_request_parses_model_english_relative_due_time(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'personal_task',
            'entities': {
                'description': '跟进客户',
                'due_time': 'tomorrow 15:00',
            },
        })

        self.assertEqual(request.changes['title'], '跟进客户')
        self.assertRegex(request.changes['due_date'], r'^\d{4}-\d{2}-\d{2} 15:00:00$')
        self.assertNotIn('due_time', request.changes)

    def test_build_action_request_extracts_task_title_when_model_only_returns_time(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'personal_task',
            'original_query': '帮我新增一个个人任务，明天下午3点跟进客户925236',
            'entities': {
                'time': '明天下午3点',
                'customer_id': '925236',
            },
        })

        self.assertEqual(request.changes['title'], '跟进客户925236')
        self.assertRegex(request.changes['due_date'], r'^\d{4}-\d{2}-\d{2} 15:00:00$')
        self.assertNotIn('time', request.changes)
        self.assertNotIn('customer_id', request.changes)

    def test_build_action_request_normalizes_task_description_alias(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'personal_task',
            'entities': {
                'task_description': '跟进客户',
                'due_time': 'tomorrow 15:00',
            },
        })

        self.assertEqual(request.changes['title'], '跟进客户')
        self.assertNotIn('task_description', request.changes)

    def test_build_action_request_uses_item_code_for_inventory_create(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'inventory',
            'entities': {
                'item_code': 'MAT-001',
            },
        })

        self.assertEqual(request.changes['code'], 'MAT-001')
        self.assertEqual(request.changes['name'], 'MAT-001')
        self.assertEqual(request.changes['unit'], '个')

    def test_build_action_request_uses_query_title_for_document_create(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'document',
            'original_query': '帮我起草一份公文，标题是质量巡检通知',
            'entities': {},
        })

        self.assertEqual(request.changes['title'], '质量巡检通知')
        self.assertIn('document_number', request.changes)
        self.assertIn('content', request.changes)

    def test_build_action_request_maps_meeting_chinese_entities(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'meeting',
            'entities': {
                '主题': 'AI回归例会',
                '时间': '明天下午3点',
            },
        }, user=SimpleNamespace(id=9, did=3))

        self.assertEqual(request.changes['title'], 'AI回归例会')
        self.assertIn('meeting_date', request.changes)
        self.assertIn('meeting_end_time', request.changes)
        self.assertEqual(request.changes['host_id'], 9)

    def test_build_action_request_combines_separate_meeting_date_and_time(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'meeting',
            'entities': {
                'meeting_title': 'AI项目例会',
                'date': '明天',
                'time': '下午3点',
                'location': '第一会议室',
            },
        }, user=SimpleNamespace(id=9, did=3))

        expected_date = (confirmation_service._local_now().date() + timedelta(days=1)).isoformat()
        self.assertEqual(request.changes['meeting_date'], f'{expected_date} 15:00:00')
        self.assertNotIn('date', request.changes)
        self.assertNotIn('time', request.changes)

    def test_build_action_request_maps_order_customer_name_to_customer_id(self):
        from apps.ai.services.confirmation_service import confirmation_service

        with patch.object(confirmation_service, '_resolve_customer_id_for_user', return_value=12):
            request = confirmation_service.build_action_request({
                'action': 'create',
                'data_type': 'order',
                'entities': {
                    'customer_name': '阿里云国际站',
                    'amount': 1100,
                },
            }, user=SimpleNamespace(id=9, is_superuser=False))

        self.assertEqual(request.changes['customer_id'], 12)
        self.assertEqual(request.changes['amount'], 1100)
        self.assertIn('order_number', request.changes)
        self.assertIn('order_date', request.changes)

    def test_build_action_request_maps_production_plan_defaults(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'production_plan',
            'entities': {
                'name': 'AI回归生产计划',
            },
        }, user=SimpleNamespace(id=9, did=3))

        self.assertEqual(request.changes['name'], 'AI回归生产计划')
        self.assertEqual(request.changes['unit'], '件')
        self.assertEqual(request.changes['quantity'], 1)
        self.assertIn('code', request.changes)
        self.assertIn('plan_start_date', request.changes)

    def test_build_action_request_normalizes_configured_resource_aliases(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'finance_account',
            'entities': {
                'account_name': 'AI验证账户',
                'account_type': 'bank',
                'currency': 'CNY',
                'initial_balance': 0,
            },
        })

        self.assertEqual(request.changes['name'], 'AI验证账户')
        self.assertEqual(request.changes['opening_balance'], 0)
        self.assertNotIn('account_name', request.changes)
        self.assertNotIn('initial_balance', request.changes)

    def test_build_action_request_normalizes_aliases_inside_model_changes(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'finance_account',
            'entities': {
                'changes': {
                    'account_name': 'AI嵌套结构账户',
                    'initial_balance': 1200,
                    'currency': 'CNY',
                },
            },
        })

        self.assertEqual(request.changes['name'], 'AI嵌套结构账户')
        self.assertEqual(request.changes['opening_balance'], 1200)
        self.assertNotIn('account_name', request.changes)
        self.assertNotIn('initial_balance', request.changes)

    def test_build_action_request_uses_text_host_for_meeting_minutes(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'meeting_minutes',
            'entities': {
                'title': 'AI验证纪要',
                'meeting_date': 'today',
            },
        }, user=SimpleNamespace(id=9, name='验证用户', username='verify'))

        self.assertEqual(request.changes['host'], '验证用户')
        self.assertNotIn('host_id', request.changes)

    def test_build_action_request_normalizes_supply_sample_required_date_alias(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'supply_chain_sample',
            'entities': {
                'material_name': 'AI验证物料',
                'require_date': 'tomorrow',
                'quantity': 1,
            },
        }, user=SimpleNamespace(id=9))

        self.assertEqual(request.changes['required_date'], 'tomorrow')
        self.assertNotIn('require_date', request.changes)

    def test_build_action_request_uses_direct_model_fields_for_update(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'update',
            'data_type': 'ai_knowledge_base',
            'entities': {
                'id': '3',
                'name': 'AI已修改知识库',
            },
        })

        self.assertEqual(request.object_ids, [3])
        self.assertEqual(request.changes, {'name': 'AI已修改知识库'})

    def test_build_action_request_uses_direct_model_id_for_delete(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'delete',
            'data_type': 'ai_knowledge_base',
            'entities': {'id': '3'},
        })

        self.assertEqual(request.object_ids, [3])
        self.assertEqual(request.changes, {})

    def test_build_action_request_normalizes_disk_share_resource(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'disk_share',
            'entities': {
                'object_ids': [91],
                'changes': {'permission_type': 'view'},
            },
        })

        self.assertEqual(request.resource, 'disk')
        self.assertEqual(request.context['model'], 'share')
        self.assertEqual(request.object_ids, [91])

    def test_build_action_request_normalizes_disk_folder_resource(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'update',
            'data_type': 'disk_folder',
            'entities': {
                'object_ids': [71],
                'changes': {'name': '新资料夹'},
            },
        })

        self.assertEqual(request.resource, 'disk')
        self.assertEqual(request.context['model'], 'folder')
        self.assertEqual(request.changes['name'], '新资料夹')

    def test_build_action_request_normalizes_finance_invoice_resource(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'update',
            'data_type': 'finance_invoice',
            'entities': {
                'object_ids': [52],
                'changes': {'delivery': 'SF123456'},
            },
        })

        self.assertEqual(request.resource, 'finance')
        self.assertEqual(request.context['model'], 'invoice')
        self.assertEqual(request.object_ids, [52])

    def test_build_action_request_normalizes_payment_resource(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'payment',
            'entities': {
                'changes': {'amount': '5000.00'},
            },
        })

        self.assertEqual(request.resource, 'finance')
        self.assertEqual(request.context['model'], 'payment')

    def test_build_action_request_normalizes_income_resource(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'finance_income',
            'entities': {
                'changes': {'amount': '3000.00'},
            },
        })

        self.assertEqual(request.resource, 'finance')
        self.assertEqual(request.context['model'], 'income')

    def test_build_action_request_normalizes_finance_order_record_resource(self):
        from apps.ai.services.confirmation_service import confirmation_service

        request = confirmation_service.build_action_request({
            'action': 'update',
            'data_type': 'finance_order_record',
            'entities': {
                'object_ids': [63],
                'changes': {'remark': '已确认回款节点'},
            },
        })

        self.assertEqual(request.resource, 'finance')
        self.assertEqual(request.context['model'], 'order_record')
        self.assertEqual(request.object_ids, [63])


class AIApprovalConversationExecutionTests(TestCase):
    def test_confirmation_payload_resolves_chinese_leave_request_type(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.confirmation_service import confirmation_service
        from apps.approval.models import ApprovalFlow, ApprovalStep, ApprovalType

        user_model = get_user_model()
        user = user_model.objects.create_user(
            username='approval-ai-chinese-leave',
            password='test-pass-123',
            is_superuser=True,
        )
        approval_type = ApprovalType.objects.create(
            name='请假审批',
            code='LEAVE-TYPE-CHINESE-AI',
            is_active=True,
        )
        flow = ApprovalFlow.objects.create(
            name='请假审批流程',
            code='LEAVE-FLOW-CHINESE-AI',
            approval_type=approval_type,
            is_active=True,
        )
        ApprovalStep.objects.create(
            flow=flow,
            step_name='人事审批',
            step_order=1,
            step_type='specific_user',
            action_type='approve',
            approver=user,
        )

        payload = {
            'success': True,
            'requires_confirmation': True,
            'message': '已识别到请假审批意图，请确认后执行。',
            'intent_type': 'DATA_CREATE',
            'action': 'create',
            'data_type': 'approval',
            'original_query': '帮我请个假，我要去结婚',
            'entities': {
                'request_type': '请假',
            },
        }

        confirmation = confirmation_service.build_confirmation_payload(payload, user=user)
        changes = confirmation['action_plan']['changes']
        context = confirmation['action_plan']['context']

        self.assertEqual(changes['flow_id'], flow.id)
        self.assertEqual(changes['type_id'], approval_type.id)
        self.assertEqual(changes['title'], '请假申请（结婚）')
        self.assertEqual(changes['content'], '请假事由：结婚')
        self.assertEqual(context['approval_request_type'], 'leave_request')
        self.assertEqual(context['approval_reason'], '结婚')

    def test_confirm_operation_creates_leave_approval_and_initial_task(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.confirmation_service import confirmation_service
        from apps.ai.services.operation_service import operation_service
        from apps.approval.models import Approval, ApprovalFlow, ApprovalStep, ApprovalTask, ApprovalType

        user_model = get_user_model()
        user = user_model.objects.create_user(
            username='approval-ai-executor',
            password='test-pass-123',
            is_superuser=True,
        )
        approval_type = ApprovalType.objects.create(
            name='请假审批',
            code='LEAVE-TYPE-AI',
            is_active=True,
        )
        flow = ApprovalFlow.objects.create(
            name='请假审批流程',
            code='LEAVE-FLOW-AI',
            approval_type=approval_type,
            is_active=True,
        )
        ApprovalStep.objects.create(
            flow=flow,
            step_name='人事审批',
            step_order=1,
            step_type='specific_user',
            action_type='approve',
            approver=user,
        )

        payload = {
            'success': True,
            'requires_confirmation': True,
            'message': '已识别到请假审批意图，请确认后执行。',
            'intent_type': 'DATA_CREATE',
            'action': 'create',
            'data_type': 'approval',
            'entities': {
                'request_type': 'leave_request',
                'reason': '结婚',
            },
        }
        payload.update(confirmation_service.build_confirmation_payload(payload, user=user))

        operation = operation_service.create_preview_operation(
            user=user,
            chat=None,
            user_message=None,
            ai_message=None,
            payload=payload,
        )
        result = operation_service.confirm_operation(
            operation.id,
            operation.confirmation_token,
            user,
        )

        self.assertTrue(result['success'])
        approval = Approval.objects.get(title__contains='请假')
        self.assertEqual(approval.flow_id, flow.id)
        self.assertEqual(approval.type_id, approval_type.id)
        self.assertIn('结婚', approval.content)
        self.assertEqual(approval.status, 1)
        self.assertTrue(
            ApprovalTask.objects.filter(approval=approval, status='pending').exists()
        )

    def test_confirm_operation_repairs_legacy_empty_approval_preview(self):
        from django.contrib.auth import get_user_model
        from apps.ai.models import AIChat, AIChatMessage
        from apps.ai.services.operation_service import operation_service
        from apps.approval.models import Approval, ApprovalFlow, ApprovalStep, ApprovalType

        user_model = get_user_model()
        user = user_model.objects.create_user(
            username='approval-ai-legacy-preview',
            password='test-pass-123',
            is_superuser=True,
        )
        approval_type = ApprovalType.objects.create(
            name='请假审批',
            code='LEAVE-TYPE-LEGACY-AI',
            is_active=True,
        )
        flow = ApprovalFlow.objects.create(
            name='请假审批流程',
            code='LEAVE-FLOW-LEGACY-AI',
            approval_type=approval_type,
            is_active=True,
        )
        ApprovalStep.objects.create(
            flow=flow,
            step_name='人事审批',
            step_order=1,
            step_type='specific_user',
            action_type='approve',
            approver=user,
        )
        chat = AIChat.objects.create(user=user, title='legacy-preview')
        user_message = AIChatMessage.objects.create(chat=chat, role='user', content='帮我请个假')
        ai_message = AIChatMessage.objects.create(
            chat=chat,
            role='assistant',
            content='已识别到新增审批意图。AI 只负责识别和带您进入业务页面，不会直接新增业务数据，请在页面内核对后再保存。',
            runtime_payload={
                'success': True,
                'requires_confirmation': True,
                'intent_type': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'approval',
                'entities': {'request_type': '请假'},
            },
        )
        operation = operation_service.create_preview_operation(
            user=user,
            chat=chat,
            user_message=user_message,
            ai_message=ai_message,
            payload={
                'action_plan': {
                    'resource': 'approval',
                    'operation': 'create',
                    'object_ids': [],
                    'changes': {},
                    'filters': {},
                    'context': {},
                },
                'confirmation': {'required': True, 'message': '待确认'},
            },
        )

        result = operation_service.confirm_operation(
            operation.id,
            operation.confirmation_token,
            user,
        )

        self.assertTrue(result['success'])
        operation.refresh_from_db()
        self.assertEqual(operation.preview_payload['changes']['flow_id'], flow.id)
        self.assertEqual(operation.preview_payload['changes']['title'], '请假申请')
        approval = Approval.objects.get(applicant_id=user.id)
        self.assertEqual(approval.flow_id, flow.id)
        self.assertEqual(approval.type_id, approval_type.id)


class AIOperationConfirmServiceTests(SimpleTestCase):
    def test_confirm_operation_validates_token_and_updates_status(self):
        try:
            from apps.ai.services.operation_service import operation_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.operation_service.operation_service is missing')

        user = SimpleNamespace(id=7, is_authenticated=True)
        operation = SimpleNamespace(
            id=9,
            status='preview',
            requires_confirmation=True,
            preview_payload={'resource': 'customer', 'operation': 'update'},
            confirmed_payload={},
            save=MagicMock(),
        )
        confirmation = SimpleNamespace(
            token='token-9',
            is_used=False,
            confirmed_by=None,
            confirmed_at=None,
            save=MagicMock(),
        )

        with patch('apps.ai.services.operation_service.AIOperation.objects.select_related') as select_related, \
                patch('apps.ai.services.operation_service.timezone.now', return_value='NOW'), \
                patch('apps.ai.services.operation_service.transaction.atomic'), \
                patch('apps.ai.services.operation_service.AIActionGateway') as gateway_cls:
            select_related.return_value.get.return_value = operation
            gateway = gateway_cls.return_value
            gateway.execute_confirmed_action.return_value = {'success': True, 'message': 'done'}
            operation.confirmation = confirmation

            result = operation_service.confirm_operation(
                operation_id=9,
                token='token-9',
                user=user,
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['operation_id'], 9)
        self.assertEqual(operation.status, 'executed')
        self.assertEqual(operation.confirmed_payload, {'resource': 'customer', 'operation': 'update'})
        self.assertTrue(confirmation.is_used)
        self.assertEqual(confirmation.confirmed_by, user)
        gateway.execute_confirmed_action.assert_called_once_with(operation, user)

    def test_confirm_operation_rejects_invalid_token(self):
        try:
            from apps.ai.services.operation_service import operation_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.operation_service.operation_service is missing')

        user = SimpleNamespace(id=7, is_authenticated=True)
        operation = SimpleNamespace(
            id=9,
            status='preview',
            requires_confirmation=True,
            preview_payload={'resource': 'customer', 'operation': 'update'},
            confirmed_payload={},
        )
        confirmation = SimpleNamespace(
            token='token-9',
            is_used=False,
        )

        with patch('apps.ai.services.operation_service.AIOperation.objects.select_related') as select_related:
            select_related.return_value.get.return_value = operation
            operation.confirmation = confirmation

            result = operation_service.confirm_operation(
                operation_id=9,
                token='wrong-token',
                user=user,
            )

        self.assertFalse(result['success'])
        self.assertEqual(result['message'], '确认令牌无效')

    def test_confirm_operation_persists_change_sets_and_marks_executed(self):
        try:
            from apps.ai.services.operation_service import operation_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.operation_service.operation_service is missing')

        user = SimpleNamespace(id=7, is_authenticated=True)
        operation = SimpleNamespace(
            id=9,
            status='preview',
            requires_confirmation=True,
            preview_payload={'resource': 'customer', 'operation': 'update', 'object_ids': [12], 'changes': {'name': '新名称'}},
            confirmed_payload={},
            save=MagicMock(),
        )
        confirmation = SimpleNamespace(
            token='token-9',
            is_used=False,
            confirmed_by=None,
            confirmed_at=None,
            save=MagicMock(),
        )
        gateway_result = {
            'success': True,
            'message': 'updated',
            'change_set': [
                {
                    'app_label': 'customer',
                    'model_name': 'Customer',
                    'object_pk': '12',
                    'change_type': 'update',
                    'before_snapshot': {'name': '旧名称'},
                    'after_snapshot': {'name': '新名称'},
                    'changed_fields': ['name'],
                }
            ],
        }

        with patch('apps.ai.services.operation_service.AIOperation.objects.select_related') as select_related, \
                patch('apps.ai.services.operation_service.AIOperationChangeSet.objects.create') as create_change_set, \
                patch('apps.ai.services.operation_service.timezone.now', return_value='NOW'), \
                patch('apps.ai.services.operation_service.transaction.atomic'), \
                patch('apps.ai.services.operation_service.AIActionGateway') as gateway_cls:
            select_related.return_value.get.return_value = operation
            operation.confirmation = confirmation
            gateway = gateway_cls.return_value
            gateway.execute_confirmed_action.return_value = gateway_result

            result = operation_service.confirm_operation(
                operation_id=9,
                token='token-9',
                user=user,
            )

        self.assertTrue(result['success'])
        self.assertEqual(operation.status, 'executed')
        self.assertEqual(operation.confirmed_payload, operation.preview_payload)
        create_change_set.assert_called_once()
        self.assertEqual(create_change_set.call_args.kwargs['operation'], operation)
        self.assertEqual(create_change_set.call_args.kwargs['object_pk'], '12')
        self.assertEqual(create_change_set.call_args.kwargs['change_type'], 'update')

    def test_confirm_operation_scopes_to_request_user(self):
        from apps.ai.services.operation_service import operation_service

        user = SimpleNamespace(id=7, is_authenticated=True)
        operation = SimpleNamespace(
            id=9,
            status='preview',
            requires_confirmation=True,
            preview_payload={'resource': 'customer', 'operation': 'update'},
            confirmed_payload={},
            save=MagicMock(),
        )
        confirmation = SimpleNamespace(
            token='token-9',
            is_used=False,
            confirmed_by=None,
            confirmed_at=None,
            save=MagicMock(),
        )

        with patch('apps.ai.services.operation_service.AIOperation.objects.select_related') as select_related, \
                patch('apps.ai.services.operation_service.timezone.now', return_value='NOW'), \
                patch('apps.ai.services.operation_service.transaction.atomic'), \
                patch('apps.ai.services.operation_service.AIActionGateway') as gateway_cls:
            select_related.return_value.get.return_value = operation
            operation.confirmation = confirmation
            gateway_cls.return_value.execute_confirmed_action.return_value = {
                'success': True,
                'message': 'done',
                'change_set': [],
            }

            operation_service.confirm_operation(
                operation_id=9,
                token='token-9',
                user=user,
            )

        select_related.return_value.get.assert_called_once_with(id=9, user=user)

    def test_confirm_operation_rejects_cancelled_preview(self):
        from apps.ai.services.operation_service import operation_service

        user = SimpleNamespace(id=7, is_authenticated=True)
        operation = SimpleNamespace(
            id=9,
            status='cancelled',
            requires_confirmation=True,
            preview_payload={'resource': 'customer', 'operation': 'update'},
            confirmed_payload={},
            save=MagicMock(),
        )
        confirmation = SimpleNamespace(
            token='token-9',
            is_used=False,
        )

        with patch('apps.ai.services.operation_service.AIOperation.objects.select_related') as select_related, \
                patch('apps.ai.services.operation_service.AIActionGateway') as gateway_cls:
            select_related.return_value.get.return_value = operation
            operation.confirmation = confirmation

            result = operation_service.confirm_operation(
                operation_id=9,
                token='token-9',
                user=user,
            )

        self.assertFalse(result['success'])
        self.assertEqual(result['message'], '该操作已处理，无法再次确认')
        gateway_cls.assert_not_called()

    def test_confirm_operation_marks_failed_when_gateway_fails(self):
        from apps.ai.services.operation_service import operation_service

        user = SimpleNamespace(id=7, is_authenticated=True)
        operation = SimpleNamespace(
            id=9,
            status='preview',
            requires_confirmation=True,
            preview_payload={'resource': 'customer', 'operation': 'update'},
            confirmed_payload={},
            save=MagicMock(),
        )
        confirmation = SimpleNamespace(
            token='token-9',
            is_used=False,
            confirmed_by=None,
            confirmed_at=None,
            save=MagicMock(),
        )

        with patch('apps.ai.services.operation_service.AIOperation.objects.select_related') as select_related, \
                patch('apps.ai.services.operation_service.timezone.now', return_value='NOW'), \
                patch('apps.ai.services.operation_service.transaction.atomic'), \
                patch('apps.ai.services.operation_service.AIActionGateway') as gateway_cls:
            select_related.return_value.get.return_value = operation
            operation.confirmation = confirmation
            gateway_cls.return_value.execute_confirmed_action.return_value = {
                'success': False,
                'message': 'adapter failed',
                'change_set': [],
            }

            result = operation_service.confirm_operation(
                operation_id=9,
                token='token-9',
                user=user,
            )

        self.assertFalse(result['success'])
        self.assertEqual(operation.status, 'failed')

    def test_confirm_operation_runs_execution_in_database_transaction(self):
        from apps.ai.services.operation_service import operation_service

        user = SimpleNamespace(id=7, is_authenticated=True)
        operation = SimpleNamespace(
            id=9,
            status='preview',
            requires_confirmation=True,
            preview_payload={'resource': 'customer', 'operation': 'update'},
            confirmed_payload={},
            save=MagicMock(),
        )
        confirmation = SimpleNamespace(
            token='token-9',
            is_used=False,
            confirmed_by=None,
            confirmed_at=None,
            save=MagicMock(),
        )

        with patch('apps.ai.services.operation_service.AIOperation.objects.select_related') as select_related, \
                patch('apps.ai.services.operation_service.timezone.now', return_value='NOW'), \
                patch('apps.ai.services.operation_service.transaction.atomic') as atomic, \
                patch('apps.ai.services.operation_service.AIActionGateway') as gateway_cls:
            select_related.return_value.get.return_value = operation
            operation.confirmation = confirmation
            gateway_cls.return_value.execute_confirmed_action.return_value = {
                'success': True,
                'message': 'done',
                'change_set': [],
            }

            operation_service.confirm_operation(
                operation_id=9,
                token='token-9',
                user=user,
            )

        atomic.assert_called_once()


class AIOperationCancelServiceTests(SimpleTestCase):
    def test_match_pending_operation_command_does_not_confirm_business_follow_up(self):
        from apps.ai.services.operation_service import operation_service

        self.assertIsNone(operation_service.match_pending_operation_command('继续查一下客户'))
        self.assertIsNone(operation_service.match_pending_operation_command('执行中的项目有几个'))
        self.assertEqual(operation_service.match_pending_operation_command('确认执行'), 'confirm')
        self.assertEqual(operation_service.match_pending_operation_command('取消吧'), 'cancel')
        self.assertEqual(operation_service.match_pending_operation_command('回退刚才的操作'), 'rollback')
        self.assertEqual(operation_service.match_pending_operation_command('撤销上一步'), 'rollback')

    def test_cancel_operation_marks_preview_cancelled(self):
        from apps.ai.services.operation_service import operation_service

        user = SimpleNamespace(id=7, is_authenticated=True)
        operation = SimpleNamespace(
            id=9,
            status='preview',
            save=MagicMock(),
        )
        confirmation = SimpleNamespace(token='token-9')

        with patch('apps.ai.services.operation_service.AIOperation.objects.select_related') as select_related:
            select_related.return_value.get.return_value = operation
            operation.confirmation = confirmation

            result = operation_service.cancel_operation(
                operation_id=9,
                token='token-9',
                user=user,
            )

        self.assertTrue(result['success'])
        self.assertEqual(operation.status, 'cancelled')
        operation.save.assert_called_once()
        select_related.return_value.get.assert_called_once_with(id=9, user=user)


class AIConfirmOperationViewTests(SimpleTestCase):
    def test_confirm_operation_view_returns_service_result(self):
        from apps.ai.views import AIConfirmOperationView

        factory = RequestFactory()
        request = factory.post(
            '/ai/operation/confirm/',
            data=json.dumps({'operation_id': 9, 'token': 'token-9'}),
            content_type='application/json',
        )
        request.user = SimpleNamespace(id=7, is_authenticated=True)

        with patch('apps.ai.views.operation_service.confirm_operation', return_value={'success': True, 'operation_id': 9, 'message': 'done'}):
            response = AIConfirmOperationView.as_view()(request)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['operation_id'], 9)

    def test_confirm_operation_view_returns_json_when_execution_raises(self):
        from apps.ai.views import AIConfirmOperationView

        factory = RequestFactory()
        request = factory.post(
            '/ai/operation/confirm/',
            data=json.dumps({'operation_id': 9, 'token': 'token-9'}),
            content_type='application/json',
        )
        request.user = SimpleNamespace(id=7, is_authenticated=True)

        with patch('apps.ai.views.operation_service.confirm_operation', side_effect=RuntimeError('database failed')):
            response = AIConfirmOperationView.as_view()(request)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 500)
        self.assertFalse(payload['success'])
        self.assertIn('执行失败', payload['message'])


class AICancelOperationViewTests(SimpleTestCase):
    def test_cancel_operation_view_returns_service_result(self):
        from apps.ai.views import AICancelOperationView

        factory = RequestFactory()
        request = factory.post(
            '/ai/operation/cancel/',
            data=json.dumps({'operation_id': 9, 'token': 'token-9'}),
            content_type='application/json',
        )
        request.user = SimpleNamespace(id=7, is_authenticated=True)

        with patch('apps.ai.views.operation_service.cancel_operation', return_value={'success': True, 'operation_id': 9, 'message': 'cancelled'}):
            response = AICancelOperationView.as_view()(request)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['operation_id'], 9)


class AIIntentCoverageTests(SimpleTestCase):
    def test_normalize_ai_result_keeps_ai_model_config_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.84,
            'action': 'list',
            'data_type': 'ai_model_config',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为AI模型配置列表',
        }, '查看 AI 模型配置')

        self.assertEqual(result['data_type'], 'ai_model_config')

    def test_normalize_ai_result_keeps_supply_chain_forecast_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.84,
            'action': 'list',
            'data_type': 'supply_chain_forecast',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为需求预测列表',
        }, '查看需求预测计划')

        self.assertEqual(result['data_type'], 'supply_chain_forecast')

    def test_normalize_ai_result_keeps_finance_account_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.84,
            'action': 'list',
            'data_type': 'finance_account',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为资金账户列表',
        }, '查看资金账户')

        self.assertEqual(result['data_type'], 'finance_account')

    def test_rule_fallback_recognizes_work_report_without_unpack_error(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result('帮我看一下本周周报', 'AI 模型暂时不可用')

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['action'], 'list')
        self.assertEqual(result['data_type'], 'work_report')

    def test_rule_fallback_prefers_order_for_create_query_with_customer_name(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '帮我添加一个订单，客户是阿里云国际站，订单金额：1100',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_CREATE')
        self.assertEqual(result['action'], 'create')
        self.assertEqual(result['data_type'], 'order')

    def test_rule_fallback_recognizes_disk_share_query(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result('帮我查一下网盘分享链接', '未配置模型')

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['action'], 'list')
        self.assertEqual(result['data_type'], 'disk_share')

    def test_rule_fallback_recognizes_approval_create_as_confirmable(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result('我要发起一个报销审批流程', '未配置模型')

        self.assertEqual(result['intent'], 'DATA_CREATE')
        self.assertEqual(result['action'], 'create')
        self.assertEqual(result['data_type'], 'approval_flow')
        self.assertTrue(result['requires_confirmation'])

    def test_enhance_corrects_ai_chat_when_business_query_is_clear(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._enhance_result({
            'intent': 'AI_CHAT',
            'confidence': 0.2,
            'entities': {},
            'action': 'chat',
            'data_type': None,
        }, '看一下我的待审批流程')

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['action'], 'list')
        self.assertEqual(result['data_type'], 'approval_task')

    def test_enhance_repairs_leave_request_ai_chat_to_confirmable_approval_create(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._enhance_result({
            'intent': 'AI_CHAT',
            'confidence': 0.4,
            'entities': {},
            'action': 'chat',
            'data_type': None,
        }, '帮我请假')

        self.assertEqual(result['intent'], 'DATA_CREATE')
        self.assertEqual(result['action'], 'create')
        self.assertEqual(result['data_type'], 'approval')
        self.assertEqual(result['entities']['request_type'], 'leave_request')
        self.assertTrue(result['requires_confirmation'])

    def test_enhance_overrides_wrong_ai_data_type_for_leave_request(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._enhance_result({
            'intent': 'DATA_CREATE',
            'confidence': 0.9,
            'entities': {},
            'action': 'create',
            'data_type': 'employee_care',
            'source': 'ai',
        }, '帮我请假')

        self.assertEqual(result['intent'], 'DATA_CREATE')
        self.assertEqual(result['action'], 'create')
        self.assertEqual(result['data_type'], 'approval')
        self.assertEqual(result['entities']['request_type'], 'leave_request')
        self.assertTrue(result['requires_confirmation'])

    def test_safe_fallback_marks_configured_service_failure(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        classifier.ai_config = {
            'provider': 'openai',
            'model_name': 'gpt-5.4',
        }

        result = classifier._safe_fallback_result('帮我查询今天待审批的流程', 'AI 模型暂时不可用')

        self.assertFalse(result['ai_available'])
        self.assertTrue(result['ai_configured'])
        self.assertEqual(result['failure_reason'], 'AI 模型暂时不可用')
        self.assertEqual(result['model_provider'], 'openai')
        self.assertEqual(result['model_name'], 'gpt-5.4')

    def test_rule_fallback_collects_candidate_data_types_for_ambiguous_write_query(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '帮我添加一个订单，客户是阿里云国际站，订单金额：1100',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['data_type'], 'order')
        self.assertEqual(result['entities']['candidate_data_types'], ['order', 'customer'])

    def test_rule_fallback_recognizes_document_create_from_office_terms(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '起草一份公文，标题是质量巡检通知',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_CREATE')
        self.assertEqual(result['action'], 'create')
        self.assertEqual(result['data_type'], 'document')
        self.assertTrue(result['requires_confirmation'])

    def test_rule_fallback_recognizes_inventory_create_from_material_terms(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '录入一个库存物料，编码 MAT-001',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_CREATE')
        self.assertEqual(result['action'], 'create')
        self.assertEqual(result['data_type'], 'inventory')
        self.assertTrue(result['requires_confirmation'])

    def test_rule_fallback_recognizes_document_publish_action(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '发布这份公文',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_UPDATE')
        self.assertEqual(result['action'], 'publish')
        self.assertEqual(result['data_type'], 'document')
        self.assertTrue(result['requires_confirmation'])

    def test_rule_fallback_recognizes_stockin_approve_action(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '审核这张入库单',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_UPDATE')
        self.assertEqual(result['action'], 'approve')
        self.assertEqual(result['data_type'], 'stockin')
        self.assertTrue(result['requires_confirmation'])

    def test_rule_fallback_recognizes_alert_approve_action(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '处理一下这个库存预警',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_UPDATE')
        self.assertEqual(result['action'], 'approve')
        self.assertEqual(result['data_type'], 'alert')
        self.assertTrue(result['requires_confirmation'])

    def test_rule_fallback_prefers_personal_contact_for_my_contacts(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '查一下我的联系人',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['data_type'], 'personal_contact')

    def test_rule_fallback_prefers_production_task_over_generic_production(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '看看今天的生产任务',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['data_type'], 'production_task')

    def test_rule_fallback_recognizes_finance_order_record_query(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '查一下订单财务记录',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['action'], 'list')
        self.assertEqual(result['data_type'], 'finance_order_record')

    def test_rule_fallback_recognizes_pending_alert_query_status(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '看看未处理的库存预警',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['data_type'], 'alert')
        self.assertEqual(result['status'], 'pending')

    def test_rule_fallback_recognizes_completed_approval_task_query_status(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '看看我已审批的流程',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['data_type'], 'approval_task')
        self.assertEqual(result['status'], 'completed')

    def test_rule_fallback_recognizes_stockin_pending_stock_query_status(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '看一下待入库确认的入库单',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['data_type'], 'stockin')
        self.assertEqual(result['status'], 'approved')

    def test_rule_fallback_recognizes_paused_production_task_query_status(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '查一下已暂停的生产任务',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['data_type'], 'production_task')
        self.assertEqual(result['status'], 'paused')

    def test_rule_fallback_recognizes_pending_publish_document_query_status(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '看一下待发布公文',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['data_type'], 'document')
        self.assertEqual(result['status'], 'approved')

    def test_rule_fallback_recognizes_maintenance_equipment_query_status(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._safe_fallback_result(
            '看一下维修中的设备',
            'AI 模型暂时不可用',
        )

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['data_type'], 'production_equipment')
        self.assertEqual(result['status'], 'maintenance')

    def test_summarize_ai_failure_identifies_unavailable_model(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier
        from apps.ai.utils.ai_client import AIClientError

        classifier = AIIntentClassifier()
        reason = classifier._summarize_ai_failure(AIClientError(
            'AI模型调用失败，请检查模型配置后重试',
            status_code=503,
            detail='No available channel for model gpt-5.5 under group test',
        ))

        self.assertIn('gpt-5.5', reason)
        self.assertIn('不可用', reason)

    def test_parse_ai_response_accepts_json_wrapped_in_text(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        response = '''好的，结果如下：
```json
{"intent":"DATA_QUERY","confidence":0.91,"action":"count","data_type":"finance","entities":{},"time_range":"this_month","status":null,"customer_name":null,"requires_confirmation":false,"reasoning":"识别为本月成交金额统计"}
```
'''

        result = classifier._parse_ai_response(response, '本月成交金额')

        self.assertEqual(result['intent'], 'DATA_QUERY')
        self.assertEqual(result['action'], 'count')
        self.assertEqual(result['data_type'], 'finance')

    def test_normalize_ai_result_keeps_finance_invoice_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.91,
            'action': 'list',
            'data_type': 'finance_invoice',
            'entities': {},
            'time_range': None,
            'status': 'unissued',
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为发票列表',
        }, '未开票的发票有哪些')

        self.assertEqual(result['data_type'], 'finance_invoice')
        self.assertEqual(result['status'], 'unissued')

    def test_normalize_ai_result_keeps_production_task_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.88,
            'action': 'list',
            'data_type': 'production_task',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为生产任务列表',
        }, '查询生产任务')

        self.assertEqual(result['data_type'], 'production_task')

    def test_normalize_ai_result_keeps_warehouse_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.84,
            'action': 'list',
            'data_type': 'warehouse',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为仓库列表',
        }, '看看仓库列表')

        self.assertEqual(result['data_type'], 'warehouse')

    def test_normalize_ai_result_keeps_contact_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.82,
            'action': 'list',
            'data_type': 'contact',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为联系人列表',
        }, '查一下联系人')

        self.assertEqual(result['data_type'], 'contact')

    def test_normalize_ai_result_keeps_enterprise_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.82,
            'action': 'list',
            'data_type': 'enterprise',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为企业列表',
        }, '查看企业信息')

        self.assertEqual(result['data_type'], 'enterprise')

    def test_normalize_ai_result_keeps_position_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.82,
            'action': 'list',
            'data_type': 'position',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为岗位列表',
        }, '查看岗位信息')

        self.assertEqual(result['data_type'], 'position')

    def test_normalize_ai_result_keeps_work_record_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.82,
            'action': 'list',
            'data_type': 'work_record',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为工作记录列表',
        }, '查看工作记录')

        self.assertEqual(result['data_type'], 'work_record')

    def test_normalize_ai_result_keeps_work_report_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.82,
            'action': 'list',
            'data_type': 'work_report',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为工作汇报列表',
        }, '查看工作汇报')

        self.assertEqual(result['data_type'], 'work_report')

    def test_normalize_ai_result_keeps_personal_task_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.82,
            'action': 'list',
            'data_type': 'personal_task',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为个人任务列表',
        }, '查看个人任务')

        self.assertEqual(result['data_type'], 'personal_task')

    def test_normalize_ai_result_keeps_personal_note_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.82,
            'action': 'list',
            'data_type': 'personal_note',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为个人笔记列表',
        }, '查看个人笔记')

        self.assertEqual(result['data_type'], 'personal_note')

    def test_normalize_ai_result_keeps_project_document_subtype(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        result = classifier._normalize_ai_result({
            'intent': 'DATA_QUERY',
            'confidence': 0.83,
            'action': 'list',
            'data_type': 'project_document',
            'entities': {},
            'time_range': None,
            'status': None,
            'customer_name': None,
            'requires_confirmation': False,
            'reasoning': '识别为项目文档列表',
        }, '看一下项目文档')

        self.assertEqual(result['data_type'], 'project_document')


class AIConfigurationSourceTests(SimpleTestCase):
    def test_project_mcp_exposes_ai_center_query_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        ai_model_query = next(item for item in capabilities if item['id'] == 'query.ai_model_config.list')

        self.assertEqual(ai_model_query['permission_code'], 'user.view_model_config')
        self.assertEqual(ai_model_query['module'], 'AI智能中心')

    def test_project_mcp_exposes_supply_chain_query_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        forecast_query = next(item for item in capabilities if item['id'] == 'query.supply_chain_forecast.list')

        self.assertEqual(forecast_query['permission_code'], 'user.view_supply_chain_forecast')
        self.assertEqual(forecast_query['module'], '供应链管理')

    def test_project_mcp_exposes_advanced_finance_query_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        account_query = next(item for item in capabilities if item['id'] == 'query.finance_account.list')

        self.assertEqual(account_query['permission_code'], 'finance.view_financeaccount')
        self.assertEqual(account_query['module'], '财务管理')

    def test_project_mcp_exposes_advanced_finance_bank_transaction_write_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        bank_tx_create = next(item for item in capabilities if item['id'] == 'write.finance_bank_transaction.create')

        self.assertEqual(bank_tx_create['permission_code'], 'finance.add_banktransaction')
        self.assertEqual(bank_tx_create['target_url'], '/finance/advanced/bank-transaction/add/')

    def test_project_mcp_exposes_reward_punishment_query_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        reward_query = next(item for item in capabilities if item['id'] == 'query.reward_punishment.list')

        self.assertEqual(reward_query['permission_code'], 'user.view_reward_punishment')
        self.assertEqual(reward_query['module'], '人事管理')

    def test_project_mcp_exposes_bom_create_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        bom_create = next(item for item in capabilities if item['id'] == 'write.bom.create')

        self.assertEqual(bom_create['permission_code'], 'user.add_bom')
        self.assertEqual(bom_create['target_url'], '/production/bom/add/')

    def test_project_mcp_exposes_approval_type_query_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        approval_type_query = next(item for item in capabilities if item['id'] == 'query.approval_type.list')

        self.assertEqual(approval_type_query['permission_code'], 'approval.view_approvaltype')
        self.assertEqual(approval_type_query['module'], '审批管理')

    def test_project_mcp_exposes_approval_step_create_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        approval_step_create = next(item for item in capabilities if item['id'] == 'write.approval_step.create')

        self.assertEqual(approval_step_create['permission_code'], 'approval.add_approvalstep')
        self.assertEqual(approval_step_create['target_url'], '/approval/approvalflow/{flow_id}/step/add/')

    def test_project_mcp_exposes_meeting_minutes_query_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        meeting_minutes_query = next(item for item in capabilities if item['id'] == 'query.meeting_minutes.list')

        self.assertEqual(meeting_minutes_query['permission_code'], 'user.view_meeting_minutes')
        self.assertEqual(meeting_minutes_query['module'], '办公管理')

    def test_project_mcp_exposes_meeting_minutes_create_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        meeting_minutes_create = next(item for item in capabilities if item['id'] == 'write.meeting_minutes.create')

        self.assertEqual(meeting_minutes_create['permission_code'], 'user.add_meeting_minutes')
        self.assertEqual(meeting_minutes_create['target_url'], '/personal/minutes/add/')

    def test_project_mcp_registry_exposes_query_and_write_capabilities(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        capability_ids = {item['id'] for item in capabilities}

        self.assertIn('query.approval_task.list', capability_ids)
        self.assertIn('write.order.create', capability_ids)

        order_create = next(item for item in capabilities if item['id'] == 'write.order.create')
        self.assertEqual(order_create['resource'], 'order')
        self.assertEqual(order_create['execution_mode'], 'business_handoff')
        self.assertIn('record_write', order_create['skill_tags'])

    def test_project_mcp_write_capability_uses_explicit_permission_code(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        document_create = next(item for item in capabilities if item['id'] == 'write.document.create')

        self.assertEqual(document_create['permission_code'], 'system.add_document')

    def test_project_mcp_exposes_document_publish_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        document_publish = next(item for item in capabilities if item['id'] == 'write.document.publish')

        self.assertEqual(document_publish['permission_code'], 'system.change_document_publish')
        self.assertEqual(document_publish['target_url'], '/system/admin_office/document/publish/{id}/')

    def test_project_mcp_exposes_project_document_create_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        project_document_create = next(item for item in capabilities if item['id'] == 'write.project_document.create')

        self.assertEqual(project_document_create['permission_code'], 'project.add_project_document')
        self.assertEqual(project_document_create['target_url'], '/project/document/add/')

    def test_project_mcp_exposes_personal_task_create_capability_without_permission_code(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        personal_task_create = next(item for item in capabilities if item['id'] == 'write.personal_task.create')

        self.assertIsNone(personal_task_create['permission_code'])
        self.assertEqual(personal_task_create['target_url'], '/personal/task/add/')

    def test_project_mcp_exposes_contact_create_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        contact_create = next(item for item in capabilities if item['id'] == 'write.contact.create')

        self.assertEqual(contact_create['permission_code'], 'customer.add_customer')
        self.assertEqual(contact_create['target_url'], '/customer/')

    def test_project_mcp_exposes_production_task_create_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        production_task_create = next(item for item in capabilities if item['id'] == 'write.production_task.create')

        self.assertEqual(production_task_create['permission_code'], 'user.add_production_task')
        self.assertEqual(production_task_create['target_url'], '/production/task/execution/add/')

    def test_project_mcp_exposes_finance_expense_query_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        expense_query = next(item for item in capabilities if item['id'] == 'query.finance_expense.list')

        self.assertEqual(expense_query['permission_code'], 'finance.view_expense')

    def test_project_mcp_exposes_finance_expense_create_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        expense_create = next(item for item in capabilities if item['id'] == 'write.finance_expense.create')

        self.assertEqual(expense_create['permission_code'], 'finance.add_reimbursement')
        self.assertEqual(expense_create['target_url'], '/finance/expense/add/')

    def test_project_mcp_exposes_production_task_query_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        production_task_query = next(item for item in capabilities if item['id'] == 'query.production_task.list')

        self.assertEqual(production_task_query['permission_code'], 'production.view_productiontask')

    def test_project_mcp_exposes_alert_approve_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        alert_approve = next(item for item in capabilities if item['id'] == 'write.alert.approve')

        self.assertEqual(alert_approve['permission_code'], 'inventory.change_inventoryalert')
        self.assertEqual(alert_approve['target_url'], '/inventory/alert/')

    def test_project_mcp_exposes_finance_order_record_update_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capabilities = project_mcp_service.get_capability_catalog()
        order_record_update = next(item for item in capabilities if item['id'] == 'write.finance_order_record.update')

        self.assertEqual(order_record_update['permission_code'], 'finance.change_orderfinancerecord')
        self.assertEqual(order_record_update['target_url'], '/finance/order-finance/')

    def test_project_mcp_matches_publish_operation_capability(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        matched = project_mcp_service.match_capabilities(
            '发布这份公文',
            {'intent': 'DATA_UPDATE', 'action': 'publish', 'data_type': 'document', 'entities': {}},
        )

        self.assertEqual(matched[0]['id'], 'write.document.publish')

    def test_ai_intent_prompt_includes_project_mcp_capability_context(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        classifier = AIIntentClassifier()
        classifier.ai_config = {
            'provider': 'openai',
            'model_name': 'gpt-5.5',
        }
        classifier.ai_client = MagicMock()
        classifier.ai_client.chat_completion.return_value = (
            '{"intent":"DATA_QUERY","confidence":0.91,"action":"list","data_type":"approval_task",'
            '"entities":{},"time_range":null,"status":null,"customer_name":null,'
            '"requires_confirmation":false,"reasoning":"识别为待审批查询"}'
        )

        with patch.object(classifier, '_get_training_data', return_value=[]):
            result = classifier._ai_classify_intent('看一下我的待审批流程')

        self.assertEqual(result['data_type'], 'approval_task')
        call_args = classifier.ai_client.chat_completion.call_args
        messages = call_args.kwargs.get('messages') or call_args.args[0]
        combined_prompt = '\n'.join(str(item.get('content', '')) for item in messages)
        self.assertIn('项目MCP能力目录', combined_prompt)
        self.assertIn('approval_task', combined_prompt)
        self.assertIn('order', combined_prompt)

    def test_config_manager_only_uses_database_configs(self):
        from apps.ai.utils.ai_config_manager import AIConfigManager

        db_config = {
            'id': 1,
            'name': '数据库配置',
            'provider': 'openai',
            'model_type': 'chat',
            'api_key': 'db-key',
            'api_base': 'https://db.example.com/v1',
            'model_name': 'db-model',
            'is_active': True,
        }

        with patch('apps.ai.utils.ai_config_manager.AICache.get_config', return_value=None), \
                patch('apps.ai.utils.ai_config_manager.AICache.set_config'), \
                patch('apps.ai.utils.ai_config_manager.AIModelConfig.get_active_runtime_configs', return_value=[db_config]), \
                patch.dict('os.environ', {
                    'AI_PROVIDER': 'openai',
                    'AI_API_KEY': 'env-key',
                    'AI_API_BASE': 'https://env.example.com/v1',
                    'AI_CHAT_MODEL': 'env-model',
                }, clear=False):
            manager = AIConfigManager()
            configs = manager.get_all_configs()

        self.assertEqual(list(configs.keys()), [1])
        self.assertEqual(configs[1]['api_key'], 'db-key')
        self.assertNotIn('settings-default', configs)

    def test_enhanced_intent_uses_service_unavailable_message_when_model_is_configured(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        intent_result = {
            'intent': 'DATA_QUERY',
            'confidence': 0.58,
            'source': 'safe_fallback',
            'action': 'list',
            'data_type': 'approval_task',
            'entities': {},
            'fallback_options': [],
            'ai_available': False,
            'ai_configured': True,
            'failure_reason': 'AI 模型暂时不可用',
            'model_provider': 'openai',
            'model_name': 'gpt-5.4',
        }

        response = service._create_confirmation_response(intent_result, '看一下我的待审批流程', None)

        self.assertTrue(response['success'])
        self.assertIn('AI 模型服务暂时不可用', response['message'])
        self.assertTrue(response['ai_configured'])
        self.assertEqual(response['failure_reason'], 'AI 模型暂时不可用')
        self.assertEqual(response['recognition_meta']['source_label'], '规则降级')
        self.assertEqual(response['recognition_meta']['status_label'], '模型不可用')
        self.assertEqual(response['mcp_context']['matched_capabilities'][0]['resource'], 'approval_task')
        self.assertIn('query_execute', response['mcp_context']['skill_hints'])

    def test_enhanced_intent_inherits_approval_count_follow_up_from_previous_query(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        intent_result = {
            'intent': 'AI_CHAT',
            'confidence': 0.32,
            'entities': {},
            'action': 'chat',
            'data_type': None,
        }

        patched = service._apply_follow_up_context(
            intent_result,
            '数量呢',
            {
                'previous_query': {
                    'specific_intent': 'approval_task_list',
                    'entities': {'status': 'pending'},
                }
            },
        )

        self.assertEqual(patched['intent'], 'DATA_QUERY')
        self.assertEqual(patched['action'], 'count')
        self.assertEqual(patched['data_type'], 'approval_task')
        self.assertEqual(patched['entities']['status'], 'pending')

    def test_enhanced_intent_inherits_project_status_follow_up_from_previous_query(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        intent_result = {
            'intent': 'AI_CHAT',
            'confidence': 0.28,
            'entities': {},
            'action': 'chat',
            'data_type': None,
        }

        patched = service._apply_follow_up_context(
            intent_result,
            '进行中的呢',
            {
                'previous_query': {
                    'specific_intent': 'project_list',
                    'entities': {},
                }
            },
        )

        self.assertEqual(patched['intent'], 'DATA_QUERY')
        self.assertEqual(patched['action'], 'list')
        self.assertEqual(patched['data_type'], 'project')
        self.assertEqual(patched['entities']['status'], '进行中')

    def test_enhanced_intent_inherits_detail_follow_up_from_previous_count_query(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        intent_result = {
            'intent': 'AI_CHAT',
            'confidence': 0.21,
            'entities': {},
            'action': 'chat',
            'data_type': None,
        }

        patched = service._apply_follow_up_context(
            intent_result,
            '明细呢',
            {
                'previous_query': {
                    'specific_intent': 'supplier_count',
                    'entities': {},
                }
            },
        )

        self.assertEqual(patched['intent'], 'DATA_QUERY')
        self.assertEqual(patched['action'], 'list')
        self.assertEqual(patched['data_type'], 'supplier')

    def test_ai_chat_prompt_includes_project_page_context(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(is_authenticated=True, id=7)
        ai_client = MagicMock()
        ai_client.chat_completion.return_value = {'content': '我可以帮你查看项目数据。'}

        page_context = {
            'title': '项目风险分析',
            'path': '/project/ai/risk-prediction/',
            'module': '项目交付',
        }

        with patch('apps.ai.services.enhanced_intent_service.ai_intent_classifier._ensure_ai_client', return_value=True), \
                patch('apps.ai.services.enhanced_intent_service.ai_intent_classifier.ai_client', ai_client), \
                patch('apps.ai.services.enhanced_intent_service.ai_intent_classifier.ai_config', {
                    'provider': 'openai',
                    'model_name': 'gpt-5.5',
                    'api_base': 'https://example.com/v1',
                    'model_names': ['gpt-5.5'],
                }):
            response = service._handle_ai_chat(
                user,
                '帮我看看这个项目能做什么',
                {'page_context': page_context},
            )

        self.assertTrue(response['success'])
        messages = ai_client.chat_completion.call_args.kwargs['messages']
        system_prompt = messages[0]['content']
        self.assertIn('DTCall', system_prompt)
        self.assertIn('项目风险分析', system_prompt)
        self.assertIn('项目交付', system_prompt)

    def test_ai_chat_meta_question_returns_current_model_info(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(is_authenticated=True, id=7)
        ai_client = MagicMock()
        ai_client.chat_completion.return_value = {'content': '我是通用模型助手。'}

        with patch('apps.ai.services.enhanced_intent_service.ai_intent_classifier._ensure_ai_client', return_value=True), \
                patch('apps.ai.services.enhanced_intent_service.ai_intent_classifier.ai_client', ai_client), \
                patch('apps.ai.services.enhanced_intent_service.ai_intent_classifier.ai_config', {
                    'provider': 'openai',
                    'model_name': 'gpt-5.5',
                    'api_base': 'https://example.com/v1',
                    'model_names': ['gpt-5.5'],
                }):
            response = service._handle_ai_chat(
                user,
                '你是什么模型？',
                {'page_context': {'title': '工作台', 'path': '/home/', 'module': '工作台'}},
            )

        self.assertTrue(response['success'])
        self.assertIn('gpt-5.5', response['result'])
        self.assertIn('https://example.com/v1', response['result'])
        self.assertNotIn('OpenAI 训练', response['result'])

    def test_approval_create_handoff_stays_enabled_without_permission_node(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: False,
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'approval',
                'entities': {},
                'confidence': 0.91,
            },
            '我要请假',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/approval/apply/')
        self.assertIsNone(task['disabled_reason'])
        self.assertTrue(task['permission_exists'])
        self.assertTrue(task['has_business_permission'])
        self.assertEqual(task['options'][0]['target_url'], '/approval/apply/')
        self.assertTrue(task['options'][0]['enabled'])

    def test_approval_task_handoff_list_button_remains_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: False,
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_QUERY',
                'action': 'list',
                'data_type': 'approval_task',
                'entities': {'status': 'pending'},
                'confidence': 0.89,
            },
            '看一下我的待审批',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/approval/pending/')
        self.assertIsNone(task['disabled_reason'])
        self.assertTrue(task['options'][0]['enabled'])

    def test_mutating_confirmation_response_prefers_dialog_execution(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: True,
        )

        response = service._create_confirmation_response(
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'approval',
                'entities': {'title': '新增审批'},
                'confidence': 0.95,
                'source': 'ai',
                'ai_available': True,
                'ai_configured': True,
            },
            '新增一个审批',
            user,
        )

        self.assertTrue(response['requires_confirmation'])
        self.assertIn('确认后直接执行', response['message'])
        self.assertIn('task', response)
        self.assertEqual(response['task']['type'], 'business_handoff')
        self.assertIn('回退记录', response['task']['safety_notice'])
        self.assertNotEqual(response['task']['options'][0]['action'], 'open_business_page')

    def test_ai_chat_prompt_describes_confirm_then_execute_for_write_requests(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        prompt = service._build_ai_chat_system_prompt(
            '帮我请假',
            conversation_context={},
            ai_config={'model_name': 'gpt-5.5'},
        )

        self.assertIn('确认后直接执行', prompt)
        self.assertIn('单条回退记录', prompt)
        self.assertIn('请假、出差、报销、采购', prompt)
        self.assertIn('人事', prompt)
        self.assertIn('个人办公', prompt)
        self.assertNotIn('不要声称会直接新增、修改、删除业务数据', prompt)

    def test_order_create_handoff_uses_order_create_url(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm == 'user.add_customer_order',
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'order',
                'entities': {'customer_name': '阿里云国际站'},
                'confidence': 0.9,
            },
            '帮我添加一个订单，客户是阿里云国际站，订单金额：1100',
        )

        self.assertEqual(task['data_type'], 'order')
        self.assertEqual(task['target_url'], '/customer/orders/create/')
        self.assertIn('新增客户订单', task['message'])

    def test_inventory_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'inventory.add_inventoryitem'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'inventory',
                'entities': {'name': '轴承'},
                'confidence': 0.9,
            },
            '新增一个库存物料，叫轴承',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/inventory/item/add/')
        self.assertIsNone(task['disabled_reason'])

    def test_document_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'system.add_document'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'document',
                'entities': {'title': '质量巡检通知'},
                'confidence': 0.92,
            },
            '起草一份质量巡检通知',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/system/admin_office/document/create/')
        self.assertIsNone(task['disabled_reason'])

    def test_document_publish_handoff_uses_action_target_url(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'system.change_document_publish'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_UPDATE',
                'action': 'publish',
                'data_type': 'document',
                'entities': {'id': 8},
                'confidence': 0.9,
            },
            '发布这份公文',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/system/admin_office/document/publish/8/')
        self.assertEqual(task['title'], '发布文档')

    def test_warehouse_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'inventory.add_warehouse'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'warehouse',
                'entities': {'name': '华东成品仓'},
                'confidence': 0.91,
            },
            '新增一个华东成品仓',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/inventory/warehouse/add/')
        self.assertIsNone(task['disabled_reason'])

    def test_project_document_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'project.add_project_document'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'project_document',
                'entities': {'title': '实施方案'},
                'confidence': 0.9,
            },
            '新增一个项目文档，标题叫实施方案',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/project/document/add/')
        self.assertIsNone(task['disabled_reason'])

    def test_position_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'position.add_position'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'position',
                'entities': {'title': '招商主管'},
                'confidence': 0.9,
            },
            '新增一个岗位，叫招商主管',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/position/add/')
        self.assertIsNone(task['disabled_reason'])

    def test_personal_task_create_handoff_is_enabled_for_authenticated_user(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: False,
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'personal_task',
                'entities': {'title': '跟进供应商报价'},
                'confidence': 0.9,
            },
            '帮我新增一个个人任务，跟进供应商报价',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/personal/task/add/')
        self.assertIsNone(task['disabled_reason'])

    def test_contact_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'customer.add_customer'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'contact',
                'entities': {'contact_person': '张三', 'phone': '13800000000'},
                'confidence': 0.9,
            },
            '给客户新增一个联系人张三',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/customer/')
        self.assertIsNone(task['disabled_reason'])

    def test_production_task_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'user.add_production_task'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'production_task',
                'entities': {'name': '装配工单'},
                'confidence': 0.9,
            },
            '新增一个生产任务',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/production/task/execution/add/')
        self.assertIsNone(task['disabled_reason'])

    def test_finance_expense_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'finance.add_reimbursement'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'finance_expense',
                'entities': {'code': 'BX-001'},
                'confidence': 0.9,
            },
            '新增一张报销单',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/finance/expense/add/')
        self.assertIsNone(task['disabled_reason'])

    def test_alert_approve_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'inventory.change_inventoryalert'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_UPDATE',
                'action': 'approve',
                'data_type': 'alert',
                'entities': {'object_ids': [12]},
                'confidence': 0.9,
            },
            '处理这个库存预警',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/inventory/alert/')
        self.assertIsNone(task['disabled_reason'])

    def test_finance_order_record_update_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'finance.change_orderfinancerecord'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_UPDATE',
                'action': 'update',
                'data_type': 'finance_order_record',
                'entities': {'object_ids': [63]},
                'confidence': 0.9,
            },
            '更新这条订单财务记录',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/finance/order-finance/')
        self.assertIsNone(task['disabled_reason'])

    def test_meeting_create_handoff_uses_apply_permission(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm == 'user.apply_meeting',
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'meeting',
                'entities': {'title': '项目例会'},
                'confidence': 0.9,
            },
            '帮我安排一个项目例会',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/oa/meeting/apply/')
        self.assertEqual(task['permission_required']['full_code'], 'user.apply_meeting')

    def test_ai_model_config_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'user.add_model_config'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'ai_model_config',
                'entities': {'name': 'OpenAI主模型'},
                'confidence': 0.9,
            },
            '新增一个 AI 模型配置',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/ai/model-config/create/')
        self.assertEqual(task['permission_required']['full_code'], 'user.add_model_config')

    def test_supply_chain_forecast_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'user.add_supply_chain_forecast'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'supply_chain_forecast',
                'entities': {'name': '7月备料预测'},
                'confidence': 0.9,
            },
            '新增一个需求预测计划',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/supply-chain/forecast/create/')
        self.assertEqual(task['permission_required']['full_code'], 'user.add_supply_chain_forecast')

    def test_finance_account_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'finance.add_financeaccount'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'finance_account',
                'entities': {'name': '招商银行基本户'},
                'confidence': 0.9,
            },
            '新增一个资金账户',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/finance/advanced/account/add/')
        self.assertEqual(task['permission_required']['full_code'], 'finance.add_financeaccount')

    def test_finance_bank_transaction_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'finance.add_banktransaction'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'finance_bank_transaction',
                'entities': {'summary': '银行来款'},
                'confidence': 0.9,
            },
            '新增一条银行流水',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/finance/advanced/bank-transaction/add/')
        self.assertEqual(task['permission_required']['full_code'], 'finance.add_banktransaction')

    def test_reward_punishment_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'user.add_reward_punishment'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'reward_punishment',
                'entities': {'title': '季度优秀员工奖励'},
                'confidence': 0.9,
            },
            '新增一条季度优秀员工奖励记录',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/user/reward-punishment/add/')
        self.assertEqual(task['permission_required']['full_code'], 'user.add_reward_punishment')

    def test_bom_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'user.add_bom'},
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'bom',
                'entities': {'name': '主板BOM'},
                'confidence': 0.9,
            },
            '新增一个主板BOM',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/production/bom/add/')
        self.assertEqual(task['permission_required']['full_code'], 'user.add_bom')

    def test_approval_flow_create_handoff_uses_model_permission(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm == 'approval.add_approvalflow',
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'approval_flow',
                'entities': {'name': '采购审批流'},
                'confidence': 0.93,
            },
            '新增一个采购审批流程',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/approval/approvalflow/add/')
        self.assertEqual(task['permission_required']['full_code'], 'approval.add_approvalflow')

    def test_approval_type_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm == 'approval.add_approvaltype',
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'approval_type',
                'entities': {'name': '用印审批'},
                'confidence': 0.91,
            },
            '新增一个用印审批类型',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/approval/approval_type/add/')
        self.assertEqual(task['permission_required']['full_code'], 'approval.add_approvaltype')

    def test_approval_step_create_handoff_is_enabled_when_flow_id_present(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm == 'approval.add_approvalstep',
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'approval_step',
                'entities': {'flow_id': 12, 'step_name': '部门负责人审批'},
                'confidence': 0.9,
            },
            '给流程12新增一个部门负责人审批步骤',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/approval/approvalflow/12/step/add/')
        self.assertEqual(task['permission_required']['full_code'], 'approval.add_approvalstep')

    def test_approval_step_create_handoff_requires_flow_id(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm == 'approval.add_approvalstep',
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'approval_step',
                'entities': {'step_name': '部门负责人审批'},
                'confidence': 0.9,
            },
            '新增一个部门负责人审批步骤',
        )

        self.assertFalse(task['enabled'])
        self.assertIn('流程', task['message'])

    def test_meeting_minutes_create_handoff_is_enabled(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm == 'user.add_meeting_minutes',
        )

        task = service._build_business_handoff(
            user,
            {
                'intent': 'DATA_CREATE',
                'action': 'create',
                'data_type': 'meeting_minutes',
                'entities': {'title': '周例会纪要'},
                'confidence': 0.91,
            },
            '新增一份周例会纪要',
        )

        self.assertTrue(task['enabled'])
        self.assertEqual(task['target_url'], '/personal/minutes/add/')
        self.assertEqual(task['permission_required']['full_code'], 'user.add_meeting_minutes')

    def test_safe_fallback_ambiguous_write_requires_business_type_clarification(self):
        from apps.ai.services.enhanced_intent_service import EnhancedIntentService

        service = EnhancedIntentService()
        user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda perm: perm in {'user.add_customer', 'user.add_customer_order'},
        )
        intent_result = {
            'intent': 'DATA_CREATE',
            'confidence': 0.58,
            'source': 'safe_fallback',
            'action': 'create',
            'data_type': 'order',
            'entities': {
                'candidate_data_types': ['order', 'customer'],
                'customer_name': '阿里云国际站',
            },
            'fallback_options': [],
            'ai_available': False,
            'ai_configured': True,
            'failure_reason': 'AI 模型暂时不可用',
            'model_provider': 'openai',
            'model_name': 'gpt-5.4',
        }

        response = service._create_confirmation_response(
            intent_result,
            '帮我添加一个订单，客户是阿里云国际站，订单金额：1100',
            user,
        )

        self.assertTrue(response['requires_confirmation'])
        self.assertIn('请先确认具体业务类型', response['message'])
        self.assertIsNone(response['task']['target_url'])
        self.assertEqual(response['task']['options'][0]['action'], 'clarify_business_type')
        self.assertEqual(response['task']['options'][0]['data_type'], 'order')
        self.assertEqual(response['task']['options'][1]['data_type'], 'customer')
        self.assertEqual(response['mcp_context']['matched_capabilities'][0]['resource'], 'order')
        self.assertIn('record_write', response['mcp_context']['skill_hints'])

    def test_chat_template_safe_business_urls_include_approval(self):
        content = Path('templates/ai/chat.html').read_text(encoding='utf-8')

        self.assertIn("'/approval/'", content)

    def test_chat_template_contains_recognition_source_labels(self):
        content = Path('templates/ai/chat.html').read_text(encoding='utf-8')

        self.assertIn('AI识别', content)
        self.assertIn('规则降级', content)
        self.assertIn('模型不可用', content)

    def test_project_mcp_capability_api_returns_catalog(self):
        from apps.ai.views import ProjectMCPCapabilityAPIView

        factory = RequestFactory()
        request = factory.get('/ai/project-mcp/capabilities/?q=待审批流程')
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda perm: True)

        response = ProjectMCPCapabilityAPIView.as_view()(request)
        payload = json.loads(response.content.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['protocol'], 'project-mcp')
        self.assertTrue(any(item['resource'] == 'approval_task' for item in payload['matched_capabilities']))


class STTDatabaseOnlyConfigTests(SimpleTestCase):
    def test_openai_stt_does_not_fallback_to_settings_when_database_missing(self):
        from apps.ai.utils.stt_service import OpenAISTTService

        with patch('apps.ai.utils.stt_service.get_stt_config_from_db', return_value=None):
            service = OpenAISTTService()

        self.assertIsNone(service.api_key)
        self.assertEqual(service.base_url, 'https://api.openai.com/v1')


class AIQueryServiceIntentCoverageTests(SimpleTestCase):
    def test_recognize_disk_share_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下共享链接')

        self.assertEqual(intent, 'disk_share_list')
        self.assertEqual(entities, {})

    def test_recognize_approval_task_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('我有哪些待审批流程')

        self.assertEqual(intent, 'approval_task_list')
        self.assertEqual(entities['status'], 'pending')

    def test_recognize_production_task_keeps_production_context(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查询生产任务')

        self.assertEqual(intent, 'production_task_list')
        self.assertEqual(entities, {})

    def test_recognize_notice_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下最新公告')

        self.assertEqual(intent, 'notice_list')
        self.assertEqual(entities, {})

    def test_recognize_company_notice_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('公司公告有哪些')

        self.assertEqual(intent, 'notice_list')
        self.assertEqual(entities['notice_type'], 'company')

    def test_recognize_system_notice_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('系统通知有多少')

        self.assertEqual(intent, 'notice_count')
        self.assertEqual(entities['notice_type'], 'system')

    def test_recognize_urgent_notice_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('紧急通知有哪些')

        self.assertEqual(intent, 'notice_list')
        self.assertEqual(entities['notice_type'], 'urgent')

    def test_recognize_schedule_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下我今天的日程安排')

        self.assertEqual(intent, 'schedule_list')
        self.assertEqual(entities['time_range'], 'today')

    def test_recognize_contract_total_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('合同金额总和是多少')

        self.assertEqual(intent, 'contract_total')
        self.assertEqual(entities, {})

    def test_recognize_project_in_progress_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看看进行中的项目')

        self.assertEqual(intent, 'project_list_in_progress')
        self.assertEqual(entities['status'], '进行中')

    def test_recognize_approval_task_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('我还有几个待审批')

        self.assertEqual(intent, 'approval_task_count')
        self.assertEqual(entities['status'], 'pending')

    def test_recognize_completed_approval_task_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('我已审批的流程有哪些')

        self.assertEqual(intent, 'approval_task_list')
        self.assertEqual(entities['status'], 'completed')

    def test_recognize_created_by_me_ongoing_approval_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('我发起但未结束的审批有哪些')

        self.assertEqual(intent, 'approval_list')
        self.assertEqual(entities['scope'], 'created_by_me')
        self.assertEqual(entities['status'], 'ongoing')

    def test_recognize_finance_income_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下回款记录')

        self.assertEqual(intent, 'finance_income_list')
        self.assertEqual(entities, {})

    def test_recognize_finance_overview_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('财务有哪些')

        self.assertEqual(intent, 'finance_expense_list')
        self.assertEqual(entities, {})

    def test_recognize_finance_account_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('启用资金账户有哪些')

        self.assertEqual(intent, 'finance_account_list')
        self.assertEqual(entities['status'], 'active')

    def test_recognize_finance_budget_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('执行中的预算有多少')

        self.assertEqual(intent, 'finance_budget_count')
        self.assertEqual(entities['status'], 'active')

    def test_recognize_receivable_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('逾期应收账款有哪些')

        self.assertEqual(intent, 'finance_receivable_list')
        self.assertEqual(entities['status'], 'overdue')

    def test_recognize_payable_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('待付款应付账款有几个')

        self.assertEqual(intent, 'finance_payable_count')
        self.assertEqual(entities['status'], 'pending')

    def test_recognize_bank_transaction_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('未匹配银行流水有哪些')

        self.assertEqual(intent, 'finance_bank_transaction_list')
        self.assertEqual(entities['match_status'], 'unmatched')

    def test_recognize_supply_chain_forecast_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('评审中的需求预测有哪些')

        self.assertEqual(intent, 'supply_chain_forecast_list')
        self.assertEqual(entities['status'], 'reviewing')

    def test_recognize_supply_chain_outsource_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('缺料委外发料单有几个')

        self.assertEqual(intent, 'supply_chain_outsource_count')
        self.assertEqual(entities['status'], 'shortage')

    def test_recognize_supply_chain_pr_review_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('异常PR审核任务有哪些')

        self.assertEqual(intent, 'supply_chain_pr_review_list')
        self.assertTrue(entities['is_abnormal'])

    def test_recognize_supply_chain_price_review_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('异常单价复核单有哪些')

        self.assertEqual(intent, 'supply_chain_price_review_list')
        self.assertEqual(entities['status'], 'exception')

    def test_recognize_supply_chain_sample_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('待领样打样申请有多少')

        self.assertEqual(intent, 'supply_chain_sample_count')
        self.assertEqual(entities['status'], 'pickup_pending')

    def test_recognize_ai_model_config_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('可用AI模型配置有哪些')

        self.assertEqual(intent, 'ai_model_config_list')
        self.assertTrue(entities['is_active'])

    def test_recognize_ai_knowledge_base_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('已发布知识库有多少')

        self.assertEqual(intent, 'ai_knowledge_base_count')
        self.assertEqual(entities['status'], 'published')

    def test_recognize_failed_ai_task_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('失败的AI任务有哪些')

        self.assertEqual(intent, 'ai_task_list')
        self.assertEqual(entities['status'], 'failed')

    def test_recognize_reward_punishment_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('奖励记录有哪些')

        self.assertEqual(intent, 'reward_punishment_list')
        self.assertEqual(entities['type'], 'reward')

    def test_recognize_bom_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('启用的BOM有多少')

        self.assertEqual(intent, 'bom_count')
        self.assertEqual(entities['status'], 'active')

    def test_recognize_active_approval_type_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('启用的审批类型有哪些')

        self.assertEqual(intent, 'approval_type_list')
        self.assertEqual(entities['status'], 'active')

    def test_recognize_returned_approval_record_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('退回的审批记录有哪些')

        self.assertEqual(intent, 'approval_record_list')
        self.assertEqual(entities['action'], 'return')

    def test_recognize_my_meeting_minutes_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('我的会议纪要有哪些')

        self.assertEqual(intent, 'meeting_minutes_list')
        self.assertEqual(entities['scope'], 'owned_by_me')

    def test_recognize_published_ai_workflow_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('已发布AI工作流有哪些')

        self.assertEqual(intent, 'ai_workflow_list')
        self.assertEqual(entities['status'], 'published')

    def test_recognize_production_overview_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('生产有哪些')

        self.assertEqual(intent, 'production_plan_list')
        self.assertEqual(entities, {})

    def test_recognize_today_production_task_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('今日生产任务有哪些')

        self.assertEqual(intent, 'production_task_list')
        self.assertEqual(entities['time_range'], 'today')

    def test_recognize_paused_production_task_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下已暂停生产任务')

        self.assertEqual(intent, 'production_task_list')
        self.assertEqual(entities['status'], 'paused')

    def test_recognize_completed_production_plan_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('已完成生产计划有哪些')

        self.assertEqual(intent, 'production_plan_list')
        self.assertEqual(entities['status'], 'completed')

    def test_recognize_maintenance_equipment_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('维修中的设备有多少')

        self.assertEqual(intent, 'production_equipment_count')
        self.assertEqual(entities['status'], 'maintenance')

    def test_recognize_disabled_equipment_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('停用设备有哪些')

        self.assertEqual(intent, 'production_equipment_list')
        self.assertEqual(entities['status'], 'disabled')

    def test_recognize_followup_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下最近的客户跟进记录')

        self.assertEqual(intent, 'followup_list')
        self.assertEqual(entities, {})

    def test_recognize_supplier_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下供应商')

        self.assertEqual(intent, 'supplier_list')
        self.assertEqual(entities, {})

    def test_recognize_inactive_supplier_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('停用供应商有哪些')

        self.assertEqual(intent, 'supplier_list')
        self.assertEqual(entities['status'], 'inactive')

    def test_recognize_product_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看看产品列表')

        self.assertEqual(intent, 'product_list')
        self.assertEqual(entities, {})

    def test_recognize_inventory_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('库存有多少')

        self.assertEqual(intent, 'inventory_count')
        self.assertEqual(entities, {})

    def test_recognize_disabled_warehouse_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('禁用仓库有哪些')

        self.assertEqual(intent, 'warehouse_list')
        self.assertEqual(entities['status'], 'inactive')

    def test_recognize_production_warehouse_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('生产仓库有几个')

        self.assertEqual(intent, 'warehouse_count')
        self.assertEqual(entities['warehouse_type'], 'production')

    def test_recognize_locked_inventory_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('锁定库存有哪些')

        self.assertEqual(intent, 'inventory_list')
        self.assertEqual(entities['status'], 'locked')

    def test_recognize_disk_shared_to_me_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下共享给我的网盘文件')

        self.assertEqual(intent, 'disk_list')
        self.assertEqual(entities['scope'], 'shared_to_me')

    def test_recognize_disk_share_created_by_me_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('我分享的文件链接')

        self.assertEqual(intent, 'disk_share_list')
        self.assertEqual(entities['scope'], 'created_by_me')


    def test_recognize_starred_disk_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看看我收藏的网盘文件')

        self.assertEqual(intent, 'disk_list')
        self.assertEqual(entities['status'], 'starred')

    def test_recognize_shared_disk_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('共享给我的文件有多少')

        self.assertEqual(intent, 'disk_count')
        self.assertEqual(entities['scope'], 'shared_to_me')

    def test_recognize_my_approval_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下我发起的审批')

        self.assertEqual(intent, 'approval_list')
        self.assertEqual(entities['scope'], 'created_by_me')

    def test_recognize_unread_message_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看看我的未读消息')

        self.assertEqual(intent, 'message_list')
        self.assertEqual(entities['status'], 'unread')


    def test_recognize_starred_message_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下我标星的消息')

        self.assertEqual(intent, 'message_list')
        self.assertEqual(entities['status'], 'starred')

    def test_recognize_read_message_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('我已读消息有多少')

        self.assertEqual(intent, 'message_count')
        self.assertEqual(entities['status'], 'read')

    def test_recognize_today_meeting_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('今天有哪些会议')

        self.assertEqual(intent, 'meeting_list')
        self.assertEqual(entities['time_range'], 'today')

    def test_recognize_this_week_schedule_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('本周日程安排')

        self.assertEqual(intent, 'schedule_list')
        self.assertEqual(entities['time_range'], 'this_week')

    def test_recognize_pending_payment_expense_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('待打款的报销有哪些')

        self.assertEqual(intent, 'finance_expense_list')
        self.assertEqual(entities['status'], 'pending_payment')

    def test_recognize_approved_expense_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('审核通过的报销有哪些')

        self.assertEqual(intent, 'finance_expense_list')
        self.assertEqual(entities['check_status'], 'approved')

    def test_recognize_pending_expense_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('待审核报销有多少')

        self.assertEqual(intent, 'finance_expense_count')
        self.assertEqual(entities['check_status'], 'pending')

    def test_recognize_pending_alert_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('未处理库存预警有多少')

        self.assertEqual(intent, 'alert_count')
        self.assertEqual(entities['status'], 'pending')

    def test_recognize_pending_stockin_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下待入库确认的入库单')

        self.assertEqual(intent, 'stockin_list')
        self.assertEqual(entities['status'], 'approved')

    def test_recognize_purchase_stockin_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('采购入库单有哪些')

        self.assertEqual(intent, 'stockin_list')
        self.assertEqual(entities['stock_type'], 'purchase')

    def test_recognize_stocked_stockout_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('已出库单据有多少')

        self.assertEqual(intent, 'stockout_count')
        self.assertEqual(entities['status'], 'stocked')

    def test_recognize_sale_stockout_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('销售出库单有多少')

        self.assertEqual(intent, 'stockout_count')
        self.assertEqual(entities['stock_type'], 'sale')

    def test_recognize_overdue_finance_order_record_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下逾期订单财务记录')

        self.assertEqual(intent, 'finance_order_record_list')
        self.assertEqual(entities['status'], 'overdue')

    def test_recognize_contact_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下联系人')

        self.assertEqual(intent, 'contact_list')
        self.assertEqual(entities, {})

    def test_recognize_contact_handoff_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下客户对接人')

        self.assertEqual(intent, 'contact_list')
        self.assertEqual(entities, {})

    def test_recognize_project_document_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下项目文档')

        self.assertEqual(intent, 'project_document_list')
        self.assertEqual(entities, {})

    def test_recognize_project_stage_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下项目阶段')

        self.assertEqual(intent, 'project_stage_list')
        self.assertEqual(entities, {})

    def test_recognize_project_category_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('项目分类有哪些')

        self.assertEqual(intent, 'project_category_list')
        self.assertEqual(entities, {})

    def test_recognize_work_type_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('工作类型有多少')

        self.assertEqual(intent, 'work_type_count')
        self.assertEqual(entities, {})

    def test_recognize_project_document_synonym_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下项目资料')

        self.assertEqual(intent, 'project_document_list')
        self.assertEqual(entities, {})

    def test_recognize_project_attachment_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下项目附件')

        self.assertEqual(intent, 'project_document_list')
        self.assertEqual(entities, {})

    def test_recognize_personal_task_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下我的个人任务')

        self.assertEqual(intent, 'personal_task_list')
        self.assertEqual(entities, {})

    def test_recognize_personal_task_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('有几个待办任务')

        self.assertEqual(intent, 'personal_task_count')
        self.assertEqual(entities, {})

    def test_recognize_completed_personal_task_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下已完成的个人任务')

        self.assertEqual(intent, 'personal_task_list')
        self.assertEqual(entities['status'], 'completed')

    def test_recognize_pending_personal_task_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('我还有几个个人待办')

        self.assertEqual(intent, 'personal_task_count')
        self.assertEqual(entities['status'], 'todo')

    def test_recognize_personal_note_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看下我的笔记')

        self.assertEqual(intent, 'personal_note_list')
        self.assertEqual(entities, {})

    def test_recognize_important_personal_note_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看看我的重要笔记')

        self.assertEqual(intent, 'personal_note_list')
        self.assertTrue(entities['is_important'])

    def test_recognize_personal_contact_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('打开个人通讯录')

        self.assertEqual(intent, 'personal_contact_list')
        self.assertEqual(entities, {})

    def test_recognize_private_contact_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下我的私人联系人')

        self.assertEqual(intent, 'personal_contact_list')
        self.assertEqual(entities, {})

    def test_recognize_enterprise_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下企业信息')

        self.assertEqual(intent, 'enterprise_list')
        self.assertEqual(entities, {})

    def test_recognize_enterprise_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('有几家企业')

        self.assertEqual(intent, 'enterprise_count')
        self.assertEqual(entities, {})

    def test_recognize_position_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下岗位信息')

        self.assertEqual(intent, 'position_list')
        self.assertEqual(entities, {})

    def test_recognize_position_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('岗位有多少个')

        self.assertEqual(intent, 'position_count')
        self.assertEqual(entities, {})

    def test_recognize_work_record_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下我的工作记录')

        self.assertEqual(intent, 'work_record_list')
        self.assertEqual(entities, {})

    def test_recognize_work_record_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('工作记录有多少条')

        self.assertEqual(intent, 'work_record_count')
        self.assertEqual(entities, {})


    def test_recognize_today_work_record_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看一下今天的工作记录')

        self.assertEqual(intent, 'work_record_list')
        self.assertEqual(entities['time_range'], 'today')

    def test_recognize_project_work_record_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('项目工作记录有多少')

        self.assertEqual(intent, 'work_record_count')
        self.assertEqual(entities['work_type'], 'project')

    def test_recognize_meeting_work_record_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('会议工作记录有哪些')

        self.assertEqual(intent, 'work_record_list')
        self.assertEqual(entities['work_type'], 'meeting')

    def test_recognize_work_report_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查看工作汇报')

        self.assertEqual(intent, 'work_report_list')
        self.assertEqual(entities, {})

    def test_recognize_work_report_daily_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('看看我上周的日报')

        self.assertEqual(intent, 'work_report_list')
        self.assertEqual(entities, {})

    def test_recognize_work_report_weekly_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下本月周报')

        self.assertEqual(intent, 'work_report_list')
        self.assertEqual(entities, {})

    def test_recognize_submitted_work_report_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下已提交的周报')

        self.assertEqual(intent, 'work_report_list')
        self.assertTrue(entities['is_submitted'])
        self.assertEqual(entities['report_type'], 'weekly')

    def test_recognize_draft_work_report_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('草稿日报有哪些')

        self.assertEqual(intent, 'work_report_list')
        self.assertFalse(entities['is_submitted'])
        self.assertEqual(entities['report_type'], 'daily')

    def test_recognize_phone_followup_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下电话跟进记录')

        self.assertEqual(intent, 'followup_list')
        self.assertEqual(entities['follow_type'], 'phone')

    def test_recognize_visit_followup_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('上门拜访跟进有多少')

        self.assertEqual(intent, 'followup_count')
        self.assertEqual(entities['follow_type'], 'visit')

    def test_recognize_payment_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('查一下付款记录')

        self.assertEqual(intent, 'payment_list')
        self.assertEqual(entities, {})

    def test_recognize_this_month_payment_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('本月付款记录')

        self.assertEqual(intent, 'payment_list')
        self.assertEqual(entities['time_range'], 'this_month')

    def test_recognize_last_month_income_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('上月回款有多少')

        self.assertEqual(intent, 'finance_income_count')
        self.assertEqual(entities['time_range'], 'last_month')

    def test_recognize_partial_income_invoice_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('部分回款的发票有哪些')

        self.assertEqual(intent, 'finance_invoice_list')
        self.assertEqual(entities['enter_status'], 'partial')

    def test_recognize_unissued_invoice_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('未开票的发票有多少')

        self.assertEqual(intent, 'finance_invoice_count')
        self.assertEqual(entities['status'], 'unissued')

    def test_recognize_inactive_employee_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('离职员工有哪些')

        self.assertEqual(intent, 'employee_list')
        self.assertEqual(entities['status'], 'inactive')

    def test_recognize_inactive_department_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('禁用部门有几个')

        self.assertEqual(intent, 'department_count')
        self.assertEqual(entities['status'], 'inactive')

    def test_recognize_pending_publish_document_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('待发布公文有哪些')

        self.assertEqual(intent, 'document_list')
        self.assertEqual(entities['status'], 'approved')

    def test_recognize_published_document_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('已发布公文有多少')

        self.assertEqual(intent, 'document_count')
        self.assertEqual(entities['status'], 'published')

    def test_recognize_owned_customer_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('我负责的客户有哪些')

        self.assertEqual(intent, 'customer_list')
        self.assertEqual(entities['scope'], 'owned_by_me')

    def test_recognize_customer_orders_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('张三公司的订单有哪些')

        self.assertEqual(intent, 'order_list')
        self.assertEqual(entities['customer_name'], '张三公司')


    def test_recognize_pending_order_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('待处理订单有哪些')

        self.assertEqual(intent, 'order_list')
        self.assertEqual(entities['status'], 'pending')

    def test_recognize_completed_order_list_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('已完成订单有哪些')

        self.assertEqual(intent, 'order_list')
        self.assertEqual(entities['status'], 'completed')

    def test_recognize_reviewing_contract_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('审核中的合同有哪些')

        self.assertEqual(intent, 'contract_list')
        self.assertEqual(entities['status'], 'reviewing')

    def test_recognize_owned_project_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('我负责的项目有哪些')

        self.assertEqual(intent, 'project_list')
        self.assertEqual(entities['scope'], 'owned_by_me')

    def test_recognize_paused_project_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('暂停项目有几个')

        self.assertEqual(intent, 'project_count_paused')
        self.assertEqual(entities['status'], 'paused')

    def test_recognize_owned_task_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('我负责的任务')

        self.assertEqual(intent, 'task_list')
        self.assertEqual(entities['scope'], 'owned_by_me')

    def test_recognize_completed_task_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('已完成任务有几个')

        self.assertEqual(intent, 'task_count')
        self.assertEqual(entities['status'], 'completed')

    def test_recognize_top_notice_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('置顶公告有哪些')

        self.assertEqual(intent, 'notice_list')
        self.assertEqual(entities['status'], 'top')

    def test_recognize_recent_notice_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('最近公告')

        self.assertEqual(intent, 'notice_list')
        self.assertEqual(entities['time_range'], 'recent')

    def test_recognize_last_week_meeting_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('上周会议有哪些')

        self.assertEqual(intent, 'meeting_list')
        self.assertEqual(entities['time_range'], 'last_week')

    def test_recognize_repair_asset_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('维修中的固定资产有哪些')

        self.assertEqual(intent, 'asset_list')
        self.assertEqual(entities['status'], 'repair')

    def test_recognize_scrap_vehicle_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('报废车辆有几个')

        self.assertEqual(intent, 'vehicle_count')
        self.assertEqual(entities['status'], 'scrap')

    def test_recognize_inactive_seal_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('停用印章有哪些')

        self.assertEqual(intent, 'seal_list')
        self.assertEqual(entities['status'], 'inactive')

    def test_recognize_finance_seal_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('财务专用章有哪些')

        self.assertEqual(intent, 'seal_list')
        self.assertEqual(entities['seal_type'], 'finance')

    def test_recognize_pending_seal_application_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('待审核用章申请有多少')

        self.assertEqual(intent, 'seal_application_count')
        self.assertEqual(entities['status'], 'pending')

    def test_recognize_pending_asset_repair_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('待处理资产报修记录有哪些')

        self.assertEqual(intent, 'asset_repair_list')
        self.assertEqual(entities['status'], 'pending')

    def test_recognize_vehicle_maintenance_count_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('车辆维修记录有几个')

        self.assertEqual(intent, 'vehicle_maintenance_count')
        self.assertEqual(entities['maintenance_type'], 'repair')

    def test_recognize_vehicle_fee_type_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('车辆保险费有哪些')

        self.assertEqual(intent, 'vehicle_fee_list')
        self.assertEqual(entities['fee_type'], 'insurance')

    def test_recognize_vehicle_oil_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('车辆油耗记录有哪些')

        self.assertEqual(intent, 'vehicle_oil_list')
        self.assertEqual(entities, {})

    def test_recognize_active_meeting_room_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('可用会议室有哪些')

        self.assertEqual(intent, 'meeting_room_list')
        self.assertEqual(entities['status'], 'active')

    def test_recognize_pending_meeting_reservation_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('待审核会议室预订有几个')

        self.assertEqual(intent, 'meeting_reservation_count')
        self.assertEqual(entities['status'], 'pending')

    def test_recognize_today_meeting_reservation_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('今天会议室预约有哪些')

        self.assertEqual(intent, 'meeting_reservation_list')
        self.assertEqual(entities['time_range'], 'today')

    def test_recognize_active_document_category_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('启用的公文分类有哪些')

        self.assertEqual(intent, 'document_category_list')
        self.assertEqual(entities['status'], 'active')

    def test_recognize_inactive_asset_category_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('停用资产分类有几个')

        self.assertEqual(intent, 'asset_category_count')
        self.assertEqual(entities['status'], 'inactive')

    def test_recognize_active_asset_brand_plain_language(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().recognize_intent('启用资产品牌有哪些')

        self.assertEqual(intent, 'asset_brand_list')
        self.assertEqual(entities['status'], 'active')

    def test_resolve_specific_intent_maps_asset_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查一下固定资产',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'asset',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'asset_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_seal_application_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '待审核用章申请数量',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'seal_application',
                'action': 'count',
                'entities': {'status': 'pending'},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'seal_application_count')
        self.assertEqual(entities['status'], 'pending')

    def test_resolve_specific_intent_maps_vehicle_fee_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查一下车辆费用',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'vehicle_fee',
                'action': 'list',
                'entities': {'fee_type': 'insurance'},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'vehicle_fee_list')
        self.assertEqual(entities['fee_type'], 'insurance')

    def test_resolve_specific_intent_maps_meeting_room_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查一下会议室',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'meeting_room',
                'action': 'list',
                'entities': {'status': 'active'},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'meeting_room_list')
        self.assertEqual(entities['status'], 'active')

    def test_resolve_specific_intent_maps_meeting_reservation_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查一下会议室预订',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'meeting_reservation',
                'action': 'count',
                'entities': {'status': 'pending'},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'meeting_reservation_count')
        self.assertEqual(entities['status'], 'pending')

    def test_resolve_specific_intent_maps_document_category_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查一下公文分类',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'document_category',
                'action': 'list',
                'entities': {'status': 'active'},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'document_category_list')
        self.assertEqual(entities['status'], 'active')

    def test_resolve_specific_intent_maps_asset_brand_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查一下资产品牌',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'asset_brand',
                'action': 'count',
                'entities': {'status': 'active'},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'asset_brand_count')
        self.assertEqual(entities['status'], 'active')

    def test_resolve_specific_intent_prefers_order_total_for_deal_amount_query(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '我问的是成交订单金额',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'finance',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'order_total')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_inherits_time_range_from_follow_up_query(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '而且是问的本月的',
            {
                'intent': 'DATA_QUERY',
                'data_type': None,
                'action': 'query',
                'entities': {},
                'source': 'ai',
            },
            context={
                'previous_query': {
                    'specific_intent': 'order_total',
                }
            },
        )

        self.assertEqual(intent, 'order_total_this_month')
        self.assertEqual(entities['time_range'], 'this_month')

    def test_resolve_specific_intent_routes_ai_customer_deal_this_month(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '帮我看下本月成交的客户有哪些',
            {
                'intent': 'DATA_QUERY',
                'confidence': 0.95,
                'action': 'list',
                'data_type': 'customer',
                'status': '成交',
                'time_range': 'this_month',
                'source': 'ai',
            },
        )

        self.assertEqual(intent, 'customer_deal_this_month')
        self.assertEqual(entities['status'], 'deal')
        self.assertEqual(entities['time_range'], 'this_month')

    def test_format_customer_deal_empty_result_uses_business_language(self):
        from apps.ai.services.query_service import QueryService

        message = QueryService().format_result({
            'type': 'list',
            'items': [],
            'total': 0,
            'data_type': 'customer',
            'status': 'deal',
            'time_range': 'this_month',
            'event': 'deal',
        })

        self.assertEqual(message, '暂无本月成交的客户数据。')

    def test_resolve_specific_intent_normalizes_chinese_order_status(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '处理中订单有哪些',
            {
                'intent': 'DATA_QUERY',
                'confidence': 0.93,
                'action': 'list',
                'data_type': 'order',
                'status': '处理中',
                'source': 'ai',
            },
        )

        self.assertEqual(intent, 'order_list')
        self.assertEqual(entities['status'], 'processing')

    def test_resolve_specific_intent_normalizes_chinese_invoice_status(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '已开票的客户发票有多少',
            {
                'intent': 'DATA_QUERY',
                'confidence': 0.94,
                'action': 'count',
                'data_type': 'invoice',
                'status': '已开票',
                'source': 'ai',
            },
        )

        self.assertEqual(intent, 'invoice_count')
        self.assertEqual(entities['status'], 'issued')

    def test_resolve_specific_intent_prefers_contract_total_for_contract_amount_query(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '合同金额总和是多少',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'finance',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'contract_total')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_inherits_count_from_approval_follow_up_query(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '数量呢',
            {
                'intent': 'DATA_QUERY',
                'data_type': None,
                'action': 'query',
                'entities': {},
                'source': 'ai',
            },
            context={
                'previous_query': {
                    'specific_intent': 'approval_task_list',
                    'entities': {'status': 'pending'},
                }
            },
        )

        self.assertEqual(intent, 'approval_task_count')
        self.assertEqual(entities['status'], 'pending')

    def test_resolve_specific_intent_inherits_count_from_project_follow_up_query(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '有几个',
            {
                'intent': 'DATA_QUERY',
                'data_type': None,
                'action': 'query',
                'entities': {},
                'source': 'ai',
            },
            context={
                'previous_query': {
                    'specific_intent': 'project_list_in_progress',
                    'entities': {'status': '进行中'},
                }
            },
        )

        self.assertEqual(intent, 'project_count_in_progress')
        self.assertEqual(entities['status'], 'in_progress')

    def test_resolve_specific_intent_inherits_list_from_count_follow_up_query(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '明细呢',
            {
                'intent': 'DATA_QUERY',
                'data_type': None,
                'action': 'query',
                'entities': {},
                'source': 'ai',
            },
            context={
                'previous_query': {
                    'specific_intent': 'supplier_count',
                    'entities': {},
                }
            },
        )

        self.assertEqual(intent, 'supplier_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_inherits_recent_notice_follow_up(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '前5个',
            {
                'intent': 'DATA_QUERY',
                'data_type': None,
                'action': 'query',
                'entities': {},
                'source': 'ai',
            },
            context={
                'previous_query': {
                    'specific_intent': 'notice_list',
                    'entities': {'time_range': 'recent'},
                }
            },
        )

        self.assertEqual(intent, 'notice_list')
        self.assertEqual(entities['time_range'], 'recent')

    def test_resolve_specific_intent_maps_finance_invoice_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '未开票的发票有哪些',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'finance_invoice',
                'action': 'list',
                'entities': {},
                'status': 'unissued',
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'finance_invoice_list')
        self.assertEqual(entities['status'], 'unissued')

    def test_resolve_specific_intent_maps_finance_income_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查一下回款记录',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'finance_income',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'finance_income_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_production_task_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查询生产任务',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'production_task',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'production_task_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_warehouse_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '看看仓库列表',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'warehouse',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'warehouse_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_stockin_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '看看入库单',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'stockin',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'stockin_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_stockout_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '看看出库单',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'stockout',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'stockout_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_alert_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '看看库存预警',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'alert',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'alert_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_contact_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查一下联系人',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'contact',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'contact_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_project_document_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '看一下项目文档',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'project_document',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'project_document_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_project_stage_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '看一下项目阶段',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'project_stage',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'project_stage_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_project_category_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '项目分类有哪些',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'project_category',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'project_category_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_work_type_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '工作类型有多少',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'work_type',
                'action': 'count',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'work_type_count')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_enterprise_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查看企业信息',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'enterprise',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'enterprise_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_position_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查看岗位',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'position',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'position_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_work_record_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查看工作记录',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'work_record',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'work_record_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_work_report_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查看工作汇报',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'work_report',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'work_report_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_payment_alias(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查一下付款记录',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'payment',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'payment_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_expense_alias(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查一下费用支出',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'expense',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'finance_expense_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_income_alias(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '查一下收入回款',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'income',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'finance_income_list')
        self.assertEqual(entities, {})

    def test_resolve_specific_intent_maps_workhour_subtype(self):
        from apps.ai.services.query_service import QueryService

        intent, entities = QueryService().resolve_specific_intent(
            '看一下工时记录',
            {
                'intent': 'DATA_QUERY',
                'data_type': 'workhour',
                'action': 'list',
                'entities': {},
                'source': 'ai',
            },
            context={},
        )

        self.assertEqual(intent, 'workhour_list')
        self.assertEqual(entities, {})


class AIQueryServiceDiskVisibilityTests(TestCase):
    def test_disk_list_only_returns_owned_or_shared_files(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.disk.models import DiskFile

        User = get_user_model()
        owner = User.objects.create_user(username='owner')
        recipient = User.objects.create_user(username='recipient')
        other = User.objects.create_user(username='other')
        shared = DiskFile.objects.create(
            name='共享方案.pdf',
            original_name='共享方案.pdf',
            file_path='disk/shared.pdf',
            owner=owner,
        )
        shared.shared_users.add(recipient)
        DiskFile.objects.create(
            name='私有方案.pdf',
            original_name='私有方案.pdf',
            file_path='disk/private.pdf',
            owner=other,
        )

        result = QueryService().handle_disk_list({}, recipient)
        names = {item['name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'共享方案.pdf'})

    def test_disk_folder_list_only_returns_owned_or_shared_folders(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.disk.models import DiskFolder

        User = get_user_model()
        owner = User.objects.create_user(username='folder-owner')
        recipient = User.objects.create_user(username='folder-recipient')
        other = User.objects.create_user(username='folder-other')
        shared = DiskFolder.objects.create(name='共享资料夹', owner=owner)
        shared.shared_users.add(recipient)
        DiskFolder.objects.create(name='私有资料夹', owner=other)

        result = QueryService().handle_disk_folder_list({}, recipient)
        names = {item['name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'共享资料夹'})

    def test_disk_list_shared_to_me_scope_excludes_owned_files(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.disk.models import DiskFile

        User = get_user_model()
        owner = User.objects.create_user(username='scope-owner')
        recipient = User.objects.create_user(username='scope-recipient')

        shared = DiskFile.objects.create(
            name='共享给我的文件.docx',
            original_name='共享给我的文件.docx',
            file_path='disk/shared-to-me.docx',
            owner=owner,
        )
        shared.shared_users.add(recipient)
        DiskFile.objects.create(
            name='我自己的文件.docx',
            original_name='我自己的文件.docx',
            file_path='disk/my-own.docx',
            owner=recipient,
        )

        result = QueryService().handle_disk_list({'scope': 'shared_to_me'}, recipient)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'共享给我的文件.docx'})

    def test_disk_share_list_created_by_me_scope_only_returns_my_shares(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.disk.models import DiskFile, DiskShare

        User = get_user_model()
        creator = User.objects.create_user(username='share-creator')
        other = User.objects.create_user(username='share-other')

        my_file = DiskFile.objects.create(
            name='我的分享文件.pdf',
            original_name='我的分享文件.pdf',
            file_path='disk/my-share.pdf',
            owner=creator,
        )
        other_file = DiskFile.objects.create(
            name='别人的分享文件.pdf',
            original_name='别人的分享文件.pdf',
            file_path='disk/other-share.pdf',
            owner=other,
        )

        DiskShare.objects.create(file=my_file, creator=creator, permission_type='view', share_type='link', share_code='mine-001')
        DiskShare.objects.create(file=other_file, creator=other, permission_type='view', share_type='link', share_code='other-001')

        result = QueryService().handle_disk_share_list({'scope': 'created_by_me'}, creator)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'我的分享文件.pdf'})


class AIQueryServiceOfficeVisibilityTests(TestCase):
    def test_asset_list_repair_scope_only_returns_repair_assets(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Asset

        User = get_user_model()
        user = User.objects.create_user(username='asset-query-user')

        Asset.objects.create(
            asset_number='ASSET-REPAIR',
            name='维修电脑',
            purchase_date=date.today(),
            purchase_price=5000,
            status='repair',
        )
        Asset.objects.create(
            asset_number='ASSET-NORMAL',
            name='正常电脑',
            purchase_date=date.today(),
            purchase_price=6000,
            status='normal',
        )

        result = QueryService().handle_asset_list({'status': 'repair'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'维修电脑'})

    def test_vehicle_count_scrap_scope_only_counts_scrapped_vehicles(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Vehicle

        User = get_user_model()
        user = User.objects.create_user(username='vehicle-query-user')

        Vehicle.objects.create(
            license_plate='京A00001',
            brand='大众',
            model='帕萨特',
            color='黑色',
            engine_number='ENG-SCRAP',
            frame_number='FRM-SCRAP',
            purchase_date=date.today(),
            purchase_price=100000,
            status='scrap',
        )
        Vehicle.objects.create(
            license_plate='京A00002',
            brand='丰田',
            model='凯美瑞',
            color='白色',
            engine_number='ENG-NORMAL',
            frame_number='FRM-NORMAL',
            purchase_date=date.today(),
            purchase_price=120000,
            status='normal',
        )

        result = QueryService().handle_vehicle_count({'status': 'scrap'}, user)

        self.assertEqual(result['value'], 1)

    def test_seal_list_inactive_scope_only_returns_inactive_seals(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Seal

        User = get_user_model()
        keeper = User.objects.create_user(username='seal-keeper')

        Seal.objects.create(name='停用公章', seal_type='company', keeper=keeper, is_active=False)
        Seal.objects.create(name='启用公章', seal_type='company', keeper=keeper, is_active=True)

        result = QueryService().handle_seal_list({'status': 'inactive'}, keeper)
        names = {item['name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'停用公章'})

    def test_seal_list_type_scope_only_returns_matching_seals(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Seal

        User = get_user_model()
        keeper = User.objects.create_user(username='seal-type-keeper')

        Seal.objects.create(name='财务章', seal_type='finance', keeper=keeper)
        Seal.objects.create(name='合同章', seal_type='contract', keeper=keeper)

        result = QueryService().handle_seal_list({'seal_type': 'finance'}, keeper)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'财务章'})

    def test_seal_application_list_pending_scope_only_returns_pending_applications(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Seal, SealApplication

        User = get_user_model()
        applicant = User.objects.create_user(username='seal-applicant')
        keeper = User.objects.create_user(username='seal-application-keeper')
        seal = Seal.objects.create(name='业务公章', seal_type='company', keeper=keeper)

        SealApplication.objects.create(
            seal=seal,
            applicant=applicant,
            purpose='合同盖章',
            document_title='待审核合同',
            use_date=date.today(),
            status='pending',
        )
        SealApplication.objects.create(
            seal=seal,
            applicant=applicant,
            purpose='协议盖章',
            document_title='已通过协议',
            use_date=date.today(),
            status='approved',
        )

        result = QueryService().handle_seal_application_list({'status': 'pending'}, applicant)
        titles = {item['document_title'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(titles, {'待审核合同'})

    def test_asset_repair_list_pending_scope_only_returns_pending_repairs(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Asset, AssetRepair

        User = get_user_model()
        reporter = User.objects.create_user(username='asset-repair-reporter')
        asset = Asset.objects.create(
            asset_number='ASSET-REPAIR-RECORD',
            name='报修电脑',
            purchase_date=date.today(),
            purchase_price=5000,
        )
        AssetRepair.objects.create(asset=asset, reporter=reporter, fault_description='不开机', status='pending')
        AssetRepair.objects.create(asset=asset, reporter=reporter, fault_description='屏幕坏', status='completed')

        result = QueryService().handle_asset_repair_list({'status': 'pending'}, reporter)
        descriptions = {item['fault_description'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(descriptions, {'不开机'})

    def test_vehicle_maintenance_list_type_scope_only_returns_repairs(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Vehicle, VehicleMaintenance

        User = get_user_model()
        operator = User.objects.create_user(username='vehicle-maintenance-operator')
        vehicle = Vehicle.objects.create(
            license_plate='京B00001',
            brand='大众',
            model='途观',
            color='蓝色',
            engine_number='ENG-MAINT',
            frame_number='FRM-MAINT',
            purchase_date=date.today(),
            purchase_price=100000,
        )
        VehicleMaintenance.objects.create(vehicle=vehicle, maintenance_type='repair', maintenance_date=date.today(), mileage=1000, cost=300, service_provider='维修厂', description='维修刹车', operator=operator)
        VehicleMaintenance.objects.create(vehicle=vehicle, maintenance_type='maintain', maintenance_date=date.today(), mileage=1100, cost=200, service_provider='保养店', description='常规保养', operator=operator)

        result = QueryService().handle_vehicle_maintenance_list({'maintenance_type': 'repair'}, operator)
        descriptions = {item['description'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(descriptions, {'维修刹车'})

    def test_vehicle_fee_list_type_scope_only_returns_insurance_fees(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Vehicle, VehicleFee

        User = get_user_model()
        operator = User.objects.create_user(username='vehicle-fee-operator')
        vehicle = Vehicle.objects.create(
            license_plate='京C00001',
            brand='丰田',
            model='荣放',
            color='白色',
            engine_number='ENG-FEE',
            frame_number='FRM-FEE',
            purchase_date=date.today(),
            purchase_price=130000,
        )
        VehicleFee.objects.create(vehicle=vehicle, fee_type='insurance', amount=3000, fee_date=date.today(), operator=operator)
        VehicleFee.objects.create(vehicle=vehicle, fee_type='fuel', amount=500, fee_date=date.today(), operator=operator)

        result = QueryService().handle_vehicle_fee_list({'fee_type': 'insurance'}, operator)
        fee_types = {item['fee_type'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(fee_types, {'保险费'})

    def test_vehicle_oil_list_returns_oil_records(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Vehicle, VehicleOil

        User = get_user_model()
        operator = User.objects.create_user(username='vehicle-oil-operator')
        vehicle = Vehicle.objects.create(
            license_plate='京D00001',
            brand='本田',
            model='雅阁',
            color='灰色',
            engine_number='ENG-OIL',
            frame_number='FRM-OIL',
            purchase_date=date.today(),
            purchase_price=150000,
        )
        VehicleOil.objects.create(vehicle=vehicle, oil_amount=30, oil_cost=240, mileage=1000, oil_date=date.today(), gas_station='测试加油站', operator=operator)

        result = QueryService().handle_vehicle_oil_list({}, operator)

        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['gas_station'], '测试加油站')

    def test_meeting_room_list_status_scope_only_returns_active_rooms(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.oa.models import MeetingRoom

        User = get_user_model()
        manager = User.objects.create_user(username='meeting-room-manager')
        MeetingRoom.objects.create(name='一号会议室', code='MR-001', location='1楼', capacity=12, status='active', manager=manager)
        MeetingRoom.objects.create(name='停用会议室', code='MR-002', location='2楼', capacity=8, status='inactive', manager=manager)

        result = QueryService().handle_meeting_room_list({'status': 'active'}, manager)
        names = {item['name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'一号会议室'})

    def test_meeting_reservation_list_filters_owner_status_and_today(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.oa.models import MeetingRoom
        from apps.system.models import MeetingReservation

        User = get_user_model()
        organizer = User.objects.create_user(username='meeting-reservation-owner')
        other = User.objects.create_user(username='meeting-reservation-other')
        room = MeetingRoom.objects.create(name='二号会议室', code='MR-003', location='3楼', capacity=16, status='active')
        today_start = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        MeetingReservation.objects.create(
            meeting_room=room,
            title='今日待审核会议',
            organizer=organizer,
            start_time=today_start,
            end_time=today_start + timedelta(hours=1),
            status='pending',
        )
        MeetingReservation.objects.create(
            meeting_room=room,
            title='他人的待审核会议',
            organizer=other,
            start_time=today_start,
            end_time=today_start + timedelta(hours=1),
            status='pending',
        )
        MeetingReservation.objects.create(
            meeting_room=room,
            title='今日已通过会议',
            organizer=organizer,
            start_time=today_start,
            end_time=today_start + timedelta(hours=1),
            status='approved',
        )

        result = QueryService().handle_meeting_reservation_list({'status': 'pending', 'time_range': 'today'}, organizer)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(titles, {'今日待审核会议'})

    def test_document_category_list_status_scope_only_returns_active_categories(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import DocumentCategory

        User = get_user_model()
        user = User.objects.create_user(username='document-category-query-user')
        DocumentCategory.objects.create(name='通知类', code='DOC-ACTIVE', is_active=True)
        DocumentCategory.objects.create(name='停用类', code='DOC-INACTIVE', is_active=False)

        result = QueryService().handle_document_category_list({'status': 'active'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'通知类'})

    def test_asset_category_list_status_scope_only_returns_inactive_categories(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import AssetCategory

        User = get_user_model()
        user = User.objects.create_user(username='asset-category-query-user')
        AssetCategory.objects.create(name='办公设备', code='ASSET-ACTIVE', is_active=True)
        AssetCategory.objects.create(name='停用设备', code='ASSET-INACTIVE', is_active=False)

        result = QueryService().handle_asset_category_list({'status': 'inactive'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'停用设备'})

    def test_asset_brand_list_status_scope_only_returns_active_brands(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import AssetBrand

        User = get_user_model()
        user = User.objects.create_user(username='asset-brand-query-user')
        AssetBrand.objects.create(name='联想', code='LENOVO', is_active=True)
        AssetBrand.objects.create(name='停用品牌', code='OLD-BRAND', is_active=False)

        result = QueryService().handle_asset_brand_list({'status': 'active'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'联想'})

    def test_notice_list_only_returns_authored_or_targeted_published_notices(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.department.models import Department
        from apps.system.models import Notice

        User = get_user_model()
        author = User.objects.create_user(username='notice-author')
        recipient = User.objects.create_user(username='notice-recipient')
        other = User.objects.create_user(username='notice-other')
        department = Department.objects.create(name='研发部')

        targeted_notice = Notice.objects.create(
            title='研发部通知',
            content='仅研发部可见',
            is_published=True,
            publish_time=timezone.now(),
            author=author,
        )
        targeted_notice.target_departments.add(department)

        Notice.objects.create(
            title='其他人的草稿',
            content='不可见',
            is_published=False,
            author=other,
        )

        own_draft = Notice.objects.create(
            title='我自己的草稿',
            content='自己可见',
            is_published=False,
            author=recipient,
        )

        recipient.did = department.id
        result = QueryService().handle_notice_list({}, recipient)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(result['total'], 2)
        self.assertEqual(titles, {'研发部通知', '我自己的草稿'})
        self.assertIn(own_draft.title, titles)

    def test_schedule_list_only_returns_own_schedules(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.oa.models import Schedule

        User = get_user_model()
        recipient = User.objects.create_user(username='schedule-recipient')
        other = User.objects.create_user(username='schedule-other')

        Schedule.objects.create(
            title='我的日程',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            labor_time=1,
            admin_id=recipient.id,
            did=1,
            labor_type=1,
            delete_time=0,
            create_time=1,
            update_time=1,
        )
        Schedule.objects.create(
            title='别人的日程',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=2),
            labor_time=2,
            admin_id=other.id,
            did=2,
            labor_type=2,
            delete_time=0,
            create_time=1,
            update_time=1,
        )

        result = QueryService().handle_schedule_list({}, recipient)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(titles, {'我的日程'})

    def test_message_list_unread_scope_only_returns_unread_messages(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.message.models import Message, MessageUserRelation

        User = get_user_model()
        recipient = User.objects.create_user(username='message-recipient')
        sender = User.objects.create_user(username='message-sender')

        unread = Message.objects.create(title='未读消息', content='x', user=recipient, sender=sender, is_active=True)
        read = Message.objects.create(title='已读消息', content='x', user=recipient, sender=sender, is_active=True)
        MessageUserRelation.objects.create(message=unread, user=recipient, is_read=False)
        MessageUserRelation.objects.create(message=read, user=recipient, is_read=True)

        result = QueryService().handle_message_list({'status': 'unread'}, recipient)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'未读消息'})

    def test_meeting_list_today_scope_only_returns_today_meetings(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.oa.models import MeetingRecord

        User = get_user_model()
        host = User.objects.create_user(username='meeting-host')
        now = timezone.now()

        MeetingRecord.objects.create(
            title='今天会议',
            host=host,
            meeting_date=now,
            meeting_end_time=now + timedelta(hours=1),
        )
        tomorrow = now + timedelta(days=1)
        MeetingRecord.objects.create(
            title='明天会议',
            host=host,
            meeting_date=tomorrow,
            meeting_end_time=tomorrow + timedelta(hours=1),
        )

        result = QueryService().handle_meeting_list({'time_range': 'today'}, host)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'今天会议'})


class AIQueryServiceApprovalAndFinanceScopeTests(TestCase):
    def test_ai_model_config_list_active_scope_only_returns_active(self):
        from django.contrib.auth import get_user_model
        from apps.ai.models import AIModelConfig
        from apps.ai.services.query_service import QueryService

        User = get_user_model()
        user = User.objects.create_user(username='ai-model-query-user')

        AIModelConfig.objects.create(name='可用模型', api_base='https://example.com/v1', api_key='sk-a', is_active=True)
        AIModelConfig.objects.create(name='停用模型', api_base='https://example.com/v1', api_key='sk-b', is_active=False)

        result = QueryService().handle_ai_model_config_list({'is_active': True}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'可用模型'})

    def test_ai_knowledge_base_count_status_scope_only_counts_published(self):
        from django.contrib.auth import get_user_model
        from apps.ai.models import AIKnowledgeBase
        from apps.ai.services.query_service import QueryService

        User = get_user_model()
        user = User.objects.create_user(username='ai-kb-query-user')

        AIKnowledgeBase.objects.create(name='已发布库', status='published', creator=user)
        AIKnowledgeBase.objects.create(name='草稿库', status='draft', creator=user)

        result = QueryService().handle_ai_knowledge_base_count({'status': 'published'}, user)

        self.assertEqual(result['value'], 1)

    def test_ai_task_list_status_scope_only_returns_failed(self):
        from django.contrib.auth import get_user_model
        from apps.ai.models import AITask
        from apps.ai.services.query_service import QueryService

        User = get_user_model()
        user = User.objects.create_user(username='ai-task-query-user')

        AITask.objects.create(user=user, task_type='document_summary', task_params={}, status='failed')
        AITask.objects.create(user=user, task_type='document_summary', task_params={}, status='completed')

        result = QueryService().handle_ai_task_list({'status': 'failed'}, user)
        statuses = {item['status'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(statuses, {'failed'})

    def test_ai_workflow_list_status_scope_only_returns_published(self):
        from django.contrib.auth import get_user_model
        from apps.ai.models import AIWorkflow
        from apps.ai.services.query_service import QueryService

        User = get_user_model()
        user = User.objects.create_user(username='ai-workflow-query-user')

        AIWorkflow.objects.create(name='已发布流程', status='published', owner=user)
        AIWorkflow.objects.create(name='草稿流程', status='draft', owner=user)

        result = QueryService().handle_ai_workflow_list({'status': 'published'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'已发布流程'})

    def test_ai_model_config_result_format_includes_primary_model(self):
        from apps.ai.services.query_service import QueryService

        result = {
            'type': 'list',
            'data_type': 'ai_model_config',
            'total': 1,
            'items': [{
                'id': 1,
                'name': '默认模型',
                'provider': 'openai',
                'primary_model': 'gpt-4o-mini',
                'is_active': True,
            }],
        }

        message = QueryService().format_result(result)

        self.assertIn('默认模型', message)
        self.assertIn('gpt-4o-mini', message)

    def test_supply_chain_forecast_list_status_scope_only_returns_reviewing(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.supply_chain.models import DemandForecastPlan

        User = get_user_model()
        user = User.objects.create_user(username='supply-forecast-user')

        DemandForecastPlan.objects.create(
            name='评审中预测',
            code='FC-REVIEW',
            period_start=date.today(),
            period_end=date.today() + timedelta(days=30),
            status='reviewing',
        )
        DemandForecastPlan.objects.create(
            name='已通过预测',
            code='FC-APPROVED',
            period_start=date.today(),
            period_end=date.today() + timedelta(days=30),
            status='approved',
        )

        result = QueryService().handle_supply_chain_forecast_list({'status': 'reviewing'}, user)
        codes = {item['code'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(codes, {'FC-REVIEW'})

    def test_supply_chain_outsource_count_status_scope_only_counts_shortage(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.supply_chain.models import OutsourceIssueOrder

        User = get_user_model()
        user = User.objects.create_user(username='supply-outsource-user')

        OutsourceIssueOrder.objects.create(code='OS-SHORT', quantity=Decimal('10'), status='shortage')
        OutsourceIssueOrder.objects.create(code='OS-READY', quantity=Decimal('8'), status='ready')

        result = QueryService().handle_supply_chain_outsource_count({'status': 'shortage'}, user)

        self.assertEqual(result['value'], 1)

    def test_supply_chain_pr_review_list_abnormal_scope_only_returns_abnormal(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.supply_chain.models import PRReviewTask

        User = get_user_model()
        user = User.objects.create_user(username='supply-pr-user')

        PRReviewTask.objects.create(code='PR-ABN', title='异常PR', is_abnormal=True, status='manual_review')
        PRReviewTask.objects.create(code='PR-NORMAL', title='正常PR', is_abnormal=False, status='done')

        result = QueryService().handle_supply_chain_pr_review_list({'is_abnormal': True}, user)
        codes = {item['code'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(codes, {'PR-ABN'})

    def test_supply_chain_price_review_list_status_scope_only_returns_exception(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.supply_chain.models import PriceReviewOrder

        User = get_user_model()
        user = User.objects.create_user(username='supply-price-user')

        PriceReviewOrder.objects.create(code='PRC-EX', quoted_price=Decimal('12.5'), status='exception')
        PriceReviewOrder.objects.create(code='PRC-OK', quoted_price=Decimal('11.0'), status='approved')

        result = QueryService().handle_supply_chain_price_review_list({'status': 'exception'}, user)
        codes = {item['code'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(codes, {'PRC-EX'})

    def test_supply_chain_sample_count_status_scope_only_counts_pickup_pending(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.supply_chain.models import SampleRequest

        User = get_user_model()
        user = User.objects.create_user(username='supply-sample-user')

        SampleRequest.objects.create(
            code='SMP-PICK',
            material_name='测试物料A',
            required_date=date.today() + timedelta(days=7),
            quantity=Decimal('2'),
            status='pickup_pending',
        )
        SampleRequest.objects.create(
            code='SMP-CLOSE',
            material_name='测试物料B',
            required_date=date.today() + timedelta(days=7),
            quantity=Decimal('3'),
            status='closed',
        )

        result = QueryService().handle_supply_chain_sample_count({'status': 'pickup_pending'}, user)

        self.assertEqual(result['value'], 1)

    def test_supply_chain_sample_result_format_includes_material_and_quantity(self):
        from apps.ai.services.query_service import QueryService

        result = {
            'type': 'list',
            'data_type': 'supply_chain_sample',
            'total': 1,
            'items': [{
                'id': 1,
                'code': 'SMP-001',
                'material_name': '测试物料',
                'quantity': Decimal('2'),
                'status': 'pickup_pending',
            }],
        }

        message = QueryService().format_result(result)

        self.assertIn('测试物料', message)
        self.assertIn('数量2', message)

    def _build_production_task(self, suffix: str):
        from apps.production.models import Equipment, ProductionPlan, ProductionProcedure, ProductionTask

        procedure = ProductionProcedure.objects.create(name=f'装配工序{suffix}', code=f'PROC-{suffix}')
        plan = ProductionPlan.objects.create(
            name=f'生产计划{suffix}',
            code=f'PLAN-{suffix}',
            quantity=Decimal('10'),
            unit='件',
            plan_start_date=date.today(),
            plan_end_date=date.today() + timedelta(days=1),
        )
        equipment = Equipment.objects.create(name=f'设备{suffix}', code=f'EQ-{suffix}')
        task = ProductionTask.objects.create(
            plan=plan,
            name=f'生产任务{suffix}',
            code=f'TASK-{suffix}',
            procedure=procedure,
            equipment=equipment,
            quantity=Decimal('10'),
            plan_start_time=timezone.now(),
            plan_end_time=timezone.now() + timedelta(hours=8),
        )
        return task, equipment

    def test_reward_punishment_list_type_scope_only_returns_reward(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.user.models.employee import RewardPunishment

        User = get_user_model()
        employee = User.objects.create_user(username='reward-employee')
        executor = User.objects.create_user(username='reward-executor')

        RewardPunishment.objects.create(
            employee=employee,
            executor=executor,
            type='reward',
            level='company',
            title='季度奖励',
            reason='业绩突出',
            effective_date=date.today(),
        )
        RewardPunishment.objects.create(
            employee=employee,
            executor=executor,
            type='punishment',
            level='department',
            title='考勤处罚',
            reason='迟到',
            effective_date=date.today(),
        )

        result = QueryService().handle_reward_punishment_list({'type': 'reward'}, employee)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(titles, {'季度奖励'})

    def test_employee_care_count_care_type_scope_only_counts_birthday(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.user.models.employee import EmployeeCare

        User = get_user_model()
        employee = User.objects.create_user(username='care-employee')
        executor = User.objects.create_user(username='care-executor')

        EmployeeCare.objects.create(
            employee=employee,
            executor=executor,
            care_type='birthday',
            title='生日礼券',
            content='生日快乐',
            care_date=date.today(),
        )
        EmployeeCare.objects.create(
            employee=employee,
            executor=executor,
            care_type='holiday',
            title='节日礼包',
            content='节日问候',
            care_date=date.today(),
        )

        result = QueryService().handle_employee_care_count({'care_type': 'birthday'}, employee)

        self.assertEqual(result['value'], 1)

    def test_bom_list_status_scope_only_returns_active(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.production.models import BOM

        User = get_user_model()
        user = User.objects.create_user(username='bom-query-user')

        BOM.objects.create(name='启用BOM', code='BOM-ACTIVE', status=True, creator=user)
        BOM.objects.create(name='停用BOM', code='BOM-INACTIVE', status=False, creator=user)

        result = QueryService().handle_bom_list({'status': 'active'}, user)
        codes = {item['code'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(codes, {'BOM-ACTIVE'})

    def test_quality_check_list_result_scope_only_returns_unqualified(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.production.models import QualityCheck

        User = get_user_model()
        inspector = User.objects.create_user(username='quality-inspector')
        task, _ = self._build_production_task('QC')

        QualityCheck.objects.create(
            task=task,
            created_by=inspector,
            check_quantity=Decimal('10'),
            qualified_quantity=Decimal('10'),
            defective_quantity=Decimal('0'),
            result=1,
        )
        QualityCheck.objects.create(
            task=task,
            created_by=inspector,
            check_quantity=Decimal('10'),
            qualified_quantity=Decimal('8'),
            defective_quantity=Decimal('2'),
            result=2,
        )

        result = QueryService().handle_quality_check_list({'status': 'unqualified'}, inspector)
        statuses = {item['result'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(statuses, {'不合格'})

    def test_datacollection_count_status_scope_only_counts_abnormal(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.production.models import DataCollection

        User = get_user_model()
        operator = User.objects.create_user(username='data-collector')
        task, equipment = self._build_production_task('DC')

        DataCollection.objects.create(
            task=task,
            equipment=equipment,
            parameter_name='温度',
            parameter_value=Decimal('32.5000'),
            unit='℃',
            is_normal=True,
            created_by=operator,
        )
        DataCollection.objects.create(
            task=task,
            equipment=equipment,
            parameter_name='温度',
            parameter_value=Decimal('85.0000'),
            unit='℃',
            is_normal=False,
            created_by=operator,
        )

        result = QueryService().handle_datacollection_count({'status': 'abnormal'}, operator)

        self.assertEqual(result['value'], 1)

    def test_approval_list_created_by_me_scope_only_returns_my_approvals(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.approval.models import Approval

        User = get_user_model()
        applicant = User.objects.create_user(username='approval-applicant')
        other = User.objects.create_user(username='approval-other')

        Approval.objects.create(title='我发起的审批', applicant_id=applicant.id)
        Approval.objects.create(title='别人的审批', applicant_id=other.id)

        result = QueryService().handle_approval_list({'scope': 'created_by_me'}, applicant)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'我发起的审批'})

    def test_approval_type_list_status_scope_only_returns_active(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.approval.models import ApprovalType

        User = get_user_model()
        user = User.objects.create_user(username='approval-type-user')

        ApprovalType.objects.create(name='启用类型', code='TYPE-ACTIVE', is_active=True)
        ApprovalType.objects.create(name='停用类型', code='TYPE-INACTIVE', is_active=False)

        result = QueryService().handle_approval_type_list({'status': 'active'}, user)
        codes = {item['code'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(codes, {'TYPE-ACTIVE'})

    def test_meeting_minutes_list_scope_only_returns_owned_minutes(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.personal.models import MeetingMinutes

        User = get_user_model()
        user = User.objects.create_user(username='minutes-owner')
        other = User.objects.create_user(username='minutes-other')

        MeetingMinutes.objects.create(
            title='我的纪要',
            meeting_date=timezone.now(),
            recorder=user,
            user=user,
            is_public=False,
        )
        MeetingMinutes.objects.create(
            title='公开纪要',
            meeting_date=timezone.now(),
            recorder=other,
            user=other,
            is_public=True,
        )

        result = QueryService().handle_meeting_minutes_list({'scope': 'owned_by_me'}, user)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(titles, {'我的纪要'})

    def test_approval_step_list_flow_scope_only_returns_target_flow(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.approval.models import ApprovalFlow, ApprovalStep, ApprovalType

        User = get_user_model()
        user = User.objects.create_user(username='approval-step-user')
        approval_type = ApprovalType.objects.create(name='流程类型', code='FLOW-TYPE')
        purchase_flow = ApprovalFlow.objects.create(name='采购审批流程', code='FLOW-PURCHASE', approval_type=approval_type)
        leave_flow = ApprovalFlow.objects.create(name='请假审批流程', code='FLOW-LEAVE', approval_type=approval_type)

        ApprovalStep.objects.create(flow=purchase_flow, step_name='采购经理审批', step_order=1, step_type='specific_user')
        ApprovalStep.objects.create(flow=leave_flow, step_name='人事审批', step_order=1, step_type='specific_user')

        result = QueryService().handle_approval_step_list({'flow_name': '采购'}, user)
        step_names = {item['step_name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(step_names, {'采购经理审批'})

    def test_approval_record_count_action_scope_only_counts_visible_approve_records(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.approval.models import Approval, ApprovalRecord

        User = get_user_model()
        applicant = User.objects.create_user(username='approval-record-applicant')
        other = User.objects.create_user(username='approval-record-other')

        my_approval = Approval.objects.create(title='我的审批', applicant_id=applicant.id)
        other_approval = Approval.objects.create(title='别人的审批', applicant_id=other.id)

        ApprovalRecord.objects.create(approval=my_approval, step_order=1, step_name='经理审批', action='approve', handler=applicant)
        ApprovalRecord.objects.create(approval=my_approval, step_order=2, step_name='财务审批', action='return', handler=applicant)
        ApprovalRecord.objects.create(approval=other_approval, step_order=1, step_name='经理审批', action='approve', handler=other)

        result = QueryService().handle_approval_record_count({'action': 'approve'}, applicant)

        self.assertEqual(result['value'], 1)

    def test_approval_flow_edge_count_edge_type_scope_only_counts_condition(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.approval.models import ApprovalFlow, ApprovalFlowEdge, ApprovalType

        User = get_user_model()
        user = User.objects.create_user(username='approval-edge-user', is_superuser=True)
        approval_type = ApprovalType.objects.create(name='连线类型', code='EDGE-TYPE')
        flow = ApprovalFlow.objects.create(name='采购审批流', code='EDGE-FLOW', approval_type=approval_type)

        ApprovalFlowEdge.objects.create(flow=flow, from_node='start', to_node='step_1', edge_type='success')
        ApprovalFlowEdge.objects.create(
            flow=flow,
            from_node='step_1',
            to_node='step_2',
            edge_type='condition',
            condition_field='amount',
            condition_operator='>',
            condition_value='1000',
        )

        result = QueryService().handle_approval_flow_edge_count({'edge_type': 'condition'}, user)

        self.assertEqual(result['value'], 1)

    def test_finance_expense_list_pending_payment_scope_only_returns_pending(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import Expense

        User = get_user_model()
        user = User.objects.create_user(username='expense-user')

        Expense.objects.create(code='BX-001', cost=100, pay_status=0, check_status=0)
        Expense.objects.create(code='BX-002', cost=120, pay_status=1, check_status=0)

        result = QueryService().handle_finance_expense_list({'status': 'pending_payment'}, user)
        codes = {item['code'] for item in result['items']}

        self.assertEqual(codes, {'BX-001'})

    def test_finance_account_list_status_scope_only_returns_active_accounts(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import FinanceAccount

        User = get_user_model()
        user = User.objects.create_user(username='finance-account-user')

        FinanceAccount.objects.create(name='基本户', current_balance=Decimal('1000'), status='active')
        FinanceAccount.objects.create(name='停用户', current_balance=Decimal('500'), status='disabled')

        result = QueryService().handle_finance_account_list({'status': 'active'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'基本户'})

    def test_finance_budget_count_status_scope_only_counts_active_budgets(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import FinanceBudget

        User = get_user_model()
        user = User.objects.create_user(username='finance-budget-user')

        FinanceBudget.objects.create(
            name='执行预算',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            budget_amount=Decimal('10000'),
            status='active',
        )
        FinanceBudget.objects.create(
            name='草稿预算',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            budget_amount=Decimal('8000'),
            status='draft',
        )

        result = QueryService().handle_finance_budget_count({'status': 'active'}, user)

        self.assertEqual(result['value'], 1)

    def test_finance_receivable_list_status_scope_only_returns_overdue(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import AccountsReceivable

        User = get_user_model()
        user = User.objects.create_user(username='finance-receivable-user')

        AccountsReceivable.objects.create(code='AR-001', amount=Decimal('1000'), status='overdue')
        AccountsReceivable.objects.create(code='AR-002', amount=Decimal('800'), status='pending')

        result = QueryService().handle_finance_receivable_list({'status': 'overdue'}, user)
        codes = {item['code'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(codes, {'AR-001'})

    def test_finance_payable_count_status_scope_only_counts_pending(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import AccountsPayable

        User = get_user_model()
        user = User.objects.create_user(username='finance-payable-user')

        AccountsPayable.objects.create(code='AP-001', amount=Decimal('1000'), status='pending')
        AccountsPayable.objects.create(code='AP-002', amount=Decimal('800'), status='settled')

        result = QueryService().handle_finance_payable_count({'status': 'pending'}, user)

        self.assertEqual(result['value'], 1)

    def test_finance_bank_transaction_list_match_scope_only_returns_unmatched(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import BankTransaction, FinanceAccount

        User = get_user_model()
        user = User.objects.create_user(username='finance-bank-user')
        account = FinanceAccount.objects.create(name='银行户', status='active')

        BankTransaction.objects.create(
            account=account,
            transaction_date=timezone.now(),
            direction='in',
            amount=Decimal('1000'),
            transaction_no='TXN-001',
            match_status='unmatched',
        )
        BankTransaction.objects.create(
            account=account,
            transaction_date=timezone.now(),
            direction='out',
            amount=Decimal('500'),
            transaction_no='TXN-002',
            match_status='matched',
        )

        result = QueryService().handle_finance_bank_transaction_list({'match_status': 'unmatched'}, user)
        transaction_nos = {item['transaction_no'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(transaction_nos, {'TXN-001'})

    def test_finance_account_result_format_includes_balance(self):
        from apps.ai.services.query_service import QueryService

        result = {
            'type': 'list',
            'data_type': 'finance_account',
            'total': 1,
            'items': [{
                'id': 1,
                'name': '基本户',
                'current_balance': Decimal('1000.00'),
                'status': 'active',
            }],
        }

        message = QueryService().format_result(result)

        self.assertIn('基本户', message)
        self.assertIn('余额¥1,000.00', message)

    def test_finance_expense_list_approved_scope_only_returns_approved(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import Expense

        User = get_user_model()
        user = User.objects.create_user(username='expense-approved-user')

        Expense.objects.create(code='BX-APPROVED', cost=100, pay_status=0, check_status=2)
        Expense.objects.create(code='BX-PENDING', cost=120, pay_status=0, check_status=0)

        result = QueryService().handle_finance_expense_list({'check_status': 'approved'}, user)
        codes = {item['code'] for item in result['items']}

        self.assertEqual(codes, {'BX-APPROVED'})

    def test_finance_invoice_list_unissued_scope_only_returns_unissued(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import Invoice

        User = get_user_model()
        user = User.objects.create_user(username='invoice-user')

        Invoice.objects.create(code='FP-001', amount=100, open_status=0)
        Invoice.objects.create(code='FP-002', amount=120, open_status=1)

        result = QueryService().handle_finance_invoice_list({'status': 'unissued'}, user)
        codes = {item['code'] for item in result['items']}

        self.assertEqual(codes, {'FP-001'})

    def test_finance_invoice_list_partial_enter_scope_only_returns_partial(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import Invoice

        User = get_user_model()
        user = User.objects.create_user(username='invoice-partial-user')

        Invoice.objects.create(code='FP-PARTIAL', amount=100, open_status=1, enter_status=1)
        Invoice.objects.create(code='FP-FULL', amount=120, open_status=1, enter_status=2)

        result = QueryService().handle_finance_invoice_list({'enter_status': 'partial'}, user)
        codes = {item['code'] for item in result['items']}

        self.assertEqual(codes, {'FP-PARTIAL'})

    def test_employee_list_inactive_scope_only_returns_dimission(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService

        User = get_user_model()
        User.objects.create_user(username='employee-active', name='在职员工', status=1)
        User.objects.create_user(username='employee-inactive', name='离职员工', status=2)

        result = QueryService().handle_employee_list({'status': 'inactive'}, User.objects.create_user(username='employee-query-user'))
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'离职员工'})

    def test_department_list_inactive_scope_only_returns_disabled(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.department.models import Department

        User = get_user_model()
        user = User.objects.create_user(username='department-query-user')

        Department.objects.create(name='启用部门', code='DEP-ACTIVE', status=1)
        Department.objects.create(name='禁用部门', code='DEP-INACTIVE', status=0)

        result = QueryService().handle_department_list({'status': 'inactive'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'禁用部门'})

    def test_approval_list_created_by_me_ongoing_scope_only_returns_unfinished(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.approval.models import Approval

        User = get_user_model()
        applicant = User.objects.create_user(username='approval-ongoing-applicant')

        Approval.objects.create(title='我发起待审批', applicant_id=applicant.id, status=0)
        Approval.objects.create(title='我发起已通过', applicant_id=applicant.id, status=2)

        result = QueryService().handle_approval_list({'scope': 'created_by_me', 'status': 'ongoing'}, applicant)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'我发起待审批'})

    def test_approval_task_list_completed_scope_only_returns_completed(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.approval.models import Approval, ApprovalFlow, ApprovalStep, ApprovalTask

        User = get_user_model()
        handler = User.objects.create_user(username='approval-task-handler')

        flow = ApprovalFlow.objects.create(name='测试流程', code='FLOW-COMPLETE')
        step = ApprovalStep.objects.create(flow=flow, step_name='审核', step_order=1)
        approval = Approval.objects.create(title='测试审批', applicant_id=handler.id)

        ApprovalTask.objects.create(approval=approval, step=step, handler=handler, status='completed')
        ApprovalTask.objects.create(approval=approval, step=step, handler=handler, status='pending')

        result = QueryService().handle_approval_task_list({'status': 'completed'}, handler)
        statuses = {item['status'] for item in result['items']}

        self.assertEqual(statuses, {'已完成'})


class AIQueryServiceCustomerOrderTaskScopeTests(TestCase):
    def test_customer_deal_this_month_applies_visibility_time_and_soft_delete(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.customer.models import Customer, CustomerOrder

        User = get_user_model()
        owner = User.objects.create_user(username='deal-scope-owner')
        other = User.objects.create_user(username='deal-scope-other')
        owned_customer = Customer.objects.create(name='本月自有成交客户', belong_uid=owner.id, delete_time=0)
        shared_customer = Customer.objects.create(name='本月共享成交客户', belong_uid=other.id, share_ids=str(owner.id), delete_time=0)
        hidden_customer = Customer.objects.create(name='本月无权成交客户', belong_uid=other.id, delete_time=0)
        old_customer = Customer.objects.create(name='上月成交客户', belong_uid=owner.id, delete_time=0)
        deleted_order_customer = Customer.objects.create(name='已删订单客户', belong_uid=owner.id, delete_time=0)

        today = date.today()
        previous_month_date = today.replace(day=1) - timedelta(days=1)
        for customer, number, order_date, delete_time in [
            (owned_customer, 'DEAL-OWNED', today, 0),
            (shared_customer, 'DEAL-SHARED', today, 0),
            (hidden_customer, 'DEAL-HIDDEN', today, 0),
            (old_customer, 'DEAL-OLD', previous_month_date, 0),
            (deleted_order_customer, 'DEAL-DELETED', today, 1),
        ]:
            CustomerOrder.objects.create(
                customer=customer,
                order_number=number,
                product_name='测试产品',
                amount=100,
                order_date=order_date,
                create_user=owner,
                delete_time=delete_time,
            )

        result = QueryService().handle_customer_deal_this_month(
            {'status': 'deal', 'time_range': 'this_month'},
            owner,
        )

        self.assertEqual(
            {item['name'] for item in result['items']},
            {'本月自有成交客户', '本月共享成交客户'},
        )
        self.assertEqual(result['total'], 2)

    def test_core_customer_business_counts_apply_status_and_visibility(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.customer.models import Customer, CustomerInvoice, CustomerOrder

        User = get_user_model()
        owner = User.objects.create_user(username='core-query-owner')
        other = User.objects.create_user(username='core-query-other')
        owned_customer = Customer.objects.create(name='核心自有客户', belong_uid=owner.id, delete_time=0)
        hidden_customer = Customer.objects.create(name='核心无权客户', belong_uid=other.id, delete_time=0)

        CustomerOrder.objects.create(customer=owned_customer, order_number='CORE-PROCESSING', product_name='产品', amount=100, order_date=date.today(), status='processing', create_user=owner, delete_time=0)
        CustomerOrder.objects.create(customer=owned_customer, order_number='CORE-COMPLETED', product_name='产品', amount=100, order_date=date.today(), status='completed', create_user=owner, delete_time=0)
        CustomerOrder.objects.create(customer=hidden_customer, order_number='CORE-HIDDEN', product_name='产品', amount=100, order_date=date.today(), status='processing', create_user=other, delete_time=0)
        CustomerInvoice.objects.create(customer=owned_customer, invoice_number='INV-ISSUED', amount=100, tax_amount=13, invoice_date=date.today(), status='issued', create_user=owner, delete_time=0)
        CustomerInvoice.objects.create(customer=owned_customer, invoice_number='INV-DRAFT', amount=100, tax_amount=13, invoice_date=date.today(), status='draft', create_user=owner, delete_time=0)
        CustomerInvoice.objects.create(customer=hidden_customer, invoice_number='INV-HIDDEN', amount=100, tax_amount=13, invoice_date=date.today(), status='issued', create_user=other, delete_time=0)

        query_service = QueryService()
        order_result = query_service.handle_order_count({'status': 'processing'}, owner)
        invoice_result = query_service.handle_invoice_count({'status': 'issued'}, owner)

        self.assertEqual(order_result['value'], 1)
        self.assertEqual(invoice_result['value'], 1)

    def test_project_count_matches_page_visibility_and_status(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.project.models import Project

        User = get_user_model()
        owner = User.objects.create_user(username='project-query-owner')
        other = User.objects.create_user(username='project-query-other')
        Project.objects.create(name='可见已完成项目', code='AI-PROJECT-VISIBLE', creator=owner, status=3)
        Project.objects.create(name='可见进行中项目', code='AI-PROJECT-PROCESSING', creator=owner, status=2)
        Project.objects.create(name='不可见已完成项目', code='AI-PROJECT-HIDDEN', creator=other, status=3)

        result = QueryService().handle_project_count({'status': 'completed'}, owner)

        self.assertEqual(result['value'], 1)

    def test_contract_count_matches_page_visibility_and_status(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.contract.models import Contract

        User = get_user_model()
        owner = User.objects.create_user(username='contract-query-owner')
        other = User.objects.create_user(username='contract-query-other')
        Contract.objects.create(code='AI-CONTRACT-VISIBLE', name='可见审核中合同', customer='客户A', admin_id=owner.id, check_status=1)
        Contract.objects.create(code='AI-CONTRACT-OTHER-STATUS', name='可见待审核合同', customer='客户B', admin_id=owner.id, check_status=0)
        Contract.objects.create(code='AI-CONTRACT-HIDDEN', name='不可见审核中合同', customer='客户C', admin_id=other.id, check_status=1)

        result = QueryService().handle_contract_count({'status': 'reviewing'}, owner)

        self.assertEqual(result['value'], 1)

    def test_customer_list_does_not_treat_partial_share_id_as_current_user(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.customer.models import Customer

        User = get_user_model()
        owner = User.objects.create_user(username='customer-share-boundary-owner')
        other = User.objects.create_user(username='customer-share-boundary-other')

        Customer.objects.create(
            name='仅共享给相似ID的客户',
            belong_uid=other.id,
            share_ids=f'{owner.id}0',
            delete_time=0,
        )

        result = QueryService().handle_customer_list({}, owner)

        self.assertEqual(result['items'], [])

    def test_customer_adapter_does_not_select_partial_share_id_match(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.module_adapters.customer import CustomerModuleAdapter
        from apps.customer.models import Customer

        User = get_user_model()
        owner = User.objects.create_user(username='customer-adapter-boundary-owner')
        other = User.objects.create_user(username='customer-adapter-boundary-other')
        customer = Customer.objects.create(
            name='不可操作的相似共享ID客户',
            belong_uid=other.id,
            share_ids=f'{owner.id}0',
            delete_time=0,
        )

        with self.assertRaises(Customer.DoesNotExist):
            CustomerModuleAdapter()._get_customer_for_update(customer.id, owner)

    def test_customer_list_owned_by_me_scope_only_returns_owned_customers(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.customer.models import Customer

        User = get_user_model()
        owner = User.objects.create_user(username='customer-owner')
        other = User.objects.create_user(username='customer-other')

        Customer.objects.create(name='我的客户', belong_uid=owner.id, delete_time=0)
        Customer.objects.create(name='别人的客户', belong_uid=other.id, delete_time=0)

        result = QueryService().handle_customer_list({'scope': 'owned_by_me'}, owner)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'我的客户'})

    def test_order_list_customer_name_scope_only_returns_matching_customer_orders(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.customer.models import Customer, CustomerOrder

        User = get_user_model()
        owner = User.objects.create_user(username='order-owner')

        customer_a = Customer.objects.create(name='张三公司', belong_uid=owner.id, delete_time=0)
        customer_b = Customer.objects.create(name='李四公司', belong_uid=owner.id, delete_time=0)
        CustomerOrder.objects.create(customer=customer_a, order_number='A-001', product_name='产品A', amount=100, order_date=date.today(), create_user=owner, delete_time=0)
        CustomerOrder.objects.create(customer=customer_b, order_number='B-001', product_name='产品B', amount=200, order_date=date.today(), create_user=owner, delete_time=0)

        result = QueryService().handle_order_list({'customer_name': '张三公司'}, owner)
        numbers = {item['order_number'] for item in result['items']}

        self.assertEqual(numbers, {'A-001'})


    def test_order_list_pending_scope_only_returns_pending_orders(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.customer.models import Customer, CustomerOrder

        User = get_user_model()
        owner = User.objects.create_user(username='order-status-owner')
        customer = Customer.objects.create(name='订单状态客户', belong_uid=owner.id, delete_time=0)

        CustomerOrder.objects.create(customer=customer, order_number='P-001', product_name='产品P', amount=100, order_date=date.today(), status='pending', create_user=owner, delete_time=0)
        CustomerOrder.objects.create(customer=customer, order_number='C-001', product_name='产品C', amount=200, order_date=date.today(), status='completed', create_user=owner, delete_time=0)

        result = QueryService().handle_order_list({'status': 'pending'}, owner)
        numbers = {item['order_number'] for item in result['items']}

        self.assertEqual(numbers, {'P-001'})

    def test_contract_list_reviewing_scope_only_returns_reviewing_contracts(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.contract.models import Contract

        User = get_user_model()
        user = User.objects.create_user(username='contract-reviewing-user')

        Contract.objects.create(name='审核中合同', code='HT-REVIEW', customer='客户A', admin_id=user.id, check_status=1, delete_time=0)
        Contract.objects.create(name='通过合同', code='HT-PASS', customer='客户B', admin_id=user.id, check_status=2, delete_time=0)

        result = QueryService().handle_contract_list({'status': 'reviewing'}, user)
        codes = {item['contract_no'] for item in result['items']}

        self.assertEqual(codes, {'HT-REVIEW'})

    def test_project_list_owned_by_me_scope_only_returns_managed_projects(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.project.models import Project

        User = get_user_model()
        manager = User.objects.create_user(username='project-manager-owned')
        other = User.objects.create_user(username='project-manager-other')

        Project.objects.create(name='我的项目', code='PRJ-MINE', manager=manager)
        Project.objects.create(name='别人项目', code='PRJ-OTHER', manager=other)

        result = QueryService().handle_project_list({'scope': 'owned_by_me'}, manager)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'我的项目'})

    def test_task_list_owned_by_me_scope_only_returns_assigned_tasks(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.task.models import Task

        User = get_user_model()
        assignee = User.objects.create_user(username='task-assignee')
        other = User.objects.create_user(username='task-other')

        Task.objects.create(title='我的任务', assignee_id=assignee.id)
        Task.objects.create(title='别人的任务', assignee_id=other.id)

        result = QueryService().handle_task_list({'scope': 'owned_by_me'}, assignee)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'我的任务'})


class AIQueryServiceNoticeAndMeetingScopeTests(TestCase):
    def test_notice_list_notice_type_scope_only_returns_matching_type(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Notice

        User = get_user_model()
        author = User.objects.create_user(username='notice-type-author')

        Notice.objects.create(title='公司公告', content='x', author=author, notice_type='company', is_published=True, publish_time=timezone.now())
        Notice.objects.create(title='系统通知', content='x', author=author, notice_type='system', is_published=True, publish_time=timezone.now())

        result = QueryService().handle_notice_list({'notice_type': 'system'}, author)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(titles, {'系统通知'})

    def test_notice_list_top_scope_only_returns_top_notices(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Notice

        User = get_user_model()
        author = User.objects.create_user(username='notice-author-2')

        Notice.objects.create(title='置顶公告', content='x', author=author, is_published=True, is_top=True, publish_time=timezone.now())
        Notice.objects.create(title='普通公告', content='x', author=author, is_published=True, is_top=False, publish_time=timezone.now())

        result = QueryService().handle_notice_list({'status': 'top'}, author)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'置顶公告'})

    def test_meeting_list_last_week_scope_only_returns_last_week_meetings(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.oa.models import MeetingRecord

        User = get_user_model()
        host = User.objects.create_user(username='meeting-host-last-week')
        now = timezone.now()
        this_week = now
        last_week = now - timedelta(days=7)

        MeetingRecord.objects.create(
            title='上周会议',
            host=host,
            meeting_date=last_week,
            meeting_end_time=last_week + timedelta(hours=1),
        )
        MeetingRecord.objects.create(
            title='本周会议',
            host=host,
            meeting_date=this_week,
            meeting_end_time=this_week + timedelta(hours=1),
        )

        result = QueryService().handle_meeting_list({'time_range': 'last_week'}, host)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'上周会议'})


class AIQueryServiceInventoryIntentBridgeTests(TestCase):
    def test_warehouse_list_returns_warehouses(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Warehouse

        Warehouse.objects.create(name='华东仓', code='WH-001')
        Warehouse.objects.create(name='华南仓', code='WH-002')

        result = QueryService().handle_warehouse_list({}, SimpleNamespace(is_superuser=False, id=1))
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'华东仓', '华南仓'})

    def test_warehouse_list_inactive_scope_only_returns_disabled(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Warehouse

        Warehouse.objects.create(name='启用仓', code='WH-ACTIVE', status=1)
        Warehouse.objects.create(name='禁用仓', code='WH-INACTIVE', status=0)

        result = QueryService().handle_warehouse_list({'status': 'inactive'}, SimpleNamespace(is_superuser=False, id=1))
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'禁用仓'})

    def test_warehouse_count_type_scope_only_counts_matching_type(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Warehouse

        Warehouse.objects.create(name='生产仓', code='WH-PROD', warehouse_type='production')
        Warehouse.objects.create(name='质检仓', code='WH-QA', warehouse_type='quality')

        result = QueryService().handle_warehouse_count({'warehouse_type': 'production'}, SimpleNamespace(is_superuser=False, id=1))

        self.assertEqual(result['value'], 1)

    def test_inventory_list_locked_scope_only_returns_locked(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Inventory, InventoryCategory, InventoryItem, Warehouse

        warehouse = Warehouse.objects.create(name='库存仓', code='WH-INV')
        category = InventoryCategory.objects.create(name='原料', code='CAT-INV')
        item = InventoryItem.objects.create(name='铜线', code='ITEM-LOCK', category=category, unit='卷')
        Inventory.objects.create(item=item, warehouse=warehouse, quantity=10, available_quantity=2, status='locked')
        Inventory.objects.create(item=item, warehouse=warehouse, batch_number='B2', quantity=10, available_quantity=10, status='normal')

        result = QueryService().handle_inventory_list({'status': 'locked'}, SimpleNamespace(is_superuser=False, id=1))
        names = {item['item_name'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(names, {'铜线'})

    def test_stockin_list_returns_stockin_orders(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Warehouse, StockIn

        warehouse = Warehouse.objects.create(name='主仓', code='WH-IN-001')
        StockIn.objects.create(code='IN-001', stock_in_type='purchase', warehouse=warehouse)

        result = QueryService().handle_stockin_list({}, SimpleNamespace(is_superuser=False, id=1))
        codes = {item['stock_in_no'] for item in result['items']}

        self.assertEqual(codes, {'IN-001'})

    def test_stockout_list_returns_stockout_orders(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Warehouse, StockOut

        warehouse = Warehouse.objects.create(name='成品仓', code='WH-OUT-001')
        StockOut.objects.create(code='OUT-001', stock_out_type='sale', warehouse=warehouse)

        result = QueryService().handle_stockout_list({}, SimpleNamespace(is_superuser=False, id=1))
        codes = {item['stock_out_no'] for item in result['items']}

        self.assertEqual(codes, {'OUT-001'})

    def test_alert_list_returns_inventory_alerts(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Warehouse, InventoryCategory, InventoryItem, InventoryAlert

        warehouse = Warehouse.objects.create(name='预警仓', code='WH-AL-001')
        category = InventoryCategory.objects.create(name='原料', code='CAT-001')
        item = InventoryItem.objects.create(name='钢材', code='IT-001', category=category, unit='吨')
        InventoryAlert.objects.create(
            item=item,
            warehouse=warehouse,
            alert_type='low_stock',
            current_quantity=1,
            threshold_value=5,
            message='库存过低'
        )

        result = QueryService().handle_alert_list({}, SimpleNamespace(is_superuser=False, id=1))
        names = {item['product_name'] for item in result['items']}

        self.assertEqual(names, {'钢材'})

    def test_alert_list_pending_scope_only_returns_unprocessed(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Warehouse, InventoryCategory, InventoryItem, InventoryAlert

        warehouse = Warehouse.objects.create(name='预警仓2', code='WH-AL-002')
        category = InventoryCategory.objects.create(name='辅料', code='CAT-002')
        item = InventoryItem.objects.create(name='锡膏', code='IT-002', category=category, unit='瓶')
        InventoryAlert.objects.create(
            item=item,
            warehouse=warehouse,
            alert_type='low_stock',
            current_quantity=1,
            threshold_value=5,
            message='待处理预警',
            status=1,
        )
        InventoryAlert.objects.create(
            item=item,
            warehouse=warehouse,
            alert_type='over_stock',
            current_quantity=20,
            threshold_value=5,
            message='已处理预警',
            status=2,
        )

        result = QueryService().handle_alert_list({'status': 'pending'}, SimpleNamespace(is_superuser=False, id=1))

        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['status'], '未处理')

    def test_stockin_list_approved_scope_only_returns_checked(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Warehouse, StockIn

        warehouse = Warehouse.objects.create(name='待入库仓', code='WH-IN-APP')
        StockIn.objects.create(code='IN-APP-1', stock_in_type='purchase', warehouse=warehouse, status=2)
        StockIn.objects.create(code='IN-APP-2', stock_in_type='purchase', warehouse=warehouse, status=3)

        result = QueryService().handle_stockin_list({'status': 'approved'}, SimpleNamespace(is_superuser=False, id=1))
        codes = {item['stock_in_no'] for item in result['items']}

        self.assertEqual(codes, {'IN-APP-1'})

    def test_stockin_list_type_scope_only_returns_matching_type(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Warehouse, StockIn

        warehouse = Warehouse.objects.create(name='采购仓', code='WH-IN-TYPE')
        StockIn.objects.create(code='IN-PURCHASE', stock_in_type='purchase', warehouse=warehouse)
        StockIn.objects.create(code='IN-PRODUCTION', stock_in_type='production', warehouse=warehouse)

        result = QueryService().handle_stockin_list({'stock_type': 'purchase'}, SimpleNamespace(is_superuser=False, id=1))
        codes = {item['stock_in_no'] for item in result['items']}

        self.assertEqual(codes, {'IN-PURCHASE'})

    def test_stockout_list_stocked_scope_only_returns_stocked(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Warehouse, StockOut

        warehouse = Warehouse.objects.create(name='已出库仓', code='WH-OUT-STOCKED')
        StockOut.objects.create(code='OUT-ST-1', stock_out_type='sale', warehouse=warehouse, status=3)
        StockOut.objects.create(code='OUT-ST-2', stock_out_type='sale', warehouse=warehouse, status=2)

        result = QueryService().handle_stockout_list({'status': 'stocked'}, SimpleNamespace(is_superuser=False, id=1))
        codes = {item['stock_out_no'] for item in result['items']}

        self.assertEqual(codes, {'OUT-ST-1'})

    def test_stockout_list_type_scope_only_returns_matching_type(self):
        from apps.ai.services.query_service import QueryService
        from apps.inventory.models import Warehouse, StockOut

        warehouse = Warehouse.objects.create(name='销售仓', code='WH-OUT-TYPE')
        StockOut.objects.create(code='OUT-SALE', stock_out_type='sale', warehouse=warehouse)
        StockOut.objects.create(code='OUT-PRODUCTION', stock_out_type='production', warehouse=warehouse)

        result = QueryService().handle_stockout_list({'stock_type': 'sale'}, SimpleNamespace(is_superuser=False, id=1))
        codes = {item['stock_out_no'] for item in result['items']}

        self.assertEqual(codes, {'OUT-SALE'})


class AIQueryServiceContactDocumentPaymentBridgeTests(TestCase):
    def test_contact_list_returns_customer_contacts(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.customer.models import Customer, Contact

        User = get_user_model()
        owner = User.objects.create_user(username='contact-owner')
        customer = Customer.objects.create(name='华星科技', belong_uid=owner.id, delete_time=0)
        Contact.objects.create(customer=customer, contact_person='张三', phone='13800138000', is_primary=True)

        result = QueryService().handle_contact_list({}, owner)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'张三'})

    def test_project_document_list_only_returns_visible_project_documents(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.project.models import Project, ProjectDocument

        User = get_user_model()
        creator = User.objects.create_user(username='project-doc-author')
        recipient = User.objects.create_user(username='project-doc-recipient')
        other = User.objects.create_user(username='project-doc-other')
        project = Project.objects.create(name='A项目', code='P-001', creator=creator, manager=recipient)
        other_project = Project.objects.create(name='B项目', code='P-002', creator=other, manager=other)

        own_doc = ProjectDocument.objects.create(project=project, title='项目方案', content='对内可见', creator=creator, file_path='docs/a.pdf')
        ProjectDocument.objects.create(project=other_project, title='别的项目文档', content='不可见', creator=other, file_path='docs/b.pdf')

        result = QueryService().handle_project_document_list({}, recipient)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(result['total'], 1)
        self.assertEqual(titles, {'项目方案'})
        self.assertIn(own_doc.title, titles)

    def test_payment_list_returns_payment_records(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import Expense, Payment

        User = get_user_model()
        user = User.objects.create_user(username='payment-user')

        expense = Expense.objects.create(code='BX-PAY-001', cost=300, pay_status=1, check_status=2)
        Payment.objects.create(expense_id=expense.id, amount=300, payment_date=timezone.now(), remark='测试付款')

        result = QueryService().handle_payment_list({}, user)
        expense_codes = {item['expense_code'] for item in result['items']}

        self.assertEqual(expense_codes, {'BX-PAY-001'})

    def test_payment_list_this_month_scope_only_returns_current_month(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import Payment

        User = get_user_model()
        user = User.objects.create_user(username='payment-this-month-user')
        now = timezone.now()
        Payment.objects.create(amount=100, payment_date=now, remark='本月付款')
        Payment.objects.create(amount=200, payment_date=now - timedelta(days=40), remark='上期付款')

        result = QueryService().handle_payment_list({'time_range': 'this_month'}, user)
        remarks = {item['remark'] for item in result['items']}

        self.assertEqual(remarks, {'本月付款'})

    def test_finance_income_count_last_month_scope_only_counts_last_month(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import Income

        User = get_user_model()
        user = User.objects.create_user(username='income-last-month-user')
        now = timezone.now()
        last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=15)
        Income.objects.create(amount=100, income_date=last_month, remark='上月回款')
        Income.objects.create(amount=200, income_date=now, remark='本月回款')

        result = QueryService().handle_finance_income_count({'time_range': 'last_month'}, user)

        self.assertEqual(result['value'], 1)

    def test_finance_order_record_list_overdue_scope_only_returns_overdue(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.finance.models import OrderFinanceRecord

        User = get_user_model()
        user = User.objects.create_user(username='finance-order-user')

        OrderFinanceRecord.objects.create(
            order_id=11,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('200.00'),
            payment_status='overdue',
            remark='已逾期',
        )
        OrderFinanceRecord.objects.create(
            order_id=12,
            total_amount=Decimal('2000.00'),
            paid_amount=Decimal('2000.00'),
            payment_status='paid',
            remark='已付款',
        )

        result = QueryService().handle_finance_order_record_list({'status': 'overdue'}, user)
        statuses = {item['payment_status'] for item in result['items']}

        self.assertEqual(statuses, {'overdue'})

    def test_document_list_published_scope_only_returns_published(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Document, DocumentCategory

        User = get_user_model()
        author = User.objects.create_user(username='document-author-published')
        category = DocumentCategory.objects.create(name='通知', code='DOC-PUB')

        Document.objects.create(
            title='已发布公文',
            document_number='DOC-001',
            category=category,
            content='x',
            author=author,
            status='published',
        )
        Document.objects.create(
            title='待发布公文',
            document_number='DOC-002',
            category=category,
            content='x',
            author=author,
            status='approved',
        )

        result = QueryService().handle_document_list({'status': 'published'}, author)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'已发布公文'})

    def test_document_list_pending_publish_scope_only_returns_approved(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.system.models import Document, DocumentCategory

        User = get_user_model()
        author = User.objects.create_user(username='document-author-approved')
        category = DocumentCategory.objects.create(name='制度', code='DOC-APR')

        Document.objects.create(
            title='待发布制度',
            document_number='DOC-101',
            category=category,
            content='x',
            author=author,
            status='approved',
        )
        Document.objects.create(
            title='草稿制度',
            document_number='DOC-102',
            category=category,
            content='x',
            author=author,
            status='draft',
        )

        result = QueryService().handle_document_list({'status': 'approved'}, author)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'待发布制度'})


class AIQueryServiceProductionScopeTests(TestCase):
    def test_production_task_list_today_scope_only_returns_today_tasks(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.production.models import ProductionPlan, ProductionProcedure, ProductionTask

        User = get_user_model()
        user = User.objects.create_user(username='production-user-today')
        procedure = ProductionProcedure.objects.create(name='组装', code='PROC-TODAY')
        plan = ProductionPlan.objects.create(
            name='今日计划',
            code='PLAN-TODAY',
            quantity=10,
            unit='件',
            plan_start_date=date.today(),
            plan_end_date=date.today(),
        )
        today_start = timezone.now()
        tomorrow_start = today_start + timedelta(days=1)

        ProductionTask.objects.create(
            plan=plan,
            name='今日任务',
            code='TASK-TODAY',
            procedure=procedure,
            quantity=10,
            plan_start_time=today_start,
            plan_end_time=today_start + timedelta(hours=2),
            status=2,
        )
        ProductionTask.objects.create(
            plan=plan,
            name='明日任务',
            code='TASK-TOMORROW',
            procedure=procedure,
            quantity=10,
            plan_start_time=tomorrow_start,
            plan_end_time=tomorrow_start + timedelta(hours=2),
            status=2,
        )

        result = QueryService().handle_production_task_list({'time_range': 'today'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'今日任务'})

    def test_production_task_list_paused_scope_only_returns_paused(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.production.models import ProductionPlan, ProductionProcedure, ProductionTask

        User = get_user_model()
        user = User.objects.create_user(username='production-user-paused')
        procedure = ProductionProcedure.objects.create(name='测试工序', code='PROC-PAUSED')
        plan = ProductionPlan.objects.create(
            name='暂停计划',
            code='PLAN-PAUSED',
            quantity=20,
            unit='件',
            plan_start_date=date.today(),
            plan_end_date=date.today(),
        )
        now = timezone.now()

        ProductionTask.objects.create(
            plan=plan,
            name='已暂停任务',
            code='TASK-PAUSED',
            procedure=procedure,
            quantity=10,
            plan_start_time=now,
            plan_end_time=now + timedelta(hours=2),
            status=4,
        )
        ProductionTask.objects.create(
            plan=plan,
            name='已完成任务',
            code='TASK-DONE',
            procedure=procedure,
            quantity=10,
            plan_start_time=now,
            plan_end_time=now + timedelta(hours=2),
            status=3,
        )

        result = QueryService().handle_production_task_list({'status': 'paused'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'已暂停任务'})

    def test_production_plan_list_completed_scope_only_returns_completed(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.production.models import ProductionPlan

        User = get_user_model()
        user = User.objects.create_user(username='production-plan-user')

        ProductionPlan.objects.create(
            name='已完成计划',
            code='PLAN-DONE',
            quantity=10,
            unit='件',
            plan_start_date=date.today(),
            plan_end_date=date.today(),
            status=4,
        )
        ProductionPlan.objects.create(
            name='执行中计划',
            code='PLAN-RUN',
            quantity=10,
            unit='件',
            plan_start_date=date.today(),
            plan_end_date=date.today(),
            status=3,
        )

        result = QueryService().handle_production_plan_list({'status': 'completed'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'已完成计划'})

    def test_production_equipment_list_maintenance_scope_only_returns_maintenance(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.production.models import Equipment

        User = get_user_model()
        user = User.objects.create_user(username='production-equipment-user')

        Equipment.objects.create(name='维修机台', code='EQ-MAINT', status=2)
        Equipment.objects.create(name='正常机台', code='EQ-NORMAL', status=1)

        result = QueryService().handle_production_equipment_list({'status': 'maintenance'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'维修机台'})



class AIQueryServiceMessagingAndWorkspaceFiltersTests(TestCase):
    def test_message_list_starred_scope_only_returns_starred(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.message.models import Message, MessageUserRelation

        User = get_user_model()
        user = User.objects.create_user(username='message-star-user')
        sender = User.objects.create_user(username='message-star-sender')

        starred = Message.objects.create(title='标星消息', content='a', sender=sender, is_active=True)
        normal = Message.objects.create(title='普通消息', content='b', sender=sender, is_active=True)
        MessageUserRelation.objects.create(message=starred, user=user, is_starred=True, is_read=False)
        MessageUserRelation.objects.create(message=normal, user=user, is_starred=False, is_read=True)

        result = QueryService().handle_message_list({'status': 'starred'}, user)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'标星消息'})

    def test_work_record_list_project_scope_only_returns_project_records(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.personal.models import WorkRecord
        from datetime import time

        User = get_user_model()
        user = User.objects.create_user(username='work-record-project-user')

        WorkRecord.objects.create(title='项目联调', content='a', work_type='project', work_date=date.today(), start_time=time(9, 0), end_time=time(10, 0), duration=1, user=user)
        WorkRecord.objects.create(title='会议纪要', content='b', work_type='meeting', work_date=date.today(), start_time=time(10, 0), end_time=time(11, 0), duration=1, user=user)

        result = QueryService().handle_work_record_list({'work_type': 'project'}, user)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'项目联调'})

    def test_work_record_list_today_scope_only_returns_today_records(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.personal.models import WorkRecord
        from datetime import time, timedelta

        User = get_user_model()
        user = User.objects.create_user(username='work-record-today-user')

        WorkRecord.objects.create(title='今日事项', content='a', work_type='daily', work_date=date.today(), start_time=time(9, 0), end_time=time(10, 0), duration=1, user=user)
        WorkRecord.objects.create(title='昨日事项', content='b', work_type='daily', work_date=date.today() - timedelta(days=1), start_time=time(9, 0), end_time=time(10, 0), duration=1, user=user)

        result = QueryService().handle_work_record_list({'time_range': 'today'}, user)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'今日事项'})

    def test_disk_list_shared_to_me_scope_only_returns_shared_files(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.disk.models import DiskFile

        User = get_user_model()
        user = User.objects.create_user(username='disk-shared-user')
        owner = User.objects.create_user(username='disk-owner-user')

        shared = DiskFile.objects.create(name='共享文件.pdf', owner=owner)
        shared.shared_users.add(user)
        DiskFile.objects.create(name='我的文件.pdf', owner=user)

        result = QueryService().handle_disk_list({'scope': 'shared_to_me'}, user)
        names = {item['name'] for item in result['items']}

        self.assertEqual(names, {'共享文件.pdf'})

class AIQueryServicePersonalWorkspaceScopeTests(TestCase):
    def test_personal_task_list_completed_scope_only_returns_completed(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.personal.models import PersonalTask

        User = get_user_model()
        user = User.objects.create_user(username='personal-task-user')

        PersonalTask.objects.create(title='已完成任务', user=user, status='completed')
        PersonalTask.objects.create(title='待办任务', user=user, status='todo')

        result = QueryService().handle_personal_task_list({'status': 'completed'}, user)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'已完成任务'})

    def test_work_report_list_submitted_scope_only_returns_submitted(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.personal.models import WorkReport

        User = get_user_model()
        user = User.objects.create_user(username='work-report-user')

        WorkReport.objects.create(
            title='已提交周报',
            report_type='weekly',
            report_date=date.today(),
            summary='s',
            completed_work='c',
            next_work='n',
            user=user,
            is_submitted=True,
        )
        WorkReport.objects.create(
            title='草稿周报',
            report_type='weekly',
            report_date=date.today(),
            summary='s',
            completed_work='c',
            next_work='n',
            user=user,
            is_submitted=False,
        )

        result = QueryService().handle_work_report_list({'is_submitted': True}, user)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'已提交周报'})

    def test_work_report_list_daily_scope_only_returns_daily_reports(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.personal.models import WorkReport

        User = get_user_model()
        user = User.objects.create_user(username='work-report-daily-user')

        WorkReport.objects.create(
            title='日报A',
            report_type='daily',
            report_date=date.today(),
            summary='s',
            completed_work='c',
            next_work='n',
            user=user,
        )
        WorkReport.objects.create(
            title='周报B',
            report_type='weekly',
            report_date=date.today(),
            summary='s',
            completed_work='c',
            next_work='n',
            user=user,
        )

        result = QueryService().handle_work_report_list({'report_type': 'daily'}, user)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'日报A'})

    def test_personal_note_list_important_scope_only_returns_important(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.personal.models import PersonalNote

        User = get_user_model()
        user = User.objects.create_user(username='personal-note-user')

        PersonalNote.objects.create(title='重要笔记', content='a', user=user, is_important=True)
        PersonalNote.objects.create(title='普通笔记', content='b', user=user, is_important=False)

        result = QueryService().handle_personal_note_list({'is_important': True}, user)
        titles = {item['title'] for item in result['items']}

        self.assertEqual(titles, {'重要笔记'})

    def test_followup_list_phone_scope_only_returns_phone_records(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.customer.models import Customer, FollowRecord

        User = get_user_model()
        user = User.objects.create_user(username='followup-phone-user')

        phone_customer = Customer.objects.create(name='电话客户', belong_uid=user.id)
        visit_customer = Customer.objects.create(name='拜访客户', belong_uid=user.id)

        FollowRecord.objects.create(customer=phone_customer, follow_type='phone', content='电话沟通', follow_user=user)
        FollowRecord.objects.create(customer=visit_customer, follow_type='visit', content='上门拜访', follow_user=user)

        result = QueryService().handle_followup_list({'follow_type': 'phone'}, user)
        customers = {item['customer'] for item in result['items']}

        self.assertEqual(customers, {'电话客户'})

    def test_followup_list_only_returns_user_visible_records(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.customer.models import Customer, FollowRecord

        User = get_user_model()
        user = User.objects.create_user(username='followup-visible-user')
        other = User.objects.create_user(username='followup-hidden-user')

        visible_customer = Customer.objects.create(name='可见客户', belong_uid=user.id)
        hidden_customer = Customer.objects.create(name='隐藏客户', belong_uid=other.id)

        FollowRecord.objects.create(customer=visible_customer, follow_type='phone', content='我的跟进', follow_user=user)
        FollowRecord.objects.create(customer=hidden_customer, follow_type='phone', content='别人的跟进', follow_user=other)

        result = QueryService().handle_followup_list({}, user)
        customers = {item['customer'] for item in result['items']}

        self.assertEqual(customers, {'可见客户'})


class AIQueryServiceWorkHourAndAliasBridgeTests(TestCase):
    def test_workhour_list_returns_user_visible_workhours(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.query_service import QueryService
        from apps.project.models import Task, WorkHour

        User = get_user_model()
        worker = User.objects.create_user(username='workhour-worker')
        other = User.objects.create_user(username='workhour-other')

        my_task = Task.objects.create(title='我的项目任务', assignee=worker, creator=worker)
        other_task = Task.objects.create(title='别人的项目任务', assignee=other, creator=other)

        WorkHour.objects.create(task=my_task, user=worker, work_date=date.today(), hours=2.5, description='联调')
        WorkHour.objects.create(task=other_task, user=other, work_date=date.today(), hours=1.0, description='无权限')

        result = QueryService().handle_workhour_list({}, worker)
        titles = {item['task_title'] for item in result['items']}

        self.assertEqual(titles, {'我的项目任务'})


class AICustomerAdapterTests(SimpleTestCase):
    def test_customer_adapter_builds_change_set_for_create(self):
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.module_adapters.customer import CustomerModuleAdapter

        adapter = CustomerModuleAdapter()
        action = AIActionRequest(
            resource='customer',
            operation='create',
            object_ids=[],
            changes={'name': '新客户'},
        )

        result = adapter.preview(action, user=SimpleNamespace(id=7))

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['change_type'], 'create')
        self.assertEqual(result['change_set'][0]['after_snapshot']['name'], '新客户')

    def test_customer_adapter_rejects_fields_outside_allowlist(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.customer import CustomerModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing customer adapter dependency: {exc}')

        adapter = CustomerModuleAdapter()
        action = AIActionRequest(
            resource='customer',
            operation='update',
            object_ids=[12],
            changes={'delete_time': 123456},
        )

        result = adapter.validate(action)

        self.assertFalse(result['success'])
        self.assertIn('delete_time', result['message'])

    def test_customer_adapter_builds_change_set_for_name_update(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.customer import CustomerModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing customer adapter dependency: {exc}')

        adapter = CustomerModuleAdapter()
        customer = SimpleNamespace(id=12, name='旧名称', address='旧地址')
        action = AIActionRequest(
            resource='customer',
            operation='update',
            object_ids=[12],
            changes={'name': '新名称'},
        )

        with patch.object(adapter, '_get_customer_for_update', return_value=customer):
            result = adapter.preview(action, user=SimpleNamespace(id=7))

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['before_snapshot']['name'], '旧名称')
        self.assertEqual(result['change_set'][0]['after_snapshot']['name'], '新名称')


class AIActionGatewayCustomerDispatchTests(SimpleTestCase):
    def test_gateway_dispatches_customer_update_to_registered_adapter(self):
        from apps.ai.services.action_gateway import AIActionGateway

        adapter = MagicMock()
        adapter.resource = 'customer'
        adapter.execute.return_value = {'success': True, 'message': 'updated'}
        operation = SimpleNamespace(
            id=20,
            resource_type='customer',
            operation_type='update',
            confirmed_payload={'resource': 'customer', 'operation': 'update', 'object_ids': [12], 'changes': {'name': '新名称'}},
        )
        user = SimpleNamespace(id=7, is_authenticated=True)

        gateway = AIActionGateway()
        gateway.register(adapter)

        result = gateway.execute_confirmed_action(operation, user)

        adapter.execute.assert_called_once()
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'updated')


class AIActionGatewayProjectCoverageTests(SimpleTestCase):
    def test_every_mcp_write_resource_has_an_action_adapter(self):
        from apps.ai.services.action_gateway import AIActionGateway
        from apps.ai.services.project_mcp_service import project_mcp_service

        gateway = AIActionGateway()
        write_resources = sorted({
            capability['resource']
            for capability in project_mcp_service.get_capability_catalog()
            if capability.get('intent_mode') == 'write'
        })
        missing = []
        for resource in write_resources:
            try:
                gateway.get_adapter(resource)
            except KeyError:
                missing.append(resource)

        self.assertEqual(missing, [])

    def test_every_mcp_write_operation_is_supported_by_its_adapter(self):
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.action_gateway import AIActionGateway
        from apps.ai.services.project_mcp_service import project_mcp_service

        gateway = AIActionGateway()
        unsupported = []
        errors = []
        capabilities = [
            item for item in project_mcp_service.get_capability_catalog()
            if item.get('intent_mode') == 'write'
        ]
        for capability in capabilities:
            adapter = gateway.get_adapter(capability['resource'])
            required = getattr(adapter, 'required_create_fields', None) or set()
            if isinstance(required, dict):
                required = required.get(capability['resource']) or set()
            action = AIActionRequest(
                resource=capability['resource'],
                operation=capability['operations'][0],
                object_ids=[1],
                changes={field: '1' for field in required},
            )
            try:
                result = adapter.validate(action)
            except Exception as exc:
                errors.append((capability['id'], type(exc).__name__, str(exc)))
                continue
            if '暂不支持' in str(result.get('message', '')):
                unsupported.append(capability['id'])

        self.assertEqual(errors, [])
        self.assertEqual(unsupported, [])

    def test_mcp_write_capability_exposes_adapter_input_schema(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capability = next(
            item for item in project_mcp_service.get_capability_catalog()
            if item['id'] == 'write.finance_account.create'
        )

        schema = capability['input_schema']
        self.assertEqual(schema['type'], 'object')
        self.assertIn('name', schema['required'])
        self.assertIn('opening_balance', schema['properties'])

    def test_mcp_update_capability_requires_target_object_ids(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capability = next(
            item for item in project_mcp_service.get_capability_catalog()
            if item['id'] == 'write.finance_account.update'
        )

        schema = capability['input_schema']
        self.assertIn('object_ids', schema['properties'])
        self.assertIn('object_ids', schema['required'])
        self.assertEqual(schema['properties']['object_ids']['items']['type'], 'integer')

    def test_mcp_does_not_advertise_unconfigured_supply_chain_delete(self):
        from apps.ai.services.project_mcp_service import project_mcp_service

        capability_ids = {
            item['id'] for item in project_mcp_service.get_capability_catalog()
        }

        self.assertNotIn('write.supply_chain_sample.delete', capability_ids)


class AIConfiguredModelAdapterPermissionTests(SimpleTestCase):
    def test_meeting_minutes_action_payload_constructs_real_model(self):
        from apps.ai.services.confirmation_service import confirmation_service
        from apps.ai.services.module_adapters.configured_model import ConfiguredModelModuleAdapter
        from apps.personal.models import MeetingMinutes

        user = SimpleNamespace(id=9, name='验证用户', username='verify')
        request = confirmation_service.build_action_request({
            'action': 'create',
            'data_type': 'meeting_minutes',
            'entities': {
                'title': 'AI验证纪要',
                'meeting_date': 'today',
            },
        }, user=user)
        normalized = ConfiguredModelModuleAdapter('meeting_minutes')._normalize_payload(
            request.changes,
            user,
            partial=False,
        )

        self.assertTrue(normalized['success'], normalized)
        self.assertNotIn('host_id', normalized['payload'])
        instance = MeetingMinutes(**normalized['payload'])
        self.assertEqual(instance.host, '验证用户')
        self.assertEqual(instance.recorder_id, 9)
        self.assertEqual(instance.user_id, 9)

    def test_configured_adapter_accepts_configured_nonstandard_permission(self):
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.module_adapters.configured_model import ConfiguredModelModuleAdapter

        adapter = ConfiguredModelModuleAdapter('supply_chain_forecast')
        action = AIActionRequest(
            resource='supply_chain_forecast',
            operation='update',
            object_ids=[3],
            changes={'status': 'reviewed'},
        )
        user = SimpleNamespace(
            id=7,
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda permission: permission == 'user.approve_supply_chain_forecast',
        )
        scoped = MagicMock()
        scoped.filter.return_value.exists.return_value = True

        with patch.object(adapter, '_scoped_queryset', return_value=scoped):
            result = adapter._check_permission(action, user)

        self.assertTrue(result['allowed'])

    def test_configured_adapter_rejects_derived_permission_when_exact_permission_is_missing(self):
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.module_adapters.configured_model import ConfiguredModelModuleAdapter

        adapter = ConfiguredModelModuleAdapter('supply_chain_forecast')
        action = AIActionRequest(
            resource='supply_chain_forecast',
            operation='update',
            object_ids=[3],
            changes={'status': 'reviewed'},
        )
        user = SimpleNamespace(
            id=7,
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda permission: permission == 'user.change_supply_chain_forecast',
        )
        scoped = MagicMock()
        scoped.filter.return_value.exists.return_value = True

        with patch.object(adapter, '_scoped_queryset', return_value=scoped):
            result = adapter._check_permission(action, user)

        self.assertFalse(result['allowed'])

    def test_configured_adapter_rejects_user_without_exact_permission(self):
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.module_adapters.configured_model import ConfiguredModelModuleAdapter

        adapter = ConfiguredModelModuleAdapter('approval_type')
        action = AIActionRequest(
            resource='approval_type',
            operation='create',
            changes={'name': '测试类型', 'code': 'TEST'},
        )
        user = SimpleNamespace(
            id=7,
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda _permission: False,
        )

        result = adapter.preview(action, user)

        self.assertFalse(result['success'])
        self.assertIn('没有该操作权限', result['message'])

    def test_configured_adapter_scopes_owned_resources_to_current_user(self):
        from apps.ai.services.module_adapters.configured_model import ConfiguredModelModuleAdapter

        adapter = ConfiguredModelModuleAdapter('ai_knowledge_base')
        queryset = MagicMock()
        model = SimpleNamespace(objects=SimpleNamespace(all=MagicMock(return_value=queryset)))
        user = SimpleNamespace(id=7, is_superuser=False)

        with patch.object(adapter, '_get_model', return_value=model):
            result = adapter._scoped_queryset(user)

        queryset.filter.assert_called_once_with(creator_id=7)
        self.assertEqual(result, queryset.filter.return_value)


class AIApprovalAdapterTests(SimpleTestCase):
    def test_approval_adapter_handles_withdraw_preview(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.approval import ApprovalModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing approval adapter dependency: {exc}')

        adapter = ApprovalModuleAdapter()
        approval = SimpleNamespace(
            id=21,
            status=1,
            current_step_order=3,
            title='测试审批',
            applicant_id=7,
            records=SimpleNamespace(
                filter=lambda **_kwargs: SimpleNamespace(exists=lambda: False),
            ),
        )
        action = AIActionRequest(
            resource='approval',
            operation='withdraw',
            object_ids=[21],
            changes={},
        )

        with patch.object(adapter, '_get_approval_for_action', return_value=approval):
            result = adapter.preview(action, user=SimpleNamespace(id=7))

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['before_snapshot']['status'], 1)
        self.assertEqual(result['change_set'][0]['after_snapshot']['status'], 0)

    def test_approval_adapter_rejects_withdraw_after_next_node_was_processed(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.approval import ApprovalModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing approval adapter dependency: {exc}')

        adapter = ApprovalModuleAdapter()
        approval = SimpleNamespace(
            id=21,
            status=1,
            applicant_id=7,
            records=SimpleNamespace(
                filter=lambda **_kwargs: SimpleNamespace(exists=lambda: True),
            ),
        )

        result = adapter._validate_withdraw(approval, user=SimpleNamespace(id=7))

        self.assertFalse(result['success'])
        self.assertIn('申请人', result['message'])

    def test_approval_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.approval import ApprovalModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing approval adapter dependency: {exc}')

        adapter = ApprovalModuleAdapter()
        action = AIActionRequest(
            resource='approval',
            operation='create',
            changes={
                'title': 'AI发起报销审批',
                'flow_id': 5,
                'type_id': 2,
                'content': '差旅报销审批',
                'reviewer_id': 9,
            },
        )

        flow = SimpleNamespace(
            id=5,
            approval_type_id=2,
            steps=SimpleNamespace(exists=lambda: False),
        )
        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_create_flow', return_value=flow):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['change_type'], 'create')
        self.assertEqual(result['change_set'][0]['after_snapshot']['title'], 'AI发起报销审批')

    def test_approval_adapter_execute_approve_delegates_to_pending_task(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.approval import ApprovalModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing approval adapter dependency: {exc}')

        adapter = ApprovalModuleAdapter()
        approval = SimpleNamespace(
            id=21,
            status=1,
            current_step_order=2,
            title='测试审批',
            reviewer_id=9,
            save=MagicMock(),
        )
        action = AIActionRequest(
            resource='approval',
            operation='approve',
            object_ids=[21],
            changes={'comment': '同意'},
        )
        task_action = AIActionRequest(
            resource='approval_task',
            operation='approve',
            object_ids=[51],
            changes={'comment': '同意'},
        )

        with patch.object(adapter, 'preview', return_value={'success': True, 'change_set': []}), \
                patch.object(adapter, '_get_approval_for_action', return_value=approval), \
                patch.object(adapter, '_build_pending_task_action', return_value=task_action), \
                patch(
                    'apps.ai.services.module_adapters.approval_task.ApprovalTaskModuleAdapter.execute',
                    return_value={'success': True, 'message': 'approve', 'change_set': []},
                ) as execute_task:
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        execute_task.assert_called_once_with(task_action, ANY, operation=None)


class AIApprovalTaskExecutionIntegrationTests(TestCase):
    def test_approval_create_rejects_user_outside_flow_initiator_scope(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.module_adapters.approval import ApprovalModuleAdapter
        from apps.approval.models import ApprovalFlow

        User = get_user_model()
        allowed_user = User.objects.create_user(username='ai-flow-allowed-user')
        blocked_user = User.objects.create_user(username='ai-flow-blocked-user')
        flow = ApprovalFlow.objects.create(
            name='受限发起流程',
            code='AI_RESTRICTED_INITIATOR',
            initiator_users=str(allowed_user.id),
        )
        action = AIActionRequest(
            resource='approval',
            operation='create',
            changes={'title': '越权发起测试', 'flow_id': flow.id},
        )

        result = ApprovalModuleAdapter().preview(action, blocked_user)

        self.assertFalse(result['success'])
        self.assertIn('发起', result['message'])

    def test_approval_task_execution_uses_flow_engine_and_records_action(self):
        from django.contrib.auth import get_user_model
        from apps.ai.models import AIOperation, AIOperationChangeSet
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.module_adapters.approval_task import ApprovalTaskModuleAdapter
        from apps.ai.services.rollback_service import rollback_service
        from apps.approval.models import Approval, ApprovalFlow, ApprovalRecord, ApprovalStep, ApprovalTask

        User = get_user_model()
        applicant = User.objects.create_user(username='ai-approval-applicant')
        handler = User.objects.create_user(username='ai-approval-handler')
        flow = ApprovalFlow.objects.create(name='AI单节点审批', code='AI_SINGLE_STEP')
        step = ApprovalStep.objects.create(
            flow=flow,
            step_name='负责人审批',
            step_order=1,
            step_type='specific_user',
            approver=handler,
        )
        approval = Approval.objects.create(
            title='AI真实审批推进',
            applicant_id=applicant.id,
            flow=flow,
            status=1,
            current_step_order=1,
        )
        task = ApprovalTask.objects.create(
            approval=approval,
            step=step,
            handler=handler,
            status='pending',
        )
        action = AIActionRequest(
            resource='approval_task',
            operation='approve',
            object_ids=[task.id],
            changes={'comment': '同意执行'},
        )
        adapter = ApprovalTaskModuleAdapter()

        with patch.object(
                adapter.permission_guard,
                'check_action_permission',
                return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.execute(action, handler)

        task.refresh_from_db()
        approval.refresh_from_db()
        record = ApprovalRecord.objects.get(approval=approval, handler=handler)

        self.assertTrue(result['success'])
        self.assertEqual(task.status, 'completed')
        self.assertEqual(task.result, 'approve')
        self.assertEqual(approval.status, 2)
        self.assertEqual(approval.current_step_order, 0)
        self.assertEqual(record.action, 'approve')
        self.assertTrue(any(
            item['model_name'] == 'ApprovalRecord' and item['change_type'] == 'create'
            for item in result['change_set']
        ))

        operation = AIOperation.objects.create(
            user=handler,
            operation_type='approve',
            resource_type='approval_task',
            status='executed',
        )
        for sequence, item in enumerate(result['change_set'], start=1):
            AIOperationChangeSet.objects.create(
                operation=operation,
                sequence=sequence,
                app_label=item['app_label'],
                model_name=item['model_name'],
                object_pk=item['object_pk'],
                change_type=item['change_type'],
                before_snapshot=item['before_snapshot'],
                after_snapshot=item['after_snapshot'],
                changed_fields=item['changed_fields'],
            )

        rollback_result = rollback_service.rollback_operation(operation.id, handler)
        task.refresh_from_db()
        approval.refresh_from_db()

        self.assertTrue(rollback_result['success'])
        self.assertEqual(task.status, 'pending')
        self.assertEqual(task.result, '')
        self.assertEqual(approval.status, 1)
        self.assertEqual(approval.current_step_order, 1)
        self.assertFalse(ApprovalRecord.objects.filter(pk=record.pk).exists())

    def test_approval_id_action_resolves_current_users_pending_task(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.module_adapters.approval import ApprovalModuleAdapter
        from apps.ai.services.module_adapters.approval_task import ApprovalTaskModuleAdapter
        from apps.approval.models import Approval, ApprovalFlow, ApprovalRecord, ApprovalStep, ApprovalTask

        User = get_user_model()
        applicant = User.objects.create_user(username='ai-approval-id-applicant')
        handler = User.objects.create_user(username='ai-approval-id-handler')
        flow = ApprovalFlow.objects.create(name='AI审批单ID流程', code='AI_APPROVAL_ID')
        step = ApprovalStep.objects.create(
            flow=flow,
            step_name='审批单ID处理',
            step_order=1,
            step_type='specific_user',
            approver=handler,
        )
        approval = Approval.objects.create(
            title='按审批单ID处理',
            applicant_id=applicant.id,
            flow=flow,
            status=1,
            current_step_order=1,
        )
        task = ApprovalTask.objects.create(
            approval=approval,
            step=step,
            handler=handler,
            status='pending',
        )
        action = AIActionRequest(
            resource='approval',
            operation='approve',
            object_ids=[approval.id],
            changes={'comment': '按审批单通过'},
        )

        with patch.object(
                ApprovalModuleAdapter.permission_guard,
                'check_action_permission',
                return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(
                    ApprovalTaskModuleAdapter.permission_guard,
                    'check_action_permission',
                    return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = ApprovalModuleAdapter().execute(action, handler)

        task.refresh_from_db()
        approval.refresh_from_db()
        self.assertTrue(result['success'])
        self.assertEqual(task.status, 'completed')
        self.assertEqual(approval.status, 2)
        self.assertTrue(ApprovalRecord.objects.filter(
            approval=approval,
            handler=handler,
            action='approve',
        ).exists())

    def test_approval_withdraw_rejects_non_applicant(self):
        from django.contrib.auth import get_user_model
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.module_adapters.approval import ApprovalModuleAdapter
        from apps.approval.models import Approval

        User = get_user_model()
        applicant = User.objects.create_user(username='ai-withdraw-applicant')
        other = User.objects.create_user(username='ai-withdraw-other')
        approval = Approval.objects.create(
            title='不可越权撤回',
            applicant_id=applicant.id,
            status=1,
        )
        action = AIActionRequest(
            resource='approval',
            operation='withdraw',
            object_ids=[approval.id],
            changes={},
        )
        adapter = ApprovalModuleAdapter()

        with patch.object(
                adapter.permission_guard,
                'check_action_permission',
                return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(action, other)

        self.assertFalse(result['success'])
        self.assertIn('申请人', result['message'])


class AIProjectAdapterTests(SimpleTestCase):
    def test_project_adapter_builds_update_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.project import ProjectModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing project adapter dependency: {exc}')

        adapter = ProjectModuleAdapter()
        project = SimpleNamespace(
            id=31,
            name='旧项目',
            status=1,
            progress=20,
            delete_time=None,
        )
        action = AIActionRequest(
            resource='project',
            operation='update',
            object_ids=[31],
            changes={'name': '新项目', 'progress': 45},
        )

        with patch.object(adapter, '_get_project_for_action', return_value=project):
            result = adapter.preview(action, user=SimpleNamespace(id=7))

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['before_snapshot']['name'], '旧项目')
        self.assertEqual(result['change_set'][0]['after_snapshot']['name'], '新项目')
        self.assertEqual(result['change_set'][0]['after_snapshot']['progress'], 45)

    def test_project_adapter_soft_delete_execute_sets_delete_time(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.project import ProjectModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing project adapter dependency: {exc}')

        adapter = ProjectModuleAdapter()
        project = SimpleNamespace(
            id=31,
            name='旧项目',
            status=1,
            progress=20,
            delete_time=None,
            save=MagicMock(),
        )
        action = AIActionRequest(
            resource='project',
            operation='delete',
            object_ids=[31],
            changes={},
        )

        with patch.object(adapter, '_get_project_for_action', return_value=project), \
                patch('apps.ai.services.module_adapters.project.timezone.now', return_value='NOW'):
            result = adapter.execute(action, user=SimpleNamespace(id=7), operation=None)

        self.assertTrue(result['success'])
        self.assertEqual(project.delete_time, 'NOW')
        project.save.assert_called_once()


class AIActionGatewayProjectDispatchTests(SimpleTestCase):
    def test_gateway_dispatches_project_update_to_registered_adapter(self):
        from apps.ai.services.action_gateway import AIActionGateway

        adapter = MagicMock()
        adapter.resource = 'project'
        adapter.execute.return_value = {'success': True, 'message': 'project updated'}
        operation = SimpleNamespace(
            id=22,
            resource_type='project',
            operation_type='update',
            confirmed_payload={'resource': 'project', 'operation': 'update', 'object_ids': [31], 'changes': {'name': '新项目'}},
        )
        user = SimpleNamespace(id=7, is_authenticated=True)

        gateway = AIActionGateway()
        gateway.register(adapter)

        result = gateway.execute_confirmed_action(operation, user)

        adapter.execute.assert_called_once()
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'project updated')


class AIOrderAdapterTests(SimpleTestCase):
    def test_order_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.order import OrderModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing order adapter dependency: {exc}')

        adapter = OrderModuleAdapter()
        action = AIActionRequest(
            resource='order',
            operation='create',
            changes={
                'customer_id': 5,
                'order_number': 'AI-ORD-001',
                'product_name': '智能工单',
                'amount': Decimal('1100.00'),
                'order_date': date(2026, 7, 7),
                'status': 'pending',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'CustomerOrder')
        self.assertEqual(result['change_set'][0]['change_type'], 'create')
        self.assertEqual(result['change_set'][0]['after_snapshot']['order_number'], 'AI-ORD-001')

    def test_order_adapter_delete_execute_sets_delete_time(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.order import OrderModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing order adapter dependency: {exc}')

        adapter = OrderModuleAdapter()
        order = SimpleNamespace(
            id=81,
            delete_time=0,
            save=MagicMock(),
            order_number='AI-ORD-001',
            product_name='智能工单',
            amount=Decimal('1100.00'),
            order_date=date(2026, 7, 7),
            status='pending',
            description='',
            remark='',
            finance_status='pending',
            invoice_request_status='none',
            customer_id=5,
            contract_id=None,
        )
        action = AIActionRequest(
            resource='order',
            operation='delete',
            object_ids=[81],
            changes={},
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_order_for_action', return_value=order), \
                patch('apps.ai.services.module_adapters.order.timezone.now', return_value=SimpleNamespace(timestamp=lambda: 1234567890)):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(order.delete_time, 1234567890)
        order.save.assert_called_once()

    def test_order_adapter_denies_without_permission(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.order import OrderModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing order adapter dependency: {exc}')

        adapter = OrderModuleAdapter()
        action = AIActionRequest(
            resource='order',
            operation='create',
            changes={
                'customer_id': 5,
                'order_number': 'AI-ORD-002',
                'product_name': '智能工单',
                'amount': Decimal('900.00'),
                'order_date': date(2026, 7, 7),
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=False, reason='missing_permission')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: False),
            )

        self.assertFalse(result['success'])
        self.assertIn('权限', result['message'])


class AIActionGatewayOrderDispatchTests(SimpleTestCase):
    def test_gateway_dispatches_order_update_to_registered_adapter(self):
        from apps.ai.services.action_gateway import AIActionGateway

        adapter = MagicMock()
        adapter.resource = 'order'
        adapter.execute.return_value = {'success': True, 'message': 'order updated'}
        operation = SimpleNamespace(
            id=24,
            resource_type='order',
            operation_type='update',
            confirmed_payload={'resource': 'order', 'operation': 'update', 'object_ids': [81], 'changes': {'remark': 'AI修改备注'}},
        )
        user = SimpleNamespace(id=7, is_authenticated=True)

        gateway = AIActionGateway()
        gateway.register(adapter)

        result = gateway.execute_confirmed_action(operation, user)

        adapter.execute.assert_called_once()
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'order updated')


class AIContractAdapterTests(SimpleTestCase):
    def test_contract_adapter_approve_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.contract import ContractModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing contract adapter dependency: {exc}')

        adapter = ContractModuleAdapter()
        contract = SimpleNamespace(
            id=91,
            code='HT-001',
            name='AI合同',
            customer='阿里云国际站',
            cost=Decimal('5000.00'),
            check_status=0,
            check_time=0,
            check_history_uids='',
            delete_time=0,
        )
        action = AIActionRequest(
            resource='contract',
            operation='approve',
            object_ids=[91],
            changes={'check_status': 2},
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_contract_for_action', return_value=contract):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Contract')
        self.assertEqual(result['change_set'][0]['after_snapshot']['check_status'], 2)

    def test_contract_adapter_delete_execute_sets_delete_time(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.contract import ContractModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing contract adapter dependency: {exc}')

        adapter = ContractModuleAdapter()
        contract = SimpleNamespace(
            id=91,
            code='HT-001',
            name='AI合同',
            customer='阿里云国际站',
            cost=Decimal('5000.00'),
            check_status=0,
            check_time=0,
            check_history_uids='',
            delete_time=0,
            save=MagicMock(),
        )
        action = AIActionRequest(
            resource='contract',
            operation='delete',
            object_ids=[91],
            changes={},
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_contract_for_action', return_value=contract), \
                patch('apps.ai.services.module_adapters.contract.timezone.now', return_value=SimpleNamespace(timestamp=lambda: 2233445566)):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(contract.delete_time, 2233445566)
        contract.save.assert_called_once()

    def test_contract_adapter_create_preview_requires_required_fields(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.contract import ContractModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing contract adapter dependency: {exc}')

        adapter = ContractModuleAdapter()
        action = AIActionRequest(
            resource='contract',
            operation='create',
            changes={'name': '信息不完整的合同'},
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertFalse(result['success'])
        self.assertIn('必填', result['message'])


class AIActionGatewayContractDispatchTests(SimpleTestCase):
    def test_gateway_dispatches_contract_update_to_registered_adapter(self):
        from apps.ai.services.action_gateway import AIActionGateway

        adapter = MagicMock()
        adapter.resource = 'contract'
        adapter.execute.return_value = {'success': True, 'message': 'contract updated'}
        operation = SimpleNamespace(
            id=25,
            resource_type='contract',
            operation_type='update',
            confirmed_payload={'resource': 'contract', 'operation': 'update', 'object_ids': [91], 'changes': {'remark': 'AI修改合同备注'}},
        )
        user = SimpleNamespace(id=7, is_authenticated=True)

        gateway = AIActionGateway()
        gateway.register(adapter)

        result = gateway.execute_confirmed_action(operation, user)

        adapter.execute.assert_called_once()
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'contract updated')


class AISupplierAdapterTests(SimpleTestCase):
    def test_supplier_adapter_update_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.supplier import SupplierModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing supplier adapter dependency: {exc}')

        adapter = SupplierModuleAdapter()
        supplier = SimpleNamespace(
            id=101,
            name='旧供应商',
            code='SUP-001',
            contact_person='张三',
            contact_phone='13800000000',
            contact_email='old@example.com',
            address='旧地址',
            tax_number='TAX001',
            bank_account='6222',
            bank_name='旧银行',
            credit_level='A',
            business_scope='旧范围',
            is_active=True,
        )
        action = AIActionRequest(
            resource='supplier',
            operation='update',
            object_ids=[101],
            changes={'name': '新供应商', 'contact_phone': '13900000000'},
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_supplier_for_action', return_value=supplier):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['after_snapshot']['name'], '新供应商')
        self.assertEqual(result['change_set'][0]['after_snapshot']['contact_phone'], '13900000000')


class AIProductAdapterTests(SimpleTestCase):
    def test_product_adapter_delete_execute_sets_delete_time(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.product import ProductModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing product adapter dependency: {exc}')

        adapter = ProductModuleAdapter()
        product = SimpleNamespace(
            id=111,
            name='智能产品',
            code='PRD-001',
            specs='标准版',
            unit='套',
            price=Decimal('199.00'),
            remark='',
            cate_id=None,
            admin_id=7,
            delete_time=None,
            save=MagicMock(),
        )
        action = AIActionRequest(
            resource='product',
            operation='delete',
            object_ids=[111],
            changes={},
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_product_for_action', return_value=product), \
                patch('apps.ai.services.module_adapters.product.timezone.now', return_value='NOW'):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(product.delete_time, 'NOW')
        product.save.assert_called_once()


class AITaskAdapterTests(SimpleTestCase):
    def test_task_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.task import TaskModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing task adapter dependency: {exc}')

        adapter = TaskModuleAdapter()
        action = AIActionRequest(
            resource='task',
            operation='create',
            changes={
                'title': 'AI创建任务',
                'description': '跟进合同回款',
                'assignee_id': 9,
                'start_date': date(2026, 7, 7),
                'end_date': date(2026, 7, 10),
                'priority': 3,
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Task')
        self.assertEqual(result['change_set'][0]['after_snapshot']['title'], 'AI创建任务')

    def test_task_adapter_delete_execute_sets_delete_time(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.task import TaskModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing task adapter dependency: {exc}')

        adapter = TaskModuleAdapter()
        task = SimpleNamespace(
            id=301,
            title='旧任务',
            description='',
            project_id=None,
            step_id=None,
            assignee_id=9,
            start_date=None,
            end_date=None,
            estimated_hours=0,
            actual_hours=0,
            status=1,
            priority=2,
            progress=0,
            creator_id=7,
            delete_time=None,
            save=MagicMock(),
        )
        action = AIActionRequest(resource='task', operation='delete', object_ids=[301], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_task_for_action', return_value=task), \
                patch('apps.ai.services.module_adapters.task.timezone.now', return_value='NOW'):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(task.delete_time, 'NOW')
        task.save.assert_called_once()


class AIWorkHourAdapterTests(SimpleTestCase):
    def test_workhour_adapter_update_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.workhour import WorkHourModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing workhour adapter dependency: {exc}')

        adapter = WorkHourModuleAdapter()
        workhour = SimpleNamespace(
            id=401,
            task_id=301,
            user_id=7,
            work_date=date(2026, 7, 7),
            hours=Decimal('2.50'),
            description='联调',
        )
        action = AIActionRequest(
            resource='workhour',
            operation='update',
            object_ids=[401],
            changes={'hours': Decimal('3.50'), 'description': '联调+回归'},
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_workhour_for_action', return_value=workhour):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['after_snapshot']['hours'], '3.50')
        self.assertEqual(result['change_set'][0]['after_snapshot']['description'], '联调+回归')


class AINoticeAdapterTests(SimpleTestCase):
    def test_notice_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.notice import NoticeModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing notice adapter dependency: {exc}')

        adapter = NoticeModuleAdapter()
        action = AIActionRequest(
            resource='notice',
            operation='create',
            changes={
                'title': 'AI公告',
                'content': '今晚系统维护',
                'notice_type': 'system',
                'is_published': True,
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['after_snapshot']['title'], 'AI公告')
        self.assertTrue(result['change_set'][0]['after_snapshot']['is_published'])


class AIScheduleAdapterTests(SimpleTestCase):
    def test_schedule_adapter_delete_execute_sets_delete_time(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.schedule import ScheduleModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing schedule adapter dependency: {exc}')

        adapter = ScheduleModuleAdapter()
        schedule = SimpleNamespace(
            id=501,
            work_id=0,
            title='客户拜访',
            start_time=timezone.now(),
            end_time=timezone.now(),
            labor_time=2.0,
            admin_id=7,
            did=3,
            labor_type=1,
            cid=None,
            tid=None,
            content='上午拜访客户',
            delete_time=0,
            create_time=0,
            update_time=0,
            save=MagicMock(),
        )
        action = AIActionRequest(resource='schedule', operation='delete', object_ids=[501], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_schedule_for_action', return_value=schedule), \
                patch('apps.ai.services.module_adapters.schedule.timezone.now', return_value=SimpleNamespace(timestamp=lambda: 99887766)):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(schedule.delete_time, 99887766)
        schedule.save.assert_called_once()


class AIMessageAdapterTests(SimpleTestCase):
    def test_message_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.message import MessageModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing message adapter dependency: {exc}')

        adapter = MessageModuleAdapter()
        action = AIActionRequest(
            resource='message',
            operation='create',
            changes={
                'title': 'AI提醒',
                'content': '请尽快审批合同',
                'priority': 3,
                'user_id': 9,
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Message')
        self.assertEqual(result['change_set'][0]['after_snapshot']['title'], 'AI提醒')

    def test_message_adapter_delete_execute_marks_inactive(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.message import MessageModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing message adapter dependency: {exc}')

        adapter = MessageModuleAdapter()
        message = SimpleNamespace(
            id=601,
            category_id=None,
            user_id=9,
            sender_id=7,
            title='AI提醒',
            content='请尽快审批合同',
            priority=2,
            is_broadcast=False,
            target_users='',
            target_departments='',
            related_object_type='',
            related_object_id=None,
            action_url='',
            expire_time=None,
            is_active=True,
            ai_summary=None,
            ai_suggested_replies=[],
            save=MagicMock(),
        )
        action = AIActionRequest(resource='message', operation='delete', object_ids=[601], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_message_for_action', return_value=message):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertFalse(message.is_active)
        message.save.assert_called_once()


class AIMeetingAdapterTests(SimpleTestCase):
    def test_meeting_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.meeting import MeetingModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing meeting adapter dependency: {exc}')

        adapter = MeetingModuleAdapter()
        action = AIActionRequest(
            resource='meeting',
            operation='create',
            changes={
                'title': 'AI项目例会',
                'meeting_date': '2026-07-07T09:00:00',
                'meeting_end_time': '2026-07-07T10:30:00',
                'meeting_type': 'project',
                'location': 'A-301',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'MeetingRecord')
        self.assertEqual(result['change_set'][0]['after_snapshot']['title'], 'AI项目例会')

    def test_meeting_adapter_delete_execute_marks_soft_deleted(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.meeting import MeetingModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing meeting adapter dependency: {exc}')

        adapter = MeetingModuleAdapter()
        meeting = SimpleNamespace(
            id=701,
            title='项目例会',
            meeting_type='project',
            meeting_date=timezone.now(),
            meeting_end_time=timezone.now() + timedelta(hours=1),
            room_id=None,
            location='A-301',
            host_id=7,
            recorder_id=7,
            department_id=None,
            status='scheduled',
            agenda='',
            content='',
            summary='',
            resolution='',
            action_items='',
            next_meeting=None,
            attachments='',
            rating=None,
            feedback='',
            deleted_at=None,
            is_deleted=False,
            save=MagicMock(),
        )
        action = AIActionRequest(resource='meeting', operation='delete', object_ids=[701], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_meeting_for_action', return_value=meeting), \
                patch('apps.ai.services.module_adapters.meeting.timezone.now', return_value='NOW'):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(meeting.deleted_at, 'NOW')
        self.assertTrue(meeting.is_deleted)
        meeting.save.assert_called_once()


class AIApprovalFlowAdapterTests(SimpleTestCase):
    def test_approval_flow_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.approval_flow import ApprovalFlowModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing approval flow adapter dependency: {exc}')

        adapter = ApprovalFlowModuleAdapter()
        action = AIActionRequest(
            resource='approval_flow',
            operation='create',
            changes={
                'name': 'AI采购审批流',
                'code': 'FLOW_AI_001',
                'description': '用于采购申请',
                'is_active': True,
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'ApprovalFlow')
        self.assertEqual(result['change_set'][0]['after_snapshot']['code'], 'FLOW_AI_001')

    def test_approval_flow_adapter_delete_execute_calls_delete(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.approval_flow import ApprovalFlowModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing approval flow adapter dependency: {exc}')

        adapter = ApprovalFlowModuleAdapter()
        flow = SimpleNamespace(
            id=801,
            name='采购审批流',
            code='FLOW_001',
            description='',
            approval_type_id=None,
            is_active=True,
            delete=MagicMock(),
        )
        action = AIActionRequest(resource='approval_flow', operation='delete', object_ids=[801], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_flow_for_action', return_value=flow):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        flow.delete.assert_called_once()


class AIProductionAdapterTests(SimpleTestCase):
    def test_production_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.production import ProductionModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing production adapter dependency: {exc}')

        adapter = ProductionModuleAdapter()
        action = AIActionRequest(
            resource='production',
            operation='create',
            changes={
                'name': 'AI生产计划',
                'code': 'PLAN_AI_001',
                'quantity': '120.50',
                'unit': '件',
                'plan_start_date': '2026-07-08',
                'plan_end_date': '2026-07-15',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'ProductionPlan')
        self.assertEqual(result['change_set'][0]['after_snapshot']['quantity'], '120.50')

    def test_production_adapter_delete_execute_calls_delete(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.production import ProductionModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing production adapter dependency: {exc}')

        adapter = ProductionModuleAdapter()
        plan = SimpleNamespace(
            id=901,
            name='生产计划A',
            code='PLAN_001',
            product_id=None,
            bom_id=None,
            procedure_set_id=None,
            process_route_id=None,
            quantity=Decimal('100.00'),
            unit='件',
            plan_start_date=date(2026, 7, 8),
            plan_end_date=date(2026, 7, 15),
            actual_start_date=None,
            actual_end_date=None,
            status=1,
            priority=2,
            department_id=None,
            manager_id=7,
            description='',
            auto_complete=False,
            complete_threshold=Decimal('100.00'),
            delete=MagicMock(),
        )
        action = AIActionRequest(resource='production', operation='delete', object_ids=[901], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_plan_for_action', return_value=plan):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        plan.delete.assert_called_once()


class AIFollowupAdapterTests(SimpleTestCase):
    def test_followup_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.followup import FollowupModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing followup adapter dependency: {exc}')

        adapter = FollowupModuleAdapter()
        action = AIActionRequest(
            resource='followup',
            operation='create',
            changes={
                'customer_id': 12,
                'content': '已电话回访，客户计划下周签约',
                'follow_type': 'phone',
                'next_follow_time': '2026-07-10T10:00:00',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'FollowRecord')
        self.assertEqual(result['change_set'][0]['after_snapshot']['customer_id'], 12)

    def test_followup_adapter_delete_execute_sets_delete_time(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.followup import FollowupModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing followup adapter dependency: {exc}')

        adapter = FollowupModuleAdapter()
        followup = SimpleNamespace(
            id=1001,
            customer_id=12,
            follow_type='phone',
            content='老内容',
            follow_user_id=7,
            follow_time=timezone.now(),
            next_follow_time=None,
            ai_summary='',
            ai_sentiment='',
            ai_key_points=[],
            create_time=timezone.now(),
            update_time=timezone.now(),
            delete_time=0,
            save=MagicMock(),
        )
        action = AIActionRequest(resource='followup', operation='delete', object_ids=[1001], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_followup_for_action', return_value=followup), \
                patch('apps.ai.services.module_adapters.followup.timezone.now', return_value=SimpleNamespace(timestamp=lambda: 778899)):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(followup.delete_time, 778899)
        followup.save.assert_called_once()


class AIEmployeeAdapterTests(SimpleTestCase):
    def test_employee_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.employee import EmployeeModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing employee adapter dependency: {exc}')

        adapter = EmployeeModuleAdapter()
        action = AIActionRequest(
            resource='employee',
            operation='create',
            changes={
                'username': 'zhangsan',
                'name': '张三',
                'mobile': '13800138000',
                'did': 3,
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Admin')
        self.assertEqual(result['change_set'][0]['after_snapshot']['username'], 'zhangsan')


class AIDepartmentAdapterTests(SimpleTestCase):
    def test_department_adapter_update_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.department import DepartmentModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing department adapter dependency: {exc}')

        adapter = DepartmentModuleAdapter()
        department = SimpleNamespace(
            id=120,
            name='旧部门',
            pid=0,
            code='D001',
            manager_id=7,
            leader_ids='7',
            phone='021-12345678',
            remark='旧备注',
            sort=10,
            status=1,
            level=0,
            is_active=True,
        )
        action = AIActionRequest(
            resource='department',
            operation='update',
            object_ids=[120],
            changes={'name': '新部门', 'phone': '021-87654321'},
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_department_for_action', return_value=department):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['after_snapshot']['name'], '新部门')

    def test_department_adapter_delete_execute_disables_department(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.department import DepartmentModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing department adapter dependency: {exc}')

        adapter = DepartmentModuleAdapter()
        department = SimpleNamespace(
            id=120,
            name='研发部',
            pid=0,
            code='D001',
            manager_id=7,
            leader_ids='7',
            phone='021-12345678',
            remark='',
            sort=10,
            status=1,
            level=0,
            is_active=True,
            save=MagicMock(),
        )
        action = AIActionRequest(resource='department', operation='delete', object_ids=[120], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_department_for_action', return_value=department):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(department.status, 0)
        self.assertFalse(department.is_active)
        department.save.assert_called_once()


class AIInventoryAdapterTests(SimpleTestCase):
    def test_inventory_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.inventory import InventoryModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing inventory adapter dependency: {exc}')

        adapter = InventoryModuleAdapter()
        action = AIActionRequest(
            resource='inventory',
            operation='create',
            changes={
                'name': '轴承',
                'code': 'MAT-001',
                'unit': '个',
                'category_id': 5,
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'InventoryItem')
        self.assertEqual(result['change_set'][0]['after_snapshot']['code'], 'MAT-001')


class AIDocumentAdapterTests(SimpleTestCase):
    def test_document_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.document import DocumentModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing document adapter dependency: {exc}')

        adapter = DocumentModuleAdapter()
        action = AIActionRequest(
            resource='document',
            operation='create',
            changes={
                'title': '关于质量巡检的通知',
                'document_number': 'DOC-2026-001',
                'category_id': 3,
                'content': '请各部门按要求完成巡检。',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Document')
        self.assertEqual(result['change_set'][0]['after_snapshot']['status'], 'draft')

    def test_document_adapter_delete_execute_archives_document(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.document import DocumentModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing document adapter dependency: {exc}')

        adapter = DocumentModuleAdapter()
        document = SimpleNamespace(
            id=81,
            title='旧公文',
            document_number='DOC-OLD',
            category_id=3,
            content='旧内容',
            summary='',
            author_id=7,
            department_id=2,
            status='draft',
            urgency='normal',
            security_level='internal',
            current_reviewer_id=None,
            review_deadline=None,
            publish_time=None,
            effective_time=None,
            expire_time=None,
            attachments='',
            save=MagicMock(),
        )
        action = AIActionRequest(resource='document', operation='delete', object_ids=[81], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_document_for_action', return_value=document):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(document.status, 'archived')
        document.save.assert_called_once()

    def test_document_adapter_submit_execute_updates_status(self):
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.module_adapters.document import DocumentModuleAdapter

        adapter = DocumentModuleAdapter()
        document = SimpleNamespace(
            id=82,
            title='质量通知',
            document_number='DOC-2026-002',
            category_id=3,
            content='内容',
            summary='',
            author_id=7,
            department_id=2,
            status='draft',
            urgency='normal',
            security_level='internal',
            current_reviewer_id=None,
            review_deadline=None,
            publish_time=None,
            effective_time=None,
            expire_time=None,
            attachments='',
            save=MagicMock(),
        )
        action = AIActionRequest(resource='document', operation='submit', object_ids=[82], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_document_for_action', return_value=document):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(document.status, 'submitted')
        document.save.assert_called_once()

    def test_document_adapter_publish_execute_sets_publish_time(self):
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.module_adapters.document import DocumentModuleAdapter

        adapter = DocumentModuleAdapter()
        document = SimpleNamespace(
            id=83,
            title='质量通知',
            document_number='DOC-2026-003',
            category_id=3,
            content='内容',
            summary='',
            author_id=7,
            department_id=2,
            status='approved',
            urgency='normal',
            security_level='internal',
            current_reviewer_id=None,
            review_deadline=None,
            publish_time=None,
            effective_time=None,
            expire_time=None,
            attachments='',
            save=MagicMock(),
        )
        action = AIActionRequest(resource='document', operation='publish', object_ids=[83], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_document_for_action', return_value=document), \
                patch('apps.ai.services.module_adapters.document.timezone.now', return_value='NOW'):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(document.status, 'published')
        self.assertEqual(document.publish_time, 'NOW')
        document.save.assert_called_once()


class AIWarehouseAdapterTests(SimpleTestCase):
    def test_warehouse_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.warehouse import WarehouseModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing warehouse adapter dependency: {exc}')

        adapter = WarehouseModuleAdapter()
        action = AIActionRequest(
            resource='warehouse',
            operation='create',
            changes={
                'name': '华东一号仓',
                'code': 'WH-EAST-001',
                'warehouse_type': 'main',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Warehouse')
        self.assertEqual(result['change_set'][0]['after_snapshot']['code'], 'WH-EAST-001')


class AIProjectMetadataAdapterTests(SimpleTestCase):
    def test_project_document_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.project_metadata import ProjectMetadataModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing project metadata adapter dependency: {exc}')

        adapter = ProjectMetadataModuleAdapter('project_document')
        action = AIActionRequest(
            resource='project_document',
            operation='create',
            changes={
                'project_id': 5,
                'title': '交付清单',
                'content': '第一版交付清单',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=12, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'ProjectDocument')
        self.assertEqual(result['change_set'][0]['after_snapshot']['title'], '交付清单')


class AIContactAdapterTests(SimpleTestCase):
    def test_contact_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.contact import ContactModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing contact adapter dependency: {exc}')

        adapter = ContactModuleAdapter()
        customer = SimpleNamespace(id=18)
        action = AIActionRequest(
            resource='contact',
            operation='create',
            changes={
                'customer_id': 18,
                'contact_person': '张三',
                'phone': '13800000000',
                'position': '采购经理',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_customer_for_action', return_value=customer):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Contact')
        self.assertEqual(result['change_set'][0]['after_snapshot']['contact_person'], '张三')


class AIProductionResourceAdapterTests(SimpleTestCase):
    def test_production_task_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.production_resource import ProductionResourceModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing production resource adapter dependency: {exc}')

        adapter = ProductionResourceModuleAdapter('production_task')
        action = AIActionRequest(
            resource='production_task',
            operation='create',
            changes={
                'plan_id': 9,
                'name': '装配工单',
                'code': 'TASK-001',
                'procedure_id': 4,
                'quantity': '20.00',
                'plan_start_time': '2026-07-08 09:00:00',
                'plan_end_time': '2026-07-08 18:00:00',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'ProductionTask')
        self.assertEqual(result['change_set'][0]['after_snapshot']['code'], 'TASK-001')

    def test_production_equipment_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.production_resource import ProductionResourceModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing production resource adapter dependency: {exc}')

        adapter = ProductionResourceModuleAdapter('production_equipment')
        action = AIActionRequest(
            resource='production_equipment',
            operation='create',
            changes={
                'name': '贴片机一号',
                'code': 'EQ-001',
                'purchase_cost': '120000.00',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Equipment')
        self.assertEqual(result['change_set'][0]['after_snapshot']['code'], 'EQ-001')


class AIAlertAdapterTests(SimpleTestCase):
    def test_alert_adapter_approve_execute_marks_processed(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.alert import AlertModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing alert adapter dependency: {exc}')

        adapter = AlertModuleAdapter()
        alert = SimpleNamespace(
            id=12,
            item_id=5,
            warehouse_id=6,
            alert_type='low_stock',
            current_quantity=Decimal('2'),
            threshold_value=Decimal('10'),
            message='库存过低',
            status=1,
            handler_id=None,
            handle_time=None,
            handle_remark='',
            create_time=None,
            save=MagicMock(),
        )
        action = AIActionRequest(resource='alert', operation='approve', object_ids=[12], changes={'handle_remark': '已安排补货'})

        with patch.object(adapter, '_check_permission', return_value={'allowed': True, 'message': 'allowed'}), \
                patch.object(adapter, '_get_alert_for_action', return_value=alert), \
                patch('apps.ai.services.module_adapters.alert.timezone.now', return_value='NOW'):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=9, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(alert.status, 2)
        self.assertEqual(alert.handler_id, 9)
        self.assertEqual(alert.handle_time, 'NOW')
        self.assertEqual(alert.handle_remark, '已安排补货')
        alert.save.assert_called()


class AIPersonalWorkspaceAdapterTests(SimpleTestCase):
    def test_personal_task_toggle_execute_updates_status(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.personal_workspace import PersonalWorkspaceModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing personal workspace adapter dependency: {exc}')

        adapter = PersonalWorkspaceModuleAdapter('personal_task')
        task = SimpleNamespace(
            id=31,
            title='跟进报价',
            description='',
            priority=2,
            status='todo',
            due_date=None,
            completed_at=None,
            progress=20,
            estimated_hours=None,
            actual_hours=None,
            user_id=9,
            save=MagicMock(),
        )
        action = AIActionRequest(resource='personal_task', operation='submit', object_ids=[31], changes={})

        with patch.object(adapter, '_check_permission', return_value={'allowed': True, 'message': 'allowed'}), \
                patch.object(adapter, '_get_instance_for_action', return_value=task), \
                patch('apps.ai.services.module_adapters.personal_workspace.timezone.now', return_value='NOW'):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=9, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(task.status, 'completed')
        self.assertEqual(task.progress, 100)
        self.assertEqual(task.completed_at, 'NOW')
        task.save.assert_called_once()


class AIStockDocumentWorkflowAdapterTests(SimpleTestCase):
    def test_stockin_adapter_approve_execute_marks_checker(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.stock import StockDocumentModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing stock adapter dependency: {exc}')

        adapter = StockDocumentModuleAdapter()
        stockin = SimpleNamespace(
            id=61,
            code='RK-001',
            stock_in_type='purchase',
            warehouse_id=9,
            supplier_id=4,
            purchase_order_id=None,
            production_plan_id=None,
            total_amount=Decimal('1000.00'),
            total_quantity=Decimal('5.00'),
            status=1,
            checker_id=None,
            check_time=None,
            stocker_id=None,
            stock_time=None,
            remark='',
            save=MagicMock(),
        )
        action = AIActionRequest(resource='stockin', operation='approve', object_ids=[61], changes={})

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')), \
                patch.object(adapter, '_get_stockin_for_action', return_value=stockin), \
                patch('apps.ai.services.module_adapters.stock.timezone.now', return_value='NOW'):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(stockin.status, 2)
        self.assertEqual(stockin.checker_id, 7)
        self.assertEqual(stockin.check_time, 'NOW')
        stockin.save.assert_called_once()

    def test_stockout_adapter_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.stock import StockDocumentModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing stock adapter dependency: {exc}')

        adapter = StockDocumentModuleAdapter()
        action = AIActionRequest(
            resource='stockout',
            operation='create',
            changes={
                'code': 'CK-001',
                'stock_out_type': 'sale',
                'warehouse_id': 3,
                'total_quantity': '8.50',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'StockOut')
        self.assertEqual(result['change_set'][0]['after_snapshot']['code'], 'CK-001')


class AIApprovalTaskAdapterTests(SimpleTestCase):
    def test_assigned_authenticated_handler_does_not_need_global_change_permission(self):
        from apps.ai.services.action_contracts import AIActionRequest
        from apps.ai.services.module_adapters.approval_task import ApprovalTaskModuleAdapter

        adapter = ApprovalTaskModuleAdapter()
        approval = SimpleNamespace(id=15, status=1, current_step_order=1)
        step = SimpleNamespace(step_order=1)
        task = SimpleNamespace(
            id=51,
            approval=approval,
            approval_id=15,
            step=step,
            step_id=3,
            handler_id=9,
            status='pending',
            result='',
            comment='',
            completed_at=None,
        )
        action = AIActionRequest(
            resource='approval_task',
            operation='approve',
            object_ids=[51],
            changes={},
        )
        user = SimpleNamespace(
            id=9,
            is_authenticated=True,
            is_superuser=False,
            has_perm=lambda _permission: False,
        )

        with patch.object(adapter, '_get_task_for_action', return_value=task):
            result = adapter.preview(action, user)

        self.assertTrue(result['success'])

    def test_approval_task_adapter_execute_delegates_to_flow_action(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.approval_task import ApprovalTaskModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing approval task adapter dependency: {exc}')

        adapter = ApprovalTaskModuleAdapter()
        approval = SimpleNamespace(
            id=15,
            status=1,
            current_step_order=2,
            save=MagicMock(),
        )
        step = SimpleNamespace(
            step_order=2,
            approval_mode='single',
            step_type='approve',
        )
        task = SimpleNamespace(
            id=51,
            approval=approval,
            step=step,
            status='pending',
            result='',
            comment='',
            completed_at=None,
            handler=None,
            save=MagicMock(),
        )
        action = AIActionRequest(resource='approval_task', operation='approve', object_ids=[51], changes={})

        with patch.object(adapter, '_check_permission', return_value={'allowed': True, 'message': 'allowed'}), \
                patch.object(adapter, '_get_task_for_action', return_value=task), \
                patch.object(
                    adapter,
                    '_execute_flow_action',
                    return_value={'success': True, 'message': 'approve', 'change_set': []},
                ) as execute_flow_action:
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=9, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        execute_flow_action.assert_called_once_with(task, action, ANY)


class AIFinanceAdapterTests(SimpleTestCase):
    def test_finance_payment_create_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.finance import FinanceModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing finance adapter dependency: {exc}')

        adapter = FinanceModuleAdapter()
        action = AIActionRequest(
            resource='finance',
            operation='create',
            context={'model': 'payment'},
            changes={
                'amount': '5200.00',
                'payment_date': '2026-07-08T11:00:00',
                'customer_id': 12,
                'remark': '预付款',
            },
        )

        with patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Payment')
        self.assertEqual(result['change_set'][0]['after_snapshot']['amount'], '5200.00')

    def test_finance_income_update_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.finance import FinanceModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing finance adapter dependency: {exc}')

        adapter = FinanceModuleAdapter()
        income = SimpleNamespace(
            id=44,
            invoice_id=43,
            amount=Decimal('3000.00'),
            income_date=timezone.now(),
            file_ids='',
            remark='旧备注',
            create_time=123,
        )
        action = AIActionRequest(
            resource='finance',
            operation='update',
            object_ids=[44],
            context={'model': 'income'},
            changes={'remark': '银行到账确认'},
        )

        with patch.object(adapter, '_get_income_for_action', return_value=income):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Income')
        self.assertEqual(result['change_set'][0]['after_snapshot']['remark'], '银行到账确认')

    def test_finance_invoice_update_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.finance import FinanceModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing finance adapter dependency: {exc}')

        adapter = FinanceModuleAdapter()
        invoice = SimpleNamespace(
            id=43,
            code='FP-001',
            customer_id=12,
            contract_id=0,
            project_id=0,
            amount=Decimal('2300.00'),
            did=3,
            admin_id=7,
            open_status=0,
            open_admin_id=0,
            open_time=0,
            delivery='',
            types=1,
            invoice_type=2,
            invoice_subject=0,
            invoice_title='旧抬头',
            invoice_tax='',
            invoice_phone='',
            invoice_address='',
            invoice_bank='',
            invoice_account='',
            invoice_banking='',
            file_ids='',
            other_file_ids='',
            enter_amount=Decimal('0'),
            enter_status=0,
            enter_time=0,
            check_status=0,
            check_flow_id=0,
            check_step_sort=0,
            check_uids='',
            check_last_uid='',
            check_history_uids='',
            check_copy_uids='',
            check_time=0,
            create_time=123,
            remark='旧备注',
        )
        action = AIActionRequest(
            resource='finance',
            operation='update',
            object_ids=[43],
            context={'model': 'invoice'},
            changes={'delivery': 'SF987654', 'remark': '已寄出'},
        )

        with patch.object(adapter, '_get_invoice_for_action', return_value=invoice):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Invoice')
        self.assertEqual(result['change_set'][0]['after_snapshot']['delivery'], 'SF987654')

    def test_finance_expense_update_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.finance import FinanceModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing finance adapter dependency: {exc}')

        adapter = FinanceModuleAdapter()
        expense = SimpleNamespace(
            id=41,
            cost=Decimal('120.00'),
            remark='旧备注',
            check_status=0,
            pay_status=0,
            file_ids='1,2',
            create_time=123,
        )
        action = AIActionRequest(
            resource='finance',
            operation='update',
            object_ids=[41],
            context={'model': 'expense'},
            changes={'remark': '新备注', 'cost': Decimal('150.00')},
        )

        with patch.object(adapter, '_get_expense_for_action', return_value=expense):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'Expense')
        self.assertEqual(result['change_set'][0]['before_snapshot']['remark'], '旧备注')
        self.assertEqual(result['change_set'][0]['after_snapshot']['remark'], '新备注')

    def test_finance_expense_delete_execute_marks_soft_delete(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.finance import FinanceModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing finance adapter dependency: {exc}')

        adapter = FinanceModuleAdapter()
        expense = SimpleNamespace(
            id=41,
            delete_time=None,
            delete=MagicMock(),
            save=MagicMock(),
        )
        action = AIActionRequest(
            resource='finance',
            operation='delete',
            object_ids=[41],
            context={'model': 'expense'},
            changes={},
        )

        with patch.object(adapter, '_get_expense_for_action', return_value=expense), \
                patch('apps.ai.services.module_adapters.finance.timezone.now', return_value='NOW'):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        expense.delete.assert_called_once()

    def test_finance_invoice_request_approve_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.finance import FinanceModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing finance adapter dependency: {exc}')

        adapter = FinanceModuleAdapter()
        request = SimpleNamespace(
            id=52,
            status='pending',
            reviewer_id=0,
            review_time=0,
            invoice_id=0,
            invoice_time=0,
            save=MagicMock(),
        )
        action = AIActionRequest(
            resource='finance',
            operation='approve',
            object_ids=[52],
            context={'model': 'invoice_request'},
            changes={'status': 'approved'},
        )

        with patch.object(adapter, '_get_invoice_request_for_action', return_value=request):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'InvoiceRequest')
        self.assertEqual(result['change_set'][0]['before_snapshot']['status'], 'pending')
        self.assertEqual(result['change_set'][0]['after_snapshot']['status'], 'approved')

    def test_finance_order_record_update_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.finance import FinanceModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing finance adapter dependency: {exc}')

        adapter = FinanceModuleAdapter()
        record = SimpleNamespace(
            id=63,
            order_id=11,
            total_amount=Decimal('9800.00'),
            paid_amount=Decimal('3000.00'),
            payment_status='partial',
            due_date=date(2026, 7, 30),
            create_time=123,
            remark='旧备注',
        )
        action = AIActionRequest(
            resource='finance',
            operation='update',
            object_ids=[63],
            context={'model': 'order_record'},
            changes={'remark': '补充回款说明', 'payment_status': 'paid'},
        )

        with patch.object(adapter, '_get_order_record_for_action', return_value=record):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'OrderFinanceRecord')
        self.assertEqual(result['change_set'][0]['after_snapshot']['payment_status'], 'paid')

    def test_finance_adapter_denies_without_permission(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.finance import FinanceModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing finance adapter dependency: {exc}')

        adapter = FinanceModuleAdapter()
        expense = SimpleNamespace(id=41, cost=Decimal('120.00'))
        action = AIActionRequest(
            resource='finance',
            operation='update',
            object_ids=[41],
            context={'model': 'expense'},
            changes={'remark': '新备注'},
        )

        with patch.object(adapter, '_get_expense_for_action', return_value=expense), \
                patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=False, reason='missing_permission')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, has_perm=lambda code: False),
            )

        self.assertFalse(result['success'])
        self.assertIn('权限', result['message'])


class AIActionGatewayFinanceDispatchTests(SimpleTestCase):
    def test_gateway_dispatches_finance_update_to_registered_adapter(self):
        from apps.ai.services.action_gateway import AIActionGateway

        adapter = MagicMock()
        adapter.resource = 'finance'
        adapter.execute.return_value = {'success': True, 'message': 'finance updated'}
        operation = SimpleNamespace(
            id=23,
            resource_type='finance',
            operation_type='update',
            confirmed_payload={
                'resource': 'finance',
                'operation': 'update',
                'object_ids': [41],
                'context': {'model': 'expense'},
                'changes': {'remark': '新备注'},
            },
        )
        user = SimpleNamespace(id=7, is_authenticated=True)

        gateway = AIActionGateway()
        gateway.register(adapter)

        result = gateway.execute_confirmed_action(operation, user)

        adapter.execute.assert_called_once()
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'finance updated')


class AIFinanceRollbackTests(SimpleTestCase):
    def test_rollback_recreates_deleted_expense_from_snapshot(self):
        try:
            from apps.ai.services.rollback_service import rollback_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.rollback_service.rollback_service is missing')

        change_set = SimpleNamespace(
            sequence=1,
            app_label='finance',
            model_name='Expense',
            object_pk='41',
            change_type='delete',
            before_snapshot={
                'id': 41,
                'code': 'BX-41',
                'cost': '120.00',
                'remark': '旧备注',
            },
            after_snapshot={
                'id': 41,
                'code': 'BX-41',
                'cost': '120.00',
                'remark': '旧备注',
            },
            changed_fields=['code', 'cost', 'remark'],
            is_rollback_supported=True,
        )
        operation = SimpleNamespace(
            id=91,
            status='executed',
            change_sets=SimpleNamespace(all=lambda: [change_set]),
            save=MagicMock(),
        )
        recreated = SimpleNamespace()

        with patch('apps.ai.services.rollback_service.AIOperation.objects.get', return_value=operation), \
                patch('apps.ai.services.rollback_service.AIOperationRollback.objects.create'), \
                patch('apps.ai.services.rollback_service.build_rollback_plan', return_value=[change_set]), \
                patch('apps.ai.services.rollback_service.apps.get_model') as get_model, \
                patch('apps.ai.services.rollback_service.transaction.atomic'):
            get_model.return_value = MagicMock(
                objects=MagicMock(
                    get=MagicMock(side_effect=Exception('missing')),
                    create=MagicMock(return_value=recreated),
                )
            )

            result = rollback_service.rollback_operation(operation_id=91, user=SimpleNamespace(id=7))

        self.assertTrue(result['success'])
        get_model.return_value.objects.create.assert_called_once()


class AIDiskRollbackTests(SimpleTestCase):
    def test_rollback_restores_permanently_deleted_disk_file_from_backup(self):
        try:
            from apps.ai.services.rollback_service import rollback_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.rollback_service.rollback_service is missing')

        import os
        import shutil
        import tempfile

        media_root = tempfile.mkdtemp(prefix='disk-rollback-tests-')
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)

        backup_path = os.path.join(media_root, 'ai_backups', 'disk', 'file', '501', '61', '旧文件.txt')
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        with open(backup_path, 'w', encoding='utf-8') as handle:
            handle.write('backup content')

        change_set = SimpleNamespace(
            sequence=1,
            app_label='disk',
            model_name='DiskFile',
            object_pk='61',
            change_type='delete',
            before_snapshot={
                'id': 61,
                'name': '旧文件.txt',
                'original_name': '旧文件.txt',
                'file_path': 'disk/61/旧文件.txt',
                'file_size': 14,
                'file_ext': '.txt',
                'file_type': 'document',
                'mime_type': 'text/plain',
                'folder_id': None,
                'owner_id': 7,
                'department_id': 3,
                'is_public': False,
                'is_starred': False,
                'version': '1.0',
                'parent_file_id': None,
            },
            after_snapshot=None,
            changed_fields=['delete_time'],
            rollback_metadata={
                'permanent': True,
                'backup_file_path': backup_path,
            },
            is_rollback_supported=True,
        )
        operation = SimpleNamespace(
            id=501,
            status='executed',
            change_sets=SimpleNamespace(all=lambda: [change_set]),
            save=MagicMock(),
        )
        recreated = SimpleNamespace(save=MagicMock())

        with patch('apps.ai.services.rollback_service.settings.MEDIA_ROOT', media_root), \
                patch('apps.ai.services.rollback_service.AIOperation.objects.get', return_value=operation), \
                patch('apps.ai.services.rollback_service.AIOperationRollback.objects.create'), \
                patch('apps.ai.services.rollback_service.build_rollback_plan', return_value=[change_set]), \
                patch('apps.ai.services.rollback_service.apps.get_model') as get_model, \
                patch('apps.ai.services.rollback_service.transaction.atomic'):
            get_model.return_value = MagicMock(
                objects=MagicMock(
                    get=MagicMock(side_effect=Exception('missing')),
                    create=MagicMock(return_value=recreated),
                )
            )

            result = rollback_service.rollback_operation(operation_id=501, user=SimpleNamespace(id=7))

        self.assertTrue(result['success'])
        self.assertTrue(os.path.exists(os.path.join(media_root, 'disk', '61', '旧文件.txt')))
        get_model.return_value.objects.create.assert_called_once()

    def test_rollback_restores_permanently_deleted_disk_folder_tree_from_snapshot(self):
        try:
            from apps.ai.services.rollback_service import rollback_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.rollback_service.rollback_service is missing')

        import os
        import shutil
        import tempfile

        media_root = tempfile.mkdtemp(prefix='disk-folder-rollback-tests-')
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)

        backup_file_path = os.path.join(media_root, 'ai_backups', 'disk', 'folder', '701', '801', '子文件.txt')
        os.makedirs(os.path.dirname(backup_file_path), exist_ok=True)
        with open(backup_file_path, 'w', encoding='utf-8') as handle:
            handle.write('folder backup content')

        tree_snapshot = {
            'folder': {
                'model_name': 'DiskFolder',
                'id': 701,
                'name': '项目资料',
                'parent_id': None,
                'owner_id': 7,
                'department_id': 3,
                'is_public': False,
                'permission_level': 2,
                'delete_time': 123,
            },
            'files': [
                {
                    'model_name': 'DiskFile',
                    'id': 801,
                    'name': '子文件.txt',
                    'original_name': '子文件.txt',
                    'file_path': 'disk/701/子文件.txt',
                    'file_size': 20,
                    'file_ext': '.txt',
                    'file_type': 'document',
                    'mime_type': 'text/plain',
                    'folder_id': 701,
                    'owner_id': 7,
                    'department_id': 3,
                    'is_public': False,
                    'is_starred': False,
                    'version': '1.0',
                    'parent_file_id': None,
                    'backup_file_path': backup_file_path,
                }
            ],
            'children': [],
        }

        change_set = SimpleNamespace(
            sequence=1,
            app_label='disk',
            model_name='DiskFolder',
            object_pk='701',
            change_type='delete',
            before_snapshot=tree_snapshot['folder'],
            after_snapshot=None,
            changed_fields=['delete_time'],
            rollback_metadata={
                'permanent': True,
                'tree_snapshot': tree_snapshot,
            },
            is_rollback_supported=True,
        )
        operation = SimpleNamespace(
            id=702,
            status='executed',
            change_sets=SimpleNamespace(all=lambda: [change_set]),
            save=MagicMock(),
        )
        restored_folder = SimpleNamespace(save=MagicMock())
        restored_file = SimpleNamespace(save=MagicMock())

        def get_model(app_label, model_name):
            if model_name == 'DiskFolder':
                return MagicMock(objects=MagicMock(get=MagicMock(side_effect=Exception('missing')), create=MagicMock(return_value=restored_folder)))
            if model_name == 'DiskFile':
                return MagicMock(objects=MagicMock(get=MagicMock(side_effect=Exception('missing')), create=MagicMock(return_value=restored_file)))
            raise LookupError(model_name)

        with patch('apps.ai.services.rollback_service.settings.MEDIA_ROOT', media_root), \
                patch('apps.ai.services.rollback_service.AIOperation.objects.get', return_value=operation), \
                patch('apps.ai.services.rollback_service.AIOperationRollback.objects.create'), \
                patch('apps.ai.services.rollback_service.build_rollback_plan', return_value=[change_set]), \
                patch('apps.ai.services.rollback_service.apps.get_model', side_effect=get_model), \
                patch('apps.ai.services.rollback_service.transaction.atomic'):
            result = rollback_service.rollback_operation(operation_id=702, user=SimpleNamespace(id=7))

        self.assertTrue(result['success'])
        self.assertTrue(os.path.exists(os.path.join(media_root, 'disk', '701', '子文件.txt')))


class AIDiskAdapterTests(SimpleTestCase):
    def test_disk_permission_nodes_include_folder_permissions(self):
        from apps.user.config.permission_nodes import get_all_permission_codenames

        codenames = set(get_all_permission_codenames())

        self.assertIn('view_disk_folder', codenames)
        self.assertIn('change_disk_folder', codenames)
        self.assertIn('delete_disk_folder', codenames)

    def test_disk_file_rename_preview_builds_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.disk import DiskModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing disk adapter dependency: {exc}')

        adapter = DiskModuleAdapter()
        disk_file = SimpleNamespace(
            id=61,
            name='旧文件.txt',
            file_path='disk/61/旧文件.txt',
            delete_time=None,
        )
        action = AIActionRequest(
            resource='disk',
            operation='update',
            object_ids=[61],
            context={'model': 'file'},
            changes={'name': '新文件'},
        )

        with patch.object(adapter, '_get_file_for_action', return_value=disk_file):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, is_superuser=True, has_perm=lambda code: True),
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['change_set'][0]['model_name'], 'DiskFile')
        self.assertEqual(result['change_set'][0]['before_snapshot']['name'], '旧文件.txt')
        self.assertEqual(result['change_set'][0]['after_snapshot']['name'], '新文件')

    def test_disk_file_preview_uses_owner_scoped_lookup(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.disk import DiskModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing disk adapter dependency: {exc}')

        adapter = DiskModuleAdapter()
        disk_file = SimpleNamespace(
            id=61,
            name='旧文件.txt',
            file_path='disk/61/旧文件.txt',
            delete_time=None,
        )
        action = AIActionRequest(
            resource='disk',
            operation='update',
            object_ids=[61],
            context={'model': 'file'},
            changes={'name': '新文件'},
        )
        user = SimpleNamespace(id=7, is_authenticated=True, is_superuser=False, has_perm=lambda code: True)

        with patch('apps.disk.models.DiskFile.objects.get', return_value=disk_file) as get_file:
            result = adapter.preview(action, user=user)

        self.assertTrue(result['success'])
        get_file.assert_called_once_with(id=61, owner=user, delete_time__isnull=True)

    def test_disk_folder_preview_uses_owner_scoped_lookup(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.disk import DiskModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing disk adapter dependency: {exc}')

        adapter = DiskModuleAdapter()
        disk_folder = SimpleNamespace(
            id=71,
            name='项目资料',
            delete_time=None,
        )
        action = AIActionRequest(
            resource='disk',
            operation='update',
            object_ids=[71],
            context={'model': 'folder'},
            changes={'name': '新资料'},
        )
        user = SimpleNamespace(id=7, is_authenticated=True, is_superuser=False, has_perm=lambda code: True)

        with patch('apps.disk.models.DiskFolder.objects.get', return_value=disk_folder) as get_folder:
            result = adapter.preview(action, user=user)

        self.assertTrue(result['success'])
        get_folder.assert_called_once_with(id=71, owner=user, delete_time__isnull=True)

    def test_disk_folder_delete_execute_soft_deletes_folder(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.disk import DiskModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing disk adapter dependency: {exc}')

        adapter = DiskModuleAdapter()
        disk_folder = SimpleNamespace(
            id=71,
            name='项目资料',
            delete_time=None,
            save=MagicMock(),
        )
        action = AIActionRequest(
            resource='disk',
            operation='delete',
            object_ids=[71],
            context={'model': 'folder'},
            changes={},
        )

        with patch.object(adapter, '_get_folder_for_action', return_value=disk_folder), \
                patch('apps.ai.services.module_adapters.disk.timezone.now', return_value='NOW'):
            result = adapter.execute(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, is_superuser=True, has_perm=lambda code: True),
                operation=None,
            )

        self.assertTrue(result['success'])
        self.assertEqual(disk_folder.delete_time, 'NOW')
        disk_folder.save.assert_called_once()

    def test_disk_file_permanent_delete_execute_backs_up_file(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.disk import DiskModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing disk adapter dependency: {exc}')

        import os
        import shutil
        import tempfile

        media_root = tempfile.mkdtemp(prefix='disk-ai-tests-')
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)

        relative_path = os.path.join('disk', '61', '旧文件.txt')
        absolute_path = os.path.join(media_root, relative_path)
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        with open(absolute_path, 'w', encoding='utf-8') as handle:
            handle.write('original content')

        adapter = DiskModuleAdapter()
        disk_file = SimpleNamespace(
            id=61,
            name='旧文件.txt',
            original_name='旧文件.txt',
            file_path=relative_path,
            file_size=16,
            file_ext='.txt',
            file_type='document',
            mime_type='text/plain',
            folder_id=None,
            owner_id=7,
            department_id=3,
            delete_time=None,
            save=MagicMock(),
            delete=MagicMock(),
        )
        action = AIActionRequest(
            resource='disk',
            operation='delete',
            object_ids=[61],
            context={'model': 'file'},
            changes={'permanent': True},
        )
        operation = SimpleNamespace(id=501)

        with patch('apps.ai.services.module_adapters.disk.settings.MEDIA_ROOT', media_root), \
                patch.object(adapter, '_get_file_for_action', return_value=disk_file), \
                patch('apps.ai.services.module_adapters.disk.timezone.now', return_value='NOW'):
            result = adapter.execute(action, user=SimpleNamespace(id=7, is_authenticated=True, is_superuser=True, has_perm=lambda code: True), operation=operation)

        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'deleted')
        self.assertTrue(result['change_set'][0]['rollback_metadata']['permanent'])
        self.assertIn('backup_file_path', result['change_set'][0]['rollback_metadata'])
        self.assertTrue(os.path.exists(result['change_set'][0]['rollback_metadata']['backup_file_path']))
        self.assertFalse(os.path.exists(absolute_path))
        disk_file.delete.assert_called_once()

    def test_disk_adapter_denies_when_permission_missing(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.disk import DiskModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing disk adapter dependency: {exc}')

        adapter = DiskModuleAdapter()
        disk_file = SimpleNamespace(id=81, name='文件.txt', delete_time=None)
        action = AIActionRequest(
            resource='disk',
            operation='update',
            object_ids=[81],
            context={'model': 'file'},
            changes={'name': '新文件'},
        )

        with patch.object(adapter, '_get_file_for_action', return_value=disk_file), \
                patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=False, reason='missing_permission')):
            result = adapter.preview(
                action,
                user=SimpleNamespace(id=7, is_authenticated=True, is_superuser=False, has_perm=lambda code: False),
            )

        self.assertFalse(result['success'])
        self.assertIn('权限', result['message'])

    def test_disk_share_create_preview_builds_share_change_set(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.disk import DiskModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing disk adapter dependency: {exc}')

        adapter = DiskModuleAdapter()
        disk_file = SimpleNamespace(id=91, name='方案说明.pdf', delete_time=None)
        share = SimpleNamespace(
            id=1001,
            share_code='ABCD1234',
            share_type='file',
            file=disk_file,
            folder=None,
            creator_id=7,
            password='',
            expire_time=None,
            permission_type='download',
            allow_download=True,
            allow_preview=True,
            allow_copy=True,
            allow_screenshot=True,
            access_limit=0,
            download_limit=0,
            is_active=True,
            save=MagicMock(),
            get_item=lambda: disk_file,
        )
        action = AIActionRequest(
            resource='disk',
            operation='create',
            object_ids=[91],
            context={'model': 'share', 'share_type': 'file'},
            changes={
                'permission_type': 'view',
                'allow_download': False,
                'allow_preview': True,
                'allow_copy': False,
                'allow_screenshot': False,
                'access_limit': 10,
            },
        )

        with patch('apps.ai.services.module_adapters.disk.DiskShare', SimpleNamespace()), \
                patch.object(adapter, '_get_share_item_for_action', return_value=disk_file), \
                patch.object(adapter.permission_guard, 'check_action_permission', return_value=SimpleNamespace(allowed=True, reason='allowed')):
            preview = adapter.preview(action, user=SimpleNamespace(id=7, is_authenticated=True, is_superuser=True, has_perm=lambda code: True))

        self.assertTrue(preview['success'])
        self.assertEqual(preview['change_set'][0]['model_name'], 'DiskShare')
        self.assertEqual(preview['change_set'][0]['after_snapshot']['permission_type'], 'view')

    def test_disk_permission_save_preview_tracks_public_flag(self):
        try:
            from apps.ai.services.action_contracts import AIActionRequest
            from apps.ai.services.module_adapters.disk import DiskModuleAdapter
        except ModuleNotFoundError as exc:
            self.fail(f'Missing disk adapter dependency: {exc}')

        adapter = DiskModuleAdapter()
        disk_folder = SimpleNamespace(id=92, name='制度', is_public=False, shared_users=SimpleNamespace(all=lambda: []), shared_departments=SimpleNamespace(all=lambda: []))
        action = AIActionRequest(
            resource='disk',
            operation='update',
            object_ids=[92],
            context={'model': 'permission'},
            changes={'is_public': True},
        )

        with patch.object(adapter, '_get_permission_target_for_action', return_value=disk_folder):
            preview = adapter.preview(action, user=SimpleNamespace(id=7, is_authenticated=True, is_superuser=True, has_perm=lambda code: True))

        self.assertTrue(preview['success'])
        self.assertEqual(preview['change_set'][0]['model_name'], 'DiskPermission')
        self.assertTrue(preview['change_set'][0]['after_snapshot']['is_public'])


class AIActionGatewayDiskDispatchTests(SimpleTestCase):
    def test_gateway_dispatches_disk_delete_to_registered_adapter(self):
        from apps.ai.services.action_gateway import AIActionGateway

        adapter = MagicMock()
        adapter.resource = 'disk'
        adapter.execute.return_value = {'success': True, 'message': 'disk updated'}
        operation = SimpleNamespace(
            id=24,
            resource_type='disk',
            operation_type='delete',
            confirmed_payload={
                'resource': 'disk',
                'operation': 'delete',
                'object_ids': [71],
                'context': {'model': 'folder'},
                'changes': {},
            },
        )
        user = SimpleNamespace(id=7, is_authenticated=True, is_superuser=True)

        gateway = AIActionGateway()
        gateway.register(adapter)

        result = gateway.execute_confirmed_action(operation, user)

        adapter.execute.assert_called_once()
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'disk updated')


class AIModelConfigCompatibilityTests(SimpleTestCase):
    def test_ai_client_uses_database_chat_config_by_default(self):
        from apps.ai.utils.ai_client import AIClient

        runtime_config = {
            'id': 21,
            'provider': 'openai',
            'api_key': 'database-key',
            'api_base': 'https://proxy.example.com/v1',
            'base_url': 'https://proxy.example.com/v1',
            'model_name': 'gpt-5.5',
            'chat': 'gpt-5.5',
            'updated_at': '2026-07-14T12:00:00+08:00',
        }

        with patch(
            'apps.ai.utils.ai_client.AIModelConfig.get_latest_chat_runtime_config',
            return_value=runtime_config,
        ), patch.object(AIClient, '_create_client', return_value=MagicMock()):
            client = AIClient()

        self.assertEqual(client.model_config, runtime_config)
        self.assertEqual(client.provider, 'openai')

    def test_database_managed_ai_client_refreshes_changed_chat_config(self):
        from apps.ai.utils.ai_client import AIClient

        initial_config = {
            'id': 21,
            'provider': 'openai',
            'api_key': 'old-key',
            'api_base': 'https://proxy.example.com/v1',
            'model_name': 'gpt-4o-mini',
            'chat': 'gpt-4o-mini',
            'updated_at': '2026-07-14T12:00:00+08:00',
        }
        refreshed_config = {
            **initial_config,
            'api_key': 'new-key',
            'model_name': 'gpt-5.5',
            'chat': 'gpt-5.5',
            'updated_at': '2026-07-14T12:05:00+08:00',
        }
        initial_client = MagicMock()
        initial_client.chat_completion.return_value = '旧配置响应'
        refreshed_client = MagicMock()
        refreshed_client.chat_completion.return_value = '新配置响应'

        with patch(
            'apps.ai.utils.ai_client.AIModelConfig.get_latest_chat_runtime_config',
            side_effect=[initial_config, refreshed_config],
        ), patch.object(
            AIClient,
            '_create_client',
            side_effect=[initial_client, refreshed_client],
        ):
            client = AIClient()
            result = client.chat_completion([{'role': 'user', 'content': '测试'}])

        self.assertEqual(result, '新配置响应')
        initial_client.chat_completion.assert_not_called()
        refreshed_client.chat_completion.assert_called_once()

    def test_model_config_form_normalizes_openai_compatible_root_url(self):
        from apps.ai.forms import AIModelConfigForm

        form = AIModelConfigForm(data={
            'name': 'Proxy Root',
            'api_base': 'https://www.aitokens.link',
            'api_key': 'sk-test',
            'model_names': 'gpt-5.5',
            'is_default': 'on',
            'is_active': 'on',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['api_base'], 'https://www.aitokens.link/v1')

    def test_simplified_model_runtime_config_uses_normalized_api_base(self):
        from apps.ai.models import AIModelConfig

        config = AIModelConfig(
            id=11,
            name='Proxy Root',
            api_base='https://www.aitokens.link',
            api_key='test-key',
            model_names=['gpt-5.5'],
            is_active=True,
        )

        runtime_config = config.to_runtime_config()

        self.assertEqual(runtime_config['api_base'], 'https://www.aitokens.link/v1')
        self.assertEqual(runtime_config['base_url'], 'https://www.aitokens.link/v1')

    def test_ai_client_uses_normalized_root_url_from_model_config(self):
        from apps.ai.models import AIModelConfig
        from apps.ai.utils.ai_client import AIClient

        config = AIModelConfig(
            id=1,
            name='Proxy Root',
            api_base='https://www.aitokens.link',
            api_key='test-key',
            model_names=['gpt-5.5'],
            is_active=True,
        )

        with patch(
            'apps.ai.utils.ai_client.AIModelConfig.get_latest_chat_runtime_config',
            return_value=None,
        ):
            client = AIClient(model_config_id=None)
        client.model_config = config
        client.client = client._create_client()

        self.assertEqual(client.client.base_url, 'https://www.aitokens.link/v1')

    def test_model_config_form_accepts_newline_separated_model_names(self):
        from apps.ai.forms import AIModelConfigForm

        form = AIModelConfigForm(data={
            'name': 'OpenAI Main',
            'api_base': 'https://api.openai.com/v1',
            'api_key': 'sk-test',
            'model_names': 'gpt-4o-mini\ngpt-4o\n\n',
            'is_default': 'on',
            'is_active': 'on',
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['model_names'], ['gpt-4o-mini', 'gpt-4o'])

    def test_simplified_model_exposes_legacy_ai_fields(self):
        from apps.ai.models import AIModelConfig

        config = AIModelConfig(
            name='gpt-4o-mini',
            api_base='https://api.openai.com/v1',
            api_key='test-key',
            model_names=['gpt-4o-mini'],
            is_active=True,
        )

        self.assertEqual(config.provider, 'openai')
        self.assertEqual(len(config.model_names) > 0, True)
        self.assertEqual(config.primary_model_name(), 'gpt-4o-mini')
        self.assertEqual(config.api_key, 'test-key')
        self.assertEqual(config.is_active, True)
        self.assertEqual(config.is_default, False)
        self.assertEqual(config.model_names, ['gpt-4o-mini'])
        self.assertEqual(True, True)
        self.assertEqual(config.is_active, True)

    def test_runtime_config_contains_derived_legacy_fields(self):
        from apps.ai.models import AIModelConfig

        config = AIModelConfig(
            id=9,
            name='deepseek-chat',
            api_base='https://api.deepseek.com/v1',
            api_key='test-key',
            model_names=['deepseek-chat'],
            is_active=True,
        )

        runtime_config = config.to_runtime_config()

        self.assertEqual(runtime_config['id'], 9)
        self.assertEqual(runtime_config['model_names'], ['deepseek-chat'])
        self.assertEqual(len(runtime_config['model_names']), 1)
        self.assertEqual(runtime_config['model_name'], 'deepseek-chat')
        self.assertEqual(runtime_config['chat'], 'deepseek-chat')
        self.assertEqual(runtime_config['api_base'], 'https://api.deepseek.com/v1')

    def test_ai_client_can_read_simplified_model_config(self):
        from apps.ai.models import AIModelConfig
        from apps.ai.utils.ai_client import AIClient

        config = AIModelConfig(
            id=1,
            name='gpt-4o-mini',
            api_base='https://api.openai.com/v1',
            api_key='test-key',
            model_names=['gpt-4o-mini'],
            is_active=True,
        )

        with patch('apps.ai.utils.ai_client.AIModelConfig.objects.get', return_value=config), \
                patch.object(AIClient, '_create_client', return_value=MagicMock()) as create_client:
            client = AIClient(model_config_id=1)

        self.assertEqual(client.provider, 'openai')
        create_client.assert_called_once()

    def test_intent_classifier_reads_simplified_active_runtime_config(self):
        from apps.ai.services.ai_intent_classifier import AIIntentClassifier

        expected_config = {
            'id': 1,
            'name': 'gpt-4o-mini',
            'provider': 'openai',
            'model_type': 'chat',
            'api_key': 'test-key',
            'api_base': 'https://api.openai.com/v1',
            'base_url': 'https://api.openai.com/v1',
            'model_name': 'gpt-4o-mini',
            'chat': 'gpt-4o-mini',
            'max_tokens': 2000,
            'temperature': 0.7,
            'top_p': 1.0,
            'is_active': True,
        }

        with patch('apps.ai.services.ai_intent_classifier.AIModelConfig.get_latest_chat_runtime_config', return_value=expected_config):
            result = AIIntentClassifier()._get_latest_chat_config()

        self.assertEqual(result, expected_config)


class AIDatabaseManagedServiceTests(SimpleTestCase):
    def test_rag_services_use_database_managed_clients(self):
        from apps.ai.services.rag_service import EnhancedRAGService, RAGService

        with patch('apps.ai.services.rag_service.AIClient', return_value=MagicMock()) as client_class:
            EnhancedRAGService()
            RAGService()

        self.assertEqual(client_class.call_count, 3)
        self.assertTrue(all(not item.args and not item.kwargs for item in client_class.call_args_list))

    def test_vector_generation_service_uses_database_managed_client(self):
        from apps.ai.services.vector_generation_service import VectorGenerationService

        with patch(
            'apps.ai.services.vector_generation_service.AIClient',
            return_value=MagicMock(),
        ) as client_class:
            VectorGenerationService()

        client_class.assert_called_once_with()

    def test_vector_quality_service_uses_database_managed_client(self):
        from apps.ai.services.vector_quality_service import VectorQualityService

        with patch(
            'apps.ai.services.vector_quality_service.AIClient',
            return_value=MagicMock(),
        ) as client_class:
            VectorQualityService()

        client_class.assert_called_once_with()


class AIModelConfigValidateViewTests(SimpleTestCase):
    def test_openai_client_falls_back_to_responses_endpoint_for_proxy_model_channel_error(self):
        from apps.ai.utils.ai_client import AIClientError, OpenAIClient

        client = OpenAIClient(
            base_url='https://proxy.example.com/v1',
            api_key='sk-test',
            model_config={'chat': 'gpt-5.5', 'model_name': 'gpt-5.5', 'max_tokens': 128},
        )

        def fake_request(method, url, **kwargs):
            if url.endswith('/chat/completions'):
                raise AIClientError(
                    'AI模型调用失败，请检查模型配置后重试',
                    error_code='http_error',
                    status_code=503,
                    detail='No available channel for model gpt-5.5 under group default',
                )
            self.assertTrue(url.endswith('/responses'))
            self.assertEqual(kwargs['json']['model'], 'gpt-5.5')
            return SimpleNamespace(json=lambda: {'output_text': '模型可用'})

        with patch.object(client, '_ensure_client', return_value=False), \
                patch.object(client, '_make_request', side_effect=fake_request):
            result = client.chat_completion([{'role': 'user', 'content': '你好'}])

        self.assertEqual(result, '模型可用')

    def test_validate_view_returns_http_status_details_for_ai_client_error(self):
        from apps.ai.views import AIModelConfigValidateView
        from apps.ai.utils.ai_client import AIClientError

        view = AIModelConfigValidateView()
        model_config = SimpleNamespace(
            id=1,
            provider='openai',
            api_base='https://www.aitokens.link/v1',
            model_name='gpt-5.4',
            model_type='chat',
            get_model_type_display=lambda: '对话模型',
            api_key='sk-test',
        )

        with patch.object(AIModelConfigValidateView, 'get_object', return_value=model_config), \
                patch('apps.ai.views.AIClient', side_effect=AIClientError(
                    'AI模型调用失败，请检查模型配置后重试',
                    error_code='http_error',
                    status_code=503,
                    detail='Service Unavailable',
                )):
            response = view.validate_connection()

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['status'], 'error')
        self.assertIn('503', payload['message'])
        self.assertEqual(payload['details']['status_code'], 503)
        self.assertEqual(payload['details']['error_code'], 'http_error')
        self.assertEqual(payload['details']['detail'], 'Service Unavailable')

    def test_validate_view_identifies_model_channel_error(self):
        from apps.ai.views import AIModelConfigValidateView
        from apps.ai.utils.ai_client import AIClientError

        view = AIModelConfigValidateView()
        model_config = SimpleNamespace(
            id=1,
            provider='openai',
            api_base='https://www.aitokens.link/v1',
            model_names=['gpt-5.5'],
            primary_model_name=lambda: 'gpt-5.5',
            api_key='sk-test',
        )

        error = AIClientError(
            'AI模型调用失败，请检查模型配置后重试',
            error_code='http_error',
            status_code=503,
            detail='{"error":{"code":"model_not_found","message":"No available channel for model gpt-5.5 under group default"}}',
        )

        payload = view._build_validation_error_payload(model_config, error)

        self.assertIn('模型', payload['message'])
        self.assertIn('渠道', payload['message'])
        self.assertIn('gpt-5.5', payload['details']['suggestion'])


class STTServiceSelectionTests(SimpleTestCase):
    @patch('apps.ai.utils.stt_service.STTServiceFactory.create_service')
    @patch('apps.ai.utils.stt_service.get_configured_stt_service')
    @patch('apps.ai.utils.stt_service.os.path.exists', return_value=True)
    def test_auto_uses_enabled_stt_service_configuration(self, exists, get_config, create_service):
        from apps.ai.utils.stt_service import transcribe_audio_file

        get_config.return_value = {
            'service_type': 'openai',
            'api_key': 'stt-key',
            'base_url': 'https://stt.example.com/v1',
            'model': 'whisper-large-v3',
        }
        service = MagicMock()
        service.transcribe_audio.return_value = '你好'
        create_service.return_value = service

        result = transcribe_audio_file('voice.webm', service_type='auto')

        self.assertEqual(result, '你好')
        create_service.assert_called_once_with(
            'openai',
            api_key='stt-key',
            base_url='https://stt.example.com/v1',
            model='whisper-large-v3',
        )

    @patch('apps.ai.utils.stt_service.STTServiceFactory.create_service')
    @patch('apps.ai.utils.stt_service.get_stt_config_from_db')
    @patch('apps.ai.utils.stt_service.get_configured_stt_service', return_value=None)
    @patch('apps.ai.utils.stt_service.os.path.exists', return_value=True)
    def test_auto_uses_audio_ai_model_before_free_fallback(self, exists, get_service_config, get_ai_config, create_service):
        from apps.ai.utils.stt_service import transcribe_audio_file

        get_ai_config.return_value = {
            'provider': 'openai',
            'api_key': 'ai-key',
            'base_url': 'https://api.example.com/v1',
            'model': 'whisper-1',
        }
        service = MagicMock()
        service.transcribe_audio.return_value = '语音文本'
        create_service.return_value = service

        result = transcribe_audio_file('voice.webm', service_type='auto')

        self.assertEqual(result, '语音文本')
        create_service.assert_called_once_with(
            'openai',
            provider='openai',
            api_key='ai-key',
            base_url='https://api.example.com/v1',
            model='whisper-1',
        )


class BusinessAIResultNormalizationTests(SimpleTestCase):
    def _normalizer(self):
        try:
            from apps.ai.services.business_result import normalize_business_ai_result
        except ModuleNotFoundError:
            self.fail('apps.ai.services.business_result.normalize_business_ai_result is missing')

        return normalize_business_ai_result

    def test_dict_result_is_normalized_to_stable_business_schema(self):
        normalize = self._normalizer()

        result = normalize(
            {
                '摘要': '该审批金额较高，需要补充发票和预算说明。',
                '风险等级': '高',
                '风险点': ['缺少发票', '超出常规预算'],
                '建议': '建议补充材料后再审批',
                '置信度': 1.4,
            },
            scenario='approval_assessment',
            source_refs=[{'type': 'approval', 'id': 12}],
        )

        self.assertEqual(result['summary'], '该审批金额较高，需要补充发票和预算说明。')
        self.assertEqual(result['risk_level'], 'high')
        self.assertEqual(result['risk_points'], ['缺少发票', '超出常规预算'])
        self.assertEqual(result['suggestions'], ['建议补充材料后再审批'])
        self.assertEqual(result['recommended_action'], 'request_more_info')
        self.assertEqual(result['confidence'], 1.0)
        self.assertTrue(result['requires_confirmation'])
        self.assertEqual(result['scenario'], 'approval_assessment')
        self.assertEqual(result['source_refs'], [{'type': 'approval', 'id': 12}])

    def test_string_result_becomes_summary_and_preserves_raw_result(self):
        normalize = self._normalizer()

        result = normalize('未发现明显风险，可以进入人工复核。')

        self.assertEqual(result['summary'], '未发现明显风险，可以进入人工复核。')
        self.assertEqual(result['risk_level'], 'unknown')
        self.assertEqual(result['risk_points'], [])
        self.assertEqual(result['suggestions'], [])
        self.assertEqual(result['recommended_action'], 'manual_review')
        self.assertEqual(result['confidence'], 0.0)
        self.assertFalse(result['requires_confirmation'])
        self.assertEqual(result['raw_result'], '未发现明显风险，可以进入人工复核。')

    def test_reject_like_action_requires_human_confirmation(self):
        normalize = self._normalizer()

        result = normalize({
            'summary': '发现重复报销嫌疑。',
            'risk_level': 'medium',
            'suggestions': ['建议拒绝本次报销'],
            'confidence': '0.72',
        })

        self.assertEqual(result['risk_level'], 'medium')
        self.assertEqual(result['recommended_action'], 'reject')
        self.assertEqual(result['confidence'], 0.72)
        self.assertTrue(result['requires_confirmation'])

    def test_build_business_ai_result_normalizes_and_records_audit(self):
        try:
            from apps.ai.services.business_result import build_business_ai_result
        except ImportError:
            self.fail('apps.ai.services.business_result.build_business_ai_result is missing')

        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True, id=7), META={})

        with patch('apps.ai.services.business_result.record_business_ai_result') as record:
            result = build_business_ai_result(
                {'analysis': '付款条件不明确。', 'risk_level': 'medium', 'confidence': 0.7},
                scenario='contract_risk_analysis',
                source_refs=[{'type': 'contract', 'id': 2}],
                request=request,
                raw_input={'content': '合同全文不应由调用方重复写日志'},
            )

        self.assertEqual(result['scenario'], 'contract_risk_analysis')
        self.assertEqual(result['summary'], '付款条件不明确。')
        self.assertEqual(result['risk_level'], 'medium')
        record.assert_called_once_with(
            request,
            result,
            raw_input={'content': '合同全文不应由调用方重复写日志'},
        )

    def test_normalized_result_includes_safe_feedback_context(self):
        normalize = self._normalizer()

        result = normalize(
            {
                'summary': '项目存在延期风险。',
                'risk_level': 'high',
                'raw_secret': '不应进入反馈上下文',
            },
            scenario='project_risk_prediction',
            source_refs=[{'type': 'project', 'id': 4}],
        )

        feedback_context = result.get('feedback_context')
        self.assertIsInstance(feedback_context, dict)
        self.assertEqual(feedback_context['endpoint'], '/ai/business-feedback/')
        self.assertEqual(feedback_context['payload']['task_id'], 'project_risk_prediction:project:4')
        self.assertEqual(feedback_context['payload']['task_type'], 'project_risk')
        self.assertEqual(feedback_context['payload']['scenario'], 'project_risk_prediction')
        self.assertEqual(feedback_context['payload']['summary'], '项目存在延期风险。')
        self.assertNotIn('raw_result', json.dumps(feedback_context, ensure_ascii=False))
        self.assertNotIn('不应进入反馈上下文', json.dumps(feedback_context, ensure_ascii=False))


class BusinessAIAuditTests(SimpleTestCase):
    def _recorder(self):
        try:
            from apps.ai.services.business_audit import record_business_ai_result
        except ModuleNotFoundError:
            self.fail('apps.ai.services.business_audit.record_business_ai_result is missing')

        return record_business_ai_result

    def test_record_business_ai_result_writes_compact_safe_log(self):
        record = self._recorder()
        user = MagicMock()
        user.is_authenticated = True
        user._meta = MagicMock()
        request = SimpleNamespace(
            user=user,
            META={'REMOTE_ADDR': '127.0.0.1'},
        )
        normalized_result = {
            'scenario': 'approval_assessment',
            'summary': '审批金额较高，需要补充发票和预算说明。',
            'risk_level': 'high',
            'risk_points': ['缺少发票'],
            'suggestions': ['建议补充材料后再审批'],
            'recommended_action': 'request_more_info',
            'confidence': 0.82,
            'source_refs': [{'type': 'approval', 'id': 12}],
            'requires_confirmation': True,
            'raw_result': {'full': '不应写入日志'},
        }

        with patch('apps.ai.services.business_audit.AILog.objects.create') as create_log:
            record(
                request,
                normalized_result,
                raw_input={'content': '不应写入日志的业务全文', 'amount': 5000},
            )

        create_log.assert_called_once()
        kwargs = create_log.call_args.kwargs
        self.assertEqual(kwargs['log_type'], 'model_call')
        self.assertEqual(kwargs['user'], request.user)
        self.assertEqual(kwargs['ip_address'], '127.0.0.1')

        content = kwargs['content']
        self.assertEqual(content['event'], 'business_ai_result')
        self.assertEqual(content['scenario'], 'approval_assessment')
        self.assertEqual(content['risk_level'], 'high')
        self.assertEqual(content['source_refs'], [{'type': 'approval', 'id': 12}])
        self.assertEqual(content['confidence'], 0.82)
        self.assertTrue(content['requires_confirmation'])
        self.assertNotIn('raw_result', content)
        self.assertNotIn('raw_input', content)
        self.assertNotIn('不应写入日志', json.dumps(content, ensure_ascii=False))

    def test_record_business_ai_result_handles_missing_request(self):
        record = self._recorder()
        normalized_result = {
            'scenario': 'meeting_summary',
            'summary': '会议明确下周上线计划。',
            'risk_level': 'low',
            'risk_points': [],
            'suggestions': [],
            'recommended_action': 'manual_review',
            'confidence': 0.6,
            'source_refs': [{'type': 'meeting', 'id': 6}],
            'requires_confirmation': False,
        }

        with patch('apps.ai.services.business_audit.AILog.objects.create') as create_log:
            record(None, normalized_result)

        create_log.assert_called_once()
        kwargs = create_log.call_args.kwargs
        self.assertIsNone(kwargs['user'])
        self.assertIsNone(kwargs['ip_address'])
        self.assertEqual(kwargs['content']['scenario'], 'meeting_summary')

    def test_record_business_ai_result_never_breaks_business_response(self):
        record = self._recorder()

        with patch(
            'apps.ai.services.business_audit.AILog.objects.create',
            side_effect=RuntimeError('database unavailable'),
        ):
            result = record(None, {'scenario': 'task_estimation'})

        self.assertIsNone(result)


class BusinessAIFeedbackTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = MagicMock()
        self.user.is_authenticated = True
        self.user._meta = MagicMock()

    def _recorder(self):
        try:
            from apps.ai.services.business_feedback import record_business_ai_feedback
        except ModuleNotFoundError:
            self.fail('apps.ai.services.business_feedback.record_business_ai_feedback is missing')

        return record_business_ai_feedback

    def test_record_business_ai_feedback_maps_scenario_to_existing_model(self):
        record = self._recorder()
        request = SimpleNamespace(user=self.user)
        payload = {
            'scenario': 'approval_assessment',
            'source_refs': [{'type': 'approval', 'id': 12}],
            'rating': 5,
            'comment': '建议清晰可用',
            'summary': '金额较高，需要补充发票。',
            'risk_level': 'high',
            'recommended_action': 'request_more_info',
            'raw_result': {'full': '不应写入反馈输出'},
        }

        with patch('apps.ai.services.business_feedback.AIFeedback.objects.create') as create_feedback:
            record(request, payload)

        create_feedback.assert_called_once()
        kwargs = create_feedback.call_args.kwargs
        self.assertEqual(kwargs['task_id'], 'approval_assessment:approval:12')
        self.assertEqual(kwargs['task_type'], 'expense_audit')
        self.assertEqual(kwargs['user'], self.user)
        self.assertEqual(kwargs['rating'], 5)
        self.assertEqual(kwargs['comment'], '建议清晰可用')
        self.assertIn('金额较高', kwargs['ai_output'])
        self.assertNotIn('不应写入反馈输出', kwargs['ai_output'])
        self.assertIn('approval_assessment', kwargs['input_content'])

    def test_record_business_ai_feedback_rejects_invalid_rating(self):
        record = self._recorder()

        with self.assertRaises(ValueError):
            record(None, {'scenario': 'task_estimation', 'rating': 6})

    def test_business_ai_feedback_api_returns_success_payload(self):
        try:
            from apps.ai.views import BusinessAIFeedbackAPIView
        except ImportError:
            self.fail('apps.ai.views.BusinessAIFeedbackAPIView is missing')

        request = self.factory.post(
            '/ai/business-feedback/',
            data=json.dumps({
                'scenario': 'project_risk_prediction',
                'source_refs': [{'type': 'project', 'id': 4}],
                'rating': 4,
                'comment': '有帮助',
                'summary': '存在延期风险。',
            }),
            content_type='application/json',
        )
        request.user = self.user

        with patch('apps.ai.services.business_feedback.AIFeedback.objects.create') as create_feedback:
            create_feedback.return_value.id = 99
            create_feedback.return_value.task_type = 'project_risk'
            response = BusinessAIFeedbackAPIView.as_view()(request)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['feedback_id'], 99)
        self.assertEqual(payload['data']['task_type'], 'project_risk')

    def test_record_business_ai_feedback_accepts_nested_feedback_context(self):
        record = self._recorder()
        request = SimpleNamespace(user=self.user)
        payload = {
            'feedback_context': {
                'endpoint': '/ai/business-feedback/',
                'payload': {
                    'task_id': 'project_risk_prediction:project:4',
                    'scenario': 'project_risk_prediction',
                    'source_refs': [{'type': 'project', 'id': 4}],
                    'summary': '项目存在延期风险。',
                    'risk_level': 'high',
                    'recommended_action': 'manual_review',
                    'confidence': 0.81,
                },
            },
            'rating': 4,
            'comment': '判断基本准确',
        }

        with patch('apps.ai.services.business_feedback.AIFeedback.objects.create') as create_feedback:
            record(request, payload)

        kwargs = create_feedback.call_args.kwargs
        self.assertEqual(kwargs['task_id'], 'project_risk_prediction:project:4')
        self.assertEqual(kwargs['task_type'], 'project_risk')
        self.assertIn('项目存在延期风险', kwargs['ai_output'])

    def test_business_ai_scenario_catalog_covers_current_business_scenarios(self):
        try:
            from apps.ai.services.business_scenarios import get_business_ai_task_type
        except ModuleNotFoundError:
            self.fail('apps.ai.services.business_scenarios.get_business_ai_task_type is missing')

        expected = {
            'approval_assessment': 'expense_audit',
            'expense_review': 'expense_audit',
            'expense_anomaly_detection': 'expense_audit',
            'customer_classification': 'customer_analysis',
            'customer_profile': 'customer_analysis',
            'meeting_summary': 'meeting_minutes',
            'meeting_action_items': 'meeting_minutes',
            'oa_meeting_minutes_generation': 'meeting_minutes',
            'oa_meeting_audio_minutes': 'meeting_minutes',
            'personal_meeting_minutes_generation': 'meeting_minutes',
            'project_risk_prediction': 'project_risk',
            'disk_file_analysis': 'document_summary',
            'contract_risk_analysis': 'text_generation',
            'contract_term_extraction': 'text_generation',
            'message_assistant': 'text_generation',
            'inventory_forecast': 'other',
            'production_optimization': 'other',
            'task_estimation': 'other',
        }

        for scenario, task_type in expected.items():
            self.assertEqual(get_business_ai_task_type(scenario), task_type)


class EnterpriseAgentRegistryTests(SimpleTestCase):
    def test_registry_exposes_phase_one_enterprise_agents_with_mixed_execution_modes(self):
        try:
            from apps.ai.services.enterprise_agents import enterprise_agent_service
        except ModuleNotFoundError:
            self.fail('apps.ai.services.enterprise_agents.enterprise_agent_service is missing')

        user = SimpleNamespace(id=7, is_superuser=True, is_authenticated=True)
        payload = enterprise_agent_service.get_center_payload(user)

        agent_ids = {agent['id'] for agent in payload['enterprise_agents']}
        self.assertTrue({
            'customer_followup_agent',
            'project_risk_agent',
            'production_dispatch_agent',
            'inventory_health_agent',
            'contract_review_agent',
            'finance_ops_agent',
            'approval_workbench_agent',
            'workforce_planning_agent',
            'meeting_coordination_agent',
            'admin_communication_agent',
            'personal_execution_agent',
            'order_fulfillment_agent',
            'document_flow_agent',
            'disk_collaboration_agent',
            'employee_masterdata_agent',
        }.issubset(agent_ids))

        self.assertGreaterEqual(payload['summary']['enterprise_agent_count'], 15)
        self.assertGreaterEqual(payload['summary']['module_count'], 9)
        self.assertGreater(payload['summary']['direct_action_count'], 0)
        self.assertGreater(payload['summary']['confirm_action_count'], 0)
        self.assertTrue(any(item['module'] == '财务管理' for item in payload['module_breakdown']))
        self.assertTrue(any(item['module'] == '企业网盘' for item in payload['module_breakdown']))

    def test_new_disk_collaboration_agent_exposes_analysis_and_execution_actions(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        user = SimpleNamespace(id=7, is_superuser=True, is_authenticated=True)
        detail = enterprise_agent_service.get_agent_detail('disk_collaboration_agent', user)
        action_ids = {action['id'] for action in detail['agent']['actions']}

        self.assertEqual(detail['agent']['module'], '企业网盘')
        self.assertTrue({
            'disk_asset_analysis',
            'rename_disk_file',
            'share_disk_file',
        }.issubset(action_ids))


class EnterpriseAgentExecutionServiceTests(SimpleTestCase):
    def test_analysis_action_returns_business_result_payload(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        user = SimpleNamespace(id=7, is_superuser=True, is_authenticated=True)
        mocked_result = {
            'scenario': 'customer_profile',
            'summary': '客户近期活跃度下降，建议安排重点回访。',
            'risk_level': 'medium',
            'suggestions': ['3 日内电话回访', '同步创建跟进任务'],
            'recommended_action': 'follow_up',
            'confidence': 0.83,
        }

        with patch.object(
            enterprise_agent_service,
            '_execute_customer_profile_analysis',
            return_value=mocked_result,
        ) as execute_analysis:
            result = enterprise_agent_service.execute(
                user=user,
                agent_id='customer_followup_agent',
                action_id='profile_analysis',
                params={'customer_id': 18},
            )

        execute_analysis.assert_called_once_with(user, {'customer_id': 18})
        self.assertTrue(result['success'])
        self.assertEqual(result['result_type'], 'business_result')
        self.assertEqual(result['data']['summary'], mocked_result['summary'])

    def test_direct_action_executes_gateway_and_persists_operation(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        user = SimpleNamespace(id=7, is_superuser=True, is_authenticated=True)
        operation = SimpleNamespace(id=201, status='preview', save=MagicMock())
        gateway_result = {
            'success': True,
            'message': 'created',
            'change_set': [
                {
                    'app_label': 'project',
                    'model_name': 'Task',
                    'object_pk': '88',
                    'change_type': 'create',
                    'before_snapshot': None,
                    'after_snapshot': {'title': '回访重点客户'},
                    'changed_fields': ['title'],
                }
            ],
        }

        with patch('apps.ai.services.enterprise_agents.AIOperation.objects.create', return_value=operation) as create_operation, \
                patch('apps.ai.services.enterprise_agents.AIOperationChangeSet.objects.create') as create_change_set, \
                patch('apps.ai.services.enterprise_agents.AIActionGateway') as gateway_cls, \
                patch('apps.ai.services.enterprise_agents.timezone.now', return_value='NOW'):
            gateway = gateway_cls.return_value
            gateway.get_adapter.return_value.execute.return_value = gateway_result

            result = enterprise_agent_service.execute(
                user=user,
                agent_id='customer_followup_agent',
                action_id='create_followup_task',
                params={
                    'title': '回访重点客户',
                    'assignee_id': 9,
                    'description': 'AI 自动生成的客户跟进任务',
                },
            )

        create_operation.assert_called_once()
        create_change_set.assert_called_once()
        self.assertTrue(result['success'])
        self.assertEqual(result['result_type'], 'operation')
        self.assertEqual(result['operation']['id'], 201)
        self.assertEqual(result['operation']['status'], 'executed')

    def test_confirm_action_creates_preview_operation_instead_of_direct_execution(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        user = SimpleNamespace(id=7, is_superuser=True, is_authenticated=True)
        preview_operation = SimpleNamespace(id=301, confirmation_token='token-301')
        preview_result = {
            'success': True,
            'change_set': [
                {
                    'app_label': 'finance',
                    'model_name': 'Payment',
                    'object_pk': 'NEW',
                    'change_type': 'create',
                    'before_snapshot': None,
                    'after_snapshot': {'amount': '5200.00'},
                    'changed_fields': ['amount'],
                }
            ],
        }

        with patch('apps.ai.services.enterprise_agents.AIActionGateway') as gateway_cls, \
                patch('apps.ai.services.enterprise_agents.operation_service.create_preview_operation', return_value=preview_operation) as create_preview:
            gateway = gateway_cls.return_value
            gateway.get_adapter.return_value.preview.return_value = preview_result

            result = enterprise_agent_service.execute(
                user=user,
                agent_id='finance_ops_agent',
                action_id='create_payment_record',
                params={
                    'amount': '5200.00',
                    'payment_date': '2026-07-08',
                    'remark': '供应商付款',
                },
            )

        create_preview.assert_called_once()
        self.assertTrue(result['success'])
        self.assertEqual(result['result_type'], 'confirmation_required')
        self.assertEqual(result['operation']['id'], 301)
        self.assertEqual(result['operation']['token'], 'token-301')
        self.assertEqual(result['preview_change_set'][0]['model_name'], 'Payment')


class EnterpriseAgentActionBuilderTests(SimpleTestCase):
    def test_build_action_create_document_request(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        action = enterprise_agent_service._get_action(
            enterprise_agent_service._get_agent('document_flow_agent'),
            'create_document',
        )
        request = enterprise_agent_service._build_action_create_document(
            'document_flow_agent',
            action,
            {
                'title': '关于上线安排的通知',
                'document_number': 'OA-2026-001',
                'category_id': '3',
                'content': '请各部门按计划完成上线准备。',
                'department_id': '2',
                'urgency': 'urgent',
            },
        )

        self.assertEqual(request.resource, 'document')
        self.assertEqual(request.operation, 'create')
        self.assertEqual(request.changes['title'], '关于上线安排的通知')
        self.assertEqual(request.changes['category_id'], '3')
        self.assertEqual(request.changes['urgency'], 'urgent')

    def test_build_action_publish_document_request(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        action = enterprise_agent_service._get_action(
            enterprise_agent_service._get_agent('document_flow_agent'),
            'publish_document',
        )
        request = enterprise_agent_service._build_action_publish_document(
            'document_flow_agent',
            action,
            {'document_id': '18'},
        )

        self.assertEqual(request.resource, 'document')
        self.assertEqual(request.operation, 'publish')
        self.assertEqual(request.object_ids, ['18'])

    def test_build_action_rename_disk_file_request(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        action = enterprise_agent_service._get_action(
            enterprise_agent_service._get_agent('disk_collaboration_agent'),
            'rename_disk_file',
        )
        request = enterprise_agent_service._build_action_rename_disk_file(
            'disk_collaboration_agent',
            action,
            {'file_id': '9', 'name': '客户报价单-最终版.pdf'},
        )

        self.assertEqual(request.resource, 'disk')
        self.assertEqual(request.operation, 'update')
        self.assertEqual(request.object_ids, ['9'])
        self.assertEqual(request.changes, {'name': '客户报价单-最终版.pdf'})
        self.assertEqual(request.context, {'model': 'file'})

    def test_build_action_share_disk_file_request(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        action = enterprise_agent_service._get_action(
            enterprise_agent_service._get_agent('disk_collaboration_agent'),
            'share_disk_file',
        )
        request = enterprise_agent_service._build_action_share_disk_file(
            'disk_collaboration_agent',
            action,
            {
                'file_id': '11',
                'permission_type': 'download',
                'allow_download': '1',
                'access_limit': '5',
                'password': 'ABCD',
            },
        )

        self.assertEqual(request.resource, 'disk')
        self.assertEqual(request.operation, 'create')
        self.assertEqual(request.object_ids, ['11'])
        self.assertTrue(request.changes['allow_download'])
        self.assertEqual(request.context, {'model': 'share', 'share_type': 'file'})

    def test_build_action_create_employee_request_includes_position_name(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        action = enterprise_agent_service._get_action(
            enterprise_agent_service._get_agent('employee_masterdata_agent'),
            'create_employee',
        )
        values_list_result = MagicMock()
        values_list_result.first.return_value = '实施顾问'
        filter_result = MagicMock()
        filter_result.values_list.return_value = values_list_result

        with patch('apps.ai.services.enterprise_agents.Position.objects.filter', return_value=filter_result):
            request = enterprise_agent_service._build_action_create_employee(
                'employee_masterdata_agent',
                action,
                {
                    'username': 'lihua',
                    'name': '李华',
                    'position_id': '6',
                    'did': '2',
                    'job_number': 'A106',
                },
            )

        self.assertEqual(request.resource, 'employee')
        self.assertEqual(request.operation, 'create')
        self.assertEqual(request.changes['position_name'], '实施顾问')
        self.assertEqual(request.changes['job_number'], 'A106')

    def test_build_action_adjust_employee_status_request(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        action = enterprise_agent_service._get_action(
            enterprise_agent_service._get_agent('employee_masterdata_agent'),
            'adjust_employee_status',
        )
        request = enterprise_agent_service._build_action_adjust_employee_status(
            'employee_masterdata_agent',
            action,
            {'employee_id': '23', 'status': '0', 'is_lock': '1'},
        )

        self.assertEqual(request.resource, 'employee')
        self.assertEqual(request.operation, 'update')
        self.assertEqual(request.object_ids, ['23'])
        self.assertEqual(request.changes, {'status': '0', 'is_lock': '1'})


class EnterpriseAgentAnalysisTests(SimpleTestCase):
    def test_document_flow_analysis_returns_business_result(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        user = SimpleNamespace(id=7, is_superuser=True, is_authenticated=True)
        queryset = MagicMock()
        queryset.order_by.return_value = queryset
        queryset.count.return_value = 12
        queryset.filter.side_effect = [
            MagicMock(count=MagicMock(return_value=4)),
            MagicMock(count=MagicMock(return_value=5)),
            MagicMock(count=MagicMock(return_value=2)),
        ]
        queryset.__getitem__.return_value = [
            SimpleNamespace(
                title='关于客户回访安排的通知',
                get_status_display=lambda: '审核中',
                get_urgency_display=lambda: '紧急',
            )
        ]

        with patch('apps.ai.services.enterprise_agents.Document.objects.select_related', return_value=queryset), \
                patch('apps.ai.services.enterprise_agents.build_business_ai_result', side_effect=lambda raw_result, **kwargs: {'raw_result': raw_result, **kwargs}):
            result = enterprise_agent_service._execute_document_flow_analysis(user, {})

        self.assertIn('待审核/流转 4 份', result['raw_result']['summary'])
        self.assertEqual(result['raw_result']['risk_level'], 'medium')
        self.assertEqual(result['scenario'], 'general')

    def test_disk_asset_analysis_returns_business_result(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        user = SimpleNamespace(id=7, is_superuser=True, is_authenticated=True)
        file_queryset = MagicMock()
        file_queryset.count.return_value = 30
        file_queryset.order_by.return_value.__getitem__.return_value = [
            SimpleNamespace(name='客户报价单.pdf', get_full_path=lambda: '销售资料/客户报价单.pdf')
        ]
        folder_queryset = MagicMock()
        folder_queryset.count.return_value = 8
        share_queryset = MagicMock()
        share_queryset.count.return_value = 6
        share_queryset.filter.return_value.count.return_value = 2

        with patch('apps.ai.services.enterprise_agents.DiskFile.objects.filter', return_value=file_queryset), \
                patch('apps.ai.services.enterprise_agents.DiskFolder.objects.filter', return_value=folder_queryset), \
                patch('apps.ai.services.enterprise_agents.DiskShare.objects.filter', return_value=share_queryset), \
                patch('apps.ai.services.enterprise_agents.build_business_ai_result', side_effect=lambda raw_result, **kwargs: {'raw_result': raw_result, **kwargs}):
            result = enterprise_agent_service._execute_disk_asset_analysis(user, {})

        self.assertIn('有效分享 6 条', result['raw_result']['summary'])
        self.assertEqual(result['raw_result']['risk_level'], 'medium')
        self.assertEqual(result['scenario'], 'general')

    def test_employee_masterdata_analysis_returns_business_result(self):
        from apps.ai.services.enterprise_agents import enterprise_agent_service

        user = SimpleNamespace(id=7, is_superuser=True, is_authenticated=True)
        queryset = MagicMock()
        queryset.count.return_value = 20
        queryset.filter.side_effect = [
            MagicMock(count=MagicMock(return_value=15)),
            MagicMock(count=MagicMock(return_value=2)),
            MagicMock(count=MagicMock(return_value=3)),
            MagicMock(count=MagicMock(return_value=1)),
        ]
        queryset.order_by.return_value.__getitem__.return_value = [
            SimpleNamespace(name='王敏', username='wangmin', position_name='')
        ]

        with patch('apps.ai.services.enterprise_agents.Admin.objects.filter', return_value=queryset), \
                patch('apps.ai.services.enterprise_agents.build_business_ai_result', side_effect=lambda raw_result, **kwargs: {'raw_result': raw_result, **kwargs}):
            result = enterprise_agent_service._execute_employee_masterdata_analysis(user, {})

        self.assertIn('在岗 15 人', result['raw_result']['summary'])
        self.assertEqual(result['raw_result']['risk_level'], 'medium')
        self.assertEqual(result['scenario'], 'general')


class AgentCenterApiViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_data_view_returns_enterprise_agent_payload(self):
        from apps.ai.views import AgentCenterDataView

        request = self.factory.get('/ai/agent-center/data/')
        request.user = SimpleNamespace(is_authenticated=True, id=7, is_superuser=True)

        mocked_payload = {
            'summary': {'enterprise_agent_count': 6},
            'enterprise_agents': [],
            'foundation_resources': [],
            'recent_operations': [],
        }

        with patch('apps.ai.views.enterprise_agent_service.get_center_payload', return_value=mocked_payload) as get_payload:
            response = AgentCenterDataView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        self.assertEqual(body['data']['summary']['enterprise_agent_count'], 6)
        get_payload.assert_called_once_with(request.user)

    def test_execute_view_dispatches_to_enterprise_agent_service(self):
        from apps.ai.views import AgentCenterExecuteView

        request = self.factory.post(
            '/ai/agent-center/execute/',
            data=json.dumps({
                'agent_id': 'customer_followup_agent',
                'action_id': 'create_followup_task',
                'params': {'title': '重点客户跟进'},
            }),
            content_type='application/json',
        )
        request.user = SimpleNamespace(is_authenticated=True, id=7, is_superuser=True)

        mocked_result = {
            'success': True,
            'result_type': 'operation',
            'operation': {'id': 201, 'status': 'executed'},
        }

        with patch('apps.ai.views.enterprise_agent_service.execute', return_value=mocked_result) as execute:
            response = AgentCenterExecuteView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        self.assertEqual(body['data']['operation']['id'], 201)
        execute.assert_called_once_with(
            user=request.user,
            agent_id='customer_followup_agent',
            action_id='create_followup_task',
            params={'title': '重点客户跟进'},
        )

    def test_rollback_view_dispatches_to_rollback_service(self):
        from apps.ai.views import AgentCenterRollbackView

        request = self.factory.post(
            '/ai/agent-center/rollback/',
            data=json.dumps({'operation_id': 88}),
            content_type='application/json',
        )
        request.user = SimpleNamespace(is_authenticated=True, id=7, is_superuser=True)

        with patch('apps.ai.views.rollback_service.rollback_operation', return_value={'success': True, 'operation_id': 88}) as rollback:
            response = AgentCenterRollbackView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['success'])
        self.assertEqual(body['data']['operation_id'], 88)
        rollback.assert_called_once_with(88, request.user)


class BusinessAIFrontendIntegrationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_root = Path(__file__).resolve().parents[2]

    def _read_project_file(self, relative_path):
        return (self.project_root / relative_path).read_text(encoding='utf-8')

    def test_ai_agent_sdk_exposes_business_result_renderer(self):
        content = self._read_project_file('static/js/ai-agent-sdk.js')

        for method_name in (
            'showBusinessAIResult',
            'mountBusinessAIResult',
            'renderBusinessAIResult',
            'bindBusinessAIResultFeedback',
            'submitBusinessAIFeedback',
        ):
            self.assertIn(method_name, content)

        self.assertIn('data-ai-feedback-rating', content)
        self.assertIn('requires_confirmation', content)

    def test_key_business_ai_templates_use_standard_renderer(self):
        expected_snippets = {
            'templates/production/plan/list.html': [
                "js/ai-agent-sdk.js",
                'showBusinessAIResult',
            ],
            'templates/project/ai_risk_prediction.html': [
                "js/ai-agent-sdk.js",
                '项目风险分析',
                '查看详情',
            ],
        }

        for relative_path, snippets in expected_snippets.items():
            content = self._read_project_file(relative_path)
            for snippet in snippets:
                self.assertIn(snippet, content)


class AgentCenterTemplateIntegrationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_root = Path(__file__).resolve().parents[2]

    def _read_project_file(self, relative_path):
        return (self.project_root / relative_path).read_text(encoding='utf-8')

    def test_agent_center_template_uses_real_workbench_hooks(self):
        content = self._read_project_file('templates/ai/agent_center.html')

        for snippet in (
            'agent-workbench-grid',
            'agent-detail-panel',
            '/ai/agent-center/data/',
            '/ai/agent-center/execute/',
            'AI 底层资源',
            'agentModuleFilters',
            'moduleBreakdownGrid',
            'agentSearchInput',
        ):
            self.assertIn(snippet, content)

    def test_agent_center_template_no_longer_contains_demo_only_copy(self):
        content = self._read_project_file('templates/ai/agent_center.html')
        self.assertNotIn('企业智能体演示版，功能开发中', content)


class AIAnalysisServiceTests(SimpleTestCase):
    def test_analyze_customer_uses_current_customer_fields_and_follow_records(self):
        from datetime import datetime
        from apps.ai.services.ai_analysis_service import AIAnalysisService

        follow_queryset = MagicMock()
        follow_queryset.order_by.return_value.__getitem__.return_value = [
            SimpleNamespace(
                follow_type='phone',
                content='客户关注预算和交付周期。',
                follow_time=datetime(2026, 6, 12, 9, 30),
                next_follow_time=None,
                follow_user=SimpleNamespace(username='sales'),
            )
        ]
        customer = SimpleNamespace(
            id=3,
            name='示例客户',
            customer_source_id=1,
            province='浙江',
            city='杭州',
            district='西湖区',
            create_time=datetime(2026, 6, 1, 8, 0),
            discard_time=0,
            belong_uid=7,
            principal=SimpleNamespace(username='负责人'),
            content='客户希望提升交付效率。',
            remark='重点客户',
            follow_records=MagicMock(),
        )
        customer.follow_records.filter.return_value = follow_queryset
        contact = SimpleNamespace(
            contact_person='张三',
            position='采购经理',
            phone='13800000000',
            email='zhang@example.com',
        )
        ai_client = MagicMock()
        ai_client.generate_content.return_value = '客户画像分析结果'

        with patch('apps.ai.services.ai_analysis_service.Customer.objects.get', return_value=customer), \
                patch('apps.ai.services.ai_analysis_service.Contact.objects.filter', return_value=[contact]), \
                patch('apps.ai.services.ai_analysis_service.AIClient', return_value=ai_client), \
                patch('apps.ai.services.ai_analysis_service.AITask.objects.create', return_value=SimpleNamespace(id=88)):
            result = AIAnalysisService.analyze_customer(SimpleNamespace(id=7), customer_id=3)

        self.assertTrue(result['success'])
        prompt = ai_client.generate_content.call_args.args[0]
        self.assertIn('示例客户', prompt)
        self.assertIn('张三', prompt)
        self.assertIn('客户关注预算和交付周期', prompt)
        self.assertEqual(result['task_id'], 88)

    def test_assess_project_risk_uses_current_project_and_task_fields(self):
        from datetime import date
        from apps.ai.services.ai_analysis_service import AIAnalysisService

        project = SimpleNamespace(
            id=4,
            name='交付项目',
            category=SimpleNamespace(name='实施交付'),
            manager=SimpleNamespace(username='pm'),
            start_date=date(2026, 6, 1),
            end_date=date(2026, 7, 1),
            status=2,
            status_display='进行中',
            description='核心客户交付',
            budget=100000,
            actual_cost=60000,
        )
        task = SimpleNamespace(
            title='接口联调',
            status=2,
            status_display='进行中',
            end_date=date(2026, 6, 20),
        )
        ai_client = MagicMock()
        ai_client.generate_content.return_value = '项目风险评估结果'

        with patch('apps.ai.services.ai_analysis_service.Project.objects.get', return_value=project), \
                patch('apps.ai.services.ai_analysis_service.Task.objects.filter', return_value=[task]), \
                patch('apps.ai.services.ai_analysis_service.AIClient', return_value=ai_client), \
                patch('apps.ai.services.ai_analysis_service.AITask.objects.create', return_value=SimpleNamespace(id=89)):
            result = AIAnalysisService.assess_project_risk(SimpleNamespace(id=7), project_id=4)

        self.assertTrue(result['success'])
        prompt = ai_client.generate_content.call_args.args[0]
        self.assertIn('交付项目', prompt)
        self.assertIn('实际成本：60000', prompt)
        self.assertIn('接口联调', prompt)
        self.assertEqual(result['task_id'], 89)


class AIAnalysisToolCallTests(SimpleTestCase):
    def test_analysis_tool_uses_database_managed_ai_client(self):
        from apps.ai.utils.analysis_tools import AIAnalysisTool

        with patch('apps.ai.utils.analysis_tools.AIClient', return_value=MagicMock()) as client_class:
            AIAnalysisTool()

        client_class.assert_called_once_with()

    def test_call_ai_parses_json_response_from_client(self):
        from apps.ai.utils.analysis_tools import AIAnalysisTool

        class FakeAIClient:
            provider = 'fake'

            def chat_completion(self, **kwargs):
                return '{"summary": "付款条件不明确", "risk_level": "medium"}'

        tool = AIAnalysisTool.__new__(AIAnalysisTool)
        tool.ai_client = FakeAIClient()

        result = tool._call_ai('请分析合同')

        self.assertEqual(result['summary'], '付款条件不明确')
        self.assertEqual(result['risk_level'], 'medium')

    def test_call_ai_returns_safe_error_payload_when_client_fails(self):
        from apps.ai.utils.analysis_tools import AIAnalysisTool

        class FailingAIClient:
            provider = 'fake'

            def chat_completion(self, **kwargs):
                raise RuntimeError('provider unavailable')

        tool = AIAnalysisTool.__new__(AIAnalysisTool)
        tool.ai_client = FailingAIClient()

        result = tool._call_ai('请分析审批')

        self.assertEqual(result['confidence'], 0)
        self.assertIn('error', result)
        self.assertIn('稍后重试', result['analysis'])


class BusinessAIEndpointResponseTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True, id=7, is_superuser=True, did=None)

    def _assert_business_result_contract(self, data, scenario):
        self.assertEqual(data['scenario'], scenario)
        for key in (
            'summary',
            'risk_level',
            'risk_points',
            'suggestions',
            'recommended_action',
            'confidence',
            'source_refs',
            'requires_confirmation',
            'raw_result',
            'feedback_context',
        ):
            self.assertIn(key, data)

        feedback_context = data['feedback_context']
        self.assertEqual(feedback_context['endpoint'], '/ai/business-feedback/')
        self.assertEqual(feedback_context['payload']['scenario'], scenario)
        self.assertIn('task_type', feedback_context['payload'])
        self.assertEqual(feedback_context['payload']['source_refs'], data['source_refs'])
        self.assertEqual(feedback_context['payload']['summary'], data['summary'])
        self.assertIn(':', feedback_context['payload']['task_id'])
        self.assertNotIn('raw_result', json.dumps(feedback_context, ensure_ascii=False))

    def test_approval_assessment_returns_normalized_business_result(self):
        from apps.approval.ai_views import ai_approval_assessment

        request = self.factory.get('/approval/1/ai/')
        request.user = self.user
        approval = SimpleNamespace(
            id=1,
            type_id=3,
            content='采购办公设备',
            amount=5000,
            flow=SimpleNamespace(approval_type=SimpleNamespace(name='采购审批')),
        )
        history_queryset = MagicMock()
        history_queryset.exclude.return_value.__getitem__.return_value = [
            SimpleNamespace(content='历史采购', amount=3000)
        ]

        with patch('apps.approval.ai_views.Approval.objects') as approval_objects, \
                patch('apps.approval.ai_views.default_approval_analysis_tool.assess_approval') as assess:
            approval_objects.select_related.return_value.get.return_value = approval
            approval_objects.filter.return_value = history_queryset
            assess.return_value = {
                '摘要': '金额高于历史采购',
                '风险等级': '高',
                '风险点': ['金额偏高'],
                '审批建议': '建议补充材料',
                '置信度': 0.8,
            }

            response = ai_approval_assessment(request, approval_id=1)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'approval_assessment')
        self.assertEqual(payload['data']['risk_level'], 'high')
        self.assertEqual(payload['data']['recommended_action'], 'request_more_info')

    def test_expense_review_returns_normalized_business_result(self):
        from apps.finance.ai_views import AIExpenseReviewView

        request = self.factory.post(
            '/finance/expense/ai/',
            data=json.dumps({'expense_id': 9, 'comment': '请重点检查票据'}),
            content_type='application/json',
        )
        request.user = self.user
        expense = SimpleNamespace(
            id=9,
            code='BX-9',
            cost=1200,
            income_month='2026-06',
            expense_time='2026-06-12',
            subject_id=2,
            remark='客户拜访餐费',
            file_ids='1,2',
            admin_id=7,
            check_status=0,
            pay_status=0,
            check_uids='',
            check_history_uids='',
            check_copy_uids='',
            create_time='2026-06-13',
        )

        with patch('apps.finance.ai_views.get_object_or_404', return_value=expense), \
                patch('apps.finance.ai_views.default_expense_analysis_tool.analyze_expense') as analyze:
            analyze.return_value = {
                'analysis': '餐费金额正常，建议人工复核发票。',
                'risk_level': 'low',
                'confidence': 0.66,
            }

            response = AIExpenseReviewView.as_view()(request)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'expense_review')
        self.assertEqual(payload['data']['summary'], '餐费金额正常，建议人工复核发票。')
        self.assertEqual(payload['data']['risk_level'], 'low')

    def test_contract_risk_analysis_returns_normalized_business_result(self):
        from apps.contract.ai_views import ai_contract_risk_analysis

        request = self.factory.get('/contract/2/ai/')
        request.user = self.user
        contract = SimpleNamespace(
            id=2,
            name='采购合同',
            amount=30000,
            content='付款条件不明确',
            remark='',
        )

        with patch('apps.contract.ai_views.Contract.objects.get', return_value=contract), \
                patch('apps.contract.ai_views.default_contract_analysis_tool.analyze_risk') as analyze:
            analyze.return_value = {
                'summary': '付款条件不明确。',
                'risk_level': 'medium',
                'risk_points': ['付款节点缺失'],
                'suggestions': ['补充付款节点'],
                'confidence': 0.75,
            }

            response = ai_contract_risk_analysis(request, contract_id=2)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'contract_risk_analysis')
        self.assertEqual(payload['data']['risk_points'], ['付款节点缺失'])
        self.assertEqual(payload['data']['recommended_action'], 'request_more_info')

    def test_customer_profile_returns_normalized_business_result(self):
        from apps.customer.ai_views import ai_customer_profile

        request = self.factory.get('/customer/3/ai-profile/')
        request.user = self.user
        customer = SimpleNamespace(
            id=3,
            name='示例客户',
            customer_source_id=1,
            grade_id=2,
            industry_id=4,
            province='浙江',
            city='杭州',
            discard_time=0,
            intent_status=1,
            address='西湖区',
            create_time=None,
        )
        contact = SimpleNamespace(
            contact_person='张三',
            phone='13800000000',
            email='zhang@example.com',
            position='采购经理',
            is_primary=True,
        )
        follow_record = SimpleNamespace(
            follow_type='call',
            follow_content='客户关注交付周期',
            follow_time=None,
            next_follow_time=None,
            follow_user=SimpleNamespace(username='sales'),
        )
        follow_queryset = MagicMock()
        follow_queryset.order_by.return_value.__getitem__.return_value = [follow_record]

        with patch('apps.customer.ai_views.Customer.objects.get', return_value=customer), \
                patch('apps.customer.ai_views.Contact.objects.filter', return_value=[contact]), \
                patch('apps.customer.ai_views.FollowRecord.objects.filter', return_value=follow_queryset), \
                patch('apps.customer.ai_views.default_customer_analysis_tool.generate_customer_profile') as profile:
            profile.return_value = {
                'analysis': '客户重视交付周期，建议安排技术沟通。',
                'risk_level': 'medium',
                'suggestions': ['安排技术预沟通'],
                'confidence': 0.71,
            }

            response = ai_customer_profile(request, customer_id=3)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'customer_profile')
        self.assertEqual(payload['data']['summary'], '客户重视交付周期，建议安排技术沟通。')
        self.assertEqual(payload['data']['risk_level'], 'medium')

    def test_project_risk_prediction_returns_normalized_business_result(self):
        from apps.project.ai_views import ai_project_risk_prediction

        request = self.factory.get('/project/4/ai-risk/')
        request.user = self.user
        project = SimpleNamespace(
            id=4,
            name='交付项目',
            status=2,
            priority=3,
            progress=45,
            start_date=None,
            end_date=None,
            budget=100000,
            actual_cost=60000,
            category_id=1,
            manager_id=7,
            description='核心客户交付',
        )
        analysis = SimpleNamespace(id=18)
        serialized_payload = {
            'analysis_id': 18,
            'project_id': 4,
            'project_name': '交付项目',
            'scenario': 'project_risk_prediction',
            'source_refs': [{'type': 'project', 'id': 4}],
            'risk_level': 'high',
            'risk_level_display': '高风险',
            'risk_score': 82,
            'warning_count': 1,
            'summary': '进度存在延期风险，需要聚焦接口联调。',
            'risk_points': ['接口联调未完成'],
            'suggestions': ['优先推进接口联调'],
            'recommended_action': 'manual_review',
            'recommended_action_display': '人工重点复核',
            'confidence': 0.83,
            'metrics': {'progress': 45},
            'trigger_source': 'manual',
            'trigger_source_display': '手动触发',
            'analyzed_at': '2026-07-09 10:00',
            'requires_confirmation': True,
            'raw_result': {
                'risk_level': 'high',
                'risk_points': ['接口联调未完成'],
            },
            'feedback_context': {
                'endpoint': '/ai/business-feedback/',
                'payload': {
                    'scenario': 'project_risk_prediction',
                    'source_refs': [{'type': 'project', 'id': 4}],
                    'summary': '进度存在延期风险，需要聚焦接口联调。',
                    'task_type': 'project_risk_analysis',
                    'task_id': 'project_risk_prediction:4',
                },
            },
        }

        with patch('apps.project.ai_views.Project.objects.get', return_value=project), \
                patch('apps.project.ai_views.project_risk_analysis_service.analyze_project', return_value=analysis) as analyze_project, \
                patch('apps.project.ai_views.serialize_risk_analysis', return_value=serialized_payload) as serialize:
            response = ai_project_risk_prediction(request, project_id=4)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'project_risk_prediction')
        self.assertEqual(payload['data']['risk_level'], 'high')
        self.assertTrue(payload['data']['requires_confirmation'])
        analyze_project.assert_called_once_with(
            project,
            trigger_source='manual',
            triggered_by=request.user,
        )
        serialize.assert_called_once_with(analysis)

    def test_inventory_forecast_returns_normalized_business_result(self):
        from datetime import datetime
        from apps.inventory.ai_views import ai_inventory_forecast

        request = self.factory.get('/inventory/5/ai-forecast/')
        request.user = self.user
        item = SimpleNamespace(
            id=50,
            name='标准件A',
            min_stock=100,
            category=SimpleNamespace(name='标准件'),
        )
        inventory = SimpleNamespace(
            id=5,
            item=item,
            warehouse=SimpleNamespace(id=6),
            quantity=80,
        )
        transaction = SimpleNamespace(
            transaction_type='out',
            quantity=30,
            create_time=datetime(2026, 6, 12),
        )
        record_queryset = MagicMock()
        record_queryset.order_by.return_value.__getitem__.return_value = [transaction]

        with patch('apps.inventory.ai_views.Inventory.objects') as inventory_objects, \
                patch('apps.inventory.ai_views.StockTransaction.objects.filter', return_value=record_queryset), \
                patch('apps.inventory.ai_views.default_inventory_analysis_tool.forecast_demand') as forecast:
            inventory_objects.select_related.return_value.get.return_value = inventory
            forecast.return_value = {
                'summary': '库存低于预警值，建议补货。',
                'risk_level': 'high',
                'suggestions': ['建议采购 120 件'],
                'confidence': 0.78,
            }

            response = ai_inventory_forecast(request, inventory_id=5)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'inventory_forecast')
        self.assertEqual(payload['data']['risk_level'], 'high')

    def test_meeting_summary_returns_normalized_business_result(self):
        from apps.oa.ai_views import ai_meeting_summary

        request = self.factory.get('/oa/meeting/6/ai-summary/')
        request.user = self.user
        meeting = SimpleNamespace(
            id=6,
            title='项目例会',
            meeting_date=None,
            host_id=7,
            host=SimpleNamespace(username='host'),
            recorder_id=8,
            recorder=SimpleNamespace(username='recorder'),
            room=SimpleNamespace(name='一号会议室'),
            content='讨论接口联调、上线排期和风险处理。',
            resolution='',
            participants=SimpleNamespace(all=lambda: [SimpleNamespace(username='成员A')]),
            department=SimpleNamespace(name='研发部'),
            created_at=None,
            save=MagicMock(),
        )

        with patch('apps.oa.ai_views.MeetingRecord.objects.get', return_value=meeting), \
                patch('apps.oa.ai_views.default_meeting_analysis_tool.generate_meeting_summary') as summarize:
            summarize.return_value = {
                'analysis': '会议明确接口联调为本周重点。',
                'resolutions': '本周完成接口联调',
                'confidence': 0.8,
            }

            response = ai_meeting_summary(request, meeting_id=6)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'meeting_summary')
        self.assertEqual(payload['data']['summary'], '会议明确接口联调为本周重点。')

    def test_message_ai_assistant_returns_normalized_business_result(self):
        from apps.message.ai_views import MessageAIAssistantView

        request = self.factory.post('/message/7/ai/', data={})
        request.user = self.user
        relations = MagicMock()
        relations.filter.return_value.exists.return_value = False
        message = SimpleNamespace(
            id=7,
            sender=self.user,
            user_relations=relations,
            title='上线安排',
            content='请大家关注本周上线安排，完成接口联调、回归测试、发布审批和客户通知等事项。'
                    '请各负责人在今天下班前同步风险、剩余问题和需要协调的资源。',
            ai_summary='',
            ai_suggested_replies=[],
            save=MagicMock(),
        )
        ai_client = MagicMock()
        ai_client.generate.return_value = '摘要：本周上线需完成联调和审批\n回复建议：["收到", "我会按时处理"]'

        with patch('apps.message.ai_views.Message.objects.get', return_value=message), \
                patch('apps.message.ai_views.AIClient', return_value=ai_client):
            response = MessageAIAssistantView.as_view()(request, message_id=7)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'message_assistant')
        self.assertEqual(payload['data']['summary'], '本周上线需完成联调和审批')

    def test_disk_file_ai_assistant_returns_normalized_business_result(self):
        from apps.disk.ai_views import FileAIAssistantView

        request = self.factory.post('/disk/file/8/ai/', data={})
        request.user = self.user
        disk_file = SimpleNamespace(
            id=8,
            owner=self.user,
            ai_status=0,
            ai_summary='',
            ai_tags='',
            ai_content_text='',
            file_ext='.txt',
            file=SimpleNamespace(path='dummy.txt'),
            save=MagicMock(),
        )
        ai_client = MagicMock()
        ai_client.generate.return_value = '摘要：这是一份项目上线说明。\n标签：项目,上线,说明'

        with patch('apps.disk.ai_views.DiskFile.objects.get', return_value=disk_file), \
                patch('apps.disk.ai_views.FileAIAssistantView.extract_text', return_value='项目上线说明内容'), \
                patch('apps.disk.ai_views.AIClient', return_value=ai_client):
            response = FileAIAssistantView.as_view()(request, file_id=8)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'disk_file_analysis')
        self.assertEqual(payload['data']['summary'], '这是一份项目上线说明。')

    def test_production_optimization_returns_normalized_business_result(self):
        from apps.production.ai_views import ai_production_optimization

        request = self.factory.get('/production/plan/9/ai/')
        request.user = self.user
        plan = SimpleNamespace(id=9, name='六月生产计划', plan_start_date=None, plan_end_date=None)
        task = SimpleNamespace(name='装配任务', status=1)

        with patch('apps.production.ai_views.ProductionPlan.objects.get', return_value=plan), \
                patch('apps.production.ai_views.ProductionTask.objects.filter', return_value=[task]), \
                patch('apps.production.ai_views.default_production_analysis_tool.optimize_plan') as optimize:
            optimize.return_value = {
                'analysis': '装配任务存在产能瓶颈。',
                'risk_level': 'medium',
                'suggestions': ['调整任务顺序'],
                'confidence': 0.7,
            }

            response = ai_production_optimization(request, plan_id=9)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'production_optimization')
        self.assertEqual(payload['data']['risk_level'], 'medium')

    def test_task_estimation_returns_normalized_business_result(self):
        from apps.task.ai_views import ai_task_estimation

        request = self.factory.get('/task/10/ai/')
        request.user = self.user
        assignee = SimpleNamespace(username='dev', department=SimpleNamespace(name='研发部'))
        task = SimpleNamespace(
            id=10,
            name='实现AI助手',
            description='统一业务AI返回结构',
            status=1,
            priority=3,
            assignee=assignee,
        )

        with patch('apps.task.ai_views.Task.objects.get', return_value=task), \
                patch('apps.task.ai_views.default_task_analysis_tool.estimate_task') as estimate:
            estimate.return_value = {
                'summary': '预计需要 6 小时完成。',
                'risk_level': 'low',
                'confidence': 0.74,
            }

            response = ai_task_estimation(request, task_id=10)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'task_estimation')
        self.assertEqual(payload['data']['summary'], '预计需要 6 小时完成。')



