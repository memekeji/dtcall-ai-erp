from apps.common.views_utils import generic_list_view, generic_form_view
from .forms import (
    ContractCategoryForm, ProductCategoryForm, ServiceCategoryForm,
    ServiceForm, SupplierForm, PurchaseCategoryForm, PurchaseItemForm, ProductForm
)
from .models import (
    ContractCategory, ProductCategory, ServiceCategory,
    Product, Service, Supplier, PurchaseCategory, PurchaseItem
)
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.views import View
from rest_framework import serializers, viewsets
from django.core.paginator import Paginator
from .models import Contract, Product, Purchase
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from django.db import models
import json
import logging
import time

from django.contrib.auth.mixins import LoginRequiredMixin

from apps.common.utils import (
    timestamp_to_date, safe_int
)
from apps.common.constants import ApiResponseCode, CommonConstant

logger = logging.getLogger(__name__)

try:
    FINANCE_MODULE_AVAILABLE = True
except ImportError:
    FINANCE_MODULE_AVAILABLE = False

try:
    CUSTOMER_MODULE_AVAILABLE = True
except ImportError:
    CUSTOMER_MODULE_AVAILABLE = False


# ==================== API ViewSets ====================

class ContractCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractCategory
        fields = [
            'id',
            'name',
            'code',
            'parent',
            'description',
            'template_path',
            'sort_order',
            'is_active',
            'created_at']


class ContractCategoryViewSet(viewsets.ModelViewSet):
    queryset = ContractCategory.objects.all()
    serializer_class = ContractCategorySerializer


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = [
            'id',
            'name',
            'code',
            'parent',
            'description',
            'sort_order',
            'is_active',
            'created_at']


class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = [
            'id',
            'name',
            'code',
            'parent',
            'description',
            'sort_order',
            'is_active',
            'created_at']


class ServiceCategoryViewSet(viewsets.ModelViewSet):
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='cate.title', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'code',
            'cate',
            'category_name',
            'name',
            'specs',
            'unit',
            'price',
            'remark',
            'create_time',
            'update_time',
            'delete_time']


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class ServiceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Service
        fields = [
            'id',
            'code',
            'name',
            'category',
            'category_name',
            'unit',
            'price',
            'duration',
            'description',
            'requirements',
            'is_active',
            'created_at']


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            'id',
            'name',
            'code',
            'contact_person',
            'contact_phone',
            'contact_email',
            'address',
            'tax_number',
            'bank_account',
            'bank_name',
            'credit_level',
            'business_scope',
            'is_active',
            'created_at']


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer


class PurchaseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseCategory
        fields = [
            'id',
            'name',
            'code',
            'parent',
            'description',
            'sort_order',
            'is_active',
            'created_at']


class PurchaseCategoryViewSet(viewsets.ModelViewSet):
    queryset = PurchaseCategory.objects.all()
    serializer_class = PurchaseCategorySerializer


class PurchaseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseItem
        fields = [
            'id',
            'name',
            'code',
            'category',
            'specification',
            'unit',
            'reference_price',
            'supplier',
            'description',
            'is_active',
            'created_at']


class PurchaseItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseItem.objects.all()
    serializer_class = PurchaseItemSerializer


class ProductView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/product_list.html')

    def get_data_list(self, request):
        params = request.POST.dict() if request.method == 'POST' else request.GET.dict()
        queryset = Product.objects.select_related('cate').filter(delete_time__isnull=True)

        if 'keywords' in params:
            queryset = queryset.filter(
                Q(name__icontains=params['keywords']) |
                Q(code__icontains=params['keywords'])
            )

        if 'cate_id' in params:
            queryset = queryset.filter(cate_id=params['cate_id'])

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
        order_by = params.get('order_field', '-id')

        paginator = Paginator(queryset.order_by(order_by), limit)
        page_obj = paginator.get_page(page)

        data = []
        for product in page_obj:
            data.append({
                'id': product.id,
                'name': product.name or '',
                'code': product.code or '',
                'category': product.cate.title if product.cate else '',
                'specification': product.specs or '',
                'unit': product.unit or '',
                'price': str(product.price) if product.price else '0',
                'sort_order': 0,
                'is_active': True,
                'created_at': product.create_time.strftime('%Y-%m-%d %H:%M:%S') if product.create_time else ''
            })

        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })


class ProductAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        form = ProductForm()
        return render(request, 'contract/product_form.html', {'form': form, 'object': None})

    def post(self, request):
        form = ProductForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})

        try:
            obj = form.save(commit=False)
            if hasattr(obj, 'admin_id') and getattr(obj, 'admin_id', None) in [None, 0, '']:
                obj.admin = request.user
            obj.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'添加产品失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class ProductDetailView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, id):
        product = get_object_or_404(Product, id=id)
        form = ProductForm(instance=product)
        return render(request, 'contract/product_form.html', {'form': form, 'object': product})

    def post(self, request, id):
        product = get_object_or_404(Product, id=id)
        form = ProductForm(request.POST, instance=product)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})

        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存产品失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class ServicesView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/service_list.html')

    def get_data_list(self, request):
        params = request.POST.dict() if request.method == 'POST' else request.GET.dict()
        queryset = Service.objects.select_related('category').all()

        search = params.get('search') or params.get('keywords')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

        paginator = Paginator(queryset.order_by('-created_at'), limit)
        page_obj = paginator.get_page(page)

        data = []
        for service in page_obj:
            data.append({
                'id': service.id,
                'name': service.name or '',
                'code': service.code or '',
                'price': str(service.price) if service.price else '0',
                'unit': service.unit or '',
                'category': service.category.name if service.category else '',
                'description': service.description or '',
                'sort_order': 0,
                'is_active': bool(service.is_active),
                'created_at': service.created_at.strftime('%Y-%m-%d %H:%M:%S') if service.created_at else ''
            })

        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })


class ServicesAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        form = ServiceForm()
        return render(request, 'contract/service_form.html', {'form': form, 'object': None})

    def post(self, request):
        form = ServiceForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})

        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存服务失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class ServicesDetailView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, id):
        service = get_object_or_404(Service, id=id)
        form = ServiceForm(instance=service)
        return render(request, 'contract/service_form.html', {'form': form, 'object': service})

    def post(self, request, id):
        service = get_object_or_404(Service, id=id)
        form = ServiceForm(request.POST, instance=service)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})

        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存服务失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class PurchaseView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/purchase_list.html')

    def get_data_list(self, request):
        params = request.POST.dict() if request.method == 'POST' else request.GET.dict()
        queryset = Purchase.objects.filter(delete_time__isnull=True)

        if 'keywords' in params:
            queryset = queryset.filter(
                Q(name__icontains=params['keywords']) |
                Q(code__icontains=params['keywords'])
            )

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

        paginator = Paginator(queryset.order_by('-create_time'), limit)
        page_obj = paginator.get_page(page)

        data = []
        for purchase in page_obj:
            data.append({
                'id': purchase.id,
                'name': purchase.name or '',
                'code': purchase.code or '',
                'customer': purchase.customer or '',
                'cost': str(purchase.cost) if purchase.cost else '0',
                'status': purchase.check_status,
                'create_time': timestamp_to_date(purchase.create_time),
            })

        return JsonResponse({
            'code': ApiResponseCode.CODE_SUCCESS,
            'msg': 'success',
            'count': paginator.count,
            'data': data
        })


class PurchaseAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return render(request,
                      'contract/purchase_add.html',
                      {'purchase': None})

    def post(self, request):
        params = request.POST.dict()
        params['admin_id'] = request.user.id

        try:
            Purchase.objects.create(**params)
            logger.info(f"用户 {request.user.id} 添加了采购合同")
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '添加成功'
            })
        except Exception as e:
            logger.error(f'添加采购合同失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': ApiResponseCode.CODE_ERROR,
                'msg': str(e)
            })


class PurchaseDetailView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, id):
        purchase = get_object_or_404(Purchase, id=id)
        return render(request,
                      'contract/purchase_add.html',
                      {'purchase': purchase})


