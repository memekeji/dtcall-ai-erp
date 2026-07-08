from datetime import date
from decimal import Decimal
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse


class SupplyChainAppSmokeTests(TestCase):
    def test_dashboard_route_exists(self):
        response = self.client.get(reverse('supply_chain:dashboard'))
        self.assertNotEqual(response.status_code, 404)


class SupplyChainModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='supply-chain-user',
            password='test-pass-123',
            email='supply@example.com',
        )

    def test_can_create_demand_forecast_plan(self):
        from apps.supply_chain.models import DemandForecastPlan

        plan = DemandForecastPlan.objects.create(
            name='7月滚动预测',
            code='DFP-202607-001',
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            created_by=self.user,
        )

        self.assertEqual(plan.status, DemandForecastPlan.STATUS_DRAFT)

    def test_outsource_issue_item_calculates_shortage_quantity(self):
        from apps.supply_chain.models import OutsourceIssueItem

        issue_item = OutsourceIssueItem(
            required_quantity=Decimal('120'),
            available_quantity=Decimal('80'),
        )

        self.assertEqual(issue_item.shortage_quantity, Decimal('40'))

    def test_pr_review_task_defaults_to_pending(self):
        from apps.supply_chain.models import PRReviewTask

        task = PRReviewTask.objects.create(
            code='PRR-001',
            title='PR异常识别',
            created_by=self.user,
        )

        self.assertEqual(task.status, PRReviewTask.STATUS_PENDING)

    def test_sample_request_code_must_be_unique(self):
        from apps.supply_chain.models import SampleRequest

        SampleRequest.objects.create(
            code='SMP-20260704-001',
            material_name='蓝牙喇叭',
            requested_by=self.user,
            engineer=self.user,
            required_date=date(2026, 7, 10),
        )

        with self.assertRaises(IntegrityError):
            SampleRequest.objects.create(
                code='SMP-20260704-001',
                material_name='蓝牙喇叭',
                requested_by=self.user,
                engineer=self.user,
                required_date=date(2026, 7, 10),
            )


class DemandForecastServiceTests(TestCase):
    def test_calculates_recommended_preparation_quantity(self):
        from apps.supply_chain.services.forecast_service import calculate_recommended_preparation_quantity

        recommended = calculate_recommended_preparation_quantity(
            predicted_quantity=Decimal('300'),
            safety_stock=Decimal('50'),
            inventory_quantity=Decimal('80'),
            wip_quantity=Decimal('60'),
            inbound_quantity=Decimal('40'),
            prepared_quantity=Decimal('20'),
            manual_adjustment=Decimal('10'),
        )

        self.assertEqual(recommended, Decimal('160'))

    def test_calculates_forecast_accuracy_percentage(self):
        from apps.supply_chain.services.forecast_service import calculate_forecast_accuracy

        accuracy = calculate_forecast_accuracy(
            predicted_quantity=Decimal('90'),
            actual_quantity=Decimal('100'),
        )

        self.assertEqual(accuracy, Decimal('90.00'))

    def test_builds_snapshot_payload(self):
        from apps.supply_chain.services.forecast_service import build_snapshot_payload

        payload = build_snapshot_payload(
            shipped_quantity=Decimal('120'),
            inventory_quantity=Decimal('30'),
            wip_quantity=Decimal('15'),
            inbound_quantity=Decimal('8'),
            prepared_quantity=Decimal('5'),
            manual_adjustment=Decimal('2'),
        )

        self.assertEqual(payload['total_supply'], Decimal('58'))


class OutsourceIssueServiceTests(TestCase):
    def test_builds_issue_item_payload_from_bom_and_inventory(self):
        from apps.supply_chain.services.outsource_service import build_issue_item_payload

        payload = build_issue_item_payload(
            bom_item={
                'material_name': '耳机外壳',
                'material_code': 'MAT-001',
                'specification': '白色',
                'quantity': Decimal('2'),
            },
            plan_quantity=Decimal('100'),
            inventory_lookup={
                'MAT-001': {
                    'available_quantity': Decimal('150'),
                    'specification': '白色',
                }
            },
        )

        self.assertEqual(payload['required_quantity'], Decimal('200.00'))
        self.assertEqual(payload['shortage_quantity'], Decimal('50.00'))
        self.assertEqual(payload['status'], 'shortage')

    def test_summarizes_issue_order_as_ready_when_all_items_ready(self):
        from apps.supply_chain.services.outsource_service import summarize_issue_order_status

        status = summarize_issue_order_status([
            {'status': 'ready'},
            {'status': 'ready'},
        ])

        self.assertEqual(status, 'ready')

    def test_summarizes_issue_order_as_shortage_when_any_item_shortage(self):
        from apps.supply_chain.services.outsource_service import summarize_issue_order_status

        status = summarize_issue_order_status([
            {'status': 'ready'},
            {'status': 'shortage'},
        ])

        self.assertEqual(status, 'shortage')


