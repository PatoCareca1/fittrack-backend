import secrets
import string

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.professional.models import LinkStatus, ProfessionalLink, WorkoutAssignment
from apps.users.models import AccountType, User
from apps.workouts.models import Workout

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_invite_code() -> str:
    while True:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
        if not ProfessionalLink.objects.filter(invite_code=code).exists():
            return code


def create_invite(professional: User) -> ProfessionalLink:
    if professional.account_type == AccountType.USER:
        raise PermissionDenied("Apenas profissionais podem criar convites.")
    return ProfessionalLink.objects.create(
        professional=professional, invite_code=_generate_invite_code()
    )


@transaction.atomic
def accept_invite(student: User, invite_code: str) -> ProfessionalLink:
    try:
        link = ProfessionalLink.objects.select_for_update().get(
            invite_code=invite_code.strip().upper(), status=LinkStatus.PENDING
        )
    except ProfessionalLink.DoesNotExist:
        raise ValidationError({"invite_code": "Código de convite inválido ou já usado."})

    if link.professional_id == student.id:
        raise ValidationError({"invite_code": "Você não pode se vincular a si mesmo."})

    # RN05: no máximo 1 profissional ativo de cada tipo por aluno.
    already = ProfessionalLink.objects.filter(
        student=student,
        status=LinkStatus.ACTIVE,
        professional__account_type=link.professional.account_type,
    ).exists()
    if already:
        kind = link.professional.get_account_type_display()
        raise ValidationError(
            {"invite_code": f"Você já está vinculado a um {kind}."}
        )

    link.student = student
    link.status = LinkStatus.ACTIVE
    link.accepted_at = timezone.now()
    link.save(update_fields=["student", "status", "accepted_at"])
    return link


def revoke_link(link: ProfessionalLink, actor: User) -> ProfessionalLink:
    if actor.id not in (link.professional_id, link.student_id):
        raise PermissionDenied("Somente as partes do vínculo podem desvinculá-lo.")
    link.status = LinkStatus.REVOKED
    link.revoked_at = timezone.now()
    link.save(update_fields=["status", "revoked_at"])
    link.workout_assignments.update(is_active=False)
    return link


def assign_workout(
    professional: User, link_id: int, workout_id: int, notes: str = ""
) -> WorkoutAssignment:
    try:
        link = ProfessionalLink.objects.get(
            id=link_id, professional=professional, status=LinkStatus.ACTIVE
        )
    except ProfessionalLink.DoesNotExist:
        raise ValidationError({"link": "Vínculo ativo não encontrado."})
    try:
        workout = Workout.objects.get(id=workout_id, user=professional)
    except Workout.DoesNotExist:
        raise ValidationError({"workout": "Treino não encontrado."})
    return WorkoutAssignment.objects.create(link=link, workout=workout, notes=notes)
