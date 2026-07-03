from django.contrib import admin

from apps.diet.models import Food, Meal, MealItem, MealLog, MealPlan


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "brand", "source", "kcal", "protein_g", "is_active")
    list_filter = ("source", "is_active")
    search_fields = ("name", "brand")


class MealItemInline(admin.TabularInline):
    model = MealItem
    extra = 0


class MealInline(admin.TabularInline):
    model = Meal
    extra = 0


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "user", "is_template", "updated_at")
    list_filter = ("is_template",)
    search_fields = ("name", "user__email")
    inlines = [MealInline]


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "plan", "time", "order")
    inlines = [MealItemInline]


@admin.register(MealLog)
class MealLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "meal", "date", "logged_at")
    list_filter = ("date",)
