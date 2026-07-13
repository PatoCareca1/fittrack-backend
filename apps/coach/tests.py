import json
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.body.models import BodyMetric
from apps.coach.agents.critic import review_meal_plan, review_workout_plan
from apps.coach.agents.diet import generate_and_review_meal_plan, generate_meal_plan
from apps.coach.agents.manager import route
from apps.coach.agents.workout import generate_and_review_workout_plan, generate_workout_plan
from apps.coach.models import (
    AgentRun,
    CoachAgent,
    CoachConversation,
    CoachJob,
    CoachJobStatus,
    CoachMessage,
    Intent,
    MessageRole,
)
from apps.coach.providers.anthropic_provider import AnthropicProvider
from apps.coach.providers.base import LLMResponse
from apps.coach.providers.gemini_provider import GeminiProvider
from apps.coach.providers.registry import get_provider
from apps.coach.runner import run_plan_job
from apps.coach.validators import (
    compute_totals,
    summarize_workout,
    validate_meal_plan,
    validate_workout_plan,
)
from apps.diet.models import Food, FoodSource, MealPlan
from apps.users.models import User
from apps.workouts.models import Exercise, MuscleGroup, Workout


class ProviderRegistryTests(TestCase):
    @override_settings(ANTHROPIC_API_KEY="anthropic-key")
    def test_resolves_anthropic_provider_by_name(self):
        provider = get_provider("anthropic")
        self.assertIsInstance(provider, AnthropicProvider)
        self.assertEqual(provider.api_key, "anthropic-key")

    @override_settings(GEMINI_API_KEY="gemini-key")
    def test_resolves_gemini_provider_by_name(self):
        provider = get_provider("gemini")
        self.assertIsInstance(provider, GeminiProvider)
        self.assertEqual(provider.api_key, "gemini-key")

    def test_unknown_provider_raises_clear_error(self):
        with self.assertRaises(ValueError) as ctx:
            get_provider("openai")
        self.assertIn("openai", str(ctx.exception))


class AnthropicProviderTests(TestCase):
    @patch("apps.coach.providers.anthropic_provider.httpx.post")
    def test_complete_parses_text_and_usage(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Olá!"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_post.return_value = mock_response

        provider = AnthropicProvider(api_key="fake-key")
        result = provider.complete(system="Você é um coach.", messages=[{"role": "user", "content": "Oi"}])

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.text, "Olá!")
        self.assertEqual(result.tool_calls, [])
        self.assertEqual(result.usage["input_tokens"], 10)
        mock_response.raise_for_status.assert_called_once()
        mock_post.assert_called_once()


class GeminiProviderTests(TestCase):
    @patch("apps.coach.providers.gemini_provider.httpx.post")
    def test_complete_parses_text_from_candidates(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Olá!"}]}}],
            "usageMetadata": {"promptTokenCount": 8},
        }
        mock_post.return_value = mock_response

        provider = GeminiProvider(api_key="fake-key")
        result = provider.complete(system="Você é um coach.", messages=[{"role": "user", "content": "Oi"}])

        self.assertEqual(result.text, "Olá!")
        self.assertEqual(result.usage["promptTokenCount"], 8)
        mock_response.raise_for_status.assert_called_once()


class CoachModelsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")

    def test_conversation_and_message_persist(self):
        conversation = CoachConversation.objects.create(user=self.user)
        message = CoachMessage.objects.create(
            conversation=conversation,
            role=MessageRole.USER,
            content="Quero emagrecer.",
        )
        self.assertEqual(CoachConversation.objects.count(), 1)
        self.assertEqual(conversation.messages.count(), 1)
        self.assertEqual(message.agent, "")

    def test_agent_run_persists_with_defaults(self):
        conversation = CoachConversation.objects.create(user=self.user)
        run = AgentRun.objects.create(
            conversation=conversation,
            agent=CoachAgent.MANAGER,
            provider="anthropic",
            model="claude-sonnet-4-5",
        )
        self.assertEqual(run.iterations, 1)
        self.assertEqual(run.validation_errors, [])
        self.assertFalse(run.approved)
        self.assertEqual(AgentRun.objects.count(), 1)

    def test_agent_run_conversation_is_optional(self):
        run = AgentRun.objects.create(
            agent=CoachAgent.CRITIC,
            provider="gemini",
            model="gemini-2.5-flash",
        )
        self.assertIsNone(run.conversation)


def _make_metric(user, **overrides):
    defaults = dict(
        weight_kg=80,
        bmr_calculated=1600,
        tdee=2000,
        calorie_goal=1500,
        protein_g=80,
        carbs_g=140,
        fat_g=50,
    )
    defaults.update(overrides)
    return BodyMetric.objects.create(user=user, **defaults)


