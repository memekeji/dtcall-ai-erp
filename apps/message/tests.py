from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.template.loader import render_to_string
from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.common.cache_service import MessageCache
from apps.message.models import (
    Conversation,
    ConversationMember,
    ConversationMessage,
    ConversationMessageReceipt,
    ConversationTaskLink,
    Message,
    MessageCategory,
    MessageUserRelation,
    NotificationPreference,
)
from apps.message.serializers import MessageListSerializer
from apps.message.services import (
    ApprovalNotificationService,
    ConversationMessageService,
    ConversationService,
    MessageTaskService,
    MessageService,
)
from apps.message.views import MessageViewSet
from apps.user.config.permission_nodes import PERMISSION_NODES
from apps.department.models import Department
from apps.project.models import Project, Task


@override_settings(ROOT_URLCONF='apps.message.test_urls')
class MessageSyncTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='message_user',
            password='test-pass-123',
            status=1,
        )
        self.category = MessageCategory.objects.create(
            name='测试通知',
            code='test_sync',
            type='system',
        )
        self.message = Message.objects.create(
            category=self.category,
            title='测试通知',
            content='这是一条测试通知',
        )
        MessageUserRelation.objects.create(message=self.message, user=self.user)
        MessageCache.invalidate_unread_count(self.user.id)

    def make_batch_request(self, operation, message_ids=None):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        request = APIRequestFactory().post(
            '/message/messages/batch_operation/',
            {
                'message_ids': message_ids or [self.message.id],
                'operation': operation,
            },
            format='json',
        )
        force_authenticate(request, user=self.user)
        view = MessageViewSet.as_view({'post': 'batch_operation'})
        return view(request)

    def create_related_message(self, title, **relation_kwargs):
        message = Message.objects.create(
            category=self.category,
            title=title,
            content='批量操作测试消息',
        )
        MessageUserRelation.objects.create(
            message=message,
            user=self.user,
            **relation_kwargs,
        )
        MessageCache.invalidate_unread_count(self.user.id)
        return message

    def test_unread_count_calculates_when_cache_missing(self):
        self.assertEqual(MessageService.get_unread_count(self.user), 1)

    def test_unread_count_includes_conversation_receipts(self):
        sender = get_user_model().objects.create_user(
            username='message_sender',
            password='test-pass-123',
            status=1,
        )
        conversation = ConversationService.get_or_create_direct(
            sender,
            self.user,
        )
        ConversationMessageService.send_text(
            conversation,
            sender,
            '请查看项目沟通消息',
        )
        MessageCache.invalidate_unread_count(self.user.id)

        self.assertEqual(MessageService.get_unread_count(self.user), 2)

    def test_mark_read_and_unread_update_unread_count(self):
        self.assertTrue(MessageService.mark_as_read(self.message.id, self.user))
        self.assertEqual(MessageService.get_unread_count(self.user), 0)

        self.assertTrue(MessageService.mark_as_unread(self.message.id, self.user))
        self.assertEqual(MessageService.get_unread_count(self.user), 1)

    def test_read_api_invalidates_unread_count_cache(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        request = APIRequestFactory().post(
            f'/message/messages/{self.message.id}/read/'
        )
        force_authenticate(request, user=self.user)
        view = MessageViewSet.as_view({'post': 'read'})

        self.assertEqual(MessageService.get_unread_count(self.user), 1)
        response = view(request, pk=self.message.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(MessageService.get_unread_count(self.user), 0)

    def test_batch_read_returns_real_count_and_invalidates_unread_cache(self):
        read_message = self.create_related_message('已读消息', is_read=True)

        self.assertEqual(MessageService.get_unread_count(self.user), 1)
        response = self.make_batch_request(
            'read',
            [self.message.id, read_message.id],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['affected_count'], 1)
        self.assertEqual(MessageService.get_unread_count(self.user), 0)

    def test_batch_unread_returns_real_count_and_invalidates_unread_cache(self):
        MessageService.mark_as_read(self.message.id, self.user)

        self.assertEqual(MessageService.get_unread_count(self.user), 0)
        response = self.make_batch_request('unread')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['affected_count'], 1)
        self.assertEqual(MessageService.get_unread_count(self.user), 1)

    def test_batch_delete_removes_relations_and_invalidates_unread_cache(self):
        read_message = self.create_related_message('要删除的已读消息', is_read=True)

        self.assertEqual(MessageService.get_unread_count(self.user), 1)
        response = self.make_batch_request(
            'delete',
            [self.message.id, read_message.id],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['affected_count'], 2)
        self.assertFalse(
            MessageUserRelation.objects.filter(
                user=self.user,
                message_id__in=[self.message.id, read_message.id],
            ).exists()
        )
        self.assertEqual(MessageService.get_unread_count(self.user), 0)

    def test_batch_star_and_unstar_return_real_count(self):
        starred_message = self.create_related_message(
            '已标星消息',
            is_starred=True,
        )

        response = self.make_batch_request(
            'star',
            [self.message.id, starred_message.id],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['affected_count'], 1)

        response = self.make_batch_request(
            'unstar',
            [self.message.id, starred_message.id],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['affected_count'], 2)

    def test_list_serializer_exposes_category_object_for_center_template(self):
        serializer = MessageListSerializer(
            self.message,
            context={'request': type('Request', (), {'user': self.user})()}
        )

        self.assertEqual(serializer.data['category']['name'], self.category.name)
        self.assertEqual(serializer.data['category']['code'], self.category.code)
        self.assertEqual(serializer.data['category']['icon'], self.category.icon)

    def test_notification_preferences_filter_category_not_message_center_delivery(self):
        NotificationPreference.objects.create(
            user=self.user,
            enable_browser=False,
            notify_system=False,
        )

        self.assertEqual(
            MessageService.filter_user_ids_by_preferences([self.user.id], 'system'),
            set(),
        )

        self.assertEqual(
            MessageService.filter_user_ids_by_preferences([self.user.id], 'approval'),
            {self.user.id},
        )

    def test_approval_comment_notification_has_detail_action_url(self):
        approval = type('ApprovalStub', (), {
            'id': 123,
            'title': '费用审批',
        })()

        ApprovalNotificationService.notify_approval_comment(
            approval=approval,
            user_id=self.user.id,
            commenter_name='审批人',
            comment='请补充附件',
        )

        message = Message.objects.get(
            related_object_type='approval_comment',
            related_object_id=approval.id,
        )
        self.assertEqual(message.action_url, '/approval/123/')


@override_settings(ROOT_URLCONF='apps.message.test_urls')
class MessageCenterCompatibilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='compat_user',
            password='test-pass-123',
            status=1,
        )
        self.category = MessageCategory.objects.create(
            name='系统通知',
            code='system',
            type='system',
        )
        MessageCache.invalidate_unread_count(self.user.id)

    def test_send_notification_creates_message_relation_and_unread_count(self):
        message = MessageService.send_notification(
            title='兼容通知',
            content='保持现有站内信行为',
            category_code='system',
            user_ids=[self.user.id],
        )

        self.assertIsNotNone(message)
        self.assertTrue(
            MessageUserRelation.objects.filter(
                message=message,
                user=self.user,
                is_read=False,
            ).exists()
        )
        self.assertEqual(MessageService.get_unread_count(self.user), 1)

    def test_mark_all_as_read_invalidates_unread_state(self):
        MessageService.send_notification(
            title='待读通知',
            content='需要全部已读',
            category_code='system',
            user_ids=[self.user.id],
        )
        self.assertEqual(MessageService.get_unread_count(self.user), 1)

        count = MessageService.mark_all_as_read(self.user)

        self.assertEqual(count, 1)
        self.assertEqual(MessageService.get_unread_count(self.user), 0)

    def test_mark_all_as_read_clears_notification_and_conversation_unread(self):
        sender = get_user_model().objects.create_user(
            username='compat_sender',
            password='test-pass-123',
            status=1,
        )
        MessageService.send_notification(
            title='通知未读',
            content='需要统一清理',
            category_code='system',
            user_ids=[self.user.id],
        )
        conversation = ConversationService.get_or_create_direct(
            sender,
            self.user,
        )
        ConversationMessageService.send_text(
            conversation,
            sender,
            '会话未读也应被清理',
        )
        MessageCache.invalidate_unread_count(self.user.id)
        self.assertEqual(MessageService.get_unread_count(self.user), 2)

        count = MessageService.mark_all_as_read(self.user)

        self.assertEqual(count, 2)
        self.assertEqual(MessageService.get_unread_count(self.user), 0)
        self.assertEqual(
            ConversationMessageService.get_unread_count(self.user),
            0,
        )


