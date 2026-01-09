"""
财务管理模块视图
只使用有数据库表的模型
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.views import View
from django.http import JsonResponse, HttpResponseBadRequest
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q, F
from django.db import transaction
from decimal import Decimal
import json
import logging
import time

from .models import (
    Expense, Invoice, Income, Payment,
    InvoiceRequest, OrderFinanceRecord,
    FinanceStatus, FinanceStatusMapping
)
from apps.common.utils import (
    timestamp_to_date, get_status_display, safe_int,
    build_error_response, build_success_response,
    StatusCodeMapper
)
from apps.common.constants import ApiResponseCode, CommonConstant

logger = logging.getLogger(__name__)


class FinancePermissionMixin(PermissionRequiredMixin):
    """财务模块权限混合类"""
    permission_required = []

    def has_permission(self):
        if not self.permission_required:
            return True
        perms = self.permission_required if isinstance(self.permission_required, list) else [self.permission_required]
        return self.request.user.has_perms(perms)


class FinanceIndexView(LoginRequiredMixin, View):
    """财务模块首页"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request):
        return render(request, 'finance/index.html')


class ExpenseListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """报销列表"""
    login_url = '/user/login/'
    permission_required = 'finance.view_expense'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/expense_list.html')

    def get_datalist(self, request):
        try:
            tab = request.GET.get('tab', '0')
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = Expense.objects.all().order_by('-create_time')
            uid = request.user.id

            if tab == '1':
                queryset = queryset.filter(admin_id=uid)
            elif tab == '2':
                queryset = queryset.filter(
                    check_status=FinanceStatus.EXPENSE_CHECK_PENDING
                ).filter(
                    Q(check_uids__contains=str(uid)) | Q(check_last_uid=str(uid))
                )

            search_code = request.GET.get('code')
            if search_code:
                queryset = queryset.filter(code__icontains=search_code)

            diff_time = request.GET.get('diff_time')
            if diff_time and '~' in diff_time:
                start, end = diff_time.split('~')
                start_ts = int(time.mktime(time.strptime(start.strip(), '%Y-%m-%d')))
                end_ts = int(time.mktime(time.strptime(end.strip(), '%Y-%m-%d'))) + 86400
                queryset = queryset.filter(expense_time__range=[start_ts, end_ts])

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = []
            for expense in page_obj:
                expense_date = timestamp_to_date(expense.expense_time) if expense.expense_time else None
                data.append({
                    'id': expense.id,
                    'code': expense.code,
                    'cost': float(expense.cost),
                    'check_status': expense.check_status,
                    'check_status_display': expense.get_check_status_display(),
                    'pay_status': expense.pay_status,
                    'pay_status_display': expense.get_pay_status_display(),
                    'expense_time': expense.expense_time,
                    'expense_date': expense_date.strftime('%Y-%m-%d') if expense_date else '',
                    'admin_id': expense.admin_id,
                    'did': expense.did,
                    'project_id': expense.project_id,
                    'create_time': expense.create_time,
                })

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取报销列表失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class ReimbursementListView(LoginRequiredMixin, View):
    """报销管理（旧路由兼容）"""
    login_url = '/user/login/'

    def get(self, request):
        return render(request, 'finance/expense_list.html')


class ExpenseSubmitView(LoginRequiredMixin, FinancePermissionMixin, View):
    """提交报销审批"""
    login_url = '/user/login/'
    permission_required = 'finance.submit_expense'

    @method_decorator(csrf_exempt)
    def post(self, request):
        try:
            data = json.loads(request.body)
            expense_id = data.get('expense_id')

            if not expense_id:
                return build_error_response('缺少报销ID')

            expense = get_object_or_404(Expense, id=expense_id)

            if expense.check_status not in [0, 3, 4]:
                return build_error_response('当前状态不允许提交')

            expense.check_status = FinanceStatus.EXPENSE_CHECK_PROCESSING
            expense.save()

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '提交成功'
            })
        except json.JSONDecodeError:
            return build_error_response('无效的JSON数据')
        except Exception as e:
            logger.error(f'提交报销失败: {str(e)}', exc_info=True)
            return build_error_response(f'提交失败: {str(e)}')


