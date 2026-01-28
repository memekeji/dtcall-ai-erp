import os
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection

print("修复所有资产相关的外键约束...")
cursor = connection.cursor()

# 修复system_asset表的brand_id外键
cursor.execute("""
    SELECT constraint_name 
    FROM information_schema.key_column_usage 
    WHERE table_schema = 'public'
    AND table_name = 'system_asset'
    AND column_name = 'brand_id'
""")
result = cursor.fetchone()
if result:
    constraint_name = result[0]
    print(f"\n发现brand_id约束: {constraint_name}")
    
    # 检查当前引用
    cursor.execute(f"""
        SELECT ccu.table_name 
        FROM information_schema.key_column_usage kcu
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON kcu.constraint_name = ccu.constraint_name
        WHERE kcu.constraint_name = '{constraint_name}'
    """)
    ref = cursor.fetchone()
    print(f"当前引用: {ref[0] if ref else 'unknown'}")
    
    if ref and 'basedata' in ref[0].lower():
        # 删除错误约束
        cursor.execute(f"ALTER TABLE system_asset DROP CONSTRAINT {constraint_name}")
        print(f"已删除约束: {constraint_name}")
        
        # 创建正确约束
        cursor.execute("""
            ALTER TABLE system_asset 
            ADD CONSTRAINT fk_system_asset_brand_correct
            FOREIGN KEY (brand_id) 
            REFERENCES system_asset_brand(id)
            ON DELETE SET NULL
        """)
        print("已创建正确约束指向 system_asset_brand")

# 检查并修复category_id外键
cursor.execute("""
    SELECT constraint_name 
    FROM information_schema.key_column_usage 
    WHERE table_schema = 'public'
    AND table_name = 'system_asset'
    AND column_name = 'category_id'
""")
result = cursor.fetchone()
if result:
    constraint_name = result[0]
    print(f"\n发现category_id约束: {constraint_name}")
    
    cursor.execute(f"""
        SELECT ccu.table_name 
        FROM information_schema.key_column_usage kcu
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON kcu.constraint_name = ccu.constraint_name
        WHERE kcu.constraint_name = '{constraint_name}'
    """)
    ref = cursor.fetchone()
    print(f"当前引用: {ref[0] if ref else 'unknown'}")
    
    if ref and 'basedata' in ref[0].lower():
        cursor.execute(f"ALTER TABLE system_asset DROP CONSTRAINT {constraint_name}")
        print(f"已删除约束: {constraint_name}")
        
        cursor.execute("""
            ALTER TABLE system_asset 
            ADD CONSTRAINT fk_system_asset_category_correct
            FOREIGN KEY (category_id) 
            REFERENCES system_asset_category(id)
            ON DELETE SET NULL
        """)
        print("已创建正确约束指向 system_asset_category")

print("\n外键约束修复完成!")
