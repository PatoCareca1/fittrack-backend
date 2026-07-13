# ADRs — apps/coach

Registro das decisões de arquitetura da camada de agentes de IA
(`apps/coach/`). Formato curto: Contexto / Decisão / Alternativas
consideradas / Consequências (incluindo as negativas).

| ADR | Título |
|---|---|
| [001](001-nenhum-llm-calcula-numeros.md) | Nenhum LLM calcula números |
| [002](002-validacao-deterministica-antes-do-critico.md) | Validação determinística antes do LLM crítico |
| [003](003-critico-em-fornecedor-diferente.md) | Crítico em fornecedor diferente do gerador |
| [004](004-abstracao-de-provider.md) | Abstração de provider (sem SDK proprietário) |
| [005](005-gerente-e-codigo.md) | Gerente é código, não LLM |
| [006](006-mcp-expoe-ferramentas-nao-agentes.md) | MCP expõe ferramentas determinísticas, não agentes |
| [007](007-sdk-oficial-de-mcp-descartado.md) | SDK oficial de MCP descartado |
| [008](008-execucao-assincrona-via-thread.md) | Execução assíncrona via thread (dívida técnica assumida) |
| [009](009-fail-safe-em-falha-de-parsing.md) | Fail-safe em toda falha de parsing de LLM |

Ver também [`docs/arquitetura-coach.md`](../arquitetura-coach.md) para os
diagramas de fluxo.
