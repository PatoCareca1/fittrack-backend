# FitTrack — Backend

> **API REST + WebSocket** que sustenta o ecossistema FitTrack: aplicativo Android (Flutter) e painel web profissional (Next.js).

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="Django" src="https://img.shields.io/badge/Django-6.0-092E20?logo=django&logoColor=white">
  <img alt="DRF" src="https://img.shields.io/badge/DRF-3.17-A30000?logo=django&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white">
  <img alt="Redis" src="https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white">
  <img alt="Celery" src="https://img.shields.io/badge/Celery-5.6-37814A?logo=celery&logoColor=white">
  <img alt="Poetry" src="https://img.shields.io/badge/Poetry-2.x-60A5FA?logo=poetry&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white">
</p>

---

## Sumário

- [1. Sobre o FitTrack](#1-sobre-o-fittrack)
- [2. Visão geral do produto](#2-visão-geral-do-produto)
- [3. Arquitetura do sistema](#3-arquitetura-do-sistema)
- [4. Stack tecnológica](#4-stack-tecnológica)
- [5. Estrutura do repositório](#5-estrutura-do-repositório)
- [6. Pré-requisitos](#6-pré-requisitos)
- [7. Setup e execução](#7-setup-e-execução)
- [8. Comandos do Makefile](#8-comandos-do-makefile)
- [9. Variáveis de ambiente](#9-variáveis-de-ambiente)
- [10. Endpoints da API](#10-endpoints-da-api)
- [11. WebSocket — Chat em tempo real](#11-websocket--chat-em-tempo-real)
- [12. Tarefas Celery](#12-tarefas-celery)
- [13. Atores do sistema](#13-atores-do-sistema)
- [14. Requisitos funcionais (RF)](#14-requisitos-funcionais-rf)
- [15. Requisitos não-funcionais (RNF)](#15-requisitos-não-funcionais-rnf)
- [16. Regras de negócio (RN)](#16-regras-de-negócio-rn)
- [17. Modelo de dados](#17-modelo-de-dados)
- [18. Fora do escopo do MVP](#18-fora-do-escopo-do-mvp)
- [19. Roadmap de execução](#19-roadmap-de-execução)
- [20. Critérios de aceitação do MVP](#20-critérios-de-aceitação-do-mvp)
- [21. Equipe e responsáveis](#21-equipe-e-responsáveis)
- [22. Glossário](#22-glossário)

---

## 1. Sobre o FitTrack

O FitTrack nasce de uma necessidade real: **centralizar tudo o que importa para a saúde** de quem treina e cuida da alimentação em um único aplicativo. Hoje, o cenário é fragmentado — uma pessoa que leva fitness a sério usa um app para registrar treino, outro para macros, uma planilha para bioimpedância, uma conversa solta no WhatsApp com o personal e um PDF do nutricionista. Os dados não conversam, a evolução não é visível e o profissional não tem visibilidade real do que o aluno está fazendo no dia a dia.

O FitTrack resolve isso oferecendo uma plataforma **única**, **mobile-first**, com:

- **Treino** — criação, execução offline-friendly, histórico de sessões, recordes pessoais.
- **Dieta** — base de alimentos TACO + Open Food Facts, plano alimentar, marcação de refeições, cálculo automático de calorias e macros.
- **Bioimpedância** — registro manual de medidas corporais com histórico e gráficos de evolução.
- **Profissional ↔ Aluno** — vínculo entre personal/nutricionista e usuário, atribuição de planos, chat interno, acompanhamento da execução.
- **Análise corporal por IA** *(em desenvolvimento)* — visão computacional para análise de proporções a partir de fotos, integrada ao backend via Celery quando estiver pronta.

O projeto começa como **uso pessoal do fundador** e evolui para plataforma multi-usuário com profissionais (Personal Trainers e Nutricionistas).

---

## 2. Visão geral do produto

| Atributo | Definição |
|---|---|
| **Nome** | FitTrack |
| **Plataforma principal** | Android (Google Play Store) |
| **Plataforma secundária** | Web (painel profissional) |
| **Público-alvo** | Atletas amadores, alunos com acompanhamento profissional, personal trainers e nutricionistas |
| **Modelo de negócio** | Freemium (definido, não urgente) |
| **Idioma** | Português (Brasil) |
| **Mercado** | Brasil |

### Plataformas e responsabilidades

| Plataforma | Público | Funções principais |
|---|---|---|
| **Mobile (Flutter/Android)** | Usuário final + profissional em campo | Executar treino, registrar refeição, bioimpedância, chat, receber planos atribuídos |
| **Web (Next.js)** | Profissional no computador | Dashboard de alunos, editor de treino e dieta, atribuição de planos, acompanhamento, chat |
| **Backend (Django/DRF)** | Ambas as plataformas | API REST única + WebSocket. Django Admin como backoffice nativo |

---

## 3. Arquitetura do sistema

```
┌──────────────────────┐     ┌──────────────────────┐
│   Mobile (Flutter)   │     │   Web (Next.js)      │
│   Riverpod 2.x       │     │   React + Tailwind   │
└──────────┬───────────┘     └──────────┬───────────┘
           │                            │
           │  HTTPS  /  WSS             │
           ▼                            ▼
    ┌────────────────────────────────────────┐
    │         Backend Django + DRF           │
    │  ┌──────────────────────────────────┐  │
    │  │  REST API   (/api/v1/)           │  │
    │  │  WebSocket  (Channels + Daphne)  │  │
    │  │  Django Admin (/admin/)          │  │
    │  └──────────────────────────────────┘  │
    └─────┬─────────────┬────────────────┬───┘
          │             │                │
          ▼             ▼                ▼
    ┌──────────┐  ┌──────────┐    ┌──────────┐
    │PostgreSQL│  │  Redis   │    │  Celery  │
    │   16     │  │  cache + │◀───│  worker  │
    │          │  │  broker  │    │  + beat  │
    └──────────┘  └──────────┘    └─────┬────┘
                                        │
                                        ▼
                            ┌────────────────────────┐
                            │  Firebase Cloud        │
                            │  Messaging (FCM)       │
                            │  S3-compatible storage │
                            │  Worker IA (standby)   │
                            └────────────────────────┘
```

### Padrões arquiteturais

- **Modular por domínio**: cada app é independente e segue o mesmo padrão interno (`models / serializers / views / services / selectors / tasks / admin / urls`).
- **Views finas**: controllers só validam, autorizam e serializam. **Toda regra de negócio fica em `services.py`.**
- **Queries complexas** ficam isoladas em `selectors.py` — facilita testes e troca de ORM, se um dia for necessário.
- **Stateless** via JWT — backend não guarda sessão.
- **Async-first** para tarefas pesadas: notificações, e-mails, processamento de imagens IA — tudo via Celery.

---

## 4. Stack tecnológica

| Camada | Tecnologia | Versão | Justificativa |
|---|---|---|---|
| **Linguagem** | Python | 3.12 | Maturidade, ecossistema, integração nativa com IA |
| **Framework** | Django + DRF | 6.0 / 3.17 | ORM maduro, Django Admin gratuito, ecossistema integrado |
| **Banco** | PostgreSQL | 16 | Robustez, JSON, full-text search nativo, escalabilidade |
| **Cache / Filas** | Redis | 7 | Cache, throttling e broker do Celery |
| **Filas assíncronas** | Celery | 5.6 | Notificações, recálculos, processamento IA |
| **WebSocket** | Channels + Daphne | 4.3 | Chat em tempo real |
| **Auth** | SimpleJWT | 5.3 | Stateless, refresh token, padrão mobile |
| **Push** | Firebase Cloud Messaging | — | Padrão Android, integração gratuita com Flutter |
| **Storage de mídia** | S3-compatible (R2/Spaces/S3) | — | Imagens de perfil, fotos para IA |
| **Gerenciador de pacotes** | Poetry | 2.x | Lock determinístico, gestão de grupos |
| **Containers** | Docker + Compose | — | Ambiente reprodutível |
| **Observabilidade** | Sentry + logs estruturados | — | Monitoramento de erros |
| **Infra inicial** | Railway ou Render | — | Deploy rápido, custo baixo, suficiente para MVP |
| **Infra escala** | AWS ou GCP | — | Migração futura sem refatoração estrutural |
| **IA / ML** *(standby)* | TensorFlow, PyTorch, MediaPipe, OpenCV | — | Visão computacional para análise corporal |

### Dependências principais

| Pacote | Uso |
|---|---|
| `djangorestframework` | API REST |
| `djangorestframework-simplejwt` | JWT auth (access 15min + refresh 30 dias) |
| `django-cors-headers` | CORS para mobile e web |
| `drf-spectacular` | OpenAPI/Swagger automático |
| `django-filter` | Filtros declarativos em endpoints |
| `celery[redis]` | Filas assíncronas |
| `django-celery-beat` | Tasks agendadas (sync TACO/OFF, lembretes) |
| `channels` + `daphne` + `channels-redis` | WebSocket |
| `psycopg2-binary` | Driver PostgreSQL |
| `django-storages` + `boto3` | S3-compatible para mídias |
| `python-decouple` | Variáveis de ambiente via `.env` |
| `firebase-admin` | Push notifications via FCM |
| `pillow` | Manipulação de imagens |
| `factory-boy` + `pytest-django` | Testes |
| `sentry-sdk` | Observabilidade |

---

## 5. Estrutura do repositório

```
fittrack-backend/
├── config/                    # Projeto Django
│   ├── settings/
│   │   ├── base.py            # Configurações comuns
│   │   ├── dev.py             # Desenvolvimento
│   │   ├── prod.py            # Produção
│   │   └── test.py            # Testes
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── celery.py
│
├── apps/                      # Domínios de negócio
│   ├── users/                 # User, Profile, JWT auth
│   ├── body/                  # BodyMetric, cálculo TMB/macros
│   ├── workouts/              # Exercise, Workout, Session, SetLog
│   ├── diet/                  # Food, MealPlan, Meal, MealItem, MealLog
│   ├── professional/          # ProfessionalLink, Assignments, Verification
│   ├── chat/                  # ChatMessage, WebSocket consumer
│   ├── notifications/         # FCM, push, in-app
│   ├── core/                  # Base models, mixins, exceptions, permissions
│   └── shared/                # Pagination, throttles, middleware, utils
│
├── tests/                     # Testes de integração
├── manage.py
├── pyproject.toml             # Dependências (Poetry)
├── poetry.lock
├── Makefile                   # Atalhos de comandos
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

### Padrão interno por app

Cada app de domínio segue a mesma estrutura — previsibilidade é mais importante que originalidade:

```
apps/<dominio>/
├── models.py          # ORM
├── serializers.py     # DRF serializers
├── views.py           # ViewSets/APIViews finos
├── services.py        # Regras de negócio (NÃO em views)
├── selectors.py       # Queries complexas e agregações
├── tasks.py           # Celery tasks
├── admin.py           # Django Admin customizado
├── filters.py         # django-filter
├── permissions.py     # Permissões específicas do domínio
├── signals.py         # Signals do Django
├── urls.py
├── migrations/
└── tests/
    ├── factories.py
    ├── test_models.py
    ├── test_services.py
    └── test_views.py
```

---

## 6. Pré-requisitos

### Para rodar com Docker (recomendado)

- Docker 24+
- Docker Compose v2
- Make (opcional, mas facilita)

### Para rodar localmente sem Docker

- Python 3.12
- Poetry 2.x
- PostgreSQL 16
- Redis 7
- Make (opcional)

---

## 7. Setup e execução

### Opção A — Docker Compose (recomendado)

```bash
# 1. Clonar
git clone <repo-url> fittrack-backend
cd fittrack-backend

# 2. Configurar variáveis de ambiente
cp .env.example .env
# Edite .env com seus valores (ver seção 9)

# 3. Subir os containers
make docker-build
make docker-up

# 4. Aplicar migrations e criar superusuário
make docker-migrate
make docker-superuser

# 5. Acessar
# API:        http://localhost:8000/api/v1/
# Admin:      http://localhost:8000/admin/
# Logs:       make docker-logs
```

### Opção B — Local sem Docker

```bash
# 1. Clonar e instalar dependências
git clone <repo-url> fittrack-backend
cd fittrack-backend
make install                       # poetry install

# 2. Subir Postgres e Redis (você pode usar containers só pra eles)
docker compose up -d db redis

# 3. Configurar ambiente
cp .env.example .env
export DJANGO_SETTINGS_MODULE=config.settings.dev

# 4. Migrations + superuser
make migrate
make superuser

# 5. Subir o servidor (HTTP + WebSocket via Daphne)
make run                           # http://localhost:8000

# 6. Em outro terminal — Celery worker
poetry run celery -A config worker -l info

# 7. Em outro terminal — Celery beat (tarefas agendadas)
poetry run celery -A config beat -l info
```

---

## 8. Comandos do Makefile

### Local (Poetry)

| Comando | Descrição |
|---|---|
| `make install` | Instala dependências via Poetry |
| `make run` | Inicia o servidor de desenvolvimento |
| `make migrate` | Aplica as migrations |
| `make makemigrations` | Gera novas migrations |
| `make shell` | Abre o Django shell |
| `make test` | Executa os testes |
| `make superuser` | Cria um superusuário |
| `make clean` | Remove caches Python (`__pycache__`, `*.pyc`) |

### Docker

| Comando | Descrição |
|---|---|
| `make docker-build` | Builda as imagens |
| `make docker-up` | Sobe os containers em background |
| `make docker-down` | Derruba os containers |
| `make docker-logs` | Exibe logs do container `web` |
| `make docker-migrate` | Roda `migrate` dentro do container |
| `make docker-makemigrations` | Roda `makemigrations` dentro do container |
| `make docker-superuser` | Cria superusuário dentro do container |
| `make docker-shell` | Abre o Django shell dentro do container |

> **Override de settings**: por padrão os comandos locais usam `config.settings.dev`. Para usar outro, exporte: `DJANGO_SETTINGS=config.settings.prod make migrate`.

---

## 9. Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```ini
# Django
SECRET_KEY=<gerar-uma-chave-segura>
DEBUG=True
DJANGO_SETTINGS_MODULE=config.settings.dev
ALLOWED_HOSTS=localhost,127.0.0.1

# Banco
DB_NAME=fittrack
DB_USER=fittrack
DB_PASSWORD=<senha>
DB_HOST=db
DB_PORT=5432

# Redis / Celery
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_URL=redis://redis:6379/0

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Firebase (push)
FIREBASE_CREDENTIALS_PATH=/app/firebase-credentials.json

# Storage S3-compatible (produção)
AWS_S3_ENDPOINT_URL=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=

# Sentry
SENTRY_DSN=
```

> ⚠️ **Nunca** commite o arquivo `.env` real. Apenas o `.env.example` (sem valores) vai pro repositório.

---

## 10. Endpoints da API

Todos os endpoints REST estão em `/api/v1/` e autenticados via JWT (`Authorization: Bearer <access_token>`), exceto onde indicado.

### Autenticação (`/api/v1/auth/`)

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| `POST` | `/auth/register/` | Cadastro (Usuário/Personal/Nutricionista) | ❌ |
| `POST` | `/auth/login/` | Login — retorna `access` + `refresh` | ❌ |
| `POST` | `/auth/refresh/` | Renovar access token | ❌ |
| `POST` | `/auth/logout/` | Logout — invalida refresh token | ✅ |
| `POST` | `/auth/password-reset/` | Solicita e-mail de recuperação | ❌ |
| `POST` | `/auth/password-reset-confirm/` | Confirma nova senha com token | ❌ |

### Perfil (`/api/v1/me/`)

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/me/` | Dados do usuário autenticado |
| `PATCH` | `/me/` | Atualizar perfil |
| `DELETE` | `/me/` | Excluir conta (LGPD — anonimização) |
| `GET` / `POST` | `/me/body-metrics/` | Histórico e nova medição de bioimpedância |
| `GET` / `PATCH` / `DELETE` | `/me/body-metrics/{id}/` | Editar/excluir medição |
| `POST` | `/me/devices/` | Registrar dispositivo FCM |
| `DELETE` | `/me/devices/{device_id}/` | Desativar dispositivo |
| `GET` | `/me/notifications/` | Listar notificações in-app |
| `POST` | `/me/notifications/{id}/read/` | Marcar como lida |
| `POST` | `/me/notifications/read-all/` | Marcar todas como lidas |

### Treino (`/api/v1/`)

| Método | Rota | Descrição |
|---|---|---|
| `GET` / `POST` | `/workouts/` | Listar e criar treinos |
| `GET` / `PATCH` / `DELETE` | `/workouts/{id}/` | Detalhe, editar, excluir |
| `POST` | `/workouts/{id}/import-template/` | Importar template público |
| `POST` | `/workouts/{id}/start-session/` | Iniciar sessão de treino |
| `GET` | `/workout-sessions/` | Histórico de sessões |
| `GET` | `/workout-sessions/{id}/` | Detalhe da sessão |
| `PATCH` | `/workout-sessions/{id}/log-set/` | Registrar série concluída |
| `POST` | `/workout-sessions/{id}/finish/` | Finalizar sessão |
| `GET` | `/exercises/` | Base de exercícios |

### Dieta (`/api/v1/diet/`)

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/diet/foods/?q=&source=` | Busca unificada TACO + Open Food Facts |
| `GET` / `POST` | `/diet/meal-plans/` | Listar e criar planos alimentares |
| `GET` / `PATCH` / `DELETE` | `/diet/meal-plans/{id}/` | Detalhe, editar, excluir |
| `POST` | `/diet/meals/{id}/mark-done/` | Marcar refeição como concluída |
| `GET` | `/diet/meal-logs/` | Histórico de refeições |
| `GET` | `/diet/daily-summary/?date=YYYY-MM-DD` | Consumido vs meta do dia |

### Profissional (`/api/v1/professional/`)

| Método | Rota | Descrição |
|---|---|---|
| `GET` / `POST` | `/professional/invite/` | Listar/gerar códigos de convite |
| `POST` | `/professional/accept-invite/` | Aceitar convite via código |
| `GET` | `/professional/links/` | Listar vínculos ativos |
| `DELETE` | `/professional/links/{id}/` | Cancelar vínculo |
| `POST` | `/professional/links/{id}/assign-workout/` | Atribuir treino a aluno |
| `POST` | `/professional/links/{id}/assign-meal-plan/` | Atribuir plano alimentar |
| `GET` | `/professional/students/` | Lista de alunos vinculados |

### Chat (`/api/v1/chat/`)

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/chat/threads/` | Lista de conversas |
| `GET` / `POST` | `/chat/{link_id}/messages/` | Mensagens (REST + WebSocket) |
| `POST` | `/chat/{link_id}/mark-read/` | Marcar mensagens como lidas |

### Documentação automática

| Rota | Descrição |
|---|---|
| `/api/schema/` | Schema OpenAPI (YAML) |
| `/api/docs/` | Swagger UI |

---

## 11. WebSocket — Chat em tempo real

O chat profissional ↔ aluno usa **Django Channels + Daphne** com autenticação JWT no handshake.

**URL:** `ws://<host>/ws/chat/<link_id>/?token=<access_token>`

```python
# Cliente (exemplo Python)
import asyncio, websockets, json

async def chat():
    uri = "ws://localhost:8000/ws/chat/1/?token=<access>"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"content": "Olá!"}))
        print(await ws.recv())

asyncio.run(chat())
```

**Códigos de fechamento:**

| Código | Significado |
|---|---|
| `4401` | Token inválido ou ausente |
| `4403` | Usuário não pertence a este vínculo |

---

## 12. Tarefas Celery

Workers configurados em `config/celery.py` e `apps/*/tasks.py`.

| Task | Quando | Onde |
|---|---|---|
| `send_push_notification` | A cada notificação criada (`.delay()`) | `apps/notifications/tasks.py` |
| `mark_stale_sessions_as_draft` | A cada 1h (Celery Beat) — RN08 | `apps/notifications/tasks.py` |
| `recompute_macros` | Quando `Profile` muda objetivo/atividade | `apps/body/tasks.py` |
| `sync_taco_database` | Cron diário (Celery Beat) | `apps/diet/tasks.py` |
| `sync_open_food_facts` | Cron diário (Celery Beat) | `apps/diet/tasks.py` |
| `process_body_image` *(IA — standby)* | Sob demanda | Worker dedicado `ai_processing` |

**Subir os workers:**

```bash
# Worker padrão
poetry run celery -A config worker -l info

# Beat (tarefas agendadas)
poetry run celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Worker dedicado de IA (futuro)
poetry run celery -A config worker -Q ai_processing -l info
```

---

## 13. Atores do sistema

| Ator | Papel |
|---|---|
| **Usuário** | Cria/usa dieta e treino próprios, ou recebe planos de um profissional |
| **Personal Trainer** | Cria treinos e atribui a usuários vinculados |
| **Nutricionista** | Cria planos alimentares e atribui a usuários vinculados |
| **Admin** | Gestão da plataforma via Django Admin |

---

## 14. Requisitos funcionais (RF)

> Prioridades: **P0** = bloqueante MVP · **P1** = importante · **P2** = desejável · **P3** = futuro.

### RF01 — Autenticação e perfis

| ID | Descrição | Prioridade |
|---|---|---|
| RF01.1 | Cadastro de novo usuário com seleção de tipo: Usuário / Personal / Nutricionista | P0 |
| RF01.2 | Login com e-mail e senha | P0 |
| RF01.3 | Recuperação de senha via e-mail | P0 |
| RF01.4 | Edição do perfil (nome, foto, dados pessoais) | P0 |
| RF01.5 | Logout com invalidação do refresh token | P0 |
| RF01.6 | Selo de verificação para profissionais com CRN/CREF aprovado | P2 |
| RF01.7 | Exclusão da conta com remoção dos dados (LGPD) | P1 |

### RF02 — Dados físicos e bioimpedância

| ID | Descrição | Prioridade |
|---|---|---|
| RF02.1 | Cadastrar dados básicos: peso, altura, idade, sexo biológico, objetivo, nível de atividade | P0 |
| RF02.2 | Registrar manualmente medições de bioimpedância (% gordura, massa magra, água, TMB, etc.) | P0 |
| RF02.3 | Cada medição salva com data e hora, formando histórico | P0 |
| RF02.4 | Gráficos de evolução das medidas ao longo do tempo | P1 |
| RF02.5 | Editar ou excluir uma medição registrada | P1 |
| RF02.6 | Cálculo automático de metas calóricas e macros baseado nos dados físicos e objetivo | P0 |

### RF03 — Módulo de treino

**Criação:**

| ID | Descrição | Prioridade |
|---|---|---|
| RF03.1 | Criar treinos com nome, divisão (A/B/C…) e objetivo | P0 |
| RF03.2 | Adicionar exercícios com nome, grupos musculares, séries, reps, carga e descanso | P0 |
| RF03.3 | Reordenar exercícios via drag & drop | P0 |
| RF03.4 | Importar templates pré-cadastrados (viram cópia editável) | P1 |

**Execução:**

| ID | Descrição | Prioridade |
|---|---|---|
| RF03.5 | Iniciar sessão de treino com visualização exercício a exercício | P0 |
| RF03.6 | Marcar série como concluída + informar reps realizadas | P0 |
| RF03.7 | Timer de descanso configurável entre séries | P0 |
| RF03.8 | Reordenar exercícios durante a execução | P1 |
| RF03.9 | Comentário por sessão (visível ao personal vinculado) | P1 |
| RF03.10 | Sessão salva automaticamente ao concluir | P0 |
| RF03.11 | Modo offline com sincronização posterior | P1 |

### RF04 — Módulo de dieta

**Base de alimentos:**

| ID | Descrição | Prioridade |
|---|---|---|
| RF04.1 | Integrar a base TACO | P0 |
| RF04.2 | Integrar a base Open Food Facts | P0 |
| RF04.3 | Busca unificada nas duas bases | P0 |
| RF04.4 | Nutricionista cadastra alimentos customizados visíveis aos pacientes | P1 |

**Plano alimentar:**

| ID | Descrição | Prioridade |
|---|---|---|
| RF04.5 | Criar plano alimentar com refeições do dia (nomeação livre) | P0 |
| RF04.6 | Adicionar alimentos com quantidade em gramas/ml/unidades | P0 |
| RF04.7 | Cálculo automático de calorias e macros (P/C/G) por refeição e total do dia | P0 |
| RF04.8 | Exibir progresso diário: consumido vs meta | P0 |
| RF04.9 | Marcar refeições como concluídas | P0 |
| RF04.10 | Adicionar comentário por refeição | P0 |
| RF04.11 | Duplicar plano de um dia para outro | P1 |

### RF05 — Relacionamento profissional ↔ usuário

| ID | Descrição | Prioridade |
|---|---|---|
| RF05.1 | Profissional envia convite de vínculo via código ou e-mail | P1 |
| RF05.2 | Usuário aceita ou recusa convite | P1 |
| RF05.3 | Profissional visualiza lista de seus alunos | P1 |
| RF05.4 | Profissional atribui treinos/dietas a alunos específicos | P1 |
| RF05.5 | Profissional visualiza status de execução do aluno | P1 |
| RF05.6 | Aluno não edita plano atribuído (somente leitura, exceto reps/cargas em execução) | P1 |
| RF05.7 | Chat interno entre profissional e aluno vinculado | P2 |
| RF05.8 | Usuário pode desfazer vínculo a qualquer momento | P1 |

### RF06 — Dashboard do usuário

| ID | Descrição | Prioridade |
|---|---|---|
| RF06.1 | Resumo diário: treino do dia, refeições planejadas, calorias vs meta | P0 |
| RF06.2 | Acesso rápido para "Iniciar Treino" do dia | P0 |
| RF06.3 | Acesso rápido para "Marcar Refeição" atual | P0 |
| RF06.4 | Gráficos de evolução corporal (peso, gordura, massa magra) | P1 |
| RF06.5 | Resumo semanal: treinos concluídos, aderência à dieta | P1 |

### RF07 — Notificações

| ID | Descrição | Prioridade |
|---|---|---|
| RF07.1 | Push em horário de refeição planejada | P2 |
| RF07.2 | Push em horário de treino programado | P2 |
| RF07.3 | Profissional recebe push quando aluno envia mensagem | P2 |
| RF07.4 | Aluno recebe push quando profissional atribui novo plano | P2 |

### RF08 — Backoffice / Admin

| ID | Descrição | Prioridade |
|---|---|---|
| RF08.1 | Gerenciar usuários via Django Admin | P0 |
| RF08.2 | Gerenciar base de exercícios | P0 |
| RF08.3 | Gerenciar alimentos customizados | P0 |
| RF08.4 | Aprovar manualmente verificação de CRN/CREF | P2 |
| RF08.5 | Painel React/Next.js para métricas avançadas | P3 |

### RF09 — Monetização (futuro)

| ID | Descrição | Prioridade |
|---|---|---|
| RF09.1 | Modelo freemium para usuários comuns | P3 |
| RF09.2 | Profissional assina plano mensal/anual | P3 |
| RF09.3 | Alunos vinculados a profissional assinante recebem acesso premium | P3 |
| RF09.4 | Venda avulsa de templates premium | P3 |

---

## 15. Requisitos não-funcionais (RNF)

### RNF01 — Performance

- Telas principais carregam em até **2s** em 4G estável.
- API: **95% das requisições em até 300ms**.
- **Modo offline obrigatório** para execução de treino, com sync posterior.
- Cálculo de macros e calorias instantâneo (client-side ou cache).

### RNF02 — Segurança

- Conformidade total com **LGPD**: consentimento explícito, direito ao esquecimento, exportação de dados.
- Senhas com hash **bcrypt (custo mínimo 12)**.
- JWT com refresh token; access expira em **15 minutos**, refresh em **30 dias** (com rotação).
- Comunicação exclusivamente via **HTTPS (TLS 1.2+)**.
- **Rate limiting** em endpoints sensíveis (login, cadastro, recuperação).
- Dados de bioimpedância e fotos classificados como **sensíveis** e criptografados em repouso.
- **Logs de auditoria** para ações administrativas no Django Admin.

### RNF03 — Usabilidade

- Interface mobile-first com gestos nativos Android (swipe, drag, long-press).
- Acessibilidade: **contraste WCAG AA**, suporte a tamanho de fonte do sistema, leitura por TalkBack.
- Curva de aprendizado: usuário novo registra primeiro treino em **até 3 minutos**.
- Telas críticas (execução de treino) **usáveis com uma só mão**.

### RNF04 — Compatibilidade

- **Android 8.0 (API 26)** ou superior.
- Smartphones em **modo retrato** (paisagem opcional).
- Resolução mínima **360x640**.
- iOS fora do escopo do MVP, mas Flutter mantém portabilidade futura.

### RNF05 — Escalabilidade

- Arquitetura preparada para **multi-tenant** (isolamento de dados por usuário).
- Tarefas pesadas executadas em **fila Celery**.
- **Cache Redis** para queries frequentes (alimentos, exercícios).
- PostgreSQL com **índices em campos de filtro frequente**.
- Migração para AWS/GCP **sem refatoração estrutural**.

### RNF06 — Disponibilidade

- MVP: **99% uptime** (aceitável para uso pessoal e early adopters).
- Produção em escala: **99.5% uptime** com Sentry + UptimeRobot.
- App **nunca pode travar em academia** — modo offline obrigatório.

---

## 16. Regras de negócio (RN)

| ID | Regra |
|---|---|
| **RN01** | Cálculo de TMB usa **Mifflin-St Jeor** por padrão. Se o usuário informar TMB pela bioimpedância, esse valor prevalece. |
| **RN02** | Distribuição padrão de macros por objetivo: emagrecimento (40C/40P/20G), hipertrofia (45C/30P/25G), manutenção e saúde geral (50C/25P/25G). Ajustável pelo nutricionista. |
| **RN03** | Necessidade calórica = TMB × fator de atividade (sedentário 1.2 → muito intenso 1.9), ajustada por ±500 kcal conforme objetivo. |
| **RN04** | Usuário vinculado a profissional **NÃO** pode editar plano atribuído. Pode apenas registrar execução. |
| **RN05** | Usuário pode estar vinculado a no máximo **1 personal + 1 nutricionista** simultaneamente. |
| **RN06** | Profissional não tem limite de alunos vinculados (limites comerciais por plano de assinatura — regra futura). |
| **RN07** | Selo CRN/CREF é concedido apenas após validação manual pelo Admin. Validação automática via API regional é P3. |
| **RN08** | Sessão de treino iniciada e não concluída fica como **'rascunho' por 24h**. Após isso, é descartada ou consolidada. |
| **RN09** | Plano alimentar criado por nutricionista é **somente leitura** para o aluno. Aluno apenas marca refeição e comenta. |
| **RN10** | Treino criado por personal é somente leitura na estrutura, mas o aluno **pode ajustar reps e carga em execução**. |
| **RN11** | Templates públicos podem ser importados e modificados livremente — viram **cópia independente** após importação. |
| **RN12** | Exclusão de conta remove dados pessoais (LGPD), mas mantém **dados agregados anonimizados** (estatísticas). |
| **RN13** | Profissional que perde a assinatura mantém acesso no plano gratuito mas **perde a capacidade de atribuir novos planos**. Alunos perdem premium 30 dias após cancelamento. |
| **RN14** | Bioimpedância exige no mínimo **peso + % gordura corporal**. Demais campos são opcionais. |

---

## 17. Modelo de dados

### Decisões de banco

- **User customizado** herdando `AbstractUser` com campo `account_type` (USER / PERSONAL / NUTRITIONIST).
- **Soft delete** em entidades sensíveis: campos `is_active` e `deleted_at`.
- **Índices compostos** `(user_id, created_at)` em todas as tabelas de log e histórico.
- **JSON fields** para dados flexíveis (ex: `Food.nutritional_data`).
- `BodyMetric` e `WorkoutSession` particionáveis por data ao escalar.

### Diagrama de entidades (alto nível)

```
User ─┬─ Profile (1:1)
      ├─ BodyMetric (1:N)
      ├─ Workout (1:N) ─── WorkoutExercise (1:N) ── Exercise (N:1)
      │                       │
      │                       └── SetLog (1:N) ── WorkoutSession (N:1)
      │
      ├─ MealPlan (1:N) ─── Meal (1:N) ── MealItem (1:N) ── Food (N:1)
      │                       │
      │                       └── MealLog (1:N)
      │
      ├─ ProfessionalLink (N:N via student/professional)
      │       │
      │       ├── WorkoutAssignment ── Workout
      │       └── MealPlanAssignment ── MealPlan
      │
      ├─ ChatMessage (via ProfessionalLink)
      ├─ FCMDevice (1:N)
      ├─ Notification (1:N)
      └─ InviteCode (1:N — apenas profissionais)
```

---

## 18. Fora do escopo do MVP

- ❌ **iOS** — Flutter mantém portabilidade, mas publicação não é prioridade.
- ❌ **Pagamentos in-app** — monetização vem depois do MVP funcional.
- ❌ **IA para geração de dieta/treino** — só análise corporal, e ainda em standby.
- ❌ **Validação automática de CRN/CREF via API** — manual no MVP, automática é P3.

### Módulo de IA — standby absoluto

Em desenvolvimento paralelo por Pedro (Engenheiro de IA/ML). Será integrado ao backend via Celery (worker `ai_processing`) quando estiver pronto. **Não há data definida e não impacta o roadmap do app principal.**

---

## 19. Roadmap de execução

> Sem prazos rígidos. Cada bloco só começa quando o anterior estiver funcional o suficiente. Ordem definida por **dependência técnica e valor entregue**.

### Bloco 1 — Fundação (P0)

- [x] Arquitetura backend e mobile definida
- [x] Configuração de ambiente e repositório
- [x] Identidade visual e design system inicial
- [ ] Autenticação completa (cadastro, login, recuperação, logout)
- [ ] Perfil de usuário + dados físicos + bioimpedância

### Bloco 2 — Core (P0)

- [ ] Módulo de treino completo (criação, execução, histórico)
- [ ] Base de exercícios pré-cadastrada
- [ ] Módulo de dieta completo (TACO + Open Food Facts, plano, marcação)
- [ ] Cálculo automático de calorias e macros

### Bloco 3 — Dashboard (P0/P1)

- [ ] Dashboard com resumo diário
- [ ] Gráficos de evolução corporal
- [ ] Histórico detalhado de sessões e refeições

### Bloco 4 — Multi-usuário (P1/P2)

- [ ] Vínculo profissional ↔ aluno
- [ ] Atribuição de planos pelo profissional
- [ ] Página de gerenciamento de alunos
- [ ] Chat interno
- [ ] Notificações push

### Bloco 5 — Templates e backoffice (P2)

- [ ] Sistema de templates importáveis
- [ ] Customizações do Django Admin
- [ ] Painel React/Next.js para métricas

### Bloco 6 — Mercado (P3)

- [ ] Monetização (freemium + assinatura)
- [ ] Marketplace de templates premium
- [ ] Validação automática CRN/CREF
- [ ] Publicação na Google Play Store + ASO

### Bloco 7 — IA (paralelo, sem dependência)

- [ ] Coleta e tratamento de dataset
- [ ] Treinamento do modelo de visão computacional
- [ ] Pipeline de processamento via Celery
- [ ] Integração com app

### Status atual

| Fase | Status | O que está pronto |
|---|---|---|
| 1 — Descoberta | ✅ Concluída | Problema definido, público-alvo claro, benchmarking |
| 2 — Planejamento | ✅ Concluída | Escopo, requisitos, arquitetura, stack, roadmap |
| 3 — Design | ✅ Concluída | Design system, identidade visual, 30 telas mobile + 5 web |
| **4 — Desenvolvimento** | 🔄 **Em andamento** | **Backend (Bloco 1) implementado** |
| 5 — Testes | ⏳ Pendente | — |
| 6 — Lançamento | ⏳ Pendente | — |
| 7 — Crescimento | ⏳ Pendente | — |

---

## 20. Critérios de aceitação do MVP

O MVP é considerado concluído quando:

- [ ] Usuário consegue se cadastrar, logar e editar perfil.
- [ ] Usuário consegue registrar bioimpedância e ver histórico.
- [ ] Usuário consegue criar treino e executar com timer de descanso.
- [ ] Usuário consegue criar plano alimentar e marcar refeições.
- [ ] Sistema calcula automaticamente metas calóricas e macros.
- [ ] Profissional consegue se vincular a aluno e atribuir planos.
- [ ] Chat funciona entre profissional e aluno.
- [ ] Notificações push chegam em horários configurados.
- [ ] App publicado na Google Play Store em fase fechada (early access).
- [ ] Todos os RFs P0 implementados e testados.

---

## 21. Glossário

| Termo | Definição |
|---|---|
| **ASO** | App Store Optimization — técnicas para melhorar posicionamento de apps em lojas. |
| **Bioimpedância** | Técnica de medição da composição corporal usando corrente elétrica de baixa intensidade. |
| **Celery** | Sistema de filas distribuídas para Python — executa tarefas em background. |
| **CREF** | Conselho Regional de Educação Física — registro obrigatório para personal trainers. |
| **CRN** | Conselho Regional de Nutricionistas — registro obrigatório para nutricionistas. |
| **DRF** | Django REST Framework — extensão do Django para construção de APIs REST. |
| **FCM** | Firebase Cloud Messaging — serviço Google para notificações push. |
| **Freemium** | Modelo de negócio com camada gratuita e camada paga (premium). |
| **JWT** | JSON Web Token — padrão para autenticação stateless via tokens assinados. |
| **LGPD** | Lei Geral de Proteção de Dados (Brasil, Lei 13.709/2018). |
| **Macros** | Macronutrientes — Proteínas, Carboidratos e Gorduras. |
| **MediaPipe** | Framework Google para visão computacional, incluindo detecção de poses corporais. |
| **Mifflin-St Jeor** | Fórmula padrão para cálculo de Taxa Metabólica Basal. |
| **MVP** | Minimum Viable Product — versão mínima funcional do produto. |
| **Open Food Facts** | Base de dados global, colaborativa e aberta de informações nutricionais. |
| **Riverpod** | Padrão de gerenciamento de estado para Flutter, evolução do Provider. |
| **TACO** | Tabela Brasileira de Composição de Alimentos — referência oficial brasileira. |
| **TMB** | Taxa Metabólica Basal — quantidade de energia que o corpo gasta em repouso. |

---

<p align="center">
  <strong>FitTrack — Treino, dieta e evolução corporal num só lugar.</strong><br>
  <sub>Documento mantido por Lucas (Analista de Sistemas). Última atualização: 01/05/2026.</sub>
</p>
