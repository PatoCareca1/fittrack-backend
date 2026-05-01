from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, user_id: int, reset_link: str) -> None:
    """Envia e-mail de recuperação de senha de forma assíncrona."""
    from django.core.mail import send_mail
    from django.conf import settings

    from apps.users.models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("send_password_reset_email: user %s not found", user_id)
        return

    subject = "FitTrack — Recuperação de senha"
    message = (
        f"Olá, {user.first_name or user.email}!\n\n"
        "Recebemos uma solicitação para redefinir a senha da sua conta FitTrack.\n\n"
        f"Use o link abaixo (válido por 1 hora):\n{reset_link}\n\n"
        "Se você não solicitou isso, ignore este e-mail — sua senha permanece a mesma.\n\n"
        "Equipe FitTrack"
    )
    from_email = settings.DEFAULT_FROM_EMAIL

    try:
        send_mail(subject, message, from_email, [user.email], fail_silently=False)
        logger.info("Password reset e-mail sent to %s", user.email)
    except Exception as exc:
        logger.error("Failed to send password reset e-mail to %s: %s", user.email, exc)
        raise self.retry(exc=exc)
