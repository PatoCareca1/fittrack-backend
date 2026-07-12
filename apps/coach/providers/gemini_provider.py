import httpx

from apps.coach.providers.base import LLMProvider, LLMResponse, ToolCall

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiProvider(LLMProvider):
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
        contents = [
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in messages
        ]
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
        }
        if tools:
            payload["tools"] = [{"function_declarations": tools}]
        if json_schema:
            payload["generationConfig"] = {
                "response_mime_type": "application/json",
                "response_schema": json_schema,
            }

        response = httpx.post(
            GEMINI_API_URL.format(model=self.model),
            params={"key": self.api_key},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        text = None
        tool_calls = []
        candidates = data.get("candidates", [])
        if candidates:
            for part in candidates[0].get("content", {}).get("parts", []):
                if "text" in part:
                    text = (text or "") + part["text"]
                elif "functionCall" in part:
                    function_call = part["functionCall"]
                    tool_calls.append(
                        ToolCall(
                            id=function_call.get("name", ""),
                            name=function_call.get("name", ""),
                            arguments=function_call.get("args", {}),
                        )
                    )

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            raw=data,
            usage=data.get("usageMetadata", {}),
        )
