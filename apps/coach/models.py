from django.db import models

from apps.users.models import User


class MessageRole(models.TextChoices):
    USER = "user", "Usuário"
    ASSISTANT = "assistant", "Assistente"
    SYSTEM = "system", "Sistema"


class CoachAgent(models.TextChoices):
    MANAGER = "manager", "Gerente"
    DIET = "diet", "Dieta"
    WORKOUT = "workout", "Treino"
    CRITIC = "critic", "Crítico"


class CoachConversation(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="coach_conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversa {self.pk} — {self.user.email}"


class CoachMessage(models.Model):
    conversation = models.ForeignKey(
        CoachConversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=MessageRole.choices)
    content = models.TextField()
    agent = models.CharField(max_length=10, choices=CoachAgent.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.conversation_id} — {self.role} ({self.created_at:%Y-%m-%d %H:%M})"


class AgentRun(models.Model):
    """Auditoria de cada chamada a LLM: sistema multiagente sem log
    estruturado por decisão é indepurável."""

    conversation = models.ForeignKey(
        CoachConversation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agent_runs",
    )
    agent = models.CharField(max_length=10, choices=CoachAgent.choices)
    provider = models.CharField(max_length=20)
    model = models.CharField(max_length=50)
    iterations = models.PositiveSmallIntegerField(default=1)
    validation_errors = models.JSONField(default=list, blank=True)
    approved = models.BooleanField(default=False)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.agent} via {self.provider} ({self.created_at:%Y-%m-%d %H:%M})"
