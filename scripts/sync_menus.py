#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统菜单数据库同步脚本
此脚本用于将 menu_config.py 中的菜单配置同步到数据库
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
from apps.system.menu_config import system_menus


def sync_menus():
    """同步所有菜单配置到数据库"""
    
    print("=" * 70)
    print("系统菜单数据库同步")
    print("=" * 70)
    
    # 先获取所有现有的菜单对象（用于建立关联）
    existing_menus = {menu.id: menu for menu in Menu.objects.all()}
    
    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors = []
    
    # 按ID排序确保父菜单先处理
    sorted_menus = sorted(system_menus.items(), key=lambda x: x[0])
    
    print(f"\n开始同步菜单配置，共 {len(sorted_menus)} 个菜单...\n")
    
    for menu_key, menu_data in sorted_menus:
        menu_id = menu_data['id']
        
        try:
            # 构建菜单数据
            menu_defaults = {
                'title': menu_data['title'],
                'src': menu_data['src'],
                'sort': menu_data['sort'],
                'status': menu_data['status'],
            }
            
            # 处理父菜单关联
            pid_id = menu_data.get('pid_id')
            if pid_id and pid_id in existing_menus:
                menu_defaults['pid'] = existing_menus[pid_id]
            elif pid_id and pid_id not in existing_menus:
                # 如果父菜单不存在，先创建父菜单
                if pid_id in system_menus:
                    print(f"  提示: 父菜单 {pid_id} 需要先处理")
            
            # 使用 update_or_create 创建或更新菜单
            menu, created = Menu.objects.update_or_create(
                id=menu_id,
                defaults=menu_defaults
            )
            
            # 更新现有菜单字典，以便后续菜单可以正确关联
            existing_menus[menu_id] = menu
            
            if created:
                created_count += 1
                status = "新增"
                pid_info = f" (父菜单: {pid_id})" if pid_id else ""
                print(f"  ✓ {status}: {menu_data['title']} (ID: {menu_id}){pid_info}")
            else:
                updated_count += 1
                status = "更新"
                pid_info = f" (父菜单: {pid_id})" if pid_id else ""
                print(f"  ✓ {status}: {menu_data['title']} (ID: {menu_id}){pid_info}")
                
        except Exception as e:
            errors.append((menu_id, menu_data.get('title', 'Unknown'), str(e)))
            print(f"  ✗ 失败: {menu_data.get('title', 'Unknown')} (ID: {menu_id}) - {e}")
    
    # 处理父菜单关联（处理第一轮中因父菜单不存在而跳过的情况）
    print("\n处理父菜单关联...")
    for menu_key, menu_data in sorted_menus:
        menu_id = menu_data['id']
        pid_id = menu_data.get('pid_id')
        
        try:
            if pid_id and pid_id != 0:
                menu = existing_menus.get(menu_id)
                parent = existing_menus.get(pid_id)
                
                if menu and parent and (not menu.pid or menu.pid_id != parent.id):
                    menu.pid = parent
                    menu.save(update_fields=['pid'])
                    print(f"  ✓ 更新父菜单关联: {menu.title} -> {parent.title}")
        except Exception as e:
            errors.append((menu_id, menu_data.get('title', 'Unknown'), f"父菜单关联失败: {e}"))
    
    # 统计结果
    print("\n" + "=" * 70)
    print("菜单同步完成！")
    print("=" * 70)
    print(f"  新增菜单: {created_count} 个")
    print(f"  更新菜单: {updated_count} 个")
    print(f"  失败数量: {len(errors)} 个")
    
    if errors:
        print("\n失败的菜单:")
        for menu_id, title, error in errors:
            print(f"  - ID:{menu_id} {title}: {error}")
    
    # 验证菜单树结构
    print("\n验证菜单树结构:")
    top_menus = Menu.objects.filter(pid__isnull=True).order_by('sort')
    for top_menu in top_menus:
        child_count = Menu.objects.filter(pid=top_menu).count()
        print(f"  📁 {top_menu.title} (ID: {top_menu.id}, 子菜单: {child_count}个)")
        children = Menu.objects.filter(pid=top_menu).order_by('sort')
        for child in children:
            grandchild_count = Menu.objects.filter(pid=child).count()
            if grandchild_count > 0:
                print(f"      ├── {child.title} (ID: {child.id}, 子菜单: {grandchild_count}个)")
            else:
                print(f"      ├── {child.title} (ID: {child.id}) -> {child.src}")
    
    return len(errors) == 0


if __name__ == '__main__':
    try:
        success = sync_menus()
        if success:
            print("\n✅ 数据库菜单同步成功！")
            sys.exit(0)
        else:
            print("\n⚠️ 数据库菜单同步部分失败，请检查错误信息。")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 数据库菜单同步失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
