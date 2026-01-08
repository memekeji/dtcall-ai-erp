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

from .models import ApprovalType, ApprovalFlow, ApprovalStep, Approval
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
                    elif hasattr(value, 'id') and hasattr(value, '__str__'):
                        value = str(value)
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
            cc_users_list = []
            notification_users_list = []
            
            if step.cc_users:
                cc_users_list = [int(x.strip()) for x in step.cc_users.split(',') if x.strip().isdigit()]
            if step.notification_users:
                notification_users_list = [int(x.strip()) for x in step.notification_users.split(',') if x.strip().isdigit()]
            
            step_dict = {
                'id': step.id,
                'step_type': step.step_type,
                'step_name': step.step_name,
                'step_order': step.step_order,
                'time_limit_hours': step.time_limit_hours,
                'condition_field': step.condition_field,
                'condition_operator': step.condition_operator,
                'condition_value': step.condition_value,
                'approver_role': step.approver_role,
                'approver_department': step.approver_department,
                'approver_level': step.approver_level,
                'approver_user': step.approver_id if step.approver else None,
                'description': step.description or '',
                'is_required': step.is_required,
                'cc_users': cc_users_list,
                'notification_users': notification_users_list,
            }
            steps_data.append(step_dict)
        
        return JsonResponse({
            'flow_id': flow.id,
            'flow_name': flow.name,
            'steps': steps_data
        })
    
    import json
    from apps.department.models import Department
    
    users_list = list(User.objects.filter(is_active=True).values('id', 'username', 'first_name', 'last_name')[:100])
    for user in users_list:
        user['full_name'] = (user.get('first_name', '') + ' ' + user.get('last_name', '')).strip() or user['username']
        del user['first_name']
        del user['last_name']
    
    depts_list = list(Department.objects.filter(is_active=True).values('id', 'name')[:100])
    
    context = {
        'flow': flow,
        'steps': steps,
        'users_json': json.dumps(users_list),
        'departments_json': json.dumps(depts_list),
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
        
        for idx, step_data in enumerate(steps):
            step = ApprovalStep()
            step.flow = flow
            step.step_order = idx + 1
            step.step_name = step_data.get('step_name', f'审批步骤{idx + 1}')
            step.step_type = step_data.get('step_type', 'department_head')
            
            frontend_type = step_data.get('step_type')
            
            if frontend_type == 'cc':
                step.action_type = 'cc'
                cc_users = step_data.get('cc_users', [])
                step.cc_users = ','.join(map(str, cc_users)) if cc_users else ''
            elif frontend_type == 'notification':
                step.action_type = 'notify'
                notify_users = step_data.get('notify_users', step_data.get('notification_users', []))
                step.notification_users = ','.join(map(str, notify_users)) if notify_users else ''
            else:
                step.action_type = 'approve'
                
                if frontend_type == 'specific_user' and step_data.get('approver_user'):
                    try:
                        step.approver = User.objects.get(pk=step_data.get('approver_user'))
                    except User.DoesNotExist:
                        pass
                elif frontend_type == 'department' and step_data.get('approver_department'):
                    step.approver_department = step_data.get('approver_department')
                elif frontend_type == 'department_head':
                    step.approver_role = 'department_head'
                elif frontend_type == 'role' and step_data.get('approver_role'):
                    step.approver_role = step_data.get('approver_role')
                elif frontend_type == 'level' and step_data.get('approver_level'):
                    step.approver_level = step_data.get('approver_level')
            
            if step_data.get('time_limit_hours'):
                step.time_limit_hours = int(step_data.get('time_limit_hours'))
            
            step.condition_field = step_data.get('condition_field', '')
            step.condition_operator = step_data.get('condition_operator', '')
            step.condition_value = step_data.get('condition_value', '')
            step.description = step_data.get('description', '')
            step.is_required = step_data.get('is_required', True)
            
            step.save()
            created_steps.append(step)
        
        return JsonResponse({'success': True, 'message': '流程保存成功', 'steps_count': len(created_steps)}, json_dumps_params={'ensure_ascii': False})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': '数据格式错误'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'保存失败：{str(e)}'})


@login_required
def approval_flow_preview(request, pk):
    flow = get_object_or_404(ApprovalFlow, pk=pk)
    steps = flow.steps.all().order_by('step_order')
    
    flow_data = {
        'nodes': [],
        'edges': []
    }
    
    for step in steps:
        approver_info = ''
        if step.approver_role:
            approver_info = step.approver_role
        elif step.approver_department:
            approver_info = step.approver_department
        elif step.approver_level:
            approver_info = f"级别{step.approver_level}"
        
        node = {
            'id': f'step_{step.id}',
            'label': step.step_name,
            'type': step.get_step_type_display(),
            'action': step.get_action_type_display(),
            'approver': approver_info,
            'description': step.description,
            'time_limit': step.time_limit_hours,
            'is_required': step.is_required,
            'is_parallel': step.is_parallel,
            'step_order': step.step_order,
        }
        flow_data['nodes'].append(node)
    
    context = {
        'flow': flow,
        'steps': steps,
        'flow_data': flow_data,
    }
    return render(request, 'Approval/approval_flow_preview.html', context)


@login_required
def get_initiator_config(request, pk):
    flow = get_object_or_404(ApprovalFlow, pk=pk)
    
    initiator_users = []
    initiator_departments = []
    initiator_roles = []
    
    if flow.initiator_users:
        initiator_users = [int(x.strip()) for x in flow.initiator_users.split(',') if x.strip().isdigit()]
    if flow.initiator_departments:
        initiator_departments = [int(x.strip()) for x in flow.initiator_departments.split(',') if x.strip().isdigit()]
    if flow.initiator_roles:
        initiator_roles = [x.strip() for x in flow.initiator_roles.split(',') if x.strip()]
    
    return JsonResponse({
        'flow_id': flow.id,
        'flow_name': flow.name,
        'initiator_users': initiator_users,
        'initiator_departments': initiator_departments,
        'initiator_roles': initiator_roles,
    })


@login_required
@require_POST
def update_initiator_config(request, pk):
    flow = get_object_or_404(ApprovalFlow, pk=pk)
    
    try:
        data = json.loads(request.body)
        
        initiator_users = data.get('initiator_users', [])
        initiator_departments = data.get('initiator_departments', [])
        initiator_roles = data.get('initiator_roles', [])
        
        flow.initiator_users = ','.join(map(str, initiator_users)) if initiator_users else ''
        flow.initiator_departments = ','.join(map(str, initiator_departments)) if initiator_departments else ''
        flow.initiator_roles = ','.join(initiator_roles) if initiator_roles else ''
        
        flow.save()
        
        return JsonResponse({
            'success': True,
            'message': '发起人配置保存成功'
        }, json_dumps_params={'ensure_ascii': False})
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': '数据格式错误'
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'保存失败：{str(e)}'
        }, json_dumps_params={'ensure_ascii': False})


