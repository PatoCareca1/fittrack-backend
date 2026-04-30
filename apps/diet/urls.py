from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.diet.views import DailySummaryView, FoodViewSet, MealLogViewSet, MealPlanViewSet

router = SimpleRouter()
router.register("foods", FoodViewSet, basename="foods")
router.register("plans", MealPlanViewSet, basename="meal-plans")
router.register("meal-logs", MealLogViewSet, basename="meal-logs")

urlpatterns = router.urls + [
    path("daily-summary/", DailySummaryView.as_view(), name="daily-summary"),
]