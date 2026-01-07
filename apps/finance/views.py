from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView
from django.views import View
from django.http import JsonResponse
from .models import Expense, Invoice, InvoiceRequest, OrderFinanceRecord, Income, Payment
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.paginator import Paginator
import json
import time
from datetime import datetime
import logging

from apps.common.utils import (
    timestamp_to_date, get_status_display, safe_int, 
    build_error_response, build_success_response,
    StatusCodeMapper
)
from apps.common.constants import (
    FinanceStatus, FinanceStatusMapping, ApiResponseCode, CommonConstant
)

logger = logging.getLogger(__name__)


class ExpenseListView(LoginRequiredMixin, View):
    """报销管理页面视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/expense_list.html')

    def get_datalist(self, request):
        """返回报销数据列表的JSON格式"""
        try:
            tab = request.GET.get('tab', '0')
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
            
            queryset = Expense.objects.all().order_by('-create_time')
            uid = request.user.id
            
            tab_map = {
                '1': ('admin_id', uid),
                '2': ('check_uids__contains', str(uid)),
                '3': ('check_history_uids__contains', str(uid)),
                '4': ('check_copy_uids__contains', str(uid)),
            }
            
            if tab in tab_map:
                field, value = tab_map[tab]
                queryset = queryset.filter(**{field: value})
            
            diff_time = request.GET.get('diff_time')
            if diff_time and '~' in diff_time:
                start, end = diff_time.split('~')
                queryset = queryset.filter(income_month__range=[start.strip(), end.strip()])
            
            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)
            
            data = []
            for expense in page_obj:
                data.append({
                    'id': expense.id,
                    'code': expense.code,
                    'cost': float(expense.cost),
                    'income_month': expense.income_month,
                    'check_status': get_status_display('check_status', expense.check_status),
                    'pay_status': get_status_display('pay_status', expense.pay_status),
                    'create_time': timestamp_to_date(expense.create_time) if expense.create_time else '',
                    'remark': expense.remark
                })
            
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取报销数据失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class ExpenseCreateView(LoginRequiredMixin, CreateView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Expense
    fields = ['subject_id', 'code', 'cost', 'income_month', 'expense_time', 'file_ids', 'remark']
    template_name = 'finance/expense_form.html'
    success_url = reverse_lazy('finance:expense_list')


class ExpenseUpdateView(LoginRequiredMixin, UpdateView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Expense
    fields = ['subject_id', 'code', 'cost', 'income_month', 'expense_time', 'file_ids', 'remark']
    template_name = 'finance/expense_form.html'
    success_url = reverse_lazy('finance:expense_list')


class InvoiceListView(LoginRequiredMixin, View):
    """发票管理页面视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/invoice_list.html')

    def get_datalist(self, request):
        """返回发票数据列表的JSON格式"""
        try:
            tab = request.GET.get('tab', '0')
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
            
            queryset = Invoice.objects.filter(invoice_type__gt=0).order_by('-create_time')
            uid = request.user.id
            
            tab_map = {
                '1': ('admin_id', uid),
                '2': ('check_uids__contains', str(uid)),
                '3': ('check_history_uids__contains', str(uid)),
                '4': ('check_copy_uids__contains', str(uid)),
            }
            
            if tab in tab_map:
                field, value = tab_map[tab]
                queryset = queryset.filter(**{field: value})
            
            diff_time = request.GET.get('diff_time')
            if diff_time and '~' in diff_time:
                start, end = diff_time.split('~')
                queryset = queryset.filter(open_time__range=[start.strip(), end.strip()])
            
            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)
            
            data = []
            for invoice in page_obj:
                data.append({
                    'id': invoice.id,
                    'code': invoice.code,
                    'amount': float(invoice.amount),
                    'customer_id': invoice.customer_id,
                    'invoice_type': get_status_display('invoice_type', invoice.invoice_type),
                    'invoice_title': invoice.invoice_title,
                    'open_status': get_status_display('open_status', invoice.open_status),
                    'enter_status': get_status_display('enter_status', invoice.enter_status),
                    'enter_amount': float(invoice.enter_amount),
                    'create_time': timestamp_to_date(invoice.create_time) if invoice.create_time else '',
                    'open_time': timestamp_to_date(invoice.open_time) if invoice.open_time else '',
                })
            
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取发票数据失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class InvoiceCreateView(LoginRequiredMixin, CreateView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Invoice
    fields = ['code', 'customer', 'contract', 'project', 'amount', 'invoice_type', 'invoice_title', 'invoice_tax', 'enter_amount']
    template_name = 'finance/invoice_form.html'
    success_url = reverse_lazy('finance:invoice_list')
    
    def get_initial(self):
        initial = super().get_initial()
        customer_id = self.request.GET.get('customer_id')
        if customer_id:
            from apps.customer.models import Customer
            initial['customer'] = Customer.objects.filter(id=customer_id).first()
        initial['enter_amount'] = 0.00
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.customer.models import Customer
        context['customers'] = Customer.objects.filter(delete_time=0)
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        try:
            self._auto_generate_related_records(form.instance, self.request.user)
        except Exception as auto_gen_error:
            logger.error(f"自动生成相关记录失败: {str(auto_gen_error)}", exc_info=True)
        return response
    
    def _auto_generate_related_records(self, invoice, user):
        """自动生成与发票相关的记录：待签约合同、待确认订单、项目"""
        try:
            from apps.customer.models import CustomerContract, CustomerOrder
            from apps.project.models import Project
            import time as time_module
            
            current_time = int(time_module.time())
            
            CustomerContract.objects.create(
                customer_id=invoice.customer_id,
                name=f"{invoice.invoice_title}合同",
                contract_number=f"CONT-INV-{invoice.code}-{current_time}",
                amount=invoice.amount,
                sign_date=None,
                end_date=None,
                status='pending',
                create_user_id=user.id,
                auto_generated=True
            )
            
            CustomerOrder.objects.create(
                customer_id=invoice.customer_id,
                product_name=invoice.invoice_title,
                order_number=f"PO-INV-{invoice.code}-{current_time}",
                amount=invoice.amount,
                order_date=None,
                status='pending',
                create_user_id=user.id,
                auto_generated=True
            )
            
            Project.objects.create(
                name=invoice.invoice_title,
                code=f"PROJ-INV-{invoice.code}-{current_time}",
                description=f"发票项目：{invoice.invoice_title}",
                customer_id=invoice.customer_id,
                contract_id=0,
                budget=invoice.amount,
                status=1,
                priority=2,
                progress=0,
                creator=user,
                auto_generated=True
            )
            
            logger.info(f"成功为发票 {invoice.id} 自动生成相关记录")
        except Exception as e:
            logger.error(f"自动生成相关记录失败: {str(e)}", exc_info=True)
            raise


class InvoiceUpdateView(LoginRequiredMixin, UpdateView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Invoice
    fields = ['code', 'customer', 'contract', 'project', 'amount', 'invoice_type', 'invoice_title', 'invoice_tax']
    template_name = 'finance/invoice_form.html'
    success_url = reverse_lazy('finance:invoice_list')


class PendingPaymentListView(LoginRequiredMixin, View):
    """待回款管理页面视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/pending_payment_list.html')

    def get_datalist(self, request):
        """返回待回款发票数据列表的JSON格式"""
        try:
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
            
            queryset = Invoice.objects.filter(
                enter_status__in=[0, 1],
                invoice_type__gt=0
            ).order_by('-create_time')
            
            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)
            
            data = []
            for invoice in page_obj:
                unpaid_amount = float(invoice.amount) - float(invoice.enter_amount)
                data.append({
                    'id': invoice.id,
                    'code': invoice.code,
                    'amount': float(invoice.amount),
                    'enter_amount': float(invoice.enter_amount),
                    'unpaid_amount': float(unpaid_amount),
                    'customer_id': invoice.customer_id,
                    'customer_name': invoice.customer.name if invoice.customer else '',
                    'contract_id': invoice.contract_id,
                    'contract_name': invoice.contract.name if invoice.contract else '',
                    'invoice_type': get_status_display('invoice_type', invoice.invoice_type),
                    'invoice_title': invoice.invoice_title,
                    'open_status': get_status_display('open_status', invoice.open_status),
                    'enter_status': get_status_display('enter_status', invoice.enter_status),
                    'create_time': timestamp_to_date(invoice.create_time) if invoice.create_time else '',
                    'open_time': timestamp_to_date(invoice.open_time) if invoice.open_time else '',
                })
            
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取待回款数据失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class IncomeListView(LoginRequiredMixin, View):
    """收入管理页面视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/income_list.html')

    def get_datalist(self, request):
        """返回收入数据列表的JSON格式"""
        try:
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
            
            queryset = Income.objects.all().select_related('invoice', 'invoice__contract').order_by('-create_time')
            
            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)
            
            data = []
            for income in page_obj:
                contract_info = {}
                if income.invoice and income.invoice.contract:
                    contract_info = {
                        'contract_id': income.invoice.contract.id,
                        'contract_code': income.invoice.contract.contract_number,
                        'contract_name': income.invoice.contract.name
                    }
                
                data.append({
                    'id': income.id,
                    'invoice_id': income.invoice.id if income.invoice else 0,
                    'invoice_code': income.invoice.code if income.invoice else '',
                    'amount': float(income.amount),
                    'income_date': income.income_date.strftime('%Y-%m-%d') if income.income_date else '',
                    'create_time': timestamp_to_date(income.create_time) if income.create_time else '',
                    'remark': income.remark,
                    'contract_info': contract_info
                })
            
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取收入数据失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class IncomeCreateView(LoginRequiredMixin, CreateView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Income
    fields = ['invoice', 'amount', 'income_date', 'file_ids', 'remark']
    template_name = 'finance/income_form.html'
    success_url = reverse_lazy('finance:paymentreceive_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer_id = self.request.GET.get('customer_id')
        if customer_id:
            context['invoices'] = Invoice.objects.filter(customer_id=customer_id)
        else:
            context['invoices'] = Invoice.objects.all()
        return context


class PaymentListView(LoginRequiredMixin, View):
    """付款管理页面视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/payment_list.html')

    def get_datalist(self, request):
        """返回付款数据列表的JSON格式"""
        try:
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
            
            queryset = Payment.objects.all().select_related('expense').order_by('-create_time')
            
            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)
            
            data = []
            for payment in page_obj:
                data.append({
                    'id': payment.id,
                    'expense_id': payment.expense.id if payment.expense else 0,
                    'expense_code': payment.expense.code if payment.expense else '',
                    'amount': float(payment.amount),
                    'payment_date': payment.payment_date.strftime('%Y-%m-%d') if payment.payment_date else '',
                    'create_time': timestamp_to_date(payment.create_time) if payment.create_time else '',
                    'remark': payment.remark,
                    'contract_info': {}
                })
            
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取付款数据失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class PaymentCreateView(LoginRequiredMixin, CreateView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Payment
    fields = ['expense', 'amount', 'payment_date', 'file_ids', 'remark']
    template_name = 'finance/payment_form.html'
    success_url = reverse_lazy('finance:payment_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['expenses'] = Expense.objects.all()
        return context


class FinanceApprovalListView(LoginRequiredMixin, ListView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Expense
    template_name = 'finance/approval_list.html'
    context_object_name = 'approvals'

    def get_queryset(self):
        return Expense.objects.filter(
            check_status__in=[FinanceStatus.EXPENSE_CHECK_PENDING],
            check_uids__contains=str(self.request.user.id)
        )


class FinanceApprovedListView(LoginRequiredMixin, ListView):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Expense
    template_name = 'finance/approved_list.html'
    context_object_name = 'approvals'

    def get_queryset(self):
        return Expense.objects.filter(
            check_status__in=[FinanceStatus.EXPENSE_CHECK_APPROVED, FinanceStatus.EXPENSE_CHECK_REJECTED],
            check_history_uids__contains=str(self.request.user.id)
        )


@method_decorator(csrf_exempt, name='dispatch')
class FinanceApprovalSubmitView(LoginRequiredMixin, View):
    login_url = '/user/login/'
    redirect_field_name = 'next'
    
    def post(self, request):
        try:
            params = json.loads(request.body)
            record_id = params.get('record_id')
            action = params.get('action')
            comment = params.get('comment', '')
            
            if not record_id or not action:
                return build_error_response('参数不完整')
            
            if action not in ['approved', 'rejected']:
                return build_error_response('无效的审批操作')
            
            expense = get_object_or_404(Expense, id=record_id)
            
            if action == 'approved':
                expense.check_status = FinanceStatus.EXPENSE_CHECK_APPROVED
            else:
                expense.check_status = FinanceStatus.EXPENSE_CHECK_REJECTED
            
            expense.check_history_uids += f',{request.user.id}'
            expense.check_time = int(time.time())
            expense.save()
            
            logger.info(f"用户 {request.user.id} 对报销记录 {record_id} 执行了 {action} 操作")
            
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '审批操作成功'
            })
        except json.JSONDecodeError:
            return build_error_response('无效的JSON数据')
        except Exception as e:
            logger.error(f'审批操作失败: {str(e)}', exc_info=True)
            return build_error_response(f'审批失败: {str(e)}')


class InvoiceRequestListView(LoginRequiredMixin, ListView):
    """开票申请列表视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = InvoiceRequest
    template_name = 'finance/invoice_request_list.html'
    context_object_name = 'requests'
    ordering = ['-create_time']

    def get_queryset(self):
        queryset = super().get_queryset()
        tab = self.request.GET.get('tab', '0')
        uid = self.request.user.id
        
        tab_action_map = {
            '1': ('applicant_id', uid),
            '2': ('status', 'pending'),
            '3': ('reviewer_id', uid),
        }
        
        if tab in tab_action_map:
            field, value = tab_action_map[tab]
            queryset = queryset.filter(**{field: value})
        
        return queryset


class InvoiceRequestDetailView(LoginRequiredMixin, View):
    """开票申请详情视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, request_id):
        try:
            invoice_request = InvoiceRequest.objects.select_related('order', 'applicant').get(id=request_id)
            
            data = {
                'id': invoice_request.id,
                'order_number': invoice_request.order.order_number,
                'customer_name': invoice_request.order.customer.name,
                'amount': float(invoice_request.amount),
                'invoice_type': invoice_request.get_invoice_type_display() if hasattr(invoice_request, 'get_invoice_type_display') else '普通发票',
                'invoice_title': invoice_request.invoice_title,
                'tax_number': invoice_request.tax_number,
                'reason': invoice_request.reason,
                'status': invoice_request.get_status_display(),
                'applicant': invoice_request.applicant.username,
                'create_time': invoice_request.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'review_comment': invoice_request.review_comment,
            }
            
            return JsonResponse({'code': 0, 'data': data})
        except InvoiceRequest.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '开票申请不存在'})
        except Exception as e:
            logger.error(f'获取开票申请详情失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': f'获取详情失败: {str(e)}'})


class InvoiceRequestApprovalView(LoginRequiredMixin, View):
    """开票申请审批视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    @method_decorator(csrf_exempt)
    def post(self, request):
        try:
            data = json.loads(request.body)
            request_id = data.get('request_id')
            action = data.get('action')
            comment = data.get('comment', '')
            
            if not request_id or not action:
                return build_error_response('参数不完整')
            
            invoice_request = InvoiceRequest.objects.get(id=request_id)
            
            if invoice_request.status != 'pending':
                return JsonResponse({'code': 1, 'msg': '该申请已被处理'})
            
            invoice_request.status = action
            invoice_request.reviewer = request.user
            invoice_request.review_time = timezone.now()
            invoice_request.review_comment = comment
            invoice_request.save()
            
            order = invoice_request.order
            if action == 'approved':
                order.invoice_request_status = 'approved'
                self._create_invoice_from_request(invoice_request)
            else:
                order.invoice_request_status = 'rejected'
            order.save()
            
            logger.info(f"用户 {request.user.id} 审批了开票申请 {request_id}，结果: {action}")
            
            return JsonResponse({'code': 0, 'msg': '审批操作成功'})
            
        except json.JSONDecodeError:
            return build_error_response('无效的JSON数据')
        except InvoiceRequest.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '开票申请不存在'})
        except Exception as e:
            logger.error(f'审批失败: {str(e)}', exc_info=True)
            return JsonResponse({'code': 1, 'msg': f'审批失败: {str(e)}'})
    
    def _create_invoice_from_request(self, invoice_request):
        """根据开票申请创建发票记录"""
        try:
            current_time = int(time.time())
            
            invoice = Invoice.objects.create(
                code=f'INV{current_time}',
                customer_id=invoice_request.order.customer.id,
                contract_id=invoice_request.order.contract.id if invoice_request.order.contract else 0,
                amount=invoice_request.amount,
                did=invoice_request.department_id,
                admin_id=invoice_request.applicant.id,
                open_status=1,
                open_admin_id=self.request.user.id,
                open_time=current_time,
                invoice_type=invoice_request.invoice_type,
                invoice_title=invoice_request.invoice_title,
                invoice_tax=invoice_request.tax_number,
                enter_amount=0,
                enter_status=0,
                create_time=current_time
            )
            
            invoice_request.invoice = invoice
            invoice_request.status = 'invoiced'
            invoice_request.invoice_time = timezone.now()
            invoice_request.save()
            
            invoice_request.order.finance_status = 'invoiced'
            invoice_request.order.save()
            
            logger.info(f"成功为开票申请 {invoice_request.id} 创建发票 {invoice.id}")
            
        except Exception as e:
            logger.error(f'创建发票失败: {str(e)}', exc_info=True)
            raise


class OrderFinanceRecordListView(LoginRequiredMixin, ListView):
    """订单财务记录列表视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = OrderFinanceRecord
    template_name = 'finance/order_finance_list.html'
    context_object_name = 'records'
    ordering = ['-create_time']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('order', 'order__customer', 'order__create_user')
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(payment_status=status)
        
        return queryset


class FinanceStatisticsView(LoginRequiredMixin, View):
    """财务统计视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        try:
            from django.db.models import Sum, Count
            
            stats = {
                'total_orders': OrderFinanceRecord.objects.count(),
                'pending_payment': OrderFinanceRecord.objects.filter(payment_status='pending').count(),
                'total_amount': OrderFinanceRecord.objects.aggregate(total=Sum('total_amount'))['total'] or 0,
                'paid_amount': OrderFinanceRecord.objects.aggregate(paid=Sum('paid_amount'))['paid'] or 0,
                'pending_invoices': InvoiceRequest.objects.filter(status='pending').count(),
                'approved_invoices': InvoiceRequest.objects.filter(status='approved').count(),
            }
            
            return JsonResponse({'code': 0, 'data': stats})
        except Exception as e:
            logger.error(f'获取统计数据失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取统计数据失败: {str(e)}')


class FinanceIndexView(LoginRequiredMixin, View):
    """财务模块主页视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return render(request, 'finance/index.html')


class InvoiceDownloadView(LoginRequiredMixin, View):
    """发票下载视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, invoice_id):
        try:
            from django.http import HttpResponse, Http404
            import os
            
            invoice = Invoice.objects.get(id=invoice_id)
            
            file_path = f'media/invoices/invoice_{invoice.code}.pdf'
            
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    response = HttpResponse(f.read(), content_type='application/pdf')
                    response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.code}.pdf"'
                    return response
            else:
                return self._generate_invoice_content(invoice)
                
        except Invoice.DoesNotExist:
            raise Http404("发票不存在")
        except Exception as e:
            logger.error(f'下载发票失败: {str(e)}', exc_info=True)
            return build_error_response(f'下载失败: {str(e)}')
    
    def _generate_invoice_content(self, invoice):
        """生成发票内容（简单实现）"""
        from django.http import HttpResponse
        
        content = f"""发票信息
========
发票号码: {invoice.code}
开票金额: ¥{invoice.amount}
开票抬头: {invoice.invoice_title}
纳税人识别号: {invoice.invoice_tax}
开票日期: {timestamp_to_date(invoice.open_time)}
开票状态: {'已开票' if invoice.open_status == 1 else '未开票'}
        """
        
        response = HttpResponse(content, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.code}.txt"'
        return response


