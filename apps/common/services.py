from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models import Sum
from django.db import transaction
import logging
import time
from datetime import datetime

# 初始化日志器
logger = logging.getLogger(__name__)

# 导入相关模型
User = get_user_model()

# 尝试导入其他模块中的模型
try:
    from apps.user.models import Admin
    from apps.user.models import EmployeeFile, EmployeeTransfer, RewardPunishment
    from apps.customer.models import Customer, CustomerContract, CustomerOrder, CustomerInvoice
    from apps.contract.models import Contract as ContractModule
    from apps.project.models import Project
    from apps.finance.models import Invoice, Payment, OrderFinanceRecord
except ImportError as e:
    logger.warning(f"模型导入失败: {e}")
    # 设置全局变量为None，避免未定义错误
    Admin = None
    Customer = None
    CustomerContract = None
    CustomerOrder = None
    CustomerInvoice = None
    ContractModule = None
    Project = None
    Invoice = None
    Payment = None
    OrderFinanceRecord = None
    EmployeeFile = None
    EmployeeTransfer = None
    RewardPunishment = None


class DataSyncService:
    """数据同步服务 - 实现合同、订单、财务及项目模块的深度集成"""

    @classmethod
    def sync_user_profile(cls, user_id=None):
        """同步用户档案数据"""
        try:
            # 检查Admin模型是否可用
            if 'Admin' not in globals():
                logger.warning("Admin模型不可用，无法同步用户档案")
                return

            users = Admin.objects.filter(
                id=user_id) if user_id else Admin.objects.all()

            for user in users:
                # 同步用户档案
                if 'EmployeeFile' in globals():
                    # EmployeeFile 模型没有 phone 和 email 字段，跳过这些字段的同步
                    try:
                        employee_file, created = EmployeeFile.objects.get_or_create(
                            employee=user, )
                        logger.debug(
                            f"员工档案：{'创建' if created else '更新'} - {user.username}")
                    except Exception as e:
                        logger.warning(f"创建员工档案失败 {user.username}: {e}")

            logger.info(f"用户档案同步完成，共同步 {users.count()} 个用户")
        except Exception as e:
            logger.error(f"同步用户档案失败: {str(e)}")

    @classmethod
    def sync_customer_business(cls, customer_id=None):
        """同步客户业务数据"""
        try:
            # 检查Customer模型是否可用
            if 'Customer' not in globals():
                logger.warning("Customer模型不可用，无法同步客户业务数据")
                return

            customers = Customer.objects.filter(
                id=customer_id) if customer_id else Customer.objects.all()

            for customer in customers:
                # 计算合同统计数据
                if 'CustomerContract' in globals():
                    contracts = CustomerContract.objects.filter(
                        customer=customer)
                    total_contracts = contracts.count()
                    active_contracts = contracts.filter(
                        status__in=['signed', 'executing']).count()
                    total_amount = contracts.aggregate(
                        Sum('amount'))['amount__sum'] or 0

                    # 计算订单统计数据
                    if 'CustomerOrder' in globals():
                        orders = CustomerOrder.objects.filter(
                            customer=customer)
                        orders.count()
                        completed_orders = orders.filter(
                            status='completed').count()
                        total_order_amount = orders.aggregate(
                            Sum('amount'))['amount__sum'] or 0

                    # 计算财务统计数据
                    if 'Invoice' in globals():
                        invoices = Invoice.objects.filter(
                            customer_id=customer.id)
                        total_invoice_amount = invoices.aggregate(
                            Sum('amount'))['amount__sum'] or 0
                        paid_invoice_amount = invoices.filter(
                            status='paid').aggregate(
                            Sum('amount'))['amount__sum'] or 0

                    # 计算项目统计数据
                    if 'Project' in globals():
                        projects = Project.objects.filter(
                            customer_id=customer.id)
                        projects.count()
                        completed_projects = projects.filter(
                            status='completed').count()

                    logger.info(
                        f"客户 {customer.name} 同步完成: 合同总数={total_contracts}, 总金额={total_amount}")

            logger.info(f"客户业务数据同步完成，共同步 {customers.count()} 个客户")
        except Exception as e:
            logger.error(f"同步客户业务数据失败: {str(e)}")

    @classmethod
    @transaction.atomic
    def sync_customer_contract_to_project(cls, contract_id):
        """同步客户合同到项目模块，自动创建或更新项目，确保深度数据集成"""
        try:
            # 检查必要的模型是否可用
            if 'CustomerContract' not in globals() or 'Project' not in globals():
                logger.warning("缺少必要的模型，无法同步合同到项目")
                return

            # 获取合同并验证状态
            contract = CustomerContract.objects.get(id=contract_id)

            # 只有有效的合同（未被删除）才进行同步
            if hasattr(contract, 'delete_time') and contract.delete_time > 0:
                logger.warning(f"合同 {contract_id} 已被删除，跳过项目同步")
                return

            # 确保合同有关联的客户
            if not contract.customer:
                logger.warning(f"合同 {contract_id} 没有关联客户，无法创建项目")
                return

            # 检查是否已存在关联项目
            existing_project = Project.objects.filter(
                contract_id=contract_id).first()

            # 根据合同状态映射项目状态
            status_map = {
                'signed': 'not_started',      # 已签署 -> 未开始
                'executing': 'in_progress',   # 执行中 -> 进行中
                'completed': 'completed',     # 已完成 -> 已完成
                'terminated': 'closed'        # 已终止 -> 已关闭
            }
            project_status = status_map.get(contract.status, 'not_started')

            if not existing_project:
                # 创建新项目
                project_data = {
                    'name': contract.name,
                    'customer_id': contract.customer.id,
                    'contract_id': contract_id,
                    'contract_number': contract.contract_number,  # 保存合同编号
                    'budget': contract.amount,
                    'status': project_status,
                    'create_user_id': contract.create_user.id if hasattr(contract, 'create_user') and contract.create_user else None,
                    'delete_time': 0  # 确保不被标记为删除
                }

                # 设置时间字段（如果有）
                if contract.sign_date:
                    project_data['start_time'] = contract.sign_date
                if contract.end_date:
                    project_data['end_time'] = contract.end_date

                project = Project.objects.create(**project_data)
                logger.info(f"为合同 {contract_id} 创建了新的项目 {project.id}")

                # 添加项目描述信息
                if hasattr(project, 'description'):
                    project.description = f"由合同自动创建: {contract.name}"
                    project.save()

            else:
                # 更新现有项目
                existing_project.name = contract.name
                existing_project.customer_id = contract.customer.id
                existing_project.budget = contract.amount
                existing_project.status = project_status  # 同步状态更新

                # 更新时间字段（如果有）
                if contract.sign_date:
                    existing_project.start_time = contract.sign_date
                if contract.end_date:
                    existing_project.end_time = contract.end_date

                # 确保合同编号已设置
                if hasattr(
                        existing_project,
                        'contract_number') and not existing_project.contract_number:
                    existing_project.contract_number = contract.contract_number

                existing_project.save()
                logger.info(
                    f"更新了合同 {contract_id} 的关联项目 {existing_project.id}，状态更新为: {project_status}")

            # 触发项目相关数据的同步
            try:
                if 'DataSyncService' in globals() and hasattr(
                        DataSyncService, 'sync_customer_business'):
                    DataSyncService.sync_customer_business(
                        contract.customer.id)
                    logger.info(f"已更新客户 {contract.customer.id} 的业务数据")
            except Exception as e:
                logger.warning(f"同步客户业务数据时发生警告: {str(e)}")

        except CustomerContract.DoesNotExist:
            logger.error(f"合同 {contract_id} 不存在")
        except Exception as e:
            logger.error(f"同步合同到项目失败: {str(e)}")
            raise

    @classmethod
    @transaction.atomic
    def sync_customer_order_to_finance(cls, order_id):
        """同步客户订单到财务模块，确保订单与财务数据深度集成，维护数据一致性"""
        try:
            # 检查必要的模型是否可用
            if 'CustomerOrder' not in globals() or 'Invoice' not in globals(
            ) or 'OrderFinanceRecord' not in globals():
                logger.warning("缺少必要的模型，无法同步订单到财务")
                return

            # 获取订单并验证状态
            order = CustomerOrder.objects.get(id=order_id)

            # 只有有效的订单（未被删除）才进行同步
            if hasattr(order, 'delete_time') and order.delete_time > 0:
                logger.warning(f"订单 {order_id} 已被删除，跳过财务同步")
                # 考虑将关联的财务记录标记为无效或取消
                try:
                    finance_record = OrderFinanceRecord.objects.filter(
                        order_id=order_id).first()
                    if finance_record and hasattr(
                            finance_record, 'status') and finance_record.status != 'cancelled':
                        finance_record.status = 'cancelled'
                        finance_record.save()
                        logger.info(f"已将被删除订单 {order_id} 的财务记录标记为已取消")
                except Exception as e:
                    logger.warning(f"取消已删除订单的财务记录时发生警告: {str(e)}")
                return

            # 确保订单有关联的客户
            if not order.customer:
                logger.warning(f"订单 {order_id} 没有关联客户，无法创建财务记录")
                return

            # 检查是否已存在关联的财务记录
            finance_record = OrderFinanceRecord.objects.filter(
                order_id=order_id).first()

            # 订单状态映射到支付状态
            status_map = {
                'created': 'unpaid',         # 已创建 -> 未支付
                'paid': 'paid',              # 已支付 -> 已支付
                'partial_paid': 'partial',   # 部分支付 -> 部分
                'refunded': 'refunded',      # 已退款 -> 已退款
                'cancelled': 'cancelled'     # 已取消 -> 已取消
            }
            payment_status = status_map.get(order.status, 'unpaid')

            # 准备财务记录数据
            finance_data = {
                'order_id': order_id,
                'customer_id': order.customer.id,
                'amount': order.amount,
                'status': payment_status
            }

            # 添加合同关联（如果有）
            if hasattr(order, 'contract_id') and order.contract_id:
                finance_data['contract_id'] = order.contract_id

            # 添加负责人信息（如果有）
            if hasattr(order, 'create_user_id') and order.create_user_id:
                finance_data['create_user_id'] = order.create_user_id

            if not finance_record:
                # 创建新的财务记录
                finance_record = OrderFinanceRecord.objects.create(
                    **finance_data)
                logger.info(f"为订单 {order_id} 创建了新的财务记录 {finance_record.id}")

                # 自动生成发票（根据订单状态）
                if order.status in ['completed', 'paid']:
                    # 检查是否已存在相关发票
                    existing_invoice = Invoice.objects.filter(
                        order_id=order_id).first()
                    if not existing_invoice:
                        invoice_data = {
                            'customer_id': order.customer.id,
                            'order_id': order_id,
                            'amount': order.amount,
                            'invoice_type': 2,  # 普通发票
                            'enter_status': 0,  # 未回款
                            'create_user_id': order.create_user.id if hasattr(order, 'create_user') and order.create_user else None
                        }
                        if hasattr(order, 'contract_id') and order.contract_id:
                            invoice_data['contract_id'] = order.contract_id

                        invoice = Invoice.objects.create(**invoice_data)
                        logger.info(f"为订单 {order_id} 自动创建了发票 {invoice.id}")
            else:
                # 更新现有财务记录
                for key, value in finance_data.items():
                    if hasattr(finance_record, key):
                        setattr(finance_record, key, value)

                finance_record.save()
                logger.info(
                    f"更新了订单 {order_id} 的关联财务记录 {finance_record.id}，状态更新为: {payment_status}")

                # 如果订单状态变更，更新相关发票状态
                try:
                    invoices = Invoice.objects.filter(order_id=order_id)
                    for invoice in invoices:
                        if payment_status == 'paid' and invoice.enter_status == 0:  # 未回款
                            invoice.enter_status = 2  # 全部回款
                            invoice.save()
                            logger.info(f"已将订单 {order_id} 的发票更新为已回款状态")
                except Exception as e:
                    logger.warning(f"更新发票状态时发生警告: {str(e)}")

            # 触发客户业务数据同步
            try:
                if 'DataSyncService' in globals() and hasattr(
                        DataSyncService, 'sync_customer_business'):
                    DataSyncService.sync_customer_business(order.customer.id)
                    logger.info(f"已更新客户 {order.customer.id} 的业务数据")
            except Exception as e:
                logger.warning(f"同步客户业务数据时发生警告: {str(e)}")

        except CustomerOrder.DoesNotExist:
            logger.error(f"订单 {order_id} 不存在")
        except Exception as e:
            logger.error(f"同步订单到财务失败: {str(e)}")
            raise

    @classmethod
    @transaction.atomic
    def sync_contract_module_to_customer_contract(cls, contract_module_id):
        """同步合同管理模块合同到客户合同，不存在时自动创建"""
        try:
            # 检查必要的模型是否可用
            if 'ContractModule' not in globals(
            ) or 'CustomerContract' not in globals() or 'Customer' not in globals():
                logger.warning("缺少必要的模型，无法同步合同管理模块合同到客户合同")
                return

            # 获取合同管理模块的合同
            contract_module = ContractModule.objects.get(id=contract_module_id)

            # 确保客户存在
            if not contract_module.customer_id:
                logger.warning(f"合同管理模块合同 {contract_module_id} 没有关联客户，无法同步")
                return

            # 查找对应的客户合同
            customer_contract = CustomerContract.objects.filter(
                contract_number=contract_module.code,
                customer_id=contract_module.customer_id
            ).first()

            if customer_contract:
                # 更新客户合同
                customer_contract.name = contract_module.name
                customer_contract.amount = contract_module.cost
                # 转换时间戳为日期对象
                if contract_module.sign_time:
                    customer_contract.sign_date = datetime.fromtimestamp(
                        contract_module.sign_time).date()
                if contract_module.end_time:
                    customer_contract.end_date = datetime.fromtimestamp(
                        contract_module.end_time).date()

                # 更新状态
                if contract_module.status == 1:
                    customer_contract.status = 'signed'
                elif contract_module.status == 2:
                    customer_contract.status = 'executing'
                elif contract_module.status == 3:
                    customer_contract.status = 'completed'
                elif contract_module.status == 4:
                    customer_contract.status = 'terminated'

                customer_contract.save()
                logger.info(
                    f"同步合同管理模块合同 {contract_module_id} 到客户合同 {customer_contract.id}")
            else:
                # 创建新的客户合同
                try:
                    customer = Customer.objects.get(
                        id=contract_module.customer_id)
                    # 准备创建客户合同的数据
                    contract_data = {
                        'customer': customer,
                        'name': contract_module.name,
                        'contract_number': contract_module.code,
                        'amount': contract_module.cost,
                        'delete_time': 0  # 确保不被标记为删除
                    }

                    # 设置时间和状态
                    if contract_module.sign_time:
                        contract_data['sign_date'] = datetime.fromtimestamp(
                            contract_module.sign_time).date()
                    if contract_module.end_time:
                        contract_data['end_date'] = datetime.fromtimestamp(
                            contract_module.end_time).date()

                    # 映射状态
                    status_map = {
                        1: 'signed',
                        2: 'executing',
                        3: 'completed',
                        4: 'terminated'
                    }
                    contract_data['status'] = status_map.get(
                        contract_module.status, 'draft')

                    # 创建客户合同
                    customer_contract = CustomerContract.objects.create(
                        **contract_data)
                    logger.info(
                        f"创建客户合同 {customer_contract.id} 对应合同管理模块合同 {contract_module_id}")

                    # 如果是已签署状态，同步到项目
                    if contract_data['status'] == 'signed':
                        try:
                            DataSyncService.sync_customer_contract_to_project(
                                customer_contract.id)
                            logger.info(
                                f"已自动将新建客户合同 {customer_contract.id} 同步到项目模块")
                        except Exception as e:
                            logger.warning(f"同步新建客户合同到项目失败: {str(e)}")

                except Customer.DoesNotExist:
                    logger.error(
                        f"客户 {contract_module.customer_id} 不存在，无法创建客户合同")
                except Exception as e:
                    logger.error(f"创建客户合同失败: {str(e)}")
                    raise

        except ContractModule.DoesNotExist:
            logger.error(f"合同管理模块合同 {contract_module_id} 不存在")
        except Exception as e:
            logger.error(f"同步合同管理模块合同到客户合同失败: {str(e)}")
            raise

    @classmethod
    @transaction.atomic
    def fix_data_inconsistencies(cls):
        """修复数据不一致问题 - 基于DataQualityMonitor检查结果实现多模块深度修复"""
        fixed_count = 0
        error_count = 0
        skipped_count = 0
        results = []

        try:
            # 检查数据质量问题
            issues = DataQualityMonitor.check_data_consistency()
            logger.info(f"开始修复数据不一致问题，共发现 {len(issues)} 类问题")

            for issue in issues:
                issue_type = issue.get('type')

                # 1. 修复缺少财务记录的订单
                if issue_type == 'missing_finance_records' and 'affected_ids' in issue:
                    result = cls._fix_missing_finance_records(
                        issue['affected_ids'])
                    fixed_count += result['fixed']
                    error_count += result['errors']
                    skipped_count += result['skipped']
                    results.append(result)

                # 2. 修复缺少项目的已签署合同
                elif issue_type == 'contract_missing_project' and 'affected_ids' in issue:
                    result = cls._fix_missing_projects(issue['affected_ids'])
                    fixed_count += result['fixed']
                    error_count += result['errors']
                    skipped_count += result['skipped']
                    results.append(result)

                # 3. 修复合同数据不一致问题
                elif issue_type == 'inconsistent_contract_data' and 'details' in issue:
                    result = cls._fix_inconsistent_contracts(issue['details'])
                    fixed_count += result['fixed']
                    error_count += result['errors']
                    skipped_count += result['skipped']
                    results.append(result)

                # 4. 修复项目状态与合同状态不一致
                elif issue_type == 'inconsistent_project_contract_status' and 'details' in issue:
                    result = cls._fix_inconsistent_project_statuses(
                        issue['details'])
                    fixed_count += result['fixed']
                    error_count += result['errors']
                    skipped_count += result['skipped']
                    results.append(result)

                # 5. 修复项目预算与合同金额不一致
                elif issue_type == 'inconsistent_project_budget' and 'details' in issue:
                    result = cls._fix_inconsistent_project_budgets(
                        issue['details'])
                    fixed_count += result['fixed']
                    error_count += result['errors']
                    skipped_count += result['skipped']
                    results.append(result)

                # 6. 修复订单金额与财务记录金额不一致
                elif issue_type == 'inconsistent_order_finance_amount' and 'details' in issue:
                    result = cls._fix_inconsistent_order_finance_amounts(
                        issue['details'])
                    fixed_count += result['fixed']
                    error_count += result['errors']
                    skipped_count += result['skipped']
                    results.append(result)

                # 7. 修复缺少双向合同映射
                elif issue_type == 'missing_contract_mapping' and 'details' in issue:
                    result = cls._fix_missing_contract_mappings(
                        issue['details'])
                    fixed_count += result['fixed']
                    error_count += result['errors']
                    skipped_count += result['skipped']
                    results.append(result)

                # 8. 修复财务与发票状态不一致
                elif issue_type == 'finance_invoice_status_mismatch' and 'affected_ids' in issue:
                    result = cls._fix_finance_invoice_statuses(
                        issue['affected_ids'])
                    fixed_count += result['fixed']
                    error_count += result['errors']
                    skipped_count += result['skipped']
                    results.append(result)

            logger.info(
                f"自动修复完成，成功修复 {fixed_count} 个问题，失败 {error_count} 个，跳过 {skipped_count} 个")

        except Exception as e:
            logger.error(f"自动修复过程中发生错误: {str(e)}")
            error_count += 1

        # 更新每日同步任务调用处需要的返回值
        return fixed_count

    @classmethod
    def _fix_missing_finance_records(cls, order_ids):
        """修复缺少财务记录的订单"""
        fixed = 0
        errors = 0
        skipped = 0

        # 限制每次处理的数量
        for order_id in order_ids[:50]:
            try:
                DataSyncService.sync_customer_order_to_finance(order_id)
                fixed += 1
                logger.info(f"已为订单 {order_id} 创建财务记录")
            except CustomerOrder.DoesNotExist:
                skipped += 1
                logger.warning(f"订单 {order_id} 不存在，跳过修复")
            except Exception as e:
                errors += 1
                logger.error(f"修复订单 {order_id} 财务记录失败: {str(e)}")

        return {
            'type': 'missing_finance_records',
            'fixed': fixed,
            'errors': errors,
            'skipped': skipped
        }

    @classmethod
    def _fix_missing_projects(cls, contract_ids):
        """修复缺少项目的已签署合同"""
        fixed = 0
        errors = 0
        skipped = 0

        # 限制每次处理的数量
        for contract_id in contract_ids[:50]:
            try:
                DataSyncService.sync_customer_contract_to_project(contract_id)
                fixed += 1
                logger.info(f"已为合同 {contract_id} 创建项目")
            except CustomerContract.DoesNotExist:
                skipped += 1
                logger.warning(f"合同 {contract_id} 不存在，跳过修复")
            except Exception as e:
                errors += 1
                logger.error(f"为合同 {contract_id} 创建项目失败: {str(e)}")

        return {
            'type': 'contract_missing_project',
            'fixed': fixed,
            'errors': errors,
            'skipped': skipped
        }

    @classmethod
    def _fix_inconsistent_contracts(cls, details):
        """修复合同数据不一致问题"""
        fixed = 0
        errors = 0
        skipped = 0

        # 限制每次处理的数量
        for detail in details[:50]:
            try:
                # 以合同管理模块的数据为准进行同步
                if 'contract_module_id' in detail:
                    DataSyncService.sync_contract_module_to_customer_contract(
                        detail['contract_module_id'])
                    fixed += 1
                    logger.info(
                        f"已修复合同 {detail.get('contract_id')} 与合同管理模块 {detail['contract_module_id']} 的数据一致性")
                else:
                    skipped += 1
                    logger.warning(f"合同修复缺少必要信息，跳过")
            except Exception as e:
                errors += 1
                logger.error(f"修复合同数据不一致失败: {str(e)}")

        return {
            'type': 'inconsistent_contract_data',
            'fixed': fixed,
            'errors': errors,
            'skipped': skipped
        }

    @classmethod
    def _fix_inconsistent_project_statuses(cls, details):
        """修复项目状态与合同状态不一致"""
        fixed = 0
        errors = 0
        skipped = 0

        # 限制每次处理的数量
        for detail in details[:50]:
            try:
                # 确保Project模型可用
                if 'Project' not in globals() or 'CustomerContract' not in globals():
                    skipped += 1
                    continue

                project = Project.objects.get(id=detail['project_id'])
                contract = CustomerContract.objects.get(
                    id=detail['contract_id'])

                # 跳过已删除的记录
                if project.delete_time > 0 or contract.delete_time > 0:
                    skipped += 1
                    continue

                # 状态映射关系
                contract_project_status_map = {
                    'signed': 'planning',
                    'executing': 'executing',
                    'completed': 'completed',
                    'terminated': 'terminated'
                }

                new_status = contract_project_status_map.get(contract.status)
                if new_status and new_status != project.status:
                    project.status = new_status
                    project.update_time = int(time.time())
                    project.save()
                    fixed += 1
                    logger.info(
                        f"已修复项目 {project.id} 状态，从 {detail['project_status']} 改为 {new_status}")
                else:
                    skipped += 1
            except (Project.DoesNotExist, CustomerContract.DoesNotExist):
                skipped += 1
                logger.warning(f"项目 {detail.get('project_id')} 或合同不存在，跳过修复")
            except Exception as e:
                errors += 1
                logger.error(
                    f"修复项目 {detail.get('project_id')} 状态不一致失败: {str(e)}")

        return {
            'type': 'inconsistent_project_contract_status',
            'fixed': fixed,
            'errors': errors,
            'skipped': skipped
        }

    @classmethod
    def _fix_inconsistent_project_budgets(cls, details):
        """修复项目预算与合同金额不一致"""
        fixed = 0
        errors = 0
        skipped = 0

        # 限制每次处理的数量
        for detail in details[:50]:
            try:
                # 确保Project模型可用
                if 'Project' not in globals():
                    skipped += 1
                    continue

                project = Project.objects.get(id=detail['project_id'])

                # 跳过已删除的项目
                if project.delete_time > 0:
                    skipped += 1
                    continue

                # 更新项目预算
                if detail.get('contract_amount') != project.budget:
                    project.budget = detail.get('contract_amount')
                    project.update_time = int(time.time())
                    project.save()
                    fixed += 1
                    logger.info(
                        f"已修复项目 {project.id} 预算，更新为 {detail.get('contract_amount')}")
                else:
                    skipped += 1
            except Project.DoesNotExist:
                skipped += 1
                logger.warning(f"项目 {detail.get('project_id')} 不存在，跳过修复")
            except Exception as e:
                errors += 1
                logger.error(
                    f"修复项目 {detail.get('project_id')} 预算不一致失败: {str(e)}")

        return {
            'type': 'inconsistent_project_budget',
            'fixed': fixed,
            'errors': errors,
            'skipped': skipped
        }

    @classmethod
    def _fix_inconsistent_order_finance_amounts(cls, details):
        """修复订单金额与财务记录金额不一致"""
        fixed = 0
        errors = 0
        skipped = 0

        # 限制每次处理的数量
        for detail in details[:50]:
            try:
                # 确保OrderFinanceRecord模型可用
                if 'OrderFinanceRecord' not in globals():
                    skipped += 1
                    continue

                finance_record = OrderFinanceRecord.objects.get(
                    id=detail['finance_record_id'])

                # 更新财务记录金额
                if detail.get('order_amount') != finance_record.amount:
                    finance_record.amount = detail.get('order_amount')
                    finance_record.update_time = int(time.time())
                    finance_record.save()
                    fixed += 1
                    logger.info(
                        f"已修复财务记录 {finance_record.id} 金额，更新为 {detail.get('order_amount')}")
                else:
                    skipped += 1
            except OrderFinanceRecord.DoesNotExist:
                skipped += 1
                logger.warning(
                    f"财务记录 {detail.get('finance_record_id')} 不存在，跳过修复")
            except Exception as e:
                errors += 1
                logger.error(
                    f"修复财务记录 {detail.get('finance_record_id')} 金额不一致失败: {str(e)}")

        return {
            'type': 'inconsistent_order_finance_amount',
            'fixed': fixed,
            'errors': errors,
            'skipped': skipped
        }

    @classmethod
    def _fix_missing_contract_mappings(cls, details):
        """修复缺少双向合同映射"""
        fixed = 0
        errors = 0
        skipped = 0

        # 限制每次处理的数量
        for detail in details[:50]:
            try:
                # 确保相关模型可用
                if 'CustomerContract' not in globals() or 'ContractModule' not in globals():
                    skipped += 1
                    continue

                # 检查修复动作
                if detail.get(
                        'fix_action') == 'create_contract_module' and 'contract_id' in detail:
                    # 从客户合同创建合同管理模块记录
                    customer_contract = CustomerContract.objects.get(
                        id=detail['contract_id'])

                    # 检查是否已存在
                    if not ContractModule.objects.filter(
                            code=customer_contract.contract_number).exists():
                        contract_module = ContractModule(
                            code=customer_contract.contract_number,
                            name=customer_contract.name,
                            customer_id=customer_contract.customer_id,
                            cost=customer_contract.amount,
                            status=1 if customer_contract.status == 'signed' else 0,
                            sign_time=int(
                                customer_contract.sign_date.timestamp()) if customer_contract.sign_date else int(
                                time.time()),
                            create_time=int(
                                time.time()),
                            update_time=int(
                                time.time()))
                        contract_module.save()
                        fixed += 1
                        logger.info(
                            f"已为客户合同 {customer_contract.id} 创建关联的合同管理模块记录")
                    else:
                        skipped += 1
                elif detail.get('fix_action') == 'create_customer_contract' and 'contract_module_id' in detail:
                    # 从合同管理模块创建客户合同记录
                    contract_module = ContractModule.objects.get(
                        id=detail['contract_module_id'])

                    # 检查是否已存在
                    if not CustomerContract.objects.filter(
                            contract_number=contract_module.contract_number).exists():
                        # 状态映射
                        status_map = {
                            1: 'signed',
                            2: 'executing',
                            3: 'completed',
                            4: 'terminated'
                        }

                        customer_contract = CustomerContract(
                            customer_id=contract_module.customer_id,
                            contract_number=contract_module.code,
                            name=contract_module.name,
                            amount=contract_module.cost,
                            status=status_map.get(
                                contract_module.status,
                                'draft'),
                            sign_date=datetime.fromtimestamp(
                                contract_module.sign_time).date() if contract_module.sign_time else None,
                            create_time=int(
                                time.time()),
                            update_time=int(
                                time.time()))
                        customer_contract.save()
                        fixed += 1
                        logger.info(
                            f"已为合同管理模块 {contract_module.id} 创建关联的客户合同记录")
                    else:
                        skipped += 1
                else:
                    skipped += 1
                    logger.warning(
                        f"跳过合同映射修复，未知的修复动作: {detail.get('fix_action')}")
            except (CustomerContract.DoesNotExist, ContractModule.DoesNotExist):
                skipped += 1
                logger.warning(f"相关合同记录不存在，跳过修复")
            except Exception as e:
                errors += 1
                logger.error(f"修复合同映射失败: {str(e)}")

        return {
            'type': 'missing_contract_mapping',
            'fixed': fixed,
            'errors': errors,
            'skipped': skipped
        }

    @classmethod
    def _fix_finance_invoice_statuses(cls, order_ids):
        """修复财务与发票状态不一致"""
        fixed = 0
        errors = 0
        skipped = 0

        try:
            # 确保CustomerInvoice模型可用
            if 'CustomerInvoice' not in globals():
                logger.warning("无法导入CustomerInvoice模型，跳过发票状态修复")
                return {
                    'type': 'finance_invoice_status_mismatch',
                    'fixed': 0,
                    'errors': 0,
                    'skipped': len(order_ids[:50])
                }

            # 限制每次处理的数量
            for order_id in order_ids[:50]:
                try:
                    invoice = CustomerInvoice.objects.get(order_id=order_id)
                    invoice.status = 'paid'
                    invoice.update_time = int(time.time())
                    invoice.save()
                    fixed += 1
                    logger.info(f"已修复订单 {order_id} 的发票状态为已付款")
                except CustomerInvoice.DoesNotExist:
                    skipped += 1
                    logger.warning(f"订单 {order_id} 的发票不存在，跳过修复")
                except Exception as e:
                    errors += 1
                    logger.error(f"修复订单 {order_id} 的发票状态失败: {str(e)}")
        except Exception as e:
            logger.error(f"发票状态修复过程中发生错误: {str(e)}")
            errors += len(order_ids[:50])

        return {
            'type': 'finance_invoice_status_mismatch',
            'fixed': fixed,
            'errors': errors,
            'skipped': skipped
        }

