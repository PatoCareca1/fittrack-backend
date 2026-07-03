from datetime import date as date_cls

from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.diet.models import Food, FoodSource, Meal, MealLog, MealPlan


def create_meal_plan(user, data: dict) -> MealPlan:
    from apps.diet.serializers import MealPlanSerializer

    serializer = MealPlanSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.save(user=user)


def update_meal_plan(instance: MealPlan, user, data: dict) -> MealPlan:
    if instance.user != user:
        raise PermissionDenied("Você não tem permissão para editar este plano.")
    from apps.diet.serializers import MealPlanSerializer

    serializer = MealPlanSerializer(instance, data=data, partial=True)
    serializer.is_valid(raise_exception=True)
    return serializer.save()


def delete_meal_plan(instance: MealPlan, user) -> None:
    if instance.user != user:
        raise PermissionDenied("Você não tem permissão para excluir este plano.")
    instance.delete()


def create_custom_food(user, data: dict) -> Food:
    from apps.diet.serializers import FoodSerializer

    serializer = FoodSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.save(owner=user, source=FoodSource.CUSTOM)


def mark_meal_done(user, meal_id: int, log_date=None, comment: str = "") -> MealLog:
    """Marca refeição como concluída no dia. Idempotente: repetir a marcação
    no mesmo dia atualiza o comentário em vez de duplicar (RN09)."""
    try:
        meal = Meal.objects.select_related("plan").get(id=meal_id)
    except Meal.DoesNotExist:
        raise ValidationError({"meal": "Refeição não encontrada."})

    # Pode marcar: o dono do plano, ou o aluno com este plano atribuído por
    # profissional (RN09 — aluno marca e comenta, não edita a composição).
    if meal.plan.user != user and not _is_assigned_to(user, meal.plan):
        raise PermissionDenied("Esta refeição não pertence a um plano seu.")

    log, _ = MealLog.objects.update_or_create(
        meal=meal,
        date=log_date or date_cls.today(),
        defaults={"user": user, "comment": comment},
    )
    return log


def _own_plan(user, plan_id: int) -> MealPlan:
    try:
        return MealPlan.objects.get(id=plan_id, user=user)
    except MealPlan.DoesNotExist:
        raise ValidationError({"plan": "Plano não encontrado."})


def _own_meal(user, meal_id: int) -> Meal:
    try:
        return Meal.objects.select_related("plan").get(id=meal_id, plan__user=user)
    except Meal.DoesNotExist:
        raise ValidationError({"meal": "Refeição não encontrada."})


def add_meal(user, plan_id: int, name: str, time=None) -> Meal:
    plan = _own_plan(user, plan_id)
    last = plan.meals.order_by("-order").first()
    return Meal.objects.create(
        plan=plan, name=name, time=time or None, order=(last.order + 1 if last else 1)
    )


def update_meal(user, meal_id: int, data: dict) -> Meal:
    meal = _own_meal(user, meal_id)
    for field in ("name", "time"):
        if field in data:
            setattr(meal, field, data[field] or None)
    meal.save()
    return meal


def delete_meal(user, meal_id: int) -> None:
    _own_meal(user, meal_id).delete()


def add_meal_item(user, meal_id: int, food_id: int, quantity_g) -> Meal:
    meal = _own_meal(user, meal_id)
    try:
        food = Food.objects.filter(is_active=True).filter(
            models.Q(owner__isnull=True) | models.Q(owner=user)
        ).get(id=food_id)
    except Food.DoesNotExist:
        raise ValidationError({"food": "Alimento não encontrado."})
    meal.items.create(food=food, quantity_g=quantity_g)
    return meal


def remove_meal_item(user, item_id: int) -> None:
    deleted, _ = MealItem.objects.filter(
        id=item_id, meal__plan__user=user
    ).delete()
    if not deleted:
        raise ValidationError({"item": "Item não encontrado."})


def _is_assigned_to(user, plan: MealPlan) -> bool:
    # Import local para evitar dependência circular diet <-> professional.
    from apps.professional.models import DietAssignment, LinkStatus

    return DietAssignment.objects.filter(
        meal_plan=plan,
        is_active=True,
        link__student=user,
        link__status=LinkStatus.ACTIVE,
    ).exists()


def unmark_meal(user, meal_id: int, log_date=None) -> None:
    MealLog.objects.filter(
        meal_id=meal_id, user=user, date=log_date or date_cls.today()
    ).delete()
