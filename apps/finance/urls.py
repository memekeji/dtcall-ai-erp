"""
财务管理模块URL配置
只包含有数据库表的模型对应的路由
"""

from django.urls import path
from . import views, ai_views

app_name = "finance"

urlpatterns = [
    # 财务模块首页
    path("", views.FinanceIndexView.as_view(), name="finance_index"),
    # 报销管理 - 新路由
    path("expense/", views.ExpenseListView.as_view(), name="expense_list"),
    path("expense/datalist/", views.ExpenseListView.as_view(), name="expense_datalist"),
    path("expense/add/", views.ExpenseCreateView.as_view(), name="expense_add"),
    path("expense/edit/<int:pk>/", views.ExpenseUpdateView.as_view(), name="expense_edit"),
    path("expense/submit/", views.ExpenseSubmitView.as_view(), name="expense_submit"),
    path(
        "expense/approve/", views.ExpenseApproveView.as_view(), name="expense_approve"
    ),
    path(
        "expense/batch-approve/",
        views.BatchApprovalView.as_view(),
        name="expense_batch_approve",
    ),
    path("expense/del/", views.ExpenseDeleteView.as_view(), name="expense_del"),
    path("expense/view/<int:id>/", views.expense_detail, name="expense_detail"),
    # 报销管理 - 旧路由兼容
    path(
        "reimbursement/",
        views.ReimbursementListView.as_view(),
        name="reimbursement_list",
    ),
    path(
        "reimbursement/datalist/",
        views.ExpenseListView.as_view(),
        name="reimbursement_datalist",
    ),
    path(
        "reimbursement/add/",
        views.ExpenseCreateView.as_view(),
        name="reimbursement_add",
    ),
    path(
        "reimbursement/edit/<int:pk>/",
        views.ExpenseUpdateView.as_view(),
        name="reimbursement_edit",
    ),
    path(
        "reimbursement/submit/",
        views.ExpenseSubmitView.as_view(),
        name="reimbursement_submit",
    ),
    path(
        "reimbursement/approve/",
        views.ExpenseApproveView.as_view(),
        name="reimbursement_approve",
    ),
    path(
        "reimbursement/batch/",
        views.BatchApprovalView.as_view(),
        name="reimbursement_batch",
    ),
    path(
        "reimbursement/batch-approve/",
        views.BatchApprovalView.as_view(),
        name="reimbursement_batch_approve",
    ),
    path(
        "reimbursement/del/",
        views.ExpenseDeleteView.as_view(),
        name="reimbursement_del",
    ),
    path(
        "reimbursement/view/<int:id>/",
        views.expense_detail,
        name="reimbursement_view",
    ),
    path("reimbursement/<int:id>/", views.expense_detail, name="reimbursement_detail"),
    # 发票管理 - 新路由
    path("invoice/", views.InvoiceListView.as_view(), name="invoice_list"),
    path("invoice/datalist/", views.InvoiceListView.as_view(), name="invoice_datalist"),
    path("invoice/add/", views.InvoiceCreateView.as_view(), name="invoice_add"),
    path(
        "invoice/edit/<int:pk>/", views.InvoiceUpdateView.as_view(), name="invoice_edit"
    ),
    path("invoice/view/<int:id>/", views.invoice_detail, name="invoice_detail"),
    path("invoice/del/", views.InvoiceDeleteView.as_view(), name="invoice_del"),
    # 发票统计
    path(
        "invoice/statistics/",
        views.InvoiceStatisticsView.as_view(),
        name="invoice_statistics",
    ),
    # 收票管理 - 旧路由兼容
    path(
        "receiveinvoice/",
        views.ReceiveInvoiceListView.as_view(),
        name="receiveinvoice_list",
    ),
    path(
        "receiveinvoice/datalist/",
        views.InvoiceListView.as_view(),
        name="receiveinvoice_datalist",
    ),
    # 回款管理
    path("income/", views.IncomeListView.as_view(), name="income_list"),
    path("income/datalist/", views.IncomeListView.as_view(), name="income_datalist"),
    path("income/add/", views.IncomeCreateView.as_view(), name="income_add"),
    path("income/view/<int:id>/", views.income_detail, name="income_detail"),
    path("income/del/", views.IncomeDeleteView.as_view(), name="income_del"),
    # 付款管理
    path("payment/", views.PaymentListView.as_view(), name="payment_list"),
    path("payment/datalist/", views.PaymentListView.as_view(), name="payment_datalist"),
    path("payment/add/", views.PaymentCreateView.as_view(), name="payment_add"),
    path("payment/view/<int:id>/", views.payment_detail, name="payment_detail"),
    path("payment/del/", views.PaymentDeleteView.as_view(), name="payment_del"),
    # 付款统计
    path(
        "payment/statistics/",
        views.PaymentStatisticsView.as_view(),
        name="payment_statistics",
    ),
    path(
        "paymentreceive/statistics/",
        views.PaymentReceiveStatisticsView.as_view(),
        name="paymentreceive_statistics",
    ),
    # 收付款管理 - 旧路由兼容
    path("paymentreceive/", views.IncomeListView.as_view(), name="paymentreceive_list"),
    path(
        "paymentreceive/datalist/",
        views.IncomeListView.as_view(),
        name="paymentreceive_datalist",
    ),
    path(
        "paymentreceive/add/",
        views.PaymentReceiveCreateView.as_view(),
        name="paymentreceive_add",
    ),
    path(
        "paymentreceive/create/",
        views.PaymentReceiveCreateView.as_view(),
        name="paymentreceive_create",
    ),
    # 开票申请
    path(
        "invoice-request/",
        views.InvoiceRequestListView.as_view(),
        name="invoice_request_list",
    ),
    path(
        "invoice-request/add/",
        views.InvoiceRequestCreateView.as_view(),
        name="invoice_request_add",
    ),
    path(
        "invoice-request/datalist/",
        views.InvoiceRequestListView.as_view(),
        name="invoice_request_datalist",
    ),
    path(
        "invoice-request/detail/<int:id>/",
        views.invoice_request_detail,
        name="invoice_request_detail",
    ),
    path(
        "invoice-request/approval/",
        views.InvoiceRequestApprovalView.as_view(),
        name="invoice_request_approval",
    ),
    # 订单财务记录
    path(
        "order-finance/",
        views.OrderFinanceRecordListView.as_view(),
        name="order_finance_list",
    ),
    path(
        "order-finance/datalist/",
        views.OrderFinanceRecordListView.as_view(),
        name="order_finance_datalist",
    ),
    path(
        "advanced/bank-transaction/import/",
        views.BankTransactionImportView.as_view(),
        name="bank_transaction_import",
    ),
    path(
        "advanced/bank-import-template/",
        views.BankImportTemplateConfigView.as_view(),
        name="bank_import_template",
    ),
    path(
        "advanced/bank-reconciliation/import/",
        views.BankReconciliationImportView.as_view(),
        name="bank_reconciliation_import",
    ),
    path(
        "advanced/bank-reconciliation/<int:id>/compare/",
        views.BankReconciliationCompareView.as_view(),
        name="bank_reconciliation_compare",
    ),
    # 专业财务扩展
    path(
        "advanced/<str:module>/",
        views.AdvancedFinanceListView.as_view(),
        name="advanced_finance_list",
    ),
    path(
        "advanced/<str:module>/datalist/",
        views.AdvancedFinanceListView.as_view(),
        name="advanced_finance_datalist",
    ),
    path(
        "advanced/<str:module>/add/",
        views.AdvancedFinanceCreateView.as_view(),
        name="advanced_finance_add",
    ),
    path(
        "advanced/<str:module>/edit/<int:pk>/",
        views.AdvancedFinanceUpdateView.as_view(),
        name="advanced_finance_edit",
    ),
    path(
        "advanced/<str:module>/del/",
        views.AdvancedFinanceDeleteView.as_view(),
        name="advanced_finance_del",
    ),
    # 财务统计 - 新路由
    path(
        "statistics/", views.FinanceStatisticsView.as_view(), name="finance_statistics"
    ),
    # 财务统计 - 旧路由兼容
    path(
        "statistics/reimbursement/",
        views.ReimbursementStatisticsView.as_view(),
        name="statistics_reimbursement",
    ),
    path(
        "statistics/invoice/",
        views.InvoiceStatisticsView.as_view(),
        name="statistics_invoice",
    ),
    path(
        "statistics/receiveinvoice/",
        views.ReceiveInvoiceStatisticsView.as_view(),
        name="statistics_receiveinvoice",
    ),
    path(
        "statistics/paymentreceive/",
        views.PaymentReceiveStatisticsView.as_view(),
        name="statistics_paymentreceive",
    ),
    path(
        "statistics/payment/",
        views.PaymentStatisticsView.as_view(),
        name="statistics_payment",
    ),
    # AI功能相关路由
    path(
        "ai/expense-review/",
        ai_views.AIExpenseReviewView.as_view(),
        name="ai_expense_review",
    ),
    path(
        "ai/expense-anomaly/",
        ai_views.AIExpenseAnomalyDetectionView.as_view(),
        name="ai_expense_anomaly",
    ),
    path(
        "ai/expense-review/<int:expense_id>/",
        ai_views.ai_expense_review,
        name="ai_expense_review_detail",
    ),
    path(
        "ai/expense-anomaly/<int:expense_id>/",
        ai_views.ai_expense_anomaly_detection,
        name="ai_expense_anomaly_detail",
    ),
]
