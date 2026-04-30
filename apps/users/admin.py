from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.users.models import Profile, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "last_name", "account_type", "is_staff")
    list_filter = ("account_type", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "goal", "activity_level", "professional_verified")
    list_filter = ("goal", "activity_level", "professional_verified", "sex")
    search_fields = ("user__email",)