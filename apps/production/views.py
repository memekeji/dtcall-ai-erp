from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q, Avg, Count, Sum, Max
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib import messages
from django import forms as django_forms
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from apps.user.models import Admin
from .models import (
    ProductionProcedure, ProcedureSet, BOM, Equipment, ProductionPlan,
    ProductionTask, QualityCheck, DataCollection, DataSource,
    DataCollectionRecord, SOP, DataMapping, ProductionDataPoint,
    DataCollectionTask, ProductionOrderChange, ProductionLineDayPlan,
    MaterialRequest, MaterialIssue,
    MaterialReturn, WorkCompletionReport, WorkCompletionRedFlush, ProductReceipt,
    MaterialScrap,
    OrderMaterialConfirmation, ResourceConsumption, ProcessRoute
)
from .forms import (
    ProductionProcedureForm,
    ProcedureSetForm,
    ProcedureSetItemInlineFormSet,
    BOMForm,
    BOMItemInlineFormSet,
    EquipmentForm,
    ProductionPlanForm,
    ProductionTaskForm,
    QualityCheckForm,
    DataCollectionForm,
    DataSourceForm,
    DataMappingForm,
    SOPForm,
    ProcessRouteForm,
    ProcessRouteItemInlineFormSet,
    ProductionOrderChangeForm,
    ProductionLineDayPlanForm,
    MaterialRequestForm,
    MaterialIssueForm,
    MaterialReturnForm,
    MaterialScrapForm,
    WorkCompletionReportForm,
    WorkCompletionRedFlushForm,
    ProductReceiptForm,
    OrderMaterialConfirmationForm,
    ResourceConsumptionForm,
    DataCollectionTaskForm)
from .services.data_collector import DataCollectorService
from .services.material_flow_service import MaterialFlowError, MaterialFlowService
from .services.scheduling_service import SchedulingOptimizerService, GanttChartService, DeliveryPredictionService
from .services.monitoring_service import EquipmentMonitorService, AlertRuleService
from .services.statistics_service import ProductionStatisticsService


def _style_production_form(form):
    """统一生产模块表单控件样式，使其与项目现有 layui 风格一致。"""
    for field in form.fields.values():
        widget = field.widget
        attrs = widget.attrs
        attrs.pop('class', None)
        if isinstance(widget, django_forms.CheckboxInput):
            continue
        if isinstance(widget, django_forms.Textarea):
            attrs['class'] = 'layui-textarea'
            attrs.setdefault('rows', 3)
        else:
            attrs['class'] = 'layui-input'
        if not attrs.get('placeholder') and field.label:
            attrs['placeholder'] = f'请输入{field.label}' if not isinstance(widget, (django_forms.Select, django_forms.SelectMultiple)) else f'请选择{field.label}'
    return form


def _apply_request_user_defaults(obj, request_user):
    """统一补齐新增单据的责任人字段，保证数据可追溯。"""
    for field_name in ('creator', 'created_by', 'confirmed_by'):
        field_id_name = f'{field_name}_id'
        if hasattr(obj, field_id_name) and not getattr(obj, field_id_name, None):
            setattr(obj, field_name, request_user)
    return obj


def _style_production_formset(formset):
    """统一内联表单集样式。"""
    for form in list(formset.forms) + [formset.empty_form]:
        _style_production_form(form)
        if 'DELETE' in form.fields:
            form.fields['DELETE'].label = '删除'
    return formset


def _build_equipment_monitor_context():
    """统一构建设备监控页上下文，避免不同入口上下文字段漂移。"""
    service = EquipmentMonitorService()
    alert_service = AlertRuleService()
    equipment_status = []
    raw_status_list = service.get_all_equipment_status()

    for raw_status in raw_status_list:
        equipment = raw_status.get('equipment') or {}
        current_task = raw_status.get('current_task') or {}
        latest_data = raw_status.get('latest_data') or {}
        latest_metric_value = latest_data.get('metric_value')
        if latest_metric_value is None:
            latest_metric_value = latest_data.get('parameter_value')
        latest_metric_unit = latest_data.get('metric_unit') or latest_data.get('unit') or ''
        latest_metric_name = latest_data.get('metric_name') or latest_data.get('parameter_name') or ''
        latest_timestamp = latest_data.get('timestamp')
        equipment_status.append({
            'id': equipment.get('id'),
            'code': equipment.get('code') or '-',
            'name': equipment.get('name') or '-',
            'status': equipment.get('status'),
            'status_display': equipment.get('status_display') or '未知',
            'location': equipment.get('location') or '-',
            'department': equipment.get('department') or '-',
            'responsible_person': equipment.get('responsible_person') or '-',
            'current_task': current_task or None,
            'task_name': current_task.get('name') or '-',
            'task_code': current_task.get('code') or '',
            'progress': current_task.get('progress') if current_task else None,
            'latest_metric_name': latest_metric_name,
            'latest_metric_value': latest_metric_value,
            'latest_metric_unit': latest_metric_unit,
            'latest_timestamp': latest_timestamp,
            'alert_count': len(raw_status.get('alerts') or []),
        })

    alerts = alert_service.get_all_alerts(limit=50)
    active_alerts = [alert for alert in alerts if not alert.get('acknowledged')]

    normal_count = sum(1 for item in equipment_status if item['status'] == 1)
    maintenance_count = sum(1 for item in equipment_status if item['status'] == 2)
    stopped_count = sum(1 for item in equipment_status if item['status'] == 3)
    scrap_count = sum(1 for item in equipment_status if item['status'] not in (1, 2, 3))

    return {
        'equipment_status': equipment_status,
        'normal_count': normal_count,
        'maintenance_count': maintenance_count,
        'stopped_count': stopped_count,
        'scrap_count': scrap_count,
        'total_count': len(equipment_status),
        'active_alert_count': len(active_alerts),
        'active_alerts': active_alerts[:8],
        'data_point_count': ProductionDataPoint.objects.count(),
        'collection_count': DataCollection.objects.count(),
        'task_count': ProductionTask.objects.count(),
        'has_live_data': ProductionDataPoint.objects.exists() or DataCollection.objects.exists(),
        'last_refresh_time': timezone.now(),
    }


def _sync_procedure_set_metrics(procedure_set):
    total_time = Decimal('0')
    total_cost = Decimal('0')
    for item in procedure_set.proceduresetitem_set.select_related('procedure').all():
        estimated_time = Decimal(str(item.estimated_time or 0))
        procedure_cost = Decimal(str(item.procedure.cost_per_hour or 0))
        total_time += estimated_time
        total_cost += estimated_time * procedure_cost
    procedure_set.total_time = total_time
    procedure_set.total_cost = total_cost
    procedure_set.save(update_fields=['total_time', 'total_cost', 'update_time'])
    return procedure_set


def _sync_process_route_metrics(route):
    total_time = Decimal('0')
    total_cost = Decimal('0')
    for item in route.processrouteitem_set.select_related('procedure').all():
        estimated_time = Decimal(str(item.estimated_time or 0))
        procedure_cost = Decimal(str(item.procedure.cost_per_hour or 0))
        total_time += estimated_time
        total_cost += estimated_time * procedure_cost
    route.total_time = total_time
    route.total_cost = total_cost
    route.save(update_fields=['total_time', 'total_cost', 'update_time'])
    return route


def _render_inline_form_page(
        request,
        form_class,
        formset_class,
        template_name,
        success_route,
        success_label,
        model_class=None,
        pk=None,
        after_save=None,
        extra_context=None):
    """渲染主表 + 明细行的结构化表单页。"""
    instance = get_object_or_404(model_class, pk=pk) if model_class and pk else None
    action = '编辑' if instance else '添加'

    if request.method == 'POST':
        form = form_class(request.POST, instance=instance)
        formset = formset_class(request.POST, instance=instance or form.instance, prefix='items')
        _style_production_form(form)
        _style_production_formset(formset)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                _apply_request_user_defaults(obj, request.user)
                obj.save()
                if hasattr(form, 'save_m2m'):
                    form.save_m2m()
                formset.instance = obj
                formset.save()
                if after_save:
                    after_save(obj)
            messages.success(request, f'{success_label}{action}成功')
            return redirect(success_route)
    else:
        form = form_class(instance=instance)
        formset = formset_class(instance=instance, prefix='items')
        _style_production_form(form)
        _style_production_formset(formset)

    context = {
        'form': form,
        'formset': formset,
        'action': action,
    }
    if extra_context:
        context.update(extra_context)
    return render(request, template_name, context)


def _build_resource_consumption_payload(task):
    payload = []
    for item in task.resource_consumptions.order_by('-consumption_time'):
        payload.append({
            'resource_type': item.resource_type,
            'resource_name': item.resource_name,
            'consumed_quantity': str(item.consumed_quantity),
            'unit': item.unit,
            'cost': str(item.cost),
            'consumption_time': item.consumption_time.isoformat() if item.consumption_time else '',
        })
    return payload


def _initialize_form_with_query_data(form, request, mapping):
    for field_name, query_name in mapping.items():
        value = request.GET.get(query_name)
        if value and field_name in form.fields and not form.initial.get(field_name):
            form.initial[field_name] = value
    return form


def _ensure_day_plan_defaults(day_plan, request_user):
    if not day_plan.code:
        day_plan.code = MaterialFlowService.generate_code('DPL')
    if not day_plan.creator_id:
        day_plan.creator = request_user
    if day_plan.production_plan_id:
        plan = day_plan.production_plan
        if not day_plan.name:
            day_plan.name = f'{plan.name}日计划'
        if not day_plan.quantity:
            day_plan.quantity = plan.quantity
        if not day_plan.manager_id and plan.manager_id:
            day_plan.manager = plan.manager
        if not day_plan.plan_date:
            day_plan.plan_date = plan.plan_start_date
    return day_plan


def _apply_order_change(change):
    plan = change.production_plan
    new_value = change.new_value or {}
    change_type = (change.change_type or '').strip()

    if change_type == 'quantity':
        quantity = Decimal(str(new_value.get('quantity') or 0))
        if quantity <= 0:
            raise ValueError('数量变更后的值必须大于 0')
        plan.quantity = quantity
        plan.save(update_fields=['quantity', 'update_time'])
        for day_plan in plan.day_plans.all():
            day_plan.quantity = quantity
            day_plan.save(update_fields=['quantity', 'update_time'])
        for material_request in plan.material_requests.filter(status__in=[1, 2]):
            material_request.items.all().delete()
            MaterialFlowService.ensure_material_request_items(material_request)
        for material_issue in plan.material_issues.filter(status__in=[1, 2]):
            material_issue.items.all().delete()
            MaterialFlowService.ensure_material_issue_items(material_issue)
    elif change_type == 'date':
        start_date = new_value.get('plan_start_date')
        end_date = new_value.get('plan_end_date')
        if isinstance(start_date, str) and start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str) and end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        if start_date:
            plan.plan_start_date = start_date
        if end_date:
            plan.plan_end_date = end_date
        plan.save(update_fields=['plan_start_date', 'plan_end_date', 'update_time'])
        if start_date:
            for day_plan in plan.day_plans.filter(status__in=[1, 2]):
                day_plan.plan_date = start_date
                day_plan.save(update_fields=['plan_date', 'update_time'])
    elif change_type == 'spec':
        if plan.product_id:
            plan.product.specs = new_value.get('specs', '')
            plan.product.save(update_fields=['specs'])
    else:
        detail = new_value.get('value', '')
        change_note = f'[{timezone.now():%Y-%m-%d %H:%M}] 订单变更：{detail}'
        plan.description = f'{plan.description}\n{change_note}'.strip()
        plan.save(update_fields=['description', 'update_time'])

    change.status = 3
    change.executed_time = timezone.now()
    change.save(update_fields=['status', 'executed_time'])
    return plan


