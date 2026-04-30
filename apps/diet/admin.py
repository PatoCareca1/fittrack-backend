from django.contrib import admin

from apps.diet.models import Food, Meal, MealItem, MealLog, MealPlan


class MealItemInline(admin.TabularInline):
    model = MealItem
    extra = 0
    autocomplete_fields = ["food"]


class MealInline(admin.StackedInline):
    model = Meal
    extra = 0
    show_change_link = True


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "source", "calories_per_100g", "protein_per_100g", "is_verified")
    list_filter = ("source", "is_verified")
    search_fields = ("name", "brand", "external_id")
    actions = ["verify_foods"]

    @admin.action(description="Marcar selecionados como verificados")
    def verify_foods(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} alimento(s) verificado(s).")


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "user__email")
    autocomplete_fields = ("user",)
    inlines = [MealInline]


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = ("name", "plan", "order", "target_time")
    search_fields = ("name", "plan__name", "plan__user__email")
    autocomplete_fields = ("plan",)
    inlines = [MealItemInline]


@admin.register(MealLog)
class MealLogAdmin(admin.ModelAdmin):
    list_display = ("user", "meal", "date", "logged_at")
    list_filter = ("date",)
    search_fields = ("user__email", "meal__name")
    date_hierarchy = "date"
    autocomplete_fields = ("user",)