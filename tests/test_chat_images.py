import base64

from tests.conftest import chat_body  # noqa: F401  (keeps helper import style consistent)

JPEG_URL = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0test").decode()


def image_body(url=JPEG_URL):
    return {
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "what is in this photo?"},
                {"type": "image_url", "image_url": {"url": url}},
            ],
        }]
    }


def test_image_forwarded_upstream_when_vision_enabled(make_client, upstream):
    client = make_client(AI_SUPPORTS_VISION="true")
    response = client.post("/api/v1/chat", json=image_body())
    assert response.status_code == 200
    parts = upstream.last_json["messages"][0]["content"]
    assert parts[1] == {"type": "image_url", "image_url": {"url": JPEG_URL}}


def test_images_refused_when_model_cannot_see(make_client, upstream):
    client = make_client(AI_SUPPORTS_VISION="false")
    response = client.post("/api/v1/chat", json=image_body())
    assert response.status_code == 400
    assert "cannot read images" in response.get_json()["error"]
    assert upstream.requests == []  # never reaches the provider


def test_rejects_non_image_data_url(make_client, upstream):
    client = make_client(AI_SUPPORTS_VISION="true")
    response = client.post("/api/v1/chat", json=image_body("data:image/heic;base64,AAAA"))
    assert response.status_code == 400
    assert "base64 JPEG" in response.get_json()["error"]


def test_rejects_remote_image_url(make_client, upstream):
    client = make_client(AI_SUPPORTS_VISION="true")
    response = client.post("/api/v1/chat", json=image_body("https://example.com/a.jpg"))
    assert response.status_code == 400


def test_rejects_oversized_image(make_client, upstream):
    client = make_client(AI_SUPPORTS_VISION="true", MAX_REQUEST_BYTES="8388608")
    big = "data:image/png;base64," + "A" * (3 * 1024 * 1024)
    response = client.post("/api/v1/chat", json=image_body(big))
    assert response.status_code == 400
    assert "too large" in response.get_json()["error"]


def test_text_only_requests_unaffected(make_client, upstream):
    client = make_client(AI_SUPPORTS_VISION="false")
    response = client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 200