def expense_view(request, id):
    """报销详情视图"""
    expense = get_object_or_404(Expense, id=id)
    return render(request, 'finance/expense_detail.html', {'expense': expense})


def expense_delete(request):
    """删除报销记录"""
    if request.method != 'POST':
        return JsonResponse({'code': 1, 'msg': '请求方法错误'})
    
    try:
        data = json.loads(request.body)
        expense_id = data.get('id')
        if not expense_id:
            return build_error_response('缺少ID参数')
        
        expense = get_object_or_404(Expense, id=expense_id)
        expense.delete()
        
        logger.info(f"用户 {request.user.id} 删除了报销记录 {expense_id}")
        
        return JsonResponse({'code': 0, 'msg': '删除成功'})
    except json.JSONDecodeError:
        return build_error_response('无效的JSON数据')
    except Exception as e:
        logger.error(f'删除报销记录失败: {str(e)}', exc_info=True)
        return build_error_response(f'删除失败: {str(e)}')


def invoice_view(request, id):
    """发票详情视图"""
    invoice = get_object_or_404(Invoice, id=id)
    return render(request, 'finance/invoice_detail.html', {'invoice': invoice})


def invoice_delete(request):
    """删除发票记录"""
    if request.method != 'POST':
        return JsonResponse({'code': 1, 'msg': '请求方法错误'})
    
    try:
        data = json.loads(request.body)
        invoice_id = data.get('id')
        if not invoice_id:
            return build_error_response('缺少ID参数')
        
        invoice = get_object_or_404(Invoice, id=invoice_id)
        invoice.delete()
        
        logger.info(f"用户 {request.user.id} 删除了发票记录 {invoice_id}")
        
        return JsonResponse({'code': 0, 'msg': '删除成功'})
    except json.JSONDecodeError:
        return build_error_response('无效的JSON数据')
    except Exception as e:
        logger.error(f'删除发票记录失败: {str(e)}', exc_info=True)
        return build_error_response(f'删除失败: {str(e)}')


