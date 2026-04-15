"""
数据一致性信号处理器
确保跨模块数据同步和一致性
"""
import logging
import traceback
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

# 导入所有需要的模型
from apps.customer.models import CustomerContract, CustomerOrder
from apps.project.models import Project
from apps.finance.models import OrderFinanceRecord, InvoiceRequest, Invoice

logger = logging.getLogger(__name__)
logger.info("数据集成信号处理器已加载")

# 定义数据集成服务


class DataIntegrationService:
    """
    数据集成服务类，处理跨模块的数据同步和一致性
    """

    def create_contract_with_project(self, contract):
        """创建合同并关联项目"""
        try:
            # 生成唯一的项目代码
            import uuid
            # 基于合同号或UUID生成唯一代码
            project_code = contract.contract_number if contract.contract_number else f"PROJ-{uuid.uuid4().hex[:8].upper()}"

            # 创建项目 - 不使用start_time和end_time字段，因为Project模型不支持
            project = Project.objects.create(
                name=f"项目-{contract.contract_number}",
                code=project_code,
                customer_id=contract.customer_id,
                contract_id=contract.id,
                budget=contract.amount,
                status=1,  # 使用数字状态，1表示'未开始'
                create_time=contract.create_time if contract.create_time else timezone.now()
            )
            logger.info(
                f"为合同 {contract.id} 创建项目 {project.id}，项目代码: {project_code}")
            return project
        except Exception as e:
            logger.error(f"创建项目失败: {str(e)}")
            raise

    def create_order_with_finance(self, contract):
        """创建订单并生成财务记录"""
        try:
            # 创建客户订单（待回款记录）
            order = CustomerOrder.objects.create(
                customer_id=contract.customer_id,
                contract_id=contract.id,
                order_number=f"ORD-{contract.contract_number}",
                amount=contract.amount,
                order_date=contract.sign_date or contract.create_time.date(),
                status='pending',
                create_time=contract.create_time if contract.create_time else timezone.now(),
                create_user_id=1  # 设置默认用户ID，需要根据实际情况调整
            )
            logger.info(f"为合同 {contract.id} 创建订单 {order.id}")

            # 创建财务记录 - 检查是否已存在
            try:
                # 先尝试查找现有财务记录
                finance_record = OrderFinanceRecord.objects.filter(
                    order=order).first()
                if finance_record:
                    # 更新现有记录
                    finance_record.total_amount = contract.amount
                    finance_record.payment_status = 'pending'
                    finance_record.due_date = contract.end_date
                    finance_record.save()
                    logger.info(f"更新订单 {order.id} 的财务记录 {finance_record.id}")
                else:
                    # 创建新记录
                    finance_record = OrderFinanceRecord.objects.create(
                        order=order,
                        total_amount=contract.amount,
                        paid_amount=0,
                        payment_status='pending',
                        due_date=contract.end_date
                    )
                    logger.info(f"为订单 {order.id} 创建财务记录 {finance_record.id}")
            except Exception as e:
                logger.error(f"创建或更新财务记录失败: {str(e)}")
                raise

            return order, finance_record
        except Exception as e:
            logger.error(f"创建订单和财务记录失败: {str(e)}")
            raise

    def create_invoice_request(self, order):
        """创建待开票记录"""
        try:
            # 获取系统用户作为默认申请人
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_user = User.objects.first()

            # 创建开票申请
            invoice_request = InvoiceRequest.objects.create(
                order=order,
                applicant=admin_user if admin_user else None,
                department_id=0,
                amount=order.amount,
                invoice_type=2,  # 默认普通发票
                invoice_title=order.customer.name if order.customer else "客户",
                reason="合同自动生成的开票申请",
                status='pending'
            )
            logger.info(f"为订单 {order.id} 创建开票申请 {invoice_request.id}")

            # 也可以创建发票草稿
            customer = order.customer
            if customer:
                invoice = Invoice.objects.create(
                    code=f"INV-{invoice_request.id}",
                    customer=customer,
                    contract=order.contract,
                    project=Project.objects.filter(
                        contract_id=order.contract_id).first(),
                    amount=order.amount,
                    did=0,
                    admin_id=admin_user.id if admin_user else 0,
                    open_status=0,
                    types=1,
                    invoice_type=2,
                    invoice_title=customer.name,
                    invoice_tax=customer.tax_number if hasattr(
                        customer,
                        'tax_number') else '',
                    enter_amount=0,
                    enter_status=0,
                    check_status=0,
                    create_time=int(
                        order.create_time.timestamp()) if order.create_time else int(
                        timezone.now().timestamp()))
                logger.info(f"为订单 {order.id} 创建发票草稿 {invoice.id}")

                # 关联开票申请和发票
                invoice_request.invoice = invoice
                invoice_request.save()

            return invoice_request
        except Exception as e:
            logger.error(f"创建开票申请失败: {str(e)}")
            # 不抛出异常，允许流程继续
            return None


