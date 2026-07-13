from collections import Counter

from django.db.models import Q

from apps.diet.models import Food
from apps.users.models import Goal
from apps.workouts.models import Exercise

MAX_QUANTITY_G = 2000
MIN_MEALS = 3
MAX_MEALS = 8

KCAL_TOLERANCE = 0.05
PROTEIN_TOLERANCE = 0.10
CARBS_TOLERANCE = 0.15
FAT_TOLERANCE = 0.15

# Treino não tem um alvo numérico externo equivalente ao calorie_goal/macros
# da dieta (ver comentário no topo de apps/coach/agents/workout.py) — por
# isso os limites abaixo são checagem de SANIDADE estrutural, não aderência
# a uma fórmula de referência.
MIN_EXERCISES = 4
MAX_EXERCISES = 10
MIN_SETS = 2
MAX_SETS = 6
MIN_REPS = 4
MAX_REPS = 30
MIN_REST_SECONDS = 20
MAX_REST_SECONDS = 300
MAX_REPEATS_PER_EXERCISE = 2

# Faixas de repetição por objetivo — deliberadamente largas: isto é uma
# checagem de sanidade (pega 1 rep ou 50 reps), não uma prescrição clínica.
GOAL_REP_RANGES = {
    Goal.HYPERTROPHY: (6, 20),
    Goal.WEIGHT_LOSS: (6, 25),
    Goal.GENERAL_HEALTH: (6, 25),
    Goal.MAINTENANCE: (6, 25),
}
DEFAULT_REP_RANGE = (MIN_REPS, MAX_REPS)


