from tests.conftest import SAMPLE_TOOLS, chat_body


def post(client, body, **kw):
    return client.post("/api/v1/chat", json=body, **kw)


def test_rejects_missing_json(make_client):
    assert make_client().post("/api/v1/chat").status_code == 400


def test_rejects_non_object_body(make_client):
    assert post(make_client(), ["x"]).status_code == 400


def test_rejects_empty_messages(make_client):
    assert post(make_client(), {"messages": []}).status_code == 400


def test_rejects_too_many_messages(make_client):
    body = {"messages": [{"role": "user", "content": "x"}] * 101}
    assert post(make_client(), body).status_code == 400


def test_rejects_unknown_role(make_client):
    body = {"messages": [{"role": "hacker", "content": "x"}]}
    assert post(make_client(), body).status_code == 400


def test_tool_message_requires_tool_call_id(make_client):
    body = {"messages": [{"role": "tool", "content": "done"}]}
    response = post(make_client(), body)
    assert response.status_code == 400 and "tool_call_id" in response.json["error"]


def test_rejects_non_boolean_stream(make_client):
    assert post(make_client(), chat_body(stream="yes")).status_code == 400


def test_rejects_bad_temperature(make_client):
    assert post(make_client(), chat_body(temperature=5)).status_code == 400
    assert post(make_client(), chat_body(temperature="hot")).status_code == 400


def test_rejects_bad_max_tokens(make_client):
    assert post(make_client(), chat_body(max_tokens=0)).status_code == 400
    assert post(make_client(), chat_body(max_tokens="many")).status_code == 400


def test_rejects_malformed_tools(make_client):
    assert post(make_client(), chat_body(tools="x")).status_code == 400
    assert post(make_client(), chat_body(tools=[{"type": "function"}])).status_code == 400


def test_rejects_invalid_tool_choice(make_client):
    body = chat_body(tools=SAMPLE_TOOLS, tool_choice="sometimes")
    assert post(make_client(), body).status_code == 400


def test_tool_choice_requires_tools(make_client):
    assert post(make_client(), chat_body(tool_choice="auto")).status_code == 400


def test_rejects_oversized_body(make_client):
    client = make_client(MAX_REQUEST_BYTES="2048")
    body = chat_body()
    body["messages"][0]["content"] = "x" * 5000
    assert post(client, body).status_code == 413