class ReceiveInvoiceListView(LoginRequiredMixin, View):
    """收票管理页面视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/receiveinvoice_list.html')

    def get_datalist(self, request):
        """返回收票数据列表的JSON格式"""
        try:
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
            
            queryset = Invoice.objects.filter(open_status=1).order_by('-create_time')
            
            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)
            
            data = []
            for invoice in page_obj:
                data.append({
                    'id': invoice.id,
                    'code': invoice.code,
                    'amount': float(invoice.amount),
                    'customer_id': invoice.customer_id,
                    'invoice_type': get_status_display('invoice_type', invoice.invoice_type),
                    'invoice_title': invoice.invoice_title,
                    'open_status': get_status_display('open_status', invoice.open_status),
                    'enter_status': get_status_display('enter_status', invoice.enter_status),
                    'create_time': timestamp_to_date(invoice.create_time) if invoice.create_time else '',
                    'open_time': timestamp_to_date(invoice.open_time) if invoice.open_time else '',
                })
            
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取收票数据失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class ReceiveInvoiceCreateView(LoginRequiredMixin, CreateView):
    """收票创建视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Invoice
    fields = ['code', 'customer_id', 'amount', 'invoice_title']
    template_name = 'finance/receiveinvoice_form.html'
    success_url = reverse_lazy('finance:receiveinvoice_list')


