from datetime import date

from django.db import models

from apps.users.models import User


class BodyMetric(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="body_metrics")
    date = models.DateField(default=date.today)

    # Obrigatórios (RN14)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2)
    body_fat_pct = models.DecimalField(max_digits=5, decimal_places=2)

    # Opcionais (RN14)
    muscle_mass_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    visceral_fat = models.PositiveSmallIntegerField(null=True, blank=True)
    body_water_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    bmr_device = models.PositiveIntegerField(null=True, blank=True)

    # Calculados e armazenados (preservam histórico mesmo se perfil mudar)
    bmr_calculated = models.PositiveIntegerField()
    tdee = models.PositiveIntegerField()
    calorie_goal = models.PositiveIntegerField()
    protein_g = models.PositiveIntegerField()
    carbs_g = models.PositiveIntegerField()
    fat_g = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="unique_body_metric_per_day")
        ]

    def __str__(self):
        return f"{self.user.email} — {self.date}"