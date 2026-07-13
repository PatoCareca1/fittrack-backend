# Progress — fittrack-backend

Última atualização: 2026-07-13

## O que já está pronto

**Ambiente rodando ponta a ponta** (2026-07-04): `poetry install`, `docker compose up
-d db` + `migrate` + `runserver 0.0.0.0:8000`, validado com o app mobile real
(celular físico via Wi-Fi, ver `../fittrack-mobile/progress.md`). Achado no processo:
o volume Docker local tinha um schema `diet_food` desatualizado (de antes da migration
`0001_initial` ser reescrita com os nomes de campo atuais — `kcal`/`protein_g`/etc.)
que quebrava `migrate` na seed da migration `0002`; resolvido com
`docker compose down -v` (dado de dev, sem perda real). Nota para troubleshooting
futuro adicionada ao README. Pendente: hospedar o backend (Render.com recomendado
para teste, grátis) para não depender do notebook ligado — ver
`../fittrack-mobile/progress.md` item 8.

- `users`: auth completa (register/login/refresh/logout via SimpleJWT, email como
  username), `/me/` com Profile. Register retorna user + par de tokens.
- `body`: BodyMetric com cálculo TMB (Mifflin-St Jeor)/TDEE/macros (RN01–RN03, RN14).
- `workouts`: CRUD de treinos, exercícios, templates com import (RN11), sessões e
  set logs.
- `diet` (**novo, 2026-07-03**): Food com seed de ~38 alimentos TACO (migration
  `0002_seed_taco_foods` — sync completo TACO/OFF via Celery fica para depois),
  busca `GET /diet/foods/?q=`, alimentos personalizados privados por usuário,
  MealPlan/Meal/MealItem com escrita aninhada e macros calculados por item/refeição,
  MealLog com `mark-done`/`unmark` idempotentes por dia (RN09). 8 testes de API.
- `professional` (**2026-07-02, estendido 2026-07-03**): vínculo aluno-profissional
  por código de convite de 6 dígitos, RN05 aplicada em `services.accept_invite`
  (máx. 1 personal + 1 nutricionista ativos), `GET /professional/students/`
  (permissão `IsProfessional`), `WorkoutAssignment` (RN04/RN10) e `DietAssignment`
  (RN09 — nutricionista atribui plano; aluno vê somente leitura e marca refeições);
  revoke desativa atribuições de treino e dieta. 10 testes de API.

- **Suporte ao MVP demo (2026-07-03)** — ver `../fittrack-mobile/MVP.md`: seed de
  57 exercícios (`workouts.0002`), `body_fat_pct` opcional em BodyMetric (pesagem
  simples; RN14 vale para bioimpedância — confirmar com Amanda), endpoints
  granulares de refeição/item (preservam MealLogs; o PATCH aninhado recriava
  refeições e apagava logs em cascata), `finish` de sessão aceita `notes`,
  `workout_name` no serializer de sessão. 19 testes passando.

- **`coach` — agentes de IA (2026-07-12/13)**: app novo, construído em etapas —
  fundação (providers httpx puro para Anthropic/Gemini, sem SDK proprietário;
  models `CoachConversation`/`CoachMessage`/`AgentRun`); agente de dieta
  (`generate_meal_plan`) com loop de retry contra `validate_meal_plan`
  determinística (LLM só escolhe `food_id`+`quantity_g`, nunca calcula macro);
  agente crítico (`review_meal_plan`) em fornecedor diferente do gerador,
  decisão final de aprovação em Python (nunca no campo `approved` do LLM);
  agente gerente (`manager.route`) determinístico por palavra-chave, LLM só em
  mensagem ambígua; execução assíncrona via `threading.Thread` (dívida técnica
  assumida — ver ADR-008, Celery é o próximo passo real); endpoints REST
  (`/coach/messages/`, `/coach/jobs/{id}/`, `/coach/conversations/{id}/messages/`)
  com isolamento por usuário; servidor MCP em `/mcp/` (JSON-RPC 2.0 manual, sem
  SDK oficial — ADR-007) expondo dados e ferramentas determinísticas a um host
  externo (Claude Desktop do profissional), com checagem de vínculo RN05 em
  toda ferramenta que toca aluno. **Agente de treino não existe ainda** — o
  gerente já roteia `WORKOUT_PLAN`, mas o endpoint só responde "indisponível".
  70 testes passando. Arquitetura completa e decisões (com trade-offs
  negativos assumidos) em `docs/arquitetura-coach.md` e `docs/adr/`.

## O que falta

1. **Sync completo TACO + Open Food Facts**: hoje a base é o seed estático de ~38
   alimentos; o sync incremental via Celery (README raiz 4.6) e a integração OFF
   ainda não existem.
2. **Chat** (`chat/threads/{id}/messages/` + WebSocket via channels) não existe.
3. Recuperação de senha (endpoint de reset) não existe — a tela mobile é só UI.
4. Celery/Redis, notificações push, drf-spectacular, Sentry — ainda não configurados
   (previstos no README raiz seção 4). Para `coach` especificamente, Celery não é
   só "melhoria" — é o item que resolve a dívida técnica assumida em ADR-008
   (jobs em thread: sem retry, sem persistência de fila, morrem se o processo
   cair, não escalam horizontalmente). `redis` já está no `docker-compose.yml`,
   mas nenhum worker Celery está configurado.
5. Cobertura de testes: `professional` (10) e `diet` (8); `users`/`body`/`workouts`
   ainda sem testes (meta RNF07: 70%).
6. **Agente de Treino** (`apps/coach/agents/workout.py`) não existe. O gerente já
   classifica `Intent.WORKOUT_PLAN`, mas `POST /coach/messages/` só responde que
   o recurso ainda não está disponível — nenhum job é criado para essa intenção.
7. **Endpoints REST do MCP não têm rate limiting nem throttling** — um host
   externo mal configurado pode gerar chamadas em excesso; considerar antes de
   expor a instância além de uso interno/demo.

## Notas de integração

- Painel web: `GET /professional/students/` já existe — dá para começar a substituir
  o mock do dashboard (`fittrack-frontend/src/lib/mock-data.ts`).
- Mobile: aceite de convite (`/professional/links/accept/`) casa com a tela
  "Aceitar Convite"; atribuições com "Plano Atribuído".
- Convenção de erros: services levantam `rest_framework.exceptions.ValidationError`
  / `PermissionDenied` (nunca as do Django core, que viram 500).
