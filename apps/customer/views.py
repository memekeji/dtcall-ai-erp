# 标准库导入
import json
import logging
import os
import time
import uuid
import ast
import operator
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

# Django核心导入
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models, transaction
from django.db.models import Prefetch, Q, Count
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    View, ListView, CreateView, DetailView, 
    UpdateView, DeleteView, TemplateView
)

# 系统日志导入
from apps.user.models import SystemLog, SystemConfiguration
from apps.common.cache_service import SystemCache
from apps.common.constants import CUSTOMER_INDUSTRY_CHOICES
from apps.common.services import CommonService

# 本地应用导入
from .models import (
    Customer, CustomerGrade, CustomerSource, CustomerIntent, SpiderTask, 
    Contact, FollowRecord, CallRecord, CustomerField, CustomerCustomFieldValue,
    CustomerOrder, CustomerContract, CustomerOrderCustomFieldValue, FollowField,
    OrderField
)
# 财务模块导入
# 用户模型导入
from apps.user.models.admin import Admin
from .forms import CustomerForm, ContactFormSet, CustomerFieldForm, FollowFieldForm, OrderFieldForm
from .forms import CustomerSourceForm, CustomerGradeForm, CustomerIntentForm
from .serializers import CustomerFieldSerializer

logger = logging.getLogger(__name__)
CUSTOMER_FORMULA_TOKEN_PATTERN = re.compile(r'\{([a-zA-Z0-9_]+)\}')
CUSTOMER_SAFE_FORMULA_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
CUSTOMER_SAFE_UNARY_OPERATORS = {
    ast.UAdd: lambda value: value,
    ast.USub: lambda value: -value,
}


def _get_customer_field_options(field):
    if not field.options:
        return []
    return [option.strip() for option in field.options.replace(',', '\n').split('\n') if option.strip()]


def _parse_customer_list_field_value(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        parsed = None

    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]

    return [item.strip() for item in text.replace(',', '\n').split('\n') if item.strip()]


def _serialize_customer_list_field_value(values):
    cleaned_values = [str(value).strip() for value in values if str(value).strip()]
    return json.dumps(cleaned_values, ensure_ascii=False)


def _parse_customer_related_field_value(value):
    if not value:
        return []

    if isinstance(value, list):
        return [
            {
                'source': str(item.get('source', '')).strip(),
                'value': str(item.get('value', '')).strip(),
            }
            for item in value
            if isinstance(item, dict) and str(item.get('source', '')).strip()
        ]

    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []

    if not isinstance(parsed, list):
        return []

    normalized_items = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        source = str(item.get('source', '')).strip()
        if not source:
            continue
        normalized_items.append({
            'source': source,
            'value': str(item.get('value', '')).strip(),
        })
    return normalized_items


def _serialize_customer_related_field_value(source_values, related_values):
    normalized_items = []
    for index, source_value in enumerate(source_values):
        source_text = str(source_value).strip()
        if not source_text:
            continue
        related_text = ''
        if index < len(related_values):
            related_text = str(related_values[index]).strip()
        normalized_items.append({
            'source': source_text,
            'value': related_text,
        })
    return json.dumps(normalized_items, ensure_ascii=False)


def _format_customer_decimal_value(value):
    normalized = value.normalize()
    text = format(normalized, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text or '0'


def _get_customer_request_field_values(request, field):
    field_key = f'custom_field_{field.id}'
    if field.field_type == 'checkbox':
        return ['1' if request.POST.get(field_key) else '0']
    if field.field_type == 'list':
        return [str(item).strip() for item in request.POST.getlist(field_key) if str(item).strip()]
    value = str(request.POST.get(field_key, '')).strip()
    return [value] if value else []


def _get_customer_request_field_value_map(request):
    value_map = {}
    custom_fields = CustomerField.objects.filter(delete_time=0)
    for field in custom_fields:
        values = _get_customer_request_field_values(request, field)
        value_map[field.field_name] = values
    return value_map


def _get_customer_formula_tokens(expression):
    return CUSTOMER_FORMULA_TOKEN_PATTERN.findall(expression or '')


def _safe_customer_decimal_eval(expression):
    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return Decimal(str(node.value))
            raise ValueError('unsupported constant')
        if isinstance(node, ast.Num):
            return Decimal(str(node.n))
        if isinstance(node, ast.BinOp) and type(node.op) in CUSTOMER_SAFE_FORMULA_OPERATORS:
            left = _eval(node.left)
            right = _eval(node.right)
            if type(node.op) is ast.Div and right == 0:
                return Decimal('0')
            return CUSTOMER_SAFE_FORMULA_OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in CUSTOMER_SAFE_UNARY_OPERATORS:
            return CUSTOMER_SAFE_UNARY_OPERATORS[type(node.op)](_eval(node.operand))
        raise ValueError('unsupported expression')

    parsed = ast.parse(expression, mode='eval')
    return _eval(parsed)


def _calculate_customer_formula_value(field, request):
    expression = (getattr(field, 'formula_expression', '') or '').strip()
    if not expression:
        return ''

    value_map = _get_customer_request_field_value_map(request)
    tokens = _get_customer_formula_tokens(expression)
    if not tokens:
        return ''

    token_values = {}
    for token in tokens:
        values = value_map.get(token, [])
        if not values:
            token_values[token] = Decimal('0')
            continue
        try:
            token_values[token] = Decimal(str(values[0]))
        except (InvalidOperation, TypeError, ValueError):
            token_values[token] = Decimal('0')

    normalized_expression = expression
    for token in sorted(set(tokens), key=len, reverse=True):
        normalized_expression = normalized_expression.replace(
            f'{{{token}}}',
            str(token_values[token]),
        )

    try:
        result = _safe_customer_decimal_eval(normalized_expression)
    except (SyntaxError, ValueError, InvalidOperation, ZeroDivisionError):
        return ''
    return _format_customer_decimal_value(result)


def _calculate_customer_related_value(field, request):
    if getattr(field, 'calculation_type', '') == 'formula':
        return _calculate_customer_formula_value(field, request)

    related_field = getattr(field, 'related_field', None)
    if not related_field:
        return ''

    source_values = _get_customer_request_field_values(request, related_field)
    calculation_type = getattr(field, 'calculation_type', '') or 'count'

    if calculation_type == 'count':
        return str(len(source_values))

    if calculation_type == 'concat':
        return '、'.join(source_values)

    numeric_values = []
    for item in source_values:
        try:
            numeric_values.append(Decimal(str(item)))
        except (InvalidOperation, TypeError, ValueError):
            continue

    if not numeric_values:
        return ''

    if calculation_type == 'sum':
        return _format_customer_decimal_value(sum(numeric_values, Decimal('0')))
    if calculation_type == 'avg':
        average = sum(numeric_values, Decimal('0')) / Decimal(len(numeric_values))
        return _format_customer_decimal_value(average)
    if calculation_type == 'max':
        return _format_customer_decimal_value(max(numeric_values))
    if calculation_type == 'min':
        return _format_customer_decimal_value(min(numeric_values))
    return ''


def _is_checked_post_flag(request, field_name):
    value = str(request.POST.get(field_name, '')).strip().lower()
    return value in {'1', 'true', 'on', 'yes'}


def _get_selected_auto_create_targets(request, *targets):
    return {
        target for target in targets
        if _is_checked_post_flag(request, f'auto_create_{target}')
    }


def _get_customer_bound_child_fields(fields):
    bound_children = {}
    for field in fields:
        if not getattr(field, 'relation_enabled', False):
            continue
        if getattr(field, 'relation_type', '') != 'bind':
            continue
        if not getattr(field, 'related_field_id', None):
            continue
        bound_children.setdefault(field.related_field_id, []).append(field)
    for child_fields in bound_children.values():
        child_fields.sort(key=lambda item: (item.sort, item.id))
    return bound_children


def _build_customer_related_rows(field, current_values):
    current_values = current_values or {}
    primary_items = _parse_customer_list_field_value(current_values.get(field.id, ''))
    child_value_map = {
        child.id: _parse_customer_related_field_value(current_values.get(child.id, ''))
        for child in getattr(field, 'bound_children', [])
    }

    row_count = len(primary_items)
    if row_count == 0:
        row_count = 1

    rows = []
    for index in range(row_count):
        row = {
            'primary_value': primary_items[index] if index < len(primary_items) else '',
            'children': [],
        }
        for child in getattr(field, 'bound_children', []):
            child_items = child_value_map.get(child.id, [])
            child_value = ''
            if index < len(child_items):
                child_value = child_items[index].get('value', '')
            row['children'].append({
                'id': child.id,
                'name': child.name,
                'field_name': child.field_name,
                'value': child_value,
                'required': child.is_required,
            })
        rows.append(row)
    return rows


def _display_customer_custom_field_value(field, value):
    if field.field_type == 'checkbox':
        return '是' if value == '1' else '否'
    if getattr(field, 'relation_enabled', False) and getattr(field, 'relation_type', '') == 'bind':
        return '、'.join(
            item.get('value', '')
            for item in _parse_customer_related_field_value(value)
            if item.get('value', '')
        )
    if getattr(field, 'relation_enabled', False) and getattr(field, 'relation_type', '') == 'calculate':
        if getattr(field, 'calculation_type', '') == 'concat':
            return value or ''
        return value or ''
    if field.field_type == 'list':
        return '、'.join(_parse_customer_list_field_value(value))
    return value or ''


def _prepare_customer_custom_fields(custom_fields, current_values=None):
    current_values = current_values or {}
    field_list = list(custom_fields)
    bound_children = _get_customer_bound_child_fields(field_list)
    prepared_fields = []

    for field in field_list:
        field.options_list = _get_customer_field_options(field)
        field.current_value = current_values.get(field.id, '')
        field.current_items = _parse_customer_list_field_value(field.current_value)
        field.bound_children = bound_children.get(field.id, [])
        field.related_rows = _build_customer_related_rows(field, current_values) if field.bound_children else []
        field.formula_expression = getattr(field, 'formula_expression', '') or ''
        field.formula_tokens = _get_customer_formula_tokens(field.formula_expression)
        field.is_calculated = bool(
            getattr(field, 'relation_enabled', False) and
            getattr(field, 'relation_type', '') == 'calculate' and (
                getattr(field, 'related_field_id', None) or field.formula_expression
            )
        )
        field.is_bound_child = bool(
            getattr(field, 'relation_enabled', False) and
            getattr(field, 'relation_type', '') == 'bind' and
            getattr(field, 'related_field_id', None)
        )
        if field.is_bound_child:
            continue
        prepared_fields.append(field)
    return prepared_fields


def _get_customer_custom_field_post_value(request, field):
    field_key = f'custom_field_{field.id}'
    if field.field_type == 'checkbox':
        return '1' if request.POST.get(field_key) else '0'
    if getattr(field, 'relation_enabled', False) and getattr(field, 'relation_type', '') == 'bind' and field.related_field_id:
        source_values = request.POST.getlist(f'custom_field_{field.related_field_id}')
        related_values = request.POST.getlist(field_key)
        return _serialize_customer_related_field_value(source_values, related_values)
    if getattr(field, 'relation_enabled', False) and getattr(field, 'relation_type', '') == 'calculate':
        return _calculate_customer_related_value(field, request)
    if field.field_type == 'list':
        return _serialize_customer_list_field_value(request.POST.getlist(field_key))
    if getattr(field, 'relation_enabled', False) and getattr(field, 'relation_type', '') == 'copy' and field.related_field_id:
        return request.POST.get(f'custom_field_{field.related_field_id}', '')
    return request.POST.get(field_key, '')


class CustomerListView(LoginRequiredMixin, ListView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Customer
    template_name = 'customer/customer_list.html'
    context_object_name = 'customers'
    
    def get_queryset(self):
        # 只返回未删除的客户记录，并预加载关联外键以解决 N+1 查询问题
        queryset = super().get_queryset().select_related('customer_source')
        queryset = queryset.filter(delete_time=0)
        
        # 添加数据权限过滤
        user = self.request.user
        
        # 超级管理员可以查看所有客户
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return queryset
        
        # 数据权限过滤：只能查看自己的客户及共享给自己的客户
        queryset = queryset.filter(
            models.Q(belong_uid=user.id) | 
            models.Q(share_ids__contains=str(user.id))
        )
        
        return queryset
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 获取客户来源和等级信息
        context['sources'] = CustomerSource.objects.filter(status=1, delete_time=0)
        context['grades'] = CustomerGrade.objects.filter(status=1, delete_time=0)
        
        # 获取客户意向信息
        context['intents'] = CustomerIntent.objects.filter(status=1, delete_time=0)
        
        # 从JSON文件读取完整的省市数据
        import json
        import os
        
        json_file_path = os.path.join(settings.BASE_DIR, 'static', 'json', '全国省市区.json')
        
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                province_city_data = json.load(f)
            
            # 获取所有省份数据
            provinces_data = province_city_data.get('00', {})
            context['provinces'] = list(provinces_data.values())
            
            # 构建省市映射关系
            province_city_map = {}
            for province_key in province_city_data:
                if province_key != '00':  # 跳过省份数据
                    # 获取省份名称（通过键值对应）
                    province_name = provinces_data.get(province_key, '')
                    if province_name:
                        cities_data = province_city_data.get(province_key, {})
                        province_city_map[province_name] = list(cities_data.values())
            
            context['cities'] = province_city_map
            
        except Exception as e:
            # 如果JSON文件读取失败，使用客户数据中的省市数据作为备选
            provinces = Customer.objects.filter(delete_time=0, province__isnull=False).exclude(province='').values_list('province', flat=True).distinct()
            
            # 构建简单的省市映射（基于现有客户数据）
            province_city_map = {}
            for province in provinces:
                cities = Customer.objects.filter(delete_time=0, province=province, city__isnull=False).exclude(city='').values_list('city', flat=True).distinct()
                province_city_map[province] = sorted(cities)
            
            context['provinces'] = sorted(provinces)
            context['cities'] = province_city_map
        
        # 获取启用的客户字段，用于动态生成表格列
        custom_fields = CustomerField.objects.filter(
            status=True, 
            delete_time=0, 
            is_list_display=True
        ).order_by('sort', 'id')
        context['custom_fields'] = custom_fields
        
        # 添加用户权限信息
        context['is_superuser'] = hasattr(self.request.user, 'is_superuser') and self.request.user.is_superuser
        
        return context


class CustomerListSimpleView(LoginRequiredMixin, TemplateView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    template_name = 'customer/customer_list.html'


class CustomerListDataView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        try:
            # 获取客户列表数据，并使用annotate添加实体关联计数
            queryset = Customer.objects.filter(delete_time=0)
            
            # 添加实体关联计数
            queryset = queryset.annotate(
                # 订单计数
                order_count=Count('orders', filter=models.Q(orders__delete_time=0)),
                # 合同计数
                contract_count=Count('contracts', filter=models.Q(contracts__delete_time=0)),
                # 项目计数
                project_count=Count('projects'),
                # 发票计数
                invoice_count=Count('invoices', filter=models.Q(invoices__delete_time=0))
            )
            
            # 添加数据权限过滤
            user = self.request.user
            
            # 数据权限过滤：
            # 1. 超级管理员：可以查看所有客户，但不包括已移入公海的客户（belong_uid=0）
            # 2. 普通用户：只能查看自己的客户及共享给自己的客户
            if hasattr(user, 'is_superuser') and user.is_superuser:
                # 超级管理员：排除已移入公海的客户
                queryset = queryset.filter(belong_uid__gt=0)
            else:
                # 普通用户：只能查看自己的客户及共享给自己的客户
                queryset = queryset.filter(
                    models.Q(belong_uid=user.id) | 
                    models.Q(share_ids__contains=str(user.id))
                )
            
            # 获取视图类型（列表视图或卡片视图）
            view_type = request.GET.get('view_type', 'list')  # 默认为列表视图
            
            # 根据视图类型设置排序规则
            if view_type == 'card':
                # 卡片视图：按ID降序排序，因为services__sort无法解析
                queryset = queryset.order_by('-id')
            else:
                # 列表视图：按ID降序排序
                queryset = queryset.order_by('-id')
            
            # 获取自定义字段定义
            custom_fields = CustomerField.objects.filter(delete_time=0, status=True)
            serialized_fields = CustomerFieldSerializer(custom_fields, many=True).data
            
            # 处理搜索条件
            customer_name = request.GET.get('customer_name', '')
            contact_name = request.GET.get('contact_name', '')
            phone = request.GET.get('phone', '')
            
            if customer_name:
                queryset = queryset.filter(name__icontains=customer_name)
            if contact_name:
                queryset = queryset.filter(contacts__contact_person__icontains=contact_name)
            if phone:
                queryset = queryset.filter(contacts__phone__icontains=phone)
            
            # 处理筛选条件
            customer_source = request.GET.get('customer_source', '')
            customer_grade = request.GET.get('customer_grade', '')
            customer_intent = request.GET.get('customer_intent', '')
            customer_intent_id = request.GET.get('customer_intent_id', '')
            province = request.GET.get('province', '')
            city = request.GET.get('city', '')
            
            if customer_source:
                queryset = queryset.filter(customer_source__title=customer_source)
            if customer_grade:
                queryset = queryset.filter(grade_id__in=CustomerGrade.objects.filter(title=customer_grade).values_list('id', flat=True))
            if customer_intent_id:
                if customer_intent_id == '__uncategorized__':
                    active_intent_ids = CustomerIntent.objects.filter(
                        status=1,
                        delete_time=0
                    ).values_list('id', flat=True)
                    queryset = queryset.exclude(services_id__in=active_intent_ids)
                else:
                    try:
                        queryset = queryset.filter(services_id=int(customer_intent_id))
                    except (TypeError, ValueError):
                        queryset = queryset.none()
            if customer_intent:
                queryset = queryset.filter(services_id__in=CustomerIntent.objects.filter(name=customer_intent).values_list('id', flat=True))
            if province:
                queryset = queryset.filter(province=province)
            if city:
                queryset = queryset.filter(city=city)
            
            # 处理自定义字段筛选
            for field in custom_fields:
                filter_key = f'custom_filter_{field.id}'
                filter_value = request.GET.get(filter_key, '')
                if filter_value:
                    queryset = queryset.filter(custom_fields__field_id=field.id, custom_fields__value=filter_value)

            queryset = queryset.distinct()
            
            # 添加预取操作
            queryset = queryset.prefetch_related(
                'contacts',
                Prefetch('custom_fields',
                    queryset=CustomerCustomFieldValue.objects.select_related('field'),
                    to_attr='custom_field_values'
                ),
                Prefetch('follow_records',
                    queryset=FollowRecord.objects.filter(delete_time=0).order_by('-follow_time'),
                    to_attr='latest_follow_records'
                )
            )

            # 处理分页
            page = int(request.GET.get('page', 1))
            limit = CommonService.get_page_size(request, 20)
            start = (page - 1) * limit
            end = start + limit

            total_count = queryset.count()
            paginated_queryset = queryset[start:end]

            # 获取基础数据映射
            sources_map = SystemCache.get_dict('customer_sources')
            if sources_map is None:
                sources_map = {s.id: s.title for s in CustomerSource.objects.filter(delete_time=0)}
                SystemCache.set_dict('customer_sources', sources_map)
            
            grades_map = SystemCache.get_dict('customer_grades')
            if grades_map is None:
                grades_map = {g.id: g.title for g in CustomerGrade.objects.filter(delete_time=0)}
                SystemCache.set_dict('customer_grades', grades_map)
            
            intents_map = SystemCache.get_dict('customer_intents')
            if intents_map is None:
                intents_map = {i.id: i.name for i in CustomerIntent.objects.filter(delete_time=0)}
                SystemCache.set_dict('customer_intents', intents_map)
            
            # 构建用户ID到姓名的映射
            user_ids = list(queryset.values_list('belong_uid', flat=True).distinct())
            users_map = {u.id: u.name for u in Admin.objects.filter(id__in=user_ids)}
            
            # 格式化数据
            items = []
            for item in paginated_queryset:
                # 获取主要联系人信息
                primary_contact = item.contacts.filter(is_primary=True).first()
                if not primary_contact:
                    primary_contact = item.contacts.first()
                
                contact_name = primary_contact.contact_person if primary_contact else ''
                phone = primary_contact.phone if primary_contact else ''
                email = primary_contact.email if primary_contact else ''
                
                # 获取最近跟进时间
                latest_followup_time = ''
                latest_followup = ''
                if hasattr(item, 'latest_follow_records') and item.latest_follow_records:
                    latest_follow_record = item.latest_follow_records[0]  # 按时间降序排列，第一个就是最新的
                    latest_followup_time = latest_follow_record.follow_time.strftime('%Y-%m-%d %H:%M:%S') if latest_follow_record.follow_time else ''
                    latest_followup = latest_follow_record.content or latest_followup_time
                
                # 获取客户归属信息
                customer_owner = ''
                if item.belong_uid and item.belong_uid > 0:
                    customer_owner = users_map.get(item.belong_uid, '')
                else:
                    customer_owner = '公海客户'
                
                item_data = {
                'id': item.id,
                'name': item.name,
                'contact_name': contact_name,
                'phone': phone,
                'email': email,
                'address': item.address,
                'create_time': item.create_time.strftime('%Y-%m-%d %H:%M:%S') if item.create_time else '',
                'customer_source': sources_map.get(item.customer_source_id, ''),
                'customer_grade': grades_map.get(item.grade_id, ''),
                'customer_intent_id': item.services_id,
                'customer_intent': intents_map.get(item.services_id, '未分类'),
                'customer_owner': customer_owner,  # 添加客户归属字段
                'latest_followup': latest_followup,
                'latest_followup_time': latest_followup_time,
                'intent_sort': getattr(item, 'intent_sort', 999),  # 添加意向排序值
                # 添加实体关联计数
                'order_count': getattr(item, 'order_count', 0),
                'contract_count': getattr(item, 'contract_count', 0),
                'project_count': getattr(item, 'project_count', 0),
                'invoice_count': getattr(item, 'invoice_count', 0),
                'payment_count': getattr(item, 'payment_count', 0)
            }
                
                # 添加自定义字段值
                for cfv in item.custom_field_values:
                    item_data[f'custom_{cfv.field.id}'] = _display_customer_custom_field_value(
                        cfv.field,
                        cfv.value,
                    )
                
                items.append(item_data)

            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': items,
                'custom_fields': serialized_fields
            })
        except Exception as e:
            logger.error(f"Error processing customer list data: {str(e)}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'msg': f'Server error: {str(e)}',
                'data': []
            }, status=500)


class CustomerCreateView(LoginRequiredMixin, CreateView):
    form_class = CustomerForm
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Customer
    template_name = 'customer/customer_form.html'
    success_url = reverse_lazy('customer:customer_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 获取启用的自定义字段
        custom_fields = CustomerField.objects.filter(status=True, delete_time=0).select_related('related_field').order_by('sort', 'id')
        
        _prepare_customer_custom_fields(custom_fields)
        
        context['custom_fields'] = custom_fields
        
        # 联系人表单集
        if self.request.POST:
            context['contact_formset'] = ContactFormSet(self.request.POST, instance=self.object)
        else:
            context['contact_formset'] = ContactFormSet(instance=self.object)
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        contact_formset = context['contact_formset']
        
        with transaction.atomic():
            # 设置客户归属用户ID为当前登录用户
            form.instance.belong_uid = self.request.user.id
            form.instance.admin_id = self.request.user.id
            # 设置初始状态值确保通过列表过滤条件
            form.instance.delete_time = 0
            form.instance.intent_status = 1
            # 设置归属时间为当前时间
            form.instance.belong_time = int(timezone.now().timestamp())
            
            self.object = form.save()
            
            # 处理主要联系人的单选逻辑
            primary_contact_value = self.request.POST.get('primary_contact')
            
            # 保存联系人信息
            if contact_formset.is_valid():
                contact_formset.instance = self.object
                contacts = contact_formset.save()
                
                # 处理主要联系人设置
                if primary_contact_value and contacts:
                    # 先将所有联系人设为非主要
                    Contact.objects.filter(customer=self.object).update(is_primary=False)
                    
                    # 根据primary_contact的值设置主要联系人
                    if primary_contact_value.isdigit():
                        # 如果是数字，表示是新添加的联系人索引
                        contact_index = int(primary_contact_value)
                        if contact_index < len(contacts):
                            contacts[contact_index].is_primary = True
                            contacts[contact_index].save()
                    else:
                        # 如果不是数字，可能是联系人ID
                        try:
                            contact_id = int(primary_contact_value)
                            Contact.objects.filter(id=contact_id, customer=self.object).update(is_primary=True)
                        except (ValueError, TypeError):
                            pass
            else:
                return self.form_invalid(form)
            
            # 处理自定义字段
            self.save_custom_fields()
            
            selected_targets = _get_selected_auto_create_targets(
                self.request,
                'contract',
                'order',
                'project',
            )
            if selected_targets:
                try:
                    self._auto_generate_related_records(
                        self.object,
                        self.request.user,
                        selected_targets,
                    )
                except Exception as auto_gen_error:
                    # 记录错误但不影响客户创建
                    logger.error(f"自动生成相关记录失败: {str(auto_gen_error)}")
            
            # 添加操作日志
            SystemLog.objects.create(
                user=self.request.user,
                log_type='create',
                module='客户管理',
                action='创建客户',
                content=f'成功创建客户: {self.object.name}',
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT')
            )
        
        messages.success(self.request, '客户添加成功！')
        # 直接使用reverse生成URL进行重定向，确保重定向正确执行
        from django.urls import reverse
        return HttpResponseRedirect(reverse('customer:customer_list'))
    
    def _auto_generate_related_records(self, customer, user, selected_targets):
        """
        根据用户勾选结果生成与客户相关的记录：合同、订单、项目
        """
        import time
        
        if 'contract' in selected_targets:
            try:
                from apps.customer.models import CustomerContract
                CustomerContract.objects.create(
                    customer_id=customer.id,
                    name=f"{customer.name}合同",
                    contract_number=f"CONT-CUST-{customer.id}-{int(time.time())}",
                    amount=0,
                    sign_date=timezone.now().date(),
                    end_date=None,
                    status='pending',
                    create_user_id=user.id,
                    auto_generated=True,
                )
            except Exception as e:
                logger.error(f"创建CustomerContract记录失败: {e}")

            try:
                from apps.contract.models import Contract
                Contract.objects.create(
                    customer_id=customer.id,
                    customer=customer.name,
                    code=f"CONTRACT-{customer.id}-{int(time.time())}",
                    name=f"{customer.name}销售合同",
                    cate_id=1,
                    types=1,
                    admin_id=user.id,
                    prepared_uid=user.id,
                    cost=0.00,
                    check_status=0,
                    delete_time=0,
                    auto_generated=True,
                )
            except Exception as e:
                logger.error(f"创建Contract记录失败: {e}")

        if 'order' in selected_targets:
            try:
                from apps.customer.models import CustomerOrder
                CustomerOrder.objects.create(
                    customer_id=customer.id,
                    order_number=f"ORD-CUST-{customer.id}-{int(time.time())}",
                    product_name=f"{customer.name}相关产品",
                    amount=0,
                    order_date=timezone.now().date(),
                    status='pending',
                    description=f"客户{customer.name}相关订单",
                    create_user_id=user.id,
                    auto_generated=True,
                )
            except Exception as e:
                logger.error(f"创建客户订单记录失败: {e}")

        if 'project' in selected_targets:
            try:
                from apps.project.models import Project
                Project.objects.create(
                    customer_id=customer.id,
                    name=f"{customer.name}项目",
                    code=f"PROJ-CUST-{customer.id}-{int(time.time())}",
                    budget=0,
                    start_date=None,
                    end_date=None,
                    status=1,
                    creator=user,
                    auto_generated=True,
                )
            except Exception as e:
                logger.error(f"创建项目记录失败: {e}")
    
    def form_invalid(self, form):
        messages.error(self.request, '表单验证失败，请检查输入信息')
        return super().form_invalid(form)
    
    def save_custom_fields(self):
        """保存自定义字段值"""
        custom_fields = CustomerField.objects.filter(status=True, delete_time=0).select_related('related_field').order_by('sort', 'id')
        
        for field in custom_fields:
            field_value = _get_customer_custom_field_post_value(self.request, field)
            
            # 创建或更新字段值
            CustomerCustomFieldValue.objects.update_or_create(
                customer=self.object,
                field=field,
                defaults={'value': field_value}
            )


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    form_class = CustomerForm
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Customer
    template_name = 'customer/customer_form.html'
    success_url = reverse_lazy('customer:customer_list')
    
    def get_queryset(self):
        queryset = Customer.objects.filter(delete_time=0)
        
        # 添加数据权限过滤
        user = self.request.user
        
        # 超级管理员可以查看所有客户
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return queryset
        
        # 数据权限过滤：只能查看自己的客户及共享给自己的客户
        queryset = queryset.filter(
            models.Q(belong_uid=user.id) | 
            models.Q(share_ids__contains=str(user.id))
        )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 获取启用的自定义字段
        custom_fields = CustomerField.objects.filter(status=True, delete_time=0).select_related('related_field').order_by('sort', 'id')
        
        # 获取当前客户的自定义字段值
        current_values = {}
        for cfv in CustomerCustomFieldValue.objects.filter(customer=self.object):
            current_values[cfv.field_id] = cfv.value
        
        _prepare_customer_custom_fields(custom_fields, current_values)
        
        context['custom_fields'] = custom_fields
        
        # 联系人表单集
        if self.request.POST:
            context['contact_formset'] = ContactFormSet(self.request.POST, instance=self.object)
        else:
            context['contact_formset'] = ContactFormSet(instance=self.object)
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        contact_formset = context['contact_formset']
        
        with transaction.atomic():
            self.object = form.save()
            
            # 处理主要联系人的单选逻辑
            primary_contact_value = self.request.POST.get('primary_contact')
            
            # 保存联系人信息
            if contact_formset.is_valid():
                contact_formset.instance = self.object
                contacts = contact_formset.save(commit=False)
                
                # 处理删除标记的联系人
                for contact in contact_formset.deleted_objects:
                    contact.delete()
                
                # 保存新建和修改的联系人
                for contact in contacts:
                    contact.save()
                
                # 处理主要联系人设置
                if primary_contact_value:
                    # 先将所有联系人设为非主要
                    Contact.objects.filter(customer=self.object).update(is_primary=False)
                    
                    # 根据primary_contact的值设置主要联系人
                    try:
                        contact_id = int(primary_contact_value)
                        Contact.objects.filter(id=contact_id, customer=self.object).update(is_primary=True)
                    except (ValueError, TypeError):
                        # 如果转换失败，可能是新添加的联系人索引
                        if primary_contact_value.isdigit():
                            contact_index = int(primary_contact_value)
                            if contact_index < len(contacts):
                                contacts[contact_index].is_primary = True
                                contacts[contact_index].save()
            else:
                return self.form_invalid(form)
            
            # 处理自定义字段
            self.save_custom_fields()
            
            # 添加操作日志
            SystemLog.objects.create(
                user=self.request.user,
                log_type='update',
                module='客户管理',
                action='更新客户',
                content=f'成功更新客户: {self.object.name}',
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT')
            )
        
        messages.success(self.request, '客户信息更新成功！')
        # 直接使用reverse生成URL进行重定向，确保重定向正确执行
        from django.urls import reverse
        return HttpResponseRedirect(reverse('customer:customer_list'))
    
    def form_invalid(self, form):
        messages.error(self.request, '表单验证失败，请检查输入信息')
        return super().form_invalid(form)
    
    def save_custom_fields(self):
        """保存自定义字段值"""
        custom_fields = CustomerField.objects.filter(status=True, delete_time=0).select_related('related_field').order_by('sort', 'id')
        
        for field in custom_fields:
            field_value = _get_customer_custom_field_post_value(self.request, field)
            
            # 创建或更新字段值
            CustomerCustomFieldValue.objects.update_or_create(
                customer=self.object,
                field=field,
                defaults={'value': field_value}
            )


class CustomerDetailView(LoginRequiredMixin, DetailView):
    model = Customer
    template_name = 'customer/customer_detail.html'
    context_object_name = 'customer'
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get_queryset(self):
        # 基础过滤：只返回未删除的客户
        queryset = Customer.objects.filter(delete_time=0)
        
        # 添加数据权限过滤
        user = self.request.user
        
        # 超级管理员可以查看所有客户
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return queryset
        
        # 数据权限过滤：只能查看自己的客户及共享给自己的客户
        queryset = queryset.filter(
            models.Q(belong_uid=user.id) | 
            models.Q(share_ids__contains=str(user.id))
        )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        current_values = {
            cfv.field_id: cfv.value
            for cfv in CustomerCustomFieldValue.objects.filter(customer=self.object).select_related('field')
        }
        custom_field_values = []
        custom_fields = _prepare_customer_custom_fields(
            CustomerField.objects.filter(status=True, delete_time=0).select_related('related_field').order_by('sort', 'id'),
            current_values,
        )
        for field in custom_fields:
            raw_value = current_values.get(field.id, '')
            list_values = _parse_customer_list_field_value(raw_value) if field.field_type == 'list' else []
            related_rows = [
                row for row in getattr(field, 'related_rows', [])
                if row.get('primary_value') or any(child.get('value') for child in row.get('children', []))
            ]
            custom_field_values.append({
                'id': field.id,
                'name': field.name,
                'field_type': field.field_type,
                'value': _display_customer_custom_field_value(field, raw_value),
                'list_values': list_values,
                'related_rows': related_rows,
                'bound_children': getattr(field, 'bound_children', []),
            })
        
        # 获取基础数据映射
        try:
            customer_grade = CustomerGrade.objects.filter(id=self.object.grade_id, delete_time=0).first()
            customer_intent = CustomerIntent.objects.filter(id=self.object.services_id, delete_time=0).first()
        except:
            customer_grade = None
            customer_intent = None
        
        context['custom_field_values'] = custom_field_values
        context['customer_grade'] = customer_grade
        context['customer_industry'] = CUSTOMER_INDUSTRY_CHOICES.get(self.object.industry_id, '未设置')
        context['customer_intent'] = customer_intent
        context['contacts'] = self.object.contacts.all()
        context['follow_records'] = self.object.follow_records.all()[:10]  # 最近10条跟进记录
        context['orders'] = self.object.orders.filter(delete_time=0)[:5]  # 最近5个订单
        
        # 获取项目标准合同模块的合同数据，而不是独立的CustomerContract数据
        try:
            from apps.contract.models import Contract
            context['contracts'] = Contract.objects.filter(customer_id=self.object.id, delete_time=0)[:5]  # 最近5个合同
        except Exception as e:
            logger.error(f"获取标准合同数据失败: {str(e)}")
            context['contracts'] = []
        
        # 获取客户发票记录 - 整合客户模块和财务模块的发票记录
        try:
            from apps.finance.models import Invoice as FinanceInvoice
            from apps.customer.models import CustomerInvoice
            customer_invoices = CustomerInvoice.objects.filter(customer_id=self.object.id, delete_time=0)[:5]
            
            finance_invoices = FinanceInvoice.objects.filter(customer_id=self.object.id, is_deleted=False).order_by('-id')[:10]
            
            # 合并发票记录，按开票时间排序
            all_invoices = list(customer_invoices) + list(finance_invoices)
            # 去重并排序
            seen_ids = set()
            unique_invoices = []
            for invoice in all_invoices:
                if invoice.id not in seen_ids:
                    seen_ids.add(invoice.id)
                    unique_invoices.append(invoice)
            
            # 按开票时间排序
            unique_invoices.sort(key=lambda x: x.issued_at if hasattr(x, 'issued_at') and x.issued_at else x.created_at, reverse=True)
            
            context['invoices'] = unique_invoices[:10]  # 显示最多10张发票
        except Exception as e:
            logger.error(f"获取发票记录失败: {str(e)}")
            context['invoices'] = []
        
        # 获取客户财务往来记录 - 直接列表显示（按日期排序）
        try:
            from apps.finance.models import Invoice as FinanceInvoice, Income, Payment
            from apps.customer.models import CustomerInvoice
            all_invoices = CustomerInvoice.objects.filter(customer=self.object.id, delete_time=0).order_by('-id')[:20]
            
            all_finance_invoices = FinanceInvoice.objects.filter(customer=self.object.id, is_deleted=False).order_by('-id')[:20]
            
            all_incomes = Income.objects.filter(invoice__customer=self.object.id).order_by('-id')[:20]
            
            # 获取所有付款记录（Payment模型）- 暂时不显示付款记录，因为Payment模型与客户没有直接关联
            all_payments = Payment.objects.none()
            
            financial_records = []
            
            for invoice in all_invoices:
                invoice_date = None
                try:
                    if hasattr(invoice, 'open_time') and invoice.open_time > 0:
                        invoice_date = datetime.fromtimestamp(invoice.open_time)
                    elif hasattr(invoice, 'create_time'):
                        invoice_date = datetime.fromtimestamp(invoice.create_time) if isinstance(invoice.create_time, (int, float)) else invoice.create_time
                except:
                    pass
                
                if invoice_date:
                    financial_records.append({
                        'type': 'invoice',
                        'record': invoice,
                        'amount': invoice.amount,
                        'date': invoice_date,
                        'status': '已开票' if getattr(invoice, 'open_status', 0) == 1 else '未开票'
                    })
            
            for invoice in all_finance_invoices:
                invoice_date = None
                try:
                    if hasattr(invoice, 'open_time') and invoice.open_time > 0:
                        invoice_date = datetime.fromtimestamp(invoice.open_time)
                    elif hasattr(invoice, 'create_time'):
                        invoice_date = datetime.fromtimestamp(invoice.create_time) if isinstance(invoice.create_time, (int, float)) else invoice.create_time
                except:
                    pass
                
                if invoice_date:
                    financial_records.append({
                        'type': 'invoice',
                        'record': invoice,
                        'amount': invoice.amount,
                        'date': invoice_date,
                        'status': '已开票' if getattr(invoice, 'open_status', 0) == 1 else '未开票'
                    })
            
            # 处理收款记录
            for income in all_incomes:
                income_date = None
                try:
                    if hasattr(income, 'income_date'):
                        income_date = income.income_date
                    elif hasattr(income, 'create_time'):
                        income_date = datetime.fromtimestamp(income.create_time) if isinstance(income.create_time, (int, float)) else income.create_time
                except:
                    pass
                
                if income_date:
                    financial_records.append({
                        'type': 'income',
                        'record': income,
                        'amount': income.amount,
                        'date': income_date,
                        'status': '已收款'
                    })
            
            # 处理付款记录
            for payment in all_payments:
                payment_date = None
                try:
                    if hasattr(payment, 'payment_date'):
                        payment_date = payment.payment_date
                    elif hasattr(payment, 'create_time'):
                        payment_date = datetime.fromtimestamp(payment.create_time) if isinstance(payment.create_time, (int, float)) else payment.create_time
                except:
                    pass
                
                if payment_date:
                    financial_records.append({
                        'type': 'payment',
                        'record': payment,
                        'amount': payment.amount,
                        'date': payment_date,
                        'status': '已付款'
                    })
            
            # 按日期排序
            financial_records.sort(key=lambda x: x['date'], reverse=True)
            
            # 直接提供按日期排序的财务记录列表
            context['financial_records'] = financial_records[:20]  # 按日期排序的财务记录列表
            
        except Exception as e:
            logger.error(f"获取财务记录失败: {str(e)}")
            context['financial_records'] = []
        
        # 获取客户项目记录
        try:
            from apps.project.models import Project
            context['projects'] = Project.objects.filter(customer_id=self.object.id, delete_time__isnull=True)[:5]  # 最近5个项目
        except:
            context['projects'] = []
        
        return context


class CustomerDetailApiView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request, pk):
        try:
            customer = get_object_or_404(Customer, id=pk, delete_time=0)
            
            # 获取主要联系人信息
            primary_contact = customer.contacts.filter(is_primary=True).first()
            contact_person = primary_contact.contact_person if primary_contact else ''
            contact_phone = primary_contact.phone if primary_contact else ''
            
            data = {
                'id': customer.id,
                'name': customer.name,
                'contact_person': contact_person,
                'phone': contact_phone or customer.phone or '',
                'address': customer.address or '',
            }
            
            return JsonResponse(data, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'获取客户详情API失败: {str(e)}', exc_info=True)
            return JsonResponse({'error': str(e)}, status=404, json_dumps_params={'ensure_ascii': False})


class CustomerDeleteView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def post(self, request, pk):
        try:
            customer = Customer.objects.get(id=pk, delete_time=0)
            
            # 检查当前用户是否有删除权限
            # 1. 超级管理员可以删除任何客户
            # 2. 客户归属人可以删除自己的客户
            # 3. 共享用户可以删除共享给自己的客户
            if not (hasattr(request.user, 'is_superuser') and request.user.is_superuser):
                # 检查是否是归属人
                is_owner = customer.belong_uid == request.user.id
                
                # 检查是否是共享用户
                is_shared = False
                if customer.share_ids:
                    shared_ids = customer.share_ids.split(',')
                    is_shared = str(request.user.id) in shared_ids
                
                if not (is_owner or is_shared):
                    return JsonResponse({'status': 'error', 'msg': '您没有权限删除此客户'}, status=403)
            
            # 保存客户名称用于日志记录
            customer_name = customer.name
            
            # 客户从个人列表删除后自动流转至公海：
            # 1. 清除归属人ID
            # 2. 清除部门ID
            # 3. 清除共享ID列表，确保不会再显示在原归属人的客户列表中
            # 4. 保留其他信息
            customer.belong_uid = 0
            customer.belong_did = 0
            customer.share_ids = ''
            customer.save()
            
            # 添加操作日志
            SystemLog.objects.create(
                user=request.user,
                log_type='update',
                module='客户管理',
                action='客户移入公海',
                content=f'将客户 "{customer_name}" 移入公海',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return JsonResponse({'status': 'success', 'msg': '客户已成功移入公海'})
        except Customer.DoesNotExist:
            return JsonResponse({'status': 'error', 'msg': '客户不存在'}, status=404)
        except Exception as e:
            logger.error(f"删除客户失败: {str(e)}")
            return JsonResponse({'status': 'error', 'msg': f'操作失败: {str(e)}'}, status=500)


class CustomerBatchDeleteView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request):
        try:
            data = json.loads(request.body)
            ids = data.get('ids', [])
            if not ids:
                return JsonResponse({'status': 'error', 'message': '未提供客户ID列表'}, status=400)

            # 获取当前用户可操作的客户
            if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
                # 超级管理员可以操作所有客户
                customers = Customer.objects.filter(id__in=ids, delete_time=0)
            else:
                # 普通用户只能操作自己的客户或共享给自己的客户
                customers = Customer.objects.filter(
                    Q(id__in=ids) &
                    Q(delete_time=0) &
                    (Q(belong_uid=request.user.id) | 
                     Q(share_ids__contains=str(request.user.id)))
                )

            # 批量将客户移入公海：
            # 1. 清除归属人ID
            # 2. 清除部门ID
            # 3. 清除共享ID列表
            updated_count = customers.update(
                belong_uid=0,
                belong_did=0,
                share_ids=''
            )

            # 添加操作日志
            if updated_count > 0:
                customer_names = ', '.join(customers.values_list('name', flat=True))
                SystemLog.objects.create(
                    user=request.user,
                    log_type='delete',
                    module='customer',
                    action='批量删除客户',
                    content=f'成功将{updated_count}个客户移入公海: {customer_names}',
                    ip_address=request.META.get('REMOTE_ADDR', '0.0.0.0'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )

            return JsonResponse({'status': 'success', 'message': f'成功将{updated_count}个客户移入公海'})
        except Exception as e:
            logger.error(f'批量处理客户失败: {str(e)}')
            return JsonResponse({'status': 'error', 'message': f'操作失败: {str(e)}'}, status=500)


class CustomerBatchImportView(LoginRequiredMixin, TemplateView):
    template_name = 'customer/customer_import.html'
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 获取基础数据选项，用于导入时的数据映射
        context['customer_sources'] = CustomerSource.objects.filter(status=1, delete_time=0).order_by('sort', 'id')
        context['customer_grades'] = CustomerGrade.objects.filter(status=1, delete_time=0).order_by('sort', 'id')
        context['customer_intents'] = CustomerIntent.objects.filter(status=1, delete_time=0).order_by('sort', 'id')
        custom_fields = CustomerField.objects.filter(status=True, delete_time=0).order_by('sort', 'id')
        context['custom_fields'] = custom_fields
        context['import_fields_json'] = json.dumps(
            _get_customer_import_field_definitions(custom_fields),
            ensure_ascii=False
        )
        
        return context


# 公海客户管理视图
class PublicCustomerListView(LoginRequiredMixin, ListView):
    """公海客户列表视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Customer
    template_name = 'customer/public_customer_list.html'
    context_object_name = 'customers'

    def get_queryset(self):
        # 公海客户：没有归属人且未废弃的客户，并预加载关联外键以解决 N+1 查询问题
        return Customer.objects.select_related('customer_source').filter(delete_time=0, belong_uid=0, discard_time=0)

class PublicCustomerListDataView(LoginRequiredMixin, View):
    """公海客户列表数据API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        try:
            # 公海客户：没有归属人且未废弃的客户
            queryset = Customer.objects.filter(delete_time=0, belong_uid=0, discard_time=0)
            
            # 处理搜索
            search = request.GET.get('search', '')
            if search:
                queryset = queryset.filter(name__icontains=search)
            
            # 分页
            page = int(request.GET.get('page', 1))
            limit = CommonService.get_page_size(request, 20)
            start = (page - 1) * limit
            end = start + limit
            
            total_count = queryset.count()
            paginated_queryset = queryset[start:end]
            
            data = []
            for customer in paginated_queryset:
                # 获取客户等级名称
                grade_name = ''
                if customer.grade_id > 0:
                    try:
                        from apps.customer.models import CustomerGrade
                        grade = CustomerGrade.objects.filter(id=customer.grade_id).first()
                        grade_name = grade.title if grade else ''
                    except:
                        pass
                
                # 获取客户来源名称
                source_name = customer.customer_source.title if customer.customer_source else ''
                
                # 获取主要联系人
                from apps.customer.models import Contact
                primary_contact = Contact.objects.filter(customer=customer, is_primary=True).first()
                contact_name = primary_contact.contact_person if primary_contact else ''
                contact_phone = primary_contact.phone if primary_contact else ''
                
                data.append({
                    'id': customer.id,
                    'name': customer.name,
                    'province': customer.province,
                    'city': customer.city,
                    'district': customer.district,
                    'address': customer.address,
                    'grade': grade_name,
                    'grade_id': customer.grade_id,
                    'source': source_name,
                    'content': customer.content[:50] + '...' if customer.content and len(customer.content) > 50 else customer.content,
                    'contact_name': contact_name,
                    'contact_phone': contact_phone,
                    'market': customer.market[:50] + '...' if customer.market and len(customer.market) > 50 else customer.market,
                    'remark': customer.remark[:50] + '...' if customer.remark and len(customer.remark) > 50 else customer.remark,
                    'create_time': customer.create_time.strftime('%Y-%m-%d %H:%M:%S') if customer.create_time else '',
                    'tax_num': customer.tax_num,
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            })
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})

