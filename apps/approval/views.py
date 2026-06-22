from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import datetime as dt, date as dt_date, timedelta
import json

from .models import ApprovalType, ApprovalFlow, ApprovalStep, Approval, ApprovalRecord, ApprovalFlowEdge, ApprovalTask
from .forms import ApprovalTypeForm, ApprovalFlowForm, ApprovalStepForm
from apps.department.models import Department

User = get_user_model()


def build_sequential_edges(steps):
    ordered_steps = list(steps)
    if not ordered_steps:
        return []
    edge_nodes = ['start'] + [f'step_{step.id}' for step in ordered_steps] + ['end']
    return [
        {
            'id': f'edge_auto_{index + 1}',
            'from_node': edge_nodes[index],
            'to_node': edge_nodes[index + 1],
            'source': edge_nodes[index],
            'target': edge_nodes[index + 1],
            'edge_type': 'success',
            'type': 'success',
            'source_port': 'output_2',
            'target_port': 'input_2',
            'label': '',
            'condition_field': '',
            'condition_operator': '',
            'condition_value': '',
            'sort_order': index,
        }
        for index in range(len(edge_nodes) - 1)
    ]


def build_flow_edges(flow, steps):
    stored_edges = flow.edges.all().order_by('sort_order', 'id')
    edges_data = []
    for edge in stored_edges:
        edge_data = {
            'id': edge.id,
            'from_node': edge.from_node,
            'to_node': edge.to_node,
            'source': edge.from_node,
            'target': edge.to_node,
            'edge_type': edge.edge_type,
            'type': edge.edge_type,
            'source_port': edge.source_port or 'output_2',
            'target_port': edge.target_port or 'input_2',
            'label': edge.label,
            'condition_field': edge.condition_field,
            'condition_operator': edge.condition_operator,
            'condition_value': edge.condition_value,
            'sort_order': edge.sort_order,
        }
        edges_data.append(edge_data)
    if edges_data:
        return edges_data
    return build_sequential_edges(steps)


def _split_ids(value):
    return [x.strip() for x in str(value or '').split(',') if x.strip()]


def _load_json_dict(value):
    try:
        data = json.loads(value or '{}')
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_id_values(value):
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = str(value).split(',')
    return [str(item).strip() for item in values if str(item).strip()]


def _unique_users(users):
    seen = set()
    result = []
    for user in users:
        if user and user.id not in seen:
            seen.add(user.id)
            result.append(user)
    return result


def _get_user_roles(user):
    if hasattr(user, 'role_codes'):
        return user.role_codes or []
    if hasattr(user, 'groups'):
        role_values = []
        for group in user.groups.all():
            role_values.extend([str(group.id), group.name])
        return role_values
    return []


def _get_step_handlers(step, approval=None):
    if not step:
        return []

    config = _load_json_dict(step.config_json)
    handler_ids = []
    for key in ('approver_users', 'handler_users', 'handlers', 'users', 'external_users'):
        handler_ids.extend(_normalize_id_values(config.get(key)))

    if step.step_type in ('specific_user', 'countersign', 'orsign', 'execute', 'external', 'intervention') and step.approver_id:
        handler_ids.append(str(step.approver_id))

    if step.step_type in ('cc', 'notification'):
        field_value = step.cc_users if step.step_type == 'cc' else step.notification_users
        handler_ids.extend(_split_ids(field_value))

    if handler_ids:
        users = User.objects.filter(pk__in=[value for value in handler_ids if str(value).isdigit()], is_active=True)
        user_map = {str(user.id): user for user in users}
        return _unique_users([user_map.get(str(value)) for value in handler_ids])

    if step.step_type == 'department_head':
        applicant_dept_id = None
        if approval:
            applicant = User.objects.filter(pk=approval.applicant_id).first()
            if applicant:
                applicant_dept_id = getattr(applicant, 'did', None)
            if not applicant_dept_id:
                applicant_dept_id = getattr(approval, 'applicant_dept_id', None)
        if applicant_dept_id:
            dept = Department.objects.filter(id=applicant_dept_id).first()
            users = []
            if dept and dept.manager_id:
                users.append(User.objects.filter(pk=dept.manager_id, is_active=True).first())
            if dept:
                leader_ids = [value for value in _split_ids(dept.leader_ids) if value.isdigit()]
                users.extend(User.objects.filter(pk__in=leader_ids, is_active=True))
            return _unique_users(users)

    if step.step_type == 'department':
        dept_ids = [value for value in _split_ids(step.approver_department) if value.isdigit()]
        if dept_ids:
            return list(User.objects.filter(did__in=dept_ids, is_active=True).order_by('id'))

    if step.step_type == 'role':
        role_codes = _split_ids(step.approver_role)
        if role_codes:
            role_filter = Q(groups__name__in=role_codes)
            numeric_roles = [int(value) for value in role_codes if value.isdigit()]
            if numeric_roles:
                role_filter |= Q(groups__id__in=numeric_roles)
            return list(User.objects.filter(role_filter, is_active=True).distinct().order_by('id'))

    if step.step_type == 'level':
        level_values = [value for value in _split_ids(step.approver_level) if value.isdigit()]
        if level_values:
            min_level = min(int(value) for value in level_values)
            return list(User.objects.filter(position_rank__gte=min_level, is_active=True).order_by('id'))

    return []


def _user_can_handle_step(user, approval, step):
    if not user or not step:
        return False

    if step.step_type in ('cc', 'notification', 'status_update', 'writeback', 'archive'):
        return False

    if any(handler.id == user.id for handler in _get_step_handlers(step, approval)):
        return True

    user_id = user.id
    step_type = step.step_type

    if step_type == 'department_head':
        applicant_dept_id = None
        applicant = User.objects.filter(pk=approval.applicant_id).first()
        if applicant:
            applicant_dept_id = getattr(applicant, 'did', None)
        if not applicant_dept_id:
            applicant_dept_id = getattr(approval, 'applicant_dept_id', None)
        if applicant_dept_id:
            dept = Department.objects.filter(id=applicant_dept_id).first()
            if dept:
                leader_ids = _split_ids(dept.leader_ids)
                if (dept.manager_id and user_id == dept.manager_id) or str(user_id) in leader_ids:
                    return True
    elif step_type == 'department':
        user_dept_id = getattr(user, 'did', None)
        return bool(user_dept_id and str(user_dept_id) in _split_ids(step.approver_department))
    elif step_type == 'role':
        role_codes = _split_ids(step.approver_role)
        return any(role in role_codes for role in _get_user_roles(user))
    elif step_type == 'level':
        try:
            return int(getattr(user, 'position_rank', 0) or 0) >= int(step.approver_level or 0)
        except (TypeError, ValueError):
            return False

    return False


