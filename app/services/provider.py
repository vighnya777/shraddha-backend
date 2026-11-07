"""OpenAI-compatible upstream forwarding.

The backend only forwards chat-completion requests. It never executes tools: tool calls returned
by the provider are passed straight back to the Android app, which runs them locally.
"""
import json
import logging

import httpx
from flask import Response, jsonify, stream_with_context

from app.core.config import get_settings

log = logging.getLogger("shraddha.provider")

CHAT_PATH = "/chat/completions"
MAX_ERROR_MESSAGE_CHARS = 300


class ProviderNotConfigured(RuntimeError):
    """Raised when the server has no upstream API key."""


def _make_client() -> httpx.Client:
    """Single seam for building the upstream client (replaced in tests)."""
    cfg = get_settings()
    timeout = httpx.Timeout(cfg.request_timeout_seconds, connect=cfg.connect_timeout_seconds)
    return httpx.Client(timeout=timeout)


def _provider_headers(stream: bool = False) -> dict[str, str]:
    cfg = get_settings()
    if not cfg.ai_api_key:
        raise ProviderNotConfigured("Backend provider is not configured")
    return {
        "Authorization": f"Bearer {cfg.ai_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
    }


def _provider_payload(payload: dict, stream: bool) -> dict:
    cfg = get_settings()
    result = dict(payload)
    requested = result.get("model")
    result["model"] = requested if (cfg.allow_client_model and requested) else cfg.ai_model
    result["stream"] = stream
    if not stream:
        result.pop("stream_options", None)
    return result


def _extract_message(body: str, status: int) -> str:
    fallback = f"AI provider returned HTTP {status}"
    if not body:
        return fallback
    try:
        data = json.loads(body)
    except ValueError:
        return fallback
    message = None
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            message = err.get("message")
        elif isinstance(err, str):
            message = err
        message = message or data.get("message") or data.get("detail")
    if not isinstance(message, str) or not message.strip():
        return fallback
    return message.strip()[:MAX_ERROR_MESSAGE_CHARS]


def _error_response(status: int, body: str, retry_after: str | None = None):
    """Translate an upstream HTTP error into a safe response for the app.

    * 400/413/422: the request itself was rejected (e.g. tools unsupported). The provider's message
      is forwarded because the app uses it to decide whether to retry without tools.
    * 429: rate limited, forwarded as 429 (with Retry-After).
    * 401/403/404/other: a server-side configuration problem; reported generically as 502 so
      provider details and credential state are not exposed to clients.
    """
    log.warning("Upstream provider returned HTTP %s", status)
    if status in (400, 413, 422):
        resp = jsonify(error=_extract_message(body, status), provider_status=status)
        return resp, 400
    if status == 429:
        resp = jsonify(error="AI provider rate limit reached", provider_status=status)
        if retry_after:
            resp.headers["Retry-After"] = retry_after
        return resp, 429
    if status in (401, 403):
        return jsonify(error="AI provider rejected the backend credentials",
                       provider_status=status), 502
    return jsonify(error=f"AI provider returned HTTP {status}", provider_status=status), 502


def _sse_error(message: str) -> bytes:
    frame = {"error": {"message": message, "type": "upstream_error"}}
    return f"data: {json.dumps(frame)}\n\n".encode("utf-8")


def complete(payload: dict):
    cfg = get_settings()
    try:
        headers = _provider_headers()
        with _make_client() as client:
            response = client.post(
                f"{cfg.ai_base_url}{CHAT_PATH}",
                headers=headers,
                json=_provider_payload(payload, stream=False),
            )
    except ProviderNotConfigured as exc:
        return jsonify(error=str(exc)), 503
    except httpx.TimeoutException:
        return jsonify(error="AI provider timed out"), 504
    except httpx.HTTPError:
        return jsonify(error="AI provider is temporarily unavailable"), 502

    if response.is_error:
        return _error_response(
            response.status_code, response.text, response.headers.get("retry-after")
        )
    try:
        return jsonify(response.json()), 200
    except ValueError:
        return jsonify(error="AI provider returned an invalid response"), 502


def stream(payload: dict):
    cfg = get_settings()
    client = None
    upstream = None
    try:
        headers = _provider_headers(stream=True)
        client = _make_client()
        upstream = client.send(
            client.build_request(
                "POST",
                f"{cfg.ai_base_url}{CHAT_PATH}",
                headers=headers,
                json=_provider_payload(payload, stream=True),
            ),
            stream=True,
        )
        if upstream.is_error:
            status = upstream.status_code
            upstream.read()
            body = upstream.text
            retry_after = upstream.headers.get("retry-after")
            upstream.close()
            client.close()
            return _error_response(status, body, retry_after)
    except ProviderNotConfigured as exc:
        return jsonify(error=str(exc)), 503
    except httpx.TimeoutException:
        _close_quietly(upstream, client)
        return jsonify(error="AI provider timed out"), 504
    except httpx.HTTPError:
        _close_quietly(upstream, client)
        return jsonify(error="AI provider is temporarily unavailable"), 502

    def generate():
        try:
            for chunk in upstream.iter_bytes():
                if chunk:
                    yield chunk
        except httpx.HTTPError:
            # The HTTP status line was already sent, so signal the failure inside the SSE stream.
            log.warning("Upstream stream interrupted")
            yield _sse_error("AI provider connection was interrupted")
            yield b"data: [DONE]\n\n"
        finally:
            # Also runs when the client disconnects (GeneratorExit), releasing the upstream socket.
            _close_quietly(upstream, client)

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _close_quietly(*resources) -> None:
    for resource in resources:
        if resource is None:
            continue
        try:
            resource.close()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
