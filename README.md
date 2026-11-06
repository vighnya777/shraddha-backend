# Shraddha Backend API (Flask)

A standalone Flask inference gateway for Shraddha in Cineflix. The backend keeps the default
AI provider credential on the server and exposes an OpenAI-compatible chat endpoint. The Android
app remains responsible for Shraddha's personality, conversation context, tool authorization,
music playback, queue/search/navigation, local controls, personalization and UI.

## Architecture

```text
Cineflix / Shraddha
  ├─ Existing prompt + music context + user profile + memory
  ├─ Existing tool schemas and local tool executor
  └─ Provider router
       ├─ 1) Shraddha Backend API (default)
       │     └─ Flask → configured AI provider (secret stays server-side)
       └─ 2) Existing custom API in AI Hub (fallback)

AI tool calls return to Android; playback/device actions never execute on the server.
```

## Routing policy

Default: **Backend first → Custom API fallback**. If the backend is disabled or unavailable,
the Android app should try the user's already-configured custom provider. Do not retry after visible
assistant output or after a tool has executed, to avoid duplicate actions.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set AI_API_KEY and SHRADDHA_API_TOKEN in .env
flask --app app.main run --debug
```

The API listens on `http://localhost:5000`. Health: `GET /health`.

## API

- `GET /health` — liveness probe.
- `GET /api/v1/status` — backend enabled/provider readiness/routing policy.
- `POST /api/v1/chat` — OpenAI-compatible chat completion; supports streamed SSE and native
  `tools` / `tool_choice` forwarding.

Example request:

```bash
curl http://localhost:5000/api/v1/chat \\
  -H 'Authorization: Bearer YOUR_APP_TOKEN' \\
  -H 'Content-Type: application/json' \\
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

## Environment

| Variable | Purpose | Default |
|---|---|---|
| `SHRADDHA_BACKEND_ENABLED` | Server-side master switch | `true` |
| `SHRADDHA_API_TOKEN` | App-to-backend bearer token | empty (development only) |
| `AI_PROVIDER` | Provider label | `openai-compatible` |
| `AI_BASE_URL` | Provider base URL | NVIDIA NIM |
| `AI_API_KEY` | Provider credential; server only | empty |
| `AI_MODEL` | Default model | `google/gemini-2.5-flash-lite` |
| `REQUEST_TIMEOUT_SECONDS` | Provider timeout | `90` |
| `MAX_REQUEST_BYTES` | Maximum request size | `1048576` |
| `ALLOWED_ORIGINS` | CORS origins, comma-separated | `*` |

## Deploy

Docker is included. For a managed Python host, use:

```bash
gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 app.main:app
```

Set `APP_ENV=production`, a strong `SHRADDHA_API_TOKEN`, and provider credentials as host environment
variables. Use HTTPS. Do not ship provider keys or a permanent shared backend token inside the APK.
Before a public production launch, add user/session authentication, rate limiting, usage metering,
secret rotation and operational monitoring.

## Compatibility and safety

- OpenAI-compatible request/response shape.
- Forwards `messages`, `tools`, `tool_choice`, and supported generation parameters.
- Backend never executes Shraddha tools; Android remains the tool executor.
- Backend OFF / network failure returns an error so the app can fall back to Custom API.
- No Cineflix Android source or Echo files are modified by this repository.

## Tests

```bash
pip install -r requirements.txt
ruff check app tests
pytest -q
```