def _get_paginated_queryset(
        request,
        queryset,
        search_fields=None,
        default_order='-create_time',
        select_related=None,
        prefetch_related=None):
    """通用的分页查询辅助函数，支持关联查询优化"""
    search = request.GET.get('search', '').strip()
    order = request.GET.get('order', default_order)

    if search and search_fields:
        query = Q()
        for field in search_fields:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)

    if select_related:
        queryset = queryset.select_related(*select_related)

    if prefetch_related:
        queryset = queryset.prefetch_related(*prefetch_related)

    paginator = Paginator(queryset.order_by(order), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search': search,
        'order': order,
    }
    return page_obj, context


def _build_copy_code(model_class, source_code):
    """为复制对象生成不冲突的新编号"""
    base_code = f'{source_code}_COPY'
    candidate_code = base_code
    suffix = 1

    while model_class.objects.filter(code=candidate_code).exists():
        suffix += 1
        candidate_code = f'{base_code}{suffix}'

    return candidate_code


def _render_paginated_list(
        request,
        queryset,
        template_name,
        model_name,
        search_fields=None,
        default_order='-create_time',
        extra_context=None):
    """渲染标准分页列表页。"""
    page_obj, context = _get_paginated_queryset(
        request,
        queryset,
        search_fields=search_fields,
        default_order=default_order
    )
    context['model_name'] = model_name
    if extra_context:
        context.update(extra_context)
    return render(request, template_name, context)


def _render_model_form(
        request,
        form_class,
        template_name,
        success_route,
        success_label,
        model_class=None,
        pk=None,
        extra_context=None):
    """渲染标准新增/编辑表单页。"""
    instance = get_object_or_404(model_class, pk=pk) if model_class and pk else None
    action = '编辑' if instance else '添加'

    if request.method == 'POST':
        form = form_class(request.POST, instance=instance)
        _style_production_form(form)
        if form.is_valid():
            obj = form.save(commit=False)
            _apply_request_user_defaults(obj, request.user)
            obj.save()
            if hasattr(form, 'save_m2m'):
                form.save_m2m()
            messages.success(request, f'{success_label}{action}成功')
            return redirect(success_route)
    else:
        form = form_class(instance=instance)
        _style_production_form(form)

    context = {'form': form, 'action': action}
    if extra_context:
        context.update(extra_context)
    return render(request, template_name, context)


def _delete_model_object(request, model_class, pk, success_route, success_label):
    """删除标准模型对象并跳回列表页。"""
    obj = get_object_or_404(model_class, pk=pk)
    obj.delete()
    messages.success(request, f'{success_label}删除成功')
    return redirect(success_route)


def baseinfo_index(request):
    """基础信息首页"""
    context = {
        'procedure_count': ProductionProcedure.objects.count(),
        'procedureset_count': ProcedureSet.objects.count(),
        'bom_count': BOM.objects.count(),
        'equipment_count': Equipment.objects.count(),
        'process_route_count': ProcessRoute.objects.count(),
        'data_source_count': DataSource.objects.count(),
        'data_task_count': DataCollectionTask.objects.count(),
    }
    return render(request, 'production/baseinfo/index.html', context)


def procedure_list(request):
    """基本工序列表"""
    return _render_paginated_list(
        request,
        ProductionProcedure.objects.all(),
        'production/procedure/list.html',
        '基本工序',
        search_fields=['name', 'code'],
        default_order='-create_time'
    )


def procedure_add(request):
    """添加工序"""
    return _render_model_form(
        request,
        ProductionProcedureForm,
        'production/procedure/form.html',
        'production:procedure_list',
        '工序'
    )


def procedure_edit(request, pk):
    """编辑工序"""
    return _render_model_form(
        request,
        ProductionProcedureForm,
        'production/procedure/form.html',
        'production:procedure_list',
        '工序',
        model_class=ProductionProcedure,
        pk=pk
    )


def procedure_delete(request, pk):
    """删除工序"""
    return _delete_model_object(
        request, ProductionProcedure, pk, 'production:procedure_list', '工序')


def procedureset_list(request):
    """工序集列表"""
    return _render_paginated_list(
        request,
        ProcedureSet.objects.annotate(item_count=Count('proceduresetitem')).all(),
        'production/procedureset/list.html',
        '工序集',
        search_fields=['name', 'code'],
        default_order='-create_time'
    )


def procedureset_add(request):
    """添加工序集"""
    return _render_inline_form_page(
        request,
        ProcedureSetForm,
        ProcedureSetItemInlineFormSet,
        'production/procedureset/form.html',
        'production:procedureset_list',
        '工序集',
        after_save=_sync_procedure_set_metrics,
    )


def procedureset_edit(request, pk):
    """编辑工序集"""
    return _render_inline_form_page(
        request,
        ProcedureSetForm,
        ProcedureSetItemInlineFormSet,
        'production/procedureset/form.html',
        'production:procedureset_list',
        '工序集',
        model_class=ProcedureSet,
        pk=pk,
        after_save=_sync_procedure_set_metrics,
    )


def procedureset_delete(request, pk):
    """删除工序集"""
    return _delete_model_object(
        request, ProcedureSet, pk, 'production:procedureset_list', '工序集')


def procedureset_detail(request, pk):
    """工序集详情"""
    procedureset = get_object_or_404(ProcedureSet, pk=pk)
    items = procedureset.proceduresetitem_set.select_related('procedure').all().order_by('sequence')
    return render(
        request,
        'production/procedureset/detail.html',
        {
            'procedureset': procedureset,
            'items': items,
        },
    )


def bom_list(request):
    """BOM列表"""
    return _render_paginated_list(
        request,
        BOM.objects.select_related('product', 'creator').annotate(item_count=Count('items')).all(),
        'production/bom/list.html',
        'BOM',
        search_fields=['name', 'code'],
        default_order='-create_time'
    )


def bom_add(request):
    """添加BOM"""
    return _render_inline_form_page(
        request,
        BOMForm,
        BOMItemInlineFormSet,
        'production/bom/form.html',
        'production:bom_list',
        'BOM'
    )


def bom_edit(request, pk):
    """编辑BOM"""
    return _render_inline_form_page(
        request,
        BOMForm,
        BOMItemInlineFormSet,
        'production/bom/form.html',
        'production:bom_list',
        'BOM',
        model_class=BOM,
        pk=pk
    )


def bom_delete(request, pk):
    """删除BOM"""
    return _delete_model_object(request, BOM, pk, 'production:bom_list', 'BOM')


def bom_detail(request, pk):
    """BOM详情"""
    bom = get_object_or_404(BOM, pk=pk)
    items = MaterialFlowService.build_bom_inventory_snapshot(bom)
    total_cost = sum([row['item'].total_cost for row in items if row['item'].total_cost])
    return render(request, 'production/bom/detail.html',
                  {'bom': bom, 'items': items, 'total_cost': total_cost})


def bom_copy(request, pk):
    """复制BOM"""
    bom = get_object_or_404(BOM, pk=pk)
    items = list(bom.items.all())

    bom.pk = None
    bom.code = _build_copy_code(BOM, bom.code)
    bom.name = f'{bom.name}-副本'
    bom.status = True
    bom.save()

    for item in items:
        item.pk = None
        item.bom = bom
        item.save()

    messages.success(request, 'BOM复制成功')
    return redirect('production:bom_list')


