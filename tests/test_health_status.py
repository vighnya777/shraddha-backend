def test_health_endpoint(make_client):
    response = make_client().get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "framework": "flask"}


def test_status_ready_reports_capabilities(make_client):
    body = make_client(AI_SUPPORTS_VISION="true").get("/api/v1/status").json
    assert body["service"] == "shraddha-backend"
    assert body["enabled"] is True and body["provider_ready"] is True and body["ready"] is True
    assert body["streaming"] is True and body["tools"] is True
    assert body["supports_vision"] is True
    assert body["routing"] == "backend_first_custom_fallback"
    assert body["model"] == "server-model"


def test_status_never_exposes_secrets(make_client):
    raw = make_client(SHRADDHA_API_TOKEN="app-secret-token").get("/api/v1/status").data.decode()
    assert "test-provider-key" not in raw
    assert "app-secret-token" not in raw


def test_status_when_disabled(make_client):
    body = make_client(SHRADDHA_BACKEND_ENABLED="false").get("/api/v1/status").json
    assert body["enabled"] is False and body["ready"] is False and body["model"] is None


def test_status_when_provider_not_configured(make_client):
    body = make_client(AI_API_KEY="").get("/api/v1/status").json
    assert body["provider_ready"] is False and body["ready"] is False


def test_status_does_not_require_auth(make_client):
    client = make_client(SHRADDHA_API_TOKEN="app-secret-token")
    assert client.get("/api/v1/status").status_code == 200


def test_unknown_route_is_json(make_client):
    response = make_client().get("/nope")
    assert response.status_code == 404 and response.json == {"error": "Not found"}
