import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.contract.models import Product, Supplier
from apps.inventory.models import Inventory, InventoryItem
from apps.production.models import BOM, ProductionPlan

from .forms import (
    DemandForecastPlanForm,
    ForecastReviewForm,
    ForecastRunForm,
    OutsourceIssueOrderForm,
    OutsourceStatusForm,
    PRBatchApproveForm,
    PRQuickApproveForm,
    PRReviewEvaluateForm,
    PRReviewTaskForm,
    PriceReviewDocumentForm,
    PriceReviewAnalyzeForm,
    PriceReviewOrderForm,
    SamplePickupForm,
    SampleReceiptForm,
    SampleRequestForm,
)
from .models import (
    DemandForecastPlan,
    DemandForecastResult,
    DemandForecastSnapshot,
    MaterialPreparationReview,
    OutsourceIssueItem,
    OutsourceIssueOrder,
    OutsourceIssueStatusLog,
    PRReviewEvidence,
    PRReviewRule,
    PRReviewTask,
    PriceReviewDocument,
    PriceReviewConclusion,
    PriceReviewComponent,
    PriceReviewOrder,
    SamplePickupRecord,
    SampleReceipt,
    SampleRequest,
)
from .services.event_service import log_supply_chain_event, send_supply_chain_notification
from .services.ai_services import supply_chain_ai
from .services.forecast_service import (
    build_forecast_trend_data,
    build_snapshot_payload,
    calculate_forecast_accuracy,
    calculate_recommended_preparation_quantity,
    calculate_safety_stock,
)
from .services.inventory_analysis_service import build_inventory_analysis_summary, build_inventory_deep_analysis
from .services.outsource_service import build_issue_item_payload, summarize_issue_order_status
from .services.price_review_service import (
    build_price_review_conclusion,
    build_price_review_report,
    compare_component_amounts,
    normalize_price_components,
    parse_price_review_document_text,
)
from .services.pr_review_service import evaluate_pr_payload
from .services.sample_service import (
    build_receipt_payload,
    get_sample_statistics,
    generate_sample_request_code,
    is_pickup_overdue,
)
from .services.sequence_service import generate_business_code
from .services.source_service import sync_supply_chain_sources


PRICE_COMPONENT_FIELDS = [
    'material_cost',
    'process_cost',
    'labor_cost',
    'loss_cost',
    'package_cost',
    'logistics_cost',
    'profit_cost',
]

OUTSOURCE_STATUS_ACTIONS = {
    'start_picking': {
        'from_statuses': {OutsourceIssueOrder.STATUS_READY},
        'to_status': OutsourceIssueOrder.STATUS_PICKING,
        'message': '仓库开始备料',
    },
    'mark_issued': {
        'from_statuses': {OutsourceIssueOrder.STATUS_PICKING},
        'to_status': OutsourceIssueOrder.STATUS_ISSUED,
        'message': '仓库完成发料',
    },
    'notify_pickup': {
        'from_statuses': {OutsourceIssueOrder.STATUS_ISSUED},
        'to_status': OutsourceIssueOrder.STATUS_NOTIFIED,
        'message': '已完成内部领料通知',
    },
    'close_order': {
        'from_statuses': {OutsourceIssueOrder.STATUS_NOTIFIED},
        'to_status': OutsourceIssueOrder.STATUS_CLOSED,
        'message': '委外发料流程关闭',
    },
}


def _generate_serial(prefix, model, date_part=True):
    return generate_business_code(prefix)


def _risk_level_by_gap(predicted_quantity, recommended_quantity):
    predicted_quantity = Decimal(str(predicted_quantity or 0))
    recommended_quantity = Decimal(str(recommended_quantity or 0))
    if predicted_quantity <= 0:
        return 'low'
    ratio = recommended_quantity / predicted_quantity
    if ratio >= Decimal('0.50'):
        return 'high'
    if ratio >= Decimal('0.20'):
        return 'medium'
    return 'low'


def _price_history_from_text(raw_text):
    values = []
    for part in (raw_text or '').split(','):
        part = part.strip()
        if not part:
            continue
        values.append(Decimal(part))
    return values


def _decimal_from_ai(value, default):
    if value in (None, ''):
        return Decimal(str(default or 0))
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(str(default or 0))


def _coerce_price_payload_from_document(document):
    payload = {}
    parsed_payload = getattr(document, 'parsed_payload', {}) or {}
    for field_name in PRICE_COMPONENT_FIELDS:
        value = parsed_payload.get(field_name)
        if value in (None, ''):
            continue
        payload[field_name] = Decimal(str(value))
    return payload


def _build_outsource_inventory_lookup(material_codes):
    inventory_lookup = {}
    for inventory in Inventory.objects.filter(item__code__in=material_codes).select_related('item'):
        data = inventory_lookup.setdefault(inventory.item.code, {
            'available_quantity': Decimal('0'),
            'specification': inventory.item.specification,
        })
        data['available_quantity'] += inventory.available_quantity
    return inventory_lookup


def _get_batch_approvable_pr_tasks():
    return PRReviewTask.objects.filter(
        status__in=[PRReviewTask.STATUS_AUTO_APPROVED, PRReviewTask.STATUS_RULE_MATCHED],
        recommended_action__in=[PRReviewRule.ACTION_APPROVE, PRReviewRule.ACTION_URGENT],
    ).select_related('created_by', 'reviewer')


def _paginate_queryset(request, queryset, per_page=10):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get('page') or 1)


def _build_supply_chain_source_summary():
    risk_rows = build_inventory_analysis_summary().get('risk_rows', [])
    return {
        'source_product_count': Product.objects.count(),
        'source_supplier_count': Supplier.objects.filter(is_active=True).count(),
        'source_inventory_item_count': InventoryItem.objects.count(),
        'source_production_plan_count': ProductionPlan.objects.count(),
        'source_bom_count': BOM.objects.count(),
        'source_inventory_risk_count': sum(1 for row in risk_rows if row['risk_level'] in {'high', 'medium'}),
    }


@login_required
def dashboard(request):
    inventory_summary = build_inventory_analysis_summary()
    ai_dashboard_summary = supply_chain_ai.analyze_inventory_risk(
        total_items=inventory_summary.get('total_items', 0),
        high_risk_count=inventory_summary.get('high_risk_count', 0),
        medium_risk_count=inventory_summary.get('medium_risk_count', 0),
        dead_stock_count=0,
        safety_breach_count=inventory_summary.get('high_risk_count', 0),
        top_risk_items=[
            f"{row['item'].name}:{row['status']}"
            for row in inventory_summary.get('risk_rows', [])
            if row.get('risk_level') in {'high', 'medium'}
        ][:5],
    )
    context = {
        'page_title': '供应链智能驾驶舱',
        'forecast_count': DemandForecastPlan.objects.count(),
        'forecast_pending_reviews': MaterialPreparationReview.objects.filter(status='pending').count(),
        'outsource_shortage_count': OutsourceIssueOrder.objects.filter(status='shortage').count(),
        'pr_manual_review_count': PRReviewTask.objects.filter(status='manual_review').count(),
        'price_exception_count': PriceReviewConclusion.objects.filter(result='exception').count(),
        'sample_pending_pickup_count': SampleRequest.objects.filter(status='pickup_pending').count(),
        'inventory_summary': inventory_summary,
        'recent_forecasts': DemandForecastPlan.objects.order_by('-create_time')[:5],
        'recent_samples': SampleRequest.objects.order_by('-create_time')[:5],
        'recent_pr_tasks': PRReviewTask.objects.order_by('-create_time')[:5],
        'has_forecast_history': DemandForecastResult.objects.exists(),
        'ai_dashboard_summary': ai_dashboard_summary,
    }
    context.update(_build_supply_chain_source_summary())
    return render(request, 'supply_chain/dashboard.html', context)


