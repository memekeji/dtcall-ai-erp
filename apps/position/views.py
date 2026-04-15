from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from apps.user.models.position import Position
from .forms import PositionForm
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from apps.common.services import CommonService


class PositionListView(LoginRequiredMixin, ListView):
    model = Position
    template_name = 'position/new_list.html'
    context_object_name = 'positions'

    def get_queryset(self):
        return Position.objects.all().order_by('sort')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('岗位职称管理')
        return context


class PositionCreateView(LoginRequiredMixin, CreateView):
    model = Position
    form_class = PositionForm
    template_name = 'position/new_form.html'
    success_url = reverse_lazy('position_list')
    extra_context = {'title': _('添加岗位'), 'is_edit': False}

    def form_valid(self, form):
        # 保存表单数据
        self.object = form.save()

        # 检查是否为AJAX请求（大小写不敏感）
        is_ajax = self.request.headers.get(
            'x-requested-with', '').lower() == 'xmlhttprequest'
        if is_ajax:
            return JsonResponse({'code': 0, 'msg': '岗位创建成功'})

        # 非AJAX请求，使用默认行为
        return super().form_valid(form)

    def form_invalid(self, form):
        # 检查是否为AJAX请求（大小写不敏感）
        is_ajax = self.request.headers.get(
            'x-requested-with', '').lower() == 'xmlhttprequest'
        if is_ajax:
            # 获取表单错误信息
            errors = []
            for field, error_list in form.errors.items():
                for error in error_list:
                    errors.append(f'{field}: {error}')
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': errors})

        # 非AJAX请求，使用默认行为
        return super().form_invalid(form)


class PositionUpdateView(LoginRequiredMixin, UpdateView):
    model = Position
    form_class = PositionForm
    template_name = 'position/new_form.html'
    success_url = reverse_lazy('position_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('编辑岗位')
        context['is_edit'] = True
        context['position_id'] = self.object.id
        return context

    def form_valid(self, form):
        # 保存表单数据
        self.object = form.save()

        # 检查是否为AJAX请求（大小写不敏感）
        is_ajax = self.request.headers.get(
            'x-requested-with', '').lower() == 'xmlhttprequest'
        if is_ajax:
            return JsonResponse({'code': 0, 'msg': '岗位信息更新成功'})

        # 非AJAX请求，使用默认行为
        return super().form_valid(form)

    def form_invalid(self, form):
        # 检查是否为AJAX请求（大小写不敏感）
        is_ajax = self.request.headers.get(
            'x-requested-with', '').lower() == 'xmlhttprequest'
        if is_ajax:
            # 获取表单错误信息
            errors = []
            for field, error_list in form.errors.items():
                for error in error_list:
                    errors.append(f'{field}: {error}')
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': errors})

        # 非AJAX请求，使用默认行为
        return super().form_invalid(form)


class PositionDeleteView(LoginRequiredMixin, DeleteView):
    model = Position
    success_url = reverse_lazy('position_list')

    # 只支持AJAX请求


def position_list_data(request):
    """岗位列表数据API"""
    keyword = request.GET.get('keyword', '').strip()
    status = request.GET.get('status', '')
    page = int(request.GET.get('page', 1))
    page_size = CommonService.get_page_size(request, 20)

    positions = Position.objects.all().order_by('sort')

    if keyword:
        positions = positions.filter(title__icontains=keyword)

    if status != '':
        positions = positions.filter(status=status)

    total_count = positions.count()

    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    positions_paginated = positions[start_index:end_index]

    data = {
        'code': 0,
        'msg': '',
        'count': total_count,
        'data': [{
            'id': pos.id,
            'title': pos.title,
            'role': None,
            'hourly_rate': 0,
            'status': pos.status,
            'sort': pos.sort,
            'desc': pos.desc or '',
            'create_time': pos.create_time.strftime('%Y-%m-%d %H:%M:%S') if pos.create_time else ''
        } for pos in positions_paginated]
    }

    return JsonResponse(data)


def position_detail_api(request, pk):
    """获取岗位详情API"""
    try:
        position = Position.objects.get(id=pk)
        return JsonResponse({
            'code': 0,
            'msg': '获取成功',
            'data': {
                'id': position.id,
                'title': position.title,
                'did': position.did,
                'desc': position.desc or '',
                'sort': position.sort,
                'status': position.status,
                'create_time': position.create_time.strftime('%Y-%m-%d %H:%M:%S') if position.create_time else ''
            }
        })
    except Position.DoesNotExist:
        return JsonResponse({'code': 1, 'msg': '岗位不存在', 'data': None})


@csrf_exempt
def position_disable(request):
    """禁用岗位"""
    if request.method == 'POST':
        position_id = request.POST.get('id')
        try:
            position = Position.objects.get(id=position_id)
            position.status = 0
            position.save()
            return JsonResponse({'code': 0, 'msg': '岗位已禁用'})
        except Position.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '岗位不存在'})
    return JsonResponse({'code': 1, 'msg': '请求方式错误'})


@csrf_exempt
def position_enable(request):
    """启用岗位"""
    if request.method == 'POST':
        position_id = request.POST.get('id')
        try:
            position = Position.objects.get(id=position_id)
            position.status = 1
            position.save()
            return JsonResponse({'code': 0, 'msg': '岗位已启用'})
        except Position.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '岗位不存在'})
    return JsonResponse({'code': 1, 'msg': '请求方式错误'})
