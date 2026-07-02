from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import include, path

from apps.system.middleware.database_setup_middleware import DatabaseSetupMiddleware
from apps.system.database_setup import build_database_config, test_database_config
from apps.system.views.database_setup_views import database_setup_view
from apps.system.models import ServiceCategory, ServiceProvider
from apps.system.context_processors import system_version, get_permission_from_src
from apps.system.update_center_service import perform_online_update
from apps.system.views.service_config_views import ServiceConfigFormView
from apps.user.config.permission_nodes import get_all_permission_codenames

urlpatterns = [
    path(
        'system/config/service/',
        include(('apps.system.urls.service_config_urls', 'system'), namespace='system'),
    ),
    path('setup/database/', database_setup_view, name='database_setup'),
]


class ServiceConfigFormInitialTests(TestCase):
    def test_category_query_prefills_service_form_defaults(self):
        request = RequestFactory().get(
            '/system/config/service/add/',
            {'category': ServiceCategory.STT},
        )

        view = ServiceConfigFormView()
        view.request = request

        initial = view.get_initial()

        self.assertEqual(initial['category'], ServiceCategory.STT)
        self.assertEqual(initial['provider'], ServiceProvider.ALIYUN)
        self.assertEqual(initial['name'], '语音转文本')
        self.assertTrue(initial['is_enabled'])

    @override_settings(ROOT_URLCONF=__name__)
    def test_add_service_page_renders_category_defaults(self):
        user = get_user_model().objects.create_user(
            username='system_config_tester',
            password='test-pass-123',
        )
        request = RequestFactory().get(
            '/system/config/service/add/',
            {'category': ServiceCategory.STT},
        )
        request.user = user

        response = ServiceConfigFormView.as_view()(request)
        response.render()
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('value="语音转文本"', content)
        self.assertIn('<option value="stt" selected>', content)


