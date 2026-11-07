import json

import httpx

from tests.conftest import SAMPLE_TOOLS, chat_body

SSE = (
    b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
    b'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
    b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_9","type":"function",'
    b'"function":{"name":"play_song","arguments":"{\\"query\\":\\"x\\"}"}}]}}]}\n\n'
    b"data: [DONE]\n\n"
)


def stream_post(client, **extra):
    return client.post("/api/v1/chat", json=chat_body(stream=True, **extra))


def test_stream_passes_sse_through_byte_for_byte(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(
        200, content=SSE, headers={"content-type": "text/event-stream"})
    response = stream_post(make_client(), tools=SAMPLE_TOOLS)
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/event-stream")
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.data == SSE  # chunks, tool-call deltas and [DONE] unchanged


def test_stream_requests_stream_upstream(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(200, content=SSE)
    stream_post(make_client())
    assert upstream.last_json["stream"] is True
    assert upstream.requests[-1].headers["accept"] == "text/event-stream"


def test_stream_provider_error_before_stream_is_json_error(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(429, json={"error": "limit"})
    response = stream_post(make_client())
    assert response.status_code == 429 and response.json["error"]


def test_stream_provider_400_keeps_message(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(400, json={"error": {"message": "no tools"}})
    response = stream_post(make_client())
    assert response.status_code == 400 and "no tools" in response.json["error"]


def test_stream_timeout_before_first_byte_is_504(make_client, upstream):
    def handler(request):
        raise httpx.ConnectTimeout("slow", request=request)
    upstream.handler = handler
    assert stream_post(make_client()).status_code == 504


def test_stream_connection_failure_is_502(make_client, upstream):
    def handler(request):
        raise httpx.ConnectError("down", request=request)
    upstream.handler = handler
    assert stream_post(make_client()).status_code == 502


class BrokenStream(httpx.SyncByteStream):
    def __iter__(self):
        yield b'data: {"choices":[{"delta":{"content":"par"}}]}\n\n'
        raise httpx.ReadError("connection reset")


def test_mid_stream_failure_emits_sse_error_then_done(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(200, stream=BrokenStream())
    response = stream_post(make_client())
    assert response.status_code == 200
    frames = [f for f in response.data.decode().split("\n\n") if f]
    assert json.loads(frames[0][len("data: "):])["choices"][0]["delta"]["content"] == "par"
    error = json.loads(frames[1][len("data: "):])
    assert error["error"]["message"]
    assert frames[-1] == "data: [DONE]"


def test_stream_requires_auth(make_client, upstream):
    client = make_client(SHRADDHA_API_TOKEN="s3cret")
    response = client.post("/api/v1/chat", json=chat_body(stream=True))
    assert response.status_code == 401 and upstream.requests == []