# 注册信号处理函数 - 确保模型存在时才注册


def register_signal_handlers():
    """动态注册信号处理函数，确保模型存在时才注册"""
    signal_handlers = []

    # 注册用户档案同步信号
    if Admin is not None:
        try:
            @receiver(post_save, sender=Admin)
            def sync_user_profile_on_save(sender, instance, created, **kwargs):
                """用户保存时同步档案"""
                DataSyncService.sync_user_profile(instance.id)
            signal_handlers.append('sync_user_profile_on_save')
        except Exception as e:
            logger.warning(f"注册用户档案同步信号失败: {e}")

    # 注册客户合同同步信号
    if CustomerContract is not None:
        try:
            @receiver(post_save, sender=CustomerContract)
            def sync_customer_business_on_customer_contract_save(
                    sender, instance, created, **kwargs):
                """客户合同保存时同步客户业务数据"""
                DataSyncService.sync_customer_business(instance.customer.id)
                # 如果是新创建的合同或状态变为已签署，同步到项目模块
                if created or instance.status == 'signed':
                    DataSyncService.sync_customer_contract_to_project(
                        instance.id)
            signal_handlers.append(
                'sync_customer_business_on_customer_contract_save')
        except Exception as e:
            logger.warning(f"注册客户合同同步信号失败: {e}")

    # 注册合同管理模块同步信号
    if ContractModule is not None:
        try:
            @receiver(post_save, sender=ContractModule)
            def sync_contract_module_to_customer(sender, instance, **kwargs):
                """合同管理模块合同保存时同步到客户模块"""
                # 尝试同步到客户合同模块
                DataSyncService.sync_contract_module_to_customer_contract(
                    instance.id)
                # 更新相关客户的业务数据
                if instance.customer_id:
                    DataSyncService.sync_customer_business(
                        instance.customer_id)
            signal_handlers.append('sync_contract_module_to_customer')
        except Exception as e:
            logger.warning(f"注册合同管理模块同步信号失败: {e}")

    # 注册客户订单同步信号
    if CustomerOrder is not None:
        try:
            @receiver(post_save, sender=CustomerOrder)
            def sync_order_to_finance_on_save(
                    sender, instance, created, **kwargs):
                """客户订单保存时同步到财务模块"""
                # 同步订单到财务
                DataSyncService.sync_customer_order_to_finance(instance.id)
                # 更新相关客户的业务数据
                DataSyncService.sync_customer_business(instance.customer.id)
            signal_handlers.append('sync_order_to_finance_on_save')
        except Exception as e:
            logger.warning(f"注册客户订单同步信号失败: {e}")

    # 注册发票同步信号
    if Invoice is not None:
        try:
            @receiver(post_save, sender=Invoice)
            def sync_customer_business_on_invoice_save(
                    sender, instance, **kwargs):
                """发票保存时同步客户业务数据"""
                DataSyncService.sync_customer_business(instance.customer_id)
            signal_handlers.append('sync_customer_business_on_invoice_save')
        except Exception as e:
            logger.warning(f"注册发票同步信号失败: {e}")

    # 注册付款记录同步信号
    if Payment is not None:
        try:
            @receiver(post_save, sender=Payment)
            def sync_customer_business_on_payment_save(
                    sender, instance, **kwargs):
                """付款记录保存时同步客户业务数据"""
                # 如果付款关联了客户，直接同步
                if hasattr(instance, 'customer_id') and instance.customer_id:
                    DataSyncService.sync_customer_business(
                        instance.customer_id)
                # 如果付款关联了订单，通过订单找到客户
                elif hasattr(instance, 'order_id') and instance.order_id:
                    try:
                        order = CustomerOrder.objects.get(id=instance.order_id)
                        DataSyncService.sync_customer_business(
                            order.customer.id)
                    except (NameError, CustomerOrder.DoesNotExist):
                        pass
                # 如果付款关联了合同，通过合同找到客户
                elif hasattr(instance, 'contract_id') and instance.contract_id:
                    try:
                        contract = CustomerContract.objects.get(
                            id=instance.contract_id)
                        DataSyncService.sync_customer_business(
                            contract.customer.id)
                    except (NameError, CustomerContract.DoesNotExist):
                        pass
            signal_handlers.append('sync_customer_business_on_payment_save')
        except Exception as e:
            logger.warning(f"注册付款记录同步信号失败: {e}")

    # 注册员工调动同步信号
    if EmployeeTransfer is not None:
        try:
            @receiver(post_save, sender=EmployeeTransfer)
            def sync_user_department_on_transfer(sender, instance, **kwargs):
                """员工调动时同步部门信息"""
                if instance.status == 'approved':
                    user = instance.employee
                    user.department = instance.to_department
                    user.save()
            signal_handlers.append('sync_user_department_on_transfer')
        except Exception as e:
            logger.warning(f"注册员工调动同步信号失败: {e}")

    logger.info(f"成功注册 {len(signal_handlers)} 个信号处理函数")
    return signal_handlers