def equipment_list(request):
    """设备列表"""
    equipment_list = Equipment.objects.select_related(
        'department', 'responsible_person', 'creator'
    ).all()
    status = request.GET.get('status', '').strip()
    if status:
        equipment_list = equipment_list.filter(status=status)
    page_obj, context = _get_paginated_queryset(
        request, equipment_list,
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    context['model_name'] = '设备'
    context['status'] = status
    context['status_choices'] = Equipment.STATUS_CHOICES
    return render(request, 'production/equipment/list.html', context)


def equipment_add(request):
    """添加设备"""
    return _render_model_form(
        request,
        EquipmentForm,
        'production/equipment/form.html',
        'production:equipment_list',
        '设备'
    )


def equipment_edit(request, pk):
    """编辑设备"""
    return _render_model_form(
        request,
        EquipmentForm,
        'production/equipment/form.html',
        'production:equipment_list',
        '设备',
        model_class=Equipment,
        pk=pk
    )


def equipment_delete(request, pk):
    """删除设备"""
    return _delete_model_object(
        request, Equipment, pk, 'production:equipment_list', '设备')


def equipment_detail(request, pk):
    """设备详情"""
    equipment = get_object_or_404(Equipment, pk=pk)
    recent_data = DataCollection.objects.filter(
        equipment=equipment
    ).order_by('-collect_time')[:20]
    data_points = equipment.data_points.all().order_by('-timestamp')[:100]
    current_task = ProductionTask.objects.filter(
        equipment=equipment,
        status=2,
    ).select_related('plan', 'procedure', 'assignee').order_by('-create_time').first()
    recent_tasks = ProductionTask.objects.filter(
        equipment=equipment
    ).select_related('plan', 'procedure', 'assignee').order_by('-create_time')[:6]
    maintenance_overdue = bool(
        equipment.next_maintenance and equipment.next_maintenance < timezone.now().date()
    )
    return render(request, 'production/equipment/detail.html',
                  {
                      'equipment': equipment,
                      'recent_data': recent_data,
                      'data_points': data_points,
                      'recent_tasks': recent_tasks,
                      'current_task': current_task,
                      'maintenance_overdue': maintenance_overdue,
                  })


def equipment_monitor(request):
    """设备监控"""
    context = _build_equipment_monitor_context()
    return render(request, 'production/monitor/index.html', context)


def data_collection_list(request):
    """数据采集列表"""
    collections = DataCollection.objects.select_related(
        'equipment', 'task', 'created_by'
    ).all()
    selected_equipment = request.GET.get('equipment', '').strip()
    selected_task = request.GET.get('task', '').strip()
    status = request.GET.get('status', '').strip()
    if selected_equipment:
        collections = collections.filter(equipment_id=selected_equipment)
    if selected_task:
        collections = collections.filter(task_id=selected_task)
    if status == 'normal':
        collections = collections.filter(is_normal=True)
    elif status == 'abnormal':
        collections = collections.filter(is_normal=False)
    page_obj, context = _get_paginated_queryset(
        request, collections,
        search_fields=['parameter_name', 'task__name', 'task__code', 'equipment__name', 'equipment__code'],
        default_order='-collect_time'
    )
    summary = collections.aggregate(
        total=Count('id'),
        abnormal_count=Count('id', filter=Q(is_normal=False)),
        equipment_count=Count('equipment', distinct=True),
        task_count=Count('task', distinct=True),
        latest_collect_time=Max('collect_time'),
    )
    context['equipments'] = Equipment.objects.all().order_by('name')
    context['tasks'] = ProductionTask.objects.select_related('plan').all().order_by('name')
    context['selected_equipment'] = selected_equipment
    context['selected_task'] = selected_task
    context['selected_status'] = status
    context['summary'] = summary
    return render(request, 'production/data/list.html', context)


def data_collection_add(request):
    """添加数据采集"""
    return _render_model_form(
        request,
        DataCollectionForm,
        'production/data/form.html',
        'production:data_collection_list',
        '数据采集'
    )


def data_chart(request, equipment_id):
    """数据图表"""
    equipment = get_object_or_404(Equipment, pk=equipment_id)
    data_points = ProductionDataPoint.objects.filter(
        equipment=equipment).order_by('-timestamp')[:100]
    return render(request, 'production/data/chart.html',
                  {'equipment': equipment, 'data_points': data_points})


def sop_list(request):
    """SOP列表"""
    sop_queryset = SOP.objects.select_related('procedure', 'creator').all()
    page_obj, context = _get_paginated_queryset(
        request,
        sop_queryset,
        search_fields=['name', 'code', 'procedure__name', 'procedure__code'],
        default_order='-create_time'
    )
    summary = sop_queryset.aggregate(
        total=Count('id'),
        active_count=Count('id', filter=Q(status=True)),
        inactive_count=Count('id', filter=Q(status=False)),
        covered_procedure_count=Count('procedure', distinct=True),
    )
    context.update({
        'summary': summary,
    })
    return render(request, 'production/sop/list.html', context)


def sop_add(request):
    """添加SOP"""
    return _render_model_form(
        request,
        SOPForm,
        'production/sop/form.html',
        'production:sop_list',
        'SOP'
    )


def sop_edit(request, pk):
    """编辑SOP"""
    return _render_model_form(
        request,
        SOPForm,
        'production/sop/form.html',
        'production:sop_list',
        'SOP',
        model_class=SOP,
        pk=pk
    )


def sop_delete(request, pk):
    """删除SOP"""
    return _delete_model_object(request, SOP, pk, 'production:sop_list', 'SOP')


def sop_detail(request, pk):
    """SOP详情"""
    sop = get_object_or_404(SOP, pk=pk)
    return render(request, 'production/sop/detail.html', {'sop': sop})


def production_task_index(request):
    """生产管理首页"""
    recent_plans = ProductionPlan.objects.select_related('product').all().order_by('-create_time')[:5]
    recent_tasks = ProductionTask.objects.select_related('plan', 'procedure').all().order_by('-create_time')[:5]
    equipments = Equipment.objects.all().order_by('-status')[:5]
    equipment_total = Equipment.objects.count()
    active_equipment_count = Equipment.objects.filter(status=1).count()
    equipment_utilization = round((active_equipment_count / equipment_total) * 100, 2) if equipment_total else 0
    avg_completion = ProductionTask.objects.exclude(status=5).aggregate(avg_rate=Avg('completed_quantity'))['avg_rate'] or 0
    task_total = ProductionTask.objects.count()
    production_efficiency = round((ProductionTask.objects.filter(status=3).count() / task_total) * 100, 2) if task_total else 0

    context = {
        'plan_count': ProductionPlan.objects.count(),
        'task_count': ProductionTask.objects.count(),
        'completed_task_count': ProductionTask.objects.filter(status=3).count(),
        'active_task_count': ProductionTask.objects.filter(status=2).count(),
        'active_plan_count': ProductionPlan.objects.filter(status=3).count(),
        'equipment_utilization': equipment_utilization,
        'production_efficiency': production_efficiency,
        'avg_completion': round(avg_completion, 2) if avg_completion else 0,
        'recent_plans': recent_plans,
        'recent_tasks': recent_tasks,
        'equipments': equipments,
        'material_request_count': MaterialRequest.objects.count(),
        'completion_report_count': WorkCompletionReport.objects.count(),
        'receipt_count': ProductReceipt.objects.count(),
        'maintenance_due_count': Equipment.objects.filter(
            next_maintenance__isnull=False,
            next_maintenance__lte=timezone.now().date(),
        ).count(),
    }
    return render(request, 'production/task/index.html', context)


def production_plan_list(request):
    """计划列表"""
    plans = ProductionPlan.objects.select_related(
        'product',
        'bom',
        'procedure_set',
        'process_route',
        'department',
        'manager').all()
    status = request.GET.get('status', '').strip()
    if status:
        plans = plans.filter(status=status)
    page_obj, context = _get_paginated_queryset(
        request, plans,
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    context['model_name'] = '生产计划'
    context['status'] = status
    context['status_choices'] = ProductionPlan.STATUS_CHOICES
    return render(request, 'production/plan/list.html', context)


def production_plan_add(request):
    """添加计划"""
    return _render_model_form(
        request,
        ProductionPlanForm,
        'production/plan/form.html',
        'production:production_plan_list',
        '生产计划'
    )


def production_plan_edit(request, pk):
    """编辑计划"""
    return _render_model_form(
        request,
        ProductionPlanForm,
        'production/plan/form.html',
        'production:production_plan_list',
        '生产计划',
        model_class=ProductionPlan,
        pk=pk
    )


def production_plan_delete(request, pk):
    """删除计划"""
    return _delete_model_object(
        request, ProductionPlan, pk, 'production:production_plan_list', '生产计划')


def production_plan_detail(request, pk):
    """计划详情"""
    plan = get_object_or_404(
        ProductionPlan.objects.select_related('product', 'bom', 'procedure_set', 'process_route', 'department', 'manager'),
        pk=pk,
    )
    tasks = plan.tasks.select_related('procedure', 'equipment', 'assignee').all()
    day_plans = plan.day_plans.all()[:5]
    completion_reports = WorkCompletionReport.objects.filter(
        production_task__plan=plan
    ).select_related('production_task').order_by('-create_time')[:5]
    return render(request, 'production/plan/detail.html',
                  {
                      'plan': plan,
                      'tasks': tasks,
                      'day_plans': day_plans,
                      'completion_reports': completion_reports,
                      'material_request_count': plan.material_requests.count(),
                      'material_issue_count': plan.material_issues.count(),
                      'material_return_count': plan.material_returns.count(),
                      'material_scrap_count': plan.material_scraps.count(),
                      'product_receipt_count': plan.product_receipts.count(),
                  })


def production_task_list(request):
    """任务列表"""
    tasks = ProductionTask.objects.select_related(
        'plan__product', 'procedure', 'equipment', 'assignee', 'creator'
    ).all()
    status = request.GET.get('status', '').strip()
    assignee = request.GET.get('assignee', '').strip()
    equipment = request.GET.get('equipment', '').strip()
    if status:
        tasks = tasks.filter(status=status)
    if assignee:
        tasks = tasks.filter(assignee_id=assignee)
    if equipment:
        tasks = tasks.filter(equipment_id=equipment)
    page_obj, context = _get_paginated_queryset(
        request, tasks,
        search_fields=['name', 'code', 'plan__name', 'plan__code', 'procedure__name', 'equipment__name', 'equipment__code', 'assignee__username'],
        default_order='-create_time'
    )
    context['model_name'] = '生产任务'
    context['status'] = status
    context['assignee'] = assignee
    context['equipment'] = equipment
    context['status_choices'] = ProductionTask.STATUS_CHOICES
    context['assignees'] = Admin.objects.filter(is_active=True).order_by('username')
    context['equipments'] = Equipment.objects.order_by('name')
    return render(request, 'production/task_execution/list.html', context)


def production_task_add(request):
    """添加任务"""
    return _render_model_form(
        request,
        ProductionTaskForm,
        'production/task_execution/form.html',
        'production:production_task_list',
        '生产任务'
    )


def production_task_edit(request, pk):
    """编辑任务"""
    return _render_model_form(
        request,
        ProductionTaskForm,
        'production/task_execution/form.html',
        'production:production_task_list',
        '生产任务',
        model_class=ProductionTask,
        pk=pk
    )


def production_task_delete(request, pk):
    """删除任务"""
    return _delete_model_object(
        request, ProductionTask, pk, 'production:production_task_list', '生产任务')


def production_task_detail(request, pk):
    """任务详情"""
    task = get_object_or_404(
        ProductionTask.objects.select_related('plan', 'procedure', 'equipment', 'assignee', 'creator', 'suspended_by'),
        pk=pk,
    )
    quality_checks = task.quality_checks.all()
    data_collections = task.data_collections.all()
    completion_reports = task.completion_reports.select_related('approved_by', 'created_by').all()
    resource_consumptions = task.resource_consumptions.all()
    material_confirmations = OrderMaterialConfirmation.objects.filter(
        material_issue__production_plan=task.plan
    ).select_related('material_issue').order_by('-confirm_time')[:5]
    return render(request, 'production/task_execution/detail.html', {
        'task': task,
        'quality_checks': quality_checks,
        'data_collections': data_collections,
        'completion_reports': completion_reports,
        'resource_consumptions': resource_consumptions,
        'material_confirmations': material_confirmations,
    })


def production_task_start(request, pk):
    """开始任务"""
    task = get_object_or_404(ProductionTask, pk=pk)
    task.status = 2
    task.actual_start_time = timezone.now()
    task.save()
    messages.success(request, '任务已开始')
    return redirect('production:production_task_detail', pk=pk)


def production_task_complete(request, pk):
    """完成任务"""
    task = get_object_or_404(ProductionTask, pk=pk)
    task.status = 3
    task.actual_end_time = timezone.now()
    task.completed_quantity = task.quantity
    task.qualified_quantity = task.quantity
    task.save()
    task.plan.check_auto_complete()
    messages.success(request, '任务已完成')
    return redirect('production:production_task_detail', pk=pk)


def production_task_quality(request, pk):
    """任务质量检查"""
    task = get_object_or_404(ProductionTask, pk=pk)
    if request.method == 'POST':
        form = QualityCheckForm(request.POST)
        if form.is_valid():
            check = form.save(commit=False)
            check.task = task
            check.save()
            task.qualified_quantity = check.qualified_quantity
            task.defective_quantity = check.defective_quantity
            task.completed_quantity = check.check_quantity
            task.save()
            task.update_task_status()
            messages.success(request, '质量检查已记录')
            return redirect('production:production_task_detail', pk=pk)
    else:
        form = QualityCheckForm(initial={'task': task})
    return render(request, 'production/quality/form.html',
                  {'form': form, 'task': task, 'action': '添加'})


def production_task_suspend(request, pk):
    """挂起任务"""
    task = get_object_or_404(ProductionTask, pk=pk)
    task.status = 6
    task.suspended_by = request.user
    task.suspended_time = timezone.now()
    task.suspend_reason = request.POST.get('reason', '')
    task.save()
    messages.success(request, '任务已挂起')
    return redirect('production:production_task_detail', pk=pk)


def production_task_resume(request, pk):
    """恢复任务"""
    task = get_object_or_404(ProductionTask, pk=pk)
    task.status = 2
    task.suspended_by = None
    task.suspended_time = None
    task.suspend_reason = ''
    task.save()
    messages.success(request, '任务已恢复')
    return redirect('production:production_task_detail', pk=pk)


def quality_check_list(request):
    """检查列表"""
    checks = QualityCheck.objects.select_related(
        'task', 'task__plan', 'task__procedure', 'created_by'
    ).all()
    selected_task = request.GET.get('task', '').strip()
    selected_result = request.GET.get('result', '').strip()
    if selected_task:
        checks = checks.filter(task_id=selected_task)
    if selected_result:
        checks = checks.filter(result=selected_result)
    page_obj, context = _get_paginated_queryset(
        request, checks,
        search_fields=['task__name', 'task__code', 'defect_description', 'improvement_suggestion'],
        default_order='-check_time'
    )
    summary = checks.aggregate(
        total=Count('id'),
        total_checked=Sum('check_quantity'),
        total_qualified=Sum('qualified_quantity'),
        pending_count=Count('id', filter=Q(result=3)),
        unqualified_count=Count('id', filter=Q(result=2)),
        latest_check_time=Max('check_time'),
    )
    total_checked = summary.get('total_checked') or 0
    total_qualified = summary.get('total_qualified') or 0
    avg_qualified_rate = round((float(total_qualified) / float(total_checked)) * 100, 2) if total_checked else 0
    context.update({
        'tasks': ProductionTask.objects.select_related('plan').all().order_by('name'),
        'result_choices': QualityCheck.STATUS_CHOICES,
        'selected_task': selected_task,
        'selected_result': selected_result,
        'summary': summary,
        'avg_qualified_rate': avg_qualified_rate,
    })
    return render(request, 'production/quality/list.html', context)


def quality_check_add(request):
    """添加检查"""
    return _render_model_form(
        request,
        QualityCheckForm,
        'production/quality/form.html',
        'production:quality_check_list',
        '质量检查'
    )


def quality_check_edit(request, pk):
    """编辑检查"""
    return _render_model_form(
        request,
        QualityCheckForm,
        'production/quality/form.html',
        'production:quality_check_list',
        '质量检查',
        model_class=QualityCheck,
        pk=pk
    )


def quality_check_delete(request, pk):
    """删除检查"""
    return _delete_model_object(
        request, QualityCheck, pk, 'production:quality_check_list', '质量检查')


def quality_check_detail(request, pk):
    """检查详情"""
    check = get_object_or_404(
        QualityCheck.objects.select_related('task', 'task__plan', 'task__procedure', 'created_by'),
        pk=pk)
    return render(request, 'production/quality/detail.html', {'check': check})


def data_source_list(request):
    """数据源列表"""
    sources = DataSource.objects.annotate(
        mapping_count=Count('mappings', distinct=True),
        collection_count=Count('collections', distinct=True),
    ).all()
    source_type = request.GET.get('source_type', '').strip()
    if source_type:
        sources = sources.filter(source_type=source_type)
    page_obj, context = _get_paginated_queryset(
        request, sources,
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    summary = sources.aggregate(
        total=Count('id'),
        active_count=Count('id', filter=Q(is_active=True)),
        issue_count=Count('id', filter=Q(error_count__gt=0)),
        never_collected_count=Count('id', filter=Q(last_collection_time__isnull=True)),
    )
    context['source_type'] = source_type
    context['source_types'] = DataSource.SOURCE_TYPES
    context['summary'] = summary
    return render(request, 'production/data/source_list.html', context)


def data_source_add(request):
    """添加数据源"""
    if request.method == 'POST':
        form = DataSourceForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            source = form.save(commit=False)
            _apply_request_user_defaults(source, request.user)
            source.save()
            messages.success(request, '数据源添加成功')
            return redirect('production:data_source_list')
    else:
        form = DataSourceForm()
        _style_production_form(form)
    return render(request, 'production/data/source_form.html',
                  {'form': form, 'action': '添加'})


def data_source_detail(request, pk):
    """数据源详情"""
    source = get_object_or_404(DataSource, pk=pk)
    mappings = source.mappings.all().order_by('sort', 'id')
    records = source.collections.all().order_by('-collection_time')[:20]
    active_mapping_names = {item.name for item in mappings.filter(is_active=True)}
    mapping_readiness = {
        'equipment_linked': 'equipment_id' in active_mapping_names or 'equipment_code' in active_mapping_names,
        'timestamp_linked': 'timestamp' in active_mapping_names,
        'mapping_count': mappings.filter(is_active=True).count(),
    }
    return render(request, 'production/data/source_detail.html',
                  {
                      'source': source,
                      'mappings': mappings,
                      'records': records,
                      'mapping_readiness': mapping_readiness,
                  })


def data_source_edit(request, pk):
    """编辑数据源"""
    source = get_object_or_404(DataSource, pk=pk)
    if request.method == 'POST':
        form = DataSourceForm(request.POST, instance=source)
        _style_production_form(form)
        if form.is_valid():
            source = form.save(commit=False)
            _apply_request_user_defaults(source, request.user)
            source.save()
            messages.success(request, '数据源编辑成功')
            return redirect('production:data_source_list')
    else:
        form = DataSourceForm(instance=source)
        _style_production_form(form)
    return render(request, 'production/data/source_form.html',
                  {'form': form, 'action': '编辑'})


def data_source_delete(request, pk):
    """删除数据源"""
    source = get_object_or_404(DataSource, pk=pk)
    source.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST:
        return JsonResponse({'code': 0, 'msg': '删除成功'})

    messages.success(request, '数据源删除成功')
    return redirect('production:data_source_list')


def data_source_test(request, pk):
    """测试数据源连接"""
    source = get_object_or_404(DataSource, pk=pk)
    service = DataCollectorService()
    try:
        result = service._test_connection(source)
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])
    except Exception as e:
        messages.error(request, f'连接测试失败: {str(e)}')
    return redirect('production:data_source_detail', pk=pk)


def data_source_collect(request, pk):
    """手动采集数据源"""
    source = get_object_or_404(DataSource, pk=pk)
    service = DataCollectorService()
    try:
        result = service.collect_data(source)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST:
            if result.get('success'):
                return JsonResponse({
                    'code': 0,
                    'msg': '采集成功',
                    'data': {
                        'record_count': result.get('record_count', 0),
                        'success_count': result.get('success_count', 0),
                        'error_count': result.get('error_count', 0)
                    }
                })
            else:
                return JsonResponse({
                    'code': 1,
                    'msg': f"手动采集失败：{result.get('error', '未知错误')}"
                })

        if result.get('success'):
            messages.success(
                request,
                f"手动采集成功，处理 {result.get('record_count', 0)} 条，成功 {result.get('success_count', 0)} 条，异常 {result.get('error_count', 0)} 条"
            )
        else:
            messages.error(request, f"手动采集失败：{result.get('error', '未知错误')}")
    except Exception as e:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST:
            return JsonResponse({
                'code': 1,
                'msg': f'手动采集失败: {str(e)}'
            })
        messages.error(request, f'手动采集失败: {str(e)}')
    return redirect('production:data_source_list')


def data_mapping_list(request):
    """数据映射列表"""
    mappings = DataMapping.objects.select_related('data_source').all()
    data_source_id = request.GET.get('data_source', '').strip()
    current_source = None
    if data_source_id:
        current_source = get_object_or_404(DataSource, pk=data_source_id)
        mappings = mappings.filter(data_source=current_source)
    page_obj, context = _get_paginated_queryset(
        request, mappings,
        search_fields=['name'],
        default_order='sort'
    )
    summary = mappings.aggregate(
        total=Count('id'),
        active_count=Count('id', filter=Q(is_active=True)),
        required_count=Count('id', filter=Q(is_required=True)),
        transformed_count=Count('id', filter=~Q(transform_type='none')),
    )
    context['current_source'] = current_source
    context['source_options'] = DataSource.objects.all().order_by('name')
    context['summary'] = summary
    return render(request, 'production/data/mapping_list.html', context)


def data_mapping_add(request):
    """添加数据映射"""
    if request.method == 'POST':
        form = DataMappingForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            mapping = form.save()
            messages.success(request, '数据映射添加成功')
            return redirect(f"{reverse('production:data_mapping_list')}?data_source={mapping.data_source_id}")
    else:
        form = DataMappingForm(initial={'data_source': request.GET.get('data_source')})
        _style_production_form(form)
    return render(request, 'production/data/mapping_form.html',
                  {'form': form, 'action': '添加'})


def data_mapping_edit(request, pk):
    """编辑数据映射"""
    mapping = get_object_or_404(DataMapping, pk=pk)
    if request.method == 'POST':
        form = DataMappingForm(request.POST, instance=mapping)
        _style_production_form(form)
        if form.is_valid():
            mapping = form.save()
            messages.success(request, '数据映射编辑成功')
            return redirect(f"{reverse('production:data_mapping_list')}?data_source={mapping.data_source_id}")
    else:
        form = DataMappingForm(instance=mapping)
        _style_production_form(form)
    return render(request, 'production/data/mapping_form.html',
                  {'form': form, 'action': '编辑'})


def data_mapping_delete(request, pk):
    """删除数据映射"""
    mapping = get_object_or_404(DataMapping, pk=pk)
    data_source_id = mapping.data_source_id
    mapping.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST:
        return JsonResponse({'code': 0, 'msg': '删除成功'})

    messages.success(request, '数据映射删除成功')
    return redirect(f"{reverse('production:data_mapping_list')}?data_source={data_source_id}")


@transaction.atomic
def data_mapping_update_sort(request):
    """更新数据映射排序"""
    if request.method == 'POST':
        mapping_id = request.POST.get('mapping_id')
        sort_value = request.POST.get('sort')
        if mapping_id and sort_value is not None:
            DataMapping.objects.filter(pk=mapping_id).update(sort=sort_value)
            return JsonResponse({'code': 0, 'msg': '排序更新成功'})
    return JsonResponse({'code': 1, 'msg': '参数错误'})


def data_collection_record_list(request):
    """数据采集记录列表"""
    records = DataCollectionRecord.objects.select_related('data_source').all()
    selected_status = request.GET.get('status', '').strip()
    if selected_status:
        records = records.filter(status=selected_status)
    page_obj, context = _get_paginated_queryset(
        request, records,
        search_fields=['data_source__name', 'status', 'error_message'],
        default_order='-collection_time'
    )
    summary = records.aggregate(
        total=Count('id'),
        success_count=Count('id', filter=Q(status='success')),
        partial_count=Count('id', filter=Q(status='partial')),
        failed_count=Count('id', filter=Q(status='failed')),
    )
    context.update({
        'summary': summary,
        'selected_status': selected_status,
        'status_choices': DataCollectionRecord.STATUS_CHOICES,
    })
    return render(
        request,
        'production/data_collection_record/list.html',
        context)


def data_collection_record_detail(request, pk):
    """数据采集记录详情"""
    record = get_object_or_404(DataCollectionRecord, pk=pk)
    return render(request,
                  'production/data_collection_record/detail.html',
                  {'record': record})


def data_point_list(request):
    """生产数据点列表"""
    points = ProductionDataPoint.objects.select_related(
        'equipment', 'data_source', 'task', 'procedure'
    ).all()
    selected_equipment = request.GET.get('equipment', '').strip()
    selected_source = request.GET.get('data_source', '').strip()
    if selected_equipment:
        points = points.filter(equipment_id=selected_equipment)
    if selected_source:
        points = points.filter(data_source_id=selected_source)
    page_obj, context = _get_paginated_queryset(
        request, points,
        search_fields=['metric_name', 'equipment__name', 'equipment__code'],
        default_order='-timestamp'
    )
    summary = points.aggregate(
        total=Count('id'),
        equipment_count=Count('equipment', distinct=True),
        metric_count=Count('metric_name', distinct=True),
        latest_timestamp=Max('timestamp'),
    )
    context.update({
        'summary': summary,
        'equipments': Equipment.objects.all().order_by('name'),
        'data_sources': DataSource.objects.filter(is_active=True).order_by('name'),
        'selected_equipment': selected_equipment,
        'selected_source': selected_source,
    })
    return render(request, 'production/data_point/list.html', context)


def data_collection_task_list(request):
    """数据采集任务列表"""
    tasks = DataCollectionTask.objects.prefetch_related('data_sources').all()
    selected_status = request.GET.get('status', '').strip()
    if selected_status:
        tasks = tasks.filter(status=selected_status)
    page_obj, context = _get_paginated_queryset(
        request, tasks,
        search_fields=['name'],
        default_order='-create_time'
    )
    summary = tasks.aggregate(
        total=Count('id'),
        active_count=Count('id', filter=Q(is_active=True)),
        scheduled_count=Count('id', filter=Q(task_type='scheduled')),
        completed_count=Count('id', filter=Q(status='completed')),
    )
    context.update({
        'summary': summary,
        'selected_status': selected_status,
        'status_choices': DataCollectionTask.STATUS_CHOICES,
    })
    return render(
        request,
        'production/data_collection_task/list.html',
        context)


def data_collection_task_add(request):
    """添加数据采集任务"""
    if request.method == 'POST':
        form = DataCollectionTaskForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            task = form.save(commit=False)
            _apply_request_user_defaults(task, request.user)
            task.save()
            form.save_m2m()
            messages.success(request, '数据采集任务添加成功')
            return redirect('production:data_collection_task_list')
    else:
        form = DataCollectionTaskForm()
        _style_production_form(form)
    return render(request,
                  'production/data_collection_task/form.html',
                  {'form': form,
                   'action': '添加'})


def data_collection_task_edit(request, pk):
    """编辑数据采集任务"""
    task = get_object_or_404(DataCollectionTask, pk=pk)
    if request.method == 'POST':
        form = DataCollectionTaskForm(request.POST, instance=task)
        _style_production_form(form)
        if form.is_valid():
            task = form.save(commit=False)
            _apply_request_user_defaults(task, request.user)
            task.save()
            form.save_m2m()
            messages.success(request, '数据采集任务编辑成功')
            return redirect('production:data_collection_task_list')
    else:
        form = DataCollectionTaskForm(instance=task)
        _style_production_form(form)
    return render(request,
                  'production/data_collection_task/form.html',
                  {'form': form,
                   'action': '编辑'})


def data_collection_task_delete(request, pk):
    """删除数据采集任务"""
    task = get_object_or_404(DataCollectionTask, pk=pk)
    task.delete()
    messages.success(request, '数据采集任务删除成功')
    return redirect('production:data_collection_task_list')


def data_collection_task_trigger(request, pk):
    """触发数据采集任务"""
    task = get_object_or_404(DataCollectionTask, pk=pk)
    service = DataCollectorService()
    try:
        result = service.execute_task(task)
        if result.get('success'):
            messages.success(
                request,
                f"任务执行成功，已完成 {result.get('success_count', 0)} 个数据源采集")
        else:
            messages.warning(
                request,
                f"任务已执行，但有 {result.get('failed_count', 0)} 个数据源采集失败")
    except Exception as e:
        messages.error(request, f'任务执行失败: {str(e)}')
    return redirect('production:data_collection_task_list')


def sop_copy(request, pk):
    """复制SOP"""
    sop = get_object_or_404(SOP, pk=pk)
    sop.pk = None
    sop.code = _build_copy_code(SOP, sop.code)
    sop.name = f'{sop.name}-副本'
    sop.status = True
    sop.save()
    messages.success(request, 'SOP复制成功')
    return redirect('production:sop_list')


def process_route_list(request):
    """工艺路线列表"""
    return _render_paginated_list(
        request,
        ProcessRoute.objects.select_related('product').annotate(item_count=Count('processrouteitem')).all(),
        'production/process_route/list.html',
        '工艺路线',
        search_fields=['name', 'code'],
        default_order='-create_time'
    )


def process_route_add(request):
    """添加工艺路线"""
    return _render_inline_form_page(
        request,
        ProcessRouteForm,
        ProcessRouteItemInlineFormSet,
        'production/process_route/form.html',
        'production:process_route_list',
        '工艺路线',
        after_save=_sync_process_route_metrics,
    )


def process_route_edit(request, pk):
    """编辑工艺路线"""
    return _render_inline_form_page(
        request,
        ProcessRouteForm,
        ProcessRouteItemInlineFormSet,
        'production/process_route/form.html',
        'production:process_route_list',
        '工艺路线',
        model_class=ProcessRoute,
        pk=pk,
        after_save=_sync_process_route_metrics,
    )


def process_route_delete(request, pk):
    """删除工艺路线"""
    return _delete_model_object(
        request, ProcessRoute, pk, 'production:process_route_list', '工艺路线')


def process_route_detail(request, pk):
    """工艺路线详情"""
    route = get_object_or_404(ProcessRoute, pk=pk)
    items = route.processrouteitem_set.select_related('procedure').all().order_by('sequence')
    return render(request, 'production/process_route/detail.html',
                  {'route': route, 'items': items})


def process_route_copy(request, pk):
    """复制工艺路线"""
    route = get_object_or_404(ProcessRoute, pk=pk)
    items = list(route.processrouteitem_set.all().order_by('sequence'))

    route.pk = None
    route.code = _build_copy_code(ProcessRoute, route.code)
    route.name = f'{route.name}-副本'
    route.status = 1
    route.save()

    for item in items:
        item.pk = None
        item.process_route = route
        item.save()

    messages.success(request, '工艺路线复制成功')
    return redirect('production:process_route_list')


def production_order_change_list(request):
    """生产订单变更列表"""
    changes = ProductionOrderChange.objects.select_related(
        'production_plan',
        'creator'
    ).all()
    change_type = request.GET.get('change_type', '').strip()
    if change_type:
        changes = changes.filter(change_type=change_type)
    page_obj, context = _get_paginated_queryset(
        request, changes,
        search_fields=['change_type', 'change_reason'],
        default_order='-create_time'
    )
    context['change_type'] = change_type
    return render(request, 'production/order_change/list.html', context)


def production_order_change_add(request):
    """添加生产订单变更"""
    if request.method == 'POST':
        form = ProductionOrderChangeForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            change = form.save(commit=False)
            change.creator = request.user
            change.save()
            messages.success(request, '生产订单变更添加成功')
            return redirect('production:production_order_change_list')
    else:
        form = ProductionOrderChangeForm()
        _initialize_form_with_query_data(form, request, {'production_plan': 'plan'})
        _style_production_form(form)
    return render(request, 'production/order_change/form.html',
                  {'form': form, 'action': '添加'})


def production_order_change_edit(request, pk):
    """编辑生产订单变更"""
    change = get_object_or_404(ProductionOrderChange, pk=pk)
    if request.method == 'POST':
        form = ProductionOrderChangeForm(request.POST, instance=change)
        _style_production_form(form)
        if form.is_valid():
            form.save()
            messages.success(request, '生产订单变更编辑成功')
            return redirect('production:production_order_change_list')
    else:
        form = ProductionOrderChangeForm(instance=change)
        _style_production_form(form)
    return render(request, 'production/order_change/form.html',
                  {'form': form, 'action': '编辑'})


def production_order_change_approve(request, pk):
    """审核生产订单变更"""
    change = get_object_or_404(ProductionOrderChange, pk=pk)
    change.status = 2
    change.approved_by = request.user
    change.approved_time = timezone.now()
    change.save()
    messages.success(request, '变更已审核')
    return redirect('production:production_order_change_list')


def production_order_change_execute(request, pk):
    """执行生产订单变更"""
    change = get_object_or_404(ProductionOrderChange, pk=pk)
    if change.status == 2:
        try:
            with transaction.atomic():
                _apply_order_change(change)
            messages.success(request, '变更已执行并同步到关联生产对象')
        except Exception as exc:
            messages.error(request, f'变更执行失败：{exc}')
    else:
        messages.error(request, '变更未审核，不能执行')
    return redirect('production:production_order_change_list')


def production_line_day_plan_list(request):
    """生产线日计划列表"""
    plans = ProductionLineDayPlan.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, plans,
        search_fields=['name', 'code'],
        default_order='-plan_date'
    )
    return render(request, 'production/line_day_plan/list.html', context)


