import secrets
from functools import wraps

from flask import jsonify, request

from app.core.config import get_settings


def require_app_token(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        cfg = get_settings()
        expected = cfg.shraddha_api_token
        # Only local development may run without an app token.
        if not expected:
            if cfg.app_env == "development":
                return view(*args, **kwargs)
            return jsonify(error="Backend authentication is not configured"), 503
        supplied = request.headers.get("Authorization", "")
        supplied = supplied.removeprefix("Bearer ")
        if not secrets.compare_digest(supplied, expected):
            return jsonify(error="Invalid app token"), 401
        return view(*args, **kwargs)
    return wrapped