@login_required
def inventory_analysis(request):
    inventory_summary = build_inventory_analysis_summary()
    deep_analysis = build_inventory_deep_analysis()
    top_risk_items = [
        f"{row['item'].name}:{row['status']}"
        for row in inventory_summary.get('risk_rows', [])
        if row.get('risk_level') in {'high', 'medium'}
    ][:5]
    ai_inventory_summary = supply_chain_ai.analyze_inventory_risk(
        total_items=inventory_summary.get('total_items', 0),
        high_risk_count=inventory_summary.get('high_risk_count', 0),
        medium_risk_count=inventory_summary.get('medium_risk_count', 0),
        dead_stock_count=deep_analysis.get('dead_stock_count', 0),
        safety_breach_count=deep_analysis.get('safety_breach_count', 0),
        top_risk_items=top_risk_items,
    )
    context = {
        'page_title': '库存智能分析',
        'ai_inventory_summary': ai_inventory_summary,
        **inventory_summary,
    }
    context.update(deep_analysis)
    return render(request, 'supply_chain/inventory_analysis.html', context)


@login_required
def forecast_list(request):
    search = (request.GET.get('search') or '').strip()
    status = (request.GET.get('status') or '').strip()
    plans = DemandForecastPlan.objects.select_related('product').prefetch_related('results__reviews')
    if search:
        plans = plans.filter(
            Q(code__icontains=search) |
            Q(name__icontains=search) |
            Q(product__name__icontains=search)
        )
    if status:
        plans = plans.filter(status=status)
    page_obj = _paginate_queryset(request, plans, per_page=8)
    context = {
        'page_title': '需求预测与备料评审',
        'plans': page_obj,
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'status_choices': DemandForecastPlan.STATUS_CHOICES,
        'total_count': plans.count(),
        'reviewing_count': DemandForecastPlan.objects.filter(status=DemandForecastPlan.STATUS_REVIEWING).count(),
        'approved_count': DemandForecastPlan.objects.filter(status=DemandForecastPlan.STATUS_APPROVED).count(),
    }
    context.update(_build_supply_chain_source_summary())
    return render(request, 'supply_chain/forecast_list.html', context)


@login_required
def forecast_create(request):
    if request.method == 'POST':
        form = DemandForecastPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.code = _generate_serial('DFP', DemandForecastPlan)
            plan.created_by = request.user
            plan.save()
            messages.success(request, '预测计划已创建')
            return redirect('supply_chain:forecast_list')
    else:
        form = DemandForecastPlanForm()

    return render(request, 'supply_chain/forecast_form.html', {
        'page_title': '新建预测计划',
        'form': form,
    })


@login_required
def forecast_run(request, pk):
    plan = get_object_or_404(DemandForecastPlan, pk=pk)
    if request.method != 'POST':
        return redirect('supply_chain:forecast_list')
    if plan.status in {DemandForecastPlan.STATUS_APPROVED, DemandForecastPlan.STATUS_ARCHIVED}:
        messages.error(request, '当前预测计划已结束，不能重复生成预测结果')
        return redirect('supply_chain:forecast_list')

    form = ForecastRunForm(request.POST)
    if not form.is_valid():
        messages.error(request, '预测参数不完整')
        return redirect('supply_chain:forecast_list')

    with transaction.atomic():
        payload = build_snapshot_payload(
            shipped_quantity=form.cleaned_data['shipped_quantity'],
            inventory_quantity=form.cleaned_data['inventory_quantity'],
            wip_quantity=form.cleaned_data['wip_quantity'],
            inbound_quantity=form.cleaned_data['inbound_quantity'],
            prepared_quantity=form.cleaned_data['prepared_quantity'],
            manual_adjustment=form.cleaned_data['manual_adjustment'],
        )
        snapshot = DemandForecastSnapshot.objects.create(
            forecast_plan=plan,
            product=plan.product,
            shipped_quantity=payload['shipped_quantity'],
            inventory_quantity=payload['inventory_quantity'],
            wip_quantity=payload['wip_quantity'],
            inbound_quantity=payload['inbound_quantity'],
            prepared_quantity=payload['prepared_quantity'],
            manual_adjustment=payload['manual_adjustment'],
            notes='系统自动生成预测快照',
        )
        safety_stock = calculate_safety_stock(form.cleaned_data['avg_daily_demand'])
        rule_recommended_quantity = calculate_recommended_preparation_quantity(
            predicted_quantity=form.cleaned_data['predicted_quantity'],
            safety_stock=safety_stock,
            inventory_quantity=payload['inventory_quantity'],
            wip_quantity=payload['wip_quantity'],
            inbound_quantity=payload['inbound_quantity'],
            prepared_quantity=payload['prepared_quantity'],
            manual_adjustment=payload['manual_adjustment'],
        )
        history_results = list(
            DemandForecastResult.objects.filter(
                forecast_plan__product_id=plan.product_id,
            ).order_by('-create_time')[:6]
        )
        ai_forecast = supply_chain_ai.generate_forecast(
            product_name=str(plan.product or plan.name),
            historical_demand=[item.predicted_quantity for item in history_results],
            inventory_quantity=payload['inventory_quantity'],
            wip_quantity=payload['wip_quantity'],
            safety_stock=safety_stock,
        )
        predicted_quantity = _decimal_from_ai(
            ai_forecast.get('predicted_quantity'),
            form.cleaned_data['predicted_quantity'],
        )
        recommended_quantity = _decimal_from_ai(
            ai_forecast.get('recommended_quantity'),
            rule_recommended_quantity,
        )
        actual_quantity = form.cleaned_data.get('actual_quantity')
        confidence = (
            calculate_forecast_accuracy(predicted_quantity, actual_quantity)
            if actual_quantity else _decimal_from_ai(ai_forecast.get('confidence'), '80.00')
        )
        result = DemandForecastResult.objects.create(
            forecast_plan=plan,
            predicted_quantity=predicted_quantity,
            safety_stock=safety_stock,
            recommended_quantity=recommended_quantity,
            confidence=confidence,
            risk_level=ai_forecast.get('risk_level') or _risk_level_by_gap(
                predicted_quantity,
                recommended_quantity,
            ),
            summary=ai_forecast.get('summary') or f'基于出货、库存、在制、在途与备料生成建议备料量 {recommended_quantity}',
        )
        MaterialPreparationReview.objects.create(
            forecast_result=result,
            code=_generate_serial('MPR', MaterialPreparationReview),
        )
        plan.status = DemandForecastPlan.STATUS_REVIEWING
        plan.save(update_fields=['status', 'update_time'])

    log_supply_chain_event(
        event_type='forecast_generated',
        title=f'预测计划 {plan.code} 已生成结果',
        object_type='demand_forecast_plan',
        object_id=plan.id,
        payload={
            'snapshot_id': snapshot.id,
            'result_id': result.id,
            'recommended_quantity': str(result.recommended_quantity),
        },
        operator=request.user,
    )
    send_supply_chain_notification(
        title=f'预测已生成: {plan.name}',
        content=f'建议备料量 {result.recommended_quantity}，请进入备料评审。',
        user_ids=[plan.created_by_id] if plan.created_by_id else [],
        related_object_type='demand_forecast_plan',
        related_object_id=plan.id,
        action_url=reverse('supply_chain:forecast_list'),
        sender=request.user,
    )
    messages.success(request, '预测结果已生成')
    return redirect('supply_chain:forecast_list')