def production_line_day_plan_add(request):
    """添加生产线日计划"""
    if request.method == 'POST':
        form = ProductionLineDayPlanForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            day_plan = form.save(commit=False)
            _ensure_day_plan_defaults(day_plan, request.user)
            day_plan.save()
            messages.success(request, '生产线日计划添加成功')
            return redirect('production:production_line_day_plan_list')
    else:
        form = ProductionLineDayPlanForm()
        _initialize_form_with_query_data(form, request, {'production_plan': 'plan'})
        _style_production_form(form)
    return render(request, 'production/line_day_plan/form.html',
                  {'form': form, 'action': '添加'})


def production_line_day_plan_edit(request, pk):
    """编辑生产线日计划"""
    plan = get_object_or_404(ProductionLineDayPlan, pk=pk)
    if request.method == 'POST':
        form = ProductionLineDayPlanForm(request.POST, instance=plan)
        _style_production_form(form)
        if form.is_valid():
            day_plan = form.save(commit=False)
            _ensure_day_plan_defaults(day_plan, request.user)
            day_plan.save()
            messages.success(request, '生产线日计划编辑成功')
            return redirect('production:production_line_day_plan_list')
    else:
        form = ProductionLineDayPlanForm(instance=plan)
        _style_production_form(form)
    return render(request, 'production/line_day_plan/form.html',
                  {'form': form, 'action': '编辑'})


