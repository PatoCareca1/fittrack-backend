from django.urls import path

from apps.users.views import MeView

urlpatterns = [
    path("", MeView.as_view(), name="me"),
]