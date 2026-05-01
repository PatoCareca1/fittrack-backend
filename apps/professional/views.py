from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from apps.professional import services
from apps.professional.models import (
    LinkStatus,
    MealPlanAssignment,
    ProfessionalLink,
    WorkoutAssignment,
)
from apps.professional.serializers import (
    AcceptInviteSerializer,
    AssignMealPlanSerializer,
    AssignWorkoutSerializer,
    InviteCodeSerializer,
    MealPlanAssignmentSerializer,
    ProfessionalLinkSerializer,
    StudentSummarySerializer,
    WorkoutAssignmentSerializer,
)


class InviteCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        codes = request.user.invite_codes.order_by("-created_at")
        return Response(InviteCodeSerializer(codes, many=True).data)

    def post(self, request):
        code = services.generate_invite(request.user)
        return Response(InviteCodeSerializer(code).data, status=status.HTTP_201_CREATED)


class AcceptInviteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AcceptInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = services.accept_invite(request.user, serializer.validated_data["code"])
        return Response(ProfessionalLinkSerializer(link).data, status=status.HTTP_201_CREATED)


class ProfessionalLinkViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfessionalLinkSerializer

    def get_queryset(self):
        from django.db.models import Q
        return (
            ProfessionalLink.objects.filter(
                Q(student=self.request.user) | Q(professional=self.request.user)
            )
            .select_related("student", "professional")
        )

    def destroy(self, request, pk=None):
        services.cancel_link(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="assign-workout")
    def assign_workout(self, request, pk=None):
        serializer = AssignWorkoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = services.assign_workout(
            request.user, pk, serializer.validated_data["workout_id"]
        )
        return Response(
            WorkoutAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"], url_path="assign-meal-plan")
    def assign_meal_plan(self, request, pk=None):
        serializer = AssignMealPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = services.assign_meal_plan(
            request.user, pk, serializer.validated_data["meal_plan_id"]
        )
        return Response(
            MealPlanAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"])
    def assignments(self, request, pk=None):
        link = self.get_object()
        workouts = WorkoutAssignment.objects.filter(link=link).select_related("workout")
        plans = MealPlanAssignment.objects.filter(link=link).select_related("meal_plan")
        return Response({
            "workouts": WorkoutAssignmentSerializer(workouts, many=True).data,
            "meal_plans": MealPlanAssignmentSerializer(plans, many=True).data,
        })


class StudentListView(ListAPIView):
    """GET /professional/students/ — lista alunos vinculados ao profissional autenticado."""
    permission_classes = [IsAuthenticated]
    serializer_class = StudentSummarySerializer

    def get_queryset(self):
        from django.db.models import Count

        return (
            ProfessionalLink.objects
            .filter(professional=self.request.user, status=LinkStatus.ACTIVE)
            .select_related("student")
            .annotate(
                workout_assignment_count=Count("workout_assignments", distinct=True),
                meal_plan_assignment_count=Count("meal_plan_assignments", distinct=True),
            )
            .order_by("student__first_name", "student__email")
        )