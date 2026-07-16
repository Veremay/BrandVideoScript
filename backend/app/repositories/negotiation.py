from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import now_iso
from app.repositories.projects import get_project
from app.services.agents.expert_agent import run_expert_generate_negotiation
from app.services.audit_log import (
    negotiation_preparation_slice,
    nodes_slice,
    record_mutation,
    script_slice,
)


async def generate_negotiation_preparation(
    db: AsyncIOMotorDatabase,
    project_id: str,
    user_id: str,
    *,
    message: str | None = None,
) -> dict[str, Any]:
    project = await get_project(db, project_id, user_id)
    if project is None:
        raise ValueError("Project not found")

    before_prep = negotiation_preparation_slice(project.get("negotiation_preparation"))
    support_nodes = [
        node
        for node in (project.get("rationale_nodes") or [])
        if node.get("in_communication_support_queue")
        or node.get("node_id") in set(project.get("communication_support_queue") or [])
    ]
    considered_nodes = [
        node
        for node in (project.get("rationale_nodes") or [])
        if node.get("in_consideration_queue")
        or node.get("node_id") in set(project.get("consideration_queue") or [])
    ]

    await db.projects.update_one(
        {"_id": project_id, "user_id": user_id},
        {"$set": {"stale.negotiation_preparation": "generating", "updated_at": now_iso()}},
    )

    try:
        result = await run_expert_generate_negotiation(project, message=message)
        prep = result.get("negotiation_preparation")
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {
                "$set": {
                    "negotiation_preparation": prep,
                    "stale.negotiation_preparation": "up_to_date",
                    "updated_at": now_iso(),
                }
            },
        )
    except Exception:
        await db.projects.update_one(
            {"_id": project_id, "user_id": user_id},
            {"$set": {"stale.negotiation_preparation": "failed", "updated_at": now_iso()}},
        )
        raise

    updated = await get_project(db, project_id, user_id)
    await record_mutation(
        db,
        action="negotiation.generate",
        user_id=user_id,
        project_id=project_id,
        before={
            "negotiation_preparation": before_prep,
            "script": script_slice(project.get("current_script")),
            "support_nodes": nodes_slice(support_nodes),
            "considered_nodes": nodes_slice(considered_nodes),
        },
        after={
            "negotiation_preparation": negotiation_preparation_slice(prep),
            "script": script_slice(updated.get("current_script") if updated else None),
            "support_nodes": nodes_slice(support_nodes),
            "considered_nodes": nodes_slice(considered_nodes),
        },
        meta={"message": (message or "")[:500]},
    )
    return {
        "project": updated,
        "negotiation_preparation": prep,
        "assistant_reply": result.get("assistant_reply", ""),
    }