# 尝试注册信号处理函数
register_signal_handlers()


class DataSyncTask:
    """数据同步任务"""

    @classmethod
    def daily_sync(cls):
        """每日数据同步任务"""
        logger.info("开始每日数据同步...")
        start_time = time.time()

        # 同步用户档案
        DataSyncService.sync_user_profile()
        logger.info("用户档案同步完成")

        # 同步客户业务数据
        DataSyncService.sync_customer_business()
        logger.info("客户业务数据同步完成")

        # 修复数据不一致问题
        fixed_count = DataSyncService.fix_data_inconsistencies()
        logger.info(f"数据修复完成，修复了 {fixed_count} 个问题")

        # 清理过期缓存
        cls.clear_expired_cache()
        logger.info("缓存清理完成")

        duration = time.time() - start_time
        logger.info(f"每日数据同步完成，耗时 {duration:.2f} 秒")

    @classmethod
    def clear_expired_cache(cls):
        """清理过期缓存"""
        # 清理特定前缀的缓存
        # 注意：Django的cache.delete_many不支持通配符，这里只是示例
        cache_keys = [
            'customer_summary_*',
            'employee_summary_*',
            'department_stats_*',
        ]

        # 在实际应用中，可能需要使用支持通配符删除的缓存后端
        # 或者维护一个键列表来跟踪所有缓存键
        logger.info(f"计划清理 {len(cache_keys)} 类缓存数据")


