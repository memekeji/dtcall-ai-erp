from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import (
    ProductionProcedure, ProcedureSet, ProcedureSetItem, BOM, BOMItem,
    Equipment, ProductionPlan, ProductionTask, QualityCheck, 
    DataCollection, DataSource, DataCollectionRecord, SOP,
    DataMapping, ProductionDataPoint, DataCollectionTask,
    ProductionOrderChange, ProductionLineDayPlan,
    MaterialRequest, MaterialRequestItem, MaterialIssue, MaterialIssueItem,
    MaterialReturn, MaterialReturnItem, WorkCompletionReport,
    WorkCompletionRedFlush, ProductReceipt, OrderMaterialConfirmation,
    ResourceConsumption, ProcessRoute, ProcessRouteItem
)
from .forms import (
    ProductionProcedureForm, ProcedureSetForm, BOMForm, BOMItemForm,
    EquipmentForm, ProductionPlanForm, ProductionTaskForm, QualityCheckForm,
    DataCollectionForm, DataSourceForm, DataMappingForm, DataCollectionRecordForm,
    SOPForm, ProcessRouteForm, ProcessRouteItemForm,
    ProductionOrderChangeForm, ProductionLineDayPlanForm,
    MaterialRequestForm, MaterialRequestItemForm, MaterialIssueForm, MaterialIssueItemForm,
    MaterialReturnForm, MaterialReturnItemForm, WorkCompletionReportForm,
    WorkCompletionRedFlushForm, ProductReceiptForm, OrderMaterialConfirmationForm,
    ResourceConsumptionForm, DataCollectionTaskForm, ProductionDataPointForm
)
from .services.data_collector import DataCollectorService


def _get_paginated_queryset(request, queryset, search_fields=None, default_order='-create_time'):
    """通用的分页查询辅助函数"""
    search = request.GET.get('search', '').strip()
    order = request.GET.get('order', default_order)
    
    if search and search_fields:
        query = Q()
        for field in search_fields:
            query |= Q(**{f'{field}__icontains': search})
        queryset = queryset.filter(query)
    
    paginator = Paginator(queryset.order_by(order), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'order': order,
    }
    return page_obj, context


def baseinfo_index(request):
    """基础信息首页"""
    context = {
        'procedure_count': ProductionProcedure.objects.count(),
        'procedureset_count': ProcedureSet.objects.count(),
        'bom_count': BOM.objects.count(),
        'equipment_count': Equipment.objects.count(),
    }
    return render(request, 'production/baseinfo/index.html', context)


def procedure_list(request):
    """基本工序列表"""
    procedures = ProductionProcedure.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, procedures, 
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    context['model_name'] = '基本工序'
    return render(request, 'production/procedure/list.html', context)


def procedure_add(request):
    """添加工序"""
    if request.method == 'POST':
        form = ProductionProcedureForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '工序添加成功')
            return redirect('production:procedure_list')
    else:
        form = ProductionProcedureForm()
    return render(request, 'production/procedure/form.html', {'form': form, 'action': '添加'})


def procedure_edit(request, pk):
    """编辑工序"""
    procedure = get_object_or_404(ProductionProcedure, pk=pk)
    if request.method == 'POST':
        form = ProductionProcedureForm(request.POST, instance=procedure)
        if form.is_valid():
            form.save()
            messages.success(request, '工序编辑成功')
            return redirect('production:procedure_list')
    else:
        form = ProductionProcedureForm(instance=procedure)
    return render(request, 'production/procedure/form.html', {'form': form, 'action': '编辑'})


def procedure_delete(request, pk):
    """删除工序"""
    procedure = get_object_or_404(ProductionProcedure, pk=pk)
    procedure.delete()
    messages.success(request, '工序删除成功')
    return redirect('production:procedure_list')


def procedureset_list(request):
    """工序集列表"""
    proceduresets = ProcedureSet.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, proceduresets,
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    context['model_name'] = '工序集'
    return render(request, 'production/procedureset/list.html', context)