@login_required
def forecast_review(request, pk):
    review = get_object_or_404(
        MaterialPreparationReview.objects.select_related('forecast_result__forecast_plan'),
        pk=pk,
    )
    if request.method != 'POST':
        return redirect('supply_chain:forecast_list')

    form = ForecastReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, '评审参数无效')
        return redirect('supply_chain:forecast_list')
    if review.status != MaterialPreparationReview.STATUS_PENDING:
        messages.error(request, '当前评审单已处理，请勿重复提交')
        return redirect('supply_chain:forecast_list')

    plan = review.forecast_result.forecast_plan
    decision = form.cleaned_data['decision']
    with transaction.atomic():
        review.status = (
            MaterialPreparationReview.STATUS_APPROVED
            if decision == 'approve'
            else MaterialPreparationReview.STATUS_REJECTED
        )
        review.comment = form.cleaned_data['comment']
        review.reviewer = request.user
        review.save(update_fields=['status', 'comment', 'reviewer', 'update_time'])
        plan.status = (
            DemandForecastPlan.STATUS_APPROVED
            if decision == 'approve'
            else DemandForecastPlan.STATUS_REJECTED
        )
        plan.save(update_fields=['status', 'update_time'])

    log_supply_chain_event(
        event_type='forecast_reviewed',
        title=f'备料评审 {review.code} 已{review.get_status_display()}',
        object_type='material_preparation_review',
        object_id=review.id,
        payload={'decision': decision, 'comment': review.comment},
        operator=request.user,
    )
    notify_ids = [user_id for user_id in {plan.created_by_id, review.reviewer_id} if user_id]
    if notify_ids:
        send_supply_chain_notification(
            title=f'备料评审完成: {review.code}',
            content=f'评审结果：{review.get_status_display()}',
            user_ids=notify_ids,
            related_object_type='material_preparation_review',
            related_object_id=review.id,
            action_url=reverse('supply_chain:forecast_list'),
            sender=request.user,
            priority=2 if decision == 'approve' else 3,
        )
    messages.success(request, '备料评审已完成')
    return redirect('supply_chain:forecast_list')


@login_required
def outsource_list(request):
    search = (request.GET.get('search') or '').strip()
    status = (request.GET.get('status') or '').strip()
    orders = OutsourceIssueOrder.objects.select_related('product', 'supplier', 'production_plan').prefetch_related('items')
    if search:
        orders = orders.filter(
            Q(code__icontains=search) |
            Q(product__name__icontains=search) |
            Q(supplier__name__icontains=search) |
            Q(production_plan__code__icontains=search)
        )
    if status:
        orders = orders.filter(status=status)
    page_obj = _paginate_queryset(request, orders, per_page=8)
    context = {
        'page_title': '委外发料齐套',
        'orders': page_obj,
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'status_choices': OutsourceIssueOrder.STATUS_CHOICES,
        'total_count': orders.count(),
        'shortage_count': OutsourceIssueOrder.objects.filter(status=OutsourceIssueOrder.STATUS_SHORTAGE).count(),
        'ready_count': OutsourceIssueOrder.objects.filter(status=OutsourceIssueOrder.STATUS_READY).count(),
    }
    context.update(_build_supply_chain_source_summary())
    return render(request, 'supply_chain/outsource_list.html', context)


@login_required
def outsource_create(request):
    if request.method == 'POST':
        form = OutsourceIssueOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.code = _generate_serial('OIO', OutsourceIssueOrder)
            order.created_by = request.user
            order.save()
            OutsourceIssueStatusLog.objects.create(
                issue_order=order,
                from_status='',
                to_status=order.status,
                message='委外发料单已创建',
                operator=request.user,
            )
            messages.success(request, '委外发料单已创建')
            return redirect('supply_chain:outsource_list')
    else:
        form = OutsourceIssueOrderForm()
    return render(request, 'supply_chain/outsource_form.html', {
        'page_title': '新建委外发料单',
        'form': form,
    })


@login_required
def outsource_check(request, pk):
    order = get_object_or_404(OutsourceIssueOrder.objects.select_related('production_plan__bom', 'product'), pk=pk)
    if request.method != 'POST':
        return redirect('supply_chain:outsource_list')
    if order.status not in {
        OutsourceIssueOrder.STATUS_DRAFT,
        OutsourceIssueOrder.STATUS_SHORTAGE,
        OutsourceIssueOrder.STATUS_READY,
    }:
        messages.error(request, '当前状态不允许重新执行齐套校验')
        return redirect('supply_chain:outsource_list')

    bom = getattr(order.production_plan, 'bom', None)
    if bom is None and order.product_id:
        bom = BOM.objects.filter(product=order.product).order_by('-id').first()
    if bom is None:
        messages.error(request, '未找到可用BOM，无法执行齐套校验')
        return redirect('supply_chain:outsource_list')

    inventory_lookup = _build_outsource_inventory_lookup(
        bom.items.values_list('material_code', flat=True),
    )

    with transaction.atomic():
        order.status = OutsourceIssueOrder.STATUS_CHECKING
        order.save(update_fields=['status', 'update_time'])
        order.items.all().delete()

        item_payloads = []
        for bom_item in bom.items.all():
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
            item_payloads.append(payload)
            OutsourceIssueItem.objects.create(
                issue_order=order,
                bom_item=bom_item,
                material_name=payload['material_name'],
                material_code=payload['material_code'],
                specification=payload['specification'],
                required_quantity=payload['required_quantity'],
                available_quantity=payload['available_quantity'],
                status=payload['status'],
                remark='系统自动齐套校验',
            )

        new_status = summarize_issue_order_status(item_payloads)
        shortage_details = [
            f"{item['material_name']}缺口{item['shortage_quantity']}"
            for item in item_payloads
            if item.get('status') == 'shortage'
        ]
        ai_advice = supply_chain_ai.outsource_completeness_advice(
            order_code=order.code,
            total_items=len(item_payloads),
            shortage_count=len(shortage_details),
            shortage_details=shortage_details,
        )
        order.status = new_status
        order.save(update_fields=['status', 'update_time'])
        OutsourceIssueStatusLog.objects.create(
            issue_order=order,
            from_status=OutsourceIssueOrder.STATUS_CHECKING,
            to_status=new_status,
            message=ai_advice or '系统完成齐套校验',
            operator=request.user,
        )

    log_supply_chain_event(
        event_type='outsource_checked',
        title=f'委外发料单 {order.code} 完成齐套校验',
        object_type='outsource_issue_order',
        object_id=order.id,
        payload={'status': new_status, 'item_count': len(item_payloads)},
        operator=request.user,
    )
    if order.created_by_id:
        message_text = '存在缺料，请采购提前跟进' if new_status == 'shortage' else '物料齐套，可推进仓库备料'
        send_supply_chain_notification(
            title=f'委外发料校验完成: {order.code}',
            content=message_text,
            user_ids=[order.created_by_id],
            related_object_type='outsource_issue_order',
            related_object_id=order.id,
            action_url=reverse('supply_chain:outsource_list'),
            sender=request.user,
        )
    messages.success(request, '委外发料齐套校验完成')
    return redirect('supply_chain:outsource_list')


