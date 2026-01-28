import os
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection

print("修复所有剩余的外键约束...")
cursor = connection.cursor()

# 列出system_asset表的所有外键约束
cursor.execute("""
    SELECT constraint_name, column_name 
    FROM information_schema.key_column_usage 
    WHERE table_schema = 'public'
    AND table_name = 'system_asset'
    AND constraint_name LIKE '%fk%'
        OR constraint_name LIKE '%_fkey'
""")
print("\nsystem_asset表的外键约束:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

# 检查每个约束引用的表
for row in cursor.fetchall():
    constraint_name, column_name = row
    
    cursor.execute(f"""
        SELECT ccu.table_name 
        FROM information_schema.key_column_usage kcu
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON kcu.constraint_name = ccu.constraint_name
        WHERE kcu.constraint_name = '{constraint_name}'
    """)
    result = cursor.fetchone()
    if result and 'basedata' in result[0].lower():
        print(f"\n发现错误引用: {constraint_name} ({column_name}) -> {result[0]}")
        
        # 删除约束
        cursor.execute(f"ALTER TABLE system_asset DROP CONSTRAINT {constraint_name}")
        print(f"  已删除约束: {constraint_name}")
        
        # 重新创建正确约束
        if column_name == 'brand_id':
            cursor.execute("""
                ALTER TABLE system_asset 
                ADD CONSTRAINT fk_system_asset_brand_correct
                FOREIGN KEY (brand_id) 
                REFERENCES system_asset_brand(id)
                ON DELETE SET NULL
            """)
            print("  已重新创建brand_id外键指向 system_asset_brand")
        elif column_name == 'category_id':
            cursor.execute("""
                ALTER TABLE system_asset 
                ADD CONSTRAINT fk_system_asset_category_correct
                FOREIGN KEY (category_id) 
                REFERENCES system_asset_category(id)
                ON DELETE SET NULL
            """)
            print("  已重新创建category_id外键指向 system_asset_category")

print("\n外键约束修复完成!")
