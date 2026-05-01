import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.professional.models import (
    InviteCode,
    LinkStatus,
    MealPlanAssignment,
    ProfessionalLink,
    WorkoutAssignment,
)
from apps.users.models import AccountType, User


def generate_invite(professional: User) -> InviteCode:
    if professional.account_type not in (AccountType.PERSONAL, AccountType.NUTRITIONIST):
        raise PermissionDenied("Apenas profissionais podem gerar convites.")
    return InviteCode.objects.create(
        professional=professional,
        code=secrets.token_urlsafe(8),
        expires_at=timezone.now() + timedelta(days=7),
    )


def accept_invite(student: User, code: str) -> ProfessionalLink:
    if student.account_type != AccountType.USER:
        raise PermissionDenied("Apenas usuários comuns podem aceitar convites.")

    try:
        invite = InviteCode.objects.select_related("professional").get(code=code)
    except InviteCode.DoesNotExist:
        raise ValidationError("Código inválido.")

    if not invite.is_valid():
        raise ValidationError("Código expirado ou já utilizado.")

    professional = invite.professional

    # RN05: máximo 1 personal + 1 nutricionista por aluno
    already_linked = ProfessionalLink.objects.filter(
        student=student,
        professional__account_type=professional.account_type,
        status=LinkStatus.ACTIVE,
    ).exists()
    if already_linked:
        raise ValidationError(
            f"Você já possui um(a) {professional.get_account_type_display()} vinculado(a)."
        )

    link = ProfessionalLink.objects.create(student=student, professional=professional)
    invite.used_by = student
    invite.save()
    from apps.notifications.services import notify_link_accepted
    notify_link_accepted(link)
    return link


def cancel_link(link: ProfessionalLink, user: User) -> None:
    if link.student != user and link.professional != user:
        raise PermissionDenied("Você não tem permissão para cancelar este vínculo.")
    link.status = LinkStatus.CANCELLED
    link.save()


def assign_workout(professional: User, link_id: int, workout_id: int) -> WorkoutAssignment:
    from apps.workouts.models import Workout

    try:
        link = ProfessionalLink.objects.get(
            id=link_id, professional=professional, status=LinkStatus.ACTIVE
        )
    except ProfessionalLink.DoesNotExist:
        raise ValidationError("Vínculo ativo não encontrado.")

    try:
        workout = Workout.objects.get(id=workout_id, user=professional)
    except Workout.DoesNotExist:
        raise ValidationError("Treino não encontrado ou não pertence a você.")

    assignment = WorkoutAssignment.objects.create(link=link, workout=workout)

    from apps.notifications.services import notify_workout_assigned
    notify_workout_assigned(assignment)
    return assignment


def assign_meal_plan(professional: User, link_id: int, plan_id: int) -> MealPlanAssignment:
    from apps.diet.models import MealPlan

    try:
        link = ProfessionalLink.objects.get(
            id=link_id, professional=professional, status=LinkStatus.ACTIVE
        )
    except ProfessionalLink.DoesNotExist:
        raise ValidationError("Vínculo ativo não encontrado.")

    try:
        plan = MealPlan.objects.get(id=plan_id, user=professional)
    except MealPlan.DoesNotExist:
        raise ValidationError("Plano não encontrado ou não pertence a você.")

    assignment = MealPlanAssignment.objects.create(link=link, meal_plan=plan)

    from apps.notifications.services import notify_meal_plan_assigned
    notify_meal_plan_assigned(assignment)
    return assignment