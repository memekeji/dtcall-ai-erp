import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
django.setup()

from django.db import connection

# 创建 comment 表
sql = """
CREATE TABLE IF NOT EXISTS comment (
    id BIGSERIAL PRIMARY KEY,
    content_type_id INTEGER NOT NULL REFERENCES django_content_type(id) ON DELETE CASCADE,
    object_id BIGINT NOT NULL,
    user_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    parent_id BIGINT REFERENCES comment(id) ON DELETE CASCADE,
    create_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    update_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    delete_time TIMESTAMP WITH TIME ZONE NULL
);
"""

# 创建索引
index_sql = """
CREATE INDEX IF NOT EXISTS idx_comment_content_type_object_id ON comment(content_type_id, object_id);
CREATE INDEX IF NOT EXISTS idx_comment_user ON comment(user_id);
CREATE INDEX IF NOT EXISTS idx_comment_parent ON comment(parent_id);
"""

try:
    with connection.cursor() as cursor:
        print("创建 comment 表...")
        cursor.execute(sql)
        print("表创建成功!")
        
        print("创建索引...")
        for stmt in index_sql.split(';'):
            if stmt.strip():
                cursor.execute(stmt)
        print("索引创建成功!")
        
except Exception as e:
    print(f"错误: {e}")
