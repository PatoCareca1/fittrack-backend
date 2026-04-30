from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.workouts.models import (
    SessionStatus,
    SetLog,
    Workout,
    WorkoutExercise,
    WorkoutSession,
)


def create_workout(user, data: dict) -> Workout:
    from apps.workouts.serializers import WorkoutSerializer

    serializer = WorkoutSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.save(user=user)


def update_workout(instance: Workout, user, data: dict) -> Workout:
    if instance.user != user:
        raise PermissionDenied("Você não tem permissão para editar este treino.")
    from apps.workouts.serializers import WorkoutSerializer

    serializer = WorkoutSerializer(instance, data=data, partial=True)
    serializer.is_valid(raise_exception=True)
    return serializer.save()


def delete_workout(instance: Workout, user) -> None:
    if instance.user != user:
        raise PermissionDenied("Você não tem permissão para excluir este treino.")
    instance.delete()


def import_template(user, template_id: int) -> Workout:
    try:
        template = Workout.objects.prefetch_related("workout_exercises__exercise").get(
            id=template_id, is_template=True
        )
    except Workout.DoesNotExist:
        raise ValidationError("Template não encontrado.")

    new_workout = Workout.objects.create(
        user=user,
        name=template.name,
        description=template.description,
        is_template=False,
    )
    WorkoutExercise.objects.bulk_create(
        [
            WorkoutExercise(
                workout=new_workout,
                exercise=ex.exercise,
                order=ex.order,
                sets=ex.sets,
                reps=ex.reps,
                duration_seconds=ex.duration_seconds,
                load_kg=ex.load_kg,
                rest_seconds=ex.rest_seconds,
            )
            for ex in template.workout_exercises.all()
        ]
    )
    return new_workout


def start_session(user, workout: Workout) -> WorkoutSession:
    return WorkoutSession.objects.create(user=user, workout=workout)


def log_set(session: WorkoutSession, data: dict) -> SetLog:
    if session.status != SessionStatus.IN_PROGRESS:
        raise ValidationError("Sessão não está em andamento.")

    from apps.workouts.serializers import SetLogSerializer

    serializer = SetLogSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    validated = serializer.validated_data

    if validated["workout_exercise"].workout_id != session.workout_id:
        raise ValidationError("Exercício não pertence ao treino desta sessão.")

    set_log, _ = SetLog.objects.update_or_create(
        session=session,
        workout_exercise=validated["workout_exercise"],
        set_number=validated["set_number"],
        defaults={
            "reps_done": validated.get("reps_done"),
            "duration_seconds": validated.get("duration_seconds"),
            "load_kg": validated.get("load_kg"),
        },
    )
    return set_log


def finish_session(session: WorkoutSession) -> WorkoutSession:
    if session.status == SessionStatus.COMPLETED:
        raise ValidationError("Sessão já foi concluída.")
    session.status = SessionStatus.COMPLETED
    session.finished_at = timezone.now()
    session.save()
    return session
