"""Application-level logging: HTTP access, errors, and user activity."""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger("brandvideo.app")

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
project_id_ctx: ContextVar[str] = ContextVar("project_id", default="")

_META_MAX = 4000
_TRUNCATE_FIELDS = frozenset(
    {
        "text",
        "message",
        "content",
        "script",
        "brief",
        "filename",
        "value",
        "messages",
        "quotes",
        "brand_insights",
        "personal_experiences",
        "changed_row_ids",
        "target_node_ids",
        "requested_perspectives",
        "accepted_hunk_ids",
        "rejected_hunk_ids",
        "target_issue_ids",
        "target_position_ids",
        "layouts",
    }
)


def setup_app_logging() -> None:
    if logger.handlers:
        return
    level_name = os.getenv("APP_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
    )
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


def activity_log_enabled() -> bool:
    return os.getenv("ACTIVITY_LOG_ENABLED", "1") != "0"


def get_request_id() -> str:
    return request_id_ctx.get()


def get_project_id() -> str:
    return project_id_ctx.get()


def _serialize(value: Any, *, max_len: int = _META_MAX) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)
    if len(text) > max_len:
        return f"{text[:max_len]}... [truncated, total {len(text)} chars]"
    return text


def summarize_request_body(body: Any) -> dict[str, Any]:
    """Build a compact, non-sensitive summary of a JSON request body."""
    if not isinstance(body, dict):
        return {"body_type": type(body).__name__}

    summary: dict[str, Any] = {}
    for key, value in body.items():
        if value is None or value == "" or value == [] or value == {}:
            continue
        if key == "script" and isinstance(value, dict):
            rows = value.get("rows") or []
            columns = value.get("columns") or []
            summary["script"] = {"row_count": len(rows), "column_count": len(columns)}
            continue
        if key in _TRUNCATE_FIELDS:
            text = _serialize(value, max_len=300)
            summary[key] = text
            continue
        if isinstance(value, (dict, list)):
            text = _serialize(value, max_len=500)
            summary[key] = text
            continue
        summary[key] = value
    return summary


def log_http(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_id: str,
    user_id: str | None = None,
    project_id: str | None = None,
    client_ip: str | None = None,
    meta: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    parts = [
        f"request_id={request_id}",
        f"{method} {path}",
        f"status={status_code}",
        f"duration={duration_ms:.1f}ms",
    ]
    if user_id:
        parts.append(f"user_id={user_id}")
    if project_id:
        parts.append(f"project_id={project_id}")
    if client_ip:
        parts.append(f"client={client_ip}")
    if error:
        parts.append(f"error={error}")
    if meta:
        parts.append(f"meta={_serialize(meta, max_len=800)}")
    logger.info(" | ".join(parts))


def log_activity(
    *,
    action: str,
    user_id: str | None = None,
    project_id: str | None = None,
    request_id: str | None = None,
    **fields: Any,
) -> None:
    """Log a domain-level user action (also persisted via middleware for HTTP)."""
    rid = request_id or get_request_id()
    parts = [f"request_id={rid}", f"action={action}"]
    if user_id:
        parts.append(f"user_id={user_id}")
    if project_id:
        parts.append(f"project_id={project_id}")
    for key, value in fields.items():
        if value is None or value == "" or value == {} or value == []:
            continue
        parts.append(f"{key}={_serialize(value, max_len=500)}")
    logger.info(" | ".join(parts))


def log_warning(message: str, **fields: Any) -> None:
    rid = get_request_id()
    parts = [f"request_id={rid}", message]
    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{key}={_serialize(value, max_len=500)}")
    logger.warning(" | ".join(parts))


def log_error(message: str, *, exc: BaseException | None = None, **fields: Any) -> None:
    rid = get_request_id()
    parts = [f"request_id={rid}", message]
    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{key}={_serialize(value, max_len=500)}")
    if exc is not None:
        parts.append(f"exception={type(exc).__name__}: {exc}")
    logger.error(" | ".join(parts))