class ArchiveListView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/archive_list.html')

    def get_data_list(self, request):
        page = safe_int(request.GET.get('page'), 1)
        limit = safe_int(
            request.GET.get('limit'),
            CommonConstant.DEFAULT_PAGE_SIZE)
        search_code = request.GET.get('code', '')
        search_date = request.GET.get('archive_date', '')

        queryset = Contract.objects.select_related('customer_id', 'cate', 'admin', 'sign_uid', 'belong_uid').filter(
            delete_time=CommonConstant.DELETE_TIME_ZERO,
            archive_time__gt=CommonConstant.DELETE_TIME_ZERO
        )

        if search_code:
            queryset = queryset.filter(code__icontains=search_code)

        if search_date and ' - ' in search_date:
            start_date, end_date = search_date.split(' - ')
            start_timestamp = int(
                timezone.datetime.strptime(
                    start_date, '%Y-%m-%d').timestamp())
            end_timestamp = int(
                timezone.datetime.strptime(
                    end_date + ' 23:59:59',
                    '%Y-%m-%d %H:%M:%S').timestamp())
            queryset = queryset.filter(
                archive_time__gte=start_timestamp,
                archive_time__lte=end_timestamp
            )

        total = queryset.count()
        start = (page - 1) * limit
        end = start + limit
        contracts = queryset.order_by('-archive_time')[start:end]

        data_list = []
        for contract in contracts:
            data_list.append({
                'id': contract.id,
                'code': contract.code or '',
                'name': contract.name or '',
                'customer': contract.customer or '',
                'cost': str(contract.cost) if contract.cost else '0',
                'archive_time': timestamp_to_date(contract.archive_time),
                'archive_uid': contract.archive_uid or '',
                'create_time': contract.create_time.strftime('%Y-%m-%d %H:%M')
            })

        return JsonResponse({
            'code': ApiResponseCode.CODE_SUCCESS,
            'msg': 'success',
            'count': total,
            'data': data_list
        })

    def post(self, request):
        params = request.POST.dict()
        queryset = Contract.objects.filter(
            archive_time__gt=CommonConstant.DELETE_TIME_ZERO,
            delete_time=CommonConstant.DELETE_TIME_ZERO
        )

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
        order_by = params.get('order_field', '-archive_time')

        paginator = Paginator(queryset.order_by(order_by), limit)
        page_obj = paginator.get_page(page)

        return JsonResponse({
            'code': ApiResponseCode.CODE_SUCCESS,
            'msg': 'success',
            'count': paginator.count,
            'data': list(page_obj.object_list.values())
        })


class StopListView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/terminate_list.html')

    def get_data_list(self, request):
        page = safe_int(request.GET.get('page'), 1)
        limit = safe_int(
            request.GET.get('limit'),
            CommonConstant.DEFAULT_PAGE_SIZE)
        search_code = request.GET.get('code', '')
        search_date = request.GET.get('terminate_date', '')

        queryset = Contract.objects.filter(
            delete_time=CommonConstant.DELETE_TIME_ZERO,
            stop_time__gt=CommonConstant.DELETE_TIME_ZERO
        )

        if search_code:
            queryset = queryset.filter(code__icontains=search_code)

        if search_date and ' - ' in search_date:
            start_date, end_date = search_date.split(' - ')
            start_timestamp = int(
                timezone.datetime.strptime(
                    start_date, '%Y-%m-%d').timestamp())
            end_timestamp = int(
                timezone.datetime.strptime(
                    end_date + ' 23:59:59',
                    '%Y-%m-%d %H:%M:%S').timestamp())
            queryset = queryset.filter(
                stop_time__gte=start_timestamp,
                stop_time__lte=end_timestamp
            )

        total = queryset.count()
        start = (page - 1) * limit
        end = start + limit
        contracts = queryset.order_by('-stop_time')[start:end]

        data_list = []
        for contract in contracts:
            data_list.append({
                'id': contract.id,
                'code': contract.code or '',
                'name': contract.name or '',
                'customer': contract.customer or '',
                'cost': str(contract.cost) if contract.cost else '0',
                'stop_time': timestamp_to_date(contract.stop_time),
                'stop_uid': contract.stop_uid or '',
                'stop_remark': contract.stop_remark or '',
                'create_time': contract.create_time.strftime('%Y-%m-%d %H:%M')
            })

        return JsonResponse({
            'code': ApiResponseCode.CODE_SUCCESS,
            'msg': 'success',
            'count': total,
            'data': data_list
        })

    def post(self, request):
        params = request.POST.dict()
        queryset = Contract.objects.filter(
            stop_time__gt=CommonConstant.DELETE_TIME_ZERO,
            delete_time=CommonConstant.DELETE_TIME_ZERO
        )

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
        order_by = params.get('order_field', '-stop_time')

        paginator = Paginator(queryset.order_by(order_by), limit)
        page_obj = paginator.get_page(page)

        return JsonResponse({
            'code': ApiResponseCode.CODE_SUCCESS,
            'msg': 'success',
            'count': paginator.count,
            'data': list(page_obj.object_list.values())
        })


