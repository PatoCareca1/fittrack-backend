from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.chat.models import ChatMessage
from apps.professional.models import LinkStatus, ProfessionalLink
from apps.users.models import User


def _ensure_access(user: User, link_id: int) -> ProfessionalLink:
    try:
        link = ProfessionalLink.objects.get(id=link_id, status=LinkStatus.ACTIVE)
    except ProfessionalLink.DoesNotExist:
        raise PermissionDenied("Vínculo não encontrado ou inativo.")
    if user.id not in (link.student_id, link.professional_id):
        raise PermissionDenied("Você não faz parte desta conversa.")
    return link


def send_message(user: User, link_id: int, content: str) -> ChatMessage:
    link = _ensure_access(user, link_id)
    message = ChatMessage.objects.create(link=link, sender=user, content=content)
    _broadcast(link_id, message)
    return message


def list_messages(user: User, link_id: int):
    _ensure_access(user, link_id)
    return ChatMessage.objects.filter(link_id=link_id).select_related("sender")


def mark_read(user: User, link_id: int) -> int:
    _ensure_access(user, link_id)
    return ChatMessage.objects.filter(
        link_id=link_id, read_at__isnull=True
    ).exclude(sender=user).update(read_at=timezone.now())


def list_threads(user: User) -> list[dict]:
    links = (
        ProfessionalLink.objects
        .filter(Q(student=user) | Q(professional=user), status=LinkStatus.ACTIVE)
        .select_related("student", "professional")
        .annotate(
            last_at=Max("messages__created_at"),
            unread=Count(
                "messages",
                filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=user),
            ),
        )
    )

    threads = []
    for link in links:
        other = link.professional if link.student_id == user.id else link.student
        last_message = (
            ChatMessage.objects.filter(link=link).order_by("-created_at").first()
        )
        threads.append({
            "link_id": link.id,
            "other_user_email": other.email,
            "other_user_type": other.get_account_type_display(),
            "last_message": last_message.content if last_message else None,
            "last_message_at": last_message.created_at if last_message else None,
            "unread_count": link.unread,
        })
    threads.sort(key=lambda t: t["last_message_at"] or timezone.now(), reverse=True)
    return threads


def _broadcast(link_id: int, message: ChatMessage) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"chat_{link_id}",
        {
            "type": "chat.message",
            "id": message.id,
            "sender_id": message.sender_id,
            "sender_email": message.sender.email,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        },
    )