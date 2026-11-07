import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

VERSION = "0.3.0"


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_float(name: str, default: float, minimum: float = 0.1) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        return default


def _as_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_env: str
    shraddha_backend_enabled: bool
    shraddha_api_token: str
    ai_provider: str
    ai_base_url: str
    ai_api_key: str
    ai_model: str
    # Whether the configured upstream model accepts image inputs. Reported via /api/v1/status so
    # the Android client can keep images on the route that supports them.
    ai_supports_vision: bool
    # When false (default) the server-side AI_MODEL always wins and clients cannot pick
    # (and be billed for) an arbitrary upstream model.
    allow_client_model: bool
    connect_timeout_seconds: float
    request_timeout_seconds: float
    max_request_bytes: int
    allowed_origins: tuple[str, ...]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = tuple(x.strip() for x in os.getenv("ALLOWED_ORIGINS", "*").split(",") if x.strip())
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        shraddha_backend_enabled=_as_bool(os.getenv("SHRADDHA_BACKEND_ENABLED"), True),
        shraddha_api_token=os.getenv("SHRADDHA_API_TOKEN", ""),
        ai_provider=os.getenv("AI_PROVIDER", "openai-compatible"),
        ai_base_url=os.getenv("AI_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/"),
        ai_api_key=os.getenv("AI_API_KEY", ""),
        ai_model=os.getenv("AI_MODEL", "google/gemini-2.5-flash-lite"),
        ai_supports_vision=_as_bool(os.getenv("AI_SUPPORTS_VISION"), False),
        allow_client_model=_as_bool(os.getenv("ALLOW_CLIENT_MODEL"), False),
        connect_timeout_seconds=_as_float("CONNECT_TIMEOUT_SECONDS", 10.0),
        request_timeout_seconds=_as_float("REQUEST_TIMEOUT_SECONDS", 90.0),
        max_request_bytes=_as_int("MAX_REQUEST_BYTES", 1048576, minimum=1024),
        allowed_origins=origins,
    )
