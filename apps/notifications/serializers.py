from rest_framework import serializers
from .models import FCMDevice, Notification


class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = ["id", "token", "device_id", "platform", "is_active"]
        read_only_fields = ["id", "is_active"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "notification_type", "title", "body", "data", "read_at", "created_at"]
        read_only_fields = fields