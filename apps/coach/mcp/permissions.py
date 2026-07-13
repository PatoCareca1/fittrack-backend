from rest_framework.exceptions import PermissionDenied

from apps.professional.models import LinkStatus, ProfessionalLink
from apps.users.models import AccountType


def get_active_link_or_error(professional, student_id) -> ProfessionalLink:
    """RN05: um profissional só acessa dados de um aluno com quem tem
    ProfessionalLink ATIVO. Sem vínculo, erro explícito — nunca uma lista
    vazia silenciosa que mascare o motivo real."""
    link = (
        ProfessionalLink.objects.filter(
            professional=professional, student_id=student_id, status=LinkStatus.ACTIVE
        )
        .select_related("student")
        .first()
    )
    if link is None:
        raise PermissionDenied(
            f"Você não tem vínculo ativo com o aluno de id {student_id}."
        )
    return link


def require_nutritionist(professional) -> None:
    if professional.account_type != AccountType.NUTRITIONIST:
        raise PermissionDenied(
            "Apenas nutricionistas podem criar planos alimentares para alunos."
        )
