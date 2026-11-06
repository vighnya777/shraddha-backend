from typing import Any

ALLOWED_FIELDS = {
    "model", "messages", "stream", "tools", "tool_choice",
    "temperature", "max_tokens", "top_p", "stop", "presence_penalty",
    "frequency_penalty", "response_format", "seed", "parallel_tool_calls",
}

def validate_chat_payload(payload: Any) -> tuple[dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, "Request body must be a JSON object"
    messages = payload.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 100:
        return None, "messages must be a list containing 1 to 100 items"
    if any(not isinstance(item, dict) for item in messages):
        return None, "Each message must be an object"
    if "stream" in payload and not isinstance(payload["stream"], bool):
        return None, "stream must be a boolean"
    if payload.get("temperature") is not None:
        try:
            if not 0 <= float(payload["temperature"]) <= 2:
                return None, "temperature must be between 0 and 2"
        except (TypeError, ValueError):
            return None, "temperature must be numeric"
    if payload.get("max_tokens") is not None:
        try:
            if not 1 <= int(payload["max_tokens"]) <= 16384:
                return None, "max_tokens must be between 1 and 16384"
        except (TypeError, ValueError):
            return None, "max_tokens must be an integer"
    # Forward known OpenAI-compatible fields; do not let arbitrary app data
    # leak to an upstream provider.
    clean = {key: value for key, value in payload.items() if key in ALLOWED_FIELDS and value is not None}
    return clean, None
