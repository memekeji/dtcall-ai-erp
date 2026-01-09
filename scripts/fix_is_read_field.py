# -*- coding: utf-8 -*-
"""
修复消息表的 is_read 字段约束
"""
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parent_root = os.path.dirname(project_root)

if parent_root not in sys.path:
    sys.path.insert(0, parent_root)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection


def fix_is_read_field():
    """修复 is_read 字段"""
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE message ALTER COLUMN is_read DROP NOT NULL")
        cursor.execute("ALTER TABLE message ALTER COLUMN is_read SET DEFAULT FALSE")
        print("✓ 已修复 message.is_read 字段")
        
        # 验证
        cursor.execute("""
            SELECT column_name, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'message' AND column_name = 'is_read'
        """)
        row = cursor.fetchone()
        print(f"  is_read: nullable={row[1]}, default={row[2]}")


if __name__ == '__main__':
    fix_is_read_field()
