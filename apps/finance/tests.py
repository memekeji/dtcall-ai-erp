import json
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.contract.models import Supplier
from apps.customer.models import Customer, CustomerContract, CustomerOrder
from apps.finance.forms import PaymentForm
from apps.finance.models import (
    BankReconciliation,
    BankTransaction,
    Expense,
    FinanceAccount,
    FinanceStatus,
    Income,
    Invoice,
    InvoiceRequest,
    OrderFinanceRecord,
    Payment,
)
from apps.finance.services import IncomeService, PaymentService
from apps.user.models import Admin, SystemConfiguration


TEST_MIDDLEWARE = [
    middleware
    for middleware in settings.MIDDLEWARE
    if middleware
    not in {
        "apps.system.middleware.permission_middleware.PermissionMiddleware",
        "apps.system.middleware.database_setup_middleware.DatabaseSetupMiddleware",
    }
]


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class FinancePaymentFormTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username="finance-form-user",
            email="finance-form@example.com",
            password="password123",
            name="财务表单测试员",
            is_superuser=True,
        )
        self.customer = Customer.objects.create(
            name="测试客户",
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )

    def test_payment_form_requires_at_least_one_business_relation(self):
        form = PaymentForm(
            data={
                "amount": "120.50",
                "payment_date": "2026-07-07T10:30",
                "remark": "无关联付款",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("至少关联一项", "".join(form.non_field_errors()))

    def test_payment_form_allows_customer_only_relation(self):
        form = PaymentForm(
            data={
                "customer_id": str(self.customer.id),
                "amount": "200.00",
                "payment_date": "2026-07-07T11:00",
                "remark": "客户独立付款",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class FinanceInvoiceRequestWorkflowTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username="finance-workflow-user",
            email="finance-workflow@example.com",
            password="password123",
            name="财务流程测试员",
            is_superuser=True,
        )
        self.client.force_login(
            self.user, backend="apps.user.auth_backend.AdminAuthBackend"
        )
        session = self.client.session
        session["admin_id"] = self.user.id
        session["admin_name"] = self.user.name or self.user.username
        session["admin_username"] = self.user.username
        session.save()

        self.customer = Customer.objects.create(
            name="流程客户",
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )
        self.order = CustomerOrder.objects.create(
            customer=self.customer,
            order_number="ORD-FIN-001",
            product_name="实施服务",
            amount="8888.00",
            order_date=date(2026, 7, 7),
            status="confirmed",
            create_user=self.user,
            delete_time=0,
        )
        self.invoice_request = InvoiceRequest.objects.create(
            order_id=self.order.id,
            applicant_id=self.user.id,
            department_id=0,
            amount="1888.00",
            invoice_type=2,
            invoice_title="流程客户开票抬头",
            tax_number="TAX-001",
            reason="项目阶段验收申请开票",
            status="pending",
            create_time=1751875200,
        )

    def test_invoice_request_list_json_returns_resolved_business_fields(self):
        response = self.client.get("/finance/invoice-request/datalist/")
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["count"], 1)
        row = payload["data"][0]
        self.assertEqual(row["order_number"], "ORD-FIN-001")
        self.assertEqual(row["customer_name"], "流程客户")
        self.assertEqual(row["invoice_title"], "流程客户开票抬头")
        self.assertEqual(row["invoice_type_display"], "普通发票")
        self.assertEqual(row["applicant"], self.user.name)
        self.assertEqual(row["status_display"], "待审核")

    def test_invoice_request_detail_page_exists(self):
        response = self.client.get(
            f"/finance/invoice-request/detail/{self.invoice_request.id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "流程客户开票抬头")
        self.assertContains(response, "ORD-FIN-001")

    def test_invoice_request_approval_endpoint_approves_pending_request(self):
        response = self.client.post(
            "/finance/invoice-request/approval/",
            data='{"request_id": %s, "action": "approved", "comment": "同意开票"}'
            % self.invoice_request.id,
            content_type="application/json",
        )
        payload = response.json()

        self.invoice_request.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 0)
        self.assertEqual(self.invoice_request.status, "invoiced")
        self.assertGreater(self.invoice_request.invoice_id, 0)

    def test_invoice_request_approval_links_invoice_to_order_customer(self):
        response = self.client.post(
            "/finance/invoice-request/approval/",
            data='{"request_id": %s, "action": "approved", "comment": "同意开票"}'
            % self.invoice_request.id,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.invoice_request.refresh_from_db()
        invoice = Invoice.objects.get(id=self.invoice_request.invoice_id)
        self.assertEqual(invoice.customer_id, self.customer.id)
        self.assertEqual(invoice.remark, "项目阶段验收申请开票")


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class FinancePaymentAndExpenseWorkflowTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username="finance-payment-user",
            email="finance-payment@example.com",
            password="password123",
            name="财务付款测试员",
            is_superuser=True,
        )
        self.client.force_login(
            self.user, backend="apps.user.auth_backend.AdminAuthBackend"
        )
        self.customer = Customer.objects.create(
            name="付款客户",
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )
        self.expense = Expense.objects.create(
            code="BX20260707001",
            subject_id=1,
            admin_id=self.user.id,
            did=0,
            project_id=0,
            cost="500.00",
            income_month=202607,
            expense_time=1751846400,
            check_status=FinanceStatus.EXPENSE_CHECK_APPROVED,
            pay_status=FinanceStatus.PAY_STATUS_PENDING,
            create_time=1751875200,
        )

    def test_payment_list_json_includes_relation_summary(self):
        Payment.objects.create(
            customer_id=self.customer.id,
            amount="300.00",
            payment_date="2026-07-07 12:00:00",
            create_time=1751880000,
        )

        response = self.client.get("/finance/payment/datalist/")
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["count"], 1)
        row = payload["data"][0]
        self.assertEqual(row["customer_id"], self.customer.id)
        self.assertIn("客户：付款客户", row["relation_summary"])

    def test_payment_service_marks_approved_expense_as_paid(self):
        payment = PaymentService.create_payment(
            {
                "expense_id": self.expense.id,
                "amount": "500.00",
                "payment_date": "2026-07-07 13:00:00",
                "remark": "打款完成",
            },
            self.user,
        )

        self.expense.refresh_from_db()

        self.assertEqual(payment.expense_id, self.expense.id)
        self.assertEqual(self.expense.pay_status, FinanceStatus.PAY_STATUS_PAID)
        self.assertEqual(self.expense.pay_admin_id, self.user.id)

    def test_reimbursement_legacy_view_and_edit_routes_exist(self):
        detail_response = self.client.get(f"/finance/reimbursement/view/{self.expense.id}/")
        edit_response = self.client.get(f"/finance/reimbursement/edit/{self.expense.id}/")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(edit_response.status_code, 200)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class FinanceAutoBankTransactionTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username="finance-bank-user",
            email="finance-bank@example.com",
            password="password123",
            name="银行流水测试员",
            is_superuser=True,
        )
        self.account = FinanceAccount.objects.create(
            name="招商银行基本户",
            account_type="bank",
            bank_name="招商银行",
            account_no="6222000000001",
            current_balance=Decimal("1000.00"),
            opening_balance=Decimal("1000.00"),
            status="active",
            create_time=1751875200,
        )
        self.customer = Customer.objects.create(
            name="自动流水客户",
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )
        self.invoice = Invoice.objects.create(
            code="INV-BANK-001",
            customer_id=self.customer.id,
            amount=Decimal("500.00"),
            admin_id=self.user.id,
            invoice_type=2,
            invoice_title="自动流水客户",
            create_time=1751875200,
        )

    def test_income_creation_auto_generates_bank_transaction(self):
        income = IncomeService.create_income(
            {
                "invoice_id": self.invoice.id,
                "account_id": self.account.id,
                "amount": "500.00",
                "income_date": datetime(2026, 7, 7, 9, 0, 0),
                "remark": "银行回款",
            }
        )

        transaction = BankTransaction.objects.get(
            related_type="income", related_id=income.id
        )
        self.account.refresh_from_db()

        self.assertEqual(transaction.account_id, self.account.id)
        self.assertEqual(transaction.direction, "in")
        self.assertEqual(transaction.amount, Decimal("500.00"))
        self.assertEqual(transaction.counterparty, "自动流水客户")
        self.assertEqual(transaction.match_status, "matched")
        self.assertEqual(self.account.current_balance, Decimal("1500.00"))

    def test_payment_creation_auto_generates_bank_transaction(self):
        payment = PaymentService.create_payment(
            {
                "customer_id": self.customer.id,
                "account_id": self.account.id,
                "amount": "200.00",
                "payment_date": datetime(2026, 7, 7, 10, 0, 0),
                "remark": "对外付款",
            },
            self.user,
        )

        transaction = BankTransaction.objects.get(
            related_type="payment", related_id=payment.id
        )
        self.account.refresh_from_db()

        self.assertEqual(transaction.account_id, self.account.id)
        self.assertEqual(transaction.direction, "out")
        self.assertEqual(transaction.amount, Decimal("200.00"))
        self.assertEqual(transaction.counterparty, "自动流水客户")
        self.assertEqual(transaction.match_status, "matched")
        self.assertEqual(self.account.current_balance, Decimal("800.00"))


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class FinanceBankImportWorkflowTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username="finance-import-user",
            email="finance-import@example.com",
            password="password123",
            name="流水导入测试员",
            is_superuser=True,
        )
        self.client.force_login(
            self.user, backend="apps.user.auth_backend.AdminAuthBackend"
        )
        session = self.client.session
        session["admin_id"] = self.user.id
        session["admin_name"] = self.user.name or self.user.username
        session["admin_username"] = self.user.username
        session.save()

        self.account = FinanceAccount.objects.create(
            name="工商银行一般户",
            account_type="bank",
            bank_name="工商银行",
            account_no="6222000000002",
            current_balance=Decimal("0"),
            opening_balance=Decimal("0"),
            status="active",
            create_time=1751875200,
        )

    def test_bank_transaction_import_auto_creates_related_records_without_duplicates(self):
        payload = {
            "account_id": self.account.id,
            "auto_create_related": True,
            "rows": [
                {
                    "transaction_no": "TXN-1001",
                    "transaction_date": "2026-07-07 09:30:00",
                    "direction": "in",
                    "amount": "3000.00",
                    "counterparty": "华北科技有限公司",
                    "customer_name": "华北科技有限公司",
                    "order_number": "ORD-IMPORT-001",
                    "contract_number": "HT-IMPORT-001",
                    "invoice_code": "INV-IMPORT-001",
                    "purpose": "项目回款",
                },
                {
                    "transaction_no": "TXN-1002",
                    "transaction_date": "2026-07-07 10:30:00",
                    "direction": "out",
                    "amount": "1200.00",
                    "counterparty": "深圳材料供应商",
                    "supplier_name": "深圳材料供应商",
                    "purpose": "采购付款",
                },
                {
                    "transaction_no": "TXN-1001",
                    "transaction_date": "2026-07-07 09:30:00",
                    "direction": "in",
                    "amount": "3000.00",
                    "counterparty": "华北科技有限公司",
                    "customer_name": "华北科技有限公司",
                    "order_number": "ORD-IMPORT-001",
                    "contract_number": "HT-IMPORT-001",
                    "invoice_code": "INV-IMPORT-001",
                    "purpose": "项目回款",
                },
            ],
        }

        response = self.client.post(
            "/finance/advanced/bank-transaction/import/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["code"], 0)
        self.assertEqual(BankTransaction.objects.count(), 2)
        self.assertEqual(Customer.objects.filter(name="华北科技有限公司").count(), 1)
        self.assertEqual(
            CustomerContract.objects.filter(contract_number="HT-IMPORT-001").count(), 1
        )
        self.assertEqual(
            CustomerOrder.objects.filter(order_number="ORD-IMPORT-001").count(), 1
        )
        self.assertEqual(Invoice.objects.filter(code="INV-IMPORT-001").count(), 1)
        self.assertEqual(Supplier.objects.filter(name="深圳材料供应商").count(), 1)
        self.assertEqual(body["data"]["created_count"], 2)
        self.assertEqual(body["data"]["skipped_count"], 1)

    def test_bank_transaction_import_page_renders_upload_controls(self):
        response = self.client.get("/finance/advanced/bank-transaction/import/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "导入银行流水")
        self.assertContains(response, 'name="file"')
        self.assertContains(response, "auto_create_related")
        self.assertContains(response, self.account.name)

    def test_bank_transaction_import_accepts_csv_upload(self):
        upload = SimpleUploadedFile(
            "bank-transaction.csv",
            (
                "transaction_no,transaction_date,direction,amount,counterparty,"
                "customer_name,order_number,contract_number,invoice_code,purpose\n"
                "TXN-CSV-001,2026-07-07 09:30:00,in,5000.00,浦东软件有限公司,"
                "浦东软件有限公司,ORD-CSV-001,HT-CSV-001,INV-CSV-001,技术服务回款\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            "/finance/advanced/bank-transaction/import/",
            data={
                "account_id": str(self.account.id),
                "auto_create_related": "1",
                "file": upload,
            },
        )
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["created_count"], 1)
        self.assertEqual(BankTransaction.objects.filter(transaction_no="TXN-CSV-001").count(), 1)
        self.assertEqual(Customer.objects.filter(name="浦东软件有限公司").count(), 1)
        self.assertEqual(
            CustomerContract.objects.filter(contract_number="HT-CSV-001").count(), 1
        )
        self.assertEqual(
            CustomerOrder.objects.filter(order_number="ORD-CSV-001").count(), 1
        )
        self.assertEqual(Invoice.objects.filter(code="INV-CSV-001").count(), 1)

    def test_bank_import_template_endpoint_returns_and_saves_alias_config(self):
        response = self.client.get("/finance/advanced/bank-import-template/")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["code"], 0)
        self.assertIn("transaction_no", body["data"]["aliases"])

        save_response = self.client.post(
            "/finance/advanced/bank-import-template/",
            data=json.dumps(
                {
                    "aliases": {
                        "transaction_no": ["自定义流水号", "流水号"],
                        "transaction_date": ["交易发生时间"],
                    }
                }
            ),
            content_type="application/json",
        )
        save_body = save_response.json()

        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(save_body["code"], 0)
        config = SystemConfiguration.objects.get(key="finance_bank_import_field_aliases")
        saved_aliases = json.loads(config.value)
        self.assertIn("自定义流水号", saved_aliases["transaction_no"])
        self.assertIn("交易发生时间", saved_aliases["transaction_date"])

    def test_bank_transaction_import_uses_configured_field_aliases(self):
        SystemConfiguration.objects.create(
            key="finance_bank_import_field_aliases",
            value=json.dumps(
                {
                    "transaction_no": ["自定义流水号"],
                    "transaction_date": ["交易发生时间"],
                    "direction": ["收支标记"],
                    "amount": ["本次金额"],
                    "counterparty": ["往来户名"],
                    "customer_name": ["客户全称"],
                    "order_number": ["销售单号"],
                    "contract_number": ["商务合同号"],
                    "invoice_code": ["票据编号"],
                    "purpose": ["业务说明"],
                },
                ensure_ascii=False,
            ),
            description="银行导入字段别名配置",
            is_active=True,
        )
        upload = SimpleUploadedFile(
            "bank-transaction-custom.csv",
            (
                "自定义流水号,交易发生时间,收支标记,本次金额,往来户名,客户全称,销售单号,商务合同号,票据编号,业务说明\n"
                "TXN-CUSTOM-001,2026-07-07 16:20:00,in,8800.00,华东智造有限公司,华东智造有限公司,ORD-CUSTOM-001,HT-CUSTOM-001,INV-CUSTOM-001,定制项目回款\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            "/finance/advanced/bank-transaction/import/",
            data={
                "account_id": str(self.account.id),
                "auto_create_related": "1",
                "file": upload,
            },
        )
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["created_count"], 1)
        transaction = BankTransaction.objects.get(transaction_no="TXN-CUSTOM-001")
        self.assertEqual(transaction.counterparty, "华东智造有限公司")
        self.assertEqual(Customer.objects.filter(name="华东智造有限公司").count(), 1)

    def test_bank_reconciliation_import_returns_mismatches_and_detail_record(self):
        customer = Customer.objects.create(
            name="对账客户",
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )
        invoice = Invoice.objects.create(
            code="INV-REC-001",
            customer_id=customer.id,
            amount=Decimal("1000.00"),
            admin_id=self.user.id,
            invoice_type=2,
            invoice_title="对账客户",
            create_time=1751875200,
        )
        IncomeService.create_income(
            {
                "invoice_id": invoice.id,
                "account_id": self.account.id,
                "amount": "1000.00",
                "income_date": datetime(2026, 7, 7, 9, 30, 0),
                "remark": "对账测试回款",
            }
        )

        response = self.client.post(
            "/finance/advanced/bank-reconciliation/import/",
            data=json.dumps(
                {
                    "account_id": self.account.id,
                    "period": "2026-07",
                    "bank_balance": "1300.00",
                    "rows": [
                        {
                            "transaction_no": "REC-001",
                            "transaction_date": "2026-07-07 09:30:00",
                            "direction": "in",
                            "amount": "1000.00",
                            "counterparty": "对账客户",
                            "invoice_code": "INV-REC-001",
                            "purpose": "回款",
                        },
                        {
                            "transaction_no": "REC-002",
                            "transaction_date": "2026-07-07 11:00:00",
                            "direction": "out",
                            "amount": "300.00",
                            "counterparty": "未知供应商",
                            "purpose": "未知付款",
                        },
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["summary"]["matched_count"], 1)
        self.assertEqual(body["data"]["summary"]["mismatch_count"], 1)

        reconciliation = BankReconciliation.objects.get(id=body["data"]["reconciliation_id"])
        detail_response = self.client.get(
            f"/finance/advanced/bank-reconciliation/{reconciliation.id}/compare/"
        )
        detail = detail_response.json()

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail["code"], 0)
        self.assertEqual(len(detail["data"]["items"]), 2)
        mismatch_item = [
            item for item in detail["data"]["items"] if item["transaction_no"] == "REC-002"
        ][0]
        self.assertEqual(mismatch_item["status"], "mismatch")
        self.assertTrue(mismatch_item["system_records"])

    def test_bank_reconciliation_import_page_renders_upload_controls(self):
        response = self.client.get("/finance/advanced/bank-reconciliation/import/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "导入银行对账")
        self.assertContains(response, 'name="file"')
        self.assertContains(response, 'name="period"')
        self.assertContains(response, 'name="bank_balance"')
        self.assertContains(response, self.account.name)

    def test_bank_reconciliation_import_accepts_csv_upload(self):
        customer = Customer.objects.create(
            name="CSV对账客户",
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )
        invoice = Invoice.objects.create(
            code="INV-REC-CSV-001",
            customer_id=customer.id,
            amount=Decimal("700.00"),
            admin_id=self.user.id,
            invoice_type=2,
            invoice_title="CSV对账客户",
            create_time=1751875200,
        )
        IncomeService.create_income(
            {
                "invoice_id": invoice.id,
                "account_id": self.account.id,
                "amount": "700.00",
                "income_date": datetime(2026, 7, 7, 9, 40, 0),
                "remark": "CSV对账回款",
            }
        )
        upload = SimpleUploadedFile(
            "bank-reconciliation.csv",
            (
                "transaction_no,transaction_date,direction,amount,counterparty,invoice_code,purpose\n"
                "REC-CSV-001,2026-07-07 09:40:00,in,700.00,CSV对账客户,INV-REC-CSV-001,回款\n"
                "REC-CSV-002,2026-07-07 12:00:00,out,200.00,未知对方,,手续费\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )

        response = self.client.post(
            "/finance/advanced/bank-reconciliation/import/",
            data={
                "account_id": str(self.account.id),
                "period": "2026-07",
                "bank_balance": "500.00",
                "file": upload,
            },
        )
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["summary"]["matched_count"], 1)
        self.assertEqual(body["data"]["summary"]["mismatch_count"], 1)
        reconciliation = BankReconciliation.objects.get(id=body["data"]["reconciliation_id"])
        self.assertEqual(reconciliation.period, "2026-07")


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class FinanceCrossModuleSyncTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username="finance-sync-user",
            email="finance-sync@example.com",
            password="password123",
            name="联动修复测试员",
            is_superuser=True,
        )
        self.customer = Customer.objects.create(
            name="联动客户",
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )
        self.contract = CustomerContract.objects.create(
            customer=self.customer,
            contract_number="HT-SYNC-001",
            name="联动合同",
            amount=Decimal("8888.00"),
            sign_date=date(2026, 7, 7),
            status="signed",
            create_user=self.user,
            delete_time=0,
        )

    def test_customer_order_creation_auto_creates_order_finance_record(self):
        order = CustomerOrder.objects.create(
            customer=self.customer,
            contract=self.contract,
            order_number="ORD-SYNC-001",
            product_name="联动产品",
            amount=Decimal("8888.00"),
            order_date=date(2026, 7, 7),
            status="confirmed",
            create_user=self.user,
            delete_time=0,
        )

        finance_record = OrderFinanceRecord.objects.filter(order_id=order.id).first()
        self.assertIsNotNone(finance_record)
        self.assertEqual(finance_record.total_amount, Decimal("8888.00"))


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class FinancePageSmokeTests(TestCase):
    def setUp(self):
        self.user = Admin.objects.create_user(
            username="finance-page-user",
            email="finance-page@example.com",
            password="password123",
            name="财务页面测试员",
            is_superuser=True,
        )
        self.client.force_login(
            self.user, backend="apps.user.auth_backend.AdminAuthBackend"
        )
        session = self.client.session
        session["admin_id"] = self.user.id
        session["admin_name"] = self.user.name or self.user.username
        session["admin_username"] = self.user.username
        session.save()

        self.customer = Customer.objects.create(
            name="页面客户",
            belong_uid=self.user.id,
            admin_id=self.user.id,
            delete_time=0,
        )
        self.order = CustomerOrder.objects.create(
            customer=self.customer,
            order_number="ORD-PAGE-001",
            product_name="页面测试订单",
            amount=Decimal("1200.00"),
            order_date=date(2026, 7, 7),
            status="confirmed",
            create_user=self.user,
            delete_time=0,
        )
        self.expense = Expense.objects.create(
            code="BXPAGE001",
            subject_id=1,
            admin_id=self.user.id,
            did=0,
            project_id=0,
            cost="120.00",
            income_month=202607,
            expense_time=1751846400,
            create_time=1751875200,
        )
        self.invoice = Invoice.objects.create(
            code="INV-PAGE-001",
            customer_id=self.customer.id,
            amount=Decimal("1200.00"),
            admin_id=self.user.id,
            invoice_type=2,
            invoice_title="页面客户",
            create_time=1751875200,
        )
        self.invoice_request = InvoiceRequest.objects.create(
            order_id=self.order.id,
            applicant_id=self.user.id,
            department_id=0,
            amount="1200.00",
            invoice_type=2,
            invoice_title="页面客户",
            reason="页面测试",
            status="pending",
            create_time=1751875200,
        )
        self.account = FinanceAccount.objects.create(
            name="页面测试账户",
            account_type="bank",
            bank_name="中国银行",
            account_no="6222000000999",
            current_balance=Decimal("2000.00"),
            opening_balance=Decimal("2000.00"),
            status="active",
            create_time=1751875200,
        )
        self.payment = Payment.objects.create(
            customer_id=self.customer.id,
            amount=Decimal("320.00"),
            payment_date=datetime(2026, 7, 7, 14, 0, 0),
            create_time=1751880000,
            remark="页面测试付款",
        )
        self.income = Income.objects.create(
            invoice_id=self.invoice.id,
            amount=Decimal("600.00"),
            income_date=datetime(2026, 7, 7, 15, 0, 0),
            create_time=1751883600,
            remark="页面测试回款",
        )

    def test_finance_core_pages_render_successfully(self):
        urls = [
            "/finance/",
            "/finance/reimbursement/",
            "/finance/expense/view/%s/" % self.expense.id,
            "/finance/payment/",
            "/finance/payment/add/?expense_id=%s" % self.expense.id,
            "/finance/payment/view/%s/" % self.payment.id,
            "/finance/invoice/",
            "/finance/invoice/view/%s/" % self.invoice.id,
            "/finance/invoice/add/",
            "/finance/income/",
            "/finance/income/add/?invoice_id=%s" % self.invoice.id,
            "/finance/income/view/%s/" % self.income.id,
            "/finance/invoice-request/",
            "/finance/invoice-request/detail/%s/" % self.invoice_request.id,
            "/finance/invoice-request/add/?order_id=%s" % self.order.id,
            "/finance/order-finance/",
            "/finance/advanced/bank-transaction/",
            "/finance/advanced/bank-transaction/add/",
            "/finance/paymentreceive/",
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_income_add_page_shows_account_selector(self):
        response = self.client.get(f"/finance/income/add/?invoice_id={self.invoice.id}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "页面测试账户")

    def test_receiveinvoice_list_uses_finance_module_style(self):
        response = self.client.get("/finance/receiveinvoice/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "finance-module.css")

    def test_expense_detail_uses_finance_module_style(self):
        response = self.client.get(f"/finance/expense/view/{self.expense.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "finance-module.css")
        self.assertContains(response, "2025-07-07")

    def test_finance_dashboard_keeps_full_shortcut_sections(self):
        response = self.client.get("/finance/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "费用与付款")
        self.assertContains(response, "发票与回款")
        self.assertContains(response, "资金与往来")
        self.assertContains(response, "总账核算")
        self.assertContains(response, "预算与成本")
        self.assertContains(response, "资产与税务")
        self.assertContains(response, "报表分析")
        self.assertContains(response, "银行流水")

    def test_finance_statistics_pages_use_finance_module_style(self):
        urls = [
            "/finance/statistics/reimbursement/",
            "/finance/statistics/invoice/",
            "/finance/statistics/receiveinvoice/",
            "/finance/statistics/paymentreceive/",
            "/finance/statistics/payment/",
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "finance-module.css")
