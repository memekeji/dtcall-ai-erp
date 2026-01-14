import django
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')

django.setup()

from django.db import connection

print("深度修复迁移历史问题...")
print("=" * 60)

with connection.cursor() as cursor:
    # 获取所有应用及其迁移记录
    cursor.execute("SELECT app, name FROM django_migrations ORDER BY id")
    all_migrations = cursor.fetchall()
    
    # 按应用分组
    app_migrations = {}
    for app, name in all_migrations:
        if app not in app_migrations:
            app_migrations[app] = []
        app_migrations[app].append(name)
    
    # 检查每个应用
    for app, migrations in app_migrations.items():
        # 找出需要删除的迁移（不是0001_initial或0002_initial）
        to_delete = []
        for m in migrations:
            if m != '0001_initial' and m != '0002_initial' and not m.startswith('0001_') and not m.startswith('0002_'):
                to_delete.append(m)
        
        if to_delete:
            # 按名称排序，保留前两个（0001和0002）
            to_delete.sort()
            count = len(to_delete)
            placeholders = ','.join(['?' for _ in to_delete])
            cursor.execute(f"DELETE FROM django_migrations WHERE app=? AND name IN ({placeholders})", [app] + to_delete)
            if cursor.rowcount > 0:
                print(f"已修复 {app}: 删除 {count} 条迁移记录")

print("\n" + "=" * 60)
print("修复完成！现在可以执行迁移命令。")