@login_required
def outsource_status_update(request, pk):
    order = get_object_or_404(OutsourceIssueOrder, pk=pk)
    if request.method != 'POST':
        return redirect('supply_chain:outsource_list')

    form = OutsourceStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, '状态流转参数无效')
        return redirect('supply_chain:outsource_list')

    action = form.cleaned_data['action']
    transition = OUTSOURCE_STATUS_ACTIONS[action]
    if order.status not in transition['from_statuses']:
        messages.error(request, f'当前状态 {order.get_status_display()} 不允许执行该动作')
        return redirect('supply_chain:outsource_list')
    new_status = transition['to_status']
    message_text = transition['message']
    previous_status = order.status
    with transaction.atomic():
        order.status = new_status
        order.save(update_fields=['status', 'update_time'])
        OutsourceIssueStatusLog.objects.create(
            issue_order=order,
            from_status=previous_status,
            to_status=new_status,
            message=message_text,
            operator=request.user,
        )

    log_supply_chain_event(
        event_type='outsource_status_updated',
        title=f'委外发料单 {order.code} 状态更新为 {order.get_status_display()}',
        object_type='outsource_issue_order',
        object_id=order.id,
        payload={'action': action, 'from_status': previous_status, 'to_status': new_status},
        operator=request.user,
    )
    if order.created_by_id:
        send_supply_chain_notification(
            title=f'委外发料状态更新: {order.code}',
            content=message_text,
            user_ids=[order.created_by_id],
            related_object_type='outsource_issue_order',
            related_object_id=order.id,
            action_url=reverse('supply_chain:outsource_list'),
            sender=request.user,
            priority=2,
        )
    messages.success(request, '委外发料状态已更新')
    return redirect('supply_chain:outsource_list')


@login_required
def pr_review_list(request):
    search = (request.GET.get('search') or '').strip()
    status = (request.GET.get('status') or '').strip()
    abnormal = (request.GET.get('abnormal') or '').strip()
    tasks = PRReviewTask.objects.prefetch_related('matched_rules')
    if search:
        tasks = tasks.filter(
            Q(code__icontains=search) |
            Q(title__icontains=search) |
            Q(source_code__icontains=search)
        )
    if status:
        tasks = tasks.filter(status=status)
    if abnormal == '1':
        tasks = tasks.filter(is_abnormal=True)
    elif abnormal == '0':
        tasks = tasks.filter(is_abnormal=False)
    page_obj = _paginate_queryset(request, tasks, per_page=10)
    context = {
        'page_title': 'PR 智能审核',
        'tasks': page_obj,
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'abnormal': abnormal,
        'status_choices': PRReviewTask.STATUS_CHOICES,
        'rules': PRReviewRule.objects.filter(is_active=True).order_by('priority'),
        'total_count': tasks.count(),
        'manual_review_count': PRReviewTask.objects.filter(status=PRReviewTask.STATUS_MANUAL_REVIEW).count(),
        'batch_ready_count': _get_batch_approvable_pr_tasks().count(),
    }
    context.update(_build_supply_chain_source_summary())
    return render(request, 'supply_chain/pr_review_list.html', context)


@login_required
def pr_review_create(request):
    if request.method == 'POST':
        form = PRReviewTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.code = _generate_serial('PRR', PRReviewTask)
            task.created_by = request.user
            task.save()
            messages.success(request, 'PR 审核任务已创建')
            return redirect('supply_chain:pr_review_list')
    else:
        form = PRReviewTaskForm()
    return render(request, 'supply_chain/pr_review_form.html', {
        'page_title': '新建 PR 审核任务',
        'form': form,
    })


@login_required
def pr_review_evaluate(request, pk):
    task = get_object_or_404(PRReviewTask, pk=pk)
    if request.method != 'POST':
        return redirect('supply_chain:pr_review_list')

    form = PRReviewEvaluateForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'PR 审核载荷无效')
        return redirect('supply_chain:pr_review_list')

    payload = form.build_payload()
    rules = list(PRReviewRule.objects.filter(is_active=True).order_by('priority').values(
        'id',
        'code',
        'name',
        'condition_json',
        'recommended_action',
        'priority',
    ))
    result = evaluate_pr_payload(payload=payload, rules=rules)
    ai_result = supply_chain_ai.evaluate_pr(
        scenario=form.cleaned_data.get('scenario') or payload.get('scenario') or task.source_type or task.title,
        order_type=payload.get('order_type') or task.source_type,
        is_urgent=bool(payload.get('is_urgent')),
        lt_shortage=bool(payload.get('lt_shortage')),
        tail_order=bool(payload.get('tail_order')),
        npi_trial=bool(payload.get('npi_trial')),
        rework_order=bool(payload.get('rework_order')),
    )
    ai_action = ai_result.get('recommended_action')
    if ai_action in {'approve', 'urgent_approve', 'manual_review', 'filter'}:
        result['recommended_action'] = ai_action
        result['is_abnormal'] = bool(ai_result.get('is_abnormal', result['is_abnormal']))
    result['evidence']['ai_result'] = ai_result

    with transaction.atomic():
        task.is_abnormal = result['is_abnormal']
        task.recommended_action = result['recommended_action']
        task.evidence = result['evidence']
        if result['recommended_action'] == 'manual_review':
            task.status = PRReviewTask.STATUS_MANUAL_REVIEW
        elif result['recommended_action'] in {'approve', 'urgent_approve'}:
            task.status = PRReviewTask.STATUS_AUTO_APPROVED
        elif result['recommended_action'] == 'filter':
            task.status = PRReviewTask.STATUS_REJECTED
        else:
            task.status = PRReviewTask.STATUS_PENDING
        task.save()
        task.matched_rules.set([rule['id'] for rule in result['matched_rules']])
        task.evidence_items.all().delete()
        if result['matched_rules']:
            for rule in result['matched_rules']:
                PRReviewEvidence.objects.create(
                    review_task=task,
                    rule_id=rule.get('id'),
                    label=f'命中规则 {rule.get("code")}',
                    value=rule.get('name', ''),
                )
        else:
            PRReviewEvidence.objects.create(
                review_task=task,
                label='规则识别',
                value='未命中规则',
            )
        PRReviewEvidence.objects.create(
            review_task=task,
            label='建议动作',
            value=result['recommended_action'] or 'pending',
        )

    log_supply_chain_event(
        event_type='pr_review_evaluated',
        title=f'PR 审核任务 {task.code} 已完成识别',
        object_type='pr_review_task',
        object_id=task.id,
        payload=result,
        operator=request.user,
    )
    notify_ids = [user_id for user_id in [task.created_by_id, task.reviewer_id] if user_id]
    if result['is_abnormal']:
        send_supply_chain_notification(
            title=f'PR 异常待复核: {task.title}',
            content='系统识别为异常 PR，请尽快人工复核。',
            user_ids=notify_ids,
            related_object_type='pr_review_task',
            related_object_id=task.id,
            action_url=reverse('supply_chain:pr_review_list'),
            sender=request.user,
            priority=3,
        )
    messages.success(request, 'PR 智能审核已完成')
    return redirect('supply_chain:pr_review_list')


