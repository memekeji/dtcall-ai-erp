#!/usr/bin/env python
"""详细检查权限和菜单匹配"""
import os
import sys

sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from apps.user.models import Menu, Admin
from django.contrib.auth.models import Permission
from apps.system.context_processors import get_permission_from_src

print("=" * 70)
print("详细检查权限和菜单匹配")
print("=" * 70)

user = Admin.objects.get(username='zhangsan')
perms = user.get_all_permissions()

print(f"\n【用户权限检查】")
hr_perms = [p for p in perms if any(kw in p for kw in ['reward', 'employee', 'care', 'department', 'position', 'employee'])]
print(f"  人事相关权限: {hr_perms}")

print(f"\n【人事管理子菜单权限检查】")
hr_menu = Menu.objects.filter(id=1107).first()
if hr_menu:
    print(f"  一级菜单: {hr_menu.title}")
    
    hr_children = Menu.objects.filter(pid=hr_menu, status=1).order_by('sort')
    for child in hr_children:
        print(f"\n    [{child.id}] {child.title}")
        print(f"        src: {child.src}")
        
        inferred = get_permission_from_src(child.src)
        print(f"        推断权限: {inferred}")
        
        has_perm = False
        if inferred:
            full = f'user.{inferred}'
            has_perm = full in perms or inferred in perms
        
        print(f"        有权限: {has_perm}")

print("\n" + "=" * 70)