def _get_flow_edges(flow):
    if not flow:
        return []

    stored_edges = list(flow.edges.select_related('from_step', 'to_step').order_by('sort_order', 'id'))
    if stored_edges:
        return stored_edges

    steps = list(flow.steps.all().order_by('step_order'))
    edges = []
    previous_step = None
    for step in steps:
        edges.append({
            'from_node': f'step_{previous_step.id}' if previous_step else 'start',
            'to_node': f'step_{step.id}',
            'from_step': previous_step,
            'to_step': step,
            'edge_type': 'success',
            'source_port': 'output_2',
            'target_port': 'input_2',
        })
        previous_step = step
    if previous_step:
        edges.append({
            'from_node': f'step_{previous_step.id}',
            'to_node': 'end',
            'from_step': previous_step,
            'to_step': None,
            'edge_type': 'success',
            'source_port': 'output_2',
            'target_port': 'input_2',
        })
    return edges


def _edge_value(edge, field):
    if isinstance(edge, dict):
        return edge.get(field)
    return getattr(edge, field, None)


def _get_approval_context_value(approval, field):
    field = str(field or '').strip()
    if not field:
        return ''

    data = _load_json_dict(getattr(approval, 'form_data', approval.content))
    if field in data:
        return data.get(field)

    for key in field.split('.'):
        if isinstance(data, dict) and key in data:
            data = data.get(key)
        else:
            data = None
            break
    if data is not None:
        return data

    if hasattr(approval, field):
        return getattr(approval, field)
    return ''


def _compare_condition(actual, operator, expected):
    operator = str(operator or 'eq').strip()
    actual_text = '' if actual is None else str(actual).strip()
    expected_text = str(expected or '').strip()

    if operator in ('eq', '=', '=='):
        return actual_text == expected_text
    if operator in ('ne', '!='):
        return actual_text != expected_text
    if operator in ('contains', 'include'):
        return expected_text in actual_text
    if operator in ('not_contains', 'exclude'):
        return expected_text not in actual_text
    if operator in ('gt', 'gte', 'lt', 'lte', '>', '>=', '<', '<='):
        try:
            actual_number = float(actual_text)
            expected_number = float(expected_text)
        except (TypeError, ValueError):
            return False
        if operator in ('gt', '>'):
            return actual_number > expected_number
        if operator in ('gte', '>='):
            return actual_number >= expected_number
        if operator in ('lt', '<'):
            return actual_number < expected_number
        return actual_number <= expected_number
    if operator == 'empty':
        return actual_text == ''
    if operator == 'not_empty':
        return actual_text != ''
    return actual_text == expected_text


def _edge_matches(approval, edge):
    edge_type = _edge_value(edge, 'edge_type') or _edge_value(edge, 'type') or 'success'
    if edge_type != 'condition':
        return edge_type == 'success'

    field = _edge_value(edge, 'condition_field')
    if not field:
        to_step = _edge_value(edge, 'to_step')
        field = getattr(to_step, 'condition_field', '') if to_step else ''
    if not field:
        return True

    operator = _edge_value(edge, 'condition_operator')
    expected = _edge_value(edge, 'condition_value')
    actual = _get_approval_context_value(approval, field)
    return _compare_condition(actual, operator, expected)


def _record_system_step(approval, step, result='auto_complete', comment='系统节点自动完成'):
    ApprovalRecord.objects.create(
        approval=approval,
        handler=None,
        step_order=step.step_order,
        step_name=step.step_name,
        action='archive' if step.step_type == 'archive' else 'approve',
        comment=comment)
    return result


def _create_tasks_for_step(approval, step):
    if not step:
        return []

    pending_tasks = list(approval.tasks.filter(step=step, status='pending'))
    if pending_tasks:
        return pending_tasks

    system_types = {'cc', 'notification', 'status_update', 'writeback', 'archive'}
    if step.step_type in system_types or step.action_type in ('notify', 'archive', 'system'):
        result = _record_system_step(approval, step)
        task = ApprovalTask.objects.create(
            approval=approval,
            step=step,
            handler=None,
            status='completed',
            result=result,
            comment='系统节点自动完成',
            completed_at=timezone.now())
        approval.status = 1
        approval.current_step_order = step.step_order
        approval.save(update_fields=['status', 'current_step_order', 'update_time'])
        _activate_next_steps(approval, step)
        return [task]

    handlers = _get_step_handlers(step, approval)
    if step.approval_mode in ('all', 'any') or step.step_type in ('countersign', 'orsign'):
        tasks = []
        for handler in handlers:
            tasks.append(ApprovalTask.objects.create(
                approval=approval,
                step=step,
                handler=handler,
                status='pending'))
        if not tasks:
            tasks.append(ApprovalTask.objects.create(
                approval=approval,
                step=step,
                handler=None,
                status='pending'))
    else:
        handler = handlers[0] if handlers else (step.approver if step.approver_id else None)
        tasks = [ApprovalTask.objects.create(
            approval=approval,
            step=step,
            handler=handler,
            status='pending')]

    approval.status = 1
    approval.current_step_order = step.step_order
    approval.save(update_fields=['status', 'current_step_order', 'update_time'])
    return tasks