# 爬虫任务管理视图
class SpiderTaskListView(LoginRequiredMixin, ListView):
    """爬虫任务列表视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = SpiderTask
    template_name = 'customer/spider_task_list.html'
    context_object_name = 'tasks'

class SpiderTaskListDataView(LoginRequiredMixin, View):
    """爬虫任务列表数据API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        try:
            tasks = SpiderTask.objects.filter(delete_time=0).order_by('-create_time')
            
            # 处理搜索
            search = request.GET.get('search', '')
            if search:
                tasks = tasks.filter(task_name__icontains=search)
            
            # 分页
            page = int(request.GET.get('page', 1))
            limit = CommonService.get_page_size(request, 20)
            start = (page - 1) * limit
            end = start + limit
            
            total_count = tasks.count()
            paginated_tasks = tasks[start:end]
            
            data = []
            for task in paginated_tasks:
                data.append({
                    'id': task.id,
                    'task_name': task.task_name,
                    'spider_keywords': task.spider_keywords,
                    'status': task.status,
                    'status_display': task.get_status_display(),
                    'create_time': task.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'create_user': task.create_user.username if task.create_user else ''
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            })
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})

class SpiderTaskCreateView(LoginRequiredMixin, CreateView):
    """创建爬虫任务视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = SpiderTask
    template_name = 'customer/spider_task_form.html'
    fields = ['task_name', 'spider_keywords', 'data_region', 'industry_limit', 'province', 'insured_count', 'contact_phone']
    success_url = reverse_lazy('customer:spider_task_list')

    def form_valid(self, form):
        form.instance.create_user = self.request.user
        self.object = form.save()
        return JsonResponse({'code': 0, 'msg': '任务创建成功', 'data': {'id': self.object.id}})

    def form_invalid(self, form):
        return JsonResponse({'code': 1, 'msg': '任务创建失败', 'errors': form.errors}, status=400)

class SpiderTaskUpdateView(LoginRequiredMixin, UpdateView):
    """编辑爬虫任务视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = SpiderTask
    template_name = 'customer/spider_task_form.html'
    fields = ['task_name', 'spider_keywords', 'data_region', 'industry_limit', 'province', 'insured_count', 'contact_phone']
    success_url = reverse_lazy('customer:spider_task_list')

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'code': 0, 'msg': '任务设置已保存', 'data': {'id': self.object.id}})

    def form_invalid(self, form):
        return JsonResponse({'code': 1, 'msg': '任务设置保存失败', 'errors': form.errors}, status=400)

class SpiderTaskDeleteView(LoginRequiredMixin, DeleteView):
    """删除爬虫任务视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = SpiderTask
    success_url = reverse_lazy('customer:spider_task_list')

class SpiderTaskActionView(LoginRequiredMixin, View):
    """爬虫任务操作视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request, pk):
        try:
            task = SpiderTask.objects.get(id=pk, delete_time=0)
            action = request.POST.get('action')
            
            if action == 'start':
                result = self._run_spider_task(task, request.user)
                task.status = 2
                task.save(update_fields=['status'])
                return JsonResponse({
                    'code': 0,
                    'msg': f"任务执行完成，获取{result['fetched_count']}条，新增{result['saved_count']}条公海客户，跳过{result['skipped_count']}条",
                    'data': result
                })
            elif action == 'stop':
                task.status = 2  # 已停止
                task.save(update_fields=['status'])
                return JsonResponse({'code': 0, 'msg': '任务已停止'})
            else:
                return JsonResponse({'code': 1, 'msg': '无效的操作'})
                
        except SpiderTask.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '任务不存在'})
        except Exception as e:
            if 'task' in locals():
                task.status = 2
                task.save(update_fields=['status'])
            logger.error(f'执行爬虫任务失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'操作失败: {str(e)}'})

    def _run_spider_task(self, task, user):
        from apps.spider.spiders.tianyancha_spider import TianyanchaSpider
        from apps.spider.models import Company

        task.status = 1
        task.save(update_fields=['status'])

        keywords = [item.strip() for item in task.spider_keywords.replace('，', ',').split(',') if item.strip()]
        if not keywords:
            raise ValueError('爬虫关键词不能为空')

        spider = TianyanchaSpider()
        saved_count = 0
        skipped_count = 0
        fetched_count = 0
        source = CustomerSource.objects.filter(title='公开数据', delete_time=0).first()
        if not source:
            source = CustomerSource.objects.filter(title='爬虫获客', delete_time=0).first()

        existing_names = set(Customer.objects.filter(delete_time=0).values_list('name', flat=True))
        max_pages = self._get_task_max_pages(task)
        region = task.data_region or task.province or ''
        industry = task.industry_limit or ''

        for keyword in keywords:
            for page in range(1, max_pages + 1):
                try:
                    companies = spider.search_companies(keyword, page=page, region=region, industry=industry)
                except Exception as e:
                    raise ValueError(str(e))
                if not companies:
                    break

                for company_data in companies:
                    name = (company_data.get('name') or '').strip()
                    if not name:
                        continue
                    fetched_count += 1

                    company_url = company_data.get('tianyancha_url') or ''
                    detail_data = spider.get_company_detail(company_url) if company_url else {}
                    company_data.update({key: value for key, value in detail_data.items() if value})

                    if not self._match_task_filters(task, company_data):
                        skipped_count += 1
                        continue

                    Company.objects.update_or_create(
                        name=name,
                        defaults={key: value for key, value in spider._company_model_data(company_data).items() if key != 'name'}
                    )

                    if name in existing_names:
                        skipped_count += 1
                        continue

                    with transaction.atomic():
                        customer = Customer.objects.create(
                            name=name,
                            customer_source=source,
                            province=region,
                            address=company_data.get('address', '')[:255],
                            admin_id=user.id,
                            belong_uid=0,
                            content=company_data.get('registration_status', ''),
                            market=company_data.get('business_scope', ''),
                            remark=self._build_spider_remark(task, keyword, company_data),
                        )
                        self._save_customer_contact(customer, company_data)
                    existing_names.add(name)
                    saved_count += 1

                time.sleep(0.6)

        if saved_count == 0 and skipped_count == 0:
            raise ValueError('未获取到公开数据，请检查关键词、筛选条件或公开数据源访问状态')

        return {'saved_count': saved_count, 'skipped_count': skipped_count, 'fetched_count': fetched_count}

    def _get_task_max_pages(self, task):
        insured_count = task.insured_count or '不限'
        if insured_count in ['1000-4999', '5000以上']:
            return 3
        if insured_count in ['50-99', '100-999']:
            return 2
        return 1

    def _match_task_filters(self, task, company_data):
        contact_phone = task.contact_phone or '不限'
        phone = company_data.get('phone', '')
        if contact_phone == '有有效手机号' and not phone.startswith('1'):
            return False
        if contact_phone == '有固定电话' and phone.startswith('1'):
            return False
        if contact_phone == '有400/800电话' and not (phone.startswith('400') or phone.startswith('800')):
            return False
        return True

    def _save_customer_contact(self, customer, company_data):
        phone = company_data.get('phone', '')
        email = company_data.get('email', '')
        if not phone and not email:
            return
        Contact.objects.create(
            customer=customer,
            contact_person=company_data.get('legal_person') or customer.name,
            phone=phone or '未公开',
            email=email or None,
            is_primary=True
        )

    def _build_spider_remark(self, task, keyword, company_data):
        remark_items = [
            f'来源任务: {task.task_name}',
            f'关键词: {keyword}',
        ]
        if company_data.get('legal_person'):
            remark_items.append(f"法定代表人: {company_data.get('legal_person')}")
        if company_data.get('registered_capital'):
            remark_items.append(f"注册资本: {company_data.get('registered_capital')}")
        if company_data.get('establishment_date'):
            remark_items.append(f"成立日期: {company_data.get('establishment_date')}")
        if company_data.get('registration_status'):
            remark_items.append(f"登记状态: {company_data.get('registration_status')}")
        if company_data.get('business_scope'):
            remark_items.append(f"经营范围: {company_data.get('business_scope')}")
        if company_data.get('tianyancha_url'):
            remark_items.append(f"公开数据链接: {company_data.get('tianyancha_url')}")
        if company_data.get('address'):
            remark_items.append(f"注册地址: {company_data.get('address')}")
        return '\n'.join(remark_items)

# 获取员工列表视图
@login_required
def get_employee_list(request):
    """
    获取员工列表，用于客户共享选择
    """
    try:
        # 获取所有员工
        from apps.user.models import Admin
        employees = Admin.objects.filter(status=1).values('id', 'username', 'name')
        return JsonResponse(list(employees), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# 获取已共享员工视图
@login_required
def get_shared_employees(request, customer_id):
    """
    获取指定客户已共享的员工ID列表
    """
    try:
        customer = Customer.objects.get(id=customer_id, delete_time=0)
        # 解析share_ids字段，获取已共享的员工ID列表
        shared_ids = customer.share_ids.split(',') if customer.share_ids else []
        # 过滤空字符串并转换为整数
        shared_ids = [int(id) for id in shared_ids if id]
        return JsonResponse(shared_ids, safe=False)
    except Customer.DoesNotExist:
        return JsonResponse([], safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# 设置客户共享视图
@login_required
def set_customer_share(request, customer_id):
    """
    设置客户共享给指定员工
    """
    try:
        # 获取当前用户
        user = request.user
        # 获取客户对象
        customer = get_object_or_404(Customer, id=customer_id, delete_time=0)
        
        # 检查权限：只有客户归属人可以设置共享
        if customer.belong_uid != user.id and not (hasattr(user, 'is_superuser') and user.is_superuser):
            return JsonResponse({'status': 'error', 'msg': '您没有权限设置此客户的共享'}, status=403)
        
        # 获取要共享的员工ID列表
        shared_user_ids = request.POST.getlist('user_ids[]', [])
        # 过滤并转换为整数
        shared_user_ids = [int(id) for id in shared_user_ids if id.isdigit()]
        
        # 转换为逗号分隔的字符串
        share_ids_str = ','.join(map(str, shared_user_ids))
        
        # 更新客户的共享字段
        customer.share_ids = share_ids_str
        customer.save()
        
        # 添加操作日志
        SystemLog.objects.create(
            user=request.user,
            log_type='update',
            module='客户管理',
            action='设置客户共享',
            content=f'将客户 "{customer.name}" 共享给员工ID: {share_ids_str}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        
        return JsonResponse({'status': 'success', 'msg': '客户共享设置成功'})
    except Exception as e:
        logger.error(f"设置客户共享失败: {str(e)}")
        return JsonResponse({'status': 'error', 'msg': f'操作失败: {str(e)}'}, status=500)

# 公海客户认领视图
@login_required
def claim_public_customer(request, customer_id):
    """
    认领公海客户
    """
    try:
        customer = Customer.objects.get(id=customer_id, delete_time=0)
        
        # 检查客户是否在公海（没有归属人）
        if customer.belong_uid != 0:
            return JsonResponse({'status': 'error', 'msg': '该客户已被认领'})
        
        # 设置客户归属人为当前用户
        customer.belong_uid = request.user.id
        customer.belong_did = request.user.main_department_id if hasattr(request.user, 'main_department_id') else 0
        customer.belong_time = int(timezone.now().timestamp())
        customer.save()
        
        return JsonResponse({'status': 'success', 'msg': '客户认领成功'})
    except Customer.DoesNotExist:
        return JsonResponse({'status': 'error', 'msg': '客户不存在'})
    except Exception as e:
        logger.error(f'认领客户失败: {str(e)}')
        return JsonResponse({'status': 'error', 'msg': f'认领失败: {str(e)}'})

# 客户移入废弃列表视图
@login_required
def discard_customer(request, customer_id):
    """
    将客户移入废弃列表
    """
    try:
        customer = Customer.objects.get(id=customer_id, delete_time=0)
        
        # 将客户移入废弃列表：
        # 1. 设置discard_time为当前时间戳
        # 2. 保留其他信息
        customer.discard_time = int(timezone.now().timestamp())
        customer.save()
        
        return JsonResponse({'status': 'success', 'msg': '客户已成功移入废弃列表'})
    except Customer.DoesNotExist:
        return JsonResponse({'status': 'error', 'msg': '客户不存在'})
    except Exception as e:
        logger.error(f'移入废弃列表失败: {str(e)}')
        return JsonResponse({'status': 'error', 'msg': f'操作失败: {str(e)}'})

# 废弃客户恢复视图
@login_required
def restore_customer(request, customer_id):
    """
    将废弃客户恢复至公海
    """
    try:
        customer = Customer.objects.get(id=customer_id, delete_time=0)
        
        # 将废弃客户恢复至公海：
        # 1. 清除discard_time
        # 2. 清除归属人ID和部门ID（恢复到公海）
        customer.discard_time = 0
        customer.belong_uid = 0
        customer.belong_did = 0
        customer.save()
        
        return JsonResponse({'status': 'success', 'msg': '客户已成功恢复至公海'})
    except Customer.DoesNotExist:
        return JsonResponse({'status': 'error', 'msg': '客户不存在'})
    except Exception as e:
        logger.error(f'恢复客户失败: {str(e)}')
        return JsonResponse({'status': 'error', 'msg': f'操作失败: {str(e)}'})

# 废弃客户清理视图
@login_required
def clean_abandoned_customers(request):
    """
    清理过期废弃客户
    """
    try:
        # 获取过期时间（默认90天）
        days = int(request.GET.get('days', 90))
        cutoff_time = int((timezone.now() - timedelta(days=days)).timestamp())
        
        # 清理过期废弃客户：
        # 1. 只清理discard_time大于0且超过过期时间的客户
        # 2. 使用软删除，设置delete_time为当前时间戳
        deleted_count = Customer.objects.filter(
            delete_time=0,
            discard_time__gt=0,
            discard_time__lt=cutoff_time
        ).update(
            delete_time=int(timezone.now().timestamp())
        )
        
        return JsonResponse({'status': 'success', 'msg': f'成功清理{deleted_count}个过期废弃客户'})
    except Exception as e:
        logger.error(f'清理废弃客户失败: {str(e)}')
        return JsonResponse({'status': 'error', 'msg': f'操作失败: {str(e)}'})

# 自动将长期未跟进的客户移入公海
@login_required
def auto_move_to_public_pool(request):
    """
    自动将长期未跟进的客户移入公海
    """
    try:
        # 获取未跟进天数（默认30天）
        days = int(request.GET.get('days', 30))
        cutoff_time = int((timezone.now() - timedelta(days=days)).timestamp())
        
        # 查找符合条件的客户：
        # 1. 非删除状态
        # 2. 有归属人（belong_uid > 0）
        # 3. 最近跟进时间follow_time < cutoff_time
        customers_to_move = Customer.objects.filter(
            delete_time=0,
            belong_uid__gt=0,
            follow_time__lt=cutoff_time,
            discard_time=0
        )
        
        # 记录要移动的客户数量
        move_count = customers_to_move.count()
        
        if move_count > 0:
            # 开始事务
            with transaction.atomic():
                # 批量更新客户信息
                customers_to_move.update(
                    belong_uid=0,  # 移除归属人
                    belong_did=0,  # 移除归属部门
                    share_ids='',  # 清空共享
                    distribute_time=int(timezone.now().timestamp())  # 更新分配时间
                )
                
                # 记录操作日志
                for customer in customers_to_move:
                    SystemLog.objects.create(
                        user=request.user,
                        log_type='update',
                        module='客户管理',
                        action='自动移入公海',
                        content=f'客户 "{customer.name}" 因超过{days}天未跟进，自动移入公海',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT')
                    )
        
        return JsonResponse({'status': 'success', 'msg': f'成功将{move_count}个长期未跟进客户移入公海'})
    except Exception as e:
        logger.error(f'自动移入公海失败: {str(e)}')
        return JsonResponse({'status': 'error', 'msg': f'操作失败: {str(e)}'})

# 废弃客户管理视图
class AbandonedCustomerListView(LoginRequiredMixin, ListView):
    """废弃客户列表视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Customer
    template_name = 'customer/abandoned_customer_list.html'
    context_object_name = 'customers'

    def get_queryset(self):
        # 废弃客户：discard_time > 0的客户
        return Customer.objects.filter(delete_time=0).exclude(discard_time=0)

class AbandonedCustomerListDataView(LoginRequiredMixin, View):
    """废弃客户列表数据API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        try:
            queryset = Customer.objects.filter(delete_time=0).exclude(discard_time=0)
            
            # 处理搜索
            search = request.GET.get('search', '')
            if search:
                queryset = queryset.filter(name__icontains=search)
            
            # 分页
            page = int(request.GET.get('page', 1))
            limit = CommonService.get_page_size(request, 20)
            start = (page - 1) * limit
            end = start + limit
            
            total_count = queryset.count()
            paginated_queryset = queryset[start:end]
            
            data = []
            for customer in paginated_queryset:
                data.append({
                    'id': customer.id,
                    'name': customer.name,
                    'province': customer.province,
                    'city': customer.city,
                    'address': customer.address,
                    'discard_time': datetime.fromtimestamp(customer.discard_time).strftime('%Y-%m-%d %H:%M:%S') if customer.discard_time > 0 else '',
                    'create_time': customer.create_time.strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            })
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})

# 客户订单管理视图
class CustomerOrderListView(LoginRequiredMixin, ListView):
    """客户订单列表视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = CustomerOrder
    template_name = 'customer/order/list.html'
    context_object_name = 'orders'

    def get_queryset(self):
        # 获取当前用户有权限查看的客户ID列表
        user = self.request.user
        if hasattr(user, 'is_superuser') and user.is_superuser:
            # 超级管理员可以查看所有订单
            return CustomerOrder.objects.select_related('customer').filter(delete_time=0)
        else:
            # 获取当前用户有权限查看的客户
            allowed_customers = Customer.objects.filter(
                models.Q(belong_uid=user.id) | 
                models.Q(share_ids__contains=str(user.id))
            ).filter(delete_time=0)
            # 只显示这些客户的订单
            return CustomerOrder.objects.select_related('customer').filter(
                customer__in=allowed_customers,
                delete_time=0
            )

class CustomerOrderListDataView(LoginRequiredMixin, View):
    """客户订单列表数据API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        try:
            # 获取当前用户有权限查看的客户
            user = self.request.user
            if hasattr(user, 'is_superuser') and user.is_superuser:
                # 超级管理员可以查看所有订单
                orders = CustomerOrder.objects.filter(delete_time=0).select_related('customer').order_by('-create_time')
            else:
                # 获取当前用户有权限查看的客户
                allowed_customers = Customer.objects.filter(
                    models.Q(belong_uid=user.id) | 
                    models.Q(share_ids__contains=str(user.id))
                ).filter(delete_time=0)
                # 只显示这些客户的订单
                orders = CustomerOrder.objects.filter(
                    customer__in=allowed_customers,
                    delete_time=0
                ).select_related('customer').order_by('-create_time')
            
            # 处理搜索
            search = request.GET.get('search', '')
            if search:
                orders = orders.filter(Q(order_number__icontains=search) | Q(customer__name__icontains=search))
            
            # 分页
            page = int(request.GET.get('page', 1))
            limit = CommonService.get_page_size(request, 20)
            start = (page - 1) * limit
            end = start + limit
            
            total_count = orders.count()
            paginated_orders = orders[start:end]
            
            data = []
            for order in paginated_orders:
                data.append({
                    'id': order.id,
                    'order_number': order.order_number,
                    'customer_name': order.customer.name,
                    'product_name': order.product_name,
                    'amount': str(order.amount),
                    'status': order.status,
                    'status_display': order.get_status_display(),
                    'order_date': order.order_date.strftime('%Y-%m-%d') if order.order_date else '',
                    'create_time': order.create_time.strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            })
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})

