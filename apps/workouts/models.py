from django.db import models

from apps.users.models import User


class MuscleGroup(models.TextChoices):
    CHEST = "chest", "Peito"
    BACK = "back", "Costas"
    SHOULDERS = "shoulders", "Ombros"
    BICEPS = "biceps", "Bíceps"
    TRICEPS = "triceps", "Tríceps"
    FOREARMS = "forearms", "Antebraços"
    CORE = "core", "Core / Abdômen"
    GLUTES = "glutes", "Glúteos"
    QUADS = "quads", "Quadríceps"
    HAMSTRINGS = "hamstrings", "Posteriores de coxa"
    CALVES = "calves", "Panturrilhas"
    CARDIO = "cardio", "Cardio"
    FULL_BODY = "full_body", "Corpo todo"


class Exercise(models.Model):
    name = models.CharField(max_length=100)
    muscle_group = models.CharField(max_length=20, choices=MuscleGroup.choices)
    icon_slug = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ["muscle_group", "name"]

    def __str__(self):
        return self.name


class Workout(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workouts")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_template = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.email} — {self.name}"


class WorkoutExercise(models.Model):
    workout = models.ForeignKey(
        Workout, on_delete=models.CASCADE, related_name="workout_exercises"
    )
    exercise = models.ForeignKey(
        Exercise, on_delete=models.PROTECT, related_name="workout_exercises"
    )
    order = models.PositiveSmallIntegerField(default=1)
    sets = models.PositiveSmallIntegerField()
    reps = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Para exercícios por tempo (prancha, etc.)"
    )
    load_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rest_seconds = models.PositiveSmallIntegerField(default=60)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["workout", "order"], name="unique_exercise_order_per_workout"
            )
        ]

    def __str__(self):
        return f"{self.workout.name} — {self.exercise.name} (#{self.order})"


class SessionStatus(models.TextChoices):
    IN_PROGRESS = "in_progress", "Em andamento"
    COMPLETED = "completed", "Concluído"
    DRAFT = "draft", "Rascunho"  # RN08: sessão não concluída após 24h


class WorkoutSession(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="workout_sessions"
    )
    workout = models.ForeignKey(
        Workout, on_delete=models.PROTECT, related_name="sessions"
    )
    status = models.CharField(
        max_length=20, choices=SessionStatus.choices, default=SessionStatus.IN_PROGRESS
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user.email} — {self.workout.name} ({self.status})"


class SetLog(models.Model):
    session = models.ForeignKey(
        WorkoutSession, on_delete=models.CASCADE, related_name="set_logs"
    )
    workout_exercise = models.ForeignKey(
        WorkoutExercise, on_delete=models.PROTECT, related_name="set_logs"
    )
    set_number = models.PositiveSmallIntegerField()
    reps_done = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveSmallIntegerField(null=True, blank=True)
    load_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["workout_exercise__order", "set_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "workout_exercise", "set_number"],
                name="unique_set_per_session_exercise",
            )
        ]

    def __str__(self):
        return f"Sessão {self.session_id} — {self.workout_exercise.exercise.name} série {self.set_number}"