@override_settings(ROOT_URLCONF=__name__)
class DatabaseSetupAdminInitializationTests(TestCase):
    @patch('apps.system.views.database_setup_views.has_initial_admin')
    @patch('apps.system.views.database_setup_views.get_database_state')
    def test_setup_page_remains_accessible_until_admin_is_created(
        self,
        mock_get_database_state,
        mock_has_initial_admin,
    ):
        from apps.system.database_setup import DatabaseState

        mock_get_database_state.return_value = DatabaseState(
            can_connect=True,
            has_tables=True,
            reason='',
        )
        mock_has_initial_admin.return_value = False

        response = self.client.get('/setup/database/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '管理员账号')

    @patch('apps.system.views.database_setup_views.run_base_migrations')
    @patch('apps.system.views.database_setup_views.apply_database_config')
    @patch('apps.system.views.database_setup_views.save_database_environment')
    @patch('apps.system.views.database_setup_views.test_database_config')
    @patch('apps.system.views.database_setup_views.build_database_config')
    @patch('apps.system.views.database_setup_views.has_initial_admin')
    @patch('apps.system.views.database_setup_views.get_database_state')
    def test_setup_page_creates_initial_admin_after_successful_database_setup(
        self,
        mock_get_database_state,
        mock_has_initial_admin,
        mock_build_database_config,
        mock_test_database_config,
        mock_save_database_environment,
        mock_apply_database_config,
        mock_run_base_migrations,
    ):
        from apps.system.database_setup import DatabaseState

        mock_get_database_state.side_effect = [
            DatabaseState(can_connect=False, has_tables=False, reason='未配置数据库连接'),
            DatabaseState(can_connect=True, has_tables=True, reason=''),
        ]
        mock_has_initial_admin.side_effect = [False, False]
        mock_build_database_config.return_value = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'db.sqlite3'}
        mock_run_base_migrations.return_value = DatabaseState(
            can_connect=True,
            has_tables=True,
            reason='',
        )

        response = self.client.post('/setup/database/', {
            'DATABASE_ENGINE': 'sqlite',
            'DATABASE_NAME': 'db.sqlite3',
            'ADMIN_USERNAME': 'bootstrap_admin',
            'ADMIN_NAME': '初始化管理员',
            'ADMIN_EMAIL': 'bootstrap@example.com',
            'ADMIN_PASSWORD': 'InitPass123!',
            'ADMIN_PASSWORD_CONFIRM': 'InitPass123!',
        })

        self.assertEqual(response.status_code, 200)
        admin = get_user_model().objects.get(username='bootstrap_admin')
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertEqual(admin.status, 1)
        self.assertEqual(admin.name, '初始化管理员')
        self.assertEqual(admin.email, 'bootstrap@example.com')
        self.assertTrue(check_password('InitPass123!', admin.pwd))
        self.assertContains(response, '数据库连接验证、基础迁移和管理员创建已完成。')
        mock_build_database_config.assert_called_once()
        mock_test_database_config.assert_called_once()
        mock_save_database_environment.assert_called_once()
        mock_apply_database_config.assert_called_once()
        mock_run_base_migrations.assert_called_once()

    @patch('apps.system.middleware.database_setup_middleware.has_initial_admin')
    @patch('apps.system.middleware.database_setup_middleware.get_database_state')
    def test_middleware_redirects_to_setup_when_admin_is_missing(
        self,
        mock_get_database_state,
        mock_has_initial_admin,
    ):
        from apps.system.database_setup import DatabaseState

        mock_get_database_state.return_value = DatabaseState(
            can_connect=True,
            has_tables=True,
            reason='',
        )
        mock_has_initial_admin.return_value = False
        middleware = DatabaseSetupMiddleware(lambda request: HttpResponse('ok'))
        request = RequestFactory().get('/user/login/')

        response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/setup/database/')

    @patch('apps.system.views.database_setup_views.get_database_state')
    def test_setup_page_rejects_mismatched_admin_password_confirmation(
        self,
        mock_get_database_state,
    ):
        from apps.system.database_setup import DatabaseState

        mock_get_database_state.return_value = DatabaseState(
            can_connect=False,
            has_tables=False,
            reason='未配置数据库连接',
        )

        response = self.client.post('/setup/database/', {
            'DATABASE_ENGINE': 'sqlite',
            'DATABASE_NAME': 'db.sqlite3',
            'ADMIN_USERNAME': 'bootstrap_admin',
            'ADMIN_NAME': '初始化管理员',
            'ADMIN_EMAIL': 'bootstrap@example.com',
            'ADMIN_PASSWORD': 'InitPass123!',
            'ADMIN_PASSWORD_CONFIRM': 'DifferentPass123!',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='bootstrap_admin').exists())
        self.assertContains(response, '管理员密码与确认密码不一致')


class DatabaseSetupConfigValidationTests(SimpleTestCase):
    def test_malformed_database_url_raises_readable_error(self):
        with self.assertRaisesMessage(ValueError, 'DATABASE_URL格式不正确'):
            build_database_config({
                'DATABASE_URL': '://bad',
                'DATABASE_ENGINE': 'mysql',
            })

    def test_example_database_url_raises_readable_error(self):
        with self.assertRaisesMessage(ValueError, 'DATABASE_URL仍是示例值'):
            build_database_config({
                'DATABASE_URL': 'postgresql://user:password@127.0.0.1:5432/dtcall',
                'DATABASE_ENGINE': 'mysql',
            })

    def test_database_url_type_must_match_selected_engine(self):
        with self.assertRaisesMessage(ValueError, '数据库类型与下方选择不一致'):
            build_database_config({
                'DATABASE_URL': 'postgresql://real_user:real_password@127.0.0.1:5432/erp51mimu',
                'DATABASE_ENGINE': 'mysql',
            })

    def test_empty_database_engine_raises_readable_error_before_backend_import(self):
        with self.assertRaisesMessage(ValueError, '数据库类型不能为空'):
            test_database_config({'ENGINE': '', 'NAME': 'dtcall'})


