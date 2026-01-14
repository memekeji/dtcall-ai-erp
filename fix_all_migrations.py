import django
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')

django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # 查找所有有问题的迁移（被应用但依赖未应用的迁移）
    print("查找迁移历史不一致的问题...")
    print("=" * 60)
    
    # 获取所有已应用的迁移
    cursor.execute("SELECT app, name FROM django_migrations ORDER BY id")
    applied_migrations = cursor.fetchall()
    
    # 检查每个应用
    apps_with_issues = set()
    for app, name in applied_migrations:
        if name.startswith('0002') or name.startswith('0003'):
            # 检查是否有更早的迁移没有被应用
            app_num = int(name[:4])
            cursor.execute(f"SELECT name FROM django_migrations WHERE app='{app}' AND name < '{name}' ORDER BY name")
            earlier_migrations = cursor.fetchall()
            
            # 如果有更早的迁移没有被应用（0002在0001之后，0003在0002之后）
            if app_num >= 2 and len(earlier_migrations) < app_num - 1:
                apps_with_issues.add(app)
                print(f"发现 {app} 应用有迁移历史问题")
    
    print("\n需要修复的应用:", list(apps_with_issues))
    
    # 修复：删除所有0003及之后的迁移记录，让迁移按顺序重新应用
    for app in apps_with_issues:
        cursor.execute(f"DELETE FROM django_migrations WHERE app='{app}' AND name >= '0003'")
        deleted = cursor.rowcount
        if deleted > 0:
            print(f"已修复 {app}: 删除 {deleted} 条迁移记录")
    
    print("\n" + "=" * 60)
    print("修复完成！建议执行：python manage.py migrate")

print("\n注意：如果还有其他应用有类似问题，请重复运行此脚本。")