@login_required
def pr_review_approve(request, pk):
    task = get_object_or_404(PRReviewTask, pk=pk)
    if request.method != 'POST':
        return redirect('supply_chain:pr_review_list')

    form = PRQuickApproveForm(request.POST)
    if not form.is_valid():
        messages.error(request, '审批备注无效')
        return redirect('supply_chain:pr_review_list')
    if task.status in {PRReviewTask.STATUS_DONE, PRReviewTask.STATUS_REJECTED}:
        messages.error(request, '当前任务已处理，不能重复审批')
        return redirect('supply_chain:pr_review_list')

    with transaction.atomic():
        task.status = PRReviewTask.STATUS_DONE
        task.reviewer = request.user
        if not task.recommended_action:
            task.recommended_action = 'approve'
        task.save(update_fields=['status', 'reviewer', 'recommended_action', 'update_time'])
        note = form.cleaned_data['note']
        if note:
            PRReviewEvidence.objects.create(
                review_task=task,
                label='审批备注',
                value=note,
            )

    log_supply_chain_event(
        event_type='pr_review_approved',
        title=f'PR 审核任务 {task.code} 已一键审批',
        object_type='pr_review_task',
        object_id=task.id,
        payload={'recommended_action': task.recommended_action, 'note': form.cleaned_data['note']},
        operator=request.user,
    )
    notify_ids = [user_id for user_id in {task.created_by_id, task.reviewer_id} if user_id]
    if notify_ids:
        send_supply_chain_notification(
            title=f'PR 已审批: {task.title}',
            content='系统已完成一键审批放行。',
            user_ids=notify_ids,
            related_object_type='pr_review_task',
            related_object_id=task.id,
            action_url=reverse('supply_chain:pr_review_list'),
            sender=request.user,
            priority=2,
        )
    messages.success(request, 'PR 已一键审批')
    return redirect('supply_chain:pr_review_list')


@login_required
def pr_review_batch_approve(request):
    if request.method != 'POST':
        return redirect('supply_chain:pr_review_list')

    form = PRBatchApproveForm(request.POST)
    if not form.is_valid():
        messages.error(request, '批量审批备注无效')
        return redirect('supply_chain:pr_review_list')

    tasks = list(_get_batch_approvable_pr_tasks())
    if not tasks:
        messages.warning(request, '当前没有可批量审批的 PR 任务')
        return redirect('supply_chain:pr_review_list')

    note = form.cleaned_data['note']
    notify_ids = set()
    with transaction.atomic():
        for task in tasks:
            task.status = PRReviewTask.STATUS_DONE
            task.reviewer = request.user
            task.save(update_fields=['status', 'reviewer', 'update_time'])
            if note:
                PRReviewEvidence.objects.create(
                    review_task=task,
                    label='批量审批备注',
                    value=note,
                )
            for user_id in {task.created_by_id, task.reviewer_id}:
                if user_id:
                    notify_ids.add(user_id)

    log_supply_chain_event(
        event_type='pr_review_batch_approved',
        title='PR 周期批量审批已完成',
        object_type='pr_review_task',
        payload={'task_codes': [task.code for task in tasks], 'note': note},
        operator=request.user,
    )
    if notify_ids:
        send_supply_chain_notification(
            title='PR 周期批量审批完成',
            content=f'本次已完成 {len(tasks)} 条 PR 审批放行。',
            user_ids=list(notify_ids),
            related_object_type='pr_review_task',
            related_object_id=tasks[0].id,
            action_url=reverse('supply_chain:pr_review_list'),
            sender=request.user,
            priority=2,
        )
    messages.success(request, f'已批量审批 {len(tasks)} 条 PR 任务')
    return redirect('supply_chain:pr_review_list')


@login_required
def price_review_list(request):
    search = (request.GET.get('search') or '').strip()
    status = (request.GET.get('status') or '').strip()
    orders = PriceReviewOrder.objects.select_related('inventory_item', 'supplier', 'conclusion').prefetch_related('components', 'documents')
    if search:
        orders = orders.filter(
            Q(code__icontains=search) |
            Q(inventory_item__name__icontains=search) |
            Q(inventory_item__code__icontains=search) |
            Q(supplier__name__icontains=search)
        )
    if status:
        orders = orders.filter(status=status)
    page_obj = _paginate_queryset(request, orders, per_page=8)
    context = {
        'page_title': '单价智能复核',
        'orders': page_obj,
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'status_choices': PriceReviewOrder.STATUS_CHOICES,
        'total_count': orders.count(),
        'exception_count': PriceReviewOrder.objects.filter(status=PriceReviewOrder.STATUS_EXCEPTION).count(),
        'approved_count': PriceReviewOrder.objects.filter(status=PriceReviewOrder.STATUS_APPROVED).count(),
    }
    context.update(_build_supply_chain_source_summary())
    return render(request, 'supply_chain/price_review_list.html', context)


@login_required
def price_review_create(request):
    if request.method == 'POST':
        form = PriceReviewOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.code = _generate_serial('PRC', PriceReviewOrder)
            order.created_by = request.user
            order.save()
            messages.success(request, '单价复核单已创建')
            return redirect('supply_chain:price_review_list')
    else:
        form = PriceReviewOrderForm()
    return render(request, 'supply_chain/price_review_form.html', {
        'page_title': '新建单价复核单',
        'form': form,
    })


@login_required
def price_review_analyze(request, pk):
    order = get_object_or_404(PriceReviewOrder.objects.select_related('inventory_item', 'supplier'), pk=pk)
    if request.method != 'POST':
        return redirect('supply_chain:price_review_list')

    form = PriceReviewAnalyzeForm(request.POST)
    if not form.is_valid():
        messages.error(request, '单价复核参数无效')
        return redirect('supply_chain:price_review_list')

    parsed_payload = {
        key: form.cleaned_data.get(key)
        for key in PRICE_COMPONENT_FIELDS
    }
    if not any(value not in (None, '') for value in parsed_payload.values()):
        latest_document = order.documents.order_by('-create_time', '-id').first()
        if latest_document is not None:
            parsed_payload = _coerce_price_payload_from_document(latest_document)
    components = normalize_price_components(parsed_payload)
    if not components:
        messages.error(request, '缺少可用的成本拆解数据，请先解析规格书或填写成本项')
        return redirect('supply_chain:price_review_list')
    reference_map = {
        '原材料': order.inventory_item.latest_cost or order.inventory_item.average_cost or order.inventory_item.standard_cost,
    } if order.inventory_item_id else {}
    component_rows = compare_component_amounts(components, reference_map)
    history = _price_history_from_text(form.cleaned_data.get('historical_prices'))
    market_price = form.cleaned_data.get('market_price') or (history[-1] if history else Decimal('0'))
    target_price = form.cleaned_data.get('target_price') or (
        order.inventory_item.standard_cost if order.inventory_item_id else Decimal('0')
    )
    conclusion_payload = build_price_review_conclusion(
        quoted_price=order.quoted_price,
        component_rows=component_rows,
        historical_prices=history,
        market_price=market_price,
        target_price=target_price,
    )
    history_average = (
        sum(history, Decimal('0')) / Decimal(len(history))
        if history else Decimal('0')
    )
    component_summary = '; '.join(
        f"{row['component_name']}:{row['amount']}"
        for row in component_rows
    )
    ai_conclusion = supply_chain_ai.analyze_price_review(
        item_name=str(order.inventory_item or order.code),
        quoted_price=order.quoted_price,
        component_summary=component_summary,
        market_price=market_price,
        history_avg=history_average,
    )
    if ai_conclusion.get('result') in {'approved', 'exception'}:
        conclusion_payload['result'] = ai_conclusion['result']
    if ai_conclusion.get('risk_level') in {'high', 'medium', 'low'}:
        conclusion_payload['risk_level'] = ai_conclusion['risk_level']
    for key in ('summary', 'abnormal_items', 'negotiation_points'):
        if ai_conclusion.get(key):
            conclusion_payload[key] = ai_conclusion[key]

    with transaction.atomic():
        order.status = (
            PriceReviewOrder.STATUS_EXCEPTION
            if conclusion_payload['result'] == 'exception'
            else PriceReviewOrder.STATUS_APPROVED
        )
        order.ai_summary = conclusion_payload['summary']
        order.save(update_fields=['status', 'ai_summary', 'update_time'])
        order.components.all().delete()
        for row in component_rows:
            PriceReviewComponent.objects.create(
                review_order=order,
                component_type=row['component_type'],
                component_name=row['component_name'],
                amount=row['amount'],
                reference_amount=row['reference_amount'],
                is_abnormal=row['is_abnormal'],
                remark='系统自动拆解',
            )
        PriceReviewConclusion.objects.update_or_create(
            review_order=order,
            defaults={
                'result': conclusion_payload['result'],
                'risk_level': conclusion_payload['risk_level'],
                'summary': conclusion_payload['summary'],
                'abnormal_items': conclusion_payload['abnormal_items'],
                'negotiation_points': conclusion_payload['negotiation_points'],
                'reviewer': request.user,
            },
        )

    log_supply_chain_event(
        event_type='price_review_analyzed',
        title=f'单价复核单 {order.code} 已完成分析',
        object_type='price_review_order',
        object_id=order.id,
        payload=conclusion_payload,
        operator=request.user,
    )
    if order.created_by_id:
        send_supply_chain_notification(
            title=f'单价复核完成: {order.code}',
            content=conclusion_payload['summary'],
            user_ids=[order.created_by_id],
            related_object_type='price_review_order',
            related_object_id=order.id,
            action_url=reverse('supply_chain:price_review_list'),
            sender=request.user,
            priority=3 if conclusion_payload['result'] == 'exception' else 2,
        )
    messages.success(request, '单价复核分析完成')
    return redirect('supply_chain:price_review_list')


