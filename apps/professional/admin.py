from django.contrib import admin

from apps.professional.models import (
    InviteCode,
    MealPlanAssignment,
    ProfessionalLink,
    WorkoutAssignment,
)


class WorkoutAssignmentInline(admin.TabularInline):
    model = WorkoutAssignment
    extra = 0
    readonly_fields = ("assigned_at",)


class MealPlanAssignmentInline(admin.TabularInline):
    model = MealPlanAssignment
    extra = 0
    readonly_fields = ("assigned_at",)


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ("professional", "code", "expires_at", "used_by", "created_at")
    list_filter = ("professional__account_type",)
    search_fields = ("professional__email", "code", "used_by__email")
    readonly_fields = ("code", "created_at")


@admin.register(ProfessionalLink)
class ProfessionalLinkAdmin(admin.ModelAdmin):
    list_display = ("student", "professional", "professional_type", "status", "created_at")
    list_filter = ("status", "professional__account_type")
    search_fields = ("student__email", "professional__email")
    readonly_fields = ("created_at",)
    inlines = [WorkoutAssignmentInline, MealPlanAssignmentInline]
    actions = ["cancel_links"]

    @admin.display(description="Tipo do profissional")
    def professional_type(self, obj):
        return obj.professional.get_account_type_display()

    @admin.action(description="Cancelar vínculos selecionados")
    def cancel_links(self, request, queryset):
        updated = queryset.update(status="cancelled")
        self.message_user(request, f"{updated} vínculo(s) cancelado(s).")