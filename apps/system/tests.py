from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import include, path

from apps.system.models import ServiceCategory, ServiceProvider
from apps.system.views.service_config_views import ServiceConfigFormView

urlpatterns = [
    path(
        'system/config/service/',
        include(('apps.system.urls.service_config_urls', 'system'), namespace='system'),
    ),
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
