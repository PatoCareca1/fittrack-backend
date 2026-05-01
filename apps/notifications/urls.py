from django.urls import path
from .views import NotificationListView, RegisterDeviceView, mark_all_read_view, mark_read_view

urlpatterns = [
    path("devices/register/", RegisterDeviceView.as_view(), name="device-register"),
    path("", NotificationListView.as_view(), name="notification-list"),
    path("<int:pk>/read/", mark_read_view, name="notification-read"),
    path("read-all/", mark_all_read_view, name="notification-read-all"),
]