from django.urls import path
from . import views, ai_views
from . import views as finance_views

app_name = 'finance'

urlpatterns = [
    # 财务模块主页
    path('', views.FinanceIndexView.as_view(), name='finance_index'),
    # AI功能相关路由
    path('ai/expense-review/', ai_views.AIExpenseReviewView.as_view(), name='ai_expense_review'),
    path('ai/expense-anomaly/', ai_views.AIExpenseAnomalyDetectionView.as_view(), name='ai_expense_anomaly'),
    path('ai/expense-review/<int:expense_id>/', ai_views.ai_expense_review, name='ai_expense_review_detail'),
    path('ai/expense-anomaly/<int:expense_id>/', ai_views.ai_expense_anomaly_detection, name='ai_expense_anomaly_detail'),
    
    # 报销管理 (reimbursement)
    path('reimbursement/', views.ExpenseListView.as_view(), name='reimbursement_list'),
    path('reimbursement/datalist/', views.ExpenseListView.as_view(), name='expense_datalist'),
    path('reimbursement/add/', views.ExpenseCreateView.as_view(), name='expense_add'),
    path('reimbursement/edit/<int:pk>/', views.ExpenseUpdateView.as_view(), name='expense_edit'),
    path('reimbursement/view/<int:id>/', views.expense_view, name='expense_view'),
    path('reimbursement/del/', views.expense_delete, name='expense_del'),
    
    # 发票管理 (invoice)
    path('invoice/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoice/datalist/', views.InvoiceListView.as_view(), name='invoice_datalist'),
    path('invoice/add/', views.InvoiceCreateView.as_view(), name='invoice_add'),
    path('invoice/edit/<int:pk>/', views.InvoiceUpdateView.as_view(), name='invoice_edit'),
    path('invoice/view/<int:id>/', views.invoice_view, name='invoice_view'),
    path('invoice/del/', views.invoice_delete, name='invoice_del'),
    path('invoice/download/<int:invoice_id>/', views.InvoiceDownloadView.as_view(), name='invoice_download'),
    
    # 收票管理 (receiveinvoice)
    path('receiveinvoice/', views.ReceiveInvoiceListView.as_view(), name='receiveinvoice_list'),
    path('receiveinvoice/datalist/', views.ReceiveInvoiceListView.as_view(), name='receiveinvoice_datalist'),
    path('receiveinvoice/add/', views.ReceiveInvoiceCreateView.as_view(), name='receiveinvoice_add'),
    path('receiveinvoice/edit/<int:pk>/', views.ReceiveInvoiceUpdateView.as_view(), name='receiveinvoice_edit'),
    path('receiveinvoice/view/<int:id>/', views.receiveinvoice_view, name='receiveinvoice_view'),
    path('receiveinvoice/del/', views.receiveinvoice_delete, name='receiveinvoice_del'),
    
    # 收款管理 (paymentreceive)
    path('paymentreceive/', views.PaymentReceiveListView.as_view(), name='paymentreceive_list'),
    path('paymentreceive/datalist/', views.PaymentReceiveListView.as_view(), name='paymentreceive_datalist'),
    path('paymentreceive/create/', views.PaymentReceiveListView.as_view(), name='paymentreceive_create'),
    path('paymentreceive/<int:pk>/update/', views.PaymentReceiveListView.as_view(), name='paymentreceive_update'),
    path('paymentreceive/<int:pk>/detail/', views.PaymentReceiveListView.as_view(), name='paymentreceive_detail'),
    path('paymentreceive/<int:pk>/delete/', views.PaymentReceiveListView.as_view(), name='paymentreceive_delete'),
    
    # 待回款管理
    path('pendingpayment/', views.PendingPaymentListView.as_view(), name='pending_payment_list'),
    path('pendingpayment/datalist/', views.PendingPaymentListView.as_view(), name='pending_payment_datalist'),
    
    # 付款管理 (payment)
    path('payment/', views.PaymentListView.as_view(), name='payment_list'),
    path('payment/datalist/', views.PaymentListView.as_view(), name='payment_datalist'),
    path('payment/add/', views.PaymentCreateView.as_view(), name='payment_add'),
    path('payment/edit/<int:pk>/', views.PaymentUpdateView.as_view(), name='payment_edit'),
    path('payment/view/<int:id>/', views.payment_view, name='payment_view'),
    path('payment/del/', views.payment_delete, name='payment_del'),
    
    # 统计页面
    path('statistics/reimbursement/', views.ReimbursementStatisticsView.as_view(), name='reimbursement_statistics'),
    path('statistics/invoice/', views.InvoiceStatisticsView.as_view(), name='invoice_statistics'),
    path('statistics/receiveinvoice/', views.ReceiveInvoiceStatisticsView.as_view(), name='receiveinvoice_statistics'),
    path('statistics/paymentreceive/', views.PaymentReceiveStatisticsView.as_view(), name='paymentreceive_statistics'),
    path('statistics/payment/', views.PaymentStatisticsView.as_view(), name='payment_statistics'),
    
    # 开票申请相关
    path('invoice-request/list/', views.InvoiceRequestListView.as_view(), name='invoice_request_list'),
    path('invoice-request/detail/<int:request_id>/', views.InvoiceRequestDetailView.as_view(), name='invoice_request_detail'),
    path('invoice-request/approval/', views.InvoiceRequestApprovalView.as_view(), name='invoice_request_approval'),
    
    # 订单财务记录
    path('order-finance/list/', views.OrderFinanceRecordListView.as_view(), name='order_finance_list'),
    
    # 审批相关
    path('approval/list/', views.FinanceApprovalListView.as_view(), name='approval_list'),
    path('approval/submit/', views.FinanceApprovalSubmitView.as_view(), name='approval_submit'),
    
    # 财务统计
    path('statistics/', views.FinanceStatisticsView.as_view(), name='finance_statistics'),
    
    # 报销类型和费用类型管理
    path('reimbursement_type/', finance_views.reimbursement_type_list, name='reimbursement_type_list'),
    path('reimbursement_type/add/', finance_views.reimbursement_type_form, name='reimbursement_type_add'),
    path('reimbursement_type/<int:pk>/edit/', finance_views.reimbursement_type_form, name='reimbursement_type_edit'),
    
    path('expense_type/', finance_views.expense_type_list, name='expense_type_list'),
    path('expense_type/add/', finance_views.expense_type_form, name='expense_type_add'),
    path('expense_type/<int:pk>/edit/', finance_views.expense_type_form, name='expense_type_edit'),
]