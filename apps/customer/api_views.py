"""
客户详情页面相关API视图
"""
import logging
from django.views.generic import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Customer, CustomerGrade, FollowRecord, CustomerContract
from apps.contract.models import Contract

logger = logging.getLogger(__name__)


class CustomerDetailAPIView(LoginRequiredMixin, View):
    """客户基本信息API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, customer_id):
        try:
            customer = Customer.objects.select_related('customer_source', 'principal').get(
                id=customer_id, delete_time=0
            )
            
            # 获取客户等级信息
            customer_grade = CustomerGrade.objects.filter(id=customer.grade_id).first()
            
            # 获取自定义字段值
            custom_fields = {}
            for field_value in customer.custom_fields.all():
                custom_fields[field_value.field.name] = field_value.value

            # 获取负责人显示名称，优先显示name，其次nickname，最后显示username
            manager_display = ''
            if customer.principal:
                if customer.principal.name:
                    manager_display = customer.principal.name
                elif customer.principal.nickname:
                    manager_display = customer.principal.nickname
                else:
                    manager_display = customer.principal.username

            # 根据客户当前状态计算显示状态
            if customer.discard_time > 0:
                status_display = '废弃'
            elif customer.belong_uid == 0:
                status_display = '公海客户'
            else:
                status_display = '个人客户'
                
            data = {
                'id': customer.id,
                'name': customer.name,
                'address': customer.address,
                'type': customer.customer_source.title if customer.customer_source else '',
                'industry': '',  # 需要根据实际业务添加行业字段
                'manager': customer.principal.name if customer.principal else '',
                'manager_name': manager_display,  # 添加manager_name字段
                'create_time': customer.create_time.strftime('%Y-%m-%d %H:%M:%S') if customer.create_time else '',
                'update_time': customer.update_time.strftime('%Y-%m-%d %H:%M:%S') if customer.update_time else '',
                'status': status_display,
                'level': customer_grade.title if customer_grade else '',
                'remark': customer.remark,
                'custom_fields': custom_fields
            }
            
            return JsonResponse(data, json_dumps_params={'ensure_ascii': False})
        except Customer.DoesNotExist:
            return JsonResponse({'error': '客户不存在'}, json_dumps_params={'ensure_ascii': False}, status=404)
        except Exception as e:
            logger.error(f'获取客户基本信息失败: {str(e)}')
            return JsonResponse({'error': '服务器错误'}, json_dumps_params={'ensure_ascii': False}, status=500)


class CustomerContactsAPIView(LoginRequiredMixin, View):
    """客户联系人信息API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, customer_id):
        try:
            customer = Customer.objects.get(id=customer_id, delete_time=0)
            contacts = customer.contacts.all()
            
            data = []
            for contact in contacts:
                data.append({
                    'id': contact.id,
                    'contact_person': contact.contact_person,
                    'phone': contact.phone,
                    'email': contact.email or '',
                    'position': contact.position or '',
                    'is_primary': contact.is_primary,
                })
            
            return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})
        except Customer.DoesNotExist:
            return JsonResponse({'error': '客户不存在'}, json_dumps_params={'ensure_ascii': False}, status=404)
        except Exception as e:
            logger.error(f'获取客户联系人信息失败: {str(e)}')
            return JsonResponse({'error': '服务器错误'}, json_dumps_params={'ensure_ascii': False}, status=500)


