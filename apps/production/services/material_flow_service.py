from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.inventory.models import (
    Inventory,
    InventoryItem,
    StockIn,
    StockInItem,
    StockOut,
    StockOutItem,
    StockTransaction,
    Warehouse,
    WarehouseLocation,
)
from apps.production.models import (
    BOMItem,
    MaterialIssue,
    MaterialIssueItem,
    MaterialRequest,
    MaterialRequestItem,
    MaterialReturn,
    MaterialReturnItem,
    MaterialScrap,
    MaterialScrapItem,
    ProductReceipt,
)


class MaterialFlowError(Exception):
    """生产物料流转业务异常"""


class MaterialFlowService:
    """生产与库存联动服务"""

    @staticmethod
    def generate_code(prefix):
        return f'{prefix}{timezone.now().strftime("%Y%m%d%H%M%S")}'

    @classmethod
    def ensure_document_code(cls, document, prefix):
        if not getattr(document, 'code', None):
            document.code = cls.generate_code(prefix)
        return document.code

    @staticmethod
    def get_default_warehouse():
        return Warehouse.objects.filter(is_default=True).first() or Warehouse.objects.first()

    @staticmethod
    def get_default_location(warehouse):
        if warehouse is None:
            return None
        return WarehouseLocation.objects.filter(warehouse=warehouse, status=1).order_by('id').first()

    @staticmethod
    def resolve_inventory_item(material_code, material_name=''):
        if material_code:
            item = InventoryItem.objects.filter(code=material_code).first()
            if item:
                return item
        if material_name:
            return InventoryItem.objects.filter(name=material_name).first()
        return None

    @classmethod
    def get_inventory_summary(cls, material_code, material_name=''):
        inventory_item = cls.resolve_inventory_item(material_code, material_name)
        if not inventory_item:
            return {
                'inventory_item': None,
                'total_quantity': Decimal('0'),
                'available_quantity': Decimal('0'),
            }
        summary = Inventory.objects.filter(item=inventory_item).aggregate(
            total_quantity=Sum('quantity'),
            available_quantity=Sum('available_quantity'),
        )
        return {
            'inventory_item': inventory_item,
            'total_quantity': summary['total_quantity'] or Decimal('0'),
            'available_quantity': summary['available_quantity'] or Decimal('0'),
        }

    @staticmethod
    def _to_decimal(value):
        if value is None:
            return Decimal('0')
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    @classmethod
    def _update_total_amount(cls, document, related_name, quantity_field):
        total_amount = Decimal('0')
        total_quantity = Decimal('0')
        for item in getattr(document, related_name).all():
            total_amount += cls._to_decimal(getattr(item, 'amount', 0))
            total_quantity += cls._to_decimal(getattr(item, quantity_field, 0))
        document.total_amount = total_amount
        if hasattr(document, 'total_quantity'):
            document.total_quantity = total_quantity
        document.save(update_fields=['total_amount'] + (['total_quantity'] if hasattr(document, 'total_quantity') else []))

    @classmethod
    def ensure_material_request_items(cls, material_request):
        if material_request.items.exists():
            cls._update_total_amount(material_request, 'items', 'request_quantity')
            return material_request.items.all()

        plan = material_request.production_plan
        if not plan or not plan.bom_id:
            return MaterialRequestItem.objects.none()

        base_quantity = cls._to_decimal(plan.quantity) if plan.quantity else Decimal('1')
        multiplier = base_quantity
        if material_request.production_task_id and base_quantity > 0:
            multiplier = cls._to_decimal(material_request.production_task.quantity) / base_quantity
        elif base_quantity <= 0:
            multiplier = Decimal('1')

        items = []
        for bom_item in plan.bom.items.all():
            request_quantity = cls._to_decimal(bom_item.quantity) * multiplier
            amount = request_quantity * cls._to_decimal(bom_item.unit_cost)
            items.append(MaterialRequestItem(
                material_request=material_request,
                bom_item=bom_item,
                material_name=bom_item.material_name,
                material_code=bom_item.material_code,
                specification=bom_item.specification,
                unit=bom_item.unit,
                request_quantity=request_quantity,
                unit_cost=bom_item.unit_cost,
                amount=amount,
            ))
        MaterialRequestItem.objects.bulk_create(items)
        cls._update_total_amount(material_request, 'items', 'request_quantity')
        return material_request.items.all()

    @classmethod
    def ensure_material_issue_items(cls, issue):
        if issue.items.exists():
            cls._update_total_amount(issue, 'items', 'issue_quantity')
            return issue.items.all()

        if issue.material_request_id:
            source_items = issue.material_request.items.all()
        elif issue.production_plan_id and issue.production_plan.bom_id:
            request = MaterialRequest.objects.create(
                production_plan=issue.production_plan,
                production_task=issue.production_plan.tasks.order_by('id').first(),
                code=cls.generate_code('REQ'),
                request_date=issue.issue_date,
                created_by=issue.created_by,
                description=f'由材料出库单 {issue.code} 自动生成',
                status=2,
            )
            source_items = cls.ensure_material_request_items(request)
            issue.material_request = request
            issue.save(update_fields=['material_request'])
        else:
            return MaterialIssueItem.objects.none()

        items = []
        for request_item in source_items:
            remaining = cls._to_decimal(request_item.request_quantity) - cls._to_decimal(request_item.issued_quantity)
            if remaining <= 0:
                continue
            amount = remaining * cls._to_decimal(request_item.unit_cost)
            items.append(MaterialIssueItem(
                material_issue=issue,
                material_request_item=request_item,
                material_name=request_item.material_name,
                material_code=request_item.material_code,
                specification=request_item.specification,
                unit=request_item.unit,
                issue_quantity=remaining,
                unit_cost=request_item.unit_cost,
                amount=amount,
            ))
        MaterialIssueItem.objects.bulk_create(items)
        cls._update_total_amount(issue, 'items', 'issue_quantity')
        return issue.items.all()

    @classmethod
    def _get_returned_quantity_map(cls, issue):
        quantity_map = {}
        for item in MaterialReturnItem.objects.filter(
                material_issue_item__material_issue=issue,
                material_return__status__in=[1, 2, 3]).exclude(material_return__status=4):
            key = item.material_issue_item_id
            quantity_map[key] = quantity_map.get(key, Decimal('0')) + cls._to_decimal(item.return_quantity)
        return quantity_map

    @classmethod
    def _get_scrapped_quantity_map(cls, issue):
        quantity_map = {}
        for item in MaterialScrapItem.objects.filter(
                material_issue_item__material_issue=issue,
                material_scrap__status__in=[1, 2, 3]).exclude(material_scrap__status=4):
            key = item.material_issue_item_id
            quantity_map[key] = quantity_map.get(key, Decimal('0')) + cls._to_decimal(item.scrap_quantity)
        return quantity_map

    @classmethod
    def ensure_material_return_items(cls, material_return):
        if material_return.items.exists():
            cls._update_total_amount(material_return, 'items', 'return_quantity')
            return material_return.items.all()
        if not material_return.material_issue_id:
            return MaterialReturnItem.objects.none()

        returned_map = cls._get_returned_quantity_map(material_return.material_issue)
        scrapped_map = cls._get_scrapped_quantity_map(material_return.material_issue)
        items = []
        for issue_item in material_return.material_issue.items.all():
            used_return = returned_map.get(issue_item.id, Decimal('0'))
            used_scrap = scrapped_map.get(issue_item.id, Decimal('0'))
            remaining = cls._to_decimal(issue_item.issue_quantity) - used_return - used_scrap
            if remaining <= 0:
                continue
            amount = remaining * cls._to_decimal(issue_item.unit_cost)
            items.append(MaterialReturnItem(
                material_return=material_return,
                material_issue_item=issue_item,
                material_name=issue_item.material_name,
                material_code=issue_item.material_code,
                specification=issue_item.specification,
                unit=issue_item.unit,
                return_quantity=remaining,
                unit_cost=issue_item.unit_cost,
                amount=amount,
            ))
        MaterialReturnItem.objects.bulk_create(items)
        cls._update_total_amount(material_return, 'items', 'return_quantity')
        return material_return.items.all()

    @classmethod
    def ensure_material_scrap_items(cls, material_scrap):
        if material_scrap.items.exists():
            cls._update_total_amount(material_scrap, 'items', 'scrap_quantity')
            return material_scrap.items.all()
        if not material_scrap.material_issue_id:
            return MaterialScrapItem.objects.none()

        returned_map = cls._get_returned_quantity_map(material_scrap.material_issue)
        scrapped_map = cls._get_scrapped_quantity_map(material_scrap.material_issue)
        items = []
        for issue_item in material_scrap.material_issue.items.all():
            used_return = returned_map.get(issue_item.id, Decimal('0'))
            used_scrap = scrapped_map.get(issue_item.id, Decimal('0'))
            remaining = cls._to_decimal(issue_item.issue_quantity) - used_return - used_scrap
            if remaining <= 0:
                continue
            amount = remaining * cls._to_decimal(issue_item.unit_cost)
            items.append(MaterialScrapItem(
                material_scrap=material_scrap,
                material_issue_item=issue_item,
                material_name=issue_item.material_name,
                material_code=issue_item.material_code,
                specification=issue_item.specification,
                unit=issue_item.unit,
                scrap_quantity=remaining,
                unit_cost=issue_item.unit_cost,
                amount=amount,
            ))
        MaterialScrapItem.objects.bulk_create(items)
        cls._update_total_amount(material_scrap, 'items', 'scrap_quantity')
        return material_scrap.items.all()

    @classmethod
    def ensure_product_receipt_defaults(cls, receipt):
        if receipt.completion_report_id and not receipt.production_plan_id:
            receipt.production_plan = receipt.completion_report.production_task.plan
        if receipt.completion_report_id and not receipt.receipt_quantity:
            receipt.receipt_quantity = receipt.completion_report.qualified_quantity
        if not receipt.code:
            receipt.code = cls.generate_code('PRD')
        return receipt

    @classmethod
    def _inventory_doc_code(cls, prefix, source_code):
        return f'{prefix}-{source_code}'[:50]

    @classmethod
    def _allocate_inventory(cls, inventory_item, warehouse, quantity):
        qty_needed = cls._to_decimal(quantity)
        records = Inventory.objects.select_for_update().filter(
            item=inventory_item,
            warehouse=warehouse,
            available_quantity__gt=0
        ).order_by('location_id', 'batch_number', 'id')
        allocations = []
        total_available = sum((record.available_quantity for record in records), Decimal('0'))
        if total_available < qty_needed:
            raise MaterialFlowError(f'物料 {inventory_item.code} 库存不足，可用 {total_available}，需求 {qty_needed}')

        for record in records:
            if qty_needed <= 0:
                break
            available = cls._to_decimal(record.available_quantity)
            take_qty = available if available <= qty_needed else qty_needed
            allocations.append((record, take_qty))
            qty_needed -= take_qty
        return allocations

    @classmethod
    def _sync_request_issued_quantity(cls, material_request):
        if not material_request:
            return
        for request_item in material_request.items.all():
            issued_quantity = MaterialIssueItem.objects.filter(
                material_request_item=request_item,
                material_issue__status=3,
            ).aggregate(total=Sum('issue_quantity'))['total'] or Decimal('0')
            request_item.issued_quantity = issued_quantity
            request_item.save(update_fields=['issued_quantity'])

    @classmethod
    def execute_material_issue(cls, issue, operator):
        if issue.status != 2:
            raise MaterialFlowError('只有已审核状态的材料出库单才能执行出库')
        warehouse = cls.get_default_warehouse()
        if warehouse is None:
            raise MaterialFlowError('未配置可用仓库，无法执行材料出库')

        with transaction.atomic():
            stock_out = StockOut.objects.create(
                code=cls._inventory_doc_code('PRODOUT', issue.code),
                stock_out_type='production',
                warehouse=warehouse,
                production_task=issue.material_request.production_task if issue.material_request_id else issue.production_plan.tasks.order_by('id').first(),
                total_amount=issue.total_amount,
                total_quantity=sum((cls._to_decimal(item.issue_quantity) for item in issue.items.all()), Decimal('0')),
                status=3,
                checker=operator,
                check_time=timezone.now(),
                stocker=operator,
                stock_time=timezone.now(),
                remark=f'生产材料出库：{issue.code}',
            )

            for issue_item in issue.items.all():
                inventory_item = cls.resolve_inventory_item(issue_item.material_code, issue_item.material_name)
                if inventory_item is None:
                    raise MaterialFlowError(f'物料 {issue_item.material_code or issue_item.material_name} 未在库存物料档案中建立')
                allocations = cls._allocate_inventory(inventory_item, warehouse, issue_item.issue_quantity)
                for inventory_record, allocated_qty in allocations:
                    amount = allocated_qty * cls._to_decimal(issue_item.unit_cost)
                    StockOutItem.objects.create(
                        stock_out=stock_out,
                        item=inventory_item,
                        location=inventory_record.location,
                        batch_number=inventory_record.batch_number,
                        quantity=allocated_qty,
                        unit_cost=issue_item.unit_cost,
                        amount=amount,
                        remark=f'来源生产出库单 {issue.code}',
                    )

                    before_quantity = inventory_record.quantity
                    inventory_record.quantity -= allocated_qty
                    inventory_record.last_movement_date = timezone.now()
                    inventory_record.save()

                    StockTransaction.objects.create(
                        transaction_type='stock_out',
                        transaction_code=stock_out.code,
                        item=inventory_item,
                        warehouse=warehouse,
                        location=inventory_record.location,
                        batch_number=inventory_record.batch_number,
                        quantity=-allocated_qty,
                        unit_cost=issue_item.unit_cost,
                        total_cost=-amount,
                        before_quantity=before_quantity,
                        after_quantity=inventory_record.quantity,
                        reference_type='MaterialIssue',
                        reference_id=issue.id,
                        reference_code=issue.code,
                        operator=operator,
                        remark=f'生产出库 {issue.code}',
                    )

            issue.status = 3
            issue.save(update_fields=['status'])
            cls._sync_request_issued_quantity(issue.material_request)
            return stock_out

    @classmethod
    def _execute_stock_in(cls, code_prefix, reference_type, source_code, source_id, operator, warehouse, items, stock_in_type='return', remark=''):
        location = cls.get_default_location(warehouse)
        stock_in = StockIn.objects.create(
            code=cls._inventory_doc_code(code_prefix, source_code),
            stock_in_type=stock_in_type,
            warehouse=warehouse,
            total_amount=sum((cls._to_decimal(item['amount']) for item in items), Decimal('0')),
            total_quantity=sum((cls._to_decimal(item['quantity']) for item in items), Decimal('0')),
            status=3,
            checker=operator,
            check_time=timezone.now(),
            stocker=operator,
            stock_time=timezone.now(),
            remark=remark,
        )

        for item in items:
            inventory_item = item['inventory_item']
            stock_in_item = StockInItem.objects.create(
                stock_in=stock_in,
                item=inventory_item,
                location=location,
                batch_number='',
                quantity=item['quantity'],
                unit_cost=item['unit_cost'],
                amount=item['amount'],
                remark=item.get('remark', ''),
            )

            inventory, _ = Inventory.objects.get_or_create(
                item=inventory_item,
                warehouse=warehouse,
                location=location,
                batch_number='',
                defaults={
                    'quantity': 0,
                    'unit_cost': item['unit_cost'],
                },
            )
            before_quantity = inventory.quantity
            inventory.quantity += item['quantity']
            inventory.unit_cost = item['unit_cost']
            inventory.last_movement_date = timezone.now()
            inventory.save()

            StockTransaction.objects.create(
                transaction_type='stock_in',
                transaction_code=stock_in.code,
                item=inventory_item,
                warehouse=warehouse,
                location=location,
                batch_number='',
                quantity=item['quantity'],
                unit_cost=item['unit_cost'],
                total_cost=item['amount'],
                before_quantity=before_quantity,
                after_quantity=inventory.quantity,
                reference_type=reference_type,
                reference_id=source_id,
                reference_code=source_code,
                operator=operator,
                remark=remark or source_code,
            )

        return stock_in

    @classmethod
    def execute_material_return(cls, material_return, operator):
        if material_return.status != 2:
            raise MaterialFlowError('只有已审核状态的退料单才能执行入库')
        warehouse = cls.get_default_warehouse()
        if warehouse is None:
            raise MaterialFlowError('未配置可用仓库，无法执行退料入库')

        items = []
        for return_item in material_return.items.all():
            inventory_item = cls.resolve_inventory_item(return_item.material_code, return_item.material_name)
            if inventory_item is None:
                raise MaterialFlowError(f'物料 {return_item.material_code or return_item.material_name} 未在库存物料档案中建立')
            items.append({
                'inventory_item': inventory_item,
                'quantity': cls._to_decimal(return_item.return_quantity),
                'unit_cost': cls._to_decimal(return_item.unit_cost),
                'amount': cls._to_decimal(return_item.amount),
                'remark': f'退料单 {material_return.code}',
            })
        with transaction.atomic():
            stock_in = cls._execute_stock_in(
                'PRODIN',
                'MaterialReturn',
                material_return.code,
                material_return.id,
                operator,
                warehouse,
                items,
                stock_in_type='return',
                remark=f'生产退料入库：{material_return.code}',
            )
            material_return.status = 3
            material_return.save(update_fields=['status'])
            return stock_in

    @classmethod
    def execute_material_scrap(cls, material_scrap, operator):
        if material_scrap.status != 2:
            raise MaterialFlowError('只有已审核状态的报废单才能执行报废')
        warehouse = cls.get_default_warehouse()
        if warehouse is None:
            raise MaterialFlowError('未配置可用仓库，无法执行物料报废')

        with transaction.atomic():
            stock_out = StockOut.objects.create(
                code=cls._inventory_doc_code('SCRAP', material_scrap.code),
                stock_out_type='scrap',
                warehouse=warehouse,
                production_task=material_scrap.production_plan.tasks.order_by('id').first(),
                total_amount=material_scrap.total_amount,
                total_quantity=sum((cls._to_decimal(item.scrap_quantity) for item in material_scrap.items.all()), Decimal('0')),
                status=3,
                checker=operator,
                check_time=timezone.now(),
                stocker=operator,
                stock_time=timezone.now(),
                remark=f'生产物料报废：{material_scrap.code}',
            )

            for scrap_item in material_scrap.items.all():
                inventory_item = cls.resolve_inventory_item(scrap_item.material_code, scrap_item.material_name)
                if inventory_item is None:
                    raise MaterialFlowError(f'物料 {scrap_item.material_code or scrap_item.material_name} 未在库存物料档案中建立')
                allocations = cls._allocate_inventory(inventory_item, warehouse, scrap_item.scrap_quantity)
                for inventory_record, allocated_qty in allocations:
                    amount = allocated_qty * cls._to_decimal(scrap_item.unit_cost)
                    StockOutItem.objects.create(
                        stock_out=stock_out,
                        item=inventory_item,
                        location=inventory_record.location,
                        batch_number=inventory_record.batch_number,
                        quantity=allocated_qty,
                        unit_cost=scrap_item.unit_cost,
                        amount=amount,
                        remark=f'来源生产报废单 {material_scrap.code}',
                    )

                    before_quantity = inventory_record.quantity
                    inventory_record.quantity -= allocated_qty
                    inventory_record.last_movement_date = timezone.now()
                    inventory_record.save()

                    StockTransaction.objects.create(
                        transaction_type='scrap',
                        transaction_code=stock_out.code,
                        item=inventory_item,
                        warehouse=warehouse,
                        location=inventory_record.location,
                        batch_number=inventory_record.batch_number,
                        quantity=-allocated_qty,
                        unit_cost=scrap_item.unit_cost,
                        total_cost=-amount,
                        before_quantity=before_quantity,
                        after_quantity=inventory_record.quantity,
                        reference_type='MaterialScrap',
                        reference_id=material_scrap.id,
                        reference_code=material_scrap.code,
                        operator=operator,
                        remark=f'生产报废 {material_scrap.code}',
                    )

            material_scrap.status = 3
            material_scrap.save(update_fields=['status'])
            return stock_out

    @classmethod
    def execute_product_receipt(cls, receipt, operator):
        if receipt.status != 2:
            raise MaterialFlowError('只有已审核状态的成品入库单才能执行入库')
        warehouse = cls.get_default_warehouse()
        if warehouse is None:
            raise MaterialFlowError('未配置可用仓库，无法执行成品入库')
        if not receipt.production_plan_id or not receipt.production_plan.product_id:
            raise MaterialFlowError('成品入库单缺少生产计划或关联产品')

        inventory_item = cls.resolve_inventory_item(
            receipt.production_plan.product.code,
            receipt.production_plan.product.name,
        )
        if inventory_item is None:
            raise MaterialFlowError(f'产品 {receipt.production_plan.product.code} 未在库存物料档案中建立')

        unit_cost = cls._to_decimal(receipt.production_plan.product.price)
        quantity = cls._to_decimal(receipt.receipt_quantity)
        amount = quantity * unit_cost

        with transaction.atomic():
            stock_in = cls._execute_stock_in(
                'FININ',
                'ProductReceipt',
                receipt.code,
                receipt.id,
                operator,
                warehouse,
                [{
                    'inventory_item': inventory_item,
                    'quantity': quantity,
                    'unit_cost': unit_cost,
                    'amount': amount,
                    'remark': f'成品入库单 {receipt.code}',
                }],
                stock_in_type='production',
                remark=f'生产成品入库：{receipt.code}',
            )
            receipt.status = 3
            receipt.save(update_fields=['status'])
            return stock_in

    @classmethod
    def build_bom_inventory_snapshot(cls, bom):
        snapshot = []
        for item in bom.items.all():
            summary = cls.get_inventory_summary(item.material_code, item.material_name)
            snapshot.append({
                'item': item,
                'inventory_item': summary['inventory_item'],
                'total_quantity': summary['total_quantity'],
                'available_quantity': summary['available_quantity'],
            })
        return snapshot
