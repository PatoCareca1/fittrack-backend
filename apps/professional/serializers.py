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


class StudentSummarySerializer(serializers.ModelSerializer):
    """Retornado em GET /professional/students/ — uma entrada por vínculo ativo."""
    student_id = serializers.IntegerField(source="student.id", read_only=True)
    student_email = serializers.EmailField(source="student.email", read_only=True)
    student_name = serializers.SerializerMethodField()
    last_session = serializers.SerializerMethodField()
    last_meal_log = serializers.SerializerMethodField()
    workout_assignment_count = serializers.IntegerField(read_only=True)
    meal_plan_assignment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProfessionalLink
        fields = (
            "id",
            "student_id",
            "student_email",
            "student_name",
            "status",
            "created_at",
            "last_session",
            "last_meal_log",
            "workout_assignment_count",
            "meal_plan_assignment_count",
        )
        read_only_fields = fields

    def get_student_name(self, obj) -> str:
        return obj.student.get_full_name() or obj.student.email

    def get_last_session(self, obj):
        session = (
            obj.student.workout_sessions
            .order_by("-started_at")
            .values("started_at", "status")
            .first()
        )
        return session or None

    def get_last_meal_log(self, obj):
        log = (
            obj.student.meal_logs
            .order_by("-date")
            .values("date", "meal__name")
            .first()
        )
        return log or None