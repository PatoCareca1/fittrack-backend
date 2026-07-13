# ADR-006 — MCP expõe ferramentas determinísticas, não agentes

## Contexto

O FitTrack precisa ser consumível por um host MCP externo — tipicamente o
Claude Desktop do nutricionista/personal vinculado a um aluno — para que o
profissional consulte e atue sobre dados dos seus alunos a partir do
próprio cliente de IA. Havia duas formas óbvias de desenhar isso: expor os
agentes de IA internos do FitTrack (dieta, crítico) como tools MCP, ou
expor só as ferramentas e dados determinísticos que os agentes já usam
internamente.

## Decisão

O servidor MCP (`apps/coach/mcp/`) **não contém nenhum LLM** e **não expõe
os agentes de IA internos** (`apps/coach/agents/*`) como tools. Ele expõe
só ferramentas determinísticas (`listar_alunos`, `obter_metricas`,
`buscar_alimento`, `listar_exercicios`, `criar_plano_alimentar`) e recursos
de leitura (`fittrack://aluno/{id}/perfil`, `.../metricas`). Quem tem o
modelo é o host do outro lado da conexão — o FitTrack só fornece dados e
ferramentas para esse modelo agir.

Pela mesma razão, **MCP não é usado na comunicação interna entre os
agentes** (gerente → dieta → crítico). Ali, os agentes já rodam no mesmo
processo Python e se chamam como funções diretas
(`generate_and_review_meal_plan` chama `generate_meal_plan` e
`review_meal_plan` diretamente) — adicionar uma camada de protocolo
(serialização JSON-RPC, autenticação por mensagem, transporte HTTP) entre
componentes que já são código nosso, no mesmo processo, adicionaria
latência e superfície de falha sem nenhum ganho. MCP resolve um problema
específico — expor capacidades a um modelo que não controlamos — e esse
problema só existe na borda com o host externo.

## Alternativas consideradas

- **Expor `generate_and_review_meal_plan` como uma tool MCP** (ex.:
  `gerar_plano_alimentar_com_ia`), deixando o host externo chamá-la.
  Rejeitada: isso embrulharia uma chamada de LLM (o Agente de Dieta, que já
  usa `COACH_GENERATOR_PROVIDER`) dentro de uma tool chamada por *outro*
  LLM (o do host MCP) — dois modelos empilhados, dobrando custo de
  inferência e empilhando o risco de alucinação de um sobre a saída do
  outro, sem nenhum ganho: o host já tem seu próprio modelo capaz de
  raciocinar sobre os dados que o FitTrack fornece via
  `obter_metricas`/`buscar_alimento`.
- **Usar MCP como o barramento de comunicação entre gerente/dieta/crítico
  internamente**, unificando o "protocolo de ferramentas" em um só lugar.
  Rejeitada: os agentes internos não precisam de descoberta dinâmica de
  capacidades nem de rodar em processos/máquinas diferentes — são chamada
  de função Python simples, e MCP não resolveria nenhum problema real ali,
  só adicionaria uma camada.

## Consequências

**Positivas**: o servidor MCP tem uma responsabilidade única e clara —
dados e ferramentas determinísticas, sem custo de LLM embutido em si
mesmo. `criar_plano_alimentar` reutiliza a mesma validação determinística
(`validate_meal_plan`) que barra o agente interno — a regra de negócio
não é duplicada nem enfraquecida para o caminho externo. Toda ferramenta
que toca dado de aluno valida vínculo profissional ativo (RN05) antes de
qualquer coisa.

**Negativas**: o profissional que quer "gerar um plano com IA" via Claude
Desktop não tem esse atalho — ele usa as tools determinísticas
(`obter_metricas`, `buscar_alimento`) e o próprio raciocínio do modelo do
host para montar a proposta, chamando `criar_plano_alimentar` só no fim.
Isso é mais trabalho para o host/modelo externo do que uma tool "gera o
plano pra mim" teria sido — uma escolha deliberada em troca de não
duplicar custo e risco de alucinação.
