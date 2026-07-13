# Arquitetura — FitTrack Coach (`apps/coach`)

Leitura de 3 minutos. Para o *porquê* de cada decisão, ver
[`docs/adr/`](adr/README.md).

## Em uma frase

O Coach é um sistema multiagente onde **código decide, LLM propõe**: um
gerente determinístico roteia, um agente de dieta propõe usando ferramentas
sobre o catálogo real de alimentos, uma validação Python confere a
aritmética, um segundo LLM (fornecedor diferente) audita qualidade, e só
então o plano é persistido — tudo executado em segundo plano e consultável
por polling. Um servidor MCP separado expõe os mesmos dados e ferramentas
determinísticas a um host externo (Claude Desktop do profissional), sem
nenhum LLM do lado do FitTrack.

## Fluxo 1 — mensagem do aluno até o plano persistido

```mermaid
sequenceDiagram
    actor Aluno
    participant API as POST /coach/messages/
    participant Gerente as manager.route()
    participant Job as CoachJob (runner)
    participant Dieta as agents.diet<br/>(generate_meal_plan)
    participant Valid as validators.<br/>validate_meal_plan
    participant Critico as agents.critic<br/>(review_meal_plan)
    participant DB as Postgres

    Aluno->>API: "monta minha dieta pra hoje"
    API->>Gerente: route(mensagem)
    Note over Gerente: 1) palavra-chave (sem LLM)<br/>2) LLM só se ambíguo (ADR-005)
    Gerente-->>API: Intent.DIET_PLAN

    API->>Job: enqueue_plan_job() [thread daemon, ADR-008]
    API-->>Aluno: 202 Accepted {job_id}

    rect rgba(120,120,200,0.08)
    Note over Job,Critico: executado em background
    Job->>Dieta: generate_meal_plan(user)
    loop até COACH_MAX_ITERATIONS
        Dieta->>Dieta: chama LLM gerador + tool buscar_alimento
        Dieta->>Valid: validate_meal_plan(proposta, BodyMetric)
        alt aritmética reprovada
            Valid-->>Dieta: erros acionáveis
            Dieta->>Dieta: reenvia erros ao LLM, tenta de novo
        else aprovado
            Valid-->>Dieta: sem erros
        end
    end
    Dieta-->>Job: DietAgentResult(approved, totals)

    alt aprovado na aritmética
        Job->>Critico: review_meal_plan(proposta, totals)
        Note over Critico: outro fornecedor (ADR-003)<br/>não recalcula macro
        loop até COACH_MAX_CRITIC_ROUNDS
            Critico-->>Job: issues [blocker?]
            alt tem blocker
                Job->>Dieta: regenera com feedback do crítico
            else sem blocker
                Note over Job: aprovado
            end
        end
    else reprovado na aritmética
        Note over Job: crítico NUNCA é chamado (ADR-002)
    end

    alt plano final aprovado
        Job->>DB: create_meal_plan_from_agent()<br/>(MealPlan/Meal/MealItem)
        Job->>DB: CoachJob.status = succeeded (com meal_plan_id)
    else reprovado (aritmética ou crítico esgotado)
        Job->>DB: CoachJob.status = succeeded (sem plano, com errors/issues)
        Note over DB: nunca persiste plano reprovado
    end
    end

    Aluno->>API: GET /coach/jobs/{id}/ (polling)
    API-->>Aluno: status + plano (se houver) + critic_summary
```

Toda chamada de LLM (gerente, dieta, crítico) grava um `AgentRun` —
provider, model, iterations, tokens, latência, `approved`,
`validation_errors`. É o log estruturado que torna o sistema depurável.

## Fluxo 2 — servidor MCP (host externo)

```mermaid
sequenceDiagram
    actor Prof as Nutricionista/Personal<br/>(Claude Desktop)
    participant MCP as POST /mcp/<br/>(JSON-RPC 2.0)
    participant Auth as mcp.auth<br/>(JWT SimpleJWT)
    participant Perm as mcp.permissions<br/>(RN05)
    participant Tools as mcp.tools
    participant Valid as validators.<br/>validate_meal_plan
    participant DB as Postgres

    Prof->>MCP: tools/call listar_alunos<br/>Authorization: Bearer <jwt>
    MCP->>Auth: resolve_user(request)
    Auth-->>MCP: User (ou erro -32001)
    MCP->>Tools: listar_alunos(user)
    Tools->>DB: ProfessionalLink ATIVOS do profissional
    DB-->>Prof: alunos vinculados

    Prof->>MCP: tools/call obter_metricas(student_id)
    MCP->>Perm: get_active_link_or_error(prof, student_id)
    alt sem vínculo ativo
        Perm-->>Prof: erro -32002 (nunca dado vazio silencioso)
    else vínculo ativo
        Perm-->>Tools: ok
        Tools-->>Prof: histórico de BodyMetric + alvos
    end

    Prof->>MCP: tools/call criar_plano_alimentar(student_id, meals)
    MCP->>Perm: vínculo ativo? profissional é nutricionista?
    Perm-->>Tools: ok
    Tools->>Valid: validate_meal_plan(meals, BodyMetric)
    Note over Valid: MESMA validação do agente interno<br/>(não duplicada, ADR-006)
    alt fora dos alvos
        Valid-->>Prof: erros acionáveis, nada persiste
    else dentro dos alvos
        Tools->>DB: MealPlan + DietAssignment
        DB-->>Prof: meal_plan_id
    end
```

Nenhuma seta neste diagrama passa por `apps/coach/providers` ou
`apps/coach/agents` — o servidor MCP não chama LLM nenhum (ADR-006). Quem
raciocina sobre os dados é o modelo do lado do host (Claude Desktop); o
FitTrack só fornece dados e ferramentas determinísticas, com a mesma
checagem de vínculo (RN05) em toda ferramenta que toca um aluno.

## Onde cada peça mora

| Peça | Módulo |
|---|---|
| Roteamento determinístico + LLM de desambiguação | `apps/coach/agents/manager.py` |
| Geração de plano + loop de retry | `apps/coach/agents/diet.py` |
| Revisão de qualidade (fornecedor diferente) | `apps/coach/agents/critic.py` |
| Validação determinística (aritmética) | `apps/coach/validators.py` |
| Ferramentas do LLM gerador (`buscar_alimento`) | `apps/coach/tools.py` |
| Abstração de fornecedor (httpx puro) | `apps/coach/providers/` |
| Execução assíncrona (thread, dívida assumida) | `apps/coach/runner.py` |
| Endpoints REST (mensagens, jobs, histórico) | `apps/coach/views.py`, `urls.py` |
| Servidor MCP (host externo) | `apps/coach/mcp/` |
| Auditoria de cada chamada de LLM | `apps/coach/models.py` (`AgentRun`) |
