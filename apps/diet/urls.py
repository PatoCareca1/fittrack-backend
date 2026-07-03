from rest_framework.routers import SimpleRouter

from apps.diet.views import (
    FoodViewSet,
    MealItemViewSet,
    MealLogViewSet,
    MealPlanViewSet,
    MealViewSet,
)

router = SimpleRouter()
router.register("foods", FoodViewSet, basename="diet-foods")
router.register("meal-plans", MealPlanViewSet, basename="diet-meal-plans")
router.register("meals", MealViewSet, basename="diet-meals")
router.register("meal-items", MealItemViewSet, basename="diet-meal-items")
router.register("meal-logs", MealLogViewSet, basename="diet-meal-logs")

urlpatterns = router.urls
