from django.contrib import admin

from apps.chat.models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "link", "short_content", "read_at", "created_at")
    list_filter = ("created_at",)
    search_fields = ("sender__email", "content")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

    @admin.display(description="Mensagem")
    def short_content(self, obj):
        return obj.content[:60] + ("…" if len(obj.content) > 60 else "")