def procedureset_add(request):
    """添加工序集"""
    if request.method == 'POST':
        form = ProcedureSetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '工序集添加成功')
            return redirect('production:procedureset_list')
    else:
        form = ProcedureSetForm()
    return render(request, 'production/procedureset/form.html', {'form': form, 'action': '添加'})


def procedureset_edit(request, pk):
    """编辑工序集"""
    procedureset = get_object_or_404(ProcedureSet, pk=pk)
    if request.method == 'POST':
        form = ProcedureSetForm(request.POST, instance=procedureset)
        if form.is_valid():
            form.save()
            messages.success(request, '工序集编辑成功')
            return redirect('production:procedureset_list')
    else:
        form = ProcedureSetForm(instance=procedureset)
    return render(request, 'production/procedureset/form.html', {'form': form, 'action': '编辑'})


def procedureset_delete(request, pk):
    """删除工序集"""
    procedureset = get_object_or_404(ProcedureSet, pk=pk)
    procedureset.delete()
    messages.success(request, '工序集删除成功')
    return redirect('production:procedureset_list')


def bom_list(request):
    """BOM列表"""
    boms = BOM.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, boms,
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    context['model_name'] = 'BOM'
    return render(request, 'production/bom/list.html', context)


def bom_add(request):
    """添加BOM"""
    if request.method == 'POST':
        form = BOMForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'BOM添加成功')
            return redirect('production:bom_list')
    else:
        form = BOMForm()
    return render(request, 'production/bom/form.html', {'form': form, 'action': '添加'})


def bom_edit(request, pk):
    """编辑BOM"""
    bom = get_object_or_404(BOM, pk=pk)
    if request.method == 'POST':
        form = BOMForm(request.POST, instance=bom)
        if form.is_valid():
            form.save()
            messages.success(request, 'BOM编辑成功')
            return redirect('production:bom_list')
    else:
        form = BOMForm(instance=bom)
    return render(request, 'production/bom/form.html', {'form': form, 'action': '编辑'})


def bom_delete(request, pk):
    """删除BOM"""
    bom = get_object_or_404(BOM, pk=pk)
    bom.delete()
    messages.success(request, 'BOM删除成功')
    return redirect('production:bom_list')


def bom_detail(request, pk):
    """BOM详情"""
    bom = get_object_or_404(BOM, pk=pk)
    items = bom.items.all()
    return render(request, 'production/bom/detail.html', {'bom': bom, 'items': items})


def equipment_list(request):
    """设备列表"""
    equipment_list = Equipment.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, equipment_list,
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    context['model_name'] = '设备'
    return render(request, 'production/equipment/list.html', context)


def equipment_add(request):
    """添加设备"""
    if request.method == 'POST':
        form = EquipmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '设备添加成功')
            return redirect('production:equipment_list')
    else:
        form = EquipmentForm()
    return render(request, 'production/equipment/form.html', {'form': form, 'action': '添加'})


def equipment_edit(request, pk):
    """编辑设备"""
    equipment = get_object_or_404(Equipment, pk=pk)
    if request.method == 'POST':
        form = EquipmentForm(request.POST, instance=equipment)
        if form.is_valid():
            form.save()
            messages.success(request, '设备编辑成功')
            return redirect('production:equipment_list')
    else:
        form = EquipmentForm(instance=equipment)
    return render(request, 'production/equipment/form.html', {'form': form, 'action': '编辑'})


def equipment_delete(request, pk):
    """删除设备"""
    equipment = get_object_or_404(Equipment, pk=pk)
    equipment.delete()
    messages.success(request, '设备删除成功')
    return redirect('production:equipment_list')


def equipment_detail(request, pk):
    """设备详情"""
    equipment = get_object_or_404(Equipment, pk=pk)
    data_points = equipment.data_points.all()[:100]
    return render(request, 'production/equipment/detail.html', {'equipment': equipment, 'data_points': data_points})


def equipment_monitor(request):
    """设备监控"""
    equipment = Equipment.objects.filter(status=1).all()
    return render(request, 'production/monitor/index.html', {'equipment': equipment})