class PaymentReceiveListView(LoginRequiredMixin, View):
    """收款管理页面视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        customer_id = request.GET.get('customer_id')
        context = {'customer_id': customer_id} if customer_id else {}
        return render(request, 'finance/paymentreceive_list.html', context)

    def get_datalist(self, request):
        """返回收款数据列表的JSON格式"""
        try:
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)
            customer_id = request.GET.get('customer_id')
            
            queryset = Income.objects.all().order_by('-create_time')
            
            if customer_id:
                queryset = queryset.filter(invoice__customer_id=customer_id)
            
            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)
            
            data = []
            for income in page_obj:
                data.append({
                    'id': income.id,
                    'invoice_id': income.invoice.id if income.invoice else 0,
                    'invoice_code': income.invoice.code if income.invoice else '',
                    'customer_name': income.invoice.customer.name if income.invoice and income.invoice.customer else '',
                    'amount': float(income.amount),
                    'income_date': income.income_date.strftime('%Y-%m-%d') if income.income_date else '',
                    'create_time': timestamp_to_date(income.create_time) if income.create_time else '',
                    'remark': income.remark
                })
            
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取收款数据失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class ReimbursementStatisticsView(LoginRequiredMixin, View):
    """报销统计视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return render(request, 'finance/statistics/reimbursement.html')


