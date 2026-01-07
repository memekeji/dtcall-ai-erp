from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import datetime as dt, date as dt_date
import json

from .models import ApprovalType, ApprovalFlow, ApprovalStep
from .forms import ApprovalTypeForm, ApprovalFlowForm, ApprovalStepForm

User = get_user_model()


def get_base_context(model_class, title, list_url):
    return {
        'model_name': model_class._meta.verbose_name,
        'model_name_plural': model_class._meta.verbose_name_plural,
        'page_title': title,
        'list_url': list_url,
    }


def generic_list_view(request, model_class, template_name, search_fields=None, filter_fields=None):
    search = request.GET.get('search', '')
    objects = model_class.objects.all()
    
    if search and search_fields:
        q_objects = Q()
        for field in search_fields:
            q_objects |= Q(**{f"{field}__icontains": search})
        objects = objects.filter(q_objects)
    
    if filter_fields:
        for field, value in filter_fields.items():
            if value:
                objects = objects.filter(**{field: value})
    
    time_field = 'created_at'
    try:
        model_class._meta.get_field('created_at')
    except:
        time_field = 'id'
    
    objects = objects.order_by(f'-{time_field}')
    
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 20))
    paginator = Paginator(objects, limit)
    page_obj = paginator.get_page(page)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'page' in request.GET and 'limit' in request.GET:
        data = []
        for obj in page_obj:
            obj_dict = {'id': obj.id}
            for field in model_class._meta.fields:
                if field.name not in obj_dict:
                    value = getattr(obj, field.name)
                    if isinstance(value, (dt, dt_date)):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    elif isinstance(value, Decimal):
                        value = float(value)
                    obj_dict[field.name] = value
            data.append(obj_dict)
        
        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })
    
    from django.urls import reverse
    context = {
        'page_obj': page_obj,
        'search': search,
        'model_name': model_class._meta.verbose_name,
        'model_name_plural': model_class._meta.verbose_name_plural,
        'page_title': f'{model_class._meta.verbose_name_plural}管理',
        'list_url': request.path,
        'add_url': f"{request.path.rstrip('/')}/add/",
        'edit_url': f"{request.path.rstrip('/')}/{{id}}/edit/",
        'delete_url': f"/approval/delete/{model_class._meta.model_name}/{{id}}/",
    }
    
    return render(request, template_name, context)


def generic_form_view(request, model_class, form_class, template_name, success_url, pk=None):
    obj = None
    if pk:
        obj = get_object_or_404(model_class, pk=pk)
    
    if request.method == 'POST':
        form = form_class(request.POST, instance=obj)
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json'
        
        if is_ajax:
            if form.is_valid():
                try:
                    form.save()
                    return JsonResponse({'code': 0, 'msg': f'{model_class._meta.verbose_name}保存成功！'})
                except Exception as e:
                    return JsonResponse({'code': 1, 'msg': f'保存失败: {str(e)}'})
            else:
                return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        else:
            if form.is_valid():
                try:
                    form.save()
                    return JsonResponse({'code': 0, 'msg': f'{model_class._meta.verbose_name}保存成功！'})
                except Exception as e:
                    return JsonResponse({'code': 1, 'msg': f'保存失败: {str(e)}'})
            else:
                return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
    else:
        form = form_class(instance=obj)
    
    context = {
        'form': form,
        'object': obj,
        'page_title': f"{'编辑' if obj else '新增'}{model_class._meta.verbose_name}",
        'back_url': success_url,
    }
    
    return render(request, template_name, context)


@login_required
def approval_type_list(request):
    return generic_list_view(
        request,
        ApprovalType,
        'Approval/approval_type_list.html',
        search_fields=['name', 'code']
    )


@login_required
def approval_type_form(request, pk=None):
    return generic_form_view(
        request,
        ApprovalType,
        ApprovalTypeForm,
        'Approval/approval_type_form.html',
        'approval:approval_type_list',
        pk
    )


