from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


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


def _generate_tokens(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }