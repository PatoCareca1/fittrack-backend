from rest_framework import serializers

from apps.coach.models import CoachJob, CoachMessage
from apps.diet.models import MealPlan
from apps.diet.serializers import MealPlanSerializer
from apps.workouts.models import Workout
from apps.workouts.serializers import WorkoutSerializer


class CoachMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoachMessage
        fields = ("id", "role", "content", "agent", "created_at")
        read_only_fields = fields


class CoachJobSerializer(serializers.ModelSerializer):
    meal_plan = serializers.SerializerMethodField()
    workout = serializers.SerializerMethodField()
    critic_summary = serializers.SerializerMethodField()
    issues = serializers.SerializerMethodField()
    totals = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = CoachJob
        fields = (
            "id",
            "intent",
            "status",
            "error",
            "meal_plan",
            "workout",
            "critic_summary",
            "issues",
            "totals",
            "summary",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_meal_plan(self, obj):
        meal_plan_id = obj.result.get("meal_plan_id")
        if not meal_plan_id:
            return None
        meal_plan = (
            MealPlan.objects.filter(id=meal_plan_id, user=obj.user)
            .prefetch_related("meals__items__food")
            .first()
        )
        if meal_plan is None:
            return None
        return MealPlanSerializer(meal_plan).data

    def get_workout(self, obj):
        workout_id = obj.result.get("workout_id")
        if not workout_id:
            return None
        workout = (
            Workout.objects.filter(id=workout_id, user=obj.user)
            .prefetch_related("workout_exercises__exercise")
            .first()
        )
        if workout is None:
            return None
        return WorkoutSerializer(workout).data

    def get_critic_summary(self, obj):
        return obj.result.get("critic_summary", "")

    def get_issues(self, obj):
        return obj.result.get("issues", [])

    def get_totals(self, obj):
        return obj.result.get("totals")

    def get_summary(self, obj):
        return obj.result.get("summary")