def compute_totals(proposal: dict) -> dict:
    """Soma real dos macros a partir do banco (diet.Food), nunca do que o
    LLM disse. `proposal` já deve estar no formato normalizado retornado por
    `parse_diet_output` (só food_id/quantity_g em cada item)."""
    food_ids = {
        item["food_id"]
        for meal in proposal.get("meals", [])
        for item in meal.get("items", [])
    }
    foods = {food.id: food for food in Food.objects.filter(id__in=food_ids)}

    totals = {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for meal in proposal.get("meals", []):
        for item in meal.get("items", []):
            food = foods.get(item["food_id"])
            if food is None:
                continue
            factor = float(item["quantity_g"]) / 100
            totals["kcal"] += float(food.kcal) * factor
            totals["protein_g"] += float(food.protein_g) * factor
            totals["carbs_g"] += float(food.carbs_g) * factor
            totals["fat_g"] += float(food.fat_g) * factor

    return {key: round(value, 1) for key, value in totals.items()}


def _within_tolerance(total: float, target: float, tolerance: float) -> bool:
    if target <= 0:
        return True
    return abs(total - target) <= target * tolerance


def _macro_error(
    label: str,
    total: float,
    target: float,
    tolerance: float,
    advice_up: str,
    advice_down: str,
    unit: str = "g",
) -> str | None:
    if _within_tolerance(total, target, tolerance):
        return None
    diff = total - target
    direction = "ACIMA" if diff > 0 else "ABAIXO"
    advice = advice_up if diff > 0 else advice_down
    return (
        f"Total de {label} {total:.0f}{unit} está {abs(diff):.0f}{unit} {direction} do "
        f"alvo de {target:.0f}{unit} (tolerância de {int(tolerance * 100)}%). {advice}"
    )


def validate_meal_plan(proposal: dict, metric, user) -> list[str]:
    """Camada determinística: valida a proposta do LLM contra regras de
    negócio e os macros reais somados a partir do banco. Retorna lista de
    mensagens de erro ACIONÁVEIS pelo LLM (vazia = aprovado)."""
    errors: list[str] = []
    meals = proposal.get("meals", [])

    if not (MIN_MEALS <= len(meals) <= MAX_MEALS):
        errors.append(
            f"O plano tem {len(meals)} refeições; são necessárias entre "
            f"{MIN_MEALS} e {MAX_MEALS} refeições."
        )

    orders = [meal.get("order") for meal in meals]
    expected_orders = list(range(1, len(meals) + 1))
    if sorted(orders) != expected_orders:
        errors.append(
            "O campo 'order' das refeições deve ser único e sequencial "
            f"começando em 1 (esperado {expected_orders}, recebido {orders})."
        )

    food_ids_used = [
        item.get("food_id") for meal in meals for item in meal.get("items", [])
    ]
    all_food_ids = {fid for fid in food_ids_used if fid is not None}
    accessible_ids = set(
        Food.objects.filter(
            Q(owner__isnull=True) | Q(owner=user), id__in=all_food_ids, is_active=True
        ).values_list("id", flat=True)
    )
    missing_ids = all_food_ids - accessible_ids
    if missing_ids:
        errors.append(
            "Os seguintes food_id não existem ou não estão acessíveis a este "
            f"aluno: {sorted(missing_ids)}. Use apenas food_id retornados pela "
            "ferramenta buscar_alimento."
        )

    invalid_quantity = False
    for meal in meals:
        for item in meal.get("items", []):
            quantity = item.get("quantity_g")
            if quantity is None or not (0 < quantity <= MAX_QUANTITY_G):
                invalid_quantity = True
                errors.append(
                    f"quantity_g={quantity} inválido para food_id={item.get('food_id')}: "
                    f"deve ser maior que 0 e no máximo {MAX_QUANTITY_G}g."
                )

    # Só soma macros se todos os food_id e quantidades forem válidos, para
    # não mascarar o erro real com um total sem sentido.
    if not missing_ids and not invalid_quantity:
        totals = compute_totals(proposal)

        macro_error = _macro_error(
            "calorias", totals["kcal"], float(metric.calorie_goal), KCAL_TOLERANCE,
            "Reduza as porções para aproximar do alvo calórico.",
            "Aumente as porções para aproximar do alvo calórico.",
            unit="kcal",
        )
        if macro_error:
            errors.append(macro_error)

        macro_error = _macro_error(
            "proteína", totals["protein_g"], float(metric.protein_g), PROTEIN_TOLERANCE,
            "Reduza porções de alimentos ricos em proteína.",
            "Aumente porções de alimentos ricos em proteína.",
        )
        if macro_error:
            errors.append(macro_error)

        macro_error = _macro_error(
            "carboidrato", totals["carbs_g"], float(metric.carbs_g), CARBS_TOLERANCE,
            "Reduza porções de fontes de carboidrato.",
            "Aumente porções de fontes de carboidrato.",
        )
        if macro_error:
            errors.append(macro_error)

        macro_error = _macro_error(
            "gordura", totals["fat_g"], float(metric.fat_g), FAT_TOLERANCE,
            "Reduza porções de fontes de gordura.",
            "Aumente porções de fontes de gordura.",
        )
        if macro_error:
            errors.append(macro_error)

    return errors


def summarize_workout(proposal: dict) -> dict:
    """Equivalente ao compute_totals da dieta — mas treino não tem uma
    métrica agregável comparável a macros (ver apps/coach/agents/
    workout.py), então isto resume contagem de exercícios/séries e os
    grupos musculares cobertos, para o crítico usar como contexto."""
    exercises = proposal.get("exercises", [])
    exercise_ids = [exercise["exercise_id"] for exercise in exercises]
    muscle_groups = sorted(
        Exercise.objects.filter(id__in=exercise_ids)
        .values_list("muscle_group", flat=True)
        .distinct()
    )
    return {
        "exercise_count": len(exercises),
        "total_sets": sum(exercise.get("sets", 0) for exercise in exercises),
        "muscle_groups": muscle_groups,
    }


def validate_workout_plan(proposal: dict, profile, user) -> list[str]:
    """Camada determinística do treino. Diferente de validate_meal_plan,
    NÃO compara contra um alvo numérico externo — valida ESTRUTURA e
    SANIDADE (exercícios existem, quantidade plausível, faixas de
    séries/repetições/descanso, sem duplicar ordem ou repetir exercício em
    excesso). Retorna lista de mensagens de erro ACIONÁVEIS pelo LLM (vazia
    = aprovado)."""
    errors: list[str] = []
    exercises = proposal.get("exercises", [])

    if not (MIN_EXERCISES <= len(exercises) <= MAX_EXERCISES):
        errors.append(
            f"O treino tem {len(exercises)} exercícios; são necessários entre "
            f"{MIN_EXERCISES} e {MAX_EXERCISES} exercícios."
        )

    orders = [exercise.get("order") for exercise in exercises]
    expected_orders = list(range(1, len(exercises) + 1))
    if sorted(orders) != expected_orders:
        errors.append(
            "O campo 'order' dos exercícios deve ser único e sequencial "
            f"começando em 1 (esperado {expected_orders}, recebido {orders})."
        )

    exercise_ids_used = [exercise.get("exercise_id") for exercise in exercises]
    all_exercise_ids = {eid for eid in exercise_ids_used if eid is not None}
    accessible_ids = set(
        Exercise.objects.filter(id__in=all_exercise_ids, is_public=True).values_list(
            "id", flat=True
        )
    )
    missing_ids = all_exercise_ids - accessible_ids
    if missing_ids:
        errors.append(
            "Os seguintes exercise_id não existem ou não estão acessíveis: "
            f"{sorted(missing_ids)}. Use apenas exercise_id retornados pela "
            "ferramenta listar_exercicios."
        )

    repeat_counts = Counter(eid for eid in exercise_ids_used if eid is not None)
    overused = sorted(
        eid for eid, count in repeat_counts.items() if count > MAX_REPEATS_PER_EXERCISE
    )
    if overused:
        errors.append(
            f"Os exercícios {overused} aparecem mais de "
            f"{MAX_REPEATS_PER_EXERCISE} vezes no mesmo treino. Varie os "
            "exercícios."
        )

    min_goal_reps, max_goal_reps = GOAL_REP_RANGES.get(profile.goal, DEFAULT_REP_RANGE)

    for exercise in exercises:
        exercise_id = exercise.get("exercise_id")
        sets = exercise.get("sets")
        reps = exercise.get("reps")
        duration_seconds = exercise.get("duration_seconds")
        rest_seconds = exercise.get("rest_seconds")

        if sets is None or not (MIN_SETS <= sets <= MAX_SETS):
            errors.append(
                f"sets={sets} inválido para exercise_id={exercise_id}: deve "
                f"estar entre {MIN_SETS} e {MAX_SETS}."
            )

        has_reps = reps is not None
        has_duration = duration_seconds is not None
        if has_reps and has_duration:
            errors.append(
                f"exercise_id={exercise_id} tem reps E duration_seconds "
                "preenchidos ao mesmo tempo; informe exatamente um dos dois."
            )
        elif not has_reps and not has_duration:
            errors.append(
                f"exercise_id={exercise_id} não tem reps nem duration_seconds "
                "preenchido; informe exatamente um dos dois."
            )
        elif has_reps and not (min_goal_reps <= reps <= max_goal_reps):
            errors.append(
                f"reps={reps} para exercise_id={exercise_id} está fora da "
                f"faixa típica para o objetivo {profile.get_goal_display()} "
                f"({min_goal_reps}-{max_goal_reps}). Ajuste a quantidade de "
                "repetições."
            )

        if rest_seconds is None or not (MIN_REST_SECONDS <= rest_seconds <= MAX_REST_SECONDS):
            errors.append(
                f"rest_seconds={rest_seconds} inválido para "
                f"exercise_id={exercise_id}: deve estar entre "
                f"{MIN_REST_SECONDS} e {MAX_REST_SECONDS}."
            )

    return errors
