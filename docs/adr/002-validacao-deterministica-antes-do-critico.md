# ADR-002 — Validação determinística antes do LLM crítico

## Contexto

Depois que o Agente de Dieta propõe um plano, dois tipos de problema podem
existir: (a) problemas de aritmética/regra de negócio — comida com
`food_id` inexistente, porção fora de faixa, refeições fora de ordem,
macros fora dos alvos — e (b) problemas de qualidade que só um julgamento
mais rico consegue avaliar — o plano é monótono? uma porção é realista?
o aluno vai depender demais de suplemento em vez de comida de verdade?

## Decisão

`apps.coach.validators.validate_meal_plan` — Python puro, sem LLM — roda
**antes** do Agente Crítico e decide tudo que é aritmética: existência e
acesso ao `food_id`, faixa de `quantity_g`, unicidade/sequência de `order`,
número de refeições, e os quatro macros somados (`compute_totals`) contra
os alvos do `BodyMetric`, com tolerância por macro (kcal ±5%, proteína
±10%, carboidrato/gordura ±15%). O Agente Crítico (`apps/coach/agents/
critic.py`) só é chamado depois que essa validação já aprovou o plano, e o
prompt do crítico deixa explícito que os macros **já foram conferidos** —
ele não recalcula, não questiona número. As mensagens de erro da validação
são acionáveis (ex.: "Total de proteína 210g está 40g ACIMA do alvo de
170g. Reduza porções de alimentos ricos em proteína.") e realimentam
diretamente o loop de retry do gerador (`generate_meal_plan`), como uma
nova mensagem de usuário pedindo correção.

## Alternativas consideradas

- **Deixar o crítico (LLM) avaliar tudo, inclusive os números.** Rejeitada
  por ADR-001: LLM não é confiável para aritmética, e chamar um segundo
  modelo para reproduzir o que uma soma resolve é caro e redundante.
- **Validar depois do crítico, não antes.** Rejeitada: gastaria uma
  chamada de LLM (o crítico) revisando qualidade de um plano que nem
  passou na aritmética — desperdício de latência e custo, e o crítico
  poderia aprovar "qualidade" de um plano com macro errado.

## Consequências

**Positivas**: separa claramente o que é responsabilidade de código
(determinístico, testável, barato) do que é responsabilidade de julgamento
(LLM, mais caro, mais lento). O crítico nunca é chamado para um plano que
já falhou na aritmética (ver ADR-003 e o teste
`test_pipeline_skips_critic_when_diet_validation_fails`), economizando uma
chamada de LLM inteira nesse caminho.

**Negativas**: a tolerância por macro (5%/10%/15%) é um parâmetro fixo no
código (`apps.coach.validators`) — ajustá-la exige deploy, não é
configurável em runtime. Além disso, a validação só enxerga o que foi
modelado (macros, contagem/ordem de refeições); qualquer regra de negócio
nova sobre a composição do plano precisa ser adicionada explicitamente ali,
não emerge "de graça" de um prompt melhor.
