from flask import Blueprint, jsonify

from app.core.config import VERSION, get_settings

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    return jsonify(status="ok", framework="flask")


@health_bp.get("/api/v1/status")
def status():
    """Unauthenticated readiness probe used by the Android app before choosing a route.

    Exposes no secrets: only whether the backend is usable and what capabilities it has.
    """
    cfg = get_settings()
    ready = bool(cfg.shraddha_backend_enabled and cfg.ai_api_key)
    return jsonify({
        "service": "shraddha-backend",
        "version": VERSION,
        "enabled": cfg.shraddha_backend_enabled,
        "provider_ready": bool(cfg.ai_api_key),
        "ready": ready,
        "auth_required": bool(cfg.shraddha_api_token) or cfg.app_env != "development",
        "streaming": True,
        "tools": True,
        "supports_vision": cfg.ai_supports_vision,
        "routing": "backend_first_custom_fallback",
        "model": cfg.ai_model if ready else None,
    })