class DietFixturesMixin:
    def _make_foods(self):
        self.protein_food = Food.objects.create(
            name="Frango grelhado", source=FoodSource.TACO,
            kcal=200, protein_g=40, carbs_g=0, fat_g=0,
        )
        self.carb_food = Food.objects.create(
            name="Arroz branco", source=FoodSource.TACO,
            kcal=130, protein_g=0, carbs_g=28, fat_g=0,
        )
        self.fat_food = Food.objects.create(
            name="Azeite", source=FoodSource.TACO,
            kcal=900, protein_g=0, carbs_g=0, fat_g=100,
        )

    def _valid_proposal(self, extra_item_fields=None):
        extra = extra_item_fields or {}
        return {
            "meals": [
                {
                    "name": "Café da manhã", "time": "08:00", "order": 1,
                    "items": [{"food_id": self.protein_food.id, "quantity_g": 200, **extra}],
                },
                {
                    "name": "Almoço", "time": "12:00", "order": 2,
                    "items": [{"food_id": self.carb_food.id, "quantity_g": 500, **extra}],
                },
                {
                    "name": "Jantar", "time": "19:00", "order": 3,
                    "items": [{"food_id": self.fat_food.id, "quantity_g": 50, **extra}],
                },
            ],
            "rationale": "Plano balanceado para o objetivo do aluno.",
        }


class WorkoutFixturesMixin:
    def _make_exercises(self):
        self.squat = Exercise.objects.create(
            name="Agachamento livre", muscle_group=MuscleGroup.QUADS,
            icon_slug="agachamento-livre-coach-test",
        )
        self.bench = Exercise.objects.create(
            name="Supino reto", muscle_group=MuscleGroup.CHEST,
            icon_slug="supino-reto-coach-test",
        )
        self.row = Exercise.objects.create(
            name="Remada curvada", muscle_group=MuscleGroup.BACK,
            icon_slug="remada-curvada-coach-test",
        )
        self.plank = Exercise.objects.create(
            name="Prancha", muscle_group=MuscleGroup.CORE,
            icon_slug="prancha-coach-test",
        )

    def _valid_workout_proposal(self, extra_exercise_fields=None):
        extra = extra_exercise_fields or {}
        return {
            "name": "Treino full body",
            "exercises": [
                {
                    "exercise_id": self.squat.id, "order": 1, "sets": 3,
                    "reps": 10, "duration_seconds": None, "load_kg": None,
                    "rest_seconds": 60, **extra,
                },
                {
                    "exercise_id": self.bench.id, "order": 2, "sets": 3,
                    "reps": 10, "duration_seconds": None, "load_kg": None,
                    "rest_seconds": 60, **extra,
                },
                {
                    "exercise_id": self.row.id, "order": 3, "sets": 3,
                    "reps": 10, "duration_seconds": None, "load_kg": None,
                    "rest_seconds": 60, **extra,
                },
                {
                    "exercise_id": self.plank.id, "order": 4, "sets": 3,
                    "reps": None, "duration_seconds": 30, "load_kg": None,
                    "rest_seconds": 45, **extra,
                },
            ],
            "rationale": "Treino balanceado para o objetivo do aluno.",
        }


