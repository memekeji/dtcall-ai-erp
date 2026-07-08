from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from apps.contract.models import Product, Supplier
from apps.inventory.models import Inventory, InventoryItem, StockTransaction
from apps.production.models import BOM, ProductionPlan
from apps.supply_chain.models import (
    DemandForecastPlan,
    DemandForecastResult,
    DemandForecastSnapshot,
    MaterialPreparationReview,
    OutsourceIssueOrder,
    OutsourceIssueItem,
    OutsourceIssueStatusLog,
    PRReviewRule,
    PRReviewTask,
    PriceReviewComponent,
    PriceReviewConclusion,
    PriceReviewOrder,
    SamplePickupRecord,
    SampleReceipt,
    SampleRequest,
)
from apps.supply_chain.services.forecast_service import (
    build_snapshot_payload,
    calculate_recommended_preparation_quantity,
    calculate_safety_stock,
)
from apps.supply_chain.services.inventory_analysis_service import build_inventory_analysis_rows
from apps.supply_chain.services.outsource_service import build_issue_item_payload, summarize_issue_order_status
from apps.supply_chain.services.price_review_service import (
    build_price_review_conclusion,
    compare_component_amounts,
)
from apps.supply_chain.services.sample_service import generate_sample_request_code


def _pick_supplier(suppliers, index):
    if not suppliers:
        return None
    return suppliers[index % len(suppliers)]


def _build_bootstrap_price_components(*, quote, standard_cost, average_cost):
    quote = Decimal(str(quote or 0))
    standard_cost = Decimal(str(standard_cost or 0))
    average_cost = Decimal(str(average_cost or 0))
    benchmark = average_cost or standard_cost or quote
    if quote <= 0:
        return []

    material_amount = min((quote * Decimal('0.62')).quantize(Decimal('0.0000')), benchmark.quantize(Decimal('0.0000')))
    remaining = max((quote - material_amount).quantize(Decimal('0.0000')), Decimal('0.0000'))
    ratio_map = [
        ('加工', 'process', Decimal('0.28')),
        ('人工', 'labor', Decimal('0.20')),
        ('损耗', 'loss', Decimal('0.08')),
        ('包装', 'package', Decimal('0.10')),
        ('物流', 'logistics', Decimal('0.12')),
        ('利润', 'profit', Decimal('0.22')),
    ]
    components = [{
        'component_type': 'material',
        'component_name': '原材料',
        'amount': material_amount,
        'reference_amount': benchmark.quantize(Decimal('0.0000')),
    }]
    allocated = Decimal('0.0000')
    for index, (component_name, component_type, ratio) in enumerate(ratio_map):
        amount = (
            remaining - allocated
            if index == len(ratio_map) - 1
            else (remaining * ratio).quantize(Decimal('0.0000'))
        )
        amount = amount.quantize(Decimal('0.0000'))
        allocated += amount
        components.append({
            'component_type': component_type,
            'component_name': component_name,
            'amount': amount,
            'reference_amount': Decimal('0.0000'),
        })
    return components


