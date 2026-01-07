#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Django管理命令：修复AI工作流菜单项链接
使用方法: python manage.py fix_ai_workflow_menu
"""
from django.core.management.base import BaseCommand
from apps.user.models import Menu


class Command(BaseCommand):
    help = '修复AI工作流菜单项链接'
    
    def handle(self, *args, **options):
        # 记录开始时间
        import time
        start_time = time.time()
        
        try:
            # 查找AI智能中心顶级菜单
            ai_center_menu = Menu.objects.filter(
                title='AI智能中心', 
                status=1,
                pid=None
            ).first()
            
            if not ai_center_menu:
                self.stdout.write(self.style.ERROR('未找到AI智能中心顶级菜单'))
                return 1
            
            # 查找AI工作流子菜单
            workflow_menu = Menu.objects.filter(
                title='AI工作流',
                status=1,
                pid=ai_center_menu.id
            ).first()
            
            if not workflow_menu:
                self.stdout.write(self.style.ERROR('未找到AI工作流子菜单'))
                return 1
            
            # 更新菜单项链接
            old_src = workflow_menu.src
            workflow_menu.src = '/ai/workflow/'
            workflow_menu.save()
            
            self.stdout.write(self.style.SUCCESS(f'成功更新AI工作流菜单项链接'))
            self.stdout.write(self.style.SUCCESS(f'旧链接: {old_src}'))
            self.stdout.write(self.style.SUCCESS(f'新链接: /ai/workflow/'))
            
            # 记录结束时间
            end_time = time.time()
            self.stdout.write(self.style.SUCCESS(f'菜单修复完成！'))
            self.stdout.write(self.style.SUCCESS(f'耗时: {end_time - start_time:.2f} 秒'))
            
            return 0
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'修复菜单链接时出错: {str(e)}'))
            import traceback
            traceback.print_exc()
            return 1