import os
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection

print("修复所有system_asset表的外键约束...")
cursor = connection.cursor()

# 获取system_asset表的所有外键约束
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

print("\n当前外键约束:")
correct_refs = {
    'category_id': 'system_asset_category',
    'brand_id': 'system_asset_brand',
    'responsible_person_id': 'auth_user',
    'department_id': 'department',
}

for row in cursor.fetchall():
    constraint_name, column_name, ref_table = row
    print(f"  {constraint_name}: {column_name} -> {ref_table}")
    
    # 检查是否需要修复
    if column_name in correct_refs:
        expected_table = correct_refs[column_name]
        if ref_table != expected_table:
            print(f"    需要修复: 应该指向 {expected_table}")
            
            # 删除错误约束
            try:
                cursor.execute(f"ALTER TABLE system_asset DROP CONSTRAINT {constraint_name}")
                print(f"    已删除约束: {constraint_name}")
                
                # 创建正确约束
                cursor.execute(f"""
                    ALTER TABLE system_asset 
                    ADD CONSTRAINT {constraint_name}
                    FOREIGN KEY ({column_name}) 
                    REFERENCES {expected_table}(id)
                    ON DELETE SET NULL
                """)
                print(f"    已创建正确约束: {column_name} -> {expected_table}")
            except Exception as e:
                print(f"    修复失败: {e}")

print("\n外键约束修复完成!")

# 验证
print("\n验证修复后的约束:")
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
""")
for row in cursor.fetchall():
    print(f"  {row[0]} -> {row[1]}")
