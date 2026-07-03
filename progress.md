# Progress — fittrack-backend

Última atualização: 2026-07-02

## O que já está pronto

- `users`: auth completa (register/login/refresh/logout via SimpleJWT, email como
  username), `/me/` com Profile. Register retorna user + par de tokens.
- `body`: BodyMetric com cálculo TMB (Mifflin-St Jeor)/TDEE/macros (RN01–RN03, RN14).
- `workouts`: CRUD de treinos, exercícios, templates com import (RN11), sessões e
  set logs.
- `professional` (**novo, 2026-07-02**): vínculo aluno-profissional por código de
  convite de 6 dígitos, RN05 aplicada em `services.accept_invite` (máx. 1 personal +
  1 nutricionista ativos), `GET /professional/students/` (permissão `IsProfessional`),
  `WorkoutAssignment` (aluno vê somente leitura — RN04/RN10), revoke desativa
  atribuições. 8 testes de API em `apps/professional/tests.py`
  (`manage.py test apps.professional`).

## O que falta

1. **`diet` é stub**: sem models (Food, MealPlan, Meal, MealItem, MealLog), sem busca
   TACO/OFF, sem `mark-done`. Por isso `DietAssignment` também não existe ainda
   (comentado em `apps/professional/models.py`).
2. **Chat** (`chat/threads/{id}/messages/` + WebSocket via channels) não existe.
3. Recuperação de senha (endpoint de reset) não existe — a tela mobile é só UI.
4. Celery/Redis, notificações push, drf-spectacular, Sentry — ainda não configurados
   (previstos no README raiz seção 4).
5. Cobertura de testes: `professional` tem 8 testes; `users`/`body`/`workouts` ainda
   sem testes (meta RNF07: 70%).

## Notas de integração

- Painel web: `GET /professional/students/` já existe — dá para começar a substituir
  o mock do dashboard (`fittrack-frontend/src/lib/mock-data.ts`).
- Mobile: aceite de convite (`/professional/links/accept/`) casa com a tela
  "Aceitar Convite"; atribuições com "Plano Atribuído".
- Convenção de erros: services levantam `rest_framework.exceptions.ValidationError`
  / `PermissionDenied` (nunca as do Django core, que viram 500).
