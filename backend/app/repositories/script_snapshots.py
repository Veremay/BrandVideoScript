from copy import deepcopy
from typing import Iterable

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import new_id, now_iso


SNAPSHOT_REASONS = {
    "manual_save",
    "before_expert_apply",
    "after_expert_apply",
    "before_restore",
    "import",
}


def build_snapshot(
    *,
    project_id: str,
    user_id: str,
    reason: str,
    script: dict,
    suggestion_id: str | None = None,
    applied_hunk_ids: Iterable[str] | None = None,
) -> dict:
    if reason not in SNAPSHOT_REASONS:
        raise ValueError("Invalid snapshot reason")
    if not isinstance(script, dict):
        raise ValueError("Snapshot script must be a dict")

    return {
        "_id": new_id("snapshot"),
        "project_id": project_id,
        "user_id": user_id,
        "reason": reason,
        "suggestion_id": suggestion_id,
        "applied_hunk_ids": list(applied_hunk_ids or []),
        "script": deepcopy(script),
        "created_at": now_iso(),
    }


def serialize_snapshot(document: dict) -> dict:
    document["_id"] = str(document["_id"])
    return document


def serialize_snapshot_summary(document: dict) -> dict:
    """Return snapshot metadata without the full script payload."""
    return {
        "_id": str(document["_id"]),
        "project_id": document.get("project_id"),
        "user_id": document.get("user_id"),
        "reason": document.get("reason"),
        "suggestion_id": document.get("suggestion_id"),
        "applied_hunk_ids": list(document.get("applied_hunk_ids") or []),
        "created_at": document.get("created_at"),
    }


async def create_snapshot(
    db: AsyncIOMotorDatabase,
    *,
    project_id: str,
    user_id: str,
    reason: str,
    script: dict,
    suggestion_id: str | None = None,
    applied_hunk_ids: Iterable[str] | None = None,
) -> dict:
    snapshot = build_snapshot(
        project_id=project_id,
        user_id=user_id,
        reason=reason,
        script=script,
        suggestion_id=suggestion_id,
        applied_hunk_ids=applied_hunk_ids,
    )
    await db.script_snapshots.insert_one(snapshot)
    return serialize_snapshot(snapshot)


async def list_snapshots(
    db: AsyncIOMotorDatabase,
    *,
    project_id: str,
    user_id: str,
    limit: int = 20,
) -> list[dict]:
    cursor = (
        db.script_snapshots.find(
            {"project_id": project_id, "user_id": user_id},
            projection={"script": 0},
        )
        .sort("created_at", -1)
        .limit(limit)
    )
    return [serialize_snapshot_summary(document) async for document in cursor]


async def get_snapshot(
    db: AsyncIOMotorDatabase,
    *,
    project_id: str,
    user_id: str,
    snapshot_id: str,
) -> dict | None:
    document = await db.script_snapshots.find_one(
        {"_id": snapshot_id, "project_id": project_id, "user_id": user_id}
    )
    return serialize_snapshot(document) if document else None
