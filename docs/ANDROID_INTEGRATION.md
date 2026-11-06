# Cineflix Android integration contract

This backend is intentionally independent from the Android app. Add a network adapter around the
existing Shraddha engine/provider selection point. Do not replace or remove existing tool executors,
music playback, queue management, navigation, local controls, personalization, intent routing,
vision handling or chat UI.

## Routing order

1. Default to **Backend first** when `shraddha_backend_enabled` is selected.
2. Query `GET /api/v1/status`, then send the existing OpenAI-compatible request to `POST /api/v1/chat`.
3. On network failure, timeout, HTTP 5xx/503 or backend disabled, transparently try the user's
   existing Custom API configuration.
4. If neither provider is configured, show a non-blocking explanation while retaining local controls.
5. If the user explicitly chooses Custom API first, honor that preference.
6. Never retry after visible assistant output or a tool has executed; avoid duplicate playback/actions.

## Preserve existing Shraddha functionality

Continue constructing the prompt/context on Android using the current Shraddha implementation.
Forward the same `messages`, `tools`, and `tool_choice` that the existing engine constructs.
The backend forwards native tool-call responses; Android parses and executes them locally through
the existing tool executor. Never move music playback, queue, navigation, or device actions to the
backend. Preserve vision capability checks and only send images to compatible providers.

## Suggested preferences

- `shraddha_enabled`: true
- `shraddha_backend_enabled`: true
- `shraddha_backend_url`: deployment URL
- `shraddha_custom_api_enabled`: false until configured
- `shraddha_route_priority`: `backend_first`

Keep user custom-provider credentials in Android encrypted storage. Keep the server provider key
on the server. A permanent shared app token embedded in a distributed APK is not secure; production
should exchange user/app identity for short-lived scoped tokens.

## Endpoints

- `GET /health` — liveness.
- `GET /api/v1/status` — backend status.
- `POST /api/v1/chat` — chat completion and SSE streaming.

A 503 from chat is a signal to try the custom-provider fallback.
