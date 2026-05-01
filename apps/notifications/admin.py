from django.contrib import admin
from .models import FCMDevice, Notification


@admin.register(FCMDevice)
class FCMDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "device_id", "is_active", "created_at")
    list_filter = ("platform", "is_active")
    search_fields = ("user__email", "device_id")
    actions = ["deactivate_devices"]

    @admin.action(description="Desativar dispositivos selecionados")
    def deactivate_devices(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "notification_type", "title", "read_at", "created_at")
    list_filter = ("notification_type",)
    search_fields = ("user__email", "title")
    readonly_fields = ("created_at",)