class CustomerOrderCreateView(LoginRequiredMixin, View):
    """创建客户订单视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        customer_id = request.GET.get('customer_id')
        if customer_id:
            try:
                # 获取当前用户
                user = request.user
                # 检查客户是否存在且当前用户有权限查看
                customer = get_object_or_404(Customer, id=customer_id, delete_time=0)
                
                # 检查权限
                if not (hasattr(user, 'is_superuser') and user.is_superuser):
                    if customer.belong_uid != user.id and str(user.id) not in customer.share_ids.split(','):
                        return JsonResponse({'status': 'error', 'message': '您没有权限访问此客户'}, json_dumps_params={'ensure_ascii': False})
                        
                # 获取客户的合同列表
                contracts = customer.contracts.filter(delete_time=0)
                
                # 获取产品分类和产品数据
                from apps.contract.models import ProductCate
                product_categories = ProductCate.objects.filter(status=1).prefetch_related('product_set')
                
                # 获取所有启用的自定义订单字段
                from apps.customer.models import OrderField
                order_fields = OrderField.objects.filter(is_active=True)
                
                # 生成默认订单编号
                import time
                default_order_number = f'ORD{int(time.time())}{customer.id}'
                
                # 初始化空的现有值字典，避免模板中访问不存在的变量
                existing_values = {}
                
                # 导入 datetime 模块获取当前时间
                from datetime import datetime
                now = datetime.now()
                
                return render(request, 'customer/customer_order_form.html', {
                    'customer': customer,
                    'contracts': contracts,
                    'product_categories': product_categories,
                    'default_order_number': default_order_number,
                    'order_fields': order_fields,
                    'existing_values': existing_values,
                    'now': now  # 传递当前时间到模板
                })
            except Customer.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': '客户不存在'}, json_dumps_params={'ensure_ascii': False})
        # 初始化空的现有值字典，避免模板中访问不存在的变量
        existing_values = {}
        
        # 导入 datetime 模块获取当前时间
        from datetime import datetime
        now = datetime.now()
        
        return render(request, 'customer/customer_order_form.html', {
            'existing_values': existing_values,
            'now': now  # 传递当前时间到模板
        })
    
    def post(self, request):
        try:
            customer_id = request.POST.get('customer_id')
            order_number = request.POST.get('order_number')
            product_name = request.POST.get('product_name')
            amount = request.POST.get('amount')
            order_date = request.POST.get('order_date')
            status = request.POST.get('status')
            contract_id = request.POST.get('contract_id')  # 新增合同关联
            description = request.POST.get('description', '')
            remark = request.POST.get('remark', '')
            
            # 检查必填字段是否为空（包括空字符串的情况）
            required_fields = [
                ('customer_id', customer_id),
                ('order_number', order_number),
                ('product_name', product_name),
                ('amount', amount),
                ('order_date', order_date),
                ('status', status)
            ]
            
            missing_fields = []
            for field_name, field_value in required_fields:
                if not field_value or str(field_value).strip() == '':
                    missing_fields.append(field_name)
            
            if missing_fields:
                return JsonResponse({'status': 'error', 'message': f'必填字段不能为空: {", ".join(missing_fields)}'})
            
            # 获取当前用户
            user = request.user
            # 检查客户是否存在且当前用户有权限查看
            customer = get_object_or_404(Customer, id=customer_id, delete_time=0)
            
            # 检查权限
            if not (hasattr(user, 'is_superuser') and user.is_superuser):
                if customer.belong_uid != user.id and str(user.id) not in customer.share_ids.split(','):
                    return JsonResponse({'status': 'error', 'message': '您没有权限访问此客户'}, json_dumps_params={'ensure_ascii': False})
            
            # 获取关联合同（如果选择了）
            contract = None
            if contract_id:
                try:
                    contract = customer.contracts.get(id=contract_id, delete_time=0)
                except:
                    pass
            
            # 创建订单
            order = CustomerOrder.objects.create(
                customer=customer,
                contract=contract,
                order_number=order_number,
                product_name=product_name,
                amount=amount,
                order_date=order_date,
                status=status,
                description=description,
                remark=remark,
                create_user=request.user
            )
            
            # 处理自定义字段值
            from apps.customer.models import OrderField
            order_fields = OrderField.objects.filter(is_active=True)
            for field in order_fields:
                field_key = f'custom_field_{field.id}'
                if field_key in request.POST:
                    # 对于复选框类型，值可能是列表
                    if field.field_type == 'checkbox':
                        values = request.POST.getlist(field_key)
                        value = ','.join(values)
                    else:
                        value = request.POST.get(field_key)
                    
                    if value:
                        # 保存自定义字段值
                        CustomerOrderCustomFieldValue.objects.create(
                            order=order,
                            field=field,
                            value=value
                        )
            
            selected_targets = _get_selected_auto_create_targets(
                request,
                'contract',
                'project',
            )
            if selected_targets:
                try:
                    self._auto_generate_related_records(order, request.user, selected_targets)
                except Exception as auto_gen_error:
                    # 记录错误但不影响订单创建
                    logger.error(f"自动生成相关记录失败: {str(auto_gen_error)}")
            
            return JsonResponse({'status': 'success', 'message': '订单添加成功'}, json_dumps_params={'ensure_ascii': False})
            
        except Customer.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '客户不存在'}, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f"创建客户订单失败: {str(e)}")
            return JsonResponse({'status': 'error', 'message': f'添加失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})
    
    def _auto_generate_related_records(self, order, user, selected_targets):
        """
        根据用户勾选结果生成与订单相关的记录：合同、项目
        """
        import time
        
        if 'contract' in selected_targets:
            try:
                from apps.customer.models import CustomerContract
                CustomerContract.objects.create(
                    customer_id=order.customer_id,
                    name=f"{order.product_name}合同",
                    contract_number=f"CONT-ORD-{order.order_number}-{int(time.time())}",
                    amount=order.amount,
                    sign_date=order.order_date if order.order_date else None,
                    end_date=None,
                    status='pending',
                    create_user_id=user.id,
                    auto_generated=True,
                )
            except Exception as e:
                logger.error(f"创建合同记录失败: {e}")

        if 'project' in selected_targets:
            try:
                from apps.project.models import Project
                Project.objects.create(
                    name=order.product_name,
                    code=f"PROJ-ORD-{order.order_number}-{int(time.time())}",
                    description=f"订单项目：{order.product_name}",
                    customer_id=order.customer_id,
                    contract=None,
                    budget=order.amount,
                    status=1,
                    priority=2,
                    progress=0,
                    creator=user,
                    auto_generated=True,
                )
            except Exception as e:
                logger.error(f"创建项目记录失败: {e}")

class CustomerOrderUpdateView(LoginRequiredMixin, UpdateView):
    """编辑客户订单视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = CustomerOrder
    template_name = 'customer/order/edit.html'
    fields = ['customer', 'order_number', 'product_name', 'amount', 'order_date', 'status', 'description', 'remark']
    context_object_name = 'order'
    success_url = reverse_lazy('customer:customer_order_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 添加自定义订单字段到上下文
        from apps.customer.models import OrderField
        context['order_fields'] = OrderField.objects.filter(is_active=True)
        # 获取现有的自定义字段值
        context['custom_field_values'] = {}
        for custom_value in self.object.custom_fields.all():
            context['custom_field_values'][custom_value.field_id] = custom_value.value
        return context
    
    def post(self, request, *args, **kwargs):
        # 获取订单对象
        self.object = self.get_object()
        
        # 使用父类的post方法处理常规字段
        response = super().post(request, *args, **kwargs)
        
        # 处理自定义字段值
        from apps.customer.models import OrderField
        order_fields = OrderField.objects.filter(is_active=True)
        
        # 删除现有的自定义字段值
        self.object.custom_fields.all().delete()
        
        # 添加新的自定义字段值
        for field in order_fields:
            field_key = f'custom_field_{field.id}'
            if field_key in request.POST:
                # 对于复选框类型，值可能是列表
                if field.field_type == 'checkbox':
                    values = request.POST.getlist(field_key)
                    value = ','.join(values)
                else:
                    value = request.POST.get(field_key)
                
                if value:
                    # 保存自定义字段值
                    CustomerOrderCustomFieldValue.objects.create(
                        order=self.object,
                        field=field,
                        value=value
                    )
        
        return response

class CustomerOrderDeleteView(LoginRequiredMixin, DeleteView):
    """删除客户订单视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = CustomerOrder
    success_url = reverse_lazy('customer:customer_order_list')


class CustomerOrderDetailView(LoginRequiredMixin, DetailView):
    """订单详情视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = CustomerOrder
    template_name = 'customer/order/detail.html'
    context_object_name = 'order'


class CustomerOrderPaymentView(LoginRequiredMixin, View):
    """订单收款视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request, pk):
        try:
            # 获取订单对象
            order = get_object_or_404(CustomerOrder, pk=pk)
            
            # 获取请求数据
            amount = request.POST.get('amount')
            payment_method = request.POST.get('payment_method')
            payment_date = request.POST.get('payment_date')
            remark = request.POST.get('remark')
            
            # 基本验证
            if not amount:
                return JsonResponse({'status': 'error', 'message': '收款金额不能为空'})
            
            try:
                amount = float(amount)
                if amount <= 0:
                    return JsonResponse({'status': 'error', 'message': '收款金额必须大于0'})
            except ValueError:
                return JsonResponse({'status': 'error', 'message': '收款金额格式不正确'})
            
            if not payment_method:
                return JsonResponse({'status': 'error', 'message': '请选择付款方式'})
            
            if not payment_date:
                return JsonResponse({'status': 'error', 'message': '请选择收款日期'})
            
            # 使用事务处理收款操作
            with transaction.atomic():
                # 更新订单状态和收款信息
                # 根据模型中的字段进行更新
                order.finance_status = 'synced'  # 更新为已同步状态
                
                # 记录收款信息到备注中
                if remark:
                    current_remark = order.remark or ''
                    payment_info = f"\n--- 收款信息 ---\n收款金额: {amount}\n付款方式: {payment_method}\n收款日期: {payment_date}\n备注: {remark}\n--- 收款信息结束 ---".strip()
                    order.remark = current_remark + ("\n" if current_remark else "") + payment_info
                
                # 更新订单状态为已完成
                order.status = 'completed'
                order.save()
                
                # 这里可以根据实际需求添加更复杂的业务逻辑
                # 例如创建收款记录、更新财务系统等
                
            return JsonResponse({'status': 'success', 'message': '收款操作成功'})
        except Exception as e:
            logger.error(f"订单收款失败 (订单ID: {pk}): {str(e)}")
            return JsonResponse({'status': 'error', 'message': '收款操作失败，请稍后重试'})


class CustomerOrderBatchDeleteView(LoginRequiredMixin, View):
    """批量删除订单视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            ids = data.get('ids', [])
            if not ids:
                return JsonResponse({'status': 'error', 'message': '请选择要删除的订单'})
            
            CustomerOrder.objects.filter(id__in=ids).delete()
            return JsonResponse({'status': 'success', 'message': f'成功删除{len(ids)}个订单'})
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': '无效的请求数据'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

# 机会线索管理视图
class OpportunityListView(LoginRequiredMixin, ListView):
    """机会线索列表视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Customer
    template_name = 'customer/opportunity_list.html'
    context_object_name = 'opportunities'

    def get_queryset(self):
        # 机会线索：意向状态为高意向的客户
        queryset = Customer.objects.filter(delete_time=0, intent_status__in=[1, 2, 3])
        
        # 添加数据权限过滤
        user = self.request.user
        
        # 超级管理员可以查看所有客户
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return queryset
        
        # 数据权限过滤：只能查看自己的客户及共享给自己的客户
        queryset = queryset.filter(
            models.Q(belong_uid=user.id) | 
            models.Q(share_ids__contains=str(user.id))
        )
        
        return queryset

class OpportunityListDataView(LoginRequiredMixin, View):
    """机会线索列表数据API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        try:
            queryset = Customer.objects.filter(delete_time=0, intent_status__in=[1, 2, 3])
            
            # 添加数据权限过滤
            user = self.request.user
            
            # 超级管理员可以查看所有客户
            if not (hasattr(user, 'is_superuser') and user.is_superuser):
                # 数据权限过滤：只能查看自己的客户及共享给自己的客户
                queryset = queryset.filter(
                    models.Q(belong_uid=user.id) | 
                    models.Q(share_ids__contains=str(user.id))
                )
            
            # 处理搜索
            search = request.GET.get('search', '')
            if search:
                queryset = queryset.filter(name__icontains=search)
            
            # 分页
            page = int(request.GET.get('page', 1))
            limit = CommonService.get_page_size(request, 20)
            start = (page - 1) * limit
            end = start + limit
            
            total_count = queryset.count()
            paginated_queryset = queryset[start:end]
            
            data = []
            for customer in paginated_queryset:
                data.append({
                    'id': customer.id,
                    'name': customer.name,
                    'province': customer.province,
                    'city': customer.city,
                    'intent_status': customer.intent_status,
                    'follow_time': customer.get_follow_time_display(),
                    'next_time': customer.get_next_time_display(),
                    'create_time': customer.create_time.strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            })
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})

# 跟进记录管理视图
class FollowRecordListView(LoginRequiredMixin, ListView):
    """跟进记录列表视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = FollowRecord
    template_name = 'customer/follow_record_list.html'
    context_object_name = 'records'

    def get_queryset(self):
        # 获取当前用户有权限查看的客户ID列表
        user = self.request.user
        if hasattr(user, 'is_superuser') and user.is_superuser:
            # 超级管理员可以查看所有跟进记录
            return FollowRecord.objects.filter(delete_time=0)
        else:
            # 获取当前用户有权限查看的客户
            allowed_customers = Customer.objects.filter(
                models.Q(belong_uid=user.id) | 
                models.Q(share_ids__contains=str(user.id))
            ).filter(delete_time=0)
            # 只显示这些客户的跟进记录
            return FollowRecord.objects.filter(
                customer__in=allowed_customers,
                delete_time=0
            )

class FollowRecordListDataView(LoginRequiredMixin, View):
    """跟进记录列表数据API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        try:
            # 获取当前用户
            user = self.request.user
            
            # 根据用户权限获取可查看的跟进记录
            if hasattr(user, 'is_superuser') and user.is_superuser:
                # 超级管理员可以查看所有跟进记录
                records = FollowRecord.objects.filter(delete_time=0).select_related('customer', 'follow_user').order_by('-follow_time')
            else:
                # 获取当前用户有权限查看的客户
                allowed_customers = Customer.objects.filter(
                    models.Q(belong_uid=user.id) | 
                    models.Q(share_ids__contains=str(user.id))
                ).filter(delete_time=0)
                # 只显示这些客户的跟进记录
                records = FollowRecord.objects.filter(
                    customer__in=allowed_customers,
                    delete_time=0
                ).select_related('customer', 'follow_user').order_by('-follow_time')
            
            # 处理搜索
            search = request.GET.get('search', '')
            if search:
                records = records.filter(Q(customer__name__icontains=search) | Q(content__icontains=search))
            
            # 分页
            page = int(request.GET.get('page', 1))
            limit = CommonService.get_page_size(request, 20)
            start = (page - 1) * limit
            end = start + limit
            
            total_count = records.count()
            paginated_records = records[start:end]
            
            data = []
            for record in paginated_records:
                data.append({
                    'id': record.id,
                    'customer_name': record.customer.name,
                    'follow_type': record.follow_type,
                    'follow_type_display': record.get_follow_type_display(),
                    'content': record.content,
                    'follow_user': record.follow_user.username,
                    'follow_time': record.follow_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'next_follow_time': record.next_follow_time.strftime('%Y-%m-%d %H:%M:%S') if record.next_follow_time else ''
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            })
        except Exception as e:
            return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})

class FollowRecordCreateView(LoginRequiredMixin, View):
    """创建跟进记录视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        customer_id = request.GET.get('customer_id')
        if customer_id:
            try:
                # 获取当前用户
                user = request.user
                # 检查客户是否存在且当前用户有权限查看
                customer = get_object_or_404(Customer, id=customer_id, delete_time=0)
                
                # 检查权限
                if not (hasattr(user, 'is_superuser') and user.is_superuser):
                    if customer.belong_uid != user.id and str(user.id) not in customer.share_ids.split(','):
                        return JsonResponse({'status': 'error', 'message': '您没有权限访问此客户'}, json_dumps_params={'ensure_ascii': False})
                        
                # 获取客户的联系人列表
                contacts = customer.contacts.all()
                # 获取所有启用的自定义跟进字段
                from apps.customer.models import FollowField
                follow_fields = FollowField.objects.filter(is_active=True).order_by('sort_order')
                
                return render(request, 'customer/follow_record_form.html', {
                    'customer': customer,
                    'contacts': contacts,
                    'follow_fields': follow_fields,
                    'existing_values': {}  # 添加跟进时没有现有值
                })
            except Customer.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': '客户不存在'}, json_dumps_params={'ensure_ascii': False})
        return render(request, 'customer/follow_record_form.html', {
            'existing_values': {}  # 即使没有客户ID也传递空字典
        })
    
    def post(self, request):
        try:
            customer_id = request.POST.get('customer_id')
            follow_type = request.POST.get('follow_type')
            contact_id = request.POST.get('contact_id')  # 新增联系人选择
            content = request.POST.get('content')
            next_follow_time = request.POST.get('next_follow_time')
            
            # 检查必填字段是否为空
            missing_fields = []
            if not customer_id or customer_id.strip() == '':
                missing_fields.append('客户ID')
            if not follow_type or follow_type.strip() == '':
                missing_fields.append('跟进方式')
            if not content or content.strip() == '':
                missing_fields.append('跟进内容')
            
            if missing_fields:
                return JsonResponse({'status': 'error', 'message': f'以下字段不能为空: {", ".join(missing_fields)}'})
            
            # 获取当前用户
            user = request.user
            # 检查客户是否存在且当前用户有权限查看
            customer = get_object_or_404(Customer, id=customer_id, delete_time=0)
            
            # 检查权限
            if not (hasattr(user, 'is_superuser') and user.is_superuser):
                if customer.belong_uid != user.id and str(user.id) not in customer.share_ids.split(','):
                    return JsonResponse({'status': 'error', 'message': '您没有权限访问此客户'}, json_dumps_params={'ensure_ascii': False})
            
            # 创建跟进记录
            follow_record = FollowRecord.objects.create(
                customer=customer,
                follow_type=follow_type,
                content=content,
                follow_user=request.user,
                next_follow_time=next_follow_time if next_follow_time else None
            )
            
            # 如果选择了联系人，可以在内容中记录
            if contact_id:
                try:
                    contact = customer.contacts.get(id=contact_id)
                    follow_record.content = f"联系人：{contact.contact_person}({contact.phone})\n{content}"
                    follow_record.save()
                except:
                    pass
            
            # 保存自定义字段值
            from apps.customer.models import FollowField, FollowRecordCustomFieldValue
            follow_fields = FollowField.objects.filter(is_active=True)
            
            for field in follow_fields:
                field_value = request.POST.get(f'custom_field_{field.id}')
                if field_value is not None:
                    # 处理复选框类型
                    if field.field_type == 'checkbox':
                        selected_values = request.POST.getlist(f'custom_field_{field.id}')
                        field_value = ','.join(selected_values)
                    
                    # 保存或更新自定义字段值
                    FollowRecordCustomFieldValue.objects.update_or_create(
                        follow_record=follow_record,
                        field=field,
                        defaults={'value': field_value}
                    )
            
            # 更新客户的最新跟进时间
            customer.follow_time = int(timezone.now().timestamp())
            customer.save()
            
            return JsonResponse({'status': 'success', 'message': '跟进记录添加成功'}, json_dumps_params={'ensure_ascii': False})
            
        except Customer.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '客户不存在'}, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f"创建跟进记录失败: {str(e)}")
            return JsonResponse({'status': 'error', 'message': f'添加失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})

class FollowRecordUpdateView(LoginRequiredMixin, UpdateView):
    """编辑跟进记录视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = FollowRecord
    template_name = 'customer/follow_record_form.html'
    fields = ['customer', 'follow_type', 'content', 'next_follow_time']
    success_url = reverse_lazy('customer:follow_record_list')
    
    def get_context_data(self, **kwargs):
        """获取上下文数据，添加自定义跟进字段"""
        context = super().get_context_data(**kwargs)
        # 获取所有启用的自定义跟进字段
        from customer.models import FollowField
        context['follow_fields'] = FollowField.objects.filter(is_active=True)
        
        # 获取现有的自定义字段值
        from customer.models import FollowRecordCustomFieldValue
        record = self.object
        existing_values = {}
        if record:
            custom_values = FollowRecordCustomFieldValue.objects.filter(follow_record=record)
            for cv in custom_values:
                existing_values[cv.field_id] = cv.value
        context['existing_values'] = existing_values
        
        return context
    
    def post(self, request, *args, **kwargs):
        """处理表单提交，保存自定义字段值"""
        self.object = self.get_object()
        response = super().post(request, *args, **kwargs)
        
        if self.object:
            # 处理自定义字段值
            from customer.models import FollowField, FollowRecordCustomFieldValue
            follow_fields = FollowField.objects.filter(is_active=True)
            
            # 删除旧的自定义字段值
            FollowRecordCustomFieldValue.objects.filter(follow_record=self.object).delete()
            
            # 保存新的自定义字段值
            for field in follow_fields:
                field_key = f'custom_field_{field.id}'
                
                # 处理复选框类型
                if field.field_type == 'checkbox':
                    # 获取所有选中的值
                    checkbox_values = request.POST.getlist(field_key)
                    if checkbox_values:
                        value = ','.join(checkbox_values)
                        FollowRecordCustomFieldValue.objects.create(
                            follow_record=self.object,
                            field_id=field.id,
                            value=value
                        )
                else:
                    # 处理其他类型
                    value = request.POST.get(field_key)
                    if value is not None and value.strip() != '':
                        FollowRecordCustomFieldValue.objects.create(
                            follow_record=self.object,
                            field_id=field.id,
                            value=value.strip()
                        )
        
        return response

