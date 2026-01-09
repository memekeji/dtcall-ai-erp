# -*- coding: utf-8 -*-
"""
修复消息模型的所有数据库字段约束
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


def fix_message_table_constraints():
    """修复消息表的所有字段约束"""
    with connection.cursor() as cursor:
        print("修复 message 表字段约束...")
        
        # 检查需要修复的字段
        fields_to_fix = [
            ('user_id', 'DROP NOT NULL'),
            ('is_read', 'DROP NOT NULL DEFAULT FALSE'),
        ]
        
        for field, action in fields_to_fix:
            try:
                cursor.execute(f"ALTER TABLE message ALTER COLUMN {field} {action};")
                print(f"✓ 已修复 message.{field} 字段")
            except Exception as e:
                print(f"  message.{field} 修复失败: {e}")
        
        # 验证修复
        print("\n验证字段可空状态:")
        cursor.execute("""
            SELECT column_name, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'message' AND column_name IN ('user_id', 'is_read')
            ORDER BY column_name
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]}: nullable={row[1]}, default={row[2]}")
        
        print("\n修复完成！")


if __name__ == '__main__':
    fix_message_table_constraints()
