from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.workouts import services
from apps.workouts.models import Exercise, Workout, WorkoutSession
from apps.workouts.serializers import (
    ExerciseSerializer,
    SetLogSerializer,
    WorkoutSerializer,
    WorkoutSessionSerializer,
)


class ExerciseViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ExerciseSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = Exercise.objects.filter(is_public=True)
        muscle_group = self.request.query_params.get("muscle_group")
        if muscle_group:
            qs = qs.filter(muscle_group=muscle_group)
        return qs


class WorkoutViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkoutSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        from django.db.models import Q
        from apps.professional.models import WorkoutAssignment

        assigned_ids = WorkoutAssignment.objects.filter(
            link__student=self.request.user,
            link__status="active",
        ).values_list("workout_id", flat=True)

        return (Workout.objects.filter(Q(user=self.request.user) | Q(id__in=assigned_ids)).prefetch_related("workout_exercises__exercise"))

    def create(self, request, *args, **kwargs):
        workout = services.create_workout(request.user, request.data)
        return Response(WorkoutSerializer(workout).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        workout = services.update_workout(self.get_object(), request.user, request.data)
        return Response(WorkoutSerializer(workout).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_workout(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def templates(self, request):
        qs = Workout.objects.filter(is_template=True).prefetch_related(
            "workout_exercises__exercise"
        )
        return Response(WorkoutSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="import")
    def import_template(self, request, pk=None):
        workout = services.import_template(request.user, pk)
        return Response(WorkoutSerializer(workout).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="start-session")
    def start_session(self, request, pk=None):
        session = services.start_session(request.user, self.get_object())
        return Response(
            WorkoutSessionSerializer(session).data, status=status.HTTP_201_CREATED
        )


class WorkoutSessionViewSet(RetrieveModelMixin, ListModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkoutSessionSerializer

    def get_queryset(self):
        return (
            WorkoutSession.objects.filter(user=self.request.user)
            .select_related("workout")
            .prefetch_related("set_logs__workout_exercise__exercise")
        )

    @action(detail=True, methods=["patch"], url_path="log-set")
    def log_set(self, request, pk=None):
        set_log = services.log_set(self.get_object(), request.data)
        return Response(SetLogSerializer(set_log).data)

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        session = services.finish_session(self.get_object())
        return Response(WorkoutSessionSerializer(session).data)
