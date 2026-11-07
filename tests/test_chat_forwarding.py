import httpx

from tests.conftest import SAMPLE_TOOLS, chat_body

PROVIDER_REPLY = {"id": "c1", "choices": [{"message": {"role": "assistant", "content": "hi"}}]}


def post(client, body):
    return client.post("/api/v1/chat", json=body)


def test_normal_chat_returns_provider_json(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(200, json=PROVIDER_REPLY)
    response = post(make_client(), chat_body())
    assert response.status_code == 200
    assert response.json == PROVIDER_REPLY


def test_forwards_to_configured_provider_with_server_key(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(200, json=PROVIDER_REPLY)
    response = post(make_client(), chat_body())
    sent = upstream.requests[-1]
    assert str(sent.url) == "https://provider.example/v1/chat/completions"
    assert sent.headers["authorization"] == "Bearer test-provider-key"
    # The provider key must never be echoed back to the app.
    assert "test-provider-key" not in response.data.decode()


def test_server_model_wins_by_default(make_client, upstream):
    post(make_client(), chat_body(model="expensive-model"))
    assert upstream.last_json["model"] == "server-model"


def test_client_model_allowed_when_enabled(make_client, upstream):
    post(make_client(ALLOW_CLIENT_MODEL="true"), chat_body(model="my-model"))
    assert upstream.last_json["model"] == "my-model"


def test_forwards_history_tools_tool_choice_and_parameters(make_client, upstream):
    history = [
        {"role": "system", "content": "You are Shraddha"},
        {"role": "user", "content": "play tum hi ho"},
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call_abc", "type": "function",
            "function": {"name": "play_song", "arguments": "{\"query\":\"tum hi ho\"}"}}]},
        {"role": "tool", "tool_call_id": "call_abc", "content": "{\"ok\":true}"},
        {"role": "user", "content": "thanks"},
    ]
    body = {"messages": history, "tools": SAMPLE_TOOLS, "tool_choice": "required",
            "temperature": 0.3, "max_tokens": 512, "top_p": 0.9,
            "parallel_tool_calls": True}
    post(make_client(), body)
    sent = upstream.last_json
    assert sent["messages"] == history            # history + tool ids/results untouched
    assert sent["tools"] == SAMPLE_TOOLS           # tool definitions untouched
    assert sent["tool_choice"] == "required"       # tool_choice preserved
    assert sent["temperature"] == 0.3 and sent["max_tokens"] == 512 and sent["top_p"] == 0.9
    assert sent["parallel_tool_calls"] is True
    assert sent["stream"] is False


def test_forced_function_tool_choice_preserved(make_client, upstream):
    choice = {"type": "function", "function": {"name": "play_song"}}
    post(make_client(), chat_body(tools=SAMPLE_TOOLS, tool_choice=choice))
    assert upstream.last_json["tool_choice"] == choice


def test_unknown_fields_are_not_forwarded(make_client, upstream):
    post(make_client(), chat_body(user_secret="x", device_id="abc"))
    assert "user_secret" not in upstream.last_json and "device_id" not in upstream.last_json


def test_multimodal_content_forwarded_intact(make_client, upstream):
    content = [{"type": "text", "text": "what is this"},
               {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]
    post(make_client(), {"messages": [{"role": "user", "content": content}]})
    assert upstream.last_json["messages"][0]["content"] == content


def test_tool_call_response_forwarded_unchanged(make_client, upstream):
    reply = {"choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "type": "function",
             "function": {"name": "play_song", "arguments": "{\"query\":\"a\"}"}},
            {"id": "call_2", "type": "function",
             "function": {"name": "set_volume", "arguments": "{\"level\":40}"}}]}}]}
    upstream.handler = lambda r: httpx.Response(200, json=reply)
    response = post(make_client(), chat_body(tools=SAMPLE_TOOLS))
    assert response.json == reply  # ids, names, args and multiple calls preserved; nothing executed


def test_backend_never_executes_tools(make_client, upstream):
    reply = {"choices": [{"message": {"tool_calls": [{"id": "x", "type": "function",
             "function": {"name": "play_song", "arguments": "{}"}}]}}]}
    upstream.handler = lambda r: httpx.Response(200, json=reply)
    post(make_client(), chat_body(tools=SAMPLE_TOOLS))
    assert len(upstream.requests) == 1  # one forward only; no follow-up/tool round trip


# ---- provider errors ----

def test_provider_400_is_forwarded_as_400_with_message(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(
        400, json={"error": {"message": "tools are not supported by this model"}})
    response = post(make_client(), chat_body(tools=SAMPLE_TOOLS))
    assert response.status_code == 400
    assert "tools are not supported" in response.json["error"]


def test_provider_429_forwarded_with_retry_after(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(429, json={"error": "slow down"},
                                                headers={"Retry-After": "7"})
    response = post(make_client(), chat_body())
    assert response.status_code == 429 and response.headers["Retry-After"] == "7"


def test_provider_auth_failure_is_generic_502(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(401, json={"error": {"message": "bad key sk-123"}})
    response = post(make_client(), chat_body())
    assert response.status_code == 502
    assert "sk-123" not in response.data.decode()
    assert "test-provider-key" not in response.data.decode()


def test_provider_500_is_502(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(500, text="boom")
    assert post(make_client(), chat_body()).status_code == 502


def test_provider_timeout_is_504(make_client, upstream):
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)
    upstream.handler = handler
    assert post(make_client(), chat_body()).status_code == 504


def test_provider_unreachable_is_502(make_client, upstream):
    def handler(request):
        raise httpx.ConnectError("down", request=request)
    upstream.handler = handler
    assert post(make_client(), chat_body()).status_code == 502


def test_provider_invalid_json_is_502(make_client, upstream):
    upstream.handler = lambda r: httpx.Response(200, content=b"<html>not json</html>")
    assert post(make_client(), chat_body()).status_code == 502


def test_provider_not_configured_is_503(make_client, upstream):
    response = post(make_client(AI_API_KEY=""), chat_body())
    assert response.status_code == 503
    assert upstream.requests == []
