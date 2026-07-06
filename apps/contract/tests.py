import shutil
import tempfile
import json
import io
import zipfile
import fitz

from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.contract.models import Contract, ContractAIReview, ContractLegalConsultRecord
from apps.contract.ai_review_views import (
    ai_review_page,
    ai_review_history_page,
    ai_contract_file_parse_api,
    ai_contract_review_api,
    ai_contract_review_preview_api,
    ai_contract_review_detail_api,
    ai_contract_review_status_api,
    ai_contract_review_history_api,
    ai_contract_quick_review_api,
    ai_legal_consultation_api,
    ai_legal_consultation_history_api,
)
from apps.contract.contract_review_service import ContractReviewService, parse_contract_file
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
        self.client.force_login(self.user, backend='apps.user.auth_backend.AdminAuthBackend')
        session = self.client.session
        session['admin_id'] = self.user.id
        session['admin_name'] = self.user.name or self.user.username
        session['admin_username'] = self.user.username
        session.save()
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

    @patch('docx.Document', side_effect=Exception('not a standard docx'))
    def test_parse_contract_file_falls_back_to_ooxml_text_extraction(self, mock_document):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            zf.writestr(
                'word/document.xml',
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>兜底提取的合同正文</w:t></w:r></w:p></w:body></w:document>'
            )
        buffer.seek(0)

        uploaded = SimpleUploadedFile(
            'fallback.docx',
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

        text = parse_contract_file(uploaded)

        self.assertIn('兜底提取的合同正文', text)

    @patch('apps.contract.contract_review_service._ocr_pdf_page_with_ai', create=True)
    def test_parse_contract_file_uses_ai_ocr_for_scanned_pdf(self, mock_ocr_page):
        pdf = io.BytesIO()
        doc = fitz.open()
        doc.new_page(width=595, height=842)
        doc.save(pdf)
        doc.close()
        pdf.seek(0)

        mock_ocr_page.return_value = '扫描件合同正文 OCR 识别结果'
        uploaded = SimpleUploadedFile(
            'scanned.pdf',
            pdf.read(),
            content_type='application/pdf'
        )

        result = parse_contract_file(uploaded, include_meta=True)

        self.assertEqual(result['text'], '扫描件合同正文 OCR 识别结果')
        self.assertTrue(result['ocr_used'])
        self.assertEqual(result['parse_method'], 'pdf_ocr')
        self.assertIn('OCR', result['accuracy_notice'])

    @patch('docx.Document', side_effect=Exception('not a word file, content type is themeManager+xml'))
    def test_ai_contract_file_parse_api_falls_back_to_ooxml_text_extraction(self, mock_document):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            zf.writestr(
                'custom/themeManager.xml',
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<root><p>主题包中的合同正文</p><p>合同金额：85000元</p></root>'
            )
            zf.writestr(
                'word/document.xml',
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>接口兜底提取成功</w:t></w:r></w:p></w:body></w:document>'
            )
        buffer.seek(0)

        uploaded = SimpleUploadedFile(
            'theme-fallback.docx',
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

        request = self.factory.post(
            reverse('contract:ai_contract_file_parse'),
            {'file': uploaded, 'contract_id': ''}
        )
        request.user = self.user
        response = ai_contract_file_parse_api(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self.assertIn('接口兜底提取成功', payload['data']['full_text'])
        self.assertGreater(payload['data']['text_length'], 0)

    @patch('apps.contract.contract_review_service._ocr_pdf_page_with_ai', create=True)
    def test_ai_contract_file_parse_api_returns_ocr_metadata_for_scanned_pdf(self, mock_ocr_page):
        pdf = io.BytesIO()
        doc = fitz.open()
        doc.new_page(width=595, height=842)
        doc.save(pdf)
        doc.close()
        pdf.seek(0)

        mock_ocr_page.return_value = '扫描件合同识别文本'
        uploaded = SimpleUploadedFile(
            'scanned.pdf',
            pdf.read(),
            content_type='application/pdf'
        )

        request = self.factory.post(
            reverse('contract:ai_contract_file_parse'),
            {'file': uploaded, 'contract_id': ''}
        )
        request.user = self.user
        response = ai_contract_file_parse_api(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['full_text'], '扫描件合同识别文本')
        self.assertTrue(payload['data']['ocr_used'])
        self.assertEqual(payload['data']['parse_method'], 'pdf_ocr')
        self.assertIn('人工复核', payload['data']['accuracy_notice'])
        self.assertTrue(payload['data']['focus_review_fields'])
        self.assertEqual(payload['data']['focus_review_fields'][0]['field'], '合同编号')

    @patch('apps.contract.contract_review_service._ocr_pdf_page_with_ai', create=True)
    def test_ai_contract_file_parse_api_updates_contract_without_status_field_error(self, mock_ocr_page):
        contract = Contract.objects.create(
            code='HT-20260703-UPLOAD-001',
            name='上传联调合同',
            customer='测试客户',
            customer_id=100,
            cost='8500.00',
            sign_time=1783036800,
            start_time=1783036800,
            end_time=1785715200,
            admin_id=self.user.id,
        )
        pdf = io.BytesIO()
        doc = fitz.open()
        doc.new_page(width=595, height=842)
        doc.save(pdf)
        doc.close()
        pdf.seek(0)

        mock_ocr_page.return_value = '扫描件更新后的合同正文'
        uploaded = SimpleUploadedFile(
            'linked-scanned.pdf',
            pdf.read(),
            content_type='application/pdf'
        )

        request = self.factory.post(
            reverse('contract:ai_contract_file_parse'),
            {'file': uploaded, 'contract_id': str(contract.id)}
        )
        request.user = self.user
        response = ai_contract_file_parse_api(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)

        contract.refresh_from_db()
        self.assertEqual(contract.content, '扫描件更新后的合同正文')
        self.assertTrue(bool(contract.scan_file))

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

    @patch('apps.contract.ai_review_views.parse_contract_file')
    def test_ai_review_page_shows_ocr_notice_for_auto_loaded_attachment(self, mock_parse_contract_file):
        contract = Contract.objects.create(
            code='HT-20260703-ATTACH-001',
            name='扫描件附件提示合同',
            customer='测试客户',
            customer_id=100,
            cost='8500.00',
            subject_id='深圳市平静科技有限公司',
            sign_time=1783036800,
            start_time=1783036800,
            end_time=1785715200,
            admin_id=self.user.id,
            content='',
        )
        contract.scan_file.save(
            'scanned-auto.pdf',
            SimpleUploadedFile(
                'scanned-auto.pdf',
                b'%PDF-1.4 fake scanned pdf',
                content_type='application/pdf'
            )
        )
        contract.content = ''
        contract.save(update_fields=['content'])

        mock_parse_contract_file.return_value = {
            'text': '扫描件自动带入的合同正文',
            'parse_method': 'pdf_ocr',
            'ocr_used': True,
            'accuracy_notice': '当前文件疑似扫描件，已启用 OCR 识别。请人工复核金额、日期、签署主体等关键信息。',
        }

        request = self.factory.get(reverse('contract:ai_review_page', args=[contract.id]))
        request.user = self.user
        response = ai_review_page(request, contract.id)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('扫描件自动带入的合同正文', html)
        self.assertIn('请人工复核金额、日期、签署主体等关键信息', html)
        self.assertIn('OCR重点复核', html)
        self.assertIn('合同金额', html)

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

    @patch('apps.contract.ai_review_views.contract_review_service.quick_review')
    def test_quick_review_api_returns_normalized_payload(self, mock_quick_review):
        mock_quick_review.return_value = {
            'risk_level': 'medium',
            'key_risks': ['付款节点未明确', '违约责任不对等'],
            'brief_summary': '合同存在中等风险，建议补充付款和违约条款细节。'
        }

        request = self.factory.post(
            reverse('contract:ai_contract_quick_review'),
            data='{"contract_text":"甲方应于验收后付款，乙方承担违约责任。"}',
            content_type='application/json'
        )
        request.user = self.user
        response = ai_contract_quick_review_api(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['risk_level'], 'medium')
        self.assertIn('付款节点未明确', payload['data']['key_risks'])
        self.assertIn('中等风险', payload['data']['brief_summary'])

    @patch('apps.contract.ai_review_views.contract_review_service.quick_review')
    def test_quick_review_api_creates_history_record_when_contract_id_provided(self, mock_quick_review):
        mock_quick_review.return_value = {
            'risk_level': 'high',
            'key_risks': ['补偿金额可能低于法定标准', '违约责任不对等'],
            'brief_summary': '建议先补足关键条款，再进入完整审查。'
        }
        contract = Contract.objects.create(
            code='HT-20260703-001',
            name='快速审查留痕合同',
            customer='测试客户',
            customer_id=100,
            cost='8800.00',
            sign_time=1783036800,
            start_time=1783036800,
            end_time=1785715200,
            admin_id=self.user.id,
        )

        request = self.factory.post(
            reverse('contract:ai_contract_quick_review'),
            data=json.dumps({
                'contract_id': contract.id,
                'contract_text': '甲方支付8500元解除劳动关系，乙方违约需双倍返还。',
                'our_role': '甲方 - 深圳市平静科技有限公司',
                'core_demands': '控制解除协议中的补偿和违约风险',
            }),
            content_type='application/json'
        )
        request.user = self.user
        response = ai_contract_quick_review_api(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)

        review = ContractAIReview.objects.get(contract=contract)
        self.assertEqual(review.review_type, 'quick')
        self.assertEqual(review.overall_risk_level, 'high')
        self.assertEqual(review.overall_summary, '建议先补足关键条款，再进入完整审查。')
        self.assertEqual(review.contract_info['our_role'], '甲方 - 深圳市平静科技有限公司')
        self.assertEqual(review.contract_info['core_demands'], '控制解除协议中的补偿和违约风险')
        self.assertIn('补偿金额可能低于法定标准', review.raw_response)
        raw_response = json.loads(review.raw_response)
        self.assertIn('focus_review_fields', raw_response)
        self.assertEqual(raw_response['focus_review_fields'][0]['field'], '合同编号')

    @patch('apps.contract.ai_review_views.contract_review_service.quick_review')
    def test_review_preview_api_returns_preliminary_result_without_creating_history(self, mock_quick_review):
        mock_quick_review.return_value = {
            'risk_level': 'medium',
            'key_risks': ['付款节点未明确', '签订时间待核对'],
            'brief_summary': '建议先关注付款与签署时间字段。'
        }
        contract = Contract.objects.create(
            code='HT-20260703-PREVIEW-001',
            name='预评估合同',
            customer='测试客户A',
            customer_id=101,
            cost='9800.00',
            subject_id='深圳市平静科技有限公司',
            sign_time=1783036800,
            start_time=1783036800,
            end_time=1785715200,
            admin_id=self.user.id,
        )

        request = self.factory.post(
            reverse('contract:ai_contract_review_preview', args=[contract.id]),
            data=json.dumps({
                'contract_text': (
                    '合同编号：HT-20260703-PREVIEW-001\n'
                    '合同名称：预评估合同\n'
                    '甲方：深圳市平静科技有限公司\n'
                    '乙方：测试客户A\n'
                    '合同金额：9800元\n'
                    '甲方应于验收后付款。'
                ),
                'our_role': '甲方 - 深圳市平静科技有限公司',
                'core_demands': '先快速看风险，再补全逐条审查'
            }),
            content_type='application/json'
        )
        request.user = self.user
        response = ai_contract_review_preview_api(request, contract.id)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self.assertTrue(payload['data']['pending_full_review'])
        self.assertEqual(payload['data']['quick_review_result']['risk_level'], 'medium')
        self.assertEqual(payload['data']['overall_assessment']['risk_level'], 'medium')
        self.assertTrue(payload['data']['focus_review_fields'])
        self.assertTrue(payload['data']['data_cross_check'])
        self.assertEqual(ContractAIReview.objects.count(), 0)

    @patch('apps.contract.ai_review_views._start_contract_full_review_job')
    def test_full_review_api_starts_background_job_and_returns_pending_status(self, mock_start_job):
        contract = Contract.objects.create(
            code='HT-20260703-ASYNC-001',
            name='异步审查合同',
            customer='测试客户B',
            customer_id=102,
            cost='15800.00',
            sign_time=1783036800,
            start_time=1783036800,
            end_time=1785715200,
            admin_id=self.user.id,
        )

        request = self.factory.post(
            reverse('contract:ai_contract_review', args=[contract.id]),
            data=json.dumps({
                'contract_text': '第一条 付款条款\n甲方于验收后付款。\n第二条 违约责任\n乙方违约承担责任。',
                'our_role': '甲方',
                'core_demands': '先返回任务状态'
            }),
            content_type='application/json'
        )
        request.user = self.user
        response = ai_contract_review_api(request, contract.id)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self.assertTrue(payload['data']['pending'])
        self.assertIn(payload['data']['status'], ['queued', 'running'])

        review = ContractAIReview.objects.get(contract=contract)
        self.assertEqual(review.review_type, 'full')
        self.assertEqual(review.overall_summary, 'AI正在生成逐条审查意见，请稍候刷新查看。')
        self.assertTrue(mock_start_job.called)

    def test_review_status_api_returns_current_review_progress(self):
        contract = Contract.objects.create(
            code='HT-20260703-STATUS-001',
            name='状态查询合同',
            customer='测试客户C',
            customer_id=103,
            cost='16800.00',
            sign_time=1783036800,
            start_time=1783036800,
            end_time=1785715200,
            admin_id=self.user.id,
        )
        review = ContractAIReview.objects.create(
            contract=contract,
            review_version=1,
            review_type='full',
            contract_info={'contract_name': contract.name},
            overall_risk_level='unknown',
            overall_summary='AI正在生成逐条审查意见，请稍候刷新查看。',
            raw_response=json.dumps({'task_status': 'running'}, ensure_ascii=False),
            is_latest=True,
        )

        request = self.factory.get(reverse('contract:ai_contract_review_status', args=[review.id]))
        request.user = self.user
        response = ai_contract_review_status_api(request, review.id)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['review_id'], review.id)
        self.assertEqual(payload['data']['status'], 'running')
        self.assertTrue(payload['data']['pending'])

    def test_review_history_api_returns_full_and_quick_records(self):
        contract = Contract.objects.create(
            code='HT-20260703-002',
            name='审查历史合同',
            customer='测试客户',
            customer_id=100,
            cost='12000.00',
            sign_time=1783036800,
            start_time=1783036800,
            end_time=1785715200,
            admin_id=self.user.id,
        )
        full_review = ContractAIReview.objects.create(
            contract=contract,
            review_version=1,
            review_type='full',
            contract_info={'contract_name': contract.name},
            overall_risk_level='medium',
            overall_summary='完整审查提示付款条件需补充。',
            is_latest=False,
        )
        quick_review = ContractAIReview.objects.create(
            contract=contract,
            review_version=2,
            review_type='quick',
            contract_info={'contract_name': contract.name},
            overall_risk_level='high',
            overall_summary='快速评估发现补偿金额和违约责任风险。',
            is_latest=True,
        )

        request = self.factory.get(reverse('contract:ai_contract_review_history', args=[contract.id]))
        request.user = self.user
        response = ai_contract_review_history_api(request, contract.id)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        data = payload['data']
        self.assertEqual([item['id'] for item in data], [quick_review.id, full_review.id])
        self.assertEqual(data[0]['review_type'], 'quick')
        self.assertEqual(data[0]['review_type_label'], '快速评估')
        self.assertTrue(data[0]['is_latest'])
        self.assertEqual(data[0]['task_status'], 'completed')
        self.assertEqual(data[1]['review_type'], 'full')
        self.assertEqual(data[1]['review_type_label'], '完整审查')
        self.assertEqual(data[1]['task_status'], 'completed')

    def test_review_history_api_includes_pending_and_failed_task_status(self):
        contract = Contract.objects.create(
            code='HT-20260703-004',
            name='任务状态历史合同',
            customer='测试客户D',
            customer_id=104,
            cost='18800.00',
            sign_time=1783036800,
            start_time=1783036800,
            end_time=1785715200,
            admin_id=self.user.id,
        )
        failed_review = ContractAIReview.objects.create(
            contract=contract,
            review_version=1,
            review_type='full',
            contract_info={'contract_name': contract.name},
            overall_risk_level='unknown',
            overall_summary='详细审查生成失败，请重试。',
            raw_response=json.dumps({'task_status': 'failed', 'task_error': 'LLM timeout'}, ensure_ascii=False),
            is_latest=True,
        )
        running_review = ContractAIReview.objects.create(
            contract=contract,
            review_version=2,
            review_type='full',
            contract_info={'contract_name': contract.name},
            overall_risk_level='unknown',
            overall_summary='AI正在生成逐条审查意见，请稍候刷新查看。',
            raw_response=json.dumps({'task_status': 'running'}, ensure_ascii=False),
            is_latest=False,
        )

        request = self.factory.get(reverse('contract:ai_contract_review_history', args=[contract.id]))
        request.user = self.user
        response = ai_contract_review_history_api(request, contract.id)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        data = payload['data']
        self.assertEqual(data[0]['id'], running_review.id)
        self.assertEqual(data[0]['task_status'], 'running')
        self.assertEqual(data[1]['id'], failed_review.id)
        self.assertEqual(data[1]['task_status'], 'failed')
        self.assertEqual(data[1]['task_error'], 'LLM timeout')

    def test_review_history_page_renders_for_right_popup(self):
        contract = Contract.objects.create(
            code='HT-20260703-POPUP-001',
            name='右侧记录页合同',
            customer='测试客户F',
            customer_id=106,
            cost='22800.00',
            sign_time=1783036800,
            start_time=1783036800,
            end_time=1785715200,
            admin_id=self.user.id,
        )

        request = self.factory.get(reverse('contract:ai_review_history_page', args=[contract.id]))
        request.user = self.user
        response = ai_review_history_page(request, contract.id)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '合同审查记录')
        self.assertContains(response, contract.name)

    def test_review_detail_api_returns_quick_and_full_payloads(self):
        contract = Contract.objects.create(
            code='HT-20260703-003',
            name='审查详情合同',
            customer='测试客户',
            customer_id=100,
            cost='13600.00',
            sign_time=1783036800,
            start_time=1783036800,
            end_time=1785715200,
            admin_id=self.user.id,
        )
        quick_review = ContractAIReview.objects.create(
            contract=contract,
            review_version=1,
            review_type='quick',
            contract_info={'contract_name': contract.name, 'our_role': '甲方'},
            overall_risk_level='medium',
            overall_summary='快速评估提示付款节点未明确。',
            raw_response=json.dumps({
                'risk_level': 'medium',
                'brief_summary': '快速评估提示付款节点未明确。',
                'key_risks': ['付款节点未明确', '争议解决条款缺失'],
                'focus_review_fields': [
                    {'field': '合同金额', 'extracted_value': '8500元', 'system_value': '13600.00元', 'match': False, 'status': '⚠️ 不一致', 'detail': '金额不一致'}
                ]
            }, ensure_ascii=False),
            is_latest=False,
        )
        full_review = ContractAIReview.objects.create(
            contract=contract,
            review_version=2,
            review_type='full',
            contract_info={'contract_name': contract.name, 'our_role': '甲方'},
            overall_risk_level='high',
            overall_summary='完整审查提示违约责任不对等。',
            clause_reviews=[{'clause_no': '第二条', 'title': '违约责任', 'risk_level': 'high'}],
            review_conclusion=[{'clause_no': '第二条', 'action': '必须修改'}],
            final_recommendation='建议修改后签署',
            data_cross_check=[{'field': '合同金额', 'status': '⚠️ 不一致', 'match': False}],
            raw_response=json.dumps({
                'focus_review_fields': [
                    {'field': '合同金额', 'extracted_value': '8500元', 'system_value': '13600.00元', 'match': False, 'status': '⚠️ 不一致', 'detail': '金额不一致'},
                    {'field': '签订时间', 'extracted_value': '', 'system_value': '2026-07-03', 'match': False, 'status': '⊘ 原文未提及', 'detail': '合同原文中未识别到该字段，请人工核对。'}
                ]
            }, ensure_ascii=False),
            is_latest=True,
        )

        quick_request = self.factory.get(reverse('contract:ai_contract_review_detail', args=[quick_review.id]))
        quick_request.user = self.user
        quick_response = ai_contract_review_detail_api(quick_request, quick_review.id)

        full_request = self.factory.get(reverse('contract:ai_contract_review_detail', args=[full_review.id]))
        full_request.user = self.user
        full_response = ai_contract_review_detail_api(full_request, full_review.id)

        quick_payload = json.loads(quick_response.content.decode('utf-8'))['data']
        full_payload = json.loads(full_response.content.decode('utf-8'))['data']

        self.assertEqual(quick_payload['review_type'], 'quick')
        self.assertEqual(quick_payload['review_type_label'], '快速评估')
        self.assertEqual(quick_payload['quick_review_result']['key_risks'][0], '付款节点未明确')
        self.assertEqual(quick_payload['focus_review_fields'][0]['field'], '合同金额')
        self.assertEqual(quick_payload['focus_review_summary']['attention_count'], 1)
        self.assertEqual(full_payload['review_type'], 'full')
        self.assertEqual(full_payload['overall_assessment']['final_recommendation'], '建议修改后签署')
        self.assertEqual(full_payload['data_cross_check'][0]['field'], '合同金额')
        self.assertEqual(full_payload['focus_review_fields'][1]['field'], '签订时间')
        self.assertEqual(full_payload['focus_review_summary']['missing_count'], 1)
        self.assertEqual(full_payload['status'], 'completed')
        self.assertFalse(full_payload['failed'])

    def test_review_detail_api_includes_failed_task_state(self):
        contract = Contract.objects.create(
            code='HT-20260703-005',
            name='失败详情合同',
            customer='测试客户E',
            customer_id=105,
            cost='19800.00',
            sign_time=1783036800,
            start_time=1783036800,
            end_time=1785715200,
            admin_id=self.user.id,
        )
        review = ContractAIReview.objects.create(
            contract=contract,
            review_version=1,
            review_type='full',
            contract_info={'contract_name': contract.name, 'our_role': '甲方'},
            overall_risk_level='unknown',
            overall_summary='详细审查生成失败，请重试。',
            raw_response=json.dumps({'task_status': 'failed', 'task_error': 'upstream unavailable'}, ensure_ascii=False),
            is_latest=True,
        )

        request = self.factory.get(reverse('contract:ai_contract_review_detail', args=[review.id]))
        request.user = self.user
        response = ai_contract_review_detail_api(request, review.id)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))['data']
        self.assertEqual(payload['status'], 'failed')
        self.assertTrue(payload['failed'])
        self.assertFalse(payload['pending'])
        self.assertEqual(payload['task_error'], 'upstream unavailable')

    def test_contract_review_service_quick_review_accepts_direct_dict_payload(self):
        service = ContractReviewService()
        with patch.object(service.tool, '_call_ai', return_value={
            'risk_level': 'low',
            'key_risks': ['争议解决条款建议补充管辖地'],
            'brief_summary': '整体风险较低，但建议补充争议解决细节。'
        }):
            result = service.quick_review('本合同约定双方合作事项。')

        self.assertEqual(result['risk_level'], 'low')
        self.assertIn('争议解决条款', result['key_risks'][0])
        self.assertIn('整体风险较低', result['brief_summary'])

    def test_contract_review_service_review_contract_builds_fallback_when_ai_output_invalid(self):
        service = ContractReviewService()
        with patch.object(service.tool, '_call_ai', side_effect=[
            {'analysis': '分析处理过程中遇到问题，请稍后重试'},
            {'analysis': '仍然没有返回合法json'}
        ]):
            result = service.review_contract(
                contract_text='第一条 付款条款\n甲方应在收到发票后7日内付款。\n第二条 违约责任\n乙方违约应双倍赔偿。',
                contract_name='测试合同',
                our_role='甲方',
                core_demands='控制付款和违约风险',
            )

        self.assertEqual(result['contract_info']['contract_name'], '测试合同')
        self.assertTrue(result.get('fallback_used'))
        self.assertIn(result['overall_assessment']['risk_level'], ['medium', 'high'])
        self.assertGreater(len(result['clause_reviews']), 0)

    def test_contract_review_service_uses_parseable_quick_review_dict(self):
        service = ContractReviewService()
        with patch.object(service.tool, '_call_ai', return_value={
            'analysis': {
                'risk_level': 'high',
                'key_risks': ['金额不清晰', '违约责任不对等'],
                'brief_summary': '整体风险较高。'
            }
        }):
            result = service.quick_review('甲方应付款，乙方违约赔偿。')

        self.assertEqual(result['risk_level'], 'high')
        self.assertEqual(result['key_risks'][0], '金额不清晰')
        self.assertIn('整体风险较高', result['brief_summary'])

    def test_contract_review_service_splits_long_contract_and_merges_results(self):
        service = ContractReviewService()
        long_text = (
            "第一条 付款条款\n" + ("甲方应在验收后付款。" * 500) +
            "\n第二条 违约责任\n" + ("乙方违约应承担赔偿责任。" * 500)
        )
        def fake_ai_call(*args, **kwargs):
            prompt = kwargs.get('prompt', '') or ''
            if '第二条 违约责任' in prompt:
                return {
                    'contract_info': {'contract_name': '长合同'},
                    'overall_assessment': {'risk_level': 'high', 'summary': '第二段违约责任较重', 'final_recommendation': '建议修改后签署'},
                    'clause_reviews': [
                        {
                            'clause_no': '第二条',
                            'title': '违约责任',
                            'original_summary': '乙方违约应承担赔偿责任',
                            'risk_analysis': '违约责任不对等',
                            'risk_level': 'high',
                            'suggestion': '调整为对等责任'
                        }
                    ],
                    'review_conclusion': []
                }
            return {
                'contract_info': {'contract_name': '长合同'},
                'overall_assessment': {'risk_level': 'medium', 'summary': '第一段需关注付款条件', 'final_recommendation': '建议修改后签署'},
                'clause_reviews': [
                    {
                        'clause_no': '第一条',
                        'title': '付款条款',
                        'original_summary': '甲方应在验收后付款',
                        'risk_analysis': '付款触发条件不清晰',
                        'risk_level': 'medium',
                        'suggestion': '明确付款节点'
                    }
                ],
                'review_conclusion': []
            }

        with patch.object(service.tool, '_call_ai', side_effect=fake_ai_call) as mock_call:
            result = service.review_contract(
                contract_text=long_text,
                contract_name='长合同',
                our_role='甲方',
                core_demands='控制付款和违约风险',
            )

        self.assertGreaterEqual(mock_call.call_count, 2)
        self.assertEqual(result['overall_assessment']['risk_level'], 'high')
        self.assertEqual(len(result['clause_reviews']), 2)
        self.assertEqual(result['clause_reviews'][0]['clause_no'], '第一条')
        self.assertEqual(result['clause_reviews'][1]['clause_no'], '第二条')

    def test_contract_review_service_splits_single_oversized_clause_into_multiple_chunks(self):
        service = ContractReviewService()
        long_text = "第一条 服务内容\n" + ("甲方委托乙方提供持续交付服务，双方按月进行验收与结算。" * 900)

        chunks = service._split_contract_for_review(long_text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk['text'].strip() for chunk in chunks))
        self.assertTrue(all(len(chunk['text']) <= 7000 for chunk in chunks))

    def test_contract_review_service_skips_second_retry_when_ai_response_obviously_failed(self):
        service = ContractReviewService()
        with patch.object(service.tool, '_call_ai', return_value={'analysis': '分析处理过程中遇到问题，请稍后重试'}) as mock_call:
            result = service.review_contract(
                contract_text='第一条 付款条款\n甲方应在收到发票后7日内付款。',
                contract_name='测试合同',
                our_role='甲方',
                core_demands='控制付款风险',
            )

        self.assertEqual(mock_call.call_count, 1)
        self.assertTrue(result.get('fallback_used'))

    def test_contract_review_service_cross_reference_check_uses_local_extraction(self):
        service = ContractReviewService()
        text = (
            "合同名称：全员培训服务合同\n"
            "合同编号：HT-2026-1008\n"
            "甲方：深圳市平静科技有限公司\n"
            "乙方：客户公司H\n"
            "合同金额：80000元\n"
            "签订时间：2026年07月01日\n"
            "合同开始时间：2026年07月05日\n"
            "合同结束时间：2026年12月31日\n"
        )
        system_data = {
            "合同编号": "HT-2026-1008",
            "合同名称": "全员培训服务合同",
            "合同金额": "80000元",
            "客户名称": "客户公司H",
            "签约主体": "深圳市平静科技有限公司",
            "合同开始时间": "2026-07-05",
            "合同结束时间": "2026-12-31",
            "签订时间": "2026-07-01",
        }

        result = service.cross_reference_check(text, system_data)
        status_map = {item['field']: item for item in result}

        self.assertEqual(status_map['合同编号']['status'], '✅ 一致')
        self.assertEqual(status_map['合同金额']['status'], '✅ 一致')
        self.assertEqual(status_map['客户名称']['status'], '✅ 一致')
        self.assertEqual(status_map['签约主体']['status'], '✅ 一致')
        self.assertEqual(status_map['合同开始时间']['status'], '✅ 一致')
