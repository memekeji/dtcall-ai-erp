import django
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')

django.setup()

from django.db import connection

# 首先检查并删除所有0003及之后的迁移记录（因为这些都依赖于0002）
print("检查并修复所有迁移历史问题...")
print("=" * 60)

with connection.cursor() as cursor:
    # 获取所有应用及其迁移记录
    cursor.execute("SELECT DISTINCT app FROM django_migrations ORDER BY app")
    all_apps = [row[0] for row in cursor.fetchall()]
    
    fixed_apps = []
    for app in all_apps:
        # 检查是否有0003但没有0002的情况
        cursor.execute(f"SELECT name FROM django_migrations WHERE app='{app}' ORDER BY name")
        migrations = [row[0] for row in cursor.fetchall()]
        
        # 检查是否存在"0003"但不存在"0002_initial"的情况
        has_0003 = any(m.startswith('0003') for m in migrations)
        has_0002 = '0002_initial' in migrations or any(m.startswith('0002') and 'initial' not in m.lower() for m in migrations)
        
        if has_0003 and not has_0002:
            # 删除所有0003及之后的迁移
            cursor.execute(f"DELETE FROM django_migrations WHERE app='{app}' AND name >= '0003'")
            deleted = cursor.rowcount
            if deleted > 0:
                fixed_apps.append((app, deleted))
                print(f"已修复 {app}: 删除 {deleted} 条迁移记录")
    
    if not fixed_apps:
        print("没有发现迁移历史问题")
    else:
        print(f"\n共修复 {len(fixed_apps)} 个应用的迁移历史")
        
print("\n" + "=" * 60)
print("修复完成！现在可以执行迁移命令。")
