# -*- coding: utf-8 -*-
"""
修复消息模型 user_id 字段的数据库约束
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


def fix_user_field_constraint():
    """修复 user_id 字段的 NOT NULL 约束"""
    with connection.cursor() as cursor:
        # 检查当前约束
        print("检查 user_id 字段约束...")
        
        # 修改字段允许为空
        try:
            cursor.execute("""
                ALTER TABLE message ALTER COLUMN user_id DROP NOT NULL;
            """)
            print("✓ 已将 message.user_id 字段改为允许为空")
        except Exception as e:
            print(f"  字段可能已经是允许为空: {e}")
        
        # 验证修改
        cursor.execute("""
            SELECT is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'message' AND column_name = 'user_id'
        """)
        result = cursor.fetchone()
        if result:
            print(f"  当前字段可空状态: {result[0]}")
        
        print("\n数据库约束修复完成！")


if __name__ == '__main__':
    fix_user_field_constraint()
