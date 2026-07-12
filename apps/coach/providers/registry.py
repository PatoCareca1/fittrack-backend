from django.conf import settings

from apps.coach.providers.anthropic_provider import AnthropicProvider
from apps.coach.providers.base import LLMProvider
from apps.coach.providers.gemini_provider import GeminiProvider

_PROVIDERS = {
    "anthropic": lambda: AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY),
    "gemini": lambda: GeminiProvider(api_key=settings.GEMINI_API_KEY),
}


def get_provider(name: str) -> LLMProvider:
    try:
        factory = _PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Provedor de LLM desconhecido: '{name}'. "
            f"Opções válidas: {', '.join(_PROVIDERS)}."
        )
    return factory()