class CommonService:
    """公共服务类 - 提供通用的工具函数"""

    @staticmethod
    def get_page_size(request, default=20):
        """获取分页大小

        Args:
            request: Django请求对象
            default: 默认分页大小

        Returns:
            int: 分页大小
        """
        from apps.system.config_service import config_service

        page_size_param = request.GET.get('limit')
        if page_size_param and page_size_param.isdigit():
            return int(page_size_param)

        return config_service.get_int_config('default_page_size', default)

    @staticmethod
    def get_paginated_data(queryset, request, page_size=None, context=None):
        """获取分页数据

        Args:
            queryset: 要分页的查询集
            request: Django请求对象
            page_size: 每页数量，如果为None则从系统配置读取
            context: 额外的上下文数据

        Returns:
            dict: 包含分页对象和上下文数据的字典
        """
        from django.core.paginator import Paginator
        from apps.system.config_service import config_service

        # 如果page_size为None，从系统配置读取
        if page_size is None:
            page_size = config_service.get_int_config('default_page_size', 20)

        # 处理page_size参数
        page_size_param = request.GET.get('page_size')
        if page_size_param and page_size_param.isdigit():
            page_size = int(page_size_param)

        paginator = Paginator(queryset, page_size)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # 构建上下文
        result = {
            'page_obj': page_obj,
        }

        # 添加额外的上下文数据
        if context:
            result.update(context)

        return result