@login_required
def get_start_config(request, pk):
    flow = get_object_or_404(ApprovalFlow, pk=pk)
    
    form_fields = []
    if flow.form_fields:
        try:
            form_fields = json.loads(flow.form_fields)
        except json.JSONDecodeError:
            form_fields = []
    
    return JsonResponse({
        'flow_id': flow.id,
        'flow_name': flow.name,
        'form_fields': form_fields,
    })


@login_required
@require_POST
def update_start_config(request, pk):
    flow = get_object_or_404(ApprovalFlow, pk=pk)
    
    try:
        data = json.loads(request.body)
        
        form_fields = data.get('form_fields', [])
        flow.form_fields = json.dumps(form_fields, ensure_ascii=False)
        flow.save()
        
        return JsonResponse({
            'success': True,
            'message': '开始节点配置保存成功'
        }, json_dumps_params={'ensure_ascii': False})
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': '数据格式错误'
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'保存失败：{str(e)}'
        }, json_dumps_params={'ensure_ascii': False})


@login_required
def my_approval_list(request):
    user = request.user
    approvals = Approval.objects.filter(applicant_id=user.id).order_by('-create_time')


@login_required
def my_approval_list(request):
    user = request.user
    approvals = Approval.objects.filter(applicant_id=user.id).order_by('-create_time')
    
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))
    paginator = Paginator(approvals, limit)
    page_obj = paginator.get_page(page)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = []
        for obj in page_obj:
            data.append({
                'id': obj.id,
                'title': obj.title,
                'flow_name': obj.flow.name if obj.flow else '',
                'status': obj.status,
                'status_display': obj.get_status_display(),
                'create_time': obj.create_time.strftime('%Y-%m-%d %H:%M:%S') if obj.create_time else '',
            })
        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })
    
    context = {
        'page_obj': page_obj,
        'page_title': '我的审批',
        'add_url': '/approval/apply/',
    }
    return render(request, 'Approval/my_approval_list.html', context)


