import os
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection

print("检查资产相关表...")
cursor = connection.cursor()

# 查询所有asset相关的表
cursor.execute("""
    SELECT tc.table_name, kcu.column_name, ccu.table_name AS referenced_table, ccu.column_name AS referenced_column
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public'
    AND tc.table_name LIKE '%asset%'
""")
print("\n外键约束:")
for row in cursor.fetchall():
    print(f"  {row[0]}.{row[1]} -> {row[2]}.{row[3]}")

# 查询所有asset相关的表
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%asset%'
    ORDER BY table_name
""")
print("\n资产相关表:")
for row in cursor.fetchall():
    print(f"  {row[0]}")

# 检查system_asset表是否有数据
cursor.execute("SELECT COUNT(*) FROM system_asset")
count = cursor.fetchone()[0]
print(f"\nsystem_asset 表记录数: {count}")

if count > 0:
    # 检查现有资产的category_id
    cursor.execute("""
        SELECT DISTINCT category_id, COUNT(*) 
        FROM system_asset 
        GROUP BY category_id 
        ORDER BY category_id
    """)
    print("\n现有资产的category_id分布:")
    for row in cursor.fetchall():
        print(f"  category_id={row[0]}: {row[1]}条记录")

# 检查system_asset_category表
cursor.execute("SELECT COUNT(*) FROM system_asset_category")
count = cursor.fetchone()[0]
print(f"\nsystem_asset_category 表记录数: {count}")

# 检查basedata_asset_category表
try:
    cursor.execute("SELECT COUNT(*) FROM basedata_asset_category")
    count = cursor.fetchone()[0]
    print(f"basedata_asset_category 表记录数: {count}")
except Exception as e:
    print(f"basedata_asset_category 表不存在或无法访问")