class VoidListView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/cancel_list.html')

    def get_data_list(self, request):
        page = safe_int(request.GET.get('page'), 1)
        limit = safe_int(
            request.GET.get('limit'),
            CommonConstant.DEFAULT_PAGE_SIZE)
        search_code = request.GET.get('code', '')
        search_date = request.GET.get('cancel_date', '')

        queryset = Contract.objects.filter(
            delete_time=CommonConstant.DELETE_TIME_ZERO,
            void_time__gt=CommonConstant.DELETE_TIME_ZERO
        )

        if search_code:
            queryset = queryset.filter(code__icontains=search_code)

        if search_date and ' - ' in search_date:
            start_date, end_date = search_date.split(' - ')
            start_timestamp = int(
                timezone.datetime.strptime(
                    start_date, '%Y-%m-%d').timestamp())
            end_timestamp = int(
                timezone.datetime.strptime(
                    end_date + ' 23:59:59',
                    '%Y-%m-%d %H:%M:%S').timestamp())
            queryset = queryset.filter(
                void_time__gte=start_timestamp,
                void_time__lte=end_timestamp
            )

        total = queryset.count()
        start = (page - 1) * limit
        end = start + limit
        contracts = queryset.order_by('-void_time')[start:end]

        data_list = []
        for contract in contracts:
            data_list.append({
                'id': contract.id,
                'code': contract.code or '',
                'name': contract.name or '',
                'customer': contract.customer or '',
                'cost': str(contract.cost) if contract.cost else '0',
                'void_time': timestamp_to_date(contract.void_time),
                'void_uid': contract.void_uid or '',
                'void_remark': contract.void_remark or '',
                'create_time': contract.create_time.strftime('%Y-%m-%d %H:%M')
            })

        return JsonResponse({
            'code': ApiResponseCode.CODE_SUCCESS,
            'msg': 'success',
            'count': total,
            'data': data_list
        })

    def post(self, request):
        params = request.POST.dict()
        queryset = Contract.objects.filter(
            void_time__gt=CommonConstant.DELETE_TIME_ZERO,
            delete_time=CommonConstant.DELETE_TIME_ZERO
        )

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
        order_by = params.get('order_field', '-void_time')

        paginator = Paginator(queryset.order_by(order_by), limit)
        page_obj = paginator.get_page(page)

        return JsonResponse({
            'code': ApiResponseCode.CODE_SUCCESS,
            'msg': 'success',
            'count': paginator.count,
            'data': list(page_obj.object_list.values())
        })


class ContractView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/sales_list.html')

    def get_data_list(self, request):
        page = safe_int(request.GET.get('page'), 1)
        limit = safe_int(
            request.GET.get('limit'),
            CommonConstant.DEFAULT_PAGE_SIZE)
        tab = request.GET.get('tab', '0')
        search_code = request.GET.get('code', '')
        search_status = request.GET.get('status', '')

        queryset = Contract.objects.filter(
            delete_time=CommonConstant.DELETE_TIME_ZERO)

        tab_filter_map = {
            '1': ('admin_id', request.user.id),
            '2': ('check_status', 0),
            '3': ('check_status__in', [2, 3]),
        }

        if tab in tab_filter_map:
            field, value = tab_filter_map[tab]
            queryset = queryset.filter(**{field: value})

        if search_code:
            queryset = queryset.filter(code__icontains=search_code)
        if search_status:
            queryset = queryset.filter(check_status=search_status)

        total = queryset.count()
        start = (page - 1) * limit
        end = start + limit
        contracts = queryset.order_by('-create_time')[start:end]

        data_list = []
        for contract in contracts:
            data_list.append({
                'id': contract.id,
                'code': contract.code or '',
                'name': contract.name or '',
                'customer': contract.customer or '',
                'cost': str(contract.cost) if contract.cost else '0',
                'check_status': contract.check_status,
                'create_time': contract.create_time.strftime('%Y-%m-%d %H:%M'),
                'sign_time': timestamp_to_date(contract.sign_time),
                'start_time': timestamp_to_date(contract.start_time),
                'end_time': timestamp_to_date(contract.end_time)
            })

        return JsonResponse({
            'code': ApiResponseCode.CODE_SUCCESS,
            'msg': 'success',
            'count': total,
            'data': data_list
        })

    def post(self, request):
        params = request.POST.dict()
        tab = params.get('tab', '0')
        uid = request.user.id

        queryset = Contract.objects.filter(
            delete_time=CommonConstant.DELETE_TIME_ZERO,
            archive_time=CommonConstant.DELETE_TIME_ZERO,
            stop_time=CommonConstant.DELETE_TIME_ZERO,
            void_time=CommonConstant.DELETE_TIME_ZERO
        )

        if 'keywords' in params:
            queryset = queryset.filter(
                models.Q(name__icontains=params['keywords']) |
                models.Q(code__icontains=params['keywords'])
            )

        if 'types' in params:
            queryset = queryset.filter(types=params['types'])

        if 'cate_id' in params:
            queryset = queryset.filter(cate_id=params['cate_id'])

        if 'check_status' in params:
            queryset = queryset.filter(check_status=params['check_status'])

        if 'sign_time' in params and '~' in params['sign_time']:
            start, end = params['sign_time'].split('~')
            queryset = queryset.filter(
                sign_time__range=(start.strip(), end.strip())
            )

        if 'end_time' in params and '~' in params['end_time']:
            start, end = params['end_time'].split('~')
            queryset = queryset.filter(
                end_time__range=(start.strip(), end.strip())
            )

        if tab == '0' and 'uid' not in params:
            if not request.user.has_perm('contract.admin'):
                queryset = queryset.filter(
                    models.Q(admin_id=uid) |
                    models.Q(check_uids__contains=str(uid))
                )

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
        order_by = params.get('order_field', '-create_time')

        paginator = Paginator(queryset.order_by(order_by), limit)
        page_obj = paginator.get_page(page)

        data = {
            'code': 0,
            'msg': 'success',
            'count': paginator.count,
            'data': list(page_obj.object_list.values())
        }
        return JsonResponse(data, json_dumps_params={'ensure_ascii': False})


class ContractAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return render(request, 'contract/sales/add.html', {'contract': None})

    def post(self, request):
        params = request.POST.dict()
        params['admin_id'] = request.user.id

        try:
            Contract.objects.create(**params)
            logger.info(f"用户 {request.user.id} 添加了合同")
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '添加成功'
            })
        except Exception as e:
            logger.error(f'添加合同失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': ApiResponseCode.CODE_ERROR,
                'msg': str(e)
            })


class ContractDetailView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, id):
        contract = get_object_or_404(Contract, id=id)
        return render(request, 'contract/view.html', {'contract': contract})


class ContractUpdateView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request, id):
        try:
            data = json.loads(request.body)
            contract = get_object_or_404(Contract, id=id)

            for key, value in data.items():
                if key not in ['id']:
                    setattr(contract, key, value)

            contract.save()
            logger.info(f"用户 {request.user.id} 更新了合同: {id}")

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '更新成功'
            })
        except Exception as e:
            logger.error(f'更新合同失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': ApiResponseCode.CODE_ERROR,
                'msg': str(e)
            })


class ContractDeleteView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request):
        try:
            data = json.loads(request.body)
            contract_id = data.get('id')

            if not contract_id:
                return JsonResponse({
                    'code': ApiResponseCode.CODE_ERROR,
                    'msg': '缺少合同ID'
                })

            contract = get_object_or_404(Contract, id=contract_id)
            contract.delete()

            logger.info(f"用户 {request.user.id} 删除了合同: {contract_id}")

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '删除成功'
            })
        except Exception as e:
            logger.error(f'删除合同失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': ApiResponseCode.CODE_ERROR,
                'msg': str(e)
            })


class ContractArchiveView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request):
        try:
            data = json.loads(request.body)
            contract_id = data.get('id')
            action = data.get('action', 'archive')

            if not contract_id:
                return JsonResponse({
                    'code': ApiResponseCode.CODE_ERROR,
                    'msg': '缺少合同ID'
                })

            contract = get_object_or_404(Contract, id=contract_id)
            current_time = int(time.time())

            if action == 'archive':
                contract.archive_time = current_time
                contract.archive_uid = request.user.id
                msg = '归档成功'
            else:
                contract.archive_time = 0
                contract.archive_uid = 0
                msg = '取消归档成功'

            contract.save()
            logger.info(
                f"用户 {request.user.id} 对合同 {contract_id} 执行了{action}操作")

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': msg
            })
        except Exception as e:
            logger.error(f'归档操作失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': ApiResponseCode.CODE_ERROR,
                'msg': str(e)
            })


class ContractTerminateView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request):
        try:
            data = json.loads(request.body)
            contract_id = data.get('id')
            remark = data.get('remark', '')

            if not contract_id:
                return JsonResponse({
                    'code': ApiResponseCode.CODE_ERROR,
                    'msg': '缺少合同ID'
                })

            contract = get_object_or_404(Contract, id=contract_id)
            contract.stop_time = int(time.time())
            contract.stop_uid = request.user.id
            contract.stop_remark = remark
            contract.save()

            logger.info(f"用户 {request.user.id} 终止了合同: {contract_id}")

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '终止成功'
            })
        except Exception as e:
            logger.error(f'终止合同失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': ApiResponseCode.CODE_ERROR,
                'msg': str(e)
            })


