from django.db import models
from apps.users.models import User


class NotificationType(models.TextChoices):
    NEW_MESSAGE = "new_message", "Nova mensagem"
    WORKOUT_ASSIGNED = "workout_assigned", "Treino atribuído"
    MEAL_PLAN_ASSIGNED = "meal_plan_assigned", "Plano alimentar atribuído"
    LINK_ACCEPTED = "link_accepted", "Vínculo aceito"
    SESSION_EXPIRED = "session_expired", "Sessão expirada"


class FCMDevice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fcm_devices")
    token = models.TextField()
    device_id = models.CharField(max_length=255)
    platform = models.CharField(
        max_length=10,
        choices=[("android", "Android"), ("ios", "iOS"), ("web", "Web")],
        default="android",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "device_id")]
        verbose_name = "Dispositivo FCM"
        verbose_name_plural = "Dispositivos FCM"

    def __str__(self):
        return f"{self.user.email} — {self.platform} ({self.device_id[:12]}…)"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"

    def __str__(self):
        return f"{self.user.email} — {self.notification_type}"