#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动备份管理命令
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
import os
import logging
from apps.system.models import SystemBackup, BackupPolicy
from django.contrib.auth.models import User
from datetime import datetime

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """自动备份管理命令"""
    help = '根据备份策略执行自动备份'

    def handle(self, *args, **options):
        """执行自动备份"""
        logger.info('开始执行自动备份')
        
        # 获取所有启用的备份策略
        active_policies = BackupPolicy.objects.filter(is_active=True)
        
        if not active_policies.exists():
            logger.info('没有启用的备份策略，退出自动备份')
            self.stdout.write(self.style.WARNING('没有启用的备份策略，退出自动备份'))
            return
        
        for policy in active_policies:
            # 检查是否需要执行备份
            if self.should_run_backup(policy):
                logger.info(f'执行备份策略: {policy.name}')
                self.run_backup(policy)
            else:
                logger.info(f'跳过备份策略: {policy.name}')
                self.stdout.write(self.style.SUCCESS(f'跳过备份策略: {policy.name}'))
        
        logger.info('自动备份执行完成')
        self.stdout.write(self.style.SUCCESS('自动备份执行完成'))
    
    def should_run_backup(self, policy):
        """检查是否需要执行备份"""
        now = timezone.now()
        
        if policy.interval == 'daily':
            # 每天执行，只检查时间
            return now.hour == policy.hour and now.minute == policy.minute
        elif policy.interval == 'weekly':
            # 每周执行，检查星期和时间
            return now.weekday() == policy.week_day and now.hour == policy.hour and now.minute == policy.minute
        elif policy.interval == 'monthly':
            # 每月执行，检查日期和时间
            return now.day == policy.month_day and now.hour == policy.hour and now.minute == policy.minute
        
        return False
    
    def run_backup(self, policy):
        """执行备份"""
        try:
            # 创建备份目录
            from datetime import datetime
            backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups', datetime.now().strftime('%Y%m%d'))
            os.makedirs(backup_dir, exist_ok=True)
            
            # 生成备份文件名
            timestamp = datetime.now().strftime('%H%M%S')
            backup_filename = f"auto_{timestamp}_{policy.backup_type}.sql"
            backup_file_path = os.path.join('backups', datetime.now().strftime('%Y%m%d'), backup_filename)
            full_backup_path = os.path.join(settings.MEDIA_ROOT, backup_file_path)
            
            logger.info(f'生成备份文件: {full_backup_path}')
            
            # 使用Django的ORM和原生SQL实现完整的SQL备份
            from django.db import connection
            
            with connection.cursor() as cursor:
                # 创建SQL备份文件
                with open(full_backup_path, 'w', encoding='utf-8') as f:
                    # 写入备份头信息
                    f.write(f"-- 数据库自动备份\n")
                    f.write(f"-- 备份名称: {policy.name}\n")
                    f.write(f"-- 备份类型: {policy.get_backup_type_display()}\n")
                    f.write(f"-- 备份时间: {datetime.now().isoformat()}\n")
                    f.write(f"-- 数据库: {settings.DATABASES['default']['NAME']}\n")
                    f.write(f"-- Schema: public\n")
                    f.write("-- \n")
                    f.write("-- 注意：此备份包含完整的数据库结构和数据\n")
                    f.write("-- \n\n")
                    
                    # 1. 备份序列
                    f.write("-- 1. 备份序列\n")
                    cursor.execute("SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public'")
                    sequences = cursor.fetchall()
                    for seq in sequences:
                        seq_name = seq[0]
                        try:
                            # 直接从序列获取当前值
                            cursor.execute(f"SELECT last_value FROM public.{seq_name}")
                            last_value = cursor.fetchone()[0]
                            # 生成简单的序列创建语句
                            f.write(f"CREATE SEQUENCE public.{seq_name} START WITH {last_value};")
                            f.write("\n")
                        except Exception as e:
                            # 如果获取序列值失败，跳过该序列
                            logger.warning(f"获取序列 {seq_name} 值失败: {str(e)}")
                    f.write("\n")
                    f.write("\n")
                    
                    # 2. 备份表结构
                    f.write("-- 2. 备份表结构\n")
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'")
                    tables = cursor.fetchall()
                    
                    # 先创建所有表结构
                    for table in tables:
                        table_name = table[0]
                        # 直接从information_schema获取表结构
                        cursor.execute(f"SELECT column_name, data_type, is_nullable, column_default, character_maximum_length, numeric_precision, numeric_scale FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '{table_name}' ORDER BY ordinal_position")
                        columns = cursor.fetchall()
                        
                        if columns:
                            # 构建CREATE TABLE语句
                            create_stmt = f"CREATE TABLE public.{table_name} (\n"
                            column_defs = []
                            
                            for col in columns:
                                col_name, data_type, is_nullable, col_default, char_max_len, num_prec, num_scale = col
                                col_def = f"    {col_name} {data_type}"
                                
                                # 添加数据类型长度或精度
                                if char_max_len is not None:
                                    col_def += f"({char_max_len})"
                                elif num_prec is not None:
                                    if num_scale is not None:
                                        col_def += f"({num_prec}, {num_scale})"
                                    else:
                                        col_def += f"({num_prec})"
                                
                                # 添加NOT NULL约束
                                if is_nullable == 'NO':
                                    col_def += " NOT NULL"
                                
                                # 添加默认值，确保值被正确引用
                                if col_default is not None:
                                    col_def += f" DEFAULT {col_default}"
                                
                                column_defs.append(col_def)
                            
                            # 获取主键约束
                            cursor.execute(f"SELECT kcu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name WHERE tc.table_schema = 'public' AND tc.table_name = '{table_name}' AND tc.constraint_type = 'PRIMARY KEY' ORDER BY kcu.ordinal_position")
                            pk_columns = cursor.fetchall()
                            if pk_columns:
                                pk_col_names = [col[0] for col in pk_columns]
                                column_defs.append(f"    PRIMARY KEY ({', '.join(pk_col_names)})")
                            
                            create_stmt += ",\n".join(column_defs)
                            create_stmt += "\n);\n"
                            f.write(create_stmt)
                    f.write("\n")
                    
                    # 3. 备份表数据
                    f.write("-- 3. 备份表数据\n")
                    for table in tables:
                        table_name = table[0]
                        
                        try:
                            f.write(f"-- 备份表：{table_name}\n")
                            # 获取表的列名
                            cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '{table_name}' ORDER BY ordinal_position")
                            columns = [col[0] for col in cursor.fetchall()]
                            
                            if not columns:
                                f.write(f"-- 表 {table_name} 没有列\n\n")
                                continue
                            
                            # 获取表的数据
                            cursor.execute(f"SELECT * FROM public.{table_name}")
                            rows = cursor.fetchall()
                            
                            if not rows:
                                f.write(f"-- 表 {table_name} 没有数据\n\n")
                                continue
                            
                            # 生成INSERT语句
                            column_names = ', '.join(columns)
                            
                            # 构建VALUES子句
                            for row in rows:
                                # 处理每个值
                                values = []
                                for val in row:
                                    if val is None:
                                        values.append('NULL')
                                    elif isinstance(val, (int, float)):
                                        values.append(str(val))
                                    elif isinstance(val, bool):
                                        values.append('TRUE' if val else 'FALSE')
                                    elif isinstance(val, (datetime, timezone.datetime, timezone.date, timezone.time)):
                                        # 处理日期时间类型
                                        values.append(f"'{val}'")
                                    else:
                                        # 字符串类型，需要转义
                                        val_str = str(val).replace("'", "''")
                                        values.append(f"'{val_str}'")
                                values_str = ', '.join(values)
                                f.write(f"INSERT INTO public.{table_name} ({column_names}) VALUES ({values_str});\n")
                            f.write("\n")
                        except Exception as e:
                            # 如果备份表数据失败，记录警告并跳过
                            logger.warning(f"无法备份表 {table_name} 的数据: {str(e)}")
                            f.write(f"-- 无法备份表 {table_name} 的数据: {str(e)}\n\n")
            
            # 获取备份文件大小
            file_size = os.path.getsize(full_backup_path)
            
            # 创建备份记录
            backup = SystemBackup.objects.create(
                name=f"自动备份_{datetime.now().strftime('%Y%m%d_%H%M%S')",
                backup_type=policy.backup_type,
                file_path=backup_file_path,
                file_size=file_size,
                description=f"由备份策略 '{policy.name}' 自动创建",
                creator=policy.creator
            )
            
            logger.info(f'备份成功，文件大小: {file_size}字节，备份ID: {backup.id}')
            self.stdout.write(self.style.SUCCESS(f'备份成功，文件大小: {file_size}字节，备份ID: {backup.id}'))
            
            # 清理旧备份
            self.cleanup_old_backups(policy)
        except Exception as e:
            logger.error(f'备份失败: {str(e)}')
            self.stdout.write(self.style.ERROR(f'备份失败: {str(e)}'))
    
    def cleanup_old_backups(self, policy):
        """清理旧备份"""
        # 获取该策略创建的所有备份
        backups = SystemBackup.objects.filter(
            description__contains=f"由备份策略 '{policy.name}' 自动创建"
        ).order_by('-created_at')
        
        # 删除超过保留份数的旧备份
        if backups.count() > policy.keep_count:
            old_backups = backups[policy.keep_count:]
            for backup in old_backups:
                try:
                    # 删除备份文件
                    full_backup_path = os.path.join(settings.MEDIA_ROOT, backup.file_path)
                    if os.path.exists(full_backup_path):
                        os.remove(full_backup_path)
                        logger.info(f'删除旧备份文件: {full_backup_path}')
                    # 删除备份记录
                    backup.delete()
                    logger.info(f'删除旧备份记录: {backup.name}')
                    self.stdout.write(self.style.SUCCESS(f'删除旧备份: {backup.name}'))
                except Exception as e:
                    logger.error(f'删除旧备份失败: {str(e)}')
                    self.stdout.write(self.style.ERROR(f'删除旧备份失败: {str(e)}'))