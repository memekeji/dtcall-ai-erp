from django.core.management.base import BaseCommand
from apps.message.models import MessageCategory


class Command(BaseCommand):
    help = '初始化消息分类数据'

    def handle(self, *args, **options):
        categories = [
            {
                'name': '公告通知',
                'code': 'announcement',
                'type': 'announcement',
                'icon': 'layui-icon-speaker',
                'description': '系统公告和公司动态通知',
                'sort_order': 1
            },
            {
                'name': '审批通知',
                'code': 'approval',
                'type': 'approval',
                'icon': 'layui-icon-survey',
                'description': '审批流程相关通知',
                'sort_order': 2
            },
            {
                'name': '任务通知',
                'code': 'task',
                'type': 'task',
                'icon': 'layui-icon-task',
                'description': '任务分配和状态变更通知',
                'sort_order': 3
            },
            {
                'name': '评论回复',
                'code': 'comment',
                'type': 'comment',
                'icon': 'layui-icon-reply-fill',
                'description': '评论和回复通知',
                'sort_order': 4
            },
            {
                'name': '系统通知',
                'code': 'system',
                'type': 'system',
                'icon': 'layui-icon-set',
                'description': '系统维护和政策更新通知',
                'sort_order': 5
            }
        ]

        for cat_data in categories:
            category, created = MessageCategory.objects.get_or_create(
                code=cat_data['code'],
                defaults=cat_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'创建消息分类: {category.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'消息分类已存在: {category.name}')
                )

        self.stdout.write(
            self.style.SUCCESS('消息分类初始化完成!')
        )