class CustomerFollowRecordsAPIView(LoginRequiredMixin, View):
    """客户跟进记录API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, customer_id):
        try:
            customer = Customer.objects.get(id=customer_id, delete_time=0)
            
            # 暂时返回空数据，因为FollowRecord模型可能还没有创建
            try:
                follow_records = customer.follow_records.filter(delete_time=0).select_related('follow_user')
                
                # 分页处理
                page = int(request.GET.get('page', 1))
                limit = int(request.GET.get('limit', 10))
                start = (page - 1) * limit
                end = start + limit
                
                total_count = follow_records.count()
                paginated_records = follow_records[start:end]
                
                data = []
                for record in paginated_records:
                    # 获取跟进人显示名称，优先显示name，其次nickname，最后显示username
                    follow_user_display = ''
                    if record.follow_user:
                        if record.follow_user.name:
                            follow_user_display = record.follow_user.name
                        elif record.follow_user.nickname:
                            follow_user_display = record.follow_user.nickname
                        else:
                            follow_user_display = record.follow_user.username
                    
                    # 添加调试日志
                    logger.info(f'跟进记录 {record.id}: follow_user={record.follow_user}, display_name={follow_user_display}')
                    
                    data.append({
                        'id': record.id,
                        'follow_type': record.get_follow_type_display(),
                        'content': record.content,
                        'follow_user': follow_user_display,
                        'follow_time': record.follow_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'next_follow_time': record.next_follow_time.strftime('%Y-%m-%d %H:%M:%S') if record.next_follow_time else '',
                    })
                
                return JsonResponse({
                    'code': 0,
                    'msg': '',
                    'count': total_count,
                    'data': data
                }, json_dumps_params={'ensure_ascii': False})
            except AttributeError:
                # 如果FollowRecord模型不存在，返回空数据
                return JsonResponse({
                        'code': 0,
                        'msg': '',
                        'count': 0,
                        'data': []
                    }, json_dumps_params={'ensure_ascii': False})
        except Customer.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '客户不存在', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=404)
        except Exception as e:
            logger.error(f'获取客户跟进记录失败: {str(e)}')
            return JsonResponse({'code': 500, 'msg': '服务器错误', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=500)


class CustomerOrdersAPIView(LoginRequiredMixin, View):
    """客户订单记录API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, customer_id):
        try:
            from .models import CustomerOrder
            
            customer = Customer.objects.get(id=customer_id, delete_time=0)
            orders = CustomerOrder.objects.filter(customer=customer, delete_time=0).select_related('contract', 'create_user')
            
            # 分页处理
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 10))
            start = (page - 1) * limit
            end = start + limit
            
            total_count = orders.count()
            paginated_orders = orders[start:end]
            
            data = []
            for order in paginated_orders:
                # 获取创建人显示名称
                create_user_display = ''
                if order.create_user:
                    if order.create_user.name:
                        create_user_display = order.create_user.name
                    elif order.create_user.nickname:
                        create_user_display = order.create_user.nickname
                    else:
                        create_user_display = order.create_user.username
                
                data.append({
                    'id': order.id,
                    'order_number': order.order_number,
                    'order_date': order.order_date.strftime('%Y-%m-%d'),
                    'amount': str(order.amount),
                    'status': order.get_status_display(),
                    'product_name': order.product_name,
                    'create_user': create_user_display,
                    'contract_name': order.contract.name if order.contract else '无关联合同',
                    'finance_status': order.get_finance_status_display(),
                    'invoice_request_status': order.get_invoice_request_status_display(),
                    'invoice_request_status_raw': order.invoice_request_status,  # 添加原始状态值
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            }, json_dumps_params={'ensure_ascii': False})
        except Customer.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '客户不存在', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=404)
        except Exception as e:
            logger.error(f'获取客户订单记录失败: {str(e)}')
            return JsonResponse({'code': 500, 'msg': '服务器错误', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=500)


class CustomerContractsAPIView(LoginRequiredMixin, View):
    """客户合同记录API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, customer_id):
        try:
            from .models import CustomerContract
            
            customer = Customer.objects.get(id=customer_id, delete_time=0)
            contracts = CustomerContract.objects.filter(customer=customer, delete_time=0).select_related('create_user')
            
            # 分页处理
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 10))
            start = (page - 1) * limit
            end = start + limit
            
            total_count = contracts.count()
            paginated_contracts = contracts[start:end]
            
            data = []
            for contract in paginated_contracts:
                data.append({
                    'id': contract.id,
                    'contract_number': contract.contract_number,
                    'name': contract.name,
                    'sign_date': contract.sign_date.strftime('%Y-%m-%d'),
                    'amount': str(contract.amount),
                    'status': contract.get_status_display(),
                    'end_date': contract.end_date.strftime('%Y-%m-%d') if contract.end_date else '',
                    'contract_type': contract.get_contract_type_display() if contract.contract_type else '',
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            }, json_dumps_params={'ensure_ascii': False})
        except Customer.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '客户不存在', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=404)
        except Exception as e:
            logger.error(f'获取客户合同记录失败: {str(e)}')
            return JsonResponse({'code': 500, 'msg': '服务器错误', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=500)


class CustomerInvoicesAPIView(LoginRequiredMixin, View):
    """客户发票记录API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, customer_id):
        try:
            from apps.finance_new.models import Invoice
            
            customer = Customer.objects.get(id=customer_id, delete_time=0)
            invoices = Invoice.objects.filter(customer_id=customer.id, is_deleted=False)
            
            # 分页处理
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 10))
            start = (page - 1) * limit
            end = start + limit
            
            total_count = invoices.count()
            paginated_invoices = invoices[start:end]
            
            data = []
            for invoice in paginated_invoices:
                # 获取发票日期，优先使用issued_at，其次使用created_at
                invoice_date = None
                if hasattr(invoice, 'issued_at') and invoice.issued_at:
                    invoice_date = invoice.issued_at.strftime('%Y-%m-%d')
                elif hasattr(invoice, 'created_at') and invoice.created_at:
                    invoice_date = invoice.created_at.strftime('%Y-%m-%d')
                
                data.append({
                    'id': invoice.id,
                    'invoice_date': invoice_date or '',
                    'amount': str(invoice.amount),
                    'type': '专用发票' if hasattr(invoice, 'invoice_type') and invoice.invoice_type == 1 else '普通发票',
                    'status': '已开票' if hasattr(invoice, 'open_status') and invoice.open_status == 1 else '未开票',
                    'contract_number': invoice.contract_id if hasattr(invoice, 'contract_id') else '',
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            }, json_dumps_params={'ensure_ascii': False})
        except Customer.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '客户不存在', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=404)
        except Exception as e:
            logger.error(f'获取客户发票记录失败: {str(e)}')
            return JsonResponse({'code': 500, 'msg': '服务器错误', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=500)


class CustomerPaymentsAPIView(LoginRequiredMixin, View):
    """客户付款记录API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, customer_id):
        try:
            from apps.finance.models import Income
            
            customer = Customer.objects.get(id=customer_id, delete_time=0)
            # 通过发票关联获取付款记录
            payments = Income.objects.filter(invoice__customer_id=customer.id)
            
            # 分页处理
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 10))
            start = (page - 1) * limit
            end = start + limit
            
            total_count = payments.count()
            paginated_payments = payments[start:end]
            
            data = []
            for payment in paginated_payments:
                data.append({
                    'id': payment.id,
                    'payment_date': payment.income_date.strftime('%Y-%m-%d'),
                    'amount': str(payment.amount),
                    'payment_method': '银行转账',  # 根据实际情况调整
                    'invoice_number': payment.invoice.code,
                    'status': '已到账',
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            }, json_dumps_params={'ensure_ascii': False})
        except Customer.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '客户不存在', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=404)
        except Exception as e:
            logger.error(f'获取客户付款记录失败: {str(e)}')
            return JsonResponse({'code': 500, 'msg': '服务器错误', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=500)


class CustomerPendingPaymentsAPIView(LoginRequiredMixin, View):
    """客户待付款记录API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, customer_id):
        try:
            from apps.finance_new.models import Invoice
            
            customer = Customer.objects.get(id=customer_id, delete_time=0)
            # 获取未完全回款的发票
            pending_invoices = Invoice.objects.filter(
                customer_id=customer.id,
                is_deleted=False,
                enter_status__in=[0, 1]  # 未回款或部分回款
            )
            
            # 分页处理
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 10))
            start = (page - 1) * limit
            end = start + limit
            
            total_count = pending_invoices.count()
            paginated_invoices = pending_invoices[start:end]
            
            data = []
            for invoice in paginated_invoices:
                # 计算待付款金额，检查enter_amount字段是否存在
                pending_amount = invoice.amount
                if hasattr(invoice, 'enter_amount') and invoice.enter_amount:
                    pending_amount = invoice.amount - invoice.enter_amount
                
                data.append({
                    'id': invoice.id,
                    'due_date': '',  # 需要根据实际业务添加到期日期字段
                    'amount': str(pending_amount),
                    'related_type': '发票',
                    'related_number': invoice.code if hasattr(invoice, 'code') else '',
                    'status': '待付款' if hasattr(invoice, 'enter_status') and invoice.enter_status == 0 else '部分付款',
                })
            
            return JsonResponse({
                'code': 0,
                'msg': '',
                'count': total_count,
                'data': data
            }, json_dumps_params={'ensure_ascii': False})
        except Customer.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '客户不存在', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=404)
        except Exception as e:
            logger.error(f'获取客户待付款记录失败: {str(e)}')
            return JsonResponse({'code': 500, 'msg': '服务器错误', 'data': []}, json_dumps_params={'ensure_ascii': False}, status=500)


