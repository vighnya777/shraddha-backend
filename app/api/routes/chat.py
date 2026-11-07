from flask import Blueprint, jsonify, request

from app.core.config import get_settings
from app.core.security import require_app_token
from app.schemas.chat import contains_images, validate_chat_payload
from app.services.provider import complete, stream

chat_bp = Blueprint("chat", __name__, url_prefix="/api/v1")


@chat_bp.post("/chat")
@require_app_token
def chat():
    cfg = get_settings()
    if not cfg.shraddha_backend_enabled:
        return jsonify(error="Shraddha backend is disabled"), 503
    if request.content_length and request.content_length > cfg.max_request_bytes:
        return jsonify(error="Request body is too large"), 413
    payload, error = validate_chat_payload(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400
    if contains_images(payload) and not cfg.ai_supports_vision:
        return jsonify(error="The configured backend model cannot read images. "
                             "Set AI_SUPPORTS_VISION=true only if AI_MODEL accepts images."), 400
    if payload.get("stream", False):
        return stream(payload)
    return complete(payload)
