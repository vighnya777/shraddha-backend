import os
from dataclasses import dataclass
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    app_env: str
    shraddha_backend_enabled: bool
    shraddha_api_token: str
    ai_provider: str
    ai_base_url: str
    ai_api_key: str
    ai_model: str
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
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "90")),
        max_request_bytes=int(os.getenv("MAX_REQUEST_BYTES", "1048576")),
        allowed_origins=origins,
    )
