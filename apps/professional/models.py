from django.db import models

from apps.users.models import User


class InviteCode(models.Model):
    professional = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="invite_codes"
    )
    code = models.CharField(max_length=20, unique=True)
    expires_at = models.DateTimeField()
    used_by = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="used_invite",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self) -> bool:
        from django.utils import timezone
        return self.used_by is None and self.expires_at > timezone.now()

    def __str__(self):
        return f"{self.professional.email} — {self.code}"


class LinkStatus(models.TextChoices):
    ACTIVE = "active", "Ativo"
    CANCELLED = "cancelled", "Cancelado"


class ProfessionalLink(models.Model):
    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="professional_links"
    )
    professional = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="student_links"
    )
    status = models.CharField(
        max_length=20, choices=LinkStatus.choices, default=LinkStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "professional"],
                name="unique_student_professional_link",
            )
        ]

    def __str__(self):
        return f"{self.student.email} ↔ {self.professional.email} ({self.status})"


class WorkoutAssignment(models.Model):
    link = models.ForeignKey(
        ProfessionalLink, on_delete=models.CASCADE, related_name="workout_assignments"
    )
    workout = models.ForeignKey(
        "workouts.Workout", on_delete=models.CASCADE, related_name="assignments"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["link", "workout"], name="unique_workout_assignment"
            )
        ]

    def __str__(self):
        return f"{self.link} → {self.workout.name}"


class MealPlanAssignment(models.Model):
    link = models.ForeignKey(
        ProfessionalLink, on_delete=models.CASCADE, related_name="meal_plan_assignments"
    )
    meal_plan = models.ForeignKey(
        "diet.MealPlan", on_delete=models.CASCADE, related_name="assignments"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["link", "meal_plan"], name="unique_meal_plan_assignment"
            )
        ]

    def __str__(self):
        return f"{self.link} → {self.meal_plan.name}"