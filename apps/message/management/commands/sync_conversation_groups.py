from django.core.management.base import BaseCommand

from apps.message.services import ConversationService


class Command(BaseCommand):
    help = '同步在线沟通默认公司全员群和部门群成员'

    def handle(self, *args, **options):
        summary = ConversationService.sync_system_conversations()
        self.stdout.write(self.style.SUCCESS(
            '同步完成：公司全员群ID {company_id}，部门群 {department_count} 个'.format(
                company_id=summary['company_group_id'],
                department_count=len(summary['department_group_ids']),
            )
        ))