def data_collection_list(request):
    """数据采集列表"""
    collections = DataCollection.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, collections,
        search_fields=['parameter_name'],
        default_order='-collect_time'
    )
    return render(request, 'production/data/list.html', context)


def data_collection_add(request):
    """添加数据采集"""
    if request.method == 'POST':
        form = DataCollectionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '数据采集添加成功')
            return redirect('production:data_collection_list')
    else:
        form = DataCollectionForm()
    return render(request, 'production/data/form.html', {'form': form, 'action': '添加'})


def data_chart(request, equipment_id):
    """数据图表"""
    equipment = get_object_or_404(Equipment, pk=equipment_id)
    data_points = ProductionDataPoint.objects.filter(equipment=equipment).order_by('-timestamp')[:100]
    return render(request, 'production/data/chart.html', {'equipment': equipment, 'data_points': data_points})


def performance_analysis(request):
    """性能分析"""
    return render(request, 'production/analysis/index.html')


def sop_list(request):
    """SOP列表"""
    sops = SOP.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, sops,
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    context['model_name'] = 'SOP'
    return render(request, 'production/sop/list.html', context)


def sop_add(request):
    """添加SOP"""
    if request.method == 'POST':
        form = SOPForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'SOP添加成功')
            return redirect('production:sop_list')
    else:
        form = SOPForm()
    return render(request, 'production/sop/form.html', {'form': form, 'action': '添加'})


def sop_edit(request, pk):
    """编辑SOP"""
    sop = get_object_or_404(SOP, pk=pk)
    if request.method == 'POST':
        form = SOPForm(request.POST, instance=sop)
        if form.is_valid():
            form.save()
            messages.success(request, 'SOP编辑成功')
            return redirect('production:sop_list')
    else:
        form = SOPForm(instance=sop)
    return render(request, 'production/sop/form.html', {'form': form, 'action': '编辑'})


def sop_delete(request, pk):
    """删除SOP"""
    sop = get_object_or_404(SOP, pk=pk)
    sop.delete()
    messages.success(request, 'SOP删除成功')
    return redirect('production:sop_list')


def sop_detail(request, pk):
    """SOP详情"""
    sop = get_object_or_404(SOP, pk=pk)
    return render(request, 'production/sop/detail.html', {'sop': sop})


def production_task_index(request):
    """生产管理首页"""
    context = {
        'plan_count': ProductionPlan.objects.count(),
        'task_count': ProductionTask.objects.count(),
        'completed_task_count': ProductionTask.objects.filter(status=3).count(),
        'pending_task_count': ProductionTask.objects.filter(status__in=[1, 2]).count(),
    }
    return render(request, 'production/task/index.html', context)


def production_plan_list(request):
    """计划列表"""
    plans = ProductionPlan.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, plans,
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    context['model_name'] = '生产计划'
    return render(request, 'production/plan/list.html', context)


def production_plan_add(request):
    """添加计划"""
    if request.method == 'POST':
        form = ProductionPlanForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '生产计划添加成功')
            return redirect('production:production_plan_list')
    else:
        form = ProductionPlanForm()
    return render(request, 'production/plan/form.html', {'form': form, 'action': '添加'})


def production_plan_edit(request, pk):
    """编辑计划"""
    plan = get_object_or_404(ProductionPlan, pk=pk)
    if request.method == 'POST':
        form = ProductionPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, '生产计划编辑成功')
            return redirect('production:production_plan_list')
    else:
        form = ProductionPlanForm(instance=plan)
    return render(request, 'production/plan/form.html', {'form': form, 'action': '编辑'})


def production_plan_delete(request, pk):
    """删除计划"""
    plan = get_object_or_404(ProductionPlan, pk=pk)
    plan.delete()
    messages.success(request, '生产计划删除成功')
    return redirect('production:production_plan_list')


def production_plan_detail(request, pk):
    """计划详情"""
    plan = get_object_or_404(ProductionPlan, pk=pk)
    tasks = plan.tasks.all()
    return render(request, 'production/plan/detail.html', {'plan': plan, 'tasks': tasks})


