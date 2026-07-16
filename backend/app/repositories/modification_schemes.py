from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.artifact_stale import stale_set_fields
from app.models.choice_history import record_scheme_position_usage
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
from app.services.audit_log import hunks_slice, record_mutation, script_slice


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
        nodes_by_id = {
            str(node.get("node_id")): node
            for node in (project.get("rationale_nodes") or [])
            if node.get("node_id")
        }
        choice_history = project.get("choice_history")
        for scheme in new_schemes:
            choice_history = record_scheme_position_usage(
                choice_history,
                scheme,
                nodes_by_id=nodes_by_id,
            )

        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {
                "$set": {
                    "modification_schemes": combined,
                    "choice_history": choice_history,
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
    rejected = {hunk_id for hunk_id in (rejected_hunk_ids or []) if hunk_id in hunks_by_id}

    if not accepted and not rejected:
        raise ValueError("No hunks to update")

    applied_ids: list[str] = []
    conflicts: list[dict[str, str]] = []
    new_version_id = None
    script = normalize_script(project["current_script"])

    if accepted:
        await create_script_snapshot(
            db,
            project_id,
            user_id,
            reason="before_expert_apply",
            script=script,
        )
        for hunk_id in accepted:
            if hunk_id in rejected:
                continue
            hunk = hunks_by_id[hunk_id]
            try:
                hunk = reconcile_hunk_for_apply(script, hunk)
                script = apply_hunk_to_script(script, hunk)
                hunks_by_id[hunk_id] = hunk
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

    now = now_iso()
    updated_hunks: list[dict[str, Any]] = []
    for hunk in scheme.get("hunks") or []:
        hunk_id = hunk["hunk_id"]
        base = hunks_by_id.get(hunk_id, hunk)
        if hunk_id in applied_ids:
            updated_hunks.append({**base, "decision": "accepted", "applied_at": now})
        elif hunk_id in rejected:
            updated_hunks.append({**base, "decision": "rejected", "applied_at": None})
        else:
            updated_hunks.append(base)

    pending_count = sum(1 for item in updated_hunks if item.get("decision", "pending") == "pending")
    if pending_count == 0:
        status = "applied" if any(item.get("decision") == "accepted" for item in updated_hunks) else "dismissed"
    elif applied_ids:
        status = "partially_applied"
    else:
        status = str(scheme.get("status", "draft"))

    schemes[scheme_index] = {**scheme, "hunks": updated_hunks, "status": status}
    from app.models.artifact_stale import mark_script_changed

    update_fields: dict[str, Any] = {
        "modification_schemes": schemes,
        "updated_at": script["updated_at"] if applied_ids else now,
        "stale.modification_schemes": "up_to_date",
    }
    if applied_ids:
        update_fields["current_script"] = script
        update_fields.update(stale_set_fields(mark_script_changed()))

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": update_fields},
    )

    updated = await get_project(db, project_id, user_id)
    decided_hunk_ids = [*accepted, *[hunk_id for hunk_id in rejected]]
    original_hunks = [hunk for hunk in (scheme.get("hunks") or []) if hunk.get("hunk_id") in decided_hunk_ids]
    await record_mutation(
        db,
        action="scheme.hunks.decide",
        user_id=user_id,
        project_id=project_id,
        before={
            "script": script_slice(project["current_script"]),
            "hunks": hunks_slice(original_hunks),
        },
        after={
            "script": script_slice(updated["current_script"]) if updated else None,
            "hunks": hunks_slice(updated_hunks),
        },
        meta={
            "scheme_id": scheme_id,
            "accepted_hunk_ids": accepted,
            "rejected_hunk_ids": sorted(rejected),
            "applied_hunk_ids": applied_ids,
            "conflicts": conflicts,
        },
    )
    return {
        "project": updated,
        "applied_hunk_ids": applied_ids,
        "applied_hunk_count": len(applied_ids),
        "conflicts": conflicts,
        "snapshot_script_version_id": new_version_id.get("script_version_id") if new_version_id else None,
    }