# 创建服务实例
data_integration_service = DataIntegrationService()


@receiver(post_save, sender=CustomerContract)
def sync_contract_to_project(sender, instance, created, **kwargs):
    """
    同步合同到项目
    当合同保存时，自动创建或更新关联的项目、订单、财务记录和开票记录
    """
    try:
        logger.info(
            f"触发合同同步信号: ID={instance.id}, created={created}, status={instance.status}")

        # 只有已签署的合同才创建相关记录
        if instance.status == 'signed':
            # 修复合同可见性问题
            if hasattr(instance, 'delete_time') and instance.delete_time:
                instance.delete_time = 0
                instance.save(update_fields=['delete_time'])
                logger.info(f"修复合同 {instance.id} 的可见性")

            # 检查是否已有相关记录，避免重复创建
            project_exists = Project.objects.filter(
                contract_id=instance.id).exists()
            order_exists = CustomerOrder.objects.filter(
                contract_id=instance.id).exists()

            logger.info(
                f"合同 {instance.id} 检查: 项目存在={project_exists}, 订单存在={order_exists}")

            # 创建项目
            if not project_exists:
                project = data_integration_service.create_contract_with_project(
                    instance)
            else:
                project = Project.objects.get(contract_id=instance.id)
                logger.info(f"项目 {project.id} 已存在，跳过创建")

            # 创建订单和财务记录
            if not order_exists:
                order, finance_record = data_integration_service.create_order_with_finance(
                    instance)

                # 创建待开票记录
                data_integration_service.create_invoice_request(order)
            else:
                order = CustomerOrder.objects.get(contract_id=instance.id)
                logger.info(f"订单 {order.id} 已存在，跳过创建")

                # 检查是否有财务记录
                if not OrderFinanceRecord.objects.filter(order=order).exists():
                    finance_record = OrderFinanceRecord.objects.create(
                        order=order,
                        total_amount=instance.amount,
                        paid_amount=0,
                        payment_status='pending',
                        due_date=instance.end_date
                    )
                    logger.info(f"为订单 {order.id} 创建财务记录 {finance_record.id}")

                # 检查是否有待开票记录
                if not InvoiceRequest.objects.filter(
                        order=order).exists() and not Invoice.objects.filter(
                        contract_id=instance.id).exists():
                    data_integration_service.create_invoice_request(order)
        else:
            # 合同更新时，同步更新关联项目状态
            if hasattr(data_integration_service, 'update_contract_status'):
                data_integration_service.update_contract_status(
                    instance.id, instance.status)
            else:
                logger.warning(f"数据集成服务没有update_contract_status方法")

    except Exception as e:
        logger.error(f"同步合同到项目失败: {str(e)}")
        # 打印完整的异常堆栈
        logger.error(traceback.format_exc())


@receiver(post_save, sender=CustomerOrder)
def sync_order_to_finance(sender, instance, created, **kwargs):
    """
    当订单保存时，确保存在对应的财务记录
    实现订单与财务数据的自动同步
    """
    try:
        if created:
            # 新订单创建时，自动创建财务记录
            if not OrderFinanceRecord.objects.filter(order=instance).exists():
                OrderFinanceRecord.objects.create(
                    order=instance,
                    total_amount=instance.amount,
                    paid_amount=0,
                    payment_status='pending'
                )
                logger.info(f"为订单{instance.order_number}自动创建财务记录")
        else:
            # 订单更新时，如果金额变化，同步更新财务记录
            try:
                finance_record = OrderFinanceRecord.objects.get(order=instance)
                if finance_record.total_amount != instance.amount:
                    old_amount = finance_record.total_amount
                    finance_record.total_amount = instance.amount
                    finance_record.save()
                    logger.info(
                        f"订单{instance.order_number}金额变更，财务记录从{old_amount}更新为{instance.amount}")
            except OrderFinanceRecord.DoesNotExist:
                # 如果财务记录不存在，创建它
                OrderFinanceRecord.objects.create(
                    order=instance,
                    total_amount=instance.amount,
                    paid_amount=0,
                    payment_status='pending'
                )
                logger.info(f"订单{instance.order_number}存在但无财务记录，已创建")

    except Exception as e:
        logger.error(f"同步订单到财务失败: {str(e)}")


