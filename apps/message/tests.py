from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.common.cache_service import MessageCache
from apps.message.models import (
    Conversation,
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
        self.client.force_authenticate(user=self.alice)

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
        self.client.force_authenticate(user=self.owner)
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
        self.client.force_authenticate(user=self.member)

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
