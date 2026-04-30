from rest_framework import serializers

from apps.body.models import BodyMetric


class BodyMetricWriteSerializer(serializers.ModelSerializer):
    """Valida apenas os campos fornecidos pelo usuário."""

    class Meta:
        model = BodyMetric
        fields = (
            "date",
            "weight_kg",
            "body_fat_pct",
            "muscle_mass_kg",
            "visceral_fat",
            "body_water_pct",
            "bmr_device",
        )


class BodyMetricSerializer(serializers.ModelSerializer):
    """Representação completa para leitura, incluindo valores calculados."""

    class Meta:
        model = BodyMetric
        fields = (
            "id",
            "date",
            "weight_kg",
            "body_fat_pct",
            "muscle_mass_kg",
            "visceral_fat",
            "body_water_pct",
            "bmr_device",
            "bmr_calculated",
            "tdee",
            "calorie_goal",
            "protein_g",
            "carbs_g",
            "fat_g",
            "created_at",
        )
        read_only_fields = fields