def _ensure_default_pr_rules():
    default_rules = [
        {
            'code': 'PR-FILTER-INTERCO-TAIL',
            'name': '公司间尾数订单',
            'scenario': 'intercompany_tail_order',
            'condition_json': {'intercompany_tail_order': True},
            'recommended_action': PRReviewRule.ACTION_FILTER,
            'priority': 10,
        },
        {
            'code': 'PR-FILTER-OUTSOURCE-TAIL',
            'name': '委外尾数订单',
            'scenario': 'outsource_tail_order',
            'condition_json': {'outsource_tail_order': True},
            'recommended_action': PRReviewRule.ACTION_FILTER,
            'priority': 20,
        },
        {
            'code': 'PR-FILTER-REWORK',
            'name': '异常工单 / 返工单',
            'scenario': 'rework_order',
            'condition_json': {'rework_order': True},
            'recommended_action': PRReviewRule.ACTION_FILTER,
            'priority': 30,
        },
        {
            'code': 'PR-URGENT-SHORTAGE',
            'name': '紧急缺料订单',
            'scenario': 'urgent_shortage',
            'condition_json': {'is_urgent': True, 'lt_shortage': True},
            'recommended_action': PRReviewRule.ACTION_URGENT,
            'priority': 40,
        },
        {
            'code': 'PR-NPI-TRIAL',
            'name': 'NPI试产工单',
            'scenario': 'npi_trial',
            'condition_json': {'npi_trial': True},
            'recommended_action': PRReviewRule.ACTION_URGENT,
            'priority': 50,
        },
        {
            'code': 'PR-APPROVE-STANDARD',
            'name': '常规需求审批',
            'scenario': 'normal',
            'condition_json': {
                'is_urgent': False,
                'lt_shortage': False,
                'tail_order': False,
                'intercompany_tail_order': False,
                'outsource_tail_order': False,
                'rework_order': False,
                'npi_trial': False,
            },
            'recommended_action': PRReviewRule.ACTION_APPROVE,
            'priority': 90,
        },
    ]

    for row in default_rules:
        PRReviewRule.objects.get_or_create(
            code=row['code'],
            defaults={
                'name': row['name'],
                'scenario': row['scenario'],
                'condition_json': row['condition_json'],
                'recommended_action': row['recommended_action'],
                'priority': row['priority'],
                'is_active': True,
            },
        )