class ExpenseApproveView(LoginRequiredMixin, FinancePermissionMixin, View):
    """审批报销"""
    login_url = '/user/login/'
    permission_required = 'finance.approve_expense'

    @method_decorator(csrf_exempt)
    def post(self, request):
        try:
            data = json.loads(request.body)
            expense_id = data.get('expense_id')
            action = data.get('action')
            notes = data.get('notes', '')

            if not expense_id or not action:
                return build_error_response('参数不完整')

            expense = get_object_or_404(Expense, id=expense_id)

            if expense.check_status != FinanceStatus.EXPENSE_CHECK_PROCESSING:
                return build_error_response('当前状态不允许审批')

            if action == 'approved':
                expense.check_status = FinanceStatus.EXPENSE_CHECK_APPROVED
                expense.check_time = int(time.time())
            else:
                expense.check_status = FinanceStatus.EXPENSE_CHECK_REJECTED

            expense.check_history_uids += f',{request.user.id}'
            expense.save()

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '审批操作成功'
            })
        except json.JSONDecodeError:
            return build_error_response('无效的JSON数据')
        except Exception as e:
            logger.error(f'审批报销失败: {str(e)}', exc_info=True)
            return build_error_response(f'审批失败: {str(e)}')


class InvoiceListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """发票列表"""
    login_url = '/user/login/'
    permission_required = 'finance.view_invoice'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/invoice_list.html')

    def get_datalist(self, request):
        try:
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = Invoice.objects.all().order_by('-create_time')

            search_code = request.GET.get('code')
            if search_code:
                queryset = queryset.filter(code__icontains=search_code)

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = []
            for invoice in page_obj:
                data.append({
                    'id': invoice.id,
                    'code': invoice.code,
                    'amount': float(invoice.amount),
                    'invoice_type': invoice.invoice_type,
                    'invoice_type_display': invoice.get_invoice_type_display(),
                    'open_status': invoice.open_status,
                    'open_status_display': invoice.get_open_status_display(),
                    'enter_amount': float(invoice.enter_amount),
                    'enter_status': invoice.enter_status,
                    'enter_status_display': invoice.get_enter_status_display(),
                    'invoice_title': invoice.invoice_title,
                    'customer_id': invoice.customer_id,
                    'create_time': invoice.create_time,
                })

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取发票列表失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class ReceiveInvoiceListView(LoginRequiredMixin, View):
    """收票列表"""
    login_url = '/user/login/'

    def get(self, request):
        return render(request, 'finance/receiveinvoice_list.html')


class InvoiceCreateView(LoginRequiredMixin, FinancePermissionMixin, CreateView):
    """创建发票"""
    login_url = '/user/login/'
    permission_required = 'finance.add_invoice'
    template_name = 'finance/invoice_form.html'
    success_url = reverse_lazy('finance:invoice_list')


class InvoiceUpdateView(LoginRequiredMixin, FinancePermissionMixin, UpdateView):
    """更新发票"""
    login_url = '/user/login/'
    permission_required = 'finance.change_invoice'
    model = Invoice
    template_name = 'finance/invoice_form.html'
    success_url = reverse_lazy('finance:invoice_list')


class IncomeListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """回款列表"""
    login_url = '/user/login/'
    permission_required = 'finance.view_income'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/income_list.html')

    def get_datalist(self, request):
        try:
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = Income.objects.all().order_by('-income_date')

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = []
            for income in page_obj:
                data.append({
                    'id': income.id,
                    'invoice_id': income.invoice_id,
                    'amount': float(income.amount),
                    'income_date': income.income_date.strftime('%Y-%m-%d %H:%M:%S') if income.income_date else '',
                    'create_time': income.create_time,
                })

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取回款列表失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class IncomeCreateView(LoginRequiredMixin, FinancePermissionMixin, CreateView):
    """创建回款"""
    login_url = '/user/login/'
    permission_required = 'finance.add_income'
    template_name = 'finance/income_form.html'
    success_url = reverse_lazy('finance:income_list')


class PaymentListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """付款列表"""
    login_url = '/user/login/'
    permission_required = 'finance.view_payment'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/payment_list.html')

    def get_datalist(self, request):
        try:
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = Payment.objects.all().order_by('-payment_date')

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = []
            for payment in page_obj:
                data.append({
                    'id': payment.id,
                    'expense_id': payment.expense_id,
                    'amount': float(payment.amount),
                    'payment_date': payment.payment_date.strftime('%Y-%m-%d %H:%M:%S') if payment.payment_date else '',
                    'create_time': payment.create_time,
                })

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取付款列表失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class PaymentReceiveListView(LoginRequiredMixin, View):
    """收付款列表"""
    login_url = '/user/login/'

    def get(self, request):
        return render(request, 'finance/paymentreceive_list.html')


class InvoiceRequestListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """开票申请列表"""
    login_url = '/user/login/'
    permission_required = 'finance.view_invoicerequest'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/invoice_request_list.html')

    def get_datalist(self, request):
        try:
            tab = request.GET.get('tab', '0')
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = InvoiceRequest.objects.all().order_by('-create_time')
            uid = request.user.id

            if tab == '1':
                queryset = queryset.filter(applicant_id=uid)
            elif tab == '2':
                queryset = queryset.filter(status='pending')

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = []
            for req in page_obj:
                data.append({
                    'id': req.id,
                    'order_id': req.order_id,
                    'amount': float(req.amount),
                    'invoice_type': req.invoice_type,
                    'status': req.status,
                    'status_display': req.get_status_display(),
                    'applicant_id': req.applicant_id,
                    'create_time': req.create_time,
                })

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取开票申请列表失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class OrderFinanceRecordListView(LoginRequiredMixin, FinancePermissionMixin, View):
    """订单财务记录列表"""
    login_url = '/user/login/'
    permission_required = 'finance.view_orderfinancerecord'

    def get(self, request):
        if 'datalist' in request.path:
            return self.get_datalist(request)
        return render(request, 'finance/order_finance_list.html')

    def get_datalist(self, request):
        try:
            status = request.GET.get('status')
            page = safe_int(request.GET.get('page'), 1)
            limit = safe_int(request.GET.get('limit'), CommonConstant.DEFAULT_PAGE_SIZE)

            queryset = OrderFinanceRecord.objects.all().order_by('-create_time')

            if status:
                queryset = queryset.filter(payment_status=status)

            paginator = Paginator(queryset, limit)
            page_obj = paginator.get_page(page)

            data = []
            for record in page_obj:
                data.append({
                    'id': record.id,
                    'order_id': record.order_id,
                    'total_amount': float(record.total_amount),
                    'paid_amount': float(record.paid_amount),
                    'unpaid_amount': float(record.unpaid_amount),
                    'payment_status': record.payment_status,
                    'payment_status_display': record.get_payment_status_display(),
                    'due_date': record.due_date.strftime('%Y-%m-%d') if record.due_date else '',
                })

            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'msg': '',
                'count': paginator.count,
                'data': data
            })
        except Exception as e:
            logger.error(f'获取订单财务记录列表失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取数据失败: {str(e)}')


class FinanceStatisticsView(LoginRequiredMixin, FinancePermissionMixin, View):
    """财务统计"""
    login_url = '/user/login/'
    permission_required = 'finance.view_statistics'

    def get(self, request):
        try:
            stats = {
                'expense_stats': {
                    'total_count': Expense.objects.count(),
                    'pending_count': Expense.objects.filter(check_status=FinanceStatus.EXPENSE_CHECK_PENDING).count(),
                    'approved_count': Expense.objects.filter(check_status=FinanceStatus.EXPENSE_CHECK_APPROVED).count(),
                    'total_amount': float(Expense.objects.aggregate(total=Sum('cost'))['total'] or 0),
                },
                'invoice_stats': {
                    'total_count': Invoice.objects.count(),
                    'total_amount': float(Invoice.objects.aggregate(total=Sum('amount'))['total'] or 0),
                    'enter_amount': float(Invoice.objects.aggregate(total=Sum('enter_amount'))['total'] or 0),
                },
                'payment_stats': {
                    'total_count': Payment.objects.count(),
                    'total_amount': float(Payment.objects.aggregate(total=Sum('amount'))['total'] or 0),
                },
                'income_stats': {
                    'total_count': Income.objects.count(),
                    'total_amount': float(Income.objects.aggregate(total=Sum('amount'))['total'] or 0),
                },
            }
            return JsonResponse({
                'code': ApiResponseCode.CODE_SUCCESS,
                'data': stats
            })
        except Exception as e:
            logger.error(f'获取统计数据失败: {str(e)}', exc_info=True)
            return build_error_response(f'获取统计数据失败: {str(e)}')


class ReimbursementStatisticsView(LoginRequiredMixin, View):
    """报销统计"""
    login_url = '/user/login/'

    def get(self, request):
        return render(request, 'finance/statistics/reimbursement.html')


class InvoiceStatisticsView(LoginRequiredMixin, View):
    """发票统计"""
    login_url = '/user/login/'

    def get(self, request):
        return render(request, 'finance/statistics/invoice.html')


class ReceiveInvoiceStatisticsView(LoginRequiredMixin, View):
    """收票统计"""
    login_url = '/user/login/'

    def get(self, request):
        return render(request, 'finance/statistics/receiveinvoice.html')


class PaymentReceiveStatisticsView(LoginRequiredMixin, View):
    """收付款统计"""
    login_url = '/user/login/'

    def get(self, request):
        return render(request, 'finance/statistics/paymentreceive.html')


class PaymentStatisticsView(LoginRequiredMixin, View):
    """付款统计"""
    login_url = '/user/login/'

    def get(self, request):
        return render(request, 'finance/statistics/payment.html')


