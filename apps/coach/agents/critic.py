# O Agente Crítico roda em COACH_CRITIC_PROVIDER, que por padrão é um
# fornecedor DIFERENTE do gerador (COACH_GENERATOR_PROVIDER). Isso é
# deliberado: a razão de ser do crítico é diversidade de erro — um modelo
# tende a ser complacente com o próprio output. Usar dois fornecedores
# diferentes reduz a chance de o mesmo viés (do mesmo modelo/fornecedor)
# aprovar silenciosamente um plano ruim.
#
# O crítico NÃO reavalia aritmética: validate_meal_plan() já garantiu que os
# macros batem com os alvos do aluno. Se o crítico checasse número, ele
# seria redundante (o código já fez isso de forma determinística) e caro
# (mais uma chamada de LLM para reproduzir o que uma soma já resolveu). O
# crítico avalia o que código não consegue: qualidade, coerência e segurança
# do plano (variedade, porções realistas, distribuição ao longo do dia,
# adequação ao objetivo do aluno).

import json
import time
from dataclasses import dataclass

from django.conf import settings

from apps.coach.agents.utils import usage_tokens
from apps.coach.models import AgentRun, CoachAgent
from apps.coach.providers.registry import get_provider
from apps.coach.schemas import strip_code_fences
from apps.coach.services import record_agent_run
from apps.diet.models import Food

CRITIC_AGENT_SYSTEM_PROMPT = """Você é o Agente Crítico do FitTrack — um revisor de qualidade independente
que avalia planos alimentares já montados pelo Agente de Dieta.

IMPORTANTE: os valores nutricionais (kcal, proteína, carboidrato, gordura)
desse plano JÁ FORAM CONFERIDOS por código determinístico e batem com os
alvos do aluno. Você NÃO deve recalcular, questionar ou comentar números de
macronutrientes — isso não é sua função.

Sua função é avaliar o que um cálculo não consegue avaliar:
- Variedade e monotonia: o plano repete o mesmo alimento em excesso?
- Porções realistas: uma quantidade como 900g de um único alimento numa
  única refeição é uma falha grave (blocker) — pessoas reais não comem assim.
- Distribuição sensata das refeições ao longo do dia.
- Adequação ao objetivo do aluno: {goal}.
- Dependência excessiva de suplementos (whey, creatina, barras proteicas)
  em vez de comida de verdade.

Classifique cada problema encontrado:
- "blocker": torna o plano de fato inadequado para o aluno seguir. Use com
  critério — só o que realmente compromete o plano.
- "warning": um ponto de atenção que não invalida o plano.

GUARDRAIL DE ESCOPO: você é um revisor de dieta. NÃO dê diagnóstico médico e
NÃO opine sobre treino físico.

Responda APENAS com o JSON abaixo — sem markdown, sem texto antes ou depois:
{{"approved": bool, "issues": [{{"severity": "blocker" | "warning", "message": "string em português, objetivo", "meal_order": <int ou null>}}], "summary": "string"}}"""


@dataclass
class CriticResult:
    approved: bool
    issues: list[dict]
    summary: str
    agent_run: AgentRun


def _enrich_proposal_with_food_names(proposal: dict) -> dict:
    """O crítico precisa ver "150g de peito de frango", não "food_id 12"."""
    food_ids = {
        item["food_id"] for meal in proposal.get("meals", []) for item in meal.get("items", [])
    }
    names = dict(Food.objects.filter(id__in=food_ids).values_list("id", "name"))
    return {
        "meals": [
            {
                "order": meal["order"],
                "name": meal["name"],
                "time": meal["time"],
                "items": [
                    {
                        "food_name": names.get(item["food_id"], f"food_id {item['food_id']}"),
                        "quantity_g": item["quantity_g"],
                    }
                    for item in meal["items"]
                ],
            }
            for meal in proposal.get("meals", [])
        ],
        "rationale": proposal.get("rationale", ""),
    }


