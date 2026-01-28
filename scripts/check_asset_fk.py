import os
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection

print("检查system_asset表的所有外键约束...")
cursor = connection.cursor()

# 只查询system_asset表的外键约束
cursor.execute("""
    SELECT 
        tc.constraint_name,
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
""")
print("\nsystem_asset表的外键约束:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]} -> {row[2]}")

# 检查basedata_asset_brand是否存在
print("\n检查basedata_asset_brand表:")
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'basedata_asset_brand'
""")
if cursor.fetchone():
    print("  basedata_asset_brand表存在!")
    cursor.execute("SELECT COUNT(*) FROM basedata_asset_brand")
    print(f"  记录数: {cursor.fetchone()[0]}")
else:
    print("  basedata_asset_brand表不存在")

print("\n检查system_asset_brand表:")
cursor.execute("SELECT COUNT(*) FROM system_asset_brand")
print(f"  记录数: {cursor.fetchone()[0]}")
