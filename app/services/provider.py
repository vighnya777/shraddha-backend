import httpx
from flask import Response, jsonify, stream_with_context

from app.core.config import get_settings


def _provider_headers(stream: bool = False) -> dict[str, str]:
    cfg = get_settings()
    if not cfg.ai_api_key:
        raise RuntimeError("Backend provider is not configured")
    return {
        "Authorization": f"Bearer {cfg.ai_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
    }

def _provider_payload(payload: dict) -> dict:
    cfg = get_settings()
    result = dict(payload)
    result["model"] = result.get("model") or cfg.ai_model
    return result

def complete(payload: dict):
    cfg = get_settings()
    try:
        with httpx.Client(timeout=cfg.request_timeout_seconds) as client:
            response = client.post(
                f"{cfg.ai_base_url}/chat/completions",
                headers=_provider_headers(),
                json=_provider_payload(payload),
            )
            response.raise_for_status()
            return jsonify(response.json()), response.status_code
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503
    except httpx.TimeoutException:
        return jsonify(error="AI provider timed out"), 504
    except httpx.HTTPStatusError as exc:
        return jsonify(error=f"AI provider returned HTTP {exc.response.status_code}"), 502
    except (httpx.HTTPError, ValueError):
        return jsonify(error="AI provider is temporarily unavailable"), 502

def stream(payload: dict):
    cfg = get_settings()
    try:
        client = httpx.Client(timeout=cfg.request_timeout_seconds)
        upstream = client.send(
            client.build_request(
                "POST",
                f"{cfg.ai_base_url}/chat/completions",
                headers=_provider_headers(stream=True),
                json=_provider_payload(payload),
            ),
            stream=True,
        )
        if upstream.is_error:
            status = upstream.status_code
            upstream.close()
            client.close()
            return jsonify(error=f"AI provider returned HTTP {status}"), 502

        def generate():
            try:
                for chunk in upstream.iter_bytes():
                    if chunk:
                        yield chunk
            finally:
                upstream.close()
                client.close()

        return Response(
            stream_with_context(generate()),
            content_type=upstream.headers.get("content-type", "text/event-stream"),
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503
    except httpx.TimeoutException:
        return jsonify(error="AI provider timed out"), 504
    except httpx.HTTPError:
        return jsonify(error="AI provider is temporarily unavailable"), 502
