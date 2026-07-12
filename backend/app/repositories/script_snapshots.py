from copy import deepcopy

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import new_id, now_iso
from app.models.script_validate import normalize_script, validate_script
from app.repositories.projects import get_project
from app.services.audit_log import record_mutation, script_slice

SNAPSHOT_REASONS = {
    "manual_save",
    "auto_save",
    "before_map_update",
    "before_expert_apply",
    "after_expert_apply",
    "brand_feedback_sync",
    "import",
    "rollback",
}


async def snapshot_before_map_update(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
) -> dict | None:
    return await create_script_snapshot(db, project_id, user_id, reason="before_map_update")


def serialize_snapshot(document: dict) -> dict:
    document["snapshot_id"] = str(document.pop("_id"))
    return document


async def list_script_snapshots(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    limit: int = 50,
) -> list[dict]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return []

    cursor = (
        db.script_snapshots.find({"project_id": project_id, "user_id": user_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    snapshots = []
    async for document in cursor:
        snapshots.append(
            {
                "snapshot_id": str(document["_id"]),
                "project_id": document["project_id"],
                "reason": document.get("reason", "manual_save"),
                "script_version_id": document.get("script_version_id"),
                "created_at": document.get("created_at"),
            }
        )
    return snapshots


async def create_script_snapshot(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    reason: str = "manual_save",
    script: dict | None = None,
) -> dict | None:
    if reason not in SNAPSHOT_REASONS:
        raise ValueError(f"Invalid snapshot reason: {reason}")

    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    source_script = script if script is not None else project["current_script"]
    normalized = normalize_script(source_script)
    validate_script(normalized)

    script_version_id = new_id("script_ver")
    snapshot_id = new_id("snapshot")
    created_at = now_iso()
    document = {
        "_id": snapshot_id,
        "project_id": project_id,
        "user_id": user_id,
        "script_version_id": script_version_id,
        "reason": reason,
        "script": deepcopy(normalized),
        "created_at": created_at,
    }
    await db.script_snapshots.insert_one(document)

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": {"current_script_version_id": script_version_id, "updated_at": created_at}},
    )

    return {
        "snapshot_id": snapshot_id,
        "project_id": project_id,
        "script_version_id": script_version_id,
        "reason": reason,
        "created_at": created_at,
    }


async def restore_script_snapshot(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    snapshot_id: str,
) -> dict | None:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return None

    snapshot = await db.script_snapshots.find_one(
        {"_id": snapshot_id, "project_id": project_id, "user_id": user_id}
    )
    if snapshot is None:
        raise ValueError("Snapshot not found")

    before_script = script_slice(project["current_script"])
    restored_script = normalize_script(snapshot["script"])
    validate_script(restored_script)
    restored_script["updated_at"] = now_iso()

    from app.models.artifact_stale import mark_script_changed, stale_set_fields

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "current_script": restored_script,
                "current_script_version_id": snapshot["script_version_id"],
                "updated_at": restored_script["updated_at"],
                **stale_set_fields(mark_script_changed()),
            }
        },
    )
    await record_mutation(
        db,
        action="script.snapshot.restore",
        user_id=user_id,
        project_id=project_id,
        before={"script": before_script},
        after={"script": script_slice(restored_script)},
        meta={"snapshot_id": snapshot_id, "reason": snapshot.get("reason")},
    )
    return await get_project(db, project_id, user_id)