def _parse_critic_output(raw: str) -> dict:
    text = strip_code_fences(raw or "")
    if not text:
        raise ValueError("Resposta vazia do crítico.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido do crítico: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("A resposta do crítico deve ser um objeto JSON.")

    issues_raw = data.get("issues", [])
    if not isinstance(issues_raw, list):
        raise ValueError("O campo 'issues' do crítico deve ser uma lista.")

    issues = []
    for issue in issues_raw:
        if not isinstance(issue, dict):
            raise ValueError("Cada issue do crítico deve ser um objeto JSON.")

        severity = issue.get("severity")
        if severity not in ("blocker", "warning"):
            raise ValueError(
                f"severity inválida: {severity!r} (esperado 'blocker' ou 'warning')."
            )

        message = issue.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Cada issue do crítico deve ter uma 'message' não vazia.")

        meal_order = issue.get("meal_order")
        if meal_order is not None:
            try:
                meal_order = int(meal_order)
            except (TypeError, ValueError) as exc:
                raise ValueError("meal_order deve ser inteiro ou null.") from exc

        issues.append({"severity": severity, "message": message, "meal_order": meal_order})

    summary = data.get("summary")
    if not isinstance(summary, str):
        summary = ""

    return {
        "approved_field": bool(data.get("approved", False)),
        "issues": issues,
        "summary": summary,
    }


def review_meal_plan(user, proposal: dict, totals: dict, metric) -> CriticResult:
    enriched = _enrich_proposal_with_food_names(proposal)
    system = CRITIC_AGENT_SYSTEM_PROMPT.format(goal=user.profile.get_goal_display())

    provider_name = settings.COACH_CRITIC_PROVIDER
    provider = get_provider(provider_name)

    messages = [
        {
            "role": "user",
            "content": (
                "Revise o seguinte plano alimentar. Os macros já foram "
                "conferidos pelo sistema e batem com os alvos do aluno — "
                "não os avalie, avalie apenas qualidade, coerência e "
                "segurança do plano:\n\n"
                + json.dumps(enriched, ensure_ascii=False, indent=2)
            ),
        }
    ]

    started = time.monotonic()
    response = provider.complete(system=system, messages=messages)
    latency_ms = int((time.monotonic() - started) * 1000)

    input_tokens = usage_tokens(response.usage, ("input_tokens", "promptTokenCount"))
    output_tokens = usage_tokens(response.usage, ("output_tokens", "candidatesTokenCount"))

    validation_errors = []
    try:
        parsed = _parse_critic_output(response.text or "")
        issues = parsed["issues"]
        summary = parsed["summary"]
        llm_approved = parsed["approved_field"]
    except ValueError as exc:
        # Resposta do crítico malformada: falha de forma conservadora (não
        # aprova silenciosamente) e registra o motivo.
        issues = [
            {
                "severity": "blocker",
                "message": f"Resposta do crítico não pôde ser interpretada: {exc}",
                "meal_order": None,
            }
        ]
        summary = ""
        llm_approved = False
        validation_errors.append(str(exc))

    # Decisão final é do Python, cruzando as issues — nunca do campo
    # "approved" do LLM isoladamente.
    approved = not any(issue["severity"] == "blocker" for issue in issues)

    if llm_approved != approved:
        validation_errors.append(
            f"Divergência entre o campo 'approved' do LLM ({llm_approved}) e a "
            f"decisão determinística baseada nas issues ({approved}). "
            "Prevaleceu a decisão determinística baseada nas issues."
        )

    agent_run = record_agent_run(
        agent=CoachAgent.CRITIC,
        provider=provider_name,
        model=getattr(provider, "model", ""),
        iterations=1,
        validation_errors=validation_errors,
        approved=approved,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )

    return CriticResult(
        approved=approved,
        issues=issues,
        summary=summary,
        agent_run=agent_run,
    )
