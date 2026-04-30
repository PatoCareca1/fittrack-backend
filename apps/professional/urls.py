from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.professional.views import (
    AcceptInviteView,
    InviteCodeView,
    ProfessionalLinkViewSet,
)

router = SimpleRouter()
router.register("links", ProfessionalLinkViewSet, basename="professional-links")

urlpatterns = router.urls + [
    path("invite/", InviteCodeView.as_view(), name="professional-invite"),
    path("accept-invite/", AcceptInviteView.as_view(), name="professional-accept-invite"),
]