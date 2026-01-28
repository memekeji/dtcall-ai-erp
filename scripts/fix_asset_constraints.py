import os
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection

print("检查并修复资产相关表的外键约束...")
cursor = connection.cursor()

# 查询所有asset相关的外键约束
cursor.execute("""
    SELECT 
        tc.table_name, 
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
    AND (tc.table_name LIKE 'system_asset%' OR tc.table_name = 'system_asset_repair')
""")
print("\n当前外键约束:")
for row in cursor.fetchall():
    print(f"  {row[0]}.{row[2]} -> {row[3]}.id (constraint: {row[1]})")

# 检查是否需要修复basedata_asset_category的引用
cursor.execute("""
    SELECT constraint_name 
    FROM information_schema.table_constraints 
    WHERE table_name = 'system_asset'
    AND constraint_type = 'FOREIGN KEY'
    AND constraint_name LIKE '%asset%category%'
""")
constraints = [row[0] for row in cursor.fetchall()]
print(f"\n需要修复的约束: {constraints}")

for constraint in constraints:
    # 获取约束的列和引用表
    cursor.execute(f"""
        SELECT kcu.column_name, ccu.table_name 
        FROM information_schema.key_column_usage kcu
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON kcu.constraint_name = ccu.constraint_name
        WHERE kcu.constraint_name = '{constraint}'
    """)
    result = cursor.fetchone()
    if result:
        column, ref_table = result
        print(f"\n  约束: {constraint}")
        print(f"  列: {column}")
        print(f"  引用表: {ref_table}")
        
        if 'basedata' in ref_table.lower():
            print(f"  发现错误引用! 需要修复...")
            
            # 删除错误的外键约束
            try:
                cursor.execute(f"ALTER TABLE system_asset DROP CONSTRAINT {constraint}")
                print(f"  已删除约束: {constraint}")
                
                # 重新创建正确的外键约束
                cursor.execute(f"""
                    ALTER TABLE system_asset 
                    ADD CONSTRAINT {constraint} 
                    FOREIGN KEY (category_id) 
                    REFERENCES system_asset_category(id)
                    ON DELETE SET NULL
                """)
                print(f"  已重新创建约束指向 system_asset_category")
            except Exception as e:
                print(f"  修复失败: {e}")

# 检查AssetRepair的外键约束
cursor.execute("""
    SELECT constraint_name 
    FROM information_schema.table_constraints 
    WHERE table_name = 'system_asset_repair'
    AND constraint_type = 'FOREIGN KEY'
""")
repair_constraints = [row[0] for row in cursor.fetchall()]
print(f"\n资产维修表约束: {repair_constraints}")

for constraint in repair_constraints:
    cursor.execute(f"""
        SELECT kcu.column_name, ccu.table_name 
        FROM information_schema.key_column_usage kcu
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON kcu.constraint_name = ccu.constraint_name
        WHERE kcu.constraint_name = '{constraint}'
    """)
    result = cursor.fetchone()
    if result:
        column, ref_table = result
        print(f"  {constraint}: {column} -> {ref_table}")

print("\n外键约束修复完成!")
