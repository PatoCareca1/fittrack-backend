# ADR-004 — Abstração de provider (sem SDK proprietário)

## Contexto

O FitTrack Coach precisa falar com pelo menos dois fornecedores de LLM
(ADR-003: Anthropic e Gemini, potencialmente mais no futuro) e trocar de
fornecedor — por preço, disponibilidade, ou qualidade — não pode significar
reescrever a lógica dos agentes.

## Decisão

`apps/coach/providers/` define uma interface neutra
(`LLMProvider.complete(system, messages, tools, json_schema) -> LLMResponse`)
implementada com `httpx` puro contra a API REST de cada fornecedor
(`anthropic_provider.py`, `gemini_provider.py`) — nenhum SDK proprietário
(`anthropic`, `google-generativeai`, etc.) é dependência do projeto.
`providers/registry.get_provider(name)` resolve a implementação por string,
e essa string vem de configuração (`COACH_GENERATOR_PROVIDER`,
`COACH_CRITIC_PROVIDER`). O formato de mensagens e de tools é neutro
(dicts simples com `role`/`content`/`tool_calls`, schema de tool com
`name`/`description`/`parameters`); cada provider traduz esse formato
neutro para o payload nativo do seu fornecedor (ex.: `input_schema` no
Anthropic vs. `parameters` no Gemini; blocos `tool_use`/`tool_result` no
Anthropic vs. `functionCall`/`functionResponse` no Gemini).

## Alternativas consideradas

- **Usar o SDK oficial de cada fornecedor** (`anthropic-sdk-python`,
  `google-genai`). Rejeitada: acopla o projeto a duas bibliotecas com
  ciclos de release, breaking changes e modelos de configuração próprios e
  diferentes entre si; a interface interna (`LLMProvider`) teria que
  existir de qualquer forma para abstrair as diferenças, então os SDKs
  só adicionariam uma camada de tradução a mais sem eliminar a que já
  escrevemos.
- **Um único fornecedor fixo, sem abstração.** Rejeitada por ADR-003 (o
  crítico já precisa de um fornecedor diferente do gerador) e por risco de
  vendor lock-in num sistema que lida com dados de saúde.

## Consequências

**Positivas**: trocar de fornecedor é mudar uma variável de ambiente
(`COACH_GENERATOR_PROVIDER=gemini`, por exemplo) — zero mudança de código
nos agentes. Adicionar um terceiro fornecedor é implementar uma classe
`LLMProvider` nova e registrá-la em `registry.py`; nada mais muda.
Superfície de dependências menor (`httpx` já era dependência do projeto).

**Negativas**: mantemos manualmente a tradução do formato de tool use e das
mensagens de cada fornecedor — quando a Anthropic ou o Google mudar o
formato da própria API (novos campos, deprecações), o time do FitTrack
sente isso diretamente em `anthropic_provider.py`/`gemini_provider.py`, sem
a rede de segurança de um SDK oficial versionado e testado pelo próprio
fornecedor. Streaming, retries com backoff específico e outras
funcionalidades que os SDKs oferecem "de graça" teriam que ser
implementadas manualmente, se e quando precisarmos delas.
