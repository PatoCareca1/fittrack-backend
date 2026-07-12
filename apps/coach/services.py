from apps.coach.models import AgentRun, CoachConversation, CoachMessage


def create_conversation(user):
    return CoachConversation.objects.create(user=user)


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
