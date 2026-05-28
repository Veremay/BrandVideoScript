from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.artifact_stale import stale_set_fields
from app.models.modification_scheme_ops import (
    apply_hunk_to_script,
    normalize_scheme,
    reconcile_hunk_for_apply,
)
from app.models.script import now_iso
from app.models.script_validate import normalize_script, validate_script
from app.repositories.projects import get_project
from app.repositories.script_snapshots import create_script_snapshot
from app.services.agents.expert_agent import run_expert_generate_modification_schemes


async def list_modification_schemes(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
) -> list[dict[str, Any]]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        return []
    return list(project.get("modification_schemes") or [])


async def generate_modification_schemes(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    target_issue_ids: list[str] | None = None,
    target_position_ids: list[str] | None = None,
    user_message: str | None = None,
) -> dict[str, Any]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": {"stale.modification_schemes": "generating", "updated_at": now_iso()}},
    )

    try:
        result = await run_expert_generate_modification_schemes(
            project,
            target_issue_ids=target_issue_ids,
            target_position_ids=target_position_ids,
            user_message=user_message,
        )
        new_schemes = (result.get("modification_schemes") or [])[:1]
        combined = new_schemes

        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {
                "$set": {
                    "modification_schemes": combined,
                    "stale.modification_schemes": "up_to_date",
                    "updated_at": now_iso(),
                }
            },
        )
    except Exception:
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {"$set": {"stale.modification_schemes": "failed", "updated_at": now_iso()}},
        )
        raise

    updated = await get_project(db, project_id, user_id)
    return {
        "project": updated,
        "schemes": new_schemes,
        "assistant_reply": result.get("assistant_reply", ""),
    }


async def apply_modification_scheme_hunks(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    scheme_id: str,
    *,
    accepted_hunk_ids: list[str],
    rejected_hunk_ids: list[str] | None = None,
) -> dict[str, Any]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")

    schemes = list(project.get("modification_schemes") or [])
    scheme_index = next((index for index, item in enumerate(schemes) if item.get("scheme_id") == scheme_id), None)
    if scheme_index is None:
        raise ValueError("Modification scheme not found")

    scheme = schemes[scheme_index]
    hunks_by_id = {hunk["hunk_id"]: hunk for hunk in scheme.get("hunks") or []}
    accepted = [hunk_id for hunk_id in accepted_hunk_ids if hunk_id in hunks_by_id]
    rejected = set(rejected_hunk_ids or [])

    if not accepted:
        raise ValueError("No accepted hunks to apply")

    script = normalize_script(project["current_script"])
    await create_script_snapshot(
        db,
        project_id,
        user_id,
        reason="before_expert_apply",
        script=script,
    )

    applied_ids: list[str] = []
    conflicts: list[dict[str, str]] = []
    for hunk_id in accepted:
        if hunk_id in rejected:
            continue
        hunk = hunks_by_id[hunk_id]
        try:
            hunk = reconcile_hunk_for_apply(script, hunk)
            script = apply_hunk_to_script(script, hunk)
            applied_ids.append(hunk_id)
        except ValueError as exc:
            conflicts.append({"hunk_id": hunk_id, "message": str(exc)})

    if not applied_ids:
        raise ValueError(conflicts[0]["message"] if conflicts else "No hunks could be applied")

    script["updated_at"] = now_iso()
    validate_script(script)
    new_version_id = await create_script_snapshot(
        db,
        project_id,
        user_id,
        reason="after_expert_apply",
        script=script,
    )

    total_hunks = len(hunks_by_id)
    if len(applied_ids) >= total_hunks:
        status = "applied"
    else:
        status = "partially_applied"

    schemes[scheme_index] = {**scheme, "status": status}
    from app.models.artifact_stale import mark_script_changed

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {
            "$set": {
                "current_script": script,
                "modification_schemes": schemes,
                "updated_at": script["updated_at"],
                **stale_set_fields(mark_script_changed()),
                "stale.modification_schemes": "up_to_date",
            }
        },
    )

    updated = await get_project(db, project_id, user_id)
    return {
        "project": updated,
        "applied_hunk_ids": applied_ids,
        "applied_hunk_count": len(applied_ids),
        "conflicts": conflicts,
        "snapshot_script_version_id": new_version_id.get("script_version_id") if new_version_id else None,
    }