class DataQualityMonitor:
    """数据质量监控 - 实现多模块深度集成的一致性检查"""

    @classmethod
    def check_data_consistency(cls):
        """检查数据一致性 - 实现合同、订单、财务、项目等多模块深度集成检查"""
        issues = []

        try:
            # 1. 检查用户-员工档案一致性
            if 'Admin' in globals() and 'EmployeeFile' in globals():
                users_without_profile = Admin.objects.filter(
                    employee_file__isnull=True)
                if users_without_profile.exists():
                    issues.append({
                        'type': 'missing_profile',
                        'count': users_without_profile.count(),
                        'message': f"{users_without_profile.count()}个用户缺少员工档案"
                    })

            # 2. 检查客户合同-项目一致性 (增强)
            if 'CustomerContract' in globals() and 'Project' in globals():
                # 查找已签署但没有关联项目的合同
                contracts_without_project = CustomerContract.objects.filter(
                    status__in=[
                        'signed', 'executing'], delete_time=0).exclude(
                    id__in=Project.objects.values_list(
                        'contract_id', flat=True))

                if contracts_without_project.exists():
                    issues.append({
                        'type': 'contract_missing_project',
                        'count': contracts_without_project.count(),
                        'message': f"{contracts_without_project.count()}个已签署合同缺少关联项目",
                        'affected_ids': list(contracts_without_project.values_list('id', flat=True))
                    })

                # 检查项目状态与合同状态一致性
                cls._check_project_contract_status_consistency(issues)

                # 检查项目预算与合同金额一致性
                cls._check_project_budget_contract_amount_consistency(issues)

            # 3. 检查订单-财务记录一致性 (增强)
            if 'CustomerOrder' in globals() and 'OrderFinanceRecord' in globals():
                # 查找没有关联财务记录的订单
                orders_without_finance = CustomerOrder.objects.filter(
                    delete_time=0
                ).exclude(
                    id__in=OrderFinanceRecord.objects.values_list(
                        'order_id', flat=True)
                )

                if orders_without_finance.exists():
                    issues.append({
                        'type': 'missing_finance_records',
                        'count': orders_without_finance.count(),
                        'message': f"{orders_without_finance.count()}个订单缺少财务记录",
                        'affected_ids': list(orders_without_finance.values_list('id', flat=True))
                    })

                # 检查订单金额与财务记录金额一致性
                cls._check_order_finance_amount_consistency(issues)

            # 4. 合同管理模块与客户合同一致性检查 (增强)
            if 'CustomerContract' in globals() and 'ContractModule' in globals():
                inconsistent_contracts = []
                missing_contract_mappings = []

                # 4.1 双向检查 - 客户合同到合同管理模块
                customer_contracts = CustomerContract.objects.filter(delete_time=0)[
                    :200]
                for customer_contract in customer_contracts:
                    try:
                        # 查找对应的合同管理模块合同
                        contract_module = ContractModule.objects.filter(
                            code=customer_contract.contract_number,
                            customer_id=customer_contract.customer_id,
                            delete_time=0
                        ).first()

                        if contract_module:
                            # 检查金额是否一致
                            if abs(float(customer_contract.amount) -
                                   float(contract_module.cost)) > 0.01:
                                inconsistent_contracts.append({
                                    'contract_id': customer_contract.id,
                                    'contract_module_id': contract_module.id,
                                    'inconsistency_type': 'amount',
                                    'customer_contract_amount': customer_contract.amount,
                                    'contract_module_amount': contract_module.cost,
                                    'fix_action': 'sync_from_contract_module'
                                })

                            # 检查状态是否一致
                            status_map = {
                                'signed': 1,
                                'executing': 2,
                                'completed': 3,
                                'terminated': 4
                            }

                            if status_map.get(
                                    customer_contract.status) != contract_module.status:
                                inconsistent_contracts.append({
                                    'contract_id': customer_contract.id,
                                    'contract_module_id': contract_module.id,
                                    'inconsistency_type': 'status',
                                    'customer_contract_status': customer_contract.status,
                                    'contract_module_status': contract_module.status,
                                    'fix_action': 'sync_from_contract_module'
                                })

                            # 检查时间信息一致性
                            if customer_contract.sign_date and contract_module.sign_time:
                                contract_date = datetime.fromtimestamp(
                                    contract_module.sign_time).date()
                                if customer_contract.sign_date != contract_date:
                                    inconsistent_contracts.append({
                                        'contract_id': customer_contract.id,
                                        'contract_module_id': contract_module.id,
                                        'inconsistency_type': 'sign_date',
                                        'fix_action': 'sync_from_contract_module'
                                    })
                        else:
                            # 记录缺少对应合同管理模块记录的情况
                            missing_contract_mappings.append({
                                'contract_id': customer_contract.id,
                                'contract_number': customer_contract.contract_number,
                                'customer_id': customer_contract.customer_id,
                                'fix_action': 'create_contract_module'
                            })
                    except Exception as e:
                        logger.error(
                            f"检查合同 {customer_contract.id} 一致性失败: {str(e)}")

                # 4.2 双向检查 - 合同管理模块到客户合同
                contract_modules = ContractModule.objects.filter(delete_time=0)[
                    :200]
                for contract_module in contract_modules:
                    try:
                        # 查找对应的客户合同
                        customer_contract = CustomerContract.objects.filter(
                            contract_number=contract_module.code,
                            customer_id=contract_module.customer_id,
                            delete_time=0
                        ).first()

                        if not customer_contract and contract_module.customer_id:
                            # 记录缺少对应客户合同的情况
                            missing_contract_mappings.append({
                                'contract_module_id': contract_module.id,
                                'contract_number': contract_module.code,
                                'customer_id': contract_module.customer_id,
                                'fix_action': 'create_customer_contract'
                            })
                    except Exception as e:
                        logger.error(
                            f"检查合同管理模块 {contract_module.id} 一致性失败: {str(e)}")

                if inconsistent_contracts:
                    issues.append({
                        'type': 'inconsistent_contract_data',
                        'count': len(inconsistent_contracts),
                        'message': f"{len(inconsistent_contracts)}个合同数据不一致",
                        'details': inconsistent_contracts
                    })

                if missing_contract_mappings:
                    issues.append({
                        'type': 'missing_contract_mapping',
                        'count': len(missing_contract_mappings),
                        'message': f"{len(missing_contract_mappings)}个合同缺少双向映射关系",
                        'details': missing_contract_mappings
                    })

            # 5. 项目与任务一致性检查
            if 'Project' in globals():
                cls._check_project_task_consistency(issues)

            # 6. 财务与发票一致性检查
            if 'OrderFinanceRecord' in globals() and 'Invoice' in globals():
                cls._check_finance_invoice_consistency(issues)

            # 7. 检查客户业务数据完整性
            if 'Customer' in globals():
                cls._check_customer_data_completeness(issues)

        except Exception as e:
            logger.error(f"数据一致性检查失败: {str(e)}")
            issues.append({
                'type': 'check_error',
                'message': f"数据一致性检查过程中发生错误: {str(e)}"
            })

        return issues

    @classmethod
    def _check_project_contract_status_consistency(cls, issues):
        """检查项目状态与合同状态一致性"""
        try:
            # 状态映射关系
            contract_project_status_map = {
                'signed': ['init', 'planning'],
                'executing': ['executing'],
                'completed': ['completed'],
                'terminated': ['suspended', 'terminated']
            }

            # 查询不一致的项目-合同状态
            inconsistent_projects = []
            projects_with_contract = Project.objects.filter(
                contract_id__isnull=False,
                delete_time=0
            )

            for project in projects_with_contract:
                try:
                    contract = CustomerContract.objects.get(
                        id=project.contract_id)
                    # 检查合同状态对应的项目状态是否匹配
                    allowed_statuses = contract_project_status_map.get(
                        contract.status, [])
                    if not allowed_statuses or project.status not in allowed_statuses:
                        inconsistent_projects.append({
                            'project_id': project.id,
                            'contract_id': project.contract_id,
                            'project_status': project.status,
                            'contract_status': contract.status,
                            'allowed_project_statuses': allowed_statuses,
                            'fix_action': 'update_project_status'
                        })
                except CustomerContract.DoesNotExist:
                    # 项目引用了不存在的合同
                    inconsistent_projects.append({
                        'project_id': project.id,
                        'contract_id': project.contract_id,
                        'issue': 'project_refers_nonexistent_contract',
                        'fix_action': 'remove_invalid_reference'
                    })

            if inconsistent_projects:
                issues.append({
                    'type': 'inconsistent_project_contract_status',
                    'count': len(inconsistent_projects),
                    'message': f"{len(inconsistent_projects)}个项目与合同状态不一致",
                    'details': inconsistent_projects
                })
        except Exception as e:
            logger.error(f"检查项目-合同状态一致性失败: {str(e)}")

    @classmethod
    def _check_project_budget_contract_amount_consistency(cls, issues):
        """检查项目预算与合同金额一致性"""
        try:
            inconsistent_budgets = []
            projects_with_contract = Project.objects.filter(
                contract_id__isnull=False,
                delete_time=0
            )

            for project in projects_with_contract:
                try:
                    contract = CustomerContract.objects.get(
                        id=project.contract_id)
                    # 检查预算与合同金额是否偏差过大
                    if abs(
                        float(
                            project.budget) -
                        float(
                            contract.amount)) > 0.01:
                        inconsistent_budgets.append({
                            'project_id': project.id,
                            'contract_id': project.contract_id,
                            'project_budget': project.budget,
                            'contract_amount': contract.amount,
                            'fix_action': 'update_project_budget'
                        })
                except CustomerContract.DoesNotExist:
                    pass

            if inconsistent_budgets:
                issues.append({
                    'type': 'inconsistent_project_budget',
                    'count': len(inconsistent_budgets),
                    'message': f"{len(inconsistent_budgets)}个项目预算与合同金额不一致",
                    'details': inconsistent_budgets
                })
        except Exception as e:
            logger.error(f"检查项目预算与合同金额一致性失败: {str(e)}")

    @classmethod
    def _check_order_finance_amount_consistency(cls, issues):
        """检查订单金额与财务记录金额一致性"""
        try:
            inconsistent_amounts = []
            orders_with_finance = CustomerOrder.objects.filter(
                delete_time=0
            )

            for order in orders_with_finance:
                try:
                    finance_record = OrderFinanceRecord.objects.get(
                        order_id=order.id)
                    # 检查金额是否一致
                    if abs(float(order.amount) -
                           float(finance_record.amount)) > 0.01:
                        inconsistent_amounts.append({
                            'order_id': order.id,
                            'finance_record_id': finance_record.id,
                            'order_amount': order.amount,
                            'finance_record_amount': finance_record.amount,
                            'fix_action': 'update_finance_record_amount'
                        })
                except OrderFinanceRecord.DoesNotExist:
                    pass

            if inconsistent_amounts:
                issues.append({
                    'type': 'inconsistent_order_finance_amount',
                    'count': len(inconsistent_amounts),
                    'message': f"{len(inconsistent_amounts)}个订单金额与财务记录不一致",
                    'details': inconsistent_amounts
                })
        except Exception as e:
            logger.error(f"检查订单金额与财务记录一致性失败: {str(e)}")

    @classmethod
    def _check_project_task_consistency(cls, issues):
        """检查项目与任务一致性"""
        try:
            # 这里可以扩展为实际的任务模型检查
            # 当前先实现基本框架
            issues.append({
                'type': 'project_task_check_framework',
                'message': "项目任务一致性检查框架已实现，可根据实际任务模型扩展"
            })
        except Exception as e:
            logger.error(f"检查项目任务一致性失败: {str(e)}")

    @classmethod
    def _check_finance_invoice_consistency(cls, issues):
        """检查财务与发票一致性"""
        try:
            # 检查已付款但发票未更新的情况
            try:
                from customer.models import CustomerInvoice
                paid_finances_with_unpaid_invoices = OrderFinanceRecord.objects.filter(
                    status='paid').exclude(
                    order_id__in=CustomerInvoice.objects.filter(
                        status='paid').values_list(
                        'order_id', flat=True))

                if paid_finances_with_unpaid_invoices.exists():
                    issues.append({
                        'type': 'finance_invoice_status_mismatch',
                        'count': paid_finances_with_unpaid_invoices.count(),
                        'message': f"{paid_finances_with_unpaid_invoices.count()}个财务记录已付款但发票状态未更新",
                        'affected_ids': list(paid_finances_with_unpaid_invoices.values_list('order_id', flat=True))
                    })
            except ImportError:
                pass

            # 检查发票金额与财务记录一致性
            inconsistent_invoices = []
            invoices = Invoice.objects.filter(delete_time=0)[:100]

            for invoice in invoices:
                try:
                    finance_record = OrderFinanceRecord.objects.get(
                        order_id=invoice.order_id)
                    if abs(
                        float(
                            invoice.amount) -
                        float(
                            finance_record.amount)) > 0.01:
                        inconsistent_invoices.append({
                            'invoice_id': invoice.id,
                            'finance_record_id': finance_record.id,
                            'invoice_amount': invoice.amount,
                            'finance_record_amount': finance_record.amount,
                            'fix_action': 'update_invoice_amount'
                        })
                except OrderFinanceRecord.DoesNotExist:
                    pass

            if inconsistent_invoices:
                issues.append({
                    'type': 'inconsistent_invoice_amount',
                    'count': len(inconsistent_invoices),
                    'message': f"{len(inconsistent_invoices)}个发票金额与财务记录不一致",
                    'details': inconsistent_invoices
                })
        except Exception as e:
            logger.error(f"检查财务与发票一致性失败: {str(e)}")

    @classmethod
    def _check_customer_data_completeness(cls, issues):
        """检查客户业务数据完整性"""
        try:
            # 检查客户关联数据的完整性
            if 'CustomerContract' in globals() and 'CustomerOrder' in globals():
                customers_with_contracts = set(CustomerContract.objects.filter(
                    delete_time=0
                ).values_list('customer_id', flat=True))

                customers_with_orders = set(CustomerOrder.objects.filter(
                    delete_time=0
                ).values_list('customer_id', flat=True))

                # 查找有合同但没有订单的客户
                customers_with_contracts_only = customers_with_contracts - customers_with_orders
                if customers_with_contracts_only:
                    issues.append({
                        'type': 'customer_contract_without_orders',
                        'count': len(customers_with_contracts_only),
                        'message': f"{len(customers_with_contracts_only)}个客户有合同但没有订单记录",
                        'affected_ids': list(customers_with_contracts_only)
                    })
        except Exception as e:
            logger.error(f"检查客户数据完整性失败: {str(e)}")


