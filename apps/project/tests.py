from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.core.management import call_command
from django.test import TestCase, override_settings
from datetime import date, datetime
from decimal import Decimal
from django.urls import reverse
from unittest.mock import patch

from apps.contract.models import ContractCate, Purchase
from apps.customer.models import Customer, CustomerContract, CustomerOrder
from apps.message.models import MessageUserRelation
from apps.message.services import MessageService
from apps.project.models import Comment, Project, ProjectRiskAnalysis, Task
from apps.user.models import Admin


TEST_MIDDLEWARE = [
    middleware for middleware in settings.MIDDLEWARE
    if middleware not in {
        'apps.system.middleware.permission_middleware.PermissionMiddleware',
        'apps.system.middleware.database_setup_middleware.DatabaseSetupMiddleware',
    }
]


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class ProjectAutoCreateOptionTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username='project-auto-create-user',
            email='project-auto-create@example.com',
            password='password123',
            name='项目自动创建测试员',
        )
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            name='项目关联客户',
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )

    def test_project_create_form_renders_auto_create_options(self):
        response = self.client.get(
            reverse('project:project_add'),
            {'customer_id': self.customer.id},
        )
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('自动创建关联信息', content)
        self.assertIn('auto_create_contract', content)
        self.assertIn('auto_create_order', content)

    def test_project_create_does_not_auto_create_related_records_by_default(self):
        response = self.client.post(
            reverse('project:project_add'),
            {
                'name': '默认不联动项目',
                'code': 'PRJ-DEFAULT-001',
                'description': '',
                'category_id': '',
                'manager_id': str(self.user.id),
                'start_date': '2026-07-02',
                'end_date': '2026-07-31',
                'budget': '5200.00',
                'priority': '2',
                'customer_id': str(self.customer.id),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        project = Project.objects.get(code='PRJ-DEFAULT-001')
        self.assertIsNone(project.contract)
        self.assertEqual(CustomerContract.objects.filter(customer=self.customer, auto_generated=True).count(), 0)
        self.assertEqual(CustomerOrder.objects.filter(customer=self.customer, auto_generated=True).count(), 0)

    def test_project_create_only_generates_checked_related_records(self):
        response = self.client.post(
            reverse('project:project_add'),
            {
                'name': '按需联动项目',
                'code': 'PRJ-SELECT-001',
                'description': '',
                'category_id': '',
                'manager_id': str(self.user.id),
                'start_date': '2026-07-02',
                'end_date': '2026-07-31',
                'budget': '8800.00',
                'priority': '3',
                'customer_id': str(self.customer.id),
                'auto_create_contract': 'on',
                'auto_create_order': 'on',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        project = Project.objects.get(code='PRJ-SELECT-001')
        self.assertIsNotNone(project.contract)
        self.assertEqual(CustomerContract.objects.filter(customer=self.customer, auto_generated=True).count(), 1)
        self.assertEqual(CustomerOrder.objects.filter(customer=self.customer, auto_generated=True).count(), 1)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class ProjectPurchaseIntegrationTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username='project_manager',
            password='secret123',
            email='pm@example.com',
            thumb='',
            name='项目经理',
        )
        self.client.force_login(self.user)

    def _create_project(self, **kwargs):
        defaults = {
            'name': '智慧园区项目',
            'code': 'PRJ-001',
            'creator': self.user,
            'manager': self.user,
            'budget': Decimal('100000.00'),
            'actual_cost': Decimal('0'),
        }
        defaults.update(kwargs)
        return Project.objects.create(**defaults)

    def _create_purchase_category(self):
        return ContractCate.objects.create(title='设备采购')

    def test_purchase_model_has_project_relation(self):
        try:
            field = Purchase._meta.get_field('project')
        except FieldDoesNotExist as exc:
            self.fail(f'Purchase model should relate to Project: {exc}')

        self.assertEqual(field.related_model, Project)

    def test_project_detail_shows_purchase_summary_and_records(self):
        try:
            Purchase._meta.get_field('project')
        except FieldDoesNotExist as exc:
            self.fail(f'Purchase model should relate to Project before rendering details: {exc}')

        project = self._create_project()
        category = self._create_purchase_category()
        Purchase.objects.create(
            name='核心交换机采购',
            code='PO-001',
            cate=category,
            project=project,
            amount=Decimal('20000.00'),
            sign_time=date(2026, 7, 1),
            start_time=date(2026, 7, 1),
            end_time=date(2026, 7, 31),
            admin=self.user,
            sign_uid=self.user,
            prepared_uid=self.user,
            keeper_uid=self.user,
        )
        Purchase.objects.create(
            name='机柜与辅材采购',
            code='PO-002',
            cate=category,
            project=project,
            amount=Decimal('15000.00'),
            sign_time=date(2026, 7, 2),
            start_time=date(2026, 7, 2),
            end_time=date(2026, 8, 1),
            admin=self.user,
            sign_uid=self.user,
            prepared_uid=self.user,
            keeper_uid=self.user,
        )

        response = self.client.get(
            reverse('project:project_detail', kwargs={'project_id': project.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '采购记录')
        self.assertContains(response, '采购总成本')
        self.assertContains(response, '核心交换机采购')
        self.assertContains(response, '机柜与辅材采购')
        self.assertContains(response, '¥35000.00')

    def test_purchase_datalist_includes_project_name_and_supports_project_filter(self):
        try:
            Purchase._meta.get_field('project')
        except FieldDoesNotExist as exc:
            self.fail(f'Purchase model should relate to Project before listing purchases: {exc}')

        project = self._create_project(name='A项目', code='PRJ-A')
        other_project = self._create_project(name='B项目', code='PRJ-B')
        category = self._create_purchase_category()

        Purchase.objects.create(
            name='A项目采购',
            code='PO-A',
            cate=category,
            project=project,
            amount=Decimal('1200.00'),
            sign_time=date(2026, 7, 1),
            start_time=date(2026, 7, 1),
            end_time=date(2026, 7, 10),
            admin=self.user,
            sign_uid=self.user,
            prepared_uid=self.user,
            keeper_uid=self.user,
        )
        Purchase.objects.create(
            name='B项目采购',
            code='PO-B',
            cate=category,
            project=other_project,
            amount=Decimal('800.00'),
            sign_time=date(2026, 7, 1),
            start_time=date(2026, 7, 1),
            end_time=date(2026, 7, 10),
            admin=self.user,
            sign_uid=self.user,
            prepared_uid=self.user,
            keeper_uid=self.user,
        )

        response = self.client.get(
            reverse('contract:contract_purchase_datalist'),
            {'project_id': project.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['data'][0]['project_name'], project.name)
        self.assertEqual(payload['data'][0]['code'], 'PO-A')

    def test_purchase_add_form_prefills_project_from_query_param(self):
        project = self._create_project(name='采购联动项目', code='PRJ-LINK')

        response = self.client.get(
            reverse('contract:contract_purchase_add'),
            {'project_id': project.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="project_id"')
        self.assertContains(response, f'<option value="{project.id}" selected>{project.name} ({project.code})</option>', html=True)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class ProjectDeletionTests(TestCase):
    def setUp(self):
        self.creator = Admin.objects.create_user(
            username='project_creator',
            password='secret123',
            email='creator@example.com',
            thumb='',
            name='项目创建人',
        )
        self.manager = Admin.objects.create_user(
            username='project_delete_manager',
            password='secret123',
            email='manager@example.com',
            thumb='',
            name='项目经理',
        )
        self.client.force_login(self.manager)

    def test_project_list_template_wires_real_delete_endpoint(self):
        response = self.client.get(reverse('project:project_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/adm/project/delete/')
        self.assertNotContains(response, '删除功能开发中...')

    def test_adm_project_delete_soft_deletes_project_for_manager(self):
        project = Project.objects.create(
            name='待删除项目',
            code='PRJ-DELETE-001',
            creator=self.creator,
            manager=self.manager,
            budget=Decimal('1000.00'),
        )

        response = self.client.post(f'/adm/project/delete/{project.id}/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)

        project.refresh_from_db()
        self.assertIsNotNone(project.delete_time)
        self.assertFalse(Project.objects.filter(id=project.id, delete_time__isnull=True).exists())


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class ProjectCommentMentionTests(TestCase):
    def setUp(self):
        self.author = Admin.objects.create_user(
            username='comment_author',
            password='secret123',
            email='author@example.com',
            thumb='',
            name='评论作者',
        )
        self.manager = Admin.objects.create_user(
            username='comment_manager',
            password='secret123',
            email='manager@example.com',
            thumb='',
            name='项目经理',
        )
        self.member = Admin.objects.create_user(
            username='comment_member',
            password='secret123',
            email='member@example.com',
            thumb='',
            name='项目成员',
        )
        self.assignee = Admin.objects.create_user(
            username='comment_assignee',
            password='secret123',
            email='assignee@example.com',
            thumb='',
            name='任务负责人',
        )
        self.participant = Admin.objects.create_user(
            username='comment_participant',
            password='secret123',
            email='participant@example.com',
            thumb='',
            name='任务参与人',
        )
        self.outsider = Admin.objects.create_user(
            username='comment_outsider',
            password='secret123',
            email='outsider@example.com',
            thumb='',
            name='外部人员',
        )
        self.client.force_login(self.author)
        self.project = Project.objects.create(
            name='评论提及项目',
            code='PRJ-COMMENT-001',
            creator=self.author,
            manager=self.manager,
            budget=Decimal('5000.00'),
            actual_cost=Decimal('0'),
        )
        self.project.members.add(self.member)
        self.task = Task.objects.create(
            project=self.project,
            title='评论提及任务',
            assignee=self.assignee,
            creator=self.author,
        )
        self.task.participants.add(self.participant)
        self.project_content_type = ContentType.objects.get_for_model(Project)

    def test_project_comment_candidates_include_manager_members_assignees_and_participants(self):
        response = self.client.get(
            '/api/project/comments/mention_candidates/',
            {
                'content_type': 'project',
                'object_id': self.project.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        returned_user_ids = {item['id'] for item in payload['results']}

        self.assertSetEqual(
            returned_user_ids,
            {
                self.manager.id,
                self.member.id,
                self.assignee.id,
                self.participant.id,
            },
        )
        self.assertEqual(len(payload['results']), 4)

    def test_project_detail_team_member_scope_matches_comment_mentions(self):
        response = self.client.get(
            reverse('project:project_detail', kwargs={'project_id': self.project.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '团队成员 (4)')

    def test_creating_comment_notifies_only_allowed_mentions(self):
        response = self.client.post(
            '/api/project/comments/',
            {
                'content': '请相关同学关注',
                'object_id': self.project.id,
                'content_type_id': self.project_content_type.id,
                'mentioned_user_ids': [
                    self.manager.id,
                    self.member.id,
                    self.outsider.id,
                    self.author.id,
                ],
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        comment = Comment.objects.get(object_id=self.project.id, user=self.author)
        relation_user_ids = set(
            MessageUserRelation.objects.filter(
                message__category__code='comment',
                message__related_object_id=comment.id,
            ).values_list('user_id', flat=True)
        )

        self.assertSetEqual(
            relation_user_ids,
            {self.manager.id, self.member.id},
        )

    def test_reply_comment_sends_reply_and_mention_notifications(self):
        parent_comment = Comment.objects.create(
            user=self.member,
            content='原始评论',
            content_type=self.project_content_type,
            object_id=self.project.id,
        )

        response = self.client.post(
            '/api/project/comments/',
            {
                'content': '回复并提及负责人',
                'object_id': self.project.id,
                'content_type_id': self.project_content_type.id,
                'parent_id': parent_comment.id,
                'mentioned_user_ids': [self.assignee.id],
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        reply_comment = Comment.objects.exclude(id=parent_comment.id).get()
        relation_user_ids = set(
            MessageUserRelation.objects.filter(
                message__category__code='comment',
                message__related_object_id=reply_comment.id,
            ).values_list('user_id', flat=True)
        )

        self.assertSetEqual(
            relation_user_ids,
            {self.member.id, self.assignee.id},
        )

    def test_project_detail_renders_comment_mention_bootstrap_hooks(self):
        response = self.client.get(
            reverse('project:project_detail', kwargs={'project_id': self.project.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lay-id="purchases"')
        self.assertContains(response, 'data-comment-mention-endpoint="/api/project/comments/mention_candidates/"')
        self.assertContains(response, 'class="comment-editor-container"')
        self.assertContains(response, 'id="comment-notification-bubble"')
        self.assertContains(response, 'triggerUnreadCountRefresh')
        self.assertContains(response, "hashTabId.indexOf('comment-') === 0")

    def test_project_comment_notification_state_endpoint_returns_unread_state(self):
        comment = Comment.objects.create(
            user=self.member,
            content='被提及的评论',
            content_type=self.project_content_type,
            object_id=self.project.id,
        )
        MessageService.send_notification(
            title='项目评论提及通知',
            content='有人在项目评论里提到了你',
            category_code='comment',
            user_ids=[self.author.id],
            sender=self.member,
            priority=2,
            related_object_type='comment',
            related_object_id=comment.id,
            action_url=f'/project/detail/{self.project.id}/#comment-{comment.id}',
        )

        response = self.client.get(
            '/api/project/comments/notification_state/',
            {'object_id': self.project.id},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['unread_count'], 1)
        self.assertTrue(payload['has_unread'])
        self.assertEqual(payload['latest']['related_object_id'], comment.id)

    def test_comment_list_includes_replies_for_project_detail_rendering(self):
        parent_comment = Comment.objects.create(
            user=self.member,
            content='父级评论',
            content_type=self.project_content_type,
            object_id=self.project.id,
        )
        reply_comment = Comment.objects.create(
            user=self.assignee,
            content='这是一个回复',
            content_type=self.project_content_type,
            object_id=self.project.id,
            parent=parent_comment,
        )

        response = self.client.get(
            '/api/project/comments/by_object/',
            {
                'content_type': 'project',
                'object_id': self.project.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['id'], parent_comment.id)
        self.assertEqual(len(payload[0]['replies']), 1)
        self.assertEqual(payload[0]['replies'][0]['id'], reply_comment.id)
        self.assertEqual(payload[0]['replies'][0]['content'], '这是一个回复')


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class ProjectRiskAnalysisTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username='risk-owner',
            password='secret123',
            email='risk-owner@example.com',
            thumb='',
            name='风险负责人',
        )
        self.client.force_login(self.user)
        self.project = Project.objects.create(
            name='智慧工厂升级项目',
            code='RISK-001',
            creator=self.user,
            manager=self.user,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 7, 31),
            budget=Decimal('200000.00'),
            actual_cost=Decimal('180000.00'),
            progress=42,
            priority=3,
        )
        Task.objects.create(
            project=self.project,
            title='核心网络改造',
            creator=self.user,
            assignee=self.user,
            status=2,
            priority=4,
            progress=30,
            estimated_hours=40,
            actual_hours=52,
            start_date=date(2026, 6, 5),
            end_date=date(2026, 6, 20),
        )
        Task.objects.create(
            project=self.project,
            title='机房收尾',
            creator=self.user,
            status=1,
            priority=2,
            progress=0,
            estimated_hours=24,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 10),
        )

    def test_risk_prediction_page_lists_projects_and_key_columns(self):
        response = self.client.get(reverse('project:ai_risk_prediction_page_default'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '项目风险分析')
        self.assertContains(response, '风险等级')
        self.assertContains(response, self.project.name)
        self.assertContains(response, '重新分析')
        self.assertContains(response, '暂无详情')

    def test_manual_risk_prediction_creates_persisted_analysis(self):
        with patch('apps.project.risk_analysis.default_project_analysis_tool._call_ai') as call_ai:
            call_ai.return_value = {
                'summary': '项目存在成本与进度双重风险，需要重点盯控采购与延期任务。',
                'risk_level': 'high',
                'risk_points': ['采购成本逼近预算上限', '存在逾期任务'],
                'suggestions': ['压缩非关键采购支出', '按周跟踪高优先级任务'],
                'confidence': 0.86,
            }

            response = self.client.post(
                reverse('project:ai_risk_prediction_api', kwargs={'project_id': self.project.id})
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['risk_level'], 'high')

        analysis = ProjectRiskAnalysis.objects.get(project=self.project)
        self.assertEqual(analysis.risk_level, 'high')
        self.assertGreaterEqual(analysis.risk_score, 1)
        self.assertIn('逾期任务', ''.join(analysis.key_risks))

    def test_risk_prediction_detail_page_renders_analysis_content(self):
        analysis = ProjectRiskAnalysis.objects.create(
            project=self.project,
            risk_level='medium',
            risk_score=67,
            warning_count=3,
            summary='项目整体可控，但存在进度滑坡风险。',
            key_risks=['里程碑偏慢', '工时超预估'],
            suggestions=['收敛关键路径任务', '追加阶段复盘'],
            recommended_action='manual_review',
            confidence=0.75,
            metrics={'schedule': {'progress_gap': 18}},
            analysis_payload={'summary': '项目整体可控，但存在进度滑坡风险。'},
            trigger_source='manual',
        )

        response = self.client.get(
            reverse('project:ai_risk_prediction_detail', kwargs={'analysis_id': analysis.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.assertContains(response, '项目整体可控，但存在进度滑坡风险。')
        self.assertContains(response, '里程碑偏慢')

    def test_daily_risk_refresh_command_generates_analysis_for_all_projects(self):
        other_project = Project.objects.create(
            name='数据中台二期',
            code='RISK-002',
            creator=self.user,
            manager=self.user,
            budget=Decimal('80000.00'),
        )

        with patch('apps.project.risk_analysis.default_project_analysis_tool._call_ai') as call_ai:
            call_ai.return_value = {
                'summary': '建议持续关注任务排期。',
                'risk_level': 'medium',
                'risk_points': ['部分任务尚未开始'],
                'suggestions': ['每日同步进展'],
                'confidence': 0.62,
            }
            call_command('refresh_project_risk_analyses')

        analyses = ProjectRiskAnalysis.objects.filter(project__in=[self.project, other_project])
        self.assertEqual(analyses.count(), 2)
        self.assertTrue(
            analyses.filter(trigger_source='scheduled').exclude(summary='').exists()
        )

    def test_old_progress_analysis_url_redirects_to_risk_prediction(self):
        response = self.client.get('/project/ai/progress-analysis/', follow=False)

        self.assertIn(response.status_code, (301, 302))
        self.assertIn('/project/ai/risk-prediction/', response['Location'])


class ProjectRiskRefreshSchedulerCommandTests(TestCase):
    def test_next_run_time_rolls_to_next_day_after_noon(self):
        from apps.project.management.commands.run_project_risk_refresh_scheduler import (
            get_next_run_time,
        )

        self.assertEqual(
            get_next_run_time(datetime(2026, 7, 2, 11, 30), hour=12, minute=0),
            datetime(2026, 7, 2, 12, 0),
        )
        self.assertEqual(
            get_next_run_time(datetime(2026, 7, 2, 12, 30), hour=12, minute=0),
            datetime(2026, 7, 3, 12, 0),
        )

    def test_scheduler_once_mode_delegates_to_refresh_command(self):
        with patch(
            'apps.project.management.commands.run_project_risk_refresh_scheduler.call_command'
        ) as call_refresh:
            call_command('run_project_risk_refresh_scheduler', '--once')

        call_refresh.assert_called_once_with('refresh_project_risk_analyses', verbosity=1)

    def test_scheduler_lock_prevents_duplicate_process(self):
        from apps.project.management.commands import run_project_risk_refresh_scheduler as scheduler_command

        with self.subTest('duplicate lock blocks startup'):
            with patch.object(scheduler_command, '_is_process_running', return_value=True):
                with patch.object(scheduler_command, 'PID_FILE', settings.BASE_DIR / 'runtime' / 'test_project_risk_scheduler.pid'):
                    scheduler_command.PID_FILE.write_text('999999', encoding='utf-8')
                    try:
                        self.assertFalse(scheduler_command.acquire_scheduler_lock())
                    finally:
                        if scheduler_command.PID_FILE.exists():
                            scheduler_command.PID_FILE.unlink()