class ValidateMealPlanTests(DietFixturesMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")
        self.other = User.objects.create_user(email="outro@test.dev", password="x")
        self._make_foods()
        self.private_food = Food.objects.create(
            name="Marmita da mãe", source=FoodSource.CUSTOM, owner=self.other,
            kcal=300, protein_g=20, carbs_g=30, fat_g=10,
        )
        self.metric = _make_metric(self.user)

    def test_approves_correct_plan(self):
        errors = validate_meal_plan(self._valid_proposal(), self.metric, self.user)
        self.assertEqual(errors, [])

    def test_rejects_nonexistent_food_id(self):
        proposal = self._valid_proposal()
        proposal["meals"][0]["items"][0]["food_id"] = 999999
        errors = validate_meal_plan(proposal, self.metric, self.user)
        self.assertTrue(any("999999" in error for error in errors))

    def test_rejects_other_users_private_food(self):
        proposal = self._valid_proposal()
        proposal["meals"][0]["items"][0]["food_id"] = self.private_food.id
        errors = validate_meal_plan(proposal, self.metric, self.user)
        self.assertTrue(any(str(self.private_food.id) in error for error in errors))

    def test_rejects_kcal_out_of_range_with_numbers_in_message(self):
        proposal = self._valid_proposal()
        proposal["meals"][0]["items"][0]["quantity_g"] = 2000
        errors = validate_meal_plan(proposal, self.metric, self.user)
        kcal_errors = [error for error in errors if "calorias" in error]
        self.assertTrue(kcal_errors)
        self.assertIn(str(self.metric.calorie_goal), kcal_errors[0])

    def test_rejects_duplicate_order(self):
        proposal = self._valid_proposal()
        proposal["meals"][1]["order"] = 1
        errors = validate_meal_plan(proposal, self.metric, self.user)
        self.assertTrue(any("order" in error for error in errors))


class ComputeTotalsTests(TestCase):
    def test_sums_from_database(self):
        food = Food.objects.create(
            name="Ovo cozido", source=FoodSource.TACO,
            kcal=155, protein_g=13, carbs_g=1.1, fat_g=11,
        )
        proposal = {
            "meals": [
                {
                    "name": "Café", "time": "08:00", "order": 1,
                    "items": [{"food_id": food.id, "quantity_g": 200}],
                },
            ],
        }
        totals = compute_totals(proposal)
        self.assertEqual(totals["kcal"], 310.0)
        self.assertEqual(totals["protein_g"], 26.0)
        self.assertEqual(totals["carbs_g"], 2.2)
        self.assertEqual(totals["fat_g"], 22.0)


class ValidateWorkoutPlanTests(WorkoutFixturesMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")
        self._make_exercises()
        self.profile = self.user.profile

    def test_approves_correct_plan(self):
        errors = validate_workout_plan(self._valid_workout_proposal(), self.profile, self.user)
        self.assertEqual(errors, [])

    def test_rejects_nonexistent_exercise_id(self):
        proposal = self._valid_workout_proposal()
        proposal["exercises"][0]["exercise_id"] = 999999
        errors = validate_workout_plan(proposal, self.profile, self.user)
        self.assertTrue(any("999999" in error for error in errors))

    def test_rejects_duplicate_order(self):
        proposal = self._valid_workout_proposal()
        proposal["exercises"][1]["order"] = 1
        errors = validate_workout_plan(proposal, self.profile, self.user)
        self.assertTrue(any("order" in error for error in errors))

    def test_rejects_reps_out_of_range(self):
        proposal = self._valid_workout_proposal()
        proposal["exercises"][0]["reps"] = 50
        errors = validate_workout_plan(proposal, self.profile, self.user)
        self.assertTrue(any("reps=50" in error for error in errors))

    def test_rejects_both_reps_and_duration_filled(self):
        proposal = self._valid_workout_proposal()
        proposal["exercises"][0]["duration_seconds"] = 30  # já tinha reps=10
        errors = validate_workout_plan(proposal, self.profile, self.user)
        self.assertTrue(any("reps E duration_seconds" in error for error in errors))

    def test_rejects_neither_reps_nor_duration_filled(self):
        proposal = self._valid_workout_proposal()
        proposal["exercises"][0]["reps"] = None
        errors = validate_workout_plan(proposal, self.profile, self.user)
        self.assertTrue(any("não tem reps nem duration_seconds" in error for error in errors))

    def test_rejects_exercise_repeated_too_many_times(self):
        proposal = self._valid_workout_proposal()
        for exercise in proposal["exercises"]:
            exercise["exercise_id"] = self.squat.id
        errors = validate_workout_plan(proposal, self.profile, self.user)
        self.assertTrue(any(str(self.squat.id) in error and "aparecem mais" in error for error in errors))


class SummarizeWorkoutTests(WorkoutFixturesMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")
        self._make_exercises()

    def test_summarize_counts_exercises_sets_and_muscle_groups(self):
        summary = summarize_workout(self._valid_workout_proposal())
        self.assertEqual(summary["exercise_count"], 4)
        self.assertEqual(summary["total_sets"], 12)
        self.assertEqual(
            summary["muscle_groups"],
            sorted([MuscleGroup.QUADS, MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.CORE]),
        )


class DietAgentTests(DietFixturesMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")
        self._make_foods()
        self.metric = _make_metric(self.user)

    def _invalid_proposal_json(self):
        proposal = self._valid_proposal()
        proposal["meals"][1]["order"] = 1  # order duplicado -> reprovado
        return json.dumps(proposal)

    def _valid_proposal_json(self, extra_item_fields=None):
        return json.dumps(self._valid_proposal(extra_item_fields))

    @patch("apps.coach.agents.diet.get_provider")
    def test_agent_retries_after_invalid_proposal_and_approves_second(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "claude-sonnet-4-5"
        provider.complete.side_effect = [
            LLMResponse(text=self._invalid_proposal_json(), tool_calls=[], usage={"input_tokens": 10, "output_tokens": 5}),
            LLMResponse(text=self._valid_proposal_json(), tool_calls=[], usage={"input_tokens": 10, "output_tokens": 5}),
        ]
        mock_get_provider.return_value = provider

        result = generate_meal_plan(self.user)

        self.assertTrue(result.approved)
        self.assertEqual(result.iterations, 2)
        self.assertIsNotNone(result.proposal)
        self.assertEqual(provider.complete.call_count, 2)
        self.assertEqual(AgentRun.objects.count(), 1)
        self.assertTrue(result.agent_run.approved)
        self.assertEqual(result.agent_run.iterations, 2)

    @override_settings(COACH_MAX_ITERATIONS=2)
    @patch("apps.coach.agents.diet.get_provider")
    def test_agent_stops_at_max_iterations_when_never_valid(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "claude-sonnet-4-5"
        provider.complete.side_effect = [
            LLMResponse(text=self._invalid_proposal_json(), tool_calls=[], usage={}),
            LLMResponse(text=self._invalid_proposal_json(), tool_calls=[], usage={}),
        ]
        mock_get_provider.return_value = provider

        result = generate_meal_plan(self.user)

        self.assertFalse(result.approved)
        self.assertEqual(result.iterations, 2)
        self.assertIsNone(result.proposal)
        self.assertTrue(result.errors)
        self.assertEqual(AgentRun.objects.count(), 1)
        self.assertFalse(result.agent_run.approved)

    @patch("apps.coach.agents.diet.get_provider")
    def test_agent_ignores_macros_returned_by_llm(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "claude-sonnet-4-5"
        fake_macros = {"kcal": 999999, "protein_g": 999999}
        provider.complete.side_effect = [
            LLMResponse(text=self._valid_proposal_json(extra_item_fields=fake_macros), tool_calls=[], usage={}),
        ]
        mock_get_provider.return_value = provider

        result = generate_meal_plan(self.user)

        self.assertTrue(result.approved)
        self.assertEqual(result.totals["kcal"], 1500.0)
        self.assertEqual(result.totals["protein_g"], 80.0)

    def test_agent_raises_when_no_body_metric(self):
        other = User.objects.create_user(email="sem-metrica@test.dev", password="x")
        with self.assertRaises(ValidationError):
            generate_meal_plan(other)


class WorkoutAgentTests(WorkoutFixturesMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")
        self._make_exercises()

    def _invalid_proposal_json(self):
        proposal = self._valid_workout_proposal()
        proposal["exercises"][1]["order"] = 1  # order duplicado -> reprovado
        return json.dumps(proposal)

    def _valid_proposal_json(self):
        return json.dumps(self._valid_workout_proposal())

    @patch("apps.coach.agents.workout.get_provider")
    def test_agent_retries_after_invalid_proposal_and_approves_second(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "claude-sonnet-4-5"
        provider.complete.side_effect = [
            LLMResponse(text=self._invalid_proposal_json(), tool_calls=[], usage={"input_tokens": 10, "output_tokens": 5}),
            LLMResponse(text=self._valid_proposal_json(), tool_calls=[], usage={"input_tokens": 10, "output_tokens": 5}),
        ]
        mock_get_provider.return_value = provider

        result = generate_workout_plan(self.user)

        self.assertTrue(result.approved)
        self.assertEqual(result.iterations, 2)
        self.assertIsNotNone(result.proposal)
        self.assertEqual(provider.complete.call_count, 2)
        self.assertEqual(AgentRun.objects.filter(agent=CoachAgent.WORKOUT).count(), 1)
        self.assertTrue(result.agent_run.approved)
        self.assertEqual(result.agent_run.iterations, 2)

    @override_settings(COACH_MAX_ITERATIONS=2)
    @patch("apps.coach.agents.workout.get_provider")
    def test_agent_stops_at_max_iterations_when_never_valid(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "claude-sonnet-4-5"
        provider.complete.side_effect = [
            LLMResponse(text=self._invalid_proposal_json(), tool_calls=[], usage={}),
            LLMResponse(text=self._invalid_proposal_json(), tool_calls=[], usage={}),
        ]
        mock_get_provider.return_value = provider

        result = generate_workout_plan(self.user)

        self.assertFalse(result.approved)
        self.assertEqual(result.iterations, 2)
        self.assertIsNone(result.proposal)
        self.assertTrue(result.errors)


def _good_critic_response(summary="Plano equilibrado."):
    return LLMResponse(
        text=json.dumps({"approved": True, "issues": [], "summary": summary}),
        tool_calls=[],
        usage={"input_tokens": 5, "output_tokens": 5},
    )


def _blocker_critic_response(
    message="Refeição com 900g de um único alimento não é realista.",
    meal_order=1,
    llm_approved=True,
    summary="Precisa de ajustes.",
):
    return LLMResponse(
        text=json.dumps(
            {
                "approved": llm_approved,
                "issues": [{"severity": "blocker", "message": message, "meal_order": meal_order}],
                "summary": summary,
            }
        ),
        tool_calls=[],
        usage={},
    )


def _warning_critic_response(
    message="Pouca variedade de vegetais.", llm_approved=False, summary="Ok com ressalvas."
):
    return LLMResponse(
        text=json.dumps(
            {
                "approved": llm_approved,
                "issues": [{"severity": "warning", "message": message, "meal_order": None}],
                "summary": summary,
            }
        ),
        tool_calls=[],
        usage={},
    )


class CriticAgentTests(DietFixturesMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")
        self._make_foods()
        self.metric = _make_metric(self.user)
        self.proposal = self._valid_proposal()
        self.totals = compute_totals(self.proposal)

    @patch("apps.coach.agents.critic.get_provider")
    def test_approves_good_plan(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "gemini-2.5-flash"
        provider.complete.return_value = _good_critic_response()
        mock_get_provider.return_value = provider

        result = review_meal_plan(self.user, self.proposal, self.totals, self.metric)

        self.assertTrue(result.approved)
        self.assertEqual(result.issues, [])
        self.assertEqual(AgentRun.objects.filter(agent=CoachAgent.CRITIC).count(), 1)
        self.assertEqual(result.agent_run.provider, settings.COACH_CRITIC_PROVIDER)

    @patch("apps.coach.agents.critic.get_provider")
    def test_blocker_issue_rejects_even_if_llm_says_approved_true(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "gemini-2.5-flash"
        provider.complete.return_value = _blocker_critic_response(llm_approved=True)
        mock_get_provider.return_value = provider

        result = review_meal_plan(self.user, self.proposal, self.totals, self.metric)

        self.assertFalse(result.approved)
        self.assertTrue(any(issue["severity"] == "blocker" for issue in result.issues))
        self.assertTrue(
            any("Divergência" in message for message in result.agent_run.validation_errors)
        )

    @patch("apps.coach.agents.critic.get_provider")
    def test_warning_only_does_not_reject(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "gemini-2.5-flash"
        provider.complete.return_value = _warning_critic_response(llm_approved=False)
        mock_get_provider.return_value = provider

        result = review_meal_plan(self.user, self.proposal, self.totals, self.metric)

        self.assertTrue(result.approved)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0]["severity"], "warning")

    @patch("apps.coach.agents.critic.get_provider")
    def test_prompt_includes_food_names_not_only_ids(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "gemini-2.5-flash"
        provider.complete.return_value = _good_critic_response()
        mock_get_provider.return_value = provider

        review_meal_plan(self.user, self.proposal, self.totals, self.metric)

        _, kwargs = provider.complete.call_args
        content = kwargs["messages"][0]["content"]
        self.assertIn(self.protein_food.name, content)
        self.assertIn(self.carb_food.name, content)
        self.assertIn(self.fat_food.name, content)
        self.assertNotIn('"food_id"', content)


class WorkoutCriticTests(WorkoutFixturesMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")
        self._make_exercises()
        self.proposal = self._valid_workout_proposal()
        self.summary = summarize_workout(self.proposal)
        self.profile = self.user.profile

    @patch("apps.coach.agents.critic.get_provider")
    def test_approves_good_plan(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "gemini-2.5-flash"
        provider.complete.return_value = _good_critic_response()
        mock_get_provider.return_value = provider

        result = review_workout_plan(self.user, self.proposal, self.summary, self.profile)

        self.assertTrue(result.approved)
        self.assertEqual(result.issues, [])
        self.assertEqual(AgentRun.objects.filter(agent=CoachAgent.CRITIC).count(), 1)

    @patch("apps.coach.agents.critic.get_provider")
    def test_blocker_issue_rejects_even_if_llm_says_approved_true(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "gemini-2.5-flash"
        provider.complete.return_value = _blocker_critic_response(
            message="Treino ignora completamente membros inferiores.", llm_approved=True
        )
        mock_get_provider.return_value = provider

        result = review_workout_plan(self.user, self.proposal, self.summary, self.profile)

        self.assertFalse(result.approved)
        self.assertTrue(any(issue["severity"] == "blocker" for issue in result.issues))
        self.assertTrue(
            any("Divergência" in message for message in result.agent_run.validation_errors)
        )

    @patch("apps.coach.agents.critic.get_provider")
    def test_prompt_includes_exercise_names_not_only_ids(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "gemini-2.5-flash"
        provider.complete.return_value = _good_critic_response()
        mock_get_provider.return_value = provider

        review_workout_plan(self.user, self.proposal, self.summary, self.profile)

        _, kwargs = provider.complete.call_args
        content = kwargs["messages"][0]["content"]
        self.assertIn(self.squat.name, content)
        self.assertIn(self.bench.name, content)
        self.assertNotIn('"exercise_id"', content)


class CoachedPipelineTests(DietFixturesMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")
        self._make_foods()
        self.metric = _make_metric(self.user)

    def _valid_proposal_json(self):
        return json.dumps(self._valid_proposal())

    def _invalid_proposal_json(self):
        proposal = self._valid_proposal()
        proposal["meals"][1]["order"] = 1  # order duplicado -> reprovado na validação
        return json.dumps(proposal)

    @patch("apps.coach.agents.diet.get_provider")
    @patch("apps.coach.agents.critic.get_provider")
    def test_pipeline_regenerates_after_critic_blocker_then_approves(
        self, mock_critic_provider, mock_diet_provider
    ):
        diet_provider = MagicMock()
        diet_provider.model = "claude-sonnet-4-5"
        diet_provider.complete.side_effect = [
            LLMResponse(text=self._valid_proposal_json(), tool_calls=[], usage={}),
            LLMResponse(text=self._valid_proposal_json(), tool_calls=[], usage={}),
        ]
        mock_diet_provider.return_value = diet_provider

        critic_provider = MagicMock()
        critic_provider.model = "gemini-2.5-flash"
        critic_provider.complete.side_effect = [
            _blocker_critic_response(),
            _good_critic_response(),
        ]
        mock_critic_provider.return_value = critic_provider

        result = generate_and_review_meal_plan(self.user)

        self.assertTrue(result.approved)
        self.assertEqual(result.critic_rounds, 2)
        self.assertEqual(diet_provider.complete.call_count, 2)
        self.assertEqual(critic_provider.complete.call_count, 2)
        self.assertEqual(len(result.agent_runs), 4)  # 2 diet + 2 crítico

    @override_settings(COACH_MAX_CRITIC_ROUNDS=2)
    @patch("apps.coach.agents.diet.get_provider")
    @patch("apps.coach.agents.critic.get_provider")
    def test_pipeline_exhausts_critic_rounds(self, mock_critic_provider, mock_diet_provider):
        diet_provider = MagicMock()
        diet_provider.model = "claude-sonnet-4-5"
        diet_provider.complete.side_effect = [
            LLMResponse(text=self._valid_proposal_json(), tool_calls=[], usage={}),
            LLMResponse(text=self._valid_proposal_json(), tool_calls=[], usage={}),
        ]
        mock_diet_provider.return_value = diet_provider

        critic_provider = MagicMock()
        critic_provider.model = "gemini-2.5-flash"
        critic_provider.complete.side_effect = [
            _blocker_critic_response(),
            _blocker_critic_response(),
        ]
        mock_critic_provider.return_value = critic_provider

        result = generate_and_review_meal_plan(self.user)

        self.assertFalse(result.approved)
        self.assertIsNone(result.proposal)
        self.assertEqual(result.critic_rounds, 2)
        self.assertEqual(MealPlan.objects.count(), 0)

    @patch("apps.coach.agents.diet.get_provider")
    @patch("apps.coach.agents.critic.get_provider")
    def test_pipeline_skips_critic_when_diet_validation_fails(
        self, mock_critic_provider, mock_diet_provider
    ):
        diet_provider = MagicMock()
        diet_provider.model = "claude-sonnet-4-5"
        diet_provider.complete.return_value = LLMResponse(
            text=self._invalid_proposal_json(), tool_calls=[], usage={}
        )
        mock_diet_provider.return_value = diet_provider

        critic_provider = MagicMock()
        mock_critic_provider.return_value = critic_provider

        result = generate_and_review_meal_plan(self.user)

        self.assertFalse(result.approved)
        self.assertEqual(result.critic_rounds, 0)
        critic_provider.complete.assert_not_called()
        mock_critic_provider.assert_not_called()


def _synchronous_enqueue_plan_job(user, message, intent=Intent.DIET_PLAN, conversation=None):
    """Substitui runner.enqueue_plan_job nos testes de view: cria o job e
    chama run_plan_job() diretamente, na mesma thread — sem passar por
    threading.Thread, que fecharia a conexão de banco compartilhada pelo
    TestCase ao final da execução."""
    job = CoachJob.objects.create(
        user=user, conversation=conversation, intent=intent, status=CoachJobStatus.PENDING
    )
    run_plan_job(job.id, message)
    return job


class ManagerRouteTests(TestCase):
    @patch("apps.coach.agents.manager.get_provider")
    def test_route_diet_by_keyword_does_not_call_llm(self, mock_get_provider):
        intent = route("Quero um plano alimentar para emagrecer")
        self.assertEqual(intent, Intent.DIET_PLAN)
        mock_get_provider.assert_not_called()

    @patch("apps.coach.agents.manager.get_provider")
    def test_route_workout_by_keyword_does_not_call_llm(self, mock_get_provider):
        intent = route("Preciso montar uma ficha de treino nova")
        self.assertEqual(intent, Intent.WORKOUT_PLAN)
        mock_get_provider.assert_not_called()

    @patch("apps.coach.agents.manager.get_provider")
    def test_route_calls_llm_only_when_ambiguous(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "claude-sonnet-4-5"
        provider.complete.return_value = LLMResponse(
            text=json.dumps(
                {"intent": "out_of_scope", "reason": "Dúvida de cobrança, não é sobre saúde."}
            ),
            tool_calls=[],
            usage={"input_tokens": 5, "output_tokens": 5},
        )
        mock_get_provider.return_value = provider

        intent = route("Estou com uma dúvida sobre o pagamento da minha assinatura.")

        self.assertEqual(intent, Intent.OUT_OF_SCOPE)
        provider.complete.assert_called_once()
        self.assertEqual(AgentRun.objects.filter(agent=CoachAgent.MANAGER).count(), 1)

    @patch("apps.coach.agents.manager.get_provider")
    def test_route_llm_invalid_intent_falls_back_to_ambiguous(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "claude-sonnet-4-5"
        provider.complete.return_value = LLMResponse(
            text=json.dumps({"intent": "algo_fora_do_enum", "reason": "..."}),
            tool_calls=[],
            usage={},
        )
        mock_get_provider.return_value = provider

        intent = route("sei la, me ajuda com uma coisa")

        self.assertEqual(intent, Intent.AMBIGUOUS)
        run = AgentRun.objects.filter(agent=CoachAgent.MANAGER).latest("created_at")
        self.assertFalse(run.approved)
        self.assertTrue(run.validation_errors)


class CoachMessageViewTests(DietFixturesMixin, WorkoutFixturesMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")
        self._make_foods()
        self._make_exercises()
        self.metric = _make_metric(self.user)
        self.client = APIClient()

    def test_requires_authentication(self):
        res = self.client.post(
            "/api/v1/coach/messages/", {"message": "Quero uma dieta"}, format="json"
        )
        self.assertEqual(res.status_code, 401)

    @patch("apps.coach.views.enqueue_plan_job", side_effect=_synchronous_enqueue_plan_job)
    @patch("apps.coach.agents.critic.get_provider")
    @patch("apps.coach.agents.diet.get_provider")
    def test_diet_message_returns_202_and_job_ends_succeeded(
        self, mock_diet_provider, mock_critic_provider, mock_enqueue
    ):
        diet_provider = MagicMock()
        diet_provider.model = "claude-sonnet-4-5"
        diet_provider.complete.return_value = LLMResponse(
            text=json.dumps(self._valid_proposal()), tool_calls=[], usage={}
        )
        mock_diet_provider.return_value = diet_provider

        critic_provider = MagicMock()
        critic_provider.model = "gemini-2.5-flash"
        critic_provider.complete.return_value = _good_critic_response()
        mock_critic_provider.return_value = critic_provider

        self.client.force_authenticate(self.user)
        res = self.client.post(
            "/api/v1/coach/messages/", {"message": "Quero um plano alimentar"}, format="json"
        )

        self.assertEqual(res.status_code, 202)
        self.assertIn("job_id", res.data)
        self.assertEqual(res.data["intent"], Intent.DIET_PLAN)

        job = CoachJob.objects.get(id=res.data["job_id"])
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.status, CoachJobStatus.SUCCEEDED)
        self.assertEqual(MealPlan.objects.filter(user=self.user).count(), 1)

    @patch("apps.coach.views.enqueue_plan_job", side_effect=_synchronous_enqueue_plan_job)
    @patch("apps.coach.agents.critic.get_provider")
    @patch("apps.coach.agents.workout.get_provider")
    def test_workout_message_returns_202_and_job_ends_succeeded(
        self, mock_workout_provider, mock_critic_provider, mock_enqueue
    ):
        workout_provider = MagicMock()
        workout_provider.model = "claude-sonnet-4-5"
        workout_provider.complete.return_value = LLMResponse(
            text=json.dumps(self._valid_workout_proposal()), tool_calls=[], usage={}
        )
        mock_workout_provider.return_value = workout_provider

        critic_provider = MagicMock()
        critic_provider.model = "gemini-2.5-flash"
        critic_provider.complete.return_value = _good_critic_response()
        mock_critic_provider.return_value = critic_provider

        self.client.force_authenticate(self.user)
        res = self.client.post(
            "/api/v1/coach/messages/", {"message": "Quero uma ficha de treino"}, format="json"
        )

        self.assertEqual(res.status_code, 202)
        self.assertIn("job_id", res.data)
        self.assertEqual(res.data["intent"], Intent.WORKOUT_PLAN)

        job = CoachJob.objects.get(id=res.data["job_id"])
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.status, CoachJobStatus.SUCCEEDED)
        self.assertEqual(Workout.objects.filter(user=self.user).count(), 1)

    @patch("apps.coach.agents.manager.get_provider")
    def test_out_of_scope_message_returns_200_polite_refusal(self, mock_get_provider):
        provider = MagicMock()
        provider.model = "claude-sonnet-4-5"
        provider.complete.return_value = LLMResponse(
            text=json.dumps({"intent": "out_of_scope", "reason": "..."}), tool_calls=[], usage={}
        )
        mock_get_provider.return_value = provider

        self.client.force_authenticate(self.user)
        res = self.client.post(
            "/api/v1/coach/messages/",
            {"message": "Estou com uma dúvida sobre o pagamento da assinatura."},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["intent"], Intent.OUT_OF_SCOPE)


class CoachJobAndConversationApiTests(DietFixturesMixin, WorkoutFixturesMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")
        self.other = User.objects.create_user(email="outro@test.dev", password="x")
        self._make_foods()
        self._make_exercises()
        self.metric = _make_metric(self.user)
        self.client = APIClient()

    def test_job_full_flow_succeeded_persists_meal_plan_for_owner(self):
        job = CoachJob.objects.create(user=self.user, intent=Intent.DIET_PLAN)

        with (
            patch("apps.coach.agents.diet.get_provider") as mock_diet_provider,
            patch("apps.coach.agents.critic.get_provider") as mock_critic_provider,
        ):
            diet_provider = MagicMock()
            diet_provider.model = "claude-sonnet-4-5"
            diet_provider.complete.return_value = LLMResponse(
                text=json.dumps(self._valid_proposal()), tool_calls=[], usage={}
            )
            mock_diet_provider.return_value = diet_provider

            critic_provider = MagicMock()
            critic_provider.model = "gemini-2.5-flash"
            critic_provider.complete.return_value = _good_critic_response()
            mock_critic_provider.return_value = critic_provider

            run_plan_job(job.id, "Quero um plano alimentar")  # síncrono, sem thread

        job.refresh_from_db()
        self.assertEqual(job.status, CoachJobStatus.SUCCEEDED)
        meal_plan = MealPlan.objects.get(id=job.result["meal_plan_id"])
        self.assertEqual(meal_plan.user, self.user)

        self.client.force_authenticate(self.user)
        res = self.client.get(f"/api/v1/coach/jobs/{job.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], CoachJobStatus.SUCCEEDED)
        self.assertIsNotNone(res.data["meal_plan"])
        self.assertEqual(res.data["meal_plan"]["id"], meal_plan.id)

    def test_job_rejected_by_validation_has_no_meal_plan_but_exposes_errors(self):
        job = CoachJob.objects.create(user=self.user, intent=Intent.DIET_PLAN)

        proposal = self._valid_proposal()
        proposal["meals"][1]["order"] = 1  # order duplicado -> reprovado na validação

        with (
            patch("apps.coach.agents.diet.get_provider") as mock_diet_provider,
            patch("apps.coach.agents.critic.get_provider") as mock_critic_provider,
        ):
            diet_provider = MagicMock()
            diet_provider.model = "claude-sonnet-4-5"
            diet_provider.complete.return_value = LLMResponse(
                text=json.dumps(proposal), tool_calls=[], usage={}
            )
            mock_diet_provider.return_value = diet_provider
            mock_critic_provider.return_value = MagicMock()

            run_plan_job(job.id, "Quero um plano alimentar")

        job.refresh_from_db()
        # O pipeline rodou até o fim sem erro de sistema — só não aprovou.
        # "failed" fica reservado para exceções (ver comentário em runner.py).
        self.assertEqual(job.status, CoachJobStatus.SUCCEEDED)
        self.assertEqual(MealPlan.objects.count(), 0)
        self.assertIsNone(job.result.get("meal_plan_id"))
        self.assertTrue(job.result.get("errors"))
        mock_critic_provider.assert_not_called()

    def test_workout_job_full_flow_succeeded_persists_workout_for_owner(self):
        job = CoachJob.objects.create(user=self.user, intent=Intent.WORKOUT_PLAN)

        with (
            patch("apps.coach.agents.workout.get_provider") as mock_workout_provider,
            patch("apps.coach.agents.critic.get_provider") as mock_critic_provider,
        ):
            workout_provider = MagicMock()
            workout_provider.model = "claude-sonnet-4-5"
            workout_provider.complete.return_value = LLMResponse(
                text=json.dumps(self._valid_workout_proposal()), tool_calls=[], usage={}
            )
            mock_workout_provider.return_value = workout_provider

            critic_provider = MagicMock()
            critic_provider.model = "gemini-2.5-flash"
            critic_provider.complete.return_value = _good_critic_response()
            mock_critic_provider.return_value = critic_provider

            run_plan_job(job.id, "Quero um treino")  # síncrono, sem thread

        job.refresh_from_db()
        self.assertEqual(job.status, CoachJobStatus.SUCCEEDED)
        workout = Workout.objects.get(id=job.result["workout_id"])
        self.assertEqual(workout.user, self.user)

        self.client.force_authenticate(self.user)
        res = self.client.get(f"/api/v1/coach/jobs/{job.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], CoachJobStatus.SUCCEEDED)
        self.assertIsNotNone(res.data["workout"])
        self.assertEqual(res.data["workout"]["id"], workout.id)

    def test_workout_job_rejected_by_validation_has_no_workout_but_exposes_errors(self):
        job = CoachJob.objects.create(user=self.user, intent=Intent.WORKOUT_PLAN)

        proposal = self._valid_workout_proposal()
        proposal["exercises"][1]["order"] = 1  # order duplicado -> reprovado na validação

        with (
            patch("apps.coach.agents.workout.get_provider") as mock_workout_provider,
            patch("apps.coach.agents.critic.get_provider") as mock_critic_provider,
        ):
            workout_provider = MagicMock()
            workout_provider.model = "claude-sonnet-4-5"
            workout_provider.complete.return_value = LLMResponse(
                text=json.dumps(proposal), tool_calls=[], usage={}
            )
            mock_workout_provider.return_value = workout_provider
            mock_critic_provider.return_value = MagicMock()

            run_plan_job(job.id, "Quero um treino")

        job.refresh_from_db()
        self.assertEqual(job.status, CoachJobStatus.SUCCEEDED)
        self.assertEqual(Workout.objects.count(), 0)
        self.assertIsNone(job.result.get("workout_id"))
        self.assertTrue(job.result.get("errors"))
        mock_critic_provider.assert_not_called()

    def test_user_cannot_access_job_of_another_user(self):
        job = CoachJob.objects.create(user=self.other, intent=Intent.DIET_PLAN)
        self.client.force_authenticate(self.user)
        res = self.client.get(f"/api/v1/coach/jobs/{job.id}/")
        self.assertEqual(res.status_code, 404)

    def test_user_cannot_access_conversation_of_another_user(self):
        conversation = CoachConversation.objects.create(user=self.other)
        self.client.force_authenticate(self.user)
        res = self.client.get(f"/api/v1/coach/conversations/{conversation.id}/messages/")
        self.assertEqual(res.status_code, 404)

    def test_own_conversation_messages_are_listed(self):
        conversation = CoachConversation.objects.create(user=self.user)
        CoachMessage.objects.create(
            conversation=conversation, role=MessageRole.USER, content="Oi"
        )
        self.client.force_authenticate(self.user)
        res = self.client.get(f"/api/v1/coach/conversations/{conversation.id}/messages/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_jobs_endpoint_requires_authentication(self):
        job = CoachJob.objects.create(user=self.user, intent=Intent.DIET_PLAN)
        res = self.client.get(f"/api/v1/coach/jobs/{job.id}/")
        self.assertEqual(res.status_code, 401)

    def test_conversation_messages_endpoint_requires_authentication(self):
        conversation = CoachConversation.objects.create(user=self.user)
        res = self.client.get(f"/api/v1/coach/conversations/{conversation.id}/messages/")
        self.assertEqual(res.status_code, 401)
