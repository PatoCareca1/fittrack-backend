import httpx

from apps.coach.providers.base import LLMProvider, LLMResponse, ToolCall

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-5"
JSON_SCHEMA_TOOL_NAME = "structured_response"


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model

    def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        json_schema: dict | None = None,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
        }
        if tools:
            payload["tools"] = list(tools)
        if json_schema:
            payload["tools"] = payload.get("tools", []) + [
                {
                    "name": JSON_SCHEMA_TOOL_NAME,
                    "description": "Retorna a resposta estruturada conforme o schema.",
                    "input_schema": json_schema,
                }
            ]
            payload["tool_choice"] = {"type": "tool", "name": JSON_SCHEMA_TOOL_NAME}

        response = httpx.post(
            ANTHROPIC_API_URL,
            json=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        text = None
        tool_calls = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text = (text or "") + block["text"]
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block["id"],
                        name=block["name"],
                        arguments=block.get("input", {}),
                    )
                )

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            raw=data,
            usage=data.get("usage", {}),
        )
