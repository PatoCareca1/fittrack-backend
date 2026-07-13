from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

# Reaproveita exatamente o mesmo esquema de autenticação da API REST
# (SimpleJWT) — o host MCP (ex.: Claude Desktop do profissional) se
# autentica com o mesmo access token JWT que o app FitTrack já emite.
# Não inventamos um sistema de auth novo para o MCP.
_jwt_authenticator = JWTAuthentication()


def resolve_user(django_request):
    """Resolve o usuário autenticado a partir do header Authorization: Bearer
    <jwt>. Sem token válido, levanta AuthenticationFailed (mapeado para um
    erro JSON-RPC pelo dispatcher em server.py)."""
    try:
        result = _jwt_authenticator.authenticate(django_request)
    except Exception as exc:
        raise AuthenticationFailed(str(exc)) from exc
    if result is None:
        raise AuthenticationFailed(
            "Token JWT ausente ou inválido no header Authorization."
        )
    user, _token = result
    return user
