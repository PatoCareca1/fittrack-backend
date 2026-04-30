from rest_framework import serializers

from apps.diet.models import Food, Meal, MealItem, MealLog, MealPlan


class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = (
            "id",
            "name",
            "brand",
            "calories_per_100g",
            "protein_per_100g",
            "carbs_per_100g",
            "fat_per_100g",
            "fiber_per_100g",
            "source",
        )


class MealItemSerializer(serializers.ModelSerializer):
    food_detail = FoodSerializer(source="food", read_only=True)
    calories = serializers.FloatField(read_only=True)
    protein_g = serializers.FloatField(read_only=True)
    carbs_g = serializers.FloatField(read_only=True)
    fat_g = serializers.FloatField(read_only=True)

    class Meta:
        model = MealItem
        fields = (
            "id",
            "food",
            "food_detail",
            "quantity_g",
            "calories",
            "protein_g",
            "carbs_g",
            "fat_g",
        )


class MealSerializer(serializers.ModelSerializer):
    items = MealItemSerializer(many=True, required=False, default=[])

    class Meta:
        model = Meal
        fields = ("id", "name", "order", "target_time", "items")

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        meal = Meal.objects.create(**validated_data)
        self._save_items(meal, items_data)
        return meal

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            self._save_items(instance, items_data)
        return instance

    @staticmethod
    def _save_items(meal: Meal, items_data: list) -> None:
        MealItem.objects.bulk_create([
            MealItem(meal=meal, **item_data) for item_data in items_data
        ])


class MealPlanSerializer(serializers.ModelSerializer):
    meals = MealSerializer(many=True, required=False, default=[])
    is_assigned = serializers.SerializerMethodField()

    class Meta:
        model = MealPlan
        fields = ("id", "name", "description", "is_active", "is_assigned", "meals", "created_at", "updated_at")
        read_only_fields = ("id", "is_assigned", "created_at", "updated_at")

    def get_is_assigned(self, obj) -> bool:
        request = self.context.get("request")
        return bool(request and obj.user_id != request.user.id)

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
        for i, meal_data in enumerate(meals_data, start=1):
            items_data = meal_data.pop("items", [])
            meal_data.setdefault("order", i)
            meal = Meal.objects.create(plan=plan, **meal_data)
            MealItem.objects.bulk_create([
                MealItem(meal=meal, **item_data) for item_data in items_data
            ])


class MealLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealLog
        fields = ("id", "meal", "date", "logged_at")
        read_only_fields = ("id", "logged_at")