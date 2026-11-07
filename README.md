# Shraddha Backend API (Flask)

A standalone Flask gateway that forwards Shraddha AI requests from the Cineflix Android app to an
OpenAI-compatible provider. The provider API key lives **only on this server**.

The backend is a *forwarding layer*, not a replacement for the assistant. The Android app still owns
Shraddha's prompt, conversation context, tool definitions, **tool execution** (playback, queue,
search, navigation, volume…), personalization, vision handling and UI. The backend never executes a
tool: tool calls returned by the model are passed back to the app unchanged.

```text
Cineflix (Android)                              this repo
 ├─ builds messages + tools + tool_choice
 ├─ 1) Shraddha Backend ──POST /api/v1/chat──▶  Flask ──▶ AI provider (key stays here)
 │        ▲  SSE / JSON, tool_calls pass through
 ├─ 2) Custom API (user's own key) ◀── automatic fallback if the backend is unavailable
 └─ executes tool calls locally, sends tool results back through the same route
```

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | Liveness probe |
| GET | `/api/v1/status` | none | Readiness + capabilities (no secrets) |
| POST | `/api/v1/chat` | Bearer token | OpenAI-compatible chat completion, JSON or SSE |

`/api/v1/status` response:

```json
{"service":"shraddha-backend","version":"0.3.0","enabled":true,"provider_ready":true,"ready":true,
 "auth_required":true,"streaming":true,"tools":true,"supports_vision":false,
 "routing":"backend_first_custom_fallback","model":"google/gemini-2.5-flash-lite"}
```

### `POST /api/v1/chat`

Accepts the OpenAI chat-completions shape. Forwarded fields: `messages`, `tools`, `tool_choice`,
`parallel_tool_calls`, `stream`, `stream_options`, `temperature`, `max_tokens`,
`max_completion_tokens`, `top_p`, `stop`, `presence_penalty`, `frequency_penalty`,
`response_format`, `seed`, `reasoning_effort`, and (only if `ALLOW_CLIENT_MODEL=true`) `model`.
Everything else is dropped. Message history, `tool_calls`, `tool_call_id` and tool results are
forwarded untouched.

Validation: JSON object body; 1–100 messages with a valid `role`; `tool` messages need a
`tool_call_id`; `tools` must be function definitions (≤128); `tool_choice` must be `auto`,
`none`, `required` or a function object and requires `tools`; `temperature` 0–2; token limits
1–16384; body ≤ `MAX_REQUEST_BYTES`.

Error responses are always JSON `{"error": "..."}`:

| Status | Meaning |
|---|---|
| 400 | invalid payload, or the provider rejected the request (provider message forwarded) |
| 401 | missing/invalid app token |
| 413 | request too large |
| 429 | provider rate limit (`Retry-After` forwarded) |
| 502 | provider unreachable / invalid response / provider rejected *server* credentials (generic message) |
| 503 | backend disabled, provider key missing, or auth not configured outside development |
| 504 | provider timeout |

**Streaming** (`"stream": true`): the provider's SSE bytes are passed through unchanged
(`data: {...}\n\n … data: [DONE]`), including tool-call deltas. Errors before the first byte are
normal JSON errors with the status above. If the upstream connection drops mid-stream the server
emits `data: {"error":{"message":"…","type":"upstream_error"}}` followed by `data: [DONE]`.
Upstream sockets are closed when the client disconnects.

## Authentication

Send `Authorization: Bearer <SHRADDHA_API_TOKEN>`. Comparison is constant-time. With
`APP_ENV=development` and no token configured the API is open (local use only); in any other
environment a missing `SHRADDHA_API_TOKEN` makes `/api/v1/chat` return 503 instead of running open.

> A single static token embedded in a distributed APK can be extracted. Treat it as a coarse gate,
> not as production security. Before a public launch add per-user/device authentication (short-lived
> signed tokens, e.g. Play Integrity + token exchange), rate limiting and usage metering.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `APP_ENV` | `development` or `production` | `development` |
| `SHRADDHA_BACKEND_ENABLED` | Server-side master switch (`false` ⇒ chat returns 503) | `true` |
| `SHRADDHA_API_TOKEN` | App-to-backend bearer token | empty (dev only) |
| `AI_PROVIDER` | Provider label | `openai-compatible` |
| `AI_BASE_URL` | Provider base URL (`…/v1`, `/chat/completions` is appended) | NVIDIA NIM |
| `AI_API_KEY` | Provider credential — **server only** | empty |
| `AI_MODEL` | Model used for all requests | `google/gemini-2.5-flash-lite` |
| `AI_SUPPORTS_VISION` | Advertise image support in `/status` | `false` |
| `ALLOW_CLIENT_MODEL` | Let clients override `model` | `false` |
| `CONNECT_TIMEOUT_SECONDS` | Upstream connect timeout | `10` |
| `REQUEST_TIMEOUT_SECONDS` | Upstream read timeout | `90` |
| `MAX_REQUEST_BYTES` | Max request body (room for one base64 photo) | `4194304` |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `*` |

Switching provider = change `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL` (any OpenAI-compatible
endpoint: OpenRouter, OpenAI, NVIDIA NIM, Groq, Gemini's OpenAI endpoint, a local vLLM/Ollama…).

## Local development

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # set AI_API_KEY (and SHRADDHA_API_TOKEN)
flask --app app.main run --debug        # http://localhost:5000
ruff check app tests && pytest -q
```

From the Android emulator the host machine is `http://10.0.2.2:5000`.

## Docker

```bash
cp .env.example .env   # fill in values; .env is git-ignored and excluded from the image
docker compose up --build -d
curl http://localhost:8000/health
```

The image runs Gunicorn (`gthread`, 2 workers × 8 threads) as a non-root user; compose adds a
health check, a read-only filesystem and `no-new-privileges`.

## Production

```bash
APP_ENV=production SHRADDHA_API_TOKEN=… AI_API_KEY=… \
gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 8 --worker-class gthread --timeout 120 app.main:app
```

- Terminate **HTTPS** at a reverse proxy / platform load balancer. The Android app requires
  `https://` for non-local backends.
- If you use nginx, keep `proxy_buffering off` for `/api/v1/chat` (the app also sends
  `X-Accel-Buffering: no`) so SSE is not buffered.
- Inject secrets through the platform's secret store, never through the image or the repo.
- Rotate `SHRADDHA_API_TOKEN` and `AI_API_KEY` periodically; rate-limit at the proxy.

## Examples

```bash
# status
curl https://api.example.com/api/v1/status

# chat
curl https://api.example.com/api/v1/chat -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'

# streaming + tools
curl -N https://api.example.com/api/v1/chat -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"stream":true,"messages":[{"role":"user","content":"play tum hi ho"}],
       "tools":[{"type":"function","function":{"name":"play_song",
         "parameters":{"type":"object","properties":{"query":{"type":"string"}}}}}],
       "tool_choice":"auto"}'
```

The model answers with a `tool_calls` entry; the **app** runs it and posts the follow-up request
containing the assistant `tool_calls` message and a `{"role":"tool","tool_call_id":…}` result.

## Tests

`pytest -q` (53 tests): health, status, validation, auth, disabled/unconfigured, forwarding of
history/tools/`tool_choice`, provider errors (400/429/401/500/timeout/unreachable/invalid body),
SSE pass-through, tool-call delta pass-through and mid-stream failure. They use
`httpx.MockTransport`; no network or provider key is needed.

## Not included (by design)

Per-user auth, rate limiting, usage metering and request logging of message content (the server
deliberately does not log prompts or the `Authorization` header).
