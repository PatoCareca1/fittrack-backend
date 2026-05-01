from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db.models import Q

from apps.chat.models import ChatMessage
from apps.professional.models import LinkStatus, ProfessionalLink


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close(code=4401)
            return

        self.link_id = int(self.scope["url_route"]["kwargs"]["link_id"])
        self.group_name = f"chat_{self.link_id}"

        if not await self._has_access(user, self.link_id):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        text = (content.get("content") or "").strip()
        if not text:
            return
        message = await self._save(self.scope["user"], self.link_id, text)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "id": message.id,
                "sender_id": message.sender_id,
                "sender_email": self.scope["user"].email,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            },
        )

    async def chat_message(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})

    @database_sync_to_async
    def _has_access(self, user, link_id):
        return ProfessionalLink.objects.filter(
            Q(student=user) | Q(professional=user),
            id=link_id,
            status=LinkStatus.ACTIVE,
        ).exists()

    @database_sync_to_async
    def _save(self, user, link_id, content):
        link = ProfessionalLink.objects.get(id=link_id)
        return ChatMessage.objects.create(link=link, sender=user, content=content)