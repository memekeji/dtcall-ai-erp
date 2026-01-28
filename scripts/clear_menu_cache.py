#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清除菜单缓存脚本
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

from django.core.cache import cache

print("=" * 50)
print("清除菜单缓存")
print("=" * 50)

# 清除所有菜单相关缓存
cache_keys = cache.keys('dashboard_menu_*')
print(f'找到 {len(cache_keys)} 个菜单缓存键')

for key in cache_keys:
    cache.delete(key)
    print(f'  ✓ 清除缓存: {key}')

# 也清除仪表板数据缓存
dashboard_keys = cache.keys('dashboard_data_*')
print(f'找到 {len(dashboard_keys)} 个仪表板缓存键')

for key in dashboard_keys:
    cache.delete(key)
    print(f'  ✓ 清除缓存: {key}')

print('=' * 50)
print('缓存清除完成！')
print('=' * 50)
