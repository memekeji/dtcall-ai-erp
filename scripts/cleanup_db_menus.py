# -*- coding: utf-8 -*-
"""
清理数据库中的旧菜单
"""
import os
import sys

# 设置项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_root = os.path.dirname(project_root)

# 添加到Python路径
if parent_root not in sys.path:
    sys.path.insert(0, parent_root)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from apps.user.models.menu import Menu
from django.db import transaction


def cleanup_old_menus():
    """清理数据库中的旧菜单"""
    
    # 查找公司动态菜单 (ID: 1155)
    old_menus = Menu.objects.filter(id=1155)
    
    if old_menus.exists():
        with transaction.atomic():
            for menu in old_menus:
                children = Menu.objects.filter(pid=menu)
                count = children.count()
                if count > 0:
                    children.delete()
                    print(f"删除菜单 '{menu.title}' (ID: {menu.id}) 的 {count} 个子菜单")
                print(f"删除旧菜单: {menu.title} (ID: {menu.id})")
                menu.delete()
    else:
        print("没有找到公司动态菜单 (ID: 1155)")
    
    # 清理"消息分类"菜单的旧记录（ID: 1402 可能已被删除）
    old_msg_category = Menu.objects.filter(id=1402, src='/message/category/list/').first()
    if old_msg_category:
        print(f"找到消息分类菜单 (ID: {old_msg_category.id})")
        
        # 检查是否已有正确的消息分类菜单
        existing = Menu.objects.filter(src='/message/category/list/', pid__isnull=False).exclude(id=old_msg_category.id).first()
        if existing:
            print(f"  已有正确的消息分类菜单 (ID: {existing.id})，删除旧记录")
            old_msg_category.delete()
        else:
            print(f"  消息分类菜单已正确配置")
    
    print("\n菜单清理完成！")


if __name__ == '__main__':
    cleanup_old_menus()
