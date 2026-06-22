import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Conversation
from .services import ConversationMessageService


class ConversationConsumer(AsyncWebsocketConsumer):
    """在线沟通 WebSocket consumer"""

    async def connect(self):
        self.user = self.scope.get('user')
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self._is_member():
            await self.close(code=4403)
            return

        self.group_name = ConversationMessageService.group_name(
            self.conversation_id
        )
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json_error('无效的消息格式')
            return

        action = payload.get('action')
        if action == 'send':
            content = payload.get('content', '')
            try:
                await self._send_message(content, payload.get('metadata') or {})
            except ValueError as exc:
                await self.send_json_error(str(exc))
            except PermissionError as exc:
                await self.send_json_error(str(exc), code='permission_denied')
        elif action == 'read':
            await self._mark_read()
        else:
            await self.send_json_error('不支持的操作')

    async def send_json_error(self, message, code='bad_request'):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'code': code,
            'message': message,
        }, ensure_ascii=False))

    async def conversation_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'conversation_id': event['conversation_id'],
            'message': event['message'],
        }, ensure_ascii=False))

    async def conversation_read(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read',
            'conversation_id': event['conversation_id'],
            'user_id': event['user_id'],
            'read_count': event['read_count'],
            'last_read_message_id': event['last_read_message_id'],
            'read_at': event['read_at'],
        }, ensure_ascii=False))

    @database_sync_to_async
    def _is_member(self):
        return Conversation.objects.filter(
            id=self.conversation_id,
            is_active=True,
            member_relations__user=self.user,
            member_relations__left_at__isnull=True,
        ).exists()

    @database_sync_to_async
    def _send_message(self, content, metadata):
        conversation = Conversation.objects.get(id=self.conversation_id)
        return ConversationMessageService.send_text(
            conversation,
            self.user,
            content,
            metadata=metadata,
        )

    @database_sync_to_async
    def _mark_read(self):
        conversation = Conversation.objects.get(id=self.conversation_id)
        return ConversationMessageService.mark_conversation_read(
            conversation,
            self.user,
        )
