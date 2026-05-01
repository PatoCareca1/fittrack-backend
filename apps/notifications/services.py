from django.utils import timezone
from .models import FCMDevice, Notification, NotificationType


def register_device(user, token: str, device_id: str, platform: str = "android") -> FCMDevice:
    device, _ = FCMDevice.objects.update_or_create(
        user=user,
        device_id=device_id,
        defaults={"token": token, "platform": platform, "is_active": True},
    )
    return device


def create_notification(user, notification_type: str, title: str, body: str, data: dict = None) -> Notification:
    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        body=body,
        data=data or {},
    )


def mark_as_read(user, notification_id: int) -> Notification:
    notification = Notification.objects.get(pk=notification_id, user=user)
    if not notification.read_at:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification


def mark_all_as_read(user) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).update(read_at=timezone.now())


def notify_new_message(message) -> None:
    from .tasks import send_push_notification
    recipient = (
        message.link.professional
        if message.sender == message.link.student
        else message.link.student
    )
    notification = create_notification(
        user=recipient,
        notification_type=NotificationType.NEW_MESSAGE,
        title="Nova mensagem",
        body=f"{message.sender.get_full_name() or message.sender.email}: {message.content[:80]}",
        data={"link_id": message.link_id, "message_id": message.pk},
    )
    send_push_notification.delay(notification.pk)


def notify_workout_assigned(assignment) -> None:
    from .tasks import send_push_notification
    notification = create_notification(
        user=assignment.link.student,
        notification_type=NotificationType.WORKOUT_ASSIGNED,
        title="Novo treino atribuído",
        body=f"Seu profissional atribuiu o treino: {assignment.workout.name}",
        data={"workout_id": assignment.workout_id},
    )
    send_push_notification.delay(notification.pk)


def notify_meal_plan_assigned(assignment) -> None:
    from .tasks import send_push_notification
    notification = create_notification(
        user=assignment.link.student,
        notification_type=NotificationType.MEAL_PLAN_ASSIGNED,
        title="Novo plano alimentar atribuído",
        body=f"Seu profissional atribuiu o plano: {assignment.meal_plan.name}",
        data={"meal_plan_id": assignment.meal_plan_id},
    )
    send_push_notification.delay(notification.pk)


def notify_link_accepted(link) -> None:
    from .tasks import send_push_notification
    notification = create_notification(
        user=link.professional,
        notification_type=NotificationType.LINK_ACCEPTED,
        title="Vínculo aceito",
        body=f"{link.student.get_full_name() or link.student.email} aceitou seu convite.",
        data={"link_id": link.pk},
    )
    send_push_notification.delay(notification.pk)