@login_required
def price_review_parse_document(request, pk):
    order = get_object_or_404(PriceReviewOrder, pk=pk)
    if request.method != 'POST':
        return redirect('supply_chain:price_review_list')

    form = PriceReviewDocumentForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, '规格书解析参数无效')
        return redirect('supply_chain:price_review_list')

    document_file = form.cleaned_data.get('document_file')
    raw_text = form.cleaned_data.get('raw_text', '')
    file_name = ''
    if document_file is not None:
        from apps.contract.contract_review_service import parse_contract_file

        file_name = document_file.name
        raw_text = parse_contract_file(document_file)

    parsed_payload = parse_price_review_document_text(raw_text)
    ai_payload = supply_chain_ai.parse_spec_document(raw_text)
    for field_name in PRICE_COMPONENT_FIELDS:
        ai_value = ai_payload.get(field_name)
        if ai_value not in (None, ''):
            parsed_payload[field_name] = f'{_decimal_from_ai(ai_value, parsed_payload.get(field_name, 0)):.4f}'
    with transaction.atomic():
        order.status = PriceReviewOrder.STATUS_PARSING
        order.save(update_fields=['status', 'update_time'])
        PriceReviewDocument.objects.update_or_create(
            review_order=order,
            file_name=file_name or 'manual-input.txt',
            defaults={
                'file_path': '',
                'raw_text': raw_text,
                'parsed_payload': parsed_payload,
            },
        )

    log_supply_chain_event(
        event_type='price_review_document_parsed',
        title=f'单价复核单 {order.code} 已完成规格书解析',
        object_type='price_review_order',
        object_id=order.id,
        payload={'file_name': file_name or 'manual-input.txt', 'parsed_fields': sorted(parsed_payload.keys())},
        operator=request.user,
    )
    messages.success(request, '规格书解析完成，可直接发起单价分析')
    return redirect('supply_chain:price_review_list')


@login_required
def sample_list(request):
    search = (request.GET.get('search') or '').strip()
    status = (request.GET.get('status') or '').strip()
    sample_requests = SampleRequest.objects.select_related('supplier', 'engineer', 'requested_by').prefetch_related('receipts', 'pickup_records')
    if search:
        sample_requests = sample_requests.filter(
            Q(code__icontains=search) |
            Q(material_name__icontains=search) |
            Q(specification__icontains=search) |
            Q(engineer__username__icontains=search)
        )
    if status:
        sample_requests = sample_requests.filter(status=status)
    page_obj = _paginate_queryset(request, sample_requests, per_page=8)
    stats = get_sample_statistics()
    pending_receipts = SampleReceipt.objects.filter(
        sample_request__status=SampleRequest.STATUS_PICKUP_PENDING,
    ).select_related('sample_request')[:5]
    overdue_details = [
        receipt.sample_request.material_name
        for receipt in pending_receipts
        if is_pickup_overdue(receipt.received_at, current_time=timezone.now())
    ]
    ai_sample_advice = supply_chain_ai.suggest_sample_priority(
        pending_count=SampleRequest.objects.filter(status=SampleRequest.STATUS_PICKUP_PENDING).count(),
        overdue_count=stats['overdue_count'],
        overdue_details=overdue_details,
    )
    context = {
        'page_title': '打样管理',
        'requests': page_obj,
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'status_choices': SampleRequest.STATUS_CHOICES,
        'total_count': sample_requests.count(),
        'pickup_pending_count': SampleRequest.objects.filter(status=SampleRequest.STATUS_PICKUP_PENDING).count(),
        'picked_up_count': SampleRequest.objects.filter(status=SampleRequest.STATUS_PICKED_UP).count(),
        'overdue_pickup_count': stats['overdue_count'],
        'ai_sample_advice': ai_sample_advice,
    }
    context.update(_build_supply_chain_source_summary())
    return render(request, 'supply_chain/sample_list.html', context)


@login_required
def sample_create(request):
    if request.method == 'POST':
        form = SampleRequestForm(request.POST)
        if form.is_valid():
            sample_request = form.save(commit=False)
            sample_request.code = generate_sample_request_code(
                current_date=date.today(),
                sequence=SampleRequest.objects.count() + 1,
            )
            sample_request.requested_by = request.user
            sample_request.status = SampleRequest.STATUS_ORDERED
            sample_request.save()
            messages.success(request, '打样申请已创建')
            return redirect('supply_chain:sample_list')
    else:
        form = SampleRequestForm()
    return render(request, 'supply_chain/sample_form.html', {
        'page_title': '新建打样申请',
        'form': form,
    })