@receiver(post_save, sender=OrderFinanceRecord)
def sync_finance_to_order(sender, instance, created, **kwargs):
    """
    当财务记录更新时，同步更新订单的财务状态
    确保财务数据的一致性
    """
    try:
        # 更新订单的财务状态
        order = instance.order

        # 根据付款状态更新订单
        if instance.payment_status == 'paid':
            if order.finance_status != 'synced':
                order.finance_status = 'synced'
                order.save()
                logger.info(f"订单{order.order_number}财务状态更新为已同步")
        elif instance.payment_status == 'partial':
            if order.finance_status != 'synced':
                order.finance_status = 'synced'
                order.save()
                logger.info(f"订单{order.order_number}财务状态更新为已同步（部分付款）")

    except Exception as e:
        logger.error(f"同步财务到订单失败: {str(e)}")


@receiver(post_save, sender=Invoice)
def sync_invoice_to_related(sender, instance, created, **kwargs):
    """
    当发票创建或更新时，同步更新关联的订单和财务状态
    """
    try:
        # 如果发票关联了订单，更新订单的开票状态
        if hasattr(instance, 'invoice_request') and instance.invoice_request:
            order = instance.invoice_request.order
            if order.invoice_request_status == 'approved':
                order.invoice_request_status = 'requested'
                order.save()
                logger.info(
                    f"发票{instance.code}已创建，更新订单{order.order_number}开票状态")

    except Exception as e:
        logger.error(f"同步发票到相关记录失败: {str(e)}")


@receiver(pre_delete, sender=CustomerContract)
def prevent_delete_used_contract(sender, instance, **kwargs):
    """
    防止删除已被使用的合同
    确保数据完整性
    """
    # 检查是否有项目关联此合同
    if Project.objects.filter(contract=instance).exists():
        projects_count = Project.objects.filter(contract=instance).count()
        raise ValueError(
            f"无法删除合同 {instance.contract_number}，该合同已关联 {projects_count} 个项目")

    # 检查是否有订单关联此合同
    if CustomerOrder.objects.filter(contract=instance).exists():
        orders_count = CustomerOrder.objects.filter(contract=instance).count()
        raise ValueError(
            f"无法删除合同 {instance.contract_number}，该合同已关联 {orders_count} 个订单")

    # 检查是否有发票关联此合同
    if Invoice.objects.filter(contract=instance).exists():
        invoices_count = Invoice.objects.filter(contract=instance).count()
        raise ValueError(
            f"无法删除合同 {instance.contract_number}，该合同已关联 {invoices_count} 张发票")


@receiver(post_save, sender=Project)
def validate_project_contract_consistency(sender, instance, created, **kwargs):
    """
    验证项目与合同的一致性
    确保项目预算不超过合同金额
    """
    try:
        if instance.contract and instance.budget:
            # 确保比较的数据类型一致，避免字符串与Decimal比较错误
            budget = instance.budget
            contract_amount = instance.contract.amount

            # 如果contract_amount是字符串，转换为Decimal
            if isinstance(contract_amount, str):
                from decimal import Decimal
                try:
                    contract_amount = Decimal(contract_amount)
                except (ValueError, TypeError):
                    logger.error(f"合同金额格式错误: {contract_amount}")
                    return

            if budget > contract_amount:
                logger.warning(
                    f"项目{instance.name}预算{budget}超过合同金额{contract_amount}")

        # 确保项目与合同的客户一致
        if instance.contract and instance.customer and instance.customer != instance.contract.customer:
            raise ValueError(f"项目客户与合同客户不一致")

    except Exception as e:
        logger.error(f"验证项目合同一致性失败: {str(e)}")
        # 在更新时抛出异常，在创建时可以自动修正
        if not created:
            raise


logger.info("数据集成信号处理器已加载")
