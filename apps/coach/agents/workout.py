# Agente de Treino — espelha o Agente de Dieta (apps/coach/agents/diet.py)
# na estrutura: tool de busca, schema de saída, validação determinística,
# loop de retry (via apps.coach.agents._loop, compartilhado com dieta),
# revisão pelo crítico.
#
# A ASSIMETRIA DE DOMÍNIO é deliberada e documentada aqui, não escondida:
# dieta tem um alvo numérico EXTERNO (calorie_goal/macros, calculado por
# apps.body.services._compute a partir de uma fórmula fisiológica —
# Mifflin-St Jeor) contra o qual validate_meal_plan compara a soma real dos
# macros do plano. Treino NÃO tem um alvo numérico equivalente no sistema —
# não existe uma fórmula de "volume de treino ideal" calculada a partir do
# perfil do aluno. Por isso `validate_workout_plan` (apps/coach/
# validators.py) não compara contra uma referência numérica: ela valida
# ESTRUTURA e SANIDADE (exercícios existem, quantidade plausível de
# exercícios/séries/repetições, faixas de repetição condizentes — de forma
# larga — com o objetivo do perfil, sem duplicar ordem/exercício em
# excesso). Fingir simetria total com a dieta aqui seria impor uma precisão
# numérica que o domínio não tem.

from dataclasses import dataclass, field

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.coach.agents._loop import run_generation_loop
from apps.coach.agents.critic import CriticResult, review_workout_plan
from apps.coach.models import AgentRun, CoachAgent
from apps.coach.providers.registry import get_provider
from apps.coach.schemas import parse_workout_output
from apps.coach.services import record_agent_run
from apps.coach.tools import WORKOUT_TOOL_SCHEMAS, execute_tool
from apps.coach.validators import summarize_workout, validate_workout_plan
from apps.users.models import Profile

WORKOUT_AGENT_SYSTEM_PROMPT = """Você é o Agente de Treino do FitTrack, especialista em educação física e
prescrição de exercícios.
Sua função é montar uma ficha de treino para o aluno, usando os exercícios
disponíveis no catálogo do FitTrack.

PERFIL DO ALUNO (já registrado pelo sistema, não questione):
- Objetivo (goal): {goal}
- Nível de atividade: {activity_level}

O treino que você montar deve ser condizente com esse objetivo e nível de
atividade.

REGRAS INEGOCIÁVEIS:
1. Você só pode usar um exercise_id que tenha sido retornado pela
   ferramenta listar_exercicios nesta conversa. Inventar um exercise_id é
   uma falha grave.
2. Use a ferramenta listar_exercicios quantas vezes precisar para encontrar
   exercícios adequados antes de montar o treino final.
3. Cada exercício deve ter exatamente um de "reps" ou "duration_seconds"
   preenchido (nunca os dois, nunca nenhum) — use "duration_seconds" para
   exercícios por tempo (prancha, etc.) e "reps" para os demais.
4. Você não calcula nem sugere carga (load_kg) a menos que o aluno peça
   explicitamente um valor de referência — na dúvida, deixe null.
5. Quando terminar, responda APENAS com o JSON no formato abaixo — sem
   markdown, sem texto antes ou depois, sem preâmbulo:
   {{"name": "string", "exercises": [{{"exercise_id": 1, "order": 1, "sets": 3, "reps": 10, "duration_seconds": null, "load_kg": null, "rest_seconds": 60}}], "rationale": "string"}}
6. O campo "rationale" deve conter uma explicação curta, em português, da
   lógica do treino para o aluno.

GUARDRAIL DE ESCOPO: você é um agente de treino. Não opine sobre dieta ou
nutrição, não faça diagnóstico médico e não comente condições de saúde do
aluno. Se o pedido do aluno tocar nesses temas, ignore-os na montagem do
treino e registre no campo "rationale" que a questão deve ser encaminhada
ao profissional responsável (nutricionista ou médico)."""


@dataclass
class WorkoutAgentResult:
    approved: bool
    proposal: dict | None
    errors: list[str]
    summary: dict | None
    iterations: int
    agent_run: AgentRun


