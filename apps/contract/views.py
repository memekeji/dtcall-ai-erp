from django.shortcuts import render, get_object_or_404
from django.views import View
from rest_framework import serializers, viewsets
from django.core.paginator import Paginator
from .models import Contract, ContractCate, Product, ProductCate, Services, Purchase
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from django.db import models
import json
import logging
import time

from django.contrib.auth.mixins import LoginRequiredMixin

from apps.common.utils import (
    timestamp_to_date, safe_int, build_error_response
)
from apps.common.constants import ApiResponseCode, CommonConstant

logger = logging.getLogger(__name__)

try:
    from apps.finance.models import Invoice, Income, Payment
    FINANCE_MODULE_AVAILABLE = True
except ImportError:
    FINANCE_MODULE_AVAILABLE = False

try:
    from apps.customer.models import Customer
    CUSTOMER_MODULE_AVAILABLE = True
except ImportError:
    CUSTOMER_MODULE_AVAILABLE = False


# ==================== API ViewSets ====================

class ContractCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractCate
        fields = ['id', 'name', 'code', 'parent', 'sort', 'status', 'delete_time', 'create_time', 'update_time']

class ContractCategoryViewSet(viewsets.ModelViewSet):
    queryset = ContractCate.objects.all()
    serializer_class = ContractCategorySerializer

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCate
        fields = ['id', 'name', 'code', 'parent', 'sort', 'status', 'delete_time', 'create_time', 'update_time']

class ProductCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProductCate.objects.all()
    serializer_class = ProductCategorySerializer

class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Services
        fields = ['id', 'name', 'code', 'parent', 'sort', 'status', 'delete_time', 'create_time', 'update_time']

class ServiceCategoryViewSet(viewsets.ModelViewSet):
    queryset = Services.objects.all()
    serializer_class = ServiceCategorySerializer

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='cate.name', read_only=True)
    
    class Meta:
        model = Product
        fields = ['id', 'code', 'title', 'cate', 'category_name', 'spec', 'unit', 'price', 'status', 'delete_time', 'create_time', 'update_time']

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class ServiceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='cate.name', read_only=True)
    
    class Meta:
        model = Services
        fields = ['id', 'code', 'title', 'cate', 'category_name', 'spec', 'unit', 'price', 'status', 'delete_time', 'create_time', 'update_time']

class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Services.objects.all()
    serializer_class = ServiceSerializer

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Purchase
        fields = ['id', 'code', 'name', 'contact', 'phone', 'email', 'address', 'status', 'delete_time', 'create_time', 'update_time']

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
    serializer_class = SupplierSerializer

class PurchaseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Purchase
        fields = ['id', 'code', 'name', 'contact', 'phone', 'email', 'address', 'status', 'delete_time', 'create_time', 'update_time']

class PurchaseCategoryViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseCategorySerializer

class PurchaseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Purchase
        fields = ['id', 'code', 'name', 'contact', 'phone', 'email', 'address', 'status', 'delete_time', 'create_time', 'update_time']

class PurchaseItemViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
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
        queryset = Product.objects.filter(delete_time__isnull=True)
        
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
                'created_at': product.create_time.strftime('%Y-%m-%d %H:%M:%S') if product.create_time else ''
            })
        
        return JsonResponse({
            'code': ApiResponseCode.CODE_SUCCESS,
            'msg': 'success',
            'count': paginator.count,
            'data': data
        })


class ProductAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        return render(request, 'contract/product_form.html', {'product': product})

    def post(self, request):
        params = request.POST.dict()
        params['admin_id'] = request.user.id
        
        try:
            Product.objects.create(**params)
            logger.info(f"用户 {request.user.id} 添加了产品")
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS, 
                'msg': '添加成功'
            })
        except Exception as e:
            logger.error(f'添加产品失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': ApiResponseCode.CODE_ERROR,
                'msg': str(e)
            })


class ProductDetailView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request, id):
        product = get_object_or_404(Product, id=id)
        return render(request, 'contract/product_form.html', {'product': product})


class ServicesView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/service_list.html')

    def get_data_list(self, request):
        params = request.POST.dict() if request.method == 'POST' else request.GET.dict()
        queryset = Services.objects.filter(delete_time__isnull=True)
        
        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
        
        paginator = Paginator(queryset.order_by('-create_time'), limit)
        page_obj = paginator.get_page(page)
        
        data = []
        for service in page_obj:
            data.append({
                'id': service.id,
                'name': service.name or '',
                'code': service.code or '',
                'price': str(service.price) if service.price else '0',
                'unit': service.unit or '',
                'duration': service.duration or '',
                'status': '启用' if service.status else '禁用',
                'create_time': timestamp_to_date(service.create_time),
            })
        
        return JsonResponse({
            'code': ApiResponseCode.CODE_SUCCESS,
            'msg': 'success',
            'count': paginator.count,
            'data': data
        })


class ServicesAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        return render(request, 'contract/service_form.html', {'service': service})
    
    def post(self, request):
        params = request.POST.dict()
        params['admin_id'] = request.user.id
        
        try:
            Services.objects.create(**params)
            logger.info(f"用户 {request.user.id} 添加了服务")
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '添加成功'
            })
        except Exception as e:
            logger.error(f'添加服务失败: {str(e)}', exc_info=True)
            return JsonResponse({
                'code': ApiResponseCode.CODE_ERROR,
                'msg': str(e)
            })


class ServicesDetailView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request, id):
        service = get_object_or_404(Services, id=id)
        return render(request, 'contract/service_form.html', {'service': service})


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
        return render(request, 'contract/purchase_add.html', {'purchase': purchase})
    
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
        return render(request, 'contract/purchase_add.html', {'purchase': purchase})


class ArchiveListView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/archive_list.html')

    def get_data_list(self, request):
        page = safe_int(request.GET.get('page'), 1)
        limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
        search_code = request.GET.get('code', '')
        search_date = request.GET.get('archive_date', '')
        
        queryset = Contract.objects.filter(
            delete_time=CommonConstant.DELETE_TIME_ZERO,
            archive_time__gt=CommonConstant.DELETE_TIME_ZERO
        )
        
        if search_code:
            queryset = queryset.filter(code__icontains=search_code)
        
        if search_date and ' - ' in search_date:
            start_date, end_date = search_date.split(' - ')
            start_timestamp = int(timezone.datetime.strptime(start_date, '%Y-%m-%d').timestamp())
            end_timestamp = int(timezone.datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S').timestamp())
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
        limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
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
            start_timestamp = int(timezone.datetime.strptime(start_date, '%Y-%m-%d').timestamp())
            end_timestamp = int(timezone.datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S').timestamp())
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
        limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
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
            start_timestamp = int(timezone.datetime.strptime(start_date, '%Y-%m-%d').timestamp())
            end_timestamp = int(timezone.datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S').timestamp())
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
        limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
        tab = request.GET.get('tab', '0')
        search_code = request.GET.get('code', '')
        search_status = request.GET.get('status', '')
        
        queryset = Contract.objects.filter(delete_time=CommonConstant.DELETE_TIME_ZERO)
        
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
            logger.info(f"用户 {request.user.id} 对合同 {contract_id} 执行了{action}操作")
            
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


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal
from datetime import datetime
import json

from .models import (
    ContractCategory, ProductCategory, ServiceCategory,
    Product, Service, Supplier, PurchaseCategory, PurchaseItem
)
from .forms import (
    ContractCategoryForm, ProductCategoryForm, ServiceCategoryForm,
    ServiceForm, SupplierForm, PurchaseCategoryForm, PurchaseItemForm
)
from apps.common.views_utils import generic_list_view, generic_form_view


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
        from apps.common.utils import safe_int
        from apps.common.constants import CommonConstant
        from django.core.paginator import Paginator
        
        params = request.GET.dict()
        queryset = ContractCate.objects.filter(delete_time__isnull=True)
        
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
        for cate in page_obj:
            parent_name = cate.parent.name if cate.parent else ''
            data.append({
                'id': cate.id,
                'name': cate.name or '',
                'code': cate.code or '',
                'parent_name': parent_name,
                'sort': cate.sort or 0,
                'status': '启用' if cate.status else '禁用',
                'create_time': cate.create_time.strftime('%Y-%m-%d %H:%M') if cate.create_time else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': 'success',
            'count': paginator.count,
            'data': data
        })


class ContractCategoryAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request):
        return render(request, 'contract/contract_category_form.html', {'action': '添加'})


class ContractCategoryEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request, id):
        category = get_object_or_404(ContractCate, id=id)
        return render(request, 'contract/contract_category_form.html', {'category': category, 'action': '编辑'})


class ProductCategoryView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/product_category_list.html')

    def get_data_list(self, request):
        from apps.common.utils import safe_int
        from apps.common.constants import CommonConstant
        from django.core.paginator import Paginator
        
        params = request.GET.dict()
        queryset = ProductCate.objects.filter(delete_time__isnull=True)
        
        if 'search' in params and params['search']:
            queryset = queryset.filter(
                Q(title__icontains=params['search'])
            )
        
        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
        
        paginator = Paginator(queryset.order_by('-create_time'), limit)
        page_obj = paginator.get_page(page)
        
        data = []
        for cate in page_obj:
            data.append({
                'id': cate.id,
                'name': cate.title or '',
                'parent': cate.pid.title if cate.pid else '',
                'status': '启用' if cate.status else '禁用',
                'created_at': cate.create_time.strftime('%Y-%m-%d %H:%M:%S') if cate.create_time else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': 'success',
            'count': paginator.count,
            'data': data
        })


class ProductCategoryAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request):
        return render(request, 'contract/product_category_form.html', {'action': '添加'})


class ProductCategoryEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request, id):
        category = get_object_or_404(ProductCate, id=id)
        return render(request, 'contract/product_category_form.html', {'category': category, 'action': '编辑'})


class ServiceCategoryView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/service_category_list.html')

    def get_data_list(self, request):
        from apps.common.utils import safe_int
        from apps.common.constants import CommonConstant
        from django.core.paginator import Paginator
        
        params = request.GET.dict()
        queryset = Services.objects.filter(delete_time__isnull=True)
        
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
        for cate in page_obj:
            data.append({
                'id': cate.id,
                'name': cate.name or '',
                'code': cate.code or '',
                'price': str(cate.price) if cate.price else '0',
                'unit': cate.unit or '',
                'status': '启用' if cate.status else '禁用',
                'create_time': cate.create_time.strftime('%Y-%m-%d %H:%M') if cate.create_time else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': 'success',
            'count': paginator.count,
            'data': data
        })


class ServiceCategoryAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request):
        return render(request, 'contract/service_category_form.html', {'action': '添加'})


class ServiceCategoryEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request, id):
        category = get_object_or_404(Services, id=id)
        return render(request, 'contract/service_category_form.html', {'category': category, 'action': '编辑'})


class SupplierView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/supplier_list.html')

    def get_data_list(self, request):
        from apps.common.utils import safe_int
        from apps.common.constants import CommonConstant
        from django.core.paginator import Paginator
        
        params = request.GET.dict()
        queryset = Purchase.objects.filter(delete_time__isnull=True)
        
        if 'keywords' in params:
            queryset = queryset.filter(
                Q(name__icontains=params['keywords']) |
                Q(code__icontains=params['keywords']) |
                Q(contact__icontains=params['keywords'])
            )
        
        page = safe_int(params.get('page'), 1)
        limit = safe_int(params.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
        
        paginator = Paginator(queryset.order_by('-create_time'), limit)
        page_obj = paginator.get_page(page)
        
        data = []
        for supplier in page_obj:
            data.append({
                'id': supplier.id,
                'name': supplier.name or '',
                'code': supplier.code or '',
                'contact': supplier.contact or '',
                'phone': supplier.phone or '',
                'email': supplier.email or '',
                'address': supplier.address or '',
                'status': '启用' if supplier.status else '禁用',
                'create_time': supplier.create_time.strftime('%Y-%m-%d %H:%M') if supplier.create_time else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': 'success',
            'count': paginator.count,
            'data': data
        })


class SupplierAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request):
        return render(request, 'contract/supplier_form.html', {'action': '添加'})


class SupplierEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request, id):
        supplier = get_object_or_404(Purchase, id=id)
        return render(request, 'contract/supplier_form.html', {'supplier': supplier, 'action': '编辑'})


class PurchaseCategoryView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_data_list(request)
        return render(request, 'contract/purchase_category_list.html')

    def get_data_list(self, request):
        from apps.common.utils import safe_int
        from apps.common.constants import CommonConstant
        from django.core.paginator import Paginator
        
        params = request.GET.dict()
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
        for cate in page_obj:
            data.append({
                'id': cate.id,
                'name': cate.name or '',
                'code': cate.code or '',
                'cost': str(cate.cost) if cate.cost else '0',
                'status': cate.check_status or '',
                'create_time': cate.create_time.strftime('%Y-%m-%d %H:%M') if cate.create_time else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': 'success',
            'count': paginator.count,
            'data': data
        })


class PurchaseCategoryAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request):
        return render(request, 'contract/purchase_category_form.html', {'action': '添加'})


class PurchaseCategoryEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request, id):
        category = get_object_or_404(Purchase, id=id)
        return render(request, 'contract/purchase_category_form.html', {'category': category, 'action': '编辑'})


class PurchaseItemView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request):
        return render(request, 'contract/purchase_item_list.html')


class PurchaseItemAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request):
        return render(request, 'contract/purchase_item_form.html', {'action': '添加'})


class PurchaseItemEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request, id):
        item = get_object_or_404(Purchase, id=id)
        return render(request, 'contract/purchase_item_form.html', {'item': item, 'action': '编辑'})


class ServiceListView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request):
        return render(request, 'contract/service_list.html')


class ServiceListAddView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request):
        return render(request, 'contract/service_form.html', {'action': '添加'})


class ServiceListEditView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    
    def get(self, request, id):
        service = get_object_or_404(Services, id=id)
        return render(request, 'contract/service_form.html', {'service': service, 'action': '编辑'})