# 拨号记录管理视图（简单实现）
class CallRecordListView(LoginRequiredMixin, TemplateView):
    """拨号记录列表视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    template_name = 'customer/call_record_list.html'

class CallRecordListDataView(LoginRequiredMixin, View):
    """拨号记录列表数据API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        from .models import CallRecord
        from django.db.models import Count, Sum, Q
        from django.utils import timezone
        
        # 获取当前用户的拨号记录
        queryset = CallRecord.objects.filter(create_user=request.user)
        
        # 处理搜索条件
        search = request.GET.get('search', '')
        if search:
            queryset = queryset.filter(Q(phone__icontains=search) | Q(customer_name__icontains=search))
        
        # 处理分页
        page = int(request.GET.get('page', 1))
        limit = CommonService.get_page_size(request, 20)
        start = (page - 1) * limit
        end = start + limit
        
        # 获取总记录数
        total_count = queryset.count()
        
        # 获取分页数据
        call_records = list(queryset.order_by('-call_time')[start:end].values())
        
        # 获取所有电话号码的拨号次数
        phone_call_counts = CallRecord.objects.filter(create_user=request.user).values('phone').annotate(
            total_count=Count('id')
        )
        
        # 构建电话号码到拨号次数的映射
        call_count_map = {item['phone']: item['total_count'] for item in phone_call_counts}
        
        # 为每条记录添加累计拨号次数
        for record in call_records:
            record['call_count'] = call_count_map.get(record['phone'], 0)
            
            # 格式化通话状态
            status_map = {
                0: '未接通',
                1: '已通话',
                2: '呼叫失败',
                3: '通话中'
            }
            record['status'] = status_map.get(record['status'], '未知')
            
            # 格式化通话时长（秒转分:秒）
            duration = record['duration']
            minutes = duration // 60
            seconds = duration % 60
            record['duration'] = f'{minutes:02d}:{seconds:02d}'
            
            # 格式化拨号时间
            call_time = record['call_time']
            from datetime import datetime
            from django.utils.timezone import make_aware, get_current_timezone, is_aware
            
            try:
                if isinstance(call_time, str):
                    # 如果已经是字符串，解析并转换为上海时间
                    if call_time.endswith('Z'):
                        # UTC时间字符串
                        try:
                            # 解析带毫秒的UTC时间字符串
                            utc_time = datetime.strptime(call_time, '%Y-%m-%dT%H:%M:%S.%fZ')
                        except ValueError:
                            # 解析不带毫秒的UTC时间字符串
                            utc_time = datetime.strptime(call_time, '%Y-%m-%dT%H:%M:%SZ')
                        
                        # 转换为带时区的datetime对象
                        aware_time = make_aware(utc_time)
                        # 转换为上海时间
                        local_time = aware_time.astimezone(get_current_timezone())
                        # 格式化本地时间
                        record['call_time'] = local_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        # 非UTC时间字符串，尝试解析
                        try:
                            # 尝试解析为datetime对象
                            dt = datetime.strptime(call_time, '%Y-%m-%d %H:%M:%S')
                            # 格式化时间
                            record['call_time'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            # 解析失败，直接使用
                            record['call_time'] = call_time
                else:
                    # 直接格式化时间
                    if is_aware(call_time):
                        # 带时区的datetime对象，转换为本地时间
                        local_time = call_time.astimezone(get_current_timezone())
                        record['call_time'] = local_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        # 不带时区的datetime对象，直接格式化
                        record['call_time'] = call_time.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                # 记录错误并使用当前时间
                logger.error(f'时间格式化错误: {e}, 原始时间: {call_time}')
                # 使用当前时间作为替代
                record['call_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 获取统计数据
        today = timezone.now().date()
        today_start = timezone.datetime(today.year, today.month, today.day, 0, 0, 0)
        
        # 今日拨号总数量
        today_call_count = CallRecord.objects.filter(
            create_user=request.user,
            call_time__gte=today_start
        ).count()
        
        # 系统累计拨号总数量
        total_call_count = CallRecord.objects.filter(create_user=request.user).count()
        
        # 今日通话总时长（秒）
        today_duration = CallRecord.objects.filter(
            create_user=request.user,
            call_time__gte=today_start,
            status=1  # 已接通
        ).aggregate(total_duration=Sum('duration'))['total_duration'] or 0
        
        # 系统累计通话总时长（秒）
        total_duration = CallRecord.objects.filter(
            create_user=request.user,
            status=1  # 已接通
        ).aggregate(total_duration=Sum('duration'))['total_duration'] or 0
        
        # 今日沟通客户总数
        today_unique_customers = CallRecord.objects.filter(
            create_user=request.user,
            call_time__gte=today_start
        ).values('customer_id').distinct().count()
        
        # 返回响应，包含统计信息和记录数据
        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': total_count,
            'data': call_records,
            'statistics': {
                'today_call_count': today_call_count,
                'total_call_count': total_call_count,
                'today_duration': today_duration,
                'total_duration': total_duration,
                'today_unique_customers': today_unique_customers
            }
        })

# 批量导入相关功能
from django.core.cache import cache
from django.conf import settings

def _get_pandas():
    try:
        import pandas as pd
        return pd
    except ImportError as exc:
        raise RuntimeError('客户导入功能需要安装 pandas，请先安装项目依赖后再上传 Excel 文件') from exc

def _get_customer_import_field_definitions(custom_fields=None):
    if custom_fields is None:
        custom_fields = CustomerField.objects.filter(
            status=True,
            delete_time=0
        ).order_by('sort', 'id')

    fields = [
        {'key': 'name', 'label': '客户名称', 'required': True, 'type': 'text'},
        {'key': 'contact_person', 'label': '联系人', 'required': True, 'type': 'text'},
        {'key': 'phone', 'label': '联系电话', 'required': True, 'type': 'text'},
        {'key': 'email', 'label': '邮箱', 'required': False, 'type': 'text'},
        {'key': 'customer_source', 'label': '客户来源', 'required': False, 'type': 'system'},
        {'key': 'grade_id', 'label': '客户等级', 'required': False, 'type': 'system'},
        {'key': 'services_id', 'label': '客户意向', 'required': False, 'type': 'system'},
        {'key': 'province', 'label': '省份', 'required': False, 'type': 'text'},
        {'key': 'city', 'label': '城市', 'required': False, 'type': 'text'},
        {'key': 'district', 'label': '区县', 'required': False, 'type': 'text'},
        {'key': 'town', 'label': '乡镇街道', 'required': False, 'type': 'text'},
        {'key': 'address', 'label': '地址', 'required': False, 'type': 'text'},
        {'key': 'content', 'label': '客户描述', 'required': False, 'type': 'textarea'},
        {'key': 'market', 'label': '主要经营业务', 'required': False, 'type': 'textarea'},
        {'key': 'remark', 'label': '备注信息', 'required': False, 'type': 'textarea'},
        {'key': 'tax_bank', 'label': '开户银行', 'required': False, 'type': 'text'},
        {'key': 'tax_banksn', 'label': '银行账号', 'required': False, 'type': 'text'},
        {'key': 'tax_num', 'label': '纳税人识别号', 'required': False, 'type': 'text'},
        {'key': 'tax_mobile', 'label': '税务联系电话', 'required': False, 'type': 'text'},
        {'key': 'tax_address', 'label': '税务地址', 'required': False, 'type': 'text'},
    ]

    for field in custom_fields:
        fields.append({
            'key': f'custom_{field.id}',
            'label': field.name,
            'required': bool(field.is_required),
            'type': field.field_type,
            'field_id': field.id,
            'field_name': field.field_name,
            'options': field.options or '',
            'is_unique': bool(field.is_unique),
        })

    return fields


def _normalize_import_header(value):
    text = '' if value is None else str(value).strip()
    return text.replace('*', '').replace('（必填）', '').replace('(必填)', '').strip()


def _normalize_import_value(value):
    pd = _get_pandas()
    if pd.isna(value):
        return ''
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S') if value.time() else value.strftime('%Y-%m-%d')
    text = str(value).strip()
    if text.lower() == 'nan':
        return ''
    if text.endswith('.0'):
        try:
            return str(int(float(text)))
        except (TypeError, ValueError):
            pass
    return text


def _parse_mapping_index(column_index):
    if column_index in ('', None, 'undefined', 'null'):
        return None
    try:
        column_index = int(column_index)
    except (TypeError, ValueError):
        return None
    return column_index if column_index >= 0 else None


def _get_custom_field_options(field):
    if not field.options:
        return []
    return [option.strip() for option in field.options.replace(',', '\n').split('\n') if option.strip()]


def _convert_customer_custom_field_value(field, value):
    value = _normalize_import_value(value)
    if not value:
        return ''

    if field.field_type == 'checkbox':
        if value.lower() in ('1', 'true', 'yes', 'y', 'on', '是', '有', '选中'):
            return '1'
        if value.lower() in ('0', 'false', 'no', 'n', 'off', '否', '无', '未选中'):
            return '0'
        return value

    if field.field_type == 'number':
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f'{field.name}必须是数字')
        return str(int(number)) if number.is_integer() else str(number)

    if field.field_type in ('select', 'radio'):
        options = _get_custom_field_options(field)
        if options and value not in options:
            raise ValueError(f'{field.name}必须是以下选项之一: {"、".join(options)}')

    return value


def _find_customer_source(value):
    value = _normalize_import_value(value)
    if not value:
        return None
    queryset = CustomerSource.objects.filter(status=1, delete_time=0)
    if value.isdigit():
        source = queryset.filter(id=int(value)).first()
        if source:
            return source
    return queryset.filter(title=value).first()


def _find_customer_grade_id(value):
    value = _normalize_import_value(value)
    if not value:
        return 0
    queryset = CustomerGrade.objects.filter(status=1, delete_time=0)
    if value.isdigit():
        grade = queryset.filter(id=int(value)).first()
        return grade.id if grade else 0
    grade = queryset.filter(title=value).first()
    return grade.id if grade else 0


def _find_customer_intent_id(value):
    value = _normalize_import_value(value)
    if not value:
        return 0
    queryset = CustomerIntent.objects.filter(status=1, delete_time=0)
    if value.isdigit():
        intent = queryset.filter(id=int(value)).first()
        return intent.id if intent else 0
    intent = queryset.filter(name=value).first()
    return intent.id if intent else 0


@login_required
def download_template(request):
    """下载客户导入模板"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.comments import Comment
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "客户导入模板"
        fields = _get_customer_import_field_definitions()
        headers = [f"{field['label']}*" if field['required'] else field['label'] for field in fields]
        
        for col, header in enumerate(headers, 1):
            field = fields[col - 1]
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(
                start_color="C00000" if field['required'] else "366092",
                end_color="C00000" if field['required'] else "366092",
                fill_type="solid"
            )
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if field.get('options'):
                cell.comment = Comment(f"可选值：{field['options']}", "dtcall")
        
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18
        
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="customer_import_template.xlsx"'
        
        wb.save(response)
        return response
        
    except Exception as e:
        logger.error(f'下载模板失败: {str(e)}')
        return JsonResponse({'code': 1, 'msg': f'下载模板失败: {str(e)}'})

@login_required
def upload_import_file(request):
    """上传导入文件"""
    if request.method != 'POST':
        return JsonResponse({'code': 1, 'msg': '请求方法错误'})
    
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'code': 1, 'msg': '请选择要上传的文件'})
        
        file = request.FILES['file']
        
        # 验证文件类型
        if not file.name.endswith(('.xlsx', '.xls')):
            return JsonResponse({'code': 1, 'msg': '请上传Excel文件(.xlsx或.xls格式)'})
        
        # 验证文件大小
        if file.size > 10 * 1024 * 1024:  # 10MB
            return JsonResponse({'code': 1, 'msg': '文件大小不能超过10MB'})
        
        # 保存临时文件
        file_id = str(uuid.uuid4())
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', 'import')
        os.makedirs(temp_dir, exist_ok=True)
        
        file_path = os.path.join(temp_dir, f'{file_id}{os.path.splitext(file.name)[1].lower()}')
        with open(file_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)
        
        # 读取Excel文件获取表头
        try:
            pd = _get_pandas()
            df = pd.read_excel(file_path, nrows=0, dtype=object)  # 只读取表头
            headers = df.columns.tolist()
        except Exception as e:
            try:
                os.remove(file_path)
            except OSError:
                pass
            return JsonResponse({'code': 1, 'msg': f'文件格式错误: {str(e)}'})
        
        # 缓存文件信息
        cache_key = f'import_file_{file_id}'
        cache.set(cache_key, {
            'file_path': file_path,
            'headers': headers,
            'upload_time': timezone.now().isoformat()
        }, timeout=3600)  # 1小时过期
        
        return JsonResponse({
            'code': 0,
            'msg': '文件上传成功',
            'data': {
                'file_id': file_id,
                'headers': headers
            }
        })
        
    except Exception as e:
        logger.error(f'上传文件失败: {str(e)}')
        return JsonResponse({'code': 1, 'msg': f'上传文件失败: {str(e)}'})

@login_required
def process_import(request):
    """处理导入数据"""
    if request.method != 'POST':
        return JsonResponse({'code': 1, 'msg': '请求方法错误'})
    
    try:
        file_id = request.POST.get('file_id')
        field_mapping = json.loads(request.POST.get('field_mapping', '{}'))
        
        if not file_id:
            return JsonResponse({'code': 1, 'msg': '文件ID不能为空'})
        
        # 获取文件信息
        cache_key = f'import_file_{file_id}'
        file_info = cache.get(cache_key)
        if not file_info:
            return JsonResponse({'code': 1, 'msg': '文件已过期，请重新上传'})
        
        # 创建导入任务
        task_id = str(uuid.uuid4())
        
        # 异步处理导入（这里简化为同步处理）
        _process_import_data(file_info['file_path'], field_mapping, request.user, task_id)
        
        return JsonResponse({
            'code': 0,
            'msg': '导入任务已创建',
            'data': {'task_id': task_id}
        })
        
    except Exception as e:
        logger.error(f'处理导入失败: {str(e)}')
        return JsonResponse({'code': 1, 'msg': f'处理导入失败: {str(e)}'})

def _process_import_data(file_path, field_mapping, user, task_id):
    """处理导入数据的核心逻辑"""
    progress_key = f'import_progress_{task_id}'
    try:
        cache.set(progress_key, {
            'status': 'processing',
            'percent': 0,
            'message': '开始处理数据...',
            'result': None
        }, timeout=3600)
        
        pd = _get_pandas()
        df = pd.read_excel(file_path, dtype=object)
        total_rows = len(df)
        success_count = 0
        error_count = 0
        errors = []
        headers = list(df.columns)
        header_map = {_normalize_import_header(header): index for index, header in enumerate(headers)}
        import_fields = _get_customer_import_field_definitions()
        custom_fields = {
            field.id: field for field in CustomerField.objects.filter(status=True, delete_time=0)
        }
        default_source = CustomerSource.objects.filter(status=1, delete_time=0).order_by('sort', 'id').first()

        if total_rows == 0:
            cache.set(progress_key, {
                'status': 'completed',
                'percent': 100,
                'message': '导入文件中没有可导入的数据',
                'result': {'total': 0, 'success': 0, 'error': 0, 'errors': []}
            }, timeout=3600)
            try:
                os.remove(file_path)
            except OSError:
                pass
            return {'total': 0, 'success': 0, 'error': 0, 'errors': []}

        normalized_mapping = {}
        for field in import_fields:
            mapped_index = _parse_mapping_index(field_mapping.get(field['key']))
            if mapped_index is None:
                mapped_index = header_map.get(field['label'])
            if mapped_index is None and field.get('field_name'):
                mapped_index = header_map.get(field['field_name'])
            if mapped_index is not None and mapped_index < len(headers):
                normalized_mapping[field['key']] = mapped_index
        
        for index, row in df.iterrows():
            try:
                percent = int((index + 1) / total_rows * 100)
                cache.set(progress_key, {
                    'status': 'processing',
                    'percent': percent,
                    'message': f'正在处理第 {index + 1} 行数据...',
                    'result': None
                }, timeout=3600)
                
                customer_data = {}
                custom_field_values = {}
                for field in import_fields:
                    column_index = normalized_mapping.get(field['key'])
                    if column_index is None:
                        continue
                    value = _normalize_import_value(row.iloc[column_index])
                    if not value:
                        continue
                    if field['key'].startswith('custom_'):
                        field_id = field.get('field_id')
                        custom_field = custom_fields.get(field_id)
                        if custom_field:
                            custom_field_values[field_id] = _convert_customer_custom_field_value(custom_field, value)
                    else:
                        customer_data[field['key']] = value
                
                missing_fields = [field['label'] for field in import_fields if field['required'] and not (custom_field_values.get(field.get('field_id')) if field['key'].startswith('custom_') else customer_data.get(field['key']))]
                if missing_fields:
                    errors.append({'row': index + 2, 'message': f'缺少必填字段: {", ".join(missing_fields)}'})
                    error_count += 1
                    continue
                
                if Customer.objects.filter(name=customer_data['name'], delete_time=0).exists():
                    errors.append({'row': index + 2, 'message': f'客户 "{customer_data["name"]}" 已存在'})
                    error_count += 1
                    continue
                
                duplicate_custom_fields = []
                for field_id, value in custom_field_values.items():
                    custom_field = custom_fields.get(field_id)
                    if custom_field and custom_field.is_unique and value:
                        exists = CustomerCustomFieldValue.objects.filter(
                            field_id=field_id,
                            value=value,
                            customer__delete_time=0
                        ).exists()
                        if exists:
                            duplicate_custom_fields.append(custom_field.name)
                if duplicate_custom_fields:
                    errors.append({'row': index + 2, 'message': f'自定义字段值重复: {", ".join(duplicate_custom_fields)}'})
                    error_count += 1
                    continue
                
                with transaction.atomic():
                    now_timestamp = int(timezone.now().timestamp())
                    customer = Customer.objects.create(
                        name=customer_data.get('name', ''),
                        customer_source=_find_customer_source(customer_data.get('customer_source')) or default_source,
                        grade_id=_find_customer_grade_id(customer_data.get('grade_id')),
                        services_id=_find_customer_intent_id(customer_data.get('services_id')),
                        province=customer_data.get('province', ''),
                        city=customer_data.get('city', ''),
                        district=customer_data.get('district', ''),
                        town=customer_data.get('town', ''),
                        address=customer_data.get('address', ''),
                        content=customer_data.get('content', ''),
                        market=customer_data.get('market', ''),
                        remark=customer_data.get('remark', ''),
                        tax_bank=customer_data.get('tax_bank', ''),
                        tax_banksn=customer_data.get('tax_banksn', ''),
                        tax_num=customer_data.get('tax_num', ''),
                        tax_mobile=customer_data.get('tax_mobile', ''),
                        tax_address=customer_data.get('tax_address', ''),
                        admin_id=user.id,
                        belong_uid=user.id,
                        belong_time=now_timestamp,
                        intent_status=1,
                        delete_time=0
                    )
                    Contact.objects.create(
                        customer=customer,
                        contact_person=customer_data.get('contact_person', ''),
                        phone=customer_data.get('phone', ''),
                        email=customer_data.get('email', ''),
                        is_primary=True
                    )
                    for field_id, value in custom_field_values.items():
                        CustomerCustomFieldValue.objects.update_or_create(
                            customer=customer,
                            field_id=field_id,
                            defaults={'value': value}
                        )
                    
                    success_count += 1
                    
            except Exception as e:
                errors.append({'row': index + 2, 'message': f'导入失败: {str(e)}'})
                error_count += 1
                continue
        
        result = {
            'total': total_rows,
            'success': success_count,
            'error': error_count,
            'errors': errors
        }
        
        cache.set(progress_key, {
            'status': 'completed',
            'percent': 100,
            'message': '导入完成',
            'result': result
        }, timeout=3600)
        
        try:
            os.remove(file_path)
        except OSError:
            pass
        
        return result
        
    except Exception as e:
        logger.error(f'导入数据处理失败: {str(e)}')
        cache.set(progress_key, {
            'status': 'failed',
            'percent': 0,
            'message': f'导入失败: {str(e)}',
            'result': None
        }, timeout=3600)
        return None

@login_required
def import_progress(request):
    """获取导入进度"""
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'code': 1, 'msg': '任务ID不能为空'})
    
    progress_key = f'import_progress_{task_id}'
    progress = cache.get(progress_key)
    
    if not progress:
        return JsonResponse({'code': 1, 'msg': '任务不存在或已过期'})
    
    return JsonResponse({
        'code': 0,
        'msg': '获取进度成功',
        'data': progress
    })
# AI机器人管理

class AIRobotView(LoginRequiredMixin, TemplateView):
    """AI机器人管理页面"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    template_name = 'customer/ai_robot.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'AI机器人管理'
        return context