class PRReviewServiceTests(TestCase):
    def test_matches_urgent_pr_rule(self):
        from apps.supply_chain.services.pr_review_service import evaluate_pr_payload

        result = evaluate_pr_payload(
            payload={
                'is_urgent': True,
                'lt_shortage': True,
                'order_type': 'customer',
            },
            rules=[
                {
                    'code': 'URGENT_SHORTAGE',
                    'name': '紧急缺料单',
                    'condition_json': {'is_urgent': True, 'lt_shortage': True},
                    'recommended_action': 'urgent_approve',
                    'priority': 10,
                }
            ],
        )

        self.assertEqual(result['recommended_action'], 'urgent_approve')
        self.assertEqual(result['matched_rules'][0]['code'], 'URGENT_SHORTAGE')

    def test_flags_abnormal_tail_order_for_manual_review(self):
        from apps.supply_chain.services.pr_review_service import evaluate_pr_payload

        result = evaluate_pr_payload(
            payload={
                'tail_order': True,
                'rework_order': False,
            },
            rules=[
                {
                    'code': 'TAIL_ORDER',
                    'name': '尾数订单',
                    'condition_json': {'tail_order': True},
                    'recommended_action': 'manual_review',
                    'priority': 20,
                }
            ],
        )

        self.assertTrue(result['is_abnormal'])
        self.assertEqual(result['recommended_action'], 'manual_review')

    def test_returns_pending_when_no_rule_matches(self):
        from apps.supply_chain.services.pr_review_service import evaluate_pr_payload

        result = evaluate_pr_payload(
            payload={'is_urgent': False},
            rules=[],
        )

        self.assertEqual(result['status'], 'pending')


class PRReviewFormTests(TestCase):
    def test_builds_payload_from_structured_scenario(self):
        from apps.supply_chain.forms import PRReviewEvaluateForm

        form = PRReviewEvaluateForm(data={
            'scenario': 'urgent_shortage',
            'order_type': 'customer',
        })

        self.assertTrue(form.is_valid())
        self.assertEqual(form.build_payload(), {
            'is_urgent': True,
            'lt_shortage': True,
            'tail_order': False,
            'intercompany_tail_order': False,
            'outsource_tail_order': False,
            'rework_order': False,
            'npi_trial': False,
            'order_type': 'customer',
        })

    def test_json_payload_still_supported_for_backward_compatibility(self):
        from apps.supply_chain.forms import PRReviewEvaluateForm

        form = PRReviewEvaluateForm(data={
            'payload_json': '{"tail_order": true}',
        })

        self.assertTrue(form.is_valid())
        self.assertEqual(form.build_payload(), {'tail_order': True})


class PriceReviewServiceTests(TestCase):
    def test_normalizes_price_components_from_parsed_payload(self):
        from apps.supply_chain.services.price_review_service import normalize_price_components

        components = normalize_price_components({
            'material_cost': Decimal('8.5000'),
            'process_cost': Decimal('1.2000'),
            'labor_cost': Decimal('0.8000'),
            'loss_cost': Decimal('0.3000'),
            'package_cost': Decimal('0.2000'),
            'logistics_cost': Decimal('0.4000'),
            'profit_cost': Decimal('0.6000'),
        })

        self.assertEqual(components[0]['component_type'], 'material')
        self.assertEqual(sum(item['amount'] for item in components), Decimal('12.0000'))

    def test_marks_component_abnormal_when_above_reference_range(self):
        from apps.supply_chain.services.price_review_service import compare_component_amounts

        rows = compare_component_amounts(
            components=[
                {
                    'component_type': 'material',
                    'component_name': '蓝牙芯片',
                    'amount': Decimal('4.5000'),
                }
            ],
            reference_map={'蓝牙芯片': Decimal('3.5000')},
            tolerance_rate=Decimal('0.10'),
        )

        self.assertTrue(rows[0]['is_abnormal'])
        self.assertEqual(rows[0]['reference_amount'], Decimal('3.5000'))

    def test_builds_exception_conclusion_when_quote_exceeds_benchmarks(self):
        from apps.supply_chain.services.price_review_service import build_price_review_conclusion

        conclusion = build_price_review_conclusion(
            quoted_price=Decimal('15.0000'),
            component_rows=[
                {
                    'component_name': '蓝牙芯片',
                    'amount': Decimal('4.5000'),
                    'reference_amount': Decimal('3.5000'),
                    'is_abnormal': True,
                },
                {
                    'component_name': '人工',
                    'amount': Decimal('2.2000'),
                    'reference_amount': Decimal('1.8000'),
                    'is_abnormal': True,
                },
            ],
            historical_prices=[Decimal('11.0000'), Decimal('12.0000')],
            market_price=Decimal('11.5000'),
            target_price=Decimal('12.0000'),
            deviation_threshold=Decimal('0.10'),
        )

        self.assertEqual(conclusion['result'], 'exception')
        self.assertEqual(conclusion['risk_level'], 'high')
        self.assertGreaterEqual(len(conclusion['abnormal_items']), 2)


