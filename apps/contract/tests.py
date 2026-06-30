import shutil
import tempfile
import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.contract.models import Contract, ContractLegalConsultRecord
from apps.contract.ai_review_views import (
    ai_review_page,
    ai_legal_consultation_api,
    ai_legal_consultation_history_api,
)
from apps.user.models import Admin
from unittest.mock import patch


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
        self.factory = RequestFactory()

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

    def test_ai_review_page_prefills_existing_attachment_content(self):
        contract = Contract.objects.create(
            code='HT-20260630-001',
            name='AI审查附件自动带入合同',
            customer='测试客户',
            customer_id=100,
            cost='6800.00',
            subject_id='深圳市平静科技有限公司',
            sign_time=1782777600,
            start_time=1782777600,
            end_time=1785456000,
            admin_id=self.user.id,
            content='',
            remark='备注内容不应优先于附件',
        )
        contract.scan_file.save(
            'auto-review.txt',
            SimpleUploadedFile(
                'auto-review.txt',
                '这是附件中的合同正文'.encode('utf-8'),
                content_type='text/plain'
            )
        )
        contract.content = ''
        contract.save(update_fields=['content'])

        request = self.factory.get(reverse('contract:ai_review_page', args=[contract.id]))
        request.user = self.user
        response = ai_review_page(request, contract.id)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('已自动读取合同附件', html)
        self.assertIn('这是附件中的合同正文', html)
        self.assertIn('甲方 - 深圳市平静科技有限公司', html)

        contract.refresh_from_db()
        self.assertEqual(contract.content, '这是附件中的合同正文')

    @patch('apps.contract.ai_review_views.legal_consultation')
    def test_legal_consultation_api_creates_history_record(self, mock_legal_consultation):
        mock_legal_consultation.return_value = {
            'success': True,
            'question': '解除劳动合同怎么写？',
            'answer': '【整体结论】建议补充解除原因和补偿标准。'
        }
        contract = Contract.objects.create(
            code='HT-20260630-002',
            name='法律咨询历史合同',
            customer='测试客户',
            customer_id=100,
            cost='5000.00',
            sign_time=1782777600,
            start_time=1782777600,
            end_time=1785456000,
            admin_id=self.user.id,
        )

        request = self.factory.post(
            reverse('contract:ai_legal_consultation'),
            data='{"question":"解除劳动合同怎么写？","context":"员工主动离职","contract_id":%s}' % contract.id,
            content_type='application/json'
        )
        request.user = self.user
        response = ai_legal_consultation_api(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)

        record = ContractLegalConsultRecord.objects.get()
        self.assertEqual(record.user_id, self.user.id)
        self.assertEqual(record.contract_id, contract.id)
        self.assertEqual(record.query_type, 'consultation')
        self.assertEqual(record.question, '解除劳动合同怎么写？')
        self.assertEqual(record.context, '员工主动离职')
        self.assertIn('补充解除原因', record.answer)

    def test_legal_consultation_history_api_returns_latest_records(self):
        older = ContractLegalConsultRecord.objects.create(
            user=self.user,
            query_type='consultation',
            question='旧问题',
            answer='旧回答',
            success=True,
        )
        newer = ContractLegalConsultRecord.objects.create(
            user=self.user,
            query_type='knowledge',
            question='最新知识查询',
            answer='最新回答',
            success=True,
        )

        request = self.factory.get(reverse('contract:ai_legal_consultation_history'))
        request.user = self.user
        response = ai_legal_consultation_history_api(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        data = payload['data']
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['id'], newer.id)
        self.assertEqual(data[0]['query_type'], 'knowledge')
        self.assertEqual(data[1]['id'], older.id)