def production_task_list(request):
    """任务列表"""
    tasks = ProductionTask.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, tasks,
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    context['model_name'] = '生产任务'
    return render(request, 'production/task_execution/list.html', context)


def production_task_add(request):
    """添加任务"""
    if request.method == 'POST':
        form = ProductionTaskForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '生产任务添加成功')
            return redirect('production:production_task_list')
    else:
        form = ProductionTaskForm()
    return render(request, 'production/task_execution/form.html', {'form': form, 'action': '添加'})


def production_task_edit(request, pk):
    """编辑任务"""
    task = get_object_or_404(ProductionTask, pk=pk)
    if request.method == 'POST':
        form = ProductionTaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, '生产任务编辑成功')
            return redirect('production:production_task_list')
    else:
        form = ProductionTaskForm(instance=task)
    return render(request, 'production/task_execution/form.html', {'form': form, 'action': '编辑'})


def production_task_delete(request, pk):
    """删除任务"""
    task = get_object_or_404(ProductionTask, pk=pk)
    task.delete()
    messages.success(request, '生产任务删除成功')
    return redirect('production:production_task_list')


def production_task_detail(request, pk):
    """任务详情"""
    task = get_object_or_404(ProductionTask, pk=pk)
    quality_checks = task.quality_checks.all()
    data_collections = task.data_collections.all()
    return render(request, 'production/task_execution/detail.html', {
        'task': task, 
        'quality_checks': quality_checks,
        'data_collections': data_collections
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
    return render(request, 'production/quality/form.html', {'form': form, 'task': task, 'action': '添加'})


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
    checks = QualityCheck.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, checks,
        search_fields=[],
        default_order='-check_time'
    )
    return render(request, 'production/quality/list.html', context)


def quality_check_add(request):
    """添加检查"""
    if request.method == 'POST':
        form = QualityCheckForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '质量检查添加成功')
            return redirect('production:quality_check_list')
    else:
        form = QualityCheckForm()
    return render(request, 'production/quality/form.html', {'form': form, 'action': '添加'})


def quality_check_edit(request, pk):
    """编辑检查"""
    check = get_object_or_404(QualityCheck, pk=pk)
    if request.method == 'POST':
        form = QualityCheckForm(request.POST, instance=check)
        if form.is_valid():
            form.save()
            messages.success(request, '质量检查编辑成功')
            return redirect('production:quality_check_list')
    else:
        form = QualityCheckForm(instance=check)
    return render(request, 'production/quality/form.html', {'form': form, 'action': '编辑'})


def quality_check_delete(request, pk):
    """删除检查"""
    check = get_object_or_404(QualityCheck, pk=pk)
    check.delete()
    messages.success(request, '质量检查删除成功')
    return redirect('production:quality_check_list')


def quality_check_detail(request, pk):
    """检查详情"""
    check = get_object_or_404(QualityCheck, pk=pk)
    return render(request, 'production/quality/detail.html', {'check': check})


def resource_scheduling(request):
    """资源调度"""
    return render(request, 'production/scheduling/index.html')


def data_source_list(request):
    """数据源列表"""
    sources = DataSource.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, sources,
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    return render(request, 'production/data/source_list.html', context)


def data_source_add(request):
    """添加数据源"""
    if request.method == 'POST':
        form = DataSourceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '数据源添加成功')
            return redirect('production:data_source_list')
    else:
        form = DataSourceForm()
    return render(request, 'production/data/source_form.html', {'form': form, 'action': '添加'})


def data_source_detail(request, pk):
    """数据源详情"""
    source = get_object_or_404(DataSource, pk=pk)
    mappings = source.mappings.all()
    records = source.collections.all()[:20]
    return render(request, 'production/data/source_detail.html', {'source': source, 'mappings': mappings, 'records': records})


