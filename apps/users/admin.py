from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.users.models import Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fk_name = "user"
    verbose_name_plural = "Perfil"
    fieldsets = (
        ("Dados físicos", {"fields": ("birth_date", "sex", "height_cm")}),
        ("Objetivo & atividade", {"fields": ("goal", "activity_level")}),
        ("Mídia & validação", {"fields": ("avatar", "professional_verified")}),
    )


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = [ProfileInline]
    list_display = (
        "email",
        "first_name",
        "last_name",
        "account_type",
        "is_professional_verified",
        "is_staff",
        "date_joined",
    )
    list_filter = (
        "account_type",
        "is_staff",
        "is_active",
        "profile__professional_verified",
    )
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-date_joined",)
    fieldsets = UserAdmin.fieldsets + (
        ("FitTrack", {"fields": ("account_type",)}),
    )

    @admin.display(boolean=True, description="CRN/CREF verificado")
    def is_professional_verified(self, obj):
        return getattr(getattr(obj, "profile", None), "professional_verified", False)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "account_type",
        "goal",
        "activity_level",
        "professional_verified",
    )
    list_filter = (
        "user__account_type",
        "professional_verified",
        "goal",
        "activity_level",
        "sex",
    )
    search_fields = ("user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)
    actions = ["verify_professionals", "unverify_professionals"]

    @admin.display(description="Tipo de conta", ordering="user__account_type")
    def account_type(self, obj):
        return obj.user.get_account_type_display()

    @admin.action(description="Marcar como verificado (CRN/CREF)")
    def verify_professionals(self, request, queryset):
        updated = queryset.update(professional_verified=True)
        self.message_user(request, f"{updated} profissional(is) verificado(s).")

    @admin.action(description="Remover verificação (CRN/CREF)")
    def unverify_professionals(self, request, queryset):
        updated = queryset.update(professional_verified=False)
        self.message_user(request, f"{updated} verificação(ões) removida(s).")