class UpdateCenterPermissionTests(TestCase):
    @patch('apps.system.context_processors.cache')
    @patch('apps.system.version_service.check_for_updates')
    @patch('apps.system.version_service.get_current_commit')
    @patch('apps.system.version_service.get_current_version')
    def test_system_version_marks_config_admin_as_update_admin(
        self,
        mock_get_current_version,
        mock_get_current_commit,
        mock_check_for_updates,
        mock_cache,
    ):
        request = RequestFactory().get('/')
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=Mock(side_effect=lambda perm: perm == 'user.change_config'),
        )
        mock_cache.get.return_value = None
        mock_get_current_version.return_value = '1.0.0'
        mock_get_current_commit.return_value = 'abc1234'
        mock_check_for_updates.return_value = {'update_available': False}

        context = system_version(request)

        self.assertTrue(context['APP_UPDATE_ADMIN_VISIBLE'])

    @patch('apps.system.context_processors.cache')
    @patch('apps.system.version_service.check_for_updates')
    @patch('apps.system.version_service.get_current_commit')
    @patch('apps.system.version_service.get_current_version')
    def test_system_version_hides_update_admin_controls_for_normal_user(
        self,
        mock_get_current_version,
        mock_get_current_commit,
        mock_check_for_updates,
        mock_cache,
    ):
        request = RequestFactory().get('/')
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            has_perm=Mock(return_value=False),
        )
        mock_cache.get.return_value = None
        mock_get_current_version.return_value = '1.0.0'
        mock_get_current_commit.return_value = 'abc1234'
        mock_check_for_updates.return_value = {'update_available': False}

        context = system_version(request)

        self.assertFalse(context['APP_UPDATE_ADMIN_VISIBLE'])


class MenuPermissionMappingTests(TestCase):
    def test_menu_urls_map_to_expected_permissions(self):
        cases = {
            '/finance/': 'view_finance',
            '/finance/reimbursement/': 'view_reimbursement',
            '/finance/receiveinvoice/': 'view_receive_invoice',
            '/finance/payment/': 'view_payment',
            '/customer/followup/': 'view_follow_record',
            '/customer/callrecord/': 'view_call_record',
            '/customer/public/list/': 'view_public_customer',
            '/production/baseinfo/': 'view_production_baseinfo',
            '/production/data/source/': 'view_datacollection',
            '/production/equipment/monitor/': 'view_equipment_monitor',
            '/production/task/plan/': 'view_production_plan',
        }

        for src, expected in cases.items():
            with self.subTest(src=src):
                self.assertEqual(get_permission_from_src(src), expected)

    def test_root_permissions_exist_in_permission_config(self):
        permission_codes = set(get_all_permission_codenames())
        self.assertIn('view_finance', permission_codes)
        self.assertIn('view_customer', permission_codes)
        self.assertIn('view_production', permission_codes)


class UpdateCenterServiceTests(TestCase):
    @patch('apps.system.update_center_service.finalize_staged_release')
    @patch('apps.system.update_center_service.extract_release_package')
    @patch('apps.system.update_center_service.verify_release_package')
    @patch('apps.system.update_center_service.download_release_package')
    @patch('apps.system.update_center_service.fetch_latest_release_info')
    @patch('apps.system.update_center_service.check_for_updates')
    @patch('apps.system.update_center_service.get_current_version')
    def test_online_update_fetches_exact_target_release_when_target_version_is_provided(
        self,
        mock_get_current_version,
        mock_check_for_updates,
        mock_fetch_latest_release_info,
        mock_download_release_package,
        mock_verify_release_package,
        mock_extract_release_package,
        mock_finalize_staged_release,
    ):
        mock_get_current_version.return_value = '1.0.0'
        mock_check_for_updates.return_value = {
            'latest_version': '1.2.0',
            'release': {
                'version': '1.2.0',
                'packageUrl': 'https://www.dtcall.cn/releases/1.2.0.zip',
                'checksum': 'sha256:latest',
            },
        }
        mock_fetch_latest_release_info.return_value = {
            'release': {
                'version': '1.1.0',
                'packageUrl': 'https://www.dtcall.cn/releases/1.1.0.zip',
                'checksum': 'sha256:target',
            }
        }
        mock_download_release_package.return_value = {'success': True, 'file': '/tmp/release.zip'}
        mock_verify_release_package.return_value = {'success': True}
        mock_extract_release_package.return_value = {'success': True, 'staging_dir': '/tmp/staging'}
        mock_finalize_staged_release.return_value = {'success': True, 'new_version': '1.1.0'}

        perform_online_update(target_version='1.1.0')

        mock_fetch_latest_release_info.assert_called_once_with(
            version='1.0.0',
            channel=None,
            platform=None,
            release_version='1.1.0',
        )
