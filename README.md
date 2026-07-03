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
```

## Rodando

```bash
docker compose up -d db      # PostgreSQL (porta 5432)
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver              # só localhost (web/emulador)
.venv/bin/python manage.py runserver 0.0.0.0:8000 # aceita celular físico na rede local
.venv/bin/python manage.py test apps              # testes
```

Variáveis em `.env` (ver `.env.example`).

**Para o app mobile no celular físico**: rode com `0.0.0.0:8000` (o `ALLOWED_HOSTS`
de dev já aceita), garanta celular e notebook na mesma rede Wi-Fi e libere a porta
8000 no firewall se houver. O passo a passo completo do lado do app está em
`../fittrack-mobile/README.md` (seção "Rodando").
