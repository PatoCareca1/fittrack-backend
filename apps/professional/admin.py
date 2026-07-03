from django.contrib import admin

from apps.professional.models import ProfessionalLink, WorkoutAssignment


@admin.register(ProfessionalLink)
class ProfessionalLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "professional", "student", "invite_code", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("invite_code", "professional__email", "student__email")


@admin.register(WorkoutAssignment)
class WorkoutAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "link", "workout", "is_active", "created_at")
    list_filter = ("is_active",)
