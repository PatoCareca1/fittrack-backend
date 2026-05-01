from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

admin.site.site_header = "FitTrack — Administração"
admin.site.site_title = "FitTrack Admin"
admin.site.index_title = "Painel administrativo"

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth
    path("api/v1/auth/", include("apps.users.urls")),

    # Perfil do usuário autenticado
    path("api/v1/me/", include("apps.users.me_urls")),
    path("api/v1/me/body-metrics/", include("apps.body.urls")),
    path("api/v1/me/devices/", include("apps.notifications.device_urls")),
    path("api/v1/me/notifications/", include("apps.notifications.notification_urls")),

    # Domínios
    path("api/v1/", include("apps.workouts.urls")),
    path("api/v1/diet/", include("apps.diet.urls")),
    path("api/v1/professional/", include("apps.professional.urls")),
    path("api/v1/chat/", include("apps.chat.urls")),

    # OpenAPI / Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
