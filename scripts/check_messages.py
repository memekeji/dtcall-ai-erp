# -*- coding: utf-8 -*-
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

from django.contrib.auth import get_user_model
from apps.message.models import Message, MessageUserRelation, MessageCategory

# 检查当前用户权限
user = get_user_model().objects.first()
print(f'当前用户: {user.username}')
print(f'是否有 view_message 权限: {user.has_perm("message.view_message")}')
print(f'是否是超级用户: {user.is_superuser}')

# 检查消息
print(f'\n消息总数: {Message.objects.count()}')

# 检查消息用户关系
print(f'消息用户关系总数: {MessageUserRelation.objects.count()}')

# 检查当前用户的消息关系
user_relations = MessageUserRelation.objects.filter(user=user)
print(f'当前用户的消息关系数: {user_relations.count()}')

# 检查公告分类的消息
announcement_cat = MessageCategory.objects.filter(code='announcement').first()
print(f'\n公告分类: {announcement_cat}')

if announcement_cat:
    notices = Message.objects.filter(category=announcement_cat)
    print(f'公告消息数: {notices.count()}')
    for msg in notices:
        rel_count = MessageUserRelation.objects.filter(message=msg).count()
        print(f'  消息 ID={msg.id}: {rel_count} 个用户关系')
