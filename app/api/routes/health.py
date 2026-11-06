from flask import Blueprint, jsonify
from app.core.config import get_settings

health_bp = Blueprint("health", __name__)

@health_bp.get("/health")
def health():
    return jsonify(status="ok", framework="flask")

@health_bp.get("/api/v1/status")
def status():
    cfg = get_settings()
    return jsonify({
        "service": "shraddha-backend",
        "enabled": cfg.shraddha_backend_enabled,
        "provider_ready": bool(cfg.ai_api_key),
        "routing": "backend_first_custom_fallback",
        "model": cfg.ai_model if cfg.ai_api_key else None,
    })
