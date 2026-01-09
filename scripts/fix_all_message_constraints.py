# -*- coding: utf-8 -*-
"""
修复消息表的所有字段约束
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


def fix_all_message_constraints():
    """修复消息表的所有字段约束"""
    with connection.cursor() as cursor:
        print("修复 message 表字段约束...")
        
        # 修复所有可能的问题字段
        fix_statements = [
            "ALTER TABLE message ALTER COLUMN user_id DROP NOT NULL",
            "ALTER TABLE message ALTER COLUMN is_read DROP NOT NULL DEFAULT FALSE",
            "ALTER TABLE message ALTER COLUMN create_time SET DEFAULT CURRENT_TIMESTAMP",
        ]
        
        for sql in fix_statements:
            try:
                cursor.execute(sql)
                print(f"✓ 已执行: {sql[:50]}...")
            except Exception as e:
                print(f"  执行失败: {e}")
        
        # 验证
        print("\n验证字段状态:")
        cursor.execute("""
            SELECT column_name, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'message' AND column_name IN ('user_id', 'is_read', 'create_time')
            ORDER BY column_name
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]}: nullable={row[1]}, default={row[2]}")
        
        print("\n修复完成！")


if __name__ == '__main__':
    fix_all_message_constraints()