class ContractCancelView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request):
        try:
            data = json.loads(request.body)
            contract_id = data.get('id')
            remark = data.get('remark', '')

            if not contract_id:
                return JsonResponse({
                    'code': ApiResponseCode.CODE_ERROR,
                    'msg': '缺少合同ID'
                })

            contract = get_object_or_404(Contract, id=contract_id)
            contract.void_time = int(time.time())
            contract.void_uid = request.user.id
            contract.void_remark = remark
            contract.save()

            logger.info(f"用户 {request.user.id} 作废了合同: {contract_id}")

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '作废成功'
            })
        except Exception as e:
            logger.error(f'作废合同失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': ApiResponseCode.CODE_ERROR,
                'msg': str(e)
            })


@login_required
def contract_category_list(request):
    return generic_list_view(
        request,
        ContractCategory,
        'contract/contract_category_list.html',
        search_fields=['name', 'code']
    )


@login_required
def contract_category_form(request, pk=None):
    return generic_form_view(
        request,
        ContractCategory,
        ContractCategoryForm,
        'contract/contract_category_form.html',
        'contract:category_list',
        pk
    )


@login_required
def product_category_list(request):
    return generic_list_view(
        request,
        ProductCategory,
        'contract/product_category_list.html',
        search_fields=['name', 'code']
    )


@login_required
def product_category_form(request, pk=None):
    return generic_form_view(
        request,
        ProductCategory,
        ProductCategoryForm,
        'contract/product_category_form.html',
        'contract:product_category_list',
        pk
    )


@login_required
def service_category_list(request):
    return generic_list_view(
        request,
        ServiceCategory,
        'contract/service_category_list.html',
        search_fields=['name', 'code']
    )


@login_required
def service_category_form(request, pk=None):
    return generic_form_view(
        request,
        ServiceCategory,
        ServiceCategoryForm,
        'contract/service_category_form.html',
        'contract:service_category_list',
        pk
    )


@login_required
def service_list(request):
    return generic_list_view(
        request,
        Service,
        'contract/service_list.html',
        search_fields=['name', 'code']
    )


@login_required
def service_form(request, pk=None):
    return generic_form_view(
        request,
        Service,
        ServiceForm,
        'contract/service_form.html',
        'contract:service_list',
        pk
    )


@login_required
def supplier_list(request):
    return generic_list_view(
        request,
        Supplier,
        'contract/supplier_list.html',
        search_fields=['name', 'code', 'contact_person']
    )


@login_required
def supplier_form(request, pk=None):
    return generic_form_view(
        request,
        Supplier,
        SupplierForm,
        'contract/supplier_form.html',
        'contract:supplier_list',
        pk
    )


@login_required
def purchase_category_list(request):
    return generic_list_view(
        request,
        PurchaseCategory,
        'contract/purchase_category_list.html',
        search_fields=['name', 'code']
    )


@login_required
def purchase_category_form(request, pk=None):
    return generic_form_view(
        request,
        PurchaseCategory,
        PurchaseCategoryForm,
        'contract/purchase_category_form.html',
        'contract:purchase_category_list',
        pk
    )


@login_required
def purchase_item_list(request):
    return generic_list_view(
        request,
        PurchaseItem,
        'contract/purchase_item_list.html',
        search_fields=['name', 'code']
    )


@login_required
def purchase_item_form(request, pk=None):
    return generic_form_view(
        request,
        PurchaseItem,
        PurchaseItemForm,
        'contract/purchase_item_form.html',
        'contract:purchase_item_list',
        pk
    )


@login_required
def contract_category_children(request, parent_id=None):
    try:
        if parent_id is None or parent_id == '0':
            categories = ContractCategory.objects.filter(
                parent__isnull=True,
                is_active=True
            ).order_by('sort_order', 'id')
        else:
            categories = ContractCategory.objects.filter(
                parent_id=parent_id,
                is_active=True
            ).order_by('sort_order', 'id')

        data = []
        for category in categories:
            has_children = ContractCategory.objects.filter(
                parent_id=category.id,
                is_active=True
            ).exists()

            data.append({
                'id': category.id,
                'name': category.name,
                'code': category.code,
                'has_children': has_children
            })

        return JsonResponse({
            'code': 0,
            'msg': '',
            'data': data
        })

    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'获取分类失败: {str(e)}'})


