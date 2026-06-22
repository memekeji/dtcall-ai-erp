from django.urls import re_path

from .consumers import ConversationConsumer


websocket_urlpatterns = [
    re_path(
        r'^ws/message/conversations/(?P<conversation_id>\d+)/$',
        ConversationConsumer.as_asgi(),
    ),
]
