from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstração sobre um fornecedor de LLM. Trocar de fornecedor deve ser
    apenas trocar a variável de ambiente do provider, nunca reescrever a
    lógica dos agentes."""

    @abstractmethod
    def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        json_schema: dict | None = None,
    ) -> LLMResponse:
        ...