class CustomerFinanceStatsAPIView(LoginRequiredMixin, View):
    """客户财务统计API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def get(self, request, customer_id):
        try:
            from apps.finance_new.models import Invoice
            
            customer = Customer.objects.get(id=customer_id, delete_time=0)
            
            # 计算财务统计数据
            invoices = Invoice.objects.filter(customer_id=customer.id, is_deleted=False)
            
            total_amount = invoices.aggregate(total=Sum('amount'))['total'] or 0
            # 检查enter_amount字段是否存在
            if hasattr(Invoice.objects.first(), 'enter_amount'):
                paid_amount = invoices.aggregate(paid=Sum('enter_amount'))['paid'] or 0
            else:
                paid_amount = 0
            unpaid_amount = total_amount - paid_amount
            
            # 逾期金额计算（这里需要根据实际业务逻辑调整）
            overdue_amount = 0
            
            data = {
                'total_amount': float(total_amount),
                'paid_amount': float(paid_amount),
                'unpaid_amount': float(unpaid_amount),
                'overdue_amount': float(overdue_amount),
            }
            
            return JsonResponse(data, json_dumps_params={'ensure_ascii': False})
        except Customer.DoesNotExist:
            return JsonResponse({'error': '客户不存在'}, json_dumps_params={'ensure_ascii': False}, status=404)
        except Exception as e:
            logger.error(f'获取客户财务统计失败: {str(e)}')
            return JsonResponse({'error': '服务器错误'}, json_dumps_params={'ensure_ascii': False}, status=500)


class CustomerOrderAddAPIView(LoginRequiredMixin, View):
    """添加客户订单API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request):
        try:
            import json
            from .models import CustomerOrder, CustomerContract
            from apps.finance.models import OrderFinanceRecord
            
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            
            customer = Customer.objects.get(id=customer_id, delete_time=0)
            
            # 检查订单编号是否重复
            if CustomerOrder.objects.filter(order_number=data['order_number'], delete_time=0).exists():
                return JsonResponse({'code': 1, 'msg': '订单编号已存在'}, json_dumps_params={'ensure_ascii': False})
            
            # 获取关联合同（如果有）
            contract = None
            if data.get('contract_id'):
                try:
                    contract = CustomerContract.objects.get(id=data['contract_id'], delete_time=0)
                except CustomerContract.DoesNotExist:
                    return JsonResponse({'code': 1, 'msg': '关联合同不存在'}, json_dumps_params={'ensure_ascii': False})
            
            # 创建订单
            order = CustomerOrder.objects.create(
                customer=customer,
                contract=contract,
                order_number=data['order_number'],
                product_name=data['product_name'],
                amount=data['amount'],
                order_date=data['order_date'],
                status=data['status'],
                description=data.get('description', ''),
                create_user=request.user,
                finance_status='pending'
            )
            
            # 同步到财务记录
            OrderFinanceRecord.objects.create(
                order=order,
                total_amount=order.amount,
                payment_status='pending'
            )
            
            # 更新订单财务状态
            order.finance_status = 'synced'
            order.save()
            
            return JsonResponse({'code': 0, 'msg': '订单添加成功，已同步到财务记录'}, json_dumps_params={'ensure_ascii': False})
            
        except Customer.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '客户不存在'}, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'添加订单失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'添加失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})


