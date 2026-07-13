from dataclasses import dataclass, field

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.body.models import BodyMetric
from apps.coach.agents._loop import run_generation_loop
from apps.coach.agents.critic import CriticResult, review_meal_plan
from apps.coach.models import AgentRun, CoachAgent
from apps.coach.providers.registry import get_provider
from apps.coach.schemas import parse_diet_output
from apps.coach.services import record_agent_run
from apps.coach.tools import DIET_TOOL_SCHEMAS, execute_tool
from apps.coach.validators import compute_totals, validate_meal_plan

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


def _get_latest_metric(user) -> BodyMetric:
    metric = BodyMetric.objects.filter(user=user).order_by("-date").first()
    if metric is None:
        raise ValidationError(
            "É preciso registrar ao menos uma medida corporal antes de gerar um plano alimentar."
        )
    return metric


def generate_meal_plan(user, goal_note: str = "") -> DietAgentResult:
    metric = _get_latest_metric(user)

    system = DIET_AGENT_SYSTEM_PROMPT.format(
        goal=user.profile.get_goal_display(),
        calorie_goal=metric.calorie_goal,
        protein_g=metric.protein_g,
        carbs_g=metric.carbs_g,
        fat_g=metric.fat_g,
    )

    provider_name = settings.COACH_GENERATOR_PROVIDER
    provider = get_provider(provider_name)

    loop_result = run_generation_loop(
        user=user,
        provider=provider,
        system=system,
        initial_message=goal_note or "Monte meu plano alimentar.",
        tools=DIET_TOOL_SCHEMAS,
        execute_tool=execute_tool,
        parse_output=parse_diet_output,
        validate_output=lambda proposal: validate_meal_plan(proposal, metric, user),
        max_iterations=settings.COACH_MAX_ITERATIONS,
    )

    approved = not loop_result.errors
    totals = compute_totals(loop_result.proposal) if approved else None

    agent_run = record_agent_run(
        agent=CoachAgent.DIET,
        provider=provider_name,
        model=getattr(provider, "model", ""),
        iterations=loop_result.iterations,
        validation_errors=loop_result.errors,
        approved=approved,
        input_tokens=loop_result.input_tokens,
        output_tokens=loop_result.output_tokens,
        latency_ms=loop_result.latency_ms,
    )

    return DietAgentResult(
        approved=approved,
        proposal=loop_result.proposal if approved else None,
        errors=loop_result.errors,
        totals=totals if approved else None,
        iterations=loop_result.iterations,
        agent_run=agent_run,
    )


@dataclass
class CoachedPlanResult:
    approved: bool
    proposal: dict | None
    totals: dict | None
    errors: list[str]
    issues: list[dict]
    critic_summary: str
    diet_iterations: int
    critic_rounds: int
    agent_runs: list[AgentRun] = field(default_factory=list)


def generate_and_review_meal_plan(user, goal_note: str = "") -> CoachedPlanResult:
    """Gera um plano alimentar e o submete ao Agente Crítico. Se o crítico
    reprovar (issue "blocker"), regenera reaproveitando o mesmo mecanismo de
    retry de `generate_meal_plan` — a rejeição do crítico é injetada como
    mais um motivo de correção no goal_note, exatamente como os erros de
    validação determinística já são injetados nas mensagens internas do
    loop de `generate_meal_plan`."""
    max_critic_rounds = settings.COACH_MAX_CRITIC_ROUNDS
    agent_runs: list[AgentRun] = []
    note = goal_note
    diet_result = None
    critic_result: CriticResult | None = None

    for critic_round in range(1, max_critic_rounds + 1):
        diet_result = generate_meal_plan(user, goal_note=note)
        agent_runs.append(diet_result.agent_run)

        if not diet_result.approved:
            # Plano nem passou na aritmética: não vale a pena gastar uma
            # chamada de LLM do crítico revisando algo que já falhou.
            return CoachedPlanResult(
                approved=False,
                proposal=None,
                totals=None,
                errors=diet_result.errors,
                issues=[],
                critic_summary="",
                diet_iterations=diet_result.iterations,
                critic_rounds=critic_round - 1,
                agent_runs=agent_runs,
            )

        metric = _get_latest_metric(user)
        critic_result = review_meal_plan(user, diet_result.proposal, diet_result.totals, metric)
        agent_runs.append(critic_result.agent_run)

        if critic_result.approved:
            return CoachedPlanResult(
                approved=True,
                proposal=diet_result.proposal,
                totals=diet_result.totals,
                errors=[],
                issues=critic_result.issues,
                critic_summary=critic_result.summary,
                diet_iterations=diet_result.iterations,
                critic_rounds=critic_round,
                agent_runs=agent_runs,
            )

        blockers = [
            issue["message"] for issue in critic_result.issues if issue["severity"] == "blocker"
        ]
        note = (
            (goal_note + " " if goal_note else "")
            + "O revisor de qualidade rejeitou a proposta anterior pelos "
            "seguintes motivos: " + " ".join(blockers) + " "
            "Gere uma nova proposta corrigindo esses pontos."
        )

    return CoachedPlanResult(
        approved=False,
        proposal=None,
        totals=None,
        errors=[],
        issues=critic_result.issues if critic_result else [],
        critic_summary=critic_result.summary if critic_result else "",
        diet_iterations=diet_result.iterations if diet_result else 0,
        critic_rounds=max_critic_rounds,
        agent_runs=agent_runs,
    )
