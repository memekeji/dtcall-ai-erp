from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import datetime


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

    time_field = 'id'
    try:
        model_class._meta.get_field('create_time')
        time_field = 'create_time'
    except BaseException:
        try:
            model_class._meta.get_field('created_at')
            time_field = 'created_at'
        except BaseException:
            pass

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

            if hasattr(obj, 'name'):
                obj_dict['name'] = obj.name
            if hasattr(obj, 'title'):
                obj_dict['title'] = obj.title
            if hasattr(obj, 'code'):
                obj_dict['code'] = obj.code
            if hasattr(obj, 'status'):
                obj_dict['status'] = obj.status
            if hasattr(obj, 'is_active'):
                obj_dict['is_active'] = obj.is_active

            if hasattr(obj, 'created_at'):
                obj_dict['created_at'] = obj.created_at.strftime(
                    '%Y-%m-%d %H:%M:%S')
            elif hasattr(obj, 'create_time'):
                if isinstance(obj.create_time, (datetime,)):
                    obj_dict['create_time'] = obj.create_time.strftime(
                        '%Y-%m-%d %H:%M:%S')

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
        'delete_url': f"/delete/{model_class._meta.model_name}/{{id}}/",
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


def generic_delete_item(request, model_map, model_name, pk):
    from django.http import JsonResponse

    if request.method == 'POST':
        model_class = model_map.get(model_name)
        if not model_class:
            return JsonResponse({'success': False, 'message': '无效的模型类型'})

        try:
            obj = get_object_or_404(model_class, pk=pk)
            obj.delete()
            return JsonResponse({'success': True, 'message': '删除成功'})
        except Exception as e:
            return JsonResponse(
                {'success': False, 'message': f'删除失败：{str(e)}'})

    return JsonResponse({'success': False, 'message': '无效的请求方法'})
