from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import new_id, now_iso
from app.services.app_log import activity_log_enabled, log_error, ui_activity_log_enabled

_HTTP_SKIP_EXACT = frozenset({"/api/health", "/health", "/openapi.json", "/docs", "/redoc"})
_HTTP_SKIP_PREFIXES = ("/docs/", "/redoc/")
_HTTP_SKIP_SUFFIXES = ("/activity-logs/batch",)


def should_persist_http_path(path: str) -> bool:
    if path in _HTTP_SKIP_EXACT:
        return False
    if any(path.startswith(prefix) for prefix in _HTTP_SKIP_PREFIXES):
        return False
    if any(path.endswith(suffix) for suffix in _HTTP_SKIP_SUFFIXES):
        return False
    return True


def build_activity_event(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_id: str,
    user_id: str | None = None,
    project_id: str | None = None,
    share_token: str | None = None,
    client_ip: str | None = None,
    query_params: dict[str, str] | None = None,
    meta: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    action = f"{method} {path}"
    event: dict[str, Any] = {
        "event_id": new_id("evt"),
        "event_type": "http",
        "ts": now_iso(),
        "action": action,
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "request_id": request_id,
        "source": "api",
    }
    if user_id:
        event["user_id"] = user_id
    if project_id:
        event["project_id"] = project_id
    if share_token:
        event["share_token"] = share_token
    if client_ip:
        event["client_ip"] = client_ip
    if query_params:
        event["query_params"] = query_params
    if meta:
        event["meta"] = meta
    if error:
        event["error"] = error
    return event


async def insert_activity_log(db: AsyncIOMotorDatabase, event: dict[str, Any]) -> None:
    await db.activity_logs.insert_one(event)


_ALLOWED_UI_ACTIONS = frozenset({"ui.click", "ui.keydown", "ui.track"})
_MAX_UI_BATCH = 50
_MAX_UI_META_KEYS = 24
_MAX_UI_META_VALUE_LEN = 240


def build_ui_activity_event(
    *,
    project_id: str,
    user_id: str,
    action: str,
    client_ts: str | None = None,
    session_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_id": new_id("evt"),
        "event_type": "ui",
        "ts": now_iso(),
        "action": action,
        "user_id": user_id,
        "project_id": project_id,
        "source": "frontend",
    }
    if client_ts:
        event["client_ts"] = client_ts
    if session_id:
        event["session_id"] = session_id
    if meta:
        event["meta"] = meta
    return event


def _sanitize_ui_meta(meta: dict[str, Any] | None) -> dict[str, Any] | None:
    if not meta:
        return None
    cleaned: dict[str, Any] = {}
    for index, (key, value) in enumerate(meta.items()):
        if index >= _MAX_UI_META_KEYS:
            break
        if value is None or value == "" or value == [] or value == {}:
            continue
        if isinstance(value, (bool, int, float)):
            cleaned[str(key)[:64]] = value
            continue
        text = str(value)
        if len(text) > _MAX_UI_META_VALUE_LEN:
            text = f"{text[:_MAX_UI_META_VALUE_LEN]}…"
        cleaned[str(key)[:64]] = text
    return cleaned or None


async def insert_ui_activity_logs_batch(
    db: AsyncIOMotorDatabase,
    *,
    project_id: str,
    user_id: str,
    events: list[dict[str, Any]],
) -> int:
    """Persist a batch of frontend UI events. Returns number inserted."""
    if not ui_activity_log_enabled() or not events:
        return 0

    documents: list[dict[str, Any]] = []
    for raw in events[:_MAX_UI_BATCH]:
        action = str(raw.get("action") or "ui.click").strip()
        if action not in _ALLOWED_UI_ACTIONS:
            action = "ui.click"
        client_ts = raw.get("client_ts")
        session_id = raw.get("session_id")
        meta = _sanitize_ui_meta(raw.get("meta") if isinstance(raw.get("meta"), dict) else None)
        documents.append(
            build_ui_activity_event(
                project_id=project_id,
                user_id=user_id,
                action=action,
                client_ts=str(client_ts).strip() if isinstance(client_ts, str) and client_ts.strip() else None,
                session_id=str(session_id).strip()[:80] if isinstance(session_id, str) and session_id.strip() else None,
                meta=meta,
            )
        )

    if not documents:
        return 0
    try:
        await db.activity_logs.insert_many(documents, ordered=False)
    except Exception as exc:
        log_error("Failed to persist UI activity log batch", exc=exc, project_id=project_id)
        raise
    return len(documents)


async def persist_http_activity_log(
    db: AsyncIOMotorDatabase | None,
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_id: str,
    user_id: str | None = None,
    project_id: str | None = None,
    share_token: str | None = None,
    client_ip: str | None = None,
    query_params: dict[str, str] | None = None,
    meta: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Persist an HTTP access event into activity_logs (same collection as mutations)."""
    if not activity_log_enabled() or not should_persist_http_path(path) or db is None:
        return
    try:
        event = build_activity_event(
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            request_id=request_id,
            user_id=user_id,
            project_id=project_id,
            share_token=share_token,
            client_ip=client_ip,
            query_params=query_params,
            meta=meta,
            error=error,
        )
        await insert_activity_log(db, event)
    except Exception as exc:
        log_error(
            "Failed to persist HTTP activity log",
            exc=exc,
            method=method,
            path=path,
            project_id=project_id,
        )


def serialize_activity_event(document: dict[str, Any]) -> dict[str, Any]:
    event = {key: value for key, value in document.items() if key != "_id"}
    if "_id" in document and "event_id" not in event:
        event["event_id"] = str(document["_id"])
    return event


async def list_project_activity_logs(
    db: AsyncIOMotorDatabase,
    project_id: str,
    *,
    event_type: str | None = None,
    action: str | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"project_id": project_id}
    if event_type:
        query["event_type"] = event_type
    if action:
        query["action"] = action

    cursor = db.activity_logs.find(query).sort("ts", 1).limit(limit)
    return [serialize_activity_event(document) async for document in cursor]


async def ensure_activity_log_indexes(db: AsyncIOMotorDatabase) -> None:
    collection = db.activity_logs
    await collection.create_index([("ts", -1)])
    await collection.create_index([("event_type", 1), ("ts", -1)])
    await collection.create_index([("user_id", 1), ("ts", -1)])
    await collection.create_index([("project_id", 1), ("ts", -1)])
    await collection.create_index([("action", 1), ("ts", -1)])
    await collection.create_index([("request_id", 1)])