def _activate_next_steps(approval, current_step):
    if not approval.flow or not current_step:
        approval.status = 2
        approval.current_step_order = 0
        approval.save(update_fields=['status', 'current_step_order', 'update_time'])
        return []

    created_tasks = []
    reached_end = False
    for edge in _get_flow_edges(approval.flow):
        from_step = _edge_value(edge, 'from_step')
        from_node = _edge_value(edge, 'from_node')
        if from_step != current_step and from_node != f'step_{current_step.id}':
            continue
        if not _edge_matches(approval, edge):
            continue
        if (_edge_value(edge, 'to_node') or '') == 'end':
            reached_end = True
            continue
        tasks = _create_tasks_for_step(approval, _edge_value(edge, 'to_step'))
        created_tasks.extend(tasks or [])

    if not created_tasks and (reached_end or not approval.tasks.filter(status='pending').exists()):
        approval.status = 2
        approval.current_step_order = 0
        approval.save(update_fields=['status', 'current_step_order', 'update_time'])
    return created_tasks


def _ensure_initial_tasks(approval):
    if approval.status != 1 or approval.tasks.filter(status='pending').exists():
        return []

    if not approval.flow:
        approval.status = 2
        approval.current_step_order = 0
        approval.save(update_fields=['status', 'current_step_order', 'update_time'])
        return []

    created_tasks = []
    edges = _get_flow_edges(approval.flow)
    for edge in edges:
        if (_edge_value(edge, 'from_node') or '') != 'start':
            continue
        if (_edge_value(edge, 'to_node') or '') == 'end':
            continue
        tasks = _create_tasks_for_step(approval, _edge_value(edge, 'to_step'))
        created_tasks.extend(tasks or [])

    if not created_tasks:
        first_step = approval.flow.steps.all().order_by('step_order').first()
        tasks = _create_tasks_for_step(approval, first_step)
        created_tasks.extend(tasks or [])

    if not created_tasks:
        approval.status = 2
        approval.current_step_order = 0
        approval.save(update_fields=['status', 'current_step_order', 'update_time'])
    return created_tasks


def _get_user_pending_task(approval, user):
    for task in approval.tasks.select_related('step').filter(status='pending').order_by('created_at', 'id'):
        if task.handler_id:
            if task.handler_id == user.id:
                return task
            continue
        if _user_can_handle_step(user, approval, task.step):
            return task
    return None


def _create_intervention_task(approval, step, handler=None, result=''):
    if not step:
        return None

    task = ApprovalTask.objects.create(
        approval=approval,
        step=step,
        handler=handler,
        status='pending',
        result=result)
    approval.status = 1
    approval.current_step_order = step.step_order
    approval.save(update_fields=['status', 'current_step_order', 'update_time'])
    return task


def _cancel_pending_tasks(approval, result, now):
    approval.tasks.filter(status='pending').update(
        status='cancelled',
        result=result,
        completed_at=now,
        updated_at=now)


def _return_to_step(approval, task, target):
    now = timezone.now()
    target = str(target or '').strip()
    target_step = None

    _cancel_pending_tasks(approval, 'return', now)

    if target == 'applicant':
        approval.status = 0
        approval.current_step_order = 0
        approval.save(update_fields=['status', 'current_step_order', 'update_time'])
        return None

    if target == 'previous':
        previous_record = approval.records.filter(
            action__in=['approve', 'execute', 'external_approve']
        ).order_by('-create_time', '-id').first()
        if previous_record and approval.flow:
            target_step = approval.flow.steps.filter(step_order=previous_record.step_order).first()
    elif target.isdigit() and approval.flow:
        target_step = approval.flow.steps.filter(pk=int(target)).first()

    if not target_step:
        raise ValueError('退回目标节点不存在')

    handler = target_step.approver if target_step.approver_id else None
    return _create_intervention_task(approval, target_step, handler=handler, result='return')


def _add_sign_task(approval, task, user_id, mode):
    sign_user = User.objects.filter(pk=user_id, is_active=True).first()
    if not sign_user:
        raise ValueError('加签人不存在或已停用')

    if mode == 'before':
        task.handler = sign_user
        task.result = 'add_before'
        task.save(update_fields=['handler', 'result', 'updated_at'])
        return task

    if mode == 'after':
        now = timezone.now()
        task.status = 'completed'
        task.result = 'add_after'
        task.completed_at = now
        task.save(update_fields=['status', 'result', 'completed_at', 'updated_at'])
        return _create_intervention_task(approval, task.step, handler=sign_user, result='add_after')

    raise ValueError('加签方式不正确')


def _can_withdraw_approval(approval, user):
    return (
        approval.applicant_id == user.id
        and approval.status in [0, 1]
        and not approval.records.filter(action__in=['approve', 'execute', 'external_approve']).exists()
    )


def _is_pending_task_handler(task, user):
    if task.handler_id:
        return task.handler_id == user.id
    return _user_can_handle_step(user, task.approval, task.step)


def _get_urge_pending_task(approval, user):
    pending_tasks = approval.tasks.select_related('step').filter(
        status='pending').order_by('created_at', 'id')
    first_task = pending_tasks.first()
    if not first_task:
        return None, False
    can_urge = approval.applicant_id == user.id or user.is_staff or user.is_superuser
    if not can_urge:
        can_urge = any(_is_pending_task_handler(task, user) for task in pending_tasks)
    return first_task, can_urge


def _get_escalate_user(step):
    try:
        config = json.loads(step.config_json or '{}')
    except (TypeError, json.JSONDecodeError):
        return None
    escalate_to = config.get('escalate_to')
    if not escalate_to:
        return None
    return User.objects.filter(pk=escalate_to, is_active=True).first()


