from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.body.models import BodyMetric
from apps.coach.mcp.permissions import get_active_link_or_error, require_nutritionist
from apps.coach.tools import buscar_alimento as _buscar_alimento_catalogo
from apps.coach.tools import listar_exercicios as _listar_exercicios_catalogo
from apps.coach.validators import validate_meal_plan
from apps.professional.models import DietAssignment, LinkStatus, ProfessionalLink

# Schemas neutros no mesmo formato usado em apps/coach/tools.py
# (name/description/inputSchema em JSON Schema puro) — o host MCP usa isto
# para descrever as ferramentas ao seu próprio LLM.
TOOLS = [
    {
        "name": "listar_alunos",
        "description": (
            "Lista os alunos com vínculo profissional ATIVO com o profissional "
            "autenticado (id, nome, email, objetivo, data da última métrica)."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "obter_metricas",
        "description": (
            "Histórico de métricas corporais (peso, %gordura, massa magra) e "
            "os alvos nutricionais já calculados (kcal, proteína, carboidrato, "
            "gordura) de um aluno. Exige vínculo profissional ativo com o aluno."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer"},
                "limit": {"type": "integer", "description": "Padrão 10, máximo 100."},
            },
            "required": ["student_id"],
        },
    },
    {
        "name": "buscar_alimento",
        "description": (
            "Busca no catálogo de alimentos (TACO + cadastros próprios do "
            "profissional autenticado), por nome. Dado público — não exige "
            "vínculo com nenhum aluno."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "description": "Padrão 10."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "listar_exercicios",
        "description": (
            "Catálogo público de exercícios, opcionalmente filtrado por grupo "
            "muscular. Dado público — não exige vínculo com nenhum aluno."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"muscle_group": {"type": "string"}},
        },
    },
    {
        "name": "criar_plano_alimentar",
        "description": (
            "Cria um plano alimentar para um aluno vinculado. Exige vínculo "
            "ativo E que o profissional autenticado seja nutricionista. O "
            "plano é validado pela MESMA regra determinística que valida os "
            "planos do agente de IA interno do FitTrack (soma de macros a "
            "partir do banco, dentro dos alvos calculados do aluno) — uma "
            "proposta fora dos alvos é rejeitada com os mesmos erros "
            "acionáveis, não persiste nada parcial."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer"},
                "meals": {
                    "type": "array",
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
            },
            "required": ["student_id", "meals"],
        },
    },
]


def listar_alunos(user, arguments: dict) -> list[dict]:
    links = (
        ProfessionalLink.objects.filter(professional=user, status=LinkStatus.ACTIVE)
        .select_related("student", "student__profile")
    )
    result = []
    for link in links:
        student = link.student
        last_metric = BodyMetric.objects.filter(user=student).order_by("-date").first()
        profile = getattr(student, "profile", None)
        result.append(
            {
                "id": student.id,
                "nome": student.get_full_name() or student.email,
                "email": student.email,
                "objetivo": profile.get_goal_display() if profile else None,
                "ultima_metrica_em": last_metric.date.isoformat() if last_metric else None,
            }
        )
    return result


def metric_history(student_id: int, limit: int) -> list[dict]:
    limit = max(1, min(int(limit or 10), 100))
    metrics = BodyMetric.objects.filter(user_id=student_id).order_by("-date")[:limit]
    return [
        {
            "date": metric.date.isoformat(),
            "weight_kg": float(metric.weight_kg),
            "body_fat_pct": float(metric.body_fat_pct) if metric.body_fat_pct is not None else None,
            "muscle_mass_kg": (
                float(metric.muscle_mass_kg) if metric.muscle_mass_kg is not None else None
            ),
            "calorie_goal": metric.calorie_goal,
            "protein_g": metric.protein_g,
            "carbs_g": metric.carbs_g,
            "fat_g": metric.fat_g,
        }
        for metric in metrics
    ]


def obter_metricas(user, arguments: dict) -> list[dict]:
    student_id = arguments.get("student_id")
    if student_id is None:
        raise ValidationError({"student_id": "Campo obrigatório."})
    get_active_link_or_error(user, student_id)
    return metric_history(student_id, arguments.get("limit", 10))


def buscar_alimento(user, arguments: dict) -> list[dict]:
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)
    return _buscar_alimento_catalogo(user, query, limit)


def listar_exercicios(user, arguments: dict) -> list[dict]:
    # Reaproveita a mesma consulta usada pelo Agente de Treino interno
    # (apps/coach/tools.py) — não duplicamos a lógica de catálogo aqui.
    return _listar_exercicios_catalogo(
        arguments.get("muscle_group"), arguments.get("limit", 30)
    )


def criar_plano_alimentar(user, arguments: dict) -> dict:
    student_id = arguments.get("student_id")
    meals = arguments.get("meals")
    if student_id is None or not meals:
        raise ValidationError({"student_id/meals": "Campos obrigatórios."})

    require_nutritionist(user)
    link = get_active_link_or_error(user, student_id)
    student = link.student

    metric = BodyMetric.objects.filter(user=student).order_by("-date").first()
    if metric is None:
        raise ValidationError(
            f"O aluno {student_id} ainda não tem nenhuma medida corporal "
            "registrada; não é possível validar o plano contra alvos "
            "nutricionais."
        )

    # Mesma validação determinística usada pelo agente de dieta interno
    # (apps/coach/agents/diet.py) — não duplicamos a regra.
    errors = validate_meal_plan({"meals": meals}, metric, student)
    if errors:
        raise ValidationError({"meals": errors})

    from apps.diet.serializers import MealPlanSerializer

    data = {
        "name": "Plano alimentar (criado via MCP)",
        "description": "",
        "meals": [
            {
                "name": meal["name"],
                "time": meal["time"],
                "order": meal["order"],
                "items": [
                    {"food": item["food_id"], "quantity_g": item["quantity_g"]}
                    for item in meal["items"]
                ],
            }
            for meal in meals
        ],
    }

    with transaction.atomic():
        serializer = MealPlanSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        # O plano pertence ao profissional que o criou (mesma semântica de
        # apps.professional.services.assign_meal_plan) e é distribuído ao
        # aluno via DietAssignment — somente leitura para o aluno (RN09).
        meal_plan = serializer.save(user=user)
        DietAssignment.objects.create(
            link=link, meal_plan=meal_plan, notes="Criado via MCP."
        )

    return {
        "meal_plan_id": meal_plan.id,
        "student_id": student.id,
        "meals_count": len(meals),
    }


_HANDLERS = {
    "listar_alunos": listar_alunos,
    "obter_metricas": obter_metricas,
    "buscar_alimento": buscar_alimento,
    "listar_exercicios": listar_exercicios,
    "criar_plano_alimentar": criar_plano_alimentar,
}


def call_tool(name: str, arguments: dict, user):
    try:
        handler = _HANDLERS[name]
    except KeyError:
        raise ValidationError({"name": f"Ferramenta desconhecida: '{name}'."})
    return handler(user, arguments or {})
