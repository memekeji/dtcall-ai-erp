#!/usr/bin/env python3
"""
管理命令：扫描media文件夹中的所有文件，并将它们添加到SystemAttachment模型中
"""
import os
import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.system.models import SystemAttachment

class Command(BaseCommand):
    help = '扫描media文件夹中的所有文件，并将它们添加到SystemAttachment模型中'
    
    def handle(self, *args, **options):
        """执行命令"""
        media_root = settings.MEDIA_ROOT
        self.stdout.write(f"开始扫描media文件夹：{media_root}")
        
        # 统计变量
        total_files = 0
        added_files = 0
        existing_files = 0
        
        # 遍历media文件夹中的所有文件
        for root, dirs, files in os.walk(media_root):
            for file_name in files:
                total_files += 1
                
                # 计算相对路径
                full_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(full_path, media_root).replace('\\', '/')
                
                # 检查文件是否已经存在于SystemAttachment模型中
                if SystemAttachment.objects.filter(file_path=relative_path).exists():
                    existing_files += 1
                    continue
                
                # 获取文件信息
                file_size = os.path.getsize(full_path)
                file_type = os.path.splitext(file_name)[1].lower() if '.' in file_name else ''
                
                # 确定模块
                module = self._determine_module(relative_path)
                
                # 创建SystemAttachment记录
                attachment = SystemAttachment(
                    name=file_name,
                    original_name=file_name,
                    file_path=relative_path,
                    file_size=file_size,
                    file_type=file_type,
                    module=module,
                    # uploader和object_id暂时为空
                )
                attachment.save()
                
                added_files += 1
                
                # 每处理100个文件输出一次进度
                if added_files % 100 == 0:
                    self.stdout.write(f"已处理 {total_files} 个文件，新增 {added_files} 个，已存在 {existing_files} 个")
        
        # 输出统计信息
        self.stdout.write(self.style.SUCCESS(f"扫描完成！"))
        self.stdout.write(f"总文件数：{total_files}")
        self.stdout.write(f"新增文件数：{added_files}")
        self.stdout.write(f"已存在文件数：{existing_files}")
    
    def _determine_module(self, relative_path):
        """根据文件路径确定所属模块"""
        path_parts = relative_path.split('/')
        
        # 根据文件夹名称确定模块
        if path_parts and len(path_parts) > 0:
            first_part = path_parts[0]
            if first_part == 'meeting_recordings':
                return 'meeting'
            elif first_part == 'knowledge_files':
                return 'ai_knowledge'
            elif first_part == 'disk':
                return 'disk'
            elif first_part == 'documents':
                return 'project'
            elif first_part == 'uploads':
                return 'system'
            elif first_part == 'temp':
                return 'temp'
        
        # 默认模块
        return 'other'