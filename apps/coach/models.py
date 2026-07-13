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


class Intent(models.TextChoices):
    """Intenção roteada pelo Agente Gerente (apps.coach.agents.manager)."""

    DIET_PLAN = "diet_plan", "Plano alimentar"
    WORKOUT_PLAN = "workout_plan", "Plano de treino"
    OUT_OF_SCOPE = "out_of_scope", "Fora de escopo"
    AMBIGUOUS = "ambiguous", "Ambíguo"


class CoachJobStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    RUNNING = "running", "Em execução"
    SUCCEEDED = "succeeded", "Concluído"
    FAILED = "failed", "Falhou"


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


class CoachJob(models.Model):
    """Execução assíncrona de um pedido roteado ao Agente Gerente (por ora,
    só geração de plano alimentar). Ver apps/coach/runner.py."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="coach_jobs")
    conversation = models.ForeignKey(
        CoachConversation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="jobs",
    )
    intent = models.CharField(max_length=20, choices=Intent.choices)
    status = models.CharField(
        max_length=10, choices=CoachJobStatus.choices, default=CoachJobStatus.PENDING
    )
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Job {self.pk} — {self.user.email} ({self.status})"
