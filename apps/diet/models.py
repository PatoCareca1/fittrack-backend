from datetime import date

from django.db import models

from apps.users.models import User


class FoodSource(models.TextChoices):
    TACO = "taco", "TACO"
    OPEN_FOOD_FACTS = "off", "Open Food Facts"
    CUSTOM = "custom", "Personalizado"


class Food(models.Model):
    name = models.CharField(max_length=150)
    brand = models.CharField(max_length=100, blank=True)
    calories_per_100g = models.DecimalField(max_digits=7, decimal_places=2)
    protein_per_100g = models.DecimalField(max_digits=6, decimal_places=2)
    carbs_per_100g = models.DecimalField(max_digits=6, decimal_places=2)
    fat_per_100g = models.DecimalField(max_digits=6, decimal_places=2)
    fiber_per_100g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    source = models.CharField(max_length=10, choices=FoodSource.choices, default=FoodSource.CUSTOM)
    external_id = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}" + (f" ({self.brand})" if self.brand else "")


class MealPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="meal_plans")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.email} — {self.name}"


class Meal(models.Model):
    plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name="meals")
    name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=1)
    target_time = models.TimeField(null=True, blank=True)

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
    quantity_g = models.DecimalField(max_digits=6, decimal_places=1)

    class Meta:
        ordering = ["food__name"]

    def __str__(self):
        return f"{self.food.name} ({self.quantity_g}g)"

    @property
    def calories(self) -> float:
        return round(float(self.food.calories_per_100g) * float(self.quantity_g) / 100, 1)

    @property
    def protein_g(self) -> float:
        return round(float(self.food.protein_per_100g) * float(self.quantity_g) / 100, 1)

    @property
    def carbs_g(self) -> float:
        return round(float(self.food.carbs_per_100g) * float(self.quantity_g) / 100, 1)

    @property
    def fat_g(self) -> float:
        return round(float(self.food.fat_per_100g) * float(self.quantity_g) / 100, 1)


class MealLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="meal_logs")
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name="logs")
    date = models.DateField(default=date.today)
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "meal__order"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "meal", "date"], name="unique_meal_log_per_day"
            )
        ]

    def __str__(self):
        return f"{self.user.email} — {self.meal.name} ({self.date})"