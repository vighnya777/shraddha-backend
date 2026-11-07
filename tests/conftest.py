import json

import httpx
import pytest

from app.core import config
from app.main import create_app
from app.services import provider

BASE_ENV = {
    "APP_ENV": "development",
    "SHRADDHA_API_TOKEN": "",
    "SHRADDHA_BACKEND_ENABLED": "true",
    "AI_API_KEY": "test-provider-key",
    "AI_BASE_URL": "https://provider.example/v1",
    "AI_MODEL": "server-model",
    "ALLOW_CLIENT_MODEL": "false",
    "AI_SUPPORTS_VISION": "false",
    "MAX_REQUEST_BYTES": "1048576",
}


@pytest.fixture
def make_client(monkeypatch):
    """Build a Flask test client with the given environment overrides."""

    def _make(**env):
        for key, value in {**BASE_ENV, **env}.items():
            monkeypatch.setenv(key, str(value))
        config.get_settings.cache_clear()
        return create_app({"TESTING": True}).test_client()

    yield _make
    config.get_settings.cache_clear()


class FakeProvider:
    """Records upstream requests and answers them with a configurable handler."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.handler = lambda request: httpx.Response(200, json={"choices": []})

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)

    @property
    def last_json(self) -> dict:
        return json.loads(self.requests[-1].content)


@pytest.fixture
def upstream(monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr(
        provider, "_make_client",
        lambda: httpx.Client(transport=httpx.MockTransport(fake.handle)),
    )
    return fake


def chat_body(**extra):
    body = {"messages": [{"role": "user", "content": "hello"}]}
    body.update(extra)
    return body


SAMPLE_TOOLS = [{
    "type": "function",
    "function": {
        "name": "play_song",
        "description": "Play a song",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
}]
