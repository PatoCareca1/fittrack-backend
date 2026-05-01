from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FCMDevice, Notification
from .serializers import FCMDeviceSerializer, NotificationSerializer
from .services import mark_all_as_read, mark_as_read, register_device


class RegisterDeviceView(generics.CreateAPIView):
    serializer_class = FCMDeviceSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        register_device(
            user=self.request.user,
            token=serializer.validated_data["token"],
            device_id=serializer.validated_data["device_id"],
            platform=serializer.validated_data.get("platform", "android"),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({"detail": "Dispositivo registrado."}, status=status.HTTP_200_OK)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_read_view(request, pk):
    from django.shortcuts import get_object_or_404
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    mark_as_read(request.user, notification.pk)
    return Response({"detail": "Lida."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_read_view(request):
    count = mark_all_as_read(request.user)
    return Response({"marked_read": count})


class DeactivateDeviceView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, device_id: str):
        updated = FCMDevice.objects.filter(
            user=request.user, device_id=device_id
        ).update(is_active=False)
        if not updated:
            from rest_framework.exceptions import NotFound
            raise NotFound("Dispositivo não encontrado.")
        return Response(status=status.HTTP_204_NO_CONTENT)