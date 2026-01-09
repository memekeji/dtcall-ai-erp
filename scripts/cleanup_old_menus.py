# -*- coding: utf-8 -*-
"""
清理旧消息菜单脚本
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
    """清理旧的消息菜单"""
    
    # 查找并删除旧的消息管理菜单 (ID: 8)
    old_menus = Menu.objects.filter(id=8)
    
    if old_menus.exists():
        with transaction.atomic():
            # 删除子菜单
            for menu in old_menus:
                children = Menu.objects.filter(pid=menu)
                count = children.count()
                children.delete()
                print(f"删除旧菜单: {menu.title} (ID: {menu.id}), 包含 {count} 个子菜单")
                menu.delete()
    else:
        print("没有找到旧的消息管理菜单")
    
    # 清理没有父菜单的孤立子菜单
    orphan_menus = Menu.objects.filter(src__startswith='/message/')
    print(f"\n找到 {orphan_menus.count()} 个消息相关菜单:")
    for menu in orphan_menus:
        print(f"  ID: {menu.id}, 标题: {menu.title}, 路径: {menu.src}")
    
    print("\n菜单清理完成！")


if __name__ == '__main__':
    cleanup_old_menus()
