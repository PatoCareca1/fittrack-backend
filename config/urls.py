from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "FitTrack — Administração"
admin.site.site_title = "FitTrack Admin"
admin.site.index_title = "Painel administrativo"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/me/", include("apps.users.me_urls")),
    path("api/v1/me/body-metrics/", include("apps.body.urls")),
    path("api/v1/", include("apps.workouts.urls")),
    path("api/v1/diet/", include("apps.diet.urls")),
    path("api/v1/professional/", include("apps.professional.urls")),
]
