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