class InvoiceRequestAPIView(LoginRequiredMixin, View):
    """开票申请API"""
    login_url = '/user/login/'
    redirect_field_name = 'next'

    def post(self, request):
        try:
            import json
            from .models import CustomerOrder
            from apps.finance.models import InvoiceRequest
            
            data = json.loads(request.body)
            order_id = data.get('order_id')
            
            order = CustomerOrder.objects.get(id=order_id, delete_time=0)
            
            # 检查是否已有待处理的开票申请
            existing_request = InvoiceRequest.objects.filter(
                order=order, 
                status__in=['pending', 'approved']
            ).first()
            
            if existing_request:
                return JsonResponse({'code': 1, 'msg': '该订单已有待处理的开票申请'}, json_dumps_params={'ensure_ascii': False})
            
            # 创建开票申请
            invoice_request = InvoiceRequest.objects.create(
                order=order,
                applicant=request.user,
                department_id=data.get('department_id', 0),
                amount=data['amount'],
                invoice_type=data.get('invoice_type', 2),
                invoice_title=data['invoice_title'],
                tax_number=data.get('tax_number', ''),
                reason=data['reason'],
                status='pending'
            )
            
            # 更新订单开票申请状态
            order.invoice_request_status = 'requested'
            order.invoice_request_time = timezone.now()
            order.invoice_request_user = request.user
            order.save()
            
            return JsonResponse({'code': 0, 'msg': '开票申请提交成功，等待财务部门审核'}, json_dumps_params={'ensure_ascii': False})
            
        except CustomerOrder.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '订单不存在'}, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            logger.error(f'开票申请失败: {str(e)}')
            return JsonResponse({'code': 1, 'msg': f'申请失败: {str(e)}'}, json_dumps_params={'ensure_ascii': False})


