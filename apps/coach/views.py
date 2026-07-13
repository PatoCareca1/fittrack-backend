from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.coach import services
from apps.coach.agents.manager import route
from apps.coach.models import CoachConversation, CoachJob, Intent, MessageRole
from apps.coach.runner import enqueue_plan_job
from apps.coach.serializers import CoachJobSerializer, CoachMessageSerializer

WORKOUT_UNAVAILABLE_MESSAGE = (
    "Ainda não tenho um agente de treino disponível. Em breve você vai poder "
    "pedir um plano de treino por aqui também."
)
OUT_OF_SCOPE_MESSAGE = (
    "Esse assunto está fora do que posso ajudar por aqui. Se for algo sobre "
    "sua saúde, treino ou dieta que precise de acompanhamento próximo, "
    "procure o profissional vinculado à sua conta."
)
AMBIGUOUS_MESSAGE = (
    "Não entendi exatamente o que você precisa. Você quer um plano "
    "alimentar ou um plano de treino? Pode detalhar um pouco mais?"
)

_REPLY_BY_INTENT = {
    Intent.WORKOUT_PLAN: WORKOUT_UNAVAILABLE_MESSAGE,
    Intent.OUT_OF_SCOPE: OUT_OF_SCOPE_MESSAGE,
    Intent.AMBIGUOUS: AMBIGUOUS_MESSAGE,
}


class CoachMessageView(APIView):
    """POST /api/v1/coach/messages/ — recebe a mensagem do aluno, roteia via
    Agente Gerente e, para pedido de dieta, dispara o job assíncrono."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = (request.data.get("message") or "").strip()
        if not message:
            raise ValidationError({"message": "Este campo é obrigatório."})

        conversation = services.get_or_create_conversation(
            request.user, request.data.get("conversation_id")
        )
        services.add_message(conversation, MessageRole.USER, message)

        intent = route(message)

        if intent == Intent.DIET_PLAN:
            job = enqueue_plan_job(request.user, message, conversation=conversation)
            return Response(
                {
                    "job_id": job.id,
                    "conversation_id": conversation.id,
                    "intent": intent,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        reply = _REPLY_BY_INTENT[intent]
        services.add_message(conversation, MessageRole.ASSISTANT, reply)

        return Response(
            {"conversation_id": conversation.id, "intent": intent, "message": reply},
            status=status.HTTP_200_OK,
        )


class CoachJobDetailView(APIView):
    """GET /api/v1/coach/jobs/{id}/ — status do job (só do próprio user)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job = CoachJob.objects.filter(id=pk, user=request.user).first()
        if job is None:
            raise NotFound("Job não encontrado.")
        return Response(CoachJobSerializer(job).data)


class ConversationMessagesView(APIView):
    """GET /api/v1/coach/conversations/{id}/messages/ — histórico (só do
    próprio user)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        conversation = CoachConversation.objects.filter(id=pk, user=request.user).first()
        if conversation is None:
            raise NotFound("Conversa não encontrada.")
        messages = conversation.messages.all()
        return Response(CoachMessageSerializer(messages, many=True).data)
