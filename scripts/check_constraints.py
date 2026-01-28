import os
import sys
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection

print("检查system_asset表的所有约束...")
cursor = connection.cursor()

# 查询所有约束
cursor.execute("""
    SELECT 
        tc.constraint_name,
        tc.constraint_type,
        kcu.column_name,
        ccu.table_name AS referenced_table
    FROM information_schema.table_constraints AS tc
    LEFT JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    LEFT JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
        AND ccu.table_schema = tc.table_schema
    WHERE tc.table_schema = 'public'
    AND tc.table_name = 'system_asset'
    ORDER BY tc.constraint_type
""")

print("\n所有约束:")
for row in cursor.fetchall():
    print(f"  {row[0]} ({row[1]}): {row[2]} -> {row[3]}")