def data_source_edit(request, pk):
    """编辑数据源"""
    source = get_object_or_404(DataSource, pk=pk)
    if request.method == 'POST':
        form = DataSourceForm(request.POST, instance=source)
        if form.is_valid():
            form.save()
            messages.success(request, '数据源编辑成功')
            return redirect('production:data_source_list')
    else:
        form = DataSourceForm(instance=source)
    return render(request, 'production/data/source_form.html', {'form': form, 'action': '编辑'})


def data_source_delete(request, pk):
    """删除数据源"""
    source = get_object_or_404(DataSource, pk=pk)
    source.delete()
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


def data_mapping_list(request):
    """数据映射列表"""
    mappings = DataMapping.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, mappings,
        search_fields=['name'],
        default_order='sort'
    )
    return render(request, 'production/data/mapping_list.html', context)


def data_mapping_add(request):
    """添加数据映射"""
    if request.method == 'POST':
        form = DataMappingForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '数据映射添加成功')
            return redirect('production:data_mapping_list')
    else:
        form = DataMappingForm()
    return render(request, 'production/data/mapping_form.html', {'form': form, 'action': '添加'})


def data_mapping_edit(request, pk):
    """编辑数据映射"""
    mapping = get_object_or_404(DataMapping, pk=pk)
    if request.method == 'POST':
        form = DataMappingForm(request.POST, instance=mapping)
        if form.is_valid():
            form.save()
            messages.success(request, '数据映射编辑成功')
            return redirect('production:data_mapping_list')
    else:
        form = DataMappingForm(instance=mapping)
    return render(request, 'production/data/mapping_form.html', {'form': form, 'action': '编辑'})


def data_mapping_delete(request, pk):
    """删除数据映射"""
    mapping = get_object_or_404(DataMapping, pk=pk)
    mapping.delete()
    messages.success(request, '数据映射删除成功')
    return redirect('production:data_mapping_list')


def data_collection_record_list(request):
    """数据采集记录列表"""
    records = DataCollectionRecord.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, records,
        search_fields=[],
        default_order='-collection_time'
    )
    return render(request, 'production/data_collection_record/list.html', context)


def data_collection_record_detail(request, pk):
    """数据采集记录详情"""
    record = get_object_or_404(DataCollectionRecord, pk=pk)
    return render(request, 'production/data_collection_record/detail.html', {'record': record})


def data_point_list(request):
    """生产数据点列表"""
    points = ProductionDataPoint.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, points,
        search_fields=['metric_name'],
        default_order='-timestamp'
    )
    return render(request, 'production/data_point/list.html', context)


def data_collection_task_list(request):
    """数据采集任务列表"""
    tasks = DataCollectionTask.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, tasks,
        search_fields=['name'],
        default_order='-create_time'
    )
    return render(request, 'production/data_collection_task/list.html', context)


def data_collection_task_add(request):
    """添加数据采集任务"""
    if request.method == 'POST':
        form = DataCollectionTaskForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '数据采集任务添加成功')
            return redirect('production:data_collection_task_list')
    else:
        form = DataCollectionTaskForm()
    return render(request, 'production/data_collection_task/form.html', {'form': form, 'action': '添加'})


def data_collection_task_edit(request, pk):
    """编辑数据采集任务"""
    task = get_object_or_404(DataCollectionTask, pk=pk)
    if request.method == 'POST':
        form = DataCollectionTaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, '数据采集任务编辑成功')
            return redirect('production:data_collection_task_list')
    else:
        form = DataCollectionTaskForm(instance=task)
    return render(request, 'production/data_collection_task/form.html', {'form': form, 'action': '编辑'})


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
        service.execute_task(task)
        messages.success(request, '任务执行成功')
    except Exception as e:
        messages.error(request, f'任务执行失败: {str(e)}')
    return redirect('production:data_collection_task_list')


def process_route_list(request):
    """工艺路线列表"""
    routes = ProcessRoute.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, routes,
        search_fields=['name', 'code'],
        default_order='-create_time'
    )
    return render(request, 'production/process_route/list.html', context)


