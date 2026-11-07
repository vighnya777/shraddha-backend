import secrets
from functools import wraps

from flask import jsonify, request

from app.core.config import get_settings


def _bearer_token(header_value: str) -> str:
    value = header_value.strip()
    if value[:7].lower() == "bearer ":
        return value[7:].strip()
    return ""


def require_app_token(view):
    """Protect a route with the app-to-backend bearer token.

    Only local development (APP_ENV=development) may run without a configured token.
    Any other environment without SHRADDHA_API_TOKEN refuses to serve (503) instead of
    silently running open.
    """

    @wraps(view)
    def wrapped(*args, **kwargs):
        cfg = get_settings()
        expected = cfg.shraddha_api_token
        if not expected:
            if cfg.app_env == "development":
                return view(*args, **kwargs)
            return jsonify(error="Backend authentication is not configured"), 503
        supplied = _bearer_token(request.headers.get("Authorization", ""))
        # Compare as bytes: compare_digest raises TypeError for non-ASCII str.
        if not secrets.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
            return jsonify(error="Invalid or missing app token"), 401
        return view(*args, **kwargs)

    return wrapped
