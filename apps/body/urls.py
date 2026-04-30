from rest_framework.routers import SimpleRouter

from apps.body.views import BodyMetricViewSet

router = SimpleRouter()
router.register("", BodyMetricViewSet, basename="body-metrics")

urlpatterns = router.urls