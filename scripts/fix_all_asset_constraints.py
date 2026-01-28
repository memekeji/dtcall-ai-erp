import os
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection

print("修复所有资产相关表的外键约束...")
cursor = connection.cursor()

# 定义需要修复的表和正确的引用表
tables_with_wrong_fk = [
    {
        'table': 'system_asset',
        'correct_refs': {
            'category_id': ('system_asset_category', 'fk_system_asset_category'),
            'brand_id': ('system_asset_brand', 'system_asset_brand_id_fkey'),
            'responsible_person_id': ('auth_user', None),  # 不需要修复，指向auth_user
            'department_id': ('department', None),  # 不需要修复
        }
    },
    {
        'table': 'system_asset_repair',
        'correct_refs': {
            'asset_id': ('system_asset', None),
            'reporter_id': ('auth_user', None),
            'repair_person_id': ('auth_user', None),
        }
    }
]

for table_info in tables_with_wrong_fk:
    table_name = table_info['table']
    correct_refs = table_info['correct_refs']
    
    print(f"\n检查表: {table_name}")
    
    # 获取所有外键约束
    cursor.execute(f"""
        SELECT constraint_name, column_name 
        FROM information_schema.key_column_usage 
        WHERE table_schema = 'public'
        AND table_name = '{table_name}'
        AND constraint_name LIKE '%fk%'
            OR constraint_name LIKE '%id_fkey%'
            OR constraint_name LIKE '%id_%'
    """)
    
    for row in cursor.fetchall():
        constraint_name, column_name = row
        
        # 检查是否是错误的外键引用
        cursor.execute(f"""
            SELECT ccu.table_name 
            FROM information_schema.key_column_usage kcu
            LEFT JOIN information_schema.constraint_column_usage ccu
                ON kcu.constraint_name = ccu.constraint_name
            WHERE kcu.constraint_name = '{constraint_name}'
        """)
        result = cursor.fetchone()
        if result:
            current_ref = result[0]
            
            # 检查是否需要修复
            should_fix = False
            correct_table = None
            
            if column_name in correct_refs:
                expected_table, expected_constraint = correct_refs[column_name]
                if expected_table and 'basedata' in current_ref.lower():
                    should_fix = True
                    correct_table = expected_table
                    correct_constraint = expected_constraint
            
            if should_fix:
                print(f"  发现错误引用: {column_name} -> {current_ref}")
                print(f"  正确引用: {column_name} -> {correct_table}")
                
                # 删除错误的外键约束
                try:
                    cursor.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}")
                    print(f"  已删除约束: {constraint_name}")
                    
                    # 重新创建正确的外键约束
                    cursor.execute(f"""
                        ALTER TABLE {table_name} 
                        ADD CONSTRAINT {constraint_name} 
                        FOREIGN KEY ({column_name}) 
                        REFERENCES {correct_table}(id)
                        ON DELETE SET NULL
                    """)
                    print(f"  已重新创建约束指向 {correct_table}")
                except Exception as e:
                    print(f"  修复失败: {e}")

print("\n外键约束修复完成!")