class CacheService:
    """缓存服务 - 优化系统性能"""

    @staticmethod
    def get_customer_summary(customer_id):
        """获取客户汇总数据并缓存"""
        cache_key = f"customer_summary_{customer_id}"
        data = cache.get(cache_key)

        if not data:
            try:
                # 检查Customer和ContractModule模型是否可用
                if 'Customer' not in globals() or 'ContractModule' not in globals():
                    logger.warning("Customer或ContractModule模型不可用，无法获取客户汇总数据")
                    return {}

                # 获取客户对象
                try:
                    customer = Customer.objects.get(id=customer_id)
                except Customer.DoesNotExist:
                    logger.warning(f"客户 {customer_id} 不存在")
                    return {}

                # 计算客户汇总数据
                contracts = ContractModule.objects.filter(customer=customer)
                total_contracts = contracts.count()
                total_amount = contracts.aggregate(
                    Sum('amount'))['amount__sum'] or 0

                # 计算已付款金额
                paid_amount = 0
                if 'Payment' in globals():
                    contract_ids = contracts.values_list('id', flat=True)
                    paid_amount = Payment.objects.filter(
                        contract_id__in=contract_ids, status='paid').aggregate(
                        Sum('amount'))['amount__sum'] or 0

                data = {
                    'total_contracts': total_contracts,
                    'total_amount': total_amount,
                    'paid_amount': paid_amount,
                    'unpaid_amount': total_amount - paid_amount,
                    'payment_rate': round((paid_amount / total_amount) * 100, 2) if total_amount > 0 else 0,
                    # 其他汇总数据
                }

                # 缓存1小时
                cache.set(cache_key, data, 3600)

            except Exception as e:
                logger.error(f"获取客户 {customer_id} 汇总数据失败: {str(e)}")
                data = {}

        return data

    @staticmethod
    def get_employee_summary(employee_id):
        """获取员工汇总数据并缓存"""
        cache_key = f"employee_summary_{employee_id}"
        data = cache.get(cache_key)

        if not data:
            try:
                # 检查Admin和RewardPunishment模型是否可用
                if 'Admin' not in globals():
                    logger.warning("Admin模型不可用，无法获取员工汇总数据")
                    return {}

                # 获取员工对象
                try:
                    employee = Admin.objects.get(id=employee_id)
                except Admin.DoesNotExist:
                    logger.warning(f"员工 {employee_id} 不存在")
                    return {}

                data = {
                    'name': employee.username,
                    'department': employee.department.name if employee.department else '',
                    'position': employee.position.name if employee.position else '',
                    'hire_date': str(employee.hire_date) if hasattr(employee, 'hire_date') else '',
                    # 其他员工汇总数据
                }

                # 如果有奖惩模型，计算奖惩次数
                if 'RewardPunishment' in globals():
                    data['total_rewards'] = RewardPunishment.objects.filter(
                        employee=employee, type='reward').count()
                    data['total_punishments'] = RewardPunishment.objects.filter(
                        employee=employee, type='punishment').count()

                # 缓存1小时
                cache.set(cache_key, data, 3600)

            except Exception as e:
                logger.error(f"获取员工 {employee_id} 汇总数据失败: {str(e)}")
                data = {}

        return data