class CustomerContractAddAPIView(APIView):
    """
    客户合同添加API视图
    """
    
    def post(self, request):
        # 获取请求数据
        data = request.data
        
        # 验证必填字段
        required_fields = ['customer_id', 'contract_number', 'name', 'amount', 'sign_date', 'end_date']
        missing_fields = []
        
        for field in required_fields:
            if field not in data or not data[field]:
                missing_fields.append(field)
        
        if missing_fields:
            return Response({
                'code': 1,
                'msg': f'缺少必填字段: {", ".join(missing_fields)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 创建客户合同记录
            customer_contract = CustomerContract.objects.create(
                customer_id=data['customer_id'],
                contract_number=data['contract_number'],
                name=data['name'],
                amount=data['amount'],
                sign_date=data['sign_date'],
                end_date=data['end_date'],
                status=data.get('status', 'active'),
                contract_type=data.get('contract_type', 'sales'),
                description=data.get('description', ''),
                create_user=request.user
            )
            
            # 同步创建合同管理模块的Contract记录
            try:
                from apps.contract.models import Contract
                
                # 转换时间格式
                def date_to_timestamp(date_str):
                    if date_str:
                        from django.utils import timezone
                        import datetime
                        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                        return int(date_obj.timestamp())
                    return 0
                
                # 创建合同管理模块的Contract记录
                contract = Contract.objects.create(
                    code=data['contract_number'],
                    name=data['name'],
                    customer_id=data['customer_id'],
                    customer=data.get('customer_name', ''),
                    cost=data['amount'],
                    sign_time=date_to_timestamp(data['sign_date']),
                    start_time=date_to_timestamp(data['sign_date']),
                    end_time=date_to_timestamp(data['end_date']),
                    admin_id=request.user.id,
                    prepared_uid=request.user.id,
                    sign_uid=request.user.id,
                    keeper_uid=request.user.id,
                    delete_time=0,
                    check_status=0,
                    auto_generated=True  # 标记为自动生成
                )
                
                # 记录同步成功
                logger.info(f"客户合同同步创建成功: 客户合同ID={customer_contract.id}, 合同管理合同ID={contract.id}")
                
            except Exception as sync_error:
                # 记录同步错误但不影响客户合同创建
                logger.warning(f"合同管理模块同步创建失败: {str(sync_error)}")
            
            return Response({
                'code': 0,
                'msg': '客户合同创建成功',
                'data': {
                    'id': customer_contract.id,
                    'contract_number': customer_contract.contract_number
                }
            })
            
        except Exception as e:
            logger.error(f"客户合同创建失败: {str(e)}")
            return Response({
                'code': 1,
                'msg': f'客户合同创建失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerContractUpdateAPIView(APIView):
    """
    客户合同更新API视图
    """
    
    def post(self, request, contract_id):
        # 获取请求数据
        data = request.data
        
        try:
            # 获取客户合同记录
            customer_contract = CustomerContract.objects.get(id=contract_id)
            
            # 更新客户合同记录
            update_fields = ['name', 'amount', 'sign_date', 'end_date', 'status', 'contract_type', 'description']
            for field in update_fields:
                if field in data:
                    setattr(customer_contract, field, data[field])
            
            customer_contract.save()
            
            # 同步更新合同管理模块的Contract记录
            try:
                from apps.contract.models import Contract
                
                # 转换时间格式
                def date_to_timestamp(date_str):
                    if date_str:
                        from django.utils import timezone
                        import datetime
                        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                        return int(date_obj.timestamp())
                    return 0
                
                # 获取合同管理模块的Contract记录
                contract = Contract.objects.get(code=customer_contract.contract_number)
                
                # 更新合同管理模块的Contract记录
                contract.name = customer_contract.name
                contract.cost = customer_contract.amount
                contract.sign_time = date_to_timestamp(customer_contract.sign_date)
                contract.start_time = date_to_timestamp(customer_contract.sign_date)
                contract.end_time = date_to_timestamp(customer_contract.end_date)
                
                # 处理状态映射
                status_mapping = {
                    'active': 0,      # 进行中
                    'completed': 2,    # 已完成
                    'terminated': 3,    # 已终止
                    'cancelled': 4      # 已作废
                }
                contract.check_status = status_mapping.get(customer_contract.status, 0)
                
                contract.save()
                
                # 记录同步成功
                logger.info(f"客户合同同步更新成功: 客户合同ID={customer_contract.id}, 合同管理合同ID={contract.id}")
                
            except Contract.DoesNotExist:
                logger.warning(f"合同管理模块未找到对应的Contract记录: {customer_contract.contract_number}")
            except Exception as sync_error:
                # 记录同步错误但不影响客户合同更新
                logger.warning(f"合同管理模块同步更新失败: {str(sync_error)}")
            
            return Response({
                'code': 0,
                'msg': '客户合同更新成功',
                'data': {
                    'id': customer_contract.id,
                    'contract_number': customer_contract.contract_number
                }
            })
            
        except CustomerContract.DoesNotExist:
            return Response({
                'code': 1,
                'msg': '客户合同不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"客户合同更新失败: {str(e)}")
            return Response({
                'code': 1,
                'msg': f'客户合同更新失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerContractDeleteAPIView(APIView):
    """
    客户合同删除API视图
    """
    
    def post(self, request, contract_id):
        try:
            # 获取客户合同记录
            customer_contract = CustomerContract.objects.get(id=contract_id)
            contract_number = customer_contract.contract_number
            
            # 同步删除合同管理模块的Contract记录
            try:
                from apps.contract.models import Contract
                
                # 获取合同管理模块的Contract记录
                contract = Contract.objects.get(code=contract_number)
                
                # 逻辑删除Contract记录
                contract.delete_time = int(timezone.now().timestamp())
                contract.save()
                
                # 记录同步成功
                logger.info(f"客户合同同步删除成功: 客户合同ID={customer_contract.id}, 合同管理合同ID={contract.id}")
                
            except Contract.DoesNotExist:
                logger.warning(f"合同管理模块未找到对应的Contract记录: {contract_number}")
            except Exception as sync_error:
                # 记录同步错误但不影响客户合同删除
                logger.warning(f"合同管理模块同步删除失败: {str(sync_error)}")
            
            # 删除客户合同记录
            customer_contract.delete()
            
            return Response({
                'code': 0,
                'msg': '客户合同删除成功'
            })
            
        except CustomerContract.DoesNotExist:
            return Response({
                'code': 1,
                'msg': '客户合同不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"客户合同删除失败: {str(e)}")
            return Response({
                'code': 1,
                'msg': f'客户合同删除失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)