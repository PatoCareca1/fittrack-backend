from django.contrib import admin

from apps.workouts.models import (
    Exercise,
    SetLog,
    Workout,
    WorkoutExercise,
    WorkoutSession,
)


class WorkoutExerciseInline(admin.TabularInline):
    model = WorkoutExercise
    extra = 0
    ordering = ["order"]
    autocomplete_fields = ["exercise"]


class SetLogInline(admin.TabularInline):
    model = SetLog
    extra = 0
    readonly_fields = ("completed_at",)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "muscle_group", "icon_slug", "is_public")
    list_filter = ("muscle_group", "is_public")
    search_fields = ("name",)
    prepopulated_fields = {"icon_slug": ("name",)}


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "is_template", "updated_at")
    list_filter = ("is_template",)
    search_fields = ("name", "user__email")
    autocomplete_fields = ("user",)
    inlines = [WorkoutExerciseInline]


@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "workout", "status", "started_at", "finished_at")
    list_filter = ("status",)
    search_fields = ("user__email", "workout__name")
    readonly_fields = ("started_at", "finished_at")
    date_hierarchy = "started_at"
    inlines = [SetLogInline]