def production_line_day_plan_delete(request, pk):
    """删除生产线日计划"""
    plan = get_object_or_404(ProductionLineDayPlan, pk=pk)
    plan.delete()
    messages.success(request, '生产线日计划删除成功')
    return redirect('production:production_line_day_plan_list')


def material_management_dashboard(request):
    """生产物料管理看板"""
    pending_requests = MaterialRequest.objects.filter(status=1).count()
    pending_issues = MaterialIssue.objects.filter(status__in=[1, 2]).count()
    pending_returns = MaterialReturn.objects.filter(status__in=[1, 2]).count()
    pending_scraps = MaterialScrap.objects.filter(status__in=[1, 2]).count()
    pending_receipts = ProductReceipt.objects.filter(status__in=[1, 2]).count()

    low_stock_items = []
    active_plans = ProductionPlan.objects.select_related('bom', 'product').filter(status__in=[1, 2, 3])[:6]
    for plan in active_plans:
        if not plan.bom_id:
            continue
        for snapshot in MaterialFlowService.build_bom_inventory_snapshot(plan.bom):
            available = snapshot['available_quantity']
            demand = snapshot['item'].quantity * plan.quantity
            if available < demand:
                low_stock_items.append({
                    'plan': plan,
                    'bom_item': snapshot['item'],
                    'inventory_item': snapshot['inventory_item'],
                    'available_quantity': available,
                    'required_quantity': demand,
                    'shortage_quantity': demand - available,
                })
    low_stock_items = low_stock_items[:8]

    context = {
        'pending_requests': pending_requests,
        'pending_issues': pending_issues,
        'pending_returns': pending_returns,
        'pending_scraps': pending_scraps,
        'pending_receipts': pending_receipts,
        'recent_requests': MaterialRequest.objects.select_related('production_plan', 'created_by').order_by('-create_time')[:5],
        'recent_issues': MaterialIssue.objects.select_related('production_plan', 'created_by').order_by('-create_time')[:5],
        'recent_returns': MaterialReturn.objects.select_related('production_plan', 'created_by').order_by('-create_time')[:5],
        'recent_scraps': MaterialScrap.objects.select_related('production_plan', 'created_by').order_by('-create_time')[:5],
        'recent_receipts': ProductReceipt.objects.select_related('production_plan', 'created_by').order_by('-create_time')[:5],
        'low_stock_items': low_stock_items,
    }
    return render(request, 'production/material/dashboard.html', context)


def material_request_list(request):
    """领料申请列表"""
    requests = MaterialRequest.objects.select_related(
        'production_plan', 'production_task', 'created_by', 'approved_by'
    ).all()
    page_obj, context = _get_paginated_queryset(
        request, requests,
        search_fields=['code'],
        default_order='-create_time'
    )
    return render(request, 'production/material_request/list.html', context)


def material_request_add(request):
    """添加领料申请"""
    if request.method == 'POST':
        form = MaterialRequestForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            material_request = form.save(commit=False)
            material_request.created_by = request.user
            MaterialFlowService.ensure_document_code(material_request, 'REQ')
            material_request.save()
            MaterialFlowService.ensure_material_request_items(material_request)
            messages.success(request, '领料申请添加成功')
            return redirect('production:material_request_list')
    else:
        form = MaterialRequestForm()
        _initialize_form_with_query_data(form, request, {'production_plan': 'plan', 'production_task': 'task'})
        _style_production_form(form)
    production_plans = ProductionPlan.objects.filter(
        status__in=[1, 2]).order_by('-create_time')
    return render(request, 'production/material_request/form.html', {
        'form': form,
        'action': '添加',
        'production_plans': production_plans
    })