class BatchApprovalView(LoginRequiredMixin, FinancePermissionMixin, View):
    """批量审批"""
    login_url = '/user/login/'
    permission_required = 'finance.approve_expense'

    @method_decorator(csrf_exempt)
    def post(self, request):
        try:
            data = json.loads(request.body)
            expense_ids = data.get('expense_ids', [])
            action = data.get('action')

            if not expense_ids or not action:
                return build_error_response('参数不完整')

            expenses = Expense.objects.filter(
                id__in=expense_ids,
                check_status=FinanceStatus.EXPENSE_CHECK_PROCESSING
            )
            results = []

            for expense in expenses:
                try:
                    if action == 'approve':
                        expense.check_status = FinanceStatus.EXPENSE_CHECK_APPROVED
                        expense.check_time = int(time.time())
                    else:
                        expense.check_status = FinanceStatus.EXPENSE_CHECK_REJECTED

                    expense.check_history_uids += f',{request.user.id}'
                    expense.save()

                    results.append({'id': expense.id, 'success': True})
                except Exception as e:
                    results.append({'id': expense.id, 'success': False, 'error': str(e)})

            return JsonResponse({
                'code': 0 if all(r['success'] for r in results) else 1,
                'msg': f'成功审批 {sum(1 for r in results if r["success"])} 条记录',
                'data': results
            })
        except json.JSONDecodeError:
            return build_error_response('无效的JSON数据')
        except Exception as e:
            logger.error(f'批量审批失败: {str(e)}', exc_info=True)
            return build_error_response(f'批量审批失败: {str(e)}')


def expense_detail(request, id):
    """报销详情"""
    expense = get_object_or_404(Expense, id=id)
    return render(request, 'finance/expense_detail.html', {'expense': expense})


def invoice_detail(request, id):
    """发票详情"""
    invoice = get_object_or_404(Invoice, id=id)
    return render(request, 'finance/invoice_detail.html', {'invoice': invoice})


@method_decorator(csrf_exempt, name='dispatch')
class ExpenseDeleteView(LoginRequiredMixin, View):
    """删除报销"""
    def post(self, request):
        try:
            data = json.loads(request.body)
            obj_id = data.get('id')
            if not obj_id:
                return build_error_response('缺少ID参数')

            obj = get_object_or_404(Expense, id=obj_id)
            obj.delete()

            return JsonResponse({'code': 0, 'msg': '删除成功'})
        except json.JSONDecodeError:
            return build_error_response('无效的JSON数据')
        except Exception as e:
            logger.error(f'删除报销失败: {str(e)}', exc_info=True)
            return build_error_response(f'删除失败: {str(e)}')


@method_decorator(csrf_exempt, name='dispatch')
class InvoiceDeleteView(LoginRequiredMixin, View):
    """删除发票"""
    def post(self, request):
        try:
            data = json.loads(request.body)
            obj_id = data.get('id')
            if not obj_id:
                return build_error_response('缺少ID参数')

            obj = get_object_or_404(Invoice, id=obj_id)
            obj.delete()

            return JsonResponse({'code': 0, 'msg': '删除成功'})
        except json.JSONDecodeError:
            return build_error_response('无效的JSON数据')
        except Exception as e:
            logger.error(f'删除发票失败: {str(e)}', exc_info=True)
            return build_error_response(f'删除失败: {str(e)}')


@method_decorator(csrf_exempt, name='dispatch')
class IncomeDeleteView(LoginRequiredMixin, View):
    """删除回款"""
    def post(self, request):
        try:
            data = json.loads(request.body)
            obj_id = data.get('id')
            if not obj_id:
                return build_error_response('缺少ID参数')

            obj = get_object_or_404(Income, id=obj_id)
            obj.delete()

            return JsonResponse({'code': 0, 'msg': '删除成功'})
        except json.JSONDecodeError:
            return build_error_response('无效的JSON数据')
        except Exception as e:
            logger.error(f'删除回款失败: {str(e)}', exc_info=True)
            return build_error_response(f'删除失败: {str(e)}')


@method_decorator(csrf_exempt, name='dispatch')
class PaymentDeleteView(LoginRequiredMixin, View):
    """删除付款"""
    def post(self, request):
        try:
            data = json.loads(request.body)
            obj_id = data.get('id')
            if not obj_id:
                return build_error_response('缺少ID参数')

            obj = get_object_or_404(Payment, id=obj_id)
            obj.delete()

            return JsonResponse({'code': 0, 'msg': '删除成功'})
        except json.JSONDecodeError:
            return build_error_response('无效的JSON数据')
        except Exception as e:
            logger.error(f'删除付款失败: {str(e)}', exc_info=True)
            return build_error_response(f'删除失败: {str(e)}')
