# Android (Cineflix) integration contract

The Cineflix app uses this backend as its **primary** Shraddha AI route and falls back to the user's
own OpenAI-compatible API when the backend is disabled, unreachable or fails before producing output.
Full app-side documentation: `docs/SHRADDHA_BACKEND_INTEGRATION.md` in the Cineflix repository.

## What the app calls

1. `GET /api/v1/status` (no auth) before choosing a route. The app requires
   `service == "shraddha-backend"`, `enabled`, `provider_ready`, and reads `supports_vision`
   (images are only sent here if true) and `auth_required`.
2. `POST /api/v1/chat` with `Authorization: Bearer <app token>`. Always sends `messages`, and when
   tools are enabled `tools` + `tool_choice`; `stream: true` for chat, `false` for tool follow-ups.
   It sends no `model` (the server's `AI_MODEL` is used).
3. Settings "Test backend" sends `POST /api/v1/chat` with `{"messages":[]}`: auth is checked
   before validation, so `400` = token accepted, `401` = rejected, `503` = disabled/unconfigured.
   No provider tokens are spent.

## Error handling the app relies on

| Backend answer | App behaviour |
|---|---|
| 401 / 502 / 503 / 504 / connection error before output | switch to custom API, mark backend down for 10 s |
| 400 with provider message mentioning tools/function | engine retries once without tools (same route) |
| 429 | surfaced as rate limit (not treated as an outage) |
| SSE `error` frame before any text | switch to custom API; after text it is shown, never retried |

Tool calls are never executed here: the model's `tool_calls` are returned to the app, which runs them
locally and posts the results back as `role:"tool"` messages with the original `tool_call_id`.
