def usage_tokens(usage: dict, keys: tuple[str, ...]) -> int:
    """Extrai a contagem de tokens de um dict de usage tentando várias
    chaves possíveis — cada provider nomeia o campo de um jeito
    (input_tokens/output_tokens no Anthropic, promptTokenCount/
    candidatesTokenCount no Gemini)."""
    for key in keys:
        if usage.get(key):
            return usage[key]
    return 0
