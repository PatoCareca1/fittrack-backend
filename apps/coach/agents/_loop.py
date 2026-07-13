# Loop de geração+retry compartilhado entre o Agente de Dieta e o Agente de
# Treino (apps/coach/agents/diet.py e workout.py). Os dois seguem
# estruturalmente o mesmo algoritmo: chamar o provider com as tools até ele
# produzir uma resposta final em texto (resolvendo tool_calls no caminho),
# fazer parse, validar, e — se inválido — reinjetar os erros como nova
# mensagem de usuário e tentar de novo, até um limite de iterações. Só o
# schema de saída, a função de validação e o prompt do sistema mudam entre
# os dois agentes. Extrair esse núcleo aqui evita que dieta e treino
# divirjam sutilmente no MESMO algoritmo por causa de duas cópias mantidas
# à mão (ex.: um dos dois ganhar um ajuste no texto de retry e o outro não).
# `get_provider()` continua sendo chamado dentro de cada agents/*.py (não
# aqui), porque os testes existentes fazem
# `@patch("apps.coach.agents.diet.get_provider")` — mover essa chamada para
# cá quebraria esse ponto de mock.

import time
from dataclasses import dataclass, field
from typing import Callable

from apps.coach.agents.utils import usage_tokens

MAX_TOOL_ROUNDS = 6


@dataclass
class LoopResult:
    proposal: dict | None
    errors: list[str]
    iterations: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    messages: list[dict] = field(default_factory=list)


def _run_provider_until_text(provider, system: str, messages: list[dict], tools: list[dict], execute_tool: Callable, user):
    """Chama o provider, resolvendo tool_calls até ele produzir uma resposta
    final em texto (ou estourar o limite de segurança de rodadas)."""
    input_tokens = 0
    output_tokens = 0
    for _ in range(MAX_TOOL_ROUNDS):
        response = provider.complete(system=system, messages=messages, tools=tools)
        input_tokens += usage_tokens(response.usage, ("input_tokens", "promptTokenCount"))
        output_tokens += usage_tokens(response.usage, ("output_tokens", "candidatesTokenCount"))

        if not response.tool_calls:
            return response, input_tokens, output_tokens

        messages.append(
            {"role": "assistant", "content": response.text, "tool_calls": response.tool_calls}
        )
        for tool_call in response.tool_calls:
            result = execute_tool(tool_call.name, tool_call.arguments, user)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "content": result,
                }
            )

    raise RuntimeError("Excesso de chamadas de ferramenta sem produzir uma resposta final.")


def run_generation_loop(
    *,
    user,
    provider,
    system: str,
    initial_message: str,
    tools: list[dict],
    execute_tool: Callable,
    parse_output: Callable[[str], dict],
    validate_output: Callable[[dict], list[str]],
    max_iterations: int,
) -> LoopResult:
    """Núcleo do loop de retry. `parse_output` levanta ValueError em caso de
    JSON malformado; `validate_output` retorna a lista de erros
    determinísticos (vazia = aprovado)."""
    messages = [{"role": "user", "content": initial_message}]

    proposal = None
    errors: list[str] = []
    input_tokens = 0
    output_tokens = 0
    iterations = 0
    started = time.monotonic()

    for iterations in range(1, max_iterations + 1):
        response, in_tok, out_tok = _run_provider_until_text(
            provider, system, messages, tools, execute_tool, user
        )
        input_tokens += in_tok
        output_tokens += out_tok
        messages.append({"role": "assistant", "content": response.text})

        try:
            proposal = parse_output(response.text or "")
            errors = validate_output(proposal)
        except ValueError as exc:
            proposal = None
            errors = [f"A resposta não é um JSON válido no formato esperado: {exc}"]

        if not errors:
            break

        proposal = None
        messages.append(
            {
                "role": "user",
                "content": (
                    "Sua proposta foi rejeitada pelos seguintes motivos: "
                    + " ".join(errors)
                    + " Corrija e responda novamente apenas com o JSON no formato especificado."
                ),
            }
        )

    latency_ms = int((time.monotonic() - started) * 1000)
    return LoopResult(
        proposal=proposal,
        errors=errors,
        iterations=iterations,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        messages=messages,
    )
