import json

DIET_PLAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "meals": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "time": {"type": "string", "description": "Formato HH:MM"},
                    "order": {"type": "integer"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "food_id": {"type": "integer"},
                                "quantity_g": {"type": "number"},
                            },
                            "required": ["food_id", "quantity_g"],
                        },
                    },
                },
                "required": ["name", "time", "order", "items"],
            },
        },
        "rationale": {
            "type": "string",
            "description": "Explicação curta ao aluno, em português.",
        },
    },
    "required": ["meals", "rationale"],
}


def strip_code_fences(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    lines = lines[1:]  # remove a cerca de abertura (``` ou ```json)
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _require_str(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"O campo '{field}' é obrigatório e deve ser uma string não vazia.")
    return value


def _parse_item(item: dict) -> dict:
    if not isinstance(item, dict):
        raise ValueError("Cada item de uma refeição deve ser um objeto JSON.")
    try:
        food_id = int(item["food_id"])
        quantity_g = float(item["quantity_g"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Item malformado (esperado food_id e quantity_g numéricos): {exc}") from exc
    # Quaisquer outros campos (ex.: kcal, protein_g) enviados pelo LLM são
    # descartados aqui — o único dado confiável de macro vem do banco.
    return {"food_id": food_id, "quantity_g": quantity_g}


def _parse_meal(meal: dict) -> dict:
    if not isinstance(meal, dict):
        raise ValueError("Cada refeição deve ser um objeto JSON.")
    name = _require_str(meal.get("name"), "meals[].name")
    time_str = _require_str(meal.get("time"), "meals[].time")
    try:
        order = int(meal["order"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"O campo 'meals[].order' é obrigatório e deve ser inteiro: {exc}") from exc

    items_raw = meal.get("items")
    if not isinstance(items_raw, list):
        raise ValueError("O campo 'meals[].items' deve ser uma lista.")

    return {
        "name": name,
        "time": time_str,
        "order": order,
        "items": [_parse_item(item) for item in items_raw],
    }


def parse_diet_output(raw: str) -> dict:
    """Parse defensivo da resposta do agente de dieta: tolera cercas de
    markdown e valida a forma mínima do contrato. Levanta ValueError com
    mensagem clara em caso de resposta malformada."""
    text = strip_code_fences(raw or "")
    if not text:
        raise ValueError("Resposta vazia.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("A resposta deve ser um objeto JSON no formato {meals, rationale}.")

    meals_raw = data.get("meals")
    if not isinstance(meals_raw, list) or not meals_raw:
        raise ValueError("O campo 'meals' é obrigatório e deve ser uma lista não vazia.")

    rationale = _require_str(data.get("rationale"), "rationale")

    return {
        "meals": [_parse_meal(meal) for meal in meals_raw],
        "rationale": rationale,
    }


WORKOUT_PLAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "exercises": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "exercise_id": {"type": "integer"},
                    "order": {"type": "integer"},
                    "sets": {"type": "integer"},
                    "reps": {"type": ["integer", "null"]},
                    "duration_seconds": {
                        "type": ["integer", "null"],
                        "description": "Para exercícios por tempo (prancha, etc.)",
                    },
                    "load_kg": {"type": ["number", "null"]},
                    "rest_seconds": {"type": "integer"},
                },
                "required": ["exercise_id", "order", "sets", "rest_seconds"],
            },
        },
        "rationale": {
            "type": "string",
            "description": "Explicação curta ao aluno, em português.",
        },
    },
    "required": ["name", "exercises", "rationale"],
}


def _to_int(value, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"O campo '{field}' deve ser inteiro: {exc}") from exc


def _to_float(value, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"O campo '{field}' deve ser numérico: {exc}") from exc


def _parse_workout_exercise(exercise: dict) -> dict:
    if not isinstance(exercise, dict):
        raise ValueError("Cada exercício deve ser um objeto JSON.")
    try:
        exercise_id = int(exercise["exercise_id"])
        order = int(exercise["order"])
        sets = int(exercise["sets"])
        rest_seconds = int(exercise["rest_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "Exercício malformado (esperado exercise_id, order, sets e "
            f"rest_seconds inteiros): {exc}"
        ) from exc

    reps_raw = exercise.get("reps")
    reps = None if reps_raw in (None, "") else _to_int(reps_raw, "exercises[].reps")

    duration_raw = exercise.get("duration_seconds")
    duration_seconds = (
        None
        if duration_raw in (None, "")
        else _to_int(duration_raw, "exercises[].duration_seconds")
    )

    load_raw = exercise.get("load_kg")
    load_kg = None if load_raw in (None, "") else _to_float(load_raw, "exercises[].load_kg")

    # Quaisquer outros campos (ex.: nome do exercício, muscle_group)
    # enviados pelo LLM são descartados aqui — mesmo princípio da dieta: o
    # único dado confiável sobre o exercício vem do banco.
    return {
        "exercise_id": exercise_id,
        "order": order,
        "sets": sets,
        "reps": reps,
        "duration_seconds": duration_seconds,
        "load_kg": load_kg,
        "rest_seconds": rest_seconds,
    }


def parse_workout_output(raw: str) -> dict:
    """Parse defensivo da resposta do agente de treino — espelha
    parse_diet_output. Levanta ValueError com mensagem clara em caso de
    resposta malformada."""
    text = strip_code_fences(raw or "")
    if not text:
        raise ValueError("Resposta vazia.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            "A resposta deve ser um objeto JSON no formato {name, exercises, rationale}."
        )

    name = _require_str(data.get("name"), "name")

    exercises_raw = data.get("exercises")
    if not isinstance(exercises_raw, list) or not exercises_raw:
        raise ValueError("O campo 'exercises' é obrigatório e deve ser uma lista não vazia.")

    rationale = _require_str(data.get("rationale"), "rationale")

    return {
        "name": name,
        "exercises": [_parse_workout_exercise(exercise) for exercise in exercises_raw],
        "rationale": rationale,
    }