def process_route_add(request):
    """添加工艺路线"""
    if request.method == 'POST':
        form = ProcessRouteForm(request.POST)
        if form.is_valid():
            route = form.save()
            messages.success(request, '工艺路线添加成功')
            return redirect('production:process_route_list')
    else:
        form = ProcessRouteForm()
    return render(request, 'production/process_route/form.html', {'form': form, 'action': '添加'})


def process_route_edit(request, pk):
    """编辑工艺路线"""
    route = get_object_or_404(ProcessRoute, pk=pk)
    if request.method == 'POST':
        form = ProcessRouteForm(request.POST, instance=route)
        if form.is_valid():
            form.save()
            messages.success(request, '工艺路线编辑成功')
            return redirect('production:process_route_list')
    else:
        form = ProcessRouteForm(instance=route)
    return render(request, 'production/process_route/form.html', {'form': form, 'action': '编辑'})


def process_route_delete(request, pk):
    """删除工艺路线"""
    route = get_object_or_404(ProcessRoute, pk=pk)
    route.delete()
    messages.success(request, '工艺路线删除成功')
    return redirect('production:process_route_list')


def process_route_detail(request, pk):
    """工艺路线详情"""
    route = get_object_or_404(ProcessRoute, pk=pk)
    items = route.processrouteitem_set.all().order_by('sequence')
    return render(request, 'production/process_route/detail.html', {'route': route, 'items': items})


def process_route_copy(request, pk):
    """复制工艺路线"""
    route = get_object_or_404(ProcessRoute, pk=pk)
    items = list(route.processrouteitem_set.all().order_by('sequence'))
    
    route.pk = None
    route.code = f'{route.code}_COPY'
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
    changes = ProductionOrderChange.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, changes,
        search_fields=['change_type', 'change_reason'],
        default_order='-create_time'
    )
    return render(request, 'production/order_change/list.html', context)


def production_order_change_add(request):
    """添加生产订单变更"""
    if request.method == 'POST':
        form = ProductionOrderChangeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '生产订单变更添加成功')
            return redirect('production:production_order_change_list')
    else:
        form = ProductionOrderChangeForm()
    return render(request, 'production/order_change/form.html', {'form': form, 'action': '添加'})


def production_order_change_edit(request, pk):
    """编辑生产订单变更"""
    change = get_object_or_404(ProductionOrderChange, pk=pk)
    if request.method == 'POST':
        form = ProductionOrderChangeForm(request.POST, instance=change)
        if form.is_valid():
            form.save()
            messages.success(request, '生产订单变更编辑成功')
            return redirect('production:production_order_change_list')
    else:
        form = ProductionOrderChangeForm(instance=change)
    return render(request, 'production/order_change/form.html', {'form': form, 'action': '编辑'})


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
        change.status = 3
        change.executed_time = timezone.now()
        change.save()
        messages.success(request, '变更已执行')
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
        if form.is_valid():
            form.save()
            messages.success(request, '生产线日计划添加成功')
            return redirect('production:production_line_day_plan_list')
    else:
        form = ProductionLineDayPlanForm()
    return render(request, 'production/line_day_plan/form.html', {'form': form, 'action': '添加'})


def production_line_day_plan_edit(request, pk):
    """编辑生产线日计划"""
    plan = get_object_or_404(ProductionLineDayPlan, pk=pk)
    if request.method == 'POST':
        form = ProductionLineDayPlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            messages.success(request, '生产线日计划编辑成功')
            return redirect('production:production_line_day_plan_list')
    else:
        form = ProductionLineDayPlanForm(instance=plan)
    return render(request, 'production/line_day_plan/form.html', {'form': form, 'action': '编辑'})


def production_line_day_plan_delete(request, pk):
    """删除生产线日计划"""
    plan = get_object_or_404(ProductionLineDayPlan, pk=pk)
    plan.delete()
    messages.success(request, '生产线日计划删除成功')
    return redirect('production:production_line_day_plan_list')


def material_request_list(request):
    """领料申请列表"""
    requests = MaterialRequest.objects.all()
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
        if form.is_valid():
            form.save()
            messages.success(request, '领料申请添加成功')
            return redirect('production:material_request_list')
    else:
        form = MaterialRequestForm()
    return render(request, 'production/material_request/form.html', {'form': form, 'action': '添加'})


