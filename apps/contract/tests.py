import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.contract.models import Contract
from apps.user.models import Admin


TEST_MEDIA_ROOT = tempfile.mkdtemp()
TEST_MIDDLEWARE = [
    middleware for middleware in settings.MIDDLEWARE
    if middleware != 'apps.system.middleware.permission_middleware.PermissionMiddleware'
]


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT, MIDDLEWARE=TEST_MIDDLEWARE)
class ContractScanUploadTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = Admin.objects.create_user(
            username='contract-user',
            email='contract@example.com',
            password='password123'
        )
        self.client.force_login(self.user)

    def test_sales_contract_upload_saves_scan_file(self):
        scan_file = SimpleUploadedFile(
            'signed-contract.pdf',
            b'%PDF-1.4 signed contract scan',
            content_type='application/pdf'
        )

        response = self.client.post(reverse('contract:contract_sales_add'), {
            'code': 'HT-20260613-001',
            'name': '测试扫描件合同',
            'cate_id': '1',
            'types': '1',
            'customer_id': '100',
            'customer': '测试客户',
            'cost': '1200.00',
            'sign_time': '2026-06-13 09:00:00',
            'start_time': '2026-06-13 09:00:00',
            'end_time': '2026-07-13 09:00:00',
            'scan_file': scan_file,
        })

        self.assertEqual(response.json()['code'], 0)
        contract = Contract.objects.get(code='HT-20260613-001')
        self.assertTrue(contract.scan_file.name.startswith('contract_scans/'))
        with contract.scan_file.open('rb') as saved_file:
            self.assertEqual(saved_file.read(), b'%PDF-1.4 signed contract scan')

    def test_sales_contract_list_exposes_scan_preview_state(self):
        contract = Contract.objects.create(
            code='HT-20260613-002',
            name='列表扫描件合同',
            customer='测试客户',
            customer_id=100,
            cost='1200.00',
            sign_time=1781308800,
            start_time=1781308800,
            end_time=1783900800,
            admin_id=self.user.id,
        )
        contract.scan_file.save(
            'signed-contract.pdf',
            SimpleUploadedFile(
                'signed-contract.pdf',
                b'%PDF-1.4 signed contract scan',
                content_type='application/pdf'
            )
        )

        response = self.client.get(reverse('contract:contract_sales_datalist'))

        self.assertEqual(response.json()['code'], 0)
        row = response.json()['data'][0]
        self.assertTrue(row['has_scan_file'])
        self.assertIn('/media/contract_scans/', row['scan_file_url'])

    def test_sales_contract_page_renders_layui_toolbar_template(self):
        response = self.client.get(reverse('contract:contract_sales'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'contractToolBar')
