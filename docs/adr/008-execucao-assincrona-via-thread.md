# ADR-008 — Execução assíncrona via thread (dívida técnica assumida)

## Contexto

Gerar um plano alimentar (`generate_and_review_meal_plan`) envolve várias
chamadas de rede a LLMs (gerador, possivelmente múltiplas iterações de
retry, mais o crítico) — não é algo que um request HTTP deva esperar
sincronamente. `POST /api/v1/coach/messages/` precisa responder rápido
(`202 Accepted` com um `job_id`) e o trabalho pesado precisa acontecer em
segundo plano.

## Decisão

`apps/coach/runner.py` dispara o trabalho numa `threading.Thread` daemon
(`enqueue_plan_job` → `_run_plan_job_in_thread` → `run_plan_job`). **Isto
é dívida técnica assumida conscientemente, não a escolha certa para
produção** — foi decisão de prazo, documentada como tal no topo do próprio
`runner.py`. A fronteira fica isolada de propósito: todo o resto do app
(views, services) só conhece `enqueue_plan_job()`; trocar a implementação
por uma fila de verdade (Celery + Redis/RabbitMQ) é mexer **só** nessa
função — nenhuma outra parte do código depende de como o job é executado.

## Alternativas consideradas

- **Configurar Celery + Redis desde já.** Rejeitada por prazo: subir um
  broker de fila (infraestrutura nova, mais um serviço no
  `docker-compose.yml`, configuração de worker) é um investimento maior do
  que o tempo disponível permitia nesta etapa. `redis` já existe no
  `docker-compose.yml` do projeto (para outro uso futuro), mas nenhum
  worker Celery está configurado.
- **Executar o job de forma síncrona no request** (sem thread nem fila),
  aceitando que `POST /messages/` demore o tempo total do pipeline de IA.
  Rejeitada: um request HTTP de dezenas de segundos (múltiplas chamadas de
  LLM em sequência) é uma experiência ruim e arrisca timeout de proxy/load
  balancer; o padrão job assíncrono com polling (`GET /jobs/{id}/`) já
  fazia sentido independente da implementação escolhida para executá-lo.

## Consequências (riscos explícitos)

**Sem retry**: se a thread lançar uma exceção não tratada em algum ponto
fora do `try/except` de `run_plan_job`, ou se o processo for encerrado no
meio da execução, não existe reprocessamento automático — o job fica
`"running"` para sempre (órfão) ou nunca é criado.

**Sem persistência de fila**: os jobs pendentes/em execução existem só
como threads vivas na memória do processo atual. Não há fila durável — se
o processo morrer, todo trabalho em andamento é perdido sem rastro além do
registro `CoachJob` (que ficará preso em `"running"`).

**Morre se o processo cair**: um restart do servidor (deploy, crash,
`runserver` reiniciado) mata todas as threads em voo. Diferente de uma
fila real, não há nada para retomar o trabalho depois que o processo volta.

**Não escala horizontalmente**: cada worker de aplicação processa os jobs
que ele mesmo recebeu — não há distribuição de carga entre múltiplas
instâncias do servidor. Rodar duas réplicas do backend não dobra a
capacidade de processar jobs, só duplica o ponto de origem.

**Ação futura**: migrar para Celery + Redis é o próximo passo natural antes
de qualquer uso em produção real — ver `progress.md`.