def material_request_edit(request, pk):
    """编辑领料申请"""
    material_request = get_object_or_404(MaterialRequest, pk=pk)
    if request.method == 'POST':
        form = MaterialRequestForm(request.POST, instance=material_request)
        _style_production_form(form)
        if form.is_valid():
            material_request = form.save()
            MaterialFlowService.ensure_material_request_items(material_request)
            messages.success(request, '领料申请编辑成功')
            return redirect('production:material_request_list')
    else:
        form = MaterialRequestForm(instance=material_request)
        _style_production_form(form)
    production_plans = ProductionPlan.objects.filter(
        status__in=[1, 2]).order_by('-create_time')
    return render(request, 'production/material_request/form.html', {
        'form': form,
        'action': '编辑',
        'production_plans': production_plans
    })


def material_request_detail(request, pk):
    """领料申请详情"""
    material_request = get_object_or_404(
        MaterialRequest.objects.select_related('production_plan', 'production_task', 'created_by', 'approved_by'),
        pk=pk)
    MaterialFlowService.ensure_material_request_items(material_request)
    item_rows = []
    for item in material_request.items.select_related('bom_item'):
        summary = MaterialFlowService.get_inventory_summary(item.material_code, item.material_name)
        item_rows.append({
            'item': item,
            'inventory_item': summary['inventory_item'],
            'available_quantity': summary['available_quantity'],
            'total_quantity': summary['total_quantity'],
        })
    return render(request, 'production/material_request/detail.html', {
        'material_request': material_request,
        'item_rows': item_rows,
    })


def material_request_approve(request, pk):
    """审核领料申请"""
    material_request = get_object_or_404(MaterialRequest, pk=pk)
    MaterialFlowService.ensure_material_request_items(material_request)
    material_request.status = 2
    material_request.approved_by = request.user
    material_request.save()
    messages.success(request, '领料申请已审核')
    return redirect('production:material_request_list')


def material_request_cancel(request, pk):
    """取消领料申请"""
    material_request = get_object_or_404(MaterialRequest, pk=pk)
    material_request.status = 5
    material_request.save()
    messages.success(request, '领料申请已取消')
    return redirect('production:material_request_list')


def material_issue_list(request):
    """材料出库列表"""
    issues = MaterialIssue.objects.select_related(
        'material_request', 'production_plan', 'created_by', 'approved_by'
    ).all()
    page_obj, context = _get_paginated_queryset(
        request, issues,
        search_fields=['code'],
        default_order='-create_time'
    )
    return render(request, 'production/material_issue/list.html', context)


def material_issue_add(request):
    """添加材料出库"""
    if request.method == 'POST':
        form = MaterialIssueForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.created_by = request.user
            MaterialFlowService.ensure_document_code(issue, 'ISS')
            issue.save()
            MaterialFlowService.ensure_material_issue_items(issue)
            messages.success(request, '材料出库添加成功')
            return redirect('production:material_issue_list')
    else:
        form = MaterialIssueForm()
        _initialize_form_with_query_data(form, request, {'production_plan': 'plan', 'material_request': 'request'})
        _style_production_form(form)
    production_plans = ProductionPlan.objects.filter(
        status__in=[1, 2]).order_by('-create_time')
    material_requests = list(
        MaterialRequest.objects.filter(
            status=2).values(
            'pk', 'code').order_by('-create_time'))
    return render(request, 'production/material_issue/form.html', {
        'form': form,
        'action': '添加',
        'production_plans': production_plans,
        'material_requests': material_requests
    })


def material_issue_edit(request, pk):
    """编辑材料出库"""
    issue = get_object_or_404(MaterialIssue, pk=pk)
    if request.method == 'POST':
        form = MaterialIssueForm(request.POST, instance=issue)
        _style_production_form(form)
        if form.is_valid():
            issue = form.save()
            MaterialFlowService.ensure_material_issue_items(issue)
            messages.success(request, '材料出库编辑成功')
            return redirect('production:material_issue_list')
    else:
        form = MaterialIssueForm(instance=issue)
        _style_production_form(form)
    production_plans = ProductionPlan.objects.filter(
        status__in=[1, 2]).order_by('-create_time')
    material_requests = MaterialRequest.objects.filter(
        status=2).order_by('-create_time')
    return render(request, 'production/material_issue/form.html', {
        'form': form,
        'action': '编辑',
        'production_plans': production_plans,
        'material_requests': material_requests
    })


def material_issue_detail(request, pk):
    """材料出库详情"""
    issue = get_object_or_404(
        MaterialIssue.objects.select_related('material_request', 'production_plan', 'created_by', 'approved_by'),
        pk=pk)
    MaterialFlowService.ensure_material_issue_items(issue)
    item_rows = []
    for item in issue.items.select_related('material_request_item'):
        summary = MaterialFlowService.get_inventory_summary(item.material_code, item.material_name)
        item_rows.append({
            'item': item,
            'inventory_item': summary['inventory_item'],
            'available_quantity': summary['available_quantity'],
            'total_quantity': summary['total_quantity'],
        })
    return render(request, 'production/material_issue/detail.html', {
        'issue': issue,
        'item_rows': item_rows,
    })


def material_issue_approve(request, pk):
    """审核材料出库"""
    issue = get_object_or_404(MaterialIssue, pk=pk)
    MaterialFlowService.ensure_material_issue_items(issue)
    issue.status = 2
    issue.approved_by = request.user
    issue.save()
    messages.success(request, '材料出库已审核')
    return redirect('production:material_issue_list')


def material_issue_execute(request, pk):
    """执行材料出库"""
    issue = get_object_or_404(MaterialIssue, pk=pk)
    try:
        MaterialFlowService.execute_material_issue(issue, request.user)
        messages.success(request, '材料出库已执行并同步库存')
    except MaterialFlowError as exc:
        messages.error(request, str(exc))
    return redirect('production:material_issue_list')


def material_issue_cancel(request, pk):
    """取消材料出库"""
    issue = get_object_or_404(MaterialIssue, pk=pk)
    issue.status = 4
    issue.save()
    messages.success(request, '材料出库已取消')
    return redirect('production:material_issue_list')


def material_return_list(request):
    """退料列表"""
    returns = MaterialReturn.objects.select_related(
        'material_issue', 'production_plan', 'created_by', 'approved_by'
    ).all()
    page_obj, context = _get_paginated_queryset(
        request, returns,
        search_fields=['code'],
        default_order='-create_time'
    )
    return render(request, 'production/material_return/list.html', context)


def material_return_add(request):
    """添加退料"""
    if request.method == 'POST':
        form = MaterialReturnForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            material_return = form.save(commit=False)
            material_return.created_by = request.user
            MaterialFlowService.ensure_document_code(material_return, 'RET')
            material_return.save()
            MaterialFlowService.ensure_material_return_items(material_return)
            messages.success(request, '退料添加成功')
            return redirect('production:material_return_list')
    else:
        form = MaterialReturnForm()
        _initialize_form_with_query_data(form, request, {'production_plan': 'plan', 'material_issue': 'issue'})
        _style_production_form(form)
    production_plans = ProductionPlan.objects.filter(
        status__in=[1, 2]).order_by('-create_time')
    material_issues = list(
        MaterialIssue.objects.filter(
            status=3).values(
            'pk',
            'code').order_by('-create_time'))
    return render(request, 'production/material_return/form.html', {
        'form': form,
        'action': '添加',
        'production_plans': production_plans,
        'material_issues': material_issues
    })


def material_return_edit(request, pk):
    """编辑退料"""
    material_return = get_object_or_404(MaterialReturn, pk=pk)
    if request.method == 'POST':
        form = MaterialReturnForm(request.POST, instance=material_return)
        _style_production_form(form)
        if form.is_valid():
            material_return = form.save()
            MaterialFlowService.ensure_material_return_items(material_return)
            messages.success(request, '退料编辑成功')
            return redirect('production:material_return_list')
    else:
        form = MaterialReturnForm(instance=material_return)
        _style_production_form(form)
    production_plans = ProductionPlan.objects.filter(
        status__in=[1, 2]).order_by('-create_time')
    material_issues = MaterialIssue.objects.filter(
        status=3).order_by('-create_time')
    return render(request, 'production/material_return/form.html', {
        'form': form,
        'action': '编辑',
        'production_plans': production_plans,
        'material_issues': material_issues
    })


def material_return_detail(request, pk):
    """退料详情"""
    material_return = get_object_or_404(
        MaterialReturn.objects.select_related('material_issue', 'production_plan', 'created_by', 'approved_by'),
        pk=pk)
    MaterialFlowService.ensure_material_return_items(material_return)
    item_rows = list(material_return.items.select_related('material_issue_item'))
    return render(request, 'production/material_return/detail.html', {
        'material_return': material_return,
        'item_rows': item_rows,
    })


def material_return_approve(request, pk):
    """审核退料"""
    material_return = get_object_or_404(MaterialReturn, pk=pk)
    MaterialFlowService.ensure_material_return_items(material_return)
    material_return.status = 2
    material_return.approved_by = request.user
    material_return.save()
    messages.success(request, '退料已审核')
    return redirect('production:material_return_list')


def material_return_execute(request, pk):
    """执行退料入库"""
    material_return = get_object_or_404(MaterialReturn, pk=pk)
    try:
        MaterialFlowService.execute_material_return(material_return, request.user)
        messages.success(request, '退料已执行并同步库存')
    except MaterialFlowError as exc:
        messages.error(request, str(exc))
    return redirect('production:material_return_list')


def material_return_cancel(request, pk):
    """取消退料"""
    material_return = get_object_or_404(MaterialReturn, pk=pk)
    material_return.status = 4
    material_return.save()
    messages.success(request, '退料已取消')
    return redirect('production:material_return_list')


def material_scrap_list(request):
    """物料报废列表"""
    scraps = MaterialScrap.objects.select_related(
        'material_issue', 'production_plan', 'created_by', 'approved_by'
    ).all()
    page_obj, context = _get_paginated_queryset(
        request, scraps,
        search_fields=['code', 'scrap_reason'],
        default_order='-create_time'
    )
    return render(request, 'production/material_scrap/list.html', context)


def material_scrap_add(request):
    """添加物料报废"""
    if request.method == 'POST':
        form = MaterialScrapForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            material_scrap = form.save(commit=False)
            material_scrap.created_by = request.user
            MaterialFlowService.ensure_document_code(material_scrap, 'SCR')
            material_scrap.save()
            MaterialFlowService.ensure_material_scrap_items(material_scrap)
            messages.success(request, '物料报废添加成功')
            return redirect('production:material_scrap_list')
    else:
        form = MaterialScrapForm()
        _initialize_form_with_query_data(form, request, {'production_plan': 'plan', 'material_issue': 'issue'})
        _style_production_form(form)
    production_plans = ProductionPlan.objects.filter(
        status__in=[1, 2, 3]).order_by('-create_time')
    material_issues = MaterialIssue.objects.filter(
        status=3).order_by('-create_time')
    return render(request, 'production/material_scrap/form.html', {
        'form': form,
        'action': '添加',
        'production_plans': production_plans,
        'material_issues': material_issues
    })