class AIRobotDataView(LoginRequiredMixin, View):
    """AI机器人数据API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def get(self, request):
        try:
            robot_data = AIRobotTaskService.get_robot_data()
            return JsonResponse({
                'code': 0,
                'msg': '获取数据成功',
                'count': len(robot_data['robots']),
                'data': robot_data['robots'],
                'statistics': robot_data['statistics'],
                'config': robot_data['config'],
                'validation': robot_data['validation'],
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'获取AI机器人数据失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'获取数据失败: {str(e)}'})

class AIRobotTaskService:
    """公海客户AI机器人任务服务"""
    ROBOT_CONFIG_KEY = 'customer_public_ai_robot_config'

    DEFAULT_CONFIG = {
        'batch_size': 20,
        'min_score_for_allocation': 60,
        'auto_allocate': False,
    }

    ROBOTS = {
        'classification': {
            'name': '智能客户分类机器人',
            'description': '识别公海客户质量、意向标签与优先级',
        },
        'profile': {
            'name': '智能客户画像机器人',
            'description': '沉淀客户画像、经营线索与维护策略',
        },
        'followup': {
            'name': '智能跟进建议机器人',
            'description': '生成下一步触达建议与跟进优先级',
        },
        'allocation': {
            'name': '智能客户分配机器人',
            'description': '按客户价值与员工负载分配公海客户',
        },
    }

    @classmethod
    def get_config(cls):
        item = SystemConfiguration.objects.filter(
            key=cls.ROBOT_CONFIG_KEY,
            is_active=True
        ).first()
        if not item:
            return cls.DEFAULT_CONFIG.copy()
        try:
            config = json.loads(item.value or '{}')
        except json.JSONDecodeError:
            config = {}
        result = cls.DEFAULT_CONFIG.copy()
        result.update({k: v for k, v in config.items() if k in result})
        return result

    @classmethod
    def save_config(cls, config):
        cleaned = cls.DEFAULT_CONFIG.copy()
        cleaned['batch_size'] = max(1, min(int(config.get('batch_size', cleaned['batch_size'])), 200))
        cleaned['min_score_for_allocation'] = max(0, min(int(config.get('min_score_for_allocation', cleaned['min_score_for_allocation'])), 100))
        cleaned['auto_allocate'] = str(config.get('auto_allocate', '')).lower() in ['1', 'true', 'on', 'yes']
        SystemConfiguration.objects.update_or_create(
            key=cls.ROBOT_CONFIG_KEY,
            defaults={
                'value': json.dumps(cleaned, ensure_ascii=False),
                'description': '客户公海AI机器人运行配置',
                'is_active': True,
            }
        )
        return cleaned

    @classmethod
    def get_public_queryset(cls, limit=None):
        queryset = Customer.objects.filter(
            delete_time=0,
            discard_time=0,
            belong_uid=0
        ).prefetch_related('contacts', 'follow_records').order_by('-ai_score', '-create_time', 'id')
        if limit:
            queryset = queryset[:limit]
        return queryset

    @classmethod
    def get_robot_data(cls):
        total_customers = Customer.objects.filter(delete_time=0).count()
        public_customers = Customer.objects.filter(delete_time=0, discard_time=0, belong_uid=0).count()
        personal_customers = Customer.objects.filter(delete_time=0, belong_uid__gt=0).count()
        abandoned_customers = Customer.objects.filter(delete_time=0, discard_time__gt=0).count()
        analyzed_customers = Customer.objects.filter(delete_time=0, belong_uid=0, ai_score__gt=0).count()
        suggested_customers = Customer.objects.filter(
            delete_time=0,
            belong_uid=0,
            ai_next_followup_suggestion__isnull=False
        ).exclude(ai_next_followup_suggestion='').count()
        recent_logs = SystemLog.objects.filter(
            module='客户公海AI机器人'
        ).order_by('-created_at')[:20]
        last_run_map = {}
        for log in recent_logs:
            for robot_type, meta in cls.ROBOTS.items():
                if meta['name'] in log.action and robot_type not in last_run_map:
                    last_run_map[robot_type] = log.created_at.strftime('%Y-%m-%d %H:%M:%S')

        validation = cls.validate_runtime()
        robots = []
        for robot_type, meta in cls.ROBOTS.items():
            robot_validation = cls.validate_runtime(robot_type)
            robots.append({
                'type': robot_type,
                'name': meta['name'],
                'status': 1 if robot_validation['ready'] else 0,
                'description': meta['description'],
                'active_customers': public_customers,
                'processed_customers': {
                    'classification': analyzed_customers,
                    'profile': suggested_customers,
                    'followup': suggested_customers,
                    'allocation': personal_customers,
                }[robot_type],
                'success_rate': cls._ratio(
                    {
                        'classification': analyzed_customers,
                        'profile': suggested_customers,
                        'followup': suggested_customers,
                        'allocation': personal_customers,
                    }[robot_type],
                    total_customers if robot_type == 'allocation' else public_customers
                ),
                'last_run_time': last_run_map.get(robot_type, '暂无运行'),
                'validation': robot_validation,
                'missing_count': robot_validation['missing_count'],
                'config_summary': robot_validation['config_summary'],
            })
        return {
            'robots': robots,
            'statistics': {
                'total_customers': total_customers,
                'public_customers': public_customers,
                'personal_customers': personal_customers,
                'abandoned_customers': abandoned_customers,
                'analyzed_customers': analyzed_customers,
            },
            'config': cls.get_config(),
            'validation': validation,
        }

    @staticmethod
    def _ratio(value, total):
        if not total:
            return 0
        return round(value / total, 2)

    @classmethod
    def validate_runtime(cls, robot_type=None):
        config = cls.get_config()
        try:
            batch_size = int(config.get('batch_size') or 0)
        except (TypeError, ValueError):
            batch_size = 0
        try:
            min_score = int(config.get('min_score_for_allocation') or 0)
        except (TypeError, ValueError):
            min_score = -1
        public_customers = Customer.objects.filter(delete_time=0, discard_time=0, belong_uid=0).count()
        employees = Admin.objects.filter(is_active=True, status=1).count()
        checks = [
            {
                'name': '公海客户数据',
                'status': public_customers > 0,
                'message': f'当前可处理公海客户 {public_customers} 个' if public_customers else '暂无可处理公海客户',
            },
            {
                'name': '单次处理数量',
                'status': 1 <= batch_size <= 200,
                'message': f'当前单次处理 {batch_size} 个客户' if batch_size else '单次处理数量未配置',
            },
            {
                'name': '分配评分阈值',
                'status': 0 <= min_score <= 100,
                'message': f'当前最低分配评分 {min_score} 分' if min_score >= 0 else '分配评分阈值未配置',
            },
        ]
        if robot_type in [None, 'allocation']:
            checks.append({
                'name': '分配员工池',
                'status': employees > 0,
                'message': f'当前可分配员工 {employees} 人' if employees else '暂无可分配员工，分配机器人不可执行',
            })
        failed_checks = [item for item in checks if not item['status']]
        return {
            'ready': not failed_checks,
            'checks': checks,
            'config': config,
            'missing_count': len(failed_checks),
            'config_summary': [
                f'单次处理 {batch_size or "未配置"} 个',
                f'分配阈值 {min_score if min_score >= 0 else "未配置"} 分',
                '自动分配已开启' if config.get('auto_allocate') else '自动分配未开启',
            ],
        }

    @classmethod
    def execute(cls, robot_type, request):
        if robot_type not in cls.ROBOTS:
            return {'code': 1, 'msg': '未知机器人类型'}
        validation = cls.validate_runtime(robot_type)
        if not validation['ready']:
            return {
                'code': 1,
                'msg': '运行前验证未通过，请先查看验证结果并完善配置',
                'validation': validation,
            }
        config = cls.get_config()
        batch_size = config['batch_size']
        if robot_type == 'classification':
            result = cls.run_classification(batch_size)
        elif robot_type == 'profile':
            result = cls.run_profile(batch_size)
        elif robot_type == 'followup':
            result = cls.run_followup(batch_size)
        elif robot_type == 'allocation':
            result = cls.run_allocation(batch_size, config['min_score_for_allocation'])

        cls.write_log(request, cls.ROBOTS[robot_type]['name'], result['msg'])
        return {
            'code': 0,
            'robot_type': robot_type,
            'robot_name': cls.ROBOTS[robot_type]['name'],
            'validation': cls.validate_runtime(robot_type),
            **result,
        }

    @classmethod
    def run_classification(cls, batch_size):
        customers = list(cls.get_public_queryset(batch_size))
        updated_count = 0
        for customer in customers:
            score, tags = cls.evaluate_customer(customer)
            customer.ai_score = score
            customer.ai_intent_tags = tags
            customer.save(update_fields=['ai_score', 'ai_intent_tags', 'update_time'])
            updated_count += 1
        return {
            'msg': f'已完成{updated_count}个公海客户分类评分',
            'processed_count': updated_count,
        }

    @classmethod
    def run_profile(cls, batch_size):
        customers = list(cls.get_public_queryset(batch_size))
        updated_count = 0
        for customer in customers:
            score, tags = cls.evaluate_customer(customer)
            customer.ai_score = max(customer.ai_score or 0, score)
            customer.ai_intent_tags = tags
            customer.ai_next_followup_suggestion = cls.build_profile_suggestion(customer, tags)
            customer.save(update_fields=[
                'ai_score', 'ai_intent_tags', 'ai_next_followup_suggestion', 'update_time'
            ])
            updated_count += 1
        return {
            'msg': f'已生成{updated_count}个公海客户画像',
            'processed_count': updated_count,
        }

    @classmethod
    def run_followup(cls, batch_size):
        customers = list(cls.get_public_queryset(batch_size))
        updated_count = 0
        for customer in customers:
            score, tags = cls.evaluate_customer(customer)
            customer.ai_score = max(customer.ai_score or 0, score)
            customer.ai_intent_tags = tags
            customer.ai_next_followup_suggestion = cls.build_followup_suggestion(customer, score, tags)
            customer.next_time = int((timezone.now() + timedelta(days=1 if score >= 70 else 3)).timestamp())
            customer.save(update_fields=[
                'ai_score', 'ai_intent_tags', 'ai_next_followup_suggestion', 'next_time', 'update_time'
            ])
            updated_count += 1
        return {
            'msg': f'已生成{updated_count}个公海客户跟进建议',
            'processed_count': updated_count,
        }

    @classmethod
    def run_allocation(cls, batch_size, min_score):
        employees = list(Admin.objects.filter(is_active=True, status=1).order_by('id'))
        if not employees:
            return {'msg': '暂无可分配员工', 'processed_count': 0}

        workloads = {
            employee.id: Customer.objects.filter(delete_time=0, belong_uid=employee.id).count()
            for employee in employees
        }
        candidates = list(Customer.objects.filter(
            delete_time=0,
            discard_time=0,
            belong_uid=0,
            ai_score__gte=min_score
        ).prefetch_related('contacts', 'follow_records').order_by('-ai_score', '-create_time', 'id')[:batch_size])
        allocated_count = 0
        now_ts = int(timezone.now().timestamp())
        with transaction.atomic():
            for customer in candidates:
                target = min(employees, key=lambda employee: (workloads.get(employee.id, 0), employee.id))
                customer.belong_uid = target.id
                customer.belong_did = getattr(target, 'did', 0) or 0
                customer.belong_time = now_ts
                customer.distribute_time = now_ts
                customer.share_ids = ''
                customer.save(update_fields=[
                    'belong_uid', 'belong_did', 'belong_time', 'distribute_time', 'share_ids', 'update_time'
                ])
                workloads[target.id] = workloads.get(target.id, 0) + 1
                allocated_count += 1
        return {
            'msg': f'已分配{allocated_count}个高意向公海客户',
            'processed_count': allocated_count,
        }

    @classmethod
    def evaluate_customer(cls, customer):
        score = 30
        tags = []
        contacts = list(customer.contacts.all())
        if contacts:
            score += 18
            tags.append('有联系人')
        if any(contact.phone for contact in contacts) or customer.tax_mobile:
            score += 15
            tags.append('可电话触达')
        if any(contact.email for contact in contacts):
            score += 8
            tags.append('可邮件触达')
        if customer.customer_source_id:
            score += 8
            tags.append('来源明确')
        if customer.grade_id:
            score += 8
            tags.append('已定级')
        if customer.industry_id:
            score += 6
            tags.append('行业明确')
        if customer.intent_status:
            score += 12
            tags.append('有意向状态')
        if customer.content or customer.market or customer.remark:
            score += 10
            tags.append('资料较完整')
        if customer.province or customer.city:
            score += 5
            tags.append('地区明确')
        if customer.follow_records.filter(delete_time=0).exists():
            score += 10
            tags.append('已有触达记录')
        if score >= 80:
            tags.insert(0, '高优先级')
        elif score >= 60:
            tags.insert(0, '中优先级')
        else:
            tags.insert(0, '待培育')
        return min(score, 100), tags[:8]

    @classmethod
    def build_profile_suggestion(cls, customer, tags):
        area = ''.join([customer.province or '', customer.city or '', customer.district or '']) or '未知地区'
        business = customer.market or customer.content or customer.remark or '暂无业务描述'
        return f'客户画像：{customer.name}，地区：{area}，特征：{"、".join(tags)}。业务线索：{business[:120]}。建议先补齐关键联系人与需求信息，再按优先级进入销售跟进。'

    @classmethod
    def build_followup_suggestion(cls, customer, score, tags):
        contact = customer.primary_contact
        contact_text = f'优先联系{contact.contact_person}' if contact else '先补充联系人信息'
        if score >= 80:
            action = '建议24小时内电话触达，确认预算、需求时间和决策人。'
        elif score >= 60:
            action = '建议3天内完成首次触达，补齐行业、规模和采购意向。'
        else:
            action = '建议先完善客户资料，再通过短信或邮件进行低频培育。'
        return f'{contact_text}；客户标签：{"、".join(tags)}；{action}'

    @classmethod
    def write_log(cls, request, robot_name, content):
        SystemLog.objects.create(
            user=request.user,
            log_type='other',
            module='客户公海AI机器人',
            action=f'{robot_name}运行',
            content=content,
            ip_address=request.META.get('REMOTE_ADDR', '0.0.0.0'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )


class AIRobotExecuteView(LoginRequiredMixin, View):
    """AI机器人执行API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request):
        try:
            data = json.loads(request.body or '{}')
            robot_type = data.get('robot_type')
            result = AIRobotTaskService.execute(robot_type, request)
            return JsonResponse(result, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'执行AI机器人失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': f'执行失败: {str(e)}'}, status=500)


class AIRobotConfigView(LoginRequiredMixin, View):
    """AI机器人配置API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return JsonResponse({
            'code': 0,
            'msg': '获取配置成功',
            'data': AIRobotTaskService.get_config()
        }, json_dumps_params={'ensure_ascii': False})

    def post(self, request):
        try:
            data = json.loads(request.body or '{}')
            config = AIRobotTaskService.save_config(data)
            SystemLog.objects.create(
                user=request.user,
                log_type='update',
                module='客户公海AI机器人',
                action='保存机器人配置',
                content=f'配置已更新：{json.dumps(config, ensure_ascii=False)}',
                ip_address=request.META.get('REMOTE_ADDR', '0.0.0.0'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return JsonResponse({'code': 0, 'msg': '配置保存成功', 'data': config}, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'保存AI机器人配置失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': f'保存失败: {str(e)}'}, status=500)


class AIRobotValidateView(LoginRequiredMixin, View):
    """AI机器人运行验证API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        robot_type = request.GET.get('robot_type')
        validation = AIRobotTaskService.validate_runtime(robot_type)
        return JsonResponse({
            'code': 0,
            'msg': '验证完成',
            'data': validation,
        }, json_dumps_params={'ensure_ascii': False})


class AIRobotLogView(LoginRequiredMixin, View):
    """AI机器人日志API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        robot_type = request.GET.get('robot_type')
        queryset = SystemLog.objects.filter(module='客户公海AI机器人')
        if robot_type in AIRobotTaskService.ROBOTS:
            queryset = queryset.filter(action__contains=AIRobotTaskService.ROBOTS[robot_type]['name'])
        logs = queryset.order_by('-created_at')[:50]
        data = [{
            'action': log.action,
            'content': log.content,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'user': log.user.name or log.user.username if log.user else ''
        } for log in logs]
        return JsonResponse({'code': 0, 'msg': '获取日志成功', 'data': data}, json_dumps_params={'ensure_ascii': False})


class MarketingRobotService:
    """营销机器人服务"""
    CONFIG_KEY = 'customer_marketing_robot_config'
    MODULE_NAME = '客户营销机器人'

    ROBOTS = {
        'customer_service': {
            'name': '智能客服机器人',
            'description': '自动回复客户咨询，沉淀客服跟进记录',
            'fields': {
                'robot_name': '智能客服小助手',
                'welcome_text': '您好！我是智能客服小助手，有什么可以帮助您的吗？',
                'work_time': '00:00-23:59',
                'batch_size': 20,
            },
        },
        'telemarketing': {
            'name': '电话营销机器人',
            'description': '筛选可电话触达客户并发起SIP外呼任务',
            'fields': {
                'call_time': '09:00-18:00',
                'script': '您好，我想了解一下您对我们产品的需求。',
                'retry_interval': 24,
                'batch_size': 20,
            },
        },
        'email_marketing': {
            'name': '邮件营销机器人',
            'description': '筛选可邮件触达客户并记录邮件营销任务',
            'fields': {
                'sender_email': '',
                'smtp_server': '',
                'subject': '客户关怀提醒',
                'template': '尊敬的客户，感谢您对我们的关注。',
                'batch_size': 20,
            },
        },
        'sms_marketing': {
            'name': '短信营销机器人',
            'description': '筛选可短信触达客户并记录短信营销任务',
            'fields': {
                'signature': '',
                'template': '尊敬的客户，您有新的优惠信息待查看。',
                'daily_limit': 1,
                'batch_size': 20,
            },
        },
        'wechat': {
            'name': '微信机器人',
            'description': '筛选客户微信触达任务并沉淀销售动作',
            'fields': {
                'robot_name': '微信销售助手',
                'welcome_text': '您好！我是您的专属销售顾问，很高兴为您服务！',
                'auto_reply': True,
                'batch_size': 20,
            },
        },
    }

    @classmethod
    def get_config(cls):
        item = SystemConfiguration.objects.filter(key=cls.CONFIG_KEY, is_active=True).first()
        saved_config = {}
        if item:
            try:
                saved_config = json.loads(item.value or '{}')
            except json.JSONDecodeError:
                saved_config = {}
        result = {}
        for robot_type, meta in cls.ROBOTS.items():
            result[robot_type] = meta['fields'].copy()
            if isinstance(saved_config.get(robot_type), dict):
                result[robot_type].update(saved_config[robot_type])
        return result

    @classmethod
    def save_config(cls, robot_type, config):
        if robot_type not in cls.ROBOTS:
            return {'code': 1, 'msg': '未知营销机器人类型'}
        current = cls.get_config()
        cleaned = cls.clean_config(robot_type, config)
        current[robot_type] = cleaned
        SystemConfiguration.objects.update_or_create(
            key=cls.CONFIG_KEY,
            defaults={
                'value': json.dumps(current, ensure_ascii=False),
                'description': '客户营销机器人运行配置',
                'is_active': True,
            }
        )
        return {'code': 0, 'msg': '配置保存成功', 'data': cleaned}

    @classmethod
    def clean_config(cls, robot_type, config):
        defaults = cls.ROBOTS[robot_type]['fields'].copy()
        cleaned = defaults.copy()
        for key in defaults:
            if key in config:
                cleaned[key] = config[key]
        if 'batch_size' in cleaned:
            cleaned['batch_size'] = max(1, min(int(cleaned.get('batch_size') or defaults['batch_size']), 100))
        if robot_type == 'sms_marketing':
            cleaned['daily_limit'] = max(1, min(int(cleaned.get('daily_limit') or 1), 20))
        if robot_type == 'telemarketing':
            cleaned['retry_interval'] = max(1, min(int(cleaned.get('retry_interval') or 24), 168))
        if robot_type == 'wechat':
            cleaned['auto_reply'] = str(cleaned.get('auto_reply', '')).lower() in ['1', 'true', 'on', 'yes']
        return cleaned

    @classmethod
    def get_robot_data(cls):
        configs = cls.get_config()
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        robots = []
        for robot_type, meta in cls.ROBOTS.items():
            stats = cls.get_robot_stats(robot_type, today_start)
            validation = cls.validate_robot(robot_type, configs.get(robot_type, {}))
            robots.append({
                'type': robot_type,
                'name': meta['name'],
                'description': meta['description'],
                'status': 1 if validation['ready'] else 0,
                'validation': validation,
                'missing_count': validation['missing_count'],
                'config_summary': validation['config_summary'],
                **stats,
            })
        return {'robots': robots, 'config': configs}

    @classmethod
    def get_robot_status(cls, robot_type, config):
        validation = cls.validate_robot(robot_type, config)
        return 1 if validation['ready'] else 0

    @classmethod
    def validate_robot(cls, robot_type, config=None):
        if robot_type not in cls.ROBOTS:
            return {
                'ready': False,
                'checks': [{
                    'name': '机器人类型',
                    'status': False,
                    'message': '未知营销机器人类型',
                }],
                'config': {},
                'missing_count': 1,
                'config_summary': [],
            }
        config = config or cls.get_config().get(robot_type, cls.ROBOTS[robot_type]['fields'])
        try:
            batch_size = int(config.get('batch_size') or 0)
        except (TypeError, ValueError):
            batch_size = 0
        checks = [
            {
                'name': '单次处理数量',
                'status': 1 <= batch_size <= 100,
                'message': f'当前单次处理 {batch_size} 个客户' if batch_size else '单次处理数量未配置',
            }
        ]
        if robot_type == 'customer_service':
            checks.append({
                'name': '欢迎语配置',
                'status': bool(config.get('welcome_text')),
                'message': '已配置客服欢迎语' if config.get('welcome_text') else '请配置客服欢迎语',
            })
        elif robot_type == 'telemarketing':
            phone_customers = Customer.objects.filter(delete_time=0).filter(Q(contacts__phone__gt='') | Q(tax_mobile__gt='')).distinct().count()
            checks.extend([
                {
                    'name': '外呼客户数据',
                    'status': phone_customers > 0,
                    'message': f'当前可外呼客户 {phone_customers} 个' if phone_customers else '暂无可外呼客户',
                },
                {
                    'name': '话术模板',
                    'status': bool(config.get('script')),
                    'message': '已配置电话话术' if config.get('script') else '请配置电话话术',
                },
            ])
        elif robot_type == 'email_marketing':
            email_customers = Customer.objects.filter(delete_time=0, contacts__email__gt='').distinct().count()
            checks.extend([
                {
                    'name': '邮件客户数据',
                    'status': email_customers > 0,
                    'message': f'当前可邮件触达客户 {email_customers} 个' if email_customers else '暂无邮箱客户',
                },
                {
                    'name': '邮件主题',
                    'status': bool(config.get('subject')),
                    'message': '已配置邮件主题' if config.get('subject') else '请配置邮件主题',
                },
                {
                    'name': '邮件模板',
                    'status': bool(config.get('template')),
                    'message': '已配置邮件模板' if config.get('template') else '请配置邮件模板',
                },
            ])
        elif robot_type == 'sms_marketing':
            phone_customers = Customer.objects.filter(delete_time=0).filter(Q(contacts__phone__gt='') | Q(tax_mobile__gt='')).distinct().count()
            checks.extend([
                {
                    'name': '短信客户数据',
                    'status': phone_customers > 0,
                    'message': f'当前可短信触达客户 {phone_customers} 个' if phone_customers else '暂无手机号客户',
                },
                {
                    'name': '短信模板',
                    'status': bool(config.get('template')),
                    'message': '已配置短信模板' if config.get('template') else '请配置短信模板',
                },
            ])
        elif robot_type == 'wechat':
            phone_customers = Customer.objects.filter(delete_time=0).filter(Q(contacts__phone__gt='') | Q(tax_mobile__gt='')).distinct().count()
            checks.extend([
                {
                    'name': '微信触达客户',
                    'status': phone_customers > 0,
                    'message': f'当前可触达客户 {phone_customers} 个' if phone_customers else '暂无可触达客户',
                },
                {
                    'name': '欢迎语配置',
                    'status': bool(config.get('welcome_text')),
                    'message': '已配置微信欢迎语' if config.get('welcome_text') else '请配置微信欢迎语',
                },
            ])
        failed_checks = [item for item in checks if not item['status']]
        summary_map = {
            'customer_service': [
                f'机器人名称：{config.get("robot_name") or "未配置"}',
                f'工作时间：{config.get("work_time") or "未配置"}',
                f'单次处理：{batch_size or "未配置"} 个',
            ],
            'telemarketing': [
                f'拨打时间：{config.get("call_time") or "未配置"}',
                f'重拨间隔：{config.get("retry_interval") or "未配置"} 小时',
                f'单次处理：{batch_size or "未配置"} 个',
            ],
            'email_marketing': [
                f'发送邮箱：{config.get("sender_email") or "未配置"}',
                f'SMTP服务器：{config.get("smtp_server") or "未配置"}',
                f'单次处理：{batch_size or "未配置"} 个',
            ],
            'sms_marketing': [
                f'短信签名：{config.get("signature") or "未配置"}',
                f'每日次数：{config.get("daily_limit") or "未配置"}',
                f'单次处理：{batch_size or "未配置"} 个',
            ],
            'wechat': [
                f'机器人名称：{config.get("robot_name") or "未配置"}',
                '自动回复已开启' if config.get('auto_reply') else '自动回复未开启',
                f'单次处理：{batch_size or "未配置"} 个',
            ],
        }
        return {
            'ready': not failed_checks,
            'checks': checks,
            'config': config,
            'missing_count': len(failed_checks),
            'config_summary': summary_map.get(robot_type, []),
        }

    @classmethod
    def get_robot_stats(cls, robot_type, today_start):
        log_count = SystemLog.objects.filter(module=cls.MODULE_NAME, action__contains=cls.ROBOTS[robot_type]['name']).count()
        today_log_count = SystemLog.objects.filter(
            module=cls.MODULE_NAME,
            action__contains=cls.ROBOTS[robot_type]['name'],
            created_at__gte=today_start
        ).count()
        last_log = SystemLog.objects.filter(
            module=cls.MODULE_NAME,
            action__contains=cls.ROBOTS[robot_type]['name']
        ).order_by('-created_at').first()
        if robot_type == 'telemarketing':
            today_calls = CallRecord.objects.filter(call_time__gte=today_start).count()
            connected_calls = CallRecord.objects.filter(call_time__gte=today_start, status=1).count()
            avg_duration = CallRecord.objects.filter(call_time__gte=today_start, status=1).aggregate(avg=models.Avg('duration'))['avg'] or 0
            return {
                'metric_one': today_calls,
                'metric_one_label': '今日通话',
                'metric_two': f'{AIRobotTaskService._ratio(connected_calls, today_calls) * 100:.0f}%',
                'metric_two_label': '接通率',
                'metric_three': f'{int(avg_duration // 60)}min',
                'metric_three_label': '平均时长',
                'last_run_time': last_log.created_at.strftime('%Y-%m-%d %H:%M:%S') if last_log else '暂无运行',
            }
        labels = {
            'customer_service': ('活跃客户', '今日回复', '解决率'),
            'email_marketing': ('今日发送', '任务批次', '完成率'),
            'sms_marketing': ('今日发送', '任务批次', '完成率'),
            'wechat': ('今日添加', '任务批次', '今日对话'),
        }[robot_type]
        return {
            'metric_one': today_log_count,
            'metric_one_label': labels[0],
            'metric_two': log_count,
            'metric_two_label': labels[1],
            'metric_three': '100%' if log_count else '0%',
            'metric_three_label': labels[2],
            'last_run_time': last_log.created_at.strftime('%Y-%m-%d %H:%M:%S') if last_log else '暂无运行',
        }

    @classmethod
    def execute(cls, robot_type, request):
        if robot_type not in cls.ROBOTS:
            return {'code': 1, 'msg': '未知营销机器人类型'}
        config = cls.get_config().get(robot_type, cls.ROBOTS[robot_type]['fields'])
        validation = cls.validate_robot(robot_type, config)
        if not validation['ready']:
            return {
                'code': 1,
                'msg': '运行前验证未通过，请先查看验证结果并完善配置',
                'validation': validation,
            }
        handlers = {
            'customer_service': cls.run_customer_service,
            'telemarketing': cls.run_telemarketing,
            'email_marketing': cls.run_email_marketing,
            'sms_marketing': cls.run_sms_marketing,
            'wechat': cls.run_wechat,
        }
        result = handlers[robot_type](request, config)
        cls.write_log(request, cls.ROBOTS[robot_type]['name'], result['msg'])
        return {
            'code': 0,
            'robot_type': robot_type,
            'robot_name': cls.ROBOTS[robot_type]['name'],
            'validation': cls.validate_robot(robot_type, config),
            **result,
        }

    @classmethod
    def get_target_customers(cls, batch_size, contact_type=None):
        queryset = Customer.objects.filter(delete_time=0).prefetch_related('contacts').order_by('-ai_score', '-create_time', 'id')
        if contact_type == 'phone':
            queryset = queryset.filter(Q(contacts__phone__gt='') | Q(tax_mobile__gt='')).distinct()
        elif contact_type == 'email':
            queryset = queryset.filter(contacts__email__gt='').distinct()
        return list(queryset[:batch_size])

    @classmethod
    def run_customer_service(cls, request, config):
        customers = cls.get_target_customers(int(config.get('batch_size') or 20))
        for customer in customers:
            FollowRecord.objects.create(
                customer=customer,
                follow_type='other',
                content=f'{config.get("robot_name", "智能客服机器人")}已生成客服接待话术：{config.get("welcome_text", "")}',
                follow_user=request.user,
            )
        return {'msg': f'已为{len(customers)}个客户生成客服接待任务', 'processed_count': len(customers)}

    @classmethod
    def run_telemarketing(cls, request, config):
        customers = cls.get_target_customers(int(config.get('batch_size') or 20), 'phone')
        created_count = 0
        for customer in customers:
            contact = customer.primary_contact
            phone = contact.phone if contact and contact.phone else customer.tax_mobile
            if not phone:
                continue
            CallRecord.objects.create(
                create_user=request.user,
                customer=customer,
                customer_name=customer.name,
                phone=phone,
                status=0,
                remark=f'电话营销机器人待外呼；话术：{config.get("script", "")}',
            )
            created_count += 1
        return {'msg': f'已创建{created_count}个电话营销外呼任务', 'processed_count': created_count}

    @classmethod
    def run_email_marketing(cls, request, config):
        customers = cls.get_target_customers(int(config.get('batch_size') or 20), 'email')
        for customer in customers:
            FollowRecord.objects.create(
                customer=customer,
                follow_type='email',
                content=f'邮件营销任务：{config.get("subject", "客户关怀提醒")}；模板：{config.get("template", "")}',
                follow_user=request.user,
            )
        return {'msg': f'已创建{len(customers)}个邮件营销任务', 'processed_count': len(customers)}

    @classmethod
    def run_sms_marketing(cls, request, config):
        customers = cls.get_target_customers(int(config.get('batch_size') or 20), 'phone')
        for customer in customers:
            FollowRecord.objects.create(
                customer=customer,
                follow_type='other',
                content=f'短信营销任务：{config.get("signature", "")} {config.get("template", "")}',
                follow_user=request.user,
            )
        return {'msg': f'已创建{len(customers)}个短信营销任务', 'processed_count': len(customers)}

    @classmethod
    def run_wechat(cls, request, config):
        customers = cls.get_target_customers(int(config.get('batch_size') or 20), 'phone')
        for customer in customers:
            FollowRecord.objects.create(
                customer=customer,
                follow_type='other',
                content=f'微信触达任务：{config.get("robot_name", "微信机器人")}；欢迎语：{config.get("welcome_text", "")}',
                follow_user=request.user,
            )
        return {'msg': f'已创建{len(customers)}个微信触达任务', 'processed_count': len(customers)}

    @classmethod
    def write_log(cls, request, robot_name, content):
        SystemLog.objects.create(
            user=request.user,
            log_type='other',
            module=cls.MODULE_NAME,
            action=f'{robot_name}运行',
            content=content,
            ip_address=request.META.get('REMOTE_ADDR', '0.0.0.0'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )


class MarketingRobotDataView(LoginRequiredMixin, View):
    """营销机器人数据API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        data = MarketingRobotService.get_robot_data()
        return JsonResponse({
            'code': 0,
            'msg': '获取数据成功',
            'data': data['robots'],
            'count': len(data['robots']),
            'config': data['config'],
        }, json_dumps_params={'ensure_ascii': False})


