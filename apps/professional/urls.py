from rest_framework.routers import DefaultRouter

from apps.professional.views import (
    DietAssignmentViewSet,
    LinkViewSet,
    StudentListViewSet,
    WorkoutAssignmentViewSet,
)

router = DefaultRouter()
router.register("links", LinkViewSet, basename="professional-links")
router.register("students", StudentListViewSet, basename="professional-students")
router.register("assignments", WorkoutAssignmentViewSet, basename="professional-assignments")
router.register("diet-assignments", DietAssignmentViewSet, basename="professional-diet-assignments")

urlpatterns = router.urls