def bootstrap_supply_chain_workspace(*, user, serial_factory):
    """Create draft supply-chain work items from existing upstream modules."""
    result = {
        'forecast_created': 0,
        'outsource_created': 0,
        'pr_created': 0,
        'price_review_created': 0,
        'sample_created': 0,
    }

    _ensure_default_pr_rules()

    seeded_product_ids = set()
    source_products = []
    for plan in ProductionPlan.objects.select_related('product').order_by('-create_time')[:8]:
        if plan.product_id and plan.product_id not in seeded_product_ids:
            source_products.append(plan.product)
            seeded_product_ids.add(plan.product_id)
    for product in Product.objects.order_by('-create_time')[:8]:
        if product.id not in seeded_product_ids:
            source_products.append(product)
            seeded_product_ids.add(product.id)

    for product in source_products:
        exists = DemandForecastPlan.objects.filter(product=product).exists()
        if exists:
            continue
        today = date.today()
        period_start = today.replace(day=1)
        period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        DemandForecastPlan.objects.create(
            # Product is the legal source; snapshot/result can be derived later from plans/inventory.
            name=f'{product.name}月度滚动预测',
            code=serial_factory('DFP', DemandForecastPlan),
            product=product,
            period_start=period_start,
            period_end=period_end,
            version='1.0',
            summary='基于现有产品主数据自动初始化的预测计划',
            created_by=user,
        )
        result['forecast_created'] += 1

    plans = ProductionPlan.objects.filter(status__in=[1, 2, 3]).select_related('product', 'bom')[:8]
    suppliers = list(Supplier.objects.filter(is_active=True).order_by('id'))
    for plan in plans:
        if OutsourceIssueOrder.objects.filter(production_plan=plan).exists():
            continue
        bom = getattr(plan, 'bom', None) or BOM.objects.filter(product=plan.product).order_by('-id').first()
        if bom is None:
            continue
        order = OutsourceIssueOrder.objects.create(
            code=serial_factory('OIO', OutsourceIssueOrder),
            product=plan.product,
            supplier=_pick_supplier(suppliers, result['outsource_created']),
            production_plan=plan,
            quantity=plan.quantity or Decimal('1'),
            created_by=user,
        )
        OutsourceIssueStatusLog.objects.create(
            issue_order=order,
            from_status='',
            to_status=order.status,
            message='基于生产计划自动初始化',
            operator=user,
        )
        result['outsource_created'] += 1

    pr_created = 0
    for row in build_inventory_analysis_rows()[:8]:
        item = row['item']
        if row['risk_level'] == 'low':
            continue
        if PRReviewTask.objects.filter(source_type='inventory_risk', source_code=item.code).exists():
            continue
        PRReviewTask.objects.create(
            code=serial_factory('PRR', PRReviewTask),
            title=f'库存补货PR审核 - {item.name}',
            source_type='inventory_risk',
            source_code=item.code,
            created_by=user,
            is_abnormal=True,
            recommended_action='manual_review',
            status=PRReviewTask.STATUS_MANUAL_REVIEW,
            evidence={
                'risk_level': row['risk_level'],
                'available_quantity': str(row['available_quantity']),
                'safety_stock': str(row['safety_stock']),
                'reorder_point': str(row['reorder_point']),
            },
        )
        pr_created += 1

    if pr_created == 0:
        for plan in ProductionPlan.objects.filter(status__in=[1, 2, 3]).select_related('product')[:6]:
            if PRReviewTask.objects.filter(source_type='production_plan', source_code=plan.code).exists():
                continue
            PRReviewTask.objects.create(
                code=serial_factory('PRR', PRReviewTask),
                title=f'生产计划补货评审 - {plan.name}',
                source_type='production_plan',
                source_code=plan.code,
                created_by=user,
                recommended_action='approve',
                status=PRReviewTask.STATUS_RULE_MATCHED,
                evidence={
                    'plan_quantity': str(plan.quantity),
                    'product': getattr(plan.product, 'name', ''),
                    'status': plan.status,
                },
            )
            pr_created += 1

    result['pr_created'] = pr_created

    cost_items = InventoryItem.objects.exclude(standard_cost=0).order_by('-standard_cost')[:8]
    for index, item in enumerate(cost_items):
        if PriceReviewOrder.objects.filter(inventory_item=item).exists():
            continue
        supplier = _pick_supplier(suppliers, index)
        quote = item.latest_cost or item.average_cost or item.standard_cost or Decimal('0')
        PriceReviewOrder.objects.create(
            code=serial_factory('PRC', PriceReviewOrder),
            inventory_item=item,
            supplier=supplier,
            quoted_price=quote,
            created_by=user,
            ai_summary='基于物料成本主数据自动初始化的待复核报价',
        )
        result['price_review_created'] += 1

    sample_products = Product.objects.order_by('-create_time')[:6]
    for product in sample_products:
        if SampleRequest.objects.filter(material_name=product.name, specification=product.specs).exists():
            continue
        SampleRequest.objects.create(
            code=generate_sample_request_code(current_date=date.today(), sequence=SampleRequest.objects.count() + 1),
            material_name=product.name,
            specification=product.specs,
            supplier=_pick_supplier(suppliers, result['sample_created']),
            engineer=getattr(product, 'admin', None) or user,
            requested_by=user,
            required_date=date.today() + timedelta(days=7),
            quantity=Decimal('1'),
            status=SampleRequest.STATUS_DRAFT,
            remark='基于产品主数据自动初始化的打样需求草稿',
        )
        result['sample_created'] += 1

    sample_requests = list(SampleRequest.objects.order_by('create_time')[:6])
    for index, sample_request in enumerate(sample_requests):
        if sample_request.supplier_id is None:
            sample_request.supplier = _pick_supplier(suppliers, index)
            sample_request.save(update_fields=['supplier', 'update_time'])
        if index == 0 and sample_request.status == SampleRequest.STATUS_DRAFT:
            sample_request.status = SampleRequest.STATUS_ORDERED
            sample_request.save(update_fields=['status', 'update_time'])
        elif index in {1, 2, 3, 4, 5}:
            receipt, _ = SampleReceipt.objects.get_or_create(
                sample_request=sample_request,
                defaults={
                    'received_quantity': sample_request.quantity or Decimal('1'),
                    'location': '研发样品柜',
                    'receiver': user,
                },
            )
            if sample_request.status in {SampleRequest.STATUS_DRAFT, SampleRequest.STATUS_ORDERED}:
                sample_request.status = SampleRequest.STATUS_PICKUP_PENDING
                sample_request.save(update_fields=['status', 'update_time'])
            if index in {4, 5} and not SamplePickupRecord.objects.filter(sample_request=sample_request).exists():
                SamplePickupRecord.objects.create(
                    sample_request=sample_request,
                    picked_by=user,
                    picked_at=receipt.received_at + timedelta(hours=4),
                    is_overdue=False,
                    note='基于系统初始化的领样闭环',
                )
                sample_request.status = SampleRequest.STATUS_PICKED_UP
                sample_request.save(update_fields=['status', 'update_time'])

    for index, order in enumerate(OutsourceIssueOrder.objects.filter(supplier__isnull=True).order_by('id')):
        order.supplier = _pick_supplier(suppliers, index)
        order.save(update_fields=['supplier', 'update_time'])

    for index, sample_request in enumerate(SampleRequest.objects.filter(supplier__isnull=True).order_by('id')):
        sample_request.supplier = _pick_supplier(suppliers, index)
        sample_request.save(update_fields=['supplier', 'update_time'])

    for issue_item in OutsourceIssueItem.objects.filter(inventory_item__isnull=True).exclude(material_code='').order_by('id'):
        matched_inventory = InventoryItem.objects.filter(code=issue_item.material_code).order_by('id').first()
        if matched_inventory is None:
            continue
        issue_item.inventory_item = matched_inventory
        issue_item.save(update_fields=['inventory_item'])

    # Enrich forecast plans into usable results whenever production plans exist.
    transaction_total = StockTransaction.objects.order_by('-create_time').aggregate(total_qty=Sum('quantity')).get('total_qty') or Decimal('0')
    for plan in DemandForecastPlan.objects.filter(results__isnull=True).select_related('product'):
        product_plan = ProductionPlan.objects.filter(product=plan.product).order_by('-create_time').first()
        if product_plan is not None:
            predicted_quantity = Decimal(str(product_plan.quantity or 0))
            confidence = Decimal('82.00')
            summary = '基于生产计划数量自动生成的预测建议'
        else:
            predicted_quantity = Decimal(str(transaction_total / Decimal('12'))) if transaction_total else Decimal('0')
            if predicted_quantity <= 0:
                continue
            confidence = Decimal('60.00')
            summary = '基于系统库存交易均值自动生成的参考预测'
        avg_daily = (predicted_quantity / Decimal('30')) if predicted_quantity > 0 else Decimal('1')
        snapshot_payload = build_snapshot_payload(
            shipped_quantity=predicted_quantity * Decimal('0.70'),
            inventory_quantity=Decimal('0'),
            wip_quantity=Decimal('0'),
            inbound_quantity=Decimal('0'),
            prepared_quantity=Decimal('0'),
            manual_adjustment=Decimal('0'),
        )
        snapshot = DemandForecastSnapshot.objects.create(
            forecast_plan=plan,
            product=plan.product,
            shipped_quantity=snapshot_payload['shipped_quantity'],
            inventory_quantity=snapshot_payload['inventory_quantity'],
            wip_quantity=snapshot_payload['wip_quantity'],
            inbound_quantity=snapshot_payload['inbound_quantity'],
            prepared_quantity=snapshot_payload['prepared_quantity'],
            manual_adjustment=snapshot_payload['manual_adjustment'],
            notes='基于生产计划自动初始化的预测快照',
        )
        safety_stock = calculate_safety_stock(avg_daily)
        recommended_quantity = calculate_recommended_preparation_quantity(
            predicted_quantity=predicted_quantity,
            safety_stock=safety_stock,
            inventory_quantity=snapshot.inventory_quantity,
            wip_quantity=snapshot.wip_quantity,
            inbound_quantity=snapshot.inbound_quantity,
            prepared_quantity=snapshot.prepared_quantity,
            manual_adjustment=snapshot.manual_adjustment,
        )
        result_row = DemandForecastResult.objects.create(
            forecast_plan=plan,
            predicted_quantity=predicted_quantity,
            safety_stock=safety_stock,
            recommended_quantity=recommended_quantity,
            confidence=confidence,
            risk_level='medium' if recommended_quantity > 0 else 'low',
            summary=summary,
        )
        MaterialPreparationReview.objects.create(
            forecast_result=result_row,
            code=serial_factory('MPR', MaterialPreparationReview),
        )
        plan.status = DemandForecastPlan.STATUS_REVIEWING
        plan.save(update_fields=['status', 'update_time'])

    # Enrich outsource orders with completeness check results.
    for index, order in enumerate(OutsourceIssueOrder.objects.filter(items__isnull=True).select_related('production_plan__bom', 'product')):
        bom = getattr(order.production_plan, 'bom', None) if order.production_plan_id else None
        if bom is None and order.product_id:
            bom = BOM.objects.filter(product=order.product).order_by('-id').first()
        if bom is None:
            continue
        inventory_lookup = {}
        for inventory in Inventory.objects.filter(item__code__in=bom.items.values_list('material_code', flat=True)).select_related('item'):
            data = inventory_lookup.setdefault(inventory.item.code, {
                'available_quantity': Decimal('0'),
                'specification': inventory.item.specification,
            })
            data['available_quantity'] += inventory.available_quantity
        payloads = []
        for bom_item in bom.items.all():
            matched_inventory = InventoryItem.objects.filter(code=bom_item.material_code).order_by('id').first()
            payload = build_issue_item_payload(
                bom_item={
                    'material_name': bom_item.material_name,
                    'material_code': bom_item.material_code,
                    'specification': bom_item.specification,
                    'quantity': bom_item.quantity,
                },
                plan_quantity=order.quantity,
                inventory_lookup=inventory_lookup,
            )
            payloads.append(payload)
            OutsourceIssueItem.objects.create(
                issue_order=order,
                bom_item=bom_item,
                inventory_item=matched_inventory,
                material_name=payload['material_name'],
                material_code=payload['material_code'],
                specification=payload['specification'],
                required_quantity=payload['required_quantity'],
                available_quantity=payload['available_quantity'],
                status=payload['status'],
                remark='基于系统库存自动初始化齐套结果',
            )
        order.status = summarize_issue_order_status(payloads)
        order.save(update_fields=['status', 'update_time'])

    # Enrich price review orders with one-pass material-cost conclusions.
    for order in PriceReviewOrder.objects.filter(conclusion__isnull=True).select_related('inventory_item'):
        cost_value = order.quoted_price or Decimal('0')
        if order.supplier_id is None:
            order.supplier = _pick_supplier(suppliers, order.id or 0)
        raw_components = _build_bootstrap_price_components(
            quote=cost_value,
            standard_cost=(order.inventory_item.standard_cost if order.inventory_item_id else Decimal('0')),
            average_cost=(order.inventory_item.average_cost if order.inventory_item_id else Decimal('0')),
        )
        component_rows = compare_component_amounts(
            components=[
                {
                    'component_type': row['component_type'],
                    'component_name': row['component_name'],
                    'amount': row['amount'],
                }
                for row in raw_components
            ],
            reference_map={row['component_name']: row['reference_amount'] for row in raw_components},
        )
        conclusion_payload = build_price_review_conclusion(
            quoted_price=order.quoted_price,
            component_rows=component_rows,
            historical_prices=[],
            market_price=(order.inventory_item.average_cost if order.inventory_item_id else Decimal('0')),
            target_price=(order.inventory_item.standard_cost if order.inventory_item_id else Decimal('0')),
        )
        order.status = (
            PriceReviewOrder.STATUS_EXCEPTION
            if conclusion_payload['result'] == 'exception'
            else PriceReviewOrder.STATUS_APPROVED
        )
        order.ai_summary = conclusion_payload['summary']
        order.save(update_fields=['supplier', 'status', 'ai_summary', 'update_time'])
        for row in component_rows:
            PriceReviewComponent.objects.create(
                review_order=order,
                component_type=row['component_type'],
                component_name=row['component_name'],
                amount=row['amount'],
                reference_amount=row['reference_amount'],
                is_abnormal=row['is_abnormal'],
                remark='基于成本主数据自动初始化',
            )
        PriceReviewConclusion.objects.create(
            review_order=order,
            result=conclusion_payload['result'],
            risk_level=conclusion_payload['risk_level'],
            summary=conclusion_payload['summary'],
            abnormal_items=conclusion_payload['abnormal_items'],
            negotiation_points=conclusion_payload['negotiation_points'],
            reviewer=user,
        )

    return result
