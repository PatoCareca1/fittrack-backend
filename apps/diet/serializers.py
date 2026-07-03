from rest_framework import serializers

from apps.diet.models import Food, Meal, MealItem, MealLog, MealPlan


class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = (
            "id",
            "name",
            "brand",
            "source",
            "kcal",
            "protein_g",
            "carbs_g",
            "fat_g",
            "nutritional_data",
        )
        read_only_fields = ("id", "source")


def _item_macros(item: MealItem) -> dict:
    factor = item.quantity_g / 100
    return {
        "kcal": round(item.food.kcal * factor, 1),
        "protein_g": round(item.food.protein_g * factor, 1),
        "carbs_g": round(item.food.carbs_g * factor, 1),
        "fat_g": round(item.food.fat_g * factor, 1),
    }


class MealItemSerializer(serializers.ModelSerializer):
    food_detail = FoodSerializer(source="food", read_only=True)
    macros = serializers.SerializerMethodField()

    class Meta:
        model = MealItem
        fields = ("id", "food", "food_detail", "quantity_g", "macros")

    def get_macros(self, obj):
        return _item_macros(obj)


class MealSerializer(serializers.ModelSerializer):
    items = MealItemSerializer(many=True, required=False, default=[])
    totals = serializers.SerializerMethodField()

    class Meta:
        model = Meal
        fields = ("id", "name", "time", "order", "items", "totals")

    def get_totals(self, obj):
        totals = {"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
        for item in obj.items.all():
            for key, value in _item_macros(item).items():
                totals[key] = round(totals[key] + value, 1)
        return totals


class MealPlanSerializer(serializers.ModelSerializer):
    meals = MealSerializer(many=True, required=False, default=[])

    class Meta:
        model = MealPlan
        fields = (
            "id",
            "name",
            "description",
            "is_template",
            "meals",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def create(self, validated_data):
        meals_data = validated_data.pop("meals", [])
        plan = MealPlan.objects.create(**validated_data)
        self._save_meals(plan, meals_data)
        return plan

    def update(self, instance, validated_data):
        meals_data = validated_data.pop("meals", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if meals_data is not None:
            instance.meals.all().delete()
            self._save_meals(instance, meals_data)
        return instance

    @staticmethod
    def _save_meals(plan: MealPlan, meals_data: list) -> None:
        for index, meal_data in enumerate(meals_data, start=1):
            items_data = meal_data.pop("items", [])
            meal_data.setdefault("order", index)
            meal = Meal.objects.create(plan=plan, **meal_data)
            for item_data in items_data:
                item_data.pop("macros", None)
                MealItem.objects.create(meal=meal, **item_data)


class MealLogSerializer(serializers.ModelSerializer):
    meal_name = serializers.CharField(source="meal.name", read_only=True)

    class Meta:
        model = MealLog
        fields = ("id", "meal", "meal_name", "date", "comment", "logged_at")
        read_only_fields = ("id", "meal", "logged_at")
