# ADR-007 — SDK oficial de MCP descartado

## Contexto

Existe um SDK oficial de MCP para Python (pacote `mcp` no PyPI, disponível
e avaliado — `1.28.1` no momento desta decisão). A orientação era usá-lo
primeiro e só implementar o protocolo manualmente se ele não estivesse
disponível.

## Decisão

O SDK oficial foi avaliado e **descartado** para este projeto. O transporte
HTTP do SDK (`mcp.server.streamable_http`) é construído sobre ASGI/
Starlette. Este projeto serve via **WSGI** de fato: `manage.py runserver`
em desenvolvimento, e o `Dockerfile`/`docker-compose.yml` não configuram
nenhum servidor ASGI (daphne, uvicorn) — `config/asgi.py` existe apenas
como scaffold padrão do Django, não é usado no serving real. Montar um
sub-app ASGI dentro dessa stack WSGI exigiria uma ponte ASGI-em-WSGI só
para o endpoint `/mcp/`, ou migrar o projeto inteiro para ASGI — ambos
riscos e esforço desproporcionais a uma única rota.

A camada de transporte HTTP do MCP é, na essência, um envelope JSON-RPC
2.0 sobre POST. Implementamos esse envelope diretamente
(`apps/coach/mcp/server.py` + `views.py`), como uma view DRF síncrona,
suportando os métodos `initialize`, `notifications/initialized`,
`tools/list`, `tools/call`, `resources/list`, `resources/read` — a mesma
fidelidade ao protocolo na borda da conexão, sem trocar a stack de serving
do projeto por causa de uma integração.

## Alternativas consideradas

- **Usar o SDK oficial mesmo assim, bridging ASGI-em-WSGI.** Rejeitada:
  adicionaria uma dependência de infraestrutura nova (um adaptador
  ASGI↔WSGI) só para uma rota, quando o wire protocol necessário é simples
  o suficiente para implementar direto e testar com o `Client` síncrono do
  Django que o resto do projeto já usa.
- **Migrar o projeto inteiro para ASGI para usar o SDK "do jeito certo".**
  Rejeitada: mudança de escopo muito maior que o pedido (afetaria
  deployment, todos os outros apps, o Dockerfile) só para viabilizar um
  SDK cujo ganho real, neste caso, é pequeno (o subset do protocolo que
  usamos é pequeno e estável).

## Consequências

**Positivas**: zero dependência nova de infraestrutura; o servidor MCP roda
exatamente como o resto do Django (WSGI síncrono), testável com o mesmo
`APIClient`/`TestCase` usado em todos os outros apps do projeto.

**Negativas**: mantemos o protocolo JSON-RPC 2.0 "à mão" — qualquer parte
nova do protocolo MCP que o time queira suportar no futuro (streaming de
respostas, notificações do servidor para o cliente, capacidades mais ricas
de `resources/templates`) precisa ser implementada manualmente, sem a rede
de segurança de conformidade que o SDK oficial garante. **Revisitar esta
decisão se o projeto migrar para ASGI** por qualquer outro motivo — nesse
cenário, adotar o SDK oficial volta a fazer sentido e deveria substituir
`apps/coach/mcp/server.py`.
