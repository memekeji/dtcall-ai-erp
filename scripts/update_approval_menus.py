#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
审批流程菜单数据库更新脚本
此脚本用于将审批流程菜单添加到系统数据库中
"""

import os
import sys

# 添加项目根目录到Python路径
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_path)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from apps.user.models.menu import Menu


def update_approval_menus():
    """更新审批流程相关菜单"""
    
    # 审批流程菜单数据
    approval_menus = [
        {
            'id': 1300,
            'title': '审批流程',
            'src': 'javascript:;',
            'pid_id': 1162,  # 个人办公
            'sort': 55,
            'status': 1
        },
        {
            'id': 1301,
            'title': '审批类型',
            'src': '/approval/approval_type/',
            'pid_id': 1300,
            'sort': 1,
            'status': 1
        },
        {
            'id': 1302,
            'title': '审批流程',
            'src': '/approval/approvalflow/',
            'pid_id': 1300,
            'sort': 2,
            'status': 1
        },
    ]
    
    created_count = 0
    updated_count = 0
    
    for menu_data in approval_menus:
        menu_id = menu_data['id']
        menu, created = Menu.objects.update_or_create(
            id=menu_id,
            defaults=menu_data
        )
        
        if created:
            created_count += 1
            print(f"✓ 创建菜单成功: {menu_data['title']} (ID: {menu_id})")
        else:
            updated_count += 1
            print(f"✓ 更新菜单成功: {menu_data['title']} (ID: {menu_id})")
    
    print(f"\n菜单更新完成！共创建 {created_count} 个，更新 {updated_count} 个")
    
    # 验证菜单是否正确添加
    print("\n验证已添加的菜单:")
    parent_menu = Menu.objects.filter(id=1300).first()
    if parent_menu:
        print(f"  父菜单: {parent_menu.title}")
        children = Menu.objects.filter(pid_id=1300).order_by('sort')
        for child in children:
            print(f"    - {child.title} ({child.src})")
    
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("审批流程菜单数据库更新")
    print("=" * 60)
    
    try:
        update_approval_menus()
        print("\n数据库菜单更新成功！")
    except Exception as e:
        print(f"\n数据库菜单更新失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
