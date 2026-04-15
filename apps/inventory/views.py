from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
import json
import logging

from apps.user.models import Admin
from .models import (
    Warehouse, WarehouseLocation, InventoryCategory, InventoryItem,
    Inventory, StockTransaction, StockIn, StockInItem, StockOut, StockOutItem,
    StockTransfer, StockCheck, PurchaseOrder, SalesOrder,
    InventoryAlert
)
from .forms import (
    WarehouseForm,
    WarehouseLocationForm,
    InventoryCategoryForm,
    InventoryItemForm,
    StockInForm,
    StockInItemForm,
    StockOutForm,
    StockOutItemForm)

logger = logging.getLogger(__name__)


def get_default_warehouse():
    try:
        return Warehouse.objects.filter(status=1).first()
    except Exception as e:
        logger.error(f"获取默认仓库失败: {e}")
        return None


def generate_code(prefix):
    now = timezone.now()
    code = f"{prefix}{now.strftime('%Y%m%d%H%M%S')}"
    return code


class InventoryMixin:
    def get_queryset(self, model, request):
        queryset = model.objects.all()
        return queryset


class WarehouseView(InventoryMixin):
    def list(self, request):
        warehouses = Warehouse.objects.all().order_by('code')
        data = [{
            'id': w.id,
            'name': w.name,
            'code': w.code,
            'warehouse_type': w.get_warehouse_type_display(),
            'address': w.address,
            'manager': w.manager.name if w.manager else '',
            'phone': w.phone,
            'status': w.status,
            'status_display': '启用' if w.status == 1 else '禁用',
            'is_default': w.is_default,
            'usage_rate': float(w.usage_rate),
            'remark': w.remark,
            'create_time': w.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        } for w in warehouses]
        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})

    def get(self, request, pk=None):
        if pk:
            warehouse = get_object_or_404(Warehouse, pk=pk)
            data = {
                'id': warehouse.id,
                'name': warehouse.name,
                'code': warehouse.code,
                'warehouse_type': warehouse.warehouse_type,
                'address': warehouse.address,
                'manager_id': warehouse.manager_id,
                'manager': warehouse.manager.name if warehouse.manager else '',
                'phone': warehouse.phone,
                'email': warehouse.email,
                'capacity': str(warehouse.capacity),
                'used_capacity': str(warehouse.used_capacity),
                'status': warehouse.status,
                'is_default': warehouse.is_default,
                'remark': warehouse.remark,
            }
            return JsonResponse({'code': 0, 'msg': 'success', 'data': data})
        else:
            return self.list(request)

    def create(self, request):
        try:
            data = json.loads(request.body)
            form = WarehouseForm(data)
            if form.is_valid():
                warehouse = form.save()
                if data.get('is_default', False):
                    Warehouse.objects.filter(
                        ~Q(pk=warehouse.pk), is_default=True).update(is_default=False)
                return JsonResponse(
                    {'code': 0, 'msg': '创建成功', 'data': {'id': warehouse.id}})
            return JsonResponse({'code': 1, 'msg': form.errors})
        except Exception as e:
            logger.error(f"创建仓库失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    def update(self, request, pk):
        try:
            warehouse = get_object_or_404(Warehouse, pk=pk)
            data = json.loads(request.body)
            form = WarehouseForm(data, instance=warehouse)
            if form.is_valid():
                warehouse = form.save()
                if data.get('is_default', False):
                    Warehouse.objects.filter(
                        ~Q(pk=warehouse.pk), is_default=True).update(is_default=False)
                return JsonResponse(
                    {'code': 0, 'msg': '更新成功', 'data': {'id': warehouse.id}})
            return JsonResponse({'code': 1, 'msg': form.errors})
        except Exception as e:
            logger.error(f"更新仓库失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    def delete(self, request, pk):
        try:
            warehouse = get_object_or_404(Warehouse, pk=pk)
            inventory_count = Inventory.objects.filter(
                warehouse=warehouse).count()
            if inventory_count > 0:
                return JsonResponse(
                    {'code': 1, 'msg': f'该仓库下有{inventory_count}条库存记录，无法删除'})
            warehouse.delete()
            return JsonResponse({'code': 0, 'msg': '删除成功'})
        except Exception as e:
            logger.error(f"删除仓库失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})


class WarehouseLocationView(InventoryMixin):
    def list(self, request):
        warehouse_id = request.GET.get('warehouse_id')
        if warehouse_id:
            locations = WarehouseLocation.objects.filter(
                warehouse_id=warehouse_id).order_by('code')
        else:
            locations = WarehouseLocation.objects.all().order_by('code')
        data = [{
            'id': loc.id,
            'warehouse_id': loc.warehouse_id,
            'warehouse_name': loc.warehouse.name,
            'parent_id': loc.parent_id,
            'parent_name': loc.parent.name if loc.parent else '',
            'name': loc.name,
            'code': loc.code,
            'location_type': loc.get_location_type_display(),
            'capacity': str(loc.capacity),
            'status': loc.status,
            'status_display': '启用' if loc.status == 1 else '禁用',
            'sort': loc.sort,
            'full_path': loc.full_path,
        } for loc in locations]
        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})

    def get(self, request, pk=None):
        if pk:
            location = get_object_or_404(WarehouseLocation, pk=pk)
            data = {
                'id': location.id,
                'warehouse_id': location.warehouse_id,
                'parent_id': location.parent_id,
                'name': location.name,
                'code': location.code,
                'location_type': location.location_type,
                'capacity': str(location.capacity),
                'status': location.status,
                'sort': location.sort,
            }
            return JsonResponse({'code': 0, 'msg': 'success', 'data': data})
        else:
            return self.list(request)

    def create(self, request):
        try:
            data = json.loads(request.body)
            form = WarehouseLocationForm(data)
            if form.is_valid():
                location = form.save()
                return JsonResponse(
                    {'code': 0, 'msg': '创建成功', 'data': {'id': location.id}})
            return JsonResponse({'code': 1, 'msg': form.errors})
        except Exception as e:
            logger.error(f"创建库位失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    def update(self, request, pk):
        try:
            location = get_object_or_404(WarehouseLocation, pk=pk)
            data = json.loads(request.body)
            form = WarehouseLocationForm(data, instance=location)
            if form.is_valid():
                location = form.save()
                return JsonResponse(
                    {'code': 0, 'msg': '更新成功', 'data': {'id': location.id}})
            return JsonResponse({'code': 1, 'msg': form.errors})
        except Exception as e:
            logger.error(f"更新库位失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    def delete(self, request, pk):
        try:
            location = get_object_or_404(WarehouseLocation, pk=pk)
            child_count = WarehouseLocation.objects.filter(
                parent=location).count()
            if child_count > 0:
                return JsonResponse(
                    {'code': 1, 'msg': f'该库位下有{child_count}个子库位，无法删除'})
            inventory_count = Inventory.objects.filter(
                location=location).count()
            if inventory_count > 0:
                return JsonResponse(
                    {'code': 1, 'msg': f'该库位下有{inventory_count}条库存记录，无法删除'})
            location.delete()
            return JsonResponse({'code': 0, 'msg': '删除成功'})
        except Exception as e:
            logger.error(f"删除库位失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})


class InventoryCategoryView(InventoryMixin):
    def list(self, request):
        categories = InventoryCategory.objects.all().order_by('code')
        data = [{
            'id': c.id,
            'name': c.name,
            'code': c.code,
            'category_type': c.get_category_type_display(),
            'parent_id': c.parent_id,
            'parent_name': c.parent.name if c.parent else '',
            'description': c.description,
            'status': c.status,
            'status_display': '启用' if c.status == 1 else '禁用',
            'sort': c.sort,
        } for c in categories]
        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})

    def get(self, request, pk=None):
        if pk:
            category = get_object_or_404(InventoryCategory, pk=pk)
            data = {
                'id': category.id,
                'name': category.name,
                'code': category.code,
                'category_type': category.category_type,
                'parent_id': category.parent_id,
                'description': category.description,
                'status': category.status,
                'sort': category.sort,
            }
            return JsonResponse({'code': 0, 'msg': 'success', 'data': data})
        else:
            return self.list(request)

    def create(self, request):
        try:
            data = json.loads(request.body)
            form = InventoryCategoryForm(data)
            if form.is_valid():
                category = form.save()
                return JsonResponse(
                    {'code': 0, 'msg': '创建成功', 'data': {'id': category.id}})
            return JsonResponse({'code': 1, 'msg': form.errors})
        except Exception as e:
            logger.error(f"创建类别失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    def update(self, request, pk):
        try:
            category = get_object_or_404(InventoryCategory, pk=pk)
            data = json.loads(request.body)
            form = InventoryCategoryForm(data, instance=category)
            if form.is_valid():
                category = form.save()
                return JsonResponse(
                    {'code': 0, 'msg': '更新成功', 'data': {'id': category.id}})
            return JsonResponse({'code': 1, 'msg': form.errors})
        except Exception as e:
            logger.error(f"更新类别失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    def delete(self, request, pk):
        try:
            category = get_object_or_404(InventoryCategory, pk=pk)
            child_count = InventoryCategory.objects.filter(
                parent=category).count()
            if child_count > 0:
                return JsonResponse(
                    {'code': 1, 'msg': f'该类别下有{child_count}个子类别，无法删除'})
            item_count = InventoryItem.objects.filter(
                category=category).count()
            if item_count > 0:
                return JsonResponse(
                    {'code': 1, 'msg': f'该类别下有{item_count}条物料，无法删除'})
            category.delete()
            return JsonResponse({'code': 0, 'msg': '删除成功'})
        except Exception as e:
            logger.error(f"删除类别失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})


class InventoryItemView(InventoryMixin):
    def list(self, request):
        items = InventoryItem.objects.all().order_by('code')
        data = [{
            'id': item.id,
            'name': item.name,
            'code': item.code,
            'category_id': item.category_id,
            'category_name': item.category.name if item.category else '',
            'specification': item.specification,
            'unit': item.unit,
            'standard_cost': str(item.standard_cost),
            'average_cost': str(item.average_cost),
            'latest_cost': str(item.latest_cost),
            'retail_price': str(item.retail_price),
            'wholesale_price': str(item.wholesale_price),
            'min_stock': str(item.min_stock),
            'max_stock': str(item.max_stock),
            'reorder_point': str(item.reorder_point),
            'safety_stock': str(item.safety_stock),
            'status': item.status,
            'status_display': '启用' if item.status == 1 else '禁用',
            'barcode': item.barcode,
            'description': item.description,
        } for item in items]
        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})

    def get(self, request, pk=None):
        if pk:
            item = get_object_or_404(InventoryItem, pk=pk)
            data = {
                'id': item.id,
                'name': item.name,
                'code': item.code,
                'category_id': item.category_id,
                'specification': item.specification,
                'unit': item.unit,
                'weight': str(item.weight),
                'length': str(item.length),
                'width': str(item.width),
                'height': str(item.height),
                'barcode': item.barcode,
                'qr_code': item.qr_code,
                'standard_cost': str(item.standard_cost),
                'average_cost': str(item.average_cost),
                'latest_cost': str(item.latest_cost),
                'retail_price': str(item.retail_price),
                'wholesale_price': str(item.wholesale_price),
                'min_stock': str(item.min_stock),
                'max_stock': str(item.max_stock),
                'reorder_point': str(item.reorder_point),
                'safety_stock': str(item.safety_stock),
                'shelf_life': item.shelf_life,
                'status': item.status,
                'image': item.image,
                'description': item.description,
            }
            return JsonResponse({'code': 0, 'msg': 'success', 'data': data})
        else:
            return self.list(request)

    def create(self, request):
        try:
            data = json.loads(request.body)
            form = InventoryItemForm(data)
            if form.is_valid():
                item = form.save()
                return JsonResponse(
                    {'code': 0, 'msg': '创建成功', 'data': {'id': item.id}})
            return JsonResponse({'code': 1, 'msg': form.errors})
        except Exception as e:
            logger.error(f"创建物料失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    def update(self, request, pk):
        try:
            item = get_object_or_404(InventoryItem, pk=pk)
            data = json.loads(request.body)
            form = InventoryItemForm(data, instance=item)
            if form.is_valid():
                item = form.save()
                return JsonResponse(
                    {'code': 0, 'msg': '更新成功', 'data': {'id': item.id}})
            return JsonResponse({'code': 1, 'msg': form.errors})
        except Exception as e:
            logger.error(f"更新物料失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    def delete(self, request, pk):
        try:
            item = get_object_or_404(InventoryItem, pk=pk)
            inventory_count = Inventory.objects.filter(item=item).count()
            if inventory_count > 0:
                return JsonResponse(
                    {'code': 1, 'msg': f'该物料有{inventory_count}条库存记录，无法删除'})
            item.delete()
            return JsonResponse({'code': 0, 'msg': '删除成功'})
        except Exception as e:
            logger.error(f"删除物料失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})


class InventoryView(InventoryMixin):
    def list(self, request):
        queryset = Inventory.objects.select_related(
            'item', 'warehouse', 'location').all()

        item_code = request.GET.get('item_code')
        item_name = request.GET.get('item_name')
        warehouse_id = request.GET.get('warehouse_id')
        location_id = request.GET.get('location_id')
        category_id = request.GET.get('category_id')
        status = request.GET.get('status')

        if item_code:
            queryset = queryset.filter(item__code__icontains=item_code)
        if item_name:
            queryset = queryset.filter(item__name__icontains=item_name)
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        if category_id:
            queryset = queryset.filter(item__category_id=category_id)
        if status:
            queryset = queryset.filter(status=status)

        total = queryset.aggregate(
            total_quantity=Sum('quantity'),
            total_value=Sum('total_cost')
        )

        data = [{
            'id': inv.id,
            'item_id': inv.item_id,
            'item_code': inv.item.code,
            'item_name': inv.item.name,
            'item_unit': inv.item.unit,
            'category_name': inv.item.category.name if inv.item.category else '',
            'warehouse_id': inv.warehouse_id,
            'warehouse_name': inv.warehouse.name,
            'location_id': inv.location_id,
            'location_name': inv.location.name if inv.location else '',
            'batch_number': inv.batch_number,
            'quantity': str(inv.quantity),
            'locked_quantity': str(inv.locked_quantity),
            'available_quantity': str(inv.available_quantity),
            'unit_cost': str(inv.unit_cost),
            'total_cost': str(inv.total_cost),
            'status': inv.status,
            'status_display': inv.get_status_display(),
            'expiry_date': inv.expiry_date.strftime('%Y-%m-%d') if inv.expiry_date else '',
        } for inv in queryset]

        return JsonResponse({
            'code': 0,
            'msg': 'success',
            'data': data,
            'count': len(data),
            'total': {
                'total_quantity': str(total['total_quantity'] or 0),
                'total_value': str(total['total_value'] or 0),
            }
        })


class StockTransactionView(InventoryMixin):
    def list(self, request):
        queryset = StockTransaction.objects.select_related(
            'item', 'warehouse', 'location', 'operator').all()

        transaction_type = request.GET.get('transaction_type')
        item_code = request.GET.get('item_code')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        if item_code:
            queryset = queryset.filter(item__code__icontains=item_code)
        if start_date:
            queryset = queryset.filter(create_time__gte=start_date)
        if end_date:
            queryset = queryset.filter(create_time__lte=end_date)

        data = [{
            'id': t.id,
            'transaction_type': t.transaction_type,
            'transaction_type_display': t.get_transaction_type_display(),
            'transaction_code': t.transaction_code,
            'item_code': t.item.code,
            'item_name': t.item.name,
            'warehouse_name': t.warehouse.name,
            'location_name': t.location.name if t.location else '',
            'batch_number': t.batch_number,
            'quantity': str(t.quantity),
            'unit_cost': str(t.unit_cost),
            'before_quantity': str(t.before_quantity),
            'after_quantity': str(t.after_quantity),
            'reference_type': t.reference_type,
            'reference_code': t.reference_code,
            'operator_name': t.operator.name if t.operator else '',
            'create_time': t.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        } for t in queryset]

        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})


class StockInView(InventoryMixin):
    def list(self, request):
        queryset = StockIn.objects.select_related(
            'warehouse', 'supplier', 'creator').all()

        status = request.GET.get('status')
        stock_in_type = request.GET.get('stock_in_type')

        if status:
            queryset = queryset.filter(status=status)
        if stock_in_type:
            queryset = queryset.filter(stock_in_type=stock_in_type)

        data = [{
            'id': si.id,
            'code': si.code,
            'stock_in_type': si.stock_in_type,
            'stock_in_type_display': si.get_stock_in_type_display(),
            'warehouse_id': si.warehouse_id,
            'warehouse_name': si.warehouse.name,
            'supplier_id': si.supplier_id,
            'supplier_name': si.supplier.name if si.supplier else '',
            'total_amount': str(si.total_amount),
            'total_quantity': str(si.total_quantity),
            'status': si.status,
            'status_display': si.get_status_display(),
            'checker_name': si.checker.name if si.checker else '',
            'check_time': si.check_time.strftime('%Y-%m-%d %H:%M:%S') if si.check_time else '',
            'stocker_name': si.stocker.name if si.stocker else '',
            'stock_time': si.stock_time.strftime('%Y-%m-%d %H:%M:%S') if si.stock_time else '',
            'create_time': si.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        } for si in queryset]

        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})

    def get(self, request, pk=None):
        if pk:
            stock_in = get_object_or_404(StockIn, pk=pk)
            items = StockInItem.objects.filter(
                stock_in=pk).select_related(
                'item', 'location')
            data = {
                'id': stock_in.id,
                'code': stock_in.code,
                'stock_in_type': stock_in.stock_in_type,
                'warehouse_id': stock_in.warehouse_id,
                'supplier_id': stock_in.supplier_id,
                'purchase_order_id': stock_in.purchase_order_id,
                'total_amount': str(stock_in.total_amount),
                'total_quantity': str(stock_in.total_quantity),
                'status': stock_in.status,
                'remark': stock_in.remark,
                'items': [{
                    'id': item.id,
                    'item_id': item.item_id,
                    'item_code': item.item.code,
                    'item_name': item.item.name,
                    'location_id': item.location_id,
                    'location_name': item.location.name if item.location else '',
                    'batch_number': item.batch_number,
                    'quantity': str(item.quantity),
                    'unit_cost': str(item.unit_cost),
                    'amount': str(item.amount),
                } for item in items]
            }
            return JsonResponse({'code': 0, 'msg': 'success', 'data': data})
        else:
            return self.list(request)

    @transaction.atomic
    def create(self, request):
        try:
            data = json.loads(request.body)
            items_data = data.pop('items', [])

            form = StockInForm(data)
            if form.is_valid():
                stock_in = form.save(commit=False)
                if not data.get('code'):
                    stock_in.code = generate_code('IN')
                stock_in.save()

                total_amount = 0
                total_quantity = 0

                for item_data in items_data:
                    item_data['stock_in'] = stock_in.id
                    item_form = StockInItemForm(item_data)
                    if item_form.is_valid():
                        item = item_form.save()
                        total_amount += float(item.amount)
                        total_quantity += float(item.quantity)

                stock_in.total_amount = total_amount
                stock_in.total_quantity = total_quantity
                stock_in.save()

                return JsonResponse(
                    {'code': 0, 'msg': '创建成功', 'data': {'id': stock_in.id}})
            return JsonResponse({'code': 1, 'msg': form.errors})
        except Exception as e:
            logger.error(f"创建入库单失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    @transaction.atomic
    def check(self, request, pk):
        try:
            stock_in = get_object_or_404(StockIn, pk=pk)
            if stock_in.status != 1:
                return JsonResponse({'code': 1, 'msg': '只有待审核状态才能审核'})

            stock_in.status = 2
            stock_in.checker_id = request.session.get('admin_id', 1)
            stock_in.check_time = timezone.now()
            stock_in.save()

            return JsonResponse({'code': 0, 'msg': '审核成功'})
        except Exception as e:
            logger.error(f"审核入库单失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    @transaction.atomic
    def stock_in(self, request, pk):
        try:
            stock_in = get_object_or_404(StockIn, pk=pk)
            if stock_in.status != 2:
                return JsonResponse({'code': 1, 'msg': '只有已审核状态才能入库'})

            admin_id = request.session.get('admin_id', 1)
            admin = Admin.objects.get(pk=admin_id)

            with transaction.atomic():
                items = StockInItem.objects.filter(
                    stock_in=stock_in).select_for_update().select_related(
                    'item', 'location')

                for item in items:
                    inventory, created = Inventory.objects.get_or_create(
                        item=item.item,
                        warehouse=stock_in.warehouse,
                        location=item.location,
                        batch_number=item.batch_number or '',
                        defaults={
                            'quantity': 0,
                            'unit_cost': item.unit_cost
                        }
                    )

                    before_quantity = inventory.quantity
                    inventory.quantity += item.quantity
                    inventory.unit_cost = item.unit_cost
                    inventory.last_movement_date = timezone.now()
                    inventory.save()

                    StockTransaction.objects.create(
                        transaction_type='stock_in',
                        transaction_code=stock_in.code,
                        item=item.item,
                        warehouse=stock_in.warehouse,
                        location=item.location,
                        batch_number=item.batch_number,
                        quantity=item.quantity,
                        unit_cost=item.unit_cost,
                        amount=item.amount,
                        before_quantity=before_quantity,
                        after_quantity=inventory.quantity,
                        reference_type='StockIn',
                        reference_id=stock_in.id,
                        reference_code=stock_in.code,
                        operator=admin
                    )

                stock_in.status = 3
                stock_in.stocker = admin
                stock_in.stock_time = timezone.now()
                stock_in.save()

            return JsonResponse({'code': 0, 'msg': '入库成功'})
        except Exception as e:
            logger.error(f"入库操作失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})


class StockOutView(InventoryMixin):
    def list(self, request):
        queryset = StockOut.objects.select_related(
            'warehouse', 'customer', 'creator').all()

        status = request.GET.get('status')
        stock_out_type = request.GET.get('stock_out_type')

        if status:
            queryset = queryset.filter(status=status)
        if stock_out_type:
            queryset = queryset.filter(stock_out_type=stock_out_type)

        data = [{
            'id': so.id,
            'code': so.code,
            'stock_out_type': so.stock_out_type,
            'stock_out_type_display': so.get_stock_out_type_display(),
            'warehouse_id': so.warehouse_id,
            'warehouse_name': so.warehouse.name,
            'customer_id': so.customer_id,
            'customer_name': so.customer.name if so.customer else '',
            'total_amount': str(so.total_amount),
            'total_quantity': str(so.total_quantity),
            'status': so.status,
            'status_display': so.get_status_display(),
            'checker_name': so.checker.name if so.checker else '',
            'check_time': so.check_time.strftime('%Y-%m-%d %H:%M:%S') if so.check_time else '',
            'stocker_name': so.stocker.name if so.stocker else '',
            'stock_time': so.stock_time.strftime('%Y-%m-%d %H:%M:%S') if so.stock_time else '',
            'create_time': so.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        } for so in queryset]

        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})

    def get(self, request, pk=None):
        if pk:
            stock_out = get_object_or_404(StockOut, pk=pk)
            items = StockOutItem.objects.filter(
                stock_out=pk).select_related(
                'item', 'location')
            data = {
                'id': stock_out.id,
                'code': stock_out.code,
                'stock_out_type': stock_out.stock_out_type,
                'warehouse_id': stock_out.warehouse_id,
                'customer_id': stock_out.customer_id,
                'sales_order_id': stock_out.sales_order_id,
                'total_amount': str(stock_out.total_amount),
                'total_quantity': str(stock_out.total_quantity),
                'status': stock_out.status,
                'remark': stock_out.remark,
                'items': [{
                    'id': item.id,
                    'item_id': item.item_id,
                    'item_code': item.item.code,
                    'item_name': item.item.name,
                    'location_id': item.location_id,
                    'location_name': item.location.name if item.location else '',
                    'batch_number': item.batch_number,
                    'quantity': str(item.quantity),
                    'unit_cost': str(item.unit_cost),
                    'amount': str(item.amount),
                } for item in items]
            }
            return JsonResponse({'code': 0, 'msg': 'success', 'data': data})
        else:
            return self.list(request)

    @transaction.atomic
    def create(self, request):
        try:
            data = json.loads(request.body)
            items_data = data.pop('items', [])

            form = StockOutForm(data)
            if form.is_valid():
                stock_out = form.save(commit=False)
                if not data.get('code'):
                    stock_out.code = generate_code('OUT')
                stock_out.save()

                total_amount = 0
                total_quantity = 0

                for item_data in items_data:
                    item_data['stock_out'] = stock_out.id
                    item_form = StockOutItemForm(item_data)
                    if item_form.is_valid():
                        item = item_form.save()
                        total_amount += float(item.amount)
                        total_quantity += float(item.quantity)

                stock_out.total_amount = total_amount
                stock_out.total_quantity = total_quantity
                stock_out.save()

                return JsonResponse(
                    {'code': 0, 'msg': '创建成功', 'data': {'id': stock_out.id}})
            return JsonResponse({'code': 1, 'msg': form.errors})
        except Exception as e:
            logger.error(f"创建出库单失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    @transaction.atomic
    def check(self, request, pk):
        try:
            stock_out = get_object_or_404(StockOut, pk=pk)
            if stock_out.status != 1:
                return JsonResponse({'code': 1, 'msg': '只有待审核状态才能审核'})

            stock_out.status = 2
            stock_out.checker_id = request.session.get('admin_id', 1)
            stock_out.check_time = timezone.now()
            stock_out.save()

            return JsonResponse({'code': 0, 'msg': '审核成功'})
        except Exception as e:
            logger.error(f"审核出库单失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    @transaction.atomic
    def stock_out(self, request, pk):
        try:
            stock_out = get_object_or_404(StockOut, pk=pk)
            if stock_out.status != 2:
                return JsonResponse({'code': 1, 'msg': '只有已审核状态才能出库'})

            admin_id = request.session.get('admin_id', 1)
            admin = Admin.objects.get(pk=admin_id)

            with transaction.atomic():
                items = StockOutItem.objects.filter(
                    stock_out=stock_out).select_for_update().select_related(
                    'item', 'location')

                for item in items:
                    inventory = Inventory.objects.select_for_update().get(
                        item=item.item,
                        warehouse=stock_out.warehouse,
                        location=item.location,
                        batch_number=item.batch_number or ''
                    )

                    if inventory.quantity < item.quantity:
                        return JsonResponse(
                            {'code': 1, 'msg': f'物料{item.item.code}库存不足'})

                    before_quantity = inventory.quantity
                    inventory.quantity -= item.quantity
                    inventory.last_movement_date = timezone.now()
                    inventory.save()

                    StockTransaction.objects.create(
                        transaction_type='stock_out',
                        transaction_code=stock_out.code,
                        item=item.item,
                        warehouse=stock_out.warehouse,
                        location=item.location,
                        batch_number=item.batch_number,
                        quantity=-item.quantity,
                        unit_cost=item.unit_cost,
                        amount=-item.amount,
                        before_quantity=before_quantity,
                        after_quantity=inventory.quantity,
                        reference_type='StockOut',
                        reference_id=stock_out.id,
                        reference_code=stock_out.code,
                        operator=admin
                    )

                stock_out.status = 3
                stock_out.stocker = admin
                stock_out.stock_time = timezone.now()
                stock_out.save()

            return JsonResponse({'code': 0, 'msg': '出库成功'})
        except Inventory.DoesNotExist:
            return JsonResponse({'code': 1, 'msg': '库存记录不存在'})
        except Exception as e:
            logger.error(f"出库操作失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})


class StockTransferView(InventoryMixin):
    def list(self, request):
        queryset = StockTransfer.objects.select_related(
            'from_warehouse', 'to_warehouse', 'requester').all()

        status = request.GET.get('status')

        if status:
            queryset = queryset.filter(status=status)

        data = [{
            'id': st.id,
            'code': st.code,
            'from_warehouse_id': st.from_warehouse_id,
            'from_warehouse_name': st.from_warehouse.name,
            'to_warehouse_id': st.to_warehouse_id,
            'to_warehouse_name': st.to_warehouse.name,
            'total_quantity': str(st.total_quantity),
            'total_amount': str(st.total_amount),
            'status': st.status,
            'status_display': st.get_status_display(),
            'requester_name': st.requester.name if st.requester else '',
            'checker_name': st.checker.name if st.checker else '',
            'executor_name': st.executor.name if st.executor else '',
            'create_time': st.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        } for st in queryset]

        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})


class StockCheckView(InventoryMixin):
    def list(self, request):
        queryset = StockCheck.objects.select_related(
            'warehouse', 'checker').all()

        status = request.GET.get('status')

        if status:
            queryset = queryset.filter(status=status)

        data = [{
            'id': sc.id,
            'code': sc.code,
            'check_type': sc.check_type,
            'check_type_display': sc.get_check_type_display(),
            'warehouse_id': sc.warehouse_id,
            'warehouse_name': sc.warehouse.name,
            'total_items': sc.total_items,
            'checked_items': sc.checked_items,
            'status': sc.status,
            'status_display': sc.get_status_display(),
            'profit_amount': str(sc.profit_amount),
            'loss_amount': str(sc.loss_amount),
            'checker_name': sc.checker.name if sc.checker else '',
            'check_time': sc.check_time.strftime('%Y-%m-%d %H:%M:%S') if sc.check_time else '',
            'complete_time': sc.complete_time.strftime('%Y-%m-%d %H:%M:%S') if sc.complete_time else '',
            'create_time': sc.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        } for sc in queryset]

        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})


class PurchaseOrderView(InventoryMixin):
    def list(self, request):
        queryset = PurchaseOrder.objects.select_related(
            'supplier', 'warehouse', 'creator').all()

        status = request.GET.get('status')

        if status:
            queryset = queryset.filter(status=status)

        data = [{
            'id': po.id,
            'code': po.code,
            'order_type': po.order_type,
            'order_type_display': po.get_order_type_display(),
            'supplier_id': po.supplier_id,
            'supplier_name': po.supplier.name,
            'warehouse_id': po.warehouse_id,
            'warehouse_name': po.warehouse.name if po.warehouse else '',
            'total_amount': str(po.total_amount),
            'total_quantity': str(po.total_quantity),
            'received_amount': str(po.received_amount),
            'received_quantity': str(po.received_quantity),
            'order_date': po.order_date.strftime('%Y-%m-%d'),
            'expected_date': po.expected_date.strftime('%Y-%m-%d') if po.expected_date else '',
            'status': po.status,
            'status_display': po.get_status_display(),
            'creator_name': po.creator.name if po.creator else '',
            'create_time': po.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        } for po in queryset]

        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})