def material_scrap_edit(request, pk):
    """编辑物料报废"""
    material_scrap = get_object_or_404(MaterialScrap, pk=pk)
    if request.method == 'POST':
        form = MaterialScrapForm(request.POST, instance=material_scrap)
        _style_production_form(form)
        if form.is_valid():
            material_scrap = form.save()
            MaterialFlowService.ensure_material_scrap_items(material_scrap)
            messages.success(request, '物料报废编辑成功')
            return redirect('production:material_scrap_list')
    else:
        form = MaterialScrapForm(instance=material_scrap)
        _style_production_form(form)
    production_plans = ProductionPlan.objects.filter(
        status__in=[1, 2, 3]).order_by('-create_time')
    material_issues = MaterialIssue.objects.filter(
        status=3).order_by('-create_time')
    return render(request, 'production/material_scrap/form.html', {
        'form': form,
        'action': '编辑',
        'production_plans': production_plans,
        'material_issues': material_issues
    })


def material_scrap_detail(request, pk):
    """物料报废详情"""
    material_scrap = get_object_or_404(
        MaterialScrap.objects.select_related('material_issue', 'production_plan', 'created_by', 'approved_by'),
        pk=pk)
    MaterialFlowService.ensure_material_scrap_items(material_scrap)
    return render(request, 'production/material_scrap/detail.html', {
        'material_scrap': material_scrap,
        'item_rows': list(material_scrap.items.select_related('material_issue_item')),
    })


def material_scrap_approve(request, pk):
    """审核物料报废"""
    material_scrap = get_object_or_404(MaterialScrap, pk=pk)
    MaterialFlowService.ensure_material_scrap_items(material_scrap)
    material_scrap.status = 2
    material_scrap.approved_by = request.user
    material_scrap.save()
    messages.success(request, '物料报废已审核')
    return redirect('production:material_scrap_list')


def material_scrap_execute(request, pk):
    """执行物料报废"""
    material_scrap = get_object_or_404(MaterialScrap, pk=pk)
    try:
        MaterialFlowService.execute_material_scrap(material_scrap, request.user)
        messages.success(request, '物料报废已执行并同步库存')
    except MaterialFlowError as exc:
        messages.error(request, str(exc))
    return redirect('production:material_scrap_list')


def material_scrap_cancel(request, pk):
    """取消物料报废"""
    material_scrap = get_object_or_404(MaterialScrap, pk=pk)
    material_scrap.status = 4
    material_scrap.save()
    messages.success(request, '物料报废已取消')
    return redirect('production:material_scrap_list')


def work_completion_report_list(request):
    """完工申报列表"""
    reports = WorkCompletionReport.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, reports,
        search_fields=['code'],
        default_order='-create_time'
    )
    return render(request, 'production/completion_report/list.html', context)


def work_completion_report_add(request):
    """添加完工申报"""
    if request.method == 'POST':
        form = WorkCompletionReportForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            report = form.save(commit=False)
            report.created_by = request.user
            MaterialFlowService.ensure_document_code(report, 'WCR')
            report.save()
            messages.success(request, '完工申报添加成功')
            return redirect('production:work_completion_report_list')
    else:
        form = WorkCompletionReportForm()
        _initialize_form_with_query_data(form, request, {'production_task': 'task'})
        _style_production_form(form)
    return render(request, 'production/completion_report/form.html',
                  {'form': form, 'action': '添加'})


def work_completion_report_edit(request, pk):
    """编辑完工申报"""
    report = get_object_or_404(WorkCompletionReport, pk=pk)
    if request.method == 'POST':
        form = WorkCompletionReportForm(request.POST, instance=report)
        _style_production_form(form)
        if form.is_valid():
            report = form.save(commit=False)
            if not report.created_by_id:
                report.created_by = request.user
            report.save()
            messages.success(request, '完工申报编辑成功')
            return redirect('production:work_completion_report_list')
    else:
        form = WorkCompletionReportForm(instance=report)
        _style_production_form(form)
    return render(request, 'production/completion_report/form.html',
                  {'form': form, 'action': '编辑'})


def work_completion_report_approve(request, pk):
    """审核完工申报"""
    report = get_object_or_404(WorkCompletionReport, pk=pk)
    with transaction.atomic():
        report.status = 2
        report.approved_by = request.user
        report.approved_time = timezone.now()
        if not report.resource_consumption:
            report.resource_consumption = _build_resource_consumption_payload(report.production_task)
        report.save()

        task = report.production_task
        task.completed_quantity = report.reported_quantity
        task.qualified_quantity = report.qualified_quantity
        task.defective_quantity = report.defective_quantity
        task.update_task_status()

        receipt = report.product_receipts.order_by('-create_time').first()
        if receipt is None and report.qualified_quantity > 0:
            receipt = ProductReceipt(
                completion_report=report,
                production_plan=task.plan,
                receipt_date=report.report_date,
                receipt_quantity=report.qualified_quantity,
                storage_location='待确认库位',
                created_by=request.user,
            )
            MaterialFlowService.ensure_product_receipt_defaults(receipt)
            receipt.save()
    messages.success(request, '完工申报已审核，并已同步任务进度与成品入库草稿')
    return redirect('production:work_completion_report_list')


def work_completion_report_red_flush(request, pk):
    """红冲完工申报"""
    report = get_object_or_404(WorkCompletionReport, pk=pk)
    if request.method == 'POST':
        form = WorkCompletionRedFlushForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            red_flush = form.save(commit=False)
            red_flush.completion_report = report
            red_flush.created_by = request.user
            red_flush.save()
            messages.success(request, '红冲申请已提交')
            return redirect('production:work_completion_report_list')
    else:
        form = WorkCompletionRedFlushForm(initial={
            'code': f'HC-{report.code}',
            'completion_report': report,
            'red_flush_quantity': report.reported_quantity
        })
        _style_production_form(form)
    return render(request,
                  'production/completion_report/red_flush_form.html',
                  {'form': form,
                   'report': report})


def work_completion_red_flush_list(request):
    """完工红冲列表"""
    red_flushes = WorkCompletionRedFlush.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, red_flushes,
        search_fields=['code', 'red_flush_reason'],
        default_order='-create_time'
    )
    return render(request, 'production/red_flush/list.html', context)


def work_completion_red_flush_add(request):
    """添加完工红冲"""
    if request.method == 'POST':
        form = WorkCompletionRedFlushForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            red_flush = form.save(commit=False)
            red_flush.created_by = request.user
            red_flush.save()
            messages.success(request, '完工红冲添加成功')
            return redirect('production:work_completion_red_flush_list')
    else:
        form = WorkCompletionRedFlushForm()
        _initialize_form_with_query_data(form, request, {'completion_report': 'report'})
        _style_production_form(form)
    return render(request, 'production/red_flush/form.html',
                  {'form': form, 'action': '添加'})


def work_completion_red_flush_approve(request, pk):
    """审核完工红冲"""
    red_flush = get_object_or_404(WorkCompletionRedFlush, pk=pk)
    red_flush.status = 2
    red_flush.approved_by = request.user
    red_flush.approved_time = timezone.now()
    red_flush.save()
    messages.success(request, '红冲已审核')
    return redirect('production:work_completion_red_flush_list')


def work_completion_red_flush_execute(request, pk):
    """执行完工红冲"""
    red_flush = get_object_or_404(WorkCompletionRedFlush, pk=pk)
    if red_flush.status == 2:
        executed_receipt_exists = red_flush.completion_report.product_receipts.filter(status=3).exists()
        if executed_receipt_exists:
            messages.error(request, '该完工申报已生成并执行成品入库，需先处理入库回退后再执行红冲')
            return redirect('production:work_completion_red_flush_list')
        with transaction.atomic():
            red_flush.status = 3
            red_flush.executed_time = timezone.now()
            red_flush.save()

            report = red_flush.completion_report
            report.status = 3
            report.save()

            task = report.production_task
            task.qualified_quantity = max(Decimal('0'), Decimal(str(task.qualified_quantity)) - Decimal(str(red_flush.red_flush_quantity)))
            task.completed_quantity = max(Decimal('0'), Decimal(str(task.completed_quantity)) - Decimal(str(red_flush.red_flush_quantity)))
            task.update_task_status()

            for receipt in report.product_receipts.filter(status__in=[1, 2]):
                receipt.receipt_quantity = max(Decimal('0'), Decimal(str(receipt.receipt_quantity)) - Decimal(str(red_flush.red_flush_quantity)))
                if receipt.receipt_quantity == 0:
                    receipt.status = 4
                    receipt.remarks = f'{receipt.remarks}\n因红冲 {red_flush.code} 自动取消。'.strip()
                    receipt.save(update_fields=['receipt_quantity', 'status', 'remarks', 'update_time'])
                else:
                    receipt.save(update_fields=['receipt_quantity', 'update_time'])

        messages.success(request, '红冲已执行，并同步回退未入库的成品入库草稿')
    else:
        messages.error(request, '红冲未审核，不能执行')
    return redirect('production:work_completion_red_flush_list')


def product_receipt_list(request):
    """成品入库列表"""
    receipts = ProductReceipt.objects.select_related(
        'completion_report', 'production_plan', 'created_by', 'approved_by'
    ).all()
    page_obj, context = _get_paginated_queryset(
        request, receipts,
        search_fields=['code'],
        default_order='-create_time'
    )
    return render(request, 'production/product_receipt/list.html', context)


def product_receipt_add(request):
    """添加成品入库"""
    if request.method == 'POST':
        form = ProductReceiptForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.created_by = request.user
            MaterialFlowService.ensure_product_receipt_defaults(receipt)
            receipt.save()
            messages.success(request, '成品入库添加成功')
            return redirect('production:product_receipt_list')
    else:
        form = ProductReceiptForm()
        _initialize_form_with_query_data(form, request, {'completion_report': 'report', 'production_plan': 'plan'})
        _style_production_form(form)
    return render(request, 'production/product_receipt/form.html',
                  {'form': form, 'action': '添加'})


def product_receipt_edit(request, pk):
    """编辑成品入库"""
    receipt = get_object_or_404(ProductReceipt, pk=pk)
    if request.method == 'POST':
        form = ProductReceiptForm(request.POST, instance=receipt)
        _style_production_form(form)
        if form.is_valid():
            receipt = form.save(commit=False)
            MaterialFlowService.ensure_product_receipt_defaults(receipt)
            receipt.save()
            messages.success(request, '成品入库编辑成功')
            return redirect('production:product_receipt_list')
    else:
        form = ProductReceiptForm(instance=receipt)
        _style_production_form(form)
    return render(request, 'production/product_receipt/form.html',
                  {'form': form, 'action': '编辑'})


def product_receipt_detail(request, pk):
    """成品入库详情"""
    receipt = get_object_or_404(
        ProductReceipt.objects.select_related('completion_report', 'production_plan__product', 'created_by', 'approved_by'),
        pk=pk)
    product = receipt.production_plan.product if receipt.production_plan_id else None
    inventory_summary = None
    if product:
        inventory_summary = MaterialFlowService.get_inventory_summary(product.code, product.name)
    return render(request, 'production/product_receipt/detail.html', {
        'receipt': receipt,
        'inventory_summary': inventory_summary,
    })


def product_receipt_approve(request, pk):
    """审核成品入库"""
    receipt = get_object_or_404(ProductReceipt, pk=pk)
    receipt.status = 2
    receipt.approved_by = request.user
    receipt.save()
    messages.success(request, '成品入库已审核')
    return redirect('production:product_receipt_list')


def product_receipt_execute(request, pk):
    """执行成品入库"""
    receipt = get_object_or_404(ProductReceipt, pk=pk)
    try:
        MaterialFlowService.execute_product_receipt(receipt, request.user)
        messages.success(request, '成品入库已执行并同步库存')
    except MaterialFlowError as exc:
        messages.error(request, str(exc))
    return redirect('production:product_receipt_list')


def product_receipt_cancel(request, pk):
    """取消成品入库"""
    receipt = get_object_or_404(ProductReceipt, pk=pk)
    receipt.status = 4
    receipt.save()
    messages.success(request, '成品入库已取消')
    return redirect('production:product_receipt_list')


