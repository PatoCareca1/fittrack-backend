from datetime import date as date_type

from django.db import IntegrityError
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.diet.models import MealLog, MealPlan


def create_plan(user, data: dict) -> MealPlan:
    from apps.diet.serializers import MealPlanSerializer

    serializer = MealPlanSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.save(user=user)


def update_plan(instance: MealPlan, user, data: dict) -> MealPlan:
    if instance.user != user:
        raise PermissionDenied("Você não tem permissão para editar este plano.")
    from apps.diet.serializers import MealPlanSerializer

    serializer = MealPlanSerializer(instance, data=data, partial=True)
    serializer.is_valid(raise_exception=True)
    return serializer.save()


def delete_plan(instance: MealPlan, user) -> None:
    if instance.user != user:
        raise PermissionDenied("Você não tem permissão para excluir este plano.")
    instance.delete()


def log_meal(user, data: dict) -> MealLog:
    from apps.diet.serializers import MealLogSerializer

    serializer = MealLogSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    validated = serializer.validated_data

    if validated["meal"].plan.user != user:
        raise PermissionDenied("Você não tem acesso a esta refeição.")

    try:
        return serializer.save(user=user)
    except IntegrityError:
        raise ValidationError({"detail": "Refeição já registrada para esta data."})


def delete_meal_log(instance: MealLog, user) -> None:
    if instance.user != user:
        raise PermissionDenied()
    instance.delete()


def get_daily_summary(user, target_date: date_type) -> dict:
    from apps.body.models import BodyMetric

    logs = (
        MealLog.objects
        .filter(user=user, date=target_date)
        .prefetch_related("meal__items__food")
    )

    consumed = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for log in logs:
        for item in log.meal.items.all():
            consumed["calories"] += item.calories
            consumed["protein_g"] += item.protein_g
            consumed["carbs_g"] += item.carbs_g
            consumed["fat_g"] += item.fat_g
    consumed = {k: round(v, 1) for k, v in consumed.items()}

    goal = None
    try:
        metric = BodyMetric.objects.filter(user=user).latest("date")
        goal = {
            "calories": metric.calorie_goal,
            "protein_g": metric.protein_g,
            "carbs_g": metric.carbs_g,
            "fat_g": metric.fat_g,
        }
    except BodyMetric.DoesNotExist:
        pass

    remaining = (
        {k: round(max(0.0, float(goal[k]) - consumed[k]), 1) for k in goal}
        if goal else None
    )

    return {
        "date": str(target_date),
        "goal": goal,
        "consumed": consumed,
        "remaining": remaining,
    }