import django
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')

django.setup()

from django.db import connection

print("查找并修复所有迁移历史问题...")
print("=" * 60)

with connection.cursor() as cursor:
    # 获取所有应用及其迁移记录
    cursor.execute("SELECT DISTINCT app FROM django_migrations ORDER BY app")
    all_apps = [row[0] for row in cursor.fetchall()]
    
    fixed_count = 0
    for app in all_apps:
        # 检查每个迁移文件是否按顺序存在
        cursor.execute(f"SELECT name FROM django_migrations WHERE app='{app}' ORDER BY name")
        applied_migrations = [row[0] for row in cursor.fetchall()]
        
        # 查找缺失的0002_initial迁移
        if '0003_add_asset_models' in applied_migrations and '0002_initial' not in applied_migrations:
            # 检查是否有其他0002迁移
            has_0002 = any(m.startswith('0002') for m in applied_migrations)
            
            if not has_0002:
                # 删除0003及之后的迁移
                cursor.execute(f"DELETE FROM django_migrations WHERE app='{app}' AND name >= '0003'")
                deleted = cursor.rowcount
                if deleted > 0:
                    print(f"已修复 {app}: 删除 {deleted} 条迁移记录 (缺少0002_initial)")
                    fixed_count += 1
    
    # 检查是否有0003但没有0002_initial的情况
    cursor.execute("""
        SELECT app, name FROM django_migrations 
        WHERE name LIKE '0003%' 
        AND app NOT IN (
            SELECT app FROM django_migrations WHERE name='0002_initial'
        )
    """)
    problem_migrations = cursor.fetchall()
    
    for app, name in problem_migrations:
        cursor.execute(f"DELETE FROM django_migrations WHERE app='{app}' AND name >= '0003'")
        print(f"已修复 {app}: 删除 {name} 及之后的迁移")
        fixed_count += 1

print("\n" + "=" * 60)
if fixed_count > 0:
    print(f"共修复 {fixed_count} 个问题")
else:
    print("没有发现新的迁移历史问题")
print("现在可以执行迁移命令。")
