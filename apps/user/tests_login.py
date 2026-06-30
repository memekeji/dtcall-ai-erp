from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.test import override_settings


@override_settings(
    MIDDLEWARE=[
        middleware for middleware in __import__('dtcall.settings', fromlist=['MIDDLEWARE']).MIDDLEWARE
        if middleware != 'apps.system.middleware.database_setup_middleware.DatabaseSetupMiddleware'
    ]
)
class LoginSubmitTests(TestCase):
    @patch('apps.user.views.admin_views.verify_captcha', return_value=True)
    def test_login_submit_keeps_session_alive(self, _mock_verify_captcha):
        password_hash = make_password('LoginPass123!')
        user = get_user_model().objects.create(
            username='login_submit_tester',
            email='login_submit_tester@example.com',
            name='Login Tester',
            pwd=password_hash,
            password=password_hash,
            status=1,
            is_active=True,
            thumb='',
        )

        response = self.client.post('/user/login-submit/', {
            'username': user.username,
            'password': 'LoginPass123!',
            'captcha': 'ok',
            'captcha_key': 'mock-key',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['redirect_url'], '/home/main/')
        self.assertEqual(self.client.session.get('_auth_user_id'), str(user.id))
        self.assertEqual(self.client.session.get('admin_id'), user.id)
