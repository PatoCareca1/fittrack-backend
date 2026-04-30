from datetime import date as date_type

from django.db import IntegrityError
from rest_framework.exceptions import ValidationError

from apps.users.models import Goal, Profile, Sex


MACRO_RATIOS = {
    Goal.WEIGHT_LOSS:    {"carbs": 0.40, "protein": 0.40, "fat": 0.20},
    Goal.HYPERTROPHY:    {"carbs": 0.45, "protein": 0.30, "fat": 0.25},
    Goal.MAINTENANCE:    {"carbs": 0.50, "protein": 0.25, "fat": 0.25},
    Goal.GENERAL_HEALTH: {"carbs": 0.50, "protein": 0.25, "fat": 0.25},
}

CALORIE_ADJUSTMENTS = {
    Goal.WEIGHT_LOSS:    -500,
    Goal.HYPERTROPHY:    +500,
    Goal.MAINTENANCE:     0,
    Goal.GENERAL_HEALTH:  0,
}


def _age(birth_date: date_type) -> int:
    today = date_type.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def _mifflin_st_jeor(profile: Profile, weight_kg: float) -> int:
    if not (profile.sex and profile.birth_date and profile.height_cm):
        raise ValidationError(
            "Preencha sexo, data de nascimento e altura no perfil antes de registrar métricas."
        )
    bmr = 10 * weight_kg + 6.25 * float(profile.height_cm) - 5 * _age(profile.birth_date)
    bmr += 5 if profile.sex == Sex.MALE else -161
    return round(bmr)


def _compute(profile: Profile, weight_kg: float, bmr_device: int | None) -> dict:
    bmr_calculated = _mifflin_st_jeor(profile, weight_kg)
    effective_bmr = bmr_device or bmr_calculated  # RN01: TMB da balança prevalece
    tdee = round(effective_bmr * profile.activity_factor)
    calorie_goal = max(1200, tdee + CALORIE_ADJUSTMENTS.get(profile.goal, 0))  # RN03
    ratios = MACRO_RATIOS.get(profile.goal, MACRO_RATIOS[Goal.GENERAL_HEALTH])  # RN02
    return {
        "bmr_calculated": bmr_calculated,
        "tdee": tdee,
        "calorie_goal": calorie_goal,
        "protein_g": round(calorie_goal * ratios["protein"] / 4),
        "carbs_g": round(calorie_goal * ratios["carbs"] / 4),
        "fat_g": round(calorie_goal * ratios["fat"] / 9),
    }


def create_body_metric(user, data: dict):
    from apps.body.models import BodyMetric
    from apps.body.serializers import BodyMetricWriteSerializer

    serializer = BodyMetricWriteSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    validated = serializer.validated_data

    computed = _compute(
        user.profile,
        float(validated["weight_kg"]),
        validated.get("bmr_device"),
    )
    try:
        return BodyMetric.objects.create(user=user, **validated, **computed)
    except IntegrityError:
        raise ValidationError({"date": "Já existe um registro para esta data."})


def update_body_metric(instance, user, data: dict):
    from apps.body.serializers import BodyMetricWriteSerializer

    serializer = BodyMetricWriteSerializer(instance, data=data, partial=True)
    serializer.is_valid(raise_exception=True)
    validated = serializer.validated_data

    weight_kg = float(validated.get("weight_kg", instance.weight_kg))
    bmr_device = validated.get("bmr_device", instance.bmr_device)
    computed = _compute(user.profile, weight_kg, bmr_device)

    for attr, value in {**validated, **computed}.items():
        setattr(instance, attr, value)
    instance.save()
    return instance