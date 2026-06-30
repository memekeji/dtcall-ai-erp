from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.customer.models import Customer, CustomerIntent
from apps.user.models import Admin


TEST_MIDDLEWARE = [
    middleware for middleware in settings.MIDDLEWARE
    if middleware != 'apps.system.middleware.permission_middleware.PermissionMiddleware'
]


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class CustomerKanbanDataViewTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username='customer-kanban-user',
            email='customer-kanban@example.com',
            password='password123',
            name='客户看板测试员',
        )
        self.client.force_login(self.user)
        self.intent = CustomerIntent.objects.create(name='重点跟进', sort=1)

        Customer.objects.create(
            name='重点客户',
            services_id=self.intent.id,
            belong_uid=self.user.id,
            admin_id=self.user.id,
        )
        Customer.objects.create(
            name='未分类客户',
            services_id=0,
            belong_uid=self.user.id,
            admin_id=self.user.id,
        )

    def test_kanban_filters_by_intent_id(self):
        response = self.client.get(
            reverse('customer:customer_list_data'),
            {
                'view_type': 'card',
                'customer_intent_id': str(self.intent.id),
            },
        )

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['data'][0]['name'], '重点客户')
        self.assertEqual(payload['data'][0]['customer_intent_id'], self.intent.id)

    def test_kanban_exposes_uncategorized_bucket(self):
        response = self.client.get(
            reverse('customer:customer_list_data'),
            {
                'view_type': 'card',
                'customer_intent_id': '__uncategorized__',
            },
        )

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['data'][0]['name'], '未分类客户')
        self.assertEqual(payload['data'][0]['customer_intent'], '未分类')
