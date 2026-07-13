# O Agente Gerente é, antes de tudo, código: o roteamento é determinístico
# sempre que possível. O LLM só entra quando a intenção é genuinamente
# ambígua e nenhuma regra de palavra-chave resolveu. Colocar um LLM para
# decidir o que um "if" já resolve adiciona custo, latência e um ponto de
# alucinação sem nenhum ganho — a regra de negócio pertence ao código, o
# LLM é o último recurso, não o primeiro.

import json
import time
import unicodedata

from django.conf import settings

from apps.coach.agents.utils import usage_tokens
from apps.coach.models import CoachAgent, Intent
from apps.coach.providers.registry import get_provider
from apps.coach.schemas import strip_code_fences
from apps.coach.services import record_agent_run

DIET_KEYWORDS = (
    "dieta",
    "plano alimentar",
    "refeicao",
    "comer",
    "macro",
    "cardapio",
    "nutricao",
    "nutricionista",
)
WORKOUT_KEYWORDS = (
    "treino",
    "exercicio",
    "serie",
    "ficha",
    "musculacao",
    "academia",
)

MANAGER_SYSTEM_PROMPT = """Você é o roteador do FitTrack Coach. Sua única função é
classificar a intenção da mensagem do aluno dentre exatamente estas opções:
- "diet_plan": o aluno quer um plano alimentar/dieta.
- "workout_plan": o aluno quer um plano de treino/exercícios.
- "out_of_scope": o pedido não tem relação com dieta ou treino (ex.: suporte
  técnico, dúvida administrativa, assunto pessoal, diagnóstico médico).
- "ambiguous": não dá para determinar a intenção com confiança a partir da
  mensagem.

Responda APENAS o JSON abaixo — sem markdown, sem texto antes ou depois:
{"intent": "diet_plan" | "workout_plan" | "out_of_scope" | "ambiguous", "reason": "string curta em português"}"""


def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char))


def _matches(normalized: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in normalized for keyword in keywords)


def route(message: str) -> Intent:
    """Etapa 1 (determinística): casa palavras-chave. Só recorre ao LLM
    (etapa 2) quando nenhuma regra bate."""
    normalized = _normalize(message or "")

    if _matches(normalized, DIET_KEYWORDS):
        return Intent.DIET_PLAN
    if _matches(normalized, WORKOUT_KEYWORDS):
        return Intent.WORKOUT_PLAN

    return _route_with_llm(message)


def _parse_intent(raw: str) -> tuple[Intent, str | None]:
    text = strip_code_fences(raw or "")
    try:
        data = json.loads(text)
        value = data.get("intent") if isinstance(data, dict) else None
        return Intent(value), None
    except (json.JSONDecodeError, ValueError, AttributeError):
        # Fail-safe: qualquer coisa fora do Enum vira AMBIGUOUS. Nunca
        # inventamos uma intenção a partir de uma resposta malformada.
        return Intent.AMBIGUOUS, f"Resposta do gerente fora do formato esperado: {raw!r}"


def _route_with_llm(message: str) -> Intent:
    provider_name = settings.COACH_GENERATOR_PROVIDER
    provider = get_provider(provider_name)

    messages = [{"role": "user", "content": message}]

    started = time.monotonic()
    response = provider.complete(system=MANAGER_SYSTEM_PROMPT, messages=messages)
    latency_ms = int((time.monotonic() - started) * 1000)

    input_tokens = usage_tokens(response.usage, ("input_tokens", "promptTokenCount"))
    output_tokens = usage_tokens(response.usage, ("output_tokens", "candidatesTokenCount"))

    intent, parse_error = _parse_intent(response.text or "")

    record_agent_run(
        agent=CoachAgent.MANAGER,
        provider=provider_name,
        model=getattr(provider, "model", ""),
        iterations=1,
        validation_errors=[parse_error] if parse_error else [],
        approved=intent != Intent.AMBIGUOUS,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )

    return intent
