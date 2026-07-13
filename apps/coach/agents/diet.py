import time
from dataclasses import dataclass

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.body.models import BodyMetric
from apps.coach.models import AgentRun, CoachAgent
from apps.coach.providers.registry import get_provider
from apps.coach.schemas import parse_diet_output
from apps.coach.services import record_agent_run
from apps.coach.tools import DIET_TOOL_SCHEMAS, execute_tool
from apps.coach.validators import compute_totals, validate_meal_plan

MAX_TOOL_ROUNDS = 6

DIET_AGENT_SYSTEM_PROMPT = """Você é o Agente de Dieta do FitTrack, especialista em nutrição esportiva.
Sua função é montar um plano alimentar para o aluno, usando os alimentos
disponíveis no catálogo do FitTrack.

ALVOS NUTRICIONAIS DO ALUNO (já calculados pelo sistema, não questione nem
recalcule):
- Objetivo (goal): {goal}
- Calorias: {calorie_goal} kcal/dia
- Proteína: {protein_g} g/dia
- Carboidrato: {carbs_g} g/dia
- Gordura: {fat_g} g/dia

O plano de refeições que você montar deve, somado, aproximar-se o máximo
possível desses alvos.

REGRAS INEGOCIÁVEIS:
1. Você NUNCA calcula nem informa valores de kcal/proteína/carboidrato/gordura
   na sua resposta. Você só escolhe QUAL alimento (food_id) e QUANTA
   quantidade em gramas (quantity_g). Todo o cálculo nutricional é feito
   pelo sistema a partir do banco de alimentos.
2. Você só pode usar um food_id que tenha sido retornado pela ferramenta
   buscar_alimento nesta conversa. Inventar um food_id é uma falha grave.
3. Use a ferramenta buscar_alimento quantas vezes precisar para encontrar
   alimentos adequados antes de montar o plano final.
4. Quando terminar, responda APENAS com o JSON no formato abaixo — sem
   markdown, sem texto antes ou depois, sem preâmbulo:
   {{"meals": [{{"name": "string", "time": "HH:MM", "order": 1, "items": [{{"food_id": 1, "quantity_g": 100}}]}}], "rationale": "string"}}
5. O campo "rationale" deve conter uma explicação curta, em português, da
   lógica do plano para o aluno.

GUARDRAIL DE ESCOPO: você é um agente de dieta. Não opine sobre treino
físico, não faça diagnóstico médico e não comente condições de saúde do
aluno. Se o pedido do aluno tocar nesses temas, ignore-os na montagem do
plano e registre no campo "rationale" que a questão deve ser encaminhada ao
profissional responsável (nutricionista ou médico)."""


@dataclass
class DietAgentResult:
    approved: bool
    proposal: dict | None
    errors: list[str]
    totals: dict | None
    iterations: int
    agent_run: AgentRun


def _usage_value(usage: dict, keys: tuple[str, ...]) -> int:
    for key in keys:
        if usage.get(key):
            return usage[key]
    return 0


def _run_provider_until_text(provider, system: str, messages: list[dict], user):
    """Chama o provider, resolvendo tool_calls até ele produzir uma resposta
    final em texto (ou estourar o limite de segurança de rodadas)."""
    input_tokens = 0
    output_tokens = 0
    for _ in range(MAX_TOOL_ROUNDS):
        response = provider.complete(system=system, messages=messages, tools=DIET_TOOL_SCHEMAS)
        input_tokens += _usage_value(response.usage, ("input_tokens", "promptTokenCount"))
        output_tokens += _usage_value(response.usage, ("output_tokens", "candidatesTokenCount"))

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


def generate_meal_plan(user, goal_note: str = "") -> DietAgentResult:
    metric = BodyMetric.objects.filter(user=user).order_by("-date").first()
    if metric is None:
        raise ValidationError(
            "É preciso registrar ao menos uma medida corporal antes de gerar um plano alimentar."
        )

    system = DIET_AGENT_SYSTEM_PROMPT.format(
        goal=user.profile.get_goal_display(),
        calorie_goal=metric.calorie_goal,
        protein_g=metric.protein_g,
        carbs_g=metric.carbs_g,
        fat_g=metric.fat_g,
    )

    provider_name = settings.COACH_GENERATOR_PROVIDER
    provider = get_provider(provider_name)

    messages = [{"role": "user", "content": goal_note or "Monte meu plano alimentar."}]

    proposal = None
    totals = None
    errors: list[str] = []
    input_tokens = 0
    output_tokens = 0
    iterations = 0
    started = time.monotonic()

    for iterations in range(1, settings.COACH_MAX_ITERATIONS + 1):
        response, in_tok, out_tok = _run_provider_until_text(provider, system, messages, user)
        input_tokens += in_tok
        output_tokens += out_tok
        messages.append({"role": "assistant", "content": response.text})

        try:
            proposal = parse_diet_output(response.text or "")
            errors = validate_meal_plan(proposal, metric, user)
        except ValueError as exc:
            proposal = None
            errors = [f"A resposta não é um JSON válido no formato esperado: {exc}"]

        if not errors:
            totals = compute_totals(proposal)
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
    approved = not errors

    agent_run = record_agent_run(
        agent=CoachAgent.DIET,
        provider=provider_name,
        model=getattr(provider, "model", ""),
        iterations=iterations,
        validation_errors=errors,
        approved=approved,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )

    return DietAgentResult(
        approved=approved,
        proposal=proposal if approved else None,
        errors=errors,
        totals=totals if approved else None,
        iterations=iterations,
        agent_run=agent_run,
    )