@override_settings(ROOT_URLCONF='apps.message.test_urls')
class ConversationModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(
            username='alice',
            password='pw',
            status=1,
        )
        self.bob = User.objects.create_user(
            username='bob',
            password='pw',
            status=1,
        )

    def test_direct_conversation_is_unique_for_same_two_users(self):
        first = ConversationService.get_or_create_direct(self.alice, self.bob)
        second = ConversationService.get_or_create_direct(self.bob, self.alice)

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.conversation_type, Conversation.TYPE_DIRECT)
        self.assertEqual(first.members.count(), 2)

    def test_group_conversation_records_owner_and_members(self):
        group = ConversationService.create_group(
            owner=self.alice,
            name='项目沟通群',
            member_ids=[self.bob.id],
        )

        owner_member = group.member_relations.get(user=self.alice)
        bob_member = group.member_relations.get(user=self.bob)
        self.assertEqual(group.conversation_type, Conversation.TYPE_GROUP)
        self.assertEqual(owner_member.role, 'owner')
        self.assertEqual(bob_member.role, 'member')

    def test_pin_conversation_updates_only_actor_membership(self):
        group = ConversationService.create_group(
            owner=self.alice,
            name='置顶测试群',
            member_ids=[self.bob.id],
        )

        member = ConversationService.set_conversation_pinned(
            group,
            self.bob,
            True,
        )

        self.assertTrue(member.is_pinned)
        self.assertFalse(
            group.member_relations.get(user=self.alice).is_pinned
        )


@override_settings(ROOT_URLCONF='apps.message.test_urls')
class ConversationSystemGroupSyncTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.sales = Department.objects.create(name='销售部', status=1, sort=1)
        self.service = Department.objects.create(name='客服部', status=1, sort=2)
        self.alice = User.objects.create_user(
            username='sync_alice',
            password='pw',
            status=1,
            did=self.sales.id,
        )
        self.bob = User.objects.create_user(
            username='sync_bob',
            password='pw',
            status=1,
            did=self.sales.id,
        )
        self.carol = User.objects.create_user(
            username='sync_carol',
            password='pw',
            status=1,
            did=self.service.id,
        )

    def active_member_ids(self, conversation):
        return set(
            conversation.member_relations.filter(
                left_at__isnull=True,
            ).values_list('user_id', flat=True)
        )

    def test_sync_creates_company_and_department_groups(self):
        summary = ConversationService.sync_system_conversations()

        company = Conversation.objects.get(
            conversation_type=Conversation.TYPE_GROUP,
            metadata__system_group='company',
        )
        sales_group = Conversation.objects.get(
            conversation_type=Conversation.TYPE_DEPARTMENT,
            metadata__system_group='department',
            metadata__department_id=self.sales.id,
        )
        service_group = Conversation.objects.get(
            conversation_type=Conversation.TYPE_DEPARTMENT,
            metadata__system_group='department',
            metadata__department_id=self.service.id,
        )

        self.assertEqual(company.name, '公司全员群')
        self.assertEqual(summary['company_group_id'], company.id)
        self.assertIn(sales_group.id, summary['department_group_ids'])
        self.assertIn(service_group.id, summary['department_group_ids'])
        self.assertEqual(
            self.active_member_ids(company),
            {self.alice.id, self.bob.id, self.carol.id},
        )
        self.assertEqual(
            self.active_member_ids(sales_group),
            {self.alice.id, self.bob.id},
        )
        self.assertEqual(
            self.active_member_ids(service_group),
            {self.carol.id},
        )

    def test_sync_moves_and_removes_members_when_personnel_changes(self):
        ConversationService.sync_system_conversations()
        self.bob.did = self.service.id
        self.bob.save(update_fields=['did'])
        self.carol.status = 2
        self.carol.save(update_fields=['status'])

        ConversationService.sync_system_conversations()

        company = Conversation.objects.get(metadata__system_group='company')
        sales_group = Conversation.objects.get(
            metadata__system_group='department',
            metadata__department_id=self.sales.id,
        )
        service_group = Conversation.objects.get(
            metadata__system_group='department',
            metadata__department_id=self.service.id,
        )
        self.assertEqual(self.active_member_ids(company), {self.alice.id, self.bob.id})
        self.assertEqual(self.active_member_ids(sales_group), {self.alice.id})
        self.assertEqual(self.active_member_ids(service_group), {self.bob.id})
        self.assertTrue(
            ConversationMember.objects.filter(
                conversation=company,
                user=self.carol,
                left_at__isnull=False,
            ).exists()
        )


@override_settings(ROOT_URLCONF='apps.message.test_urls')
class ConversationMessageServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(
            username='msg_alice',
            password='pw',
            status=1,
        )
        self.bob = User.objects.create_user(
            username='msg_bob',
            password='pw',
            status=1,
        )
        self.conversation = ConversationService.get_or_create_direct(
            self.alice,
            self.bob,
        )

    def test_send_message_creates_unread_receipt_for_other_member(self):
        message = ConversationMessageService.send_text(
            conversation=self.conversation,
            sender=self.alice,
            content='明天评审图纸',
        )

        receipt = message.receipts.get(user=self.bob)
        self.assertEqual(receipt.status, 'delivered')
        self.assertFalse(receipt.is_read)
        self.assertEqual(ConversationMessageService.get_unread_count(self.bob), 1)

    def test_mark_conversation_read_updates_receipts_and_member_cursor(self):
        message = ConversationMessageService.send_text(
            self.conversation,
            self.alice,
            '请确认',
        )

        count = ConversationMessageService.mark_conversation_read(
            self.conversation,
            self.bob,
        )

        self.assertEqual(count, 1)
        self.assertTrue(message.receipts.get(user=self.bob).is_read)
        self.assertEqual(ConversationMessageService.get_unread_count(self.bob), 0)
        member = self.conversation.member_relations.get(user=self.bob)
        self.assertEqual(member.last_read_message, message)

    def test_send_attachment_creates_file_message_with_metadata(self):
        message = ConversationMessageService.send_attachment(
            conversation=self.conversation,
            sender=self.alice,
            file_url='/media/conversations/1/report.pdf',
            file_name='report.pdf',
            file_size=2048,
            content_type='application/pdf',
        )

        self.assertEqual(message.message_type, ConversationMessage.TYPE_FILE)
        self.assertEqual(message.content, 'report.pdf')
        self.assertEqual(message.metadata['file_url'], '/media/conversations/1/report.pdf')
        self.assertEqual(message.metadata['file_name'], 'report.pdf')
        self.assertEqual(message.metadata['file_size'], 2048)
        self.assertEqual(message.metadata['content_type'], 'application/pdf')
        self.assertEqual(ConversationMessageService.get_unread_count(self.bob), 1)


