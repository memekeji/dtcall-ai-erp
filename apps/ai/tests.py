import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.apps import apps
from django.test import RequestFactory, SimpleTestCase


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
            'project_progress_analysis': 'project_risk',
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
                'mountBusinessAIResult',
                'raw_result',
            ],
            'templates/project/ai_progress_analysis.html': [
                "js/ai-agent-sdk.js",
                'mountBusinessAIResult',
                'raw_result',
            ],
        }

        for relative_path, snippets in expected_snippets.items():
            content = self._read_project_file(relative_path)
            for snippet in snippets:
                self.assertIn(snippet, content)


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
        task = SimpleNamespace(
            id=40,
            title='接口联调',
            status=2,
            priority=3,
            start_date=None,
            end_date=None,
            assignee_id=8,
            estimated_hours=16,
        )
        task_queryset = MagicMock()
        task_queryset.__iter__.return_value = iter([task])
        task_queryset.aggregate.return_value = {
            'total_tasks': 1,
            'completed_tasks': 0,
            'in_progress_tasks': 1,
            'pending_tasks': 0,
        }
        work_hour_queryset = MagicMock()
        work_hour_queryset.aggregate.return_value = {'total': 20}

        with patch('apps.project.ai_views.Project.objects.get', return_value=project), \
                patch('apps.project.ai_views.Task.objects.filter', return_value=task_queryset), \
                patch('apps.project.ai_views.WorkHour.objects.filter', return_value=work_hour_queryset), \
                patch('apps.project.ai_views.default_project_analysis_tool.predict_project_risk') as predict:
            predict.return_value = {
                'analysis': '进度存在延期风险，需要聚焦接口联调。',
                'risk_level': 'high',
                'risk_points': ['接口联调未完成'],
                'confidence': 0.83,
            }

            response = ai_project_risk_prediction(request, project_id=4)

        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self._assert_business_result_contract(payload['data'], 'project_risk_prediction')
        self.assertEqual(payload['data']['risk_level'], 'high')
        self.assertTrue(payload['data']['requires_confirmation'])

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
