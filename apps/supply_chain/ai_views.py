from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone

from .models import DemandForecastPlan, DemandForecastResult, PRReviewTask, PriceReviewOrder
from .services.ai_services import supply_chain_ai
from .services.ai_insight_service import refresh_ai_insight
from .services.inventory_analysis_service import build_inventory_analysis_summary, build_inventory_deep_analysis
from .services.sample_service import get_sample_statistics, is_pickup_overdue


@login_required
def forecast_ai_summary(request, pk):
    plan = get_object_or_404(DemandForecastPlan.objects.prefetch_related('results'), pk=pk)
    result = plan.results.order_by('-create_time').first()
    if result is None:
        return JsonResponse({'status': 'error', 'message': '暂无预测结果'}, status=404)

    history_results = []
    if plan.product_id:
        history_results = list(
            DemandForecastResult.objects.filter(
                forecast_plan__product_id=plan.product_id,
            ).exclude(
                forecast_plan_id=plan.id,
            ).order_by('-create_time')[:5]
        )
    historical_average_confidence = (
        sum(item.confidence for item in history_results) / len(history_results)
        if history_results else None
    )
    ai_result = supply_chain_ai.generate_forecast(
        product_name=str(plan.product or plan.name),
        historical_demand=[item.predicted_quantity for item in history_results],
        inventory_quantity=getattr(result, 'recommended_quantity', 0),
        wip_quantity=0,
        safety_stock=result.safety_stock,
    )
    summary = ai_result.get('summary') or (
        f'预测量 {result.predicted_quantity}，建议备料量 {result.recommended_quantity}，'
        f'风险等级 {result.risk_level}，置信度 {result.confidence}%。'
    )
    return JsonResponse({
        'status': 'success',
        'data': {
            'summary': summary,
            'predicted_quantity': str(ai_result.get('predicted_quantity') or result.predicted_quantity),
            'recommended_quantity': str(ai_result.get('recommended_quantity') or result.recommended_quantity),
            'risk_level': ai_result.get('risk_level') or result.risk_level,
            'confidence': str(ai_result.get('confidence') or result.confidence),
            'history_result_count': len(history_results),
            'historical_average_confidence': (
                f'{historical_average_confidence:.2f}'
                if historical_average_confidence is not None else None
            ),
            'ai_enabled': True,
        },
    })


@login_required
def price_review_ai_summary(request, pk):
    order = get_object_or_404(PriceReviewOrder.objects.select_related('conclusion', 'inventory_item', 'supplier'), pk=pk)
    conclusion = getattr(order, 'conclusion', None)
    if conclusion is None:
        return JsonResponse({'status': 'error', 'message': '暂无复核结论'}, status=404)

    component_summary = '; '.join(
        f'{component.component_name}:{component.amount}'
        for component in order.components.all()[:12]
    ) or conclusion.summary
    ai_result = supply_chain_ai.analyze_price_review(
        item_name=str(order.inventory_item or order.code),
        quoted_price=order.quoted_price,
        component_summary=component_summary,
        market_price=getattr(order.inventory_item, 'average_cost', 0) if order.inventory_item_id else 0,
        history_avg=getattr(order.inventory_item, 'latest_cost', 0) if order.inventory_item_id else 0,
    )
    summary_prefix = '建议议价' if conclusion.result == 'exception' else '建议按当前价格执行'
    abnormal_text = '、'.join(conclusion.abnormal_items or []) or '无异常项'
    summary = ai_result.get('summary') or f'{summary_prefix}；风险等级 {conclusion.risk_level}；异常项：{abnormal_text}。'
    return JsonResponse({
        'status': 'success',
        'data': {
            'summary': summary,
            'result': ai_result.get('result') or conclusion.result,
            'risk_level': ai_result.get('risk_level') or conclusion.risk_level,
            'negotiation_points': ai_result.get('negotiation_points') or conclusion.negotiation_points,
            'abnormal_items': ai_result.get('abnormal_items') or conclusion.abnormal_items,
            'ai_enabled': True,
        },
    })


