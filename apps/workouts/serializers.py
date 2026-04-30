from rest_framework import serializers

from apps.workouts.models import (
    Exercise,
    SetLog,
    Workout,
    WorkoutExercise,
    WorkoutSession,
)


class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = ("id", "name", "muscle_group", "icon_slug", "description")


class WorkoutExerciseSerializer(serializers.ModelSerializer):
    exercise_detail = ExerciseSerializer(source="exercise", read_only=True)

    class Meta:
        model = WorkoutExercise
        fields = (
            "id",
            "exercise",
            "exercise_detail",
            "order",
            "sets",
            "reps",
            "duration_seconds",
            "load_kg",
            "rest_seconds",
        )

    def validate(self, data):
        if not data.get("reps") and not data.get("duration_seconds"):
            raise serializers.ValidationError("Informe reps ou duration_seconds.")
        return data


class WorkoutSerializer(serializers.ModelSerializer):
    exercises = WorkoutExerciseSerializer(
        many=True, source="workout_exercises", required=False, default=[]
    )

    is_assigned = serializers.SerializerMethodField()

    class Meta:
        model = Workout
        fields = (
            "id",
            "name",
            "description",
            "is_template",
            "exercises",
            "is_assigned",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_assigned", "created_at", "updated_at")

    def get_is_assigned(self, obj):
        request = self.context.get("request")
        return bool(request and obj.user_id != request.user.id)

    def create(self, validated_data):
        exercises_data = validated_data.pop("workout_exercises", [])
        workout = Workout.objects.create(**validated_data)
        self._save_exercises(workout, exercises_data)
        return workout

    def update(self, instance, validated_data):
        exercises_data = validated_data.pop("workout_exercises", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if exercises_data is not None:
            instance.workout_exercises.all().delete()
            self._save_exercises(instance, exercises_data)
        return instance

    @staticmethod
    def _save_exercises(workout: Workout, exercises_data: list) -> None:
        for i, ex_data in enumerate(exercises_data, start=1):
            ex_data.setdefault("order", i)
            WorkoutExercise.objects.create(workout=workout, **ex_data)


class SetLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SetLog
        fields = (
            "id",
            "workout_exercise",
            "set_number",
            "reps_done",
            "duration_seconds",
            "load_kg",
            "completed_at",
        )
        read_only_fields = ("id", "completed_at")

    def validate(self, data):
        if not data.get("reps_done") and not data.get("duration_seconds"):
            raise serializers.ValidationError("Informe reps_done ou duration_seconds.")
        return data


class WorkoutSessionSerializer(serializers.ModelSerializer):
    set_logs = SetLogSerializer(many=True, read_only=True)

    class Meta:
        model = WorkoutSession
        fields = (
            "id",
            "workout",
            "status",
            "started_at",
            "finished_at",
            "notes",
            "set_logs",
        )
        read_only_fields = ("id", "status", "started_at", "finished_at")