def order_material_confirmation_list(request):
    """材料确认列表"""
    confirmations = OrderMaterialConfirmation.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, confirmations,
        search_fields=[],
        default_order='-confirm_time'
    )
    return render(request, 'production/order_confirmation/list.html', context)


def order_material_confirmation_add(request):
    """添加材料确认"""
    if request.method == 'POST':
        form = OrderMaterialConfirmationForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            confirmation = form.save(commit=False)
            confirmation.confirmed_by = request.user
            confirmation.save()
            messages.success(request, '材料确认添加成功')
            return redirect('production:order_material_confirmation_list')
    else:
        form = OrderMaterialConfirmationForm()
        _initialize_form_with_query_data(form, request, {'production_plan': 'plan', 'material_issue': 'issue'})
        _style_production_form(form)
    return render(request, 'production/order_confirmation/form.html',
                  {'form': form, 'action': '添加'})


def resource_consumption_list(request):
    """资源消耗列表"""
    consumptions = ResourceConsumption.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, consumptions,
        search_fields=['resource_name'],
        default_order='-consumption_time'
    )
    return render(
        request,
        'production/resource_consumption/list.html',
        context)


def resource_consumption_add(request):
    """添加资源消耗"""
    if request.method == 'POST':
        form = ResourceConsumptionForm(request.POST)
        _style_production_form(form)
        if form.is_valid():
            consumption = form.save(commit=False)
            consumption.created_by = request.user
            consumption.save()
            messages.success(request, '资源消耗添加成功')
            return redirect('production:resource_consumption_list')
    else:
        form = ResourceConsumptionForm()
        _initialize_form_with_query_data(form, request, {'production_task': 'task'})
        _style_production_form(form)
    return render(request,
                  'production/resource_consumption/form.html',
                  {'form': form,
                   'action': '添加'})


def resource_scheduling(request):
    """智能资源调度页面"""
    SchedulingOptimizerService()
    today = timezone.now().date()

    equipment_usage = []
    for equipment in Equipment.objects.filter(status=1).all():
        tasks = ProductionTask.objects.filter(
            equipment=equipment,
            status__in=[1, 2]
        ).order_by('plan_start_time')[:5]

        equipment_usage.append({'equipment': equipment, 'task_count': ProductionTask.objects.filter(
            equipment=equipment, status__in=[1, 2]).count(), 'current_tasks': list(tasks)})

    user_workload = []
    users = Admin.objects.filter(is_active=True)[:10]
    for user in users:
        active_tasks = ProductionTask.objects.filter(
            assignee=user,
            status=2
        ).count()

        user_workload.append({
            'user': user,
            'active_tasks': active_tasks
        })

    context = {
        'equipment_usage': equipment_usage,
        'user_workload': user_workload,
        'strategies': [
            ('hybrid', '综合优化'),
            ('priority', '优先级优先'),
            ('equipment', '设备均衡'),
        ],
        'default_start_date': today,
        'default_end_date': today + timedelta(days=14),
        'plan_options': ProductionPlan.objects.filter(status__in=[1, 2, 3]).order_by('-plan_start_date')[:20],
    }
    return render(request, 'production/scheduling/index.html', context)


def scheduling_optimize(request):
    """执行智能排程优化"""
    if request.method == 'POST':
        try:
            strategy = request.POST.get('strategy', 'hybrid')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')

            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
            else:
                start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
            else:
                end_date = start_date + timedelta(days=30)

            service = SchedulingOptimizerService()
            result = service.optimize_schedule(
                start_date=start_date,
                end_date=end_date,
                strategy=strategy
            )

            return JsonResponse({
                'success': True,
                'message': result.message,
                'scheduled_count': len(result.scheduled_tasks),
                'unscheduled_count': len(result.unscheduled_tasks),
                'optimization_score': result.optimization_score,
                'execution_time': result.execution_time,
                'gantt_data': GanttChartService().generate_gantt_data(result.scheduled_tasks)
            })
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"排程优化失败: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'排程优化失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '仅支持POST请求'})


def scheduling_bottleneck_analysis(request):
    """瓶颈分析"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date()

        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = start_date + timedelta(days=30)

        service = SchedulingOptimizerService()
        analysis = service.calculate_bottleneck_analysis(start_date, end_date)

        return JsonResponse({
            'success': True,
            'analysis': analysis
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


def scheduling_simulation(request, plan_id):
    """排程模拟"""
    try:
        plan = get_object_or_404(ProductionPlan, pk=plan_id)

        service = SchedulingOptimizerService()
        simulation = service.simulate_schedule(plan)

        return JsonResponse({
            'success': True,
            'simulation': simulation
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


def gantt_chart_data(request):
    """获取甘特图数据"""
    try:
        service = SchedulingOptimizerService()

        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        else:
            end_date = start_date + timedelta(days=30)

        result = service.optimize_schedule(
            start_date=start_date,
            end_date=end_date,
            strategy='hybrid'
        )

        gantt_data = GanttChartService().generate_gantt_data(result.scheduled_tasks)

        return JsonResponse({
            'success': True,
            'gantt_data': gantt_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


def delivery_prediction(request, plan_id=None):
    """交期达成率预测"""
    try:
        if plan_id:
            plan = get_object_or_404(ProductionPlan, pk=plan_id)
            service = DeliveryPredictionService()
            prediction = service.predict_delivery_rate(plan)
            return JsonResponse({'success': True, 'prediction': prediction})

        plans = ProductionPlan.objects.filter(status__in=[2, 3])
        predictions = []
        service = DeliveryPredictionService()

        for plan in plans:
            prediction = service.predict_delivery_rate(plan)
            predictions.append(prediction)

        return JsonResponse({
            'success': True,
            'predictions': predictions
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


def equipment_monitor_realtime(request):
    """实时设备监控页面"""
    context = _build_equipment_monitor_context()
    return render(request, 'production/monitor/index.html', context)


def equipment_status_api(request, equipment_id):
    """获取设备实时状态API"""
    try:
        service = EquipmentMonitorService()
        status = service.get_equipment_status(equipment_id)
        return JsonResponse({'success': True, 'status': status})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def equipment_data_history(request, equipment_id):
    """获取设备历史数据"""
    try:
        service = EquipmentMonitorService()

        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        metric_name = request.GET.get('metric_name')
        limit = int(request.GET.get('limit', 500))

        if start_time:
            start_time = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S')
        if end_time:
            end_time = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S')

        history = service.get_equipment_data_history(
            equipment_id,
            start_time=start_time,
            end_time=end_time,
            metric_name=metric_name,
            limit=limit
        )

        return JsonResponse({'success': True, 'history': history})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def equipment_oee(request, equipment_id):
    """获取设备OEE"""
    try:
        service = EquipmentMonitorService()

        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        oee = service.calculate_equipment_oee(
            equipment_id,
            start_date=start_date,
            end_date=end_date
        )

        return JsonResponse({'success': True, 'oee': oee})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def production_progress(request, plan_id=None, task_id=None):
    """获取生产进度"""
    try:
        service = EquipmentMonitorService()
        progress = service.get_production_progress(
            plan_id=plan_id, task_id=task_id)
        return JsonResponse({'success': True, 'progress': progress})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def alert_list(request):
    """告警列表页面"""
    return render(request, 'production/alert/list.html')


def alert_api(request):
    """获取告警API"""
    try:
        equipment_id = request.GET.get('equipment_id')
        severity = request.GET.get('severity', '').strip()
        time_range = request.GET.get('time_range', '').strip()

        service = AlertRuleService()
        alerts = service.get_all_alerts(limit=50)

        if equipment_id:
            alerts = [a for a in alerts if a.get(
                'equipment_id') == int(equipment_id)]
        if severity:
            alerts = [a for a in alerts if a.get('severity') == severity]
        if time_range in {'today', 'week', 'month'}:
            now = timezone.now()
            if time_range == 'today':
                cutoff = now - timedelta(days=1)
            elif time_range == 'week':
                cutoff = now - timedelta(days=7)
            else:
                cutoff = now - timedelta(days=30)
            filtered_alerts = []
            for alert in alerts:
                timestamp = alert.get('timestamp')
                if not timestamp:
                    continue
                try:
                    alert_time = datetime.fromisoformat(timestamp)
                    if timezone.is_aware(cutoff) and timezone.is_naive(alert_time):
                        alert_time = timezone.make_aware(alert_time, timezone.get_current_timezone())
                    elif timezone.is_naive(cutoff) and timezone.is_aware(alert_time):
                        alert_time = timezone.make_naive(alert_time, timezone.get_current_timezone())
                except ValueError:
                    continue
                if alert_time >= cutoff:
                    filtered_alerts.append(alert)
            alerts = filtered_alerts

        return JsonResponse({'success': True, 'alerts': alerts})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def alert_acknowledge(request, alert_id):
    """确认告警"""
    try:
        service = AlertRuleService()
        service.acknowledge_alert(alert_id, request.user.id)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def performance_analysis(request):
    """性能分析页面"""
    service = ProductionStatisticsService()

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = timezone.now().date() - timedelta(days=30)

    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = timezone.now().date()

    summary = service.get_production_summary(start_date, end_date)
    equipment_stats = service.get_equipment_efficiency(start_date, end_date)

    context = {
        'summary': summary,
        'equipment_stats': equipment_stats,
        'start_date': start_date,
        'end_date': end_date
    }
    return render(request, 'production/analysis/index.html', context)


def statistics_production_summary(request):
    """生产统计概览API"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        department_id = request.GET.get('department_id')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        service = ProductionStatisticsService()
        summary = service.get_production_summary(
            start_date=start_date,
            end_date=end_date,
            department_id=department_id
        )

        return JsonResponse({'success': True, 'summary': summary})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def statistics_production_trend(request):
    """生产趋势API"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        granularity = request.GET.get('granularity', 'day')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        service = ProductionStatisticsService()
        trend = service.get_production_trend(
            start_date=start_date,
            end_date=end_date,
            granularity=granularity
        )

        return JsonResponse({'success': True, 'trend': trend})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def statistics_quality(request):
    """质量统计API"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        service = ProductionStatisticsService()
        quality = service.get_quality_statistics(
            start_date=start_date,
            end_date=end_date
        )

        return JsonResponse({'success': True, 'quality': quality})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def statistics_equipment_efficiency(request):
    """设备效率API"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        service = ProductionStatisticsService()
        efficiency = service.get_equipment_efficiency(
            start_date=start_date,
            end_date=end_date
        )

        return JsonResponse({'success': True, 'efficiency': efficiency})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def statistics_labor_efficiency(request):
    """人员效率API"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        service = ProductionStatisticsService()
        efficiency = service.get_labor_efficiency(
            start_date=start_date,
            end_date=end_date
        )

        return JsonResponse({'success': True, 'efficiency': efficiency})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def statistics_cost(request):
    """成本分析API"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        service = ProductionStatisticsService()
        cost = service.get_cost_analysis(
            start_date=start_date,
            end_date=end_date
        )

        return JsonResponse({'success': True, 'cost': cost})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def statistics_on_time_delivery(request):
    """准时交货率API"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        service = ProductionStatisticsService()
        delivery = service.get_on_time_delivery_rate(
            start_date=start_date,
            end_date=end_date
        )

        return JsonResponse({'success': True, 'delivery': delivery})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def statistics_comprehensive_report(request):
    """综合分析报告API"""
    try:
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        service = ProductionStatisticsService()
        report = service.generate_comprehensive_report(
            start_date=start_date,
            end_date=end_date
        )

        return JsonResponse({'success': True, 'report': report})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
