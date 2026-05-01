from rest_framework import serializers

from apps.chat.models import ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source="sender.email", read_only=True)

    class Meta:
        model = ChatMessage
        fields = ("id", "sender", "sender_email", "content", "read_at", "created_at")
        read_only_fields = ("id", "sender", "sender_email", "read_at", "created_at")


class ChatThreadSerializer(serializers.Serializer):
    link_id = serializers.IntegerField()
    other_user_email = serializers.EmailField()
    other_user_type = serializers.CharField()
    last_message = serializers.CharField(allow_null=True)
    last_message_at = serializers.DateTimeField(allow_null=True)
    unread_count = serializers.IntegerField()