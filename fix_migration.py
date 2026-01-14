import django
import os
import sys

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
sys.path.insert(0, r'c:\Users\Administrator\Desktop\dtcall')

django.setup()

from django.db import connection

# 检查django_migrations表中的project迁移记录
with connection.cursor() as cursor:
    cursor.execute("SELECT id, app, name FROM django_migrations WHERE app='project' ORDER BY id")
    print("当前project应用的迁移记录：")
    for row in cursor.fetchall():
        print(f"  ID: {row[0]}, App: {row[1]}, Migration: {row[2]}")

    print("\n修复迁移历史...")

    # 方案：删除0003_add_projectcategory的迁移记录，然后先应用0002
    cursor.execute("DELETE FROM django_migrations WHERE app='project' AND name='0003_add_projectcategory'")
    print("已删除0003_add_projectcategory的迁移记录")

print("\n修复完成！现在可以正常执行迁移命令。")