@login_required
def sample_receive(request, pk):
    sample_request = get_object_or_404(SampleRequest, pk=pk)
    if request.method != 'POST':
        return redirect('supply_chain:sample_list')

    form = SampleReceiptForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, '到货信息无效')
        return redirect('supply_chain:sample_list')
    if sample_request.status not in {SampleRequest.STATUS_DRAFT, SampleRequest.STATUS_ORDERED}:
        messages.error(request, '当前打样单状态不允许重复登记到货')
        return redirect('supply_chain:sample_list')

    received_at = timezone.now()
    payload = build_receipt_payload(
        material_name=sample_request.material_name,
        specification=sample_request.specification,
        engineer_name=getattr(sample_request.engineer, 'name', '') or getattr(sample_request.engineer, 'username', ''),
        location=form.cleaned_data['location'],
        received_quantity=form.cleaned_data['received_quantity'],
    )
    photo_file = form.cleaned_data.get('photo_file')
    photo_path = ''
    if photo_file:
        photo_path = default_storage.save(
            f'supply_chain/sample_receipts/{timezone.now():%Y/%m}/{photo_file.name}',
            photo_file,
        )
    with transaction.atomic():
        SampleReceipt.objects.create(
            sample_request=sample_request,
            received_quantity=form.cleaned_data['received_quantity'],
            received_at=received_at,
            location=form.cleaned_data['location'],
            photo_path=photo_path,
            receiver=request.user,
        )
        sample_request.status = SampleRequest.STATUS_PICKUP_PENDING
        sample_request.save(update_fields=['status', 'update_time'])

    log_supply_chain_event(
        event_type='sample_received',
        title=f'样品 {sample_request.code} 已到货',
        object_type='sample_request',
        object_id=sample_request.id,
        payload=payload,
        operator=request.user,
    )
    notify_ids = [user_id for user_id in {sample_request.engineer_id, sample_request.requested_by_id} if user_id]
    send_supply_chain_notification(
        title=payload['notification_title'],
        content=payload['notification_message'],
        user_ids=notify_ids,
        related_object_type='sample_request',
        related_object_id=sample_request.id,
        action_url=reverse('supply_chain:sample_list'),
        sender=request.user,
        priority=3,
    )
    messages.success(request, '样品到货已登记')
    return redirect('supply_chain:sample_list')


@login_required
def sample_pickup(request, pk):
    sample_request = get_object_or_404(SampleRequest, pk=pk)
    if request.method != 'POST':
        return redirect('supply_chain:sample_list')

    form = SamplePickupForm(request.POST)
    if not form.is_valid():
        messages.error(request, '领样信息无效')
        return redirect('supply_chain:sample_list')
    if sample_request.status != SampleRequest.STATUS_PICKUP_PENDING:
        messages.error(request, '当前打样单尚未进入待领样状态')
        return redirect('supply_chain:sample_list')

    latest_receipt = sample_request.receipts.order_by('-received_at').first()
    if latest_receipt is None:
        messages.error(request, '尚未登记到货，不能确认领样')
        return redirect('supply_chain:sample_list')
    picked_at = timezone.now()
    overdue = is_pickup_overdue(
        received_at=latest_receipt.received_at if latest_receipt else None,
        current_time=picked_at,
    )
    with transaction.atomic():
        SamplePickupRecord.objects.create(
            sample_request=sample_request,
            picked_by=request.user,
            picked_at=picked_at,
            is_overdue=overdue,
            note=form.cleaned_data['note'],
        )
        sample_request.status = SampleRequest.STATUS_PICKED_UP
        sample_request.save(update_fields=['status', 'update_time'])

    log_supply_chain_event(
        event_type='sample_picked_up',
        title=f'样品 {sample_request.code} 已领样',
        object_type='sample_request',
        object_id=sample_request.id,
        payload={'is_overdue': overdue},
        operator=request.user,
    )
    messages.success(request, '领样已确认')
    return redirect('supply_chain:sample_list')


dashboard.permission_required = 'user.view_supply_chain_dashboard'
inventory_analysis.permission_required = 'user.view_supply_chain_inventory_analysis'
forecast_list.permission_required = 'user.view_supply_chain_forecast'
forecast_create.permission_required = 'user.add_supply_chain_forecast'
forecast_run.permission_required = 'user.add_supply_chain_forecast'
forecast_review.permission_required = 'user.approve_supply_chain_forecast'
outsource_list.permission_required = 'user.view_supply_chain_outsource'
outsource_create.permission_required = 'user.add_supply_chain_outsource'
outsource_check.permission_required = 'user.change_supply_chain_outsource'
outsource_status_update.permission_required = 'user.change_supply_chain_outsource'
pr_review_list.permission_required = 'user.view_supply_chain_pr_review'
pr_review_create.permission_required = 'user.add_supply_chain_pr_review'
pr_review_evaluate.permission_required = 'user.approve_supply_chain_pr_review'
pr_review_approve.permission_required = 'user.approve_supply_chain_pr_review'
pr_review_batch_approve.permission_required = 'user.approve_supply_chain_pr_review'
price_review_list.permission_required = 'user.view_supply_chain_price_review'
price_review_create.permission_required = 'user.add_supply_chain_price_review'
price_review_parse_document.permission_required = 'user.change_supply_chain_price_review'
price_review_analyze.permission_required = 'user.approve_supply_chain_price_review'
sample_list.permission_required = 'user.view_supply_chain_sample'
sample_create.permission_required = 'user.add_supply_chain_sample'
sample_receive.permission_required = 'user.change_supply_chain_sample'
sample_pickup.permission_required = 'user.change_supply_chain_sample'


# ============================================================
# Gap-fill views: sample remind, statistics, forecast trend,
# price review report, forecast QA, outsource from plan
# ============================================================

@login_required
def sample_remind(request, pk):
    """Send overdue pickup reminder for a sample request."""
    sample_request = get_object_or_404(SampleRequest.objects.prefetch_related("receipts"), pk=pk)
    if request.method != "POST":
        return redirect("supply_chain:sample_list")
    if sample_request.status != SampleRequest.STATUS_PICKUP_PENDING:
        messages.error(request, "当前打样单不在待领样状态，无法发送提醒")
        return redirect("supply_chain:sample_list")

    latest_receipt = sample_request.receipts.order_by("-received_at").first()
    if latest_receipt is None:
        messages.error(request, "该打样单尚未登记到货")
        return redirect("supply_chain:sample_list")

    from .services.sample_service import build_reminder_message, is_pickup_overdue
    if not is_pickup_overdue(latest_receipt.received_at):
        messages.warning(request, "尚未超期，可稍后再次提醒")
        return redirect("supply_chain:sample_list")

    new_count = (latest_receipt.reminder_count or 0) + 1
    reminder = build_reminder_message(sample_request, latest_receipt, latest_receipt.reminder_count)
    with transaction.atomic():
        latest_receipt.pickup_reminded_at = timezone.now()
        latest_receipt.reminder_count = new_count
        latest_receipt.save(update_fields=["pickup_reminded_at", "reminder_count"])

    engineer_id = sample_request.engineer_id
    notify_ids = [engineer_id] if engineer_id else []
    if notify_ids:
        send_supply_chain_notification(
            title=reminder["notification_title"],
            content=reminder["notification_message"],
            user_ids=notify_ids,
            related_object_type="sample_request",
            related_object_id=sample_request.id,
            action_url=reverse("supply_chain:sample_list"),
            sender=request.user,
            priority=2,
        )

    log_supply_chain_event(
        event_type="sample_reminder_sent",
        title=f"打样单 {sample_request.code} 发送第 {new_count} 次领样提醒",
        object_type="sample_request",
        object_id=sample_request.id,
        payload={"reminder_count": new_count},
        operator=request.user,
    )
    messages.success(request, f"已发送第 {new_count} 次领样提醒到工程师")
    return redirect("supply_chain:sample_list")


@login_required
def sample_statistics(request):
    """Sample monthly/quarterly statistics dashboard."""
    stats = get_sample_statistics()
    context = {
        "page_title": "打样台账统计",
        **stats,
    }
    return render(request, "supply_chain/sample_statistics.html", context)


@login_required
def forecast_trend(request):
    """Historical forecast accuracy trend analysis."""
    product_id = (request.GET.get("product_id") or "").strip()
    product = None
    if product_id:
        product = get_object_or_404(Product, pk=product_id)
    trend = build_forecast_trend_data(product=product)
    context = {
        "page_title": "预测历史趋势",
        "product": product,
        "product_id": product_id,
        **trend,
    }
    return render(request, "supply_chain/forecast_trend.html", context)


