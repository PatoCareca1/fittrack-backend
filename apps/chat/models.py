from django.db import models

from apps.professional.models import ProfessionalLink
from apps.users.models import User


class ChatMessage(models.Model):
    link = models.ForeignKey(
        ProfessionalLink, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_messages"
    )
    content = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["link", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.sender.email} → link {self.link_id} @ {self.created_at:%Y-%m-%d %H:%M}"