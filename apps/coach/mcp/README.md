# FitTrack MCP Server

Servidor [MCP](https://modelcontextprotocol.io) (Model Context Protocol) do
FitTrack. Expõe ferramentas e dados do FitTrack a um host MCP externo —
tipicamente o **Claude Desktop do nutricionista/personal trainer** vinculado
a um aluno — para que o profissional consulte e atue sobre os dados dos seus
alunos a partir do seu próprio cliente de IA.

## Por que MCP aqui, e deliberadamente não entre os agentes internos

O FitTrack já tem agentes de IA internos (`apps/coach/agents/`: dieta,
crítico, gerente) que conversam entre si via chamadas Python diretas — não
via MCP. Isso é proposital: MCP existe para expor ferramentas a um **modelo
que o FitTrack não controla** (o do host externo). Entre os próprios
agentes, que já rodam no mesmo processo e são código nosso, adicionar uma
camada de protocolo (serialização JSON-RPC, autenticação por mensagem,
transporte HTTP) só adicionaria latência e superfície de falha sem nenhum
ganho — eles já se chamam como funções Python.

Pela mesma razão, **este servidor MCP não contém nenhum LLM e não expõe os
agentes de IA internos como tools**. Ele expõe só ferramentas
determinísticas (consultas ao banco, criação de registros com validação de
código) e dados de leitura. Embrulhar um agente — que já é uma chamada de
LLM — numa tool chamada por outro LLM (o do host MCP) dobraria custo de
inferência e empilharia alucinação de um modelo sobre a saída de outro, sem
nenhum ganho: quem tem o modelo é o host do outro lado da conexão MCP; o
FitTrack só precisa fornecer as ferramentas e os dados corretos.

## Transporte

HTTP, montado em `POST /mcp/` (não stdio — precisa ser acessível a um host
remoto, não a um processo filho local).

O SDK oficial de MCP para Python (pacote `mcp`) foi avaliado antes de
implementar isto manualmente. O transporte HTTP do SDK
(`mcp.server.streamable_http`) é construído sobre ASGI/Starlette; este
projeto serve via **WSGI** de fato (`manage.py runserver`, e o
`Dockerfile`/`docker-compose.yml` não configuram um servidor ASGI como
daphne/uvicorn). Rodar um sub-app ASGI dentro dessa stack WSGI exigiria uma
ponte ASGI-em-WSGI só para este endpoint — risco e complexidade reais para
uma única rota. Como a camada de transporte HTTP do MCP é, na essência, um
envelope JSON-RPC 2.0 sobre POST, implementamos esse envelope diretamente
como uma view do DRF (`apps/coach/mcp/views.py` + `server.py`), de forma
síncrona — mesma fidelidade ao protocolo na borda, sem trocar a stack de
serving do projeto inteiro por causa de uma integração.

Métodos JSON-RPC suportados: `initialize`, `notifications/initialized`,
`tools/list`, `tools/call`, `resources/list`, `resources/read`.

## Autenticação

Reaproveita o **mesmo JWT (SimpleJWT)** que o resto da API FitTrack já usa —
não há um sistema de autenticação novo para o MCP. O host se autentica
enviando o access token do profissional no header:

```
Authorization: Bearer <access_token>
```

`initialize` e `tools/list` não exigem token (só descrevem o servidor). Toda
mensagem que toca dado de aluno (`tools/call`, `resources/list`,
`resources/read`) exige um JWT válido; sem ele, o servidor responde um erro
JSON-RPC de autenticação (`code: -32001`).

## Segurança: vínculo profissional-aluno (RN05)

Estes dados são de saúde. Toda ferramenta ou recurso que toque dados de um
aluno específico (`obter_metricas`, `criar_plano_alimentar`,
`fittrack://aluno/{id}/...`) valida que o profissional autenticado tem um
`ProfessionalLink` **ATIVO** com aquele aluno (a mesma regra RN05 já
aplicada em `apps/professional`). Sem vínculo, o servidor responde um erro
de permissão explícito (`code: -32002`) — nunca uma lista vazia silenciosa,
nunca dado do aluno vazado.

`buscar_alimento` e `listar_exercicios` são catálogos públicos e não exigem
vínculo com nenhum aluno.

`criar_plano_alimentar` exige, além do vínculo ativo, que o profissional
autenticado seja **nutricionista** (`account_type == "nutritionist"`) — a
mesma regra de `apps.professional.services.assign_meal_plan`.

## Tools

| Tool                    | Vínculo exigido | Descrição                                                                 |
|--------------------------|:---:|-----------------------------------------------------------------------------|
| `listar_alunos`          | —   | Alunos com vínculo ativo com o profissional autenticado.                    |
| `obter_metricas`         | ✅  | Histórico de métricas corporais + alvos nutricionais calculados de um aluno.|
| `buscar_alimento`        | —   | Busca no catálogo de alimentos (TACO + próprios). Dado público.             |
| `listar_exercicios`      | —   | Catálogo público de exercícios, opcionalmente por grupo muscular.           |
| `criar_plano_alimentar`  | ✅ + nutricionista | Cria um plano alimentar para o aluno, validado pela mesma regra determinística do agente de dieta interno (`apps.coach.validators.validate_meal_plan`). Uma proposta fora dos alvos nutricionais do aluno é rejeitada com os mesmos erros acionáveis que rejeitariam o agente de IA interno — a regra de negócio não é duplicada. |

## Resources

| URI                                  | Descrição                                  |
|---------------------------------------|---------------------------------------------|
| `fittrack://aluno/{id}/perfil`        | Perfil, objetivo e nível de atividade do aluno. |
| `fittrack://aluno/{id}/metricas`      | Últimas métricas corporais e alvos calculados.  |

`resources/list` retorna, para o profissional autenticado, os recursos
concretos de cada aluno com vínculo ativo.

## Exemplo de configuração de cliente MCP

Configuração de um host MCP compatível com transporte HTTP (streamable
HTTP/JSON-RPC), como o Claude Desktop, apontando para uma instância local:

```json
{
  "mcpServers": {
    "fittrack": {
      "url": "http://localhost:8000/mcp/",
      "headers": {
        "Authorization": "Bearer <access_token_do_profissional>"
      }
    }
  }
}
```

O `access_token` é obtido normalmente via `POST /api/v1/auth/login/` (mesmo
fluxo de login da API REST) e deve pertencer a um usuário com
`account_type` `personal` ou `nutritionist`.