class MarketingRobotConfigView(LoginRequiredMixin, View):
    """营销机器人配置API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request):
        try:
            data = json.loads(request.body or '{}')
            robot_type = data.get('robot_type')
            config = data.get('config') or {}
            result = MarketingRobotService.save_config(robot_type, config)
            if result.get('code') == 0:
                SystemLog.objects.create(
                    user=request.user,
                    log_type='update',
                    module=MarketingRobotService.MODULE_NAME,
                    action=f'{MarketingRobotService.ROBOTS[robot_type]["name"]}配置',
                    content=f'配置已更新：{json.dumps(result["data"], ensure_ascii=False)}',
                    ip_address=request.META.get('REMOTE_ADDR', '0.0.0.0'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            return JsonResponse(result, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'保存营销机器人配置失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': f'保存失败: {str(e)}'}, status=500)


class MarketingRobotExecuteView(LoginRequiredMixin, View):
    """营销机器人执行API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request):
        try:
            data = json.loads(request.body or '{}')
            result = MarketingRobotService.execute(data.get('robot_type'), request)
            return JsonResponse(result, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'执行营销机器人失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': f'执行失败: {str(e)}'}, status=500)


class MarketingRobotValidateView(LoginRequiredMixin, View):
    """营销机器人运行验证API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        robot_type = request.GET.get('robot_type')
        validation = MarketingRobotService.validate_robot(robot_type)
        return JsonResponse({
            'code': 0,
            'msg': '验证完成',
            'data': validation,
        }, json_dumps_params={'ensure_ascii': False})


class MarketingRobotLogView(LoginRequiredMixin, View):
    """营销机器人日志API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        robot_type = request.GET.get('robot_type')
        queryset = SystemLog.objects.filter(module=MarketingRobotService.MODULE_NAME)
        if robot_type in MarketingRobotService.ROBOTS:
            queryset = queryset.filter(action__contains=MarketingRobotService.ROBOTS[robot_type]['name'])
        logs = queryset.order_by('-created_at')[:50]
        data = [{
            'action': log.action,
            'content': log.content,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'user': log.user.name or log.user.username if log.user else ''
        } for log in logs]
        return JsonResponse({'code': 0, 'msg': '获取日志成功', 'data': data}, json_dumps_params={'ensure_ascii': False})

# 爬虫任务批量删除
class SpiderTaskBatchDeleteView(LoginRequiredMixin, View):
    """爬虫任务批量删除"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def post(self, request):
        try:
            import json
            data = json.loads(request.body)
            ids = data.get('ids', [])
            
            if not ids:
                return JsonResponse({'status': 'error', 'message': '请选择要删除的任务'}, status=400)
            
            SpiderTask.objects.filter(id__in=ids).delete()
            
            return JsonResponse({'status': 'success', 'message': f'成功删除{len(ids)}个任务'})
        except Exception as e:
            logger.error(f'批量删除爬虫任务失败: {str(e)}')
            return JsonResponse({'status': 'error', 'message': f'删除失败: {str(e)}'}, status=500)

# 爬虫任务启动和停止
class SpiderTaskStartView(LoginRequiredMixin, View):
    """启动爬虫任务"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def post(self, request, pk):
        try:
            task = SpiderTask.objects.get(id=pk)
            task.start()
            
            return JsonResponse({'status': 'success', 'message': '任务启动成功'})
        except Exception as e:
            logger.error(f'启动爬虫任务失败: {str(e)}')
            return JsonResponse({'status': 'error', 'message': f'启动失败: {str(e)}'}, status=500)

