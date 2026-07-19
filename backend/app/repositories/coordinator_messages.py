from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import new_id, now_iso


def build_coordinator_message(
    *,
    project_id: str,
    user_id: str,
    role: str,
    content: str,
    task_type: str = "user_message",
    requested_perspectives: list[str] | None = None,
    active_persona_id: str | None = None,
    quotes: list[dict[str, Any]] | None = None,
    attachments: list[dict[str, Any]] | None = None,
    related_node_ids: list[str] | None = None,
    generated_artifact_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "message_id": new_id("msg"),
        "project_id": project_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "task_type": task_type,
        "requested_perspectives": requested_perspectives or [],
        "active_persona_id": active_persona_id,
        "quotes": quotes or [],
        "attachments": attachments or [],
        "related_node_ids": related_node_ids or [],
        "generated_artifact_ids": generated_artifact_ids or [],
        "created_at": now_iso(),
    }


async def save_coordinator_message(db: AsyncIOMotorDatabase, message: dict[str, Any]) -> dict[str, Any]:
    await db.coordinator_messages.insert_one(message)
    return message


async def list_coordinator_messages(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    cursor = (
        db.coordinator_messages.find({"project_id": project_id, "user_id": user_id})
        .sort("created_at", 1)
        .limit(limit)
    )
    return [doc async for doc in cursor]
