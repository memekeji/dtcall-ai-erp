from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.contract.models import Product
from apps.department.models import Department
from apps.inventory.models import (
    Inventory,
    InventoryCategory,
    InventoryItem,
    StockIn,
    StockOut,
    StockTransaction,
    Warehouse,
)
from apps.production.models import (
    BOM,
    BOMItem,
    DataCollection,
    DataCollectionRecord,
    DataCollectionTask,
    DataSource,
    Equipment,
    MaterialIssue,
    MaterialRequest,
    MaterialReturn,
    MaterialScrap,
    ProcessRoute,
    ProductReceipt,
    ProductionOrderChange,
    ProductionPlan,
    ProductionProcedure,
    ProductionDataPoint,
    ProcedureSet,
    ProductionTask,
    QualityCheck,
    WorkCompletionRedFlush,
    WorkCompletionReport,
)
from apps.production.services.data_collector import DataCollectorService
from apps.production.services.material_flow_service import MaterialFlowService
from apps.production.services.monitoring_service import RealTimeDataManager


class ProductionMaterialFlowTests(TestCase):
    def setUp(self):
        RealTimeDataManager().active_alerts = []
        self.user = get_user_model().objects.create_user(
            username='tester',
            email='tester@example.com',
            password='pass123456',
            name='测试用户',
            thumb='',
        )
        self.user.is_superuser = True
        self.user.is_staff = 1
        self.user.save()
        self.department = Department.objects.create(name='生产部', code='PD-01')
        self.material_category = InventoryCategory.objects.create(
            name='原材料',
            code='CAT-MAT',
            category_type='material',
        )
        self.product_category = InventoryCategory.objects.create(
            name='产成品',
            code='CAT-FIN',
            category_type='product',
        )
        self.warehouse = Warehouse.objects.create(
            name='主仓库',
            code='WH-001',
            warehouse_type='finished',
            status=1,
            is_default=True,
        )
        self.material_item = InventoryItem.objects.create(
            name='测试螺栓',
            code='MAT-BOLT',
            category=self.material_category,
            unit='PCS',
            standard_cost=Decimal('2.50'),
        )
        self.finished_item = InventoryItem.objects.create(
            name='测试成品',
            code='PROD-001',
            category=self.product_category,
            unit='EA',
            standard_cost=Decimal('99.00'),
        )
        Inventory.objects.create(
            item=self.material_item,
            warehouse=self.warehouse,
            quantity=Decimal('200.0000'),
            available_quantity=Decimal('200.0000'),
            unit_cost=Decimal('2.50'),
        )
        self.product = Product.objects.create(
            name='测试成品',
            code='PROD-001',
            price=Decimal('99.00'),
            unit='EA',
            admin=self.user,
        )
        self.bom = BOM.objects.create(
            name='测试BOM',
            code='BOM-001',
            product=self.product,
            creator=self.user,
        )
        self.bom_item = BOMItem.objects.create(
            bom=self.bom,
            material_name='测试螺栓',
            material_code='MAT-BOLT',
            specification='M6',
            unit='PCS',
            quantity=Decimal('2.0000'),
            unit_cost=Decimal('2.50'),
            total_cost=Decimal('5.00'),
        )
        self.plan = ProductionPlan.objects.create(
            name='测试计划',
            code='PLAN-001',
            product=self.product,
            bom=self.bom,
            quantity=Decimal('10.00'),
            unit='EA',
            plan_start_date=timezone.now().date(),
            plan_end_date=timezone.now().date() + timedelta(days=3),
            status=2,
            department=self.department,
            manager=self.user,
            creator=self.user,
        )
        self.procedure = ProductionProcedure.objects.create(
            name='装配',
            code='PROC-001',
            department=self.department,
            creator=self.user,
        )
        self.task = ProductionTask.objects.create(
            plan=self.plan,
            name='装配任务',
            code='TASK-001',
            procedure=self.procedure,
            quantity=Decimal('10.00'),
            plan_start_time=timezone.now(),
            plan_end_time=timezone.now() + timedelta(hours=8),
            assignee=self.user,
            creator=self.user,
        )

    def test_material_request_generation_uses_bom(self):
        material_request = MaterialRequest.objects.create(
            production_plan=self.plan,
            production_task=self.task,
            code='REQ-001',
            created_by=self.user,
        )

        MaterialFlowService.ensure_material_request_items(material_request)

        self.assertEqual(material_request.items.count(), 1)
        request_item = material_request.items.first()
        self.assertEqual(request_item.material_code, 'MAT-BOLT')
        self.assertEqual(request_item.request_quantity, Decimal('2.0000'))
        self.assertEqual(material_request.total_amount, Decimal('5.00'))

    def test_execute_material_issue_updates_inventory(self):
        material_request = MaterialRequest.objects.create(
            production_plan=self.plan,
            production_task=self.task,
            code='REQ-002',
            created_by=self.user,
            status=2,
        )
        MaterialFlowService.ensure_material_request_items(material_request)
        issue = MaterialIssue.objects.create(
            code='ISS-001',
            material_request=material_request,
            production_plan=self.plan,
            created_by=self.user,
            status=2,
        )
        MaterialFlowService.ensure_material_issue_items(issue)

        MaterialFlowService.execute_material_issue(issue, self.user)

        inventory = Inventory.objects.get(item=self.material_item, warehouse=self.warehouse)
        material_request.refresh_from_db()
        request_item = material_request.items.first()
        self.assertEqual(issue.status, 3)
        self.assertEqual(inventory.quantity, Decimal('198.0000'))
        self.assertEqual(request_item.issued_quantity, Decimal('2.0000'))
        self.assertEqual(StockOut.objects.filter(stock_out_type='production').count(), 1)
        self.assertTrue(StockTransaction.objects.filter(reference_code='ISS-001').exists())

    def test_execute_material_return_restores_inventory(self):
        material_request = MaterialRequest.objects.create(
            production_plan=self.plan,
            production_task=self.task,
            code='REQ-003',
            created_by=self.user,
            status=2,
        )
        MaterialFlowService.ensure_material_request_items(material_request)
        issue = MaterialIssue.objects.create(
            code='ISS-002',
            material_request=material_request,
            production_plan=self.plan,
            created_by=self.user,
            status=2,
        )
        MaterialFlowService.ensure_material_issue_items(issue)
        MaterialFlowService.execute_material_issue(issue, self.user)
        material_return = MaterialReturn.objects.create(
            code='RET-001',
            material_issue=issue,
            production_plan=self.plan,
            created_by=self.user,
            status=2,
            return_reason='多领退回',
        )
        MaterialFlowService.ensure_material_return_items(material_return)

        MaterialFlowService.execute_material_return(material_return, self.user)

        inventory = Inventory.objects.get(item=self.material_item, warehouse=self.warehouse)
        self.assertEqual(material_return.status, 3)
        self.assertEqual(inventory.quantity, Decimal('200.0000'))
        self.assertEqual(StockIn.objects.filter(stock_in_type='return').count(), 1)

    def test_execute_material_scrap_creates_scrap_transaction(self):
        material_request = MaterialRequest.objects.create(
            production_plan=self.plan,
            production_task=self.task,
            code='REQ-004',
            created_by=self.user,
            status=2,
        )
        MaterialFlowService.ensure_material_request_items(material_request)
        issue = MaterialIssue.objects.create(
            code='ISS-003',
            material_request=material_request,
            production_plan=self.plan,
            created_by=self.user,
            status=2,
        )
        MaterialFlowService.ensure_material_issue_items(issue)
        MaterialFlowService.execute_material_issue(issue, self.user)
        scrap = MaterialScrap.objects.create(
            code='SCR-001',
            material_issue=issue,
            production_plan=self.plan,
            created_by=self.user,
            status=2,
            scrap_reason='来料破损',
        )
        MaterialFlowService.ensure_material_scrap_items(scrap)

        MaterialFlowService.execute_material_scrap(scrap, self.user)

        self.assertEqual(scrap.status, 3)
        self.assertTrue(StockOut.objects.filter(stock_out_type='scrap').exists())
        self.assertTrue(StockTransaction.objects.filter(transaction_type='scrap', reference_code='SCR-001').exists())

    def test_execute_product_receipt_creates_inventory_inbound(self):
        receipt = ProductReceipt.objects.create(
            code='PRD-001',
            production_plan=self.plan,
            created_by=self.user,
            status=2,
            receipt_date=timezone.now().date(),
            receipt_quantity=Decimal('8.00'),
            storage_location='成品区-A01',
        )

        MaterialFlowService.execute_product_receipt(receipt, self.user)

        inventory = Inventory.objects.get(item=self.finished_item, warehouse=self.warehouse)
        self.assertEqual(receipt.status, 3)
        self.assertEqual(inventory.quantity, Decimal('8.0000'))
        self.assertTrue(StockIn.objects.filter(stock_in_type='production').exists())

    def test_material_dashboard_route_renders(self):
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse('production:material_management_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_approve_completion_report_syncs_task_and_creates_receipt(self):
        client = Client()
        client.force_login(self.user)
        report = WorkCompletionReport.objects.create(
            code='WCR-001',
            production_task=self.task,
            reported_quantity=Decimal('10.00'),
            qualified_quantity=Decimal('8.00'),
            defective_quantity=Decimal('2.00'),
            created_by=self.user,
        )

        response = client.get(reverse('production:work_completion_report_approve', args=[report.pk]))

        self.assertEqual(response.status_code, 302)
        report.refresh_from_db()
        self.task.refresh_from_db()
        receipt = ProductReceipt.objects.get(completion_report=report)
        self.assertEqual(report.status, 2)
        self.assertEqual(self.task.completed_quantity, Decimal('10.00'))
        self.assertEqual(self.task.qualified_quantity, Decimal('8.00'))
        self.assertEqual(receipt.receipt_quantity, Decimal('8.00'))

    def test_execute_order_change_updates_plan_quantity(self):
        client = Client()
        client.force_login(self.user)
        change = ProductionOrderChange.objects.create(
            production_plan=self.plan,
            change_type='quantity',
            change_reason='客户追加',
            old_value={'quantity': '10.00'},
            new_value={'quantity': '15.00'},
            status=2,
            creator=self.user,
        )

        response = client.get(reverse('production:production_order_change_execute', args=[change.pk]))

        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        change.refresh_from_db()
        self.assertEqual(self.plan.quantity, Decimal('15.00'))
        self.assertEqual(change.status, 3)

    def test_red_flush_cannot_execute_after_receipt_stock_in(self):
        client = Client()
        client.force_login(self.user)
        report = WorkCompletionReport.objects.create(
            code='WCR-002',
            production_task=self.task,
            reported_quantity=Decimal('10.00'),
            qualified_quantity=Decimal('8.00'),
            defective_quantity=Decimal('2.00'),
            created_by=self.user,
            status=2,
        )
        receipt = ProductReceipt.objects.create(
            code='PRD-002',
            completion_report=report,
            production_plan=self.plan,
            created_by=self.user,
            status=2,
            receipt_date=timezone.now().date(),
            receipt_quantity=Decimal('8.00'),
            storage_location='成品库-A01',
        )
        MaterialFlowService.execute_product_receipt(receipt, self.user)
        red_flush = WorkCompletionRedFlush.objects.create(
            code='RF-001',
            completion_report=report,
            red_flush_reason='异常回退',
            red_flush_quantity=Decimal('2.00'),
            created_by=self.user,
            status=2,
        )

        response = client.get(reverse('production:work_completion_red_flush_execute', args=[red_flush.pk]))

        self.assertEqual(response.status_code, 302)
        red_flush.refresh_from_db()
        self.assertEqual(red_flush.status, 2)

    def test_create_bom_with_inline_items(self):
        client = Client()
        client.force_login(self.user)

        response = client.post(reverse('production:bom_add'), data={
            'name': '耳机BOM',
            'code': 'BOM-NEW',
            'product': self.product.pk,
            'version': '2.0',
            'description': '测试新增BOM',
            'status': 'on',
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-material_name': '测试螺栓',
            'items-0-material_code': 'MAT-BOLT',
            'items-0-specification': 'M6',
            'items-0-unit': 'PCS',
            'items-0-quantity': '3.0000',
            'items-0-unit_cost': '2.50',
            'items-0-total_cost': '7.50',
            'items-0-supplier': '默认供应商',
            'items-0-remark': '自动测试',
        })

        self.assertEqual(response.status_code, 302)
        bom = BOM.objects.get(code='BOM-NEW')
        self.assertEqual(bom.items.count(), 1)
        self.assertEqual(bom.items.first().total_cost, Decimal('7.50'))

    def test_create_procedureset_with_inline_items_updates_totals(self):
        client = Client()
        client.force_login(self.user)

        response = client.post(reverse('production:procedureset_add'), data={
            'name': '装配工序集',
            'code': 'PS-001',
            'description': '测试工序集',
            'status': 'on',
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-procedure': str(self.procedure.pk),
            'items-0-sequence': '1',
            'items-0-estimated_time': '2.50',
        })

        self.assertEqual(response.status_code, 302)
        procedureset = ProcedureSet.objects.get(code='PS-001')
        self.assertEqual(procedureset.proceduresetitem_set.count(), 1)
        self.assertEqual(procedureset.total_time, Decimal('2.50'))
        self.assertEqual(procedureset.total_cost, Decimal('0.00'))

    def test_create_process_route_with_inline_items_updates_totals(self):
        client = Client()
        client.force_login(self.user)

        response = client.post(reverse('production:process_route_add'), data={
            'name': '装配路线',
            'code': 'PR-001',
            'description': '测试工艺路线',
            'product': self.product.pk,
            'total_time': '0',
            'total_cost': '0',
            'status': '1',
            'version': '1.0',
            'effective_date': timezone.now().date().isoformat(),
            'expiry_date': '',
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-procedure': str(self.procedure.pk),
            'items-0-sequence': '1',
            'items-0-estimated_time': '1.50',
            'items-0-workstation': 'A01',
            'items-0-work_instruction': '按标准作业',
            'items-0-quality_check_points': '首件确认',
            'items-0-cycle_time': '35.00',
        })

        self.assertEqual(response.status_code, 302)
        route = ProcessRoute.objects.get(code='PR-001')
        self.assertEqual(route.processrouteitem_set.count(), 1)
        self.assertEqual(route.total_time, Decimal('1.50'))

    def test_procedureset_detail_route_renders(self):
        procedureset = ProcedureSet.objects.create(
            name='测试工序集',
            code='PS-ROUTE',
            creator=self.user,
        )
        procedureset.proceduresetitem_set.create(
            procedure=self.procedure,
            sequence=1,
            estimated_time=Decimal('1.00'),
        )
        client = Client()
        client.force_login(self.user)

        response = client.get(reverse('production:procedureset_detail', args=[procedureset.pk]))

        self.assertEqual(response.status_code, 200)

    def test_quality_check_add_sets_created_by_and_summary_is_real(self):
        client = Client()
        client.force_login(self.user)

        response = client.post(reverse('production:quality_check_add'), data={
            'task': self.task.pk,
            'check_time': timezone.now().strftime('%Y-%m-%dT%H:%M'),
            'check_quantity': '10.00',
            'qualified_quantity': '9.00',
            'defective_quantity': '1.00',
            'result': 2,
            'defect_description': '外观瑕疵',
            'improvement_suggestion': '增加首检',
        })

        self.assertEqual(response.status_code, 302)
        quality = QualityCheck.objects.get(task=self.task)
        self.assertEqual(quality.created_by, self.user)

        list_response = client.get(reverse('production:quality_check_list'), {'task': self.task.pk, 'result': 2})
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.context['summary']['unqualified_count'], 1)
        self.assertEqual(list_response.context['avg_qualified_rate'], 90.0)

    def test_data_collection_add_sets_created_by(self):
        client = Client()
        client.force_login(self.user)
        equipment = self.task.equipment
        if equipment is None:
            equipment = Equipment.objects.create(
                name='采集设备',
                code='EQ-001',
                department=self.department,
                creator=self.user,
            )
            self.task.equipment = equipment
            self.task.save(update_fields=['equipment'])

        response = client.post(reverse('production:data_collection_add'), data={
            'task': self.task.pk,
            'equipment': equipment.pk,
            'parameter_name': '温度',
            'parameter_value': '26.5000',
            'unit': 'C',
            'standard_min': '20.0000',
            'standard_max': '30.0000',
            'is_normal': 'on',
            'collect_time': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        })

        self.assertEqual(response.status_code, 302)
        collection = DataCollection.objects.get(task=self.task, parameter_name='温度')
        self.assertEqual(collection.created_by, self.user)

    def test_data_source_and_collection_task_add_set_creator(self):
        client = Client()
        client.force_login(self.user)

        response = client.post(reverse('production:data_source_add'), data={
            'name': '设备API',
            'code': 'SRC-API',
            'source_type': 'api',
            'description': '测试数据源',
            'endpoint_url': 'https://example.com/data',
            'auth_type': 'none',
            'request_method': 'GET',
            'request_headers': '{}',
            'request_params': '{}',
            'request_body': '',
            'timeout': 30,
            'retry_count': 3,
            'collection_interval': 60,
            'is_active': 'on',
        })

        self.assertEqual(response.status_code, 302)
        source = DataSource.objects.get(code='SRC-API')
        self.assertEqual(source.creator, self.user)

        response = client.post(reverse('production:data_collection_task_add'), data={
            'name': '定时采集',
            'task_type': 'scheduled',
            'data_sources': [source.pk],
            'cron_expression': '0 */1 * * *',
            'interval_seconds': '',
            'max_retries': 3,
            'timeout_seconds': 300,
            'status': 'pending',
            'is_active': 'on',
        })

        self.assertEqual(response.status_code, 302)
        task = DataCollectionTask.objects.get(name='定时采集')
        self.assertEqual(task.creator, self.user)

    def test_data_collector_can_resolve_equipment_code_for_data_points(self):
        equipment = Equipment.objects.create(
            name='贴片机-01',
            code='EQ-SMT-01',
            department=self.department,
            creator=self.user,
        )
        self.task.equipment = equipment
        self.task.save(update_fields=['equipment'])
        data_source = DataSource.objects.create(
            name='SMT接口',
            code='SRC-SMT',
            source_type='api',
            endpoint_url='https://example.com/smt',
            creator=self.user,
        )
        record = DataCollectionRecord.objects.create(
            data_source=data_source,
            status='success',
            processed_data={
                'equipment_code': 'EQ-SMT-01',
                'task_code': self.task.code,
                'procedure_code': self.procedure.code,
                'temperature': 31.5,
                'timestamp': timezone.now().isoformat(),
            },
            record_count=1,
            success_count=1,
        )

        DataCollectorService()._save_data_points(record)

        point = ProductionDataPoint.objects.get(equipment=equipment, metric_name='temperature')
        self.assertEqual(point.task, self.task)
        self.assertEqual(point.procedure, self.procedure)

    def test_task_list_supports_assignee_filter(self):
        other_user = get_user_model().objects.create_user(
            username='operator2',
            email='operator2@example.com',
            password='pass123456',
            name='操作员2',
            thumb='',
        )
        other_user.is_staff = 1
        other_user.save()
        other_task = ProductionTask.objects.create(
            plan=self.plan,
            name='分流任务',
            code='TASK-002',
            procedure=self.procedure,
            quantity=Decimal('5.00'),
            plan_start_time=timezone.now(),
            plan_end_time=timezone.now() + timedelta(hours=4),
            assignee=other_user,
            creator=self.user,
        )
        client = Client()
        client.force_login(self.user)

        response = client.get(reverse('production:production_task_list'), {'assignee': other_user.pk})

        self.assertEqual(response.status_code, 200)
        page_items = list(response.context['page_obj'].object_list)
        self.assertEqual(page_items, [other_task])

    def test_alert_api_filters_by_severity_and_time_range(self):
        manager = RealTimeDataManager()
        manager.active_alerts = [
            {
                'id': 'alert-high',
                'equipment_id': 1,
                'rule_id': 'quality_issue',
                'name': '高优先级告警',
                'message': '测试异常',
                'severity': 'high',
                'timestamp': timezone.now().isoformat(),
                'acknowledged': False,
            },
            {
                'id': 'alert-low-old',
                'equipment_id': 1,
                'rule_id': 'equipment_maintenance',
                'name': '低优先级告警',
                'message': '历史提醒',
                'severity': 'low',
                'timestamp': (timezone.now() - timedelta(days=10)).isoformat(),
                'acknowledged': False,
            },
        ]
        client = Client()
        client.force_login(self.user)

        response = client.get(reverse('production:alert_api'), {'severity': 'high', 'time_range': 'today'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(len(payload['alerts']), 1)
        self.assertEqual(payload['alerts'][0]['id'], 'alert-high')
