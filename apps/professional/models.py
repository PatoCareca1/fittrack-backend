from django.conf import settings
from django.db import models


class LinkStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    ACTIVE = "active", "Ativo"
    REVOKED = "revoked", "Desvinculado"


class ProfessionalLink(models.Model):
    """Vínculo aluno-profissional (RN05: no máximo 1 personal e 1 nutricionista
    ativos por aluno; RN06: profissional sem limite de alunos)."""

    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="professional_links",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_links",
        null=True,
        blank=True,
    )
    invite_code = models.CharField(max_length=6, unique=True)
    status = models.CharField(
        max_length=10, choices=LinkStatus.choices, default=LinkStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["professional", "status"]),
        ]

    def __str__(self):
        return f"{self.professional} -> {self.student or self.invite_code} ({self.status})"


class WorkoutAssignment(models.Model):
    """Atribuição de treino do profissional ao aluno. A estrutura do treino é
    somente leitura para o aluno (RN04/RN10)."""

    link = models.ForeignKey(
        ProfessionalLink, on_delete=models.CASCADE, related_name="workout_assignments"
    )
    workout = models.ForeignKey(
        "workouts.Workout", on_delete=models.CASCADE, related_name="assignments"
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["link", "is_active"])]

    def __str__(self):
        return f"{self.workout} -> {self.link.student}"


# DietAssignment entra quando o app `diet` tiver models (MealPlan ainda não existe).
