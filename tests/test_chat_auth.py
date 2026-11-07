from tests.conftest import chat_body


def test_missing_token_rejected(make_client, upstream):
    client = make_client(SHRADDHA_API_TOKEN="s3cret")
    response = client.post("/api/v1/chat", json=chat_body())
    assert response.status_code == 401
    assert upstream.requests == []  # never reaches the provider


def test_wrong_token_rejected(make_client, upstream):
    client = make_client(SHRADDHA_API_TOKEN="s3cret")
    response = client.post("/api/v1/chat", json=chat_body(),
                           headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_non_ascii_token_is_401_not_500(make_client, upstream):
    client = make_client(SHRADDHA_API_TOKEN="s3cret")
    response = client.post("/api/v1/chat", json=chat_body(),
                           headers={"Authorization": "Bearer t\u00f6ken"})
    assert response.status_code == 401


def test_correct_token_accepted(make_client, upstream):
    client = make_client(SHRADDHA_API_TOKEN="s3cret")
    response = client.post("/api/v1/chat", json=chat_body(),
                           headers={"Authorization": "Bearer s3cret"})
    assert response.status_code == 200


def test_production_without_token_refuses_to_serve(make_client, upstream):
    client = make_client(APP_ENV="production", SHRADDHA_API_TOKEN="")
    response = client.post("/api/v1/chat", json=chat_body())
    assert response.status_code == 503
    assert upstream.requests == []


def test_development_without_token_is_open(make_client, upstream):
    client = make_client(APP_ENV="development", SHRADDHA_API_TOKEN="")
    assert client.post("/api/v1/chat", json=chat_body()).status_code == 200


def test_backend_disabled_returns_503(make_client, upstream):
    client = make_client(SHRADDHA_BACKEND_ENABLED="false")
    response = client.post("/api/v1/chat", json=chat_body())
    assert response.status_code == 503 and "disabled" in response.json["error"]
    assert upstream.requests == []
