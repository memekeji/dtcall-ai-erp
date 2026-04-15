"""
通用视图工具模块
提供通用的列表视图、表单视图等功能
"""
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from typing import Dict, Any


class GenericListView(LoginRequiredMixin, ListView):
    """通用列表视图"""

    model = None
    template_name = None
    context_object_name = 'objects'
    paginate_by = 20
    search_fields = []
    filter_fields = {}

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.GET.get('search', '')
        if search and self.search_fields:
            q_objects = Q()
            for field in self.search_fields:
                q_objects |= Q(**{f"{field}__icontains": search})
            queryset = queryset.filter(q_objects)

        for field, lookup in self.filter_fields.items():
            value = self.request.GET.get(field, '')
            if value:
                queryset = queryset.filter(**{lookup: value})

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['search'] = self.request.GET.get('search', '')
        context.update(self.filter_fields)

        return context


class GenericCreateView(LoginRequiredMixin, CreateView):
    """通用创建视图"""

    model = None
    form_class = None
    template_name = None
    success_url = None

    def form_valid(self, form):
        self.object = form.save()

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {'code': 200, 'msg': '创建成功', 'data': {'id': self.object.id}})

        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {'code': 400, 'msg': '创建失败', 'errors': form.errors})

        return super().form_invalid(form)


class GenericUpdateView(LoginRequiredMixin, UpdateView):
    """通用更新视图"""

    model = None
    form_class = None
    template_name = None
    success_url = None

    def form_valid(self, form):
        self.object = form.save()

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {'code': 200, 'msg': '更新成功', 'data': {'id': self.object.id}})

        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {'code': 400, 'msg': '更新失败', 'errors': form.errors})

        return super().form_invalid(form)


class GenericDeleteView(LoginRequiredMixin, DeleteView):
    """通用删除视图"""

    model = None
    success_url = None

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()

        return JsonResponse({'code': 200, 'msg': '删除成功'})


class GenericDetailView(LoginRequiredMixin, DetailView):
    """通用详情视图"""

    model = None
    template_name = None
    context_object_name = 'object'


class GenericAPIView(LoginRequiredMixin, View):
    """通用API视图"""

    model = None
    serializer_class = None
    search_fields = []
    filter_fields = {}

    def get_queryset(self):
        queryset = self.model.objects.all()

        search = self.request.GET.get('search', '')
        if search and self.search_fields:
            q_objects = Q()
            for field in self.search_fields:
                q_objects |= Q(**{f"{field}__icontains": search})
            queryset = queryset.filter(q_objects)

        for field, lookup in self.filter_fields.items():
            value = self.request.GET.get(field, '')
            if value:
                queryset = queryset.filter(**{lookup: value})

        return queryset

    def get(self, request, *args, **kwargs):
        pk = kwargs.get('pk')

        if pk:
            return self.get_detail(request, pk)
        else:
            return self.get_list(request)

    def get_list(self, request):
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))

        queryset = self.get_queryset()
        total = queryset.count()
        objects = queryset[(page - 1) * limit:page * limit]

        data = []
        for obj in objects:
            data.append(self.serialize_object(obj))

        return JsonResponse({
            'code': 200,
            'msg': 'success',
            'data': {
                'total': total,
                'items': data
            }
        })

    def get_detail(self, request, pk):
        try:
            obj = self.model.objects.get(id=pk)
            return JsonResponse({
                'code': 200,
                'msg': 'success',
                'data': self.serialize_object(obj)
            })
        except self.model.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'msg': 'Object not found'
            })

    def serialize_object(self, obj) -> Dict[str, Any]:
        """序列化对象"""
        if self.serializer_class:
            return self.serializer_class(obj)
        else:
            return {
                'id': obj.id,
                'name': str(obj)
            }