class SampleWorkflowServiceTests(TestCase):
    def test_generates_sample_request_code(self):
        from apps.supply_chain.services.sample_service import generate_sample_request_code

        code = generate_sample_request_code(
            current_date=date(2026, 7, 4),
            sequence=12,
        )

        self.assertEqual(code, 'SMP-20260704-012')

    def test_builds_receipt_payload_and_pickup_notification(self):
        from apps.supply_chain.services.sample_service import build_receipt_payload

        payload = build_receipt_payload(
            material_name='耳机电池',
            specification='500mAh',
            engineer_name='张工',
            location='研发样品柜',
            received_quantity=Decimal('3'),
        )

        self.assertEqual(payload['request_status'], 'pickup_pending')
        self.assertIn('研发样品柜', payload['notification_message'])
        self.assertIn('张工', payload['notification_message'])

    def test_detects_pickup_overdue_by_deadline_hours(self):
        from apps.supply_chain.services.sample_service import is_pickup_overdue
        from django.utils import timezone
        from datetime import timedelta

        overdue = is_pickup_overdue(
            received_at=timezone.now() - timedelta(hours=30),
            pickup_deadline_hours=24,
            current_time=timezone.now(),
        )

        self.assertTrue(overdue)


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class SupplyChainViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        from apps.contract.models import Product, ProductCate, Supplier
        from apps.inventory.models import Inventory, InventoryCategory, InventoryItem, Warehouse
        from apps.production.models import BOM, BOMItem, ProductionPlan
        from apps.supply_chain.models import PRReviewRule

        self.user = get_user_model().objects.create_user(
            username='supply-chain-view-user',
            password='test-pass-123',
            email='view@example.com',
        )
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.status = 1
        self.user.save(update_fields=['is_superuser', 'is_staff', 'status'])
        self.client.force_login(self.user)

        self.product_category = ProductCate.objects.create(title='耳机')
        self.product = Product.objects.create(
            name='蓝牙耳机',
            code='PROD-001',
            cate=self.product_category,
            price=Decimal('99.00'),
            admin=self.user,
        )
        self.supplier = Supplier.objects.create(
            name='声学供应商',
            code='SUP-001',
            contact_person='李四',
            contact_phone='13800138000',
            contact_email='supplier@example.com',
        )
        self.inventory_category = InventoryCategory.objects.create(
            name='原材料',
            code='CAT-001',
        )
        self.inventory_item = InventoryItem.objects.create(
            name='蓝牙芯片',
            code='MAT-001',
            category=self.inventory_category,
            specification='V5.4',
            unit='pcs',
            safety_stock=Decimal('20'),
        )
        self.warehouse = Warehouse.objects.create(
            name='主仓',
            code='WH-001',
            manager=self.user,
        )
        Inventory.objects.create(
            item=self.inventory_item,
            warehouse=self.warehouse,
            quantity=Decimal('180'),
            locked_quantity=Decimal('10'),
            unit_cost=Decimal('3.50'),
        )
        self.bom = BOM.objects.create(
            name='蓝牙耳机BOM',
            code='BOM-001',
            product=self.product,
            creator=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom,
            material_name='蓝牙芯片',
            material_code='MAT-001',
            specification='V5.4',
            unit='pcs',
            quantity=Decimal('1.0000'),
        )
        self.production_plan = ProductionPlan.objects.create(
            name='7月计划',
            code='PLAN-001',
            product=self.product,
            bom=self.bom,
            quantity=Decimal('100'),
            unit='pcs',
            plan_start_date=date(2026, 7, 1),
            plan_end_date=date(2026, 7, 31),
            manager=self.user,
            creator=self.user,
        )
        self.pr_rule = PRReviewRule.objects.create(
            name='尾数订单',
            code='TAIL_ORDER',
            condition_json={'tail_order': True},
            recommended_action='manual_review',
            priority=20,
        )

    def test_can_create_and_run_forecast_workflow(self):
        from apps.supply_chain.models import (
            DemandForecastPlan,
            DemandForecastResult,
            DemandForecastSnapshot,
            MaterialPreparationReview,
        )

        response = self.client.post(reverse('supply_chain:forecast_create'), {
            'name': '7月需求预测',
            'product': self.product.id,
            'period_start': '2026-07-01',
            'period_end': '2026-07-31',
            'version': '1.0',
            'summary': '滚动预测',
        })
        self.assertEqual(response.status_code, 302)

        plan = DemandForecastPlan.objects.get(name='7月需求预测')
        run_response = self.client.post(reverse('supply_chain:forecast_run', args=[plan.id]), {
            'shipped_quantity': '120',
            'inventory_quantity': '40',
            'wip_quantity': '20',
            'inbound_quantity': '10',
            'prepared_quantity': '5',
            'manual_adjustment': '5',
            'predicted_quantity': '180',
            'avg_daily_demand': '8',
            'actual_quantity': '170',
        })

        self.assertEqual(run_response.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(DemandForecastSnapshot.objects.filter(forecast_plan=plan).count(), 1)
        self.assertEqual(DemandForecastResult.objects.filter(forecast_plan=plan).count(), 1)
        self.assertEqual(MaterialPreparationReview.objects.filter(forecast_result__forecast_plan=plan).count(), 1)
        self.assertEqual(plan.status, DemandForecastPlan.STATUS_REVIEWING)

    def test_can_create_outsource_order_and_run_completeness_check(self):
        from apps.supply_chain.models import OutsourceIssueOrder

        response = self.client.post(reverse('supply_chain:outsource_create'), {
            'product': self.product.id,
            'supplier': self.supplier.id,
            'production_plan': self.production_plan.id,
            'quantity': '100',
        })
        self.assertEqual(response.status_code, 302)

        issue_order = OutsourceIssueOrder.objects.get(production_plan=self.production_plan)
        check_response = self.client.post(reverse('supply_chain:outsource_check', args=[issue_order.id]))
        self.assertEqual(check_response.status_code, 302)

        issue_order.refresh_from_db()
        self.assertEqual(issue_order.items.count(), 1)
        self.assertEqual(issue_order.status, 'ready')

    def test_can_evaluate_pr_review_task(self):
        from apps.supply_chain.models import PRReviewEvidence, PRReviewTask

        task = PRReviewTask.objects.create(
            code='PRR-TEST-001',
            title='异常PR识别',
            created_by=self.user,
        )
        response = self.client.post(reverse('supply_chain:pr_review_evaluate', args=[task.id]), {
            'payload_json': '{"tail_order": true}',
        })

        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.recommended_action, 'manual_review')
        self.assertTrue(task.is_abnormal)
        self.assertEqual(PRReviewEvidence.objects.filter(review_task=task).count(), 2)

    def test_can_evaluate_pr_review_task_with_structured_inputs(self):
        from apps.supply_chain.models import PRReviewRule, PRReviewTask

        PRReviewRule.objects.create(
            code='PR-URGENT-SHORTAGE-CUSTOM',
            name='紧急缺料单',
            condition_json={'is_urgent': True, 'lt_shortage': True},
            recommended_action='urgent_approve',
            priority=10,
        )
        task = PRReviewTask.objects.create(
            code='PRR-TEST-STRUCTURED-001',
            title='紧急缺料 PR',
            created_by=self.user,
        )

        response = self.client.post(reverse('supply_chain:pr_review_evaluate', args=[task.id]), {
            'scenario': 'urgent_shortage',
            'order_type': 'customer',
        })

        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.recommended_action, 'urgent_approve')
        self.assertFalse(task.is_abnormal)

    def test_can_analyze_price_review_order(self):
        from apps.supply_chain.models import PriceReviewConclusion, PriceReviewOrder

        order = PriceReviewOrder.objects.create(
            code='PRC-001',
            inventory_item=self.inventory_item,
            supplier=self.supplier,
            quoted_price=Decimal('15.0000'),
            created_by=self.user,
        )
        response = self.client.post(reverse('supply_chain:price_review_analyze', args=[order.id]), {
            'material_cost': '8.5000',
            'process_cost': '1.2000',
            'labor_cost': '2.1000',
            'loss_cost': '0.4000',
            'package_cost': '0.2000',
            'logistics_cost': '0.5000',
            'profit_cost': '0.8000',
            'historical_prices': '11,12',
            'market_price': '11.5',
            'target_price': '12',
        })

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.components.count(), 7)
        self.assertTrue(PriceReviewConclusion.objects.filter(review_order=order).exists())

    def test_can_create_sample_request_and_complete_receipt_pickup(self):
        from apps.supply_chain.models import SamplePickupRecord, SampleReceipt, SampleRequest

        response = self.client.post(reverse('supply_chain:sample_create'), {
            'material_name': '耳机电池',
            'specification': '500mAh',
            'supplier': self.supplier.id,
            'engineer': self.user.id,
            'required_date': '2026-07-10',
            'quantity': '3',
            'remark': '新品试样',
        })
        self.assertEqual(response.status_code, 302)

        sample_request = SampleRequest.objects.get(material_name='耳机电池')
        self.assertTrue(sample_request.code.startswith('SMP-'))

        receipt_response = self.client.post(reverse('supply_chain:sample_receive', args=[sample_request.id]), {
            'received_quantity': '3',
            'location': '研发样品柜',
        })
        self.assertEqual(receipt_response.status_code, 302)

        pickup_response = self.client.post(reverse('supply_chain:sample_pickup', args=[sample_request.id]), {
            'note': '已领取测试',
        })
        self.assertEqual(pickup_response.status_code, 302)

        sample_request.refresh_from_db()
        self.assertEqual(sample_request.status, 'picked_up')
        self.assertEqual(SampleReceipt.objects.filter(sample_request=sample_request).count(), 1)
        self.assertEqual(SamplePickupRecord.objects.filter(sample_request=sample_request).count(), 1)

    def test_sample_receipt_can_store_uploaded_photo(self):
        from apps.supply_chain.models import SampleReceipt, SampleRequest

        sample_request = SampleRequest.objects.create(
            code='SMP-RECEIPT-001',
            material_name='耳机面壳',
            specification='银色',
            supplier=self.supplier,
            engineer=self.user,
            requested_by=self.user,
            required_date=date(2026, 7, 10),
            quantity=Decimal('2'),
            status=SampleRequest.STATUS_ORDERED,
        )
        uploaded = SimpleUploadedFile(
            'sample-photo.jpg',
            b'fake-image-bytes',
            content_type='image/jpeg',
        )

        response = self.client.post(reverse('supply_chain:sample_receive', args=[sample_request.id]), {
            'received_quantity': '2',
            'location': '研发样品柜',
            'photo_file': uploaded,
        })

        self.assertEqual(response.status_code, 302)
        receipt = SampleReceipt.objects.get(sample_request=sample_request)
        self.assertIn('sample-photo.jpg', receipt.photo_path)

    def test_dashboard_and_inventory_analysis_pages_render(self):
        dashboard_response = self.client.get(reverse('supply_chain:dashboard'))
        inventory_response = self.client.get(reverse('supply_chain:inventory_analysis'))

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, '供应链智能驾驶舱')
        self.assertEqual(inventory_response.status_code, 200)
        self.assertContains(inventory_response, '库存智能分析')
        self.assertContains(inventory_response, '170.00', status_code=200)
        self.assertContains(inventory_response, '180.00', status_code=200)

    def test_can_bootstrap_supply_chain_workspace_from_existing_modules(self):
        from apps.supply_chain.models import (
            DemandForecastPlan,
            OutsourceIssueOrder,
            PRReviewRule,
            PRReviewTask,
            PriceReviewOrder,
            SampleRequest,
        )
        from apps.inventory.models import Inventory, InventoryItem

        risk_item = InventoryItem.objects.create(
            name='补货风险物料',
            code='MAT-RISK-001',
            category=self.inventory_category,
            specification='Risk',
            unit='pcs',
            safety_stock=Decimal('50'),
            reorder_point=Decimal('40'),
            standard_cost=Decimal('9.50'),
        )
        Inventory.objects.create(
            item=risk_item,
            warehouse=self.warehouse,
            quantity=Decimal('20'),
            locked_quantity=Decimal('0'),
            unit_cost=Decimal('9.50'),
        )

        response = self.client.post(reverse('supply_chain:bootstrap_workspace'), {
            'target': 'dashboard',
        })

        self.assertEqual(response.status_code, 302)
        self.assertGreater(DemandForecastPlan.objects.count(), 0)
        self.assertGreater(OutsourceIssueOrder.objects.count(), 0)
        self.assertGreater(PRReviewRule.objects.count(), 0)
        self.assertGreater(PRReviewTask.objects.count(), 0)
        self.assertGreater(PriceReviewOrder.objects.count(), 0)
        self.assertGreater(SampleRequest.objects.count(), 0)
        self.assertFalse(OutsourceIssueOrder.objects.filter(supplier__isnull=True).exists())
        self.assertFalse(SampleRequest.objects.filter(supplier__isnull=True).exists())

    def test_can_approve_forecast_review(self):
        from apps.supply_chain.models import (
            DemandForecastPlan,
            DemandForecastResult,
            MaterialPreparationReview,
        )

        plan = DemandForecastPlan.objects.create(
            name='审批预测',
            code='DFP-REVIEW-001',
            product=self.product,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            created_by=self.user,
            status=DemandForecastPlan.STATUS_GENERATED,
        )
        result = DemandForecastResult.objects.create(
            forecast_plan=plan,
            predicted_quantity=Decimal('220'),
            safety_stock=Decimal('30'),
            recommended_quantity=Decimal('80'),
            confidence=Decimal('85.00'),
            risk_level='medium',
            summary='待评审',
        )
        review = MaterialPreparationReview.objects.create(
            forecast_result=result,
            code='MPR-001',
        )

        response = self.client.post(reverse('supply_chain:forecast_review', args=[review.id]), {
            'decision': 'approve',
            'comment': '同意执行备料',
        })

        self.assertEqual(response.status_code, 302)
        review.refresh_from_db()
        plan.refresh_from_db()
        self.assertEqual(review.status, 'approved')
        self.assertEqual(plan.status, DemandForecastPlan.STATUS_APPROVED)

    def test_can_progress_outsource_order_to_notified(self):
        from apps.supply_chain.models import OutsourceIssueOrder

        order = OutsourceIssueOrder.objects.create(
            code='OIO-FLOW-001',
            product=self.product,
            supplier=self.supplier,
            production_plan=self.production_plan,
            quantity=Decimal('100'),
            created_by=self.user,
            status=OutsourceIssueOrder.STATUS_READY,
        )

        picking_response = self.client.post(reverse('supply_chain:outsource_status_update', args=[order.id]), {
            'action': 'start_picking',
        })
        issued_response = self.client.post(reverse('supply_chain:outsource_status_update', args=[order.id]), {
            'action': 'mark_issued',
        })
        notified_response = self.client.post(reverse('supply_chain:outsource_status_update', args=[order.id]), {
            'action': 'notify_pickup',
        })

        self.assertEqual(picking_response.status_code, 302)
        self.assertEqual(issued_response.status_code, 302)
        self.assertEqual(notified_response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, OutsourceIssueOrder.STATUS_NOTIFIED)
        self.assertGreaterEqual(order.status_logs.count(), 3)

    def test_can_one_click_approve_pr_review_task(self):
        from apps.supply_chain.models import PRReviewTask

        task = PRReviewTask.objects.create(
            code='PRR-APPROVE-001',
            title='紧急采购申请',
            created_by=self.user,
            status=PRReviewTask.STATUS_MANUAL_REVIEW,
            recommended_action='urgent_approve',
            is_abnormal=True,
        )

        response = self.client.post(reverse('supply_chain:pr_review_approve', args=[task.id]), {
            'note': '紧急订单，先行放行',
        })

        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, PRReviewTask.STATUS_DONE)
        self.assertEqual(task.reviewer, self.user)

    def test_can_batch_approve_pr_review_tasks(self):
        from apps.supply_chain.models import PRReviewEvidence, PRReviewTask

        task = PRReviewTask.objects.create(
            code='PRR-BATCH-001',
            title='周期审批任务',
            created_by=self.user,
            status=PRReviewTask.STATUS_AUTO_APPROVED,
            recommended_action='approve',
        )

        response = self.client.post(reverse('supply_chain:pr_review_batch_approve'), {
            'note': '周一批量审批',
        })

        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.status, PRReviewTask.STATUS_DONE)
        self.assertEqual(task.reviewer, self.user)
        self.assertTrue(
            PRReviewEvidence.objects.filter(
                review_task=task,
                label='批量审批备注',
                value='周一批量审批',
            ).exists()
        )

    def test_can_parse_price_review_document(self):
        from apps.supply_chain.models import PriceReviewDocument, PriceReviewOrder

        order = PriceReviewOrder.objects.create(
            code='PRC-DOC-001',
            inventory_item=self.inventory_item,
            supplier=self.supplier,
            quoted_price=Decimal('12.8000'),
            created_by=self.user,
        )
        uploaded = SimpleUploadedFile(
            'speaker-spec.txt',
            (
                '材质: 铝壳\n'
                '原材料成本: 8.2\n'
                '工艺成本: 1.1\n'
                '人工成本: 0.8\n'
                '损耗成本: 0.2\n'
                '包装成本: 0.3\n'
                '物流成本: 0.4\n'
                '利润: 0.6\n'
            ).encode('utf-8'),
            content_type='text/plain',
        )

        response = self.client.post(reverse('supply_chain:price_review_parse_document', args=[order.id]), {
            'document_file': uploaded,
        })

        self.assertEqual(response.status_code, 302)
        document = PriceReviewDocument.objects.get(review_order=order)
        self.assertIn('原材料成本', document.raw_text)
        self.assertEqual(document.parsed_payload['material_cost'], '8.2000')

    def test_can_analyze_price_review_from_latest_parsed_document(self):
        from apps.supply_chain.models import PriceReviewConclusion, PriceReviewDocument, PriceReviewOrder

        order = PriceReviewOrder.objects.create(
            code='PRC-DOC-ANALYZE-001',
            inventory_item=self.inventory_item,
            supplier=self.supplier,
            quoted_price=Decimal('12.9000'),
            created_by=self.user,
        )
        PriceReviewDocument.objects.create(
            review_order=order,
            file_name='manual.txt',
            raw_text='',
            parsed_payload={
                'material_cost': '8.2000',
                'process_cost': '1.1000',
                'labor_cost': '0.7000',
                'loss_cost': '0.2000',
                'package_cost': '0.3000',
                'logistics_cost': '0.2000',
                'profit_cost': '0.5000',
            },
        )

        response = self.client.post(reverse('supply_chain:price_review_analyze', args=[order.id]), {
            'historical_prices': '11.8,12.1',
            'market_price': '12.0',
            'target_price': '12.2',
        })

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.components.count(), 7)
        self.assertTrue(PriceReviewConclusion.objects.filter(review_order=order).exists())

    def test_invalid_outsource_transition_is_blocked(self):
        from apps.supply_chain.models import OutsourceIssueOrder

        order = OutsourceIssueOrder.objects.create(
            code='OIO-INVALID-001',
            product=self.product,
            supplier=self.supplier,
            production_plan=self.production_plan,
            quantity=Decimal('100'),
            created_by=self.user,
            status=OutsourceIssueOrder.STATUS_DRAFT,
        )

        response = self.client.post(reverse('supply_chain:outsource_status_update', args=[order.id]), {
            'action': 'mark_issued',
        })

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, OutsourceIssueOrder.STATUS_DRAFT)


class SupplyChainPermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_user(
            username='supply-chain-admin-user',
            password='test-pass-123',
            email='admin@example.com',
        )
        self.admin.is_superuser = True
        self.admin.is_staff = True
        self.admin.status = 1
        self.admin.save(update_fields=['is_superuser', 'is_staff', 'status'])
        self.user = get_user_model().objects.create_user(
            username='supply-chain-normal-user',
            password='test-pass-123',
            email='normal@example.com',
        )
        self.user.status = 1
        self.user.save(update_fields=['status'])

    def test_normal_user_can_access_dashboard_with_supply_chain_permission(self):
        permission = Permission.objects.get(
            codename='view_supply_chain_dashboard',
            content_type__app_label='user',
        )
        self.user.user_permissions.add(permission)
        cache.clear()
        self.client.force_login(self.user)

        response = self.client.get(reverse('supply_chain:dashboard'))

        self.assertEqual(response.status_code, 200)

    def test_normal_user_is_blocked_without_supply_chain_permission(self):
        cache.clear()
        self.client.force_login(self.user)

        response = self.client.get(reverse('supply_chain:dashboard'))

        self.assertEqual(response.status_code, 403)


class SupplyChainNotificationTests(TestCase):
    def setUp(self):
        from apps.contract.models import Supplier
        from apps.supply_chain.models import PRReviewRule, PRReviewTask, SampleRequest

        self.user = get_user_model().objects.create_user(
            username='supply-chain-notify-user',
            password='test-pass-123',
            email='notify@example.com',
        )
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.status = 1
        self.user.save(update_fields=['is_superuser', 'is_staff', 'status'])
        self.client.force_login(self.user)
        self.supplier = Supplier.objects.create(
            name='样品供应商',
            code='SUP-NT-001',
            contact_person='王五',
            contact_phone='13900139000',
            contact_email='notify-supplier@example.com',
        )
        self.sample_request = SampleRequest.objects.create(
            code='SMP-20260704-001',
            material_name='耳机外壳',
            specification='黑色',
            supplier=self.supplier,
            engineer=self.user,
            requested_by=self.user,
            required_date=date(2026, 7, 10),
            quantity=Decimal('2'),
        )
        self.pr_rule = PRReviewRule.objects.create(
            name='尾数订单',
            code='TAIL-NT',
            condition_json={'tail_order': True},
            recommended_action='manual_review',
            priority=20,
        )
        self.pr_task = PRReviewTask.objects.create(
            code='PRR-NT-001',
            title='PR提醒任务',
            created_by=self.user,
        )

    def test_sample_receipt_creates_message_and_event_log(self):
        from apps.message.models import Message
        from apps.supply_chain.models import SupplyChainEventLog

        response = self.client.post(reverse('supply_chain:sample_receive', args=[self.sample_request.id]), {
            'received_quantity': '2',
            'location': '研发样品柜',
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Message.objects.filter(related_object_type='sample_request').exists())
        self.assertTrue(SupplyChainEventLog.objects.filter(event_type='sample_received').exists())

    def test_abnormal_pr_review_creates_message_and_event_log(self):
        from apps.message.models import Message
        from apps.supply_chain.models import SupplyChainEventLog

        response = self.client.post(reverse('supply_chain:pr_review_evaluate', args=[self.pr_task.id]), {
            'payload_json': '{"tail_order": true}',
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Message.objects.filter(related_object_type='pr_review_task').exists())
        self.assertTrue(SupplyChainEventLog.objects.filter(event_type='pr_review_evaluated').exists())


class SupplyChainAITests(TestCase):
    def setUp(self):
        from apps.contract.models import Supplier
        from apps.inventory.models import InventoryCategory, InventoryItem
        from apps.supply_chain.models import (
            DemandForecastPlan,
            DemandForecastResult,
            PriceReviewConclusion,
            PriceReviewOrder,
        )

        self.user = get_user_model().objects.create_user(
            username='supply-chain-ai-user',
            password='test-pass-123',
            email='ai@example.com',
        )
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.status = 1
        self.user.save(update_fields=['is_superuser', 'is_staff', 'status'])
        self.client.force_login(self.user)
        self.forecast_plan = DemandForecastPlan.objects.create(
            name='8月预测',
            code='DFP-202608-001',
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            created_by=self.user,
            status='generated',
        )
        DemandForecastResult.objects.create(
            forecast_plan=self.forecast_plan,
            predicted_quantity=Decimal('200'),
            safety_stock=Decimal('56'),
            recommended_quantity=Decimal('120'),
            confidence=Decimal('88.00'),
            risk_level='medium',
            summary='预测偏紧',
        )
        self.supplier = Supplier.objects.create(
            name='AI供应商',
            code='SUP-AI-001',
            contact_person='赵六',
            contact_phone='13700137000',
            contact_email='ai-supplier@example.com',
        )
        self.inventory_category = InventoryCategory.objects.create(
            name='电子料',
            code='CAT-AI-001',
        )
        self.inventory_item = InventoryItem.objects.create(
            name='喇叭单元',
            code='MAT-AI-001',
            category=self.inventory_category,
            unit='pcs',
        )
        self.price_review_order = PriceReviewOrder.objects.create(
            code='PRC-AI-001',
            inventory_item=self.inventory_item,
            supplier=self.supplier,
            quoted_price=Decimal('13.5000'),
            created_by=self.user,
        )
        PriceReviewConclusion.objects.create(
            review_order=self.price_review_order,
            result='exception',
            risk_level='high',
            summary='报价偏高',
            abnormal_items=['原材料'],
            negotiation_points=['原材料成本偏高'],
            reviewer=self.user,
        )

    def test_forecast_ai_summary_endpoint_returns_json(self):
        response = self.client.get(reverse('supply_chain:forecast_ai_summary', args=[self.forecast_plan.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertIn('recommended_quantity', response.json()['data'])

    def test_price_review_ai_summary_endpoint_returns_json(self):
        response = self.client.get(reverse('supply_chain:price_review_ai_summary', args=[self.price_review_order.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertIn('议价', response.json()['data']['summary'])

    def test_pr_review_ai_summary_endpoint_returns_json(self):
        from apps.supply_chain.models import PRReviewRule, PRReviewTask

        task = PRReviewTask.objects.create(
            code='PRR-AI-001',
            title='AI PR 总结',
            created_by=self.user,
            is_abnormal=True,
            recommended_action='manual_review',
            status='manual_review',
        )
        rule = PRReviewRule.objects.create(
            name='试产工单',
            code='NPI-001',
            condition_json={'npi_trial': True},
            recommended_action='manual_review',
            priority=10,
        )
        task.matched_rules.add(rule)

        response = self.client.get(reverse('supply_chain:pr_review_ai_summary', args=[task.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertIn('manual_review', response.json()['data']['summary'])
        self.assertEqual(response.json()['data']['matched_rules'], ['NPI-001'])
