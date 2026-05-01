from django.urls import path

from apps.notifications.views import DeactivateDeviceView, RegisterDeviceView

urlpatterns = [
    path("", RegisterDeviceView.as_view(), name="device-register"),
    path("<str:device_id>/", DeactivateDeviceView.as_view(), name="device-deactivate"),
]
