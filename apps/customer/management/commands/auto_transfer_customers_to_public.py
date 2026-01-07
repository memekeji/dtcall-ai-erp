import time
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from django.db.models import Q
from apps.customer.models import Customer
from apps.system.config_service import config_service
from apps.user.models import SystemLog
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = '自动将符合条件的客户流转到公海'

    def handle(self, *args, **options):
        # 获取配置的流转规则天数
        no_follow_days = config_service.get_int_config('customer_no_follow_days', 30)
        no_deal_days = config_service.get_int_config('customer_no_deal_days', 90)
        
        self.stdout.write(f'开始执行客户自动流转公海任务...')
        self.stdout.write(f'配置规则：无跟进记录 {no_follow_days} 天流转，无成交 {no_deal_days} 天流转')
        
        # 检查是否启用流转规则
        follow_rule_enabled = no_follow_days > 0
        deal_rule_enabled = no_deal_days > 0
        
        if not follow_rule_enabled and not deal_rule_enabled:
            self.stdout.write(f'所有流转规则均未启用，任务结束')
            return
        
        # 计算时间阈值
        now = datetime.now()
        follow_threshold = now - timedelta(days=no_follow_days) if follow_rule_enabled else None
        deal_threshold = now - timedelta(days=no_deal_days) if deal_rule_enabled else None
        
        transferred_no_follow_count = 0
        transferred_no_deal_count = 0
        
        # 1. 处理无跟进记录的客户
        if follow_rule_enabled:
            follow_threshold_timestamp = int(follow_threshold.timestamp())
            
            # 获取所有非公海、非废弃且超过指定天数无跟进记录的客户
            no_follow_customers = Customer.objects.filter(
                Q(belong_uid__gt=0) &  # 非公海客户
                Q(discard_time=0) &     # 非废弃客户
                Q(follow_time__lt=follow_threshold_timestamp) &  # 超过指定天数无跟进记录
                Q(is_lock=False)        # 未锁定
            )
            
            for customer in no_follow_customers:
                # 检查是否有已成交的订单或合同
                has_completed_order = False
                has_effective_contract = False
                
                if deal_rule_enabled:
                    has_completed_order = customer.orders.filter(
                        status='completed',
                        order_date__gt=deal_threshold
                    ).exists()
                    
                    has_effective_contract = customer.contracts.filter(
                        Q(status__in=['signed', 'executing', 'completed']),
                        sign_date__gt=deal_threshold
                    ).exists()
                
                # 如果有已成交的订单或合同，则不流转
                if has_completed_order or has_effective_contract:
                    continue
                
                # 流转到公海
                customer.belong_uid = 0
                customer.belong_time = 0
                customer.distribute_time = 0
                customer.share_ids = ''  # 清空共享人员，确保客户完全进入公海
                customer.update_time = timezone.now()
                customer.save()
                
                # 记录操作日志
                SystemLog.objects.create(
                    user=None,  # 系统操作
                    log_type='update',
                    module='customer',
                    action=f'客户自动流转公海',
                    content=f'客户 {customer.name} 因超过 {no_follow_days} 天无跟进记录自动流转到公海',
                    ip_address='127.0.0.1'
                )
                
                transferred_no_follow_count += 1
        
        # 2. 处理无成交的客户
        if deal_rule_enabled:
            # 获取所有非公海、非废弃且超过指定天数无成交的客户
            no_deal_customers = Customer.objects.filter(
                Q(belong_uid__gt=0) &  # 非公海客户
                Q(discard_time=0) &     # 非废弃客户
                Q(is_lock=False)        # 未锁定
            )
            
            for customer in no_deal_customers:
                # 检查是否有已成交的订单或合同
                has_recent_order = customer.orders.filter(
                    status='completed',
                    order_date__gt=deal_threshold
                ).exists()
                
                has_recent_contract = customer.contracts.filter(
                    Q(status__in=['signed', 'executing', 'completed']),
                    sign_date__gt=deal_threshold
                ).exists()
                
                # 如果没有近期成交记录，则流转到公海
                if not has_recent_order and not has_recent_contract:
                    customer.belong_uid = 0
                    customer.belong_time = 0
                    customer.distribute_time = 0
                    customer.share_ids = ''  # 清空共享人员，确保客户完全进入公海
                    customer.update_time = timezone.now()
                    customer.save()
                    
                    # 记录操作日志
                    SystemLog.objects.create(
                        user=None,  # 系统操作
                        log_type='update',
                        module='customer',
                        action=f'客户自动流转公海',
                        content=f'客户 {customer.name} 因超过 {no_deal_days} 天无成交自动流转到公海',
                        ip_address='127.0.0.1'
                    )
                    
                    transferred_no_deal_count += 1
        
        # 3. 去重统计
        total_transferred = transferred_no_follow_count + transferred_no_deal_count
        
        self.stdout.write(f'无跟进记录流转客户数：{transferred_no_follow_count}')
        self.stdout.write(f'无成交流转客户数：{transferred_no_deal_count}')
        self.stdout.write(f'总流转客户数：{total_transferred}')
        self.stdout.write(f'客户自动流转公海任务执行完成')
        
        # 记录任务执行日志
        SystemLog.objects.create(
            user=None,  # 系统操作
            log_type='task',
            module='customer',
            action=f'客户自动流转公海任务执行',
            content=f'客户自动流转公海任务执行完成，共流转 {total_transferred} 个客户到公海',
            ip_address='127.0.0.1'
        )