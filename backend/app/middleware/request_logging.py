"""HTTP request logging middleware — console access log only.

Implemented as pure ASGI middleware (not BaseHTTPMiddleware) so StreamingResponse /
SSE endpoints are not buffered or truncated.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.app_log import (
    log_http,
    request_id_ctx,
    summarize_request_body,
)

_PROJECT_ID_RE = re.compile(r"/projects/([^/]+)")


def _extract_project_id(path: str) -> str | None:
    match = _PROJECT_ID_RE.search(path)
    return match.group(1) if match else None


def _client_ip(scope: Scope) -> str | None:
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = scope.get("client")
    if client:
        return client[0]
    return None


def _query_user_id(scope: Scope) -> str | None:
    raw_qs = scope.get("query_string", b"").decode("latin-1")
    for part in raw_qs.split("&"):
        if not part:
            continue
        key, _, value = part.partition("=")
        if key == "user_id" and value:
            return value
    return None


async def _buffer_body(receive: Receive) -> tuple[bytes, Receive]:
    """Read the request body once, then replay it and pass through disconnects.

    StreamingResponse listens for ``http.disconnect`` on ``receive``. A naive
    replay that always returns ``http.request`` busy-loops and starves the
    event loop — SSE never progresses and LLM tokens never print.
    """
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            body = b"".join(chunks)

            async def disconnected() -> Message:
                return message

            return body, disconnected
        if message["type"] != "http.request":
            async def passthrough() -> Message:
                return message

            return b"".join(chunks), passthrough
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    body = b"".join(chunks)
    body_sent = False

    async def replay() -> Message:
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        # After the body is consumed, wait for disconnect (or further messages).
        return await receive()

    return body, replay


def _parse_json_object(body: bytes, content_type: str | None) -> dict[str, Any] | None:
    if not body or not content_type or "application/json" not in content_type:
        return None
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:12]
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()

        method = scope.get("method", "")
        path = scope.get("path", "")
        user_id = _query_user_id(scope)
        project_id = _extract_project_id(path)
        client_ip = _client_ip(scope)
        body_meta: dict[str, Any] | None = None

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        content_type = headers.get("content-type")

        app_receive = receive
        if method in {"POST", "PUT", "PATCH"}:
            body_bytes, app_receive = await _buffer_body(receive)
            body_json = _parse_json_object(body_bytes, content_type)
            if body_json:
                if not user_id:
                    raw_user_id = body_json.get("user_id")
                    if isinstance(raw_user_id, str) and raw_user_id.strip():
                        user_id = raw_user_id.strip()
                body_meta = summarize_request_body(body_json)

        status_code = 500
        logged = False

        def _log(*, error: str | None = None) -> None:
            nonlocal logged
            if logged:
                return
            logged = True
            log_http(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=(time.perf_counter() - start) * 1000,
                request_id=request_id,
                user_id=user_id,
                project_id=project_id,
                client_ip=client_ip,
                meta=body_meta,
                error=error,
            )

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers_out = MutableHeaders(scope=message)
                headers_out["X-Request-ID"] = request_id
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                _log()

        try:
            await self.app(scope, app_receive, send_wrapper)
            # Streaming may end without a final body frame in disconnect edge cases.
            _log()
        except Exception as exc:
            _log(error=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            request_id_ctx.reset(token)
