from typing import Any

# Fields forwarded to the upstream provider. Anything else is dropped so arbitrary app data
# never leaks upstream.
ALLOWED_FIELDS = {
    "model", "messages", "stream", "stream_options", "tools", "tool_choice",
    "parallel_tool_calls", "temperature", "max_tokens", "max_completion_tokens", "top_p",
    "stop", "presence_penalty", "frequency_penalty", "response_format", "seed",
    "reasoning_effort",
}

ALLOWED_ROLES = {"system", "user", "assistant", "tool", "developer"}
# Image inputs: only inline base64 images in common formats (the app always sends this form).
ALLOWED_IMAGE_PREFIXES = ("data:image/jpeg;base64,", "data:image/png;base64,",
                          "data:image/webp;base64,", "data:image/gif;base64,")
MAX_IMAGE_DATA_URL_CHARS = 3 * 1024 * 1024  # ~2.2 MB of image data after base64
ALLOWED_TOOL_CHOICE_STRINGS = {"auto", "none", "required"}
MAX_MESSAGES = 100
MAX_TOOLS = 128


def _validate_messages(messages: Any) -> str | None:
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_MESSAGES:
        return f"messages must be a list containing 1 to {MAX_MESSAGES} items"
    for index, item in enumerate(messages):
        if not isinstance(item, dict):
            return "Each message must be an object"
        if item.get("role") not in ALLOWED_ROLES:
            return f"messages[{index}].role must be one of {sorted(ALLOWED_ROLES)}"
        if item["role"] == "tool" and not isinstance(item.get("tool_call_id"), str):
            return f"messages[{index}] with role 'tool' requires a string tool_call_id"
        tool_calls = item.get("tool_calls")
        if tool_calls is not None and not isinstance(tool_calls, list):
            return f"messages[{index}].tool_calls must be a list"
        content = item.get("content")
        if isinstance(content, list):
            error = _validate_content_parts(content, index)
            if error:
                return error
    return None


def _validate_content_parts(parts: list, index: int) -> str | None:
    for part_index, part in enumerate(parts):
        if not isinstance(part, dict):
            return f"messages[{index}].content[{part_index}] must be an object"
        kind = part.get("type")
        if kind == "text":
            if not isinstance(part.get("text"), str):
                return f"messages[{index}].content[{part_index}].text must be a string"
        elif kind == "image_url":
            url = (part.get("image_url") or {}).get("url") if isinstance(part.get("image_url"), dict) else None
            if not isinstance(url, str) or not url.startswith(ALLOWED_IMAGE_PREFIXES):
                return ("Images must be sent as base64 JPEG, PNG, WebP or GIF "
                        f"(messages[{index}].content[{part_index}]).")
            if len(url) > MAX_IMAGE_DATA_URL_CHARS:
                return f"Image is too large (messages[{index}].content[{part_index}]). Send a smaller image."
        else:
            return f"messages[{index}].content[{part_index}].type must be 'text' or 'image_url'"
    return None


def contains_images(payload: dict) -> bool:
    """True when any message carries an image_url content part."""
    for item in payload.get("messages") or []:
        content = item.get("content") if isinstance(item, dict) else None
        if isinstance(content, list) and any(
            isinstance(part, dict) and part.get("type") == "image_url" for part in content
        ):
            return True
    return False


def _validate_tools(tools: Any) -> str | None:
    if not isinstance(tools, list) or len(tools) > MAX_TOOLS:
        return f"tools must be a list of at most {MAX_TOOLS} items"
    for index, tool in enumerate(tools):
        if not isinstance(tool, dict) or tool.get("type") != "function":
            return f"tools[{index}] must be an object with type 'function'"
        function = tool.get("function")
        if not isinstance(function, dict) or not isinstance(function.get("name"), str) \
                or not function["name"]:
            return f"tools[{index}].function.name must be a non-empty string"
    return None


def _validate_tool_choice(choice: Any) -> str | None:
    if isinstance(choice, str):
        if choice not in ALLOWED_TOOL_CHOICE_STRINGS:
            return "tool_choice must be 'auto', 'none', 'required' or a function object"
        return None
    if isinstance(choice, dict):
        function = choice.get("function")
        if choice.get("type") == "function" and isinstance(function, dict) \
                and isinstance(function.get("name"), str):
            return None
    return "tool_choice must be 'auto', 'none', 'required' or a function object"


def validate_chat_payload(payload: Any) -> tuple[dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, "Request body must be a JSON object"
    error = _validate_messages(payload.get("messages"))
    if error:
        return None, error
    if "stream" in payload and not isinstance(payload["stream"], bool):
        return None, "stream must be a boolean"
    if payload.get("tools") is not None:
        error = _validate_tools(payload["tools"])
        if error:
            return None, error
    if payload.get("tool_choice") is not None:
        if not payload.get("tools"):
            return None, "tool_choice requires a non-empty tools list"
        error = _validate_tool_choice(payload["tool_choice"])
        if error:
            return None, error
    if payload.get("temperature") is not None:
        try:
            if not 0 <= float(payload["temperature"]) <= 2:
                return None, "temperature must be between 0 and 2"
        except (TypeError, ValueError):
            return None, "temperature must be numeric"
    for field in ("max_tokens", "max_completion_tokens"):
        if payload.get(field) is not None:
            try:
                if not 1 <= int(payload[field]) <= 16384:
                    return None, f"{field} must be between 1 and 16384"
            except (TypeError, ValueError):
                return None, f"{field} must be an integer"
    clean = {k: v for k, v in payload.items() if k in ALLOWED_FIELDS and v is not None}
    return clean, None