def _handle_timeout_tasks(approval, user, now, comment):
    timeout_count = 0
    pending_tasks = list(approval.tasks.select_related('step').filter(
        status='pending').order_by('created_at', 'id'))

    for task in pending_tasks:
        step = task.step
        if not step or not step.time_limit_hours or step.time_limit_hours <= 0:
            continue
        if not task.created_at or task.created_at + timedelta(hours=step.time_limit_hours) > now:
            continue

        timeout_count += 1
        timeout_action = step.timeout_action or 'none'
        record_comment = comment or f'超时策略：{step.get_timeout_action_display()}'

        if timeout_action == 'auto_approve':
            task.status = 'completed'
            task.result = 'timeout_auto_approve'
            task.comment = record_comment
            task.completed_at = now
            task.save(update_fields=['status', 'result', 'comment', 'completed_at', 'updated_at'])
            _activate_next_steps(approval, step)
        elif timeout_action == 'auto_reject':
            task.status = 'completed'
            task.result = 'timeout_auto_reject'
            task.comment = record_comment
            task.completed_at = now
            task.save(update_fields=['status', 'result', 'comment', 'completed_at', 'updated_at'])
            approval.tasks.filter(status='pending').exclude(pk=task.pk).update(
                status='cancelled',
                result='timeout_auto_reject',
                completed_at=now,
                updated_at=now)
            approval.status = 3
            approval.current_step_order = 0
            approval.save(update_fields=['status', 'current_step_order', 'update_time'])
        elif timeout_action == 'escalate':
            escalate_user = _get_escalate_user(step)
            if escalate_user:
                task.handler = escalate_user
            task.result = 'timeout_escalate'
            task.comment = record_comment
            task.save(update_fields=['handler', 'result', 'comment', 'updated_at'])
        else:
            task.result = 'timeout'
            task.comment = record_comment
            task.save(update_fields=['result', 'comment', 'updated_at'])

        ApprovalRecord.objects.create(
            approval=approval,
            step_order=step.step_order,
            step_name=step.step_name,
            action='timeout',
            comment=record_comment,
            handler=user)

        if timeout_action == 'auto_reject':
            break

    return timeout_count


def normalize_client_node(node_id, client_step_map):
    node_id = str(node_id or '').strip()
    if node_id in ('start', 'end'):
        return node_id
    return client_step_map.get(node_id) or (node_id if node_id.startswith('step_') else '')


def get_base_context(model_class, title, list_url):
    return {
        'model_name': model_class._meta.verbose_name,
        'model_name_plural': model_class._meta.verbose_name_plural,
        'page_title': title,
        'list_url': list_url,
    }


def generic_list_view(
        request,
        model_class,
        template_name,
        search_fields=None,
        filter_fields=None):
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
    except BaseException:
        time_field = 'id'

    objects = objects.order_by(f'-{time_field}')

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 20))
    paginator = Paginator(objects, limit)
    page_obj = paginator.get_page(page)

    if request.headers.get(
            'X-Requested-With') == 'XMLHttpRequest' or 'page' in request.GET and 'limit' in request.GET:
        data = []
        for obj in page_obj:
            obj_dict = {'id': obj.id}
            for field in model_class._meta.fields:
                if field.name not in obj_dict:
                    value = getattr(obj, field.name)
                    if field.name == 'approval_type':
                        obj_dict['approval_type_name'] = str(value) if value else ''
                    elif field.name == 'created_by':
                        obj_dict['created_by_name'] = str(value) if value else ''
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

    context = {
        'page_obj': page_obj,
        'search': search,
        'model_name': model_class._meta.verbose_name,
        'model_name_plural': model_class._meta.verbose_name_plural,
        'page_title': f'{model_class._meta.verbose_name_plural}管理',
        'list_url': request.path,
        'add_url': f"{request.path.rstrip('/')}/add/",
        'edit_url': f"{request.path.rstrip('/')}/{{id}}/edit/",
        'delete_url': reverse('approval:delete_item', kwargs={
            'model_name': model_class._meta.model_name,
            'pk': 0,
        }).replace('/0/', '/{id}/'),
    }

    return render(request, template_name, context)


