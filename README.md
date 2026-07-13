# fittrack-backend

API REST (Django 5 + DRF) do FitTrack, consumida pelo app mobile (Flutter) e pelo
painel web (Next.js). JWT via SimpleJWT (access 15min + refresh).

**Contexto completo do produto** (visão, stack, modelo de dados, RN01–RN14, RNFs):
ver `../fittrack-frontend/README.md`. Fonte de verdade em caso de conflito:
`FitTrack_Documento_de_Requisitos_v1.pdf` e `FitTrack_Decisoes_v2.pdf`.

**Estado atual e pendências:** ver `progress.md`.

## Apps (domínios)

| App | Conteúdo |
|---|---|
| `users` | User customizado (email login, `account_type`), Profile, register/login/refresh/logout, `/me/` |
| `body` | BodyMetric (bioimpedância) + cálculo TMB/TDEE/macros (RN01–RN03, RN14) |
| `workouts` | Exercise, Workout, WorkoutExercise, WorkoutSession, SetLog, templates (RN11) |
| `professional` | ProfessionalLink (convite por código, RN05), WorkoutAssignment (RN04/RN10), lista de alunos |
| `diet` | Food (TACO seed + customizados), MealPlan/Meal/MealItem aninhados, MealLog (mark-done diário, RN09) |
| `coach` | Agentes de IA (dieta + crítico + gerente), execução assíncrona, servidor MCP — ver seção própria abaixo |

Padrão interno obrigatório: views finas; regra de negócio em `services.py`
(exceções do DRF: `ValidationError`/`PermissionDenied`).

## Endpoints principais (`/api/v1/`)

```
POST  /auth/register|login|refresh|logout/
GET/PATCH /me/
GET/POST/PATCH/DELETE /me/body-metrics/
GET/POST/PATCH/DELETE /workouts/            (+ /workouts/templates/, /workouts/{id}/import/)
POST  /workouts/{id}/start-session/ · PATCH /workout-sessions/{id}/log-set/ · POST .../finish/
GET   /diet/foods/?q=&source=               busca no catálogo (seed TACO incluso)
POST  /diet/foods/                          alimento personalizado (privado do usuário)
GET/POST/PATCH/DELETE /diet/meal-plans/     planos com refeições/itens aninhados + macros
POST  /diet/meals/{id}/mark-done/           marca refeição no dia ({date?, comment?}) — idempotente
POST  /diet/meals/{id}/unmark/              desfaz a marcação do dia
GET   /diet/meal-logs/?date=                histórico de refeições concluídas
GET/POST /professional/links/               vínculos do usuário autenticado
POST  /professional/links/invite/           profissional gera código de 6 dígitos
POST  /professional/links/accept/           aluno aceita ({"invite_code": "ABC123"})
POST  /professional/links/{id}/revoke/      qualquer parte desvincula
GET   /professional/students/               alunos ativos (só profissionais)
GET/POST /professional/assignments/         atribuição de treino (POST só profissional)
GET/POST /professional/diet-assignments/    atribuição de plano alimentar (RN09)
POST  /coach/messages/                      mensagem do aluno; roteia (Intent) e dispara job de dieta
GET   /coach/jobs/{id}/                     status do job (+ plano/critic_summary/issues quando succeeded)
GET   /coach/conversations/{id}/messages/   histórico da conversa com o Coach
POST  /mcp/                                 servidor MCP (JSON-RPC 2.0) — ver seção "Coach (IA)"
```

## Coach (IA)

Sistema multiagente (gerar plano alimentar por IA) + servidor MCP para
profissionais vinculados. Arquitetura completa, diagramas e as decisões
(com trade-offs negativos assumidos) estão documentados em:

- [`docs/arquitetura-coach.md`](docs/arquitetura-coach.md) — visão geral em 3 minutos, com diagramas do fluxo completo e do servidor MCP.
- [`docs/adr/`](docs/adr/README.md) — um ADR por decisão (ex.: por que o LLM nunca calcula número, por que o crítico roda em outro fornecedor, por que a execução assíncrona por thread é dívida técnica assumida).

### Endpoints REST

