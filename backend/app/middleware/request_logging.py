"""HTTP request logging middleware — console access log only."""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.app_log import (
    log_http,
    request_id_ctx,
    summarize_request_body,
)

_PROJECT_ID_RE = re.compile(r"/projects/([^/]+)")
_SHARE_TOKEN_RE = re.compile(r"/share/([^/]+)")


def _extract_project_id(path: str) -> str | None:
    match = _PROJECT_ID_RE.search(path)
    return match.group(1) if match else None


def _extract_share_token(path: str) -> str | None:
    match = _SHARE_TOKEN_RE.search(path)
    return match.group(1) if match else None


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _safe_query_params(request: Request) -> dict[str, str]:
    return {key: value for key, value in request.query_params.multi_items()}


async def _read_json_body(request: Request) -> tuple[bytes, dict[str, Any] | None]:
    body_bytes = await request.body()

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    request._receive = receive  # type: ignore[method-assign]

    content_type = request.headers.get("content-type", "")
    if not body_bytes or "application/json" not in content_type:
        return body_bytes, None
    try:
        parsed = json.loads(body_bytes)
    except json.JSONDecodeError:
        return body_bytes, None
    if not isinstance(parsed, dict):
        return body_bytes, None
    return body_bytes, parsed


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid.uuid4().hex[:12]
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()

        method = request.method
        path = request.url.path
        user_id = request.query_params.get("user_id")
        project_id = _extract_project_id(path)
        share_token = _extract_share_token(path)
        client_ip = _client_ip(request)
        body_meta: dict[str, Any] | None = None
        query_params = _safe_query_params(request)

        if method in {"POST", "PUT", "PATCH"}:
            _, body_json = await _read_json_body(request)
            if body_json:
                if not user_id:
                    raw_user_id = body_json.get("user_id")
                    if isinstance(raw_user_id, str) and raw_user_id.strip():
                        user_id = raw_user_id.strip()
                body_meta = summarize_request_body(body_json)

        status_code = 500
        error: str | None = None
        response: Response | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
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
            request_id_ctx.reset(token)
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        log_http(
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            request_id=request_id,
            user_id=user_id,
            project_id=project_id,
            client_ip=client_ip,
            meta=body_meta,
        )

        response.headers["X-Request-ID"] = request_id
        request_id_ctx.reset(token)
        return response