@override_settings(ROOT_URLCONF='apps.message.test_urls')
class ConversationAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(
            username='api_alice',
            password='pw',
            status=1,
            is_superuser=True,
        )
        self.bob = User.objects.create_user(
            username='api_bob',
            password='pw',
            status=1,
        )
        self.client = APIClient()
        self.client.force_login(self.alice)

    def test_direct_endpoint_creates_or_returns_conversation(self):
        response = self.client.post(
            '/message/conversations/direct/',
            {'user_id': self.bob.id},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['conversation_type'], Conversation.TYPE_DIRECT)
        self.assertEqual(
            set(response.data['member_ids']),
            {self.alice.id, self.bob.id},
        )

    def test_group_endpoint_creates_group_conversation(self):
        response = self.client.post(
            '/message/conversations/groups/',
            {'name': '项目群', 'member_ids': [self.bob.id]},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['name'], '项目群')
        self.assertEqual(response.data['conversation_type'], Conversation.TYPE_GROUP)

    def test_list_returns_only_current_user_conversations(self):
        own = ConversationService.get_or_create_direct(self.alice, self.bob)
        other = Conversation.objects.create(conversation_type=Conversation.TYPE_GROUP, name='其它群')

        response = self.client.get('/message/conversations/')

        self.assertEqual(response.status_code, 200)
        ids = {item['id'] for item in response.data['results']}
        self.assertIn(own.id, ids)
        self.assertNotIn(other.id, ids)

    def test_pinned_conversation_is_marked_and_sorted_first(self):
        first = ConversationService.create_group(
            self.alice,
            '普通群',
            [self.bob.id],
        )
        pinned = ConversationService.create_group(
            self.alice,
            '置顶群',
            [self.bob.id],
        )

        response = self.client.post(
            f'/message/conversations/{pinned.id}/pin/',
            {'is_pinned': True},
            format='json',
        )
        list_response = self.client.get('/message/conversations/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_pinned'])
        self.assertEqual(list_response.data['results'][0]['id'], pinned.id)
        self.assertTrue(list_response.data['results'][0]['is_pinned'])
        self.assertIn(first.id, {item['id'] for item in list_response.data['results']})

    def test_messages_endpoint_sends_message(self):
        conversation = ConversationService.get_or_create_direct(self.alice, self.bob)

        response = self.client.post(
            f'/message/conversations/{conversation.id}/messages/',
            {'content': '请看项目计划'},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['content'], '请看项目计划')
        self.assertEqual(response.data['sender']['id'], self.alice.id)
        self.assertEqual(ConversationMessageService.get_unread_count(self.bob), 1)

    def test_messages_endpoint_accepts_collaboration_card_payload(self):
        conversation = ConversationService.get_or_create_direct(self.alice, self.bob)

        response = self.client.post(
            f'/message/conversations/{conversation.id}/messages/',
            {
                'message_type': 'card',
                'metadata': {
                    'type': 'collaboration_card',
                    'module': 'project',
                    'module_name': '项目',
                    'item_id': 12,
                    'title': '协同项目',
                    'url': '/project/detail/12/',
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['message_type'], ConversationMessage.TYPE_TEXT)
        self.assertEqual(response.data['metadata']['type'], 'collaboration_card')
        self.assertEqual(response.data['metadata']['module'], 'project')
        self.assertEqual(response.data['content'], '[项目] 协同项目')

    def test_messages_endpoint_sends_reply_with_mentions(self):
        conversation = ConversationService.get_or_create_direct(self.alice, self.bob)
        original = ConversationMessageService.send_text(
            conversation,
            self.bob,
            '请确认设计稿',
        )

        response = self.client.post(
            f'/message/conversations/{conversation.id}/messages/',
            {
                'content': '@api_bob 已确认',
                'reply_to': original.id,
                'metadata': {'mentions': [self.bob.id]},
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['reply_to'], original.id)
        self.assertEqual(response.data['reply_to_message']['id'], original.id)
        self.assertEqual(response.data['metadata']['mentions'], [self.bob.id])
        mention_notice = MessageUserRelation.objects.get(user=self.bob)
        self.assertFalse(mention_notice.is_read)
        self.assertEqual(
            mention_notice.message.related_object_type,
            'conversation_message',
        )
        self.assertEqual(
            mention_notice.message.related_object_id,
            response.data['id'],
        )

    def test_mentions_notify_only_active_conversation_members(self):
        conversation = ConversationService.get_or_create_direct(self.alice, self.bob)
        outsider = get_user_model().objects.create_user(
            username='api_outsider',
            password='pw',
            status=1,
        )

        response = self.client.post(
            f'/message/conversations/{conversation.id}/messages/',
            {
                'content': '@api_bob @api_alice @api_outsider 请关注',
                'metadata': {'mentions': [self.bob.id, self.alice.id, outsider.id]},
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(MessageUserRelation.objects.filter(user=self.bob).exists())
        self.assertFalse(MessageUserRelation.objects.filter(user=self.alice).exists())
        self.assertFalse(MessageUserRelation.objects.filter(user=outsider).exists())

    def test_upload_message_endpoint_saves_image_message(self):
        conversation = ConversationService.get_or_create_direct(self.alice, self.bob)
        image = SimpleUploadedFile(
            'clipboard.png',
            b'\x89PNG\r\n\x1a\nimage-bytes',
            content_type='image/png',
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL='/media/'):
                response = self.client.post(
                    f'/message/conversations/{conversation.id}/messages/upload/',
                    {'file': image},
                    format='multipart',
                )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['message_type'], ConversationMessage.TYPE_IMAGE)
        self.assertEqual(response.data['content'], 'clipboard.png')
        self.assertEqual(response.data['metadata']['file_name'], 'clipboard.png')
        self.assertEqual(response.data['metadata']['content_type'], 'image/png')
        self.assertTrue(response.data['metadata']['file_url'].startswith('/media/conversations/'))
        self.assertEqual(ConversationMessageService.get_unread_count(self.bob), 1)

    def test_read_endpoint_marks_conversation_read(self):
        conversation = ConversationService.get_or_create_direct(self.alice, self.bob)
        ConversationMessageService.send_text(conversation, self.bob, '收到请回复')

        response = self.client.post(
            f'/message/conversations/{conversation.id}/read/',
            {},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['read_count'], 1)
        self.assertEqual(ConversationMessageService.get_unread_count(self.alice), 0)

    def test_contacts_endpoint_returns_active_organization_users(self):
        response = self.client.get('/message/contacts/?q=api_b')

        self.assertEqual(response.status_code, 200)
        ids = {item['id'] for item in response.data['results']}
        self.assertIn(self.bob.id, ids)
        self.assertNotIn(self.alice.id, ids)

    def test_contacts_endpoint_can_return_organization_grouped_users(self):
        sales = Department.objects.create(name='销售部', status=1, sort=1)
        service = Department.objects.create(name='客服部', status=1, sort=2)
        self.bob.did = sales.id
        self.bob.save(update_fields=['did'])
        carol = get_user_model().objects.create_user(
            username='api_carol',
            password='pw',
            status=1,
            did=service.id,
        )

        response = self.client.get('/message/contacts/?grouped=1')

        self.assertEqual(response.status_code, 200)
        groups = {group['name']: group for group in response.data['groups']}
        self.assertIn('公司全员', groups)
        self.assertIn('销售部', groups)
        self.assertIn('客服部', groups)
        self.assertIn(self.bob.id, {user['id'] for user in groups['销售部']['users']})
        self.assertIn(carol.id, {user['id'] for user in groups['客服部']['users']})
        self.assertNotIn(
            self.alice.id,
            {user['id'] for user in groups['公司全员']['users']},
        )


class ConversationTemplateTests(TestCase):
    @override_settings(ROOT_URLCONF='apps.message.test_urls')
    def test_conversation_center_page_url_is_not_captured_by_api_router(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='conversation_page_user',
            password='pw',
            status=1,
            is_superuser=True,
        )
        client = APIClient()
        client.force_login(user)

        response = client.get('/message/conversations/page/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '在线沟通')
        self.assertContains(response, 'conversation-shell')

    def test_conversation_center_script_runs_after_base_assets(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='template_user',
            password='pw',
            status=1,
            is_superuser=True,
        )
        html = render_to_string(
            'message/conversation_center.html',
            {'request': type('Request', (), {'user': user})(), 'csrf_token': 'test-token'},
        )

        self.assertIn('js/common.js', html)
        self.assertLess(html.index('js/common.js'), html.index("layui.use(['layer']"))
        self.assertIn('href="/message/page/"', html)
        self.assertIn('groupContactList', html)
        self.assertIn('renderContactGroups', html)
        self.assertIn('contact-group', html)
        self.assertIn('memberList', html)
        self.assertIn('renderMembers', html)
        self.assertIn('会话成员', html)
        self.assertIn('conversationContextMenu', html)
        self.assertIn('togglePinConversation', html)
        self.assertIn('is_pinned', html)
        self.assertIn('contact-group-toggle', html)
        self.assertIn('collapsedContactGroups', html)
        self.assertIn('group-picker-layout', html)
        self.assertIn('mentionPanel', html)
        self.assertIn('replyPreview', html)
        self.assertIn('reply_to', html)
        self.assertIn('metadata: {mentions:', html)
        self.assertIn('taskAssigneeSelect', html)
        self.assertIn('/project/api/projects/', html)
        self.assertIn('attachmentInput', html)
        self.assertIn('imageInput', html)
        self.assertIn("addEventListener('paste'", html)
        self.assertIn('uploadAttachment', html)
        self.assertIn('renderMessageContent', html)
        self.assertIn('message-image-preview', html)
        self.assertIn('message-file-card', html)
        self.assertIn('notifyParentMessageStateChange', html)
        self.assertIn('showIncomingMessageNotice', html)
        self.assertIn('.conversation-item.has-unread', html)
        self.assertNotIn('转任务功能开发中', html)
        self.assertIn('function openMessageShareDialog(module, itemId, messageId)', html)
        self.assertIn('function openCollaborationShareDialog()', html)
        self.assertIn("openMessageShareDialog(module, itemId, messageId);", html)
        self.assertIn("openCollaborationShareDialog();", html)
        self.assertIn("approval: '/approval/' + itemId + '/'", html)
        self.assertIn("task: '/task/detail/' + itemId + '/'", html)
        self.assertIn("production: '/production/task/plan/detail/' + itemId + '/'", html)
        self.assertIn("finance: '/finance/expense/view/' + itemId + '/'", html)
        self.assertNotIn('/approval/instance/detail/', html)
        self.assertNotIn('/project/task/detail/', html)
        self.assertNotIn('/production/plan/detail/', html)
        self.assertNotIn('/finance/expense/detail/', html)
        self.assertIn("item.status_display || item.status", html)
        self.assertNotIn("(item.status ? '<span class=\"collaboration-item-status\">' + escapeHtml(item.status) + '</span>' : '')", html)
        self.assertIn("moduleId === 'file' || moduleId === 'disk'", html)
        self.assertIn("file: '/disk/file/preview/' + itemId + '/'", html)
        self.assertIn('data-send-module', html)
        self.assertIn('data-send-item-id', html)
        self.assertIn('data-send-status-display', html)
        self.assertIn("sendLink.getAttribute('data-send-module')", html)
        self.assertIn("item_id: sendLink.getAttribute('data-send-item-id')", html)
        self.assertIn('share-dialog-layout', html)
        self.assertIn('share-dialog-sidebar', html)
        self.assertIn('share-dialog-main', html)
        self.assertIn('share-dialog-selected', html)
        self.assertIn('share-type-filters', html)
        self.assertIn('share-selected-list', html)
        self.assertIn('share-empty-hint', html)
        self.assertIn('renderShareTypeFilters', html)
        self.assertIn('renderSelectedShareItems', html)
        self.assertIn('filterShareItems', html)
        self.assertIn('share-quick-actions', html)
        self.assertIn('data-quick-actions', html)
        self.assertIn('data-item-type', html)
        self.assertIn('data-item-type-label', html)
        self.assertIn('shareSummaryText', html)

    def test_message_center_links_back_to_conversation_center(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='message_center_template_user',
            password='pw',
            status=1,
            is_superuser=True,
        )
        html = render_to_string(
            'message/message_center.html',
            {'request': type('Request', (), {'user': user})(), 'csrf_token': 'test-token'},
        )

        self.assertIn('href="/message/conversations/page/"', html)
        self.assertIn('href="/message/page/" class="active"', html)

    def test_home_message_bell_opens_unified_conversation_center(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='home_template_user',
            password='pw',
            status=1,
            is_superuser=True,
        )
        html = render_to_string(
            'home/base.html',
            {
                'request': type('Request', (), {'user': user})(),
                'configs': {},
                'database_menus': [],
            },
        )

        self.assertIn("addTab('/message/conversations/page/', '在线沟通')", html)
        self.assertNotIn("addTab('/message/page/', '消息中心')", html)

    def test_home_message_reminder_has_obvious_global_badges(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='home_badge_template_user',
            password='pw',
            status=1,
            is_superuser=True,
        )
        html = render_to_string(
            'home/base.html',
            {
                'request': type('Request', (), {'user': user})(),
                'configs': {},
                'database_menus': [
                    {
                        'title': '个人办公',
                        'src': 'javascript:;',
                        'submenus_list': [
                            {
                                'title': '沟通中心',
                                'src': '/message/conversations/page/',
                                'sort': 1,
                                'submenus_list': [],
                            },
                        ],
                    },
                ],
            },
        )

        self.assertIn('.message-bell.has-unread', html)
        self.assertIn('messageMenuBadge', html)
        self.assertIn('updateMessageMenuBadges', html)
        self.assertIn('updateUnreadDocumentTitle', html)
        self.assertIn('showMessageReminderToast', html)
        self.assertIn('aria-label="打开消息中心"', html)
        self.assertIn('data-message-menu-link="1"', html)

    def test_online_communication_permissions_are_under_personal_office(self):
        personal_children = PERMISSION_NODES['personal']['children']

        self.assertIn('conversation_center', personal_children)
        self.assertIn('message_center', personal_children)
        self.assertNotIn('message', PERMISSION_NODES)


class ProjectDetailTemplateTests(TestCase):
    def test_project_detail_supports_hash_navigation_for_docs_and_activities(self):
        template_path = Path('templates/project/detail.html')
        html = template_path.read_text(encoding='utf-8')

        self.assertIn('lay-id="docs"', html)
        self.assertIn('lay-id="purchases"', html)
        self.assertIn('lay-id="activities"', html)
        self.assertIn("window.location.hash.replace('#', '')", html)
        self.assertIn("element.tabChange('projectDetailTab', hashTabId);", html)

    def test_project_detail_statistics_tab_uses_actual_last_tab_index(self):
        template_path = Path('templates/project/detail.html')
        html = template_path.read_text(encoding='utf-8')

        self.assertIn('if (tabIndex === 9)', html)
        self.assertNotIn('if (tabIndex === 10)', html)


@override_settings(ROOT_URLCONF='apps.message.test_urls')
class ConversationExtendedAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username='group_owner',
            password='pw',
            status=1,
            is_superuser=True,
        )
        self.member = User.objects.create_user(
            username='group_member',
            password='pw',
            status=1,
        )
        self.new_member = User.objects.create_user(
            username='group_new_member',
            password='pw',
            status=1,
        )
        self.client = APIClient()
        self.client.force_login(self.owner)
        self.group = ConversationService.create_group(
            owner=self.owner,
            name='完整功能群',
            member_ids=[self.member.id],
        )

    def test_group_owner_can_add_and_remove_members(self):
        add_response = self.client.post(
            f'/message/conversations/{self.group.id}/members/',
            {'user_ids': [self.new_member.id]},
            format='json',
        )

        self.assertEqual(add_response.status_code, 200)
        self.assertIn(self.new_member.id, add_response.data['member_ids'])

        remove_response = self.client.delete(
            f'/message/conversations/{self.group.id}/members/{self.new_member.id}/',
            format='json',
        )

        self.assertEqual(remove_response.status_code, 200)
        self.assertFalse(
            self.group.member_relations.filter(
                user=self.new_member,
                left_at__isnull=True,
            ).exists()
        )

    def test_non_manager_cannot_add_members(self):
        self.client.force_login(self.member)

        response = self.client.post(
            f'/message/conversations/{self.group.id}/members/',
            {'user_ids': [self.new_member.id]},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_receipts_endpoint_returns_read_and_unread_users(self):
        message = ConversationMessageService.send_text(
            self.group,
            self.owner,
            '请大家确认任务拆分',
        )
        ConversationMessageReceipt.objects.filter(
            message=message,
            user=self.member,
        ).update(
            status=ConversationMessageReceipt.STATUS_READ,
        )

        response = self.client.get(
            f'/message/conversations/{self.group.id}/messages/{message.id}/receipts/',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['message_id'], message.id)
        self.assertEqual(response.data['read_count'], 1)
        self.assertEqual(response.data['unread_count'], 0)

    def test_convert_message_to_task_creates_project_task_link(self):
        message = ConversationMessageService.send_text(
            self.group,
            self.owner,
            '整理上线前检查清单',
        )

        response = self.client.post(
            f'/message/conversations/{self.group.id}/messages/{message.id}/to-task/',
            {
                'title': '上线前检查清单',
                'assignee_id': self.member.id,
                'priority': 3,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['task']['title'], '上线前检查清单')
        self.assertTrue(
            ConversationTaskLink.objects.filter(
                message=message,
                task_id=response.data['task']['id'],
                created_by=self.owner,
            ).exists()
        )


@override_settings(ROOT_URLCONF='apps.message.test_urls')
class ConversationCollaborationAndShareTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(
            username='collab_alice',
            password='pw',
            status=1,
            is_superuser=True,
            name='Alice',
        )
        self.bob = User.objects.create_user(
            username='collab_bob',
            password='pw',
            status=1,
            name='Bob',
        )
        self.client = APIClient()
        self.client.force_login(self.alice)

    def test_collaboration_endpoint_returns_real_cross_module_items(self):
        from apps.customer.models import Customer, CustomerContract
        from apps.project.models import Project, Task
        from apps.approval.models import Approval
        from apps.finance.models import Expense

        customer = Customer.objects.create(
            name='华星客户',
            principal=self.alice,
            admin_id=self.bob.id,
        )
        project = Project.objects.create(
            name='协同项目',
            code='COLLAB-PJT-001',
            customer=customer,
            manager=self.alice,
            creator=self.bob,
        )
        project.members.add(self.bob)
        contract = CustomerContract.objects.create(
            customer=customer,
            contract_number='HT-COLLAB-001',
            name='年度合作合同',
            amount=1000,
            sign_date=date.today(),
            status='signed',
            create_user=self.bob,
        )
        task = Task.objects.create(
            title='联调任务',
            project=project,
            assignee=self.bob,
            creator=self.alice,
        )
        approval = Approval.objects.create(
            title='费用审批',
            applicant_id=self.alice.id,
            reviewer=self.bob,
            status=1,
        )
        expense = Expense.objects.create(
            code='BX-COLLAB-001',
            admin_id=self.alice.id,
            cost=200,
            check_uids=str(self.bob.id),
            check_status=1,
            create_time=1719000000,
        )

        response = self.client.get(
            f'/message/collaboration/?target_user_id={self.bob.id}'
        )

        self.assertEqual(response.status_code, 200)
        modules = {item['module']: item for item in response.data['modules']}
        self.assertEqual(response.data['target_user']['id'], self.bob.id)
        self.assertEqual(modules['customer']['items'][0]['url'], f'/customer/detail/{customer.id}/')
        self.assertEqual(modules['project']['items'][0]['url'], f'/project/detail/{project.id}/')
        self.assertEqual(modules['contract']['items'][0]['url'], f'/customer/orders/{contract.id}/detail/')
        self.assertEqual(modules['approval']['items'][0]['url'], f'/approval/{approval.id}/')
        self.assertEqual(modules['task']['items'][0]['url'], f'/task/detail/{task.id}/')
        self.assertEqual(modules['finance']['items'][0]['url'], f'/finance/expense/view/{expense.id}/')

    def test_share_content_approval_query_uses_real_fields(self):
        from apps.approval.models import Approval

        approval = Approval.objects.create(
            title='采购审批',
            applicant_id=self.alice.id,
            reviewer=self.bob,
            status=1,
        )

        response = self.client.get('/message/share/content/?module=approval')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], approval.id)
        self.assertEqual(response.data['results'][0]['title'], '采购审批')

    def test_share_content_production_uses_real_completion_rate(self):
        from decimal import Decimal
        from datetime import timedelta
        from django.utils import timezone
        from apps.contract.models import Product
        from apps.production.models import ProductionProcedure, ProductionPlan, ProductionTask

        product = Product.objects.create(
            name='协同产品',
            code='COLLAB-PROD-001',
            price=Decimal('88.00'),
            admin=self.alice,
        )
        procedure = ProductionProcedure.objects.create(
            name='切割',
            code='COLLAB-PROC-001',
            creator=self.alice,
        )
        plan = ProductionPlan.objects.create(
            name='共享生产计划',
            code='COLLAB-PLAN-001',
            product=product,
            quantity=Decimal('100'),
            unit='件',
            plan_start_date=timezone.now().date(),
            plan_end_date=(timezone.now() + timedelta(days=2)).date(),
            status=3,
            manager=self.alice,
            creator=self.alice,
        )
        ProductionTask.objects.create(
            plan=plan,
            name='切割任务',
            code='COLLAB-TASK-001',
            procedure=procedure,
            quantity=Decimal('100'),
            completed_quantity=Decimal('35'),
            plan_start_time=timezone.now(),
            plan_end_time=timezone.now() + timedelta(hours=4),
            status=2,
            assignee=self.alice,
            creator=self.alice,
        )

        response = self.client.get('/message/share/content/?module=production')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(
            {item['item_type'] for item in response.data['results']},
            {'plan', 'task'},
        )
        plan_item = next(item for item in response.data['results'] if item['item_type'] == 'plan')
        task_item = next(item for item in response.data['results'] if item['item_type'] == 'task')
        self.assertEqual(plan_item['id'], plan.id)
        self.assertEqual(plan_item['progress'], 35.0)
        self.assertEqual(task_item['title'], '切割任务')
        self.assertEqual(
            {item['id'] for item in response.data['type_filters']},
            {'all', 'plan', 'task'},
        )

    def test_share_content_finance_handles_timestamp_create_time(self):
        from apps.finance.models import Expense

        expense = Expense.objects.create(
            code='BX-SHARE-001',
            admin_id=self.alice.id,
            cost=Decimal('120.00'),
            check_status=1,
            create_time=1719000000,
        )

        response = self.client.get('/message/share/content/?module=finance')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], expense.id)
        self.assertEqual(response.data['results'][0]['title'], f'报销-{expense.code}')
        self.assertIn('item_type', response.data['results'][0])
        self.assertIn('quick_actions', response.data['results'][0])
        self.assertIn('type_filters', response.data)

    def test_collaboration_finance_matches_exact_user_ids_in_audit_fields(self):
        from apps.finance.models import Expense

        confusing_user = None
        for index in range(20):
            candidate = get_user_model().objects.create_user(
                username=f'collab_noise_{index}',
                password='pw',
                status=1,
                name=f'Noise {index}',
            )
            if str(self.bob.id) in str(candidate.id) and candidate.id != self.bob.id:
                confusing_user = candidate
                break

        self.assertIsNotNone(confusing_user)

        Expense.objects.create(
            code='BX-NOISE-001',
            admin_id=self.alice.id,
            cost=Decimal('88.00'),
            check_uids=str(confusing_user.id),
            check_status=1,
            create_time=1719000001,
        )

        response = self.client.get(
            f'/message/collaboration/?target_user_id={self.bob.id}'
        )

        self.assertEqual(response.status_code, 200)
        modules = {item['module']: item for item in response.data['modules']}
        self.assertNotIn('finance', modules)

    def test_collaboration_finance_formats_timestamp_dates_for_display(self):
        from apps.finance.models import Expense

        Expense.objects.create(
            code='BX-DATE-001',
            admin_id=self.alice.id,
            cost=Decimal('66.00'),
            check_uids=str(self.bob.id),
            check_status=1,
            create_time=1719000000,
        )

        response = self.client.get(
            f'/message/collaboration/?target_user_id={self.bob.id}'
        )

        self.assertEqual(response.status_code, 200)
        modules = {item['module']: item for item in response.data['modules']}
        finance_item = modules['finance']['items'][0]
        self.assertNotEqual(finance_item['date'], '1719000000')
        self.assertRegex(finance_item['date'], r'^\d{4}-\d{2}-\d{2}')

    def test_collaboration_finance_includes_invoice_detail_url(self):
        from apps.finance.models import Invoice

        invoice = Invoice.objects.create(
            code='FP-COLLAB-001',
            admin_id=self.alice.id,
            amount=Decimal('320.00'),
            check_uids=str(self.bob.id),
            check_status=1,
            open_status=1,
            create_time=1719000100,
        )

        response = self.client.get(
            f'/message/collaboration/?target_user_id={self.bob.id}'
        )

        self.assertEqual(response.status_code, 200)
        modules = {item['module']: item for item in response.data['modules']}
        finance_titles = {item['title']: item for item in modules['finance']['items']}
        self.assertEqual(
            finance_titles[f'开票-{invoice.code}']['url'],
            f'/finance/invoice/view/{invoice.id}/'
        )

    def test_collaboration_endpoint_returns_project_document_and_production_subtypes(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.contract.models import Product
        from apps.customer.models import Customer
        from apps.project.models import Project, ProjectDocument
        from apps.production.models import BOM, ProcessRoute, ProductionProcedure, ProductionPlan, ProductionTask

        customer = Customer.objects.create(
            name='多类型协同客户',
            principal=self.alice,
            admin_id=self.bob.id,
        )
        project = Project.objects.create(
            name='多类型协同项目',
            code='COLLAB-MULTI-PJT',
            customer=customer,
            manager=self.alice,
            creator=self.bob,
        )
        project.members.add(self.bob)
        document = ProjectDocument.objects.create(
            project=project,
            title='项目说明书',
            content='用于顶部协同栏测试',
            creator=self.alice,
        )

        product = Product.objects.create(
            name='多类型产品',
            code='COLLAB-MULTI-PROD',
            price=Decimal('56.00'),
            admin=self.alice,
        )
        procedure = ProductionProcedure.objects.create(
            name='焊接',
            code='COLLAB-WELD-001',
            creator=self.alice,
        )
        plan = ProductionPlan.objects.create(
            name='顶部协同生产计划',
            code='COLLAB-MULTI-PLAN',
            product=product,
            quantity=Decimal('50'),
            unit='件',
            plan_start_date=timezone.now().date(),
            plan_end_date=(timezone.now() + timedelta(days=3)).date(),
            status=3,
            manager=self.alice,
            creator=self.bob,
        )
        production_task = ProductionTask.objects.create(
            plan=plan,
            name='焊接任务',
            code='COLLAB-WELD-TASK',
            procedure=procedure,
            quantity=Decimal('50'),
            completed_quantity=Decimal('20'),
            plan_start_time=timezone.now(),
            plan_end_time=timezone.now() + timedelta(hours=8),
            status=2,
            assignee=self.alice,
            creator=self.bob,
        )
        route = ProcessRoute.objects.create(
            name='焊接路线',
            code='COLLAB-ROUTE-001',
            creator=self.alice,
        )
        bom = BOM.objects.create(
            name='焊接BOM',
            code='COLLAB-BOM-001',
            creator=self.bob,
        )

        response = self.client.get(
            f'/message/collaboration/?target_user_id={self.bob.id}'
        )

        self.assertEqual(response.status_code, 200)
        modules = {item['module']: item for item in response.data['modules']}

        project_types = {item['item_type'] for item in modules['project']['items']}
        self.assertIn('project', project_types)
        self.assertIn('document', project_types)
        project_doc = next(item for item in modules['project']['items'] if item['item_type'] == 'document')
        self.assertEqual(project_doc['title'], document.title)
        self.assertEqual(project_doc['url'], f'/project/document/detail/{document.id}/')
        self.assertIn('summary', project_doc)
        self.assertIn('quick_actions', project_doc)

        production_types = {item['item_type'] for item in modules['production']['items']}
        self.assertIn('plan', production_types)
        self.assertIn('task', production_types)
        self.assertIn('route', production_types)
        self.assertIn('bom', production_types)
        route_item = next(item for item in modules['production']['items'] if item['item_type'] == 'route')
        bom_item = next(item for item in modules['production']['items'] if item['item_type'] == 'bom')
        task_item = next(item for item in modules['production']['items'] if item['item_type'] == 'task')
        self.assertEqual(route_item['url'], f'/production/process/detail/{route.id}/')
        self.assertEqual(bom_item['url'], f'/production/bom/detail/{bom.id}/')
        self.assertEqual(task_item['title'], production_task.name)
        self.assertIn('quick_actions', task_item)

    def test_share_content_project_returns_project_and_document_types(self):
        from apps.project.models import Project, ProjectDocument

        project = Project.objects.create(
            name='多类型项目',
            code='SHARE-PROJECT-001',
            manager=self.alice,
            creator=self.alice,
            status=2,
        )
        document = ProjectDocument.objects.create(
            project=project,
            title='实施方案',
            content='项目文档内容',
            creator=self.alice,
        )

        response = self.client.get('/message/share/content/?module=project')

        self.assertEqual(response.status_code, 200)
        result_types = {item['item_type'] for item in response.data['results']}
        self.assertIn('project', result_types)
        self.assertIn('document', result_types)
        type_filter_ids = {item['id'] for item in response.data['type_filters']}
        self.assertIn('all', type_filter_ids)
        self.assertIn('project', type_filter_ids)
        self.assertIn('document', type_filter_ids)

    def test_share_content_finance_returns_expense_and_invoice_types(self):
        from apps.finance.models import Expense, Invoice

        expense = Expense.objects.create(
            code='BX-SHARE-MIX-001',
            admin_id=self.alice.id,
            cost=Decimal('88.00'),
            check_status=1,
            create_time=1719000200,
        )
        invoice = Invoice.objects.create(
            code='FP-SHARE-MIX-001',
            admin_id=self.alice.id,
            amount=Decimal('188.00'),
            check_status=1,
            open_status=1,
            create_time=1719000300,
        )

        response = self.client.get('/message/share/content/?module=finance')

        self.assertEqual(response.status_code, 200)
        type_map = {item['title']: item['item_type'] for item in response.data['results']}
        self.assertEqual(type_map[f'报销-{expense.code}'], 'expense')
        self.assertEqual(type_map[f'开票-{invoice.code}'], 'invoice')
        finance_filters = {item['id'] for item in response.data['type_filters']}
        self.assertIn('expense', finance_filters)
        self.assertIn('invoice', finance_filters)

    def test_share_content_production_returns_route_and_bom_detail_urls(self):
        from apps.production.models import BOM, ProcessRoute

        route = ProcessRoute.objects.create(
            name='装配路线',
            code='ROUTE-SHARE-001',
            creator=self.alice,
        )
        bom = BOM.objects.create(
            name='成品BOM',
            code='BOM-SHARE-001',
            creator=self.alice,
        )

        response = self.client.get('/message/share/content/?module=production')

        self.assertEqual(response.status_code, 200)
        item_map = {item['item_type']: item for item in response.data['results']}
        self.assertEqual(item_map['route']['id'], route.id)
        self.assertEqual(item_map['route']['url'], f'/production/process/detail/{route.id}/')
        self.assertEqual(item_map['bom']['id'], bom.id)
        self.assertEqual(item_map['bom']['url'], f'/production/bom/detail/{bom.id}/')
        type_filter_ids = {item['id'] for item in response.data['type_filters']}
        self.assertIn('route', type_filter_ids)
        self.assertIn('bom', type_filter_ids)


    def test_collaboration_customer_returns_follow_types(self):
        from apps.customer.models import Customer, FollowRecord

        customer = Customer.objects.create(
            name='跟进客户',
            principal=self.alice,
            admin_id=self.bob.id,
        )
        follow = FollowRecord.objects.create(
            customer=customer,
            follow_user=self.alice,
            follow_type='phone',
            content='已电话联系确认需求',
        )

        response = self.client.get(
            f'/message/collaboration/?target_user_id={self.bob.id}'
        )

        self.assertEqual(response.status_code, 200)
        modules = {item['module']: item for item in response.data['modules']}
        cust_items = modules['customer']['items']
        cust_types = {item['item_type'] for item in cust_items}
        self.assertIn('customer', cust_types)
        self.assertIn('follow', cust_types)
        follow_item = next(item for item in cust_items if item['item_type'] == 'follow')
        self.assertEqual(follow_item['title'], '电话沟通 - 跟进客户')
        self.assertEqual(follow_item['url'], f'/customer/detail/{customer.id}/')
        self.assertIn('quick_actions', follow_item)
        self.assertIn('view', follow_item['quick_actions'])

    def test_collaboration_approval_returns_task_types(self):
        from apps.approval.models import Approval, ApprovalFlow, ApprovalStep, ApprovalTask

        flow = ApprovalFlow.objects.create(name='测试流程', code='TEST_FLOW_001')
        step = ApprovalStep.objects.create(
            flow=flow,
            step_name='直属审批',
            step_order=1,
            step_type='user',
            action_type='approve',
            approver=self.alice,
            approval_mode='single',
        )
        approval = Approval.objects.create(
            title='报销审批',
            flow=flow,
            applicant_id=self.alice.id,
            status=1,
            current_step_order=1,
        )
        task = ApprovalTask.objects.create(
            approval=approval,
            step=step,
            handler=self.bob,
            status='pending',
        )

        response = self.client.get(
            f'/message/collaboration/?target_user_id={self.bob.id}'
        )

        self.assertEqual(response.status_code, 200)
        modules = {item['module']: item for item in response.data['modules']}
        appr_items = modules['approval']['items']
        appr_types = {item['item_type'] for item in appr_items}
        self.assertIn('approval', appr_types)
        self.assertIn('approval_task', appr_types)
        task_item = next(item for item in appr_items if item['item_type'] == 'approval_task')
        self.assertIn('直属审批', task_item['title'])
        self.assertEqual(task_item['url'], f'/approval/{approval.id}/')
        self.assertIn('quick_actions', task_item)
        self.assertIn('approve', task_item['quick_actions'])


@override_settings(ROOT_URLCONF='apps.message.test_urls')
class ConversationCardActionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username='card_owner',
            password='pw',
            status=1,
            is_superuser=True,
            name='Owner',
        )
        self.member = User.objects.create_user(
            username='card_member',
            password='pw',
            status=1,
            name='Member',
        )
        self.client = APIClient()
        self.client.force_login(self.owner)
        self.conversation = ConversationService.get_or_create_direct(
            self.owner,
            self.member,
        )
        self.project = Project.objects.create(
            name='卡片协同项目',
            code='CARD-PROJ-001',
            manager=self.owner,
            creator=self.owner,
        )

    def test_card_view_action_returns_fixed_detail_urls(self):
        payloads = [
            ('approval', '/approval/9/'),
            ('task', '/task/detail/9/'),
            ('production', '/production/task/plan/detail/9/'),
            ('finance', '/finance/expense/view/9/'),
            ('contract', '/customer/orders/9/detail/'),
            ('file', '/disk/file/preview/9/'),
        ]
        for module, expected_url in payloads:
            response = self.client.post(
                '/message/card/action/',
                {'action': 'view', 'module': module, 'item_id': 9},
                format='json',
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['url'], expected_url)

    def test_card_view_action_honors_explicit_metadata_url(self):
        response = self.client.post(
            '/message/card/action/',
            {
                'action': 'view',
                'module': 'finance',
                'item_id': 9,
                'metadata': {
                    'url': '/finance/invoice/view/9/'
                }
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['url'], '/finance/invoice/view/9/')

    def test_card_view_action_uses_item_type_specific_urls(self):
        payloads = [
            ('project', 'document', '/project/document/detail/9/'),
            ('finance', 'invoice', '/finance/invoice/view/9/'),
            ('production', 'bom', '/production/bom/detail/9/'),
            ('production', 'route', '/production/process/detail/9/'),
        ]
        for module, item_type, expected_url in payloads:
            response = self.client.post(
                '/message/card/action/',
                {
                    'action': 'view',
                    'module': module,
                    'item_id': 9,
                    'metadata': {'item_type': item_type},
                },
                format='json',
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['url'], expected_url)

    def test_card_follow_action_creates_follow_record(self):
        from apps.customer.models import Customer, FollowRecord

        customer = Customer.objects.create(
            name='跟进客户',
            principal=self.owner,
            admin_id=self.owner.id,
        )

        response = self.client.post(
            '/message/card/action/',
            {
                'action': 'follow',
                'module': 'customer',
                'item_id': customer.id,
                'content': '已电话跟进',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertTrue(
            FollowRecord.objects.filter(
                customer=customer,
                follow_user=self.owner,
                content='已电话跟进',
            ).exists()
        )

    def test_card_contact_action_creates_real_follow_record(self):
        from apps.customer.models import Customer, FollowRecord

        customer = Customer.objects.create(
            name='沟通客户',
            principal=self.owner,
            admin_id=self.owner.id,
        )

        response = self.client.post(
            '/message/card/action/',
            {
                'action': 'contact',
                'module': 'customer',
                'item_id': customer.id,
                'content': '已安排现场拜访并确认需求细节',
                'contact_type': 'visit',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['url'], f'/customer/detail/{customer.id}/')
        follow = FollowRecord.objects.get(customer=customer, follow_user=self.owner)
        self.assertEqual(follow.follow_type, 'visit')
        self.assertEqual(follow.content, '已安排现场拜访并确认需求细节')

    def test_card_complete_action_creates_explicit_system_notice(self):
        task = Task.objects.create(
            title='待完成任务',
            project=self.project,
            assignee=self.owner,
            creator=self.owner,
            status=2,
            progress=60,
        )

        response = self.client.post(
            '/message/card/action/',
            {
                'action': 'complete',
                'module': 'task',
                'item_id': task.id,
                'conversation_id': self.conversation.id,
                'message_id': 99,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        task.refresh_from_db()
        self.assertEqual(task.status, 3)
        self.assertEqual(task.progress, 100)

        notice = ConversationMessage.objects.filter(
            conversation=self.conversation,
            sender=self.owner,
            message_type=ConversationMessage.TYPE_SYSTEM,
            metadata__type='card_action_notice',
            metadata__action='complete',
            metadata__module='task',
        ).latest('id')
        self.assertEqual(notice.content, f'{self.owner.name}完成了任务')

    def test_card_approve_action_processes_real_approval_task(self):
        from apps.approval.models import Approval, ApprovalFlow, ApprovalStep, ApprovalTask, ApprovalRecord

        flow = ApprovalFlow.objects.create(name='卡片审批流程', code='CARD_APPROVAL_FLOW_001')
        step = ApprovalStep.objects.create(
            flow=flow,
            step_name='直属审批',
            step_order=1,
            step_type='user',
            action_type='approve',
            approver=self.owner,
            approval_mode='single',
        )
        approval = Approval.objects.create(
            title='卡片审批单',
            flow=flow,
            applicant_id=self.member.id,
            status=1,
            current_step_order=1,
        )
        approval_task = ApprovalTask.objects.create(
            approval=approval,
            step=step,
            handler=self.owner,
            status='pending',
        )

        response = self.client.post(
            '/message/card/action/',
            {
                'action': 'approve',
                'module': 'approval',
                'item_id': approval.id,
                'decision': 'approved',
                'comment': '同意，按流程执行',
                'conversation_id': self.conversation.id,
                'message_id': 77,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['url'], f'/approval/{approval.id}/')
        approval.refresh_from_db()
        approval_task.refresh_from_db()
        self.assertEqual(approval.status, 2)
        self.assertEqual(approval_task.status, 'completed')
        self.assertEqual(approval_task.result, 'approve')
        self.assertEqual(approval_task.comment, '同意，按流程执行')
        self.assertTrue(
            ApprovalRecord.objects.filter(
                approval=approval,
                action='approve',
                handler=self.owner,
                step_order=step.step_order,
                step_name=step.step_name,
                comment='同意，按流程执行',
            ).exists()
        )

    def test_card_reject_action_rejects_real_approval_task(self):
        from apps.approval.models import Approval, ApprovalFlow, ApprovalStep, ApprovalTask, ApprovalRecord

        flow = ApprovalFlow.objects.create(name='卡片拒绝流程', code='CARD_APPROVAL_FLOW_002')
        step = ApprovalStep.objects.create(
            flow=flow,
            step_name='经理审批',
            step_order=1,
            step_type='user',
            action_type='approve',
            approver=self.owner,
            approval_mode='single',
        )
        approval = Approval.objects.create(
            title='待拒绝审批单',
            flow=flow,
            applicant_id=self.member.id,
            status=1,
            current_step_order=1,
        )
        approval_task = ApprovalTask.objects.create(
            approval=approval,
            step=step,
            handler=self.owner,
            status='pending',
        )

        response = self.client.post(
            '/message/card/action/',
            {
                'action': 'approve',
                'module': 'approval',
                'item_id': approval.id,
                'decision': 'rejected',
                'comment': '资料不完整，请补充后重提',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        approval.refresh_from_db()
        approval_task.refresh_from_db()
        self.assertEqual(approval.status, 3)
        self.assertEqual(approval_task.status, 'completed')
        self.assertEqual(approval_task.result, 'reject')
        self.assertEqual(approval_task.comment, '资料不完整，请补充后重提')
        self.assertTrue(
            ApprovalRecord.objects.filter(
                approval=approval,
                action='reject',
                handler=self.owner,
                step_order=step.step_order,
                step_name=step.step_name,
                comment='资料不完整，请补充后重提',
            ).exists()
        )

    def test_card_sign_action_updates_contract_status(self):
        from apps.customer.models import Customer, CustomerContract

        customer = Customer.objects.create(
            name='签约客户',
            principal=self.owner,
            admin_id=self.owner.id,
        )
        contract = CustomerContract.objects.create(
            customer=customer,
            contract_number='HT-CARD-SIGN-001',
            name='待签署合同',
            amount=5000,
            sign_date=date.today(),
            status='pending',
            create_user=self.owner,
        )

        response = self.client.post(
            '/message/card/action/',
            {
                'action': 'sign',
                'module': 'contract',
                'item_id': contract.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        contract.refresh_from_db()
        self.assertEqual(contract.status, 'signed')

    def test_card_finance_approve_updates_audit_trail_fields(self):
        from apps.finance.models import Expense

        expense = Expense.objects.create(
            code='BX-CARD-001',
            admin_id=self.member.id,
            cost=300,
            check_status=1,
            check_last_uid='',
            check_history_uids='',
            create_time=1719000000,
        )

        response = self.client.post(
            '/message/card/action/',
            {
                'action': 'approve_finance',
                'module': 'finance',
                'item_id': expense.id,
                'decision': 'approved',
                'comment': '同意报销',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        expense.refresh_from_db()
        self.assertEqual(expense.check_status, 2)
        self.assertEqual(expense.check_last_uid, str(self.owner.id))
        self.assertIn(str(self.owner.id), expense.check_history_uids)
        self.assertGreater(expense.check_time, 0)

    def test_card_comment_action_creates_real_task_comment(self):
        from django.contrib.contenttypes.models import ContentType
        from apps.project.models import Comment

        task = Task.objects.create(
            title='待评论任务',
            project=self.project,
            assignee=self.member,
            creator=self.owner,
        )

        response = self.client.post(
            '/message/card/action/',
            {
                'action': 'comment',
                'module': 'task',
                'item_id': task.id,
                'comment': '请今天补充现场巡检记录',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        task_type = ContentType.objects.get_for_model(Task)
        self.assertTrue(
            Comment.objects.filter(
                content_type=task_type,
                object_id=task.id,
                user=self.owner,
                content='请今天补充现场巡检记录',
            ).exists()
        )

    def test_card_update_action_updates_real_production_task_progress(self):
        from decimal import Decimal
        from datetime import timedelta
        from django.utils import timezone
        from apps.contract.models import Product
        from apps.production.models import ProductionProcedure, ProductionPlan, ProductionTask

        product = Product.objects.create(
            name='测试产品',
            code='PROD-CARD-001',
            price=Decimal('100'),
            admin=self.owner,
        )
        procedure = ProductionProcedure.objects.create(
            name='装配',
            code='PROC-CARD-001',
            creator=self.owner,
        )
        plan = ProductionPlan.objects.create(
            name='测试生产计划',
            code='PLAN-CARD-001',
            product=product,
            quantity=Decimal('100'),
            unit='件',
            plan_start_date=timezone.now().date(),
            plan_end_date=(timezone.now() + timedelta(days=3)).date(),
            status=3,
            manager=self.owner,
            creator=self.owner,
        )
        task = ProductionTask.objects.create(
            plan=plan,
            name='装配任务',
            code='TASK-CARD-001',
            procedure=procedure,
            quantity=Decimal('100'),
            completed_quantity=Decimal('0'),
            plan_start_time=timezone.now(),
            plan_end_time=timezone.now() + timedelta(hours=8),
            status=2,
            assignee=self.owner,
            creator=self.owner,
        )

        response = self.client.post(
            '/message/card/action/',
            {
                'action': 'update',
                'module': 'production',
                'item_id': plan.id,
                'progress': 75,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        task.refresh_from_db()
        self.assertEqual(task.completed_quantity, Decimal('75'))
        self.assertEqual(response.data['progress'], 75)


@override_settings(ROOT_URLCONF='apps.message.test_urls')
class MessageTaskServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.creator = User.objects.create_user(
            username='task_creator',
            password='pw',
            status=1,
        )
        self.assignee = User.objects.create_user(
            username='task_assignee',
            password='pw',
            status=1,
        )
        self.conversation = ConversationService.get_or_create_direct(
            self.creator,
            self.assignee,
        )
        self.message = ConversationMessageService.send_text(
            self.conversation,
            self.creator,
            '安排材料采购',
        )

    def test_convert_message_creates_task_and_link(self):
        task = MessageTaskService.convert_to_task(
            message=self.message,
            creator=self.creator,
            title='材料采购',
            assignee_id=self.assignee.id,
        )

        self.assertEqual(task.title, '材料采购')
        self.assertEqual(task.creator, self.creator)
        self.assertEqual(task.assignee, self.assignee)
        self.assertTrue(
            ConversationTaskLink.objects.filter(
                message=self.message,
                task=task,
            ).exists()
        )


@override_settings(
    ROOT_URLCONF='apps.message.test_urls',
    CHANNEL_LAYERS={
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    },
)
class ConversationRealtimeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.alice = User.objects.create_user(
            username='rt_alice',
            password='pw',
            status=1,
            is_superuser=True,
        )
        self.bob = User.objects.create_user(
            username='rt_bob',
            password='pw',
            status=1,
        )
        self.conversation = ConversationService.get_or_create_direct(
            self.alice,
            self.bob,
        )

    def test_send_message_publishes_realtime_event_to_conversation_group(self):
        channel_layer = get_channel_layer()
        channel_name = async_to_sync(channel_layer.new_channel)()
        async_to_sync(channel_layer.group_add)(
            f'message_conversation_{self.conversation.id}',
            channel_name,
        )

        message = ConversationMessageService.send_text(
            self.conversation,
            self.alice,
            '实时消息',
        )
        event = async_to_sync(channel_layer.receive)(channel_name)

        self.assertEqual(event['type'], 'conversation.message')
        self.assertEqual(event['message']['id'], message.id)
        self.assertEqual(event['conversation_id'], self.conversation.id)

    def test_mark_read_publishes_realtime_read_event(self):
        message = ConversationMessageService.send_text(
            self.conversation,
            self.alice,
            '请确认阅读状态',
        )
        channel_layer = get_channel_layer()
        channel_name = async_to_sync(channel_layer.new_channel)()
        async_to_sync(channel_layer.group_add)(
            f'message_conversation_{self.conversation.id}',
            channel_name,
        )

        ConversationMessageService.mark_conversation_read(
            self.conversation,
            self.bob,
        )
        event = async_to_sync(channel_layer.receive)(channel_name)

        self.assertEqual(event['type'], 'conversation.read')
        self.assertEqual(event['user_id'], self.bob.id)
        self.assertEqual(event['last_read_message_id'], message.id)

    def test_recall_endpoint_publishes_updated_message_to_conversation_group(self):
        client = APIClient()
        client.force_login(self.alice)
        message = ConversationMessageService.send_text(
            self.conversation,
            self.alice,
            '需要撤回的消息',
        )
        channel_layer = get_channel_layer()
        channel_name = async_to_sync(channel_layer.new_channel)()
        async_to_sync(channel_layer.group_add)(
            f'message_conversation_{self.conversation.id}',
            channel_name,
        )

        response = client.post(
            f'/message/conversations/{self.conversation.id}/messages/{message.id}/recall/',
            {},
            format='json',
        )
        event = async_to_sync(channel_layer.receive)(channel_name)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(event['type'], 'conversation.message')
        self.assertEqual(event['message']['id'], message.id)
        self.assertEqual(event['message']['message_type'], ConversationMessage.TYPE_SYSTEM)
        self.assertTrue(event['message']['metadata']['recalled'])

    def test_recall_endpoint_rejects_messages_already_read(self):
        client = APIClient()
        client.force_login(self.alice)
        message = ConversationMessageService.send_text(
            self.conversation,
            self.alice,
            '对方已读后不可撤回',
        )
        ConversationMessageService.mark_conversation_read(
            self.conversation,
            self.bob,
        )

        response = client.post(
            f'/message/conversations/{self.conversation.id}/messages/{message.id}/recall/',
            {},
            format='json',
        )
        message.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(message.message_type, ConversationMessage.TYPE_TEXT)
        self.assertFalse(message.metadata.get('recalled'))
