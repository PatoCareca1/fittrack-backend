from django.contrib import admin

from apps.body.models import BodyMetric


@admin.register(BodyMetric)
class BodyMetricAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "date",
        "weight_kg",
        "body_fat_pct",
        "tdee",
        "calorie_goal",
    )
    list_filter = ("date",)
    search_fields = ("user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)
    date_hierarchy = "date"
    ordering = ("-date",)
    readonly_fields = (
        "bmr_calculated",
        "tdee",
        "calorie_goal",
        "protein_g",
        "carbs_g",
        "fat_g",
        "created_at",
    )
    fieldsets = (
        (None, {"fields": ("user", "date")}),
        ("Medidas registradas", {
            "fields": (
                "weight_kg",
                "body_fat_pct",
                "muscle_mass_kg",
                "visceral_fat",
                "body_water_pct",
                "bmr_device",
            )
        }),
        ("Calculados", {
            "fields": (
                "bmr_calculated",
                "tdee",
                "calorie_goal",
                "protein_g",
                "carbs_g",
                "fat_g",
            )
        }),
        ("Auditoria", {"fields": ("created_at",)}),
    )