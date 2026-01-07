#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
创建生产模块缺失的数据库表
"""
import os
import sys

# 添加项目根目录到Python路径
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_path)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')

import django
django.setup()

from django.db import connection


def create_process_route_tables():
    """创建工艺路线相关表"""
    
    sql_statements = [
        # 创建 ProcessRoute 表
        """
        CREATE TABLE IF NOT EXISTS production_process_route (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            code VARCHAR(50) UNIQUE NOT NULL,
            description TEXT,
            total_time DECIMAL(10, 2) DEFAULT 0,
            total_cost DECIMAL(12, 2) DEFAULT 0,
            status INTEGER DEFAULT 1,
            version VARCHAR(20) DEFAULT '1.0',
            effective_date DATE,
            expiry_date DATE,
            create_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            update_time TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        
        # 创建 ProcessRouteItem 表
        """
        CREATE TABLE IF NOT EXISTS production_process_route_item (
            id BIGSERIAL PRIMARY KEY,
            sequence INTEGER NOT NULL,
            estimated_time DECIMAL(8, 2) DEFAULT 0,
            workstation VARCHAR(100),
            work_instruction TEXT,
            quality_check_points TEXT,
            cycle_time DECIMAL(8, 2) DEFAULT 0,
            procedure_id INTEGER NOT NULL,
            process_route_id INTEGER NOT NULL REFERENCES production_process_route(id) ON DELETE CASCADE
        );
        """,
        
        # 创建唯一约束
        """
        CREATE UNIQUE INDEX IF NOT EXISTS production_process_route_item_unique 
        ON production_process_route_item (process_route_id, procedure_id);
        """,
    ]
    
    with connection.cursor() as cursor:
        for sql in sql_statements:
            try:
                cursor.execute(sql)
                print(f"✓ 执行成功")
            except Exception as e:
                print(f"✗ 执行失败: {e}")
                print(f"  SQL: {sql[:100]}...")
    
    print("\n检查已创建的表:")
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name LIKE 'production_%'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table[0]}")


if __name__ == '__main__':
    print("=" * 60)
    print("创建生产模块缺失的数据库表")
    print("=" * 60)
    
    try:
        create_process_route_tables()
        print("\n✅ 数据库表创建完成！")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