@login_required
def pr_review_ai_summary(request, pk):
    task = get_object_or_404(PRReviewTask.objects.prefetch_related('matched_rules'), pk=pk)
    matched_rules = list(task.matched_rules.all())
    matched_codes = [rule.code for rule in matched_rules]
    payload = (task.evidence or {}).get('payload') or {}
    ai_result = supply_chain_ai.evaluate_pr(
        scenario=payload.get('scenario') or task.source_type or task.title,
        order_type=payload.get('order_type') or task.source_type,
        is_urgent=bool(payload.get('is_urgent')),
        lt_shortage=bool(payload.get('lt_shortage')),
        tail_order=bool(payload.get('tail_order')),
        npi_trial=bool(payload.get('npi_trial')),
        rework_order=bool(payload.get('rework_order')),
    )
    abnormal_text = '异常PR' if task.is_abnormal else '常规PR'
    summary = (
        f'{abnormal_text}；建议动作 {ai_result.get("recommended_action") or task.recommended_action or "pending"}；'
        f'命中规则：{", ".join(matched_codes) if matched_codes else "无"}。'
    )
    if ai_result.get('reason'):
        summary = f'{summary} AI判断：{ai_result["reason"]}'
    return JsonResponse({
        'status': 'success',
        'data': {
            'summary': summary,
            'is_abnormal': ai_result.get('is_abnormal', task.is_abnormal),
            'recommended_action': ai_result.get('recommended_action') or task.recommended_action,
            'risk_level': ai_result.get('risk_level'),
            'matched_rules': matched_codes,
            'ai_enabled': True,
        },
    })


def _insight_response(insight):
    return JsonResponse({
        'status': insight.status,
        'data': {
            'content': insight.content,
            'result': insight.result_payload,
            'error': insight.error_message,
            'generated_at': insight.generated_at.isoformat(),
        },
    })


def _finish_refresh(request, insight):
    next_route = request.POST.get('next')
    if next_route:
        if insight.status == insight.STATUS_SUCCESS:
            messages.success(request, 'AI分析已刷新')
        else:
            messages.warning(request, 'AI刷新失败，已保留上次有效结论')
        return redirect(next_route)
    return _insight_response(insight)


@login_required
def dashboard_ai_refresh(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '仅支持POST刷新'}, status=405)
    summary = build_inventory_analysis_summary()
    insight = refresh_ai_insight(
        scope='dashboard', object_type='inventory_overview', object_id=0, user=request.user,
        generator=lambda: supply_chain_ai.analyze_inventory_risk(
            total_items=summary.get('total_items', 0),
            high_risk_count=summary.get('high_risk_count', 0),
            medium_risk_count=summary.get('medium_risk_count', 0),
            dead_stock_count=0,
            safety_breach_count=summary.get('high_risk_count', 0),
            top_risk_items=[
                f"{row['item'].name}:{row['status']}"
                for row in summary.get('risk_rows', [])
                if row.get('risk_level') in {'high', 'medium'}
            ][:5],
        ),
    )
    return _finish_refresh(request, insight)


@login_required
def inventory_ai_refresh(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '仅支持POST刷新'}, status=405)
    summary = build_inventory_analysis_summary()
    deep_analysis = build_inventory_deep_analysis()
    insight = refresh_ai_insight(
        scope='inventory', object_type='inventory_overview', object_id=0, user=request.user,
        generator=lambda: supply_chain_ai.analyze_inventory_risk(
            total_items=summary.get('total_items', 0),
            high_risk_count=summary.get('high_risk_count', 0),
            medium_risk_count=summary.get('medium_risk_count', 0),
            dead_stock_count=deep_analysis.get('dead_stock_count', 0),
            safety_breach_count=deep_analysis.get('safety_breach_count', 0),
            top_risk_items=[
                f"{row['item'].name}:{row['status']}"
                for row in summary.get('risk_rows', [])
                if row.get('risk_level') in {'high', 'medium'}
            ][:5],
        ),
    )
    return _finish_refresh(request, insight)


@login_required
def sample_ai_refresh(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '仅支持POST刷新'}, status=405)
    from .models import SampleReceipt, SampleRequest

    stats = get_sample_statistics()
    pending_receipts = SampleReceipt.objects.filter(
        sample_request__status=SampleRequest.STATUS_PICKUP_PENDING,
    ).select_related('sample_request')[:5]
    overdue_details = [
        receipt.sample_request.material_name
        for receipt in pending_receipts
        if is_pickup_overdue(receipt.received_at, current_time=timezone.now())
    ]
    insight = refresh_ai_insight(
        scope='sample', object_type='sample_priority', object_id=0, user=request.user,
        generator=lambda: supply_chain_ai.suggest_sample_priority(
            pending_count=SampleRequest.objects.filter(status=SampleRequest.STATUS_PICKUP_PENDING).count(),
            overdue_count=stats['overdue_count'],
            overdue_details=overdue_details,
        ),
    )
    return _finish_refresh(request, insight)


forecast_ai_summary.permission_required = 'user.view_supply_chain_forecast'
pr_review_ai_summary.permission_required = 'user.view_supply_chain_pr_review'
price_review_ai_summary.permission_required = 'user.view_supply_chain_price_review'
dashboard_ai_refresh.permission_required = 'user.view_supply_chain_dashboard'
inventory_ai_refresh.permission_required = 'user.view_supply_chain_inventory_analysis'
sample_ai_refresh.permission_required = 'user.view_supply_chain_sample'
