from app.main import create_app


def test_health_endpoint():
    client = create_app({"TESTING": True}).test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "framework": "flask"}


def test_status_has_backend_first_routing():
    client = create_app({"TESTING": True}).test_client()
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json["routing"] == "backend_first_custom_fallback"


def test_chat_requires_json_messages():
    client = create_app({"TESTING": True}).test_client()
    response = client.post("/api/v1/chat", json={"messages": []})
    assert response.status_code == 400


def test_chat_rejects_missing_json():
    client = create_app({"TESTING": True}).test_client()
    response = client.post("/api/v1/chat")
    assert response.status_code == 400
