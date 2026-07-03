from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.professional import services
from apps.professional.models import (
    DietAssignment,
    LinkStatus,
    ProfessionalLink,
    WorkoutAssignment,
)
from apps.professional.permissions import IsProfessional
from apps.professional.serializers import (
    DietAssignmentSerializer,
    ProfessionalLinkSerializer,
    StudentSerializer,
    WorkoutAssignmentSerializer,
)


class LinkViewSet(ModelViewSet):
    """Vínculos do usuário autenticado (como profissional ou como aluno)."""

    permission_classes = [IsAuthenticated]
    serializer_class = ProfessionalLinkSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        return (
            ProfessionalLink.objects.filter(professional=user)
            | ProfessionalLink.objects.filter(student=user)
        ).select_related("professional", "student")

    @action(detail=False, methods=["post"], permission_classes=[IsProfessional])
    def invite(self, request):
        link = services.create_invite(request.user)
        return Response(
            ProfessionalLinkSerializer(link).data, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["post"])
    def accept(self, request):
        link = services.accept_invite(request.user, request.data.get("invite_code", ""))
        return Response(ProfessionalLinkSerializer(link).data)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        link = services.revoke_link(self.get_object(), request.user)
        return Response(ProfessionalLinkSerializer(link).data)


class StudentListViewSet(GenericViewSet):
    """GET /professional/students/ — alunos vinculados (só profissionais)."""

    permission_classes = [IsProfessional]
    serializer_class = StudentSerializer

    def list(self, request):
        qs = ProfessionalLink.objects.filter(
            professional=request.user, status=LinkStatus.ACTIVE
        ).select_related("student")
        return Response(StudentSerializer(qs, many=True).data)


class WorkoutAssignmentViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkoutAssignmentSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        return (
            WorkoutAssignment.objects.filter(link__professional=user)
            | WorkoutAssignment.objects.filter(
                link__student=user, is_active=True, link__status=LinkStatus.ACTIVE
            )
        ).select_related("link__student", "workout")

    def create(self, request, *args, **kwargs):
        self.permission_classes = [IsProfessional]
        self.check_permissions(request)
        assignment = services.assign_workout(
            request.user,
            link_id=request.data.get("link"),
            workout_id=request.data.get("workout"),
            notes=request.data.get("notes", ""),
        )
        return Response(
            WorkoutAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED
        )


class DietAssignmentViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = DietAssignmentSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        return (
            DietAssignment.objects.filter(link__professional=user)
            | DietAssignment.objects.filter(
                link__student=user, is_active=True, link__status=LinkStatus.ACTIVE
            )
        ).select_related("link__student", "meal_plan")

    def create(self, request, *args, **kwargs):
        self.permission_classes = [IsProfessional]
        self.check_permissions(request)
        assignment = services.assign_meal_plan(
            request.user,
            link_id=request.data.get("link"),
            meal_plan_id=request.data.get("meal_plan"),
            notes=request.data.get("notes", ""),
        )
        return Response(
            DietAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED
        )
