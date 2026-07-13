from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.coach.models import AgentRun, CoachConversation, CoachMessage


def create_conversation(user):
    return CoachConversation.objects.create(user=user)


def get_or_create_conversation(user, conversation_id=None):
    if conversation_id:
        try:
            return CoachConversation.objects.get(id=conversation_id, user=user)
        except CoachConversation.DoesNotExist:
            raise ValidationError({"conversation_id": "Conversa não encontrada."})
    return create_conversation(user)


def add_message(conversation, role, content, agent=""):
    return CoachMessage.objects.create(
        conversation=conversation, role=role, content=content, agent=agent
    )


def record_agent_run(
    *,
    agent,
    provider,
    model,
    conversation=None,
    iterations=1,
    validation_errors=None,
    approved=False,
    input_tokens=0,
    output_tokens=0,
    latency_ms=0,
):
    return AgentRun.objects.create(
        conversation=conversation,
        agent=agent,
        provider=provider,
        model=model,
        iterations=iterations,
        validation_errors=validation_errors or [],
        approved=approved,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )


def create_meal_plan_from_agent(user, result, name="Plano gerado pelo FitTrack Coach"):
    """Persiste um diet.MealPlan a partir de um DietAgentResult aprovado.
    Reaproveita o MealPlanSerializer do app diet para não duplicar a lógica
    de criação de Meal/MealItem."""
    if not result.approved or not result.proposal:
        raise ValidationError("Só é possível salvar um plano alimentar aprovado pelo agente.")

    from apps.diet.serializers import MealPlanSerializer

    data = {
        "name": name,
        "description": result.proposal.get("rationale", ""),
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
            for meal in result.proposal["meals"]
        ],
    }

    with transaction.atomic():
        serializer = MealPlanSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.save(user=user)


def create_workout_from_agent(user, result, name=None):
    """Persiste um workouts.Workout a partir de um WorkoutAgentResult
    aprovado. Reaproveita o WorkoutSerializer do app workouts para não
    duplicar a lógica de criação de WorkoutExercise — espelha
    create_meal_plan_from_agent."""
    if not result.approved or not result.proposal:
        raise ValidationError("Só é possível salvar um treino aprovado pelo agente.")

    from apps.workouts.serializers import WorkoutSerializer

    proposal = result.proposal
    data = {
        "name": name or proposal.get("name") or "Treino gerado pelo FitTrack Coach",
        "description": proposal.get("rationale", ""),
        "exercises": [
            {
                "exercise": exercise["exercise_id"],
                "order": exercise["order"],
                "sets": exercise["sets"],
                "reps": exercise["reps"],
                "duration_seconds": exercise["duration_seconds"],
                "load_kg": exercise["load_kg"],
                "rest_seconds": exercise["rest_seconds"],
            }
            for exercise in proposal["exercises"]
        ],
    }

    with transaction.atomic():
        serializer = WorkoutSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.save(user=user)
