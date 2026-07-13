import json
import re

from rest_framework.exceptions import NotFound

from apps.coach.mcp.permissions import get_active_link_or_error
from apps.coach.mcp.tools import metric_history
from apps.professional.models import LinkStatus, ProfessionalLink
from apps.users.models import User

RESOURCE_URI_RE = re.compile(r"^fittrack://aluno/(?P<student_id>\d+)/(?P<kind>perfil|metricas)$")


def list_resources(user) -> list[dict]:
    """Lista os recursos concretos disponíveis para o profissional
    autenticado: perfil e métricas de cada aluno com vínculo ATIVO."""
    links = ProfessionalLink.objects.filter(
        professional=user, status=LinkStatus.ACTIVE
    ).select_related("student")

    resources = []
    for link in links:
        student = link.student
        label = student.get_full_name() or student.email
        resources.append(
            {
                "uri": f"fittrack://aluno/{student.id}/perfil",
                "name": f"Perfil de {label}",
                "mimeType": "application/json",
            }
        )
        resources.append(
            {
                "uri": f"fittrack://aluno/{student.id}/metricas",
                "name": f"Métricas de {label}",
                "mimeType": "application/json",
            }
        )
    return resources


def _read_profile(student_id: int) -> dict:
    student = User.objects.select_related("profile").get(id=student_id)
    profile = student.profile
    history = metric_history(student_id, limit=1)
    return {
        "id": student.id,
        "nome": student.get_full_name() or student.email,
        "email": student.email,
        "objetivo": profile.get_goal_display(),
        "nivel_atividade": profile.get_activity_level_display(),
        "ultima_metrica_em": history[0]["date"] if history else None,
    }


def read_resource(user, uri: str) -> dict:
    match = RESOURCE_URI_RE.match(uri or "")
    if not match:
        raise NotFound(f"URI de recurso desconhecida ou malformada: {uri!r}")

    student_id = int(match.group("student_id"))
    kind = match.group("kind")

    # RN05: mesma checagem de vínculo das tools.
    get_active_link_or_error(user, student_id)

    if kind == "perfil":
        payload = _read_profile(student_id)
    else:
        payload = {"metricas": metric_history(student_id, limit=10)}

    return {
        "uri": uri,
        "mimeType": "application/json",
        "text": json.dumps(payload, ensure_ascii=False),
    }