class SpiderTaskStopView(LoginRequiredMixin, View):
    """停止爬虫任务"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def post(self, request, pk):
        try:
            # 这里可以添加实际的停止逻辑
            # task = SpiderTask.objects.get(id=pk)
            # task.stop()
            
            return JsonResponse({'status': 'success', 'message': '任务停止成功'})
        except Exception as e:
            logger.error(f'停止爬虫任务失败: {str(e)}')
            return JsonResponse({'status': 'error', 'message': f'停止失败: {str(e)}'}, status=500)




# 客户字段管理视图
@login_required
def customer_field_page(request):
    """客户字段页面"""
    return render(request, 'customer/customer_field_list.html')


@login_required
@require_POST
def sip_call(request):
    """SIP拨号接口"""
    import requests
    import time
    from django.http import JsonResponse
    from .models import CallRecord
    from apps.system.config_service import config_service
    
    try:
        phone = request.POST.get('phone')
        customer_id = request.POST.get('customer_id')
        customer_name = request.POST.get('customer_name', '')
        
        if not phone:
            return JsonResponse({'code': 1, 'msg': '电话号码不能为空'})
        
        sip_account = request.user.sip_account
        sip_password = request.user.sip_password
        
        if not sip_account or not sip_password:
            return JsonResponse({'code': 1, 'msg': '当前用户未配置SIP账号信息，请联系管理员'})
        
        sip_server_url = config_service.get_config('sip_server_url', 'http://192.168.1.200:9078')
        lycc_url = f"{sip_server_url.rstrip('/')}" if sip_server_url else "http://192.168.1.200:9078"
        params = {
            'op': 'callout',
            'Exten': sip_account,
            'phone': phone,
            'flowid': f"{request.user.id}_{int(time.time() * 1000)}"
        }

        response = requests.get(lycc_url, params=params, timeout=10)
        result = response.text.strip()
        
        # 解析LYCC系统的返回结果
        if result == '100':
            # 呼叫成功，记录拨号记录
            call_record = CallRecord.objects.create(
                create_user=request.user,
                customer_id=customer_id if customer_id else None,
                customer_name=customer_name,
                phone=phone,
                status=3,  # 3表示通话中
                flow_id=params['flowid']  # 保存flow_id
            )
            return JsonResponse({'code': 0, 'msg': '呼叫成功', 'call_id': call_record.id})
        else:
            # 呼叫失败，记录失败原因
            error_map = {
                '101': '分机号不存在',
                '102': '没有空闲的线路',
                '103': '参数错误',
                '104': '外呼失败',
                '105': '分机未注册',
                '500': '其他错误'
            }
            
            error_msg = error_map.get(result, f'未知错误: {result}')
            
            CallRecord.objects.create(
                create_user=request.user,
                customer_id=customer_id if customer_id else None,
                customer_name=customer_name,
                phone=phone,
                status=2,  # 2表示拨号失败
                flow_id=params['flowid']  # 保存flow_id
            )
            return JsonResponse({'code': 1, 'msg': f'呼叫失败: {error_msg} (错误码: {result})', 'result_code': result, 'error_message': error_msg})
            
    except Exception as e:
        # 记录异常信息
        try:
            CallRecord.objects.create(
                create_user=request.user,
                customer_id=customer_id if customer_id else None,
                customer_name=customer_name,
                phone=phone,
                status=2,  # 2表示拨号失败
                flow_id=params.get('flowid', '')  # 保存flow_id
            )
        except Exception as create_error:
            logger.error(f'创建拨号记录失败: {str(create_error)}')
        return JsonResponse({'code': 1, 'msg': f'呼叫失败: {str(e)}'})

@login_required
def update_call_status(request):
    """更新通话状态"""
    import requests
    import json
    import datetime
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import CallRecord
    
    try:
        # 从当前用户获取所有通话记录
        all_calls = CallRecord.objects.filter(
            create_user=request.user
        )
        
        # 调用LYCC系统的外呼记录接口，获取最新的通话状态
        lycc_url = "http://192.168.1.200:9078"
        params = {
            'op': 'outlist',
            'WorkerID': request.user.sip_account  # 使用SIP账号作为员工工号
        }
        
        response = requests.get(lycc_url, params=params)
        call_records_data = []
        
        # 尝试解析响应
        if response.text:
            try:
                # 预处理响应：去除前后空白字符，然后转义反斜杠
                raw_text = response.text.strip()
                # 替换所有反斜杠为双反斜杠以符合JSON规范
                fixed_text = raw_text.replace('\\', '\\\\')
                call_records_data = json.loads(fixed_text)
            except json.JSONDecodeError:
                # 如果解析失败，记录错误（只记录前100字符避免日志过大）
                logger.error(f'LYCC接口返回数据格式错误: {response.text[:100]}...')
        
        # 更新本地记录的状态
        updated_count = 0
        
        # 1. 先处理所有通话记录，尝试从LYCC获取最新状态
        if call_records_data:
            # 遍历所有本地记录
            for local_call in all_calls:
                # 查找对应的远程记录
                for remote_call in call_records_data:
                    # 根据flow_id或电话号码匹配（使用CallerID和CalleeID字段）
                    if (remote_call.get('FlowNo') == local_call.flow_id or 
                        remote_call.get('CallerID') == local_call.phone or 
                        remote_call.get('CalleeID') == local_call.phone):
                        
                        # 更新本地状态和时长
                        # 完整的状态映射，包括数值结果（根据文档第237行）
                        status_map = {
                            # 字符串状态
                            '呼叫中': 3,      # 3表示通话中
                            '通话中': 3,
                            '未接通': 0,      # 0表示未接通
                            '已通话': 1,      # 1表示已通话
                            '通话完成': 1,    # 通话完成对应已通话
                            '呼叫失败': 2,    # 2表示呼叫失败
                            '通话结束': 1,    # 通话结束对应已通话
                            # 数值状态（根据文档第237行）
                            0: 0,    # 0呼叫排队中 → 未接通
                            1: 3,    # 1呼叫中 → 通话中
                            3: 1,    # 3呼叫成功 → 已通话
                            4: 2,    # 4呼叫失败 → 呼叫失败
                            6: 1,    # 6已转人工 → 已通话
                            7: 2,    # 7转人工失败 → 呼叫失败
                            8: 3     # 8转人工呼叫中 → 通话中
                        }
                        
                        # 获取远程状态，根据文档可能的字段名
                        remote_status = remote_call.get('Status', '') or remote_call.get('Result', '')
                        
                        # 尝试将状态转换为数值，处理字符串状态和数值状态
                        try:
                            # 尝试转换为整数
                            remote_status = int(remote_status)
                        except (ValueError, TypeError):
                            # 如果转换失败，保持为字符串
                            pass
                        
                        # 获取新状态
                        new_status = status_map.get(remote_status, local_call.status)
                        
                        # 获取通话时长，根据文档可能的字段名
                        duration = remote_call.get('Hold', 0) or remote_call.get('Duration', 0)
                        
                        # 确保时长是整数
                        try:
                            duration = int(duration)
                        except (ValueError, TypeError):
                            duration = 0
                        
                        # 计算实际通话时长
                        if local_call.status == 3 and new_status != 3:  # 通话结束
                            # 计算从拨号时间到现在的时间差
                            from django.utils import timezone
                            now = timezone.now()
                            call_duration = int((now - local_call.call_time).total_seconds())
                            # 确保时长大于0
                            if call_duration > 0:
                                duration = call_duration
                        
                        # 只有当状态或时长有变化时才更新
                        if local_call.status != new_status or local_call.duration != duration:
                            local_call.status = new_status
                            local_call.duration = duration
                            local_call.save()
                            updated_count += 1
                        break
        
        # 2. 处理超时的"通话中"记录
        timeout_threshold = timezone.now() - datetime.timedelta(minutes=1)  # 1分钟超时，快速更新
        
        timed_out_calls = CallRecord.objects.filter(
            create_user=request.user,
            status=3,  # 3表示通话中
            call_time__lt=timeout_threshold
        )
        
        for call in timed_out_calls:
            # 超时的通话中记录标记为已通话（假设通话已完成）
            call.status = 1  # 1表示已通话
            # 设置合理的通话时长，默认为60秒
            if call.duration == 0:
                call.duration = 60
            call.save()
            updated_count += 1
        
        return JsonResponse({'code': 0, 'msg': f'成功更新{updated_count}条通话状态', 'updated_count': updated_count})
    except Exception as e:
        logger.error(f'更新通话状态失败: {str(e)}')
        return JsonResponse({'code': 1, 'msg': f'更新通话状态失败: {str(e)}'})

# 跟进字段管理视图
@login_required
def follow_field_list(request):
    """跟进字段列表"""
    from django.shortcuts import render
    
    # 准备上下文，使用静态URL路径
    context = {
        'page_title': '跟进字段管理',
        'list_url': '/customer/follow/field/list/data/',
        'add_url': '/customer/follow/field/form/',
        'edit_url': '/customer/follow/field/form/{id}/',
        'delete_url': '/customer/follow/field/delete/{id}/'
    }
    
    return render(request, 'customer/follow_field_list.html', context)

@login_required
def follow_field_form(request, pk=None):
    """跟进字段表单"""
    from apps.common.views_utils import generic_form_view
    from .models import FollowField
    from .forms import FollowFieldForm
    return generic_form_view(
        request,
        FollowField,
        FollowFieldForm,
        'customer/follow_field_form.html',
        'customer:follow_field_list',
        pk
    )

@login_required
def follow_field_list_data(request):
    """跟进字段列表数据API"""
    from .models import FollowField
    from django.core.paginator import Paginator
    from django.db.models import Q
    from django.http import JsonResponse
    
    try:
        search = request.GET.get('search', '')
        page = int(request.GET.get('page', 1))
        limit = CommonService.get_page_size(request, 20)
        
        # 构建查询
        query = Q()
        if search:
            query |= Q(name__icontains=search) | Q(field_name__icontains=search)
        
        # 获取数据
        fields = FollowField.objects.filter(query).order_by('sort_order', 'id')
        
        # 分页
        paginator = Paginator(fields, limit)
        page_obj = paginator.get_page(page)
        
        # 构建返回数据
        data = []
        for field in page_obj:
            data.append({
                'id': field.id,
                'name': field.name,
                'field_name': field.field_name,
                'field_type': field.field_type,
                'get_field_type_display': field.get_field_type_display(),
                'is_required': field.is_required,
                'sort_order': field.sort_order,
                'is_active': field.is_active,
                'created_at': field.created_at.strftime('%Y-%m-%d %H:%M:%S') if field.created_at else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})

@login_required
def follow_field_toggle(request, pk):
    """切换跟进字段状态"""
    try:
        from .models import FollowField
        field = FollowField.objects.get(id=pk)
        field.is_active = not field.is_active
        field.save()
        
        status_text = '启用' if field.is_active else '禁用'
        return JsonResponse({'code': 0, 'msg': f'字段已{status_text}'})
        
    except FollowField.DoesNotExist:
        return JsonResponse({'code': 1, 'msg': '字段不存在'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'操作失败: {str(e)}'})

@login_required
def follow_field_delete(request, pk):
    """删除跟进字段"""
    try:
        from .models import FollowField
        field = FollowField.objects.get(id=pk)
        field.delete()
        
        return JsonResponse({'code': 0, 'msg': '删除成功'})
        
    except FollowField.DoesNotExist:
        return JsonResponse({'code': 1, 'msg': '字段不存在'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})

# 订单字段管理视图
@login_required
def order_field_list_data(request):
    """订单字段列表数据API"""
    from .models import OrderField
    from django.core.paginator import Paginator
    from django.db.models import Q
    from django.http import JsonResponse
    
    try:
        search = request.GET.get('search', '')
        page = int(request.GET.get('page', 1))
        limit = CommonService.get_page_size(request, 20)
        
        # 构建查询
        query = Q()
        if search:
            query |= Q(name__icontains=search) | Q(field_name__icontains=search)
        
        # 获取数据
        fields = OrderField.objects.filter(query).order_by('sort_order', 'id')
        
        # 分页
        paginator = Paginator(fields, limit)
        page_obj = paginator.get_page(page)
        
        # 构建返回数据
        data = []
        for field in page_obj:
            data.append({
                'id': field.id,
                'name': field.name,
                'field_name': field.field_name,
                'field_type': field.field_type,
                'get_field_type_display': field.get_field_type_display(),
                'is_required': field.is_required,
                'is_summary': field.is_summary,
                'sort_order': field.sort_order,
                'is_active': field.is_active,
                'created_at': field.created_at.strftime('%Y-%m-%d %H:%M:%S') if field.created_at else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})

@login_required
def order_field_toggle(request, pk):
    """切换订单字段状态"""
    try:
        from .models import OrderField
        field = OrderField.objects.get(id=pk)
        field.is_active = not field.is_active
        field.save()
        
        status_text = '启用' if field.is_active else '禁用'
        return JsonResponse({'code': 0, 'msg': f'字段已{status_text}'})
        
    except OrderField.DoesNotExist:
        return JsonResponse({'code': 1, 'msg': '字段不存在'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'操作失败: {str(e)}'})

@login_required
def order_field_delete(request, pk):
    """删除订单字段"""
    try:
        from .models import OrderField
        field = OrderField.objects.get(id=pk)
        field.delete()
        
        return JsonResponse({'code': 0, 'msg': '删除成功'})
        
    except OrderField.DoesNotExist:
        return JsonResponse({'code': 1, 'msg': '字段不存在'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})

@login_required
def order_field_list(request):
    """订单字段列表"""
    from django.shortcuts import render
    
    # 准备上下文，使用静态URL路径
    context = {
        'page_title': '订单字段管理',
        'list_url': '/customer/order/field/list/data/',
        'add_url': '/customer/order/field/form/',
        'edit_url': '/customer/order/field/form/{id}/',
        'delete_url': '/customer/order/field/delete/{id}/'
    }
    
    return render(request, 'customer/order_field_list.html', context)

@login_required
def order_field_form(request, pk=None):
    """订单字段表单"""
    from apps.common.views_utils import generic_form_view
    from .models import OrderField
    from .forms import OrderFieldForm
    return generic_form_view(
        request,
        OrderField,
        OrderFieldForm,
        'customer/order_field_form.html',
        'customer:order_field_list',
        pk
    )


@login_required
def follow_field_sync(request):
    """同步跟进字段配置"""
    from django.http import JsonResponse
    from .models import FollowField, FollowRecord, FollowRecordCustomFieldValue
    
    if request.method == 'POST':
        try:
            # 获取所有启用的跟进字段
            active_fields = FollowField.objects.filter(is_active=True)
            
            # 获取所有跟进记录
            follow_records = FollowRecord.objects.all()
            
            # 为每个跟进记录同步字段
            sync_count = 0
            for follow_record in follow_records:
                for field in active_fields:
                    # 检查是否已存在对应的自定义字段值记录
                    custom_field_value, created = FollowRecordCustomFieldValue.objects.get_or_create(
                        follow_record=follow_record,
                        field=field,
                        defaults={'value': ''}
                    )
                    if created:
                        sync_count += 1

            # 返回成功响应
            return JsonResponse({
                'status': 'success',
                'message': f'成功同步 {sync_count} 个跟进字段配置'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'同步失败: {str(e)}'
            })
    else:
        return JsonResponse({
            'status': 'error',
            'message': '无效的请求方法'
        })


@login_required
def order_field_sync(request):
    """同步订单字段配置"""
    from django.http import JsonResponse
    from .models import OrderField, CustomerOrder, CustomerOrderCustomFieldValue
    
    if request.method == 'POST':
        try:
            # 获取所有启用的订单字段
            active_fields = OrderField.objects.filter(is_active=True)
            
            # 获取所有订单记录
            orders = CustomerOrder.objects.all()
            
            # 为每个订单同步字段
            sync_count = 0
            for order in orders:
                for field in active_fields:
                    # 检查是否已存在对应的自定义字段值记录
                    custom_field_value, created = CustomerOrderCustomFieldValue.objects.get_or_create(
                        order=order,
                        field=field,
                        defaults={'value': ''}
                    )
                    if created:
                        sync_count += 1

            # 返回成功响应
            return JsonResponse({
                'status': 'success',
                'message': f'成功同步 {sync_count} 个订单字段配置'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'同步失败: {str(e)}'
            })
    else:
        return JsonResponse({
            'status': 'error',
            'message': '无效的请求方法'
        })


class ContractAddView(LoginRequiredMixin, View):
    """合同添加页面视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        """渲染合同添加表单页面"""
        customer_id = request.GET.get('customer_id')
        
        # 生成默认合同编号（日期+序号格式）
        from django.utils import timezone
        date_str = timezone.now().strftime('%Y%m%d')
        
        # 查找当日已存在的最大序号
        last_contract = CustomerContract.objects.filter(
            contract_number__startswith=date_str
        ).order_by('-contract_number').first()
        
        if last_contract and last_contract.contract_number:
            try:
                if len(last_contract.contract_number) >= 12:
                    last_num = int(last_contract.contract_number[8:12])
                    new_num = last_num + 1
                else:
                    new_num = 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        default_contract_number = f'{date_str}{new_num:04d}'
        
        # 加载合同分类数据
        try:
            from apps.contract.models import ContractCategory
            contract_categories = ContractCategory.objects.all()
            if hasattr(ContractCategory, 'is_active'):
                contract_categories = contract_categories.filter(is_active=True)
            contract_categories = contract_categories.order_by('name')
        except ImportError:
            contract_categories = []

        context = {
            'default_contract_number': default_contract_number,
            'contract_categories': contract_categories,
            'status_choices': CustomerContract.STATUS_CHOICES,
            'type_choices': CustomerContract.TYPE_CHOICES,
        }
        
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id, delete_time=0)
                context['customer'] = customer
                return render(request, 'customer/add_contract.html', context)
            except Customer.DoesNotExist:
                context['error'] = '客户不存在'
                return render(request, 'customer/add_contract.html', context)
        
        return render(request, 'customer/add_contract.html', context)

    def post(self, request):
        """处理合同添加表单提交"""
        from django.http import JsonResponse
        import json
        
        try:
            if request.content_type and 'application/json' in request.content_type:
                data = json.loads(request.body or '{}')
            else:
                data = request.POST.dict()
            
            # 获取客户ID
            customer_id = data.get('customer_id')
            if not customer_id:
                return JsonResponse({
                    'code': 1,
                    'msg': '客户ID不能为空'
                })
            
            # 验证客户是否存在
            try:
                customer = Customer.objects.get(id=customer_id, delete_time=0)
            except Customer.DoesNotExist:
                return JsonResponse({
                    'code': 1,
                    'msg': '客户不存在'
                })
            
            # 验证必填字段
            required_fields = ['contract_number', 'name', 'amount', 'sign_date', 'status', 'category_id']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'code': 1,
                        'msg': f'{field}字段不能为空'
                    })
            
            # 验证和转换日期格式
            from django.utils import timezone
            
            # 处理签订日期
            sign_date = None
            if data['sign_date']:
                try:
                    # 尝试解析日期格式
                    if isinstance(data['sign_date'], str):
                        # 如果是字符串，尝试解析为日期对象
                        sign_date = timezone.datetime.strptime(data['sign_date'], '%Y-%m-%d').date()
                    else:
                        # 如果不是字符串，直接使用
                        sign_date = data['sign_date']
                except (ValueError, TypeError):
                    return JsonResponse({
                        'code': 1,
                        'msg': '签订日期格式错误，应为YYYY-MM-DD格式'
                    })
            
            # 处理到期日期
            end_date = None
            if data.get('end_date'):
                try:
                    if isinstance(data['end_date'], str):
                        end_date = timezone.datetime.strptime(data['end_date'], '%Y-%m-%d').date()
                    else:
                        end_date = data['end_date']
                except (ValueError, TypeError):
                    return JsonResponse({
                        'code': 1,
                        'msg': '到期日期格式错误，应为YYYY-MM-DD格式'
                    })
            
            # 创建合同记录
            contract = CustomerContract.objects.create(
                customer=customer,
                contract_number=data['contract_number'],
                name=data['name'],
                amount=data['amount'],
                sign_date=sign_date,
                end_date=end_date,
                status=data['status'],
                category_id=data['category_id'],
                contract_type=data.get('contract_type', ''),
                description=data.get('description', ''),
                remark=data.get('remark', ''),
                create_user=request.user
            )
            
            # 返回成功响应
            return JsonResponse({
                'code': 0,
                'msg': '合同添加成功',
                'data': {
                    'id': contract.id,
                    'contract_number': contract.contract_number,
                    'name': contract.name
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'code': 1,
                'msg': '请求数据格式错误'
            })
        except Exception as e:
            logger.error(f"合同添加失败: {str(e)}")
            return JsonResponse({
                'code': 1,
                'msg': f'合同添加失败: {str(e)}'
            })


class CustomerSelectView(LoginRequiredMixin, View):
    """客户选择视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        """渲染客户选择页面"""
        return render(request, 'customer/customer_select.html')

    def post(self, request):
        """获取客户列表数据"""
        try:
            # 获取查询参数
            search = request.POST.get('search', '')
            page = int(request.POST.get('page', 1))
            limit = int(request.POST.get('limit', 10))
            
            # 构建查询条件
            queryset = Customer.objects.filter(delete_time=0)
            
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) | 
                    Q(contacts__contact_person__icontains=search) |
                    Q(contacts__phone__icontains=search)
                ).distinct()
            
            # 分页处理
            total_count = queryset.count()
            start = (page - 1) * limit
            end = start + limit
            customers = queryset[start:end]
            
            # 构建返回数据
            data = []
            for customer in customers:
                # 获取主要联系人信息
                primary_contact = customer.contacts.filter(is_primary=True).first()
                if not primary_contact:
                    primary_contact = customer.contacts.first()
                
                contact_name = primary_contact.contact_person if primary_contact else ''
                phone = primary_contact.phone if primary_contact else ''
                
                data.append({
                    'id': customer.id,
                    'name': customer.name,
                    'contact_name': contact_name,
                    'phone': phone,
                    'address': customer.address,
                    'create_time': customer.create_time.strftime('%Y-%m-%d') if customer.create_time else ''
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            })
            
        except Exception as e:
            logger.error(f"获取客户列表失败: {str(e)}")
            return JsonResponse({
                'code': 1,
                'msg': f'获取客户列表失败: {str(e)}'
            })


class ContractNumberCheckView(LoginRequiredMixin, View):
    """检查合同编号是否已存在"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request):
        """检查合同编号是否已存在"""
        contract_number = request.POST.get('contract_number')
        
        if not contract_number:
            return JsonResponse({
                'exists': False,
                'msg': '合同编号不能为空'
            })
        
        # 检查编号是否已存在
        exists = CustomerContract.objects.filter(
            contract_number=contract_number
        ).exists()
        
        return JsonResponse({
            'exists': exists,
            'msg': '编号已存在' if exists else '编号可用'
        })


class ContractNumberGenerateView(LoginRequiredMixin, View):
    """生成新的合同编号"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        """生成新的合同编号"""
        from django.utils import timezone
        
        # 生成默认合同编号（日期+序号格式）
        date_str = timezone.now().strftime('%Y%m%d')
        
        # 查找当日已存在的最大序号
        last_contract = CustomerContract.objects.filter(
            contract_number__startswith=date_str
        ).order_by('-contract_number').first()
        
        if last_contract and last_contract.contract_number:
            try:
                if len(last_contract.contract_number) >= 12:
                    last_num = int(last_contract.contract_number[8:12])
                    new_num = last_num + 1
                else:
                    new_num = 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        contract_number = f'{date_str}{new_num:04d}'
        
        return JsonResponse({
            'code': 0,
            'contract_number': contract_number,
            'msg': '合同编号生成成功'
        })


class CustomerContractListView(LoginRequiredMixin, View):
    """客户合同列表视图（用于局部刷新）"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, customer_id):
        """获取客户合同列表HTML片段"""
        try:
            # 获取客户信息
            customer = Customer.objects.get(id=customer_id, delete_time=0)
            
            # 获取客户的最近合同（最多5个）
            contracts = customer.contracts.filter(delete_time=0).order_by('-create_time')[:5]
            
            # 渲染合同列表HTML片段
            return render(request, 'customer/_contract_list.html', {
                'customer': customer,
                'contracts': contracts
            })
            
        except Customer.DoesNotExist:
            return HttpResponse('<p style="text-align: center; color: #999; padding: 20px;">客户不存在</p>')
        except Exception as e:
            logger.error(f"获取客户合同列表失败: {str(e)}")
            return HttpResponse('<p style="text-align: center; color: #999; padding: 20px;">获取合同列表失败</p>')


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime
import json

from .models import CustomerSource, CustomerGrade, CustomerIntent, FollowField, OrderField
from .forms import CustomerSourceForm, CustomerGradeForm, CustomerIntentForm, FollowFieldForm, OrderFieldForm
from apps.common.views_utils import generic_list_view, generic_form_view


@login_required
def customer_source_list(request):
    return generic_list_view(
        request,
        CustomerSource,
        'customer/customer_source_list.html',
        search_fields=['title']
    )


@login_required
def customer_source_form(request, pk=None):
    return generic_form_view(
        request,
        CustomerSource,
        CustomerSourceForm,
        'customer/customer_source_form.html',
        'customer:customer_source_list',
        pk
    )


@login_required
def customer_source_list_data(request):
    try:
        search = request.GET.get('search', '')
        page = int(request.GET.get('page', 1))
        limit = CommonService.get_page_size(request, 20)
        
        queryset = CustomerSource.objects.filter(delete_time=0)
        
        if search:
            queryset = queryset.filter(title__icontains=search)
        
        queryset = queryset.order_by('sort', 'id')
        
        paginator = Paginator(queryset, limit)
        page_obj = paginator.get_page(page)
        
        data = []
        for obj in page_obj:
            data.append({
                'id': obj.id,
                'title': obj.title,
                'sort': obj.sort,
                'status': obj.status,
                'status_display': '启用' if obj.status == 1 else '禁用',
                'create_time': obj.create_time.strftime('%Y-%m-%d %H:%M:%S') if obj.create_time else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})


@login_required
def customer_source_toggle(request, pk):
    try:
        obj = get_object_or_404(CustomerSource, pk=pk, delete_time=0)
        obj.status = 1 - obj.status
        obj.save()
        
        status_text = '启用' if obj.status == 1 else '禁用'
        return JsonResponse({'code': 0, 'msg': f'客户来源已{status_text}'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'操作失败: {str(e)}'})


@login_required
def customer_source_delete(request, pk):
    try:
        obj = get_object_or_404(CustomerSource, pk=pk, delete_time=0)
        obj.delete_time = int(timezone.now().timestamp())
        obj.save()
        
        return JsonResponse({'code': 0, 'msg': '删除成功'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})


@login_required
def customer_grade_list(request):
    return generic_list_view(
        request,
        CustomerGrade,
        'customer/customer_grade_list.html',
        search_fields=['title']
    )


@login_required
def customer_grade_form(request, pk=None):
    return generic_form_view(
        request,
        CustomerGrade,
        CustomerGradeForm,
        'customer/customer_grade_form.html',
        'customer:customer_grade_list',
        pk
    )


@login_required
def customer_grade_list_data(request):
    try:
        search = request.GET.get('search', '')
        page = int(request.GET.get('page', 1))
        limit = CommonService.get_page_size(request, 20)
        
        queryset = CustomerGrade.objects.filter(delete_time=0)
        
        if search:
            queryset = queryset.filter(title__icontains=search)
        
        queryset = queryset.order_by('sort', 'id')
        
        paginator = Paginator(queryset, limit)
        page_obj = paginator.get_page(page)
        
        data = []
        for obj in page_obj:
            data.append({
                'id': obj.id,
                'title': obj.title,
                'sort': obj.sort,
                'status': obj.status,
                'status_display': '启用' if obj.status == 1 else '禁用',
                'create_time': obj.create_time.strftime('%Y-%m-%d %H:%M:%S') if obj.create_time else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})


@login_required
def customer_grade_toggle(request, pk):
    try:
        obj = get_object_or_404(CustomerGrade, pk=pk, delete_time=0)
        obj.status = 1 - obj.status
        obj.save()
        
        status_text = '启用' if obj.status == 1 else '禁用'
        return JsonResponse({'code': 0, 'msg': f'客户等级已{status_text}'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'操作失败: {str(e)}'})


@login_required
def customer_grade_delete(request, pk):
    try:
        obj = get_object_or_404(CustomerGrade, pk=pk, delete_time=0)
        obj.delete_time = int(timezone.now().timestamp())
        obj.save()
        
        return JsonResponse({'code': 0, 'msg': '删除成功'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})


@login_required
def customer_intent_list(request):
    return generic_list_view(
        request,
        CustomerIntent,
        'customer/customer_intent_list.html',
        search_fields=['name']
    )


@login_required
def customer_intent_form(request, pk=None):
    return generic_form_view(
        request,
        CustomerIntent,
        CustomerIntentForm,
        'customer/customer_intent_form.html',
        'customer:customer_intent_list',
        pk
    )


@login_required
def customer_intent_list_data(request):
    try:
        search = request.GET.get('search', '')
        page = int(request.GET.get('page', 1))
        limit = CommonService.get_page_size(request, 20)
        
        queryset = CustomerIntent.objects.filter(delete_time=0)
        
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        queryset = queryset.order_by('sort', 'id')
        
        paginator = Paginator(queryset, limit)
        page_obj = paginator.get_page(page)
        
        data = []
        for obj in page_obj:
            data.append({
                'id': obj.id,
                'name': obj.name,
                'sort': obj.sort,
                'status': obj.status,
                'status_display': '启用' if obj.status == 1 else '禁用',
                'create_time': obj.create_time.strftime('%Y-%m-%d %H:%M:%S') if obj.create_time else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})


@login_required
def customer_intent_toggle(request, pk):
    try:
        obj = get_object_or_404(CustomerIntent, pk=pk, delete_time=0)
        obj.status = 1 - obj.status
        obj.save()
        
        status_text = '启用' if obj.status == 1 else '禁用'
        return JsonResponse({'code': 0, 'msg': f'客户意向已{status_text}'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'操作失败: {str(e)}'})


@login_required
def customer_intent_delete(request, pk):
    try:
        obj = get_object_or_404(CustomerIntent, pk=pk, delete_time=0)
        obj.delete_time = int(timezone.now().timestamp())
        obj.save()
        
        return JsonResponse({'code': 0, 'msg': '删除成功'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})


@login_required
def customer_intent_update_sort(request, pk):
    try:
        obj = get_object_or_404(CustomerIntent, pk=pk, delete_time=0)
        new_sort = int(request.POST.get('sort', 0))
        
        obj.sort = new_sort
        obj.save()
        
        return JsonResponse({'code': 0, 'msg': '排序更新成功'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'排序更新失败: {str(e)}'})


@login_required
def customer_intent_batch_update_sort(request):
    try:
        data = json.loads(request.body)
        intents = data.get('intents', [])
        
        for item in intents:
            intent_id = item.get('id')
            new_sort = item.get('sort')
            
            if intent_id and new_sort is not None:
                CustomerIntent.objects.filter(id=intent_id, delete_time=0).update(sort=new_sort)
        
        return JsonResponse({'code': 0, 'msg': '批量排序更新成功'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'批量排序更新失败: {str(e)}'})


@login_required
def customer_field_list(request):
    return generic_list_view(
        request,
        CustomerField,
        'customer/customer_field_list.html',
        search_fields=['name', 'field_name']
    )


@login_required
def customer_field_form(request, pk=None):
    return generic_form_view(
        request,
        CustomerField,
        CustomerFieldForm,
        'customer/customer_field_form.html',
        'customer:customer_field_list',
        pk
    )


@login_required
def customer_field_list_data(request):
    try:
        search = request.GET.get('search', '')
        page = int(request.GET.get('page', 1))
        limit = CommonService.get_page_size(request, 20)
        
        queryset = CustomerField.objects.filter(delete_time=0).select_related('related_field')
        
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(field_name__icontains=search))
        
        queryset = queryset.order_by('sort', 'id')
        
        paginator = Paginator(queryset, limit)
        page_obj = paginator.get_page(page)
        
        data = []
        for obj in page_obj:
            data.append({
                'id': obj.id,
                'name': obj.name,
                'field_name': obj.field_name,
                'field_type': obj.field_type,
                'field_type_display': obj.get_field_type_display(),
                'is_required': obj.is_required,
                'is_unique': obj.is_unique,
                'relation_enabled': obj.relation_enabled,
                'related_field_name': obj.related_field.name if obj.related_field else '',
                'relation_type': obj.relation_type,
                'relation_type_display': obj.get_relation_type_display() if obj.relation_enabled else '',
                'calculation_type': obj.calculation_type,
                'calculation_type_display': obj.get_calculation_type_display() if getattr(obj, 'calculation_type', '') else '',
                'formula_expression': getattr(obj, 'formula_expression', '') or '',
                'is_list_display': obj.is_list_display,
                'sort': obj.sort,
                'status': obj.status,
                'status_display': '启用' if obj.status == 1 else '禁用',
                'create_time': obj.create_time.strftime('%Y-%m-%d %H:%M:%S') if obj.create_time else ''
            })
        
        return JsonResponse({
            'code': 0,
            'msg': '',
            'count': paginator.count,
            'data': data
        })
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'获取失败: {str(e)}'})


@login_required
def customer_field_toggle(request, pk):
    try:
        obj = get_object_or_404(CustomerField, pk=pk, delete_time=0)
        obj.status = 1 - obj.status
        obj.save()
        
        status_text = '启用' if obj.status == 1 else '禁用'
        return JsonResponse({'code': 0, 'msg': f'客户字段已{status_text}'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'操作失败: {str(e)}'})


@login_required
def customer_field_delete(request, pk):
    try:
        obj = get_object_or_404(CustomerField, pk=pk, delete_time=0)
        obj.delete_time = int(timezone.now().timestamp())
        obj.save()
        
        return JsonResponse({'code': 0, 'msg': '删除成功'})
    except Exception as e:
        return JsonResponse({'code': 1, 'msg': f'删除失败: {str(e)}'})


@login_required
def follow_field_list(request):
    return generic_list_view(
        request,
        FollowField,
        'customer/follow_field_list.html',
        search_fields=['name', 'field_name'],
        list_url=reverse_lazy('customer:follow_field_list_data'),
        add_url=reverse_lazy('customer:follow_field_form'),
        edit_url='/customer/follow/field/form/{id}/',
        delete_url='/customer/follow/field/delete/{id}/',
    )


@login_required
def follow_field_form(request, pk=None):
    return generic_form_view(
        request,
        FollowField,
        FollowFieldForm,
        'customer/follow_field_form.html',
        'customer:follow_field_list',
        pk
    )


@login_required
def order_field_list(request):
    return generic_list_view(
        request,
        OrderField,
        'customer/order_field_list.html',
        search_fields=['name', 'field_name'],
        list_url=reverse_lazy('customer:order_field_list_data'),
        add_url=reverse_lazy('customer:order_field_form'),
        edit_url='/customer/order/field/form/{id}/',
        delete_url='/customer/order/field/delete/{id}/',
    )


@login_required
def order_field_form(request, pk=None):
    return generic_form_view(
        request,
        OrderField,
        OrderFieldForm,
        'customer/order_field_form.html',
        'customer:order_field_list',
        pk
    )



