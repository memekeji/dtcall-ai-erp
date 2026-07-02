from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.common.constants import CUSTOMER_INDUSTRY_CHOICES
from apps.contract.models import Contract
from apps.customer.models import (
    Customer,
    CustomerField,
    CustomerCustomFieldValue,
    CustomerContract,
    CustomerIntent,
    CustomerOrder,
    FollowField,
    OrderField,
)
from apps.project.models import Project
from apps.user.models import Admin


TEST_MIDDLEWARE = [
    middleware for middleware in settings.MIDDLEWARE
    if middleware not in {
        'apps.system.middleware.permission_middleware.PermissionMiddleware',
        'apps.system.middleware.database_setup_middleware.DatabaseSetupMiddleware',
    }
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


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class CustomerIntentFormViewTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username='customer-intent-form-user',
            email='customer-intent-form@example.com',
            password='password123',
            name='客户意向表单测试员',
        )
        self.client.force_login(self.user)

    def test_regular_post_redirects_after_saving_intent(self):
        response = self.client.post(
            reverse('customer:customer_intent_form'),
            {
                'name': '初步沟通',
                'sort': '10',
                'status': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('customer:customer_intent_list'))
        self.assertTrue(CustomerIntent.objects.filter(name='初步沟通').exists())

    def test_ajax_post_returns_json_after_saving_intent(self):
        response = self.client.post(
            reverse('customer:customer_intent_form'),
            {
                'name': '重点推进',
                'sort': '20',
                'status': 'on',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['msg'], '客户意向保存成功！')
        self.assertTrue(CustomerIntent.objects.filter(name='重点推进').exists())

    def test_intent_list_opens_create_and_edit_in_right_popup(self):
        response = self.client.get(reverse('customer:customer_intent_list'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertRegex(content, r'<script>\s*function openRightPopup\(')
        self.assertIn('openRightPopup(', content)
        self.assertIn('openIntentForm(', content)
        self.assertIn("openIntentForm('新增客户意向'", content)
        self.assertIn("openIntentForm('编辑客户意向'", content)
        self.assertNotIn('window.location.href', content)

    def test_intent_form_closes_parent_popup_after_ajax_save(self):
        response = self.client.get(reverse('customer:customer_intent_form'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Requested-With", content)
        self.assertIn("parent.layer.getFrameIndex", content)
        self.assertIn("parent.layer.close", content)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class CustomerCustomFieldFormViewTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username='customer-custom-field-user',
            email='customer-custom-field@example.com',
            password='password123',
            name='客户自定义字段测试员',
        )
        self.client.force_login(self.user)

    def test_customer_field_regular_post_redirects_after_saving(self):
        response = self.client.post(
            reverse('customer:customer_field_form'),
            {
                'name': '客户预算',
                'field_name': 'customer_budget',
                'field_type': 'number',
                'options': '',
                'sort': '1',
                'status': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('customer:customer_field_list'))
        self.assertTrue(CustomerField.objects.filter(field_name='customer_budget').exists())

    def test_customer_field_ajax_post_returns_json_after_saving(self):
        response = self.client.post(
            reverse('customer:customer_field_form'),
            {
                'name': '客户地区',
                'field_name': 'customer_region',
                'field_type': 'text',
                'options': '',
                'sort': '2',
                'status': 'on',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertIn('保存成功', payload['msg'])
        self.assertTrue(CustomerField.objects.filter(field_name='customer_region').exists())

    def test_customer_field_form_supports_related_field_configuration(self):
        CustomerField.objects.create(
            name='客户账号',
            field_name='customer_accounts',
            field_type='list',
            status=True,
            delete_time=0,
        )

        response = self.client.get(reverse('customer:customer_field_form'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('关联已有字段', content)
        self.assertIn('关联方式', content)
        self.assertIn('客户账号', content)

    def test_customer_field_form_wires_relation_switch_with_layui_events(self):
        response = self.client.get(reverse('customer:customer_field_form'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('lay-filter="relationEnabledSwitch"', content)
        self.assertIn("form.on('switch(relationEnabledSwitch)'", content)

    def test_customer_field_form_wires_relation_selects_with_layui_events(self):
        response = self.client.get(reverse('customer:customer_field_form'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('lay-filter="relationTypeSelect"', content)
        self.assertIn('lay-filter="calculationTypeSelect"', content)
        self.assertIn("form.on('select(relationTypeSelect)'", content)
        self.assertIn("form.on('select(calculationTypeSelect)'", content)

    def test_customer_field_can_save_related_field_configuration(self):
        related_field = CustomerField.objects.create(
            name='客户账号',
            field_name='customer_accounts',
            field_type='list',
            status=True,
            delete_time=0,
        )

        response = self.client.post(
            reverse('customer:customer_field_form'),
            {
                'name': '账号绑定邮箱',
                'field_name': 'account_bind_email',
                'field_type': 'text',
                'options': '',
                'sort': '3',
                'status': 'on',
                'relation_enabled': 'on',
                'related_field': str(related_field.id),
                'relation_type': 'bind',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = response.json()
        field = CustomerField.objects.get(field_name='account_bind_email')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertTrue(field.relation_enabled)
        self.assertEqual(field.related_field_id, related_field.id)
        self.assertEqual(field.relation_type, 'bind')

    def test_customer_field_form_supports_calculation_configuration(self):
        CustomerField.objects.create(
            name='客户账号',
            field_name='customer_accounts',
            field_type='list',
            status=True,
            delete_time=0,
        )

        response = self.client.get(reverse('customer:customer_field_form'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('计算结果', content)
        self.assertIn('计算规则', content)

    def test_customer_field_can_save_calculation_configuration(self):
        related_field = CustomerField.objects.create(
            name='客户账号',
            field_name='customer_accounts',
            field_type='list',
            status=True,
            delete_time=0,
        )

        response = self.client.post(
            reverse('customer:customer_field_form'),
            {
                'name': '账号数量',
                'field_name': 'account_count',
                'field_type': 'number',
                'options': '',
                'sort': '4',
                'status': 'on',
                'relation_enabled': 'on',
                'related_field': str(related_field.id),
                'relation_type': 'calculate',
                'calculation_type': 'count',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = response.json()
        field = CustomerField.objects.get(field_name='account_count')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertTrue(field.relation_enabled)
        self.assertEqual(field.related_field_id, related_field.id)
        self.assertEqual(field.relation_type, 'calculate')
        self.assertEqual(field.calculation_type, 'count')

    def test_customer_field_form_supports_formula_configuration(self):
        CustomerField.objects.create(
            name='单价',
            field_name='unit_price',
            field_type='number',
            status=True,
            delete_time=0,
        )
        CustomerField.objects.create(
            name='数量',
            field_name='quantity',
            field_type='number',
            status=True,
            delete_time=0,
        )

        response = self.client.get(reverse('customer:customer_field_form'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('公式计算', content)
        self.assertIn('计算公式', content)
        self.assertIn('{unit_price}', content)
        self.assertIn('{quantity}', content)
        self.assertIn('添加计算节点', content)
        self.assertIn('左侧来源', content)
        self.assertIn('右侧来源', content)
        self.assertIn('高级公式', content)

    def test_customer_field_can_save_formula_configuration(self):
        response = self.client.post(
            reverse('customer:customer_field_form'),
            {
                'name': '总价',
                'field_name': 'total_amount',
                'field_type': 'number',
                'options': '',
                'sort': '5',
                'status': 'on',
                'relation_enabled': 'on',
                'relation_type': 'calculate',
                'calculation_type': 'formula',
                'formula_expression': '{unit_price} * {quantity}',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = response.json()
        field = CustomerField.objects.get(field_name='total_amount')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertEqual(field.relation_type, 'calculate')
        self.assertEqual(field.calculation_type, 'formula')
        self.assertEqual(field.formula_expression, '{unit_price} * {quantity}')

    def test_follow_field_regular_post_redirects_after_saving(self):
        response = self.client.post(
            reverse('customer:follow_field_form'),
            {
                'name': '跟进方式',
                'field_name': 'follow_method',
                'field_type': 'text',
                'options': '',
                'sort_order': '1',
                'is_required': 'on',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('customer:follow_field_list'))
        self.assertTrue(FollowField.objects.filter(field_name='follow_method').exists())

    def test_follow_field_ajax_post_returns_json_after_saving(self):
        response = self.client.post(
            reverse('customer:follow_field_form'),
            {
                'name': '跟进结果',
                'field_name': 'follow_result',
                'field_type': 'text',
                'options': '',
                'sort_order': '2',
                'is_required': 'on',
                'is_active': 'on',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertIn('保存成功', payload['msg'])
        self.assertTrue(FollowField.objects.filter(field_name='follow_result').exists())

    def test_order_field_regular_post_redirects_after_saving(self):
        response = self.client.post(
            reverse('customer:order_field_form'),
            {
                'name': '订单来源',
                'field_name': 'order_channel',
                'field_type': 'text',
                'options': '',
                'sort_order': '1',
                'is_required': 'on',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('customer:order_field_list'))
        self.assertTrue(OrderField.objects.filter(field_name='order_channel').exists())

    def test_order_field_ajax_post_returns_json_after_saving(self):
        response = self.client.post(
            reverse('customer:order_field_form'),
            {
                'name': '交付方式',
                'field_name': 'delivery_method',
                'field_type': 'text',
                'options': '',
                'sort_order': '2',
                'is_required': 'on',
                'is_active': 'on',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertIn('保存成功', payload['msg'])
        self.assertTrue(OrderField.objects.filter(field_name='delivery_method').exists())

    def test_custom_field_forms_close_parent_popup_after_ajax_save(self):
        form_urls = [
            reverse('customer:customer_field_form'),
            reverse('customer:follow_field_form'),
            reverse('customer:order_field_form'),
        ]

        for url in form_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                content = response.content.decode()

                self.assertEqual(response.status_code, 200)
                self.assertIn('X-Requested-With', content)
                self.assertIn('parent.layer.getFrameIndex', content)
                self.assertIn('parent.layer.close', content)

    def test_custom_field_lists_open_create_and_edit_in_right_popup(self):
        list_urls = [
            (reverse('customer:customer_field_list'), 'openCustomerFieldForm(', '添加字段'),
            (reverse('customer:follow_field_list'), 'onclick="addItem()"', '新增跟进字段'),
            (reverse('customer:order_field_list'), 'onclick="addItem()"', '新增订单字段'),
        ]

        for url, open_call, button_text in list_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                content = response.content.decode()

                self.assertEqual(response.status_code, 200)
                if url == reverse('customer:customer_field_list'):
                    self.assertRegex(content, r'<script>\s*function openRightPopup\(')
                self.assertIn('openRightPopup', content)
                self.assertIn(open_call, content)
                self.assertIn(button_text, content)
                self.assertNotIn('<a href="/customer/field/form/" class="layui-btn layui-btn-sm">', content)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class CustomerListCustomFieldValueTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username='customer-list-field-user',
            email='customer-list-field@example.com',
            password='password123',
            name='客户列表字段测试员',
        )
        self.client.force_login(self.user)
        self.account_field = CustomerField.objects.create(
            name='客户账号',
            field_name='customer_accounts',
            field_type='list',
            is_list_display=True,
            status=True,
            delete_time=0,
        )
        self.account_email_field = CustomerField.objects.create(
            name='账号绑定邮箱',
            field_name='account_bind_email',
            field_type='text',
            relation_enabled=True,
            related_field=self.account_field,
            relation_type='bind',
            status=True,
            delete_time=0,
        )
        self.account_count_field = CustomerField.objects.create(
            name='账号数量',
            field_name='account_count',
            field_type='number',
            relation_enabled=True,
            related_field=self.account_field,
            relation_type='calculate',
            calculation_type='count',
            status=True,
            delete_time=0,
        )
        self.unit_price_field = CustomerField.objects.create(
            name='单价',
            field_name='unit_price',
            field_type='number',
            status=True,
            delete_time=0,
        )
        self.quantity_field = CustomerField.objects.create(
            name='数量',
            field_name='quantity',
            field_type='number',
            status=True,
            delete_time=0,
        )
        self.total_amount_field = CustomerField.objects.create(
            name='总价',
            field_name='total_amount',
            field_type='number',
            relation_enabled=True,
            relation_type='calculate',
            calculation_type='formula',
            formula_expression='{unit_price} * {quantity}',
            status=True,
            delete_time=0,
        )

    def test_customer_field_form_supports_list_field_type(self):
        response = self.client.get(reverse('customer:customer_field_form'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('value="list"', content)
        self.assertIn('列表', content)

    def test_customer_create_form_renders_list_custom_field(self):
        response = self.client.get(reverse('customer:customer_create'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('客户账号', content)
        self.assertIn('data-list-custom-field', content)
        self.assertIn(f'name="custom_field_{self.account_field.id}"', content)

    def test_customer_create_form_renders_related_inputs_for_list_custom_field(self):
        response = self.client.get(reverse('customer:customer_create'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('账号绑定邮箱', content)
        self.assertIn('data-related-child-field', content)
        self.assertIn(f'name="custom_field_{self.account_email_field.id}"', content)

    def test_customer_create_saves_multiple_list_custom_field_values(self):
        response = self.client.post(
            reverse('customer:customer_create'),
            {
                'name': '多账号客户',
                'customer_source': '',
                'grade_id': '',
                'industry_id': '0',
                'services_id': '',
                'province': '',
                'city': '',
                'district': '',
                'town': '',
                'address': '',
                'content': '',
                'market': '',
                'remark': '',
                'tax_bank': '',
                'tax_banksn': '',
                'tax_num': '',
                'tax_mobile': '',
                'tax_address': '',
                'contacts-TOTAL_FORMS': '0',
                'contacts-INITIAL_FORMS': '0',
                'contacts-MIN_NUM_FORMS': '0',
                'contacts-MAX_NUM_FORMS': '1000',
                f'custom_field_{self.account_field.id}': ['acct-001', 'acct-002'],
                f'custom_field_{self.account_email_field.id}': ['acct-001@example.com', 'acct-002@example.com'],
            },
            HTTP_USER_AGENT='test-client',
        )

        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(name='多账号客户')
        custom_value = CustomerCustomFieldValue.objects.get(
            customer=customer,
            field=self.account_field,
        )
        related_custom_value = CustomerCustomFieldValue.objects.get(
            customer=customer,
            field=self.account_email_field,
        )
        self.assertEqual(custom_value.value, '["acct-001", "acct-002"]')
        self.assertEqual(
            related_custom_value.value,
            '[{"source": "acct-001", "value": "acct-001@example.com"}, {"source": "acct-002", "value": "acct-002@example.com"}]'
        )

    def test_customer_create_calculates_related_custom_field_value(self):
        response = self.client.post(
            reverse('customer:customer_create'),
            {
                'name': '账号数量客户',
                'customer_source': '',
                'grade_id': '',
                'industry_id': '0',
                'services_id': '',
                'province': '',
                'city': '',
                'district': '',
                'town': '',
                'address': '',
                'content': '',
                'market': '',
                'remark': '',
                'tax_bank': '',
                'tax_banksn': '',
                'tax_num': '',
                'tax_mobile': '',
                'tax_address': '',
                'contacts-TOTAL_FORMS': '0',
                'contacts-INITIAL_FORMS': '0',
                'contacts-MIN_NUM_FORMS': '0',
                'contacts-MAX_NUM_FORMS': '1000',
                f'custom_field_{self.account_field.id}': ['acct-001', 'acct-002', 'acct-003'],
            },
            HTTP_USER_AGENT='test-client',
        )

        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(name='账号数量客户')
        calculated_value = CustomerCustomFieldValue.objects.get(
            customer=customer,
            field=self.account_count_field,
        )
        self.assertEqual(calculated_value.value, '3')

    def test_customer_create_calculates_formula_custom_field_value(self):
        response = self.client.post(
            reverse('customer:customer_create'),
            {
                'name': '公式计算客户',
                'customer_source': '',
                'grade_id': '',
                'industry_id': '0',
                'services_id': '',
                'province': '',
                'city': '',
                'district': '',
                'town': '',
                'address': '',
                'content': '',
                'market': '',
                'remark': '',
                'tax_bank': '',
                'tax_banksn': '',
                'tax_num': '',
                'tax_mobile': '',
                'tax_address': '',
                'contacts-TOTAL_FORMS': '0',
                'contacts-INITIAL_FORMS': '0',
                'contacts-MIN_NUM_FORMS': '0',
                'contacts-MAX_NUM_FORMS': '1000',
                f'custom_field_{self.unit_price_field.id}': '12.5',
                f'custom_field_{self.quantity_field.id}': '4',
            },
            HTTP_USER_AGENT='test-client',
        )

        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(name='公式计算客户')
        calculated_value = CustomerCustomFieldValue.objects.get(
            customer=customer,
            field=self.total_amount_field,
        )
        self.assertEqual(calculated_value.value, '50')

    def test_customer_create_calculates_multi_node_formula_per_customer(self):
        service_fee_field = CustomerField.objects.create(
            name='服务费',
            field_name='service_fee',
            field_type='number',
            status=True,
            delete_time=0,
        )
        total_with_fee_field = CustomerField.objects.create(
            name='含服务费总价',
            field_name='total_with_fee',
            field_type='number',
            relation_enabled=True,
            relation_type='calculate',
            calculation_type='formula',
            formula_expression='({unit_price} * {quantity}) + {service_fee}',
            status=True,
            delete_time=0,
        )

        response = self.client.post(
            reverse('customer:customer_create'),
            {
                'name': '多节点公式客户',
                'customer_source': '',
                'grade_id': '',
                'industry_id': '0',
                'services_id': '',
                'province': '',
                'city': '',
                'district': '',
                'town': '',
                'address': '',
                'content': '',
                'market': '',
                'remark': '',
                'tax_bank': '',
                'tax_banksn': '',
                'tax_num': '',
                'tax_mobile': '',
                'tax_address': '',
                'contacts-TOTAL_FORMS': '0',
                'contacts-INITIAL_FORMS': '0',
                'contacts-MIN_NUM_FORMS': '0',
                'contacts-MAX_NUM_FORMS': '1000',
                f'custom_field_{self.unit_price_field.id}': '12.5',
                f'custom_field_{self.quantity_field.id}': '4',
                f'custom_field_{service_fee_field.id}': '3',
            },
            HTTP_USER_AGENT='test-client',
        )

        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(name='多节点公式客户')
        calculated_value = CustomerCustomFieldValue.objects.get(
            customer=customer,
            field=total_with_fee_field,
        )
        self.assertEqual(calculated_value.value, '53')

    def test_customer_detail_displays_list_custom_field_values(self):
        customer = Customer.objects.create(
            name='详情多账号客户',
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )
        CustomerCustomFieldValue.objects.create(
            customer=customer,
            field=self.account_field,
            value='["acct-A", "acct-B"]',
        )
        CustomerCustomFieldValue.objects.create(
            customer=customer,
            field=self.account_email_field,
            value='[{"source": "acct-A", "value": "acct-a@example.com"}, {"source": "acct-B", "value": "acct-b@example.com"}]',
        )

        response = self.client.get(reverse('customer:customer_detail', args=[customer.id]))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('客户账号', content)
        self.assertIn('acct-A', content)
        self.assertIn('acct-B', content)
        self.assertIn('账号绑定邮箱', content)
        self.assertIn('acct-a@example.com', content)
        self.assertIn('custom-list-linked-group', content)

    def test_customer_list_exposes_list_custom_field_values(self):
        customer = Customer.objects.create(
            name='列表多账号客户',
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )
        CustomerCustomFieldValue.objects.create(
            customer=customer,
            field=self.account_field,
            value='["acct-X", "acct-Y"]',
        )

        page_response = self.client.get(reverse('customer:customer_list'))
        list_response = self.client.get(reverse('customer:customer_list_data'))
        page_content = page_response.content.decode()
        payload = list_response.json()

        self.assertEqual(page_response.status_code, 200)
        self.assertIn("title: '客户账号'", page_content)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data'][0][f'custom_{self.account_field.id}'], 'acct-X、acct-Y')


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class CustomerIndustryFieldTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username='customer-industry-user',
            email='customer-industry@example.com',
            password='password123',
            name='客户行业字段测试员',
        )
        self.client.force_login(self.user)

    def test_customer_create_form_renders_industry_select_choices(self):
        response = self.client.get(reverse('customer:customer_create'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('name="industry_id"', content)
        self.assertIn('<select', content)
        self.assertIn('请选择所属行业', content)
        self.assertIn(CUSTOMER_INDUSTRY_CHOICES[1], content)

    def test_customer_create_saves_selected_industry_choice(self):
        response = self.client.post(
            reverse('customer:customer_create'),
            {
                'name': '行业客户',
                'customer_source': '',
                'grade_id': '',
                'industry_id': '3',
                'services_id': '',
                'province': '',
                'city': '',
                'district': '',
                'town': '',
                'address': '',
                'content': '',
                'market': '',
                'remark': '',
                'tax_bank': '',
                'tax_banksn': '',
                'tax_num': '',
                'tax_mobile': '',
                'tax_address': '',
                'contacts-TOTAL_FORMS': '0',
                'contacts-INITIAL_FORMS': '0',
                'contacts-MIN_NUM_FORMS': '0',
                'contacts-MAX_NUM_FORMS': '1000',
            },
            HTTP_USER_AGENT='test-client',
        )

        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(name='行业客户')
        self.assertEqual(customer.industry_id, 3)

    def test_customer_detail_displays_industry_label_instead_of_id(self):
        customer = Customer.objects.create(
            name='行业展示客户',
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
            industry_id=4,
        )

        response = self.client.get(reverse('customer:customer_detail', args=[customer.id]))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn(CUSTOMER_INDUSTRY_CHOICES[4], content)
        self.assertNotIn('<td>4</td>', content)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class CustomerStatusDisplayTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username='customer-status-user',
            email='customer-status@example.com',
            password='password123',
            name='客户状态测试员',
        )
        self.client.force_login(self.user)

    def test_customer_create_form_does_not_render_empty_customer_status_field(self):
        response = self.client.get(reverse('customer:customer_create'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('客户状态', content)

    def test_customer_detail_displays_meaningful_customer_status(self):
        customer = Customer.objects.create(
            name='状态展示客户',
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )

        response = self.client.get(reverse('customer:customer_detail', args=[customer.id]))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('个人客户', content)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class CustomerAutoCreateOptionTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username='customer-auto-create-user',
            email='customer-auto-create@example.com',
            password='password123',
            name='客户自动创建测试员',
        )
        self.client.force_login(self.user)

    def test_customer_create_form_renders_auto_create_options(self):
        response = self.client.get(reverse('customer:customer_create'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('自动创建关联信息', content)
        self.assertIn('auto_create_contract', content)
        self.assertIn('auto_create_order', content)
        self.assertIn('auto_create_project', content)

    def test_customer_create_does_not_auto_create_related_records_by_default(self):
        response = self.client.post(
            reverse('customer:customer_create'),
            {
                'name': '默认不联动客户',
                'customer_source': '',
                'grade_id': '',
                'industry_id': '',
                'services_id': '',
                'province': '',
                'city': '',
                'district': '',
                'town': '',
                'address': '',
                'content': '',
                'market': '',
                'remark': '',
                'tax_bank': '',
                'tax_banksn': '',
                'tax_num': '',
                'tax_mobile': '',
                'tax_address': '',
                'contacts-TOTAL_FORMS': '0',
                'contacts-INITIAL_FORMS': '0',
                'contacts-MIN_NUM_FORMS': '0',
                'contacts-MAX_NUM_FORMS': '1000',
            },
            HTTP_USER_AGENT='test-client',
        )

        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(name='默认不联动客户')
        self.assertEqual(CustomerContract.objects.filter(customer=customer, auto_generated=True).count(), 0)
        self.assertEqual(Contract.objects.filter(customer_id=customer.id, auto_generated=True).count(), 0)
        self.assertEqual(CustomerOrder.objects.filter(customer=customer, auto_generated=True).count(), 0)
        self.assertEqual(Project.objects.filter(customer=customer, auto_generated=True).count(), 0)

    def test_customer_create_only_generates_checked_related_records(self):
        response = self.client.post(
            reverse('customer:customer_create'),
            {
                'name': '按需联动客户',
                'customer_source': '',
                'grade_id': '',
                'industry_id': '',
                'services_id': '',
                'province': '',
                'city': '',
                'district': '',
                'town': '',
                'address': '',
                'content': '',
                'market': '',
                'remark': '',
                'tax_bank': '',
                'tax_banksn': '',
                'tax_num': '',
                'tax_mobile': '',
                'tax_address': '',
                'contacts-TOTAL_FORMS': '0',
                'contacts-INITIAL_FORMS': '0',
                'contacts-MIN_NUM_FORMS': '0',
                'contacts-MAX_NUM_FORMS': '1000',
                'auto_create_contract': 'on',
                'auto_create_project': 'on',
            },
            HTTP_USER_AGENT='test-client',
        )

        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(name='按需联动客户')
        self.assertEqual(CustomerContract.objects.filter(customer=customer, auto_generated=True).count(), 1)
        self.assertEqual(Contract.objects.filter(customer_id=customer.id, auto_generated=True).count(), 1)
        self.assertEqual(CustomerOrder.objects.filter(customer=customer, auto_generated=True).count(), 0)
        self.assertEqual(Project.objects.filter(customer=customer, auto_generated=True).count(), 1)

    def test_customer_order_form_renders_auto_create_options(self):
        customer = Customer.objects.create(
            name='订单联动客户',
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )

        response = self.client.get(
            reverse('customer:customer_order_create'),
            {'customer_id': customer.id},
        )
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('自动创建关联信息', content)
        self.assertIn('auto_create_contract', content)
        self.assertIn('auto_create_project', content)

    def test_customer_order_create_does_not_auto_create_related_records_by_default(self):
        customer = Customer.objects.create(
            name='订单默认不联动客户',
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )

        response = self.client.post(
            reverse('customer:customer_order_create'),
            {
                'customer_id': str(customer.id),
                'order_number': 'ORD-DEFAULT-001',
                'product_name': '测试产品A',
                'amount': '199.00',
                'order_date': '2026-07-02',
                'status': 'pending',
                'description': '',
                'remark': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['status'], 'success')
        order = CustomerOrder.objects.get(order_number='ORD-DEFAULT-001')
        self.assertEqual(CustomerContract.objects.filter(customer=customer, auto_generated=True).count(), 0)
        self.assertEqual(Project.objects.filter(customer=customer, auto_generated=True).count(), 0)
        self.assertFalse(order.auto_generated)

    def test_customer_order_create_only_generates_checked_related_records(self):
        customer = Customer.objects.create(
            name='订单按需联动客户',
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )

        response = self.client.post(
            reverse('customer:customer_order_create'),
            {
                'customer_id': str(customer.id),
                'order_number': 'ORD-SELECT-001',
                'product_name': '测试产品B',
                'amount': '299.00',
                'order_date': '2026-07-02',
                'status': 'confirmed',
                'description': '',
                'remark': '',
                'auto_create_contract': 'on',
                'auto_create_project': 'on',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(CustomerContract.objects.filter(customer=customer, auto_generated=True).count(), 1)
        self.assertEqual(Project.objects.filter(customer=customer, auto_generated=True).count(), 1)
