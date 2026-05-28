#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from apps.system.menu_sync import sync_menus_from_config
from apps.user.models.menu import Menu


def sync_menus():
    print('=' * 70)
    print('系统菜单数据库同步')
    print('=' * 70)

    result = sync_menus_from_config(delete_extra=True)

    print(f"新增菜单: {result['created']} 个")
    print(f"更新菜单: {result['updated']} 个")
    print(f"删除菜单: {result['deleted']} 个")
    print(f"禁用额外菜单: {result['disabled_extra']} 个")
    print(f"父级关联调整: {result['parent_updated']} 个")
    print(f"配置菜单总数: {result['total']} 个")

    if result['errors']:
        print('菜单同步失败，请检查服务端日志')
        for error in result['errors']:
            print(f"  - ID:{error['id']} {error['title']}: {error['message']}")
        return False

    print('\n验证菜单树结构:')
    top_menus = Menu.objects.filter(pid__isnull=True).order_by('sort', 'id')
    for top_menu in top_menus:
        child_count = Menu.objects.filter(pid=top_menu).count()
        print(f"  [DIR] {top_menu.title} (ID: {top_menu.id}, 子菜单: {child_count}个)")
        children = Menu.objects.filter(pid=top_menu).order_by('sort', 'id')
        for child in children:
            grandchild_count = Menu.objects.filter(pid=child).count()
            if grandchild_count:
                print(f"      |-- {child.title} (ID: {child.id}, 子菜单: {grandchild_count}个)")
            else:
                print(f"      |-- {child.title} (ID: {child.id}) -> {child.src}")

    return True


if __name__ == '__main__':
    try:
        success = sync_menus()
        if success:
            print('\n[OK] 数据库菜单同步成功！')
            sys.exit(0)
        print('\n[WARN] 数据库菜单同步失败，请检查错误信息。')
        sys.exit(1)
    except Exception:
        print('\n[ERROR] 数据库菜单同步失败，请检查服务端日志。')
        raise
