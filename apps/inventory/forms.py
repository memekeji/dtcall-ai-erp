from django import forms
from django.core.exceptions import ValidationError
from .models import (
    Warehouse, WarehouseLocation, InventoryCategory, InventoryItem,
    Inventory, StockIn, StockInItem, StockOut, StockOutItem,
    StockTransfer, StockTransferItem, StockCheck, StockCheckItem,
    PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem,
    InventoryAlert
)


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ['name', 'code', 'warehouse_type', 'address', 'manager', 
                  'phone', 'email', 'capacity', 'status', 'is_default', 'remark']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input'}),
            'code': forms.TextInput(attrs={'class': 'layui-input'}),
            'warehouse_type': forms.Select(attrs={'class': 'layui-input'}),
            'address': forms.TextInput(attrs={'class': 'layui-input'}),
            'manager': forms.Select(attrs={'class': 'layui-input'}),
            'phone': forms.TextInput(attrs={'class': 'layui-input'}),
            'email': forms.EmailInput(attrs={'class': 'layui-input'}),
            'capacity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'is_default': forms.CheckboxInput(),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }


class WarehouseLocationForm(forms.ModelForm):
    class Meta:
        model = WarehouseLocation
        fields = ['warehouse', 'parent', 'name', 'code', 'location_type', 
                  'capacity', 'status', 'sort']
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'layui-input'}),
            'parent': forms.Select(attrs={'class': 'layui-input'}),
            'name': forms.TextInput(attrs={'class': 'layui-input'}),
            'code': forms.TextInput(attrs={'class': 'layui-input'}),
            'location_type': forms.Select(attrs={'class': 'layui-input'}),
            'capacity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'sort': forms.NumberInput(attrs={'class': 'layui-input'}),
        }


class InventoryCategoryForm(forms.ModelForm):
    class Meta:
        model = InventoryCategory
        fields = ['name', 'code', 'category_type', 'parent', 'description', 'status', 'sort']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input'}),
            'code': forms.TextInput(attrs={'class': 'layui-input'}),
            'category_type': forms.Select(attrs={'class': 'layui-input'}),
            'parent': forms.Select(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'sort': forms.NumberInput(attrs={'class': 'layui-input'}),
        }


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ['name', 'code', 'category', 'specification', 'unit', 
                  'weight', 'length', 'width', 'height', 'volume',
                  'barcode', 'qr_code', 'standard_cost', 'average_cost', 
                  'latest_cost', 'retail_price', 'wholesale_price',
                  'min_stock', 'max_stock', 'reorder_point', 'safety_stock',
                  'shelf_life', 'status', 'image', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'layui-input'}),
            'code': forms.TextInput(attrs={'class': 'layui-input'}),
            'category': forms.Select(attrs={'class': 'layui-input'}),
            'specification': forms.TextInput(attrs={'class': 'layui-input'}),
            'unit': forms.TextInput(attrs={'class': 'layui-input'}),
            'weight': forms.NumberInput(attrs={'class': 'layui-input'}),
            'length': forms.NumberInput(attrs={'class': 'layui-input'}),
            'width': forms.NumberInput(attrs={'class': 'layui-input'}),
            'height': forms.NumberInput(attrs={'class': 'layui-input'}),
            'volume': forms.NumberInput(attrs={'class': 'layui-input'}),
            'barcode': forms.TextInput(attrs={'class': 'layui-input'}),
            'qr_code': forms.TextInput(attrs={'class': 'layui-input'}),
            'standard_cost': forms.NumberInput(attrs={'class': 'layui-input'}),
            'average_cost': forms.NumberInput(attrs={'class': 'layui-input'}),
            'latest_cost': forms.NumberInput(attrs={'class': 'layui-input'}),
            'retail_price': forms.NumberInput(attrs={'class': 'layui-input'}),
            'wholesale_price': forms.NumberInput(attrs={'class': 'layui-input'}),
            'min_stock': forms.NumberInput(attrs={'class': 'layui-input'}),
            'max_stock': forms.NumberInput(attrs={'class': 'layui-input'}),
            'reorder_point': forms.NumberInput(attrs={'class': 'layui-input'}),
            'safety_stock': forms.NumberInput(attrs={'class': 'layui-input'}),
            'shelf_life': forms.NumberInput(attrs={'class': 'layui-input'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'image': forms.TextInput(attrs={'class': 'layui-input'}),
            'description': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }


class StockInForm(forms.ModelForm):
    class Meta:
        model = StockIn
        fields = ['code', 'stock_in_type', 'warehouse', 'supplier', 
                  'purchase_order', 'total_amount', 'total_quantity', 'status', 'remark']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'layui-input'}),
            'stock_in_type': forms.Select(attrs={'class': 'layui-input'}),
            'warehouse': forms.Select(attrs={'class': 'layui-input'}),
            'supplier': forms.Select(attrs={'class': 'layui-input'}),
            'purchase_order': forms.Select(attrs={'class': 'layui-input'}),
            'total_amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'total_quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }


class StockInItemForm(forms.ModelForm):
    class Meta:
        model = StockInItem
        fields = ['stock_in', 'item', 'location', 'batch_number', 
                  'quantity', 'unit_cost', 'amount', 'production_date', 
                  'expiry_date', 'remark']
        widgets = {
            'stock_in': forms.HiddenInput(),
            'item': forms.Select(attrs={'class': 'layui-input'}),
            'location': forms.Select(attrs={'class': 'layui-input'}),
            'batch_number': forms.TextInput(attrs={'class': 'layui-input'}),
            'quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'layui-input'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'production_date': forms.DateInput(attrs={'class': 'layui-input', 'id': 'production_date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'layui-input', 'id': 'expiry_date'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }


class StockOutForm(forms.ModelForm):
    class Meta:
        model = StockOut
        fields = ['code', 'stock_out_type', 'warehouse', 'customer',
                  'sales_order', 'production_task', 'total_amount', 
                  'total_quantity', 'status', 'remark']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'layui-input'}),
            'stock_out_type': forms.Select(attrs={'class': 'layui-input'}),
            'warehouse': forms.Select(attrs={'class': 'layui-input'}),
            'customer': forms.Select(attrs={'class': 'layui-input'}),
            'sales_order': forms.Select(attrs={'class': 'layui-input'}),
            'production_task': forms.Select(attrs={'class': 'layui-input'}),
            'total_amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'total_quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }


class StockOutItemForm(forms.ModelForm):
    class Meta:
        model = StockOutItem
        fields = ['stock_out', 'item', 'location', 'batch_number', 
                  'quantity', 'unit_cost', 'amount', 'remark']
        widgets = {
            'stock_out': forms.HiddenInput(),
            'item': forms.Select(attrs={'class': 'layui-input'}),
            'location': forms.Select(attrs={'class': 'layui-input'}),
            'batch_number': forms.TextInput(attrs={'class': 'layui-input'}),
            'quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'layui-input'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }


class StockTransferForm(forms.ModelForm):
    class Meta:
        model = StockTransfer
        fields = ['code', 'from_warehouse', 'to_warehouse', 'total_quantity', 
                  'total_amount', 'status', 'requester', 'remark']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'layui-input'}),
            'from_warehouse': forms.Select(attrs={'class': 'layui-input'}),
            'to_warehouse': forms.Select(attrs={'class': 'layui-input'}),
            'total_quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'total_amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'requester': forms.Select(attrs={'class': 'layui-input'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }


class StockTransferItemForm(forms.ModelForm):
    class Meta:
        model = StockTransferItem
        fields = ['stock_transfer', 'item', 'from_location', 'to_location', 
                  'batch_number', 'quantity', 'unit_cost', 'amount', 
                  'transferred_quantity', 'remark']
        widgets = {
            'stock_transfer': forms.HiddenInput(),
            'item': forms.Select(attrs={'class': 'layui-input'}),
            'from_location': forms.Select(attrs={'class': 'layui-input'}),
            'to_location': forms.Select(attrs={'class': 'layui-input'}),
            'batch_number': forms.TextInput(attrs={'class': 'layui-input'}),
            'quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'layui-input'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'transferred_quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }


class StockCheckForm(forms.ModelForm):
    class Meta:
        model = StockCheck
        fields = ['code', 'check_type', 'warehouse', 'category', 'status', 'remark']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'layui-input'}),
            'check_type': forms.Select(attrs={'class': 'layui-input'}),
            'warehouse': forms.Select(attrs={'class': 'layui-input'}),
            'category': forms.Select(attrs={'class': 'layui-input'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }


class StockCheckItemForm(forms.ModelForm):
    class Meta:
        model = StockCheckItem
        fields = ['stock_check', 'item', 'location', 'batch_number',
                  'system_quantity', 'actual_quantity', 'difference',
                  'unit_cost', 'difference_amount', 'status', 'remark']
        widgets = {
            'stock_check': forms.HiddenInput(),
            'item': forms.Select(attrs={'class': 'layui-input'}),
            'location': forms.Select(attrs={'class': 'layui-input'}),
            'batch_number': forms.TextInput(attrs={'class': 'layui-input'}),
            'system_quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'actual_quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'difference': forms.NumberInput(attrs={'class': 'layui-input'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'layui-input'}),
            'difference_amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['code', 'order_type', 'supplier', 'warehouse', 'total_amount',
                  'total_quantity', 'order_date', 'expected_date', 'status',
                  'creator', 'contact_person', 'contact_phone', 
                  'delivery_address', 'payment_terms', 'remark']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'layui-input'}),
            'order_type': forms.Select(attrs={'class': 'layui-input'}),
            'supplier': forms.Select(attrs={'class': 'layui-input'}),
            'warehouse': forms.Select(attrs={'class': 'layui-input'}),
            'total_amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'total_quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'order_date': forms.DateInput(attrs={'class': 'layui-input', 'id': 'order_date'}),
            'expected_date': forms.DateInput(attrs={'class': 'layui-input', 'id': 'expected_date'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'creator': forms.Select(attrs={'class': 'layui-input'}),
            'contact_person': forms.TextInput(attrs={'class': 'layui-input'}),
            'contact_phone': forms.TextInput(attrs={'class': 'layui-input'}),
            'delivery_address': forms.TextInput(attrs={'class': 'layui-input'}),
            'payment_terms': forms.TextInput(attrs={'class': 'layui-input'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }


class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ['purchase_order', 'item', 'quantity', 'unit_price', 'amount',
                  'received_quantity', 'unit_cost', 'tax_rate', 'tax_amount',
                  'expected_date', 'remark']
        widgets = {
            'purchase_order': forms.HiddenInput(),
            'item': forms.Select(attrs={'class': 'layui-input'}),
            'quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'unit_price': forms.NumberInput(attrs={'class': 'layui-input'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'received_quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'layui-input'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'layui-input'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'expected_date': forms.DateInput(attrs={'class': 'layui-input', 'id': 'item_expected_date'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }


class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = ['code', 'order_type', 'customer', 'warehouse', 'contract',
                  'total_amount', 'total_quantity', 'order_date', 'expected_date',
                  'status', 'creator', 'contact_person', 'contact_phone',
                  'shipping_address', 'payment_terms', 'discount_amount',
                  'tax_amount', 'remark']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'layui-input'}),
            'order_type': forms.Select(attrs={'class': 'layui-input'}),
            'customer': forms.Select(attrs={'class': 'layui-input'}),
            'warehouse': forms.Select(attrs={'class': 'layui-input'}),
            'contract': forms.Select(attrs={'class': 'layui-input'}),
            'total_amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'total_quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'order_date': forms.DateInput(attrs={'class': 'layui-input', 'id': 'sales_order_date'}),
            'expected_date': forms.DateInput(attrs={'class': 'layui-input', 'id': 'sales_expected_date'}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'creator': forms.Select(attrs={'class': 'layui-input'}),
            'contact_person': forms.TextInput(attrs={'class': 'layui-input'}),
            'contact_phone': forms.TextInput(attrs={'class': 'layui-input'}),
            'shipping_address': forms.TextInput(attrs={'class': 'layui-input'}),
            'payment_terms': forms.TextInput(attrs={'class': 'layui-input'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
        }


class SalesOrderItemForm(forms.ModelForm):
    class Meta:
        model = SalesOrderItem
        fields = ['sales_order', 'item', 'quantity', 'unit_price', 'amount',
                  'shipped_quantity', 'unit_cost', 'cost_amount', 'tax_rate',
                  'tax_amount', 'discount_rate', 'expected_date', 'remark']
        widgets = {
            'sales_order': forms.HiddenInput(),
            'item': forms.Select(attrs={'class': 'layui-input'}),
            'quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'unit_price': forms.NumberInput(attrs={'class': 'layui-input'}),
            'amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'shipped_quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'layui-input'}),
            'cost_amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'layui-input'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'layui-input'}),
            'discount_rate': forms.NumberInput(attrs={'class': 'layui-input'}),
            'expected_date': forms.DateInput(attrs={'class': 'layui-input', 'id': 'sales_item_expected_date'}),
            'remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }


class InventorySearchForm(forms.Form):
    item_code = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '物料编码'}))
    item_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'layui-input', 'placeholder': '物料名称'}))
    category = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': 'layui-input'}))
    warehouse = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': 'layui-input'}))
    location = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': 'layui-input'}))
    status = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': 'layui-input'}))
    min_quantity = forms.DecimalField(required=False, widget=forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '最小数量'}))
    max_quantity = forms.DecimalField(required=False, widget=forms.NumberInput(attrs={'class': 'layui-input', 'placeholder': '最大数量'}))


class InventoryAlertForm(forms.ModelForm):
    class Meta:
        model = InventoryAlert
        fields = ['item', 'warehouse', 'alert_type', 'current_quantity', 
                  'threshold_value', 'message', 'status', 'handler', 
                  'handle_remark']
        widgets = {
            'item': forms.Select(attrs={'class': 'layui-input'}),
            'warehouse': forms.Select(attrs={'class': 'layui-input'}),
            'alert_type': forms.Select(attrs={'class': 'layui-input'}),
            'current_quantity': forms.NumberInput(attrs={'class': 'layui-input'}),
            'threshold_value': forms.NumberInput(attrs={'class': 'layui-input'}),
            'message': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'layui-input'}),
            'handler': forms.Select(attrs={'class': 'layui-input'}),
            'handle_remark': forms.Textarea(attrs={'class': 'layui-textarea', 'rows': 2}),
        }
