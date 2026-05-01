from django.contrib.auth import authenticate
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User

_token_generator = PasswordResetTokenGenerator()


def register_user(data: dict) -> dict:
    from apps.users.serializers import RegisterSerializer, UserSerializer

    serializer = RegisterSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    tokens = _generate_tokens(user)
    return {"user": UserSerializer(user).data, **tokens}


def login_user(email: str, password: str) -> dict:
    user = authenticate(username=email, password=password)
    if user is None:
        raise AuthenticationFailed("Credenciais inválidas.")
    if not user.is_active:
        raise AuthenticationFailed("Conta desativada.")
    return _generate_tokens(user)


def logout_user(refresh_token: str) -> None:
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
    except Exception:
        raise ValidationError("Token inválido ou já revogado.")


def update_me(user: User, data: dict) -> User:
    from apps.users.serializers import MeSerializer

    serializer = MeSerializer(user, data=data, partial=True)
    serializer.is_valid(raise_exception=True)
    return serializer.save()


def _generate_tokens(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def request_password_reset(email: str, reset_url_base: str) -> None:
    """
    Gera token de reset e dispara e-mail via Celery.
    Retorna silenciosamente para e-mails não cadastrados (evita enumeração).
    """
    from apps.users.tasks import send_password_reset_email

    try:
        user = User.objects.get(email__iexact=email, is_active=True)
    except User.DoesNotExist:
        return

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = _token_generator.make_token(user)
    reset_link = f"{reset_url_base.rstrip('/')}/{uid}/{token}/"
    send_password_reset_email.delay(user.pk, reset_link)


def confirm_password_reset(uid_b64: str, token: str, new_password: str) -> None:
    """Valida uid + token e define a nova senha."""
    try:
        uid = force_str(urlsafe_base64_decode(uid_b64))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, OverflowError):
        raise ValidationError({"uid": "Link inválido."})

    if not _token_generator.check_token(user, token):
        raise ValidationError({"token": "Token inválido ou expirado."})

    user.set_password(new_password)
    user.save(update_fields=["password"])