@login_required
def apply_approval(request):
    user = request.user
    user_dept_id = getattr(user, 'did', None)
    
    flows = ApprovalFlow.objects.filter(is_active=True)
    
    available_flows = []
    for flow in flows:
        can_apply = False
        if not flow.initiator_departments and not flow.initiator_roles and not flow.initiator_users:
            can_apply = True
        else:
            if flow.initiator_users:
                user_ids = [int(x.strip()) for x in flow.initiator_users.split(',') if x.strip().isdigit()]
                if user.id in user_ids:
                    can_apply = True
            
            if not can_apply and flow.initiator_departments and user_dept_id:
                dept_ids = [int(x.strip()) for x in flow.initiator_departments.split(',') if x.strip().isdigit()]
                if user_dept_id in dept_ids:
                    can_apply = True
            
            if not can_apply and flow.initiator_roles:
                user_roles = []
                if hasattr(user, 'roles'):
                    user_roles = [r.code for r in user.roles.all()]
                elif hasattr(user, 'role_codes'):
                    user_roles = user.role_codes or []
                flow_role_codes = [r.strip() for r in flow.initiator_roles.split(',') if r.strip()]
                for ur in user_roles:
                    if ur in flow_role_codes:
                        can_apply = True
                        break
        
        if can_apply:
            step_count = flow.steps.count()
            available_flows.append({
                'id': flow.id,
                'name': flow.name,
                'code': flow.code,
                'description': flow.description,
                'step_count': step_count,
            })
    
    context = {
        'flows': available_flows,
        'page_title': '发起审批',
    }
    return render(request, 'Approval/apply_approval.html', context)


@login_required
def create_approval(request, flow_id):
    flow = get_object_or_404(ApprovalFlow, pk=flow_id, is_active=True)
    steps = flow.steps.all().order_by('step_order')
    
    if request.method == 'POST':
        title = request.POST.get('title', '')
        content = request.POST.get('content', '')
        
        if not title:
            messages.error(request, '请输入审批标题')
        else:
            approval = Approval.objects.create(
                title=title,
                flow=flow,
                applicant_id=request.user.id,
                status=0,
                content=content,
            )
            messages.success(request, '审批申请已提交成功！')
            return redirect('approval:my_approval_list')
    
    context = {
        'flow': flow,
        'steps': steps,
        'page_title': '提交审批 - ' + flow.name,
    }
    return render(request, 'Approval/create_approval.html', context)


@login_required
def get_available_flows(request):
    user = request.user
    user_dept_id = getattr(user, 'did', None)
    
    flows = ApprovalFlow.objects.filter(is_active=True)
    
    available_flows = []
    for flow in flows:
        can_apply = False
        if not flow.initiator_departments and not flow.initiator_roles and not flow.initiator_users:
            can_apply = True
        else:
            if flow.initiator_users:
                user_ids = [int(x.strip()) for x in flow.initiator_users.split(',') if x.strip().isdigit()]
                if user.id in user_ids:
                    can_apply = True
            
            if not can_apply and flow.initiator_departments and user_dept_id:
                dept_ids = [int(x.strip()) for x in flow.initiator_departments.split(',') if x.strip().isdigit()]
                if user_dept_id in dept_ids:
                    can_apply = True
            
            if not can_apply and flow.initiator_roles:
                user_roles = []
                if hasattr(user, 'roles'):
                    user_roles = [r.code for r in user.roles.all()]
                elif hasattr(user, 'role_codes'):
                    user_roles = user.role_codes or []
                flow_role_codes = [r.strip() for r in flow.initiator_roles.split(',') if r.strip()]
                for ur in user_roles:
                    if ur in flow_role_codes:
                        can_apply = True
                        break
        
        if can_apply:
            available_flows.append({
                'id': flow.id,
                'name': flow.name,
                'code': flow.code,
                'description': flow.description or '',
            })
    
    return JsonResponse({'flows': available_flows})


@login_required
def delete_item(request, model_name, pk):
    model_map = {
        'approvaltype': ApprovalType,
        'approvalflow': ApprovalFlow,
        'approvalstep': ApprovalStep,
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
