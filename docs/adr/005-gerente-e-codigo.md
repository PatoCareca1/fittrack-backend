# ADR-005 — Gerente é código, não LLM

## Contexto

Toda mensagem do aluno para o Coach precisa ser roteada para uma intenção
(`Intent`: `DIET_PLAN`, `WORKOUT_PLAN`, `OUT_OF_SCOPE`, `AMBIGUOUS`) antes
de qualquer agente especializado agir. A tentação óbvia é usar um LLM para
classificar essa intenção — é exatamente o tipo de tarefa que "parece"
pedir compreensão de linguagem natural.

## Decisão

`apps.coach.agents.manager.route(message)` resolve a intenção em duas
etapas, nessa ordem: **(1) regras determinísticas** — normaliza a mensagem
(minúsculas, sem acento) e casa contra listas fixas de palavras-chave
(`DIET_KEYWORDS`: "dieta", "plano alimentar", "refeição", "comer", "macro",
etc.; `WORKOUT_KEYWORDS`: "treino", "exercício", "série", "ficha", etc.).
Só quando **nenhuma regra bate**, a etapa 2 chama o LLM
(`COACH_GENERATOR_PROVIDER`) para desambiguar, pedindo JSON estrito
`{"intent": ..., "reason": ...}` restrito ao Enum — qualquer valor fora do
Enum vira `AMBIGUOUS` (ver ADR-009). Um `AgentRun(agent="manager")` só é
gravado quando o LLM é de fato chamado — a etapa determinística não deixa
rastro de LLM porque não usou LLM nenhum.

## Alternativas consideradas

- **LLM classifica toda mensagem, sempre.** Rejeitada: a maioria das
  mensagens de um aluno de academia/nutrição contém palavras-chave óbvias
  ("quero um treino", "monta minha dieta") — chamar um LLM para resolver o
  que um `if` resolve adiciona custo e latência (uma chamada de rede a mais
  por mensagem) e um ponto de alucinação (o LLM pode classificar errado uma
  mensagem que uma regra simples classificaria certo) sem nenhum ganho de
  qualidade nesses casos óbvios.
- **Regras determinísticas cobrindo tudo, sem fallback de LLM.** Rejeitada:
  palavras-chave fixas não cobrem frases genuinamente ambíguas ou
  fora de escopo ("posso ficar bravo com meu personal?", "qual o preço do
  plano premium?") — para esses casos, um LLM classifica melhor do que uma
  lista de keywords que cresceria sem fim tentando prever toda variação de
  linguagem.

## Consequências

**Positivas**: a maioria das mensagens (as óbvias) não gasta nenhuma
chamada de LLM nem sofre a latência de rede associada; o comportamento
para essas mensagens é 100% determinístico e testável sem mock de rede. O
LLM só entra onde ele de fato agrega — desambiguação genuína.

**Negativas**: a lista de palavras-chave é mantida manualmente
(`DIET_KEYWORDS`/`WORKOUT_KEYWORDS` em `manager.py`) — uma gíria nova ou
uma forma de pedir dieta/treino que não esteja na lista cai para o LLM
(mais lento e mais caro que deveria) ou, na pior hipótese de um prompt mal
calibrado, pode ser mal classificada. Ajustar a cobertura das regras exige
deploy de código, não é configurável em runtime.