@login_required
def approval_flow_list(request):
    return generic_list_view(
        request,
        ApprovalFlow,
        'Approval/approval_flow_list.html',
        search_fields=['name', 'code']
    )


@login_required
def approval_flow_form(request, pk=None):
    return generic_form_view(
        request,
        ApprovalFlow,
        ApprovalFlowForm,
        'Approval/approval_flow_form.html',
        'approval:approval_flow_list',
        pk
    )


@login_required
def approval_flow_steps(request, pk):
    flow = get_object_or_404(ApprovalFlow, pk=pk)
    steps = flow.steps.all().order_by('step_order')
    
    if request.GET.get('format') == 'json':
        steps_data = []
        for step in steps:
            step_dict = {
                'id': step.id,
                'step_type': step.step_type,
                'step_name': step.step_name,
                'time_limit_hours': step.time_limit_hours,
                'condition_field': step.condition_field,
                'condition_operator': step.condition_operator,
                'condition_value': step.condition_value,
                'branch_target_true': step.next_step_success.id if step.next_step_success else None,
                'branch_target_false': step.next_step_reject.id if step.next_step_reject else None
            }
            steps_data.append(step_dict)
        
        return JsonResponse({
            'flow_id': flow.id,
            'flow_name': flow.name,
            'steps': steps_data
        })
    
    context = {
        'flow': flow,
        'steps': steps,
    }
    return render(request, 'Approval/approval_flow_steps.html', context)


@login_required
def approval_step_form(request, flow_pk, pk=None):
    flow = get_object_or_404(ApprovalFlow, pk=flow_pk)
    step = None
    if pk:
        step = get_object_or_404(ApprovalStep, pk=pk, flow=flow)
    
    if request.method == 'POST':
        form = ApprovalStepForm(request.POST, instance=step, flow=flow)
        if form.is_valid():
            step = form.save(commit=False)
            step.flow = flow
            step.save()
            form.save_m2m()
            messages.success(request, f'审批步骤保存成功！')
            return redirect('approval:approval_flow_steps', pk=flow.pk)
    else:
        form = ApprovalStepForm(instance=step, flow=flow)
    
    context = {
        'form': form,
        'flow': flow,
        'step': step,
        'page_title': f"{'编辑' if step else '新增'}审批步骤",
    }
    return render(request, 'Approval/approval_step_form.html', context)


@login_required
def approval_step_delete(request, flow_pk, pk):
    flow = get_object_or_404(ApprovalFlow, pk=flow_pk)
    step = get_object_or_404(ApprovalStep, pk=pk, flow=flow)
    
    if request.method == 'POST':
        step.delete()
        messages.success(request, '审批步骤删除成功！')
        return redirect('approval:approval_flow_steps', pk=flow.pk)
    
    context = {
        'flow': flow,
        'step': step,
    }
    return render(request, 'Approval/approval_step_delete.html', context)


