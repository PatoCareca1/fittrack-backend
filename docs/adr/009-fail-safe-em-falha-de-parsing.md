# ADR-009 — Fail-safe em toda falha de parsing de LLM

## Contexto

Toda resposta de LLM que o sistema espera em JSON pode chegar malformada:
markdown ao redor do JSON, campo ausente, valor fora do conjunto esperado,
ou texto solto sem nenhum JSON. Isso acontece mesmo com prompts bem
escritos — é uma característica do canal (texto livre), não um bug do
prompt. A pergunta de design é: quando o parsing falha, o sistema deve
tender a aprovar (permissivo) ou a rejeitar (conservador)?

## Decisão

Toda falha de parsing de uma resposta de LLM cai para o estado **mais
conservador**, nunca para o mais permissivo:

- `apps.coach.schemas.parse_diet_output` levanta `ValueError` com mensagem
  clara em qualquer forma inesperada; isso vira mais uma rodada do loop de
  retry do gerador (`generate_meal_plan`), nunca uma aprovação silenciosa.
- `apps.coach.agents.critic._parse_critic_output`: se a resposta do crítico
  não puder ser interpretada, o resultado vira uma única `issue` sintética
  com `severity: "blocker"` (`"Resposta do crítico não pôde ser
  interpretada: ..."`) — o plano é reprovado por causa da falha de parsing,
  nunca aprovado por causa dela.
- `apps.coach.agents.manager._parse_intent`: se o campo `intent` da
  resposta do LLM não existir ou não for um dos quatro valores válidos do
  Enum `Intent`, o resultado cai em `AMBIGUOUS` — nunca é inventada uma
  intenção, e `AMBIGUOUS` é o estado que leva o aluno a esclarecer o pedido
  (o caminho mais seguro), não a um agente sendo acionado por engano.

Em todos os três casos, a falha fica registrada (`AgentRun.validation_errors`
ou a mensagem de retry) — o sistema nunca finge que não aconteceu.

## Alternativas consideradas

- **Em caso de dúvida, tentar extrair o melhor JSON possível e seguir em
  frente** (parsing tolerante, "assume o que fizer mais sentido").
  Rejeitada: isso trocaria uma falha visível e recuperável (retry, ou
  pedido de esclarecimento) por um comportamento imprevisível — o sistema
  agindo sobre uma interpretação adivinhada de uma resposta malformada, num
  domínio de dados de saúde.
- **Deixar a exceção de parsing propagar como erro 500.** Rejeitada onde
  existe um mecanismo de retry natural (gerador, crítico): a falha de
  parsing é tratada como só mais um motivo de correção, reaproveitando o
  loop que já existe, em vez de derrubar o pipeline inteiro por uma
  resposta malformada pontual.

## Consequências

**Positivas**: o sistema nunca "inventa" um resultado a partir de uma
resposta que não conseguiu interpretar — falha de parsing sempre se traduz
em "tentar de novo" ou "recusar", nunca em "seguir como se estivesse tudo
certo". Isso é consistente com o restante da arquitetura (ADR-001, ADR-002,
ADR-003): código decide, LLM propõe.

**Negativas**: uma taxa de resposta malformada mais alta do que o esperado
consome mais iterações do loop de retry (`COACH_MAX_ITERATIONS`,
`COACH_MAX_CRITIC_ROUNDS`) ou aumenta a frequência de `AMBIGUOUS` no
roteamento — na prática, mais latência e mais chamadas de LLM (custo) do
que uma abordagem tolerante teria, em troca de nunca agir sobre uma
interpretação inventada.
