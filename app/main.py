from flask import Flask, jsonify
from flask_cors import CORS

from app.api.routes.chat import chat_bp
from app.api.routes.health import health_bp
from app.core.config import get_settings


def create_app(test_config: dict | None = None) -> Flask:
    cfg = get_settings()
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=cfg.max_request_bytes,
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)
    CORS(
        app,
        origins=list(cfg.allowed_origins) if cfg.allowed_origins != ("*",) else "*",
        methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.register_blueprint(health_bp)
    app.register_blueprint(chat_bp)

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify(error="Request body is too large"), 413

    return app

app = create_app()
