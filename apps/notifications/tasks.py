from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_push_notification(self, notification_id: int) -> None:
    from .models import Notification, FCMDevice
    try:
        import firebase_admin
        from firebase_admin import messaging
    except ImportError:
        logger.warning("firebase-admin not installed; skipping push")
        return

    try:
        notification = Notification.objects.select_related("user").get(pk=notification_id)
    except Notification.DoesNotExist:
        return

    tokens = list(
        FCMDevice.objects.filter(user=notification.user, is_active=True).values_list("token", flat=True)
    )
    if not tokens:
        return

    _ensure_firebase_app()

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=notification.title,
            body=notification.body,
        ),
        data={k: str(v) for k, v in notification.data.items()},
        tokens=tokens,
    )
    try:
        response = messaging.send_each_for_multicast(message)
        _handle_send_response(notification.user, tokens, response)
    except Exception as exc:
        logger.error("FCM send failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task
def mark_stale_sessions_as_draft() -> int:
    """RN08: sessions in_progress for more than 24h are moved to DRAFT."""
    from django.utils import timezone
    from datetime import timedelta
    from apps.workouts.models import WorkoutSession, SessionStatus

    cutoff = timezone.now() - timedelta(hours=24)
    updated = WorkoutSession.objects.filter(
        status=SessionStatus.IN_PROGRESS,
        started_at__lt=cutoff,
    ).update(status=SessionStatus.DRAFT)

    if updated:
        logger.info("Marked %d stale sessions as DRAFT", updated)
    return updated


def _ensure_firebase_app():
    import firebase_admin
    from firebase_admin import credentials
    from django.conf import settings

    if not firebase_admin._apps:
        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", None)
        if cred_path:
            cred = credentials.Certificate(cred_path)
        else:
            cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)


def _handle_send_response(user, tokens, response):
    from .models import FCMDevice
    import firebase_admin.messaging as messaging

    for idx, result in enumerate(response.responses):
        if not result.success:
            err = result.exception
            if isinstance(err, (
                messaging.UnregisteredError,
                messaging.InvalidArgumentError,
            )):
                FCMDevice.objects.filter(user=user, token=tokens[idx]).update(is_active=False)
                logger.info("Deactivated invalid token for %s", user.email)