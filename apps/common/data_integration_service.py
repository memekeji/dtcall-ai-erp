from django.db import transaction
from django.db.models import Q
from django.utils import timezone
import logging

from apps.customer.models import Customer, CustomerContract, CustomerOrder
from apps.project.models import Project
from apps.finance.models import OrderFinanceRecord, Invoice

logger = logging.getLogger(__name__)


class DataIntegrationService:
    """
    数据深度集成服务
    确保合同、订单、财务及项目相关的数据模型实现深度集成，消除数据孤岛
    提供统一的数据访问和同步接口
    """
    
    @staticmethod
    @transaction.atomic
    def create_contract_with_project(customer_id, contract_data, project_data=None):
        """
        创建合同并自动创建关联项目
        实现合同与项目的深度集成
        """
        try:
            # 验证客户存在
            customer = Customer.objects.get(id=customer_id)
            
            # 创建合同
            contract = CustomerContract.objects.create(
                customer=customer,
                **contract_data
            )
            
            # 如果提供了项目数据，则自动创建关联项目
            if project_data:
                project = Project.objects.create(
                    customer=customer,
                    contract=contract,
                    **project_data
                )
                logger.info(f"创建合同{contract.contract_number}并关联项目{project.name}")
                return contract, project
            
            logger.info(f"创建合同{contract.contract_number}")
            return contract, None
            
        except Exception as e:
            logger.error(f"创建合同与项目失败: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def create_order_with_finance(customer_id, contract_id, order_data):
        """
        创建订单并自动创建财务记录
        实现订单与财务的深度集成
        """
        try:
            # 验证客户和合同存在
            customer = Customer.objects.get(id=customer_id)
            contract = CustomerContract.objects.get(id=contract_id)
            
            # 创建订单
            order = CustomerOrder.objects.create(
                customer=customer,
                contract=contract,
                **order_data
            )
            
            # 自动创建财务记录
            finance_record = OrderFinanceRecord.objects.create(
                order=order,
                total_amount=order.amount,
                paid_amount=0,
                payment_status='pending'
            )
            
            logger.info(f"创建订单{order.order_number}并关联财务记录")
            return order, finance_record
            
        except Exception as e:
            logger.error(f"创建订单与财务记录失败: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def update_contract_status(contract_id, new_status):
        """
        更新合同状态并同步更新关联项目状态
        确保数据一致性
        """
        try:
            contract = CustomerContract.objects.get(id=contract_id)
            old_status = contract.status
            contract.status = new_status
            contract.save()
            
            # 同步更新关联项目状态
            project_status_mapping = {
                'draft': 'pending',
                'signed': 'approved',
                'executing': 'in_progress',
                'completed': 'completed',
                'terminated': 'terminated'
            }
            
            if new_status in project_status_mapping:
                Project.objects.filter(contract=contract).update(
                    status=project_status_mapping[new_status]
                )
                logger.info(f"合同{contract.contract_number}状态从{old_status}更新为{new_status}，同步更新关联项目")
            
            return contract
            
        except Exception as e:
            logger.error(f"更新合同状态失败: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def update_project_budget(project_id, new_budget):
        """
        更新项目预算并验证是否超过合同金额
        确保预算控制的一致性
        """
        try:
            project = Project.objects.select_related('contract').get(id=project_id)
            
            # 如果项目关联了合同，验证预算是否合理
            if project.contract and new_budget > project.contract.amount:
                logger.warning(f"项目{project.name}预算{new_budget}超过合同金额{project.contract.amount}")
                # 这里可以选择抛出异常或仅记录警告
                # raise ValueError(f"项目预算不能超过合同金额{project.contract.amount}")
            
            project.budget = new_budget
            project.save()
            logger.info(f"更新项目{project.name}预算为{new_budget}")
            
            return project
            
        except Exception as e:
            logger.error(f"更新项目预算失败: {str(e)}")
            raise
    
    @staticmethod
    def get_contract_related_data(contract_id):
        """
        获取合同相关的所有数据（项目、订单、财务记录、发票）
        提供统一的数据访问接口
        """
        try:
            contract = CustomerContract.objects.get(id=contract_id)
            
            # 获取关联项目
            projects = Project.objects.filter(contract=contract)
            
            # 获取关联订单
            orders = CustomerOrder.objects.filter(contract=contract)
            
            # 获取财务记录
            order_ids = orders.values_list('id', flat=True)
            finance_records = OrderFinanceRecord.objects.filter(order_id__in=order_ids)
            
            # 获取发票
            invoices = Invoice.objects.filter(contract=contract)
            
            # 计算统计数据
            total_orders_amount = sum(order.amount for order in orders)
            total_paid_amount = sum(record.paid_amount for record in finance_records)
            total_invoice_amount = sum(invoice.amount for invoice in invoices)
            
            return {
                'contract': contract,
                'projects': projects,
                'orders': orders,
                'finance_records': finance_records,
                'invoices': invoices,
                'statistics': {
                    'total_orders_amount': total_orders_amount,
                    'total_paid_amount': total_paid_amount,
                    'total_invoice_amount': total_invoice_amount,
                    'unpaid_amount': total_orders_amount - total_paid_amount
                }
            }
            
        except Exception as e:
            logger.error(f"获取合同相关数据失败: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def reconcile_financial_data():
        """
        执行财务数据对账
        确保订单、财务记录和发票数据的一致性
        """
        try:
            # 查找没有财务记录的订单
            orders_without_finance = CustomerOrder.objects.filter(
                ~Q(id__in=OrderFinanceRecord.objects.values_list('order_id', flat=True))
            )
            
            for order in orders_without_finance:
                OrderFinanceRecord.objects.create(
                    order=order,
                    total_amount=order.amount,
                    paid_amount=0,
                    payment_status='pending'
                )
                logger.info(f"为订单{order.order_number}创建缺失的财务记录")
            
            # 更新订单的财务状态
            for order in CustomerOrder.objects.all():
                try:
                    finance_record = OrderFinanceRecord.objects.get(order=order)
                    if finance_record.payment_status == 'paid':
                        order.finance_status = 'synced'
                        order.save()
                except OrderFinanceRecord.DoesNotExist:
                    pass
            
            return {
                'orders_reconciled': orders_without_finance.count()
            }
            
        except Exception as e:
            logger.error(f"财务数据对账失败: {str(e)}")
            raise


# 初始化数据集成服务实例
data_integration_service = DataIntegrationService()