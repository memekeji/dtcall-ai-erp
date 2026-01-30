#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
为项目-CONT1763015340创建全面测试数据
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dtcall.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import datetime, timedelta
import random

User = get_user_model()

def create_test_data():
    """创建测试数据"""
    
    # 获取项目
    from apps.project.models import Project, ProjectStep, Task, Comment, ProjectDocument, ProjectCategory
    from apps.message.models import Message, MessageCategory
    
    try:
        project = Project.objects.get(id=73)
        print(f'✅ 找到项目: {project.name} (ID: {project.id})')
    except Project.DoesNotExist:
        print('❌ 项目不存在')
        return
    
    # 获取或创建测试用户
    test_users = []
    user_data = [
        {'username': 'zhangsan', 'first_name': '张', 'last_name': '三'},
        {'username': 'lisi', 'first_name': '李', 'last_name': '四'},
        {'username': 'wangwu', 'first_name': '王', 'last_name': '五'},
        {'username': 'zhaoliu', 'first_name': '赵', 'last_name': '六'},
        {'username': 'sunqi', 'first_name': '孙', 'last_name': '七'},
    ]
    
    for data in user_data:
        user, created = User.objects.get_or_create(
            username=data['username'],
            defaults={
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'is_active': True
            }
        )
        test_users.append(user)
        if created:
            print(f'✅ 创建测试用户: {user.username}')
        else:
            print(f'📌 使用现有用户: {user.username}')
    
    # 获取当前用户作为项目创建者
    current_user = User.objects.filter(is_superuser=True).first()
    if not current_user:
        current_user = test_users[0]
    
    print(f'\n📊 开始为项目创建测试数据...\n')
    
    # 1. 添加项目成员
    print('--- 创建项目成员 ---')
    if project.members.exists():
        print(f'项目已有 {project.members.count()} 个成员')
    else:
        for user in test_users[:3]:
            project.members.add(user)
        print(f'✅ 添加了 {test_users[:3].__len__()} 个项目成员')
    
    # 2. 创建项目阶段/步骤
    print('\n--- 创建项目阶段 ---')
    steps_data = [
        {'name': '需求分析', 'description': '完成项目需求调研和分析', 'progress': 100},
        {'name': '系统设计', 'description': '完成系统架构和详细设计', 'progress': 80},
        {'name': '编码开发', 'description': '完成各模块代码开发', 'progress': 45},
        {'name': '测试验收', 'description': '完成系统测试和用户验收', 'progress': 0},
        {'name': '上线部署', 'description': '系统上线和部署', 'progress': 0},
    ]
    
    for i, step_data in enumerate(steps_data, 1):
        step, created = ProjectStep.objects.get_or_create(
            project=project,
            name=step_data['name'],
            defaults={
                'description': step_data['description'],
                'progress': step_data['progress'],
                'sort': i
            }
        )
        if created:
            print(f'✅ 创建阶段: {step.name} (进度: {step.progress}%)')
    
    # 3. 创建任务
    print('\n--- 创建任务 ---')
    tasks_data = [
        {
            'title': '需求调研与整理',
            'description': '完成用户需求调研，整理需求文档',
            'status': 3,
            'progress': 100,
            'start_date': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() - timedelta(days=25)).strftime('%Y-%m-%d'),
            'priority': 2,
            'assignee': test_users[0]
        },
        {
            'title': '系统架构设计',
            'description': '设计系统整体架构和技术选型',
            'status': 3,
            'progress': 100,
            'start_date': (datetime.now() - timedelta(days=24)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() - timedelta(days=18)).strftime('%Y-%m-%d'),
            'priority': 2,
            'assignee': test_users[1]
        },
        {
            'title': '数据库设计',
            'description': '设计数据库表结构和关系',
            'status': 3,
            'progress': 100,
            'start_date': (datetime.now() - timedelta(days=17)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d'),
            'priority': 2,
            'assignee': test_users[1]
        },
        {
            'title': '用户模块开发',
            'description': '完成用户注册、登录、个人中心等功能',
            'status': 3,
            'progress': 100,
            'start_date': (datetime.now() - timedelta(days=13)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() - timedelta(days=8)).strftime('%Y-%m-%d'),
            'priority': 3,
            'assignee': test_users[2]
        },
        {
            'title': '项目模块开发',
            'description': '完成项目CRUD、任务管理等功能',
            'status': 2,
            'progress': 60,
            'start_date': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
            'priority': 3,
            'assignee': test_users[2]
        },
        {
            'title': '甘特图功能开发',
            'description': '实现项目甘特图展示功能',
            'status': 2,
            'progress': 40,
            'start_date': (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'),
            'priority': 2,
            'assignee': test_users[3]
        },
        {
            'title': '看板视图开发',
            'description': '实现任务看板视图展示',
            'status': 2,
            'progress': 30,
            'start_date': (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
            'priority': 2,
            'assignee': test_users[3]
        },
        {
            'title': '评论功能开发',
            'description': '实现项目评论和回复功能',
            'status': 2,
            'progress': 20,
            'start_date': (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=8)).strftime('%Y-%m-%d'),
            'priority': 1,
            'assignee': test_users[4]
        },
        {
            'title': 'API接口开发',
            'description': '开发RESTful API接口',
            'status': 1,
            'progress': 0,
            'start_date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d'),
            'priority': 2,
            'assignee': test_users[0]
        },
        {
            'title': '单元测试',
            'description': '编写和执行单元测试',
            'status': 1,
            'progress': 0,
            'start_date': (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=12)).strftime('%Y-%m-%d'),
            'priority': 2,
            'assignee': test_users[1]
        },
        {
            'title': '系统集成测试',
            'description': '完成系统集成测试',
            'status': 1,
            'progress': 0,
            'start_date': (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d'),
            'priority': 2,
            'assignee': test_users[2]
        },
        {
            'title': '用户验收测试',
            'description': '协助用户完成验收测试',
            'status': 1,
            'progress': 0,
            'start_date': (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=18)).strftime('%Y-%m-%d'),
            'priority': 3,
            'assignee': test_users[3]
        },
        {
            'title': '系统上线部署',
            'description': '完成生产环境部署',
            'status': 1,
            'progress': 0,
            'start_date': (datetime.now() + timedelta(days=17)).strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=20)).strftime('%Y-%m-%d'),
            'priority': 3,
            'assignee': test_users[4]
        },
    ]
    
    created_tasks = []
    for i, task_data in enumerate(tasks_data, 1):
        task, created = Task.objects.get_or_create(
            project=project,
            title=task_data['title'],
            defaults={
                'description': task_data['description'],
                'status': task_data['status'],
                'progress': task_data['progress'],
                'start_date': task_data['start_date'],
                'end_date': task_data['end_date'],
                'priority': task_data['priority'],
                'assignee': task_data['assignee'],
                'creator': current_user
            }
        )
        if created:
            created_tasks.append(task)
            print(f'✅ 创建任务: {task.title} (状态: {task.get_status_display()}, 进度: {task.progress}%)')
    
    # 4. 创建评论
    print('\n--- 创建评论 ---')
    
    # 获取项目的ContentType
    project_ct = ContentType.objects.get_for_model(Project)
    
    # 获取实际存在的用户 - 只使用admin
    admin_user = User.objects.filter(username='admin').first()
    if not admin_user:
        print('❌ admin用户不存在')
        return
    
    print(f'📌 使用用户: {admin_user.id} - {admin_user.username}')
    
    # 创建根评论（无父评论）
    root_comments = []
    root_contents = [
        '这个项目整体进展良好，需求分析阶段已经完成，大家辛苦了！',
        '系统架构设计已经完成，采用了先进的技术方案，性能应该会有很大提升。',
        '设计文档很详细，对开发工作很有帮助。',
        '用户模块开发完成，测试通过。',
        '请问项目模块的开发进度如何？预计什么时候可以完成？',
        '甘特图功能开发中，目前进展顺利。',
        '看板视图的交互设计需要优化一下，用户体验很重要。',
    ]
    
    for i, content in enumerate(root_contents):
        comment = Comment.objects.create(
            content_type=project_ct,
            object_id=project.id,
            user=admin_user,
            content=content,
            parent=None
        )
        root_comments.append(comment)
        print(f'✅ 创建评论: {comment.user.username}: {content[:30]}...')
    
    # 创建回复评论
    reply_contents = [
        '项目模块开发进度60%，预计再需要3天可以完成核心功能。',
        '好的，注意质量第一，有问题及时沟通。',
        '收到，我会优化交互设计，增加拖拽功能。',
    ]
    
    for i, content in enumerate(reply_contents):
        if i < len(root_comments):
            comment = Comment.objects.create(
                content_type=project_ct,
                object_id=project.id,
                user=admin_user,
                content=content,
                parent=root_comments[i]  # 回复到对应的根评论
            )
            print(f'✅ 创建回复: {comment.user.username} 回复 {comment.parent.user.username}: {content[:30]}...')
    
    # 5. 创建项目文档
    print('\n--- 创建项目文档 ---')
    documents_data = [
        {
            'title': '项目需求文档',
            'content': '详细的项目需求说明文档，包含功能需求和非功能需求的详细描述。',
            'file_path': ''
        },
        {
            'title': '系统设计说明书',
            'content': '系统架构和详细设计文档，包含技术选型、模块划分、接口设计等内容。',
            'file_path': ''
        },
        {
            'title': '数据库设计文档',
            'content': '数据库表结构和关系说明，包含ER图、表结构定义、索引设计等。',
            'file_path': ''
        },
        {
            'title': 'API接口文档',
            'content': 'RESTful API接口说明，包含所有接口的请求方法、参数、返回值等。',
            'file_path': ''
        },
        {
            'title': '测试报告',
            'content': '系统测试报告，包含测试用例、测试结果、缺陷统计等内容。',
            'file_path': ''
        },
    ]
    
    for doc_data in documents_data:
        doc, created = ProjectDocument.objects.get_or_create(
            project=project,
            title=doc_data['title'],
            defaults={
                'content': doc_data['content'],
                'file_path': doc_data['file_path'],
                'creator': current_user
            }
        )
        if created:
            print(f'✅ 创建文档: {doc.title}')
    
    # 6. 更新项目状态为进行中
    print('\n--- 更新项目状态 ---')
    project.status = 2  # 进行中
    project.start_date = datetime.now().date()
    project.save()
    print(f'✅ 项目状态更新为: 进行中')
    
    # 7. 统计总结
    print('\n' + '='*60)
    print('📊 测试数据创建完成！')
    print('='*60)
    print(f'项目: {project.name} (ID: {project.id})')
    print(f'  - 项目成员: {project.members.count()} 人')
    print(f'  - 项目阶段: {project.steps.count()} 个')
    print(f'  - 任务数量: {project.tasks.count()} 个')
    print(f'  - 评论数量: {Comment.objects.filter(content_type=project_ct, object_id=project.id).count()} 条')
    print(f'  - 文档数量: {project.documents.count()} 个')
    print(f'  - 已完成任务: {project.tasks.filter(status=3).count()} 个')
    print(f'  - 进行中任务: {project.tasks.filter(status=2).count()} 个')
    print(f'  - 未开始任务: {project.tasks.filter(status=1).count()} 个')
    print('='*60)
    
    # 计算项目进度
    total_progress = sum(t.progress for t in project.tasks.all())
    task_count = project.tasks.count()
    if task_count > 0:
        avg_progress = total_progress // task_count
        project.progress = avg_progress
        project.save()
        print(f'📈 项目平均进度: {avg_progress}%')

if __name__ == '__main__':
    print('='*60)
    print('🚀 开始为项目-CONT1763015340创建测试数据...')
    print('='*60)
    create_test_data()
