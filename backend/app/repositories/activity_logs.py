from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import new_id, now_iso


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