def generic_form_view(
        request,
        model_class,
        form_class,
        template_name,
        success_url,
        pk=None):
    obj = None
    if pk:
        obj = get_object_or_404(model_class, pk=pk)

    if request.method == 'POST':
        form = form_class(request.POST, instance=obj)

        is_ajax = request.headers.get(
            'X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json'

        if is_ajax:
            if form.is_valid():
                try:
                    form.save()
                    return JsonResponse(
                        {'code': 0, 'msg': f'{model_class._meta.verbose_name}保存成功！'})
                except Exception as e:
                    return JsonResponse({'code': 1, 'msg': f'保存失败: {str(e)}'})
            else:
                return JsonResponse(
                    {'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        else:
            if form.is_valid():
                try:
                    form.save()
                    return JsonResponse(
                        {'code': 0, 'msg': f'{model_class._meta.verbose_name}保存成功！'})
                except Exception as e:
                    return JsonResponse({'code': 1, 'msg': f'保存失败: {str(e)}'})
            else:
                return JsonResponse(
                    {'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
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
                cc_users_list = [int(x.strip()) for x in step.cc_users.split(
                    ',') if x.strip().isdigit()]
            if step.notification_users:
                notification_users_list = [int(
                    x.strip()) for x in step.notification_users.split(',') if x.strip().isdigit()]

            step_dict = {
                'id': step.id,
                'step_type': step.step_type,
                'step_name': step.step_name,
                'step_order': step.step_order,
                'action_type': step.action_type,
                'approval_mode': step.approval_mode,
                'timeout_action': step.timeout_action,
                'config_json': step.config_json or '{}',
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
                'require_comment': step.require_comment,
                'comment_hint': step.comment_hint,
                'node_x': step.node_x,
                'node_y': step.node_y,
                'cc_users': cc_users_list,
                'notification_users': notification_users_list,
            }
            steps_data.append(step_dict)

        edges_data = build_flow_edges(flow, steps)

        return JsonResponse({
            'flow_id': flow.id,
            'flow_name': flow.name,
            'steps': steps_data,
            'edges': edges_data
        })

    users_list = list(
        User.objects.filter(
            is_active=True).values(
            'id',
            'username',
            'first_name',
            'last_name')[
                :100])
    for user in users_list:
        user['full_name'] = (
            user.get(
                'first_name',
                '') +
            ' ' +
            user.get(
                'last_name',
                '')).strip() or user['username']
        del user['first_name']
        del user['last_name']

    depts_list = list(
        Department.objects.filter(
            is_active=True).values(
            'id',
            'name')[
                :100])

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
        form = ApprovalStepForm(request.POST, instance=step)
        if form.is_valid():
            step = form.save(commit=False)
            step.flow = flow
            step.save()
            form.save_m2m()
            messages.success(request, f'审批步骤保存成功！')
            return redirect('approval:approval_flow_steps', pk=flow.pk)
    else:
        form = ApprovalStepForm(instance=step)

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
        edges = data.get('edges', [])

        if not steps:
            return JsonResponse({'success': False, 'message': '请至少添加一个审批步骤'})

        valid_step_types = dict(ApprovalStep.STEP_TYPE_CHOICES)
        valid_action_types = dict(ApprovalStep.ACTION_TYPE_CHOICES)
        valid_approval_modes = dict(ApprovalStep.APPROVAL_MODE_CHOICES)
        valid_timeout_actions = dict(ApprovalStep.TIMEOUT_ACTION_CHOICES)
        created_steps = []
        client_step_map = {}
        valid_edge_nodes = {'start', 'end'}

        with transaction.atomic():
            flow.edges.all().delete()
            flow.steps.all().delete()

            for idx, step_data in enumerate(steps):
                step = ApprovalStep()
                step.flow = flow
                step.step_order = int(step_data.get('step_order') or idx + 1)
                step.step_name = step_data.get('step_name', f'审批步骤{idx + 1}')
                step.step_type = step_data.get('step_type', 'department_head')
                if step.step_type not in valid_step_types:
                    return JsonResponse({'success': False, 'message': f'不支持的节点类型：{step.step_type}'})

                frontend_type = step_data.get('step_type')
                step.action_type = step_data.get('action_type') or 'approve'

                if frontend_type == 'cc':
                    step.action_type = step_data.get('action_type') or 'notify'
                    cc_users = step_data.get('cc_users', [])
                    step.cc_users = ','.join(map(str, cc_users)) if cc_users else ''
                elif frontend_type == 'notification':
                    step.action_type = step_data.get('action_type') or 'notify'
                    notify_users = step_data.get(
                        'notify_users', step_data.get(
                            'notification_users', []))
                    step.notification_users = ','.join(
                        map(str, notify_users)) if notify_users else ''
                else:
                    if frontend_type in ('countersign', 'orsign'):
                        step.action_type = step_data.get('action_type') or 'sign'
                    elif frontend_type in ('execute', 'intervention'):
                        step.action_type = step_data.get('action_type') or 'execute'
                    elif frontend_type == 'external':
                        step.action_type = step_data.get('action_type') or 'external'
                    elif frontend_type == 'archive':
                        step.action_type = step_data.get('action_type') or 'archive'
                    elif frontend_type in ('condition', 'status_update', 'writeback'):
                        step.action_type = step_data.get('action_type') or 'system'
                    elif not step_data.get('action_type'):
                        step.action_type = 'approve'
                    if step.action_type not in valid_action_types:
                        step.action_type = 'approve'

                    if frontend_type in ('specific_user', 'execute', 'external', 'intervention') and step_data.get(
                            'approver_user'):
                        try:
                            step.approver = User.objects.get(
                                pk=step_data.get('approver_user'))
                        except User.DoesNotExist:
                            pass
                    elif frontend_type == 'department' and step_data.get('approver_department'):
                        step.approver_department = step_data.get(
                            'approver_department')
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
                step.approval_mode = step_data.get('approval_mode') or 'single'
                if step.approval_mode not in valid_approval_modes:
                    step.approval_mode = 'single'
                step.timeout_action = step_data.get('timeout_action') or 'none'
                if step.timeout_action not in valid_timeout_actions:
                    step.timeout_action = 'none'
                config_payload = _load_json_dict(step_data.get('config_json') or '{}')
                if frontend_type in ('countersign', 'orsign'):
                    approver_users = _normalize_id_values(step_data.get('approver_users'))
                    if approver_users:
                        config_payload['approver_users'] = approver_users
                if frontend_type in ('execute', 'external', 'intervention') and step_data.get('approver_user'):
                    config_payload['handler_user'] = str(step_data.get('approver_user'))
                step.config_json = json.dumps(config_payload, ensure_ascii=False)
                step.description = step_data.get('description', '')
                step.is_required = step_data.get('is_required', True)
                step.require_comment = step_data.get('require_comment', True)
                step.comment_hint = step_data.get('comment_hint') or '请输入审批意见'
                step.node_x = int(step_data.get('node_x') or 0)
                step.node_y = int(step_data.get('node_y') or 0)

                step.save()
                created_steps.append(step)
                server_node_id = f'step_{step.id}'
                valid_edge_nodes.add(server_node_id)
                client_step_map[server_node_id] = server_node_id
                client_id = step_data.get('client_id')
                if client_id:
                    client_step_map[str(client_id)] = server_node_id

            edge_payloads = edges or build_sequential_edges(created_steps)
            saved_pairs = set()
            step_lookup = {f'step_{step.id}': step for step in created_steps}

            for idx, edge_data in enumerate(edge_payloads):
                edge_type = edge_data.get('edge_type') or edge_data.get('type') or 'success'
                if edge_type not in dict(ApprovalFlowEdge.EDGE_TYPE_CHOICES):
                    edge_type = 'success'
                from_node = normalize_client_node(edge_data.get('from_node') or edge_data.get('source'), client_step_map)
                to_node = normalize_client_node(edge_data.get('to_node') or edge_data.get('target'), client_step_map)

                if (not from_node or not to_node or from_node == to_node or
                        from_node == 'end' or to_node == 'start' or
                        from_node not in valid_edge_nodes or to_node not in valid_edge_nodes):
                    continue

                source_port = edge_data.get('source_port') or edge_data.get('from_port') or 'output_2'
                target_port = edge_data.get('target_port') or edge_data.get('to_port') or 'input_2'
                pair_key = (from_node, to_node, source_port, target_port, edge_type)
                if pair_key in saved_pairs:
                    continue
                saved_pairs.add(pair_key)

                ApprovalFlowEdge.objects.create(
                    flow=flow,
                    from_node=from_node,
                    to_node=to_node,
                    source_port=source_port,
                    target_port=target_port,
                    from_step=step_lookup.get(from_node),
                    to_step=step_lookup.get(to_node),
                    edge_type=edge_type,
                    label=edge_data.get('label', ''),
                    condition_field=edge_data.get('condition_field', ''),
                    condition_operator=edge_data.get('condition_operator', ''),
                    condition_value=edge_data.get('condition_value', ''),
                    sort_order=int(edge_data.get('sort_order') or idx),
                )

        return JsonResponse({'success': True, 'message': '流程保存成功', 'steps_count': len(
            created_steps)}, json_dumps_params={'ensure_ascii': False})

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
        'edges': build_flow_edges(flow, steps)
    }

    for step in steps:
        approver_info = ''
        handlers = _get_step_handlers(step)
        if handlers:
            approver_info = '、'.join([handler.get_full_name() or handler.username for handler in handlers])
        elif step.approver_role:
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
            'approval_mode': step.get_approval_mode_display(),
            'timeout_action': step.get_timeout_action_display(),
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
        'flow_data_json': json.dumps(flow_data, ensure_ascii=False),
    }
    return render(request, 'Approval/approval_flow_preview.html', context)


@login_required
def get_initiator_config(request, pk):
    flow = get_object_or_404(ApprovalFlow, pk=pk)

    initiator_users = []
    initiator_departments = []
    initiator_roles = []

    if flow.initiator_users:
        initiator_users = [int(x.strip()) for x in flow.initiator_users.split(
            ',') if x.strip().isdigit()]
    if flow.initiator_departments:
        initiator_departments = [int(x.strip()) for x in flow.initiator_departments.split(
            ',') if x.strip().isdigit()]
    if flow.initiator_roles:
        initiator_roles = [x.strip()
                           for x in flow.initiator_roles.split(',') if x.strip()]

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

        flow.initiator_users = ','.join(
            map(str, initiator_users)) if initiator_users else ''
        flow.initiator_departments = ','.join(
            map(str, initiator_departments)) if initiator_departments else ''
        flow.initiator_roles = ','.join(
            initiator_roles) if initiator_roles else ''

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
    approvals = Approval.objects.filter(
        applicant_id=user.id).order_by('-create_time')

    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 10))
    paginator = Paginator(approvals, limit)
    page_obj = paginator.get_page(page)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = []
        for obj in page_obj:
            pending_tasks = list(obj.tasks.select_related('step').filter(
                status='pending').order_by('created_at', 'id'))
            current_steps = '、'.join(
                task.step.step_name for task in pending_tasks if task.step)
            data.append({
                'id': obj.id,
                'title': obj.title,
                'flow_name': obj.flow.name if obj.flow else '',
                'status': obj.status,
                'status_display': obj.get_status_display(),
                'create_time': obj.create_time.strftime('%Y-%m-%d %H:%M:%S') if obj.create_time else '',
                'can_withdraw': _can_withdraw_approval(obj, user),
                'pending_count': len(pending_tasks),
                'current_steps': current_steps,
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
        'add_url': reverse('approval:apply_approval'),
    }
    return render(request, 'Approval/my_approval_list.html', context)


@login_required
def pending_list(request):
    context = {
        'page_title': '待我审批',
    }
    return render(request, 'Approval/pending_list.html', context)


@login_required
def get_pending_approvals(request):
    user = request.user
    pending_approvals = []

    approvals = Approval.objects.filter(status=1).select_related('flow').order_by('-create_time')

    for approval in approvals:
        flow = approval.flow
        if not flow:
            continue

        _ensure_initial_tasks(approval)
        tasks = approval.tasks.select_related('step').filter(status='pending').order_by('created_at', 'id')

        for task in tasks:
            if task.handler_id:
                if task.handler_id != user.id:
                    continue
            elif not _user_can_handle_step(user, approval, task.step):
                continue
            stay_hours = 0
            if task.created_at:
                stay_hours = round((timezone.now() - task.created_at).total_seconds() / 3600, 1)
            pending_approvals.append({
                'id': approval.id,
                'task_id': task.id,
                'title': approval.title,
                'flow_name': flow.name,
                'applicant_id': approval.applicant_id,
                'content': approval.content[:100] if approval.content else '',
                'create_time': approval.create_time.strftime('%Y-%m-%d %H:%M') if approval.create_time else '',
                'current_step': task.step.step_name,
                'step_type': task.step.get_step_type_display(),
                'task_status': task.get_status_display(),
                'task_created_at': task.created_at.strftime('%Y-%m-%d %H:%M') if task.created_at else '',
                'handler_name': task.handler.get_full_name() or task.handler.username if task.handler else '',
                'stay_hours': stay_hours,
            })

    return JsonResponse({
        'code': 0,
        'msg': '',
        'count': len(pending_approvals),
        'data': pending_approvals
    })


@login_required
def approval_detail(request, pk):
    approval = get_object_or_404(Approval, pk=pk)

    flow = approval.flow
    steps = []
    if flow:
        steps = flow.steps.all().order_by('step_order')

    records = approval.records.all().order_by('create_time')
    tasks = approval.tasks.select_related('step', 'handler').order_by('created_at')
    pending_tasks = tasks.filter(status='pending')
    has_pending_tasks = pending_tasks.exists()
    now = timezone.now()
    for task in tasks:
        if task.status == 'pending' and task.created_at:
            task.stay_hours = round((now - task.created_at).total_seconds() / 3600, 1)
        else:
            task.stay_hours = None

    context = {
        'approval': approval,
        'flow': flow,
        'steps': steps,
        'records': records,
        'tasks': tasks,
        'pending_tasks': pending_tasks,
        'has_pending_tasks': has_pending_tasks,
        'can_withdraw': _can_withdraw_approval(approval, request.user),
        'can_force_end': request.user.is_staff or request.user.is_superuser,
        'now': now,
        'page_title': '审批详情 - ' + approval.title,
    }
    return render(request, 'Approval/approval_detail.html', context)


@login_required
def process_approval(request, pk):
    approval = get_object_or_404(Approval, pk=pk)

    if approval.status not in [0, 1]:
        messages.error(request, '该审批已处理完成')
        return redirect('approval:pending_list')

    flow = approval.flow
    steps = []
    if flow:
        steps = flow.steps.all().order_by('step_order')

    if approval.status == 1:
        _ensure_initial_tasks(approval)
    task = _get_user_pending_task(approval, request.user)

    current_step_order = approval.current_step_order or 1
    current_step = task.step if task else None
    if not current_step and flow:
        current_step = flow.steps.filter(step_order=current_step_order).first()

    context = {
        'approval': approval,
        'flow': flow,
        'steps': steps,
        'current_step': current_step,
        'current_task': task,
        'page_title': '处理审批 - ' + approval.title,
    }
    return render(request, 'Approval/process_approval.html', context)


@login_required
@require_POST
def approval_action(request, pk):
    approval = get_object_or_404(Approval, pk=pk)

    try:
        data = json.loads(request.body)
        action = data.get('action', '')
        comment = data.get('comment', '')

        if not action:
            return JsonResponse({
                'success': False,
                'message': '请选择操作类型'
            }, json_dumps_params={'ensure_ascii': False})

        if approval.status not in [0, 1]:
            return JsonResponse({
                'success': False,
                'message': '该审批已处理完成，不能重复操作'
            }, json_dumps_params={'ensure_ascii': False})

        user = request.user
        with transaction.atomic():
            now = timezone.now()

            if action == 'withdraw':
                if approval.applicant_id != user.id or approval.status not in [0, 1]:
                    return JsonResponse({
                        'success': False,
                        'message': '仅申请人可撤回待处理审批'
                    }, json_dumps_params={'ensure_ascii': False})
                if approval.records.filter(action__in=['approve', 'execute', 'external_approve']).exists():
                    return JsonResponse({
                        'success': False,
                        'message': '下一节点已处理，不能撤回'
                    }, json_dumps_params={'ensure_ascii': False})
                _cancel_pending_tasks(approval, 'withdraw', now)
                approval.status = 0
                approval.current_step_order = 0
                approval.save(update_fields=['status', 'current_step_order', 'update_time'])
                ApprovalRecord.objects.create(
                    approval=approval,
                    step_order=0,
                    step_name='申请人撤回',
                    action='withdraw',
                    comment=comment,
                    handler=user)
            elif action == 'force_end':
                if not (user.is_superuser or user.is_staff):
                    return JsonResponse({
                        'success': False,
                        'message': '仅管理员可强制结束审批'
                    }, json_dumps_params={'ensure_ascii': False})
                _cancel_pending_tasks(approval, 'force_end', now)
                approval.status = 2
                approval.current_step_order = 0
                approval.save(update_fields=['status', 'current_step_order', 'update_time'])
                ApprovalRecord.objects.create(
                    approval=approval,
                    step_order=0,
                    step_name='强制结束',
                    action='force_end',
                    comment=comment,
                    handler=user)
            elif action == 'urge':
                if approval.status == 1:
                    _ensure_initial_tasks(approval)
                task, can_urge = _get_urge_pending_task(approval, user)
                if not task:
                    return JsonResponse({
                        'success': False,
                        'message': '当前没有可催办任务'
                    }, json_dumps_params={'ensure_ascii': False})
                if not can_urge:
                    return JsonResponse({
                        'success': False,
                        'message': '仅申请人、当前处理人或管理员可发起催办'
                    }, json_dumps_params={'ensure_ascii': False})
                ApprovalRecord.objects.create(
                    approval=approval,
                    step_order=task.step.step_order if task.step else 0,
                    step_name=task.step.step_name if task.step else '流程催办',
                    action='urge',
                    comment=comment,
                    handler=user)
            elif action == 'timeout':
                if not (user.is_superuser or user.is_staff):
                    return JsonResponse({
                        'success': False,
                        'message': '仅管理员可执行超时策略'
                    }, json_dumps_params={'ensure_ascii': False})
                timeout_count = _handle_timeout_tasks(approval, user, now, comment)
                if timeout_count == 0:
                    return JsonResponse({
                        'success': False,
                        'message': '当前没有已超时任务'
                    }, json_dumps_params={'ensure_ascii': False})
            else:
                if approval.status == 1:
                    _ensure_initial_tasks(approval)
                task = _get_user_pending_task(approval, user)

                if not task:
                    current_step_order = approval.current_step_order or 1
                    current_step = approval.flow.steps.filter(step_order=current_step_order).first() if approval.flow else None
                    if not current_step or not _user_can_handle_step(user, approval, current_step):
                        return JsonResponse({
                            'success': False,
                            'message': '当前没有可处理的审批任务'
                        }, json_dumps_params={'ensure_ascii': False})
                    tasks = _create_tasks_for_step(approval, current_step)
                    task = tasks[0] if tasks else None
                    if not task:
                        return JsonResponse({
                            'success': False,
                            'message': '当前审批节点无法创建处理任务'
                        }, json_dumps_params={'ensure_ascii': False})

                current_step = task.step
                current_step_order = current_step.step_order
                step_name = current_step.step_name

                if action in ('approve', 'execute', 'external_approve'):
                    task.status = 'completed'
                    task.result = action
                    task.comment = comment
                    task.completed_at = now
                    task.handler = user
                    task.save(update_fields=['status', 'result', 'comment', 'completed_at', 'handler', 'updated_at'])

                    step_pending_tasks = approval.tasks.filter(step=current_step, status='pending')
                    if current_step.approval_mode in ('single', 'any') or current_step.step_type == 'orsign':
                        step_pending_tasks.update(status='cancelled', result='cancelled', completed_at=now, updated_at=now)
                        _activate_next_steps(approval, current_step)
                    elif not step_pending_tasks.exists():
                        _activate_next_steps(approval, current_step)

                elif action == 'reject':
                    task.status = 'completed'
                    task.result = 'reject'
                    task.comment = comment
                    task.completed_at = now
                    task.handler = user
                    task.save(update_fields=['status', 'result', 'comment', 'completed_at', 'handler', 'updated_at'])
                    _cancel_pending_tasks(approval, 'reject', now)
                    approval.status = 3
                    approval.current_step_order = 0
                    approval.save(update_fields=['status', 'current_step_order', 'update_time'])

                elif action == 'cancel':
                    _cancel_pending_tasks(approval, 'cancel', now)
                    approval.status = 4
                    approval.current_step_order = 0
                    approval.save(update_fields=['status', 'current_step_order', 'update_time'])

                elif action == 'delegate':
                    delegate_to = data.get('delegate_to', 0)
                    if not delegate_to:
                        return JsonResponse({
                            'success': False,
                            'message': '请选择委托人'
                        }, json_dumps_params={'ensure_ascii': False})
                    delegate_user = User.objects.filter(pk=delegate_to, is_active=True).first()
                    if not delegate_user:
                        return JsonResponse({
                            'success': False,
                            'message': '委托人不存在或已停用'
                        }, json_dumps_params={'ensure_ascii': False})
                    task.handler = delegate_user
                    task.result = 'delegate'
                    task.comment = comment
                    task.save(update_fields=['handler', 'result', 'comment', 'updated_at'])

                elif action == 'return':
                    return_target = data.get('return_target', '')
                    if not return_target:
                        return JsonResponse({
                            'success': False,
                            'message': '请选择退回目标'
                        }, json_dumps_params={'ensure_ascii': False})
                    _return_to_step(approval, task, return_target)

                elif action == 'transfer':
                    transfer_to = data.get('transfer_to', 0)
                    if not transfer_to:
                        return JsonResponse({
                            'success': False,
                            'message': '请输入转交人ID'
                        }, json_dumps_params={'ensure_ascii': False})
                    transfer_user = User.objects.filter(pk=transfer_to, is_active=True).first()
                    if not transfer_user:
                        return JsonResponse({
                            'success': False,
                            'message': '转交人不存在或已停用'
                        }, json_dumps_params={'ensure_ascii': False})
                    task.handler = transfer_user
                    task.result = 'transfer'
                    task.comment = comment
                    task.save(update_fields=['handler', 'result', 'comment', 'updated_at'])

                elif action in ('add_before', 'add_after'):
                    add_sign_user = data.get('add_sign_user', 0)
                    if not add_sign_user:
                        return JsonResponse({
                            'success': False,
                            'message': '请输入加签人ID'
                        }, json_dumps_params={'ensure_ascii': False})
                    _add_sign_task(approval, task, add_sign_user, 'before' if action == 'add_before' else 'after')

                else:
                    return JsonResponse({
                        'success': False,
                        'message': '不支持的操作类型'
                    }, json_dumps_params={'ensure_ascii': False})

                ApprovalRecord.objects.create(
                    approval=approval,
                    step_order=current_step_order,
                    step_name=step_name,
                    action=action,
                    comment=comment,
                    handler=user)

        action_msg = {
            'approve': '审批已通过',
            'execute': '办理已完成',
            'external_approve': '外部审批已通过',
            'reject': '审批已拒绝',
            'cancel': '已取消该审批',
            'delegate': '已委托给指定人员处理',
            'return': '审批已退回',
            'transfer': '审批已转交',
            'add_before': '已发起前加签',
            'add_after': '已发起后加签',
            'withdraw': '审批已撤回',
            'force_end': '审批已强制结束',
            'urge': '催办已发送/记录',
            'timeout': '超时策略已执行',
        }.get(action, '操作成功')

        return JsonResponse({
            'success': True,
            'message': action_msg
        }, json_dumps_params={'ensure_ascii': False})

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': '数据格式错误'
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'操作失败：{str(e)}'
        }, json_dumps_params={'ensure_ascii': False})


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
                user_ids = [int(x.strip()) for x in flow.initiator_users.split(
                    ',') if x.strip().isdigit()]
                if user.id in user_ids:
                    can_apply = True

            if not can_apply and flow.initiator_departments and user_dept_id:
                dept_ids = [int(x.strip()) for x in flow.initiator_departments.split(
                    ',') if x.strip().isdigit()]
                if user_dept_id in dept_ids:
                    can_apply = True

            if not can_apply and flow.initiator_roles:
                user_roles = []
                if hasattr(user, 'roles'):
                    user_roles = [r.code for r in user.roles.all()]
                elif hasattr(user, 'role_codes'):
                    user_roles = user.role_codes or []
                flow_role_codes = [
                    r.strip() for r in flow.initiator_roles.split(',') if r.strip()]
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
                status=1 if steps.exists() else 2,
                content=content,
            )
            _ensure_initial_tasks(approval)
            messages.success(request, '审批申请已提交成功！')
            return redirect('approval:my_approval_list')

    context = {
        'flow': flow,
        'steps': steps,
        'page_title': '提交审批 - ' + flow.name,
    }

    if request.GET.get('iframe') == '1':
        return render(request, 'Approval/create_approval_iframe.html', context)

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
                user_ids = [int(x.strip()) for x in flow.initiator_users.split(
                    ',') if x.strip().isdigit()]
                if user.id in user_ids:
                    can_apply = True

            if not can_apply and flow.initiator_departments and user_dept_id:
                dept_ids = [int(x.strip()) for x in flow.initiator_departments.split(
                    ',') if x.strip().isdigit()]
                if user_dept_id in dept_ids:
                    can_apply = True

            if not can_apply and flow.initiator_roles:
                user_roles = []
                if hasattr(user, 'roles'):
                    user_roles = [r.code for r in user.roles.all()]
                elif hasattr(user, 'role_codes'):
                    user_roles = user.role_codes or []
                flow_role_codes = [
                    r.strip() for r in flow.initiator_roles.split(',') if r.strip()]
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
        return JsonResponse({'success': False,
                             'message': '无效的模型类型'},
                            json_dumps_params={'ensure_ascii': False})

    try:
        obj = get_object_or_404(model_class, pk=pk)
        obj.delete()
        return JsonResponse({'success': True, 'message': '删除成功'},
                            json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        return JsonResponse({'success': False,
                             'message': f'删除失败：{str(e)}'},
                            json_dumps_params={'ensure_ascii': False})
