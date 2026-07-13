# A execução do job roda numa threading.Thread daemon. Isso é uma decisão
# deliberada de PRAZO — evita ter que subir um broker de fila (Celery/RQ +
# Redis/RabbitMQ) só para esta etapa do projeto — e NÃO é a escolha certa
# para produção: sob carga real uma thread por request não escala, não tem
# retry, e o processo morre junto com o worker se o servidor reiniciar no
# meio da execução.
#
# A fronteira fica isolada de propósito: todo o resto do app (views,
# services) só conhece `enqueue_plan_job()`. Trocar a implementação por
# Celery é mexer SÓ nesta função — nada fora daqui precisa saber como o job
# é executado.

import threading

from django.db import connection

from apps.coach.agents.diet import generate_and_review_meal_plan
from apps.coach.models import CoachAgent, CoachJob, CoachJobStatus, Intent, MessageRole
from apps.coach.services import add_message, create_meal_plan_from_agent


def run_plan_job(job_id: int, message: str) -> None:
    """O trabalho de fato — não fecha conexão de banco nenhuma, porque quem
    chama pode estar na mesma thread (é o caso dos testes, que chamam esta
    função diretamente, de forma síncrona). Fechar a conexão aqui derrubaria
    a conexão de quem chamou. Ver `_run_plan_job_in_thread` para o wrapper
    usado de fato pela thread em background."""
    try:
        job = CoachJob.objects.select_related("user", "conversation").get(id=job_id)
        job.status = CoachJobStatus.RUNNING
        job.save(update_fields=["status", "updated_at"])

        result = generate_and_review_meal_plan(job.user, goal_note=message)

        if result.approved:
            meal_plan = create_meal_plan_from_agent(job.user, result)
            job.result = {
                "meal_plan_id": meal_plan.id,
                "totals": result.totals,
                "critic_summary": result.critic_summary,
                "issues": result.issues,
                "diet_iterations": result.diet_iterations,
                "critic_rounds": result.critic_rounds,
            }
            rationale = (result.proposal or {}).get("rationale", "")
            content = "\n\n".join(part for part in (rationale, result.critic_summary) if part)
            if job.conversation_id:
                add_message(
                    job.conversation,
                    MessageRole.ASSISTANT,
                    content or "Seu plano alimentar foi gerado com sucesso.",
                    agent=CoachAgent.DIET,
                )
        else:
            # O pipeline rodou até o fim sem erro de sistema — só não
            # produziu um plano aprovado. Isso é um resultado válido do
            # job, não uma falha: "failed" fica reservado para exceções.
            job.result = {
                "totals": result.totals,
                "critic_summary": result.critic_summary,
                "issues": result.issues,
                "errors": result.errors,
                "diet_iterations": result.diet_iterations,
                "critic_rounds": result.critic_rounds,
            }
            if job.conversation_id:
                add_message(
                    job.conversation,
                    MessageRole.ASSISTANT,
                    "Não consegui montar um plano alimentar aprovado desta vez. "
                    "Tente detalhar melhor suas preferências e peça novamente.",
                    agent=CoachAgent.DIET,
                )

        job.status = CoachJobStatus.SUCCEEDED
        job.save(update_fields=["status", "result", "updated_at"])
    except Exception as exc:
        CoachJob.objects.filter(id=job_id).update(status=CoachJobStatus.FAILED, error=str(exc))


def _run_plan_job_in_thread(job_id: int, message: str) -> None:
    """Alvo real da threading.Thread: roda o job e, ao final, fecha a
    conexão de banco desta thread — cada thread abre a sua própria conexão
    e o Django não a libera sozinho quando a thread termina."""
    try:
        run_plan_job(job_id, message)
    finally:
        connection.close()


def enqueue_plan_job(user, message: str, conversation=None) -> CoachJob:
    job = CoachJob.objects.create(
        user=user,
        conversation=conversation,
        intent=Intent.DIET_PLAN,
        status=CoachJobStatus.PENDING,
    )
    thread = threading.Thread(target=_run_plan_job_in_thread, args=(job.id, message), daemon=True)
    thread.start()
    return job
