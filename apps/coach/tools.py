from django.db.models import Q

from apps.diet.models import Food

DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50


def buscar_alimento(user, query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> list[dict]:
    """Busca alimentos públicos ou cadastrados pelo próprio usuário pelo nome."""
    limit = max(1, min(int(limit or DEFAULT_SEARCH_LIMIT), MAX_SEARCH_LIMIT))
    foods = (
        Food.objects.filter(is_active=True)
        .filter(Q(owner__isnull=True) | Q(owner=user))
        .filter(name__icontains=query or "")
        .order_by("name")[:limit]
    )
    return [
        {
            "id": food.id,
            "name": food.name,
            "brand": food.brand,
            "kcal": float(food.kcal),
            "protein_g": float(food.protein_g),
            "carbs_g": float(food.carbs_g),
            "fat_g": float(food.fat_g),
        }
        for food in foods
    ]


# Schema neutro (independente de fornecedor): "parameters" é JSON Schema puro.
# Cada provider traduz para o formato nativo dele (ver providers/*.py).
DIET_TOOL_SCHEMAS = [
    {
        "name": "buscar_alimento",
        "description": (
            "Busca alimentos disponíveis (públicos ou cadastrados pelo próprio "
            "aluno) pelo nome. Retorna id, nome, marca e valores nutricionais "
            "por 100g. Use apenas os food_id retornados aqui para montar o "
            "plano — nunca invente um id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termo de busca, ex.: 'frango', 'arroz'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Número máximo de resultados (padrão 10).",
                },
            },
            "required": ["query"],
        },
    }
]

_TOOLS_BY_NAME = {
    "buscar_alimento": lambda arguments, user: {
        "results": buscar_alimento(
            user,
            arguments.get("query", ""),
            arguments.get("limit", DEFAULT_SEARCH_LIMIT),
        )
    },
}


def execute_tool(name: str, arguments: dict, user) -> dict:
    try:
        handler = _TOOLS_BY_NAME[name]
    except KeyError:
        raise ValueError(
            f"Ferramenta desconhecida: '{name}'. "
            f"Ferramentas disponíveis: {', '.join(_TOOLS_BY_NAME)}."
        )
    return handler(arguments or {}, user)
