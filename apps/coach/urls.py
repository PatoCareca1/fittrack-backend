from django.urls import path

from apps.coach.views import CoachJobDetailView, CoachMessageView, ConversationMessagesView

urlpatterns = [
    path("messages/", CoachMessageView.as_view(), name="coach-messages"),
    path("jobs/<int:pk>/", CoachJobDetailView.as_view(), name="coach-job-detail"),
    path(
        "conversations/<int:pk>/messages/",
        ConversationMessagesView.as_view(),
        name="coach-conversation-messages",
    ),
]