class InvoiceStatisticsView(LoginRequiredMixin, View):
    """发票统计视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return render(request, 'finance/statistics/invoice.html')


class ReceiveInvoiceStatisticsView(LoginRequiredMixin, View):
    """收票统计视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return render(request, 'finance/statistics/receiveinvoice.html')


class PaymentReceiveStatisticsView(LoginRequiredMixin, View):
    """收款统计视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return render(request, 'finance/statistics/paymentreceive.html')


class PaymentStatisticsView(LoginRequiredMixin, View):
    """付款统计视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return render(request, 'finance/statistics/payment.html')


class ReceiveInvoiceUpdateView(LoginRequiredMixin, UpdateView):
    """收票更新视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Invoice
    fields = ['code', 'customer_id', 'amount', 'invoice_title']
    template_name = 'finance/receiveinvoice_form.html'
    success_url = reverse_lazy('finance:receiveinvoice_list')


class IncomeUpdateView(LoginRequiredMixin, UpdateView):
    """收入更新视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Income
    fields = ['invoice', 'amount', 'income_date', 'file_ids', 'remark']
    template_name = 'finance/income_form.html'
    success_url = reverse_lazy('finance:paymentreceive_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invoices'] = Invoice.objects.all()
        return context


class PaymentUpdateView(LoginRequiredMixin, UpdateView):
    """付款更新视图"""
    login_url = '/user/login/'
    redirect_field_name = 'next'
    model = Payment
    fields = ['expense', 'amount', 'payment_date', 'file_ids', 'remark']
    template_name = 'finance/payment_form.html'
    success_url = reverse_lazy('finance:payment_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['expenses'] = Expense.objects.all()
        return context


def receiveinvoice_view(request, id):
    """收票详情视图"""
    invoice = get_object_or_404(Invoice, id=id)
    return render(request, 'finance/receiveinvoice_detail.html', {'invoice': invoice})


def receiveinvoice_delete(request):
    """删除收票记录"""
    if request.method != 'POST':
        return JsonResponse({'code': 1, 'msg': '请求方法错误'})
    
    try:
        data = json.loads(request.body)
        invoice_id = data.get('id')
        if not invoice_id:
            return build_error_response('缺少ID参数')
        
        invoice = get_object_or_404(Invoice, id=invoice_id)
        invoice.delete()
        
        logger.info(f"用户 {request.user.id} 删除了收票记录 {invoice_id}")
        
        return JsonResponse({'code': 0, 'msg': '删除成功'})
    except json.JSONDecodeError:
        return build_error_response('无效的JSON数据')
    except Exception as e:
        logger.error(f'删除收票记录失败: {str(e)}', exc_info=True)
        return build_error_response(f'删除失败: {str(e)}')


def income_view(request, id):
    """收入详情视图"""
    income = get_object_or_404(Income, id=id)
    return render(request, 'finance/income_detail.html', {'income': income})


def income_delete(request):
    """删除收入记录"""
    if request.method != 'POST':
        return JsonResponse({'code': 1, 'msg': '请求方法错误'})
    
    try:
        data = json.loads(request.body)
        income_id = data.get('id')
        if not income_id:
            return build_error_response('缺少ID参数')
        
        income = get_object_or_404(Income, id=income_id)
        income.delete()
        
        logger.info(f"用户 {request.user.id} 删除了收入记录 {income_id}")
        
        return JsonResponse({'code': 0, 'msg': '删除成功'})
    except json.JSONDecodeError:
        return build_error_response('无效的JSON数据')
    except Exception as e:
        logger.error(f'删除收入记录失败: {str(e)}', exc_info=True)
        return build_error_response(f'删除失败: {str(e)}')


def payment_view(request, id):
    """付款详情视图"""
    payment = get_object_or_404(Payment, id=id)
    return render(request, 'finance/payment_detail.html', {'payment': payment})


def payment_delete(request):
    """删除付款记录"""
    if request.method != 'POST':
        return JsonResponse({'code': 1, 'msg': '请求方法错误'})
    
    try:
        data = json.loads(request.body)
        payment_id = data.get('id')
        if not payment_id:
            return build_error_response('缺少ID参数')
        
        payment = get_object_or_404(Payment, id=payment_id)
        payment.delete()
        
        logger.info(f"用户 {request.user.id} 删除了付款记录 {payment_id}")
        
        return JsonResponse({'code': 0, 'msg': '删除成功'})
    except json.JSONDecodeError:
        return build_error_response('无效的JSON数据')
    except Exception as e:
        logger.error(f'删除付款记录失败: {str(e)}', exc_info=True)
        return build_error_response(f'删除失败: {str(e)}')


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q

from .models import ReimbursementType, ExpenseType
from .forms import ReimbursementTypeForm, ExpenseTypeForm
from apps.common.views_utils import generic_list_view, generic_form_view


@login_required
def reimbursement_type_list(request):
    return generic_list_view(
        request,
        ReimbursementType,
        'finance/reimbursement_type_list.html',
        search_fields=['name', 'code']
    )


@login_required
def reimbursement_type_form(request, pk=None):
    return generic_form_view(
        request,
        ReimbursementType,
        ReimbursementTypeForm,
        'finance/reimbursement_type_form.html',
        'finance:reimbursement_type_list',
        pk
    )


@login_required
def expense_type_list(request):
    return generic_list_view(
        request,
        ExpenseType,
        'finance/expense_type_list.html',
        search_fields=['name', 'code']
    )


@login_required
def expense_type_form(request, pk=None):
    return generic_form_view(
        request,
        ExpenseType,
        ExpenseTypeForm,
        'finance/expense_type_form.html',
        'finance:expense_type_list',
        pk
    )