def material_request_edit(request, pk):
    """编辑领料申请"""
    material_request = get_object_or_404(MaterialRequest, pk=pk)
    if request.method == 'POST':
        form = MaterialRequestForm(request.POST, instance=material_request)
        if form.is_valid():
            form.save()
            messages.success(request, '领料申请编辑成功')
            return redirect('production:material_request_list')
    else:
        form = MaterialRequestForm(instance=material_request)
    return render(request, 'production/material_request/form.html', {'form': form, 'action': '编辑'})


def material_request_approve(request, pk):
    """审核领料申请"""
    material_request = get_object_or_404(MaterialRequest, pk=pk)
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
    issues = MaterialIssue.objects.all()
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
        if form.is_valid():
            form.save()
            messages.success(request, '材料出库添加成功')
            return redirect('production:material_issue_list')
    else:
        form = MaterialIssueForm()
    return render(request, 'production/material_issue/form.html', {'form': form, 'action': '添加'})


def material_issue_edit(request, pk):
    """编辑材料出库"""
    issue = get_object_or_404(MaterialIssue, pk=pk)
    if request.method == 'POST':
        form = MaterialIssueForm(request.POST, instance=issue)
        if form.is_valid():
            form.save()
            messages.success(request, '材料出库编辑成功')
            return redirect('production:material_issue_list')
    else:
        form = MaterialIssueForm(instance=issue)
    return render(request, 'production/material_issue/form.html', {'form': form, 'action': '编辑'})


def material_issue_approve(request, pk):
    """审核材料出库"""
    issue = get_object_or_404(MaterialIssue, pk=pk)
    issue.status = 2
    issue.approved_by = request.user
    issue.save()
    messages.success(request, '材料出库已审核')
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
    returns = MaterialReturn.objects.all()
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
        if form.is_valid():
            form.save()
            messages.success(request, '退料添加成功')
            return redirect('production:material_return_list')
    else:
        form = MaterialReturnForm()
    return render(request, 'production/material_return/form.html', {'form': form, 'action': '添加'})


def material_return_edit(request, pk):
    """编辑退料"""
    material_return = get_object_or_404(MaterialReturn, pk=pk)
    if request.method == 'POST':
        form = MaterialReturnForm(request.POST, instance=material_return)
        if form.is_valid():
            form.save()
            messages.success(request, '退料编辑成功')
            return redirect('production:material_return_list')
    else:
        form = MaterialReturnForm(instance=material_return)
    return render(request, 'production/material_return/form.html', {'form': form, 'action': '编辑'})


def material_return_approve(request, pk):
    """审核退料"""
    material_return = get_object_or_404(MaterialReturn, pk=pk)
    material_return.status = 2
    material_return.approved_by = request.user
    material_return.save()
    messages.success(request, '退料已审核')
    return redirect('production:material_return_list')


def material_return_cancel(request, pk):
    """取消退料"""
    material_return = get_object_or_404(MaterialReturn, pk=pk)
    material_return.status = 4
    material_return.save()
    messages.success(request, '退料已取消')
    return redirect('production:material_return_list')


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
        if form.is_valid():
            form.save()
            messages.success(request, '完工申报添加成功')
            return redirect('production:work_completion_report_list')
    else:
        form = WorkCompletionReportForm()
    return render(request, 'production/completion_report/form.html', {'form': form, 'action': '添加'})


def work_completion_report_edit(request, pk):
    """编辑完工申报"""
    report = get_object_or_404(WorkCompletionReport, pk=pk)
    if request.method == 'POST':
        form = WorkCompletionReportForm(request.POST, instance=report)
        if form.is_valid():
            form.save()
            messages.success(request, '完工申报编辑成功')
            return redirect('production:work_completion_report_list')
    else:
        form = WorkCompletionReportForm(instance=report)
    return render(request, 'production/completion_report/form.html', {'form': form, 'action': '编辑'})


