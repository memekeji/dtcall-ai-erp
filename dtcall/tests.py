from django.conf import settings
from django.test import TestCase
from django.urls import NoReverseMatch, reverse


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
