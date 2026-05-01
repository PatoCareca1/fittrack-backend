from django.urls import path

from apps.chat.views import MarkReadView, MessagesView, ThreadsView

urlpatterns = [
    path("threads/", ThreadsView.as_view(), name="chat-threads"),
    path("<int:link_id>/messages/", MessagesView.as_view(), name="chat-messages"),
    path("<int:link_id>/mark-read/", MarkReadView.as_view(), name="chat-mark-read"),
]