def work_completion_report_approve(request, pk):
    """审核完工申报"""
    report = get_object_or_404(WorkCompletionReport, pk=pk)
    report.status = 2
    report.approved_by = request.user
    report.approved_time = timezone.now()
    report.save()
    messages.success(request, '完工申报已审核')
    return redirect('production:work_completion_report_list')


def work_completion_report_red_flush(request, pk):
    """红冲完工申报"""
    report = get_object_or_404(WorkCompletionReport, pk=pk)
    if request.method == 'POST':
        form = WorkCompletionRedFlushForm(request.POST)
        if form.is_valid():
            red_flush = form.save(commit=False)
            red_flush.completion_report = report
            red_flush.save()
            messages.success(request, '红冲申请已提交')
            return redirect('production:work_completion_report_list')
    else:
        form = WorkCompletionRedFlushForm(initial={
            'code': f'HC-{report.code}',
            'completion_report': report,
            'red_flush_quantity': report.reported_quantity
        })
    return render(request, 'production/completion_report/red_flush_form.html', {'form': form, 'report': report})


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
        if form.is_valid():
            form.save()
            messages.success(request, '完工红冲添加成功')
            return redirect('production:work_completion_red_flush_list')
    else:
        form = WorkCompletionRedFlushForm()
    return render(request, 'production/red_flush/form.html', {'form': form, 'action': '添加'})


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
        with transaction.atomic():
            red_flush.status = 3
            red_flush.executed_time = timezone.now()
            red_flush.save()
            
            report = red_flush.completion_report
            report.status = 3
            report.save()
            
            task = report.production_task
            task.qualified_quantity -= red_flush.red_flush_quantity
            task.completed_quantity -= red_flush.red_flush_quantity
            task.save()
        
        messages.success(request, '红冲已执行')
    else:
        messages.error(request, '红冲未审核，不能执行')
    return redirect('production:work_completion_red_flush_list')


def product_receipt_list(request):
    """成品入库列表"""
    receipts = ProductReceipt.objects.all()
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
        if form.is_valid():
            form.save()
            messages.success(request, '成品入库添加成功')
            return redirect('production:product_receipt_list')
    else:
        form = ProductReceiptForm()
    return render(request, 'production/product_receipt/form.html', {'form': form, 'action': '添加'})


def product_receipt_edit(request, pk):
    """编辑成品入库"""
    receipt = get_object_or_404(ProductReceipt, pk=pk)
    if request.method == 'POST':
        form = ProductReceiptForm(request.POST, instance=receipt)
        if form.is_valid():
            form.save()
            messages.success(request, '成品入库编辑成功')
            return redirect('production:product_receipt_list')
    else:
        form = ProductReceiptForm(instance=receipt)
    return render(request, 'production/product_receipt/form.html', {'form': form, 'action': '编辑'})


def product_receipt_approve(request, pk):
    """审核成品入库"""
    receipt = get_object_or_404(ProductReceipt, pk=pk)
    receipt.status = 2
    receipt.approved_by = request.user
    receipt.save()
    messages.success(request, '成品入库已审核')
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
        if form.is_valid():
            form.save()
            messages.success(request, '材料确认添加成功')
            return redirect('production:order_material_confirmation_list')
    else:
        form = OrderMaterialConfirmationForm()
    return render(request, 'production/order_confirmation/form.html', {'form': form, 'action': '添加'})


def resource_consumption_list(request):
    """资源消耗列表"""
    consumptions = ResourceConsumption.objects.all()
    page_obj, context = _get_paginated_queryset(
        request, consumptions,
        search_fields=['resource_name'],
        default_order='-consumption_time'
    )
    return render(request, 'production/resource_consumption/list.html', context)


def resource_consumption_add(request):
    """添加资源消耗"""
    if request.method == 'POST':
        form = ResourceConsumptionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '资源消耗添加成功')
            return redirect('production:resource_consumption_list')
    else:
        form = ResourceConsumptionForm()
    return render(request, 'production/resource_consumption/form.html', {'form': form, 'action': '添加'})
