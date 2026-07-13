from django.contrib import admin

from apps.coach.models import AgentRun, CoachConversation, CoachJob, CoachMessage


class CoachMessageInline(admin.TabularInline):
    model = CoachMessage
    extra = 0
    readonly_fields = ("role", "content", "agent", "created_at")


@admin.register(CoachConversation)
class CoachConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "updated_at")
    search_fields = ("user__email",)
    autocomplete_fields = ("user",)
    inlines = [CoachMessageInline]


@admin.register(CoachMessage)
class CoachMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "agent", "created_at")
    list_filter = ("role", "agent")
    search_fields = ("conversation__user__email", "content")


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "agent",
        "provider",
        "model",
        "iterations",
        "approved",
        "input_tokens",
        "output_tokens",
        "latency_ms",
        "created_at",
    )
    list_filter = ("agent", "provider", "approved")
    search_fields = ("conversation__user__email",)


@admin.register(CoachJob)
class CoachJobAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "intent", "status", "created_at", "updated_at")
    list_filter = ("intent", "status")
    search_fields = ("user__email",)
    autocomplete_fields = ("user",)
    readonly_fields = ("result", "error", "created_at", "updated_at")
