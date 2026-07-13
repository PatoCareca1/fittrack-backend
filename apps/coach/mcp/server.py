# DECISÃO ARQUITETURAL: este servidor MCP NÃO contém LLM nenhum e NÃO expõe
# os agentes de IA internos (apps/coach/agents/*). Ele expõe só ferramentas
# determinísticas e dados. Embrulhar um agente — que já é uma chamada de
# LLM — numa tool chamada por outro LLM (o do host MCP, ex.: Claude Desktop
# do nutricionista) dobraria custo e empilharia alucinação sobre alucinação,
# sem nenhum ganho: quem tem o modelo é o host do outro lado da conexão MCP;
# o FitTrack só precisa fornecer as ferramentas e os dados. Se você se pegar
# importando `apps.coach.providers` ou `apps.coach.agents` aqui, parou algo
# errado — volte e tire.
#
# IMPLEMENTAÇÃO: tentamos o SDK oficial (pacote `mcp` no PyPI) primeiro. Ele
# está disponível e foi avaliado, mas o transporte HTTP do SDK
# (`mcp.server.streamable_http`) é construído sobre ASGI/Starlette — e este
# projeto serve via WSGI de fato (`manage.py runserver`, Dockerfile/
# docker-compose usam o WSGI padrão do Django, não daphne/uvicorn).
# Montar um sub-app ASGI dentro de uma stack WSGI exigiria uma ponte
# ASGI-em-WSGI só para este endpoint — risco e complexidade real para uma
# única rota, sem ganho: o protocolo MCP na camada de transporte HTTP é,
# na essência, JSON-RPC 2.0 sobre POST. Implementamos esse envelope
# diretamente aqui, de forma síncrona, compatível com o resto do projeto —
# mesma fidelidade ao protocolo, sem trocar a stack de serving do projeto
# inteiro por causa de uma integração.

import json

from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.coach.mcp import resources as resources_module
from apps.coach.mcp import tools as tools_module
from apps.coach.mcp.auth import resolve_user

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "fittrack-mcp", "version": "1.0.0"}

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
UNAUTHORIZED = -32001
FORBIDDEN = -32002
NOT_FOUND = -32004


def _error(code: int, message: str, data=None) -> dict:
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return error


def _drf_exception_to_error(exc: Exception) -> dict:
    detail = getattr(exc, "detail", str(exc))
    if isinstance(exc, AuthenticationFailed):
        return _error(UNAUTHORIZED, str(detail))
    if isinstance(exc, PermissionDenied):
        return _error(FORBIDDEN, str(detail))
    if isinstance(exc, NotFound):
        return _error(NOT_FOUND, str(detail))
    if isinstance(exc, ValidationError):
        return _error(INVALID_PARAMS, "Parâmetros inválidos.", data=detail)
    if isinstance(exc, APIException):
        return _error(INTERNAL_ERROR, str(detail))
    return _error(INTERNAL_ERROR, str(exc))


def _call_tool(user, params: dict) -> dict:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    output = tools_module.call_tool(name, arguments, user)
    return {
        "content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}],
        "isError": False,
    }


def _read_resource(user, params: dict) -> dict:
    uri = params.get("uri")
    if not uri:
        raise ValidationError({"uri": "Campo obrigatório."})
    return {"contents": [resources_module.read_resource(user, uri)]}


def handle_message(django_request, payload: dict) -> dict | None:
    """Processa uma única mensagem JSON-RPC 2.0 e devolve a resposta (ou
    None para notificações, que por definição do protocolo não têm
    resposta)."""
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return {
            "jsonrpc": "2.0",
            "id": payload.get("id") if isinstance(payload, dict) else None,
            "error": _error(INVALID_REQUEST, "Mensagem não é um envelope JSON-RPC 2.0 válido."),
        }

    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}
    is_notification = "id" not in payload

    try:
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": SERVER_INFO,
            }
        elif method == "notifications/initialized":
            return None
        elif method == "tools/list":
            result = {"tools": tools_module.TOOLS}
        elif method == "tools/call":
            user = resolve_user(django_request)
            result = _call_tool(user, params)
        elif method == "resources/list":
            user = resolve_user(django_request)
            result = {"resources": resources_module.list_resources(user)}
        elif method == "resources/read":
            user = resolve_user(django_request)
            result = _read_resource(user, params)
        else:
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": _error(METHOD_NOT_FOUND, f"Método desconhecido: {method!r}"),
            }
    except Exception as exc:
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "error": _drf_exception_to_error(exc)}

    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "result": result}
