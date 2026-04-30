from rest_framework.routers import SimpleRouter

from apps.workouts.views import ExerciseViewSet, WorkoutSessionViewSet, WorkoutViewSet

router = SimpleRouter()
router.register("exercises", ExerciseViewSet, basename="exercises")
router.register("workouts", WorkoutViewSet, basename="workouts")
router.register("workout-sessions", WorkoutSessionViewSet, basename="workout-sessions")

urlpatterns = router.urls
