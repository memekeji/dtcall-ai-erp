import os
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection

print("永久修复system_asset表的外键约束...")
cursor = connection.cursor()

# 1. 删除所有现有的brand_id和category_id外键约束
constraints_to_delete = [
    "fk_system_asset_brand",
    "fk_system_asset_brand_correct",
    "fk_system_asset_category",
    "fk_system_asset_category_correct",
]

for constraint in constraints_to_delete:
    try:
        cursor.execute(f"ALTER TABLE system_asset DROP CONSTRAINT IF EXISTS {constraint}")
        print(f"删除约束: {constraint}")
    except Exception as e:
        print(f"约束 {constraint} 不存在或无法删除: {e}")

# 2. 删除可能存在的其他自动创建的约束
cursor.execute("""
    SELECT constraint_name 
    FROM information_schema.key_column_usage 
    WHERE table_schema = 'public'
    AND table_name = 'system_asset'
    AND column_name IN ('brand_id', 'category_id')
""")
for row in cursor.fetchall():
    try:
        cursor.execute(f"ALTER TABLE system_asset DROP CONSTRAINT IF EXISTS {row[0]}")
        print(f"删除额外约束: {row[0]}")
    except Exception as e:
        print(f"无法删除 {row[0]}: {e}")

# 3. 创建正确的外键约束
print("\n创建正确的外键约束...")

try:
    cursor.execute("""
        ALTER TABLE system_asset 
        ADD CONSTRAINT fk_system_asset_brand 
        FOREIGN KEY (brand_id) 
        REFERENCES system_asset_brand(id)
        ON DELETE SET NULL
    """)
    print("brand_id -> system_asset_brand (正确)")
except Exception as e:
    print(f"创建brand_id约束失败: {e}")

try:
    cursor.execute("""
        ALTER TABLE system_asset 
        ADD CONSTRAINT fk_system_asset_category 
        FOREIGN KEY (category_id) 
        REFERENCES system_asset_category(id)
        ON DELETE SET NULL
    """)
    print("category_id -> system_asset_category (正确)")
except Exception as e:
    print(f"创建category_id约束失败: {e}")

print("\n外键约束修复完成!")
print("\n验证约束:")
cursor.execute("""
    SELECT 
        kcu.column_name,
        ccu.table_name AS referenced_table
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    LEFT JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public'
    AND tc.table_name = 'system_asset'
    AND kcu.column_name IN ('brand_id', 'category_id')
""")
for row in cursor.fetchall():
    print(f"  {row[0]} -> {row[1]}")
