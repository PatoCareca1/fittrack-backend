import json

import httpx

from apps.coach.providers.base import LLMProvider, LLMResponse, ToolCall

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-5"
JSON_SCHEMA_TOOL_NAME = "structured_response"


def _stringify(content) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool["parameters"],
        }
        for tool in tools
    ]


def _to_anthropic_messages(messages: list[dict]) -> list[dict]:
    native = []
    for message in messages:
        role = message["role"]
        if role == "tool":
            native.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message["tool_call_id"],
                            "content": _stringify(message["content"]),
                        }
                    ],
                }
            )
        elif role == "assistant" and message.get("tool_calls"):
            blocks = []
            if message.get("content"):
                blocks.append({"type": "text", "text": message["content"]})
            for tool_call in message["tool_calls"]:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "input": tool_call.arguments,
                    }
                )
            native.append({"role": "assistant", "content": blocks})
        else:
            native.append({"role": role, "content": message["content"]})
    return native


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
            "messages": _to_anthropic_messages(messages),
        }

        native_tools = _to_anthropic_tools(tools) if tools else []
        if json_schema:
            native_tools = native_tools + [
                {
                    "name": JSON_SCHEMA_TOOL_NAME,
                    "description": "Retorna a resposta estruturada conforme o schema.",
                    "input_schema": json_schema,
                }
            ]
            payload["tool_choice"] = {"type": "tool", "name": JSON_SCHEMA_TOOL_NAME}
        if native_tools:
            payload["tools"] = native_tools

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
