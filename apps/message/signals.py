import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.department.models import Department
from apps.user.models import Admin

logger = logging.getLogger(__name__)


def sync_managed_conversation_groups():
    try:
        from apps.message.services import ConversationService
        ConversationService.sync_system_conversations()
    except Exception:
        logger.exception('同步企业沟通默认群失败')


@receiver(post_save, sender=Admin, dispatch_uid='message.sync_groups_on_admin_save')
@receiver(post_delete, sender=Admin, dispatch_uid='message.sync_groups_on_admin_delete')
@receiver(post_save, sender=Department, dispatch_uid='message.sync_groups_on_department_save')
@receiver(post_delete, sender=Department, dispatch_uid='message.sync_groups_on_department_delete')
def sync_groups_on_org_change(sender, **kwargs):
    sync_managed_conversation_groups()
