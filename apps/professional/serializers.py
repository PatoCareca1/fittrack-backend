from rest_framework import serializers

from apps.professional.models import (
    InviteCode,
    MealPlanAssignment,
    ProfessionalLink,
    WorkoutAssignment,
)


class InviteCodeSerializer(serializers.ModelSerializer):
    is_used = serializers.SerializerMethodField()

    class Meta:
        model = InviteCode
        fields = ("id", "code", "expires_at", "is_used", "created_at")
        read_only_fields = ("id", "code", "expires_at", "created_at")

    def get_is_used(self, obj) -> bool:
        return obj.used_by_id is not None


class ProfessionalLinkSerializer(serializers.ModelSerializer):
    student_email = serializers.EmailField(source="student.email", read_only=True)
    professional_email = serializers.EmailField(source="professional.email", read_only=True)
    professional_type = serializers.CharField(
        source="professional.get_account_type_display", read_only=True
    )

    class Meta:
        model = ProfessionalLink
        fields = (
            "id",
            "student_email",
            "professional_email",
            "professional_type",
            "status",
            "created_at",
        )
        read_only_fields = fields


class AcceptInviteSerializer(serializers.Serializer):
    code = serializers.CharField()


class AssignWorkoutSerializer(serializers.Serializer):
    workout_id = serializers.IntegerField()


class AssignMealPlanSerializer(serializers.Serializer):
    meal_plan_id = serializers.IntegerField()


class WorkoutAssignmentSerializer(serializers.ModelSerializer):
    workout_name = serializers.CharField(source="workout.name", read_only=True)

    class Meta:
        model = WorkoutAssignment
        fields = ("id", "workout", "workout_name", "assigned_at")
        read_only_fields = ("id", "assigned_at")


class MealPlanAssignmentSerializer(serializers.ModelSerializer):
    meal_plan_name = serializers.CharField(source="meal_plan.name", read_only=True)

    class Meta:
        model = MealPlanAssignment
        fields = ("id", "meal_plan", "meal_plan_name", "assigned_at")
        read_only_fields = ("id", "assigned_at")