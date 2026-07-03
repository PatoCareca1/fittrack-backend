# Progress — fittrack-backend

Última atualização: 2026-07-03

## O que já está pronto

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

## O que falta

1. **Sync completo TACO + Open Food Facts**: hoje a base é o seed estático de ~38
   alimentos; o sync incremental via Celery (README raiz 4.6) e a integração OFF
   ainda não existem.
2. **Chat** (`chat/threads/{id}/messages/` + WebSocket via channels) não existe.
3. Recuperação de senha (endpoint de reset) não existe — a tela mobile é só UI.
4. Celery/Redis, notificações push, drf-spectacular, Sentry — ainda não configurados
   (previstos no README raiz seção 4).
5. Cobertura de testes: `professional` (10) e `diet` (8); `users`/`body`/`workouts`
   ainda sem testes (meta RNF07: 70%).

## Notas de integração

- Painel web: `GET /professional/students/` já existe — dá para começar a substituir
  o mock do dashboard (`fittrack-frontend/src/lib/mock-data.ts`).
- Mobile: aceite de convite (`/professional/links/accept/`) casa com a tela
  "Aceitar Convite"; atribuições com "Plano Atribuído".
- Convenção de erros: services levantam `rest_framework.exceptions.ValidationError`
  / `PermissionDenied` (nunca as do Django core, que viram 500).
