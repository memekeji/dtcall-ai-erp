from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import include, path

from apps.system.middleware.database_setup_middleware import DatabaseSetupMiddleware
from apps.system.views.database_setup_views import database_setup_view
from apps.system.models import ServiceCategory, ServiceProvider
from apps.system.views.service_config_views import ServiceConfigFormView

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
