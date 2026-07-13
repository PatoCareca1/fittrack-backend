from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.coach.mcp.server import handle_message


class MCPView(APIView):
    """Endpoint HTTP único do servidor MCP do FitTrack: POST /mcp/ recebe
    uma mensagem (ou lote de mensagens) JSON-RPC 2.0.

    `authentication_classes`/`permission_classes` ficam vazios de propósito:
    a autenticação acontece por MENSAGEM (via `apps.coach.mcp.auth`), não
    por request HTTP — `initialize` e `tools/list` são públicos (descrevem o
    servidor), o resto exige o JWT do profissional."""

    authentication_classes = []
    permission_classes = []
    parser_classes = [JSONParser]

    def post(self, request):
        payload = request.data

        if isinstance(payload, list):
            responses = [handle_message(request, item) for item in payload]
            responses = [response for response in responses if response is not None]
            if not responses:
                return Response(status=204)
            return Response(responses)

        result = handle_message(request, payload)
        if result is None:
            return Response(status=204)
        return Response(result)
