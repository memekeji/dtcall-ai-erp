#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Django管理命令：菜单管理工具
注意：当前系统已优化为仅使用数据库存储菜单，不再通过本地文件管理菜单
此脚本已被修改为菜单管理工具，支持查看和导出数据库中的菜单配置
使用方法: python manage.py import_menus
"""
from django.core.management.base import BaseCommand
from apps.user.models import Menu
from django.http import Http404
import json


class Command(BaseCommand):
    help = '菜单管理工具（查看和导出数据库中的菜单配置）'
    
    def add_arguments(self, parser):
        parser.add_argument('--export', type=str, help='导出菜单配置到指定文件')
    
    def handle(self, *args, **options):
        # 记录开始时间
        import time
        start_time = time.time()
        
        # 获取所有菜单数据
        try:
            # 获取所有顶级菜单并预取所有子菜单
            top_menus = Menu.objects.filter(pid=None, status=1).order_by('sort')
            
            if not top_menus:
                self.stdout.write(self.style.WARNING('数据库中没有有效的菜单数据'))
                return 0
            
            # 递归构建菜单树
            def build_menu_tree(menus):
                menu_list = []
                for menu in menus:
                    menu_data = {
                        'title': menu.title,
                        'src': menu.src,
                        'icon': menu.icon,
                        'sort': menu.sort,
                    }
                    
                    # 获取当前菜单的子菜单
                    submenus = Menu.objects.filter(pid=menu, status=1).order_by('sort')
                    if submenus:
                        menu_data['children'] = build_menu_tree(submenus)
                    
                    menu_list.append(menu_data)
                return menu_list
            
            # 构建完整的菜单树
            menu_tree = build_menu_tree(top_menus)
            
            # 输出菜单信息
            self.stdout.write(self.style.SUCCESS('数据库中的菜单配置：'))
            self.stdout.write(json.dumps(menu_tree, ensure_ascii=False, indent=2))
            
            # 如果指定了导出文件，则导出菜单配置
            export_file = options.get('export')
            if export_file:
                try:
                    with open(export_file, 'w', encoding='utf-8') as f:
                        json.dump(menu_tree, f, ensure_ascii=False, indent=2)
                    self.stdout.write(self.style.SUCCESS(f'菜单配置已成功导出到 {export_file}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'导出菜单配置时出错: {str(e)}'))
                    return 1
            
            # 记录结束时间
            end_time = time.time()
            self.stdout.write(self.style.SUCCESS(f'菜单数据处理完成！'))
            self.stdout.write(self.style.SUCCESS(f'耗时: {end_time - start_time:.2f} 秒'))
            
            return 0
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'处理菜单数据时出错: {str(e)}'))
            import traceback
            traceback.print_exc()
            return 1