@login_required
def price_review_report(request):
    """Price review cost breakdown report."""
    report = build_price_review_report()
    context = {
        "page_title": "单价复核成本报表",
        **report,
    }
    return render(request, "supply_chain/price_review_report.html", context)


@login_required
def forecast_qa(request, pk):
    """Conversational Q&A about a forecast plan."""
    plan = get_object_or_404(
        DemandForecastPlan.objects.prefetch_related("results__reviews"),
        pk=pk,
    )
    result = plan.results.order_by("-create_time").first()
    qa_context = {}
    if result:
        history = list(
            DemandForecastResult.objects.filter(
                forecast_plan__product_id=plan.product_id,
            ).exclude(forecast_plan_id=plan.id).order_by("-create_time")[:5]
        )
        qa_context = {
            "result": result,
            "predicted": str(result.predicted_quantity),
            "recommended": str(result.recommended_quantity),
            "confidence": str(result.confidence),
            "risk_level": result.risk_level,
            "history_count": len(history),
            "history_confidence": (
                round(float(sum(h.confidence for h in history) / len(history)), 2)
                if history else None
            ),
        }
    if request.method == "POST":
        question = (request.POST.get("question") or "").strip()
        answer = supply_chain_ai.answer_forecast_question(
            plan_name=plan.name,
            predicted_quantity=result.predicted_quantity if result else Decimal('0'),
            recommended_quantity=result.recommended_quantity if result else Decimal('0'),
            risk_level=result.risk_level if result else 'unknown',
            confidence=float(result.confidence) if result else 0,
            question=question,
        ) or _generate_forecast_answer(plan, result, question, qa_context)
        qa_context["question"] = question
        qa_context["answer"] = answer
    context = {
        "page_title": f"需求问答: {plan.name}",
        "plan": plan,
        **qa_context,
    }
    return render(request, "supply_chain/forecast_qa.html", context)


def _generate_forecast_answer(plan, result, question, ctx):
    """Simple rule-based forecast Q&A."""
    question_lower = question.lower()
    if "建议" in question or "备料" in question or "recommend" in question_lower:
        return (
            f"预测计划「{plan.name}」的建议备料量为 {ctx.get('recommended', 'N/A')}。"
            f"该数值基于当前库存、在制、在途和已备料数据综合计算得出，置信度 {ctx.get('confidence', 'N/A')}%。"
            f"风险等级为 {ctx.get('risk_level', 'N/A')}。"
        )
    if "准确" in question or "accuracy" in question_lower or "置信" in question:
        return (
            f"当前预测置信度为 {ctx.get('confidence', 'N/A')}%。"
            + (
                f"该产品历史 {ctx.get('history_count', 0)} 次预测平均置信度为 {ctx.get('history_confidence', 'N/A')}%。"
                if ctx.get("history_confidence") else ""
            )
        )
    if "风险" in question or "risk" in question_lower:
        risk_map = {"high": "高风险 — 建议立即补充备料", "medium": "中风险 — 持续关注库存水位", "low": "低风险 — 当前备料充足"}
        return risk_map.get(ctx.get("risk_level", ""), "未检测到明确风险。")
    if "库存" in question or "inventory" in question_lower:
        return (
            f"预测计划「{plan.name}」关联产品 {plan.product or '未指定'}，预测需求量为 {ctx.get('predicted', 'N/A')}，"
            f"建议备料 {ctx.get('recommended', 'N/A')}。当前系统已综合库存水位和周转情况自动计算建议值。"
        )
    return (
        f"关于预测计划「{plan.name}」：预测量 {ctx.get('predicted', 'N/A')}，"
        f"建议备料 {ctx.get('recommended', 'N/A')}，置信度 {ctx.get('confidence', 'N/A')}%，"
        f"风险等级 {ctx.get('risk_level', 'N/A')}。如需了解具体维度（建议/准确度/风险/库存），请进一步描述。"
    )


@login_required
def outsource_generate_from_plan(request):
    """Generate outsource issue orders from production plans."""
    if request.method == "POST":
        plan_ids = request.POST.getlist("plan_ids")
        if not plan_ids:
            messages.error(request, "请至少选择一个生产计划")
            return redirect("supply_chain:outsource_generate_from_plan")

        plans = ProductionPlan.objects.filter(pk__in=plan_ids).select_related("product")
        created_count = 0
        with transaction.atomic():
            for plan in plans:
                bom = BOM.objects.filter(product=plan.product).order_by("-id").first()
                if bom is None:
                    continue
                existing = OutsourceIssueOrder.objects.filter(
                    production_plan=plan,
                    status__in=[
                        OutsourceIssueOrder.STATUS_DRAFT,
                        OutsourceIssueOrder.STATUS_SHORTAGE,
                        OutsourceIssueOrder.STATUS_READY,
                    ],
                ).exists()
                if existing:
                    continue
                order = OutsourceIssueOrder.objects.create(
                    code=_generate_serial("OIO", OutsourceIssueOrder),
                    production_plan=plan,
                    product=plan.product,
                    quantity=plan.quantity or 1,
                    created_by=request.user,
                )
                OutsourceIssueStatusLog.objects.create(
                    issue_order=order,
                    from_status="",
                    to_status=order.status,
                    message=f"从生产计划 {plan.code} 自动生成",
                    operator=request.user,
                )
                created_count += 1

        messages.success(request, f"已从 {len(plan_ids)} 个生产计划生成 {created_count} 条委外发料单")
        return redirect("supply_chain:outsource_list")

    plans = ProductionPlan.objects.filter(
        status__in=[1, 2, 3],
    ).select_related("product", "bom").order_by("-create_time")

    plan_data = []
    for plan in plans:
        has_existing = OutsourceIssueOrder.objects.filter(production_plan=plan).exists()
        plan_data.append({
            "plan": plan,
            "has_existing": has_existing,
            "bom_count": BOM.objects.filter(product=plan.product).count(),
        })

    context = {
        "page_title": "从生产计划生成委外发料单",
        "plan_data": plan_data,
    }
    return render(request, "supply_chain/outsource_generate_from_plan.html", context)


sample_remind.permission_required = 'user.change_supply_chain_sample'
sample_statistics.permission_required = 'user.view_supply_chain_sample'
forecast_trend.permission_required = 'user.view_supply_chain_forecast'
forecast_qa.permission_required = 'user.view_supply_chain_forecast'
price_review_report.permission_required = 'user.view_supply_chain_price_review'
outsource_generate_from_plan.permission_required = 'user.view_supply_chain_outsource'


@login_required
def source_sync(request):
    if request.method != 'POST':
        return redirect('supply_chain:dashboard')

    target = (request.POST.get('target') or 'dashboard').strip()
    with transaction.atomic():
        result = sync_supply_chain_sources(user=request.user)

    messages.success(
        request,
        '已同步项目真实业务来源：'
        f"预测 {result['forecast_created']} 条，"
        f"委外 {result['outsource_created']} 条，"
        f"PR {result['pr_created']} 条，"
        f"核价 {result['price_review_created']} 条，"
        '打样不会自动生成，请按真实需求创建。',
    )
    redirect_name = f'supply_chain:{target}' if ':' not in target else target
    return redirect(redirect_name)


source_sync.permission_required = 'user.view_supply_chain_dashboard'
