from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.coach.models import AgentRun, CoachAgent, CoachConversation, CoachMessage, MessageRole
from apps.coach.providers.anthropic_provider import AnthropicProvider
from apps.coach.providers.base import LLMResponse
from apps.coach.providers.gemini_provider import GeminiProvider
from apps.coach.providers.registry import get_provider
from apps.users.models import User


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