@login_required
@require_POST
def batch_create_steps(request, pk):
    flow = get_object_or_404(ApprovalFlow, pk=pk)
    
    try:
        data = json.loads(request.body)
        steps = data.get('steps', [])
        
        if not steps:
            return JsonResponse({'success': False, 'message': '请至少添加一个审批步骤'})
        
        flow.steps.all().delete()
        
        created_steps = []
        step_order_mapping = {}
        
        for step_data in steps:
            step = ApprovalStep()
            step.flow = flow
            step.step_order = step_data.get('step_order')
            step.step_name = step_data.get('step_name')
            
            frontend_type = step_data.get('step_type')
            type_mapping = {
                'specific_user': 'user',
                'department': 'department',
                'role': 'role',
                'level': 'level',
                'department_head': 'user'
            }
            step.step_type = type_mapping.get(frontend_type, 'user')
            
            step.action_type = 'approve'
            
            if frontend_type == 'specific_user' and step_data.get('approver_user'):
                try:
                    step.approver = User.objects.get(pk=step_data.get('approver_user'))
                except User.DoesNotExist:
                    pass
            elif frontend_type == 'department' and step_data.get('approver_department'):
                step.approver_department = step_data.get('approver_department')
                if step_data.get('department_role'):
                    step.approver_role = step_data.get('department_role')
            elif frontend_type == 'role' and step_data.get('approver_role'):
                step.approver_role = step_data.get('approver_role')
            elif frontend_type == 'level' and step_data.get('approver_level'):
                step.approver_level = step_data.get('approver_level')
            elif frontend_type == 'department_head':
                step.approver_role = 'department_head'
            
            if step_data.get('time_limit_hours'):
                step.time_limit_hours = step_data.get('time_limit_hours')
            
            step.condition_field = step_data.get('condition_field', '')
            step.condition_operator = step_data.get('condition_operator', '')
            step.condition_value = step_data.get('condition_value', '')
            
            step.save()
            created_steps.append(step)
            step_order_mapping[step.step_order] = step
        
        for step_data in steps:
            current_step_order = step_data.get('step_order')
            current_step = step_order_mapping.get(current_step_order)
            
            if not current_step:
                continue
            
            branch_target_true = step_data.get('branch_target_true')
            if branch_target_true and branch_target_true != '':
                if branch_target_true.isdigit():
                    target_step = step_order_mapping.get(int(branch_target_true))
                    if target_step:
                        current_step.next_step_success = target_step
            
            branch_target_false = step_data.get('branch_target_false')
            if branch_target_false and branch_target_false != '':
                if branch_target_false.isdigit():
                    target_step = step_order_mapping.get(int(branch_target_false))
                    if target_step:
                        current_step.next_step_reject = target_step
            
            if not current_step.condition_field:
                next_step_order = current_step_order + 1
                next_step = None
                while next_step_order <= len(created_steps):
                    if step_order_mapping.get(next_step_order):
                        next_step = step_order_mapping[next_step_order]
                        break
                    next_step_order += 1
                
                if next_step:
                    current_step.next_step_success = next_step
                    current_step.next_step_reject = next_step
            
            current_step.save()
        
        return JsonResponse({'success': True, 'message': '流程保存成功'}, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, json_dumps_params={'ensure_ascii': False})


@login_required
def approval_flow_preview(request, pk):
    flow = get_object_or_404(ApprovalFlow, pk=pk)
    steps = flow.steps.all().order_by('step_order')
    
    flow_data = {
        'nodes': [],
        'edges': []
    }
    
    for step in steps:
        node = {
            'id': f'step_{step.id}',
            'label': step.step_name,
            'type': step.get_step_type_display(),
            'action': step.get_action_type_display(),
            'approver': str(step.approver) if step.approver else step.approver_role or step.approver_department,
            'description': step.description,
            'time_limit': step.time_limit_hours,
            'is_required': step.is_required,
            'is_parallel': step.is_parallel,
        }
        flow_data['nodes'].append(node)
        
        if step.next_step_success:
            flow_data['edges'].append({
                'source': f'step_{step.id}',
                'target': f'step_{step.next_step_success.id}',
                'label': '通过',
                'type': 'success'
            })
        
        if step.next_step_reject:
            flow_data['edges'].append({
                'source': f'step_{step.id}',
                'target': f'step_{step.next_step_reject.id}',
                'label': '拒绝',
                'type': 'reject'
            })
    
    context = {
        'flow': flow,
        'steps': steps,
        'flow_data': flow_data,
    }
    return render(request, 'Approval/approval_flow_preview.html', context)


@login_required
def delete_item(request, model_name, pk):
    model_map = {
        'approval_type': ApprovalType,
        'approval_flow': ApprovalFlow,
        'approval_step': ApprovalStep,
    }
    
    model_class = model_map.get(model_name)
    if not model_class:
        return JsonResponse({'success': False, 'message': '无效的模型类型'}, json_dumps_params={'ensure_ascii': False})
    
    try:
        obj = get_object_or_404(model_class, pk=pk)
        obj.delete()
        return JsonResponse({'success': True, 'message': '删除成功'}, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'删除失败：{str(e)}'}, json_dumps_params={'ensure_ascii': False})