class ContractCategoryView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/contract_category_list.html')

    def get_data_list(self, request):
        params = request.GET.dict()
        queryset = ContractCategory.objects.all()

        search = params.get('search') or params.get('keywords')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

        paginator = Paginator(queryset.order_by('-created_at'), limit)
        page_obj = paginator.get_page(page)

        data = []
        for category in page_obj:
            data.append({
                'id': category.id,
                'name': category.name,
                'code': category.code,
                'parent': category.parent.name if category.parent else '',
                'description': category.description or '',
                'template_path': category.template_path or '',
                'sort_order': category.sort_order or 0,
                'is_active': bool(category.is_active),
                'created_at': category.created_at.strftime('%Y-%m-%d %H:%M:%S') if category.created_at else ''
            })

        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })


class ContractCategoryAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request):
        form = ContractCategoryForm()
        return render(request, 'contract/contract_category_form.html', {'form': form, 'object': None})

    def post(self, request):
        form = ContractCategoryForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存合同分类失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class ContractCategoryEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request, id):
        category = get_object_or_404(ContractCategory, id=id)
        form = ContractCategoryForm(instance=category)
        return render(request, 'contract/contract_category_form.html', {'form': form, 'object': category})

    def post(self, request, id):
        category = get_object_or_404(ContractCategory, id=id)
        form = ContractCategoryForm(request.POST, instance=category)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存合同分类失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class ProductCategoryView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/product_category_list.html')

    def get_data_list(self, request):
        params = request.GET.dict()
        queryset = ProductCategory.objects.all()

        search = params.get('search') or params.get('keywords')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

        paginator = Paginator(queryset.order_by('-created_at'), limit)
        page_obj = paginator.get_page(page)

        data = []
        for cate in page_obj:
            data.append({
                'id': cate.id,
                'name': cate.name,
                'code': cate.code,
                'parent': cate.parent.name if cate.parent else '',
                'description': cate.description or '',
                'sort_order': cate.sort_order or 0,
                'is_active': bool(cate.is_active),
                'created_at': cate.created_at.strftime('%Y-%m-%d %H:%M:%S') if cate.created_at else ''
            })

        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })


class ProductCategoryAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request):
        form = ProductCategoryForm()
        return render(request, 'contract/product_category_form.html', {'form': form, 'object': None})

    def post(self, request):
        form = ProductCategoryForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存产品分类失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class ProductCategoryEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request, id):
        category = get_object_or_404(ProductCategory, id=id)
        form = ProductCategoryForm(instance=category)
        return render(request, 'contract/product_category_form.html', {'form': form, 'object': category})

    def post(self, request, id):
        category = get_object_or_404(ProductCategory, id=id)
        form = ProductCategoryForm(request.POST, instance=category)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存产品分类失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class ServiceCategoryView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/service_category_list.html')

    def get_data_list(self, request):
        params = request.GET.dict()
        queryset = ServiceCategory.objects.all()

        search = params.get('search') or params.get('keywords')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

        paginator = Paginator(queryset.order_by('-created_at'), limit)
        page_obj = paginator.get_page(page)

        data = []
        for cate in page_obj:
            data.append({
                'id': cate.id,
                'name': cate.name,
                'code': cate.code,
                'parent': cate.parent.name if cate.parent else '',
                'description': cate.description or '',
                'sort_order': cate.sort_order or 0,
                'is_active': bool(cate.is_active),
                'created_at': cate.created_at.strftime('%Y-%m-%d %H:%M:%S') if cate.created_at else ''
            })

        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })


class ServiceCategoryAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request):
        form = ServiceCategoryForm()
        return render(request, 'contract/service_category_form.html', {'form': form, 'object': None})

    def post(self, request):
        form = ServiceCategoryForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存服务分类失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class ServiceCategoryEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request, id):
        category = get_object_or_404(ServiceCategory, id=id)
        form = ServiceCategoryForm(instance=category)
        return render(request, 'contract/service_category_form.html', {'form': form, 'object': category})

    def post(self, request, id):
        category = get_object_or_404(ServiceCategory, id=id)
        form = ServiceCategoryForm(request.POST, instance=category)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存服务分类失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class SupplierView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/supplier_list.html')

    def get_data_list(self, request):
        params = request.GET.dict()
        queryset = Supplier.objects.all()

        search = params.get('search') or params.get('keywords')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(contact_person__icontains=search)
            )

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

        paginator = Paginator(queryset.order_by('-created_at'), limit)
        page_obj = paginator.get_page(page)

        data = []
        for supplier in page_obj:
            data.append({
                'id': supplier.id,
                'name': supplier.name or '',
                'code': supplier.code or '',
                'contact': supplier.contact_person or '',
                'phone': supplier.contact_phone or '',
                'email': supplier.contact_email or '',
                'address': supplier.address or '',
                'is_active': bool(supplier.is_active),
                'created_at': supplier.created_at.strftime('%Y-%m-%d %H:%M:%S') if supplier.created_at else ''
            })

        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })


class SupplierAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request):
        form = SupplierForm()
        return render(request, 'contract/supplier_form.html', {'form': form, 'object': None})

    def post(self, request):
        form = SupplierForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存供应商失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class SupplierEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request, id):
        supplier = get_object_or_404(Supplier, id=id)
        form = SupplierForm(instance=supplier)
        return render(request, 'contract/supplier_form.html', {'form': form, 'object': supplier})

    def post(self, request, id):
        supplier = get_object_or_404(Supplier, id=id)
        form = SupplierForm(request.POST, instance=supplier)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存供应商失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class PurchaseCategoryView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/purchase_category_list.html')

    def get_data_list(self, request):
        params = request.GET.dict()
        queryset = PurchaseCategory.objects.all()

        search = params.get('search') or params.get('keywords')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

        paginator = Paginator(queryset.order_by('-created_at'), limit)
        page_obj = paginator.get_page(page)

        data = []
        for cate in page_obj:
            data.append({
                'id': cate.id,
                'name': cate.name or '',
                'code': cate.code or '',
                'parent': cate.parent.name if cate.parent else '',
                'description': cate.description or '',
                'sort_order': cate.sort_order or 0,
                'is_active': bool(cate.is_active),
                'created_at': cate.created_at.strftime('%Y-%m-%d %H:%M:%S') if cate.created_at else ''
            })

        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })


class PurchaseCategoryAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request):
        form = PurchaseCategoryForm()
        return render(request, 'contract/purchase_category_form.html', {'form': form, 'object': None})

    def post(self, request):
        form = PurchaseCategoryForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存采购分类失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class PurchaseCategoryEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request, id):
        category = get_object_or_404(PurchaseCategory, id=id)
        form = PurchaseCategoryForm(instance=category)
        return render(request, 'contract/purchase_category_form.html', {'form': form, 'object': category})

    def post(self, request, id):
        category = get_object_or_404(PurchaseCategory, id=id)
        form = PurchaseCategoryForm(request.POST, instance=category)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存采购分类失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class PurchaseItemView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/purchase_item_list.html')

    def get_data_list(self, request):
        params = request.GET.dict()
        queryset = PurchaseItem.objects.all()

        search = params.get('search') or params.get('keywords')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))

        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
        paginator = Paginator(queryset.order_by('-created_at'), limit)
        page_obj = paginator.get_page(page)

        data = []
        for item in page_obj:
            data.append({
                'id': item.id,
                'name': item.name or '',
                'code': item.code or '',
                'category': item.category.name if item.category else '',
                'specification': item.specification or '',
                'unit': item.unit or '',
                'reference_price': str(item.reference_price) if item.reference_price else '0',
                'supplier': item.supplier.name if item.supplier else '',
                'is_active': bool(item.is_active),
                'created_at': item.created_at.strftime('%Y-%m-%d %H:%M:%S') if item.created_at else ''
            })

        return JsonResponse({'code': 0, 'msg': '', 'count': paginator.count, 'data': data})


class PurchaseItemAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request):
        form = PurchaseItemForm()
        return render(request, 'contract/purchase_item_form.html', {'form': form, 'object': None})

    def post(self, request):
        form = PurchaseItemForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存采购品失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class PurchaseItemEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'

    def get(self, request, id):
        item = get_object_or_404(PurchaseItem, id=id)
        form = PurchaseItemForm(instance=item)
        return render(request, 'contract/purchase_item_form.html', {'form': form, 'object': item})

    def post(self, request, id):
        item = get_object_or_404(PurchaseItem, id=id)
        form = PurchaseItemForm(request.POST, instance=item)
        if not form.is_valid():
            return JsonResponse({'code': 1, 'msg': '表单验证失败', 'errors': form.errors})
        try:
            form.save()
            return JsonResponse({'code': 0, 'msg': '保存成功'})
        except Exception as e:
            logger.error(f'保存采购品失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': str(e)})


class ServiceListView(ServicesView):
    pass


class ServiceListAddView(ServicesAddView):
    pass


class ServiceListEditView(ServicesDetailView):
    pass
