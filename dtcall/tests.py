import os
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch, reverse


class DatabaseConfigurationTests(SimpleTestCase):
    def test_missing_database_environment_uses_dummy_backend(self):
        from dtcall import settings as dtcall_settings

        keys = [
            'DATABASE_URL',
            'DATABASE_ENGINE',
            'DATABASE_TYPE',
            'DB_ENGINE',
            'DATABASE_HOST',
            'DATABASE_NAME',
        ]
        saved = {key: os.environ.get(key) for key in keys}
        try:
            for key in keys:
                os.environ.pop(key, None)

            with patch.object(dtcall_settings.sys, 'argv', ['manage.py', 'runserver']):
                database_config = dtcall_settings._database_from_env()
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(
            database_config['ENGINE'],
            'django.db.backends.dummy',
        )

    def test_mysql_database_options_normalize_bare_init_command(self):
        from dtcall import settings as dtcall_settings

        with patch.dict(os.environ, {'MYSQL_INIT_COMMAND': "'STRICT_TRANS_TABLES'"}):
            options = dtcall_settings._database_options('django.db.backends.mysql')

        self.assertEqual(
            options['init_command'],
            "SET sql_mode='STRICT_TRANS_TABLES'",
        )

    def test_mysql_database_options_preserve_full_init_command(self):
        from dtcall import settings as dtcall_settings

        with patch.dict(
            os.environ,
            {'MYSQL_INIT_COMMAND': "SET SESSION sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE'"},
        ):
            options = dtcall_settings._database_options('django.db.backends.mysql')

        self.assertEqual(
            options['init_command'],
            "SET SESSION sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE'",
        )

    def test_database_setup_build_config_normalizes_mysql_init_command(self):
        from apps.system.database_setup import build_database_config

        config = build_database_config({
            'DATABASE_ENGINE': 'mysql',
            'DATABASE_HOST': '127.0.0.1',
            'DATABASE_PORT': '3306',
            'DATABASE_NAME': 'dtcall',
            'DATABASE_USER': 'root',
            'DATABASE_PASSWORD': 'secret',
            'MYSQL_INIT_COMMAND': 'STRICT_TRANS_TABLES',
        })

        self.assertEqual(
            config['OPTIONS']['init_command'],
            "SET sql_mode='STRICT_TRANS_TABLES'",
        )

    def test_runserver_auto_starts_project_risk_scheduler_subprocess(self):
        from dtcall import startup_tasks

        with patch.dict(
            os.environ,
            {'AUTO_START_PROJECT_RISK_REFRESH_SCHEDULER': 'true'},
            clear=False,
        ):
            os.environ.pop('DTCALL_PROJECT_RISK_SCHEDULER_STARTED', None)
            os.environ.pop('DTCALL_PROJECT_RISK_SCHEDULER_CHILD', None)
            with patch.object(startup_tasks.sys, 'argv', ['manage.py', 'runserver']):
                with patch('dtcall.startup_tasks.subprocess.Popen') as popen:
                    started = startup_tasks.start_project_risk_scheduler_subprocess(
                        context='runserver'
                    )

        self.assertTrue(started)
        popen.assert_called_once()

    def test_non_runserver_command_does_not_auto_start_project_risk_scheduler(self):
        from dtcall import startup_tasks

        with patch.dict(
            os.environ,
            {'AUTO_START_PROJECT_RISK_REFRESH_SCHEDULER': 'true'},
            clear=False,
        ):
            os.environ.pop('DTCALL_PROJECT_RISK_SCHEDULER_STARTED', None)
            os.environ.pop('DTCALL_PROJECT_RISK_SCHEDULER_CHILD', None)
            with patch.object(startup_tasks.sys, 'argv', ['manage.py', 'migrate']):
                with patch('dtcall.startup_tasks.subprocess.Popen') as popen:
                    started = startup_tasks.start_project_risk_scheduler_subprocess(
                        context='runserver'
                    )

        self.assertFalse(started)
        popen.assert_not_called()


class ProjectSmokeTests(TestCase):
    def test_root_redirects_to_login(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/user/login/')

    def test_login_page_is_accessible(self):
        response = self.client.get(reverse('user:login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '企业数字化管理平台')

    def test_core_named_routes_resolve(self):
        route_names = [
            'user:login',
            'home:main',
            'home:dashboard',
            'finance:finance_index',
            'finance:expense_list',
            'customer:customer_list',
            'production:baseinfo_index',
            'production:procedure_list',
            'project:project_list',
            'project:project_category_list',
            'disk:index',
            'ai:chat',
            'ai:workflow_list',
        ]

        unresolved = []
        for route_name in route_names:
            try:
                reverse(route_name)
            except NoReverseMatch:
                unresolved.append(route_name)

        self.assertEqual(unresolved, [])

    def test_core_module_entrypoints_do_not_error_for_anonymous_users(self):
        paths = [
            reverse('finance:finance_index'),
            reverse('finance:expense_list'),
            reverse('customer:customer_list'),
            reverse('production:baseinfo_index'),
            reverse('production:procedure_list'),
            reverse('project:project_list'),
            reverse('project:project_category_list'),
            reverse('disk:index'),
            reverse('ai:chat'),
            reverse('ai:workflow_list'),
        ]

        failures = []
        for path in paths:
            response = self.client.get(path)
            if response.status_code >= 500:
                failures.append((path, response.status_code))

        self.assertEqual(failures, [])

    def test_static_media_and_temp_urls_are_configured(self):
        self.assertEqual(settings.STATIC_URL, '/static/')
        self.assertEqual(settings.MEDIA_URL, '/media/')
        self.assertEqual(settings.TEMP_URL, '/temp/')
