from datetime import date

from django.db import models

from apps.users.models import User


class FoodSource(models.TextChoices):
    TACO = "taco", "TACO"
    OFF = "off", "Open Food Facts"
    CUSTOM = "custom", "Personalizado"


class Food(models.Model):
    """Catálogo de alimentos. Valores nutricionais sempre por 100g.

    Alimentos TACO/OFF são públicos (owner nulo); usuários podem cadastrar
    alimentos próprios (source=custom, owner preenchido).
    """

    name = models.CharField(max_length=150)
    brand = models.CharField(max_length=100, blank=True)
    source = models.CharField(
        max_length=10, choices=FoodSource.choices, default=FoodSource.CUSTOM
    )
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name="foods"
    )
    kcal = models.DecimalField(max_digits=7, decimal_places=2)
    protein_g = models.DecimalField(max_digits=6, decimal_places=2)
    carbs_g = models.DecimalField(max_digits=6, decimal_places=2)
    fat_g = models.DecimalField(max_digits=6, decimal_places=2)
    nutritional_data = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name


class MealPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="meal_plans")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_template = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.email} — {self.name}"


class Meal(models.Model):
    plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name="meals")
    name = models.CharField(max_length=80)
    time = models.TimeField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "order"], name="unique_meal_order_per_plan"
            )
        ]

    def __str__(self):
        return f"{self.plan.name} — {self.name}"


class MealItem(models.Model):
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name="items")
    food = models.ForeignKey(Food, on_delete=models.PROTECT, related_name="meal_items")
    quantity_g = models.DecimalField(max_digits=7, decimal_places=2)

    def __str__(self):
        return f"{self.meal} — {self.food.name} ({self.quantity_g}g)"


class MealLog(models.Model):
    """Registro de refeição concluída em um dia (RN09: aluno marca e comenta,
    não altera a composição do plano atribuído)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="meal_logs")
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name="logs")
    date = models.DateField(default=date.today)
    comment = models.TextField(blank=True)
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-logged_at"]
        indexes = [models.Index(fields=["user", "date"])]
        constraints = [
            models.UniqueConstraint(
                fields=["meal", "date"], name="unique_meal_log_per_day"
            )
        ]

    def __str__(self):
        return f"{self.user.email} — {self.meal.name} em {self.date}"
