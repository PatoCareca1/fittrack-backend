# ADR-001 — Nenhum LLM calcula números

## Contexto

O Agente de Dieta (`apps/coach/agents/diet.py`) monta planos alimentares que
precisam bater com alvos nutricionais (kcal, proteína, carboidrato, gordura)
de um aluno. LLMs são notoriamente ruins em aritmética exata e podem
"alucinar" valores plausíveis, mas errados — um risco inaceitável em dados
que orientam a alimentação de uma pessoa.

## Decisão

Os alvos calóricos/macros nunca são calculados pelo LLM. Eles vêm de
`apps.body.services._compute` (fórmula de Mifflin-St Jeor + fatores de
atividade/objetivo — RN01–RN03), persistidos em `BodyMetric` antes de
qualquer chamada ao agente. O LLM só **seleciona** `food_id` e
`quantity_g` a partir do catálogo (`apps.coach.tools.buscar_alimento`);
todo o valor nutricional real é somado por Python a partir de `diet.Food`
(`apps.coach.validators.compute_totals`). Se o modelo devolver qualquer
campo de macro na resposta (ex.: um item vier com `"kcal": 250`),
`apps.coach.schemas.parse_diet_output` descarta esse campo silenciosamente
— só `food_id`/`quantity_g` sobrevivem ao parse.

## Alternativas consideradas

- **Deixar o LLM calcular e só auditar o resultado depois.** Rejeitada:
  auditar depois de gerar ainda expõe o aluno ao risco se a auditoria
  falhar ou for ignorada; mais barato prevenir na origem.
- **Pedir ao LLM os macros e usá-los como uma dica, cruzando com o banco.**
  Rejeitada: qualquer uso do número vindo do modelo, mesmo como "dica",
  cria uma superfície para inconsistência silenciosa entre o que foi
  mostrado ao aluno e o que o banco diz.

## Consequências

**Positivas**: elimina a classe inteira de alucinação numérica na raiz —
não existe caminho de código em que um número de macro gerado pelo modelo
chegue ao aluno. Também simplifica o prompt (o modelo não precisa "saber"
fazer conta) e a auditoria (o único lugar que calcula é
`compute_totals`/`_compute`, testável isoladamente).

**Negativas**: o modelo perde flexibilidade — não pode propor um alvo fora
da fórmula (ex.: um ajuste fino que um nutricionista humano faria por
julgamento clínico). Qualquer refinamento de alvo tem que passar pela
fórmula em `apps.body.services` ou por edição manual do `BodyMetric`, não
por uma conversa com o agente.
