from datetime import date
from decimal import Decimal
from time import perf_counter, sleep
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class SupplyChainRealAITests(TestCase):
    """Tests that verify real AI calls (mocked at client level)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure AI config exists so AIAnalysisTool does not fall back to mock
        try:
            from apps.ai.models import AIModelConfig
            if not AIModelConfig.objects.filter(is_active=True).exists():
                AIModelConfig.objects.create(
                    name="test-supply-ai",
                    provider="openai",
                    model_name="gpt-4o-mini",
                    api_base="https://api.openai.com/v1",
                    api_key="sk-test-key",
                    is_active=True,
                )
        except Exception:
            pass

    def setUp(self):
        from apps.contract.models import Product, ProductCate, Supplier
        from apps.inventory.models import Inventory, InventoryCategory, InventoryItem, Warehouse
        from apps.production.models import BOM, BOMItem, ProductionPlan
        from apps.supply_chain.models import (
            DemandForecastPlan,
            DemandForecastResult,
            PriceReviewConclusion,
            PriceReviewOrder,
            PRReviewRule,
            PRReviewTask,
            SampleRequest,
            PriceReviewDocument,
        )

        self.user = get_user_model().objects.create_user(
            username="supply-chain-ai-real-user",
            password="test-pass-123",
            email="ai-real@example.com",
        )
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.status = 1
        self.user.save(update_fields=["is_superuser", "is_staff", "status"])
        self.client.force_login(self.user)

        self.product_category = ProductCate.objects.create(title="耳机")
        self.product = Product.objects.create(
            name="蓝牙耳机", code="PROD-AI-REAL", cate=self.product_category,
            price=Decimal("99.00"), admin=self.user,
        )
        self.supplier = Supplier.objects.create(
            name="AI供应商", code="SUP-AI-REAL",
            contact_person="赵六", contact_phone="13700137000",
            contact_email="ai-supplier@example.com",
        )
        self.inventory_category = InventoryCategory.objects.create(name="电子料", code="CAT-AI-REAL")
        self.inventory_item = InventoryItem.objects.create(
            name="蓝牙芯片", code="MAT-AI-REAL", category=self.inventory_category,
            specification="V5.4", unit="pcs", safety_stock=Decimal("20"),
            standard_cost=Decimal("3.50"),
        )
        self.warehouse = Warehouse.objects.create(name="主仓", code="WH-AI-REAL", manager=self.user)
        Inventory.objects.create(
            item=self.inventory_item, warehouse=self.warehouse,
            quantity=Decimal("180"), locked_quantity=Decimal("10"), unit_cost=Decimal("3.50"),
        )
        self.bom = BOM.objects.create(name="蓝牙耳机BOM", code="BOM-AI-REAL", product=self.product, creator=self.user)
        BOMItem.objects.create(
            bom=self.bom, material_name="蓝牙芯片", material_code="MAT-AI-REAL",
            specification="V5.4", unit="pcs", quantity=Decimal("1.0000"),
        )
        self.production_plan = ProductionPlan.objects.create(
            name="7月计划", code="PLAN-AI-REAL", product=self.product, bom=self.bom,
            quantity=Decimal("100"), unit="pcs",
            plan_start_date=date(2026, 7, 1), plan_end_date=date(2026, 7, 31),
            manager=self.user, creator=self.user,
        )
        self.forecast_plan = DemandForecastPlan.objects.create(
            name="8月AI预测", code="DFP-AI-REAL-001",
            period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
            created_by=self.user, status="generated",
        )
        DemandForecastResult.objects.create(
            forecast_plan=self.forecast_plan,
            predicted_quantity=Decimal("200"), safety_stock=Decimal("56"),
            recommended_quantity=Decimal("120"), confidence=Decimal("88.00"),
            risk_level="medium", summary="预测偏紧",
        )
        self.price_review_order = PriceReviewOrder.objects.create(
            code="PRC-AI-REAL-001", inventory_item=self.inventory_item,
            supplier=self.supplier, quoted_price=Decimal("13.5000"), created_by=self.user,
        )
        PriceReviewConclusion.objects.create(
            review_order=self.price_review_order,
            result="exception", risk_level="high", summary="报价偏高",
            abnormal_items=["原材料"], negotiation_points=["原材料成本偏高"],
            reviewer=self.user,
        )
        self.pr_rule = PRReviewRule.objects.create(
            name="尾数订单", code="TAIL-AI-REAL",
            condition_json={"tail_order": True}, recommended_action="manual_review", priority=20,
        )

    # --- real LLM fallback tests (mock client calls, verify integration) ---

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_ai_generate_forecast_calls_llm(self, mock_call):
        from apps.supply_chain.services.ai_services import supply_chain_ai
        mock_call.return_value = {
            "predicted_quantity": 210,
            "recommended_quantity": 130,
            "confidence": 85.5,
            "risk_level": "medium",
            "summary": "需求小幅增长，建议适度增加备料。",
        }
        result = supply_chain_ai.generate_forecast(
            product_name="蓝牙耳机",
            historical_demand=[Decimal("180"), Decimal("190"), Decimal("200")],
            inventory_quantity=Decimal("40"),
            wip_quantity=Decimal("20"),
            safety_stock=Decimal("56"),
        )
        self.assertTrue(mock_call.called)
        self.assertIn("predicted_quantity", result)
        self.assertEqual(result["predicted_quantity"], 210)

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_ai_service_parses_json_string_response(self, mock_call):
        from apps.supply_chain.services.ai_services import supply_chain_ai

        mock_call.return_value = (
            '{"is_abnormal": true, "recommended_action": "manual_review", '
            '"reason": "尾数订单需人工确认", "risk_level": "medium"}'
        )
        result = supply_chain_ai.evaluate_pr(
            scenario="tail_order",
            order_type="customer",
            is_urgent=False,
            lt_shortage=False,
            tail_order=True,
            npi_trial=False,
            rework_order=False,
        )

        self.assertTrue(result["is_abnormal"])
        self.assertEqual(result["recommended_action"], "manual_review")

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_ai_answer_forecast_question_calls_llm(self, mock_call):
        from apps.supply_chain.services.ai_services import supply_chain_ai
        mock_call.return_value = {"content": "当前建议备料量为120，请关注库存变化。"}
        answer = supply_chain_ai.answer_forecast_question(
            plan_name="8月预测", predicted_quantity=Decimal("200"),
            recommended_quantity=Decimal("120"), risk_level="medium",
            confidence=88.0, question="建议备料量是多少？",
        )
        self.assertTrue(mock_call.called)
        self.assertIn("120", answer)

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_ai_inventory_risk_summary_calls_llm(self, mock_call):
        from apps.supply_chain.services.ai_services import supply_chain_ai
        mock_call.return_value = {"content": "高风险物料3项，建议优先补货。"}
        summary = supply_chain_ai.analyze_inventory_risk(
            total_items=50, high_risk_count=3, medium_risk_count=8,
            dead_stock_count=2, safety_breach_count=5,
            top_risk_items=["蓝牙芯片", "耳机外壳", "线材"],
        )
        self.assertTrue(mock_call.called)
        self.assertIn("建议", summary)

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_ai_outsource_advice_calls_llm(self, mock_call):
        from apps.supply_chain.services.ai_services import supply_chain_ai
        mock_call.return_value = {"content": "缺料2项，建议采购加急跟进蓝牙芯片。"}
        advice = supply_chain_ai.outsource_completeness_advice(
            order_code="OIO-001", total_items=5, shortage_count=2,
            shortage_details=["蓝牙芯片缺50", "耳机外壳缺30"],
        )
        self.assertTrue(mock_call.called)
        self.assertIn("缺料", advice)

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_ai_evaluate_pr_calls_llm(self, mock_call):
        from apps.supply_chain.services.ai_services import supply_chain_ai
        mock_call.return_value = {
            "is_abnormal": True, "recommended_action": "manual_review",
            "reason": "NPI试产工单需人工确认物料可用性。", "risk_level": "high",
        }
        result = supply_chain_ai.evaluate_pr(
            scenario="npi_trial", order_type="npi",
            is_urgent=True, lt_shortage=False, tail_order=False,
            npi_trial=True, rework_order=False,
        )
        self.assertTrue(mock_call.called)
        self.assertTrue(result["is_abnormal"])
        self.assertEqual(result["recommended_action"], "manual_review")

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_ai_parse_spec_document_calls_llm(self, mock_call):
        from apps.supply_chain.services.ai_services import supply_chain_ai
        mock_call.return_value = {
            "material_cost": 8.2, "process_cost": 1.1, "labor_cost": 0.8,
            "loss_cost": 0.2, "package_cost": 0.3, "logistics_cost": 0.4, "profit_cost": 0.6,
        }
        result = supply_chain_ai.parse_spec_document(
            raw_text="原材料成本: 8.2 工艺成本: 1.1 人工成本: 0.8",
        )
        self.assertTrue(mock_call.called)
        self.assertIn("material_cost", result)

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_ai_price_review_analysis_calls_llm(self, mock_call):
        from apps.supply_chain.services.ai_services import supply_chain_ai
        mock_call.return_value = {
            "result": "exception", "risk_level": "high",
            "summary": "原材料成本偏高，建议议价。",
            "abnormal_items": ["原材料成本"], "negotiation_points": ["对比三家供应商询价"],
        }
        result = supply_chain_ai.analyze_price_review(
            item_name="蓝牙芯片", quoted_price=Decimal("13.50"),
            component_summary="原材料8.2,工艺1.1,人工0.8",
            market_price=Decimal("11.50"), history_avg=Decimal("12.00"),
        )
        self.assertTrue(mock_call.called)
        self.assertEqual(result["result"], "exception")

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_ai_sample_priority_calls_llm(self, mock_call):
        from apps.supply_chain.services.ai_services import supply_chain_ai
        mock_call.return_value = {"content": "超期3项，建议优先处理蓝牙芯片打样。"}
        advice = supply_chain_ai.suggest_sample_priority(
            pending_count=10, overdue_count=3,
            overdue_details=["蓝牙芯片(3天)", "耳机外壳(2天)"],
        )
        self.assertTrue(mock_call.called)
        self.assertIn("优先", advice)


class SupplyChainAIIntegrationTests(TestCase):
    """Verify existing ai_views endpoints work when LLM is enabled."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            from apps.ai.models import AIModelConfig
            if not AIModelConfig.objects.filter(is_active=True).exists():
                AIModelConfig.objects.create(
                    name="test-supply-ai-int",
                    provider="openai",
                    model_name="gpt-4o-mini",
                    api_base="https://api.openai.com/v1",
                    api_key="sk-test-key",
                    is_active=True,
                )
        except Exception:
            pass

    def setUp(self):
        from apps.contract.models import Product, ProductCate, Supplier
        from apps.inventory.models import InventoryCategory, InventoryItem
        from apps.production.models import BOM, BOMItem, ProductionPlan
        from apps.supply_chain.models import (
            DemandForecastPlan, DemandForecastResult,
            PriceReviewConclusion, PriceReviewOrder,
        )

        self.user = get_user_model().objects.create_user(
            username="supply-chain-ai-int-user",
            password="test-pass-123", email="ai-int@example.com",
        )
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.status = 1
        self.user.save(update_fields=["is_superuser", "is_staff", "status"])
        self.client.force_login(self.user)

        self.supplier = Supplier.objects.create(
            name="集成供应商", code="SUP-INT-001",
            contact_person="钱七", contact_phone="13600136000",
            contact_email="int-supplier@example.com",
        )
        self.product_category = ProductCate.objects.create(title="耳机")
        self.product = Product.objects.create(
            name="AI蓝牙耳机", code="PROD-INT-001", cate=self.product_category,
            price=Decimal("99.00"), admin=self.user,
        )
        self.inventory_item = InventoryItem.objects.create(
            name="喇叭单元", code="MAT-INT-001",
            category=InventoryCategory.objects.create(name="电子料", code="CAT-INT-001"),
            unit="pcs",
        )
        self.bom = BOM.objects.create(
            name="AI蓝牙耳机BOM", code="BOM-INT-001",
            product=self.product, creator=self.user,
        )
        BOMItem.objects.create(
            bom=self.bom, material_name="喇叭单元", material_code="MAT-INT-001",
            specification="", unit="pcs", quantity=Decimal("1.0000"),
        )
        self.production_plan = ProductionPlan.objects.create(
            name="AI集成计划", code="PLAN-INT-001", product=self.product,
            bom=self.bom, quantity=Decimal("100"), unit="pcs",
            plan_start_date=date(2026, 8, 1), plan_end_date=date(2026, 8, 31),
            manager=self.user, creator=self.user,
        )
        self.forecast_plan = DemandForecastPlan.objects.create(
            name="集成预测", code="DFP-INT-001",
            product=self.product,
            period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
            created_by=self.user, status="generated",
        )
        DemandForecastResult.objects.create(
            forecast_plan=self.forecast_plan,
            predicted_quantity=Decimal("200"), safety_stock=Decimal("56"),
            recommended_quantity=Decimal("120"), confidence=Decimal("88.00"),
            risk_level="medium", summary="预测偏紧",
        )
        self.price_review_order = PriceReviewOrder.objects.create(
            code="PRC-INT-001", inventory_item=self.inventory_item,
            supplier=self.supplier, quoted_price=Decimal("13.5000"),
            created_by=self.user,
        )
        PriceReviewConclusion.objects.create(
            review_order=self.price_review_order,
            result="exception", risk_level="high", summary="报价偏高",
            abnormal_items=["原材料"], negotiation_points=["原材料成本偏高"],
            reviewer=self.user,
        )

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_forecast_ai_summary_endpoint_returns_real_ai_summary(self, mock_call):
        mock_call.return_value = {
            "predicted_quantity": 210, "recommended_quantity": 130,
            "confidence": 85.5, "risk_level": "medium",
            "summary": "AI分析：需求小幅增长。",
        }
        response = self.client.get(
            reverse("supply_chain:forecast_ai_summary", args=[self.forecast_plan.id])
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("recommended_quantity", data["data"])
        self.assertTrue(mock_call.called)

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_price_review_ai_summary_endpoint_returns_real_ai_summary(self, mock_call):
        mock_call.return_value = {
            "result": "exception", "risk_level": "high",
            "summary": "原材料成本偏高，建议议价。",
            "abnormal_items": ["原材料成本"], "negotiation_points": ["对比三家询价"],
        }
        response = self.client.get(
            reverse("supply_chain:price_review_ai_summary", args=[self.price_review_order.id])
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("summary", data["data"])
        self.assertTrue(mock_call.called)

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_pr_review_ai_summary_endpoint_returns_real_ai_summary(self, mock_call):
        from apps.supply_chain.models import PRReviewRule, PRReviewTask

        task = PRReviewTask.objects.create(
            code="PRR-INT-001", title="集成PR审核",
            created_by=self.user, is_abnormal=True,
            recommended_action="manual_review", status="manual_review",
        )
        rule = PRReviewRule.objects.create(
            name="试产工单", code="NPI-INT-001",
            condition_json={"npi_trial": True},
            recommended_action="manual_review", priority=10,
        )
        task.matched_rules.add(rule)
        mock_call.return_value = {
            "is_abnormal": True, "recommended_action": "manual_review",
            "reason": "NPI试产需人工确认。", "risk_level": "high",
        }
        response = self.client.get(
            reverse("supply_chain:pr_review_ai_summary", args=[task.id])
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("summary", data["data"])
        self.assertTrue(mock_call.called)

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_forecast_run_uses_real_ai_prediction(self, mock_call):
        mock_call.return_value = {
            "predicted_quantity": 240,
            "recommended_quantity": 155,
            "confidence": 91,
            "risk_level": "medium",
            "summary": "AI预测显示需求增长，建议提高备料。",
        }
        response = self.client.post(reverse("supply_chain:forecast_run", args=[self.forecast_plan.id]), {
            "shipped_quantity": "120",
            "inventory_quantity": "40",
            "wip_quantity": "20",
            "inbound_quantity": "10",
            "prepared_quantity": "5",
            "manual_adjustment": "5",
            "predicted_quantity": "180",
            "avg_daily_demand": "8",
        })
        self.assertEqual(response.status_code, 302)
        self.forecast_plan.refresh_from_db()
        latest = self.forecast_plan.results.order_by("-id").first()
        self.assertTrue(mock_call.called)
        self.assertEqual(latest.predicted_quantity, Decimal("240"))
        self.assertEqual(latest.recommended_quantity, Decimal("155"))
        self.assertIn("AI预测", latest.summary)

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_forecast_run_falls_back_when_ai_numbers_are_invalid(self, mock_call):
        mock_call.return_value = {
            "predicted_quantity": "约240件",
            "recommended_quantity": "",
            "confidence": "较高",
            "risk_level": "medium",
            "summary": "AI返回了非标准数字，系统应保留规则兜底。",
        }
        response = self.client.post(reverse("supply_chain:forecast_run", args=[self.forecast_plan.id]), {
            "shipped_quantity": "120",
            "inventory_quantity": "40",
            "wip_quantity": "20",
            "inbound_quantity": "10",
            "prepared_quantity": "5",
            "manual_adjustment": "5",
            "predicted_quantity": "180",
            "avg_daily_demand": "8",
        })
        self.assertEqual(response.status_code, 302)
        latest = self.forecast_plan.results.order_by("-id").first()
        self.assertTrue(mock_call.called)
        self.assertEqual(latest.predicted_quantity, Decimal("100"))
        self.assertEqual(latest.confidence, Decimal("80.00"))

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_forecast_qa_uses_real_ai_answer(self, mock_call):
        mock_call.return_value = {"content": "AI回答：建议维持120件备料并关注库存。"}
        response = self.client.post(reverse("supply_chain:forecast_qa", args=[self.forecast_plan.id]), {
            "question": "为什么建议这个备料量？",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_call.called)
        self.assertContains(response, "AI回答")

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_inventory_analysis_page_uses_real_ai_summary(self, mock_call):
        mock_call.return_value = {"content": "AI库存体检：当前风险可控。"}
        refresh_response = self.client.post(reverse("supply_chain:inventory_ai_refresh"))
        response = self.client.get(reverse("supply_chain:inventory_analysis"))
        self.assertEqual(refresh_response.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_call.called)
        self.assertContains(response, "AI库存体检")

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_dashboard_uses_real_ai_overview(self, mock_call):
        mock_call.return_value = {"content": "AI总览：供应链整体风险可控。"}
        refresh_response = self.client.post(reverse("supply_chain:dashboard_ai_refresh"))
        response = self.client.get(reverse("supply_chain:dashboard"))
        self.assertEqual(refresh_response.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_call.called)
        self.assertContains(response, "AI总览")

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_pr_review_evaluate_uses_real_ai_decision(self, mock_call):
        from apps.supply_chain.models import PRReviewTask

        task = PRReviewTask.objects.create(
            code="PRR-AI-OP-001",
            title="AI操作PR",
            created_by=self.user,
        )
        mock_call.return_value = {
            "is_abnormal": True,
            "recommended_action": "manual_review",
            "reason": "AI判断尾数订单需人工复核。",
            "risk_level": "high",
        }
        response = self.client.post(reverse("supply_chain:pr_review_evaluate", args=[task.id]), {
            "scenario": "tail_order",
        })
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertTrue(mock_call.called)
        self.assertTrue(task.is_abnormal)
        self.assertIn("AI判断", str(task.evidence))

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_price_document_parse_uses_real_ai_parser(self, mock_call):
        from apps.supply_chain.models import PriceReviewDocument

        mock_call.return_value = {
            "material_cost": 8.8,
            "process_cost": 1.2,
            "labor_cost": 0.9,
            "loss_cost": 0.2,
            "package_cost": 0.3,
            "logistics_cost": 0.4,
            "profit_cost": 0.6,
        }
        response = self.client.post(reverse("supply_chain:price_review_parse_document", args=[self.price_review_order.id]), {
            "raw_text": "规格书：材料为铝壳，工艺喷涂，供应商报价明细略。",
        })
        self.assertEqual(response.status_code, 302)
        doc = PriceReviewDocument.objects.get(review_order=self.price_review_order)
        self.assertTrue(mock_call.called)
        self.assertEqual(doc.parsed_payload["material_cost"], "8.8000")

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_price_review_analyze_uses_real_ai_conclusion(self, mock_call):
        from apps.supply_chain.models import PriceReviewDocument

        PriceReviewDocument.objects.create(
            review_order=self.price_review_order,
            file_name="manual.txt",
            raw_text="",
            parsed_payload={
                "material_cost": "8.2000",
                "process_cost": "1.1000",
                "labor_cost": "0.7000",
                "loss_cost": "0.2000",
                "package_cost": "0.3000",
                "logistics_cost": "0.2000",
                "profit_cost": "0.5000",
            },
        )
        mock_call.return_value = {
            "result": "exception",
            "risk_level": "high",
            "summary": "AI核价：报价明显偏高。",
            "abnormal_items": ["原材料"],
            "negotiation_points": ["要求供应商解释材料溢价"],
        }
        response = self.client.post(reverse("supply_chain:price_review_analyze", args=[self.price_review_order.id]), {
            "historical_prices": "11.8,12.1",
            "market_price": "12.0",
            "target_price": "12.2",
        })
        self.assertEqual(response.status_code, 302)
        self.price_review_order.refresh_from_db()
        self.assertTrue(mock_call.called)
        self.assertIn("AI核价", self.price_review_order.ai_summary)

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_outsource_check_uses_real_ai_advice(self, mock_call):
        from apps.supply_chain.models import OutsourceIssueOrder

        order = OutsourceIssueOrder.objects.create(
            code="OIO-AI-OP-001",
            product=self.product,
            supplier=self.supplier,
            production_plan=self.production_plan,
            quantity=Decimal("100"),
            created_by=self.user,
        )
        mock_call.return_value = {"content": "AI齐套建议：物料齐套，可安排仓库备料。"}
        response = self.client.post(reverse("supply_chain:outsource_check", args=[order.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(mock_call.called)

        self.assertTrue(order.status_logs.filter(message__icontains="AI齐套建议").exists())

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_sample_list_uses_real_ai_priority_advice(self, mock_call):
        from apps.supply_chain.models import SampleRequest

        SampleRequest.objects.create(
            code="SMP-AI-OP-001",
            material_name="蓝牙芯片",
            specification="V5.4",
            supplier=self.supplier,
            engineer=self.user,
            requested_by=self.user,
            required_date=date(2026, 8, 10),
            quantity=Decimal("2"),
            status="pickup_pending",
        )
        mock_call.return_value = {"content": "AI打样建议：优先催领超期样品。"}
        refresh_response = self.client.post(reverse("supply_chain:sample_ai_refresh"))
        response = self.client.get(reverse("supply_chain:sample_list"))
        self.assertEqual(refresh_response.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_call.called)
        self.assertContains(response, "AI打样建议")

    @patch("apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai")
    def test_supply_chain_ai_timeout_returns_fast_fallback(self, mock_call):
        from apps.supply_chain.services.ai_services import supply_chain_ai

        original_timeout = supply_chain_ai.timeout_seconds
        supply_chain_ai.timeout_seconds = 0.05
        mock_call.side_effect = lambda *args, **kwargs: sleep(0.2) or {"content": "late"}

        try:
            started_at = perf_counter()
            result = supply_chain_ai.analyze_inventory_risk(
                total_items=10,
                high_risk_count=1,
                medium_risk_count=2,
                dead_stock_count=0,
                safety_breach_count=1,
                top_risk_items=["蓝牙芯片"],
            )
            elapsed = perf_counter() - started_at
        finally:
            supply_chain_ai.timeout_seconds = original_timeout

        self.assertLess(elapsed, 0.5)
        self.assertIn("AI响应超时", result)


class SupplyChainAIProductionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='supply-chain-ai-production',
            password='test-pass-123',
        )
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.status = 1
        self.user.save(update_fields=['is_superuser', 'is_staff', 'status'])
        self.client.force_login(self.user)

    @patch('apps.supply_chain.services.ai_services.AIAnalysisTool._call_ai')
    def test_dashboard_get_does_not_call_ai(self, mock_call):
        response = self.client.get(reverse('supply_chain:dashboard'))

        self.assertEqual(response.status_code, 200)
        mock_call.assert_not_called()

    def test_refresh_persists_successful_ai_result(self):
        from apps.supply_chain.services.ai_insight_service import refresh_ai_insight

        insight = refresh_ai_insight(
            scope='inventory',
            object_type='inventory_overview',
            object_id=0,
            generator=lambda: {'content': '库存风险可控', 'risk_level': 'low'},
            user=self.user,
        )

        self.assertEqual(insight.status, 'success')
        self.assertEqual(insight.content, '库存风险可控')
        self.assertEqual(insight.result_payload['risk_level'], 'low')

    def test_failed_refresh_preserves_last_successful_content(self):
        from apps.supply_chain.services.ai_insight_service import refresh_ai_insight

        refresh_ai_insight(
            scope='inventory',
            object_type='inventory_overview',
            object_id=0,
            generator=lambda: {'content': '上次有效结论'},
            user=self.user,
        )
        insight = refresh_ai_insight(
            scope='inventory',
            object_type='inventory_overview',
            object_id=0,
            generator=lambda: {'error': '模型超时'},
            user=self.user,
        )

        self.assertEqual(insight.status, 'error')
        self.assertEqual(insight.content, '上次有效结论')
        self.assertIn('模型超时', insight.error_message)


