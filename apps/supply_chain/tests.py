from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
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
