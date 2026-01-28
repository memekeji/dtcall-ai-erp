import os
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from apps.system.models import AssetCategory, AssetBrand

print('=== 资产分类数据 ===')
categories = AssetCategory.objects.all()
print(f'总数: {categories.count()}')

print('\n一级分类:')
for cat in categories.filter(parent__isnull=True):
    print(f'  {cat.id}: {cat.code} - {cat.name} (active: {cat.is_active})')

print('\n二级分类:')
for cat in categories.filter(parent__isnull=False):
    parent_name = cat.parent.name if cat.parent else ''
    print(f'  {cat.id}: {cat.code} - {cat.name} -> {parent_name} (active: {cat.is_active})')

print('\n=== 资产品牌数据 ===')
brands = AssetBrand.objects.all()
print(f'总数: {brands.count()}')
for brand in brands[:10]:
    print(f'  {brand.id}: {brand.code} - {brand.name} (active: {brand.is_active})')
