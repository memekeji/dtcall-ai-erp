#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入菜单配置到数据库
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 支持命令行指定 settings 参数
if len(sys.argv) > 1 and sys.argv[1].startswith('--settings='):
    settings_module = sys.argv[1].split('=')[1]
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from apps.user.models import Menu, SystemModule
from apps.system.menu_config import system_menus
from django.utils import timezone
from datetime import datetime


def import_menus():
    """导入系统菜单配置到数据库"""
    print("=" * 70)
    print("开始导入系统菜单配置")
    print("=" * 70)
    
    # 获取或创建默认模块
    default_module, _ = SystemModule.objects.get_or_create(
        code='DEFAULT',
        defaults={
            'name': '默认模块',
            'description': '系统默认功能模块',
            'is_active': True,
            'sort_order': 0
        }
    )
    
    current_time = timezone.now()
    created_count = 0
    updated_count = 0
    errors = []
    
    # 先按ID排序确保父菜单先创建
    sorted_menus = sorted(system_menus.items(), key=lambda x: x[0])
    
    for menu_id, menu_data in sorted_menus:
        try:
            # 获取父菜单ID
            parent_id = menu_data.get('pid_id', 0)
            
            # 获取父菜单对象
            if parent_id == 0:
                parent_menu = None  # 使用None而不是根菜单对象
            else:
                try:
                    parent_menu = Menu.objects.get(id=parent_id)
                except Menu.DoesNotExist:
                    parent_menu = None
            
            # 准备更新数据
            update_data = {
                'title': menu_data['title'],
                'src': menu_data.get('src', ''),
                'sort': menu_data.get('sort', 0),
                'status': menu_data.get('status', 1),
                'module': default_module,
                'permission_required': menu_data.get('permission_required', ''),
                'update_time': current_time
            }
            
            # 如果pid不为0才设置
            if parent_id != 0:
                update_data['pid'] = parent_menu
            
            # 创建或更新菜单
            menu, is_created = Menu.objects.update_or_create(
                id=menu_id,
                defaults=update_data
            )
            
            if is_created:
                created_count += 1
                print(f"  ✓ 创建菜单: {menu.title} (ID: {menu_id}, 父ID: {parent_id})")
            else:
                updated_count += 1
                
        except Exception as e:
            error_msg = f"处理菜单 ID {menu_id} ({menu_data.get('title', '未知')}) 失败: {str(e)}"
            errors.append(error_msg)
            print(f"  ✗ {error_msg}")
    
    print()
    print("=" * 70)
    print(f"菜单导入完成!")
    print(f"  - 新建菜单: {created_count}")
    print(f"  - 更新菜单: {updated_count}")
    print(f"  - 错误数量: {len(errors)}")
    print("=" * 70)
    
    # 显示菜单统计
    total_menus = Menu.objects.count()
    active_menus = Menu.objects.filter(status=1).count()
    print(f"\n菜单统计:")
    print(f"  - 总菜单数: {total_menus}")
    print(f"  - 启用菜单: {active_menus}")
    print(f"  - 禁用菜单: {total_menus - active_menus}")
    
    if errors:
        print(f"\n错误详情:")
        for error in errors:
            print(f"  - {error}")
    
    return created_count + updated_count


if __name__ == '__main__':
    import_menus()