def _get_profile(user) -> Profile:
    """Profile é auto-criado (com defaults) via signal para todo User — em
    operação normal isto nunca deveria disparar. Mantido mesmo assim, pela
    mesma disciplina defensiva de `_get_latest_metric` na dieta: nunca
    assumir uma precondição sem checar."""
    profile = getattr(user, "profile", None)
    if profile is None or not profile.goal or not profile.activity_level:
        raise ValidationError(
            "É preciso completar seu perfil (objetivo e nível de atividade) "
            "antes de gerar um plano de treino."
        )
    return profile


def generate_workout_plan(user, goal_note: str = "") -> WorkoutAgentResult:
    profile = _get_profile(user)

    system = WORKOUT_AGENT_SYSTEM_PROMPT.format(
        goal=profile.get_goal_display(),
        activity_level=profile.get_activity_level_display(),
    )

    provider_name = settings.COACH_GENERATOR_PROVIDER
    provider = get_provider(provider_name)

    loop_result = run_generation_loop(
        user=user,
        provider=provider,
        system=system,
        initial_message=goal_note or "Monte meu plano de treino.",
        tools=WORKOUT_TOOL_SCHEMAS,
        execute_tool=execute_tool,
        parse_output=parse_workout_output,
        validate_output=lambda proposal: validate_workout_plan(proposal, profile, user),
        max_iterations=settings.COACH_MAX_ITERATIONS,
    )

    approved = not loop_result.errors
    summary = summarize_workout(loop_result.proposal) if approved else None

    agent_run = record_agent_run(
        agent=CoachAgent.WORKOUT,
        provider=provider_name,
        model=getattr(provider, "model", ""),
        iterations=loop_result.iterations,
        validation_errors=loop_result.errors,
        approved=approved,
        input_tokens=loop_result.input_tokens,
        output_tokens=loop_result.output_tokens,
        latency_ms=loop_result.latency_ms,
    )

    return WorkoutAgentResult(
        approved=approved,
        proposal=loop_result.proposal if approved else None,
        errors=loop_result.errors,
        summary=summary if approved else None,
        iterations=loop_result.iterations,
        agent_run=agent_run,
    )


@dataclass
class CoachedWorkoutResult:
    approved: bool
    proposal: dict | None
    summary: dict | None
    errors: list[str]
    issues: list[dict]
    critic_summary: str
    workout_iterations: int
    critic_rounds: int
    agent_runs: list[AgentRun] = field(default_factory=list)


def generate_and_review_workout_plan(user, goal_note: str = "") -> CoachedWorkoutResult:
    """Espelha generate_and_review_meal_plan: mesmo mecanismo de retry via
    generate_workout_plan, reaproveitando COACH_MAX_CRITIC_ROUNDS."""
    max_critic_rounds = settings.COACH_MAX_CRITIC_ROUNDS
    agent_runs: list[AgentRun] = []
    note = goal_note
    workout_result = None
    critic_result: CriticResult | None = None

    for critic_round in range(1, max_critic_rounds + 1):
        workout_result = generate_workout_plan(user, goal_note=note)
        agent_runs.append(workout_result.agent_run)

        if not workout_result.approved:
            # Treino nem passou na sanidade estrutural: não vale a pena
            # gastar uma chamada de LLM do crítico revisando algo que já
            # falhou.
            return CoachedWorkoutResult(
                approved=False,
                proposal=None,
                summary=None,
                errors=workout_result.errors,
                issues=[],
                critic_summary="",
                workout_iterations=workout_result.iterations,
                critic_rounds=critic_round - 1,
                agent_runs=agent_runs,
            )

        profile = _get_profile(user)
        critic_result = review_workout_plan(
            user, workout_result.proposal, workout_result.summary, profile
        )
        agent_runs.append(critic_result.agent_run)

        if critic_result.approved:
            return CoachedWorkoutResult(
                approved=True,
                proposal=workout_result.proposal,
                summary=workout_result.summary,
                errors=[],
                issues=critic_result.issues,
                critic_summary=critic_result.summary,
                workout_iterations=workout_result.iterations,
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

    return CoachedWorkoutResult(
        approved=False,
        proposal=None,
        summary=None,
        errors=[],
        issues=critic_result.issues if critic_result else [],
        critic_summary=critic_result.summary if critic_result else "",
        workout_iterations=workout_result.iterations if workout_result else 0,
        critic_rounds=max_critic_rounds,
        agent_runs=agent_runs,
    )
