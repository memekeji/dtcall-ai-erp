"""
财务管理模块管理配置
只包含有数据库表的模型
"""
from django.contrib import admin
from .models import Expense, Invoice, Income, Payment, InvoiceRequest, OrderFinanceRecord


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['id', 'code', 'admin_id', 'cost',
                    'check_status', 'pay_status', 'expense_time', 'create_time']
    list_filter = ['check_status', 'pay_status', 'admin_id']
    search_fields = ['code']
    ordering = ['-create_time']
    readonly_fields = ['create_time']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'code', 'customer_id', 'amount',
                    'invoice_type', 'open_status', 'enter_amount',
                    'open_status', 'create_time']
    list_filter = ['open_status', 'invoice_type', 'customer_id']
    search_fields = ['code', 'invoice_title']
    ordering = ['-create_time']
    readonly_fields = ['create_time']


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ['id', 'invoice_id', 'amount', 'income_date', 'file_ids']
    list_filter = ['income_date']
    search_fields = ['invoice_id']
    ordering = ['-income_date']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'expense_id', 'amount', 'payment_date', 'file_ids']
    list_filter = ['payment_date']
    search_fields = ['expense_id']
    ordering = ['-payment_date']


@admin.register(InvoiceRequest)
class InvoiceRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'order_id', 'amount', 'invoice_type', 'status',
                    'applicant_id', 'reviewer_id', 'create_time']
    list_filter = ['status', 'invoice_type', 'create_time']
    search_fields = ['order_id', 'invoice_title']
    ordering = ['-create_time']

    fieldsets = (
        ('基本信息', {
            'fields': ('order_id', 'applicant_id', 'department_id', 'amount', 'invoice_type')
        }),
        ('开票信息', {
            'fields': ('invoice_title', 'tax_number', 'reason')
        }),
        ('审批信息', {
            'fields': ('status', 'reviewer_id', 'review_time', 'review_comment')
        }),
        ('开票信息', {
            'fields': ('invoice_id', 'invoice_time')
        }),
    )


@admin.register(OrderFinanceRecord)
class OrderFinanceRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'order_id', 'total_amount', 'paid_amount', 'payment_status', 'due_date']
    list_filter = ['payment_status', 'due_date']
    search_fields = ['order_id']
    ordering = ['-create_time']
