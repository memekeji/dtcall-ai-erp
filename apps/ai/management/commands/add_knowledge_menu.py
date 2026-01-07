#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Django管理命令：将知识库管理菜单添加到AI智能中心下
使用方法: python manage.py add_knowledge_menu
"""
from django.core.management.base import BaseCommand
from apps.user.models import Menu


class Command(BaseCommand):
    help = '将知识库管理菜单添加到AI智能中心下'
    
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
            
            # 添加知识库管理菜单项
            knowledge_menu, created = Menu.objects.update_or_create(
                title='知识库管理',
                pid=ai_center_menu,
                defaults={
                    'src': '/ai/knowledge-base/list/',
                    'icon': 'layui-icon layui-icon-file-common',
                    'status': 1,
                    'sort': 2  # 设置排序，确保在AI工作流之后
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'成功创建知识库管理菜单项'))
            else:
                self.stdout.write(self.style.SUCCESS(f'成功更新知识库管理菜单项'))
            
            self.stdout.write(self.style.SUCCESS(f'菜单标题: {knowledge_menu.title}'))
            self.stdout.write(self.style.SUCCESS(f'菜单链接: {knowledge_menu.src}'))
            self.stdout.write(self.style.SUCCESS(f'菜单图标: {knowledge_menu.icon}'))
            
            # 记录结束时间
            end_time = time.time()
            self.stdout.write(self.style.SUCCESS(f'菜单添加完成！'))
            self.stdout.write(self.style.SUCCESS(f'耗时: {end_time - start_time:.2f} 秒'))
            
            return 0
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'添加菜单时出错: {str(e)}'))
            import traceback
            traceback.print_exc()
            return 1
