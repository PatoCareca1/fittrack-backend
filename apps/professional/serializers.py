from rest_framework import serializers

from apps.professional.models import ProfessionalLink, WorkoutAssignment
from apps.users.serializers import UserSerializer
from apps.workouts.serializers import WorkoutSerializer


class ProfessionalLinkSerializer(serializers.ModelSerializer):
    professional = UserSerializer(read_only=True)
    student = UserSerializer(read_only=True)

    class Meta:
        model = ProfessionalLink
        fields = (
            "id",
            "professional",
            "student",
            "invite_code",
            "status",
            "created_at",
            "accepted_at",
        )
        read_only_fields = fields


class WorkoutAssignmentSerializer(serializers.ModelSerializer):
    workout = WorkoutSerializer(read_only=True)
    student = UserSerializer(source="link.student", read_only=True)

    class Meta:
        model = WorkoutAssignment
        fields = ("id", "link", "student", "workout", "notes", "is_active", "created_at")
        read_only_fields = fields


class StudentSerializer(serializers.ModelSerializer):
    """Linha da lista GET /professional/students/ — o aluno com o vínculo."""

    student = UserSerializer(read_only=True)

    class Meta:
        model = ProfessionalLink
        fields = ("id", "student", "status", "accepted_at")
        read_only_fields = fields
