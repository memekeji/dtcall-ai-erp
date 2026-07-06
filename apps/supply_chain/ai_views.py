from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import DemandForecastPlan, DemandForecastResult, PRReviewTask, PriceReviewOrder


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
    summary = (
        f'预测量 {result.predicted_quantity}，建议备料量 {result.recommended_quantity}，'
        f'风险等级 {result.risk_level}，置信度 {result.confidence}%。'
    )
    return JsonResponse({
        'status': 'success',
        'data': {
            'summary': summary,
            'predicted_quantity': str(result.predicted_quantity),
            'recommended_quantity': str(result.recommended_quantity),
            'risk_level': result.risk_level,
            'confidence': str(result.confidence),
            'history_result_count': len(history_results),
            'historical_average_confidence': (
                f'{historical_average_confidence:.2f}'
                if historical_average_confidence is not None else None
            ),
        },
    })


@login_required
def price_review_ai_summary(request, pk):
    order = get_object_or_404(PriceReviewOrder.objects.select_related('conclusion', 'inventory_item', 'supplier'), pk=pk)
    conclusion = getattr(order, 'conclusion', None)
    if conclusion is None:
        return JsonResponse({'status': 'error', 'message': '暂无复核结论'}, status=404)

    summary_prefix = '建议议价' if conclusion.result == 'exception' else '建议按当前价格执行'
    abnormal_text = '、'.join(conclusion.abnormal_items or []) or '无异常项'
    summary = f'{summary_prefix}；风险等级 {conclusion.risk_level}；异常项：{abnormal_text}。'
    return JsonResponse({
        'status': 'success',
        'data': {
            'summary': summary,
            'result': conclusion.result,
            'risk_level': conclusion.risk_level,
            'negotiation_points': conclusion.negotiation_points,
        },
    })


@login_required
def pr_review_ai_summary(request, pk):
    task = get_object_or_404(PRReviewTask.objects.prefetch_related('matched_rules'), pk=pk)
    matched_codes = [rule.code for rule in task.matched_rules.all()]
    abnormal_text = '异常PR' if task.is_abnormal else '常规PR'
    summary = (
        f'{abnormal_text}；建议动作 {task.recommended_action or "pending"}；'
        f'命中规则：{", ".join(matched_codes) if matched_codes else "无"}。'
    )
    return JsonResponse({
        'status': 'success',
        'data': {
            'summary': summary,
            'is_abnormal': task.is_abnormal,
            'recommended_action': task.recommended_action,
            'matched_rules': matched_codes,
        },
    })


forecast_ai_summary.permission_required = 'user.view_supply_chain_forecast'
pr_review_ai_summary.permission_required = 'user.view_supply_chain_pr_review'
price_review_ai_summary.permission_required = 'user.view_supply_chain_price_review'