`POST /coach/messages/` recebe `{"message": str, "conversation_id": int|null}`,
roteia via `apps.coach.agents.manager.route()` e:
- intenção de dieta → dispara job assíncrono, responde `202` com `{"job_id"}`;
- treino → `200` avisando que o agente de treino ainda não existe;
- fora de escopo / ambíguo → `200` com orientação ao aluno.

`GET /coach/jobs/{id}/` consulta o status (`pending`/`running`/`succeeded`/
`failed`); quando `succeeded`, inclui o plano persistido (mesmo serializer
do app `diet`), `critic_summary`, `issues` e `totals`. Isolamento por
usuário em todas as rotas — job/conversa de outro usuário sempre `404`.

### Servidor MCP (`/mcp/`)

Expõe dados e ferramentas determinísticas do FitTrack a um host MCP
externo — tipicamente o **Claude Desktop do nutricionista/personal**
vinculado a um aluno. **Não contém nenhum LLM** (ver ADR-006): quem
raciocina é o modelo do host; o FitTrack só fornece `listar_alunos`,
`obter_metricas`, `buscar_alimento`, `listar_exercicios` e
`criar_plano_alimentar` (esta última reaproveitando a mesma validação
determinística do agente interno — `apps.coach.validators.validate_meal_plan`).
Toda ferramenta que toca dado de um aluno exige `ProfessionalLink` **ATIVO**
(RN05); sem vínculo, erro explícito, nunca dado vazado.

Autenticação: o mesmo JWT (SimpleJWT) do resto da API, no header
`Authorization: Bearer <access_token>` de cada mensagem JSON-RPC. Protocolo
implementado manualmente sobre JSON-RPC 2.0 (não o SDK oficial — motivo em
ADR-007). Detalhes completos, exemplo de config de cliente MCP e a lista
de tools/resources: [`apps/coach/mcp/README.md`](apps/coach/mcp/README.md).

### Variáveis de ambiente (`COACH_*`)

| Variável | Default | Uso |
|---|---|---|
| `COACH_GENERATOR_PROVIDER` | `anthropic` | Fornecedor do agente de dieta e do gerente (desambiguação) |
| `COACH_CRITIC_PROVIDER` | `gemini` | Fornecedor do agente crítico — deliberadamente diferente do gerador (ADR-003) |
| `COACH_MAX_ITERATIONS` | `3` | Máximo de tentativas do agente de dieta contra a validação determinística |
| `COACH_MAX_CRITIC_ROUNDS` | `2` | Máximo de rodadas gerador↔crítico no pipeline completo |
| `ANTHROPIC_API_KEY` | — | Chave da API Anthropic (`httpx` puro, sem SDK — ADR-004) |
| `GEMINI_API_KEY` | — | Chave da API Gemini (`httpx` puro, sem SDK — ADR-004) |

Trocar de fornecedor é mudar `COACH_GENERATOR_PROVIDER`/
`COACH_CRITIC_PROVIDER` — nenhuma mudança de código.

## Rodando

```bash
poetry install                    # 1ª vez: instala deps Python em .venv/ (in-project)
cp .env.example .env              # 1ª vez
docker compose up -d db      # PostgreSQL (porta 5432)
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver              # só localhost (web/emulador)
.venv/bin/python manage.py runserver 0.0.0.0:8000 # aceita celular físico na rede local
.venv/bin/python manage.py test apps              # testes
```

Variáveis em `.env` (ver `.env.example`).

**Para o app mobile no celular físico**: rode com `0.0.0.0:8000` (o `ALLOWED_HOSTS`
de dev já aceita), garanta celular e notebook na mesma rede (Wi-Fi ou o PC na LAN
por cabo/roteador — não precisa Wi-Fi no PC, só estar na mesma sub-rede) e libere
a porta 8000 no firewall se houver. O passo a passo completo do lado do app está em
`../fittrack-mobile/README.md` (seção "Rodando").

**Troubleshooting — `migrate` falha com "column ... does not exist"**: normalmente é
o volume Docker do Postgres com um schema antigo (de uma versão anterior de algum
model, antes de uma migration ser reescrita). Como é só dado de dev/seed, resete:
```bash
docker compose down -v && docker compose up -d db
.venv/bin/python manage.py migrate
```
