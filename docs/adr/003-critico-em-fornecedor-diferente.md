# ADR-003 — Crítico em fornecedor diferente do gerador

## Contexto

Depois que `validate_meal_plan` aprova a aritmética de um plano (ADR-002),
o Agente Crítico (`apps/coach/agents/critic.py`) avalia o que código não
consegue: variedade, porções realistas, distribuição das refeições ao
longo do dia, adequação ao objetivo do aluno, dependência excessiva de
suplemento. Se o crítico rodasse no mesmo modelo/fornecedor que gerou o
plano, haveria um viés estrutural: um modelo tende a ser complacente com o
próprio output — é o mesmo "estilo de raciocínio" avaliando a si mesmo.

## Decisão

O Agente de Dieta roda em `COACH_GENERATOR_PROVIDER` (padrão `anthropic`)
e o Agente Crítico roda em `COACH_CRITIC_PROVIDER` (padrão `gemini`) — dois
fornecedores diferentes por padrão, deliberadamente. A razão é diversidade
de erro: dois modelos de famílias diferentes têm menos chance de
compartilhar o mesmo ponto cego. Além disso, **a decisão final de
aprovação nunca é o campo `"approved"` que o LLM crítico devolve** — é
Python cruzando as `issues` retornadas: se existir qualquer issue com
`severity: "blocker"`, o plano é reprovado, ponto. Se o campo `"approved"`
do LLM divergir dessa decisão (ex.: o modelo diz `true` mas listou um
blocker), a divergência é registrada em `AgentRun.validation_errors` e a
decisão determinística prevalece — nunca se confia isoladamente na
autoavaliação do modelo.

## Alternativas consideradas

- **Mesmo fornecedor para gerador e crítico**, mudando só o prompt/papel.
  Rejeitada pela razão de diversidade de erro acima — o ganho de qualidade
  de crítica independente supera a simplicidade operacional de um único
  fornecedor.
- **Confiar no campo `"approved"` do LLM crítico diretamente.** Rejeitada:
  isso delegaria a decisão de negócio (aprovar ou não um plano de saúde) a
  uma única saída de texto de um LLM, sem nenhuma camada de verificação —
  o mesmo problema que ADR-001/002 evitam para os números, evitado aqui
  para a decisão binária de aprovação.

## Consequências

**Positivas**: reduz a chance de um plano ruim ser aprovado só porque o
mesmo modelo que o gerou também o revisou. A divergência entre o que o LLM
"achou" e o que as issues realmente implicam fica registrada e auditável
via `AgentRun`.

**Negativas (custo real assumido)**: dependência de **dois** fornecedores
de LLM em vez de um — duas chaves de API (`ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`), dois pontos de falha externos, dois SLAs diferentes para
monitorar. Se um dos dois fornecedores cair, o pipeline completo
(`generate_and_review_meal_plan`) para, mesmo que o outro esteja saudável.
Também dobra o número de chamadas de rede por plano gerado (gerador +
crítico), com custo e latência maiores que uma solução de um único
fornecedor.
