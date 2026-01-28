import os
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection

print("检查并修复system_asset表的department_id约束...")
cursor = connection.cursor()

# 检查department_id列的约束
cursor.execute("""
    SELECT column_name, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND table_name = 'system_asset'
    AND column_name = 'department_id'
""")
result = cursor.fetchone()
if result:
    print(f"department_id列: nullable={result[1]}, default={result[2]}")

# 检查是否有NOT NULL约束
cursor.execute("""
    SELECT tc.constraint_name, tc.constraint_type
    FROM information_schema.table_constraints tc
    JOIN information_schema.constraint_column_usage ccu
        ON tc.constraint_name = ccu.constraint_name
    WHERE tc.table_name = 'system_asset'
    AND ccu.column_name = 'department_id'
""")
for row in cursor.fetchall():
    print(f"约束: {row[0]} ({row[1]})")

# 尝试删除NOT NULL约束（如果存在）
try:
    cursor.execute("""
        ALTER TABLE system_asset 
        ALTER COLUMN department_id DROP NOT NULL
    """)
    print("已移除department_id的NOT NULL约束")
except Exception as e:
    print(f"无法移除NOT NULL约束: {e}")

# 同样处理responsible_person_id
try:
    cursor.execute("""
        ALTER TABLE system_asset 
        ALTER COLUMN responsible_person_id DROP NOT NULL
    """)
    print("已移除responsible_person_id的NOT NULL约束")
except Exception as e:
    print(f"无法移除responsible_person_id的NOT NULL约束: {e}")