class SalesOrderView(InventoryMixin):
    def list(self, request):
        queryset = SalesOrder.objects.select_related(
            'customer', 'warehouse', 'creator').all()

        status = request.GET.get('status')

        if status:
            queryset = queryset.filter(status=status)

        data = [{
            'id': so.id,
            'code': so.code,
            'order_type': so.order_type,
            'order_type_display': so.get_order_type_display(),
            'customer_id': so.customer_id,
            'customer_name': so.customer.name,
            'warehouse_id': so.warehouse_id,
            'warehouse_name': so.warehouse.name if so.warehouse else '',
            'total_amount': str(so.total_amount),
            'total_quantity': str(so.total_quantity),
            'shipped_amount': str(so.shipped_amount),
            'shipped_quantity': str(so.shipped_quantity),
            'order_date': so.order_date.strftime('%Y-%m-%d'),
            'expected_date': so.expected_date.strftime('%Y-%m-%d') if so.expected_date else '',
            'status': so.status,
            'status_display': so.get_status_display(),
            'creator_name': so.creator.name if so.creator else '',
            'create_time': so.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        } for so in queryset]

        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})


class InventoryAlertView(InventoryMixin):
    def list(self, request):
        queryset = InventoryAlert.objects.select_related(
            'item', 'warehouse', 'handler').all()

        alert_type = request.GET.get('alert_type')
        status = request.GET.get('status')

        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        if status:
            queryset = queryset.filter(status=status)

        data = [{
            'id': alert.id,
            'item_id': alert.item_id,
            'item_code': alert.item.code,
            'item_name': alert.item.name,
            'warehouse_id': alert.warehouse_id,
            'warehouse_name': alert.warehouse.name,
            'alert_type': alert.alert_type,
            'alert_type_display': alert.get_alert_type_display(),
            'current_quantity': str(alert.current_quantity),
            'threshold_value': str(alert.threshold_value),
            'message': alert.message,
            'status': alert.status,
            'status_display': '已处理' if alert.status == 2 else ('已忽略' if alert.status == 3 else '未处理'),
            'handler_name': alert.handler.name if alert.handler else '',
            'handle_time': alert.handle_time.strftime('%Y-%m-%d %H:%M:%S') if alert.handle_time else '',
            'create_time': alert.create_time.strftime('%Y-%m-%d %H:%M:%S'),
        } for alert in queryset]

        return JsonResponse({'code': 0, 'msg': 'success',
                            'data': data, 'count': len(data)})


