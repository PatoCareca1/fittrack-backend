from django.urls import path

from apps.coach.mcp.views import MCPView

urlpatterns = [
    path("", MCPView.as_view(), name="mcp-endpoint"),
]
