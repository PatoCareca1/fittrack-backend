from django.contrib import admin

from apps.body.models import BodyMetric


@admin.register(BodyMetric)
class BodyMetricAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "weight_kg", "body_fat_pct", "tdee", "calorie_goal")
    list_filter = ("date",)
    search_fields = ("user__email",)
    readonly_fields = ("bmr_calculated", "tdee", "calorie_goal", "protein_g", "carbs_g", "fat_g")