class InventoryReportView(InventoryMixin):
    def summary(self, request):
        try:
            warehouse_id = request.GET.get('warehouse_id')
            category_id = request.GET.get('category_id')

            queryset = Inventory.objects.select_related('item', 'warehouse')

            if warehouse_id:
                queryset = queryset.filter(warehouse_id=warehouse_id)
            if category_id:
                queryset = queryset.filter(item__category_id=category_id)

            summary = queryset.aggregate(
                total_items=Count('id', distinct=True),
                total_quantity=Sum('quantity'),
                total_value=Sum('total_cost')
            )

            by_category = queryset.values('item__category__name').annotate(
                quantity=Sum('quantity'),
                value=Sum('total_cost')
            )

            by_warehouse = queryset.values('warehouse__name').annotate(
                quantity=Sum('quantity'),
                value=Sum('total_cost')
            )

            data = {
                'summary': {
                    'total_items': summary['total_items'] or 0,
                    'total_quantity': str(summary['total_quantity'] or 0),
                    'total_value': str(summary['total_value'] or 0),
                },
                'by_category': list(by_category),
                'by_warehouse': list(by_warehouse),
            }

            return JsonResponse({'code': 0, 'msg': 'success', 'data': data})
        except Exception as e:
            logger.error(f"生成库存汇总报表失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})

    def transaction(self, request):
        try:
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            transaction_type = request.GET.get('transaction_type')

            queryset = StockTransaction.objects.select_related(
                'item', 'warehouse')

            if start_date:
                queryset = queryset.filter(create_time__gte=start_date)
            if end_date:
                queryset = queryset.filter(create_time__lte=end_date)
            if transaction_type:
                queryset = queryset.filter(transaction_type=transaction_type)

            summary = queryset.aggregate(
                total_in=Sum(
                    'quantity', filter=Q(
                        transaction_type='stock_in')), total_out=Sum(
                    'quantity', filter=Q(
                        transaction_type='stock_out')), )

            data = {
                'summary': {
                    'total_in': str(summary['total_in'] or 0),
                    'total_out': str(summary['total_out'] or 0),
                },
                'transactions': [{
                    'id': t.id,
                    'transaction_type': t.transaction_type,
                    'transaction_type_display': t.get_transaction_type_display(),
                    'item_code': t.item.code,
                    'item_name': t.item.name,
                    'warehouse_name': t.warehouse.name,
                    'quantity': str(t.quantity),
                    'create_time': t.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                } for t in queryset[:100]]
            }

            return JsonResponse({'code': 0, 'msg': 'success', 'data': data})
        except Exception as e:
            logger.error(f"生成库存变动报表失败: {e}")
            return JsonResponse({'code': 1, 'msg': str(e)})


def inventory_dashboard(request):
    return render(request, 'inventory/dashboard.html')


def warehouse_list(request):
    return render(request, 'inventory/warehouse_list.html')


def warehouse_form(request):
    return render(request, 'inventory/warehouse_form.html')


def location_list(request):
    return render(request, 'inventory/location_list.html')


def location_form(request):
    return render(request, 'inventory/location_form.html')


def category_list(request):
    return render(request, 'inventory/category_list.html')


def category_form(request):
    return render(request, 'inventory/category_form.html')


def item_list(request):
    return render(request, 'inventory/item_list.html')


def item_form(request):
    return render(request, 'inventory/item_form.html')


def inventory_list(request):
    return render(request, 'inventory/inventory_list.html')


def transaction_list(request):
    return render(request, 'inventory/transaction_list.html')


def stock_in_list(request):
    return render(request, 'inventory/stock_in_list.html')


def stock_in_form(request):
    return render(request, 'inventory/stock_in_form.html')


def stock_out_list(request):
    return render(request, 'inventory/stock_out_list.html')


def stock_out_form(request):
    return render(request, 'inventory/stock_out_form.html')


def transfer_list(request):
    return render(request, 'inventory/transfer_list.html')


def transfer_form(request):
    return render(request, 'inventory/transfer_form.html')


def check_list(request):
    return render(request, 'inventory/check_list.html')


def check_form(request):
    return render(request, 'inventory/check_form.html')


def purchase_order_list(request):
    return render(request, 'inventory/purchase_order_list.html')


def purchase_order_form(request):
    return render(request, 'inventory/purchase_order_form.html')


def sales_order_list(request):
    return render(request, 'inventory/sales_order_list.html')


def sales_order_form(request):
    return render(request, 'inventory/sales_order_form.html')


def alert_list(request):
    return render(request, 'inventory/alert_list.html')


def report_summary(request):
    return render(request, 'inventory/report_summary.html')


def report_transaction(request):
    return render(request, 'inventory/report_transaction.html')
