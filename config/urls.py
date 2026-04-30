from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/me/", include("apps.users.me_urls")),
    path("api/v1/me/body-metrics/", include("apps.body.urls")),
]