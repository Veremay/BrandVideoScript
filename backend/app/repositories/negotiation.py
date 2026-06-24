from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.script import now_iso
from app.repositories.projects import get_project
from app.services.agents.expert_agent import run_expert_generate_negotiation


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
    return {
        "project": updated,
        "negotiation_preparation": prep,
        "assistant_reply": result.get("assistant_reply", ""),
    }
