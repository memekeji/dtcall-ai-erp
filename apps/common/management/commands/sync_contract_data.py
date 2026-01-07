from django.core.management.base import BaseCommand
from django.db.models import Q
from django.db import transaction
import logging
import traceback

from apps.customer.models import CustomerContract
from apps.common.signals import sync_contract_to_project

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    手动同步合同数据到相关模块的管理命令
    用于修复已存在的不一致数据，或手动触发数据同步
    """
    help = '同步合同数据到项目、订单和财务模块'
    
    def add_arguments(self, parser):
        parser.add_argument('--contract-id', type=int, help='指定单个合同ID进行同步')
        parser.add_argument('--all', action='store_true', help='同步所有合同数据')
        parser.add_argument('--signed-only', action='store_true', help='只同步已签署的合同')
        
    def handle(self, *args, **options):
        contract_id = options.get('contract_id')
        sync_all = options.get('all')
        signed_only = options.get('signed_only')
        
        if contract_id:
            # 同步单个合同
            try:
                contract = CustomerContract.objects.get(id=contract_id)
                self.stdout.write(f'开始同步合同: {contract.contract_number} ({contract.name})')
                
                # 强制修复合同可见性
                if hasattr(contract, 'delete_time') and contract.delete_time:
                    contract.delete_time = 0
                    contract.save(update_fields=['delete_time'])
                    self.stdout.write(f'已修复合同 {contract.id} 的可见性')
                    
                # 使用事务确保数据一致性
                with transaction.atomic():
                    # 直接调用信号处理函数
                    sync_contract_to_project(sender=CustomerContract, instance=contract, created=False, **{})
                    
                    # 验证创建的关联数据
                    self._verify_contract_relations(contract)
                    
                self.stdout.write(self.style.SUCCESS(f'合同 {contract.id} 同步完成'))
            except CustomerContract.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'合同 ID {contract_id} 不存在'))
                return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'合同 {contract.id} 同步失败: {str(e)}'))
                logger.error(f'同步合同 {contract.id} 失败: {str(e)}')
                logger.error(traceback.format_exc())
        elif sync_all:
            # 同步所有合同
            query = Q()
            if signed_only:
                query = Q(status='signed')
            
            # 排除已删除的合同
            if hasattr(CustomerContract, 'delete_time'):
                query &= Q(delete_time=0) | Q(delete_time__isnull=True)
            
            contracts = CustomerContract.objects.filter(query)
            total = contracts.count()
            self.stdout.write(f'开始同步 {total} 个合同...')
            
            success_count = 0
            failed_count = 0
            failed_contracts = []
            
            for contract in contracts:
                try:
                    self.stdout.write(f'同步合同: {contract.contract_number} ({contract.name})')
                    
                    # 强制修复合同可见性
                    if hasattr(contract, 'delete_time') and contract.delete_time:
                        contract.delete_time = 0
                        contract.save(update_fields=['delete_time'])
                        self.stdout.write(f'已修复合同 {contract.id} 的可见性')
                        
                    # 使用事务确保数据一致性
                    with transaction.atomic():
                        # 直接调用信号处理函数
                        sync_contract_to_project(sender=CustomerContract, instance=contract, created=False, **{})
                        
                        # 验证创建的关联数据
                        self._verify_contract_relations(contract)
                        
                    success_count += 1
                except Exception as e:
                    logger.error(f'同步合同 {contract.id} 失败: {str(e)}')
                    logger.error(traceback.format_exc())
                    self.stdout.write(self.style.ERROR(f'同步合同 {contract.id} 失败: {str(e)}'))
                    failed_count += 1
                    failed_contracts.append((contract.id, str(e)))
            
            self.stdout.write(self.style.SUCCESS(f'合同同步完成: 成功 {success_count}, 失败 {failed_count}'))
            
            if failed_contracts:
                self.stdout.write('\n失败的合同:')
                for contract_id, error in failed_contracts:
                    self.stdout.write(f'  - 合同ID {contract_id}: {error}')
        else:
            self.stdout.write(self.style.WARNING('请指定 --contract-id 或 --all 参数'))
            self.stdout.write('示例:')
            self.stdout.write('  python manage.py sync_contract_data --contract-id 1')
            self.stdout.write('  python manage.py sync_contract_data --all')
            self.stdout.write('  python manage.py sync_contract_data --all --signed-only')
    
    def _verify_contract_relations(self, contract):
        """验证合同关联数据是否正确创建"""
        try:
            from apps.project.models import Project
            from apps.customer.models import CustomerOrder
            from apps.finance.models import OrderFinanceRecord, InvoiceRequest, Invoice
            
            verification_msg = []
            
            # 检查项目
            project_exists = Project.objects.filter(contract_id=contract.id).exists()
            if project_exists:
                project = Project.objects.get(contract_id=contract.id)
                verification_msg.append(f'✓ 项目 {project.id}')
            else:
                verification_msg.append(f'✗ 项目')
            
            # 检查订单
            order_exists = CustomerOrder.objects.filter(contract_id=contract.id).exists()
            if order_exists:
                order = CustomerOrder.objects.get(contract_id=contract.id)
                verification_msg.append(f'✓ 订单 {order.id}')
                
                # 检查财务记录
                finance_exists = OrderFinanceRecord.objects.filter(order=order).exists()
                verification_msg.append(f'✓ 财务记录' if finance_exists else f'✗ 财务记录')
                
                # 检查开票申请
                invoice_request_exists = InvoiceRequest.objects.filter(order=order).exists()
                invoice_exists = Invoice.objects.filter(contract_id=contract.id).exists()
                if invoice_request_exists:
                    verification_msg.append(f'✓ 开票申请')
                elif invoice_exists:
                    verification_msg.append(f'✓ 发票草稿')
                else:
                    verification_msg.append(f'✗ 开票记录')
            else:
                verification_msg.append(f'✗ 订单')
                verification_msg.append(f'✗ 财务记录')
                verification_msg.append(f'✗ 开票记录')
            
            self.stdout.write(f'验证结果: {" ".join(verification_msg)}')
        except Exception as e:
            logger.warning(f'验证合同关联数据时出错: {str(e)}')
            self.stdout.write(f'验证失败: {str(e)}')