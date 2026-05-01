from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat import services
from apps.chat.serializers import ChatMessageSerializer, ChatThreadSerializer


class ThreadsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        threads = services.list_threads(request.user)
        return Response(ChatThreadSerializer(threads, many=True).data)


class MessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, link_id):
        qs = services.list_messages(request.user, link_id)
        return Response(ChatMessageSerializer(qs, many=True).data)

    def post(self, request, link_id):
        content = (request.data.get("content") or "").strip()
        if not content:
            return Response(
                {"content": "Mensagem vazia."}, status=status.HTTP_400_BAD_REQUEST
            )
        message = services.send_message(request.user, link_id, content)
        return Response(
            ChatMessageSerializer(message).data, status=status.HTTP_201_CREATED
        )


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, link_id):
        updated = services.mark_read(request.user, link_id)
        return Response({"updated": updated})